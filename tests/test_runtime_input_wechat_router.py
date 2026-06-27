from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from taskweavn.contract_revision import (
    ContractRevisionCommandService,
    ContractTaskNodeCommandOutcome,
    CreateExecutionTaskPayload,
    InMemoryContractCommandIdempotencyStore,
    InMemoryGuidanceFactStore,
)
from taskweavn.execution_plane.errors import ExecutionPlaneError
from taskweavn.execution_plane.models import (
    TaskError,
    TaskExecution,
    TaskRequest,
    utcnow,
)
from taskweavn.interaction import InProcessMessageBus, SqliteMessageStream
from taskweavn.server import HttpApiRequest, PlatoUiHttpTransport
from taskweavn.server.runtime_input_activity import (
    ROUTER_REPLY_TITLE,
    ROUTER_TRACE_TITLE,
    USER_INPUT_TITLE,
    MessageBusRuntimeInputActivityPublisher,
)
from taskweavn.server.runtime_input_llm_router import (
    RouterPlannerResult,
    RouterTaskPolicyDraft,
    RouterTaskRequestDraft,
    RuntimeInputRouteProposal,
)
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
from taskweavn.server.ui_contract.mapping import map_agent_message_view
from taskweavn.server.ui_contract.session_activity_projection import (
    DefaultSessionActivityProjectionService,
)
from taskweavn.server.ui_contract.view_models import ConfirmationActionView
from taskweavn.task.plan_models import PlanTaskNode

NOW = datetime(2026, 6, 24, 10, 0, tzinfo=UTC)


def test_router_creates_confirmation_gated_wechat_execution_task() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    handler = _TaskNodeCommandHandler()
    router = _router(
        query,
        commands,
        handler=handler,
        route_planner=_wechat_planner("Plato 本地发送测试"),
    )

    response = router.route(
        _request(
            command_id="route-wechat-send",
            content="给微信的文件传输助手发送测试消息",
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
        route_planner=_wechat_planner("hello"),
    )

    response = router.route(
        _request(
            command_id="route-wechat-send",
            content="给微信文件传输助手发送消息",
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


def test_router_capability_missing_is_conversation_visible(tmp_path: Path) -> None:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    query = _QueryGateway()
    commands = _CommandGateway()
    execution_plane = _ExecutionPlaneService(
        error=ExecutionPlaneError(
            "capability_not_available",
            "WeChat desktop send capability is not enabled in this environment.",
            retryable=True,
            details={
                "recoveryActions": [
                    "open_macos_privacy_accessibility",
                    "restart_helper",
                    "rerun_helper_preflight",
                ],
            },
        )
    )
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
        route_planner=_wechat_planner("你好"),
        activity_publisher=MessageBusRuntimeInputActivityPublisher(bus),
    )
    request = _request(
        command_id="route-wechat-capability-missing",
        content='给微信的文件传输助手发送"你好"',
    )

    try:
        response = router.route(request)
        duplicate = router.route(request)

        messages = tuple(
            map_agent_message_view(message)
            for message in stream.list_for_session(request.session_id)
        )
        timeline = DefaultSessionActivityProjectionService().project(
            session_id=request.session_id,
            messages=messages,
        )
    finally:
        bus.close()
        stream.close()

    assert response.ok is True
    assert duplicate.ok is True
    assert response.data is not None
    assert response.data.outcome.status == "rejected"
    assert response.data.outcome.user_message == (
        "当前执行环境不支持微信发送能力。没有发送消息。\n"
        "错误代码：capability_not_available\n"
        "错误信息：WeChat desktop send capability is not enabled in this environment."
    )
    assert response.data.outcome.recovery_actions == (
        "open_macos_privacy_accessibility",
        "restart_helper",
        "rerun_helper_preflight",
    )
    assert [message.title for message in messages] == [
        USER_INPUT_TITLE,
        ROUTER_TRACE_TITLE,
        ROUTER_REPLY_TITLE,
        "Runtime input routed",
    ]
    assert messages[0].body == request.content
    reply = messages[2]
    assert reply.kind == "error"
    assert reply.body.startswith("当前执行环境不支持微信发送能力。没有发送消息。")
    assert "错误代码：capability_not_available" in reply.body
    assert (
        "错误信息：WeChat desktop send capability is not enabled in this environment."
        in reply.body
    )
    assert "建议的恢复操作" in reply.body
    assert "打开 macOS 隐私与安全性 > 辅助功能" in reply.body
    assert "重启 Plato Computer Use Helper 后再检查" in reply.body
    assert "重新运行 helper 就绪预检，确认权限已生效" in reply.body
    assert reply.conversation_render is not None
    assert reply.conversation_render.render_kind == "text"
    assert reply.conversation_render.text is not None
    assert reply.conversation_render.text.body == reply.body
    item_by_kind = {item.kind: item for item in timeline.items}
    assert item_by_kind["user_input"].body == request.content
    assert item_by_kind["recovery_note"].body == reply.body
    assert len(execution_plane.requests) == 0
    assert commands.calls == []


def test_router_immediate_wechat_execution_failure_is_conversation_visible(
    tmp_path: Path,
) -> None:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    query = _QueryGateway()
    commands = _CommandGateway()
    task_error = TaskError(
        error_ref="error:wechat-runtime:exec-wechat-1:wechat_not_ready",
        execution_id="exec-wechat-1",
        code="wechat_not_ready",
        message=(
            "macOS computer-use readiness: missing_accessibility. "
            "Grant Accessibility permission to the Python process or host app."
        ),
        retryable=True,
        recovery_hint="Review local Accessibility permissions, then start a new task.",
        evidence_refs=("evidence:wechat-runtime:exec-wechat-1:readiness",),
        created_at=NOW,
    )
    execution_plane = _ExecutionPlaneService(
        status="failed",
        task_error=task_error,
    )
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
        route_planner=_wechat_planner("你好"),
        activity_publisher=MessageBusRuntimeInputActivityPublisher(bus),
    )
    request = _request(
        command_id="route-wechat-readiness-failed",
        content='给微信的文件传输助手发送"你好"',
    )

    try:
        response = router.route(request)
        messages = tuple(
            map_agent_message_view(message)
            for message in stream.list_for_session(request.session_id)
        )
        timeline = DefaultSessionActivityProjectionService().project(
            session_id=request.session_id,
            messages=messages,
        )
    finally:
        bus.close()
        stream.close()

    assert response.ok is True
    assert response.data is not None
    assert response.data.outcome.status == "rejected"
    assert "错误代码：wechat_not_ready" in response.data.outcome.user_message
    assert "错误信息：macOS computer-use readiness: missing_accessibility" in (
        response.data.outcome.user_message
    )
    assert "恢复建议：Review local Accessibility permissions" in (
        response.data.outcome.user_message
    )
    assert response.data.outcome.recovery_actions == (
        "open_settings",
        "retry_command",
    )
    assert [message.title for message in messages] == [
        USER_INPUT_TITLE,
        ROUTER_TRACE_TITLE,
        ROUTER_REPLY_TITLE,
        "WeChat send task failed",
    ]
    reply = messages[2]
    assert reply.kind == "error"
    assert "错误代码：wechat_not_ready" in reply.body
    assert "建议的恢复操作" in reply.body
    assert "打开设置，检查 provider、权限或本地运行配置。" in reply.body
    item_by_title = {item.title: item for item in timeline.items}
    assert "错误信息：macOS computer-use readiness: missing_accessibility" in (
        item_by_title["WeChat send task failed"].body
    )
    assert len(execution_plane.requests) == 1
    assert commands.calls == []


def test_router_uses_planner_wechat_task_request_draft_for_execution_plane() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    execution_plane = _ExecutionPlaneService(status="waiting_for_user")
    planner = _Planner(
        RuntimeInputRouteProposal(
            intent="execution_request",
            dispatch_target="execution_handoff",
            side_effect="state_effect",
            confidence="high",
            visible_reasoning_summary="Router skill created a WeChat task draft.",
            user_message="I will create a confirmation-gated WeChat task.",
            activated_skill_ids=("internal:router-wechat-send",),
            task_request_draft=_wechat_task_request_draft("LLM proposal path"),
        )
    )
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
        route_planner=planner,
    )

    response = router.route(
        _request(
            command_id="route-wechat-llm",
            content="请按刚才讨论的外部联系流程处理这条消息",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "execution_request"
    assert response.data.decision.dispatch_target == "execution_handoff"
    assert response.data.decision.side_effect == "execution_request"
    assert response.data.outcome.status == "dispatched"
    assert len(execution_plane.requests) == 1
    task_request = execution_plane.requests[0]
    assert task_request.idempotency_key == "runtime-input:session-1:route-wechat-llm"
    assert task_request.task_type == "communication.wechat.send_message"
    assert task_request.input["contactDisplayName"] == "文件传输助手"
    assert task_request.input["messageText"] == "LLM proposal path"
    assert task_request.policy.requires_human_confirmation is True
    assert task_request.policy.risk_level == "high"
    assert commands.calls == []


def test_router_planner_unavailable_does_not_fall_back_to_wechat_parser() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    execution_plane = _ExecutionPlaneService(status="waiting_for_user")
    planner = _Planner(None, status="unavailable", warning="planner timeout")
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
        route_planner=planner,
    )

    response = router.route(
        _request(
            command_id="route-wechat-planner-unavailable",
            content="给微信文件传输助手发送消息：should not send",
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.explanation == "planner timeout"
    assert response.data.outcome.status == "unsupported"
    assert execution_plane.requests == []
    assert commands.calls == []


def test_workspace_http_route_publishes_wechat_send_task_to_execution_plane() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    execution_plane = _ExecutionPlaneService(status="waiting_for_user")
    router = _router(
        query,
        commands,
        execution_plane_service=execution_plane,
        route_planner=_wechat_planner("HTTP route smoke"),
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
                "content": "给微信文件传输助手发送一条消息",
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


def test_router_without_planner_does_not_parse_wechat_send_text() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    handler = _TaskNodeCommandHandler()
    router = _router(query, commands, handler=handler)

    response = router.route(_request(content="给微信文件传输助手发送消息：hello"))

    assert response.ok is True
    assert response.data is not None
    assert response.data.decision.intent == "unsupported"
    assert response.data.decision.dispatch_target == "unsupported"
    assert response.data.decision.side_effect == "no_effect"
    assert response.data.outcome.status == "unsupported"
    assert handler.payloads == []
    assert commands.calls == []


def test_router_active_confirmation_without_planner_does_not_parse_wechat_send_text() -> None:
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
    assert response.data.decision.intent == "unsupported"
    assert response.data.outcome.status == "unsupported"
    assert handler.payloads == []
    assert commands.calls == []


def _request(
    *,
    content: str,
    command_id: str = "route-1",
    active_confirmation_id: str | None = None,
) -> RuntimeInputRouteRequest:
    return RuntimeInputRouteRequest(
        command_id=command_id,
        session_id="session-1",
        workspace_id="workspace-1",
        content=content,
        selection=RuntimeInputSelection(scope_kind="session"),
        client_state=RuntimeInputClientState(
            active_confirmation_id=active_confirmation_id,
        ),
    )


def _router(
    query: _QueryGateway,
    commands: _CommandGateway,
    *,
    handler: _TaskNodeCommandHandler | None = None,
    execution_plane_service: _ExecutionPlaneService | None = None,
    route_planner: _Planner | None = None,
    activity_publisher: Any | None = None,
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
        route_planner=route_planner,
        activity_publisher=activity_publisher,
    )


def _wechat_planner(message_text: str) -> _Planner:
    return _Planner(
        RuntimeInputRouteProposal(
            intent="execution_request",
            dispatch_target="execution_handoff",
            side_effect="state_effect",
            confidence="high",
            visible_reasoning_summary="Router skill created a WeChat task draft.",
            user_message="I will create a confirmation-gated WeChat task.",
            activated_skill_ids=("internal:router-wechat-send",),
            task_request_draft=_wechat_task_request_draft(message_text),
        )
    )


def _wechat_task_request_draft(message_text: str) -> RouterTaskRequestDraft:
    return RouterTaskRequestDraft(
        task_type="communication.wechat.send_message",
        instructions="Send one confirmation-gated WeChat message.",
        input={
            "contactDisplayName": "文件传输助手",
            "messageText": message_text,
        },
        policy=RouterTaskPolicyDraft(
            required_capability="communication.wechat_desktop_send",
            requires_human_confirmation=True,
            risk_level="high",
        ),
    )


@dataclass
class _ExecutionPlaneService:
    status: str = "pending"
    error: ExecutionPlaneError | None = None
    task_error: TaskError | None = None
    requests: list[TaskRequest] = field(default_factory=list)

    def publish_task(self, request: TaskRequest) -> TaskExecution:
        if self.error is not None:
            raise self.error
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
            completed_at=now if self.status in {"done", "failed", "cancelled"} else None,
            error_ref=(
                self.task_error.error_ref
                if self.status == "failed" and self.task_error is not None
                else None
            ),
            session_id=cast(str, request.metadata["sessionId"]),
        )

    def get_error(self, error_ref: str) -> TaskError:
        if self.task_error is not None and self.task_error.error_ref == error_ref:
            return self.task_error
        raise ExecutionPlaneError(
            "result_not_found",
            f"Task error {error_ref!r} was not found.",
            retryable=False,
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
