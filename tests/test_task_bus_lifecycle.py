"""Tests for in-memory TaskBus execution lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from taskweavn.task import InMemoryTaskBus, TaskDispatchConstraints, TaskDomain, TaskStatus


def test_in_memory_task_bus_claim_complete_fail_and_skip() -> None:
    bus = InMemoryTaskBus([
        _task("a"),
        _task("b", required_capability="special"),
        _task("c"),
    ])

    first = bus.claim_next("s1", capability="general", agent_id="agent-1")
    assert first is not None
    assert first.task_id == "a"
    assert first.status == "running"
    assert first.claimed_by == "agent-1"

    completed = bus.complete("s1", "a", result_ref="result:a")
    assert completed.status == "done"
    assert completed.result_ref == "result:a"

    second = bus.claim_next("s1", capability="general", agent_id="agent-1")
    assert second is not None
    assert second.task_id == "c"

    failed = bus.fail("s1", "c", error_ref="error:c")
    assert failed.status == "failed"
    assert failed.error_ref == "error:c"

    skipped = bus.skip("s1", "b", reason="optional")
    assert skipped.status == "failed"
    assert skipped.error_ref == "skipped: optional"


def test_in_memory_task_bus_claims_child_after_parent_retry_done() -> None:
    bus = InMemoryTaskBus(
        [
            _task("root", status="failed", created_at=_time(0)),
            _task("child", parent_id="root", root_id="root", created_at=_time(1)),
            _task(
                "retry",
                status="done",
                metadata={"retry_of": "root"},
                created_at=_time(2),
            ),
        ]
    )

    claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")

    assert claimed is not None
    assert claimed.task_id == "child"
    assert claimed.status == "running"


def test_in_memory_task_bus_latest_retry_attempt_controls_parent_dependency() -> None:
    bus = InMemoryTaskBus(
        [
            _task("root", status="failed", created_at=_time(0)),
            _task("child", parent_id="root", root_id="root", created_at=_time(1)),
            _task(
                "retry-a",
                status="done",
                metadata={"retry_of": "root"},
                created_at=_time(2),
            ),
            _task(
                "retry-b",
                metadata={"retry_of": "root"},
                created_at=_time(3),
            ),
        ]
    )

    claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")

    assert claimed is not None
    assert claimed.task_id == "retry-b"


def _task(
    task_id: str,
    *,
    required_capability: str = "general",
    status: TaskStatus = "pending",
    parent_id: str | None = None,
    root_id: str | None = None,
    metadata: dict[str, object] | None = None,
    created_at: datetime | None = None,
) -> TaskDomain:
    kwargs: dict[str, Any] = {"created_at": created_at} if created_at is not None else {}
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        parent_id=parent_id,
        root_id=root_id or task_id,
        intent=f"Do {task_id}",
        required_capability=required_capability,
        status=status,
        created_by="tester",
        dispatch_constraints=(
            TaskDispatchConstraints(metadata=metadata) if metadata is not None else None
        ),
        **kwargs,
    )


def _time(seconds: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
