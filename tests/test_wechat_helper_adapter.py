from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from taskweavn.execution_plane import (
    WECHAT_SEND_CAPABILITY,
    WECHAT_SEND_TASK_TYPE,
    EmbeddedTaskApiService,
    InMemoryExecutionEnvRegistry,
    InMemoryExecutionPlaneStore,
    SqliteWeChatSendBoundaryStore,
    TaskExecution,
    TaskRequest,
    WeChatSendRuntimeHandler,
    default_local_execution_env,
)
from taskweavn.integrations.wechat_desktop import (
    WeChatDesktopHelperAdapter,
    wechat_message_hash,
)
from taskweavn.interaction import AgentMessage, InProcessMessageBus, SqliteMessageStream
from taskweavn.task import InMemoryTaskBus
from taskweavn.types.computer_use import ComputerUseAction


def test_wechat_runtime_uses_helper_wechat_api_for_draft_and_send(
    tmp_path: Path,
) -> None:
    helper_client = _FakeWeChatHelperClient()
    fixture = _fixture(tmp_path, helper_client=helper_client)
    request = _wechat_request()

    first = fixture.service.publish_task(request)
    _respond_to_confirmation(fixture, first, "confirm")
    second = fixture.service.publish_task(request)

    assert first.status == "waiting_for_user"
    assert second.status == "done"
    assert second.result_ref is not None
    assert len(helper_client.open_calls) == 1
    assert len(helper_client.draft_calls) == 1
    assert len(helper_client.send_calls) == 1
    open_call = helper_client.open_calls[0]
    assert open_call["path"] == "/v1/operations/open-app"
    assert open_call["target"] == "WeChat"
    draft_call = helper_client.draft_calls[0]
    assert draft_call["path"] == "/v1/apps/wechat/draft-message"
    assert draft_call["contact_display_name"] == "文件传输助手"
    assert draft_call["message_text"] == "你好"
    send_call = helper_client.send_calls[0]
    assert send_call["path"] == "/v1/apps/wechat/send-confirmed"
    assert send_call["confirmation_id"] != "unknown-confirmation"
    assert send_call["action_fingerprint"]
    assert send_call["action_fingerprint_payload"]["execution_id"] == second.execution_id


@dataclass
class _Fixture:
    service: EmbeddedTaskApiService
    task_bus: InMemoryTaskBus
    message_bus: InProcessMessageBus


def _fixture(
    tmp_path: Path,
    *,
    helper_client: _FakeWeChatHelperClient,
) -> _Fixture:
    task_bus = InMemoryTaskBus()
    message_stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    message_bus = InProcessMessageBus(message_stream)
    execution_store = InMemoryExecutionPlaneStore()
    boundary_store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    handler = WeChatSendRuntimeHandler(
        task_bus=task_bus,
        message_bus=message_bus,
        message_stream=message_stream,
        execution_store=execution_store,
        boundary_store=boundary_store,
        adapter=WeChatDesktopHelperAdapter(helper_client),
    )
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
        runtime_handlers=(handler,),
    )
    return _Fixture(service=service, task_bus=task_bus, message_bus=message_bus)


def _wechat_request() -> TaskRequest:
    return TaskRequest.model_validate(
        {
            "idempotencyKey": "wechat-helper-send-1",
            "requester": {"kind": "external_app", "id": "local-test"},
            "externalRef": {
                "system": "test",
                "kind": "wechat_message",
                "id": "msg-1",
            },
            "taskType": WECHAT_SEND_TASK_TYPE,
            "intent": "Send one confirmed WeChat message.",
            "input": {
                "contactDisplayName": "文件传输助手",
                "messageText": "你好",
            },
            "policy": {
                "requiredCapability": WECHAT_SEND_CAPABILITY,
                "allowedTools": ["computer_use", "wechat_desktop"],
                "requiresHumanConfirmation": True,
                "riskLevel": "high",
            },
            "metadata": {"sessionId": "session-1"},
        }
    )


def _respond_to_confirmation(
    fixture: _Fixture,
    execution: TaskExecution,
    response_value: str,
) -> None:
    task = fixture.task_bus.get("session-1", execution.task_id)
    assert task is not None
    assert task.waiting_for_confirmation_id is not None
    fixture.message_bus.publish(
        AgentMessage(
            session_id="session-1",
            task_id=execution.task_id,
            agent_id="user",
            parent_message_id=task.waiting_for_confirmation_id,
            message_type="response",
            content=response_value,
            response_source="user",
            response_value=response_value,
        )
    )


@dataclass
class _FakeWeChatHelperClient:
    open_calls: list[dict[str, Any]] = field(default_factory=list)
    draft_calls: list[dict[str, Any]] = field(default_factory=list)
    send_calls: list[dict[str, Any]] = field(default_factory=list)

    def readiness(self) -> Mapping[str, Any]:
        return {
            "status": "ready",
            "success": True,
            "summary": "Helper ready.",
        }

    def execute(self, action: ComputerUseAction) -> Mapping[str, Any]:
        self.open_calls.append(
            {
                "path": "/v1/operations/open-app",
                "request_id": action.event_id,
                "operation": action.operation,
                "target": action.target,
            }
        )
        return {
            "requestId": action.event_id,
            "operation": action.operation,
            "status": "ok",
            "success": True,
            "summary": "Opened app: WeChat",
            "metadata": {"app": "WeChat"},
        }

    def wechat_draft_message(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        caller: Mapping[str, str],
        contact_display_name: str,
        message_text: str,
        contact_alias: str | None = None,
        operator_note: str | None = None,
        external_ref: Mapping[str, str] | None = None,
        app_identity: str | None = None,
    ) -> Mapping[str, Any]:
        self.draft_calls.append(
            {
                "path": "/v1/apps/wechat/draft-message",
                "request_id": request_id,
                "idempotency_key": idempotency_key,
                "caller": dict(caller),
                "contact_display_name": contact_display_name,
                "message_text": message_text,
                "contact_alias": contact_alias,
                "operator_note": operator_note,
                "external_ref": dict(external_ref or {}),
                "app_identity": app_identity,
            }
        )
        return {
            "requestId": request_id,
            "operation": "wechat.draft_message",
            "status": "ok",
            "success": True,
            "summary": f"Drafted message for contact {contact_display_name}.",
            "phase": "draft",
            "contactResolution": {
                "status": "resolved",
                "selected": contact_display_name,
                "observationRef": "helper-contact-observation",
            },
            "draftState": {
                "status": "drafted",
                "contactSummary": contact_display_name,
                "messageHash": wechat_message_hash(message_text),
                "messagePreview": message_text,
                "draftObservationRef": "helper-draft-observation",
            },
            "evidence": {"observationRef": "helper-draft-observation"},
            "diagnostics": {},
        }

    def wechat_send_confirmed(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        caller: Mapping[str, str],
        action_fingerprint_payload: Mapping[str, Any],
        action_fingerprint: str,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str,
    ) -> Mapping[str, Any]:
        self.send_calls.append(
            {
                "path": "/v1/apps/wechat/send-confirmed",
                "request_id": request_id,
                "idempotency_key": idempotency_key,
                "caller": dict(caller),
                "action_fingerprint_payload": dict(action_fingerprint_payload),
                "action_fingerprint": action_fingerprint,
                "contact_summary": contact_summary,
                "message_preview": message_preview,
                "confirmation_id": confirmation_id,
            }
        )
        return {
            "requestId": request_id,
            "operation": "wechat.send_confirmed",
            "status": "sent",
            "success": True,
            "summary": "WeChat message submitted with keyboard Return.",
            "phase": "keyboard_submit",
            "evidence": {
                "targetApp": "WeChat",
                "targetContact": contact_summary,
                "observationRef": "helper-send-observation",
                "redaction": "no_raw_chat_history",
            },
            "diagnostics": {
                "send_method": "keyboard_return",
                "send_attempted": "true",
            },
        }
