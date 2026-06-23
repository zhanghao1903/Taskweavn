from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from taskweavn.execution_plane import (
    WECHAT_SEND_CAPABILITY,
    WECHAT_SEND_TASK_TYPE,
    EmbeddedTaskApiService,
    ExecutionPlaneError,
    InMemoryExecutionEnvRegistry,
    InMemoryExecutionPlaneStore,
    SqliteWeChatSendBoundaryStore,
    TaskExecution,
    TaskRequest,
    WeChatSendRuntimeHandler,
    default_local_execution_env,
)
from taskweavn.integrations.wechat_desktop import (
    FakeWeChatDesktopAdapter,
    WeChatContactCandidate,
    WeChatContactResolution,
)
from taskweavn.interaction import AgentMessage, InProcessMessageBus, SqliteMessageStream
from taskweavn.task import InMemoryTaskBus


def test_wechat_runtime_publish_drafts_and_waits_for_confirmation(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    execution = fixture.service.publish_task(_wechat_request())

    assert execution.status == "waiting_for_user"
    task = fixture.task_bus.get("session-1", execution.task_id)
    assert task is not None
    assert task.status == "waiting_for_user"
    assert task.waiting_for_confirmation_id is not None
    boundary = fixture.boundary_store.get(execution.execution_id)
    assert boundary is not None
    assert boundary.status == "confirmation_requested"
    assert _send_call_count(fixture.adapter) == 0
    assert [call[0] for call in fixture.adapter.calls] == [
        "readiness",
        "open_or_focus",
        "resolve_contact",
        "draft_message",
    ]


def test_wechat_runtime_confirmed_replay_sends_once_and_projects_result(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    request = _wechat_request()
    first = fixture.service.publish_task(request)
    _respond_to_confirmation(fixture, first, "confirm")

    second = fixture.service.publish_task(request)
    third = fixture.service.publish_task(request)

    assert second.status == "done"
    assert second.result_ref is not None
    assert third.status == "done"
    assert third.result_ref == second.result_ref
    assert _send_call_count(fixture.adapter) == 1
    result = fixture.service.get_result(second.result_ref)
    assert result.structured_payload["kind"] == "wechat_send_result"
    assert result.structured_payload["messagePreview"] == "你好，样品已寄出。"
    evidence = fixture.service.list_evidence(second.execution_id)
    assert {item.title for item in evidence.items} >= {
        "WeChat readiness",
        "WeChat contact resolution",
        "WeChat draft",
        "WeChat send observation",
    }


def test_wechat_runtime_rejected_confirmation_fails_without_send(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    request = _wechat_request()
    first = fixture.service.publish_task(request)
    _respond_to_confirmation(fixture, first, "reject")

    second = fixture.service.publish_task(request)

    assert second.status == "failed"
    assert second.error_ref is not None
    assert _send_call_count(fixture.adapter) == 0
    error = fixture.service.get_error(second.error_ref)
    assert error.code == "wechat_send_rejected"


def test_wechat_runtime_requires_human_confirmation_policy(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    request = _wechat_request(requires_human_confirmation=False)

    with pytest.raises(ExecutionPlaneError) as exc_info:
        fixture.service.publish_task(request)

    assert exc_info.value.code == "permission_denied"
    assert fixture.task_bus.list_for_session("session-1") == []


def test_wechat_runtime_not_ready_fails_safely(tmp_path: Path) -> None:
    fixture = _fixture(
        tmp_path,
        adapter=FakeWeChatDesktopAdapter(
            readiness_result=FakeWeChatDesktopAdapter().readiness_result.__class__(
                status="not_logged_in",
                summary="WeChat Desktop requires login.",
                app_name="WeChat",
            ),
            contact_resolution=_resolved_contact(),
        ),
    )

    execution = fixture.service.publish_task(_wechat_request())

    assert execution.status == "failed"
    assert execution.error_ref is not None
    assert _send_call_count(fixture.adapter) == 0
    error = fixture.service.get_error(execution.error_ref)
    assert error.code == "wechat_not_ready"


def test_wechat_runtime_contact_failure_projects_diagnostics(tmp_path: Path) -> None:
    fixture = _fixture(
        tmp_path,
        adapter=FakeWeChatDesktopAdapter(
            contact_resolution=WeChatContactResolution(
                status="needs_user",
                reason="WeChat main window/search readiness AppleScript failed.",
                diagnostics={"stderr": "Can’t get UI element 1 of window 1"},
            ),
        ),
    )

    execution = fixture.service.publish_task(_wechat_request())

    assert execution.status == "failed"
    assert execution.error_ref is not None
    assert _send_call_count(fixture.adapter) == 0
    evidence = fixture.service.list_evidence(execution.execution_id)
    contact_evidence = next(
        item for item in evidence.items if item.title == "WeChat contact resolution"
    )
    assert contact_evidence.object_ref["reason"] == (
        "WeChat main window/search readiness AppleScript failed."
    )
    assert contact_evidence.object_ref["diagnostics"] == {
        "stderr": "Can’t get UI element 1 of window 1"
    }


@dataclass
class _Fixture:
    service: EmbeddedTaskApiService
    task_bus: InMemoryTaskBus
    message_stream: SqliteMessageStream
    message_bus: InProcessMessageBus
    boundary_store: SqliteWeChatSendBoundaryStore
    adapter: FakeWeChatDesktopAdapter


def _fixture(
    tmp_path: Path,
    *,
    adapter: FakeWeChatDesktopAdapter | None = None,
) -> _Fixture:
    task_bus = InMemoryTaskBus()
    message_stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    message_bus = InProcessMessageBus(message_stream)
    execution_store = InMemoryExecutionPlaneStore()
    boundary_store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    adapter = adapter or FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())
    handler = WeChatSendRuntimeHandler(
        task_bus=task_bus,
        message_bus=message_bus,
        message_stream=message_stream,
        execution_store=execution_store,
        boundary_store=boundary_store,
        adapter=adapter,
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
    return _Fixture(
        service=service,
        task_bus=task_bus,
        message_stream=message_stream,
        message_bus=message_bus,
        boundary_store=boundary_store,
        adapter=adapter,
    )


def _wechat_request(
    *,
    idempotency_key: str = "wechat-send-1",
    requires_human_confirmation: bool = True,
) -> TaskRequest:
    return TaskRequest.model_validate(
        {
            "idempotencyKey": idempotency_key,
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
                "requiresHumanConfirmation": requires_human_confirmation,
                "riskLevel": "high",
            },
            "metadata": {"sessionId": "session-1"},
        }
    )


def _resolved_contact() -> WeChatContactResolution:
    return WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(
            display_name="张三",
            subtitle="测试联系人",
            confidence=0.96,
        ),
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


def _send_call_count(adapter: FakeWeChatDesktopAdapter) -> int:
    return sum(1 for name, _payload in adapter.calls if name == "send_after_confirmation")
