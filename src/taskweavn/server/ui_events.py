"""Framework-neutral event source and SSE helpers for Plato UI."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, runtime_checkable

from taskweavn.server.ui_contract import UiEvent, resync_required

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS ui_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    cursor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(session_id, cursor)
);

CREATE INDEX IF NOT EXISTS idx_ui_events_session_created
    ON ui_events(session_id, id);
CREATE INDEX IF NOT EXISTS idx_ui_events_session_type_created
    ON ui_events(session_id, event_type, id);
"""


@runtime_checkable
class UiEventSource(Protocol):
    """Session-scoped source of UI events for local sidecar transports."""

    def subscribe(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
    ) -> Iterator[UiEvent]: ...


@runtime_checkable
class UiEventStore(UiEventSource, Protocol):
    """Appendable UI event source used by runtime emitters."""

    def append(self, event: UiEvent) -> UiEvent: ...


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


class UiEventSourceError(RuntimeError):
    """Raised when a UI event source cannot persist or replay events."""


class SqliteUiEventSource:
    """Workspace-backed UI event source.

    The store is intentionally small: AP-013D owns durable replay and cursor
    resync behavior; later runtime slices decide which system changes append
    audit-specific events.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def append(self, event: UiEvent) -> UiEvent:
        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO ui_events(
                        event_id,
                        session_id,
                        event_type,
                        cursor,
                        created_at,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.session_id,
                        event.event_type,
                        event.cursor,
                        event.created_at.isoformat(),
                        event.model_dump_json(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise UiEventSourceError(
                    "UI event event_id or session cursor already exists"
                ) from exc
            except sqlite3.Error as exc:
                raise UiEventSourceError("failed to append UI event") from exc
        return event

    def subscribe(
        self,
        session_id: str,
        *,
        cursor: str | None = None,
    ) -> Iterator[UiEvent]:
        with self._lock:
            if cursor is None:
                rows = tuple(
                    self._conn.execute(
                        """
                        SELECT payload_json FROM ui_events
                        WHERE session_id = ?
                        ORDER BY id ASC
                        """,
                        (session_id,),
                    )
                )
                return (_event_from_row(row) for row in rows)
            else:
                cursor_row = self._conn.execute(
                    """
                    SELECT id FROM ui_events
                    WHERE session_id = ? AND cursor = ?
                    """,
                    (session_id, cursor),
                ).fetchone()
                if cursor_row is None:
                    rows = tuple(
                        self._conn.execute(
                            """
                            SELECT payload_json FROM ui_events
                            WHERE session_id = ?
                            ORDER BY id ASC
                            """,
                            (session_id,),
                        )
                    )
                    return iter(
                        (
                            resync_required(
                                session_id,
                                cursor=cursor,
                                reason=(
                                    "cursor is not available in workspace UI event source"
                                ),
                            ),
                            *(_event_from_row(row) for row in rows),
                        )
                    )
                rows = tuple(
                    self._conn.execute(
                        """
                        SELECT payload_json FROM ui_events
                        WHERE session_id = ? AND id > ?
                        ORDER BY id ASC
                        """,
                        (session_id, int(cursor_row["id"])),
                    )
                )
        return (_event_from_row(row) for row in rows)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SqliteUiEventSource:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


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


def _event_from_row(row: sqlite3.Row) -> UiEvent:
    try:
        return UiEvent.model_validate_json(str(row["payload_json"]))
    except ValueError as exc:
        raise UiEventSourceError("invalid stored UI event row") from exc


__all__ = [
    "ResyncOnlyEventSource",
    "SqliteUiEventSource",
    "StaticUiEventSource",
    "UiEventSourceError",
    "UiEventSource",
    "UiEventStore",
    "sse_frame",
    "sse_stream",
]
