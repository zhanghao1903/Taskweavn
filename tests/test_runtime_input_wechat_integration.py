from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from taskweavn.execution_plane import (
    WECHAT_SEND_CAPABILITY,
    EmbeddedTaskApiService,
    InMemoryExecutionEnvRegistry,
    InMemoryExecutionPlaneStore,
    SqliteWeChatSendBoundaryStore,
    WeChatSendRuntimeHandler,
    default_local_execution_env,
)
from taskweavn.integrations.wechat_desktop import (
    FakeWeChatDesktopAdapter,
    WeChatContactCandidate,
    WeChatContactResolution,
)
from taskweavn.interaction import AgentMessage, InProcessMessageBus, SqliteMessageStream
from taskweavn.server import HttpApiRequest, PlatoUiHttpTransport
from taskweavn.server.runtime_input_router import DefaultRuntimeInputRouter
from taskweavn.server.ui_contract import (
    ApiError,
    AskListResult,
    AskRequestView,
    CommandResponse,
    MainPageSnapshot,
    ProjectSummary,
    QueryResponse,
    SessionSummary,
    WorkflowSummary,
)
from taskweavn.task import InMemoryTaskBus

NOW = datetime(2026, 6, 24, 10, 0, tzinfo=UTC)


def test_runtime_input_wechat_route_rejects_without_send(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    first = _route_wechat_send(
        fixture.transport,
        command_id="route-wechat-reject",
        content="给微信文件传输助手发送一条消息：reject path",
    )
    task = _single_task(fixture)
    assert task.waiting_for_confirmation_id is not None
    _respond_to_confirmation(fixture, task.task_id, task.waiting_for_confirmation_id, "reject")

    second = _route_wechat_send(
        fixture.transport,
        command_id="route-wechat-reject",
        content="给微信文件传输助手发送一条消息：reject path",
    )
    execution = fixture.service.get_task(f"exec_{task.task_id}")

    assert first["data"]["outcome"]["status"] == "dispatched"
    assert first["data"]["outcome"]["userMessage"] == "微信发送任务已创建，正在等待用户确认。"
    assert second["data"]["outcome"]["status"] == "dispatched"
    assert execution.status == "failed"
    assert execution.error_ref is not None
    assert fixture.service.get_error(execution.error_ref).code == "wechat_send_rejected"
    assert _send_call_count(fixture.adapter) == 0


def test_runtime_input_wechat_route_confirm_sends_once(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    _route_wechat_send(
        fixture.transport,
        command_id="route-wechat-confirm",
        content="给微信文件传输助手发送一条消息：confirm path",
    )
    task = _single_task(fixture)
    assert task.waiting_for_confirmation_id is not None
    _respond_to_confirmation(fixture, task.task_id, task.waiting_for_confirmation_id, "confirm")

    second = _route_wechat_send(
        fixture.transport,
        command_id="route-wechat-confirm",
        content="给微信文件传输助手发送一条消息：confirm path",
    )
    third = _route_wechat_send(
        fixture.transport,
        command_id="route-wechat-confirm",
        content="给微信文件传输助手发送一条消息：confirm path",
    )
    execution = fixture.service.get_task(f"exec_{task.task_id}")

    assert second["data"]["outcome"]["status"] == "dispatched"
    assert third["data"]["outcome"]["status"] == "dispatched"
    assert execution.status == "done"
    assert execution.result_ref is not None
    result = fixture.service.get_result(execution.result_ref)
    assert result.structured_payload["kind"] == "wechat_send_result"
    assert result.structured_payload["messagePreview"] == "confirm path"
    assert _send_call_count(fixture.adapter) == 1


@dataclass
class _Fixture:
    transport: PlatoUiHttpTransport
    service: EmbeddedTaskApiService
    task_bus: InMemoryTaskBus
    message_bus: InProcessMessageBus
    adapter: FakeWeChatDesktopAdapter


def _fixture(tmp_path: Path) -> _Fixture:
    task_bus = InMemoryTaskBus()
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    message_bus = InProcessMessageBus(stream)
    execution_store = InMemoryExecutionPlaneStore()
    boundary_store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())
    service = EmbeddedTaskApiService(
        task_bus=task_bus,
        store=execution_store,
        env_registry=InMemoryExecutionEnvRegistry(
            (
                default_local_execution_env(
                    capabilities=(WECHAT_SEND_CAPABILITY,),
                    tool_pool=("computer_use", "wechat_desktop"),
                ),
            )
        ),
        runtime_handlers=(
            WeChatSendRuntimeHandler(
                task_bus=task_bus,
                message_bus=message_bus,
                message_stream=stream,
                execution_store=execution_store,
                boundary_store=boundary_store,
                adapter=adapter,
            ),
        ),
    )
    query = _QueryGateway()
    commands = _CommandGateway()
    router = DefaultRuntimeInputRouter(
        query_gateway=cast(Any, query),
        command_gateway=cast(Any, commands),
        execution_plane_service=service,
    )
    transport = PlatoUiHttpTransport(
        query_gateway=cast(Any, query),
        command_gateway=cast(Any, commands),
        runtime_input_router=router,
        execution_plane_service=service,
    )
    return _Fixture(
        transport=transport,
        service=service,
        task_bus=task_bus,
        message_bus=message_bus,
        adapter=adapter,
    )


def _route_wechat_send(
    transport: PlatoUiHttpTransport,
    *,
    command_id: str,
    content: str,
) -> dict[str, Any]:
    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/workspaces/workspace-1/sessions/session-1/runtime-input/route",
            body={
                "commandId": command_id,
                "sessionId": "session-1",
                "content": content,
                "selection": {"scopeKind": "session"},
            },
        )
    )
    assert response.status_code == 200
    assert isinstance(response.body, dict)
    assert response.body["ok"] is True
    return response.body


def _single_task(fixture: _Fixture) -> Any:
    tasks = fixture.task_bus.list_for_session("session-1")
    assert len(tasks) == 1
    return tasks[0]


def _respond_to_confirmation(
    fixture: _Fixture,
    task_id: str,
    confirmation_id: str,
    response_value: str,
) -> None:
    fixture.message_bus.publish(
        AgentMessage(
            session_id="session-1",
            task_id=task_id,
            agent_id="user",
            parent_message_id=confirmation_id,
            message_type="response",
            content=response_value,
            response_source="user",
            response_value=response_value,
        )
    )


def _resolved_contact() -> WeChatContactResolution:
    return WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(
            display_name="文件传输助手",
            subtitle="测试联系人",
            confidence=0.98,
        ),
    )


def _send_call_count(adapter: FakeWeChatDesktopAdapter) -> int:
    return sum(1 for name, _payload in adapter.calls if name == "send_after_confirmation")


@dataclass
class _QueryGateway:
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
        return QueryResponse[MainPageSnapshot](
            request_id=request_id or "snapshot",
            ok=True,
            data=MainPageSnapshot(
                project=project,
                workflows=(workflow,),
                workflow=workflow,
                sessions=(session,),
                session=session,
                generated_at=NOW,
            ),
        )


@dataclass
class _CommandGateway:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def answer_ask(self, *args: Any, **kwargs: Any) -> CommandResponse:
        raise AssertionError("answer_ask should not be called")

    def resolve_confirmation(self, *args: Any, **kwargs: Any) -> CommandResponse:
        raise AssertionError("resolve_confirmation should not be called")

    def stop_task(self, *args: Any, **kwargs: Any) -> CommandResponse:
        raise AssertionError("stop_task should not be called")

    def retry_task(self, *args: Any, **kwargs: Any) -> CommandResponse:
        raise AssertionError("retry_task should not be called")
