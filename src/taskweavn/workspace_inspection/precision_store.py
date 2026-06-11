"""Durable idempotency store for precision file mutations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


class PrecisionFileOperationConflictError(ValueError):
    """Raised when an operation id is reused with a different request."""


class PrecisionFileOperationBusyError(RuntimeError):
    """Raised when an operation id is already in progress."""


@dataclass(frozen=True)
class PrecisionOperationReplay:
    """A previously completed precision operation response."""

    response: dict[str, Any]


@dataclass(frozen=True)
class SqlitePrecisionFileOperationStore:
    """Workspace-scoped operation idempotency for precision file mutations."""

    db_path: Path

    def reserve(
        self,
        *,
        operation_id: str,
        request_hash: str,
        kind: Literal["replace_range", "append"],
        workspace_id: str,
        path_label: str,
    ) -> PrecisionOperationReplay | None:
        self._ensure_schema()
        now = _utcnow()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT operation_id, request_hash, status, response_json
                FROM precision_file_operations
                WHERE operation_id = ?
                """,
                (operation_id,),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash:
                    raise PrecisionFileOperationConflictError(
                        "operation id reused with a different request"
                    )
                if row["status"] == "completed":
                    response = json.loads(row["response_json"])
                    if isinstance(response, dict):
                        return PrecisionOperationReplay(response=response)
                if row["status"] == "pending":
                    raise PrecisionFileOperationBusyError("operation is already running")
                conn.execute(
                    """
                    UPDATE precision_file_operations
                    SET status = 'pending', created_at = ?, completed_at = NULL
                    WHERE operation_id = ?
                    """,
                    (now, operation_id),
                )
                return None
            conn.execute(
                """
                INSERT INTO precision_file_operations(
                    operation_id,
                    request_hash,
                    kind,
                    workspace_id,
                    path_label,
                    status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (operation_id, request_hash, kind, workspace_id, path_label, now),
            )
        return None

    def complete(
        self,
        *,
        operation_id: str,
        before_hash: str,
        after_hash: str,
        evidence_id: str,
        response: dict[str, Any],
    ) -> None:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE precision_file_operations
                SET status = 'completed',
                    before_hash = ?,
                    after_hash = ?,
                    evidence_id = ?,
                    response_json = ?,
                    completed_at = ?
                WHERE operation_id = ?
                """,
                (
                    before_hash,
                    after_hash,
                    evidence_id,
                    json.dumps(response, sort_keys=True),
                    _utcnow(),
                    operation_id,
                ),
            )

    def fail(self, *, operation_id: str, message: str) -> None:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE precision_file_operations
                SET status = 'failed',
                    response_json = ?,
                    completed_at = ?
                WHERE operation_id = ?
                """,
                (
                    json.dumps({"error": message}, sort_keys=True),
                    _utcnow(),
                    operation_id,
                ),
            )

    def get(self, operation_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT operation_id, request_hash, kind, workspace_id, path_label,
                       status, before_hash, after_hash, evidence_id, response_json,
                       created_at, completed_at
                FROM precision_file_operations
                WHERE operation_id = ?
                """,
                (operation_id,),
            ).fetchone()
        if row is None:
            return None
        response_json = row["response_json"]
        return {
            "operationId": row["operation_id"],
            "requestHash": row["request_hash"],
            "kind": row["kind"],
            "workspaceId": row["workspace_id"],
            "pathLabel": row["path_label"],
            "status": row["status"],
            "beforeHash": row["before_hash"],
            "afterHash": row["after_hash"],
            "evidenceId": row["evidence_id"],
            "response": json.loads(response_json) if response_json else None,
            "createdAt": row["created_at"],
            "completedAt": row["completed_at"],
        }

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS precision_file_operations (
                    operation_id TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    path_label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    before_hash TEXT,
                    after_hash TEXT,
                    evidence_id TEXT,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_precision_file_operations_workspace_created
                ON precision_file_operations(workspace_id, created_at DESC)
                """
            )


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
