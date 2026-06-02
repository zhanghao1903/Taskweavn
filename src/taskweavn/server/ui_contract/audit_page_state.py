"""Audit Page state, filtering, and navigation projection."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from taskweavn.core.session import Session
from taskweavn.server.ui_contract.gateway_protocols import AuditConfigProvider
from taskweavn.server.ui_contract.view_models import (
    AuditEmptyPageState,
    AuditEntryContext,
    AuditFilterKind,
    AuditFilterView,
    AuditOverview,
    AuditPartialPageState,
    AuditReadyPageState,
    AuditRecord,
    AuditRecordKind,
    AuditSessionScope,
    AuditTaskScope,
    EffectiveConfigSummary,
    MainPageReturnTarget,
    SessionSummary,
    TaskNodeCardView,
    TaskTreeView,
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
    counts: dict[AuditFilterKind, int] = {kind: 0 for kind in _AUDIT_FILTER_LABELS}
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


__all__ = [
    "_audit_entry_context",
    "_audit_entry_kind",
    "_audit_filter_kind",
    "_audit_filters",
    "_audit_overview",
    "_audit_page_state",
    "_audit_record_kind",
    "_audit_return_target",
    "_audit_scope",
    "_effective_config",
    "_filter_audit_records",
    "_page_audit_records",
    "_selected_task",
]
