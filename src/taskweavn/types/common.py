"""Built-in Action / Observation types shared by core, runtime and tools."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from taskweavn.types.base import BaseAction, BaseObservation


class ErrorObservation(BaseObservation):
    """Generic failure result.

    Used by Runtime when an Action cannot be dispatched (no executor) or when
    an executor raises. ``success`` is locked to ``False``.
    """

    success: bool = Field(default=False, frozen=True)
    error_type: str = Field(
        description="Short machine-readable category, e.g. 'no_executor' or 'execution_error'.",
    )
    message: str = Field(description="Human-readable error description.")


class AgentFinishAction(BaseAction):
    """Signals that the agent has completed the task.

    The ReAct loop short-circuits on this Action — it never reaches the
    Runtime. The ``final_answer`` is what the user sees.
    """

    # See docs/interaction_layer_design.md Appendix B — control flow only,
    # no IO, but consumes user attention so it's not literally zero.
    baseline_risk: ClassVar[float] = 0.1

    final_answer: str = Field(description="Summary of what was accomplished.")


class AgentFinishObservation(BaseObservation):
    """Companion observation emitted when the loop sees an :class:`AgentFinishAction`."""

    final_answer: str
