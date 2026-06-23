"""Tests for send-after-confirmation WeChat execution closure."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from taskweavn.execution_plane import (
    InMemoryExecutionPlaneStore,
    SqliteWeChatSendBoundaryStore,
    WeChatSendBoundary,
    WeChatSendExecutionRequest,
    WeChatSendExecutionService,
)
from taskweavn.integrations.wechat_desktop import (
    FakeWeChatDesktopAdapter,
    WeChatDraftState,
    WeChatSendActionFingerprint,
    build_wechat_send_confirmation_payload,
    wechat_message_hash,
    wechat_message_preview,
)
from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendConfirmationAuthorizer,
)
from taskweavn.interaction import AgentMessage, InProcessMessageBus, SqliteMessageStream
from taskweavn.tools import RequestConfirmationTool


@dataclass
class _TaskBusStub:
    waits: list[tuple[str, str, str]] = field(default_factory=list)

    def wait_for_confirmation(
        self,
        session_id: str,
        task_id: str,
        *,
        confirmation_id: str,
    ) -> None:
        self.waits.append((session_id, task_id, confirmation_id))


def test_approved_confirmation_sends_once_and_projects_result(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, response_value="confirm")

    outcome = fixture.service.execute(fixture.request)

    assert outcome.status == "sent"
    assert outcome.result_ref is not None
    assert fixture.boundary_store.get("exec-1").status == "sent"  # type: ignore[union-attr]
    assert _send_call_count(fixture.adapter) == 1
    result = fixture.execution_store.get_result(outcome.result_ref)
    assert result is not None
    assert result.structured_payload["kind"] == "wechat_send_result"
    assert result.structured_payload["contactSummary"] == "张三"
    assert result.evidence_refs
    assert fixture.execution_store.list_evidence("exec-1")


def test_rejected_confirmation_marks_not_sent_without_adapter_call(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, response_value="reject")

    outcome = fixture.service.execute(fixture.request)

    assert outcome.status == "not_sent"
    assert outcome.error_ref is not None
    assert _send_call_count(fixture.adapter) == 0
    boundary = fixture.boundary_store.get("exec-1")
    assert boundary is not None
    assert boundary.status == "not_sent"
    error = fixture.execution_store.get_error(outcome.error_ref)
    assert error is not None
    assert error.code == "wechat_send_rejected"
    assert error.evidence_refs


def test_confirmation_fingerprint_mismatch_marks_not_sent_without_send(
    tmp_path: Path,
) -> None:
    confirmation_fingerprint = _fingerprint(execution_id="exec-1", idempotency_key="idem-1")
    request_fingerprint = _fingerprint(execution_id="exec-1", idempotency_key="idem-2")
    fixture = _fixture(
        tmp_path,
        response_value="confirm",
        confirmation_fingerprint=confirmation_fingerprint,
        request_fingerprint=request_fingerprint,
    )

    outcome = fixture.service.execute(fixture.request)

    assert outcome.status == "not_sent"
    assert _send_call_count(fixture.adapter) == 0
    assert outcome.error_ref is not None
    error = fixture.execution_store.get_error(outcome.error_ref)
    assert error is not None
    assert error.code == "wechat_send_confirmation_mismatch"


def test_sent_boundary_replay_does_not_call_adapter_again(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, response_value="confirm")

    first = fixture.service.execute(fixture.request)
    second = fixture.service.execute(fixture.request)

    assert first.status == "sent"
    assert second.status == "sent"
    assert second.result_ref == first.result_ref
    assert _send_call_count(fixture.adapter) == 1


def test_unknown_boundary_blocks_retry_without_adapter_call(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, response_value="confirm")
    fixture.boundary_store.transition("exec-1", "confirmed")
    fixture.boundary_store.transition("exec-1", "send_attempted")
    fixture.boundary_store.transition("exec-1", "unknown", error_ref="error:unknown")

    outcome = fixture.service.execute(fixture.request)

    assert outcome.status == "blocked"
    assert "manual review" in outcome.summary
    assert _send_call_count(fixture.adapter) == 0


def test_failed_send_attempt_becomes_unknown_and_manual_review_required(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, response_value="confirm", send_status="failed")

    outcome = fixture.service.execute(fixture.request)

    assert outcome.status == "unknown"
    assert outcome.error_ref is not None
    assert _send_call_count(fixture.adapter) == 1
    boundary = fixture.boundary_store.get("exec-1")
    assert boundary is not None
    assert boundary.status == "unknown"
    error = fixture.execution_store.get_error(outcome.error_ref)
    assert error is not None
    assert error.code == "wechat_send_unknown"
    assert error.retryable is False


def test_pre_submit_failure_marks_not_sent_without_manual_review(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, response_value="confirm", send_status="not_sent")

    outcome = fixture.service.execute(fixture.request)

    assert outcome.status == "not_sent"
    assert outcome.error_ref is not None
    assert _send_call_count(fixture.adapter) == 1
    boundary = fixture.boundary_store.get("exec-1")
    assert boundary is not None
    assert boundary.status == "not_sent"
    error = fixture.execution_store.get_error(outcome.error_ref)
    assert error is not None
    assert error.code == "wechat_send_not_attempted"
    evidence = fixture.execution_store.list_evidence("exec-1")
    send_evidence = next(
        item for item in evidence if item.title == "WeChat send observation"
    )
    assert send_evidence.object_ref["metadata"]["send_attempted"] == "false"


def test_pending_confirmation_waits_without_adapter_call(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, response_value=None)

    outcome = fixture.service.execute(fixture.request)

    assert outcome.status == "waiting_for_user"
    assert _send_call_count(fixture.adapter) == 0
    boundary = fixture.boundary_store.get("exec-1")
    assert boundary is not None
    assert boundary.status == "confirmation_requested"


@dataclass
class _Fixture:
    service: WeChatSendExecutionService
    request: WeChatSendExecutionRequest
    adapter: FakeWeChatDesktopAdapter
    boundary_store: SqliteWeChatSendBoundaryStore
    execution_store: InMemoryExecutionPlaneStore


def _fixture(
    tmp_path: Path,
    *,
    response_value: str | None,
    send_status: str = "sent",
    confirmation_fingerprint: WeChatSendActionFingerprint | None = None,
    request_fingerprint: WeChatSendActionFingerprint | None = None,
) -> _Fixture:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    task_bus = _TaskBusStub()
    draft = _draft_state()
    confirmation_fingerprint = confirmation_fingerprint or _fingerprint()
    request_fingerprint = request_fingerprint or confirmation_fingerprint
    payload = build_wechat_send_confirmation_payload(
        contact_summary=draft.contact_summary,
        message_preview=draft.message_preview,
        message_hash=draft.message_hash,
        action_fingerprint=confirmation_fingerprint,
    )
    observation = RequestConfirmationTool(
        message_bus=bus,
        task_bus=task_bus,  # type: ignore[arg-type]
        session_id="session-1",
        task_id="task-1",
    ).execute(payload.to_request_action())
    if response_value is not None:
        bus.publish(
            AgentMessage(
                session_id="session-1",
                task_id="task-1",
                agent_id="user",
                parent_message_id=observation.confirmation_id,
                message_type="response",
                content=response_value,
                response_source="user",
                response_value=response_value,
            )
        )

    boundary_store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    boundary_store.put(
        WeChatSendBoundary(
            execution_id=request_fingerprint.execution_id,
            idempotency_key=request_fingerprint.idempotency_key,
            task_ref_kind="task",
            task_ref_id="task-1",
            contact_summary_hash=request_fingerprint.contact_summary_hash,
            message_hash=request_fingerprint.message_hash,
            action_fingerprint=request_fingerprint.digest(),
        )
    )
    boundary_store.transition(
        request_fingerprint.execution_id,
        "drafted",
        draft_observation_ref=draft.draft_observation_ref,
    )
    boundary_store.transition(
        request_fingerprint.execution_id,
        "confirmation_requested",
        confirmation_id=observation.confirmation_id,
    )

    execution_store = InMemoryExecutionPlaneStore()
    adapter = FakeWeChatDesktopAdapter(send_status=send_status)  # type: ignore[arg-type]
    service = WeChatSendExecutionService(
        boundary_store=boundary_store,
        execution_store=execution_store,
        confirmation_authorizer=WeChatSendConfirmationAuthorizer(stream),
        adapter=adapter,
    )
    request = WeChatSendExecutionRequest(
        execution_id=request_fingerprint.execution_id,
        action_fingerprint=request_fingerprint,
        contact_summary=draft.contact_summary,
        message_preview=draft.message_preview,
    )
    return _Fixture(
        service=service,
        request=request,
        adapter=adapter,
        boundary_store=boundary_store,
        execution_store=execution_store,
    )


def _draft_state() -> WeChatDraftState:
    message_text = "你好，样品已寄出，麻烦查收。"
    return WeChatDraftState(
        status="drafted",
        contact_summary="张三",
        message_hash=wechat_message_hash(message_text),
        message_preview=wechat_message_preview(message_text),
        draft_observation_ref="observe:draft-1",
    )


def _fingerprint(
    *,
    execution_id: str = "exec-1",
    idempotency_key: str = "idem-1",
) -> WeChatSendActionFingerprint:
    return WeChatSendActionFingerprint.from_draft(
        execution_id=execution_id,
        idempotency_key=idempotency_key,
        draft_state=_draft_state(),
        app_identity="com.tencent.xinWeChat",
    )


def _send_call_count(adapter: FakeWeChatDesktopAdapter) -> int:
    return sum(1 for name, _payload in adapter.calls if name == "send_after_confirmation")
