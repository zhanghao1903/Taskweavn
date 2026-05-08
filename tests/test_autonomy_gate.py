"""Tests for AutonomyGate (Phase 3.5).

Coverage strategy: walk the trigger × risk-shape table from design doc §5.1,
plus the confidence-provider plumbing. The gate is pure, so we drive it
directly without a bus.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from code_agent.interaction import (
    AUTONOMY_PRESETS,
    AssessmentContext,
    AutonomyBehavior,
    AutonomyGate,
    BaselineOnlyAssessor,
    GateVerdict,
    RiskAssessment,
)
from code_agent.tools.fs import ReadFileAction, WriteFileAction
from code_agent.tools.shell import RunCommandAction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(tmp_path: Path) -> AssessmentContext:
    return AssessmentContext(workspace_root=tmp_path, session_id="s")


class _FixedAssessor:
    """Test double — return a hand-rolled assessment regardless of action."""

    def __init__(self, baseline: float, dynamic: float | None = None) -> None:
        self._baseline = baseline
        self._dynamic = baseline if dynamic is None else dynamic

    def assess(self, action, context):  # type: ignore[no-untyped-def]
        return RiskAssessment(
            baseline=self._baseline,
            dynamic=self._dynamic,
            rationale=("test",),
            assessor="test",
        )


class _ConstantConfidence:
    def __init__(self, value: float) -> None:
        self._value = value

    def get(self, action) -> float:  # type: ignore[no-untyped-def]
        return self._value


# ---------------------------------------------------------------------------
# trigger="never"
# ---------------------------------------------------------------------------


def test_never_always_proceeds(tmp_path: Path) -> None:
    behavior = AUTONOMY_PRESETS["full_auto"]
    gate = AutonomyGate(behavior, _FixedAssessor(0.99))
    decision = gate.check(RunCommandAction(command="rm -rf /"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED
    assert decision.inform_user is False  # full_auto.notify_on_proceed=False
    assert decision.risk_assessment.final == pytest.approx(0.99)


def test_never_with_notify_on_proceed_informs_when_risk_positive(
    tmp_path: Path,
) -> None:
    behavior = replace(
        AUTONOMY_PRESETS["full_auto"], notify_on_proceed=True
    )
    gate = AutonomyGate(behavior, _FixedAssessor(0.4))
    decision = gate.check(RunCommandAction(command="ls"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED
    assert decision.inform_user is True


def test_never_with_zero_risk_does_not_inform(tmp_path: Path) -> None:
    behavior = replace(
        AUTONOMY_PRESETS["full_auto"], notify_on_proceed=True
    )
    gate = AutonomyGate(behavior, _FixedAssessor(0.0))
    decision = gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED
    assert decision.inform_user is False  # risk=0 → no notice spam


# ---------------------------------------------------------------------------
# trigger="always"
# ---------------------------------------------------------------------------


def test_always_emits_regardless_of_risk(tmp_path: Path) -> None:
    gate = AutonomyGate(AUTONOMY_PRESETS["manual"], _FixedAssessor(0.0))
    decision = gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.EMIT
    assert decision.inform_user is False  # the actionable IS the notification
    assert "trigger=always" in decision.reason


# ---------------------------------------------------------------------------
# trigger="on_risk"
# ---------------------------------------------------------------------------


def test_on_risk_emits_when_risk_meets_threshold(tmp_path: Path) -> None:
    """Threshold is inclusive — final == threshold should still emit."""
    behavior = replace(AUTONOMY_PRESETS["risk_gated"], risk_threshold=0.5)
    gate = AutonomyGate(behavior, _FixedAssessor(0.5))
    decision = gate.check(RunCommandAction(command="ls"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.EMIT


def test_on_risk_proceeds_below_threshold_with_inform(tmp_path: Path) -> None:
    behavior = replace(AUTONOMY_PRESETS["risk_gated"], risk_threshold=0.5)
    gate = AutonomyGate(behavior, _FixedAssessor(0.3))
    decision = gate.check(WriteFileAction(path="/tmp/x", content="x"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED
    assert decision.inform_user is True
    assert "0.30" in decision.reason and "0.50" in decision.reason


def test_on_risk_zero_does_not_inform(tmp_path: Path) -> None:
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], _FixedAssessor(0.0))
    decision = gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED
    assert decision.inform_user is False


# ---------------------------------------------------------------------------
# trigger="on_uncertainty"
# ---------------------------------------------------------------------------


def test_on_uncertainty_without_provider_proceeds(tmp_path: Path) -> None:
    """No ConfidenceProvider configured → confidence defaults to 1.0
    (fully confident), so we PROCEED. That's the documented Phase 3 behavior.
    """
    gate = AutonomyGate(
        AUTONOMY_PRESETS["collaborative"], _FixedAssessor(0.0)
    )
    decision = gate.check(RunCommandAction(command="ls"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED


def test_on_uncertainty_low_confidence_emits(tmp_path: Path) -> None:
    behavior = AUTONOMY_PRESETS["collaborative"]  # threshold 0.5
    gate = AutonomyGate(
        behavior, _FixedAssessor(0.0),
        confidence_provider=_ConstantConfidence(0.3),
    )
    decision = gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.EMIT
    assert "0.30" in decision.reason


def test_on_uncertainty_high_confidence_proceeds(tmp_path: Path) -> None:
    behavior = AUTONOMY_PRESETS["collaborative"]
    gate = AutonomyGate(
        behavior, _FixedAssessor(0.0),
        confidence_provider=_ConstantConfidence(0.9),
    )
    decision = gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED


def test_on_uncertainty_threshold_inclusive(tmp_path: Path) -> None:
    """confidence == threshold counts as confident enough → PROCEED."""
    behavior = AUTONOMY_PRESETS["collaborative"]
    gate = AutonomyGate(
        behavior, _FixedAssessor(0.0),
        confidence_provider=_ConstantConfidence(0.5),
    )
    decision = gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))
    assert decision.verdict == GateVerdict.PROCEED


def test_confidence_out_of_range_rejected(tmp_path: Path) -> None:
    gate = AutonomyGate(
        AUTONOMY_PRESETS["collaborative"], _FixedAssessor(0.0),
        confidence_provider=_ConstantConfidence(1.5),
    )
    with pytest.raises(ValueError):
        gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))


# ---------------------------------------------------------------------------
# Real assessor end-to-end
# ---------------------------------------------------------------------------


def test_baseline_assessor_drives_real_actions(tmp_path: Path) -> None:
    """Sanity check that BaselineOnlyAssessor + risk_gated lines up with
    Appendix B baselines: read=0.0 (proceed), write=0.3 (proceed+inform),
    shell=0.5 (emit)."""
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    ctx = _ctx(tmp_path)

    read_decision = gate.check(ReadFileAction(path="/tmp/x"), ctx)
    write_decision = gate.check(
        WriteFileAction(path="/tmp/x", content="hi"), ctx
    )
    run_decision = gate.check(RunCommandAction(command="ls"), ctx)

    assert read_decision.verdict == GateVerdict.PROCEED
    assert read_decision.inform_user is False
    assert write_decision.verdict == GateVerdict.PROCEED
    assert write_decision.inform_user is True
    assert run_decision.verdict == GateVerdict.EMIT


def test_invalid_trigger_raises(tmp_path: Path) -> None:
    """Defensive: if someone bypasses Literal validation and feeds a bad
    trigger, the gate complains rather than silently proceeding."""
    behavior = AUTONOMY_PRESETS["risk_gated"]
    object.__setattr__(behavior, "_test_attr", None)  # ensure object identity
    bad = AutonomyBehavior.__new__(AutonomyBehavior)
    object.__setattr__(bad, "trigger", "bogus")
    object.__setattr__(bad, "risk_threshold", 0.5)
    object.__setattr__(bad, "confidence_threshold", 0.5)
    object.__setattr__(bad, "wait_strategy", "sync")
    object.__setattr__(bad, "wait_timeout", 1.0)
    object.__setattr__(bad, "timeout_action", "proceed_default")
    object.__setattr__(bad, "notify_on_proceed", True)
    gate = AutonomyGate(bad, _FixedAssessor(0.0))
    with pytest.raises(ValueError, match="unknown autonomy trigger"):
        gate.check(ReadFileAction(path="/tmp/x"), _ctx(tmp_path))


def test_gate_exposes_behavior(tmp_path: Path) -> None:
    behavior = AUTONOMY_PRESETS["careful"]
    gate = AutonomyGate(behavior, BaselineOnlyAssessor())
    assert gate.behavior is behavior
