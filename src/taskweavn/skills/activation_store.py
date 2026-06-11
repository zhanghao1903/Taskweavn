"""Durable skill activation store."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, runtime_checkable

from taskweavn.skills.models import SkillActivation, SkillActivationStatus

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS skill_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activation_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    task_id TEXT,
    agent_run_id TEXT,
    skill_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    scope TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skill_activations_session
    ON skill_activations(session_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_skill_activations_task
    ON skill_activations(session_id, task_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_skill_activations_run
    ON skill_activations(agent_run_id, status);
"""


@runtime_checkable
class SkillActivationStore(Protocol):
    def save(self, activation: SkillActivation) -> SkillActivation: ...

    def get(self, activation_id: str) -> SkillActivation | None: ...

    def list_for_context(
        self,
        *,
        session_id: str,
        task_id: str | None = None,
        agent_run_id: str | None = None,
        statuses: tuple[SkillActivationStatus, ...] = ("active",),
    ) -> tuple[SkillActivation, ...]: ...


class InMemorySkillActivationStore:
    """Process-local activation store for tests and simple runtime assembly."""

    def __init__(self) -> None:
        self._activations: dict[str, SkillActivation] = {}

    def save(self, activation: SkillActivation) -> SkillActivation:
        self._activations[activation.activation_id] = activation
        return activation

    def get(self, activation_id: str) -> SkillActivation | None:
        return self._activations.get(activation_id)

    def list_for_context(
        self,
        *,
        session_id: str,
        task_id: str | None = None,
        agent_run_id: str | None = None,
        statuses: tuple[SkillActivationStatus, ...] = ("active",),
    ) -> tuple[SkillActivation, ...]:
        status_set = set(statuses)
        values = [
            activation
            for activation in self._activations.values()
            if activation.session_id == session_id and activation.status in status_set
        ]
        if task_id is not None:
            values = [
                activation
                for activation in values
                if activation.task_id is None or activation.task_id == task_id
            ]
        if agent_run_id is not None:
            values = [
                activation
                for activation in values
                if activation.agent_run_id is None or activation.agent_run_id == agent_run_id
            ]
        return tuple(sorted(values, key=lambda item: (item.updated_at, item.activation_id)))


class SqliteSkillActivationStore:
    """SQLite-backed activation store for workspace/session skill governance."""

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

    def save(self, activation: SkillActivation) -> SkillActivation:
        payload = activation.model_dump_json()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO skill_activations(
                    activation_id,
                    session_id,
                    task_id,
                    agent_run_id,
                    skill_id,
                    content_hash,
                    status,
                    scope,
                    created_at,
                    updated_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(activation_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    task_id = excluded.task_id,
                    agent_run_id = excluded.agent_run_id,
                    skill_id = excluded.skill_id,
                    content_hash = excluded.content_hash,
                    status = excluded.status,
                    scope = excluded.scope,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (
                    activation.activation_id,
                    activation.session_id,
                    activation.task_id,
                    activation.agent_run_id,
                    activation.skill_id,
                    activation.content_hash,
                    activation.status,
                    activation.scope,
                    activation.created_at.isoformat(),
                    activation.updated_at.isoformat(),
                    payload,
                ),
            )
        return activation

    def get(self, activation_id: str) -> SkillActivation | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM skill_activations WHERE activation_id = ?",
                (activation_id,),
            ).fetchone()
        if row is None:
            return None
        return _activation_from_row(row)

    def list_for_context(
        self,
        *,
        session_id: str,
        task_id: str | None = None,
        agent_run_id: str | None = None,
        statuses: tuple[SkillActivationStatus, ...] = ("active",),
    ) -> tuple[SkillActivation, ...]:
        if not statuses:
            return ()
        placeholders = ", ".join("?" for _ in statuses)
        sql = f"""
            SELECT payload FROM skill_activations
            WHERE session_id = ?
              AND status IN ({placeholders})
        """
        params: list[Any] = [session_id, *statuses]
        if task_id is not None:
            sql += " AND (task_id IS NULL OR task_id = ?)"
            params.append(task_id)
        if agent_run_id is not None:
            sql += " AND (agent_run_id IS NULL OR agent_run_id = ?)"
            params.append(agent_run_id)
        sql += " ORDER BY updated_at ASC, activation_id ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return tuple(_activation_from_row(row) for row in rows)

    def close(self) -> None:
        with self._lock, contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SqliteSkillActivationStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _activation_from_row(row: sqlite3.Row) -> SkillActivation:
    return SkillActivation.model_validate_json(str(row["payload"]))
