"""Idempotency stores for Contract Revision commands."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Protocol, runtime_checkable

from taskweavn.contract_revision.models import (
    ContractCommandRecord,
    ContractCommandRequest,
    ContractCommandResult,
)
from taskweavn.server.ui_contract.base import utcnow

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS contract_revision_command_records (
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    command_id TEXT NOT NULL,
    command_kind TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    PRIMARY KEY (session_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_contract_revision_commands_session_created
    ON contract_revision_command_records(session_id, created_at, idempotency_key);
"""


class ContractCommandIdempotencyStoreError(RuntimeError):
    """Raised when command idempotency persistence fails."""


@runtime_checkable
class ContractCommandIdempotencyStore(Protocol):
    def get(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> ContractCommandRecord | None: ...

    def put_completed(
        self,
        request: ContractCommandRequest,
        *,
        request_hash: str,
        result: ContractCommandResult,
    ) -> ContractCommandRecord: ...


class InMemoryContractCommandIdempotencyStore:
    """In-memory idempotency store for focused tests."""

    def __init__(self, records: Iterable[ContractCommandRecord] = ()) -> None:
        self._lock = RLock()
        self._records = {
            (record.session_id, record.idempotency_key): record for record in records
        }

    def get(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> ContractCommandRecord | None:
        with self._lock:
            return self._records.get((session_id, idempotency_key))

    def put_completed(
        self,
        request: ContractCommandRequest,
        *,
        request_hash: str,
        result: ContractCommandResult,
    ) -> ContractCommandRecord:
        record = ContractCommandRecord(
            session_id=request.session_id,
            idempotency_key=request.idempotency_key,
            command_id=request.command_id,
            command_kind=request.command_kind,
            request_hash=request_hash,
            status=result.status,
            result=result,
            created_at=utcnow(),
            completed_at=utcnow(),
        )
        key = (record.session_id, record.idempotency_key)
        with self._lock:
            current = self._records.get(key)
            if current is not None:
                return current
            self._records[key] = record
            return record


class SqliteContractCommandIdempotencyStore:
    """SQLite-backed idempotency store for Contract Revision commands."""

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
    ) -> ContractCommandRecord | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM contract_revision_command_records
                WHERE session_id = ? AND idempotency_key = ?
                """,
                (session_id, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def put_completed(
        self,
        request: ContractCommandRequest,
        *,
        request_hash: str,
        result: ContractCommandResult,
    ) -> ContractCommandRecord:
        created_at = utcnow()
        completed_at = utcnow()
        result_json = result.model_dump_json()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO contract_revision_command_records(
                        session_id,
                        idempotency_key,
                        command_id,
                        command_kind,
                        request_hash,
                        status,
                        result_json,
                        created_at,
                        completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request.session_id,
                        request.idempotency_key,
                        request.command_id,
                        request.command_kind,
                        request_hash,
                        result.status,
                        result_json,
                        created_at.isoformat(),
                        completed_at.isoformat(),
                    ),
                )
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise ContractCommandIdempotencyStoreError(
                    "failed to save contract revision idempotency record"
                ) from exc
            else:
                self._conn.commit()

        current = self.get(request.session_id, request.idempotency_key)
        if current is None:
            raise ContractCommandIdempotencyStoreError(
                "contract revision idempotency record was not saved"
            )
        return current

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SqliteContractCommandIdempotencyStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _record_from_row(row: sqlite3.Row) -> ContractCommandRecord:
    try:
        result_json = row["result_json"]
        result = (
            None
            if result_json is None
            else ContractCommandResult.model_validate(json.loads(str(result_json)))
        )
        return ContractCommandRecord.model_validate(
            {
                "session_id": str(row["session_id"]),
                "idempotency_key": str(row["idempotency_key"]),
                "command_id": str(row["command_id"]),
                "command_kind": str(row["command_kind"]),
                "request_hash": str(row["request_hash"]),
                "status": str(row["status"]),
                "result": result,
                "created_at": _parse_datetime(str(row["created_at"])),
                "completed_at": (
                    None
                    if row["completed_at"] is None
                    else _parse_datetime(str(row["completed_at"]))
                ),
            }
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ContractCommandIdempotencyStoreError(
            "invalid contract revision idempotency record row"
        ) from exc


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


__all__ = [
    "ContractCommandIdempotencyStore",
    "ContractCommandIdempotencyStoreError",
    "InMemoryContractCommandIdempotencyStore",
    "SqliteContractCommandIdempotencyStore",
]
