"""Tests for server-core projection to Plato UI contract mapping."""

from __future__ import annotations

from taskweavn.interaction import AgentMessage
from taskweavn.server.ui_contract import (
    derive_task_tree_status,
    map_agent_message_view,
    map_confirmation_action_view,
    map_file_change_summary_view,
    map_result_card_view,
    map_session_message_view,
    map_task_tree_view,
)
from taskweavn.task import (
    ConfirmationActionView,
    ConfirmationOptionView,
    SessionMessageView,
    TaskCardBadges,
    TaskCardPermissions,
    TaskCardView,
    TaskFileChangeSummary,
    TaskRef,
    TaskSummaryView,
    TaskTreeView,
)


def _published_card(
    task_id: str,
    *,
    parent_id: str | None = None,
    depth: int = 0,
    status: str = "pending",
    confirmation: ConfirmationActionView | None = None,
    result_ref: str | None = None,
    error_ref: str | None = None,
) -> TaskCardView:
    ref = TaskRef.published(task_id)
    return TaskCardView(
        task_ref=ref,
        parent_ref=TaskRef.published(parent_id) if parent_id is not None else None,
        root_ref=TaskRef.published("root"),
        title=f"{task_id} title",
        intent_preview=f"{task_id} summary",
        status=status,  # type: ignore[arg-type]
        depth=depth,
        order_index=depth,
        result_ref=result_ref,
        error_ref=error_ref,
        badges=TaskCardBadges(
            pending_confirmation_count=1 if confirmation is not None else 0,
            unread_message_count=2,
            direct_file_change_count=1,
            subtree_file_change_count=3,
        ),
        permissions=TaskCardPermissions(
            can_edit=True,
            can_append_guidance=True,
            can_cancel=True,
        ),
        confirmation=confirmation,
    )


def test_map_task_tree_uses_synthetic_projection_id_and_flat_nodes() -> None:
    root = _published_card("root")
    child = _published_card("child", parent_id="root", depth=1, status="done")
    source = TaskTreeView(session_id="session-1", nodes=(root, child))

    mapped = map_task_tree_view(source)
    payload = mapped.model_dump(mode="json")

    assert mapped.id == "session:session-1:task-tree"
    assert mapped.status == "published"
    assert payload["nodes"][0]["id"] == "root"
    assert payload["nodes"][0]["status"] == "queued"
    assert payload["nodes"][0]["execution"] == "pending"
    assert payload["nodes"][1]["parentId"] == "root"
    assert payload["nodes"][0]["badges"]["subtreeFileChangeCount"] == 3
    assert payload["nodes"][0]["permissions"]["canCancel"] is True


def test_map_task_node_preserves_canonical_execution_status() -> None:
    source = TaskTreeView(
        session_id="session-1",
        nodes=(
            _published_card("pending-task", status="pending"),
            _published_card("running-task", status="running"),
            _published_card("waiting-task", status="waiting_for_user"),
            _published_card("done-task", status="done"),
            _published_card("failed-task", status="failed"),
        ),
    )

    payload = map_task_tree_view(source).model_dump(mode="json")

    assert [node["status"] for node in payload["nodes"]] == [
        "queued",
        "running",
        "waiting_user",
        "done",
        "failed",
    ]
    assert [node["execution"] for node in payload["nodes"]] == [
        "pending",
        "running",
        "waiting_for_user",
        "done",
        "failed",
    ]


def test_map_task_node_preserves_execution_result_and_error_refs() -> None:
    done = _published_card("done-task", status="done", result_ref="result:done-task")
    failed = _published_card("failed-task", status="failed", error_ref="error:failed-task")
    source = TaskTreeView(session_id="session-1", nodes=(done, failed))

    payload = map_task_tree_view(source).model_dump(mode="json")

    assert payload["nodes"][0]["status"] == "done"
    assert payload["nodes"][0]["resultRef"] == "result:done-task"
    assert payload["nodes"][0]["errorRef"] is None
    assert payload["nodes"][1]["status"] == "failed"
    assert payload["nodes"][1]["resultRef"] is None
    assert payload["nodes"][1]["errorRef"] == "error:failed-task"


def test_map_task_node_with_pending_confirmation_becomes_waiting_user() -> None:
    option = ConfirmationOptionView(
        option_id="yes-option",
        label="Yes",
        value="yes",
        is_default=True,
    )
    confirmation = ConfirmationActionView(
        confirmation_id="confirmation-1",
        task_ref=TaskRef.published("root"),
        prompt="Proceed?",
        options=(option,),
        default_option_id="yes-option",
        risk_summary="risk=0.50",
    )
    source = TaskTreeView(
        session_id="session-1",
        nodes=(_published_card("root", status="running", confirmation=confirmation),),
    )

    mapped = map_task_tree_view(source)
    mapped_confirmation = map_confirmation_action_view(
        confirmation,
        session_id="session-1",
    )

    assert mapped.nodes[0].status == "waiting_user"
    assert mapped.status == "running"
    assert mapped_confirmation.task_node_id == "root"
    assert mapped_confirmation.default_option_value == "yes"
    assert mapped_confirmation.options[0].tone == "primary"
    assert mapped_confirmation.risk_label == "risk=0.50"


def test_map_session_message_types_to_contract_kinds() -> None:
    user_message = SessionMessageView(
        message_id="message-1",
        session_id="session-1",
        task_ref=TaskRef.published("root"),
        message_type="user",
        content_summary="Use safer defaults.",
        related_action_id="command-1",
    )
    confirmation_message = SessionMessageView(
        message_id="message-2",
        session_id="session-1",
        task_ref=TaskRef.published("root"),
        message_type="confirmation",
        content_summary="Proceed?",
        related_confirmation_id="confirmation-1",
    )

    mapped_user = map_session_message_view(user_message)
    mapped_confirmation = map_session_message_view(confirmation_message)

    assert mapped_user.kind == "informational"
    assert mapped_user.task_node_id == "root"
    assert mapped_user.related_command_id == "command-1"
    assert mapped_confirmation.kind == "actionable"
    assert mapped_confirmation.title == "Confirmation required"
    assert mapped_confirmation.related_confirmation_id == "confirmation-1"


def test_map_file_changes_preserves_recursive_rollup_and_normalizes_unknown() -> None:
    direct = TaskFileChangeSummary(
        owner_task_ref=TaskRef.published("root"),
        path="README.md",
        change_type="modified",
        summary="Updated docs.",
    )
    unknown = TaskFileChangeSummary(
        owner_task_ref=TaskRef.published("child"),
        path="notes.txt",
        change_type="unknown",
        summary="Detected change.",
        from_subtree=True,
    )

    mapped = map_file_change_summary_view(
        (direct, unknown),
        session_id="session-1",
        task_ref=TaskRef.published("root"),
        recursive=True,
    )

    assert mapped.task_node_id == "root"
    assert mapped.recursive is True
    assert mapped.summary == "2 files changed."
    assert mapped.changed_files[1].change_type == "modified"
    assert mapped.changed_files[1].owner_task_node_id == "child"


def test_map_result_card_adds_failure_followup_and_artifact_sections() -> None:
    source = TaskSummaryView(
        task_ref=TaskRef.published("root"),
        summary="Implementation finished with warnings.",
        failure_reason="One optional check failed.",
        follow_up_suggestions=("Retry optional check",),
        artifact_refs=("artifact://report",),
    )

    mapped = map_result_card_view(source, session_id="session-1")

    assert mapped.id == "result:published:root"
    assert mapped.task_node_id == "root"
    assert mapped.summary == "Implementation finished with warnings."
    assert [section.title for section in mapped.sections] == [
        "Failure reason",
        "Follow-up suggestions",
        "Artifacts",
    ]


def test_map_agent_message_uses_execution_context_title_and_error_kind() -> None:
    message = AgentMessage(
        session_id="session-1",
        task_id="task-1",
        message_type="informational",
        content="Task execution failed.",
        context={
            "task_ref_kind": "published",
            "title": "Task failed",
            "ui_kind": "error",
        },
    )

    mapped = map_agent_message_view(message)

    assert mapped.kind == "error"
    assert mapped.title == "Task failed"
    assert mapped.task_node_id == "task-1"
    assert mapped.body == "Task execution failed."


def test_derive_task_tree_status_priority() -> None:
    assert derive_task_tree_status(()) == "draft"
    assert (
        derive_task_tree_status(
            map_task_tree_view(TaskTreeView(session_id="s1")).nodes
        )
        == "draft"
    )
    assert (
        map_task_tree_view(
            TaskTreeView(session_id="s1", nodes=(_published_card("root", status="done"),))
        ).status
        == "completed"
    )
    assert (
        map_task_tree_view(
            TaskTreeView(
                session_id="s1",
                nodes=(_published_card("root", status="failed"),),
            )
        ).status
        == "failed"
    )
