"""Best-effort recovery for interrupted Tasks stuck in stopping projection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from taskweavn.observability.main_page_trace import main_page_trace
from taskweavn.task.bus import TaskBus, _task_trace_summary
from taskweavn.task.models import TaskDomain
from taskweavn.task.stores import TaskStoreError

DEFAULT_STOP_RECOVERY_GRACE = timedelta(seconds=45)


class SnapshotRecoveryService(Protocol):
    def recover_session(self, session_id: str) -> object: ...


@dataclass(frozen=True)
class TaskStopRecoveryResult:
    """Summary of one stale stop recovery pass."""

    recovered_task_ids: tuple[str, ...] = ()

    @property
    def recovered_count(self) -> int:
        return len(self.recovered_task_ids)


class CompositeSnapshotRecoveryService:
    """Run multiple best-effort snapshot recovery services in order."""

    def __init__(self, *services: SnapshotRecoveryService | None) -> None:
        self._services = tuple(service for service in services if service is not None)

    def recover_session(self, session_id: str) -> tuple[object, ...]:
        return tuple(service.recover_session(session_id) for service in self._services)


class DefaultTaskStopRecoveryService:
    """Fail stale interrupted running Tasks before projecting a snapshot.

    A normal stop remains cooperative: the AgentLoop should observe the interrupt
    at a safe point and report a cancelled failure. This recovery only prevents
    the UI from staying in ``Stopping`` when no safe-point acknowledgement arrives
    within the grace period, which can happen after dev restarts, worker crashes,
    or long non-interruptible calls.
    """

    def __init__(
        self,
        *,
        task_bus: TaskBus,
        stale_after: timedelta = DEFAULT_STOP_RECOVERY_GRACE,
        now_provider: Callable[[], datetime] | None = None,
        on_task_lifecycle_committed: Callable[[TaskDomain], None] | None = None,
    ) -> None:
        if stale_after < timedelta(0):
            raise ValueError("stale_after must be non-negative")
        self._task_bus = task_bus
        self._stale_after = stale_after
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._on_task_lifecycle_committed = on_task_lifecycle_committed

    def recover_session(self, session_id: str) -> TaskStopRecoveryResult:
        now = _as_utc(self._now_provider())
        recovered: list[TaskDomain] = []
        for task in self._task_bus.list_for_session(session_id):
            if not _needs_recovery(task, now=now, stale_after=self._stale_after):
                continue
            try:
                failed = self._task_bus.fail(
                    task.session_id,
                    task.task_id,
                    error_ref=_recovery_error_ref(task),
                )
            except TaskStoreError as exc:
                main_page_trace(
                    "task_stop_recovery.task_skipped",
                    error=type(exc).__name__,
                    message=str(exc),
                    task=_task_trace_summary(task),
                )
                continue
            recovered.append(failed)
            if self._on_task_lifecycle_committed is not None:
                self._on_task_lifecycle_committed(failed)

        result = TaskStopRecoveryResult(
            recovered_task_ids=tuple(task.task_id for task in recovered),
        )
        if result.recovered_count:
            main_page_trace(
                "task_stop_recovery.session_result",
                recovered_task_count=result.recovered_count,
                recovered_task_ids=result.recovered_task_ids,
                session_id=session_id,
            )
        return result


def _needs_recovery(
    task: TaskDomain,
    *,
    now: datetime,
    stale_after: timedelta,
) -> bool:
    if task.status != "running" or not task.interrupt_requested:
        return False
    if task.interrupt_requested_at is None:
        return True
    return now - _as_utc(task.interrupt_requested_at) >= stale_after


def _recovery_error_ref(task: TaskDomain) -> str:
    reason = (task.interrupt_reason or "user requested stop").strip()
    return f"cancelled: {reason}; safe_point=snapshot_recovery"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "CompositeSnapshotRecoveryService",
    "DEFAULT_STOP_RECOVERY_GRACE",
    "DefaultTaskStopRecoveryService",
    "TaskStopRecoveryResult",
]
