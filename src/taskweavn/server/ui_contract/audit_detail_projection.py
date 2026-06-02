"""Audit Page selected-record and evidence detail projection."""

from __future__ import annotations

from collections.abc import Sequence

from taskweavn.core.session import Session
from taskweavn.server.ui_contract.audit_disclosure import _no_payload, _record_partial_reason
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditLogProvider,
    AuditPayloadDisclosureService,
)
from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.server.ui_contract.view_models import (
    AuditEvidenceSource,
    AuditRecord,
    AuditRecordDetail,
    AuditReference,
    EvidenceDetail,
    EvidenceRef,
    EvidenceSummary,
    RelatedLogsLink,
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


__all__ = [
    "_audit_record_detail",
    "_evidence_detail",
    "_related_logs",
    "_require_audit_record",
    "_require_evidence_ref",
]
