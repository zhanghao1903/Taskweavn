"""Framework-neutral event source and SSE helpers for Plato UI."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from taskweavn.server.ui_contract import UiEvent, resync_required


@runtime_checkable
class UiEventSource(Protocol):
    """Session-scoped source of UI events for local sidecar transports."""

    def subscribe(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
    ) -> Iterator[UiEvent]: ...


@dataclass(frozen=True)
class StaticUiEventSource:
    """Small deterministic event source for tests and local smoke checks."""

    events: tuple[UiEvent, ...] = ()

    def subscribe(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
    ) -> Iterator[UiEvent]:
        session_events = tuple(event for event in self.events if event.session_id == session_id)
        if cursor is None:
            yield from session_events
            return

        for index, event in enumerate(session_events):
            if event.cursor == cursor:
                yield from session_events[index + 1 :]
                return

        yield resync_required(
            session_id,
            cursor=_fallback_cursor(session_id, cursor),
            reason="cursor is not available in this sidecar event source",
        )


@dataclass(frozen=True)
class ResyncOnlyEventSource:
    """Event source used before durable or live event replay is wired."""

    reason: str = "sidecar event replay is not available"

    def subscribe(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
    ) -> Iterator[UiEvent]:
        yield resync_required(
            session_id,
            cursor=_fallback_cursor(session_id, cursor),
            reason=self.reason,
        )


def sse_frame(event: UiEvent) -> str:
    """Serialize one UiEvent as an SSE frame."""

    return "\n".join(
        (
            f"id: {event.cursor}",
            f"event: {event.event_type}",
            f"data: {event.model_dump_json()}",
            "",
            "",
        )
    )


def sse_stream(events: Iterable[UiEvent]) -> str:
    """Serialize a finite batch of UiEvents as an SSE stream body."""

    return "".join(sse_frame(event) for event in events)


def _fallback_cursor(session_id: str, cursor: str | None) -> str:
    if cursor is not None and cursor.strip():
        return cursor
    return f"resync:{session_id}"


__all__ = [
    "ResyncOnlyEventSource",
    "StaticUiEventSource",
    "UiEventSource",
    "sse_frame",
    "sse_stream",
]
