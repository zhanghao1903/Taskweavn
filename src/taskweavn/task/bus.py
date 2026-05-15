"""Minimal TaskBus publish boundary for published Task facts."""

from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Protocol, runtime_checkable

from taskweavn.task.models import TaskDomain
from taskweavn.task.stores import TaskStore, TaskStoreError


@runtime_checkable
class TaskBus(Protocol):
    """Published Task state authority.

    This first server-core boundary only models publishing and read-side
    queries. Claim/complete/fail semantics remain future TaskBus work.
    """

    def publish(self, task: TaskDomain) -> TaskDomain: ...

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


__all__ = ["InMemoryTaskBus", "TaskBus", "TaskStore"]
