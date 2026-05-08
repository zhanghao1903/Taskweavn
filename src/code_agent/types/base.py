"""Base classes for the strongly-typed Action / Observation system.

Every event flowing through the agent is either an Action (something the agent
or user wants to happen) or an Observation (the result of an Action). Both
share an ``event_id`` and ``timestamp``, and both carry a ``kind`` discriminator
so they can be deserialized back to the correct subclass.

Subclasses auto-register with :data:`ActionRegistry` /
:data:`ObservationRegistry` via ``__init_subclass__``. To opt out (for an
abstract intermediate layer), set ``register=False`` in the class definition::

    class _BaseToolAction(BaseAction, register=False):
        ...
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from code_agent.types.registry import ActionRegistry, ObservationRegistry


def _new_event_id() -> str:
    return uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BaseEvent(BaseModel):
    """Anything that lives on the EventStream."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    event_id: str = Field(default_factory=_new_event_id)
    timestamp: datetime = Field(default_factory=_utcnow)

    # The discriminator is set by each subclass via ``__init_subclass__``.
    kind: ClassVar[str] = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-ready dict, including the ``kind`` discriminator."""
        data = self.model_dump(mode="json")
        data["kind"] = self.kind
        return data

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), sort_keys=True)


class BaseAction(BaseEvent):
    """An intent: something the agent (or user) wants to happen.

    Subclasses define the concrete payload (what file to read, what command to
    run, etc.). The Runtime turns each Action into one or more Observations.

    The class-level ``baseline_risk`` is the static lower bound on how
    dangerous *any* instance of this Action is. Runtime risk assessors
    (Phase 3.2+) can raise the risk further but never lower it. See
    ``docs/interaction_layer_design.md`` Appendix B for the calibration table.
    """

    baseline_risk: ClassVar[float] = 0.0
    """Static lower-bound risk for this Action class, in [0.0, 1.0].

    Override on subclasses; default 0.0 = pure-read / no side effects.
    Validated as a class-level constant, not a Pydantic field — instances
    do not carry their own baseline.
    """

    source: str = Field(
        default="agent",
        description="Who originated this action — 'agent', 'user', or 'system'.",
    )

    def __init_subclass__(
        cls,
        *,
        register: bool = True,
        kind: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        risk = cls.baseline_risk
        if not 0.0 <= float(risk) <= 1.0:
            raise ValueError(
                f"{cls.__name__}.baseline_risk={risk!r} out of range; "
                f"must satisfy 0.0 <= baseline_risk <= 1.0"
            )
        if not register:
            return
        resolved = ActionRegistry.register(cls, kind)
        cls.kind = resolved


class BaseObservation(BaseEvent):
    """The result of executing an Action.

    Every Observation references the ``event_id`` of the Action that produced
    it via ``action_id``. ``success`` lets the loop branch quickly without
    inspecting the full payload.
    """

    action_id: str | None = Field(
        default=None,
        description="event_id of the Action this Observation responds to.",
    )
    success: bool = Field(default=True)

    def __init_subclass__(
        cls,
        *,
        register: bool = True,
        kind: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if not register:
            return
        resolved = ObservationRegistry.register(cls, kind)
        cls.kind = resolved
