"""SessionManager — workspace.sqlite-backed session registry (Phase 3.1).

One :class:`SessionManager` per workspace. Owns the ``workspace.sqlite``
registry and orchestrates session lifecycle: create / list / get / touch /
mark_status. Path math lives in :class:`WorkspaceLayout`; on-disk session
state (events, thoughts, plan) lives under each session's meta dir and is
created lazily by the consumers — the manager only owns the registry.
"""

from __future__ import annotations

import contextlib
import shutil
import sqlite3
from datetime import UTC, datetime
from typing import Any, get_args

from taskweavn.core.session import (
    Session,
    SessionStatus,
    new_session_id,
)
from taskweavn.core.workspace_layout import WorkspaceLayout

_VALID_STATUSES: frozenset[str] = frozenset(get_args(SessionStatus))

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    last_active_at  TEXT NOT NULL,
    status          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON sessions(last_active_at DESC);
"""


class SessionManagerError(RuntimeError):
    """Raised on misuse — unknown id, invalid status, etc."""


class SessionManager:
    """CRUD layer over the workspace's session registry."""

    def __init__(self, layout: WorkspaceLayout) -> None:
        self.layout = layout
        layout.bootstrap()
        self._conn = sqlite3.connect(
            str(layout.registry_db_path),
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.executescript(_SCHEMA_DDL)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create(self, name: str) -> Session:
        """Allocate a new session with a fresh id and on-disk skeleton."""
        if not name.strip():
            raise SessionManagerError("session name must not be empty")
        now = _utcnow()
        session = Session(
            id=new_session_id(),
            name=name,
            workspace_root=self.layout.root,
            created_at=now,
            last_active_at=now,
            status="active",
        )
        self._conn.execute(
            "INSERT INTO sessions(id, name, created_at, last_active_at, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session.id,
                session.name,
                session.created_at.isoformat(),
                session.last_active_at.isoformat(),
                session.status,
            ),
        )
        self.layout.bootstrap_session(session.id)
        return session

    def get(self, session_id: str) -> Session | None:
        cursor = self._conn.execute(
            "SELECT id, name, created_at, last_active_at, status "
            "FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        return self._row_to_session(row) if row is not None else None

    def require(self, session_id: str) -> Session:
        """Like :meth:`get` but raises if missing — handy for CLI commands."""
        session = self.get(session_id)
        if session is None:
            raise SessionManagerError(f"no such session: {session_id!r}")
        return session

    def list(self) -> list[Session]:
        """All sessions, most-recently-active first."""
        cursor = self._conn.execute(
            "SELECT id, name, created_at, last_active_at, status "
            "FROM sessions ORDER BY last_active_at DESC"
        )
        return [self._row_to_session(row) for row in cursor.fetchall()]

    def touch(self, session_id: str) -> Session:
        """Bump ``last_active_at`` to now and return the refreshed session."""
        now = _utcnow()
        result = self._conn.execute(
            "UPDATE sessions SET last_active_at = ? WHERE id = ?",
            (now.isoformat(), session_id),
        )
        if result.rowcount == 0:
            raise SessionManagerError(f"no such session: {session_id!r}")
        return self.require(session_id)

    def rename(self, session_id: str, name: str) -> Session:
        """Rename a session and bump its activity timestamp."""
        if not name.strip():
            raise SessionManagerError("session name must not be empty")
        now = _utcnow()
        result = self._conn.execute(
            "UPDATE sessions SET name = ?, last_active_at = ? WHERE id = ?",
            (name.strip(), now.isoformat(), session_id),
        )
        if result.rowcount == 0:
            raise SessionManagerError(f"no such session: {session_id!r}")
        return self.require(session_id)

    def delete(self, session_id: str) -> Session | None:
        """Delete a session registry row and archive its on-disk directory.

        The local 1.0 UI exposes this as "delete", but we archive files under
        ``.plato/deleted-sessions`` instead of physically removing the
        project directory. That keeps user work recoverable while making the
        session disappear from normal lists.
        """
        self.require(session_id)
        self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._archive_session_dir(session_id)
        remaining = self.list()
        return remaining[0] if remaining else None

    def mark_status(self, session_id: str, status: SessionStatus) -> Session:
        """Transition a session's lifecycle status."""
        if status not in _VALID_STATUSES:
            raise SessionManagerError(f"invalid status: {status!r}")
        now = _utcnow()
        result = self._conn.execute(
            "UPDATE sessions SET status = ?, last_active_at = ? WHERE id = ?",
            (status, now.isoformat(), session_id),
        )
        if result.rowcount == 0:
            raise SessionManagerError(f"no such session: {session_id!r}")
        return self.require(session_id)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        with contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SessionManager:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _row_to_session(self, row: tuple[str, str, str, str, str]) -> Session:
        sid, name, created_at, last_active_at, status = row
        return Session(
            id=sid,
            name=name,
            workspace_root=self.layout.root,
            created_at=datetime.fromisoformat(created_at),
            last_active_at=datetime.fromisoformat(last_active_at),
            status=_parse_status(status),
        )

    def _archive_session_dir(self, session_id: str) -> None:
        source = self.layout.session_dir(session_id)
        if not source.exists():
            return
        archive_root = self.layout.meta_dir / "deleted-sessions"
        archive_root.mkdir(parents=True, exist_ok=True)
        destination = archive_root / f"{session_id}-{_utcnow().strftime('%Y%m%d%H%M%S%f')}"
        shutil.move(str(source), str(destination))


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_status(raw: str) -> SessionStatus:
    if raw not in _VALID_STATUSES:
        raise SessionManagerError(f"db contains invalid status: {raw!r}")
    return raw  # type: ignore[return-value]


__all__ = [
    "SessionManager",
    "SessionManagerError",
]
