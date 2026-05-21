"""SQLite-backed TaskBus for published Task facts."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from taskweavn.task.models import TaskDomain
from taskweavn.task.stores import TaskStoreError

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    parent_id TEXT,
    root_id TEXT NOT NULL,
    status TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(session_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_session_created
    ON tasks(session_id, created_at, order_index, task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_children
    ON tasks(session_id, parent_id, order_index, created_at, task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_root
    ON tasks(session_id, root_id, order_index, created_at, task_id);
"""


class SqliteTaskBus:
    """SQLite TaskBus materialized view.

    This persists the same publish/read surface as :class:`InMemoryTaskBus`.
    Claim/complete/fail lifecycle remains future TaskBus work.
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
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()

    def publish(self, task: TaskDomain) -> TaskDomain:
        with self._lock:
            if task.status != "pending":
                raise TaskStoreError("published tasks must enter TaskBus as pending")
            if self.get(task.session_id, task.task_id) is not None:
                raise TaskStoreError(f"task {task.task_id!r} already exists")
            if task.parent_id is not None:
                parent = self.get(task.session_id, task.parent_id)
                if parent is None:
                    raise TaskStoreError(f"parent task {task.parent_id!r} not found")
                if parent.root_id != task.root_id:
                    raise TaskStoreError("child task root_id must match parent root_id")
            self._conn.execute(
                """
                INSERT INTO tasks(
                    session_id,
                    task_id,
                    parent_id,
                    root_id,
                    status,
                    order_index,
                    created_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.session_id,
                    task.task_id,
                    task.parent_id,
                    task.root_id,
                    task.status,
                    task.order_index,
                    task.created_at.isoformat(),
                    task.model_dump_json(),
                ),
            )
            return task

    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT payload FROM tasks
                WHERE session_id = ? AND task_id = ?
                """,
                (session_id, task_id),
            ).fetchone()
        if row is None:
            return None
        return _task_from_row(row)

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT payload FROM tasks
                WHERE session_id = ?
                ORDER BY created_at ASC, order_index ASC, task_id ASC
                """,
                (session_id,),
            ).fetchall()
        return [_task_from_row(row) for row in rows]

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        with self._lock:
            if parent_id is None:
                rows = self._conn.execute(
                    """
                    SELECT payload FROM tasks
                    WHERE session_id = ? AND parent_id IS NULL
                    ORDER BY order_index ASC, created_at ASC, task_id ASC
                    """,
                    (session_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT payload FROM tasks
                    WHERE session_id = ? AND parent_id = ?
                    ORDER BY order_index ASC, created_at ASC, task_id ASC
                    """,
                    (session_id, parent_id),
                ).fetchall()
        return [_task_from_row(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SqliteTaskBus:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _task_from_row(row: sqlite3.Row) -> TaskDomain:
    return TaskDomain.model_validate_json(str(row["payload"]))


__all__ = ["SqliteTaskBus"]
