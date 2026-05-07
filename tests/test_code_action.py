"""Tests for the CodeAction schema (Phase 2.1)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from code_agent.llm.client import tool_schema_from_action
from code_agent.types import (
    ActionRegistry,
    CodeAction,
    CodeExecutionObservation,
    FileChange,
    ObservationRegistry,
    TrackingConfig,
)

# ---------------------------------------------------------------------------
# TrackingConfig
# ---------------------------------------------------------------------------


def test_tracking_config_accepts_empty_lists() -> None:
    """Empty TrackingConfig is the explicit 'I claim no side effects' form."""
    cfg = TrackingConfig(files=[], variables=[])
    assert cfg.files == []
    assert cfg.variables == []


def test_tracking_config_requires_both_fields() -> None:
    """Both fields are required — no implicit defaults."""
    with pytest.raises(ValidationError):
        TrackingConfig(files=["a.txt"])  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        TrackingConfig(variables=["x"])  # type: ignore[call-arg]


def test_tracking_config_rejects_invalid_variable_names() -> None:
    with pytest.raises(ValidationError, match="valid Python identifiers"):
        TrackingConfig(files=[], variables=["1bad"])
    with pytest.raises(ValidationError, match="valid Python identifiers"):
        TrackingConfig(files=[], variables=["obj.attr"])


def test_tracking_config_accepts_underscore_and_unicode_basics() -> None:
    cfg = TrackingConfig(files=[], variables=["_x", "x1", "snake_case_name"])
    assert cfg.variables == ["_x", "x1", "snake_case_name"]


def test_tracking_config_is_frozen() -> None:
    cfg = TrackingConfig(files=[], variables=[])
    with pytest.raises(ValidationError):
        cfg.files = ["x"]


# ---------------------------------------------------------------------------
# CodeAction
# ---------------------------------------------------------------------------


def test_code_action_minimal() -> None:
    action = CodeAction(
        intent="print hello",
        code="print('hi')",
        tracking=TrackingConfig(files=[], variables=[]),
    )
    assert action.language == "python"
    assert action.intent == "print hello"
    assert action.tracking.files == []


def test_code_action_intent_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        CodeAction(
            intent="",
            code="x = 1",
            tracking=TrackingConfig(files=[], variables=[]),
        )


def test_code_action_intent_length_capped() -> None:
    long_intent = "a" * 501
    with pytest.raises(ValidationError):
        CodeAction(
            intent=long_intent,
            code="x = 1",
            tracking=TrackingConfig(files=[], variables=[]),
        )


def test_code_action_code_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        CodeAction(
            intent="noop",
            code="",
            tracking=TrackingConfig(files=[], variables=[]),
        )


def test_code_action_language_locked_to_python() -> None:
    with pytest.raises(ValidationError):
        CodeAction(
            intent="run shell",
            code="echo hi",
            language="bash",  # type: ignore[arg-type]
            tracking=TrackingConfig(files=[], variables=[]),
        )


def test_code_action_tracking_required() -> None:
    with pytest.raises(ValidationError):
        CodeAction(intent="x", code="y")  # type: ignore[call-arg]


def test_code_action_round_trips_through_json() -> None:
    action = CodeAction(
        intent="write counts to out.json",
        code="import json; json.dump({'n': 3}, open('out.json', 'w'))",
        tracking=TrackingConfig(files=["out.json"], variables=[]),
    )
    payload = action.to_dict()
    rehydrated = ActionRegistry.deserialize(payload)
    assert isinstance(rehydrated, CodeAction)
    assert rehydrated.intent == action.intent
    assert rehydrated.tracking.files == ["out.json"]


def test_code_action_registers_kind() -> None:
    assert "CodeAction" in ActionRegistry.all_kinds()


# ---------------------------------------------------------------------------
# CodeExecutionObservation
# ---------------------------------------------------------------------------


def test_observation_minimal_success() -> None:
    obs = CodeExecutionObservation(
        intent="print hello",
        exit_code=0,
        stdout="hi\n",
        stderr="",
        duration_ms=12.5,
    )
    assert obs.success is True  # default from BaseObservation
    assert obs.declared_changes == []
    assert obs.undeclared_changes == []
    assert obs.variable_dump == {}
    assert obs.blocked_reason is None
    assert obs.timed_out is False


def test_observation_with_file_changes() -> None:
    obs = CodeExecutionObservation(
        intent="write a file",
        exit_code=0,
        stdout="",
        stderr="",
        duration_ms=8.0,
        declared_changes=[
            FileChange(
                path="out.txt",
                change_type="created",
                before_sha256=None,
                after_sha256="a" * 64,
                size_delta=42,
            )
        ],
        undeclared_changes=[
            FileChange(
                path="leaked.log",
                change_type="created",
                after_sha256="b" * 64,
                size_delta=10,
            )
        ],
        variable_dump={"n": "3"},
    )
    assert obs.declared_changes[0].change_type == "created"
    assert obs.undeclared_changes[0].path == "leaked.log"


def test_observation_blocked_form() -> None:
    obs = CodeExecutionObservation(
        intent="rm -rf /",
        exit_code=-1,
        stdout="",
        stderr="",
        duration_ms=0.0,
        blocked_reason="dangerous_command",
        success=False,
    )
    assert obs.blocked_reason == "dangerous_command"
    assert obs.success is False


def test_observation_duration_ms_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        CodeExecutionObservation(
            intent="x",
            exit_code=0,
            stdout="",
            stderr="",
            duration_ms=-1.0,
        )


def test_observation_round_trips_through_json() -> None:
    obs = CodeExecutionObservation(
        intent="write a file",
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_ms=1.0,
        declared_changes=[
            FileChange(
                path="x.txt",
                change_type="created",
                after_sha256="c" * 64,
                size_delta=1,
            )
        ],
        variable_dump={"x": "1"},
    )
    payload = obs.to_dict()
    rehydrated = ObservationRegistry.deserialize(payload)
    assert isinstance(rehydrated, CodeExecutionObservation)
    assert rehydrated.declared_changes[0].path == "x.txt"
    assert rehydrated.variable_dump == {"x": "1"}


def test_observation_registers_kind() -> None:
    assert "CodeExecutionObservation" in ObservationRegistry.all_kinds()


# ---------------------------------------------------------------------------
# FileChange
# ---------------------------------------------------------------------------


def test_file_change_change_type_constrained() -> None:
    with pytest.raises(ValidationError):
        FileChange(
            path="x",
            change_type="renamed",  # type: ignore[arg-type]
            size_delta=0,
        )


def test_file_change_creation_form() -> None:
    fc = FileChange(
        path="x.txt",
        change_type="created",
        after_sha256="a" * 64,
        size_delta=10,
    )
    assert fc.before_sha256 is None
    assert fc.after_sha256 == "a" * 64


def test_file_change_deletion_form() -> None:
    fc = FileChange(
        path="x.txt",
        change_type="deleted",
        before_sha256="b" * 64,
        size_delta=-10,
    )
    assert fc.after_sha256 is None


# ---------------------------------------------------------------------------
# LLM-tool-schema generation
# ---------------------------------------------------------------------------


def test_code_action_renders_to_openai_tool_schema() -> None:
    """The schema sent to the LLM must include intent/code/language/tracking,
    nest TrackingConfig properly, and hide event bookkeeping fields."""
    schema = tool_schema_from_action(
        name="run_code",
        description="Run a python snippet under a tracking contract.",
        action_type=CodeAction,
    )
    assert schema["type"] == "function"
    params = schema["function"]["parameters"]
    properties = params["properties"]

    for hidden in ("event_id", "timestamp", "source"):
        assert hidden not in properties

    for required in ("intent", "code", "language", "tracking"):
        assert required in properties

    # Sanity: emit one full JSON to ensure no $defs cycles or non-serializable nodes.
    json.dumps(schema)
