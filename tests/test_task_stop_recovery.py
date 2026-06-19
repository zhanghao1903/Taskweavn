from __future__ import annotations

from datetime import UTC, datetime, timedelta

from taskweavn.server.task_stop_recovery import (
    CompositeSnapshotRecoveryService,
    DefaultTaskStopRecoveryService,
)
from taskweavn.task.bus import InMemoryTaskBus
from taskweavn.task.models import TaskDomain, TaskStatus

NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


def test_task_stop_recovery_fails_stale_interrupted_running_task() -> None:
    bus = InMemoryTaskBus(
        [
            _task(
                "task-1",
                interrupt_requested=True,
                interrupt_requested_at=NOW - timedelta(minutes=1),
                status="running",
            )
        ]
    )
    committed: list[TaskDomain] = []
    recovery = DefaultTaskStopRecoveryService(
        task_bus=bus,
        stale_after=timedelta(seconds=45),
        now_provider=lambda: NOW,
        on_task_lifecycle_committed=committed.append,
    )

    result = recovery.recover_session("s1")
    recovered = bus.get("s1", "task-1")

    assert result.recovered_task_ids == ("task-1",)
    assert recovered is not None
    assert recovered.status == "failed"
    assert recovered.interrupt_requested is True
    assert recovered.error_ref == (
        "cancelled: user requested stop; safe_point=snapshot_recovery"
    )
    assert committed == [recovered]


def test_task_stop_recovery_leaves_recent_interrupted_task_running() -> None:
    bus = InMemoryTaskBus(
        [
            _task(
                "task-1",
                interrupt_requested=True,
                interrupt_requested_at=NOW,
                status="running",
            )
        ]
    )
    recovery = DefaultTaskStopRecoveryService(
        task_bus=bus,
        stale_after=timedelta(days=1),
        now_provider=lambda: NOW + timedelta(seconds=1),
    )

    result = recovery.recover_session("s1")
    recovered = bus.get("s1", "task-1")

    assert result.recovered_task_ids == ()
    assert recovered is not None
    assert recovered.status == "running"
    assert recovered.interrupt_requested is True


def test_task_stop_recovery_skips_running_task_without_interrupt() -> None:
    bus = InMemoryTaskBus([_task("task-1", status="running")])
    recovery = DefaultTaskStopRecoveryService(
        task_bus=bus,
        stale_after=timedelta(0),
        now_provider=lambda: NOW,
    )

    result = recovery.recover_session("s1")
    recovered = bus.get("s1", "task-1")

    assert result.recovered_task_ids == ()
    assert recovered is not None
    assert recovered.status == "running"
    assert recovered.interrupt_requested is False


def test_composite_snapshot_recovery_runs_services_in_order() -> None:
    calls: list[str] = []
    composite = CompositeSnapshotRecoveryService(
        _RecoveryRecorder("first", calls),
        None,
        _RecoveryRecorder("second", calls),
    )

    result = composite.recover_session("s1")

    assert calls == ["first:s1", "second:s1"]
    assert result == ("first-result", "second-result")


class _RecoveryRecorder:
    def __init__(self, name: str, calls: list[str]) -> None:
        self._name = name
        self._calls = calls

    def recover_session(self, session_id: str) -> str:
        self._calls.append(f"{self._name}:{session_id}")
        return f"{self._name}-result"


def _task(
    task_id: str,
    *,
    interrupt_requested: bool = False,
    interrupt_requested_at: datetime | None = None,
    status: TaskStatus = "pending",
) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        root_id=task_id,
        intent=f"Run {task_id}",
        required_capability="general",
        created_by="test",
        status=status,
        claimed_by="default_agent" if status == "running" else None,
        interrupt_reason="user requested stop" if interrupt_requested else None,
        interrupt_request_id="stop-1" if interrupt_requested else None,
        interrupt_requested=interrupt_requested,
        interrupt_requested_at=interrupt_requested_at,
        interrupt_requested_by="user" if interrupt_requested else None,
        started_at=NOW if status == "running" else None,
    )
