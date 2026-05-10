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

from taskweavn.observability.setup import get_channel_logger
from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation
from taskweavn.types.registry import ActionRegistry, ObservationRegistry

_ACTION_LOGGER = get_channel_logger("action")
_OBSERVATION_LOGGER = get_channel_logger("observation")

# Notes on the schema evolution:
#   * 3.1 shipped the table without ``task_id``. 3.3 adds the column via an
#     idempotent ALTER on first open so existing on-disk databases keep
#     working — old rows have task_id=NULL, new ones get the run id.
#   * The Protocol contract (``EventStream.append(event)``) is unchanged;
#     ``task_id`` is a concrete-impl-only optional kwarg. Callers holding the
#     Protocol type stay source-compatible.
#   * Per design doc §7.1.5: events table is already session-scoped (one
#     events.sqlite per session), so ``session_id`` does not appear here —
#     the cross-stream task join uses (session_id implicit, task_id explicit).
# Two-phase init so legacy DBs migrate cleanly:
#   1. Create the table (or no-op for legacy) WITHOUT touching task_id.
#   2. Add task_id column if it's missing.
#   3. Create indexes — by now task_id is guaranteed to exist.
_SCHEMA_BASE_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT    NOT NULL,
    kind        TEXT    NOT NULL,
    family      TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    payload     TEXT    NOT NULL,
    task_id     TEXT
);
"""

_SCHEMA_INDEXES_DDL = """
CREATE INDEX IF NOT EXISTS idx_events_kind         ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_timestamp    ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_task_created ON events(task_id, timestamp, id);
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
        self._conn.executescript(_SCHEMA_BASE_DDL)
        self._migrate_task_id_column()
        self._conn.executescript(_SCHEMA_INDEXES_DDL)
        # Serialize append() across threads — sqlite3 is fine, but the JSONL
        # channel logging side-effect should observe append order.
        self._lock = Lock()

    def _migrate_task_id_column(self) -> None:
        """Add ``task_id`` column to pre-3.3 databases. Idempotent.

        ``CREATE TABLE IF NOT EXISTS`` won't add a column to an already-existing
        table, so old workspaces would skip the new column entirely. We probe
        ``PRAGMA table_info`` and ALTER if missing; the new column defaults to
        NULL on every existing row, which is the contract.
        """
        cur = self._conn.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cur.fetchall()}
        if "task_id" not in columns:
            self._conn.execute("ALTER TABLE events ADD COLUMN task_id TEXT")
        # The matching index is created by ``_SCHEMA_INDEXES_DDL`` after this
        # method returns, so both fresh and migrated databases land on the
        # same final shape.

    # ------------------------------------------------------------------
    # EventStream Protocol
    # ------------------------------------------------------------------

    def append(self, event: BaseEvent, *, task_id: str | None = None) -> None:
        """Persist an event. ``task_id`` is an optional aggregation key.

        The Protocol declares only ``append(event)``; the keyword extension
        keeps Protocol-typed callers source-compatible (omit the kwarg) while
        AgentLoop and similar can stamp the current run id without going
        through a side channel. Old databases that don't yet have the column
        are migrated on connect (see :meth:`_migrate_task_id_column`).
        """
        family = _family_of(event)
        payload = event.to_dict()
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        timestamp_iso = event.timestamp.isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(event_id, kind, family, timestamp, payload, task_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.kind,
                    family,
                    timestamp_iso,
                    payload_json,
                    task_id,
                ),
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
    # Concrete-impl extensions (not in the EventStream Protocol)
    # ------------------------------------------------------------------

    def iter_for_task(self, task_id: str) -> Iterator[BaseEvent]:
        """Replay every event tagged with ``task_id``, in insertion order.

        Pairs with :meth:`SqliteMessageStream.list_for_task` to reconstruct
        the full timeline of one ``AgentLoop.run()``.
        """
        cursor = self._conn.execute(
            "SELECT family, payload FROM events WHERE task_id = ? "
            "ORDER BY timestamp ASC, id ASC",
            (task_id,),
        )
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
