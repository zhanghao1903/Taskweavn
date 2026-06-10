"""Dedicated workspace inspection evidence store."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskweavn.workspace_inspection.limits import WorkspaceInspectionLimits


class InspectionEvidenceNotFoundError(KeyError):
    """Raised when a captured inspection evidence record does not exist."""


@dataclass(frozen=True)
class SqliteInspectionEvidenceStore:
    """Workspace-scoped store for captured inspection evidence refs."""

    db_path: Path
    limits: WorkspaceInspectionLimits = WorkspaceInspectionLimits()

    def capture(
        self,
        *,
        workspace_id: str,
        kind: str,
        source: str,
        payload: dict[str, Any],
        descriptor: dict[str, Any],
        path_label: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_schema()
        evidence_id = f"inspection-{uuid.uuid4().hex}"
        captured_at = _utcnow()
        payload_for_store = self._bounded_payload(payload)
        descriptor_for_store = dict(descriptor)
        if payload_for_store is not payload:
            descriptor_for_store["payloadOmitted"] = True
            descriptor_for_store["omittedReason"] = "workspace.inspection_truncated"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO inspection_evidence(
                    evidence_id,
                    workspace_id,
                    kind,
                    source,
                    path_label,
                    captured_at,
                    payload_json,
                    descriptor_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    workspace_id,
                    kind,
                    source,
                    path_label,
                    captured_at,
                    json.dumps(payload_for_store, sort_keys=True),
                    json.dumps(descriptor_for_store, sort_keys=True),
                ),
            )
        return {
            "evidenceId": evidence_id,
            "kind": kind,
            "workspaceId": workspace_id,
            **({"pathLabel": path_label} if path_label else {}),
            "createdAt": captured_at,
        }

    def get(self, evidence_id: str) -> dict[str, Any]:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT evidence_id, workspace_id, kind, source, path_label,
                       captured_at, payload_json, descriptor_json
                FROM inspection_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
        if row is None:
            raise InspectionEvidenceNotFoundError(evidence_id)
        return {
            "evidenceId": row["evidence_id"],
            "workspaceId": row["workspace_id"],
            "kind": row["kind"],
            "source": row["source"],
            "pathLabel": row["path_label"],
            "capturedAt": row["captured_at"],
            "payload": json.loads(row["payload_json"]),
            "descriptor": json.loads(row["descriptor_json"]),
        }

    def list_recent(self, *, max_records: int = 50) -> tuple[dict[str, Any], ...]:
        if not self.db_path.exists():
            return ()
        self._ensure_schema()
        limit = max(0, max_records)
        if limit == 0:
            return ()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT evidence_id, workspace_id, kind, source, path_label,
                       captured_at, payload_json, descriptor_json
                FROM inspection_evidence
                ORDER BY captured_at DESC, evidence_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(_row_to_record(row) for row in rows)

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS inspection_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    path_label TEXT,
                    captured_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    descriptor_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_inspection_evidence_workspace_created
                ON inspection_evidence(workspace_id, captured_at DESC)
                """
            )

    def _bounded_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        if len(encoded) <= self.limits.evidence_payload_bytes:
            return payload
        return {
            "omitted": True,
            "omittedReason": "workspace.inspection_truncated",
        }


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _row_to_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "evidenceId": row["evidence_id"],
        "workspaceId": row["workspace_id"],
        "kind": row["kind"],
        "source": row["source"],
        "pathLabel": row["path_label"],
        "capturedAt": row["captured_at"],
        "payload": json.loads(row["payload_json"]),
        "descriptor": json.loads(row["descriptor_json"]),
    }
