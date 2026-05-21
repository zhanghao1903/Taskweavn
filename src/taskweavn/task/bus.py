"""TaskBus publish and execution lifecycle boundary for published Task facts."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol, runtime_checkable

from taskweavn.task.models import TaskDomain
from taskweavn.task.stores import TaskStore, TaskStoreError


@runtime_checkable
class TaskBus(Protocol):
    """Published Task state authority.

    The bus owns published Task lifecycle transitions. It deliberately keeps
    the state machine small: pending -> running -> done/failed. Higher-level
    retry creates a new Task through TaskPublisher; skip is represented as a
    failed terminal Task with a user-visible reason.
    """

    def publish(self, task: TaskDomain) -> TaskDomain: ...

    def claim_next(
        self,
        session_id: str,
        *,
        capability: str,
        agent_id: str,
    ) -> TaskDomain | None: ...

    def complete(
        self,
        session_id: str,
        task_id: str,
        *,
        result_ref: str | None = None,
    ) -> TaskDomain: ...

    def fail(
        self,
        session_id: str,
        task_id: str,
        *,
        error_ref: str,
    ) -> TaskDomain: ...

    def skip(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
    ) -> TaskDomain: ...

    def get(self, session_id: str, task_id: str) -> TaskDomain | None: ...

    def list_for_session(self, session_id: str) -> list[TaskDomain]: ...

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]: ...


class InMemoryTaskBus:
    """Process-local TaskBus materialized view for publisher tests."""

    def __init__(self, tasks: list[TaskDomain] | None = None) -> None:
        self._lock = RLock()
        self._tasks: dict[tuple[str, str], TaskDomain] = {}
        self._children: dict[tuple[str, str | None], list[str]] = defaultdict(list)
        for task in tasks or []:
            self._load(task)

    def publish(self, task: TaskDomain) -> TaskDomain:
        if task.status != "pending":
            raise TaskStoreError("published tasks must enter TaskBus as pending")
        return self._load(task)

    def claim_next(
        self,
        session_id: str,
        *,
        capability: str,
        agent_id: str,
    ) -> TaskDomain | None:
        if not capability.strip():
            raise TaskStoreError("claim capability must not be empty")
        if not agent_id.strip():
            raise TaskStoreError("claim agent_id must not be empty")
        with self._lock:
            candidates = sorted(
                (
                    task
                    for task in self._tasks.values()
                    if task.session_id == session_id
                    and task.status == "pending"
                    and task.required_capability == capability
                    and self._parent_is_done(task)
                ),
                key=lambda task: (task.created_at, task.order_index, task.task_id),
            )
            if not candidates:
                return None
            task = candidates[0]
            updated = task.model_copy(
                update={
                    "status": "running",
                    "claimed_by": agent_id,
                    "started_at": _utcnow(),
                }
            )
            self._tasks[(session_id, task.task_id)] = updated
            return updated

    def complete(
        self,
        session_id: str,
        task_id: str,
        *,
        result_ref: str | None = None,
    ) -> TaskDomain:
        return self._transition_running(
            session_id,
            task_id,
            status="done",
            result_ref=result_ref,
            error_ref=None,
        )

    def fail(
        self,
        session_id: str,
        task_id: str,
        *,
        error_ref: str,
    ) -> TaskDomain:
        if not error_ref.strip():
            raise TaskStoreError("failed task requires error_ref")
        return self._transition_running(
            session_id,
            task_id,
            status="failed",
            result_ref=None,
            error_ref=error_ref,
        )

    def skip(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
    ) -> TaskDomain:
        if not reason.strip():
            raise TaskStoreError("skipped task requires reason")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status not in {"pending", "running"}:
                raise TaskStoreError(
                    f"only pending or running tasks can be skipped; got {task.status}"
                )
            updated = task.model_copy(
                update={
                    "status": "failed",
                    "error_ref": f"skipped: {reason}",
                    "completed_at": _utcnow(),
                }
            )
            self._tasks[(session_id, task_id)] = updated
            return updated

    def _load(self, task: TaskDomain) -> TaskDomain:
        key = (task.session_id, task.task_id)
        with self._lock:
            if key in self._tasks:
                raise TaskStoreError(f"task {task.task_id!r} already exists")
            if task.parent_id is not None:
                parent = self._tasks.get((task.session_id, task.parent_id))
                if parent is None:
                    raise TaskStoreError(f"parent task {task.parent_id!r} not found")
                if parent.root_id != task.root_id:
                    raise TaskStoreError("child task root_id must match parent root_id")
            self._tasks[key] = task
            self._children[(task.session_id, task.parent_id)].append(task.task_id)
            return task

    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        with self._lock:
            return self._tasks.get((session_id, task_id))

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        with self._lock:
            return sorted(
                (task for task in self._tasks.values() if task.session_id == session_id),
                key=lambda task: (task.created_at, task.order_index, task.task_id),
            )

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        with self._lock:
            task_ids = self._children.get((session_id, parent_id), [])
            return sorted(
                (self._tasks[(session_id, task_id)] for task_id in task_ids),
                key=lambda task: (task.order_index, task.created_at, task.task_id),
            )

    def _parent_is_done(self, task: TaskDomain) -> bool:
        if task.parent_id is None:
            return True
        parent = self._tasks.get((task.session_id, task.parent_id))
        return parent is not None and parent.status == "done"

    def _transition_running(
        self,
        session_id: str,
        task_id: str,
        *,
        status: str,
        result_ref: str | None,
        error_ref: str | None,
    ) -> TaskDomain:
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "running":
                raise TaskStoreError(
                    f"only running tasks can transition to {status}; got {task.status}"
                )
            updated = task.model_copy(
                update={
                    "status": status,
                    "result_ref": result_ref,
                    "error_ref": error_ref,
                    "completed_at": _utcnow(),
                }
            )
            self._tasks[(session_id, task_id)] = updated
            return updated

    def _require_task(self, session_id: str, task_id: str) -> TaskDomain:
        task = self._tasks.get((session_id, task_id))
        if task is None:
            raise TaskStoreError(f"task {task_id!r} not found")
        return task


def _utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = ["InMemoryTaskBus", "TaskBus", "TaskStore"]
