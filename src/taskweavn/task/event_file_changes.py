"""Project deterministic file changes from session EventStream facts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from taskweavn.core import SqliteEventStream, WorkspaceLayout
from taskweavn.task.models import TaskRef
from taskweavn.task.views import TaskFileChangeSummary
from taskweavn.tools.fs import FileWriteObservation
from taskweavn.types.base import BaseEvent
from taskweavn.types.code_action import CodeExecutionObservation, FileChange


class EventStreamFileChangeStore:
    """Read-only file change projection over session-scoped EventStreams."""

    def __init__(self, layout: WorkspaceLayout | Path) -> None:
        self._layout = layout if isinstance(layout, WorkspaceLayout) else WorkspaceLayout(layout)

    def list_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        recursive: bool = False,
    ) -> list[TaskFileChangeSummary]:
        # Recursive roll-up is owned by TaskProjectionService because it knows
        # the Task tree. This store only projects direct observed facts.
        del recursive
        db_path = self._layout.session_events_db(session_id)
        if not db_path.exists():
            return []
        with SqliteEventStream(db_path) as stream:
            changes: list[TaskFileChangeSummary] = []
            for event in stream.iter_for_task(task_id):
                changes.extend(_changes_from_event(event, task_id=task_id))
        return sorted(changes, key=lambda change: (change.recorded_at, change.change_id))


def _changes_from_event(
    event: BaseEvent,
    *,
    task_id: str,
) -> list[TaskFileChangeSummary]:
    if isinstance(event, FileWriteObservation):
        return [_summary_from_file_write(event, task_id=task_id)]
    if isinstance(event, CodeExecutionObservation):
        return [
            _summary_from_code_file_change(
                change,
                task_id=task_id,
                event_id=event.event_id,
                recorded_at=event.timestamp,
                declared=declared,
            )
            for declared, source_changes in (
                (True, event.declared_changes),
                (False, event.undeclared_changes),
            )
            for change in source_changes
        ]
    return []


def _summary_from_file_write(
    event: FileWriteObservation,
    *,
    task_id: str,
) -> TaskFileChangeSummary:
    change_type: Literal["created", "modified"] = "created" if event.created else "modified"
    verb = "Created" if event.created else "Modified"
    return TaskFileChangeSummary(
        change_id=f"{event.event_id}:{event.path}",
        owner_task_ref=TaskRef.published(task_id),
        path=event.path,
        change_type=change_type,
        summary=f"{verb} {event.path} ({event.bytes_written} bytes written).",
        recorded_at=event.timestamp,
    )


def _summary_from_code_file_change(
    change: FileChange,
    *,
    task_id: str,
    event_id: str,
    recorded_at: datetime,
    declared: bool,
) -> TaskFileChangeSummary:
    scope = "declared" if declared else "undeclared"
    return TaskFileChangeSummary(
        change_id=f"{event_id}:{scope}:{change.path}",
        owner_task_ref=TaskRef.published(task_id),
        path=change.path,
        change_type=change.change_type,
        summary=(
            f"{change.change_type.capitalize()} {change.path} "
            f"({scope} code execution change; size delta {change.size_delta} bytes)."
        ),
        recorded_at=recorded_at,
    )


__all__ = ["EventStreamFileChangeStore"]
