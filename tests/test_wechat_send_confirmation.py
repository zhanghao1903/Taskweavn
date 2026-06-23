"""Tests for the confirmation-gated local WeChat send boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from taskweavn.integrations.wechat_desktop import (
    WeChatDraftState,
    WeChatSendActionFingerprint,
    WeChatSendConfirmationAuthorizer,
    build_wechat_send_confirmation_payload,
    wechat_message_hash,
    wechat_message_preview,
)
from taskweavn.interaction import AgentMessage, InProcessMessageBus, SqliteMessageStream
from taskweavn.tools import RequestConfirmationTool
from taskweavn.types.confirmation import RequestConfirmationAction


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


def test_wechat_send_confirmation_is_pending_until_user_response(
    tmp_path: Path,
) -> None:
    stream, _bus, task_bus, confirmation_id, fingerprint = _create_confirmation(tmp_path)

    message = stream.get(confirmation_id)
    assert message is not None
    assert message.message_type == "actionable"
    assert message.context["confirmation_kind"] == "wechat_send"
    assert message.context["action_fingerprint"] == fingerprint.digest()
    assert message.action_options == ["confirm", "reject", "approve_session"]
    assert task_bus.waits == [("session-1", "task-1", confirmation_id)]

    result = WeChatSendConfirmationAuthorizer(stream).authorize(
        confirmation_id=confirmation_id,
        action_fingerprint=fingerprint,
    )

    assert result.status == "pending"
    assert result.authorized is False


def test_wechat_send_confirmation_authorizes_explicit_confirm(
    tmp_path: Path,
) -> None:
    stream, bus, _task_bus, confirmation_id, fingerprint = _create_confirmation(tmp_path)
    _publish_response(bus, confirmation_id, "confirm")

    result = WeChatSendConfirmationAuthorizer(stream).authorize(
        confirmation_id=confirmation_id,
        action_fingerprint=fingerprint,
    )

    assert result.status == "authorized"
    assert result.authorized is True
    assert result.response_value == "confirm"
    assert result.response_source == "user"


def test_wechat_send_confirmation_authorizes_current_send_for_session_approval(
    tmp_path: Path,
) -> None:
    stream, bus, _task_bus, confirmation_id, fingerprint = _create_confirmation(tmp_path)
    _publish_response(bus, confirmation_id, "approve_session")

    result = WeChatSendConfirmationAuthorizer(stream).authorize(
        confirmation_id=confirmation_id,
        action_fingerprint=fingerprint,
    )

    assert result.status == "authorized"
    assert result.authorized is True
    assert result.response_value == "approve_session"


def test_wechat_send_confirmation_rejects_user_reject(tmp_path: Path) -> None:
    stream, bus, _task_bus, confirmation_id, fingerprint = _create_confirmation(tmp_path)
    _publish_response(bus, confirmation_id, "reject")

    result = WeChatSendConfirmationAuthorizer(stream).authorize(
        confirmation_id=confirmation_id,
        action_fingerprint=fingerprint,
    )

    assert result.status == "rejected"
    assert result.authorized is False


def test_wechat_send_confirmation_rejects_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    stream, bus, _task_bus, confirmation_id, fingerprint = _create_confirmation(tmp_path)
    _publish_response(bus, confirmation_id, "confirm")
    mismatched = WeChatSendActionFingerprint(
        execution_id=fingerprint.execution_id,
        idempotency_key="different-idempotency-key",
        contact_summary_hash=fingerprint.contact_summary_hash,
        message_hash=fingerprint.message_hash,
        draft_observation_ref=fingerprint.draft_observation_ref,
        app_identity=fingerprint.app_identity,
    )

    result = WeChatSendConfirmationAuthorizer(stream).authorize(
        confirmation_id=confirmation_id,
        action_fingerprint=mismatched,
    )

    assert result.status == "mismatch"
    assert result.authorized is False


def test_wechat_send_confirmation_expires_before_send(tmp_path: Path) -> None:
    now = datetime(2026, 6, 20, 8, 30, tzinfo=UTC)
    stream, bus, _task_bus, confirmation_id, fingerprint = _create_confirmation(
        tmp_path,
        expires_at=now - timedelta(seconds=1),
    )
    _publish_response(bus, confirmation_id, "confirm")

    result = WeChatSendConfirmationAuthorizer(stream, now=lambda: now).authorize(
        confirmation_id=confirmation_id,
        action_fingerprint=fingerprint,
    )

    assert result.status == "expired"
    assert result.authorized is False


def test_wechat_send_confirmation_rejects_non_wechat_confirmation(
    tmp_path: Path,
) -> None:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    task_bus = _TaskBusStub()
    generic = RequestConfirmationAction(
        title="Confirm file write",
        body="Write a local file.",
        risk_label="file write",
    )
    observation = RequestConfirmationTool(
        message_bus=bus,
        task_bus=task_bus,  # type: ignore[arg-type]
        session_id="session-1",
        task_id="task-1",
    ).execute(generic)
    fingerprint = _fingerprint()

    result = WeChatSendConfirmationAuthorizer(stream).authorize(
        confirmation_id=observation.confirmation_id,
        action_fingerprint=fingerprint,
    )

    assert result.status == "invalid"
    assert result.authorized is False


def _create_confirmation(
    tmp_path: Path,
    *,
    expires_at: datetime | None = None,
) -> tuple[
    SqliteMessageStream,
    InProcessMessageBus,
    _TaskBusStub,
    str,
    WeChatSendActionFingerprint,
]:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    task_bus = _TaskBusStub()
    draft = _draft_state()
    fingerprint = _fingerprint(draft_state=draft)
    payload = build_wechat_send_confirmation_payload(
        contact_summary=draft.contact_summary,
        message_preview=draft.message_preview,
        message_hash=draft.message_hash,
        action_fingerprint=fingerprint,
        expires_at=expires_at,
    )
    observation = RequestConfirmationTool(
        message_bus=bus,
        task_bus=task_bus,  # type: ignore[arg-type]
        session_id="session-1",
        task_id="task-1",
    ).execute(payload.to_request_action())
    return stream, bus, task_bus, observation.confirmation_id, fingerprint


def _draft_state() -> WeChatDraftState:
    message_text = "你好，想确认一下本周的合作排期是否方便。"
    return WeChatDraftState(
        status="drafted",
        contact_summary="张三",
        message_hash=wechat_message_hash(message_text),
        message_preview=wechat_message_preview(message_text),
        draft_observation_ref="observe:draft-1",
    )


def _fingerprint(
    *,
    draft_state: WeChatDraftState | None = None,
) -> WeChatSendActionFingerprint:
    return WeChatSendActionFingerprint.from_draft(
        execution_id="exec-1",
        idempotency_key="idem-1",
        draft_state=draft_state or _draft_state(),
        app_identity="com.tencent.xinWeChat",
    )


def _publish_response(
    bus: InProcessMessageBus,
    confirmation_id: str,
    value: str,
) -> None:
    bus.publish(
        AgentMessage(
            session_id="session-1",
            task_id="task-1",
            agent_id="user",
            parent_message_id=confirmation_id,
            message_type="response",
            content=value,
            response_source="user",
            response_value=value,
        )
    )
