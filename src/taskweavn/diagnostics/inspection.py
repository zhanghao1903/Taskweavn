"""Workspace inspection evidence projection for diagnostic bundles."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from taskweavn.workspace_inspection import SqliteInspectionEvidenceStore

MAX_DIAGNOSTIC_INSPECTION_RECORDS = 50
MAX_DIAGNOSTIC_PREVIEW_LINES = 20
MAX_DIAGNOSTIC_PREVIEW_CHARS = 200


def collect_inspection_evidence_summary(
    *,
    inspection_db_path: Path,
    max_records: int = MAX_DIAGNOSTIC_INSPECTION_RECORDS,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Return redaction-ready inspection evidence descriptors for diagnostics."""

    if not inspection_db_path.exists():
        return None, ("workspace inspection evidence store is not present",)

    records = SqliteInspectionEvidenceStore(inspection_db_path).list_recent(
        max_records=max_records,
    )
    if not records:
        return None, ("workspace inspection evidence store is empty",)

    warnings: list[str] = []
    if len(records) >= max_records:
        warnings.append(
            f"workspace inspection evidence truncated to {max_records} records"
        )

    return (
        {
            "schemaVersion": "plato.workspace_inspection.diagnostic_summary.v1",
            "evidenceCount": len(records),
            "includedEvidenceCount": len(records),
            "records": [_record_summary(record) for record in records],
        },
        tuple(warnings),
    )


def _record_summary(record: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = _mapping(record.get("descriptor"))
    payload = _mapping(record.get("payload"))
    summary: dict[str, Any] = {
        "evidenceRef": {
            "evidenceId": record.get("evidenceId"),
            "kind": record.get("kind"),
            "workspaceId": record.get("workspaceId"),
            **({"pathLabel": record.get("pathLabel")} if record.get("pathLabel") else {}),
            "createdAt": record.get("capturedAt"),
        },
        "source": record.get("source"),
        "descriptor": descriptor,
        "payloadOmitted": bool(payload.get("omitted")),
    }
    payload_summary = _payload_summary(record.get("kind"), payload)
    if payload_summary:
        summary["payloadSummary"] = payload_summary
    return summary


def _payload_summary(kind: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not payload or payload.get("omitted") is True:
        return {
            "omitted": True,
            "omittedReason": payload.get("omittedReason", "workspace.inspection_omitted"),
        }

    if kind == "git_status_snapshot":
        repository = _mapping(payload.get("repository"))
        summary = _mapping(payload.get("summary"))
        return {
            "repositoryStatus": repository.get("status"),
            "changedFileCount": summary.get("changedFileCount"),
            "stagedFileCount": summary.get("stagedFileCount"),
            "unstagedFileCount": summary.get("unstagedFileCount"),
            "untrackedFileCount": summary.get("untrackedFileCount"),
            "hasMore": summary.get("hasMore"),
        }

    if kind == "diff_snapshot":
        file = _mapping(payload.get("file"))
        stats = _mapping(payload.get("stats"))
        return {
            "pathLabel": file.get("pathLabel"),
            "changeKind": file.get("changeKind"),
            "isAvailable": payload.get("isAvailable"),
            "additions": stats.get("additions"),
            "deletions": stats.get("deletions"),
            "hunkCount": stats.get("hunkCount"),
            "truncated": stats.get("truncated"),
            "contentHash": payload.get("contentHash"),
        }

    if kind == "file_snapshot":
        file = _mapping(payload.get("file"))
        range_summary = _mapping(payload.get("range"))
        content = _mapping(payload.get("content"))
        lines = content.get("lines")
        preview_lines = []
        if isinstance(lines, list):
            preview_lines = [
                _line_preview(line)
                for line in lines[:MAX_DIAGNOSTIC_PREVIEW_LINES]
                if isinstance(line, Mapping)
            ]
        return {
            "pathLabel": file.get("pathLabel"),
            "fileKind": file.get("fileKind"),
            "startLine": range_summary.get("startLine"),
            "endLine": range_summary.get("endLine"),
            "totalLines": range_summary.get("totalLines"),
            "truncated": range_summary.get("truncated"),
            "previewLines": preview_lines,
            "previewTruncated": (
                isinstance(lines, list) and len(lines) > len(preview_lines)
            ),
            "contentHash": payload.get("contentHash"),
        }

    return {}


def _line_preview(line: Mapping[str, Any]) -> dict[str, Any]:
    text = str(line.get("text", ""))
    if len(text) > MAX_DIAGNOSTIC_PREVIEW_CHARS:
        text = f"{text[: MAX_DIAGNOSTIC_PREVIEW_CHARS - 3]}..."
    return {
        "lineNumber": line.get("lineNumber"),
        "text": text,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
