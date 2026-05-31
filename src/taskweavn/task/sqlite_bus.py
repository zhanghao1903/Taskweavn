"""SQLite-backed TaskBus for published Task facts."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from taskweavn.task.bus import _retry_updates
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

    This persists the same publish/read/lifecycle surface as
    :class:`InMemoryTaskBus`.
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

    def claim_next(
        self,
        session_id: str,
        *,
        capability: str,
        agent_id: str,
    ) -> TaskDomain | None:
        if not capability.strip():
            raise TaskStoreError("claim capability must not be empty")
        if not agent_id.strip():
            raise TaskStoreError("claim agent_id must not be empty")
        with self._lock:
            session_tasks = self.list_for_session(session_id)
            task_by_id = {task.task_id: task for task in session_tasks}
            rows = self._conn.execute(
                """
                SELECT child.payload
                FROM tasks AS child
                LEFT JOIN tasks AS parent
                  ON parent.session_id = child.session_id
                 AND parent.task_id = child.parent_id
                WHERE child.session_id = ?
                  AND child.status = 'pending'
                  AND (
                    child.parent_id IS NULL
                    OR parent.task_id IS NOT NULL
                  )
                ORDER BY child.created_at ASC, child.order_index ASC, child.task_id ASC
                """,
                (session_id,),
            ).fetchall()
            for row in rows:
                task = _task_from_row(row)
                if task.required_capability != capability:
                    continue
                if not _parent_is_done(
                    task,
                    task_by_id=task_by_id,
                    session_tasks=session_tasks,
                ):
                    continue
                updated = task.model_copy(
                    update={
                        "status": "running",
                        "claimed_by": agent_id,
                        "started_at": _utcnow(),
                    }
                )
                self._save_task(updated)
                return updated
        return None

    def complete(
        self,
        session_id: str,
        task_id: str,
        *,
        result_ref: str | None = None,
    ) -> TaskDomain:
        return self._transition_running(
            session_id,
            task_id,
            status="done",
            result_ref=result_ref,
            error_ref=None,
        )

    def fail(
        self,
        session_id: str,
        task_id: str,
        *,
        error_ref: str,
    ) -> TaskDomain:
        if not error_ref.strip():
            raise TaskStoreError("failed task requires error_ref")
        return self._transition_running(
            session_id,
            task_id,
            status="failed",
            result_ref=None,
            error_ref=error_ref,
        )

    def skip(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
    ) -> TaskDomain:
        if not reason.strip():
            raise TaskStoreError("skipped task requires reason")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status not in {"pending", "running"}:
                raise TaskStoreError(
                    f"only pending or running tasks can be skipped; got {task.status}"
                )
            updated = task.model_copy(
                update={
                    "status": "failed",
                    "error_ref": f"skipped: {reason}",
                    "completed_at": _utcnow(),
                }
            )
            self._save_task(updated)
            return updated

    def retry(
        self,
        session_id: str,
        task_id: str,
        *,
        instruction: str | None = None,
    ) -> TaskDomain:
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "failed":
                raise TaskStoreError(f"only failed tasks can be retried; got {task.status}")
            updated = task.model_copy(
                update=_retry_updates(task, instruction=instruction)
            )
            self._save_task(updated)
            return updated

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

    def _transition_running(
        self,
        session_id: str,
        task_id: str,
        *,
        status: str,
        result_ref: str | None,
        error_ref: str | None,
    ) -> TaskDomain:
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "running":
                raise TaskStoreError(
                    f"only running tasks can transition to {status}; got {task.status}"
                )
            updated = task.model_copy(
                update={
                    "status": status,
                    "result_ref": result_ref,
                    "error_ref": error_ref,
                    "completed_at": _utcnow(),
                }
            )
            self._save_task(updated)
            return updated

    def _require_task(self, session_id: str, task_id: str) -> TaskDomain:
        task = self.get(session_id, task_id)
        if task is None:
            raise TaskStoreError(f"task {task_id!r} not found")
        return task

    def _save_task(self, task: TaskDomain) -> None:
        self._conn.execute(
            """
            UPDATE tasks
            SET status = ?, payload = ?
            WHERE session_id = ? AND task_id = ?
            """,
            (
                task.status,
                task.model_dump_json(),
                task.session_id,
                task.task_id,
            ),
        )


def _task_from_row(row: sqlite3.Row) -> TaskDomain:
    return TaskDomain.model_validate_json(str(row["payload"]))


def _parent_is_done(
    task: TaskDomain,
    *,
    task_by_id: dict[str, TaskDomain],
    session_tasks: list[TaskDomain],
) -> bool:
    if task.parent_id is None:
        return True
    parent = task_by_id.get(task.parent_id)
    if parent is None:
        return False
    return parent.status == "done"


def _utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = ["SqliteTaskBus"]
