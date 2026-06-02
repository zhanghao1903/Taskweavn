"""EventStream-backed Audit Page record projection helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from taskweavn.core.session import Session
from taskweavn.server.ui_contract.gateway_protocols import AuditEventProvider
from taskweavn.server.ui_contract.view_models import (
    AuditActionScope,
    AuditRecord,
    AuditRecordFlags,
    AuditSessionScope,
    AuditSeverity,
    AuditVerdict,
    EvidenceRef,
)
from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation

_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def event_audit_records(
    session: Session,
    provider: AuditEventProvider | None,
    *,
    task_node_id: str | None,
) -> tuple[AuditRecord, ...]:
    if provider is None:
        return ()
    try:
        return tuple(
            event_audit_record(session.id, event, task_node_id=task_node_id)
            for event in provider.list_for_session(session, task_node_id=task_node_id)
        )
    except Exception as exc:  # noqa: BLE001 - Audit Page must degrade, not fail.
        return (
            source_unavailable_record(
                session.id,
                source_name="EventStream",
                reason=f"{type(exc).__name__}: {exc}",
                task_node_id=task_node_id,
            ),
        )


def event_audit_record(
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


def source_unavailable_record(
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


def _safe_token(value: str) -> str:
    return _ID_SAFE_RE.sub("-", value).strip("-") or "item"


__all__ = [
    "event_audit_record",
    "event_audit_records",
    "source_unavailable_record",
]
