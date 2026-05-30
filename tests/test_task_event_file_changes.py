"""Tests for deterministic file-change projection from task EventStream facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from taskweavn.core import SqliteEventStream, WorkspaceLayout
from taskweavn.task import EventStreamFileChangeStore, TaskRef
from taskweavn.tools.fs import FileWriteObservation, WriteFileAction
from taskweavn.types.code_action import CodeExecutionObservation, FileChange

NOW = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)


def test_event_stream_file_change_store_projects_write_file_observations(
    tmp_path: Any,
) -> None:
    layout = WorkspaceLayout(tmp_path)
    action = WriteFileAction(path="src/App.tsx", content="hello", event_id="action-1")
    observation = FileWriteObservation(
        action_id=action.event_id,
        event_id="obs-1",
        timestamp=NOW,
        path="src/App.tsx",
        bytes_written=5,
        created=True,
    )
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        stream.append(action, task_id="task-1")
        stream.append(observation, task_id="task-1")
        stream.append(
            FileWriteObservation(
                action_id="other-action",
                event_id="other-obs",
                timestamp=NOW,
                path="other.txt",
                bytes_written=4,
                created=True,
            ),
            task_id="other-task",
        )

    changes = EventStreamFileChangeStore(layout).list_for_task("session-1", "task-1")

    assert len(changes) == 1
    assert changes[0].owner_task_ref == TaskRef.published("task-1")
    assert changes[0].path == "src/App.tsx"
    assert changes[0].change_type == "created"
    assert changes[0].summary == "Created src/App.tsx (5 bytes written)."


def test_event_stream_file_change_store_projects_code_execution_file_facts(
    tmp_path: Any,
) -> None:
    layout = WorkspaceLayout(tmp_path)
    observation = CodeExecutionObservation(
        action_id="code-action",
        event_id="code-obs",
        timestamp=NOW,
        intent="update files",
        exit_code=0,
        stdout="",
        stderr="",
        duration_ms=1.0,
        declared_changes=[
            FileChange(
                path="declared.py",
                change_type="modified",
                before_sha256="before",
                after_sha256="after",
                size_delta=12,
            )
        ],
        undeclared_changes=[
            FileChange(
                path="extra.py",
                change_type="created",
                before_sha256=None,
                after_sha256="after",
                size_delta=8,
            )
        ],
    )
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        stream.append(observation, task_id="task-1")

    changes = EventStreamFileChangeStore(layout).list_for_task("session-1", "task-1")

    assert [change.path for change in changes] == ["declared.py", "extra.py"]
    assert changes[0].change_type == "modified"
    assert changes[0].summary == (
        "Modified declared.py (declared code execution change; size delta 12 bytes)."
    )
    assert changes[1].summary == (
        "Created extra.py (undeclared code execution change; size delta 8 bytes)."
    )


def test_event_stream_file_change_store_returns_empty_when_stream_is_missing(
    tmp_path: Any,
) -> None:
    changes = EventStreamFileChangeStore(tmp_path).list_for_task("missing", "task-1")

    assert changes == []
