from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from taskweavn.contract_revision import (
    ContractRevisionCommandService,
    ContractTaskNodeCommandOutcome,
    InMemoryContractCommandIdempotencyStore,
    InMemoryGuidanceFactStore,
    MessageBusContractRevisionActivityPublisher,
    UiGatewayContractInteractionCommandHandler,
)
from taskweavn.interaction import InProcessMessageBus, SqliteMessageStream
from taskweavn.observability import configure_session_logging
from taskweavn.server import HttpApiRequest, PlatoUiHttpTransport
from taskweavn.server.runtime_input_activity import (
    READ_ONLY_INQUIRY_ACTIVITY_TITLE,
    MessageBusRuntimeInputActivityPublisher,
)
from taskweavn.server.runtime_input_llm_router import (
    RouterPlannerResult,
    RuntimeInputRouteProposal,
)
from taskweavn.server.runtime_input_router import DefaultRuntimeInputRouter
from taskweavn.server.ui_contract import (
    ApiError,
    AskListResult,
    AskRequestView,
    CommandRequest,
    CommandResponse,
    CommandResult,
    ConfirmationActionView,
    MainPageSnapshot,
    ObjectRef,
    ProjectSummary,
    QueryResponse,
    ReadOnlyInquiryAnswer,
    ReadOnlyInquiryRef,
    ReadOnlyInquiryResult,
    RuntimeInputClientState,
    RuntimeInputRouteRequest,
    RuntimeInputSelection,
    SessionSummary,
    WorkflowSummary,
)
from taskweavn.server.ui_contract.mapping import map_agent_message_view
from taskweavn.server.ui_contract.session_activity_projection import (
    DefaultSessionActivityProjectionService,
)
from taskweavn.server.ui_contract.view_models import SessionActivityItemView
from taskweavn.task.plan_models import PlanTaskNode

NOW = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)


def test_runtime_input_route_request_rejects_task_scope_without_task_id() -> None:
    try:
        RuntimeInputRouteRequest(
            command_id="route-1",
            session_id="session-1",
            content="retry",
            selection=RuntimeInputSelection(scope_kind="task"),
        )
    except ValueError as exc:
        assert "task-scoped runtime input requires taskNodeId" in str(exc)
    else:
        raise AssertionError("expected task scope validation to fail")


def test_router_default_without_planner_rejects_free_text_semantic_fallback() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(query, commands)

    question = router.route(
        _request(
            content="What changed in this workspace?",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )
    stop = router.route(
        _request(
            command_id="route-stop",
            content="stop",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
        )
    )
    change = router.route(
        _request(
            command_id="route-change",
            content="create file README.md",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert question.data is not None
    assert question.data.decision.dispatch_target == "unsupported"
    assert question.data.outcome.status == "unsupported"
    assert stop.data is not None
    assert stop.data.decision.dispatch_target == "unsupported"
    assert stop.data.outcome.status == "unsupported"
    assert change.data is not None
    assert change.data.decision.dispatch_target == "unsupported"
    assert change.data.outcome.status == "unsupported"
    assert commands.calls == []


def test_router_question_returns_read_only_inquiry_answer() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    publisher = _ActivityPublisher()
    router = _router(query, commands, activity_publisher=publisher)

    response = router.route(
        _request(
            content="What changed in this workspace?",
            mode="ask",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "question"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.decision.dispatch_target == "read_only_inquiry"
    assert response.data.outcome.status == "answered"
    assert response.data.command_response is None
    assert response.data.inquiry_result is not None
    assert response.data.inquiry_result.status == "answered"
    assert response.data.inquiry_result.evidence_refs[0].kind == "session_status"
    assert response.data.activity is not None
    assert response.data.activity.kind == "answer"
    assert response.data.activity.side_effect == "no_effect"
    assert commands.calls == []
    assert publisher.calls == [
        ("conversation", "route-1", "question"),
        ("activity", "route-1", "activity:inquiry:route-1", "answered"),
    ]


def test_router_passes_workspace_id_to_read_only_inquiry() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    inquiry = _CapturingInquiry()
    router = _router(query, commands, read_only_inquiry_service=inquiry)

    response = router.route(
        _request(
            content="What changed in this workspace?",
            mode="ask",
            workspace_id="workspace-1",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert inquiry.requests[0].workspace_id == "workspace-1"


def test_router_writes_final_dispatch_summary_log(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="session-1")
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(query, commands)

    response = router.route(
        _request(
            content="What changed in this workspace?",
            mode="ask",
            workspace_id="workspace-1",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    runtime_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "runtime.jsonl"
    )
    dispatch_log = runtime_rows[-1]
    assert dispatch_log["event"] == "runtime_input_router_dispatch"
    data = dispatch_log["data"]
    assert data["request_id"] == "route-1"
    assert data["workspace_id"] == "workspace-1"
    assert data["intent"] == "question"
    assert data["dispatch_target"] == "read_only_inquiry"
    assert data["side_effect"] == "no_effect"
    assert data["outcome_status"] == "answered"
    assert data["inquiry_result"]["status"] == "answered"
    assert data["command_response"] is None
    assert data["requires_confirmation"] is False
    assert "What changed in this workspace?" not in json.dumps(
        runtime_rows,
        ensure_ascii=False,
    )


def test_router_planner_can_request_read_only_workspace_file_context() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    inquiry = _CapturingInquiry()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="question",
            dispatch_target="read_only_inquiry",
            side_effect="no_effect",
            confidence="high",
            visible_reasoning_summary="Router will answer from README.",
            user_message="I can answer this from README.",
            read_only_refs=(
                ReadOnlyInquiryRef(
                    kind="file",
                    path="README.md",
                    label="README",
                ),
            ),
        )
    )
    router = _router(
        query,
        commands,
        read_only_inquiry_service=inquiry,
        route_planner=planner,
    )

    response = router.route(
        _request(
            content="How do I start this project?",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.dispatch_target == "read_only_inquiry"
    assert response.data.decision.explanation == "Router will answer from README."
    assert inquiry.requests[0].refs[0].kind == "file"
    assert inquiry.requests[0].refs[0].path == "README.md"
    assert commands.calls == []


def test_router_planner_unavailable_fails_closed_without_question_fallback() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    inquiry = _CapturingInquiry()
    planner = _Planner(None, status="unavailable", warning="planner timeout")
    router = _router(
        query,
        commands,
        read_only_inquiry_service=inquiry,
        route_planner=planner,
    )

    response = router.route(
        _request(
            content="What changed in this workspace?",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.explanation == "planner timeout"
    assert response.data.outcome.status == "unsupported"
    assert inquiry.requests == []
    assert commands.calls == []


def test_router_planner_unavailable_fails_closed_without_stop_fallback() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    planner = _Planner(None, status="unavailable", warning="planner timeout")
    router = _router(query, commands, route_planner=planner)

    response = router.route(
        _request(
            content="stop",
            selection=RuntimeInputSelection(
                scope_kind="task",
                task_node_id="task-1",
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.explanation == "planner timeout"
    assert response.data.outcome.status == "unsupported"
    assert commands.calls == []


def test_router_planner_unavailable_fails_closed_without_change_fallback() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
    )
    planner = _Planner(None, status="unavailable", warning="planner timeout")
    router = _router(
        query,
        commands,
        contract_revision_service=service,
        route_planner=planner,
    )

    response = router.route(
        _request(
            content="create file README.md",
            selection=RuntimeInputSelection(scope_kind="session"),
            workspace_id="workspace-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.explanation == "planner timeout"
    assert response.data.outcome.status == "unsupported"
    assert response.data.command_response is None
    assert commands.calls == []


def test_router_planner_can_dispatch_existing_stop_command() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="command",
            dispatch_target="existing_command",
            side_effect="state_effect",
            confidence="high",
            visible_reasoning_summary="Router skill mapped this to stop_task.",
            user_message="I will stop the selected task.",
            activated_skill_ids=("internal:router-control-commands",),
            command_draft={
                "commandKind": "stop_task",
                "targetScopeKind": "task",
                "targetTaskNodeId": "task-1",
                "rationale": "User asked to stop the current task.",
            },
        )
    )
    router = _router(query, commands, route_planner=planner)

    response = router.route(
        _request(
            content="stop",
            selection=RuntimeInputSelection(
                scope_kind="task",
                task_node_id="task-1",
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "command"
    assert response.data.decision.dispatch_target == "existing_command"
    assert response.data.decision.explanation == "Router skill mapped this to stop_task."
    assert response.data.outcome.status == "dispatched"
    assert commands.calls == [("stop_task", "task-1", "stop")]


def test_router_planner_can_dispatch_existing_retry_command() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="command",
            dispatch_target="existing_command",
            side_effect="state_effect",
            confidence="high",
            visible_reasoning_summary="Router skill mapped this to retry_task.",
            user_message="I will retry the selected task.",
            activated_skill_ids=("internal:router-control-commands",),
            command_draft={
                "commandKind": "retry_task",
                "targetScopeKind": "task",
                "targetTaskNodeId": "task-1",
                "rationale": "User asked to retry the current task.",
            },
        )
    )
    router = _router(query, commands, route_planner=planner)

    response = router.route(
        _request(
            content="run that one again",
            selection=RuntimeInputSelection(
                scope_kind="task",
                task_node_id="task-1",
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "command"
    assert response.data.decision.dispatch_target == "existing_command"
    assert response.data.decision.explanation == "Router skill mapped this to retry_task."
    assert response.data.outcome.status == "dispatched"
    assert commands.calls == [("retry_task", "task-1", "run that one again", True)]


def test_router_planner_can_dispatch_active_ask_answer() -> None:
    query = _QueryGateway(active_ask_id="ask-1")
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="ask_answer",
            dispatch_target="resolve_ask",
            side_effect="resume_effect",
            confidence="high",
            visible_reasoning_summary="Router mapped this to the active ASK answer.",
            user_message="I will answer the active ASK.",
            activated_skill_ids=("internal:router-control-commands",),
            ask_answer_draft={
                "askId": "ask-1",
                "answerText": "Use Netlify.",
            },
        )
    )
    router = _router(query, commands, route_planner=planner)

    response = router.route(
        _request(
            content="I think Netlify is better here.",
            selection=RuntimeInputSelection(scope_kind="session"),
            active_ask_id="ask-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "ask_answer"
    assert response.data.decision.dispatch_target == "resolve_ask"
    assert response.data.outcome.status == "dispatched"
    assert commands.calls == [("answer_ask", "ask-1", "Use Netlify.")]


def test_router_planner_unavailable_fails_closed_without_active_ask_fallback() -> None:
    query = _QueryGateway(active_ask_id="ask-1")
    commands = _CommandGateway()
    planner = _Planner(None, status="unavailable", warning="planner timeout")
    router = _router(query, commands, route_planner=planner)

    response = router.route(
        _request(
            content="Use Vercel.",
            selection=RuntimeInputSelection(scope_kind="session"),
            active_ask_id="ask-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.explanation == "planner timeout"
    assert response.data.outcome.status == "unsupported"
    assert commands.calls == []


def test_router_planner_can_dispatch_active_confirmation_response() -> None:
    query = _QueryGateway(active_confirmation_id="confirm-1")
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="confirmation_response",
            dispatch_target="resolve_confirmation",
            side_effect="authorization_effect",
            confidence="high",
            visible_reasoning_summary="Router mapped this to confirmation rejection.",
            user_message="I will reject the active confirmation.",
            activated_skill_ids=("internal:router-control-commands",),
            confirmation_response_draft={
                "confirmationId": "confirm-1",
                "resolution": "rejected",
            },
        )
    )
    router = _router(query, commands, route_planner=planner)

    response = router.route(
        _request(
            content="No, do not send it.",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
            active_confirmation_id="confirm-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "confirmation_response"
    assert response.data.decision.dispatch_target == "resolve_confirmation"
    assert response.data.outcome.status == "dispatched"
    assert commands.calls == [("resolve_confirmation", "confirm-1", "rejected")]


def test_router_records_guidance_through_contract_revision_service() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    guidance_store = InMemoryGuidanceFactStore()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=guidance_store,
        workspace_id="workspace-1",
    )
    router = _router(query, commands, contract_revision_service=service)

    response = router.route(
        _request(
            content="Keep the implementation small.",
            mode="guide",
            workspace_id="workspace-1",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "guidance"
    assert response.data.decision.dispatch_target == "record_guidance"
    assert response.data.decision.side_effect == "context_effect"
    assert response.data.outcome.status == "dispatched"
    assert response.data.activity is not None
    assert response.data.activity.kind == "guidance_recorded"
    facts = guidance_store.list_for_scope(session_id="session-1")
    assert len(facts) == 1
    assert facts[0].guidance_text == "Keep the implementation small."


def test_router_guidance_activity_persists_to_message_stream(tmp_path: Path) -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    guidance_store = InMemoryGuidanceFactStore()
    message_stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    message_bus = InProcessMessageBus(message_stream)
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=guidance_store,
        workspace_id="workspace-1",
        activity_publisher=MessageBusContractRevisionActivityPublisher(message_bus),
    )
    router = _router(query, commands, contract_revision_service=service)
    try:
        response = router.route(
            _request(
                content="Prefer concise diffs.",
                mode="guide",
                workspace_id="workspace-1",
                selection=RuntimeInputSelection(scope_kind="session"),
            )
        )
        assert response.ok is True

        messages = tuple(message_stream.list_for_session("session-1"))
        views = tuple(map_agent_message_view(message) for message in messages)
        timeline = DefaultSessionActivityProjectionService().project(
            session_id="session-1",
            messages=views,
        )
    finally:
        message_bus.close()
        message_stream.close()

    assert len(timeline.items) == 1
    assert timeline.items[0].kind == "guidance_recorded"
    assert timeline.items[0].side_effect == "context_effect"
    assert timeline.items[0].body == "Guidance recorded: Prefer concise diffs."


def test_router_passes_explicit_inquiry_refs_to_read_only_inquiry() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    inquiry = _CapturingInquiry()
    router = _router(query, commands, read_only_inquiry_service=inquiry)

    response = router.route(
        _request(
            content="What changed in diagnostics-summary.md?",
            mode="ask",
            selection=RuntimeInputSelection(
                scope_kind="session",
                refs=(ObjectRef(kind="message", id="activity-1"),),
            ),
            inquiry_refs=(
                ReadOnlyInquiryRef(
                    kind="file",
                    path="diagnostics-summary.md",
                    label="diagnostics-summary.md",
                ),
                ReadOnlyInquiryRef(
                    kind="diagnostic",
                    id="diagnostic:bundle_export",
                    label="Diagnostic bundle export",
                ),
            ),
        )
    )

    assert response.ok is True
    assert [ref.kind for ref in inquiry.requests[0].refs] == [
        "file",
        "diagnostic",
        "activity",
    ]


def test_router_read_only_answer_is_durable_activity(
    tmp_path: Path,
) -> None:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(
        query,
        commands,
        activity_publisher=MessageBusRuntimeInputActivityPublisher(bus),
    )
    request = _request(
        content="What changed in this workspace?",
        mode="ask",
        selection=RuntimeInputSelection(scope_kind="session"),
    )

    response = router.route(request)
    duplicate = router.route(request)

    assert response.ok is True
    assert duplicate.ok is True
    assert len(stream) == 3
    messages = tuple(
        map_agent_message_view(message)
        for message in stream.list_for_session(request.session_id)
    )
    assert [message.title for message in messages] == [
        "User input",
        "Router interpretation",
        READ_ONLY_INQUIRY_ACTIVITY_TITLE,
    ]
    assert messages[0].body == "What changed in this workspace?"
    assert messages[0].conversation_render is not None
    assert messages[0].conversation_render.render_kind == "text"
    assert messages[1].conversation_render is not None
    assert messages[1].conversation_render.render_kind == "router_trace"
    assert messages[1].conversation_render.router_trace is not None
    assert messages[1].conversation_render.router_trace.intent == "question"
    assert messages[2].activity_related_refs[0].kind == "session"
    assert messages[2].activity_related_refs[0].id == "session:session-1:status"
    timeline = DefaultSessionActivityProjectionService().project(
        session_id=request.session_id,
        messages=messages,
    )
    assert timeline.total_count == 3
    item_by_kind = {item.kind: item for item in timeline.items}
    assert set(item_by_kind) == {"user_input", "router_interpretation", "answer"}
    assert item_by_kind["user_input"].id == "activity:runtime-input:route-1:user_input"
    assert item_by_kind["user_input"].body == "What changed in this workspace?"
    item = item_by_kind["answer"]
    assert item.id == "activity:inquiry:route-1"
    assert item.kind == "answer"
    assert item.side_effect == "no_effect"
    assert item.source_kind == "router"
    assert item.source_id == "route-1"
    assert item.body == "Session 'Session' is running."
    assert item.related_refs[0].kind == "session"
    assert item.related_refs[0].id == "session:session-1:status"
    assert commands.calls == []

    bus.close()
    stream.close()


def test_router_planner_interpretation_is_durable_activity(
    tmp_path: Path,
) -> None:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    query = _QueryGateway()
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="question",
            dispatch_target="read_only_inquiry",
            side_effect="no_effect",
            confidence="high",
            visible_reasoning_summary="Router will answer from README.",
            user_message="I can answer this from README.",
            read_only_refs=(
                ReadOnlyInquiryRef(
                    kind="file",
                    path="README.md",
                    label="README",
                ),
            ),
        )
    )
    router = _router(
        query,
        commands,
        read_only_inquiry_service=_CapturingInquiry(),
        activity_publisher=MessageBusRuntimeInputActivityPublisher(bus),
        route_planner=planner,
    )
    request = _request(
        content="How do I start this project?",
        selection=RuntimeInputSelection(scope_kind="session"),
    )

    response = router.route(request)

    assert response.ok is True
    messages = tuple(
        map_agent_message_view(message)
        for message in stream.list_for_session(request.session_id)
    )
    timeline = DefaultSessionActivityProjectionService().project(
        session_id=request.session_id,
        messages=messages,
    )
    item_by_kind = {item.kind: item for item in timeline.items}
    assert set(item_by_kind) == {"user_input", "router_interpretation", "answer"}
    assert item_by_kind["user_input"].id == "activity:runtime-input:route-1:user_input"
    assert item_by_kind["user_input"].body == "How do I start this project?"
    assert item_by_kind["router_interpretation"].title == "Router interpretation"
    assert "Router will answer from README." in item_by_kind["router_interpretation"].body
    assert item_by_kind["router_interpretation"].side_effect == "no_effect"
    assert item_by_kind["answer"].body == "Captured without side effects."

    bus.close()
    stream.close()


def test_router_clarification_is_durable_question_card(
    tmp_path: Path,
) -> None:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    query = _QueryGateway()
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="clarification",
            dispatch_target="clarification",
            side_effect="no_effect",
            confidence="medium",
            visible_reasoning_summary="Router needs a clearer response.",
            user_message="Please clarify before Plato changes anything.",
            activated_skill_ids=("internal:router-core",),
        )
    )
    router = _router(
        query,
        commands,
        activity_publisher=MessageBusRuntimeInputActivityPublisher(bus),
        route_planner=planner,
    )
    request = _request(
        command_id="route-confirm-clarify",
        content="maybe later",
        selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
    )

    response = router.route(request)

    assert response.ok is True
    assert response.data is not None
    assert response.data.outcome.status == "needs_clarification"
    messages = tuple(
        map_agent_message_view(message)
        for message in stream.list_for_session(request.session_id)
    )
    question = next(message for message in messages if message.title == "Router question")
    assert question.conversation_render is not None
    assert question.conversation_render.render_kind == "question_card"
    assert question.conversation_render.question_card is not None
    assert question.conversation_render.question_card.card_kind == "clarification"
    assert question.conversation_render.question_card.status == "pending"
    assert question.conversation_render.question_card.options == ()
    assert commands.calls == []

    bus.close()
    stream.close()


def test_router_ask_answer_is_durable_conversation_answer(
    tmp_path: Path,
) -> None:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    query = _QueryGateway(active_ask_id="ask-1")
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="ask_answer",
            dispatch_target="resolve_ask",
            side_effect="resume_effect",
            confidence="high",
            visible_reasoning_summary="Router mapped this to the active ASK answer.",
            user_message="I will answer the active ASK.",
            activated_skill_ids=("internal:router-control-commands",),
            ask_answer_draft={
                "askId": "ask-1",
                "answerText": "Use Vercel.",
            },
        )
    )
    router = _router(
        query,
        commands,
        activity_publisher=MessageBusRuntimeInputActivityPublisher(bus),
        route_planner=planner,
    )
    request = _request(
        command_id="route-ask-answer",
        content="Use Vercel.",
        selection=RuntimeInputSelection(scope_kind="session"),
        active_ask_id="ask-1",
    )

    response = router.route(request)

    assert response.ok is True
    assert response.data is not None
    assert response.data.outcome.status == "dispatched"
    messages = tuple(
        map_agent_message_view(message)
        for message in stream.list_for_session(request.session_id)
    )
    user_answer = messages[0]
    assert user_answer.title == "User input"
    assert user_answer.body == "Use Vercel."
    assert user_answer.conversation_render is not None
    assert user_answer.conversation_render.text is not None
    assert user_answer.conversation_render.text.body == "Use Vercel."
    assert any(message.title == "ASK answered" for message in messages)
    assert commands.calls == [("answer_ask", "ask-1", "Use Vercel.")]

    bus.close()
    stream.close()


def test_router_question_falls_back_when_read_only_inquiry_unavailable() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(query, commands, read_only_inquiry_service=_FailingInquiry())

    response = router.route(
        _request(
            content="What changed in this workspace?",
            mode="ask",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "question"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.decision.dispatch_target == "read_only_inquiry"
    assert response.data.outcome.status == "unsupported"
    assert response.data.command_response is None
    assert response.data.inquiry_result is None
    assert response.data.activity is not None
    assert response.data.activity.kind == "router_interpretation"
    assert commands.calls == []


def test_router_active_ask_without_planner_is_unsupported() -> None:
    query = _QueryGateway(active_ask_id="ask-1")
    commands = _CommandGateway()
    router = _router(query, commands)

    response = router.route(
        _request(
            command_id="route-ask",
            content="Use Vercel.",
            selection=RuntimeInputSelection(scope_kind="session"),
            active_ask_id="ask-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.outcome.status == "unsupported"
    assert response.data.activity is not None
    assert response.data.activity.kind == "router_interpretation"
    assert response.data.command_response is None
    assert commands.calls == []


def test_router_active_ask_with_contract_service_without_planner_is_unsupported() -> None:
    query = _QueryGateway(active_ask_id="ask-1")
    commands = _CommandGateway()
    service = _contract_revision_service(commands)
    router = _router(query, commands, contract_revision_service=service)

    response = router.route(
        _request(
            command_id="route-ask",
            content="Use Vercel.",
            selection=RuntimeInputSelection(scope_kind="session"),
            active_ask_id="ask-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.outcome.status == "unsupported"
    assert response.data.command_response is None
    assert commands.calls == []


def test_router_active_confirmation_without_planner_is_unsupported() -> None:
    query = _QueryGateway(active_confirmation_id="confirm-1")
    commands = _CommandGateway()
    router = _router(query, commands)

    response = router.route(
        _request(
            content="maybe later",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
            active_confirmation_id="confirm-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.outcome.status == "unsupported"
    assert response.data.command_response is None
    assert commands.calls == []


def test_router_confirmation_response_without_planner_is_unsupported() -> None:
    query = _QueryGateway(active_confirmation_id="confirm-1")
    commands = _CommandGateway()
    router = _router(query, commands)

    response = router.route(
        _request(
            command_id="route-confirm",
            content="yes",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
            active_confirmation_id="confirm-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.outcome.status == "unsupported"
    assert response.data.activity is not None
    assert response.data.activity.kind == "router_interpretation"
    assert commands.calls == []


def test_router_confirmation_with_contract_service_without_planner_is_unsupported() -> None:
    query = _QueryGateway(active_confirmation_id="confirm-1")
    commands = _CommandGateway()
    service = _contract_revision_service(commands)
    router = _router(query, commands, contract_revision_service=service)

    response = router.route(
        _request(
            command_id="route-confirm",
            content="yes",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
            active_confirmation_id="confirm-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.outcome.status == "unsupported"
    assert response.data.command_response is None
    assert commands.calls == []


def test_router_stop_and_retry_free_text_without_planner_are_unsupported() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(query, commands)

    no_scope = router.route(
        _request(
            content="stop",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )
    stop = router.route(
        _request(
            command_id="route-stop",
            content="stop",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
        )
    )
    retry = router.route(
        _request(
            command_id="route-retry",
            content="retry",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
        )
    )

    assert no_scope.data is not None
    assert no_scope.data.outcome.status == "unsupported"
    assert stop.data is not None
    assert stop.data.decision.dispatch_target == "unsupported"
    assert retry.data is not None
    assert retry.data.decision.dispatch_target == "unsupported"
    assert commands.calls == []


def test_router_defers_publish_and_workspace_changing_requests() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(query, commands)

    publish = router.route(
        _request(
            content="publish plan",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )
    workspace_change = router.route(
        _request(
            content="edit file index.html",
            mode="change",
            selection=RuntimeInputSelection(scope_kind="task", task_node_id="task-1"),
        )
    )

    assert publish.data is not None
    assert publish.data.outcome.status == "unsupported"
    assert workspace_change.data is not None
    assert workspace_change.data.decision.intent == "execution_request"
    assert workspace_change.data.outcome.status == "unsupported"
    assert commands.calls == []


def test_router_change_mode_dispatches_execution_task_command() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    task_node_handler = _TaskNodeCommandHandler()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        task_node_handler=task_node_handler,
    )
    router = _router(query, commands, contract_revision_service=service)

    response = router.route(
        _request(
            content="Edit README with the release notes.",
            mode="change",
            workspace_id="workspace-1",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "execution_request"
    assert response.data.decision.dispatch_target == "execution_handoff"
    assert response.data.decision.side_effect == "state_effect"
    assert response.data.outcome.status == "dispatched"
    assert response.data.activity is not None
    assert response.data.activity.kind == "task_created"
    assert response.data.activity.title == "Execution work created"
    assert response.data.command_response is None
    assert commands.calls == []
    assert task_node_handler.calls == [
        (
            "create_execution_task",
            "session",
            None,
            "Edit README with the release notes.",
        )
    ]


def test_runtime_input_http_route_returns_contract_json() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="command",
            dispatch_target="existing_command",
            side_effect="state_effect",
            confidence="high",
            visible_reasoning_summary="Router skill mapped this to stop_task.",
            user_message="I will stop the selected task.",
            activated_skill_ids=("internal:router-control-commands",),
            command_draft={
                "commandKind": "stop_task",
                "targetScopeKind": "task",
                "targetTaskNodeId": "task-1",
                "rationale": "User asked to stop the current task.",
            },
        )
    )
    router = _router(query, commands, route_planner=planner)
    transport = PlatoUiHttpTransport(
        query_gateway=cast(Any, query),
        command_gateway=cast(Any, commands),
        runtime_input_router=router,
    )

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/runtime-input/route",
            body={
                "commandId": "route-stop",
                "sessionId": "session-1",
                "content": "stop",
                "selection": {
                    "scopeKind": "task",
                    "taskNodeId": "task-1",
                },
            },
        )
    )

    assert response.status_code == 200
    assert isinstance(response.body, dict)
    assert response.body["ok"] is True
    assert response.body["requestId"] == "route-stop"
    assert response.body["data"]["decision"]["intent"] == "command"
    assert response.body["data"]["activity"]["kind"] == "router_interpretation"
    assert response.body["data"]["commandResponse"]["ok"] is True
    assert commands.calls == [("stop_task", "task-1", "stop")]


def _request(
    *,
    content: str,
    selection: RuntimeInputSelection,
    command_id: str = "route-1",
    mode: str = "auto",
    workspace_id: str | None = None,
    inquiry_refs: tuple[ReadOnlyInquiryRef, ...] = (),
    active_ask_id: str | None = None,
    active_confirmation_id: str | None = None,
) -> RuntimeInputRouteRequest:
    return RuntimeInputRouteRequest(
        command_id=command_id,
        session_id="session-1",
        workspace_id=workspace_id,
        content=content,
        mode=mode,  # type: ignore[arg-type]
        selection=selection,
        inquiry_refs=inquiry_refs,
        client_state=RuntimeInputClientState(
            active_ask_id=active_ask_id,
            active_confirmation_id=active_confirmation_id,
        ),
    )


def _router(
    query: _QueryGateway,
    commands: _CommandGateway,
    *,
    read_only_inquiry_service: Any | None = None,
    activity_publisher: Any | None = None,
    contract_revision_service: Any | None = None,
    route_planner: Any | None = None,
) -> DefaultRuntimeInputRouter:
    return DefaultRuntimeInputRouter(
        query_gateway=cast(Any, query),
        command_gateway=cast(Any, commands),
        read_only_inquiry_service=read_only_inquiry_service,
        activity_publisher=activity_publisher,
        contract_revision_service=contract_revision_service,
        route_planner=route_planner,
    )


def _contract_revision_service(
    commands: _CommandGateway,
) -> ContractRevisionCommandService:
    return ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        interaction_handler=UiGatewayContractInteractionCommandHandler(
            cast(Any, commands)
        ),
    )


@dataclass
class _ActivityPublisher:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def publish_router_conversation(
        self,
        request: RuntimeInputRouteRequest,
        decision: Any,
        outcome: Any,
    ) -> None:
        del outcome
        self.calls.append(("conversation", request.command_id, decision.intent))

    def publish_router_activity(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
        *,
        outcome_status: str | None = None,
    ) -> None:
        self.calls.append(
            ("activity", request.command_id, activity.id, outcome_status)
        )

    def publish_read_only_answer(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
    ) -> None:
        self.calls.append(("answer", request.command_id, activity.id))


@dataclass
class _TaskNodeCommandHandler:
    calls: list[tuple[str, str, str | None, str]] = field(default_factory=list)

    def patch_task_node(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
        raise AssertionError("patch_task_node should not be called")

    def create_task_node(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
        raise AssertionError("create_task_node should not be called")

    def delete_task_node(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
        raise AssertionError("delete_task_node should not be called")

    def create_execution_task(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
        self.calls.append(
            (
                "create_execution_task",
                request.scope_kind,
                request.plan_id,
                payload.intent,
            )
        )
        node = PlanTaskNode(
            task_node_id="task-exec-1",
            plan_id="plan-1",
            session_id=request.session_id,
            task_index="1",
            order_index=0,
            title="Execution task",
            intent=payload.intent,
            summary=payload.intent,
            readiness="approved",
        )
        return ContractTaskNodeCommandOutcome(
            accepted=True,
            message="Execution TaskNode was created.",
            plan_id="plan-1",
            task_node=node,
        )


@dataclass
class _QueryGateway:
    active_ask_id: str | None = None
    active_confirmation_id: str | None = None
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def get_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[AskRequestView]:
        self.calls.append(("get_ask", session_id, ask_id, request_id))
        if self.active_ask_id != ask_id:
            return QueryResponse[AskRequestView](
                request_id=request_id or "ask-missing",
                ok=False,
                data=None,
                error=ApiError(code="not_found", message="ASK not found"),
            )
        return QueryResponse[AskRequestView](
            request_id=request_id or "ask-detail",
            ok=True,
            data=_ask(session_id, ask_id),
        )

    def list_asks(
        self,
        session_id: str,
        *,
        status: str | None = None,
        task_node_id: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AskListResult]:
        self.calls.append(("list_asks", session_id, status, task_node_id, request_id))
        ask = (
            _ask(session_id, self.active_ask_id, task_node_id=task_node_id)
            if self.active_ask_id is not None
            else None
        )
        return QueryResponse[AskListResult](
            request_id=request_id or "ask-list",
            ok=True,
            data=AskListResult(
                session_id=session_id,
                asks=() if ask is None else (ask,),
                active_ask=ask,
            ),
        )

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
        self.calls.append(("snapshot", session_id, request_id))
        return QueryResponse[MainPageSnapshot](
            request_id=request_id or "snapshot",
            ok=True,
            data=_snapshot(session_id, confirmation_id=self.active_confirmation_id),
        )


@dataclass
class _CommandGateway:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def answer_ask(
        self,
        ask_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(("answer_ask", ask_id, request.payload.text))
        return _accepted(request.command_id)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(
            ("resolve_confirmation", confirmation_id, request.payload.value)
        )
        return _accepted(request.command_id)

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(("stop_task", task_node_id, request.payload.reason))
        return _accepted(request.command_id)

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(
            (
                "retry_task",
                task_node_id,
                request.payload.instruction,
                request.payload.start_immediately,
            )
        )
        return _accepted(request.command_id)


class _FailingInquiry:
    def answer(self, request: Any) -> QueryResponse[ReadOnlyInquiryResult]:
        return QueryResponse[ReadOnlyInquiryResult](
            request_id=request.inquiry_id,
            ok=False,
            data=None,
            error=ApiError(code="internal_error", message="Inquiry unavailable"),
        )


@dataclass
class _CapturingInquiry:
    requests: list[Any] = field(default_factory=list)

    def answer(self, request: Any) -> QueryResponse[ReadOnlyInquiryResult]:
        self.requests.append(request)
        return QueryResponse[ReadOnlyInquiryResult](
            request_id=request.inquiry_id,
            ok=True,
            data=ReadOnlyInquiryResult(
                inquiry_id=request.inquiry_id,
                session_id=request.session_id,
                scope=request.scope,
                status="answered",
                answer=ReadOnlyInquiryAnswer(
                    title="Captured",
                    body="Captured without side effects.",
                    confidence="high",
                ),
            ),
        )


@dataclass
class _Planner:
    proposal: RuntimeInputRouteProposal | None
    status: str = "planned"
    warning: str | None = None

    def plan(self, *args: Any, **kwargs: Any) -> RouterPlannerResult:
        return RouterPlannerResult(
            status=cast(Any, self.status),
            proposal=self.proposal,
            warning=self.warning,
        )


def _ask(
    session_id: str,
    ask_id: str,
    *,
    task_node_id: str | None = None,
) -> AskRequestView:
    return AskRequestView(
        id=ask_id,
        session_id=session_id,
        task_node_id=task_node_id,
        question="Which deployment target should be used?",
        reason="The agent needs a user-owned deployment decision.",
        answer_type="free_text",
        allow_free_text=True,
        allow_no_option_with_text=True,
        blocking=True,
        status="pending",
        created_at=NOW,
    )


def _snapshot(
    session_id: str,
    *,
    confirmation_id: str | None,
) -> MainPageSnapshot:
    project = ProjectSummary(id="project-local", name="Local")
    workflow = WorkflowSummary(id="authoring", name="Authoring")
    session = SessionSummary(
        id=session_id,
        project_id=project.id,
        workflow_id=workflow.id,
        name="Session",
        status="running",
        created_at=NOW,
        updated_at=NOW,
    )
    confirmations: tuple[ConfirmationActionView, ...] = ()
    if confirmation_id is not None:
        confirmations = (
            ConfirmationActionView(
                id=confirmation_id,
                session_id=session_id,
                task_node_id="task-1",
                title="Confirm execution",
                body="Proceed?",
                status="pending",
            ),
        )
    return MainPageSnapshot(
        project=project,
        workflows=(workflow,),
        workflow=workflow,
        sessions=(session,),
        session=session,
        pending_confirmations=confirmations,
        generated_at=NOW,
    )


def _accepted(command_id: str) -> CommandResponse:
    return CommandResponse(
        request_id=f"request-{command_id}",
        ok=True,
        result=CommandResult(
            command_id=command_id,
            status="accepted",
            message="accepted",
        ),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
