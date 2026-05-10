"""Multi-agent orchestration interface — placeholder for Phase 4.

Phase 1 deliberately freezes the *shape* of the multi-agent boundary so the
single-agent core never has to be retrofitted later: an :class:`Orchestrator`
schedules sub-tasks across child agents, exchanges messages via the same
Action / Observation types, and collects results.

Today we ship a no-op :class:`NullOrchestrator`. Phase 4 (E4) plugs in the
real planner / executor implementation behind this same Protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskweavn.types.base import BaseAction, BaseObservation


@runtime_checkable
class Orchestrator(Protocol):
    """Routes Actions to one or more child agents and aggregates Observations.

    The single-agent loop never imports a concrete Orchestrator — it only
    sees this Protocol, so multi-agent support stays additive.
    """

    def submit(self, action: BaseAction) -> BaseObservation:
        """Dispatch an Action and block until the resulting Observation is ready."""
        ...

    def shutdown(self) -> None:
        """Release any child-agent resources."""
        ...


class NullOrchestrator:
    """Default no-op implementation. Used wherever an Orchestrator is optional."""

    def submit(self, action: BaseAction) -> BaseObservation:
        raise NotImplementedError(
            "NullOrchestrator cannot dispatch actions. Plug in a real "
            "Orchestrator implementation in Phase 4 (E4)."
        )

    def shutdown(self) -> None:
        return None
