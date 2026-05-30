"""SQLite-backed task execution summary store."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from taskweavn.task.result_summary import (
    TaskExecutionSummary,
    TaskExecutionSummaryKind,
)
from taskweavn.task.stores import TaskStoreError

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS task_execution_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_execution_summaries_task
    ON task_execution_summaries(session_id, task_id, kind, updated_at);
"""


class SqliteTaskExecutionSummaryStore:
    """Durable store for result/error summaries addressed by TaskBus refs."""

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

    def put(self, summary: TaskExecutionSummary) -> TaskExecutionSummary:
        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO task_execution_summaries(
                        summary_id,
                        session_id,
                        task_id,
                        kind,
                        source,
                        created_at,
                        updated_at,
                        payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(summary_id) DO UPDATE SET
                        session_id = excluded.session_id,
                        task_id = excluded.task_id,
                        kind = excluded.kind,
                        source = excluded.source,
                        updated_at = excluded.updated_at,
                        payload = excluded.payload
                    """,
                    (
                        summary.summary_id,
                        summary.session_id,
                        summary.task_id,
                        summary.kind,
                        summary.source,
                        summary.created_at.isoformat(),
                        summary.updated_at.isoformat(),
                        summary.model_dump_json(),
                    ),
                )
            except sqlite3.Error as exc:
                raise TaskStoreError(f"failed to store task result summary: {exc}") from exc
        return summary

    def get(self, summary_id: str) -> TaskExecutionSummary | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT payload FROM task_execution_summaries
                WHERE summary_id = ?
                """,
                (summary_id,),
            ).fetchone()
        if row is None:
            return None
        return _summary_from_row(row)

    def get_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        kind: TaskExecutionSummaryKind | None = None,
    ) -> TaskExecutionSummary | None:
        sql = """
            SELECT payload FROM task_execution_summaries
            WHERE session_id = ?
              AND task_id = ?
        """
        params: list[Any] = [session_id, task_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY updated_at DESC, id DESC LIMIT 1"
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return _summary_from_row(row)

    def close(self) -> None:
        with self._lock, contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SqliteTaskExecutionSummaryStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _summary_from_row(row: sqlite3.Row) -> TaskExecutionSummary:
    return TaskExecutionSummary.model_validate_json(str(row["payload"]))


__all__ = ["SqliteTaskExecutionSummaryStore"]
