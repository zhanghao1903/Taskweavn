"""Tests for Plato UI/backend contract models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from taskweavn.server.ui_contract import (
    AffectedObjectRef,
    AffectedScope,
    ApiError,
    AppendSessionInputPayload,
    CommandRequest,
    CommandResponse,
    CommandResult,
    ConfirmationActionView,
    ConfirmationOptionView,
    ConversationAskCardView,
    ConversationAskQuestionView,
    ConversationRenderView,
    GenerateTaskTreePayload,
    MainPageSnapshot,
    ObjectRef,
    ProjectSummary,
    QueryResponse,
    RefreshHint,
    SessionMessageView,
    SessionSummary,
    TaskNodeBadges,
    TaskNodeCardView,
    TaskNodePermissions,
    TaskTreeView,
    UiEvent,
    UpdateTaskNodePayload,
    WorkflowSummary,
    product_error_audit_ref_for_task,
    product_error_details_for_llm_classification,
)
from taskweavn.server.ui_contract.errors import (
    bad_request,
    command_rejected,
    internal_error,
    not_found,
)
from taskweavn.task import TaskRef

NOW = datetime(2026, 5, 20, 10, 30, tzinfo=UTC)


def _project() -> ProjectSummary:
    return ProjectSummary(id="project-local", name="Local Project")


def _workflow() -> WorkflowSummary:
    return WorkflowSummary(
        id="workflow-task-authoring",
        name="Task authoring",
        description="Turn user intent into a TaskTree.",
        input_hint="Describe the goal.",
        delivery_kind="task_tree",
    )


def _session() -> SessionSummary:
    return SessionSummary(
        id="session-1",
        project_id="project-local",
        workflow_id="workflow-task-authoring",
        name="Website session",
        status="draft_ready",
        created_at=NOW,
        updated_at=NOW,
        workspace_label="Isolated session workspace",
    )


def _task_card() -> TaskNodeCardView:
    return TaskNodeCardView(
        id="draft-1",
        task_ref=TaskRef.draft("draft-1"),
        parent_id=None,
        title="Draft homepage",
        summary="Create the first homepage draft.",
        status="draft",
        depth=0,
        order_index=0,
        badges=TaskNodeBadges(pending_confirmation_count=1),
        permissions=TaskNodePermissions(
            can_edit=True,
            can_append_guidance=True,
            can_publish=True,
        ),
        version=2,
    )


def _snapshot() -> MainPageSnapshot:
    project = _project()
    workflow = _workflow()
    session = _session()
    message = SessionMessageView(
        id="message-1",
        session_id=session.id,
        task_node_id="draft-1",
        task_ref=TaskRef.draft("draft-1"),
        kind="actionable",
        title="Confirm direction",
        body="Should Plato create the first homepage draft?",
        created_at=NOW,
        related_confirmation_id="confirmation-1",
    )
    confirmation = ConfirmationActionView(
        id="confirmation-1",
        session_id=session.id,
        task_node_id="draft-1",
        task_ref=TaskRef.draft("draft-1"),
        title="Confirm direction",
        body="Should Plato create the first homepage draft?",
        options=(
            ConfirmationOptionView(value="yes", label="Yes", tone="primary"),
            ConfirmationOptionView(value="no", label="No", tone="danger"),
        ),
        default_option_value="yes",
        status="pending",
        created_at=NOW,
    )
    return MainPageSnapshot(
        project=project,
        workflows=(workflow,),
        workflow=workflow,
        sessions=(session,),
        session=session,
        task_tree=TaskTreeView(
            id="tree-1",
            session_id=session.id,
            title="Website Task Tree",
            status="draft",
            nodes=(_task_card(),),
            version=2,
        ),
        messages=(message,),
        pending_confirmations=(confirmation,),
        cursor="cursor-1",
        generated_at=NOW,
    )


def test_contract_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ProjectSummary.model_validate(
            {
                "id": "project-local",
                "name": "Local Project",
                "extraField": True,
            }
        )


def test_contract_models_are_frozen() -> None:
    project = _project()
    with pytest.raises(ValidationError, match="frozen"):
        project.name = "Tampered"


def test_camel_case_json_serialization_and_alias_input() -> None:
    session = SessionSummary.model_validate(
        {
            "id": "session-1",
            "projectId": "project-local",
            "workflowId": "workflow-task-authoring",
            "name": "Website session",
            "status": "new",
            "createdAt": NOW.isoformat(),
            "updatedAt": NOW.isoformat(),
            "workspaceLabel": "Isolated session workspace",
        }
    )

    payload = session.model_dump(mode="json")

    assert session.project_id == "project-local"
    assert "projectId" in payload
    assert "project_id" not in payload
    assert payload["createdAt"] == "2026-05-20T10:30:00Z"


def test_conversation_ask_card_serializes_with_visibility_and_stable_identity() -> None:
    message = SessionMessageView(
        id="conversation-ask:execution:ask-1",
        session_id="session-1",
        task_node_id="task-1",
        kind="actionable",
        title="Plato question",
        body="Where should Plato deploy?",
        created_at=NOW,
        conversation_render=ConversationRenderView(
            render_kind="ask_card",
            ask_card=ConversationAskCardView(
                card_id="conversation-ask:execution:ask-1",
                domain="execution",
                status="pending",
                title="Task needs input",
                ask_id="ask-1",
                task_node_id="task-1",
                questions=(
                    ConversationAskQuestionView(
                        id="ask-1",
                        prompt="Where should Plato deploy?",
                        required=True,
                        answer_type="free_text",
                        allow_free_text=True,
                    ),
                ),
                created_at=NOW,
                can_answer=True,
            ),
        ),
        conversation_visibility="visible",
    )

    payload = message.model_dump(mode="json")

    assert payload["conversationVisibility"] == "visible"
    assert payload["conversationRender"]["renderKind"] == "ask_card"
    assert payload["conversationRender"]["askCard"]["askId"] == "ask-1"
    assert payload["conversationRender"]["askCard"]["questions"][0]["answered"] is False


def test_query_response_success_and_error_invariants() -> None:
    ok = QueryResponse[ProjectSummary](ok=True, data=_project(), error=None)
    assert ok.ok is True

    error = ApiError(code="not_found", message="session not found")
    failed = QueryResponse[ProjectSummary](ok=False, data=None, error=error)
    assert failed.error == error

    with pytest.raises(ValidationError, match="requires data"):
        QueryResponse[ProjectSummary](ok=True, data=None, error=None)
    with pytest.raises(ValidationError, match="requires error"):
        QueryResponse[ProjectSummary](ok=False, data=None, error=None)


def test_command_response_success_and_error_invariants() -> None:
    result = CommandResult(
        command_id="command-1",
        status="accepted",
        message="accepted",
        affected_task_refs=(TaskRef.draft("draft-1"),),
    )
    response = CommandResponse(ok=True, result=result, error=None)
    payload = response.model_dump(mode="json")

    assert response.result == result
    assert payload["result"]["affectedTaskRefs"] == [{"kind": "draft", "id": "draft-1"}]

    rejected = CommandResult(
        command_id="command-2",
        status="rejected",
        message="no",
    )
    with pytest.raises(ValidationError, match="accepted result"):
        CommandResponse(ok=True, result=rejected, error=None)

    error = ApiError(code="command_rejected", message="cannot edit completed task")
    failed = CommandResponse(
        ok=False,
        result=rejected,
        error=error,
        refresh=RefreshHint(wait_for_events=False),
    )
    assert failed.error == error


def test_command_result_carries_non_task_object_refs_and_scope_hints() -> None:
    result = CommandResult(
        command_id="command-rebuild",
        status="accepted",
        message="subtree regenerated",
        affected_task_refs=(TaskRef.draft("parent-1"),),
        object_refs=(
            ObjectRef(kind="raw_task", id="raw-1"),
            ObjectRef(kind="draft_tree", id="tree-1"),
        ),
        affected_objects=(
            AffectedObjectRef(
                ref=ObjectRef(kind="draft_subtree", id="parent-1"),
                impact="replaced",
                reason="Parent task intent changed.",
            ),
            AffectedObjectRef(
                ref=ObjectRef(kind="raw_task_ask", id="ask-1"),
                impact="superseded",
                reason="Subtree was regenerated from newer user guidance.",
            ),
        ),
        debug_refs={
            "sourceMessageId": "message-1",
            "authoringBatchId": "batch-1",
        },
    )
    refresh = RefreshHint(
        suggested_queries=("task.tree", "task.detail"),
        affected_task_refs=(TaskRef.draft("parent-1"),),
        affected_scopes=(
            AffectedScope(
                kind="task_subtree",
                task_ref=TaskRef.draft("parent-1"),
                reason="Subtree was regenerated.",
            ),
        ),
    )
    payload = CommandResponse(ok=True, result=result, refresh=refresh).model_dump(
        mode="json"
    )

    assert payload["result"]["objectRefs"] == [
        {"kind": "raw_task", "id": "raw-1"},
        {"kind": "draft_tree", "id": "tree-1"},
    ]
    assert payload["result"]["affectedObjects"][0] == {
        "ref": {"kind": "draft_subtree", "id": "parent-1"},
        "impact": "replaced",
        "reason": "Parent task intent changed.",
    }
    assert payload["result"]["debugRefs"]["sourceMessageId"] == "message-1"
    assert payload["refresh"]["affectedScopes"] == [
        {
            "kind": "task_subtree",
            "taskRef": {"kind": "draft", "id": "parent-1"},
            "reason": "Subtree was regenerated.",
        }
    ]

    with pytest.raises(ValidationError, match="requires task_ref"):
        AffectedScope(kind="task_subtree")


def test_error_code_enum_includes_permission_denied_and_rejects_unknown() -> None:
    error = ApiError(code="permission_denied", message="not allowed")
    assert error.code == "permission_denied"

    with pytest.raises(ValidationError):
        ApiError(code="rate_limited", message="unknown")  # type: ignore[arg-type]


def test_error_helpers_attach_product_error_metadata() -> None:
    bad = bad_request("missing input", field="prompt")
    missing = not_found("session not found", session_id="missing")
    rejected = command_rejected("cannot edit completed task")
    internal = internal_error("Unable to load snapshot", error_type="RuntimeError")

    assert bad.details["productCategory"] == "input_validation"
    assert bad.details["recoveryActions"] == ["edit_input"]
    assert bad.details["field"] == "prompt"
    assert missing.details["productCategory"] == "missing_context"
    assert rejected.details["productCategory"] == "command_conflict"
    assert internal.details["productCategory"] == "unexpected_internal"
    assert internal.details["recoveryActions"] == [
        "refresh_snapshot",
        "export_diagnostics",
    ]
    assert internal.details["error_type"] == "RuntimeError"


def test_llm_product_error_metadata_mapping() -> None:
    auth = product_error_details_for_llm_classification(
        "fatal_auth",
        diagnostic_refs={"providerName": "deepseek"},
    )
    rate = product_error_details_for_llm_classification("rate_limit", retry_count=2)
    context = product_error_details_for_llm_classification("context_limit")

    assert auth["productCategory"] == "llm_auth_or_config"
    assert auth["recoveryActions"] == ["open_settings", "export_diagnostics"]
    assert auth["diagnosticRefs"] == {"providerName": "deepseek"}
    assert rate["productCategory"] == "llm_rate_or_retry_exhausted"
    assert rate["retryCount"] == 2
    assert context["productCategory"] == "llm_context_or_capability"


def test_product_error_audit_ref_matches_audit_result_ids() -> None:
    assert product_error_audit_ref_for_task(
        session_id="session-1",
        task_id="task-1",
    ) == {
        "scope": "task",
        "sessionId": "session-1",
        "taskId": "task-1",
        "recordId": "record-result-published-task-1",
        "evidenceId": "evidence-record-result-published-task-1",
        "filter": "results",
    }


def test_ui_event_validates_type_and_serializes_aliases() -> None:
    event = UiEvent(
        event_id="event-1",
        session_id="session-1",
        event_type="message.appended",
        cursor="cursor-2",
        task_node_ids=("draft-1",),
        task_refs=(TaskRef.draft("draft-1"),),
        message_ids=("message-1",),
        command_id="command-1",
        created_at=NOW,
    )
    payload = event.model_dump(mode="json")

    assert payload["eventType"] == "message.appended"
    assert payload["taskNodeIds"] == ["draft-1"]
    assert payload["taskRefs"] == [{"kind": "draft", "id": "draft-1"}]

    with pytest.raises(ValidationError):
        UiEvent(
            session_id="session-1",
            event_type="message.deleted",  # type: ignore[arg-type]
            cursor="cursor-2",
        )


def test_main_page_snapshot_matches_frontend_contract_shape() -> None:
    payload = _snapshot().model_dump(mode="json")

    assert payload["project"]["id"] == "project-local"
    assert payload["taskTree"]["nodes"][0]["taskRef"] == {
        "kind": "draft",
        "id": "draft-1",
    }
    assert payload["taskTree"]["nodes"][0]["badges"] == {
        "pendingConfirmationCount": 1,
        "unreadMessageCount": 0,
        "directFileChangeCount": 0,
        "subtreeFileChangeCount": 0,
    }
    assert payload["pendingConfirmations"][0]["defaultOptionValue"] == "yes"
    assert payload["fileChangeSummary"] is None
    assert payload["auditLinks"] == []
    assert "pending_confirmations" not in payload


def test_command_request_payloads_validate_business_minimums() -> None:
    request = CommandRequest[AppendSessionInputPayload](
        command_id="command-1",
        session_id="session-1",
        payload=AppendSessionInputPayload(
            content="Build a personal website",
            mode="generate_task_tree",
        ),
    )
    assert request.payload.mode == "generate_task_tree"

    with pytest.raises(ValidationError, match="prompt or raw_task_id"):
        GenerateTaskTreePayload()

    with pytest.raises(ValidationError, match="at least one field"):
        UpdateTaskNodePayload()

    replace_subtree = UpdateTaskNodePayload(
        full_intent="Use the updated parent intent and rebuild descendants.",
        update_mode="replace_subtree",
    )
    assert replace_subtree.model_dump(mode="json")["updateMode"] == "replace_subtree"
    assert replace_subtree.preserve_root_id is True
