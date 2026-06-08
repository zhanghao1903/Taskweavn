"""Tests for shared AgentLoop profile contracts."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from taskweavn.core import (
    AgentLoopProfile,
    AgentLoopProfileResult,
    LoopTerminalAction,
)


class _Result:
    status = "finished"
    evidence_refs = ("evidence-1",)


class _Profile:
    profile_id = "test_profile"
    allowed_tool_names = ("finish_test",)
    terminal_tool_name = "finish_test"

    def build_initial_messages(self, request: object) -> list[dict[str, Any]]:
        return [{"role": "user", "content": str(request)}]

    def map_terminal_action(
        self,
        action: LoopTerminalAction,
        context: object,
    ) -> _Result:
        return _Result()

    def map_rejection(self, error: Exception, context: object) -> _Result:
        return _Result()


def test_agent_loop_profile_protocol_conformance() -> None:
    profile = _Profile()
    action = LoopTerminalAction(
        profile_id=profile.profile_id,
        tool_name=profile.terminal_tool_name,
        arguments={"answer": "done"},
    )

    result = profile.map_terminal_action(action, object())

    assert isinstance(profile, AgentLoopProfile)
    assert isinstance(result, AgentLoopProfileResult)
    assert result.status == "finished"
    assert result.evidence_refs == ("evidence-1",)


def test_terminal_action_rejects_blank_identity() -> None:
    with pytest.raises(ValidationError, match="profile_id"):
        LoopTerminalAction(profile_id=" ", tool_name="finish_test")

    with pytest.raises(ValidationError, match="tool_name"):
        LoopTerminalAction(profile_id="test_profile", tool_name=" ")


def test_terminal_action_is_frozen() -> None:
    action = LoopTerminalAction(profile_id="test_profile", tool_name="finish_test")

    with pytest.raises(ValidationError):
        action.tool_name = "mutated"
