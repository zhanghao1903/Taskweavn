"""Base class for Tools.

A Tool packages four things together:

1. The Action subclass it consumes.
2. The Observation subclass it produces on success.
3. A name + human-readable description (consumed by the LLM tool-use schema).
4. The :meth:`execute` callable that turns the Action into the Observation.

Tools self-register with a :class:`code_agent.runtime.LocalRuntime` via
:meth:`register`, so the loop never has to know which executor handles which
Action — it just hands Actions to the Runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from code_agent.runtime.local import LocalRuntime
from code_agent.types.base import BaseAction, BaseObservation


class Tool[ActionT: BaseAction, ObservationT: BaseObservation](ABC):
    """Abstract base for an executable Tool."""

    name: ClassVar[str]
    description: ClassVar[str]
    action_type: ClassVar[type[BaseAction]]
    observation_type: ClassVar[type[BaseObservation]]

    @abstractmethod
    def execute(self, action: ActionT) -> ObservationT:
        """Run the action and return the observation. May raise — the Runtime
        catches exceptions and converts them to ErrorObservations."""

    def register(self, runtime: LocalRuntime) -> None:
        """Bind this tool's executor to ``runtime`` for its declared action type."""
        runtime.register(self.action_type, self.execute)  # type: ignore[arg-type]
