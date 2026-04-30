"""Tests for Action / Observation base classes and registries (1.1)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from code_agent.types import (
    ActionRegistry,
    BaseAction,
    BaseObservation,
    ObservationRegistry,
)


class _PingAction(BaseAction):
    """Sample Action used only by the test suite."""

    message: str


class _PongObservation(BaseObservation):
    """Sample Observation paired with _PingAction."""

    echoed: str


def test_subclass_auto_registers_action() -> None:
    assert ActionRegistry.get("_PingAction") is _PingAction
    assert "_PingAction" in ActionRegistry.all_kinds()


def test_subclass_auto_registers_observation() -> None:
    assert ObservationRegistry.get("_PongObservation") is _PongObservation
    assert "_PongObservation" in ObservationRegistry.all_kinds()


def test_action_serializes_with_kind() -> None:
    action = _PingAction(message="hello")
    payload = action.to_dict()
    assert payload["kind"] == "_PingAction"
    assert payload["message"] == "hello"
    assert payload["source"] == "agent"
    assert "event_id" in payload
    assert "timestamp" in payload


def test_observation_carries_action_id_and_success() -> None:
    obs = _PongObservation(echoed="hi", action_id="abc", success=False)
    payload = obs.to_dict()
    assert payload["action_id"] == "abc"
    assert payload["success"] is False
    assert payload["kind"] == "_PongObservation"


def test_round_trip_via_json_preserves_subclass() -> None:
    original = _PingAction(message="round trip")
    blob = original.to_json()
    decoded = ActionRegistry.deserialize(json.loads(blob))
    assert isinstance(decoded, _PingAction)
    assert decoded.message == "round trip"
    assert decoded.event_id == original.event_id


def test_observation_round_trip_via_json() -> None:
    original = _PongObservation(echoed="back", action_id="xyz")
    decoded = ObservationRegistry.deserialize(json.loads(original.to_json()))
    assert isinstance(decoded, _PongObservation)
    assert decoded.echoed == "back"
    assert decoded.action_id == "xyz"


def test_unknown_kind_raises() -> None:
    with pytest.raises(KeyError):
        ActionRegistry.get("MissingAction")


def test_payload_without_kind_raises() -> None:
    with pytest.raises(ValueError, match="missing 'kind'"):
        ActionRegistry.deserialize({"message": "no kind here"})


def test_register_false_skips_registry() -> None:
    class _AbstractTool(BaseAction, register=False):
        pass

    assert "_AbstractTool" not in ActionRegistry.all_kinds()


def test_duplicate_kind_raises() -> None:
    class _Dup(BaseAction):
        x: int = 0

    with pytest.raises(ValueError, match="already registered"):

        class _Dup(BaseAction, kind="_Dup"):  # noqa: F811 — intentional duplicate
            y: int = 0


def test_event_is_immutable() -> None:
    action = _PingAction(message="frozen")
    with pytest.raises(ValidationError):
        action.message = "mutated"  # type: ignore[misc]
