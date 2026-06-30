"""Typed WeChat Desktop tool actions and observations."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from taskweavn.types.base import BaseAction, BaseObservation

WeChatDesktopOperation = Literal[
    "open_wechat",
    "focus_contact",
    "observe_current_chat",
    "read_visible_messages",
    "draft_message",
    "submit_draft",
    "send_message",
]

WeChatDesktopStatus = Literal[
    "ok",
    "needs_user",
    "not_available",
    "failed",
    "unknown",
]


class WeChatDesktopAction(BaseAction):
    """Request one semantic WeChat Desktop operation through the package tool."""

    baseline_risk: ClassVar[float] = 0.8

    operation: WeChatDesktopOperation
    contact: str | None = Field(default=None, min_length=1, max_length=400)
    message: str | None = Field(default=None, min_length=1, max_length=4_000)
    include_visible_messages: bool = True
    limit: int = Field(default=20, ge=1, le=100)
    method: str = Field(default="keyboard_return", min_length=1, max_length=100)
    verify_after_submit: bool = False
    verify_limit: int = Field(default=20, ge=1, le=100)
    timeout_ms: int | None = Field(default=None, gt=0, le=120_000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=400)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_operation_payload(self) -> WeChatDesktopAction:
        if self.operation in {"focus_contact", "send_message"} and self.contact is None:
            raise ValueError(f"{self.operation} requires contact")
        if self.operation in {"draft_message", "send_message"} and self.message is None:
            raise ValueError(f"{self.operation} requires message")
        return self


class WeChatDesktopObservation(BaseObservation):
    """Sanitized result of one WeChat Desktop package operation."""

    operation: WeChatDesktopOperation
    status: WeChatDesktopStatus
    summary: str = Field(min_length=1, max_length=2_000)
    text_extract: str | None = Field(default=None, max_length=4_000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_success_status(self) -> WeChatDesktopObservation:
        if self.success != (self.status == "ok"):
            raise ValueError("wechat_desktop success must match status == 'ok'")
        return self


__all__ = [
    "WeChatDesktopAction",
    "WeChatDesktopObservation",
    "WeChatDesktopOperation",
    "WeChatDesktopStatus",
]
