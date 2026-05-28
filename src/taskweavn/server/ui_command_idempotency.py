"""Idempotency store for UI command HTTP responses."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, cast, runtime_checkable

from taskweavn.server.transport import HttpApiResponse

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS ui_command_response_idempotency_records (
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    headers_json TEXT NOT NULL,
    body_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ui_command_response_idempotency_session_created
    ON ui_command_response_idempotency_records(session_id, created_at, idempotency_key);
"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class UiCommandResponseIdempotencyRecord:
    """Completed HTTP command response cached for idempotent replay."""

    session_id: str
    idempotency_key: str
    request_hash: str
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any]
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def key(self) -> tuple[str, str]:
        return (self.session_id, self.idempotency_key)

    @classmethod
    def from_response(
        cls,
        *,
        session_id: str,
        idempotency_key: str,
        request_hash: str,
        response: HttpApiResponse,
    ) -> UiCommandResponseIdempotencyRecord:
        body = response.body
        if not isinstance(body, dict):
            raise TypeError("idempotent command response body must be a JSON object")
        return cls(
            session_id=session_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status_code=response.status_code,
            headers=dict(response.headers),
            body=cast(dict[str, Any], dict(body)),
        )

    def to_response(self) -> HttpApiResponse:
        return HttpApiResponse(
            status_code=self.status_code,
            headers=dict(self.headers),
            body=dict(self.body),
        )


@runtime_checkable
class UiCommandResponseIdempotencyStore(Protocol):
    """Caches completed UI command responses by session and idempotency key."""

    def get(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> UiCommandResponseIdempotencyRecord | None: ...

    def put(
        self,
        record: UiCommandResponseIdempotencyRecord,
    ) -> UiCommandResponseIdempotencyRecord: ...


class InMemoryUiCommandResponseIdempotencyStore:
    """In-memory command response idempotency cache for tests."""

    def __init__(
        self,
        records: Iterable[UiCommandResponseIdempotencyRecord] = (),
    ) -> None:
        self._lock = RLock()
        self._records = {record.key: record for record in records}

    def get(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> UiCommandResponseIdempotencyRecord | None:
        with self._lock:
            return self._records.get((session_id, idempotency_key))

    def put(
        self,
        record: UiCommandResponseIdempotencyRecord,
    ) -> UiCommandResponseIdempotencyRecord:
        with self._lock:
            current = self._records.get(record.key)
            if current is not None:
                return current
            self._records[record.key] = record
            return record


class UiCommandResponseIdempotencyStoreError(RuntimeError):
    """Raised when a command response idempotency store cannot be used."""


class SqliteUiCommandResponseIdempotencyStore:
    """SQLite-backed UI command response idempotency cache."""

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

    def get(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> UiCommandResponseIdempotencyRecord | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM ui_command_response_idempotency_records
                WHERE session_id = ? AND idempotency_key = ?
                """,
                (session_id, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def put(
        self,
        record: UiCommandResponseIdempotencyRecord,
    ) -> UiCommandResponseIdempotencyRecord:
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO ui_command_response_idempotency_records(
                        session_id,
                        idempotency_key,
                        request_hash,
                        status_code,
                        headers_json,
                        body_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.session_id,
                        record.idempotency_key,
                        record.request_hash,
                        record.status_code,
                        _json_dumps(record.headers),
                        _json_dumps(record.body),
                        record.created_at.isoformat(),
                    ),
                )
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise UiCommandResponseIdempotencyStoreError(
                    "failed to save UI command response idempotency record"
                ) from exc
            else:
                self._conn.commit()

        current = self.get(record.session_id, record.idempotency_key)
        if current is None:
            raise UiCommandResponseIdempotencyStoreError(
                "UI command response idempotency record was not saved"
            )
        return current

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SqliteUiCommandResponseIdempotencyStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _record_from_row(row: sqlite3.Row) -> UiCommandResponseIdempotencyRecord:
    try:
        headers = json.loads(str(row["headers_json"]))
        body = json.loads(str(row["body_json"]))
        if not isinstance(headers, dict) or not isinstance(body, dict):
            raise TypeError("stored headers/body must be JSON objects")
        return UiCommandResponseIdempotencyRecord(
            session_id=str(row["session_id"]),
            idempotency_key=str(row["idempotency_key"]),
            request_hash=str(row["request_hash"]),
            status_code=int(row["status_code"]),
            headers={str(key): str(value) for key, value in headers.items()},
            body=cast(dict[str, Any], body),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise UiCommandResponseIdempotencyStoreError(
            "invalid UI command response idempotency record row"
        ) from exc


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


__all__ = [
    "InMemoryUiCommandResponseIdempotencyStore",
    "SqliteUiCommandResponseIdempotencyStore",
    "UiCommandResponseIdempotencyRecord",
    "UiCommandResponseIdempotencyStore",
    "UiCommandResponseIdempotencyStoreError",
]
