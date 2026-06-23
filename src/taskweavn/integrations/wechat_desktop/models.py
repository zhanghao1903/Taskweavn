"""Typed models for the local macOS WeChat Desktop integration."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

WeChatReadinessStatus = Literal[
    "ready",
    "wechat_missing",
    "not_logged_in",
    "not_observable",
    "needs_user",
    "failed",
]

WeChatOperationStatus = Literal["ok", "needs_user", "not_available", "failed"]

WeChatContactResolutionStatus = Literal[
    "resolved",
    "ambiguous",
    "not_found",
    "needs_user",
    "failed",
]

WeChatDraftStatus = Literal["drafted", "failed"]
WeChatSendAttemptStatus = Literal["sent", "not_sent", "unknown", "failed"]


@dataclass(frozen=True)
class WeChatSendTaskInput:
    """Input accepted by the local WeChat send MVP route."""

    contact_display_name: str
    message_text: str
    contact_alias: str | None = None
    external_ref: dict[str, str] | None = None
    operator_note: str | None = None

    def __post_init__(self) -> None:
        if not self.contact_display_name.strip():
            raise ValueError("contact_display_name is required")
        if not self.message_text.strip():
            raise ValueError("message_text is required")


@dataclass(frozen=True)
class WeChatReadiness:
    """Readiness state for local WeChat Desktop automation."""

    status: WeChatReadinessStatus
    summary: str
    app_name: str
    bundle_id: str | None = None
    observation_ref: str | None = None
    setup_hint: str | None = None


@dataclass(frozen=True)
class WeChatOperationResult:
    """Result for a non-send WeChat adapter operation."""

    status: WeChatOperationStatus
    summary: str
    observation_ref: str | None = None
    text_extract: str | None = None
    metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class WeChatContactCandidate:
    """Safe summary of one possible WeChat contact match."""

    display_name: str
    subtitle: str | None = None
    stable_hint: str | None = None
    confidence: float = 0.0

    def summary(self) -> str:
        if self.subtitle:
            return f"{self.display_name} ({self.subtitle})"
        return self.display_name


@dataclass(frozen=True)
class WeChatContactResolution:
    """Outcome of resolving user input to one WeChat contact."""

    status: WeChatContactResolutionStatus
    selected: WeChatContactCandidate | None = None
    candidates: tuple[WeChatContactCandidate, ...] = ()
    observation_ref: str | None = None
    reason: str | None = None
    diagnostics: dict[str, str] | None = None


@dataclass(frozen=True)
class WeChatDraftState:
    """Draft-only state before any confirmation-gated send action exists."""

    status: WeChatDraftStatus
    contact_summary: str
    message_hash: str
    message_preview: str
    draft_observation_ref: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class WeChatSendAttemptResult:
    """Outcome of the final confirmation-authorized send attempt."""

    status: WeChatSendAttemptStatus
    summary: str
    send_observation_ref: str | None = None
    reason: str | None = None
    metadata: dict[str, str] | None = None


def wechat_message_hash(message_text: str) -> str:
    """Return the stable hash used by draft/send boundary checks."""

    return sha256(message_text.encode("utf-8")).hexdigest()


def wechat_message_preview(message_text: str, *, max_chars: int = 160) -> str:
    """Return a bounded preview safe for confirmation/result surfaces."""

    normalized = " ".join(message_text.strip().split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1]}..."


__all__ = [
    "WeChatContactCandidate",
    "WeChatContactResolution",
    "WeChatContactResolutionStatus",
    "WeChatDraftState",
    "WeChatDraftStatus",
    "WeChatOperationResult",
    "WeChatOperationStatus",
    "WeChatReadiness",
    "WeChatReadinessStatus",
    "WeChatSendAttemptResult",
    "WeChatSendAttemptStatus",
    "WeChatSendTaskInput",
    "wechat_message_hash",
    "wechat_message_preview",
]
