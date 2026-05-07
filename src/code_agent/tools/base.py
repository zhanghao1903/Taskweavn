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

    def startup(self) -> None:  # noqa: B027 — intentional no-op base hook.
        """Per-task setup hook.

        Called by :class:`code_agent.core.loop.AgentLoop` before the first
        action of a run. Stateless tools (read_file, write_file, …) leave this
        as a no-op; stateful tools (e.g. the CodeActionTool that owns a Docker
        container) override it to allocate per-task resources.
        """

    def shutdown(self) -> None:  # noqa: B027 — intentional no-op base hook.
        """Per-task teardown hook.

        Always called by the loop in a ``finally`` block opposite
        :meth:`startup`. Implementations must be tolerant of being called even
        when ``startup`` failed or was never invoked.
        """

    def register(self, runtime: LocalRuntime) -> None:
        """Bind this tool's executor to ``runtime`` for its declared action type."""
        runtime.register(self.action_type, self.execute)  # type: ignore[arg-type]
