"""SQLite-backed ContextStore for session-scoped context snapshots."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from taskweavn.context.models import ContextSnapshot, ContextTrace

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS context_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_run_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    context_version TEXT NOT NULL,
    renderer_version TEXT NOT NULL,
    rendered_input_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_task
    ON context_snapshots(session_id, task_id, agent_run_id, turn_index);

CREATE TABLE IF NOT EXISTS context_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL UNIQUE,
    snapshot_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    renderer_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_context_traces_snapshot
    ON context_traces(snapshot_id);
"""


class SqliteContextStore:
    """Durable local store for context snapshots and selection traces."""

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
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()

    def save_snapshot(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        payload = snapshot.model_dump_json()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO context_snapshots(
                    snapshot_id,
                    session_id,
                    task_id,
                    agent_id,
                    agent_run_id,
                    purpose,
                    turn_index,
                    context_version,
                    renderer_version,
                    rendered_input_hash,
                    created_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    task_id = excluded.task_id,
                    agent_id = excluded.agent_id,
                    agent_run_id = excluded.agent_run_id,
                    purpose = excluded.purpose,
                    turn_index = excluded.turn_index,
                    context_version = excluded.context_version,
                    renderer_version = excluded.renderer_version,
                    rendered_input_hash = excluded.rendered_input_hash,
                    created_at = excluded.created_at,
                    payload = excluded.payload
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.session_id,
                    snapshot.task_id,
                    snapshot.agent_id,
                    snapshot.agent_run_id,
                    snapshot.purpose,
                    snapshot.turn_index,
                    snapshot.context_version,
                    snapshot.renderer_version,
                    snapshot.rendered_input_hash,
                    snapshot.created_at.isoformat(),
                    payload,
                ),
            )
        return snapshot

    def save_trace(self, trace: ContextTrace) -> ContextTrace:
        payload = trace.model_dump_json()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO context_traces(
                    trace_id,
                    snapshot_id,
                    session_id,
                    task_id,
                    policy_version,
                    renderer_version,
                    created_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    snapshot_id = excluded.snapshot_id,
                    session_id = excluded.session_id,
                    task_id = excluded.task_id,
                    policy_version = excluded.policy_version,
                    renderer_version = excluded.renderer_version,
                    created_at = excluded.created_at,
                    payload = excluded.payload
                """,
                (
                    trace.trace_id,
                    trace.snapshot_id,
                    trace.session_id,
                    trace.task_id,
                    trace.policy_version,
                    trace.renderer_version,
                    trace.created_at.isoformat(),
                    payload,
                ),
            )
        return trace

    def get_snapshot(self, snapshot_id: str) -> ContextSnapshot | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM context_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        return _snapshot_from_row(row)

    def get_trace(self, trace_id: str) -> ContextTrace | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM context_traces WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
        if row is None:
            return None
        return _trace_from_row(row)

    def list_snapshots_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        agent_run_id: str | None = None,
    ) -> list[ContextSnapshot]:
        sql = """
            SELECT payload FROM context_snapshots
            WHERE session_id = ?
              AND task_id = ?
        """
        params: list[Any] = [session_id, task_id]
        if agent_run_id is not None:
            sql += " AND agent_run_id = ?"
            params.append(agent_run_id)
        sql += " ORDER BY turn_index ASC, created_at ASC, id ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_snapshot_from_row(row) for row in rows]

    def close(self) -> None:
        with self._lock, contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SqliteContextStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _snapshot_from_row(row: sqlite3.Row) -> ContextSnapshot:
    return ContextSnapshot.model_validate_json(str(row["payload"]))


def _trace_from_row(row: sqlite3.Row) -> ContextTrace:
    return ContextTrace.model_validate_json(str(row["payload"]))
