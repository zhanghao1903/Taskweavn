"""SQLite-backed :class:`MessageStream` (Phase 3.3).

Single workspace-level ``messages.sqlite`` holds every message across every
session in this workspace. Rows are keyed by ``message_id`` (globally unique
per design Q7) and aggregable along four axes:

* ``session_id × created_at`` — main UI timeline
* ``session_id × task_id × created_at`` — single-run replay / resume
* ``task_id × created_at`` — cross-session view of one task (Phase 4)
* ``session_id × agent_id × created_at`` / ``agent_id × created_at`` —
  audit one agent's output (Phase 4 multi-agent)

Plus:

* ``parent_message_id`` for ``response_for`` / ``thread`` / pending lookup
* ``message_id`` UNIQUE for direct ``get``

Each index has ``id`` as its trailing column so ``ORDER BY created_at, id``
walks the index in physical order — no extra sort.

This module owns reads (``MessageStream`` Protocol). The writer
(:class:`MessageBus` in 3.4) delegates persistence to :meth:`_insert` here
so all write paths converge on the same constraint logic.
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

from code_agent.interaction.message import AgentMessage, MessageStreamError

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id            TEXT    NOT NULL UNIQUE,
    session_id            TEXT    NOT NULL,
    task_id               TEXT,
    agent_id              TEXT    NOT NULL,
    parent_message_id     TEXT,
    message_type          TEXT    NOT NULL
        CHECK(message_type IN ('informational','actionable','response')),
    content               TEXT    NOT NULL,
    context_json          TEXT    NOT NULL DEFAULT '{}',
    action_options_json   TEXT    NOT NULL DEFAULT '[]',
    requires_response     INTEGER NOT NULL DEFAULT 0,
    timeout_seconds       REAL,
    risk_json             TEXT,
    related_action_id     TEXT,
    response_source       TEXT,
    response_value        TEXT,
    created_at            TEXT    NOT NULL
);

-- Aggregation indexes; trailing 'id' makes (created_at, id) the unique
-- monotonic order even when many messages share a millisecond.
CREATE INDEX IF NOT EXISTS idx_messages_session_created
    ON messages(session_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_session_task_created
    ON messages(session_id, task_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_task_created
    ON messages(task_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_session_agent_created
    ON messages(session_id, agent_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_agent_created
    ON messages(agent_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_session_type_created
    ON messages(session_id, message_type, created_at, id);
CREATE INDEX IF NOT EXISTS idx_messages_parent
    ON messages(parent_message_id);
"""


# Columns selected by every read path; SELECT * is fragile if we ever ALTER.
_COLUMNS = (
    "message_id",
    "session_id",
    "task_id",
    "agent_id",
    "parent_message_id",
    "message_type",
    "content",
    "context_json",
    "action_options_json",
    "requires_response",
    "timeout_seconds",
    "risk_json",
    "related_action_id",
    "response_source",
    "response_value",
    "created_at",
)
_SELECT = f"SELECT {', '.join(_COLUMNS)} FROM messages"


class SqliteMessageStream:
    """SQLite-backed message store. Read interface is :class:`MessageStream`;
    writes happen via :meth:`_insert`, called by the bus (Phase 3.4)."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path), isolation_level=None, check_same_thread=False
        )
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA_DDL)
        # Serialize INSERTs against the bus's own threading.Condition (3.4).
        # The lock here protects only writes from this process — multi-process
        # writers are out of scope until Phase 4.
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Write path (called by MessageBus in 3.4)
    # ------------------------------------------------------------------

    def _insert(self, message: AgentMessage) -> None:
        """Persist a single message. Validates parent existence and uniqueness.

        Raises :class:`MessageStreamError` on integrity violations so the bus
        can surface them as ``DuplicateResponseError`` / ``UnknownParent``.
        Direct callers other than the bus should be exceedingly rare.
        """
        # Pre-flight checks within the same lock as the INSERT so a concurrent
        # writer can't slip a row in between the check and the write.
        with self._lock:
            self._validate_for_insert(message)
            payload = _to_row(message)
            try:
                self._conn.execute(
                    f"INSERT INTO messages({', '.join(_COLUMNS)}) "
                    f"VALUES ({', '.join('?' * len(_COLUMNS))})",
                    payload,
                )
            except sqlite3.IntegrityError as exc:
                # UNIQUE(message_id) — caller tried to publish the same id twice.
                raise MessageStreamError(
                    f"message_id {message.message_id!r} already exists"
                ) from exc

    def _validate_for_insert(self, message: AgentMessage) -> None:
        if message.message_type == "response":
            if message.parent_message_id is None:
                raise MessageStreamError(
                    "response message must set parent_message_id"
                )
            cur = self._conn.execute(
                "SELECT message_type FROM messages WHERE message_id = ?",
                (message.parent_message_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise MessageStreamError(
                    f"parent_message_id {message.parent_message_id!r} not found"
                )
            if row[0] != "actionable":
                raise MessageStreamError(
                    f"response parent must be 'actionable', "
                    f"got {row[0]!r} for {message.parent_message_id!r}"
                )

    # ------------------------------------------------------------------
    # MessageStream Protocol — direct lookup
    # ------------------------------------------------------------------

    def get(self, message_id: str) -> AgentMessage | None:
        cur = self._conn.execute(
            f"{_SELECT} WHERE message_id = ?", (message_id,)
        )
        row = cur.fetchone()
        return None if row is None else _from_row(row)

    def __len__(self) -> int:
        (count,) = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        return int(count)

    # ------------------------------------------------------------------
    # MessageStream Protocol — aggregation queries
    # ------------------------------------------------------------------

    def list_for_session(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        return self._list(
            base_clauses=["session_id = ?"],
            base_params=[session_id],
            types=types,
            since=since,
            limit=limit,
        )

    def list_for_task(
        self,
        task_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        return self._list(
            base_clauses=["task_id = ?"],
            base_params=[task_id],
            types=types,
            since=since,
            limit=limit,
        )

    def list_for_agent(
        self,
        agent_id: str,
        *,
        session_id: str | None = None,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        clauses = ["agent_id = ?"]
        params: list[Any] = [agent_id]
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        return self._list(
            base_clauses=clauses,
            base_params=params,
            types=types,
            since=since,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # MessageStream Protocol — relationship queries
    # ------------------------------------------------------------------

    def pending_actionable(
        self, session_id: str, *, task_id: str | None = None
    ) -> list[AgentMessage]:
        """Actionable messages that have not yet received a ``response``.

        Plan: filter ``messages`` to actionable rows in this session (and
        optionally task), then anti-join against rows whose
        ``parent_message_id`` matches. The anti-join uses the
        ``idx_messages_parent`` index, so cost is roughly the number of open
        actionables — fine even on a long session log.
        """
        prefixed = ", ".join(f"m.{c}" for c in _COLUMNS)
        sql = (
            f"SELECT {prefixed} FROM messages AS m "
            "WHERE m.session_id = ? "
            "AND m.message_type = 'actionable' "
            "AND NOT EXISTS ("
            "    SELECT 1 FROM messages r "
            "    WHERE r.parent_message_id = m.message_id "
            "      AND r.message_type = 'response'"
            ")"
        )
        params: list[Any] = [session_id]
        if task_id is not None:
            sql += " AND m.task_id = ?"
            params.append(task_id)
        sql += " ORDER BY m.created_at, m.id"
        cur = self._conn.execute(sql, params)
        return [_from_row(r) for r in cur]

    def response_for(self, message_id: str) -> AgentMessage | None:
        # Earliest response wins; later "responses" are kept on the table for
        # the audit trail (e.g. user retracts) but the canonical answer is the
        # first one.
        cur = self._conn.execute(
            f"{_SELECT} WHERE parent_message_id = ? AND message_type = 'response' "
            "ORDER BY created_at, id LIMIT 1",
            (message_id,),
        )
        row = cur.fetchone()
        return None if row is None else _from_row(row)

    def thread(self, message_id: str) -> list[AgentMessage]:
        # Anchor + every reply, in chronological order. The anchor itself
        # might be any type (we don't restrict to actionable here — useful
        # for inspecting an informational that someone replied to).
        cur = self._conn.execute(
            f"{_SELECT} WHERE message_id = ? OR parent_message_id = ? "
            "ORDER BY created_at, id",
            (message_id, message_id),
        )
        return [_from_row(r) for r in cur]

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        with contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SqliteMessageStream:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _list(
        self,
        *,
        base_clauses: list[str],
        base_params: list[Any],
        types: Iterable[str] | None,
        since: datetime | None,
        limit: int | None,
    ) -> Iterator[AgentMessage]:
        clauses = list(base_clauses)
        params = list(base_params)
        if types is not None:
            type_list = list(types)
            if type_list:
                placeholders = ",".join("?" for _ in type_list)
                clauses.append(f"message_type IN ({placeholders})")
                params.extend(type_list)
        if since is not None:
            clauses.append("created_at > ?")
            params.append(since.isoformat())
        sql = _SELECT
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at, id"
        if limit is not None:
            if limit < 0:
                raise ValueError(f"limit must be non-negative; got {limit}")
            sql += " LIMIT ?"
            params.append(limit)
        cur = self._conn.execute(sql, params)
        for row in cur:
            yield _from_row(row)


# ---------------------------------------------------------------------------
# Row codec
# ---------------------------------------------------------------------------


def _to_row(message: AgentMessage) -> tuple[Any, ...]:
    risk = message.risk_assessment
    return (
        message.message_id,
        message.session_id,
        message.task_id,
        message.agent_id,
        message.parent_message_id,
        message.message_type,
        message.content,
        json.dumps(message.context, ensure_ascii=False, sort_keys=True),
        json.dumps(message.action_options, ensure_ascii=False, sort_keys=True),
        1 if message.requires_response else 0,
        message.timeout_seconds,
        None if risk is None else json.dumps(risk.to_dict(), sort_keys=True),
        message.related_action_id,
        message.response_source,
        message.response_value,
        message.created_at.isoformat(),
    )


def _from_row(row: tuple[Any, ...]) -> AgentMessage:
    (
        message_id,
        session_id,
        task_id,
        agent_id,
        parent_message_id,
        message_type,
        content,
        context_json,
        action_options_json,
        requires_response,
        timeout_seconds,
        risk_json,
        related_action_id,
        response_source,
        response_value,
        created_at,
    ) = row
    return AgentMessage(
        message_id=message_id,
        session_id=session_id,
        task_id=task_id,
        agent_id=agent_id,
        parent_message_id=parent_message_id,
        message_type=message_type,
        content=content,
        context=json.loads(context_json),
        action_options=json.loads(action_options_json),
        requires_response=bool(requires_response),
        timeout_seconds=timeout_seconds,
        risk_assessment=(None if risk_json is None else json.loads(risk_json)),
        related_action_id=related_action_id,
        response_source=response_source,
        response_value=response_value,
        created_at=datetime.fromisoformat(created_at),
    )
