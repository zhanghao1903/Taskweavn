from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from taskweavn.contract_revision import (
    ContractRevisionCommandService,
    ContractTaskNodeCommandOutcome,
    CreateExecutionTaskPayload,
    InMemoryContractCommandIdempotencyStore,
    InMemoryGuidanceFactStore,
)
from taskweavn.execution_plane.models import TaskExecution, TaskRequest, utcnow
from taskweavn.server import HttpApiRequest, PlatoUiHttpTransport
from taskweavn.server.runtime_input_router import DefaultRuntimeInputRouter
from taskweavn.server.ui_contract import (
    ApiError,
    AskListResult,
    AskRequestView,
    CommandRequest,
    CommandResponse,
    MainPageSnapshot,
    ProjectSummary,
    QueryResponse,
    RuntimeInputClientState,
    RuntimeInputPendingClarification,
    RuntimeInputRouteRequest,
    RuntimeInputSelection,
    SessionSummary,
    WorkflowSummary,
)
from taskweavn.server.ui_contract.commands import (
    AnswerAskPayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
)
from taskweavn.server.ui_contract.view_models import ConfirmationActionView
from taskweavn.task.plan_models import PlanTaskNode

NOW = datetime(2026, 6, 24, 10, 0, tzinfo=UTC)


def test_router_creates_confirmation_gated_wechat_execution_task() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    handler = _TaskNodeCommandHandler()
    router = _router(query, commands, handler=handler)

    response = router.route(
        _request(
            command_id="route-wechat-send",
            content="给微信文件传输助手发送一条消息：Plato 本地发送测试。发送前让我确认。",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "execution_request"
    assert response.data.decision.dispatch_target == "execution_handoff"
    assert response.data.decision.side_effect == "state_effect"
    assert response.data.outcome.status == "dispatched"
    assert response.data.outcome.user_message == "微信发送任务已创建；真正发送前仍需要用户确认。"
    assert commands.calls == []
    assert len(handler.payloads) == 1
    payload = handler.payloads[0]
    assert payload.title == "Send WeChat message to 文件传输助手"
    assert payload.required_capability == "communication.wechat_desktop_send"
    assert "Task type: communication.wechat.send_message" in payload.instructions
    assert "Contact: 文件传输助手" in payload.instructions
    assert "Message: Plato 本地发送测试" in payload.instructions
    assert "Do not send without user confirmation." in payload.constraints
    assert "The final send is gated by user confirmation." in payload.acceptance_criteria


def test_router_publishes_wechat_send_task_to_execution_plane_when_available() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    execution_plane = _ExecutionPlaneService(status="waiting_for_user")
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
    )

    response = router.route(
        _request(
            command_id="route-wechat-send",
            content="给微信文件传输助手发送消息：hello",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "execution_request"
    assert response.data.decision.dispatch_target == "execution_handoff"
    assert response.data.decision.side_effect == "execution_request"
    assert response.data.outcome.status == "dispatched"
    assert response.data.outcome.user_message == "微信发送任务已创建，正在等待用户确认。"
    assert response.data.activity is not None
    assert response.data.activity.kind == "task_created"
    assert response.data.activity.title == "WeChat send task created"
    assert len(execution_plane.requests) == 1
    task_request = execution_plane.requests[0]
    assert task_request.idempotency_key == "runtime-input:session-1:route-wechat-send"
    assert task_request.task_type == "communication.wechat.send_message"
    assert task_request.input["contactDisplayName"] == "文件传输助手"
    assert task_request.input["messageText"] == "hello"
    assert task_request.policy.requires_human_confirmation is True
    assert task_request.policy.required_capability == "communication.wechat_desktop_send"
    assert commands.calls == []


def test_workspace_http_route_publishes_wechat_send_task_to_execution_plane() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    execution_plane = _ExecutionPlaneService(status="waiting_for_user")
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
    )
    transport = PlatoUiHttpTransport(
        query_gateway=cast(Any, query),
        command_gateway=cast(Any, commands),
        runtime_input_router=router,
    )

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path=(
                "/api/v1/workspaces/workspace-1/sessions/session-1"
                "/runtime-input/route"
            ),
            body={
                "commandId": "route-wechat-http",
                "sessionId": "session-1",
                "content": "给微信文件传输助手发送一条消息：HTTP route smoke",
                "selection": {"scopeKind": "session"},
            },
        )
    )

    assert response.status_code == 200
    assert isinstance(response.body, dict)
    assert response.body["ok"] is True
    data = response.body["data"]
    assert data["decision"]["intent"] == "execution_request"
    assert data["decision"]["dispatchTarget"] == "execution_handoff"
    assert data["decision"]["sideEffect"] == "execution_request"
    assert data["outcome"]["status"] == "dispatched"
    assert data["outcome"]["userMessage"] == "微信发送任务已创建，正在等待用户确认。"
    assert data["activity"]["kind"] == "task_created"
    assert data["commandResponse"] is None
    assert len(execution_plane.requests) == 1
    task_request = execution_plane.requests[0]
    assert task_request.idempotency_key == "runtime-input:session-1:route-wechat-http"
    assert task_request.policy.workspace_scope == "workspace-1"
    assert task_request.policy.requires_human_confirmation is True
    assert task_request.input["contactDisplayName"] == "文件传输助手"
    assert task_request.input["messageText"] == "HTTP route smoke"
    assert commands.calls == []


def test_router_wechat_send_missing_message_needs_clarification_without_task() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    handler = _TaskNodeCommandHandler()
    router = _router(query, commands, handler=handler)

    response = router.route(_request(content="给微信文件传输助手发消息"))

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "clarification"
    assert response.data.decision.dispatch_target == "clarification"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.outcome.status == "needs_clarification"
    assert response.data.outcome.pending_clarification is not None
    pending = response.data.outcome.pending_clarification
    assert pending.kind == "wechat_send"
    assert pending.contact_display_name == "文件传输助手"
    assert pending.message_text is None
    assert pending.missing_slots == ("messageText",)
    assert (
        response.data.outcome.user_message
        == "要发送给文件传输助手的消息内容是什么？没有创建发送任务。"
    )
    assert handler.payloads == []
    assert commands.calls == []


def test_router_completes_pending_wechat_send_clarification() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    execution_plane = _ExecutionPlaneService(status="waiting_for_user")
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
    )

    response = router.route(
        _request(
            command_id="route-wechat-complete",
            content="Plato 补全后的消息。发送前让我确认。",
            pending_clarification=RuntimeInputPendingClarification(
                kind="wechat_send",
                reason_code="missing_message",
                contact_display_name="文件传输助手",
                missing_slots=("messageText",),
                original_content="给微信文件传输助手发消息",
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "execution_request"
    assert response.data.outcome.status == "dispatched"
    assert response.data.outcome.pending_clarification is None
    assert len(execution_plane.requests) == 1
    task_request = execution_plane.requests[0]
    assert task_request.input["contactDisplayName"] == "文件传输助手"
    assert task_request.input["messageText"] == "Plato 补全后的消息"


def test_router_wechat_send_bulk_contact_is_unsupported_without_task() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    handler = _TaskNodeCommandHandler()
    router = _router(query, commands, handler=handler)

    response = router.route(_request(content="给微信张三和李四发送消息：明天开会"))

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "execution_request"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.outcome.status == "unsupported"
    assert response.data.outcome.user_message == "一次只能创建一个微信发送任务。没有发送消息。"
    assert handler.payloads == []
    assert commands.calls == []


def test_router_active_confirmation_takes_priority_over_wechat_send_intent() -> None:
    query = _QueryGateway(active_confirmation_id="confirm-1")
    commands = _CommandGateway()
    handler = _TaskNodeCommandHandler()
    router = _router(query, commands, handler=handler)

    response = router.route(
        _request(
            content="给微信文件传输助手发送消息：这不应该创建新任务",
            active_confirmation_id="confirm-1",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "clarification"
    assert response.data.outcome.status == "needs_clarification"
    assert handler.payloads == []
    assert commands.calls == []


def _request(
    *,
    content: str,
    command_id: str = "route-1",
    active_confirmation_id: str | None = None,
    pending_clarification: RuntimeInputPendingClarification | None = None,
) -> RuntimeInputRouteRequest:
    return RuntimeInputRouteRequest(
        command_id=command_id,
        session_id="session-1",
        workspace_id="workspace-1",
        content=content,
        selection=RuntimeInputSelection(scope_kind="session"),
        client_state=RuntimeInputClientState(
            active_confirmation_id=active_confirmation_id,
            pending_clarification=pending_clarification,
        ),
    )


def _router(
    query: _QueryGateway,
    commands: _CommandGateway,
    *,
    handler: _TaskNodeCommandHandler | None = None,
    execution_plane_service: _ExecutionPlaneService | None = None,
) -> DefaultRuntimeInputRouter:
    service = (
        None
        if handler is None
        else ContractRevisionCommandService(
            idempotency_store=InMemoryContractCommandIdempotencyStore(),
            guidance_store=InMemoryGuidanceFactStore(),
            workspace_id="workspace-1",
            task_node_handler=handler,
        )
    )
    return DefaultRuntimeInputRouter(
        query_gateway=cast(Any, query),
        command_gateway=cast(Any, commands),
        contract_revision_service=service,
        execution_plane_service=cast(Any, execution_plane_service),
    )


@dataclass
class _ExecutionPlaneService:
    status: str = "pending"
    requests: list[TaskRequest] = field(default_factory=list)

    def publish_task(self, request: TaskRequest) -> TaskExecution:
        self.requests.append(request)
        now = utcnow()
        return TaskExecution(
            execution_id="exec-wechat-1",
            task_id="task-wechat-1",
            request_id=request.idempotency_key,
            status=cast(Any, self.status),
            requester=request.requester,
            external_ref=request.external_ref,
            task_type=request.task_type,
            required_capability=request.policy.required_capability,
            env_id="local",
            created_at=now,
            updated_at=now,
            session_id=cast(str, request.metadata["sessionId"]),
        )


@dataclass
class _TaskNodeCommandHandler:
    payloads: list[CreateExecutionTaskPayload] = field(default_factory=list)

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
        payload: CreateExecutionTaskPayload,
    ) -> ContractTaskNodeCommandOutcome:
        self.payloads.append(payload)
        node = PlanTaskNode(
            task_node_id="task-wechat-1",
            plan_id="plan-1",
            session_id=request.session_id,
            task_index="1",
            order_index=0,
            title=payload.title or "Execution task",
            intent=payload.intent,
            summary=payload.summary or payload.intent,
            instructions=payload.instructions,
            required_capability=payload.required_capability or "general",
            constraints=payload.constraints,
            acceptance_criteria=payload.acceptance_criteria,
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
    active_confirmation_id: str | None = None

    def get_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[AskRequestView]:
        return QueryResponse[AskRequestView](
            request_id=request_id or "ask-missing",
            ok=False,
            data=None,
            error=ApiError(code="not_found", message="ASK not found"),
        )

    def list_asks(
        self,
        session_id: str,
        *,
        status: str | None = None,
        task_node_id: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AskListResult]:
        return QueryResponse[AskListResult](
            request_id=request_id or "ask-list",
            ok=True,
            data=AskListResult(session_id=session_id, asks=(), active_ask=None),
        )

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
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
        request: CommandRequest[AnswerAskPayload],
    ) -> CommandResponse:
        self.calls.append(("answer_ask", ask_id, request.payload.text))
        raise AssertionError("answer_ask should not be called")

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[ResolveConfirmationPayload],
    ) -> CommandResponse:
        self.calls.append(("resolve_confirmation", confirmation_id, request.payload.value))
        raise AssertionError("resolve_confirmation should not be called")

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[StopTaskPayload],
    ) -> CommandResponse:
        self.calls.append(("stop_task", task_node_id, request.payload.reason))
        raise AssertionError("stop_task should not be called")

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[RetryTaskPayload],
    ) -> CommandResponse:
        self.calls.append(("retry_task", task_node_id, request.payload.instruction))
        raise AssertionError("retry_task should not be called")


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
                title="Confirm send",
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
