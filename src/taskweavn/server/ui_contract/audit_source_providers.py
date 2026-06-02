"""Workspace-backed Audit Page source providers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from taskweavn.core.session import Session
from taskweavn.observability.models import LogArchiveManifest
from taskweavn.server.ui_contract.audit_event_records import source_unavailable_record
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditConfigProvider,
    AuditLogProvider,
)
from taskweavn.server.ui_contract.view_models import (
    AuditConfigScope,
    AuditLogEvidenceScope,
    AuditRecord,
    AuditRecordFlags,
    EffectiveConfigSummary,
    EvidenceRef,
    RelatedLogsLink,
)

_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


class WorkspaceAuditConfigProvider:
    """Read config evidence from the session log manifest when present."""

    def list_for_session(
        self,
        session: Session,
        *,
        task_node_id: str | None = None,
    ) -> tuple[AuditRecord, ...]:
        manifest = _read_session_log_manifest(session)
        if manifest is None:
            return ()
        return (_config_record_from_manifest(session, manifest, task_node_id),)

    def get_effective_config(
        self,
        session: Session,
        *,
        records: Sequence[AuditRecord],
    ) -> EffectiveConfigSummary | None:
        manifest = _read_session_log_manifest(session)
        if manifest is None:
            return None
        config_records = tuple(record.id for record in records if record.filter_kind == "config")
        active = (
            f" from {manifest.active_config_path}"
            if manifest.active_config_path is not None
            else ""
        )
        return EffectiveConfigSummary(
            summary=f"Logging config hash {manifest.config_hash} is active{active}.",
            profile_label="Session log manifest",
            effective_at=manifest.created_at,
            relevant_record_ids=config_records,
            settings_href=(
                None
                if manifest.active_config_path is None
                else manifest.active_config_path
            ),
        )


class WorkspaceAuditLogProvider:
    """Read log evidence references from the session log directory."""

    def list_for_session(
        self,
        session: Session,
        *,
        task_node_id: str | None = None,
    ) -> tuple[AuditRecord, ...]:
        log_dir = session.logs_dir
        if not log_dir.exists():
            return ()
        records: list[AuditRecord] = []
        for path in sorted(log_dir.iterdir(), key=lambda item: item.name):
            if not path.is_file() or path.name == "manifest.json":
                continue
            if path.suffix.lower() not in {".jsonl", ".log"}:
                continue
            records.append(_log_record_from_path(session, path, task_node_id))
        return tuple(records)

    def related_logs(
        self,
        session: Session,
        *,
        task_node_id: str | None,
        record_id: str | None,
    ) -> tuple[RelatedLogsLink, ...]:
        log_dir = session.logs_dir
        enabled = log_dir.exists()
        return (
            RelatedLogsLink(
                label="Session log archive",
                href=str(log_dir),
                filters={
                    "sessionId": session.id,
                    "taskNodeId": task_node_id,
                    "recordId": record_id,
                    "category": "audit",
                },
                enabled=enabled,
                disabled_reason=None if enabled else "Session log archive is not present.",
            ),
        )


def config_audit_records(
    session: Session,
    provider: AuditConfigProvider | None,
    *,
    task_node_id: str | None,
) -> tuple[AuditRecord, ...]:
    if provider is None:
        return ()
    try:
        return tuple(provider.list_for_session(session, task_node_id=task_node_id))
    except Exception as exc:  # noqa: BLE001 - source failure should be visible.
        return (
            source_unavailable_record(
                session.id,
                source_name="Config store",
                reason=f"{type(exc).__name__}: {exc}",
                task_node_id=task_node_id,
            ),
        )


def log_audit_records(
    session: Session,
    provider: AuditLogProvider | None,
    *,
    task_node_id: str | None,
) -> tuple[AuditRecord, ...]:
    if provider is None:
        return ()
    try:
        return tuple(provider.list_for_session(session, task_node_id=task_node_id))
    except Exception as exc:  # noqa: BLE001 - source failure should be visible.
        return (
            source_unavailable_record(
                session.id,
                source_name="Log archive",
                reason=f"{type(exc).__name__}: {exc}",
                task_node_id=task_node_id,
            ),
        )


def _config_record_from_manifest(
    session: Session,
    manifest: LogArchiveManifest,
    task_node_id: str | None,
) -> AuditRecord:
    record_id = "record-config-logging-manifest"
    active_config = (
        f" Active config path: {manifest.active_config_path}."
        if manifest.active_config_path is not None
        else ""
    )
    return AuditRecord(
        id=record_id,
        scope=AuditConfigScope(session_id=session.id, config_key="logging"),
        kind="config_change",
        filter_kind="config",
        title="Logging config snapshot",
        summary=f"Session logging config hash is {manifest.config_hash}.{active_config}",
        actor="system",
        source_label="Log archive manifest",
        occurred_at=manifest.created_at,
        severity="info",
        confidence="high",
        completeness="complete",
        task_node_id=task_node_id,
        config_key="logging",
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="config_snapshot",
                label="Session log manifest",
                summary=f"Manifest records {len(manifest.files)} log file(s).",
            ),
        ),
    )


def _log_record_from_path(
    session: Session,
    path: Path,
    task_node_id: str | None,
) -> AuditRecord:
    file_token = _safe_token(path.name)
    record_id = f"record-log-{file_token}"
    try:
        stat = path.stat()
        occurred_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        size = stat.st_size
    except OSError:
        occurred_at = datetime.now(UTC)
        size = 0
    evidence_id = f"evidence-{record_id}"
    return AuditRecord(
        id=record_id,
        scope=AuditLogEvidenceScope(
            session_id=session.id,
            evidence_id=evidence_id,
            task_node_id=task_node_id,
        ),
        kind="log_evidence",
        filter_kind="logs",
        title="Log evidence available",
        summary=f"{path.name} is available in the session log archive ({size} bytes).",
        actor="system",
        source_label="Log archive",
        occurred_at=occurred_at,
        severity="info",
        confidence="high",
        completeness="partial",
        task_node_id=task_node_id,
        evidence_refs=(
            EvidenceRef(
                id=evidence_id,
                kind="log_excerpt",
                label=path.name,
                summary=f"Session log file: {path}",
            ),
        ),
        flags=AuditRecordFlags(partial=True),
    )


def _read_session_log_manifest(session: Session) -> LogArchiveManifest | None:
    path = session.logs_dir / "manifest.json"
    if not path.exists():
        return None
    try:
        return LogArchiveManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - invalid manifests should not break Audit Page.
        return None


def _safe_token(value: str) -> str:
    return _ID_SAFE_RE.sub("-", value).strip("-") or "item"


__all__ = [
    "WorkspaceAuditConfigProvider",
    "WorkspaceAuditLogProvider",
    "config_audit_records",
    "log_audit_records",
]
