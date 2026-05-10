"""AgentMessage + MessageStream Protocol (Phase 3.3).

A message is the user-facing analogue of an Action: when the agent wants
the user to confirm something ("ok to delete?"), tell them about something
that already happened ("I just edited auth.py"), or accept a reply, it goes
through the message stream — not the EventStream.

The two streams stay separate because users care about *messages* (product
surface) but rarely about every individual Action (audit surface). Mixing
them would couple two evolution rates that should stay independent.

This module defines the type and the read protocol; the write side
(:class:`MessageBus`) lands in 3.4. The default SQLite-backed read impl
(:class:`SqliteMessageStream`) lives next door — see
``taskweavn.interaction.sqlite_message_stream``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from taskweavn.interaction.risk import RiskAssessment

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

MessageType = Literal["informational", "actionable", "response"]
"""Three families of message — see design doc §4.3.1."""

ResponseSource = Literal[
    "user", "timeout_default", "timeout_confident", "timeout_skip", "auto_proceed"
]
"""Who produced a ``response`` — humans or one of the timeout self-decisions."""


def _new_message_id() -> str:
    return uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Message type
# ---------------------------------------------------------------------------


class AgentMessage(BaseModel):
    """One row on the user/agent message stream.

    Three message types share the same shape — the discriminator is
    ``message_type`` and the per-type fields are simply unused for the others
    (e.g. ``response_source`` is None on actionable / informational).

    ``task_id`` is the within-session aggregation key: every message emitted
    inside one ``AgentLoop.run()`` shares it. Cross-stream queries (events
    ⊕ messages) use this key to assemble "what happened during one run".
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    # ── Identity ──────────────────────────────────────────────────────
    message_id: str = Field(default_factory=_new_message_id)
    session_id: str
    task_id: str | None = None
    """Set to the AgentLoop.run() task id; None for non-task-bound messages
    (e.g. resume notices emitted before any run starts)."""

    agent_id: str = "agent"
    """Phase 3 stays 'agent' / 'user' / 'system'. Phase 4 fills concrete
    agent instance ids."""

    parent_message_id: str | None = None
    """If this is a ``response``, points at the actionable it answers."""

    # ── Body ──────────────────────────────────────────────────────────
    message_type: MessageType
    content: str
    context: dict[str, Any] = Field(default_factory=dict)
    """Structured side-channel — relevant file paths, code snippets, etc.
    Anything UI / LLM might want without parsing ``content``."""

    # ── Actionable-only ───────────────────────────────────────────────
    action_options: list[str] = Field(default_factory=list)
    """Suggested reply values when the agent wants a choice. Unconstrained
    free-form input is still accepted — this list is just a UI hint."""

    requires_response: bool = False
    timeout_seconds: float | None = None
    """Per-message override of AutonomyBehavior.wait_timeout. None = use
    behavior's value (see Q3 in design doc)."""

    risk_assessment: RiskAssessment | None = None
    """The assessment that triggered this actionable. Required in practice
    for actionable; left optional in the type so test fixtures can omit it."""

    related_action_id: str | None = None
    """``event_id`` of the BaseAction this actionable concerns. Pinning a
    message to its underlying action lets the UI show 'agent wants to run X'
    rather than just an opaque message body."""

    # ── Response-only ─────────────────────────────────────────────────
    response_source: ResponseSource | None = None
    response_value: str | None = None

    # ── Common ────────────────────────────────────────────────────────
    created_at: datetime = Field(default_factory=_utcnow)

    # ── Validators ────────────────────────────────────────────────────

    @field_validator("risk_assessment", mode="before")
    @classmethod
    def _coerce_risk(cls, value: object) -> object:
        # Accept a dict form so SqliteMessageStream can hydrate AgentMessage
        # from the SQL row without going through a separate codec.
        if value is None or isinstance(value, RiskAssessment):
            return value
        if isinstance(value, dict):
            return RiskAssessment.from_dict(value)
        raise TypeError(
            f"risk_assessment must be RiskAssessment | dict | None; "
            f"got {type(value).__name__}"
        )

    @field_serializer("risk_assessment", when_used="json")
    def _serialize_risk(
        self, value: RiskAssessment | None
    ) -> dict[str, object] | None:
        return None if value is None else value.to_dict()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MessageStreamError(RuntimeError):
    """Raised by MessageStream / MessageBus implementations on consistency
    failures (duplicate response, unknown parent, etc.)."""


# ---------------------------------------------------------------------------
# Read protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MessageStream(Protocol):
    """Read-only view over the message log.

    Writes go through :class:`MessageBus` (Phase 3.4); the bus writes through
    a stream-compatible storage backend, then the reader sees the same row.

    All ``list_*`` methods iterate in ``(created_at ASC, insertion_id ASC)``
    order so the timeline is deterministic even when many messages share a
    millisecond. The trailing id is what makes the order *strictly* total —
    timestamps alone aren't enough on a fast loop.
    """

    # ── Direct lookup ─────────────────────────────────────────────────
    def get(self, message_id: str) -> AgentMessage | None: ...

    # ── Aggregation queries ───────────────────────────────────────────
    def list_for_session(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]: ...

    def list_for_task(
        self,
        task_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]: ...

    def list_for_agent(
        self,
        agent_id: str,
        *,
        session_id: str | None = None,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]: ...

    # ── Relationship queries ──────────────────────────────────────────
    def pending_actionable(
        self, session_id: str, *, task_id: str | None = None
    ) -> list[AgentMessage]: ...

    def response_for(self, message_id: str) -> AgentMessage | None: ...

    def thread(self, message_id: str) -> list[AgentMessage]: ...

    def __len__(self) -> int: ...
