"""SQLite-backed :class:`ThoughtStore` (Phase 2.4).

Thoughts are second-class citizens compared to the EventStream — they're
larger, noisier, and not every consumer cares — so they live in their own
SQLite database keyed by ``event_id``. The store fulfils the same
:class:`code_agent.memory.thought_store.ThoughtStore` Protocol that
:class:`NullThoughtStore` implements, so flipping persistence on/off in
configuration is a one-line change inside the loop.

A thought is persisted only when:

* the store was instantiated (``backend="sqlite"`` in :class:`ThoughtConfig`), and
* its ``phase`` is in the configured allow-list (or no list is given).

The schema is intentionally tiny — one row per :class:`ThoughtRecord` with
``metadata`` stored as a JSON blob. Phase 3 will likely add a separate FTS5
table for retrieval; we do not pre-build that index here to keep the write
path cheap when retrieval isn't enabled.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from code_agent.memory.thought_store import ThoughtRecord

#: DDL applied lazily when a fresh database is opened.
_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS thoughts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT    NOT NULL,
    phase        TEXT    NOT NULL,
    content      TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL,
    metadata     TEXT    NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_thoughts_event_id ON thoughts(event_id);
"""


class SqliteThoughtStore:
    """Append-only thought log persisted in a single SQLite file."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        phases: Iterable[str] | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # `isolation_level=None` puts us in autocommit mode — every statement
        # is its own transaction. Combined with WAL it makes the store safe
        # for concurrent reads from a separate process (e.g. a Phase 3
        # retrieval worker) without any explicit commit() bookkeeping.
        self._conn = sqlite3.connect(
            str(self._db_path), isolation_level=None, check_same_thread=False
        )
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.executescript(_SCHEMA_DDL)
        self._phases: frozenset[str] | None = (
            frozenset(phases) if phases is not None else None
        )

    # ------------------------------------------------------------------
    # ThoughtStore Protocol
    # ------------------------------------------------------------------

    def write(self, record: ThoughtRecord) -> None:
        if self._phases is not None and record.phase not in self._phases:
            return
        self._conn.execute(
            "INSERT INTO thoughts(event_id, phase, content, timestamp, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                record.event_id,
                record.phase,
                record.content,
                record.timestamp.isoformat(),
                json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
            ),
        )

    def iter_for_event(self, event_id: str) -> Iterator[ThoughtRecord]:
        cursor = self._conn.execute(
            "SELECT event_id, phase, content, timestamp, metadata "
            "FROM thoughts WHERE event_id = ? ORDER BY id ASC",
            (event_id,),
        )
        for row in cursor:
            yield _row_to_record(row)

    def __len__(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) FROM thoughts")
        (count,) = cursor.fetchone()
        return int(count)

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

    def __enter__(self) -> SqliteThoughtStore:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def _row_to_record(
    row: tuple[str, str, str, str, str],
) -> ThoughtRecord:
    event_id, phase, content, timestamp_iso, metadata_json = row
    return ThoughtRecord(
        event_id=event_id,
        phase=phase,
        content=content,
        timestamp=datetime.fromisoformat(timestamp_iso),
        metadata=json.loads(metadata_json) if metadata_json else {},
    )
