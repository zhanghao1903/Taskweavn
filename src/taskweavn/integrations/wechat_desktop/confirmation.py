"""Confirmation boundary helpers for local WeChat send actions."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal

from taskweavn.interaction import MessageStream
from taskweavn.types.confirmation import RequestConfirmationAction

from .models import WeChatDraftState

WeChatSendAuthorizationStatus = Literal[
    "authorized",
    "pending",
    "rejected",
    "mismatch",
    "expired",
    "not_found",
    "invalid",
]

_AUTHORIZE_DECISIONS = {"confirm", "approve_session"}
_REJECT_DECISIONS = {"reject", "cancel", "skip"}


@dataclass(frozen=True)
class WeChatSendActionFingerprint:
    """Stable identity for the exact WeChat draft a user confirmed."""

    execution_id: str
    idempotency_key: str
    contact_summary_hash: str
    message_hash: str
    draft_observation_ref: str | None
    app_identity: str

    @classmethod
    def from_draft(
        cls,
        *,
        execution_id: str,
        idempotency_key: str,
        draft_state: WeChatDraftState,
        app_identity: str,
    ) -> WeChatSendActionFingerprint:
        return cls(
            execution_id=_required("execution_id", execution_id),
            idempotency_key=_required("idempotency_key", idempotency_key),
            contact_summary_hash=_hash_text(draft_state.contact_summary),
            message_hash=_required("message_hash", draft_state.message_hash),
            draft_observation_ref=draft_state.draft_observation_ref,
            app_identity=_required("app_identity", app_identity),
        )

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()

    def to_safe_context(self) -> dict[str, str | None]:
        return {
            "execution_id": self.execution_id,
            "idempotency_key": self.idempotency_key,
            "contact_summary_hash": self.contact_summary_hash,
            "message_hash": self.message_hash,
            "draft_observation_ref": self.draft_observation_ref,
            "app_identity": self.app_identity,
        }


@dataclass(frozen=True)
class WeChatSendConfirmationPayload:
    """User-facing confirmation payload for one pending WeChat send."""

    title: str
    body: str
    action_fingerprint: WeChatSendActionFingerprint
    contact_summary: str
    message_preview: str
    message_hash: str
    risk_label: str = "external message"
    options: tuple[str, ...] = ("confirm", "reject")
    default_option: str = "reject"
    allow_session_approval: bool = True
    expires_at: datetime | None = None

    def to_request_action(self) -> RequestConfirmationAction:
        return RequestConfirmationAction(
            title=self.title,
            body=self.body,
            risk_label=self.risk_label,
            options=self.options,
            default_option=self.default_option,
            allow_session_approval=self.allow_session_approval,
            context=self.context(),
        )

    def context(self) -> dict[str, object]:
        context: dict[str, object] = {
            "confirmation_kind": "wechat_send",
            "action_fingerprint": self.action_fingerprint.digest(),
            "action_fingerprint_payload": self.action_fingerprint.to_safe_context(),
            "wechat_contact_summary": self.contact_summary,
            "wechat_message_hash": self.message_hash,
            "wechat_message_preview": self.message_preview,
        }
        if self.expires_at is not None:
            context["expires_at"] = _as_utc(self.expires_at).isoformat()
        return context


@dataclass(frozen=True)
class WeChatSendConfirmationAuthorization:
    """Decision after checking a confirmation response against a fingerprint."""

    status: WeChatSendAuthorizationStatus
    confirmation_id: str
    fingerprint_digest: str
    response_value: str | None = None
    response_source: str | None = None
    reason: str | None = None

    @property
    def authorized(self) -> bool:
        return self.status == "authorized"


class WeChatSendConfirmationAuthorizer:
    """Validate that a user response authorizes one exact WeChat send."""

    def __init__(
        self,
        message_stream: MessageStream,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._message_stream = message_stream
        self._now = now or (lambda: datetime.now(UTC))

    def authorize(
        self,
        *,
        confirmation_id: str,
        action_fingerprint: WeChatSendActionFingerprint,
    ) -> WeChatSendConfirmationAuthorization:
        expected_digest = action_fingerprint.digest()
        confirmation = self._message_stream.get(confirmation_id)
        if confirmation is None:
            return self._result(
                "not_found",
                confirmation_id,
                expected_digest,
                reason="confirmation message not found",
            )
        if (
            confirmation.message_type != "actionable"
            or not confirmation.requires_response
            or confirmation.context.get("confirmation_kind") != "wechat_send"
        ):
            return self._result(
                "invalid",
                confirmation_id,
                expected_digest,
                reason="confirmation message is not a WeChat send confirmation",
            )
        actual_digest = confirmation.context.get("action_fingerprint")
        if actual_digest != expected_digest:
            return self._result(
                "mismatch",
                confirmation_id,
                expected_digest,
                reason="confirmation fingerprint does not match pending send",
            )
        expired_reason = self._expired_reason(confirmation.context.get("expires_at"))
        if expired_reason is not None:
            return self._result(
                "expired",
                confirmation_id,
                expected_digest,
                reason=expired_reason,
            )
        response = self._message_stream.response_for(confirmation_id)
        if response is None:
            return self._result(
                "pending",
                confirmation_id,
                expected_digest,
                reason="waiting for user response",
            )
        decision = (response.response_value or "").strip()
        if response.response_source != "user":
            return self._result(
                "invalid",
                confirmation_id,
                expected_digest,
                response_value=decision or None,
                response_source=response.response_source,
                reason="WeChat send requires an explicit user response",
            )
        if decision in _AUTHORIZE_DECISIONS:
            return self._result(
                "authorized",
                confirmation_id,
                expected_digest,
                response_value=decision,
                response_source=response.response_source,
            )
        if decision in _REJECT_DECISIONS:
            return self._result(
                "rejected",
                confirmation_id,
                expected_digest,
                response_value=decision,
                response_source=response.response_source,
                reason="user rejected WeChat send",
            )
        return self._result(
            "invalid",
            confirmation_id,
            expected_digest,
            response_value=decision or None,
            response_source=response.response_source,
            reason="unsupported WeChat send confirmation response",
        )

    def _expired_reason(self, expires_at: object) -> str | None:
        if expires_at is None:
            return None
        if not isinstance(expires_at, str) or not expires_at.strip():
            return "confirmation expiry is invalid"
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return "confirmation expiry is invalid"
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry <= _as_utc(self._now()):
            return "confirmation expired"
        return None

    @staticmethod
    def _result(
        status: WeChatSendAuthorizationStatus,
        confirmation_id: str,
        fingerprint_digest: str,
        *,
        response_value: str | None = None,
        response_source: str | None = None,
        reason: str | None = None,
    ) -> WeChatSendConfirmationAuthorization:
        return WeChatSendConfirmationAuthorization(
            status=status,
            confirmation_id=confirmation_id,
            fingerprint_digest=fingerprint_digest,
            response_value=response_value,
            response_source=response_source,
            reason=reason,
        )


def build_wechat_send_confirmation_payload(
    *,
    contact_summary: str,
    message_preview: str,
    message_hash: str,
    action_fingerprint: WeChatSendActionFingerprint,
    expires_at: datetime | None = None,
) -> WeChatSendConfirmationPayload:
    contact = _required("contact_summary", contact_summary)
    preview = _required("message_preview", message_preview)
    message_digest = _required("message_hash", message_hash)
    return WeChatSendConfirmationPayload(
        title="Confirm WeChat send",
        body=(
            "Plato has drafted a WeChat message and needs approval before "
            "sending.\n\n"
            f"Contact: {contact}\n"
            f"Message preview: {preview}"
        ),
        contact_summary=contact,
        message_preview=preview,
        message_hash=message_digest,
        action_fingerprint=action_fingerprint,
        expires_at=expires_at,
    )


def _hash_text(value: str) -> str:
    return sha256(_required("value", value).encode("utf-8")).hexdigest()


def _required(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "WeChatSendActionFingerprint",
    "WeChatSendAuthorizationStatus",
    "WeChatSendConfirmationAuthorization",
    "WeChatSendConfirmationAuthorizer",
    "WeChatSendConfirmationPayload",
    "build_wechat_send_confirmation_payload",
]
