"""Tests for LLMRiskAssessor + CompositeAssessor (Phase 3.7).

The LLM is stubbed at the ``LLMClient.chat`` boundary so tests stay
deterministic and offline. Each scenario exercises one row in the
spec table:

    LLM reply            → expected behavior
    ─────────────────────────────────────────────
    valid JSON, score≥baseline   → use score
    valid JSON, score<baseline   → clamp to baseline
    valid JSON, score>1.0         → clamp to 1.0
    JSON wrapped in ``` fences   → still parsed
    malformed JSON               → fall back to baseline
    raises                       → fall back to baseline
    empty content                → fall back to baseline
    missing 'score' key          → fall back to baseline
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from code_agent.interaction import (
    AssessmentContext,
    BaselineOnlyAssessor,
    CompositeAssessor,
    LLMRiskAssessor,
    RiskAssessment,
    RiskAssessor,
)
from code_agent.llm.client import ChatResponse
from code_agent.tools.fs import ReadFileAction, WriteFileAction
from code_agent.tools.shell import RunCommandAction

# ---------------------------------------------------------------------------
# Stub LLM
# ---------------------------------------------------------------------------


@dataclass
class _StubLLM:
    """Captures the last chat() call and returns a canned ChatResponse,
    or raises if ``raises`` is set."""

    content: str = ""
    raises: Exception | None = None
    captured: list[dict[str, Any]] | None = None

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        self.captured = list(messages)
        if self.raises is not None:
            raise self.raises
        return ChatResponse(
            content=self.content,
            tool_calls=[],
            raw_assistant_message={"role": "assistant", "content": self.content},
        )


@pytest.fixture
def context(tmp_path: Path) -> AssessmentContext:
    return AssessmentContext(
        workspace_root=tmp_path,
        session_id="s",
        task_id="t",
    )


# ---------------------------------------------------------------------------
# LLMRiskAssessor — happy path
# ---------------------------------------------------------------------------


def test_llm_assessor_uses_score_when_above_baseline(
    context: AssessmentContext,
) -> None:
    """LLM returns a score above baseline → that score wins."""
    llm = _StubLLM(content='{"score": 0.85, "rationale": "writes credentials"}')
    assessor = LLMRiskAssessor(llm=llm)  # type: ignore[arg-type]
    action = WriteFileAction(path="creds.env", content="SECRET=...")
    result = assessor.assess(action, context)
    assert result.baseline == 0.3
    assert result.dynamic == pytest.approx(0.85)
    assert result.final == pytest.approx(0.85)
    assert result.assessor == "llm"
    assert "writes credentials" in result.rationale[0]


def test_llm_assessor_clamps_below_baseline_to_baseline(
    context: AssessmentContext,
) -> None:
    """``dynamic >= baseline`` is the contract; if the LLM tries to lower
    risk, we clamp up to the baseline rather than reject."""
    llm = _StubLLM(content='{"score": 0.1, "rationale": "looks safe"}')
    assessor = LLMRiskAssessor(llm=llm)  # type: ignore[arg-type]
    action = RunCommandAction(command="ls")
    result = assessor.assess(action, context)
    assert result.baseline == 0.5
    assert result.dynamic == 0.5  # clamped up
    assert result.final == 0.5


def test_llm_assessor_clamps_above_one_to_one(
    context: AssessmentContext,
) -> None:
    llm = _StubLLM(content='{"score": 9.9, "rationale": "extremely bad"}')
    assessor = LLMRiskAssessor(llm=llm)  # type: ignore[arg-type]
    result = assessor.assess(WriteFileAction(path="x", content="y"), context)
    assert result.dynamic == 1.0


def test_llm_assessor_accepts_json_inside_code_fence(
    context: AssessmentContext,
) -> None:
    """Models occasionally wrap responses in ```json fences. The regex-based
    parser snips the first balanced object so this still works."""
    llm = _StubLLM(
        content=(
            "Sure! Here is the JSON:\n"
            "```json\n"
            '{"score": 0.7, "rationale": "modifies a tracked path"}\n'
            "```\n"
            "Let me know if you need more."
        )
    )
    result = LLMRiskAssessor(llm=llm).assess(  # type: ignore[arg-type]
        WriteFileAction(path="a.py", content="print()"), context
    )
    assert result.dynamic == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# LLMRiskAssessor — total / fallback contract
# ---------------------------------------------------------------------------


def test_llm_assessor_falls_back_when_llm_raises(
    context: AssessmentContext,
) -> None:
    llm = _StubLLM(raises=RuntimeError("network exploded"))
    result = LLMRiskAssessor(llm=llm).assess(  # type: ignore[arg-type]
        WriteFileAction(path="a", content="b"), context
    )
    assert result.dynamic == 0.3  # = baseline
    assert "failed" in result.rationale[0].lower()
    assert "RuntimeError" in result.rationale[0]


def test_llm_assessor_falls_back_on_malformed_json(
    context: AssessmentContext,
) -> None:
    llm = _StubLLM(content="this is not json at all")
    result = LLMRiskAssessor(llm=llm).assess(  # type: ignore[arg-type]
        WriteFileAction(path="a", content="b"), context
    )
    assert result.dynamic == 0.3
    assert "failed" in result.rationale[0].lower()


def test_llm_assessor_falls_back_on_empty_content(
    context: AssessmentContext,
) -> None:
    llm = _StubLLM(content="")
    result = LLMRiskAssessor(llm=llm).assess(  # type: ignore[arg-type]
        WriteFileAction(path="a", content="b"), context
    )
    assert result.dynamic == 0.3


def test_llm_assessor_falls_back_when_score_missing(
    context: AssessmentContext,
) -> None:
    llm = _StubLLM(content='{"rationale": "no score here"}')
    result = LLMRiskAssessor(llm=llm).assess(  # type: ignore[arg-type]
        WriteFileAction(path="a", content="b"), context
    )
    assert result.dynamic == 0.3


# ---------------------------------------------------------------------------
# Prompt shape
# ---------------------------------------------------------------------------


def test_llm_assessor_prompt_includes_action_payload_and_baseline(
    context: AssessmentContext,
) -> None:
    """Best-effort: the prompt should mention the action class name and the
    baseline so the model has enough to grade. We don't assert on exact
    text — just on key facts being present."""
    llm = _StubLLM(content='{"score": 0.4, "rationale": "ok"}')
    assessor = LLMRiskAssessor(llm=llm)  # type: ignore[arg-type]
    assessor.assess(
        RunCommandAction(command="rm -rf /tmp/foo"), context
    )
    captured = llm.captured
    assert captured is not None
    user_msg = next(m for m in captured if m["role"] == "user")
    body = user_msg["content"]
    assert "RunCommandAction" in body
    assert "0.50" in body  # baseline rendered with %.2f
    assert "rm -rf" in body  # payload echoed


def test_llm_assessor_drops_observations_when_max_is_zero(
    tmp_path: Path,
) -> None:
    from code_agent.types.common import ErrorObservation

    ctx = AssessmentContext(
        workspace_root=tmp_path,
        session_id="s",
        recent_observations=(
            ErrorObservation(error_type="x", message="boom"),
            ErrorObservation(error_type="y", message="bang"),
        ),
    )
    llm = _StubLLM(content='{"score": 0.4, "rationale": "ok"}')
    LLMRiskAssessor(llm=llm, max_recent_observations=0).assess(  # type: ignore[arg-type]
        ReadFileAction(path="a"), ctx
    )
    assert llm.captured is not None
    body = next(m for m in llm.captured if m["role"] == "user")["content"]
    assert "(none)" in body


# ---------------------------------------------------------------------------
# CompositeAssessor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StaticAssessor:
    """Deterministic assessor: always returns the configured dynamic score
    and rationale. Used to exercise CompositeAssessor's fold logic."""

    dynamic: float
    note: str
    name: str = "static"

    def assess(
        self, action: Any, context: AssessmentContext
    ) -> RiskAssessment:
        baseline = float(getattr(type(action), "baseline_risk", 0.0))
        return RiskAssessment(
            baseline=baseline,
            dynamic=max(baseline, self.dynamic),
            rationale=(self.note,),
            assessor=self.name,
        )


def test_composite_picks_max_dynamic(context: AssessmentContext) -> None:
    """Two links, one says 0.4, the other says 0.8 → composite picks 0.8."""
    composite = CompositeAssessor(
        assessors=(
            _StaticAssessor(dynamic=0.4, note="low"),
            _StaticAssessor(dynamic=0.8, note="high"),
        ),
    )
    result = composite.assess(WriteFileAction(path="a", content="b"), context)
    assert result.baseline == 0.3
    assert result.dynamic == pytest.approx(0.8)
    assert result.assessor == "composite"
    # Both rationales survived.
    assert "low" in result.rationale
    assert "high" in result.rationale


def test_composite_swallows_link_order(context: AssessmentContext) -> None:
    """Order of assessors does not change the final dynamic score (max is
    commutative). Rationales appear in input order."""
    high_first = CompositeAssessor(
        assessors=(
            _StaticAssessor(dynamic=0.9, note="A"),
            _StaticAssessor(dynamic=0.2, note="B"),
        ),
    )
    low_first = CompositeAssessor(
        assessors=(
            _StaticAssessor(dynamic=0.2, note="B"),
            _StaticAssessor(dynamic=0.9, note="A"),
        ),
    )
    a = high_first.assess(WriteFileAction(path="a", content="b"), context)
    b = low_first.assess(WriteFileAction(path="a", content="b"), context)
    assert a.dynamic == b.dynamic == pytest.approx(0.9)
    assert a.rationale == ("A", "B")
    assert b.rationale == ("B", "A")


def test_composite_with_baseline_only_passthrough(
    context: AssessmentContext,
) -> None:
    """A composite of just BaselineOnlyAssessor matches the underlying
    behavior modulo assessor name."""
    composite = CompositeAssessor(assessors=(BaselineOnlyAssessor(),))
    direct = BaselineOnlyAssessor().assess(
        WriteFileAction(path="a", content="b"), context
    )
    via = composite.assess(WriteFileAction(path="a", content="b"), context)
    assert via.baseline == direct.baseline
    assert via.dynamic == direct.dynamic
    assert via.assessor == "composite"


def test_composite_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one"):
        CompositeAssessor(assessors=())


def test_composite_satisfies_protocol() -> None:
    a: RiskAssessor = CompositeAssessor(assessors=(BaselineOnlyAssessor(),))
    assert isinstance(a, RiskAssessor)


def test_composite_layered_with_llm(context: AssessmentContext) -> None:
    """End-to-end: BaselineOnly + LLMRiskAssessor stacked. LLM wins when
    its score > baseline; baseline wins otherwise — and the gate sees the
    composite identity in the assessor field."""
    llm = _StubLLM(content='{"score": 0.75, "rationale": "spicy"}')
    composite = CompositeAssessor(
        assessors=(
            BaselineOnlyAssessor(),
            LLMRiskAssessor(llm=llm),  # type: ignore[arg-type]
        ),
    )
    result = composite.assess(
        WriteFileAction(path="a", content="b"), context
    )
    assert result.dynamic == pytest.approx(0.75)
    assert result.assessor == "composite"
    assert "spicy" in result.rationale
