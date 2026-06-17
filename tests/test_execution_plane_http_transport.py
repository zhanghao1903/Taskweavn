"""Tests for local HTTP shell routes for the Execution Plane Task API."""

from __future__ import annotations

from typing import Any, cast

from taskweavn.execution_plane import EmbeddedTaskApiService, TaskResult
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


def _dict_body(body: Any) -> dict[str, Any]:
    assert isinstance(body, dict)
    return body
