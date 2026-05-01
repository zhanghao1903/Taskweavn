"""ThoughtStore — side-channel storage for the LLM's internal reasoning.

Thoughts are *not* first-class EventStream members: they're noisier, larger,
and not every consumer cares about them. They live in their own store and
link back to the EventStream via ``event_id``.

Phase 1 ships only the Protocol plus :class:`NullThoughtStore` (no-op,
default). Phase 2.4 adds :class:`SqliteThoughtStore` behind the same
interface, controlled by configuration so turning thoughts off costs zero.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ThoughtRecord(BaseModel):
    """One reasoning artifact tied to a single EventStream event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(
        description="event_id of the BaseEvent this thought is associated with."
    )
    phase: str = Field(
        description="Loop phase the thought belongs to (e.g. 'plan', 'reflect')."
    )
    content: str
    timestamp: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ThoughtStore(Protocol):
    """Sink for ThoughtRecords. Implementations decide where to persist."""

    def write(self, record: ThoughtRecord) -> None:
        """Persist a single record."""
        ...

    def iter_for_event(self, event_id: str) -> Iterator[ThoughtRecord]:
        """Yield every thought associated with the given event, in append order."""
        ...

    def __len__(self) -> int:
        """Total number of records currently stored."""
        ...


class NullThoughtStore:
    """Default no-op store. Selected when thoughts are disabled.

    All writes are dropped; iteration yields nothing. Keeps consumers simple —
    they always have a ThoughtStore, never ``None`` — without paying any cost
    when the feature is off.
    """

    def write(self, record: ThoughtRecord) -> None:  # noqa: ARG002
        return None

    def iter_for_event(self, event_id: str) -> Iterator[ThoughtRecord]:  # noqa: ARG002
        return iter(())

    def __len__(self) -> int:
        return 0
