"""Confirmation actions and observations used by execution agents."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field

from taskweavn.types.base import BaseAction, BaseObservation


class RequestConfirmationAction(BaseAction, kind="RequestConfirmationAction"):
    """Request user authorization for a known action and block the task."""

    baseline_risk: ClassVar[float] = 0.0

    title: str = Field(
        min_length=1,
        description="Short user-facing title for the known action needing approval.",
    )
    body: str = Field(
        min_length=1,
        description="Concise explanation of the action, impact, and why approval is required.",
    )
    risk_label: str | None = Field(
        default=None,
        min_length=1,
        description="Optional short risk label such as 'external message' or 'file write'.",
    )
    options: tuple[str, ...] = Field(
        default=("confirm", "reject"),
        description=(
            "Decision values. Use confirm/reject by default; include "
            "approve_session only when session-level approval is safe to offer."
        ),
    )
    default_option: str | None = Field(
        default="confirm",
        description="Default decision value from options.",
    )
    allow_session_approval: bool = Field(
        default=False,
        description=(
            "When true, the UI may offer approve_session as an additional "
            "decision value. Product 1.0 records it but does not auto-bypass "
            "future confirmations."
        ),
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured business metadata copied onto the actionable message. "
            "Use for action fingerprints or route context; do not put raw "
            "secret payloads here."
        ),
    )
    blocking: Literal[True] = True


class RequestConfirmationObservation(
    BaseObservation,
    kind="RequestConfirmationObservation",
):
    """Observation returned after durable confirmation creation succeeds."""

    confirmation_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    status: Literal["waiting_for_user"] = "waiting_for_user"
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    message: str = Field(min_length=1)


__all__ = ["RequestConfirmationAction", "RequestConfirmationObservation"]
