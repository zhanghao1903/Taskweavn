"""Execution Plane persistence and idempotency stores."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.execution_plane.errors import ExecutionPlaneError
from taskweavn.execution_plane.models import (
    EvidenceRef,
    TaskError,
    TaskEvent,
    TaskExecution,
    TaskRequest,
    TaskResult,
    utcnow,
)


class _StoreModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class TaskRequestIdempotencyRecord(_StoreModel):
    scoped_key: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    request: TaskRequest
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


@runtime_checkable
class ExecutionPlaneStore(Protocol):
    def get_idempotency(self, scoped_key: str) -> TaskRequestIdempotencyRecord | None: ...

    def put_idempotency(
        self,
        record: TaskRequestIdempotencyRecord,
    ) -> TaskRequestIdempotencyRecord: ...

    def put_execution(self, execution: TaskExecution) -> TaskExecution: ...

    def get_execution(self, execution_id: str) -> TaskExecution | None: ...

    def append_event(self, event: TaskEvent) -> TaskEvent: ...

    def list_events(self, execution_id: str, *, limit: int = 100) -> tuple[TaskEvent, ...]: ...

    def put_result(self, result: TaskResult) -> TaskResult: ...

    def get_result(self, result_ref: str) -> TaskResult | None: ...

    def put_error(self, error: TaskError) -> TaskError: ...

    def get_error(self, error_ref: str) -> TaskError | None: ...

    def put_evidence(self, evidence: EvidenceRef) -> EvidenceRef: ...

    def list_evidence(self, execution_id: str) -> tuple[EvidenceRef, ...]: ...


class InMemoryExecutionPlaneStore:
    def __init__(
        self,
        *,
        idempotency_records: Iterable[TaskRequestIdempotencyRecord] = (),
        executions: Iterable[TaskExecution] = (),
    ) -> None:
        self._lock = RLock()
        self._idempotency: dict[str, TaskRequestIdempotencyRecord] = {}
        self._executions: dict[str, TaskExecution] = {}
        self._events: dict[str, list[TaskEvent]] = {}
        self._results: dict[str, TaskResult] = {}
        self._errors: dict[str, TaskError] = {}
        self._evidence: dict[str, list[EvidenceRef]] = {}
        for record in idempotency_records:
            self.put_idempotency(record)
        for execution in executions:
            self.put_execution(execution)

    def get_idempotency(self, scoped_key: str) -> TaskRequestIdempotencyRecord | None:
        with self._lock:
            return self._idempotency.get(scoped_key)

    def put_idempotency(
        self,
        record: TaskRequestIdempotencyRecord,
    ) -> TaskRequestIdempotencyRecord:
        with self._lock:
            existing = self._idempotency.get(record.scoped_key)
            if existing is None:
                self._idempotency[record.scoped_key] = record
                return record
            if existing.request_hash != record.request_hash:
                raise ExecutionPlaneError(
                    "idempotency_conflict",
                    "idempotency key was already used with a different request",
                    status_code=409,
                    details={
                        "existingRequestHash": existing.request_hash,
                        "requestHash": record.request_hash,
                    },
                )
            return existing

    def put_execution(self, execution: TaskExecution) -> TaskExecution:
        with self._lock:
            self._executions[execution.execution_id] = execution
            return execution

    def get_execution(self, execution_id: str) -> TaskExecution | None:
        with self._lock:
            return self._executions.get(execution_id)

    def append_event(self, event: TaskEvent) -> TaskEvent:
        with self._lock:
            self._events.setdefault(event.execution_id, []).append(event)
            return event

    def list_events(self, execution_id: str, *, limit: int = 100) -> tuple[TaskEvent, ...]:
        with self._lock:
            return tuple(self._events.get(execution_id, [])[:limit])

    def put_result(self, result: TaskResult) -> TaskResult:
        with self._lock:
            self._results[result.result_ref] = result
            return result

    def get_result(self, result_ref: str) -> TaskResult | None:
        with self._lock:
            return self._results.get(result_ref)

    def put_error(self, error: TaskError) -> TaskError:
        with self._lock:
            self._errors[error.error_ref] = error
            return error

    def get_error(self, error_ref: str) -> TaskError | None:
        with self._lock:
            return self._errors.get(error_ref)

    def put_evidence(self, evidence: EvidenceRef) -> EvidenceRef:
        with self._lock:
            self._evidence.setdefault(evidence.execution_id, []).append(evidence)
            return evidence

    def list_evidence(self, execution_id: str) -> tuple[EvidenceRef, ...]:
        with self._lock:
            return tuple(self._evidence.get(execution_id, ()))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_idempotency (
    scoped_key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    request_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_tasks (
    execution_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_results (
    result_ref TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_errors (
    error_ref TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class SqliteExecutionPlaneStore:
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
        self._conn.executescript(_SCHEMA)
        self._lock = RLock()

    def get_idempotency(self, scoped_key: str) -> TaskRequestIdempotencyRecord | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT scoped_key, request_hash, execution_id, request_json, created_at, updated_at
                FROM execution_idempotency
                WHERE scoped_key = ?
                """,
                (scoped_key,),
            ).fetchone()
        if row is None:
            return None
        return _idempotency_from_row(row)

    def put_idempotency(
        self,
        record: TaskRequestIdempotencyRecord,
    ) -> TaskRequestIdempotencyRecord:
        with self._lock:
            existing = self.get_idempotency(record.scoped_key)
            if existing is not None:
                if existing.request_hash != record.request_hash:
                    raise ExecutionPlaneError(
                        "idempotency_conflict",
                        "idempotency key was already used with a different request",
                        status_code=409,
                        details={
                            "existingRequestHash": existing.request_hash,
                            "requestHash": record.request_hash,
                        },
                    )
                return existing
            self._conn.execute(
                """
                INSERT INTO execution_idempotency(
                    scoped_key, request_hash, execution_id, request_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.scoped_key,
                    record.request_hash,
                    record.execution_id,
                    record.request.model_dump_json(by_alias=True),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
            return record

    def put_execution(self, execution: TaskExecution) -> TaskExecution:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO execution_tasks(execution_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    execution.execution_id,
                    execution.model_dump_json(by_alias=True),
                    execution.updated_at.isoformat(),
                ),
            )
            return execution

    def get_execution(self, execution_id: str) -> TaskExecution | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM execution_tasks WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
        if row is None:
            return None
        return TaskExecution.model_validate_json(str(row["payload"]))

    def append_event(self, event: TaskEvent) -> TaskEvent:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO execution_events(
                    execution_id, event_id, occurred_at, payload
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    event.execution_id,
                    event.event_id,
                    event.occurred_at.isoformat(),
                    event.model_dump_json(by_alias=True),
                ),
            )
            return event

    def list_events(self, execution_id: str, *, limit: int = 100) -> tuple[TaskEvent, ...]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT payload FROM execution_events
                WHERE execution_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (execution_id, limit),
            ).fetchall()
        return tuple(TaskEvent.model_validate_json(str(row["payload"])) for row in rows)

    def put_result(self, result: TaskResult) -> TaskResult:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO execution_results(result_ref, execution_id, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(result_ref) DO UPDATE SET payload = excluded.payload
                """,
                (
                    result.result_ref,
                    result.execution_id,
                    result.model_dump_json(by_alias=True),
                    result.created_at.isoformat(),
                ),
            )
            return result

    def get_result(self, result_ref: str) -> TaskResult | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM execution_results WHERE result_ref = ?",
                (result_ref,),
            ).fetchone()
        if row is None:
            return None
        return TaskResult.model_validate_json(str(row["payload"]))

    def put_error(self, error: TaskError) -> TaskError:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO execution_errors(error_ref, execution_id, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(error_ref) DO UPDATE SET payload = excluded.payload
                """,
                (
                    error.error_ref,
                    error.execution_id,
                    error.model_dump_json(by_alias=True),
                    error.created_at.isoformat(),
                ),
            )
            return error

    def get_error(self, error_ref: str) -> TaskError | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM execution_errors WHERE error_ref = ?",
                (error_ref,),
            ).fetchone()
        if row is None:
            return None
        return TaskError.model_validate_json(str(row["payload"]))

    def put_evidence(self, evidence: EvidenceRef) -> EvidenceRef:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO execution_evidence(
                    execution_id, evidence_id, created_at, payload
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    evidence.execution_id,
                    evidence.evidence_id,
                    evidence.created_at.isoformat(),
                    evidence.model_dump_json(by_alias=True),
                ),
            )
            return evidence

    def list_evidence(self, execution_id: str) -> tuple[EvidenceRef, ...]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT payload FROM execution_evidence
                WHERE execution_id = ?
                ORDER BY id ASC
                """,
                (execution_id,),
            ).fetchall()
        return tuple(EvidenceRef.model_validate_json(str(row["payload"])) for row in rows)

    def close(self) -> None:
        with self._lock, contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SqliteExecutionPlaneStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def scoped_idempotency_key(request: TaskRequest) -> str:
    return f"{request.requester.scoped_id}:{request.idempotency_key}"


def request_hash(request: TaskRequest) -> str:
    payload = request.model_dump(mode="json", by_alias=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _idempotency_from_row(row: sqlite3.Row) -> TaskRequestIdempotencyRecord:
    return TaskRequestIdempotencyRecord(
        scoped_key=str(row["scoped_key"]),
        request_hash=str(row["request_hash"]),
        execution_id=str(row["execution_id"]),
        request=TaskRequest.model_validate_json(str(row["request_json"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )
