"""Task timeline to Audit Page record projection."""

from __future__ import annotations

import re

from taskweavn.server.ui_contract.audit_event_records import source_unavailable_record
from taskweavn.server.ui_contract.view_models import (
    AuditActorKind,
    AuditConfirmationScope,
    AuditFileScope,
    AuditRecord,
    AuditRecordFlags,
    AuditResultScope,
    AuditTaskScope,
    EvidenceRef,
)
from taskweavn.task.models import TaskRef
from taskweavn.task.timeline import TaskInteractionEntry, TaskInteractionTimelineService
from taskweavn.task.views import TaskDetailView, TaskFileChangeSummary, TaskSummaryView

_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def timeline_audit_records(
    session_id: str,
    task_ref: TaskRef,
    *,
    task_detail: TaskDetailView | None,
    timeline_service: TaskInteractionTimelineService,
) -> tuple[AuditRecord, ...]:
    """Project timeline entries into existing Audit record shapes."""

    try:
        timeline = timeline_service.get_timeline(
            session_id,
            task_ref,
            include_subtree=True,
        )
    except Exception as exc:  # noqa: BLE001 - Audit Page must degrade, not fail.
        return (
            source_unavailable_record(
                session_id,
                source_name="Task timeline",
                reason=type(exc).__name__,
                task_node_id=task_ref.id,
            ),
        )

    changes_by_id = _file_changes_by_id(task_detail)
    summary = None if task_detail is None else task_detail.result_summary
    records: list[AuditRecord] = []
    for entry in timeline.entries:
        record = _timeline_entry_record(
            entry,
            file_changes_by_id=changes_by_id,
            result_summary=summary,
        )
        if record is not None:
            records.append(record)
    return tuple(records)


def _timeline_entry_record(
    entry: TaskInteractionEntry,
    *,
    file_changes_by_id: dict[str, TaskFileChangeSummary],
    result_summary: TaskSummaryView | None,
) -> AuditRecord | None:
    if entry.source == "draft":
        return _draft_record(entry)
    if entry.source == "message":
        return _message_record(entry)
    if entry.source == "confirmation":
        return _confirmation_record(entry)
    if entry.source == "file":
        change = file_changes_by_id.get(entry.payload_ref or "")
        return _file_record(entry, change=change)
    if entry.source == "summary":
        return _result_record(entry, summary=result_summary)
    # EventStream actions/observations stay on the typed EventStream provider.
    return None


def _draft_record(entry: TaskInteractionEntry) -> AuditRecord:
    record_id = f"record-timeline-draft-{_safe_token(entry.entry_id)}"
    return AuditRecord(
        id=record_id,
        scope=AuditTaskScope(
            session_id=entry.session_id,
            task_node_id=entry.task_ref.id,
            task_ref=entry.task_ref,
        ),
        kind="system",
        filter_kind="system",
        title=_draft_title(entry),
        summary=entry.summary,
        actor=_actor(entry, default="system"),
        source_label="Task projection",
        occurred_at=entry.occurred_at,
        severity="info",
        confidence="medium",
        completeness="partial",
        task_node_id=entry.task_ref.id,
        task_ref=entry.task_ref,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="event",
                label="Draft timeline entry",
                summary=entry.summary,
            ),
        ),
        flags=AuditRecordFlags(partial=True),
    )


def _message_record(entry: TaskInteractionEntry) -> AuditRecord:
    message_id = entry.payload_ref or _safe_token(entry.entry_id)
    record_id = f"record-message-{message_id}"
    return AuditRecord(
        id=record_id,
        scope=AuditTaskScope(
            session_id=entry.session_id,
            task_node_id=entry.task_ref.id,
            task_ref=entry.task_ref,
        ),
        kind="message",
        filter_kind="system",
        title=_message_title(entry),
        summary=entry.summary,
        actor=_actor(entry, default="agent"),
        source_label="Message stream",
        occurred_at=entry.occurred_at,
        severity="info",
        confidence="medium",
        completeness="complete",
        task_node_id=entry.task_ref.id,
        task_ref=entry.task_ref,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="message",
                label="Task message",
                summary=entry.summary,
            ),
        ),
    )


def _confirmation_record(entry: TaskInteractionEntry) -> AuditRecord:
    confirmation_id = entry.payload_ref or _safe_token(entry.entry_id)
    record_id = f"record-confirmation-{confirmation_id}"
    resolved = "resolved" in entry.kind
    return AuditRecord(
        id=record_id,
        scope=AuditConfirmationScope(
            session_id=entry.session_id,
            confirmation_id=confirmation_id,
            task_node_id=entry.task_ref.id,
        ),
        kind="confirmation",
        filter_kind="confirmations",
        title="User confirmation resolved" if resolved else "User confirmation required",
        summary=entry.summary,
        actor="user",
        source_label="Message stream",
        occurred_at=entry.occurred_at,
        severity="success" if resolved else "warning",
        confidence="high",
        verdict="passed" if resolved else "warning",
        completeness="complete",
        task_node_id=entry.task_ref.id,
        task_ref=entry.task_ref,
        confirmation_id=confirmation_id,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="message",
                label="Confirmation message",
                summary=entry.summary,
            ),
        ),
    )


def _file_record(
    entry: TaskInteractionEntry,
    *,
    change: TaskFileChangeSummary | None,
) -> AuditRecord:
    change_id = change.change_id if change is not None else entry.payload_ref
    record_id = f"record-file-{change_id or _safe_token(entry.entry_id)}"
    owner_ref = change.owner_task_ref if change is not None else entry.task_ref
    path = change.path if change is not None else _file_path_from_summary(entry.summary)
    summary = change.summary if change is not None else entry.summary
    return AuditRecord(
        id=record_id,
        scope=AuditFileScope(
            session_id=entry.session_id,
            path=path,
            task_node_id=owner_ref.id,
        ),
        kind="file_change",
        filter_kind="files",
        title="File change recorded",
        summary=summary,
        actor="tool",
        source_label="Task projection",
        occurred_at=change.recorded_at if change is not None else entry.occurred_at,
        severity="warning",
        confidence="medium",
        verdict="warning",
        completeness="partial",
        task_node_id=owner_ref.id,
        task_ref=owner_ref,
        file_path=path,
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="file_change",
                label="Timeline file change",
                summary=summary,
            ),
        ),
        flags=AuditRecordFlags(partial=True),
    )


def _result_record(
    entry: TaskInteractionEntry,
    *,
    summary: TaskSummaryView | None,
) -> AuditRecord:
    task_ref = summary.task_ref if summary is not None else entry.task_ref
    failed = summary.failure_reason is not None if summary is not None else False
    record_id = f"record-result-{task_ref.kind}-{task_ref.id}"
    body = summary.summary if summary is not None else entry.summary
    return AuditRecord(
        id=record_id,
        scope=AuditResultScope(
            session_id=entry.session_id,
            result_id=f"result:{task_ref.kind}:{task_ref.id}",
            task_node_id=task_ref.id,
        ),
        kind="result",
        filter_kind="results",
        title="Task result available",
        summary=body,
        actor="agent",
        source_label="Task summary",
        occurred_at=summary.updated_at if summary is not None else entry.occurred_at,
        severity="danger" if failed else "success",
        confidence="medium",
        verdict="failed" if failed else "passed",
        completeness="partial",
        task_node_id=task_ref.id,
        task_ref=task_ref,
        result_id=f"result:{task_ref.kind}:{task_ref.id}",
        evidence_refs=(
            EvidenceRef(
                id=f"evidence-{record_id}",
                kind="result",
                label="Timeline task result",
                summary=body,
            ),
        ),
        flags=AuditRecordFlags(partial=True),
    )


def _file_changes_by_id(
    task_detail: TaskDetailView | None,
) -> dict[str, TaskFileChangeSummary]:
    if task_detail is None:
        return {}
    return {change.change_id: change for change in task_detail.file_changes}


def _actor(entry: TaskInteractionEntry, *, default: AuditActorKind) -> AuditActorKind:
    actor = (entry.actor or "").strip().lower()
    if actor in {"user", "agent", "tool", "system", "audit_agent"}:
        return actor  # type: ignore[return-value]
    if "user" in actor:
        return "user"
    if "tool" in actor:
        return "tool"
    if "audit" in actor:
        return "audit_agent"
    if "system" in actor:
        return "system"
    if actor:
        return "agent"
    return default


def _draft_title(entry: TaskInteractionEntry) -> str:
    if entry.kind == "draft.created":
        return "Draft task created"
    if entry.kind == "draft.published":
        return "Draft task published"
    return "Draft task updated"


def _message_title(entry: TaskInteractionEntry) -> str:
    actor = _actor(entry, default="agent")
    if actor == "user":
        return "User message"
    if actor == "system":
        return "System message"
    return "Agent message"


def _file_path_from_summary(summary: str) -> str:
    path = summary.split(":", 1)[0].strip()
    return path or "unknown"


def _safe_token(value: str) -> str:
    return _ID_SAFE_RE.sub("-", value).strip("-") or "item"


__all__ = ["timeline_audit_records"]
