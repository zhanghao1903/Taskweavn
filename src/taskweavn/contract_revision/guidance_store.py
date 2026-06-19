"""Stores for typed contract guidance facts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Protocol, runtime_checkable

from taskweavn.contract_revision.models import GuidanceFact
from taskweavn.server.ui_contract.refs import ObjectRef

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS guidance_facts (
    guidance_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    scope_kind TEXT NOT NULL,
    plan_id TEXT,
    task_node_id TEXT,
    guidance_kind TEXT NOT NULL,
    guidance_text TEXT NOT NULL,
    applies_to_future_tasks INTEGER NOT NULL DEFAULT 0,
    source_command_id TEXT NOT NULL,
    source_router_decision_id TEXT,
    source_message_ref_json TEXT,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_guidance_facts_session_scope_created
    ON guidance_facts(session_id, scope_kind, plan_id, task_node_id, created_at);
"""


class GuidanceFactStoreError(RuntimeError):
    """Raised when guidance fact persistence fails."""


@runtime_checkable
class GuidanceFactStore(Protocol):
    def create(self, fact: GuidanceFact) -> GuidanceFact: ...

    def get(self, session_id: str, guidance_id: str) -> GuidanceFact | None: ...

    def list_for_scope(
        self,
        *,
        session_id: str,
        plan_id: str | None = None,
        task_node_id: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[GuidanceFact, ...]: ...


class InMemoryGuidanceFactStore:
    """In-memory guidance store for tests."""

    def __init__(self, facts: Iterable[GuidanceFact] = ()) -> None:
        self._lock = RLock()
        self._facts = {fact.guidance_id: fact for fact in facts}

    def create(self, fact: GuidanceFact) -> GuidanceFact:
        with self._lock:
            current = self._facts.get(fact.guidance_id)
            if current is not None:
                return current
            self._facts[fact.guidance_id] = fact
            return fact

    def get(self, session_id: str, guidance_id: str) -> GuidanceFact | None:
        with self._lock:
            fact = self._facts.get(guidance_id)
        if fact is None or fact.session_id != session_id:
            return None
        return fact

    def list_for_scope(
        self,
        *,
        session_id: str,
        plan_id: str | None = None,
        task_node_id: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[GuidanceFact, ...]:
        with self._lock:
            facts = list(self._facts.values())
        filtered = [
            fact
            for fact in facts
            if fact.session_id == session_id
            and (include_archived or fact.archived_at is None)
            and _scope_matches(fact, plan_id=plan_id, task_node_id=task_node_id)
        ]
        filtered.sort(key=lambda fact: (fact.created_at, fact.guidance_id))
        return tuple(filtered[-limit:])


class SqliteGuidanceFactStore:
    """SQLite-backed guidance fact store."""

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
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()

    def create(self, fact: GuidanceFact) -> GuidanceFact:
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO guidance_facts(
                        guidance_id,
                        workspace_id,
                        session_id,
                        scope_kind,
                        plan_id,
                        task_node_id,
                        guidance_kind,
                        guidance_text,
                        applies_to_future_tasks,
                        source_command_id,
                        source_router_decision_id,
                        source_message_ref_json,
                        version,
                        created_at,
                        archived_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _fact_params(fact),
                )
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise GuidanceFactStoreError("failed to save guidance fact") from exc
            else:
                self._conn.commit()
        current = self.get(fact.session_id, fact.guidance_id)
        if current is None:
            raise GuidanceFactStoreError("guidance fact was not saved")
        return current

    def get(self, session_id: str, guidance_id: str) -> GuidanceFact | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM guidance_facts
                WHERE session_id = ? AND guidance_id = ?
                """,
                (session_id, guidance_id),
            ).fetchone()
        if row is None:
            return None
        return _fact_from_row(row)

    def list_for_scope(
        self,
        *,
        session_id: str,
        plan_id: str | None = None,
        task_node_id: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[GuidanceFact, ...]:
        query = [
            """
            SELECT * FROM guidance_facts
            WHERE session_id = ?
            """,
        ]
        params: list[object] = [session_id]
        if not include_archived:
            query.append("AND archived_at IS NULL")
        if task_node_id is not None:
            query.append("AND (task_node_id = ? OR scope_kind = 'session')")
            params.append(task_node_id)
        elif plan_id is not None:
            query.append("AND (plan_id = ? OR scope_kind = 'session')")
            params.append(plan_id)
        else:
            query.append("AND scope_kind = 'session'")
        query.append("ORDER BY created_at ASC, guidance_id ASC LIMIT ?")
        params.append(limit)
        with self._lock:
            rows = self._conn.execute("\n".join(query), tuple(params)).fetchall()
        return tuple(_fact_from_row(row) for row in rows)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SqliteGuidanceFactStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _scope_matches(
    fact: GuidanceFact,
    *,
    plan_id: str | None,
    task_node_id: str | None,
) -> bool:
    if task_node_id is not None:
        return fact.task_node_id == task_node_id or fact.scope_kind == "session"
    if plan_id is not None:
        return fact.plan_id == plan_id or fact.scope_kind == "session"
    return fact.scope_kind == "session"


def _fact_params(fact: GuidanceFact) -> tuple[object, ...]:
    return (
        fact.guidance_id,
        fact.workspace_id,
        fact.session_id,
        fact.scope_kind,
        fact.plan_id,
        fact.task_node_id,
        fact.guidance_kind,
        fact.guidance_text,
        1 if fact.applies_to_future_tasks else 0,
        fact.source_command_id,
        fact.source_router_decision_id,
        (
            None
            if fact.source_message_ref is None
            else fact.source_message_ref.model_dump_json()
        ),
        fact.version,
        fact.created_at.isoformat(),
        None if fact.archived_at is None else fact.archived_at.isoformat(),
    )


def _fact_from_row(row: sqlite3.Row) -> GuidanceFact:
    try:
        source_ref_json = row["source_message_ref_json"]
        source_ref = (
            None
            if source_ref_json is None
            else ObjectRef.model_validate(json.loads(str(source_ref_json)))
        )
        return GuidanceFact.model_validate(
            {
                "guidance_id": str(row["guidance_id"]),
                "workspace_id": str(row["workspace_id"]),
                "session_id": str(row["session_id"]),
                "scope_kind": str(row["scope_kind"]),
                "plan_id": None if row["plan_id"] is None else str(row["plan_id"]),
                "task_node_id": (
                    None if row["task_node_id"] is None else str(row["task_node_id"])
                ),
                "guidance_kind": str(row["guidance_kind"]),
                "guidance_text": str(row["guidance_text"]),
                "applies_to_future_tasks": bool(row["applies_to_future_tasks"]),
                "source_command_id": str(row["source_command_id"]),
                "source_router_decision_id": (
                    None
                    if row["source_router_decision_id"] is None
                    else str(row["source_router_decision_id"])
                ),
                "source_message_ref": source_ref,
                "version": int(row["version"]),
                "created_at": datetime.fromisoformat(str(row["created_at"])),
                "archived_at": (
                    None
                    if row["archived_at"] is None
                    else datetime.fromisoformat(str(row["archived_at"]))
                ),
            }
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GuidanceFactStoreError("invalid guidance fact row") from exc


__all__ = [
    "GuidanceFactStore",
    "GuidanceFactStoreError",
    "InMemoryGuidanceFactStore",
    "SqliteGuidanceFactStore",
]
