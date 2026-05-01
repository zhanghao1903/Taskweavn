"""Runtime Protocol — turns Actions into Observations.

The Runtime is the *only* component that knows where actions actually
execute (current process, Docker, remote sandbox, ...). The agent loop
hands off Actions and consumes Observations through this Protocol; the
implementation behind it is swappable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from code_agent.types.base import BaseAction, BaseObservation


@runtime_checkable
class Runtime(Protocol):
    """Executes a single Action and returns the resulting Observation."""

    def execute(self, action: BaseAction) -> BaseObservation:
        """Run ``action`` and return its Observation.

        Implementations must never raise: convert any failure into an
        :class:`~code_agent.types.ErrorObservation` so the loop can decide
        what to do next without try/except scaffolding everywhere.
        """
        ...
