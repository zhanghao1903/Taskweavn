"""Typed local computer-use actions and observations."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from taskweavn.types.base import BaseAction, BaseObservation

ComputerUseOperation = Literal[
    "observe",
    "open_app",
    "click",
    "type_text",
    "press_key",
    "wait",
]

ComputerUseStatus = Literal[
    "ok",
    "blocked",
    "needs_user",
    "not_available",
    "failed",
]


class ComputerUseAction(BaseAction):
    """Request one controlled local desktop operation.

    This is a foundation contract only. Real OS automation backends remain
    opt-in and are not enabled by default.
    """

    baseline_risk: ClassVar[float] = 0.75

    operation: ComputerUseOperation
    instruction: str = Field(min_length=1, max_length=1_000)
    target: str | None = Field(default=None, min_length=1, max_length=400)
    text: str | None = Field(default=None, min_length=1, max_length=4_000)
    keys: tuple[str, ...] = Field(default=())
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    require_confirmation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_operation_payload(self) -> ComputerUseAction:
        if self.operation == "open_app" and self.target is None:
            raise ValueError("open_app requires target")
        if self.operation == "type_text" and self.text is None:
            raise ValueError("type_text requires text")
        if self.operation == "press_key" and not self.keys:
            raise ValueError("press_key requires keys")
        if self.operation == "click" and self.target is None and (
            self.x is None or self.y is None
        ):
            raise ValueError("click requires target or x/y coordinates")
        return self


class ComputerUseObservation(BaseObservation):
    """Sanitized result of one computer-use operation."""

    operation: ComputerUseOperation
    status: ComputerUseStatus
    summary: str = Field(min_length=1, max_length=2_000)
    screenshot_ref: str | None = Field(default=None, min_length=1)
    text_extract: str | None = Field(default=None, max_length=4_000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_success_status(self) -> ComputerUseObservation:
        if self.success != (self.status == "ok"):
            raise ValueError("computer_use success must match status == 'ok'")
        return self


__all__ = [
    "ComputerUseAction",
    "ComputerUseObservation",
    "ComputerUseOperation",
    "ComputerUseStatus",
]
