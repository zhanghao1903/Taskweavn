"""Tests for the local computer-use tool foundation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from taskweavn.tools import (
    ComputerUseTool,
    DisabledComputerUseBackend,
    ScriptedComputerUseBackend,
)
from taskweavn.types import ComputerUseAction, ComputerUseObservation


def test_computer_use_action_validates_operation_payloads() -> None:
    ComputerUseAction(operation="observe", instruction="Inspect the visible state.")
    ComputerUseAction(
        operation="open_app",
        instruction="Open the mail app.",
        target="Mail",
    )
    ComputerUseAction(
        operation="click",
        instruction="Click the send button.",
        target="Send",
    )
    ComputerUseAction(
        operation="click",
        instruction="Click by coordinate.",
        x=10,
        y=20,
    )
    ComputerUseAction(
        operation="type_text",
        instruction="Type the prepared text.",
        text="hello",
    )
    ComputerUseAction(
        operation="press_key",
        instruction="Submit the current dialog.",
        keys=("Enter",),
    )

    with pytest.raises(ValidationError, match="open_app requires target"):
        ComputerUseAction(operation="open_app", instruction="Open an app.")
    with pytest.raises(ValidationError, match="type_text requires text"):
        ComputerUseAction(operation="type_text", instruction="Type something.")
    with pytest.raises(ValidationError, match="press_key requires keys"):
        ComputerUseAction(operation="press_key", instruction="Press a key.")
    with pytest.raises(ValidationError, match="click requires target or x/y"):
        ComputerUseAction(operation="click", instruction="Click something.")


def test_computer_use_observation_requires_success_to_match_ok_status() -> None:
    ok = ComputerUseObservation(
        action_id="action-1",
        operation="observe",
        status="ok",
        summary="Visible UI inspected.",
    )
    failed = ComputerUseObservation(
        action_id="action-1",
        success=False,
        operation="observe",
        status="failed",
        summary="Observation failed.",
    )

    assert ok.success is True
    assert failed.success is False
    with pytest.raises(ValidationError, match="success must match"):
        ComputerUseObservation(
            action_id="action-1",
            operation="observe",
            status="failed",
            summary="Invalid success.",
        )


def test_disabled_backend_never_touches_os_and_returns_not_available() -> None:
    action = ComputerUseAction(
        operation="observe",
        instruction="Inspect the visible desktop state.",
    )
    backend = DisabledComputerUseBackend(reason="disabled for test")

    observation = ComputerUseTool(backend).execute(action)

    assert observation.action_id == action.event_id
    assert observation.success is False
    assert observation.operation == "observe"
    assert observation.status == "not_available"
    assert observation.summary == "disabled for test"


def test_scripted_backend_records_actions_and_returns_sanitized_observation() -> None:
    template = ComputerUseObservation(
        operation="observe",
        status="ok",
        summary="Scripted desktop state is visible.",
        text_extract="Ready",
    )
    backend = ScriptedComputerUseBackend([template])
    action = ComputerUseAction(
        operation="observe",
        instruction="Inspect the desktop state.",
    )

    observation = ComputerUseTool(backend).execute(action)

    assert backend.actions == [action]
    assert observation.action_id == action.event_id
    assert observation.success is True
    assert observation.summary == "Scripted desktop state is visible."
    assert observation.text_extract == "Ready"


def test_scripted_backend_reports_operation_mismatch_without_running_fallback() -> None:
    backend = ScriptedComputerUseBackend(
        [
            ComputerUseObservation(
                operation="wait",
                status="ok",
                summary="Unexpected wait response.",
            )
        ]
    )
    action = ComputerUseAction(
        operation="observe",
        instruction="Inspect the desktop state.",
    )

    observation = ComputerUseTool(backend).execute(action)

    assert backend.actions == [action]
    assert observation.success is False
    assert observation.operation == "observe"
    assert observation.status == "failed"
    assert "operation mismatch" in observation.summary


def test_tool_blocks_actions_that_require_external_confirmation() -> None:
    backend = ScriptedComputerUseBackend()
    action = ComputerUseAction(
        operation="type_text",
        instruction="Type an outbound message.",
        text="hello",
        require_confirmation=True,
    )

    observation = ComputerUseTool(backend).execute(action)

    assert backend.actions == []
    assert observation.success is False
    assert observation.status == "blocked"
    assert "requires explicit confirmation" in observation.summary
