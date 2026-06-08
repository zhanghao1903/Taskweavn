"""Shared AgentLoop profile contracts.

These contracts are intentionally runtime-neutral. They describe the seam that
future loop profiles use without changing the current execution AgentLoop.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

LoopProfileState = Literal[
    "running",
    "reading_context",
    "waiting_for_context",
    "finished",
    "rejected",
]
LoopProfileResultStatus = Literal["finished", "waiting_for_context", "rejected"]


class _FrozenLoopProfileModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class LoopTerminalAction(_FrozenLoopProfileModel):
    """Profile-neutral terminal tool call produced by a loop run."""

    profile_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_not_blank(self) -> LoopTerminalAction:
        if not self.profile_id.strip():
            raise ValueError("profile_id must not be blank")
        if not self.tool_name.strip():
            raise ValueError("tool_name must not be blank")
        return self


@runtime_checkable
class AgentLoopProfileResult(Protocol):
    """Minimum result surface produced by a profile-specific terminal mapper."""

    status: str
    evidence_refs: tuple[str, ...]


@runtime_checkable
class AgentLoopProfile(Protocol):
    """Public profile contract for shared loop mechanics.

    Implementations own prompt construction, terminal action mapping, rejection
    mapping, and the allowed tool boundary. Shared mechanics own tool-call
    ordering, transcript preservation, step limits, and terminal detection.
    """

    profile_id: str
    allowed_tool_names: tuple[str, ...]
    terminal_tool_name: str

    def build_initial_messages(self, request: object) -> list[dict[str, Any]]: ...

    def map_terminal_action(
        self,
        action: LoopTerminalAction,
        context: object,
    ) -> AgentLoopProfileResult: ...

    def map_rejection(
        self,
        error: Exception,
        context: object,
    ) -> AgentLoopProfileResult: ...


__all__ = [
    "AgentLoopProfile",
    "AgentLoopProfileResult",
    "LoopProfileResultStatus",
    "LoopProfileState",
    "LoopTerminalAction",
]
