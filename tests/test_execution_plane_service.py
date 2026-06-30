"""Tests for the embedded Execution Plane Task API service."""

from __future__ import annotations

import pytest

from taskweavn.execution_plane import (
    EmbeddedTaskApiService,
    EvidenceRef,
    ExecutionPlaneError,
    InMemoryExecutionEnvRegistry,
    SqliteExecutionPlaneStore,
    TaskRequest,
    TaskResult,
    default_local_execution_env,
)
from taskweavn.task import InMemoryTaskBus


def test_embedded_service_publishes_task_and_lists_acceptance_event() -> None:
    bus = InMemoryTaskBus()
    service = EmbeddedTaskApiService(task_bus=bus)
    request = _request(session_id="session-1")

    execution = service.publish_task(request)
    task = bus.get("session-1", execution.task_id)
    events = service.list_events(execution.execution_id)

    assert execution.status == "pending"
    assert execution.session_id == "session-1"
    assert execution.required_capability == "execute"
    assert task is not None
    assert task.intent == "Implement the selected task."
    assert task.dispatch_constraints is not None
    assert task.dispatch_constraints.metadata["execution_plane_task_type"] == (
        "plato.default_execution"
    )
    assert events.items[0].kind == "task.accepted"


def test_embedded_service_publish_is_idempotent_for_same_request() -> None:
    bus = InMemoryTaskBus()
    service = EmbeddedTaskApiService(task_bus=bus)
    request = _request(idempotency_key="publish-once", session_id="session-1")

    first = service.publish_task(request)
    second = service.publish_task(request)

    assert second == first
    assert len(bus.list_for_session("session-1")) == 1


def test_embedded_service_rejects_idempotency_key_reuse_with_different_payload() -> None:
    service = EmbeddedTaskApiService(task_bus=InMemoryTaskBus())
    first = _request(idempotency_key="same-key", intent="Do the first thing.")
    second = _request(idempotency_key="same-key", intent="Do a different thing.")

    service.publish_task(first)

    with pytest.raises(ExecutionPlaneError) as exc_info:
        service.publish_task(second)

    assert exc_info.value.code == "idempotency_conflict"
    assert exc_info.value.status_code == 409


def test_embedded_service_rejects_capability_without_compatible_env() -> None:
    service = EmbeddedTaskApiService(
        task_bus=InMemoryTaskBus(),
        env_registry=InMemoryExecutionEnvRegistry(
            (
                default_local_execution_env(
                    capabilities=("testing",),
                    tool_pool=(),
                ),
            )
        ),
    )

    with pytest.raises(ExecutionPlaneError) as exc_info:
        service.publish_task(_request(capability="execute"))

    assert exc_info.value.code == "capability_not_available"
    assert exc_info.value.retryable is True


def test_embedded_service_publishes_wechat_task_without_runtime_handler() -> None:
    bus = InMemoryTaskBus()
    service = EmbeddedTaskApiService(
        task_bus=bus,
        env_registry=InMemoryExecutionEnvRegistry(
            (
                default_local_execution_env(
                    capabilities=("communication.wechat_desktop_send",),
                    tool_pool=("computer_use", "wechat_desktop"),
                ),
            )
        ),
    )

    execution = service.publish_task(
        TaskRequest.model_validate(
            {
                "idempotencyKey": "wechat-runtime-required",
                "requester": {"kind": "external_app", "id": "local-test"},
                "taskType": "communication.wechat.send_message",
                "intent": "Send a WeChat message.",
                "input": {
                    "contactDisplayName": "文件传输助手",
                    "messageText": "你好",
                },
                "policy": {
                    "requiredCapability": "communication.wechat_desktop_send",
                    "allowedTools": ["computer_use", "wechat_desktop"],
                    "requiresHumanConfirmation": True,
                    "riskLevel": "high",
                },
                "metadata": {"sessionId": "session-1"},
            }
        )
    )

    assert execution.status == "pending"
    [task] = bus.list_for_session("session-1")
    assert task.required_capability == "communication.wechat_desktop_send"
    assert task.dispatch_constraints is not None
    assert task.dispatch_constraints.metadata["execution_plane_allowed_tools"] == [
        "computer_use",
        "wechat_desktop",
    ]


def test_embedded_service_reflects_taskbus_completion_and_exposes_result_evidence() -> None:
    bus = InMemoryTaskBus()
    service = EmbeddedTaskApiService(task_bus=bus)
    execution = service.publish_task(_request(session_id="session-1"))
    claimed = bus.claim_next("session-1", capability="execute", agent_id="agent-1")
    assert claimed is not None
    bus.complete("session-1", claimed.task_id, result_ref="result:task-1")
    service.record_result(
        TaskResult(
            result_ref="result:task-1",
            execution_id=execution.execution_id,
            summary="Task completed.",
        )
    )
    service.record_evidence(
        EvidenceRef(
            evidence_id="evidence-1",
            execution_id=execution.execution_id,
            kind="tool_observation",
            title="Observation",
            summary="Tool produced a useful observation.",
        )
    )

    updated = service.get_task(execution.execution_id)
    result = service.get_result("result:task-1")
    evidence = service.list_evidence(execution.execution_id)

    assert updated.status == "done"
    assert updated.result_ref == "result:task-1"
    assert result.summary == "Task completed."
    assert evidence.items[0].evidence_id == "evidence-1"


def test_sqlite_execution_plane_store_preserves_idempotent_publish_after_restart(
    tmp_path,
) -> None:
    bus = InMemoryTaskBus()
    db_path = tmp_path / "execution-plane.sqlite"
    request = _request(idempotency_key="durable-key", session_id="session-1")

    with SqliteExecutionPlaneStore(db_path) as store:
        first = EmbeddedTaskApiService(task_bus=bus, store=store).publish_task(request)

    with SqliteExecutionPlaneStore(db_path) as reopened:
        replay = EmbeddedTaskApiService(task_bus=bus, store=reopened).publish_task(request)

    assert replay.execution_id == first.execution_id
    assert len(bus.list_for_session("session-1")) == 1


def _request(
    *,
    idempotency_key: str = "publish-task-1",
    session_id: str = "session-1",
    intent: str = "Implement the selected task.",
    capability: str = "execute",
) -> TaskRequest:
    return TaskRequest.model_validate(
        {
            "idempotencyKey": idempotency_key,
            "requester": {"kind": "plato", "id": "workspace:local"},
            "externalRef": {
                "system": "plato",
                "kind": "task_node",
                "id": "task-node-1",
            },
            "taskType": "plato.default_execution",
            "intent": intent,
            "input": {
                "summary": "Selected task summary.",
                "instructions": "Use the current workspace.",
                "acceptanceCriteria": ["Result is visible."],
            },
            "policy": {"requiredCapability": capability},
            "metadata": {"sessionId": session_id},
        }
    )
