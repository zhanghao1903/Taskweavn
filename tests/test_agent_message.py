"""Tests for the AgentMessage Pydantic model (Phase 3.3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from code_agent.interaction import AgentMessage, RiskAssessment


def test_minimum_message_fills_defaults() -> None:
    m = AgentMessage(
        session_id="sess1",
        message_type="informational",
        content="hi",
    )
    assert m.session_id == "sess1"
    assert m.task_id is None
    assert m.agent_id == "agent"
    assert m.parent_message_id is None
    assert m.context == {}
    assert m.action_options == []
    assert m.requires_response is False
    assert isinstance(m.created_at, datetime)
    assert m.created_at.tzinfo is UTC


def test_task_id_is_first_class() -> None:
    m = AgentMessage(
        session_id="sess1",
        task_id="task-XYZ",
        message_type="informational",
        content="x",
    )
    assert m.task_id == "task-XYZ"


def test_message_id_unique_per_instance() -> None:
    a = AgentMessage(session_id="s", message_type="informational", content="a")
    b = AgentMessage(session_id="s", message_type="informational", content="b")
    assert a.message_id != b.message_id


def test_message_is_frozen() -> None:
    m = AgentMessage(session_id="s", message_type="informational", content="hi")
    with pytest.raises(ValidationError):
        m.content = "tampered"  # type: ignore[misc]


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentMessage(  # type: ignore[call-arg]
            session_id="s",
            message_type="informational",
            content="x",
            extra="boom",
        )


def test_message_type_must_be_one_of_three() -> None:
    with pytest.raises(ValidationError):
        AgentMessage(  # type: ignore[arg-type]
            session_id="s", message_type="weird", content="x"
        )


def test_risk_assessment_passthrough() -> None:
    risk = RiskAssessment(
        baseline=0.5, dynamic=0.7, rationale=("llm",), assessor="llm"
    )
    m = AgentMessage(
        session_id="s",
        message_type="actionable",
        content="confirm?",
        requires_response=True,
        risk_assessment=risk,
    )
    assert m.risk_assessment is risk


def test_risk_assessment_coerced_from_dict() -> None:
    """SqliteMessageStream rehydrates from a dict — the validator must accept."""
    m = AgentMessage(
        session_id="s",
        message_type="actionable",
        content="confirm?",
        risk_assessment={  # type: ignore[arg-type]
            "baseline": 0.3,
            "dynamic": 0.6,
            "rationale": ["one", "two"],
            "assessor": "x",
        },
    )
    assert isinstance(m.risk_assessment, RiskAssessment)
    assert m.risk_assessment.dynamic == 0.6
    assert m.risk_assessment.rationale == ("one", "two")


def test_risk_assessment_serializes_to_json_dict() -> None:
    """JSON dump must produce a plain dict, not a dataclass repr."""
    risk = RiskAssessment(baseline=0.3, dynamic=0.5)
    m = AgentMessage(
        session_id="s", message_type="actionable", content="x",
        risk_assessment=risk,
    )
    payload = m.model_dump(mode="json")
    assert isinstance(payload["risk_assessment"], dict)
    assert payload["risk_assessment"]["baseline"] == 0.3
    assert payload["risk_assessment"]["dynamic"] == 0.5


def test_response_fields_optional_on_other_types() -> None:
    m = AgentMessage(
        session_id="s",
        message_type="informational",
        content="hi",
    )
    assert m.response_source is None
    assert m.response_value is None


def test_response_carries_source_and_value() -> None:
    m = AgentMessage(
        session_id="s",
        message_type="response",
        content="yes",
        parent_message_id="parent-id",
        agent_id="user",
        response_source="user",
        response_value="yes",
    )
    assert m.response_source == "user"
    assert m.response_value == "yes"
