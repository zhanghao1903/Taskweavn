"""Tests for AutonomyBehavior + presets (Phase 3.2)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from taskweavn.interaction import (
    AUTONOMY_PRESETS,
    AutonomyBehavior,
    get_preset,
)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score", [-0.01, 1.01, 2.0])
def test_risk_threshold_must_be_unit_interval(score: float) -> None:
    with pytest.raises(ValueError, match="risk_threshold"):
        AutonomyBehavior(risk_threshold=score)


@pytest.mark.parametrize("score", [-0.01, 1.01, 2.0])
def test_confidence_threshold_must_be_unit_interval(score: float) -> None:
    with pytest.raises(ValueError, match="confidence_threshold"):
        AutonomyBehavior(confidence_threshold=score)


@pytest.mark.parametrize("timeout", [0.0, -1.0, -100.0])
def test_wait_timeout_must_be_positive_or_none(timeout: float) -> None:
    with pytest.raises(ValueError, match="wait_timeout"):
        AutonomyBehavior(wait_timeout=timeout)


def test_wait_timeout_none_allowed() -> None:
    AutonomyBehavior(wait_timeout=None)  # no raise


def test_default_is_risk_gated_shaped() -> None:
    """Calling AutonomyBehavior() with no args should equal the risk_gated preset."""
    assert AutonomyBehavior() == get_preset("risk_gated")


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


def test_all_five_presets_exist() -> None:
    expected = {"full_auto", "risk_gated", "careful", "collaborative", "manual"}
    assert set(AUTONOMY_PRESETS) == expected


def test_full_auto_never_blocks() -> None:
    p = get_preset("full_auto")
    assert p.trigger == "never"
    assert p.wait_strategy == "async"


def test_risk_gated_threshold_default() -> None:
    p = get_preset("risk_gated")
    assert p.trigger == "on_risk"
    assert p.risk_threshold == 0.5
    assert p.wait_strategy == "sync"


def test_careful_lower_threshold() -> None:
    p = get_preset("careful")
    assert p.risk_threshold == 0.3
    assert p.wait_timeout == 600.0


def test_collaborative_uses_uncertainty() -> None:
    p = get_preset("collaborative")
    assert p.trigger == "on_uncertainty"


def test_manual_always_asks_and_waits() -> None:
    p = get_preset("manual")
    assert p.trigger == "always"
    assert p.wait_timeout is None
    assert p.timeout_action == "wait"


def test_unknown_preset_raises() -> None:
    with pytest.raises(KeyError, match="full_auto"):
        get_preset("does_not_exist")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Immutability + forking
# ---------------------------------------------------------------------------


def test_behavior_is_frozen() -> None:
    import dataclasses

    p = get_preset("risk_gated")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.risk_threshold = 0.7  # type: ignore[misc]


def test_user_can_fork_via_replace() -> None:
    base = get_preset("careful")
    custom = replace(base, risk_threshold=0.2, wait_timeout=120.0)
    assert custom.risk_threshold == 0.2
    assert custom.wait_timeout == 120.0
    # Original untouched.
    assert base.risk_threshold == 0.3
    assert base.wait_timeout == 600.0


def test_replace_validates() -> None:
    base = get_preset("risk_gated")
    with pytest.raises(ValueError, match="risk_threshold"):
        replace(base, risk_threshold=2.0)
