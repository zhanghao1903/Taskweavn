"""SQLite-backed publish control-plane stores."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from pydantic import ValidationError

from taskweavn.task.bus import TaskBus
from taskweavn.task.pipeline import PipelineTaskLoader
from taskweavn.task.publisher import (
    DefaultTaskPublisher,
    PublisherKind,
    PublisherRef,
    PublishResult,
)
from taskweavn.task.publisher_service import (
    PublishAuditEvent,
    PublishIdempotencyConflictError,
    PublishIdempotencyRecord,
    TaskPublishService,
)
from taskweavn.task.scheduler import ScheduledPublishConfig, ScheduledPublishState
from taskweavn.task.stores import TaskStoreError

_SCHEMA_VERSION = "1"

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS publish_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publish_idempotency_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    publisher_kind TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    publish_result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, publisher_kind, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_publish_idempotency_session_created
    ON publish_idempotency_records(session_id, created_at, id);

CREATE TABLE IF NOT EXISTS publish_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    request_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    publisher_kind TEXT NOT NULL,
    actor_id TEXT,
    idempotency_key TEXT,
    root_task_ids_json TEXT NOT NULL,
    published_task_ids_json TEXT NOT NULL,
    reason TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_publish_audit_session_created
    ON publish_audit_events(session_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_publish_audit_request
    ON publish_audit_events(request_id, id);

CREATE INDEX IF NOT EXISTS idx_publish_audit_idempotency
    ON publish_audit_events(session_id, publisher_kind, idempotency_key, id);

CREATE TABLE IF NOT EXISTS scheduled_publish_configs (
    schedule_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scheduled_configs_enabled
    ON scheduled_publish_configs(enabled, updated_at, schedule_id);

CREATE TABLE IF NOT EXISTS scheduled_publish_states (
    schedule_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL,
    last_run_at TEXT,
    next_run_at TEXT,
    last_result_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(schedule_id) REFERENCES scheduled_publish_configs(schedule_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scheduled_states_due
    ON scheduled_publish_states(enabled, next_run_at, updated_at, schedule_id);
"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PublishStoreError(TaskStoreError):
    """Raised for durable publish control-plane store failures."""


class _SqlitePublishStore:
    """Shared SQLite connection and schema initialization for publish stores."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_DDL)
        self._conn.execute(
            """
            INSERT INTO publish_schema_meta(key, value, updated_at)
            VALUES('schema_version', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (_SCHEMA_VERSION, _utcnow().isoformat()),
        )

    @contextmanager
    def _write_transaction(self) -> Iterator[None]:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            yield
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class SqlitePublishIdempotencyStore(_SqlitePublishStore):
    """SQLite-backed publish idempotency store."""

    def get(
        self,
        session_id: str,
        publisher_kind: PublisherKind,
        idempotency_key: str,
    ) -> PublishIdempotencyRecord | None:
        row = self._conn.execute(
            """
            SELECT
                session_id,
                publisher_kind,
                idempotency_key,
                request_hash,
                publish_result_json,
                created_at
            FROM publish_idempotency_records
            WHERE session_id = ?
              AND publisher_kind = ?
              AND idempotency_key = ?
            """,
            (session_id, publisher_kind, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return _idempotency_from_row(row)

    def put(self, record: PublishIdempotencyRecord) -> PublishIdempotencyRecord:
        try:
            with self._write_transaction():
                self._conn.execute(
                    """
                    INSERT INTO publish_idempotency_records(
                        session_id,
                        publisher_kind,
                        idempotency_key,
                        request_hash,
                        publish_result_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.session_id,
                        record.publisher_kind,
                        record.idempotency_key,
                        record.request_hash,
                        record.publish_result.model_dump_json(),
                        record.created_at.isoformat(),
                    ),
                )
            return record
        except sqlite3.IntegrityError:
            current = self.get(
                record.session_id,
                record.publisher_kind,
                record.idempotency_key,
            )
            if current is None:
                raise PublishStoreError(
                    "idempotency insert failed but no existing record could be loaded"
                ) from None
            if current.request_hash != record.request_hash:
                raise PublishIdempotencyConflictError(
                    "idempotency key was already used with a different request"
                ) from None
            return current
        except sqlite3.Error as exc:
            raise PublishStoreError("failed to store publish idempotency record") from exc


class SqliteTaskPublishAuditSink(_SqlitePublishStore):
    """SQLite-backed append-only publish audit sink."""

    def record(self, event: PublishAuditEvent) -> None:
        try:
            self._conn.execute(
                """
                INSERT INTO publish_audit_events(
                    event_id,
                    kind,
                    request_id,
                    session_id,
                    publisher_kind,
                    actor_id,
                    idempotency_key,
                    root_task_ids_json,
                    published_task_ids_json,
                    reason,
                    metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.kind,
                    event.request_id,
                    event.session_id,
                    event.publisher_kind,
                    event.actor_id,
                    event.idempotency_key,
                    _json_dumps(list(event.root_task_ids)),
                    _json_dumps(list(event.published_task_ids)),
                    event.reason,
                    _json_dumps(event.metadata),
                    event.created_at.isoformat(),
                ),
            )
        except sqlite3.Error as exc:
            raise PublishStoreError("failed to record publish audit event") from exc

    def list_for_session(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> tuple[PublishAuditEvent, ...]:
        if limit is not None and limit <= 0:
            return ()
        sql = """
            SELECT *
            FROM publish_audit_events
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
        """
        params: tuple[Any, ...] = (session_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (session_id, limit)
        rows = self._conn.execute(sql, params).fetchall()
        return tuple(_audit_from_row(row) for row in rows)

    def list_for_request(self, request_id: str) -> tuple[PublishAuditEvent, ...]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM publish_audit_events
            WHERE request_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (request_id,),
        ).fetchall()
        return tuple(_audit_from_row(row) for row in rows)

    def list_for_idempotency(
        self,
        session_id: str,
        publisher_kind: PublisherKind,
        idempotency_key: str,
    ) -> tuple[PublishAuditEvent, ...]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM publish_audit_events
            WHERE session_id = ?
              AND publisher_kind = ?
              AND idempotency_key = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id, publisher_kind, idempotency_key),
        ).fetchall()
        return tuple(_audit_from_row(row) for row in rows)


class SqliteScheduledPublishStore(_SqlitePublishStore):
    """SQLite-backed scheduled publish config and state store."""

    def upsert_config(self, config: ScheduledPublishConfig) -> ScheduledPublishConfig:
        now = _utcnow().isoformat()
        try:
            with self._write_transaction():
                self._conn.execute(
                    """
                    INSERT INTO scheduled_publish_configs(
                        schedule_id,
                        enabled,
                        config_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(schedule_id) DO UPDATE SET
                        enabled = excluded.enabled,
                        config_json = excluded.config_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        config.schedule_id,
                        _bool_to_int(config.enabled),
                        config.model_dump_json(by_alias=True),
                        now,
                        now,
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO scheduled_publish_states(
                        schedule_id,
                        enabled,
                        updated_at
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(schedule_id) DO UPDATE SET
                        enabled = excluded.enabled,
                        updated_at = excluded.updated_at
                    """,
                    (config.schedule_id, _bool_to_int(config.enabled), now),
                )
        except sqlite3.Error as exc:
            raise PublishStoreError("failed to upsert scheduled publish config") from exc
        return config

    def get_config(self, schedule_id: str) -> ScheduledPublishConfig | None:
        row = self._conn.execute(
            """
            SELECT schedule_id, config_json
            FROM scheduled_publish_configs
            WHERE schedule_id = ?
            """,
            (schedule_id,),
        ).fetchone()
        if row is None:
            return None
        return _scheduled_config_from_row(row)

    def list_configs(self) -> tuple[ScheduledPublishConfig, ...]:
        rows = self._conn.execute(
            """
            SELECT schedule_id, config_json
            FROM scheduled_publish_configs
            ORDER BY schedule_id ASC
            """
        ).fetchall()
        return tuple(_scheduled_config_from_row(row) for row in rows)

    def set_enabled(self, schedule_id: str, enabled: bool) -> ScheduledPublishConfig:
        config = self.get_config(schedule_id)
        if config is None:
            raise LookupError(f"ScheduledPublishConfig {schedule_id!r} not found")
        updated = config.model_copy(update={"enabled": enabled})
        now = _utcnow().isoformat()
        try:
            with self._write_transaction():
                self._conn.execute(
                    """
                    UPDATE scheduled_publish_configs
                    SET enabled = ?,
                        config_json = ?,
                        updated_at = ?
                    WHERE schedule_id = ?
                    """,
                    (
                        _bool_to_int(updated.enabled),
                        updated.model_dump_json(by_alias=True),
                        now,
                        schedule_id,
                    ),
                )
                self._conn.execute(
                    """
                    INSERT INTO scheduled_publish_states(
                        schedule_id,
                        enabled,
                        updated_at
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(schedule_id) DO UPDATE SET
                        enabled = excluded.enabled,
                        updated_at = excluded.updated_at
                    """,
                    (schedule_id, _bool_to_int(enabled), now),
                )
        except sqlite3.Error as exc:
            raise PublishStoreError("failed to set scheduled publish enabled state") from exc
        return updated

    def get_state(self, schedule_id: str) -> ScheduledPublishState | None:
        row = self._conn.execute(
            """
            SELECT
                schedule_id,
                enabled,
                last_run_at,
                next_run_at,
                last_result_json,
                updated_at
            FROM scheduled_publish_states
            WHERE schedule_id = ?
            """,
            (schedule_id,),
        ).fetchone()
        if row is None:
            return None
        return _scheduled_state_from_row(row)

    def save_state(self, state: ScheduledPublishState) -> ScheduledPublishState:
        if self.get_config(state.schedule_id) is None:
            raise LookupError(f"ScheduledPublishConfig {state.schedule_id!r} not found")
        updated = state.model_copy(update={"updated_at": _utcnow()})
        try:
            with self._write_transaction():
                self._conn.execute(
                    """
                    INSERT INTO scheduled_publish_states(
                        schedule_id,
                        enabled,
                        last_run_at,
                        next_run_at,
                        last_result_json,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(schedule_id) DO UPDATE SET
                        enabled = excluded.enabled,
                        last_run_at = excluded.last_run_at,
                        next_run_at = excluded.next_run_at,
                        last_result_json = excluded.last_result_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        updated.schedule_id,
                        _bool_to_int(updated.enabled),
                        _datetime_to_iso(updated.last_run_at),
                        _datetime_to_iso(updated.next_run_at),
                        _publish_result_json_or_none(updated.last_result),
                        updated.updated_at.isoformat(),
                    ),
                )
        except sqlite3.Error as exc:
            raise PublishStoreError("failed to save scheduled publish state") from exc
        return updated


def build_sqlite_publish_service(
    *,
    task_bus: TaskBus,
    publish_db_path: str | Path,
    publisher: PublisherRef | None = None,
    pipeline_loader: PipelineTaskLoader | None = None,
) -> TaskPublishService:
    """Build a TaskPublishService wired to SQLite publish control-plane stores."""

    return TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=task_bus, publisher=publisher),
        idempotency_store=SqlitePublishIdempotencyStore(publish_db_path),
        audit_sink=SqliteTaskPublishAuditSink(publish_db_path),
        pipeline_loader=pipeline_loader,
    )


def _idempotency_from_row(row: sqlite3.Row) -> PublishIdempotencyRecord:
    try:
        return PublishIdempotencyRecord.model_validate(
            {
                "session_id": str(row["session_id"]),
                "publisher_kind": str(row["publisher_kind"]),
                "idempotency_key": str(row["idempotency_key"]),
                "request_hash": str(row["request_hash"]),
                "publish_result": PublishResult.model_validate_json(
                    str(row["publish_result_json"])
                ),
                "created_at": str(row["created_at"]),
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise PublishStoreError(
            "invalid publish idempotency record "
            f"{row['session_id']!r}/{row['publisher_kind']!r}/{row['idempotency_key']!r}"
        ) from exc


def _audit_from_row(row: sqlite3.Row) -> PublishAuditEvent:
    try:
        root_task_ids = _str_tuple_from_json(str(row["root_task_ids_json"]))
        published_task_ids = _str_tuple_from_json(str(row["published_task_ids_json"]))
        metadata = json.loads(str(row["metadata_json"]))
        if not isinstance(metadata, dict):
            raise TypeError("metadata_json must decode to an object")
        return PublishAuditEvent.model_validate(
            {
                "event_id": str(row["event_id"]),
                "kind": str(row["kind"]),
                "request_id": str(row["request_id"]),
                "session_id": str(row["session_id"]),
                "publisher_kind": str(row["publisher_kind"]),
                "actor_id": row["actor_id"],
                "idempotency_key": row["idempotency_key"],
                "root_task_ids": root_task_ids,
                "published_task_ids": published_task_ids,
                "reason": row["reason"],
                "metadata": metadata,
                "created_at": str(row["created_at"]),
            }
        )
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        raise PublishStoreError(f"invalid publish audit event {row['event_id']!r}") from exc


def _scheduled_config_from_row(row: sqlite3.Row) -> ScheduledPublishConfig:
    try:
        return ScheduledPublishConfig.model_validate_json(str(row["config_json"]))
    except (TypeError, ValueError, ValidationError) as exc:
        raise PublishStoreError(
            f"invalid scheduled publish config {row['schedule_id']!r}"
        ) from exc


def _scheduled_state_from_row(row: sqlite3.Row) -> ScheduledPublishState:
    try:
        last_result_raw = row["last_result_json"]
        last_result = None
        if last_result_raw is not None:
            last_result = PublishResult.model_validate_json(str(last_result_raw))
        return ScheduledPublishState.model_validate(
            {
                "schedule_id": str(row["schedule_id"]),
                "enabled": bool(row["enabled"]),
                "last_run_at": row["last_run_at"],
                "next_run_at": row["next_run_at"],
                "last_result": last_result,
                "updated_at": str(row["updated_at"]),
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise PublishStoreError(
            f"invalid scheduled publish state {row['schedule_id']!r}"
        ) from exc


def _str_tuple_from_json(raw: str) -> tuple[str, ...]:
    decoded = json.loads(raw)
    if not isinstance(decoded, list):
        raise TypeError("expected JSON array")
    return tuple(str(value) for value in decoded)


def _json_dumps(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _bool_to_int(value: bool) -> int:
    return 1 if value else 0


def _datetime_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _publish_result_json_or_none(value: PublishResult | None) -> str | None:
    if value is None:
        return None
    return value.model_dump_json()


__all__ = [
    "PublishStoreError",
    "SqlitePublishIdempotencyStore",
    "SqliteScheduledPublishStore",
    "SqliteTaskPublishAuditSink",
    "build_sqlite_publish_service",
]
