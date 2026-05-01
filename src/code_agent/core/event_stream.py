"""EventStream — the append-only spine of every agent run.

Every Action and every Observation lands on the stream in arrival order.
Consumers (loop, audit agent, replay, persistence) read it back through the
same Protocol no matter where the events are physically stored — in memory
today, SQLite later (Phase 3.3).

Phase 1 ships :class:`InMemoryEventStream` only. The Protocol exists so the
SQLite implementation drops in without touching any consumer.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from threading import Lock
from typing import Protocol, runtime_checkable

from code_agent.types.base import BaseEvent


@runtime_checkable
class EventStream(Protocol):
    """Append-only ordered log of agent events."""

    def append(self, event: BaseEvent) -> None:
        """Add an event to the end of the stream."""
        ...

    def __iter__(self) -> Iterator[BaseEvent]:
        """Iterate a snapshot of every event currently on the stream."""
        ...

    def __len__(self) -> int:
        """Number of events on the stream."""
        ...

    def replay(
        self,
        *,
        since: datetime | None = None,
        kinds: Iterable[str] | None = None,
    ) -> Iterator[BaseEvent]:
        """Replay events in append order, optionally filtered.

        Args:
            since: Only emit events with ``timestamp > since`` (UTC).
            kinds: Only emit events whose ``kind`` is in this set.
        """
        ...


class InMemoryEventStream:
    """The default in-process EventStream. Thread-safe append + snapshot iter."""

    def __init__(self) -> None:
        self._events: list[BaseEvent] = []
        self._lock = Lock()

    def append(self, event: BaseEvent) -> None:
        with self._lock:
            self._events.append(event)

    def __iter__(self) -> Iterator[BaseEvent]:
        # Snapshot under the lock so concurrent appends can't mutate the list
        # mid-iteration.
        with self._lock:
            snapshot = list(self._events)
        return iter(snapshot)

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def replay(
        self,
        *,
        since: datetime | None = None,
        kinds: Iterable[str] | None = None,
    ) -> Iterator[BaseEvent]:
        kind_set = set(kinds) if kinds is not None else None
        for event in self:
            if since is not None and event.timestamp <= since:
                continue
            if kind_set is not None and event.kind not in kind_set:
                continue
            yield event
