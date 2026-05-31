"""Published Task retry lineage helpers."""

from __future__ import annotations

from collections.abc import Iterable

from taskweavn.task.models import TaskDomain


def retry_source_task_id(task: TaskDomain) -> str | None:
    """Return the source Task id when ``task`` is a retry attempt."""

    metadata = (
        task.dispatch_constraints.metadata
        if task.dispatch_constraints is not None
        else {}
    )
    value = metadata.get("retry_of")
    return value if isinstance(value, str) and value.strip() else None


def latest_retry_attempt(
    tasks: Iterable[TaskDomain],
    source_task_id: str,
    *,
    session_id: str | None = None,
) -> TaskDomain | None:
    """Return the latest retry attempt for a source Task, if one exists."""

    latest: TaskDomain | None = None
    for task in tasks:
        if session_id is not None and task.session_id != session_id:
            continue
        if retry_source_task_id(task) != source_task_id:
            continue
        if latest is None or (task.created_at, task.task_id) > (
            latest.created_at,
            latest.task_id,
        ):
            latest = task
    return latest


def task_effectively_done(task: TaskDomain, tasks: Iterable[TaskDomain]) -> bool:
    """Treat a failed Task as done when its latest retry attempt is done."""

    if task.status == "done":
        return True
    if task.status != "failed":
        return False
    retry = latest_retry_attempt(tasks, task.task_id, session_id=task.session_id)
    return retry is not None and retry.status == "done"


__all__ = [
    "latest_retry_attempt",
    "retry_source_task_id",
    "task_effectively_done",
]
