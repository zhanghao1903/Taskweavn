"""Workspace inspection evidence projection for diagnostic bundles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
            "supportSummary": _support_summary(records, max_records=max_records),
            "records": [_record_summary(record) for record in records],
        },
        tuple(warnings),
    )


def _support_summary(
    records: Sequence[Mapping[str, Any]],
    *,
    max_records: int,
) -> dict[str, Any]:
    records_by_kind = _count_by(records, "kind")
    records_by_source = _count_by(records, "source")
    omitted_payload_count = 0
    latest_captured_at: str | None = None

    for record in records:
        payload = _mapping(record.get("payload"))
        if payload.get("omitted") is True:
            omitted_payload_count += 1
        captured_at = record.get("capturedAt")
        if isinstance(captured_at, str) and (
            latest_captured_at is None or captured_at > latest_captured_at
        ):
            latest_captured_at = captured_at

    return {
        "schemaVersion": "plato.workspace_inspection.support_summary.v1",
        "recordCount": len(records),
        "recordLimit": max_records,
        "recordsByKind": records_by_kind,
        "recordsBySource": records_by_source,
        "latestCapturedAt": latest_captured_at,
        "omittedPayloadCount": omitted_payload_count,
        "availableEvidenceKinds": tuple(sorted(records_by_kind)),
        "hasGitStatusEvidence": "git_status_snapshot" in records_by_kind,
        "hasDiffEvidence": "diff_snapshot" in records_by_kind,
        "hasFileEvidence": "file_snapshot" in records_by_kind,
        "previewLimits": {
            "maxPreviewLines": MAX_DIAGNOSTIC_PREVIEW_LINES,
            "maxPreviewChars": MAX_DIAGNOSTIC_PREVIEW_CHARS,
        },
        "supportUse": (
            "Use evidenceRef.pathLabel and payloadSummary to identify the inspected file or diff.",
            "Use contentHash when present to compare whether later evidence "
            "describes the same content.",
            "Use manifest section warnings to see whether the evidence list was truncated.",
        ),
        "limitations": (
            "The diagnostic bundle includes descriptors and small redacted previews only.",
            "Raw unified diffs and full file contents are intentionally excluded.",
            "Only the most recent workspace inspection evidence records are included.",
        ),
    }


def _count_by(
    records: Sequence[Mapping[str, Any]],
    key: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = record.get(key)
        if value is None:
            continue
        label = str(value)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


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
