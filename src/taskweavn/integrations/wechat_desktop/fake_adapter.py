"""Deterministic fake WeChat adapter for route and workflow tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendActionFingerprint,
)
from taskweavn.integrations.wechat_desktop.models import (
    WeChatContactResolution,
    WeChatDraftState,
    WeChatOperationResult,
    WeChatReadiness,
    WeChatSendAttemptResult,
    WeChatSendAttemptStatus,
    WeChatSendTaskInput,
    wechat_message_hash,
    wechat_message_preview,
)


@dataclass
class FakeWeChatDesktopAdapter:
    """Small fake with the same draft-only surface as ``WeChatDesktopAdapter``."""

    readiness_result: WeChatReadiness = field(
        default_factory=lambda: WeChatReadiness(
            status="ready",
            summary="Fake WeChat is ready.",
            app_name="WeChat",
        )
    )
    open_result: WeChatOperationResult = field(
        default_factory=lambda: WeChatOperationResult(
            status="ok",
            summary="Fake WeChat focused.",
        )
    )
    contact_resolution: WeChatContactResolution = field(
        default_factory=lambda: WeChatContactResolution(status="not_found")
    )
    draft_status: str = "drafted"
    send_status: WeChatSendAttemptStatus = "sent"
    send_summary: str = "Fake WeChat send completed."
    calls: list[tuple[str, object]] = field(default_factory=list)

    def readiness(self) -> WeChatReadiness:
        self.calls.append(("readiness", None))
        return self.readiness_result

    def open_or_focus(self) -> WeChatOperationResult:
        self.calls.append(("open_or_focus", None))
        return self.open_result

    def resolve_contact(
        self,
        task_input: WeChatSendTaskInput,
        *,
        execution_id: str | None = None,
        idempotency_key: str | None = None,
        session_id: str | None = None,
    ) -> WeChatContactResolution:
        self.calls.append(("resolve_contact", task_input))
        return self.contact_resolution

    def draft_message(
        self,
        resolution: WeChatContactResolution,
        message_text: str,
    ) -> WeChatDraftState:
        self.calls.append(("draft_message", (resolution, message_text)))
        contact_summary = resolution.selected.summary() if resolution.selected else ""
        if self.draft_status != "drafted":
            return WeChatDraftState(
                status="failed",
                contact_summary=contact_summary,
                message_hash=wechat_message_hash(message_text),
                message_preview=wechat_message_preview(message_text),
                reason="Fake draft failed.",
            )
        return WeChatDraftState(
            status="drafted",
            contact_summary=contact_summary,
            message_hash=wechat_message_hash(message_text),
            message_preview=wechat_message_preview(message_text),
            draft_observation_ref="fake-draft-observation",
        )

    def send_after_confirmation(
        self,
        fingerprint: WeChatSendActionFingerprint,
        *,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str | None = None,
    ) -> WeChatSendAttemptResult:
        self.calls.append(
            (
                "send_after_confirmation",
                {
                    "fingerprint": fingerprint,
                    "contact_summary": contact_summary,
                    "message_preview": message_preview,
                    "confirmation_id": confirmation_id,
                },
            )
        )
        send_attempted = "false" if self.send_status == "not_sent" else "true"
        return WeChatSendAttemptResult(
            status=self.send_status,
            summary=self.send_summary,
            send_observation_ref="fake-send-observation",
            reason=None if self.send_status == "sent" else self.send_summary,
            metadata={
                "fake": "true",
                "send_method": "keyboard_return",
                "send_attempted": send_attempted,
                "phase": "keyboard_submit",
            },
        )


__all__ = ["FakeWeChatDesktopAdapter"]
