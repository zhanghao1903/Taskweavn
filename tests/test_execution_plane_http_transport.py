"""Tests for local HTTP shell routes for the Execution Plane Task API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from taskweavn.execution_plane import (
    WECHAT_SEND_CAPABILITY,
    WECHAT_SEND_TASK_TYPE,
    EmbeddedTaskApiService,
    InMemoryExecutionEnvRegistry,
    InMemoryExecutionPlaneStore,
    SqliteWeChatSendBoundaryStore,
    TaskResult,
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
from taskweavn.task import InMemoryTaskBus


def test_http_task_api_publish_get_events_and_result() -> None:
    bus = InMemoryTaskBus()
    service = EmbeddedTaskApiService(task_bus=bus)
    transport = _transport(service=service)

    published = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/tasks",
            body=_request_body(),
        )
    )
    body = _dict_body(published.body)
    execution_id = body["data"]["executionId"]
    task_id = body["data"]["taskId"]
    claimed = bus.claim_next("session-1", capability="execute", agent_id="agent-1")
    assert claimed is not None
    bus.complete("session-1", task_id, result_ref="result:task-1")
    service.record_result(
        TaskResult(
            result_ref="result:task-1",
            execution_id=execution_id,
            summary="Task completed through HTTP shell.",
        )
    )

    fetched = transport.handle(
        HttpApiRequest(method="GET", path=f"/api/v1/tasks/{execution_id}")
    )
    events = transport.handle(
        HttpApiRequest(method="GET", path=f"/api/v1/tasks/{execution_id}/events")
    )
    result = transport.handle(
        HttpApiRequest(method="GET", path=f"/api/v1/tasks/{execution_id}/result")
    )

    assert published.status_code == 200
    assert _dict_body(fetched.body)["data"]["status"] == "done"
    assert _dict_body(events.body)["data"]["items"][0]["kind"] == "task.accepted"
    assert _dict_body(result.body)["data"]["summary"] == (
        "Task completed through HTTP shell."
    )


def test_http_task_api_requires_configured_service() -> None:
    response = _transport().handle(
        HttpApiRequest(method="POST", path="/api/v1/tasks", body=_request_body())
    )

    assert response.status_code == 503
    assert _dict_body(response.body)["error"]["details"]["route"] == (
        "execution_plane_publish"
    )


def test_http_task_api_maps_idempotency_conflict() -> None:
    service = EmbeddedTaskApiService(task_bus=InMemoryTaskBus())
    transport = _transport(service=service)

    first = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/tasks",
            body=_request_body(idempotency_key="same-key", intent="First intent."),
        )
    )
    conflict = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/tasks",
            body=_request_body(idempotency_key="same-key", intent="Second intent."),
        )
    )
    body = _dict_body(conflict.body)

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert body["error"]["code"] == "idempotency_conflict"
    assert body["error"]["details"]["serviceCode"] == "idempotency_conflict"


def test_workspace_prefixed_task_api_injects_workspace_metadata() -> None:
    service = EmbeddedTaskApiService(task_bus=InMemoryTaskBus())
    transport = _transport(service=service)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/workspaces/workspace-1/tasks",
            body=_request_body(idempotency_key="workspace-key"),
        )
    )

    assert response.status_code == 200
    assert _dict_body(response.body)["data"]["executionId"].startswith("exec_")


def test_http_wechat_send_route_waits_for_confirmation_then_projects_result(
    tmp_path: Path,
) -> None:
    bus = InMemoryTaskBus()
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    message_bus = InProcessMessageBus(stream)
    execution_store = InMemoryExecutionPlaneStore()
    boundary_store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())
    service = EmbeddedTaskApiService(
        task_bus=bus,
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
                task_bus=bus,
                message_bus=message_bus,
                message_stream=stream,
                execution_store=execution_store,
                boundary_store=boundary_store,
                adapter=adapter,
            ),
        ),
    )
    transport = _transport(service=service)

    first = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/tasks",
            body=_wechat_request_body(),
        )
    )
    first_body = _dict_body(first.body)
    execution_id = first_body["data"]["executionId"]
    task_id = first_body["data"]["taskId"]
    task = bus.get("session-1", task_id)
    assert task is not None
    assert task.waiting_for_confirmation_id is not None
    message_bus.publish(
        AgentMessage(
            session_id="session-1",
            task_id=task_id,
            agent_id="user",
            parent_message_id=task.waiting_for_confirmation_id,
            message_type="response",
            content="confirm",
            response_source="user",
            response_value="confirm",
        )
    )

    second = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/tasks",
            body=_wechat_request_body(),
        )
    )
    result = transport.handle(
        HttpApiRequest(method="GET", path=f"/api/v1/tasks/{execution_id}/result")
    )

    assert first.status_code == 200
    assert first_body["data"]["status"] == "waiting_for_user"
    assert second.status_code == 200
    assert _dict_body(second.body)["data"]["status"] == "done"
    assert _dict_body(result.body)["data"]["structuredPayload"]["kind"] == (
        "wechat_send_result"
    )


def _transport(
    *,
    service: EmbeddedTaskApiService | None = None,
) -> PlatoUiHttpTransport:
    return PlatoUiHttpTransport(
        query_gateway=cast(Any, object()),
        command_gateway=cast(Any, object()),
        execution_plane_service=service,
    )


def _request_body(
    *,
    idempotency_key: str = "publish-task-1",
    intent: str = "Implement the selected task.",
) -> dict[str, Any]:
    return {
        "idempotencyKey": idempotency_key,
        "requester": {"kind": "plato", "id": "workspace:local"},
        "externalRef": {
            "system": "plato",
            "kind": "task_node",
            "id": "task-node-1",
        },
        "taskType": "plato.default_execution",
        "intent": intent,
        "input": {"instructions": "Use the current workspace."},
        "policy": {"requiredCapability": "execute"},
        "metadata": {"sessionId": "session-1"},
    }


def _wechat_request_body() -> dict[str, Any]:
    return {
        "idempotencyKey": "wechat-send-http-1",
        "requester": {"kind": "external_app", "id": "local-test"},
        "externalRef": {
            "system": "test",
            "kind": "wechat_message",
            "id": "msg-1",
        },
        "taskType": WECHAT_SEND_TASK_TYPE,
        "intent": "Send one confirmed WeChat message.",
        "input": {
            "contactDisplayName": "张三",
            "messageText": "你好，样品已寄出。",
        },
        "policy": {
            "requiredCapability": WECHAT_SEND_CAPABILITY,
            "allowedTools": ["computer_use", "wechat_desktop"],
            "requiresHumanConfirmation": True,
            "riskLevel": "high",
        },
        "metadata": {"sessionId": "session-1"},
    }


def _resolved_contact() -> WeChatContactResolution:
    return WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(
            display_name="张三",
            subtitle="测试联系人",
            confidence=0.96,
        ),
    )


def _dict_body(body: Any) -> dict[str, Any]:
    assert isinstance(body, dict)
    return body
