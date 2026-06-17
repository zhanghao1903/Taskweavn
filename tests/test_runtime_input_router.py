from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from taskweavn.contract_revision import (
    ContractRevisionCommandService,
    InMemoryContractCommandIdempotencyStore,
    InMemoryGuidanceFactStore,
    MessageBusContractRevisionActivityPublisher,
    UiGatewayContractInteractionCommandHandler,
)
from taskweavn.interaction import InProcessMessageBus, SqliteMessageStream
from taskweavn.server import HttpApiRequest, PlatoUiHttpTransport
from taskweavn.server.runtime_input_activity import (
    READ_ONLY_INQUIRY_ACTIVITY_TITLE,
    MessageBusRuntimeInputActivityPublisher,
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


def test_router_question_returns_read_only_inquiry_answer() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    publisher = _ActivityPublisher()
    router = _router(query, commands, activity_publisher=publisher)

    response = router.route(
        _request(
            content="What changed in this workspace?",
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
    assert publisher.calls == [("route-1", "activity:inquiry:route-1")]


def test_router_passes_workspace_id_to_read_only_inquiry() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    inquiry = _CapturingInquiry()
    router = _router(query, commands, read_only_inquiry_service=inquiry)

    response = router.route(
        _request(
            content="What changed in this workspace?",
            workspace_id="workspace-1",
            selection=RuntimeInputSelection(scope_kind="session"),
        )
    )

    assert response.ok is True
    assert inquiry.requests[0].workspace_id == "workspace-1"


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
        selection=RuntimeInputSelection(scope_kind="session"),
    )

    response = router.route(request)
    duplicate = router.route(request)

    assert response.ok is True
    assert duplicate.ok is True
    assert len(stream) == 1
    messages = tuple(
        map_agent_message_view(message)
        for message in stream.list_for_session(request.session_id)
    )
    assert messages[0].title == READ_ONLY_INQUIRY_ACTIVITY_TITLE
    assert messages[0].activity_related_refs[0].kind == "session"
    assert messages[0].activity_related_refs[0].id == "session:session-1:status"
    timeline = DefaultSessionActivityProjectionService().project(
        session_id=request.session_id,
        messages=messages,
    )
    assert timeline.total_count == 1
    item = timeline.items[0]
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


def test_router_question_falls_back_when_read_only_inquiry_unavailable() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(query, commands, read_only_inquiry_service=_FailingInquiry())

    response = router.route(
        _request(
            content="What changed in this workspace?",
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


def test_router_active_ask_answer_dispatches_existing_command() -> None:
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
    assert response.data.decision.intent == "ask_answer"
    assert response.data.decision.side_effect == "resume_effect"
    assert response.data.outcome.status == "dispatched"
    assert response.data.activity is not None
    assert response.data.activity.kind == "ask_answered"
    assert response.data.command_response is not None
    assert commands.calls == [("answer_ask", "ask-1", "Use Vercel.")]


def test_router_active_ask_answer_dispatches_through_contract_revision_service() -> None:
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
    assert response.data.decision.intent == "ask_answer"
    assert response.data.decision.dispatch_target == "resolve_ask"
    assert response.data.decision.side_effect == "resume_effect"
    assert response.data.outcome.status == "dispatched"
    assert response.data.activity is not None
    assert response.data.activity.kind == "ask_answered"
    assert response.data.command_response is not None
    assert commands.calls == [("answer_ask", "ask-1", "Use Vercel.")]


def test_router_confirmation_requires_clear_response() -> None:
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
    assert response.data.decision.intent == "clarification"
    assert response.data.outcome.status == "needs_clarification"
    assert response.data.command_response is None
    assert commands.calls == []


def test_router_confirmation_response_dispatches_existing_command() -> None:
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
    assert response.data.decision.intent == "confirmation_response"
    assert response.data.decision.side_effect == "authorization_effect"
    assert response.data.outcome.status == "dispatched"
    assert response.data.activity is not None
    assert response.data.activity.kind == "confirmation_resolved"
    assert commands.calls == [("resolve_confirmation", "confirm-1", "confirmed")]


def test_router_confirmation_response_dispatches_through_contract_revision_service() -> None:
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
    assert response.data.decision.intent == "confirmation_response"
    assert response.data.decision.dispatch_target == "resolve_confirmation"
    assert response.data.decision.side_effect == "authorization_effect"
    assert response.data.outcome.status == "dispatched"
    assert response.data.activity is not None
    assert response.data.activity.kind == "confirmation_resolved"
    assert response.data.command_response is not None
    assert commands.calls == [("resolve_confirmation", "confirm-1", "confirmed")]


def test_router_stop_and_retry_require_selected_task() -> None:
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
    assert no_scope.data.outcome.status == "needs_clarification"
    assert stop.data is not None
    assert stop.data.decision.dispatch_target == "existing_command"
    assert retry.data is not None
    assert retry.data.decision.dispatch_target == "existing_command"
    assert commands.calls == [
        ("stop_task", "task-1", "stop"),
        ("retry_task", "task-1", "retry", True),
    ]


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


def test_runtime_input_http_route_returns_contract_json() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    router = _router(query, commands)
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
) -> DefaultRuntimeInputRouter:
    return DefaultRuntimeInputRouter(
        query_gateway=cast(Any, query),
        command_gateway=cast(Any, commands),
        read_only_inquiry_service=read_only_inquiry_service,
        activity_publisher=activity_publisher,
        contract_revision_service=contract_revision_service,
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
    calls: list[tuple[str, str]] = field(default_factory=list)

    def publish_read_only_answer(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
    ) -> None:
        self.calls.append((request.command_id, activity.id))


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
