"""Risk model for the interaction layer (Phase 3.2 + 3.7).

Every Action carries a *baseline* risk on its class — a static lower bound
that says "this kind of operation is at least this dangerous, regardless of
arguments". A :class:`RiskAssessor` then looks at the runtime instance and
may *raise* the dynamic risk further (an `rm -rf /` is worse than `ls`).

Two invariants make this composable:

* ``dynamic >= baseline`` — assessors can only add risk, never remove it
* ``final == max(baseline, dynamic)`` — the score the gate consults

Multiple assessors (LLM, audit, custom) compose via :class:`CompositeAssessor`
and the invariant still holds — chained max is monotone.

Three concrete assessors ship in Phase 3:

* :class:`BaselineOnlyAssessor` — the default; enough for ``full_auto`` and
  most tests.
* :class:`LLMRiskAssessor` (Phase 3.7) — asks an LLM to grade dynamic risk
  given the action payload and recent observations. **Total**: any LLM /
  parse failure falls back to baseline so the gate never crashes the loop.
* :class:`CompositeAssessor` (Phase 3.7) — chains assessors; every link can
  only raise the dynamic score, and rationales accumulate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from code_agent.llm.client import LLMClient
    from code_agent.types.base import BaseAction, BaseObservation


# ---------------------------------------------------------------------------
# Score primitive
# ---------------------------------------------------------------------------

# RiskScore is a float in [0.0, 1.0]. Kept as an alias (not NewType) so
# arithmetic with literals stays ergonomic — the constraint is enforced at
# RiskAssessment construction time, not at the type level.
RiskScore = float


_SCORE_FLOOR = 0.0
_SCORE_CEILING = 1.0


def _validate_score(name: str, value: float) -> None:
    if not _SCORE_FLOOR <= value <= _SCORE_CEILING:
        raise ValueError(
            f"{name}={value!r} out of range; must satisfy "
            f"{_SCORE_FLOOR} <= {name} <= {_SCORE_CEILING}"
        )


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskAssessment:
    """The output of one (or a chain of) :class:`RiskAssessor`.

    ``rationale`` is a list rather than a string so a CompositeAssessor can
    append without losing earlier reasoning. ``assessor`` names the producer
    so logs and audits can answer "who set this score?".
    """

    baseline: RiskScore
    dynamic: RiskScore
    rationale: tuple[str, ...] = ()
    assessor: str = "baseline"

    def __post_init__(self) -> None:
        _validate_score("baseline", self.baseline)
        _validate_score("dynamic", self.dynamic)
        if self.dynamic < self.baseline:
            raise ValueError(
                f"dynamic ({self.dynamic}) must be >= baseline "
                f"({self.baseline}); assessors can only raise risk, not lower it"
            )

    @property
    def final(self) -> RiskScore:
        # Defensive max(); __post_init__ already enforces dynamic >= baseline,
        # but the formula is the canonical contract callers reason about.
        return max(self.baseline, self.dynamic)

    def with_dynamic(
        self, dynamic: RiskScore, *, rationale: str, assessor: str
    ) -> RiskAssessment:
        """Return a new assessment with raised dynamic risk.

        Used by composite assessors to fold in a downstream judgment without
        mutating the upstream result. The new ``dynamic`` must not undercut
        the existing one — the helper enforces monotonicity.
        """
        if dynamic < self.dynamic:
            raise ValueError(
                f"composite update would lower dynamic from {self.dynamic} "
                f"to {dynamic}; assessors can only raise risk"
            )
        return RiskAssessment(
            baseline=self.baseline,
            dynamic=dynamic,
            rationale=(*self.rationale, rationale),
            assessor=assessor,
        )

    # ── Serialization helpers ────────────────────────────────────────
    # Used by AgentMessage and SqliteMessageStream to round-trip through
    # SQL JSON columns. Kept on the type so the wire format lives in one
    # place — change here, change everywhere.

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline,
            "dynamic": self.dynamic,
            "rationale": list(self.rationale),
            "assessor": self.assessor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RiskAssessment:
        return cls(
            baseline=float(data["baseline"]),  # type: ignore[arg-type]
            dynamic=float(data["dynamic"]),  # type: ignore[arg-type]
            rationale=tuple(data.get("rationale", ())),  # type: ignore[arg-type]
            assessor=str(data.get("assessor", "baseline")),
        )


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssessmentContext:
    """Everything an assessor is allowed to look at.

    Phase 3.2 ships the minimum: workspace location, session/task identity,
    and the most recent observations (so an LLM assessor can spot patterns
    like "the agent has retried this command three times"). Phase 3.3 will
    add ``recent_messages`` once :class:`AgentMessage` lands.
    """

    workspace_root: Path
    session_id: str
    task_id: str | None = None
    recent_observations: tuple[BaseObservation, ...] = ()


# ---------------------------------------------------------------------------
# Protocol + default implementation
# ---------------------------------------------------------------------------


@runtime_checkable
class RiskAssessor(Protocol):
    """Evaluate the dynamic risk of one Action instance.

    Implementations MUST satisfy the
    ``RiskAssessment.dynamic >= action.baseline_risk`` invariant. The
    :class:`RiskAssessment` constructor enforces it, so the simplest way to
    comply is to construct the result through it.
    """

    def assess(
        self, action: BaseAction, context: AssessmentContext
    ) -> RiskAssessment: ...


@dataclass(frozen=True)
class BaselineOnlyAssessor:
    """No-op assessor: trust the class-level baseline verbatim.

    Used as the default when no LLM-backed assessor is configured (CI,
    ``full_auto`` runs, unit tests). Always returns ``dynamic == baseline``,
    so ``final == baseline``.
    """

    name: str = "baseline-only"

    def assess(
        self, action: BaseAction, context: AssessmentContext
    ) -> RiskAssessment:
        baseline = float(getattr(type(action), "baseline_risk", 0.0))
        return RiskAssessment(
            baseline=baseline,
            dynamic=baseline,
            rationale=("static baseline; no dynamic evaluation",),
            assessor=self.name,
        )


# ---------------------------------------------------------------------------
# LLMRiskAssessor (Phase 3.7)
# ---------------------------------------------------------------------------


_LLM_RISK_SYSTEM_PROMPT = """\
You are a security risk evaluator for a code agent.

You are given:
* the class-level *baseline* risk of an action (a float in [0,1])
* the action payload (JSON)
* recent observations from the agent's runtime

Rate the *dynamic* risk of this specific instance on a 0.0–1.0 scale.
Your score MUST be >= the baseline; assessors may only RAISE risk, never
lower it. If the action looks routine, return the baseline. If the
arguments make it more dangerous (e.g. ``rm -rf`` on a wide path,
writing to a config file outside the workspace, running a command with
credentials), raise the score proportionally.

Respond with a single JSON object and NOTHING else:

    {"score": <float in [0,1]>, "rationale": "<one sentence>"}

No prose outside the JSON. No markdown fences. No additional fields.
"""


# Models occasionally wrap JSON in ```json fences despite instructions; this
# regex extracts the first balanced object so the parser is forgiving.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class LLMRiskAssessor:
    """LLM-backed dynamic risk grader (Phase 3.7).

    Builds a single chat prompt per assessment, calls
    :meth:`LLMClient.chat`, parses a JSON ``{"score","rationale"}`` payload,
    and clamps the score into ``[baseline, 1.0]``.

    **Total**: any failure (network error, malformed JSON, score out of
    range, etc.) falls back to a baseline-only assessment with the failure
    noted in the rationale. The gate then proceeds against the static class
    risk — the same fallback as :class:`BaselineOnlyAssessor`. This keeps
    the loop alive when the LLM is flaky; the alternative ("crash the loop
    because risk grading failed") would be strictly worse.

    The assessor caps the number of recent observations included in the
    prompt to keep the request cheap. Pass ``max_recent_observations=0`` to
    drop them entirely.
    """

    llm: LLMClient
    name: str = "llm"
    max_recent_observations: int = 5

    def assess(
        self, action: BaseAction, context: AssessmentContext
    ) -> RiskAssessment:
        baseline = float(getattr(type(action), "baseline_risk", 0.0))
        try:
            user_payload = self._build_user_payload(action, context, baseline)
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": _LLM_RISK_SYSTEM_PROMPT},
                    {"role": "user", "content": user_payload},
                ],
                tools=None,
            )
            score, rationale = self._parse(response.content)
        except Exception as exc:
            return RiskAssessment(
                baseline=baseline,
                dynamic=baseline,
                rationale=(
                    f"llm assessor {self.name!r} failed ({type(exc).__name__}: "
                    f"{exc}); falling back to baseline",
                ),
                assessor=self.name,
            )

        # Clamp into [baseline, 1.0]. We don't error on out-of-range scores —
        # an LLM scoring 1.5 just means "very dangerous"; treat as 1.0.
        clamped = max(baseline, min(score, _SCORE_CEILING))
        return RiskAssessment(
            baseline=baseline,
            dynamic=clamped,
            rationale=(rationale,),
            assessor=self.name,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_user_payload(
        self,
        action: BaseAction,
        context: AssessmentContext,
        baseline: RiskScore,
    ) -> str:
        """Render the action + context into the user message body.

        Trims long observation reprs to keep prompts cheap. The LLM only
        needs a hint of the recent state; we don't dump full payloads.
        """
        action_payload: dict[str, Any]
        if hasattr(action, "model_dump"):
            try:
                action_payload = action.model_dump(mode="json")
            except Exception:
                action_payload = {"_repr": repr(action)}
        else:
            action_payload = {"_repr": repr(action)}

        recent: list[str] = []
        if self.max_recent_observations > 0 and context.recent_observations:
            for obs in list(context.recent_observations)[-self.max_recent_observations:]:
                snippet = repr(obs)
                if len(snippet) > 240:
                    snippet = snippet[:237] + "..."
                recent.append(f"- {snippet}")

        lines = [
            f"Action class: {type(action).__name__}",
            f"Baseline risk: {baseline:.2f}",
            f"Workspace root: {context.workspace_root}",
            f"Session id: {context.session_id}",
            f"Action payload (JSON): {json.dumps(action_payload, default=str)}",
        ]
        if recent:
            lines.append("Recent observations:")
            lines.extend(recent)
        else:
            lines.append("Recent observations: (none)")
        return "\n".join(lines)

    @staticmethod
    def _parse(content: str) -> tuple[float, str]:
        """Extract ``(score, rationale)`` from the model's reply.

        The model is instructed to return raw JSON; we accept stray prose by
        snipping the first balanced object via :data:`_JSON_OBJECT_RE`.
        Raises on anything that isn't recoverable so the caller's
        ``except Exception`` arm logs the failure in the rationale.
        """
        if not content or not content.strip():
            raise ValueError("LLM returned empty content")
        match = _JSON_OBJECT_RE.search(content)
        if match is None:
            raise ValueError(f"no JSON object in LLM reply: {content!r}")
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError(f"LLM JSON is not an object: {payload!r}")
        if "score" not in payload:
            raise ValueError(f"LLM JSON missing 'score' field: {payload!r}")
        score = float(payload["score"])
        rationale_raw = payload.get("rationale", "")
        rationale = str(rationale_raw).strip() or "(no rationale provided)"
        return score, rationale


# ---------------------------------------------------------------------------
# CompositeAssessor (Phase 3.7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompositeAssessor:
    """Chain multiple :class:`RiskAssessor` so each can only raise risk.

    The composite is itself a ``RiskAssessor``. It runs each link in order,
    folding via :meth:`RiskAssessment.with_dynamic` so the
    ``dynamic >= prior_dynamic`` invariant is enforced at every step.
    Rationales accumulate; the final ``assessor`` field is the composite's
    own name so logs distinguish "the composite said X" from any single
    link's contribution.

    A composite with one assessor is equivalent to that assessor (modulo the
    name change). An empty list raises at construction time — silent no-ops
    are worse than a clear error.
    """

    assessors: tuple[RiskAssessor, ...] = field(default_factory=tuple)
    name: str = "composite"

    def __post_init__(self) -> None:
        if not self.assessors:
            raise ValueError(
                "CompositeAssessor requires at least one assessor; got empty tuple"
            )

    def assess(
        self, action: BaseAction, context: AssessmentContext
    ) -> RiskAssessment:
        result = self.assessors[0].assess(action, context)
        # Re-stamp the first link's rationale under the composite name so
        # the audit trail is consistent regardless of how many links ran.
        rationales: list[str] = list(result.rationale)
        running_dynamic = result.dynamic
        baseline = result.baseline

        for asr in self.assessors[1:]:
            link = asr.assess(action, context)
            # Each link must agree on baseline (they're all looking at the
            # same action). If a downstream link reports a different
            # baseline, prefer the higher one — same monotonicity argument.
            baseline = max(baseline, link.baseline)
            running_dynamic = max(running_dynamic, link.dynamic)
            rationales.extend(link.rationale)

        return RiskAssessment(
            baseline=baseline,
            dynamic=running_dynamic,
            rationale=tuple(rationales),
            assessor=self.name,
        )
