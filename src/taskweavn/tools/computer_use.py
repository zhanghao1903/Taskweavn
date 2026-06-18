"""Local computer-use tool foundation.

The first implementation is intentionally backend-driven and safe by default:
without an explicitly injected backend, no OS automation is performed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Protocol, runtime_checkable

from taskweavn.tools.base import Tool
from taskweavn.types.base import BaseAction, BaseObservation
from taskweavn.types.computer_use import (
    ComputerUseAction,
    ComputerUseObservation,
    ComputerUseStatus,
)


@runtime_checkable
class ComputerUseBackend(Protocol):
    """Backend seam for local desktop automation providers."""

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation: ...


@dataclass
class DisabledComputerUseBackend:
    """Safe fallback backend that never touches the operating system."""

    reason: str = "computer-use backend is not enabled"

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        return ComputerUseObservation(
            action_id=action.event_id,
            success=False,
            operation=action.operation,
            status="not_available",
            summary=self.reason,
        )


@dataclass
class ScriptedComputerUseBackend:
    """Deterministic backend for tests and local scripted demos."""

    responses: Iterable[ComputerUseObservation] = ()
    default_status: ComputerUseStatus = "ok"
    default_summary: str = "Scripted computer-use operation completed."
    actions: list[ComputerUseAction] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._responses = list(self.responses)

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        self.actions.append(action)
        if self._responses:
            template = self._responses.pop(0)
            if template.operation != action.operation:
                return ComputerUseObservation(
                    action_id=action.event_id,
                    success=False,
                    operation=action.operation,
                    status="failed",
                    summary=(
                        "scripted computer-use response operation mismatch: "
                        f"expected {action.operation}, got {template.operation}"
                    ),
                )
            return template.model_copy(
                update={
                    "action_id": action.event_id,
                    "success": template.status == "ok",
                }
            )
        return ComputerUseObservation(
            action_id=action.event_id,
            success=self.default_status == "ok",
            operation=action.operation,
            status=self.default_status,
            summary=self.default_summary,
        )


class ComputerUseTool(Tool[ComputerUseAction, ComputerUseObservation]):
    name: ClassVar[str] = "computer_use"
    description: ClassVar[str] = (
        "Use controlled local desktop automation for visible UI tasks. Use only "
        "when the task explicitly requires operating a local app. Do not send "
        "external messages or perform irreversible actions unless task policy "
        "and user confirmation allow it."
    )
    action_type: ClassVar[type[BaseAction]] = ComputerUseAction
    observation_type: ClassVar[type[BaseObservation]] = ComputerUseObservation

    def __init__(self, backend: ComputerUseBackend | None = None) -> None:
        self._backend = backend or DisabledComputerUseBackend()

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        if action.require_confirmation:
            return ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="blocked",
                summary=(
                    "computer-use action requires explicit confirmation before "
                    "execution"
                ),
            )
        try:
            return self._backend.execute(action)
        except Exception as exc:  # noqa: BLE001 - tool boundary must sanitize failures.
            return ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="failed",
                summary=f"computer-use backend failed: {type(exc).__name__}",
                metadata={"error": str(exc)},
            )


__all__ = [
    "ComputerUseBackend",
    "ComputerUseTool",
    "DisabledComputerUseBackend",
    "ScriptedComputerUseBackend",
]
