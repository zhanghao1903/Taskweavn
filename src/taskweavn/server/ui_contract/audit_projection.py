"""Audit Page projection helpers and workspace-backed evidence providers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from taskweavn.core.session import Session
from taskweavn.observability.models import LogArchiveManifest
from taskweavn.server.ui_contract.audit_disclosure import _no_payload, _record_partial_reason
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditConfigProvider,
    AuditEventProvider,
    AuditLogProvider,
    AuditPayloadDisclosureService,
)
from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.server.ui_contract.view_models import (
    AuditActionScope,
    AuditConfigScope,
    AuditConfirmationScope,
    AuditEmptyPageState,
    AuditEntryContext,
    AuditEvidenceSource,
    AuditFileScope,
    AuditFilterKind,
    AuditFilterView,
    AuditLogEvidenceScope,
    AuditOverview,
    AuditPartialPageState,
    AuditReadyPageState,
    AuditRecord,
    AuditRecordDetail,
    AuditRecordFlags,
    AuditRecordKind,
    AuditReference,
    AuditResultScope,
    AuditSessionScope,
    AuditSeverity,
    AuditTaskScope,
    AuditVerdict,
    EffectiveConfigSummary,
    EvidenceDetail,
    EvidenceRef,
    EvidenceSummary,
    MainPageReturnTarget,
    ProjectSummary,
    RelatedLogsLink,
    SessionMessageView,
    SessionSummary,
    TaskNodeCardView,
    TaskTreeView,
    WorkflowSummary,
)
from taskweavn.task.models import TaskRef
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.views import ConfirmationActionView as CoreConfirmationActionView
from taskweavn.task.views import TaskCardView as CoreTaskCardView
from taskweavn.task.views import TaskTreeView as CoreTaskTreeView
from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation


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


_AUDIT_FILTER_LABELS: dict[AuditFilterKind, str] = {
    "all": "All records",
    "confirmations": "Confirmations",
    "actions": "Actions",
    "risks": "Risks",
    "files": "Files",
    "results": "Results",
    "system": "System",
    "config": "Config",
    "logs": "Logs",
}
_AUDIT_FILTER_KINDS = frozenset(_AUDIT_FILTER_LABELS)
_AUDIT_RECORD_KINDS = frozenset(
    {
        "confirmation",
        "action",
        "observation",
        "risk",
        "file_change",
        "result",
        "message",
        "config_change",
        "audit_verdict",
        "system",
        "log_evidence",
    }
)
_AUDIT_ENTRY_KINDS = frozenset(
    {
        "from_session",
        "from_task",
        "from_confirmation",
        "from_result",
        "from_file_change",
    }
)
_AUDIT_PROJECTION_PARTIAL_REASON = (
    "Audit records are projected from Task state. Dedicated audit-agent, log, "
    "and raw event evidence aggregation is not connected yet."
)
_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


@dataclass(frozen=True)
class _AuditProjectionBundle:
    session: Session
    session_summary: SessionSummary
    project: ProjectSummary
    workflow: WorkflowSummary
    source_tree: CoreTaskTreeView
    task_tree: TaskTreeView | None
    selected_task: TaskNodeCardView | None
    records: tuple[AuditRecord, ...]


def _safe_token(value: str) -> str:
    return _ID_SAFE_RE.sub("-", value).strip("-") or "item"



def _audit_records_from_projection(
    source: CoreTaskTreeView,
    *,
    session: Session,
    session_id: str,
    task_node_id: str | None,
    messages: Sequence[SessionMessageView],
    task_projection: TaskProjectionService,
    event_provider: AuditEventProvider | None,
    config_provider: AuditConfigProvider | None,
    log_provider: AuditLogProvider | None,
) -> tuple[AuditRecord, ...]:
    records: list[AuditRecord] = []
    scoped_nodes = _scoped_nodes(source, task_node_id=task_node_id)
    for node in scoped_nodes:
        records.append(_task_state_audit_record(session_id, node))
        if node.confirmation is not None:
            records.append(_confirmation_audit_record(session_id, node.confirmation))
        records.extend(
            _detail_audit_records(
                session_id,
                node.task_ref,
                task_projection=task_projection,
            )
        )
    records.extend(
        _message_audit_record(message)
        for message in messages
        if task_node_id is None or message.task_node_id == task_node_id
    )
    records.extend(_event_audit_records(session, event_provider, task_node_id=task_node_id))
    records.extend(_config_audit_records(session, config_provider, task_node_id=task_node_id))
    records.extend(_log_audit_records(session, log_provider, task_node_id=task_node_id))
    return _sort_audit_records(records)


def _sort_audit_records(records: Iterable[AuditRecord]) -> tuple[AuditRecord, ...]:
    by_id: dict[str, AuditRecord] = {}
    for record in records:
        by_id[record.id] = record
    return tuple(sorted(by_id.values(), key=lambda record: (record.occurred_at, record.id)))


def _event_audit_records(
    session: Session,
    provider: AuditEventProvider | None,
    *,
    task_node_id: str | None,
) -> tuple[AuditRecord, ...]:
    if provider is None:
        return ()
    try:
        return tuple(
            _event_audit_record(session.id, event, task_node_id=task_node_id)
            for event in provider.list_for_session(session, task_node_id=task_node_id)
        )
    except Exception as exc:  # noqa: BLE001 - Audit Page must degrade, not fail.
        return (
            _source_unavailable_record(
                session.id,
                source_name="EventStream",
                reason=f"{type(exc).__name__}: {exc}",
                task_node_id=task_node_id,
            ),
        )


def _config_audit_records(
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
            _source_unavailable_record(
                session.id,
                source_name="Config store",
                reason=f"{type(exc).__name__}: {exc}",
                task_node_id=task_node_id,
            ),
        )


def _log_audit_records(
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
            _source_unavailable_record(
                session.id,
                source_name="Log archive",
                reason=f"{type(exc).__name__}: {exc}",
                task_node_id=task_node_id,
            ),
        )


def _event_audit_record(
    session_id: str,
    event: BaseEvent,
    *,
    task_node_id: str | None,
) -> AuditRecord:
    if _is_audit_observation(event):
        return _audit_observation_record(session_id, event, task_node_id=task_node_id)
    if isinstance(event, BaseAction):
        return _action_event_record(session_id, event, task_node_id=task_node_id)
    if isinstance(event, BaseObservation):
        return _observation_event_record(session_id, event, task_node_id=task_node_id)
    return _generic_event_record(session_id, event, task_node_id=task_node_id)


def _action_event_record(
    session_id: str,
    event: BaseAction,
    *,
    task_node_id: str | None,
) -> AuditRecord:
    risk = float(getattr(type(event), "baseline_risk", 0.0))
    severity: AuditSeverity = "warning" if risk >= 0.3 else "info"
    return AuditRecord(
        id=f"record-event-action-{event.event_id}",
        scope=AuditActionScope(
            session_id=session_id,
            action_id=event.event_id,
            task_node_id=task_node_id,
        ),
        kind="action",
        filter_kind="actions",
        title=f"{event.kind} action",
        summary=_event_summary(event),
        actor=_action_actor(event),
        source_label="EventStream",
        occurred_at=event.timestamp,
        severity=severity,
        confidence="high",
        completeness="complete",
        task_node_id=task_node_id,
        action_id=event.event_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-event-action-{event.event_id}",
                kind="action",
                label=f"{event.kind} payload",
                summary=f"Durable Action event {event.event_id}.",
            ),
        ),
    )


def _observation_event_record(
    session_id: str,
    event: BaseObservation,
    *,
    task_node_id: str | None,
) -> AuditRecord:
    failed = event.success is False
    action_id = event.action_id or event.event_id
    return AuditRecord(
        id=f"record-event-observation-{event.event_id}",
        scope=AuditActionScope(
            session_id=session_id,
            action_id=action_id,
            task_node_id=task_node_id,
        ),
        kind="observation",
        filter_kind="actions",
        title=f"{event.kind} observation",
        summary=_event_summary(event),
        actor="tool",
        source_label="EventStream",
        occurred_at=event.timestamp,
        severity="danger" if failed else "success",
        confidence="high",
        verdict="failed" if failed else "passed",
        completeness="complete",
        task_node_id=task_node_id,
        action_id=action_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-event-observation-{event.event_id}",
                kind="observation",
                label=f"{event.kind} payload",
                summary=f"Durable Observation event {event.event_id}.",
            ),
        ),
    )


def _audit_observation_record(
    session_id: str,
    event: BaseEvent,
    *,
    task_node_id: str | None,
) -> AuditRecord:
    raw_verdict = getattr(event, "verdict", "inconclusive")
    verdict = _audit_verdict(raw_verdict)
    action_id = getattr(event, "action_id", None)
    audited_observation_id = getattr(event, "audited_observation_id", None)
    concerns = getattr(event, "concerns", ())
    concern_count = len(concerns) if isinstance(concerns, list | tuple) else 0
    summary = getattr(event, "rationale", None)
    if not isinstance(summary, str) or not summary.strip():
        summary = f"AuditAgent returned {raw_verdict}."
    if concern_count:
        summary = f"{summary} ({concern_count} concern(s).)"
    return AuditRecord(
        id=f"record-audit-verdict-{event.event_id}",
        scope=AuditActionScope(
            session_id=session_id,
            action_id=action_id or event.event_id,
            task_node_id=task_node_id,
        ),
        kind="audit_verdict",
        filter_kind="risks",
        title="AuditAgent verdict",
        summary=summary,
        actor="audit_agent",
        source_label="AuditAgent",
        occurred_at=event.timestamp,
        severity=_audit_verdict_severity(verdict),
        confidence="high" if verdict in {"passed", "failed"} else "medium",
        verdict=verdict,
        completeness="complete" if verdict in {"passed", "failed"} else "partial",
        task_node_id=task_node_id,
        action_id=action_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-audit-verdict-{event.event_id}",
                kind="audit_observation",
                label="AuditAgent observation",
                summary=summary,
            ),
        ),
        related_record_ids=tuple(
            record_id
            for record_id in (
                f"record-event-action-{action_id}" if isinstance(action_id, str) else None,
                (
                    f"record-event-observation-{audited_observation_id}"
                    if isinstance(audited_observation_id, str)
                    else None
                ),
            )
            if record_id is not None
        ),
        flags=AuditRecordFlags(partial=verdict == "inconclusive"),
    )


def _generic_event_record(
    session_id: str,
    event: BaseEvent,
    *,
    task_node_id: str | None,
) -> AuditRecord:
    return AuditRecord(
        id=f"record-event-{event.event_id}",
        scope=AuditSessionScope(session_id=session_id),
        kind="system",
        filter_kind="system",
        title=f"{event.kind} event",
        summary=_event_summary(event),
        actor="system",
        source_label="EventStream",
        occurred_at=event.timestamp,
        severity="info",
        confidence="high",
        completeness="complete",
        task_node_id=task_node_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-event-{event.event_id}",
                kind="event",
                label=f"{event.kind} payload",
                summary=f"Durable EventStream event {event.event_id}.",
            ),
        ),
    )


def _source_unavailable_record(
    session_id: str,
    *,
    source_name: str,
    reason: str,
    task_node_id: str | None,
) -> AuditRecord:
    token = _safe_token(source_name.lower())
    return AuditRecord(
        id=f"record-system-source-unavailable-{token}",
        scope=AuditSessionScope(session_id=session_id),
        kind="system",
        filter_kind="system",
        title=f"{source_name} unavailable",
        summary=f"{source_name} could not be read: {reason}",
        actor="system",
        source_label=source_name,
        occurred_at=datetime.now(UTC),
        severity="warning",
        confidence="high",
        verdict="warning",
        completeness="partial",
        task_node_id=task_node_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-system-source-unavailable-{token}",
                kind="event",
                label=f"{source_name} read failure",
                summary=reason[:500],
            ),
        ),
        flags=AuditRecordFlags(partial=True),
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


def _event_summary(event: BaseEvent) -> str:
    payload = event.to_dict()
    if isinstance(event, BaseAction):
        source = payload.get("source")
        suffix = f" from {source}" if isinstance(source, str) and source else ""
        return f"{event.kind} action{suffix} was recorded in EventStream."
    if isinstance(event, BaseObservation):
        outcome = "succeeded" if event.success else "failed"
        return f"{event.kind} observation {outcome}."
    return f"{event.kind} event was recorded in EventStream."


def _is_audit_observation(event: BaseEvent) -> bool:
    return event.kind == "AuditObservation"


def _action_actor(event: BaseAction) -> Literal["user", "agent", "system"]:
    source = event.source.lower().strip()
    if source == "user":
        return "user"
    if source == "system":
        return "system"
    return "agent"


def _audit_verdict(value: object) -> AuditVerdict:
    if value == "pass":
        return "passed"
    if value == "fail":
        return "failed"
    if value == "inconclusive":
        return "inconclusive"
    return "inconclusive"


def _audit_verdict_severity(verdict: AuditVerdict) -> AuditSeverity:
    if verdict == "passed":
        return "success"
    if verdict == "failed":
        return "danger"
    return "warning"


def _scoped_nodes(
    source: CoreTaskTreeView,
    *,
    task_node_id: str | None,
) -> tuple[CoreTaskCardView, ...]:
    if task_node_id is None:
        return source.nodes
    return tuple(node for node in source.nodes if node.task_ref.id == task_node_id)


def _detail_audit_records(
    session_id: str,
    task_ref: TaskRef,
    *,
    task_projection: TaskProjectionService,
) -> tuple[AuditRecord, ...]:
    try:
        detail = task_projection.get_task_detail(session_id, task_ref)
    except LookupError:
        return ()
    records: list[AuditRecord] = []
    for change in detail.file_changes:
        record_id = f"record-file-{change.change_id}"
        records.append(
            AuditRecord(
                id=record_id,
                scope=AuditFileScope(
                    session_id=session_id,
                    path=change.path,
                    task_node_id=change.owner_task_ref.id,
                ),
                kind="file_change",
                filter_kind="files",
                title="File change recorded",
                summary=change.summary,
                actor="tool",
                source_label="Task projection",
                occurred_at=change.recorded_at,
                severity="warning",
                confidence="medium",
                verdict="warning",
                completeness="partial",
                task_node_id=change.owner_task_ref.id,
                task_ref=change.owner_task_ref,
                file_path=change.path,
                evidence_refs=(
                    EvidenceRef(
                        id=f"evidence-{record_id}",
                        kind="file_change",
                        label="Projected file change",
                        summary=change.summary,
                    ),
                ),
                flags=AuditRecordFlags(partial=True),
            )
        )
    if detail.result_summary is not None:
        summary = detail.result_summary
        failed = summary.failure_reason is not None
        record_id = f"record-result-{summary.task_ref.kind}-{summary.task_ref.id}"
        records.append(
            AuditRecord(
                id=record_id,
                scope=AuditResultScope(
                    session_id=session_id,
                    result_id=f"result:{summary.task_ref.kind}:{summary.task_ref.id}",
                    task_node_id=summary.task_ref.id,
                ),
                kind="result",
                filter_kind="results",
                title="Task result available",
                summary=summary.summary,
                actor="agent",
                source_label="Task summary",
                occurred_at=summary.updated_at,
                severity="danger" if failed else "success",
                confidence="medium",
                verdict="failed" if failed else "passed",
                completeness="partial",
                task_node_id=summary.task_ref.id,
                task_ref=summary.task_ref,
                result_id=f"result:{summary.task_ref.kind}:{summary.task_ref.id}",
                evidence_refs=(
                    EvidenceRef(
                        id=f"evidence-{record_id}",
                        kind="result",
                        label="Projected task result",
                        summary=summary.summary,
                    ),
                ),
                flags=AuditRecordFlags(partial=True),
            )
        )
    return tuple(records)


def _task_state_audit_record(session_id: str, node: CoreTaskCardView) -> AuditRecord:
    record_id = f"record-task-{node.task_ref.kind}-{node.task_ref.id}"
    failed = node.status == "failed"
    return AuditRecord(
        id=record_id,
        scope=AuditTaskScope(
            session_id=session_id,
            task_node_id=node.task_ref.id,
            task_ref=node.task_ref,
        ),
        kind="action",
        filter_kind="actions",
        title="Task state projected",
        summary=f"{node.title} is {node.status}.",
        actor="system",
        source_label="Task projection",
        occurred_at=_source_generated_at_or_now(node),
        severity="danger" if failed else "info",
        confidence="medium",
        verdict="failed" if failed else None,
        completeness="partial",
        task_node_id=node.task_ref.id,
        task_ref=node.task_ref,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="event",
                label="Task projection record",
                summary=f"Task status is {node.status}.",
            ),
        ),
        flags=AuditRecordFlags(partial=True),
    )


def _source_generated_at_or_now(node: CoreTaskCardView) -> datetime:
    message_time = None if node.latest_message is None else node.latest_message.created_at
    file_time = None if node.file_summary is None else node.file_summary.recorded_at
    candidates = [candidate for candidate in (message_time, file_time) if candidate is not None]
    return max(candidates) if candidates else datetime.now(UTC)


def _confirmation_audit_record(
    session_id: str,
    confirmation: CoreConfirmationActionView,
) -> AuditRecord:
    record_id = f"record-confirmation-{confirmation.confirmation_id}"
    pending = confirmation.status == "pending"
    return AuditRecord(
        id=record_id,
        scope=AuditConfirmationScope(
            session_id=session_id,
            confirmation_id=confirmation.confirmation_id,
            task_node_id=confirmation.task_ref.id,
        ),
        kind="confirmation",
        filter_kind="confirmations",
        title="User confirmation required" if pending else "User confirmation resolved",
        summary=confirmation.prompt,
        actor="user",
        source_label="Task confirmation",
        severity="warning" if pending else "success",
        confidence="high",
        verdict="warning" if pending else "passed",
        completeness="complete",
        task_node_id=confirmation.task_ref.id,
        task_ref=confirmation.task_ref,
        confirmation_id=confirmation.confirmation_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="message",
                label="Confirmation prompt",
                summary=confirmation.prompt,
            ),
        ),
    )


def _message_audit_record(message: SessionMessageView) -> AuditRecord:
    record_id = f"record-message-{message.id}"
    task_ref = message.task_ref
    task_node_id = message.task_node_id
    return AuditRecord(
        id=record_id,
        scope=(
            AuditTaskScope(
                session_id=message.session_id,
                task_node_id=task_node_id,
                task_ref=task_ref,
            )
            if task_node_id is not None
            else AuditSessionScope(session_id=message.session_id)
        ),
        kind="message",
        filter_kind="system",
        title=message.title,
        summary=message.body,
        actor=_message_actor(message),
        source_label="Message stream",
        occurred_at=message.created_at,
        severity="warning" if message.kind == "actionable" else "info",
        confidence="medium",
        completeness="complete",
        task_node_id=task_node_id,
        task_ref=task_ref,
        confirmation_id=message.related_confirmation_id,
        action_id=message.related_command_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="message",
                label=message.title,
                summary=message.body,
            ),
        ),
    )


def _message_actor(message: SessionMessageView) -> Literal["user", "agent", "system"]:
    if message.title.lower().startswith("user"):
        return "user"
    if message.title.lower().startswith("system"):
        return "system"
    return "agent"


def _audit_scope(
    session_id: str,
    *,
    task_node_id: str | None,
    selected_task: TaskNodeCardView | None,
) -> AuditSessionScope | AuditTaskScope:
    if task_node_id is None:
        return AuditSessionScope(session_id=session_id)
    return AuditTaskScope(
        session_id=session_id,
        task_node_id=task_node_id,
        task_ref=None if selected_task is None else selected_task.task_ref,
    )


def _audit_entry_context(
    session_id: str,
    *,
    entry: str,
    task_node_id: str | None,
    selected_task: TaskNodeCardView | None,
    filter_kind: AuditFilterKind,
    record_id: str | None,
) -> AuditEntryContext:
    return AuditEntryContext(
        kind=entry,  # type: ignore[arg-type]
        session_id=session_id,
        task_node_id=task_node_id,
        task_ref=None if selected_task is None else selected_task.task_ref,
        source_route=_main_source_route(session_id, task_node_id=task_node_id),
        preferred_filter=filter_kind,
        preferred_record_id=record_id,
    )


def _audit_return_target(
    session: SessionSummary,
    *,
    task_node_id: str | None,
    record_id: str | None,
) -> MainPageReturnTarget:
    return MainPageReturnTarget(
        route_name="main.sessionFallback",
        session_id=session.id,
        project_id=session.project_id,
        workflow_id=session.workflow_id,
        task_node_id=task_node_id,
        focus="task" if task_node_id is not None else "session",
        record_id=record_id,
    )


def _main_source_route(session_id: str, *, task_node_id: str | None) -> str:
    if task_node_id is None:
        return f"/sessions/{session_id}"
    return f"/sessions/{session_id}?taskNodeId={task_node_id}"


def _selected_task(
    task_tree: TaskTreeView | None,
    task_node_id: str | None,
) -> TaskNodeCardView | None:
    if task_tree is None or task_node_id is None:
        return None
    for node in task_tree.nodes:
        if node.id == task_node_id:
            return node
    return None


def _audit_overview(records: Sequence[AuditRecord]) -> AuditOverview:
    counts = _audit_record_counts(records)
    important = tuple(record.id for record in _important_audit_records(records))
    hidden_count = sum(1 for record in records if record.flags.hidden)
    if not records:
        return AuditOverview(
            verdict="not_available",
            completeness="not_started",
            summary="No audit records exist for this scope yet.",
            record_counts=counts,
            important_record_ids=important,
            hidden_evidence_count=hidden_count,
            generated_by="projection",
        )
    if any(record.verdict == "failed" or record.severity == "danger" for record in records):
        return AuditOverview(
            verdict="failed",
            completeness="partial",
            summary="Audit projection found at least one failed or dangerous record.",
            key_issue="Review failed records before trusting this task.",
            record_counts=counts,
            important_record_ids=important,
            hidden_evidence_count=hidden_count,
            partial_reason=_AUDIT_PROJECTION_PARTIAL_REASON,
            generated_by="projection",
        )
    if any(record.flags.partial or record.verdict == "warning" for record in records):
        return AuditOverview(
            verdict="warning",
            completeness="partial",
            summary="Audit projection is available, but dedicated evidence aggregation is partial.",
            key_issue="Treat this as a projected audit until audit-agent evidence is connected.",
            record_counts=counts,
            important_record_ids=important,
            hidden_evidence_count=hidden_count,
            partial_reason=_AUDIT_PROJECTION_PARTIAL_REASON,
            generated_by="projection",
        )
    return AuditOverview(
        verdict="passed",
        completeness="complete",
        summary="Audit records are available for this scope.",
        record_counts=counts,
        important_record_ids=important,
        hidden_evidence_count=hidden_count,
        generated_by="projection",
    )


def _audit_record_counts(records: Sequence[AuditRecord]) -> dict[AuditFilterKind, int]:
    counts: dict[AuditFilterKind, int] = {
        kind: 0 for kind in _AUDIT_FILTER_LABELS
    }
    counts["all"] = len(records)
    for record in records:
        counts[record.filter_kind] = counts.get(record.filter_kind, 0) + 1
    return counts


def _important_audit_records(records: Sequence[AuditRecord]) -> tuple[AuditRecord, ...]:
    ordered = sorted(
        records,
        key=lambda record: (
            _severity_rank(record),
            0 if record.flags.partial else 1,
            record.occurred_at,
            record.id,
        ),
    )
    return tuple(ordered[:5])


def _severity_rank(record: AuditRecord) -> int:
    if record.severity == "danger" or record.verdict == "failed":
        return 0
    if record.severity == "warning" or record.verdict == "warning":
        return 1
    return 2


def _audit_filters(records: Sequence[AuditRecord]) -> tuple[AuditFilterView, ...]:
    counts = _audit_record_counts(records)
    return tuple(
        AuditFilterView(kind=kind, label=label, count=counts.get(kind, 0))
        for kind, label in _AUDIT_FILTER_LABELS.items()
    )


def _audit_page_state(
    all_records: Sequence[AuditRecord],
    filtered_records: Sequence[AuditRecord],
) -> AuditReadyPageState | AuditEmptyPageState | AuditPartialPageState:
    if not all_records:
        return AuditEmptyPageState(reason="No audit records exist for this scope.")
    if not filtered_records:
        return AuditEmptyPageState(reason="No audit records match the current filter.")
    if any(record.flags.partial for record in all_records):
        return AuditPartialPageState(reason=_AUDIT_PROJECTION_PARTIAL_REASON)
    return AuditReadyPageState()


def _effective_config(
    session: Session,
    records: Sequence[AuditRecord],
    provider: AuditConfigProvider | None,
) -> EffectiveConfigSummary:
    if provider is not None:
        try:
            provided = provider.get_effective_config(session, records=records)
        except Exception:  # noqa: BLE001 - config summary is advisory.
            provided = None
        if provided is not None:
            return provided
    return EffectiveConfigSummary(
        summary="Projection-only audit profile is active.",
        profile_label="Projection baseline",
        relevant_record_ids=tuple(record.id for record in _important_audit_records(records)),
    )


def _related_logs(
    session: Session | str,
    *,
    task_node_id: str | None,
    record_id: str | None,
    log_provider: AuditLogProvider | None = None,
) -> tuple[RelatedLogsLink, ...]:
    if isinstance(session, Session) and log_provider is not None:
        try:
            return log_provider.related_logs(
                session,
                task_node_id=task_node_id,
                record_id=record_id,
            )
        except Exception:  # noqa: BLE001 - keep the default disabled link.
            pass
    session_id = session.id if isinstance(session, Session) else session
    return (
        RelatedLogsLink(
            label="Related logs",
            href=f"/sessions/{session_id}/diagnostics/logs",
            filters={
                "sessionId": session_id,
                "taskNodeId": task_node_id,
                "recordId": record_id,
                "category": "audit",
            },
            enabled=False,
            disabled_reason="Log archive integration is not implemented yet.",
        ),
    )


def _filter_audit_records(
    records: Sequence[AuditRecord],
    *,
    filter_kind: AuditFilterKind,
    kind: AuditRecordKind | None,
    from_time: str | None,
    to_time: str | None,
) -> tuple[AuditRecord, ...]:
    start = _parse_optional_datetime(from_time, "from")
    end = _parse_optional_datetime(to_time, "to")
    filtered: list[AuditRecord] = []
    for record in records:
        if filter_kind != "all" and record.filter_kind != filter_kind:
            continue
        if kind is not None and record.kind != kind:
            continue
        if start is not None and record.occurred_at < start:
            continue
        if end is not None and record.occurred_at > end:
            continue
        filtered.append(record)
    return tuple(filtered)


def _page_audit_records(
    records: Sequence[AuditRecord],
    *,
    limit: int,
    cursor: str | None,
) -> tuple[tuple[AuditRecord, ...], str | None]:
    if limit < 1 or limit > 200:
        raise ValueError("audit record limit must be between 1 and 200")
    offset = _cursor_offset(cursor)
    page = tuple(records[offset : offset + limit])
    next_offset = offset + limit
    next_cursor = f"offset:{next_offset}" if next_offset < len(records) else None
    return page, next_cursor


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith("offset:"):
        raise ValueError("audit cursor must use offset:<number>")
    try:
        offset = int(cursor.removeprefix("offset:"))
    except ValueError as exc:
        raise ValueError("audit cursor offset must be an integer") from exc
    if offset < 0:
        raise ValueError("audit cursor offset must be non-negative")
    return offset


def _parse_optional_datetime(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"audit {name} timestamp must be ISO-8601") from exc


def _require_audit_record(
    records: Sequence[AuditRecord],
    record_id: str | None,
) -> AuditRecord:
    if record_id is None:
        raise LookupError("audit record id is required")
    for record in records:
        if record.id == record_id:
            return record
    raise LookupError("audit record not found")


def _require_evidence_ref(
    records: Sequence[AuditRecord],
    evidence_id: str,
) -> tuple[AuditRecord, EvidenceRef]:
    for record in records:
        for evidence_ref in record.evidence_refs:
            if evidence_ref.id == evidence_id:
                return record, evidence_ref
    raise LookupError("audit evidence not found")


def _audit_record_detail(
    record: AuditRecord,
    *,
    session: Session | None = None,
    log_provider: AuditLogProvider | None = None,
    payload_disclosure_service: AuditPayloadDisclosureService | None = None,
    include_evidence: bool,
    include_sanitized_payload: bool,
) -> AuditRecordDetail:
    evidence = (
        tuple(_evidence_summary(record, evidence_ref) for evidence_ref in record.evidence_refs)
        if include_evidence
        else ()
    )
    resolved_session = session
    disclosure_result = (
        payload_disclosure_service.build_record_payload(
            record,
            session=resolved_session,
            include_sanitized_payload=include_sanitized_payload,
        )
        if payload_disclosure_service is not None and resolved_session is not None
        else _no_payload(_record_partial_reason(record))
    )
    return AuditRecordDetail(
        **record.model_dump(),
        body=_record_detail_body(record),
        why_it_matters=_record_why_it_matters(record),
        outcome=_record_outcome(record),
        references=_record_references(record),
        evidence=evidence,
        disclosure=disclosure_result.disclosure,
        related_logs=_related_logs(
            resolved_session or _record_session_id(record),
            task_node_id=record.task_node_id,
            record_id=record.id,
            log_provider=log_provider,
        ),
        raw_payload=disclosure_result.payload,
    )


def _record_detail_body(record: AuditRecord) -> str:
    return f"{record.title}: {record.summary}"


def _record_session_id(record: AuditRecord) -> str:
    raw = getattr(record.scope, "session_id", None)
    return raw if isinstance(raw, str) else ""


def _record_why_it_matters(record: AuditRecord) -> str:
    if record.kind == "confirmation":
        return "User authorization decisions affect whether the task can safely proceed."
    if record.kind == "audit_verdict":
        return "AuditAgent verdicts explain whether executed code matched the declared intent."
    if record.kind in {"action", "observation"}:
        return "EventStream facts are the durable execution spine for replay and audit."
    if record.kind == "file_change":
        return "File changes must remain attributable to the Task that produced them."
    if record.kind == "result":
        return "Task results are the user's trust boundary for deciding whether work is done."
    if record.kind == "message":
        return "Messages explain how task context changed during the session."
    if record.kind == "config_change":
        return (
            "Effective configuration changes what the system records and how much "
            "detail is retained."
        )
    if record.kind == "log_evidence":
        return (
            "Logs help testers and advanced users inspect runtime behavior behind "
            "productized records."
        )
    return "This record helps reconstruct the Task lifecycle from user-facing facts."


def _record_outcome(record: AuditRecord) -> str | None:
    if record.verdict is None:
        return None
    return f"Projected verdict: {record.verdict}."


def _record_references(record: AuditRecord) -> tuple[AuditReference, ...]:
    references: list[AuditReference] = []
    if record.task_ref is not None:
        references.append(
            AuditReference(
                kind="task",
                label=f"Task {record.task_ref.id}",
                ref=ObjectRef(
                    kind=(
                        "draft_task"
                        if record.task_ref.kind == "draft"
                        else "published_task"
                    ),
                    id=record.task_ref.id,
                ),
            )
        )
    if record.confirmation_id is not None:
        references.append(
            AuditReference(
                kind="confirmation",
                label=f"Confirmation {record.confirmation_id}",
                ref=ObjectRef(kind="message", id=record.confirmation_id),
            )
        )
    if record.action_id is not None:
        references.append(
            AuditReference(
                kind="action",
                label=f"Action {record.action_id}",
            )
        )
    if record.config_key is not None:
        references.append(
            AuditReference(kind="config", label=f"Config {record.config_key}")
        )
    if record.file_path is not None:
        references.append(AuditReference(kind="file", label=record.file_path))
    if record.result_id is not None:
        references.append(AuditReference(kind="result", label=record.result_id))
    return tuple(references)


def _evidence_summary(
    record: AuditRecord,
    evidence_ref: EvidenceRef,
) -> EvidenceSummary:
    return EvidenceSummary(
        **evidence_ref.model_dump(),
        source=_evidence_source(record, evidence_ref),
        occurred_at=record.occurred_at,
    )


def _evidence_source(
    record: AuditRecord,
    evidence_ref: EvidenceRef,
) -> AuditEvidenceSource:
    if evidence_ref.kind in {"action", "observation"}:
        return "event_stream"
    if evidence_ref.kind == "event":
        return "event_stream" if record.source_label == "EventStream" else "task_projection"
    if evidence_ref.kind == "audit_observation":
        return "audit_agent"
    if evidence_ref.kind == "message":
        return "message_stream" if record.source_label == "Message stream" else "task_projection"
    if evidence_ref.kind == "config_snapshot":
        return "config_store"
    if evidence_ref.kind == "log_excerpt":
        return "log_archive"
    return "task_projection"


def _evidence_detail(
    record: AuditRecord,
    evidence_ref: EvidenceRef,
    *,
    session: Session | None = None,
    payload_disclosure_service: AuditPayloadDisclosureService | None = None,
    include_sanitized_payload: bool,
) -> EvidenceDetail:
    summary = _evidence_summary(record, evidence_ref)
    disclosure_result = (
        payload_disclosure_service.build_evidence_payload(
            record,
            evidence_ref,
            session=session,
            include_sanitized_payload=include_sanitized_payload,
        )
        if payload_disclosure_service is not None and session is not None
        else _no_payload(_record_partial_reason(record))
    )
    return EvidenceDetail(
        **summary.model_dump(),
        body=f"{evidence_ref.label}: {evidence_ref.summary}",
        sanitized_payload=disclosure_result.payload,
        disclosure=disclosure_result.disclosure,
    )


def _audit_filter_kind(value: str) -> AuditFilterKind:
    if value not in _AUDIT_FILTER_KINDS:
        raise ValueError(f"unsupported audit filter: {value!r}")
    return value


def _audit_record_kind(value: str | None) -> AuditRecordKind | None:
    if value is None:
        return None
    if value not in _AUDIT_RECORD_KINDS:
        raise ValueError(f"unsupported audit record kind: {value!r}")
    return value  # type: ignore[return-value]


def _audit_entry_kind(value: str | None, *, task_node_id: str | None) -> str:
    if value is None:
        return "from_task" if task_node_id is not None else "from_session"
    if value not in _AUDIT_ENTRY_KINDS:
        raise ValueError(f"unsupported audit entry: {value!r}")
    return value


