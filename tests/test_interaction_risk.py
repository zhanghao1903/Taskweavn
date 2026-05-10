"""Tests for the risk model (Phase 3.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.interaction import (
    AssessmentContext,
    BaselineOnlyAssessor,
    RiskAssessment,
    RiskAssessor,
)
from taskweavn.tools.fs import ReadFileAction, WriteFileAction
from taskweavn.tools.shell import RunCommandAction
from taskweavn.types.code_action import CodeAction, TrackingConfig
from taskweavn.types.common import AgentFinishAction

# ---------------------------------------------------------------------------
# Baseline calibration (Appendix B)
# ---------------------------------------------------------------------------


def test_baseline_calibration_matches_appendix_b() -> None:
    """Locks in the design doc's calibration table.

    If a number changes here, update Appendix B in the design doc and bump
    the doc revision.
    """
    from taskweavn.tools.fs import ListDirAction

    assert ReadFileAction.baseline_risk == 0.0
    assert ListDirAction.baseline_risk == 0.0
    assert AgentFinishAction.baseline_risk == 0.1
    assert WriteFileAction.baseline_risk == 0.3
    assert CodeAction.baseline_risk == 0.5
    assert RunCommandAction.baseline_risk == 0.5


def test_baseline_risk_validated_on_subclass_creation() -> None:
    from taskweavn.types.base import BaseAction

    with pytest.raises(ValueError, match="baseline_risk"):

        class _BadHigh(BaseAction):
            baseline_risk = 1.5

    with pytest.raises(ValueError, match="baseline_risk"):

        class _BadLow(BaseAction):
            baseline_risk = -0.1


# ---------------------------------------------------------------------------
# RiskAssessment invariants
# ---------------------------------------------------------------------------


def test_assessment_final_equals_max() -> None:
    a = RiskAssessment(baseline=0.3, dynamic=0.7)
    assert a.final == 0.7
    b = RiskAssessment(baseline=0.5, dynamic=0.5)
    assert b.final == 0.5


def test_assessment_rejects_dynamic_below_baseline() -> None:
    with pytest.raises(ValueError, match="dynamic.*baseline"):
        RiskAssessment(baseline=0.5, dynamic=0.3)


@pytest.mark.parametrize("score", [-0.01, 1.01, 2.0, -1.0])
def test_assessment_rejects_out_of_range(score: float) -> None:
    with pytest.raises(ValueError, match="out of range"):
        RiskAssessment(baseline=score, dynamic=max(score, 0.0))


def test_with_dynamic_monotone_only() -> None:
    a = RiskAssessment(baseline=0.3, dynamic=0.5, assessor="x")
    b = a.with_dynamic(0.8, rationale="llm flagged it", assessor="llm")
    assert b.baseline == 0.3
    assert b.dynamic == 0.8
    assert b.final == 0.8
    assert b.rationale[-1] == "llm flagged it"
    assert b.assessor == "llm"

    with pytest.raises(ValueError, match="lower"):
        a.with_dynamic(0.4, rationale="oops", assessor="llm")


def test_assessment_is_frozen() -> None:
    import dataclasses

    a = RiskAssessment(baseline=0.3, dynamic=0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.dynamic = 0.6  # type: ignore[misc]


def test_assessment_rationale_is_immutable_tuple() -> None:
    a = RiskAssessment(baseline=0.0, dynamic=0.0, rationale=("one",))
    assert isinstance(a.rationale, tuple)


# ---------------------------------------------------------------------------
# BaselineOnlyAssessor
# ---------------------------------------------------------------------------


@pytest.fixture
def context(tmp_path: Path) -> AssessmentContext:
    return AssessmentContext(
        workspace_root=tmp_path,
        session_id="abc12345",
        task_id="task-001",
    )


def test_baseline_only_uses_class_baseline(context: AssessmentContext) -> None:
    assessor = BaselineOnlyAssessor()
    a = WriteFileAction(path="foo.txt", content="bar")
    result = assessor.assess(a, context)
    assert result.baseline == 0.3
    assert result.dynamic == 0.3
    assert result.final == 0.3
    assert result.assessor == "baseline-only"


def test_baseline_only_handles_zero_baseline(context: AssessmentContext) -> None:
    a = ReadFileAction(path="foo.txt")
    result = BaselineOnlyAssessor().assess(a, context)
    assert result.baseline == 0.0
    assert result.final == 0.0


def test_baseline_only_satisfies_protocol(context: AssessmentContext) -> None:
    assessor: RiskAssessor = BaselineOnlyAssessor()
    assert isinstance(assessor, RiskAssessor)


def test_code_action_baseline_via_assessor(context: AssessmentContext) -> None:
    a = CodeAction(
        intent="print hi",
        code="print('hi')",
        tracking=TrackingConfig(files=[], variables=[]),
    )
    result = BaselineOnlyAssessor().assess(a, context)
    assert result.baseline == 0.5
    assert result.final == 0.5
