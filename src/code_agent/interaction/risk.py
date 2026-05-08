"""Risk model for the interaction layer (Phase 3.2).

Every Action carries a *baseline* risk on its class — a static lower bound
that says "this kind of operation is at least this dangerous, regardless of
arguments". A :class:`RiskAssessor` then looks at the runtime instance and
may *raise* the dynamic risk further (an `rm -rf /` is worse than `ls`).

Two invariants make this composable:

* ``dynamic >= baseline`` — assessors can only add risk, never remove it
* ``final == max(baseline, dynamic)`` — the score the gate consults

Multiple assessors (LLM, audit, custom) can be chained via a future
``CompositeAssessor`` and the invariant still holds — chained max is
monotone.

The default :class:`BaselineOnlyAssessor` is enough for tests and for
``full_auto`` runs that don't need LLM-level judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
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
