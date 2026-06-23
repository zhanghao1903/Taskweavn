"""SQLite-backed runtime configuration change store."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, Self, cast, runtime_checkable

from taskweavn.runtime_config.models import (
    EffectiveRuntimeConfig,
    RuntimeConfigActor,
    RuntimeConfigChange,
    RuntimeConfigChangeStatus,
    RuntimeConfigRejection,
    RuntimeConfigScope,
    RuntimeConfigScopeLevel,
    RuntimeConfigSnapshotRecord,
)


class RuntimeConfigChangeStoreError(RuntimeError):
    """Raised when runtime config change persistence fails."""


@runtime_checkable
class RuntimeConfigChangeStore(Protocol):
    """Durable ledger for runtime config changes and effective snapshots."""

    def append_change(self, change: RuntimeConfigChange) -> RuntimeConfigChange: ...

    def save_snapshot(
        self,
        snapshot: RuntimeConfigSnapshotRecord,
    ) -> RuntimeConfigSnapshotRecord: ...

    def get_change(self, change_id: str) -> RuntimeConfigChange | None: ...

    def get_change_by_idempotency_key(
        self,
        idempotency_key: str,
        scope: RuntimeConfigScope,
    ) -> RuntimeConfigChange | None: ...

    def get_snapshot(self, config_hash: str) -> RuntimeConfigSnapshotRecord | None: ...

    def list_changes(
        self,
        scope: RuntimeConfigScope,
    ) -> tuple[RuntimeConfigChange, ...]: ...


_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS runtime_config_changes (
    change_id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL,
    idempotency_key TEXT,
    scope_level TEXT NOT NULL,
    workspace_id TEXT,
    session_id TEXT,
    task_id TEXT,
    agent_run_id TEXT,
    actor_json TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL,
    requested_values_json TEXT NOT NULL,
    accepted_values_json TEXT NOT NULL,
    rejected_values_json TEXT NOT NULL,
    redacted_keys_json TEXT NOT NULL,
    base_config_hash TEXT NOT NULL,
    resulting_config_hash TEXT,
    effective_status_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runtime_config_changes_scope_created
    ON runtime_config_changes(
        scope_level,
        workspace_id,
        session_id,
        task_id,
        agent_run_id,
        created_at
    );

CREATE UNIQUE INDEX IF NOT EXISTS idx_runtime_config_changes_idempotency_scope
    ON runtime_config_changes(
        idempotency_key,
        scope_level,
        COALESCE(workspace_id, ''),
        COALESCE(session_id, ''),
        COALESCE(task_id, ''),
        COALESCE(agent_run_id, '')
    )
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_runtime_config_changes_resulting_hash
    ON runtime_config_changes(resulting_config_hash);

CREATE TABLE IF NOT EXISTS runtime_config_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    scope_level TEXT NOT NULL,
    workspace_id TEXT,
    session_id TEXT,
    task_id TEXT,
    agent_run_id TEXT,
    effective_config_json TEXT NOT NULL,
    created_by_change_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runtime_config_snapshots_hash
    ON runtime_config_snapshots(config_hash);

CREATE INDEX IF NOT EXISTS idx_runtime_config_snapshots_scope_created
    ON runtime_config_snapshots(
        scope_level,
        workspace_id,
        session_id,
        task_id,
        agent_run_id,
        created_at
    );

CREATE INDEX IF NOT EXISTS idx_runtime_config_snapshots_change
    ON runtime_config_snapshots(created_by_change_id);
"""


class SqliteRuntimeConfigChangeStore:
    """SQLite-backed runtime config control-plane ledger."""

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
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()

    def append_change(self, change: RuntimeConfigChange) -> RuntimeConfigChange:
        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO runtime_config_changes(
                        change_id,
                        patch_id,
                        idempotency_key,
                        scope_level,
                        workspace_id,
                        session_id,
                        task_id,
                        agent_run_id,
                        actor_json,
                        reason,
                        status,
                        requested_values_json,
                        accepted_values_json,
                        rejected_values_json,
                        redacted_keys_json,
                        base_config_hash,
                        resulting_config_hash,
                        effective_status_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _change_row(change),
                )
            except sqlite3.IntegrityError as exc:
                raise RuntimeConfigChangeStoreError(
                    "runtime config change already exists or idempotency key "
                    "was reused in the same scope"
                ) from exc
            except sqlite3.Error as exc:
                raise RuntimeConfigChangeStoreError(
                    f"failed to append runtime config change: {exc}"
                ) from exc
        return change

    def save_snapshot(
        self,
        snapshot: RuntimeConfigSnapshotRecord,
    ) -> RuntimeConfigSnapshotRecord:
        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO runtime_config_snapshots(
                        snapshot_id,
                        config_hash,
                        scope_level,
                        workspace_id,
                        session_id,
                        task_id,
                        agent_run_id,
                        effective_config_json,
                        created_by_change_id,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _snapshot_row(snapshot),
                )
            except sqlite3.IntegrityError as exc:
                raise RuntimeConfigChangeStoreError(
                    "runtime config snapshot already exists"
                ) from exc
            except sqlite3.Error as exc:
                raise RuntimeConfigChangeStoreError(
                    f"failed to save runtime config snapshot: {exc}"
                ) from exc
        return snapshot

    def get_change(self, change_id: str) -> RuntimeConfigChange | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM runtime_config_changes
                WHERE change_id = ?
                """,
                (change_id,),
            ).fetchone()
        return None if row is None else _change_from_row(row)

    def get_change_by_idempotency_key(
        self,
        idempotency_key: str,
        scope: RuntimeConfigScope,
    ) -> RuntimeConfigChange | None:
        with self._lock:
            row = self._conn.execute(
                f"""
                SELECT * FROM runtime_config_changes
                WHERE idempotency_key = ?
                  AND {_scope_where_clause()}
                ORDER BY created_at ASC, change_id ASC
                LIMIT 1
                """,
                (idempotency_key, *_scope_values(scope)),
            ).fetchone()
        return None if row is None else _change_from_row(row)

    def get_snapshot(self, config_hash: str) -> RuntimeConfigSnapshotRecord | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM runtime_config_snapshots
                WHERE config_hash = ?
                ORDER BY created_at DESC, snapshot_id DESC
                LIMIT 1
                """,
                (config_hash,),
            ).fetchone()
        return None if row is None else _snapshot_from_row(row)

    def list_changes(
        self,
        scope: RuntimeConfigScope,
    ) -> tuple[RuntimeConfigChange, ...]:
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM runtime_config_changes
                WHERE {_scope_where_clause()}
                ORDER BY created_at ASC, change_id ASC
                """,
                _scope_values(scope),
            ).fetchall()
        return tuple(_change_from_row(row) for row in rows)

    def close(self) -> None:
        with self._lock, contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _change_row(change: RuntimeConfigChange) -> tuple[Any, ...]:
    scope_values = _scope_values(change.scope)
    return (
        change.change_id,
        change.patch_id,
        change.idempotency_key,
        *scope_values,
        change.actor.model_dump_json(by_alias=True),
        change.reason,
        change.status,
        _json_dumps(change.requested_values),
        _json_dumps(change.accepted_values),
        _json_dumps(
            {
                key: rejection.model_dump(mode="json", by_alias=True)
                for key, rejection in change.rejected_values.items()
            }
        ),
        _json_dumps(change.redacted_keys),
        change.base_config_hash,
        change.resulting_config_hash,
        _json_dumps(change.effective_status_by_key),
        change.created_at.isoformat(),
    )


def _snapshot_row(snapshot: RuntimeConfigSnapshotRecord) -> tuple[Any, ...]:
    scope_values = _scope_values(snapshot.scope)
    return (
        snapshot.snapshot_id,
        snapshot.config_hash,
        *scope_values,
        snapshot.effective_config.model_dump_json(by_alias=True),
        snapshot.created_by_change_id,
        snapshot.created_at.isoformat(),
    )


def _change_from_row(row: sqlite3.Row) -> RuntimeConfigChange:
    rejected_values = {
        key: RuntimeConfigRejection.model_validate(value)
        for key, value in _json_loads(str(row["rejected_values_json"])).items()
    }
    return RuntimeConfigChange(
        change_id=str(row["change_id"]),
        patch_id=str(row["patch_id"]),
        idempotency_key=_nullable_str(row["idempotency_key"]),
        scope=_scope_from_row(row),
        actor=RuntimeConfigActor.model_validate_json(str(row["actor_json"])),
        reason=_nullable_str(row["reason"]),
        status=cast(RuntimeConfigChangeStatus, str(row["status"])),
        requested_values=_json_loads(str(row["requested_values_json"])),
        accepted_values=_json_loads(str(row["accepted_values_json"])),
        rejected_values=rejected_values,
        redacted_keys=tuple(_json_loads(str(row["redacted_keys_json"]))),
        base_config_hash=str(row["base_config_hash"]),
        resulting_config_hash=_nullable_str(row["resulting_config_hash"]),
        effective_status_by_key=_json_loads(str(row["effective_status_json"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _snapshot_from_row(row: sqlite3.Row) -> RuntimeConfigSnapshotRecord:
    return RuntimeConfigSnapshotRecord(
        snapshot_id=str(row["snapshot_id"]),
        config_hash=str(row["config_hash"]),
        scope=_scope_from_row(row),
        effective_config=EffectiveRuntimeConfig.model_validate_json(
            str(row["effective_config_json"])
        ),
        created_by_change_id=_nullable_str(row["created_by_change_id"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _scope_values(scope: RuntimeConfigScope) -> tuple[str | None, ...]:
    return (
        scope.level,
        scope.workspace_id,
        scope.session_id,
        scope.task_id,
        scope.agent_run_id,
    )


def _scope_where_clause() -> str:
    return """
        scope_level IS ?
        AND workspace_id IS ?
        AND session_id IS ?
        AND task_id IS ?
        AND agent_run_id IS ?
    """


def _scope_from_row(row: sqlite3.Row) -> RuntimeConfigScope:
    return RuntimeConfigScope(
        level=cast(RuntimeConfigScopeLevel, str(row["scope_level"])),
        workspace_id=_nullable_str(row["workspace_id"]),
        session_id=_nullable_str(row["session_id"]),
        task_id=_nullable_str(row["task_id"]),
        agent_run_id=_nullable_str(row["agent_run_id"]),
    )


def _nullable_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str) -> Any:
    return json.loads(value)


__all__ = [
    "RuntimeConfigChangeStore",
    "RuntimeConfigChangeStoreError",
    "SqliteRuntimeConfigChangeStore",
]
