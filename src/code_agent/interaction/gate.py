"""AutonomyGate — the single "ask user or not?" decision point (Phase 3.5).

Every Action the AgentLoop is about to execute passes through ``check()``.
The gate consumes an :class:`AutonomyBehavior` (user contract), runs a
:class:`RiskAssessor` (objective danger score), and emits a
:class:`GateDecision` saying one of:

* ``PROCEED`` — execute now; optionally publish an informational message
  to keep the user in the loop.
* ``EMIT`` — publish an ``actionable`` message and let the
  :class:`WaitCoordinator` figure out how to wait for / time out on a
  reply.

The gate itself does **not** publish or block. It's a pure function of
``(action, context, behavior, assessor)`` so it's trivially testable and
trivially composable (you can plug in a different assessor without
touching anything downstream).

The branch logic mirrors design doc §5.1:

* ``trigger="never"`` → PROCEED unconditionally.
* ``trigger="always"`` → EMIT unconditionally.
* ``trigger="on_risk"`` → EMIT iff ``risk.final >= behavior.risk_threshold``;
  else PROCEED. Emits an informational on PROCEED iff
  ``notify_on_proceed and risk.final > 0``.
* ``trigger="on_uncertainty"`` → EMIT iff confidence < threshold (Phase 3
  has no :class:`ConfidenceProvider`, so confidence defaults to 1.0,
  meaning this branch always PROCEEDS until the provider lands).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from code_agent.interaction.autonomy import AutonomyBehavior
from code_agent.interaction.risk import (
    AssessmentContext,
    RiskAssessment,
    RiskAssessor,
)

if TYPE_CHECKING:  # pragma: no cover
    from code_agent.types.base import BaseAction


# ---------------------------------------------------------------------------
# Verdict + decision
# ---------------------------------------------------------------------------


class GateVerdict(Enum):
    """Three outcomes the gate can return — see module docstring."""

    PROCEED = "proceed"
    EMIT = "emit"


@dataclass(frozen=True)
class GateDecision:
    """Result of :meth:`AutonomyGate.check`.

    Carries the underlying :class:`RiskAssessment` so callers can attach it
    to the published actionable message (UI shows the score), and ``reason``
    so logs explain *why* the gate chose this branch — invaluable when
    debugging "why did the agent ask me about this innocuous thing?".
    """

    verdict: GateVerdict
    risk_assessment: RiskAssessment
    inform_user: bool
    """Only meaningful when ``verdict == PROCEED``; the AgentLoop should
    publish an informational message before executing the action.
    Always ``False`` when ``verdict == EMIT`` (the actionable itself is the
    notification)."""
    reason: str


# ---------------------------------------------------------------------------
# Confidence provider stub
# ---------------------------------------------------------------------------


@runtime_checkable
class ConfidenceProvider(Protocol):
    """Optional hook (Phase 3.7+).

    Implementations look at the LLM output that produced ``action`` (logprobs,
    explicit ``confidence`` fields, audit verdict, …) and report a value in
    ``[0.0, 1.0]``: 1.0 means "very sure", 0.0 means "totally uncertain".

    Phase 3 ships the gate *without* a provider; ``trigger='on_uncertainty'``
    therefore degrades to PROCEED. That's the safer side of the bimodal
    failure: missing confidence shouldn't block work.
    """

    def get(self, action: BaseAction) -> float: ...


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


class AutonomyGate:
    """Decide whether to ask the user before running ``action``.

    Stateless modulo its dependencies — ``check`` is a pure function of the
    inputs. Threading-safe by construction; share one gate across the whole
    loop or build a fresh one per session, both work.
    """

    def __init__(
        self,
        behavior: AutonomyBehavior,
        assessor: RiskAssessor,
        confidence_provider: ConfidenceProvider | None = None,
    ) -> None:
        self._behavior = behavior
        self._assessor = assessor
        self._confidence_provider = confidence_provider

    # ------------------------------------------------------------------
    # Read-only views (handy for tests / introspection)
    # ------------------------------------------------------------------

    @property
    def behavior(self) -> AutonomyBehavior:
        return self._behavior

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def check(
        self,
        action: BaseAction,
        context: AssessmentContext,
    ) -> GateDecision:
        """Run the assessor and dispatch on ``behavior.trigger``."""
        assessment = self._assessor.assess(action, context)
        trigger = self._behavior.trigger

        if trigger == "never":
            return GateDecision(
                verdict=GateVerdict.PROCEED,
                risk_assessment=assessment,
                inform_user=self._inform_on_proceed(assessment),
                reason="trigger=never",
            )

        if trigger == "always":
            return GateDecision(
                verdict=GateVerdict.EMIT,
                risk_assessment=assessment,
                inform_user=False,
                reason="trigger=always",
            )

        if trigger == "on_risk":
            threshold = self._behavior.risk_threshold
            if assessment.final >= threshold:
                return GateDecision(
                    verdict=GateVerdict.EMIT,
                    risk_assessment=assessment,
                    inform_user=False,
                    reason=(
                        f"risk {assessment.final:.2f} >= threshold {threshold:.2f}"
                    ),
                )
            return GateDecision(
                verdict=GateVerdict.PROCEED,
                risk_assessment=assessment,
                inform_user=self._inform_on_proceed(assessment),
                reason=(
                    f"risk {assessment.final:.2f} < threshold {threshold:.2f}"
                ),
            )

        if trigger == "on_uncertainty":
            confidence = self._confidence(action)
            threshold = self._behavior.confidence_threshold
            if confidence < threshold:
                return GateDecision(
                    verdict=GateVerdict.EMIT,
                    risk_assessment=assessment,
                    inform_user=False,
                    reason=(
                        f"confidence {confidence:.2f} < threshold {threshold:.2f}"
                    ),
                )
            return GateDecision(
                verdict=GateVerdict.PROCEED,
                risk_assessment=assessment,
                inform_user=self._inform_on_proceed(assessment),
                reason=(
                    f"confidence {confidence:.2f} >= threshold {threshold:.2f}"
                ),
            )

        # The Literal restricts ``trigger``; an unknown value here means
        # someone forced an invalid AutonomyBehavior past validation.
        raise ValueError(f"unknown autonomy trigger: {trigger!r}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _inform_on_proceed(self, assessment: RiskAssessment) -> bool:
        """Should we publish an informational alongside a silent proceed?

        Per design doc §5.1: only when ``notify_on_proceed`` is on AND there's
        actually some risk to mention. We use ``> 0`` as the floor — risk 0.0
        actions (read-only file ops, etc.) shouldn't spam the user.
        """
        return self._behavior.notify_on_proceed and assessment.final > 0.0

    def _confidence(self, action: BaseAction) -> float:
        """Look up confidence for ``action`` or default to fully-confident.

        No provider → 1.0, which makes ``on_uncertainty`` a no-op until a
        provider is wired in. That's the documented Phase 3 behavior.
        """
        if self._confidence_provider is None:
            return 1.0
        value = self._confidence_provider.get(action)
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"confidence_provider returned {value!r}; must be in [0, 1]"
            )
        return value
