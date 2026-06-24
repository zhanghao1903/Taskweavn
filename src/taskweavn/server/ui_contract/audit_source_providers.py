"""Workspace-backed Audit Page source providers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from taskweavn.core.session import Session
from taskweavn.observability.models import LogArchiveManifest
from taskweavn.runtime_config import (
    EffectiveRuntimeConfig,
    RuntimeConfigChange,
    RuntimeConfigScope,
)
from taskweavn.server.runtime_config_gateway import RuntimeConfigGateway
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
    """Read config evidence from runtime config and session log manifests."""

    def __init__(
        self,
        *,
        runtime_config_gateway: RuntimeConfigGateway | None = None,
    ) -> None:
        self._runtime_config_gateway = runtime_config_gateway

    def list_for_session(
        self,
        session: Session,
        *,
        task_node_id: str | None = None,
    ) -> tuple[AuditRecord, ...]:
        records: list[AuditRecord] = []
        records.extend(
            _runtime_config_records(
                session,
                self._runtime_config_gateway,
                task_node_id=task_node_id,
            )
        )
        manifest = _read_session_log_manifest(session)
        if manifest is not None:
            records.append(_config_record_from_manifest(session, manifest, task_node_id))
        return tuple(records)

    def get_effective_config(
        self,
        session: Session,
        *,
        records: Sequence[AuditRecord],
    ) -> EffectiveConfigSummary | None:
        runtime_summary = _effective_runtime_config_summary(
            session,
            self._runtime_config_gateway,
            records=records,
        )
        if runtime_summary is not None:
            return runtime_summary
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
                href=_diagnostics_logs_href(
                    session.id,
                    task_node_id=task_node_id,
                    record_id=record_id,
                ),
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


def _runtime_config_records(
    session: Session,
    gateway: RuntimeConfigGateway | None,
    *,
    task_node_id: str | None,
) -> tuple[AuditRecord, ...]:
    if gateway is None:
        return ()
    try:
        effective = gateway.effective(RuntimeConfigScope())
        changes = gateway.list_changes(RuntimeConfigScope())
    except Exception as exc:  # noqa: BLE001 - Audit Page should degrade, not fail.
        return (
            source_unavailable_record(
                session.id,
                source_name="Runtime config",
                reason=f"{type(exc).__name__}: {exc}",
                task_node_id=task_node_id,
            ),
        )
    records = [_runtime_config_snapshot_record(session, effective, task_node_id)]
    records.extend(
        _runtime_config_change_record(session, change, task_node_id)
        for change in changes
    )
    return tuple(records)


def _runtime_config_snapshot_record(
    session: Session,
    effective: EffectiveRuntimeConfig,
    task_node_id: str | None,
) -> AuditRecord:
    token = _safe_token(effective.config_hash[:16])
    record_id = f"record-config-runtime-effective-{token}"
    return AuditRecord(
        id=record_id,
        scope=AuditConfigScope(session_id=session.id, config_key="runtime"),
        kind="config_change",
        filter_kind="config",
        title="Runtime config snapshot",
        summary=(
            f"Runtime config hash {effective.config_hash} is active with "
            f"{len(effective.values)} key(s) from {len(effective.source_layers)} source layer(s)."
        ),
        actor="system",
        source_label="Runtime config",
        occurred_at=effective.created_at,
        severity="info",
        confidence="high",
        completeness="complete",
        task_node_id=task_node_id,
        config_key="runtime",
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="config_snapshot",
                label="Effective runtime config",
                summary=(
                    "Effective runtime config is available by hash; raw values are "
                    "not exposed in Audit records."
                ),
            ),
        ),
    )


def _runtime_config_change_record(
    session: Session,
    change: RuntimeConfigChange,
    task_node_id: str | None,
) -> AuditRecord:
    token = _safe_token(change.change_id)
    record_id = f"record-config-runtime-change-{token}"
    accepted_count = len(change.accepted_values)
    rejected_count = len(change.rejected_values)
    redacted = bool(change.redacted_keys)
    return AuditRecord(
        id=record_id,
        scope=AuditConfigScope(session_id=session.id, config_key="runtime"),
        kind="config_change",
        filter_kind="config",
        title=f"Runtime config change {change.status}",
        summary=(
            f"Runtime config change {change.change_id} was {change.status}: "
            f"{accepted_count} accepted key(s), {rejected_count} rejected key(s), "
            f"{len(change.redacted_keys)} redacted key(s)."
        ),
        actor="system",
        source_label="Runtime config",
        occurred_at=change.created_at,
        severity="warning" if change.status == "rejected" else "info",
        confidence="high",
        verdict="warning" if change.status == "rejected" else None,
        completeness="complete",
        task_node_id=task_node_id,
        config_key=_change_config_key(change),
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="config_snapshot",
                label="Runtime config change ledger",
                summary=(
                    f"Base hash {change.base_config_hash}; resulting hash "
                    f"{change.resulting_config_hash or 'not_available'}. Values are not exposed."
                ),
                redacted=redacted,
            ),
        ),
        flags=AuditRecordFlags(redacted=redacted),
    )


def _effective_runtime_config_summary(
    session: Session,
    gateway: RuntimeConfigGateway | None,
    *,
    records: Sequence[AuditRecord],
) -> EffectiveConfigSummary | None:
    if gateway is None:
        return None
    try:
        effective = gateway.effective(RuntimeConfigScope())
    except Exception:  # noqa: BLE001 - summary is optional; records show source failure.
        return None
    config_records = tuple(record.id for record in records if record.filter_kind == "config")
    return EffectiveConfigSummary(
        summary=(
            f"Runtime config hash {effective.config_hash} is active for session "
            f"{session.id}."
        ),
        profile_label="Runtime config",
        effective_at=effective.created_at,
        relevant_record_ids=config_records,
        settings_href="/settings?tab=runtime",
    )


def _change_config_key(change: RuntimeConfigChange) -> str:
    keys = sorted(set(change.accepted_values) | set(change.rejected_values))
    return keys[0] if len(keys) == 1 else "runtime"


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
                summary=f"Session log file: session-logs://{path.name}",
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


def _diagnostics_logs_href(
    session_id: str,
    *,
    task_node_id: str | None,
    record_id: str | None,
) -> str:
    params = {
        "category": "audit",
        "recordId": record_id,
        "taskNodeId": task_node_id,
    }
    query = urlencode({key: value for key, value in params.items() if value})
    path = f"/sessions/{quote(session_id, safe='')}/diagnostics/logs"
    return f"{path}?{query}" if query else path


__all__ = [
    "WorkspaceAuditConfigProvider",
    "WorkspaceAuditLogProvider",
    "config_audit_records",
    "log_audit_records",
]
