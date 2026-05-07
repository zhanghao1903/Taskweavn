"""SQLite-backed :class:`EventStream` — durable spine for resumable sessions
(Phase 3.1).

Mirrors :class:`InMemoryEventStream` semantically (Protocol-conforming,
thread-safe append, snapshot iteration) but persists every event so a
session can be reconstructed from disk after the process exits.

Each row stores the event's ``to_dict()`` JSON together with its ``family``
(action vs observation) so the right registry can deserialize it back. The
``kind`` and ``timestamp`` columns are denormalized out of the JSON to make
``replay()`` filters cheap.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from code_agent.observability.setup import get_channel_logger
from code_agent.types.base import BaseAction, BaseEvent, BaseObservation
from code_agent.types.registry import ActionRegistry, ObservationRegistry

_ACTION_LOGGER = get_channel_logger("action")
_OBSERVATION_LOGGER = get_channel_logger("observation")

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT    NOT NULL,
    kind        TEXT    NOT NULL,
    family      TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    payload     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_kind      ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
"""


class SqliteEventStream:
    """Append-only event log persisted in a single SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # Autocommit + WAL: matches SqliteThoughtStore. Each append is its own
        # transaction; concurrent readers (e.g. a future replay UI) work
        # without explicit commit bookkeeping.
        self._conn = sqlite3.connect(
            str(self._db_path), isolation_level=None, check_same_thread=False
        )
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.executescript(_SCHEMA_DDL)
        # Serialize append() across threads — sqlite3 is fine, but the JSONL
        # channel logging side-effect should observe append order.
        self._lock = Lock()

    # ------------------------------------------------------------------
    # EventStream Protocol
    # ------------------------------------------------------------------

    def append(self, event: BaseEvent) -> None:
        family = _family_of(event)
        payload = event.to_dict()
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        timestamp_iso = event.timestamp.isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(event_id, kind, family, timestamp, payload) "
                "VALUES (?, ?, ?, ?, ?)",
                (event.event_id, event.kind, family, timestamp_iso, payload_json),
            )
            _emit_channel(event)

    def __iter__(self) -> Iterator[BaseEvent]:
        cursor = self._conn.execute(
            "SELECT family, payload FROM events ORDER BY id ASC"
        )
        return _iter_cursor(cursor)

    def __len__(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) FROM events")
        (count,) = cursor.fetchone()
        return int(count)

    def replay(
        self,
        *,
        since: datetime | None = None,
        kinds: Iterable[str] | None = None,
    ) -> Iterator[BaseEvent]:
        sql = "SELECT family, payload FROM events"
        clauses: list[str] = []
        params: list[Any] = []
        if since is not None:
            clauses.append("timestamp > ?")
            params.append(since.isoformat())
        kind_list = list(kinds) if kinds is not None else None
        if kind_list is not None:
            placeholders = ",".join("?" for _ in kind_list)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kind_list)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id ASC"
        cursor = self._conn.execute(sql, params)
        return _iter_cursor(cursor)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        """Close the underlying SQLite connection. Idempotent."""
        with contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SqliteEventStream:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _family_of(event: BaseEvent) -> str:
    if isinstance(event, BaseAction):
        return "action"
    if isinstance(event, BaseObservation):
        return "observation"
    raise TypeError(
        f"event {type(event).__name__} is neither BaseAction nor BaseObservation"
    )


def _emit_channel(event: BaseEvent) -> None:
    if isinstance(event, BaseAction):
        _ACTION_LOGGER.info("emit", extra={"data": event.to_dict()})
    elif isinstance(event, BaseObservation):
        _OBSERVATION_LOGGER.info("emit", extra={"data": event.to_dict()})


def _iter_cursor(cursor: sqlite3.Cursor) -> Iterator[BaseEvent]:
    for family, payload_json in cursor:
        payload = json.loads(payload_json)
        if family == "action":
            yield ActionRegistry.deserialize(payload)
        elif family == "observation":
            yield ObservationRegistry.deserialize(payload)
        else:
            raise ValueError(f"unknown event family in db: {family!r}")
