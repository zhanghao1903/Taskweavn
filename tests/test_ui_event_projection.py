"""Tests for Plato UI event projection constructors."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from taskweavn.interaction import AgentMessage
from taskweavn.server.ui_contract import (
    UiEvent,
    audit_summary_updated,
    command_completed,
    command_failed,
    confirmation_created,
    confirmation_resolved,
    file_changes_updated,
    message_appended,
    result_updated,
    resync_required,
    session_status_changed,
    task_node_changed,
    task_tree_changed,
)
from taskweavn.task import TaskRef


def test_message_appended_maps_message_identity_and_task_ref() -> None:
    message = AgentMessage(
        message_id="message-1",
        session_id="session-1",
        task_id="draft-1",
        agent_id="user",
        message_type="informational",
        content="Please tighten this node.",
        context={"task_ref_kind": "draft"},
    )

    event = message_appended(message, cursor="cursor-1")
    payload = event.model_dump(mode="json")

    assert event.event_type == "message.appended"
    assert event.message_ids == ("message-1",)
    assert event.task_refs == (TaskRef.draft("draft-1"),)
    assert payload["taskNodeIds"] == ["draft-1"]
    assert payload["taskRefs"] == [{"kind": "draft", "id": "draft-1"}]
    assert payload["payload"] == {
        "message_type": "informational",
        "agent_id": "user",
    }


def test_confirmation_created_and_resolved_keep_parent_and_response_ids() -> None:
    parent = AgentMessage(
        message_id="confirmation-1",
        session_id="session-1",
        task_id="task-1",
        message_type="actionable",
        content="Proceed?",
        requires_response=True,
    )
    response = AgentMessage(
        message_id="response-1",
        session_id="session-1",
        task_id="task-1",
        parent_message_id="confirmation-1",
        agent_id="user",
        message_type="response",
        content="yes",
        response_source="user",
        response_value="yes",
    )

    created = confirmation_created(parent, cursor="cursor-2")
    resolved = confirmation_resolved(response, cursor="cursor-3")

    assert created.event_type == "confirmation.created"
    assert created.message_ids == ("confirmation-1",)
    assert created.payload["requires_response"] is True
    assert resolved.event_type == "confirmation.resolved"
    assert resolved.message_ids == ("confirmation-1", "response-1")
    assert resolved.payload == {
        "response_value": "yes",
        "response_source": "user",
    }


def test_task_tree_and_node_events_are_thin_invalidation_hints() -> None:
    ref = TaskRef.published("task-1")
    tree = task_tree_changed(
        "session-1",
        cursor="cursor-4",
        task_refs=(ref,),
        command_id="command-1",
        reason="published",
    )
    node = task_node_changed(
        "session-1",
        cursor="cursor-5",
        task_refs=(ref,),
        reason="status_changed",
    )

    assert tree.event_type == "task.tree.changed"
    assert tree.command_id == "command-1"
    assert tree.task_node_ids == ("task-1",)
    assert tree.payload == {"reason": "published"}
    assert node.event_type == "task.node.changed"
    assert node.task_refs == (ref,)


def test_result_file_audit_and_session_events() -> None:
    ref = TaskRef.published("task-1")

    result = result_updated(
        "session-1",
        cursor="cursor-6",
        task_ref=ref,
        result_id="result-1",
    )
    files = file_changes_updated(
        "session-1",
        cursor="cursor-7",
        task_ref=ref,
        recursive=True,
    )
    audit = audit_summary_updated("session-1", cursor="cursor-8", severity="warning")
    status = session_status_changed(
        "session-1",
        cursor="cursor-9",
        previous_status="running",
        current_status="completed",
    )

    assert result.event_type == "result.updated"
    assert result.payload["result_id"] == "result-1"
    assert files.event_type == "file_changes.updated"
    assert files.payload["recursive"] is True
    assert audit.event_type == "audit.summary_updated"
    assert audit.payload["severity"] == "warning"
    assert status.event_type == "session.status_changed"
    assert status.payload["current_status"] == "completed"


def test_command_and_resync_events() -> None:
    completed = command_completed(
        "session-1",
        cursor="cursor-10",
        command_id="command-1",
        task_refs=(TaskRef.draft("draft-1"),),
    )
    failed = command_failed(
        "session-1",
        cursor="cursor-11",
        command_id="command-2",
        message="version conflict",
        retryable=True,
    )
    resync = resync_required("session-1", cursor="cursor-12", reason="cursor_expired")

    assert completed.event_type == "command.completed"
    assert completed.command_id == "command-1"
    assert completed.task_refs == (TaskRef.draft("draft-1"),)
    assert failed.event_type == "command.failed"
    assert failed.payload == {"message": "version conflict", "retryable": True}
    assert resync.event_type == "session.resync_required"
    assert resync.payload == {"reason": "cursor_expired"}


def test_event_type_validation_still_rejects_unknown_values() -> None:
    event = resync_required("session-1", cursor="cursor-1", reason="test")
    assert event.cursor == "cursor-1"

    with pytest.raises(ValidationError):
        UiEvent(
            session_id="session-1",
            event_type="task.card.changed",  # type: ignore[arg-type]
            cursor="cursor-2",
        )
