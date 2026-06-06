"""Audit Page projection helpers and workspace-backed evidence providers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from taskweavn.core.session import Session
from taskweavn.server.ui_contract.audit_detail_projection import (
    _audit_record_detail as _audit_record_detail,
)
from taskweavn.server.ui_contract.audit_detail_projection import (
    _evidence_detail as _evidence_detail,
)
from taskweavn.server.ui_contract.audit_detail_projection import (
    _related_logs as _related_logs,
)
from taskweavn.server.ui_contract.audit_detail_projection import (
    _require_audit_record as _require_audit_record,
)
from taskweavn.server.ui_contract.audit_detail_projection import (
    _require_evidence_ref as _require_evidence_ref,
)
from taskweavn.server.ui_contract.audit_event_records import event_audit_records
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_entry_context as _audit_entry_context,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_entry_kind as _audit_entry_kind,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_filter_kind as _audit_filter_kind,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_filters as _audit_filters,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_overview as _audit_overview,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_page_state as _audit_page_state,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_record_kind as _audit_record_kind,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_return_target as _audit_return_target,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _audit_scope as _audit_scope,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _effective_config as _effective_config,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _filter_audit_records as _filter_audit_records,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _page_audit_records as _page_audit_records,
)
from taskweavn.server.ui_contract.audit_page_state import (
    _selected_task as _selected_task,
)
from taskweavn.server.ui_contract.audit_source_providers import (
    WorkspaceAuditConfigProvider as WorkspaceAuditConfigProvider,
)
from taskweavn.server.ui_contract.audit_source_providers import (
    WorkspaceAuditLogProvider as WorkspaceAuditLogProvider,
)
from taskweavn.server.ui_contract.audit_source_providers import (
    config_audit_records,
    log_audit_records,
)
from taskweavn.server.ui_contract.audit_timeline_records import timeline_audit_records
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditConfigProvider,
    AuditEventProvider,
    AuditLogProvider,
)
from taskweavn.server.ui_contract.view_models import (
    AuditConfirmationScope,
    AuditFileScope,
    AuditRecord,
    AuditRecordFlags,
    AuditResultScope,
    AuditSessionScope,
    AuditTaskScope,
    EvidenceRef,
    ProjectSummary,
    SessionMessageView,
    SessionSummary,
    TaskNodeCardView,
    TaskTreeView,
    WorkflowSummary,
)
from taskweavn.task.models import TaskRef
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.timeline import TaskInteractionTimelineService
from taskweavn.task.views import ConfirmationActionView as CoreConfirmationActionView
from taskweavn.task.views import TaskCardView as CoreTaskCardView
from taskweavn.task.views import TaskDetailView as CoreTaskDetailView
from taskweavn.task.views import TaskTreeView as CoreTaskTreeView


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


def _audit_records_from_projection(
    source: CoreTaskTreeView,
    *,
    session: Session,
    session_id: str,
    task_node_id: str | None,
    messages: Sequence[SessionMessageView],
    task_projection: TaskProjectionService,
    task_timeline_service: TaskInteractionTimelineService | None,
    event_provider: AuditEventProvider | None,
    config_provider: AuditConfigProvider | None,
    log_provider: AuditLogProvider | None,
) -> tuple[AuditRecord, ...]:
    records: list[AuditRecord] = []
    scoped_nodes = _scoped_nodes(source, task_node_id=task_node_id)
    for node in scoped_nodes:
        detail = _task_detail(
            session_id,
            node.task_ref,
            task_projection=task_projection,
        )
        records.append(_task_state_audit_record(session_id, node))
        if node.confirmation is not None:
            records.append(_confirmation_audit_record(session_id, node.confirmation))
        records.extend(_detail_audit_records(session_id, detail))
        if task_timeline_service is not None:
            records.extend(
                timeline_audit_records(
                    session_id,
                    node.task_ref,
                    task_detail=detail,
                    timeline_service=task_timeline_service,
                )
            )
    records.extend(
        _message_audit_record(message)
        for message in messages
        if task_node_id is None or message.task_node_id == task_node_id
    )
    records.extend(event_audit_records(session, event_provider, task_node_id=task_node_id))
    records.extend(config_audit_records(session, config_provider, task_node_id=task_node_id))
    records.extend(log_audit_records(session, log_provider, task_node_id=task_node_id))
    return _sort_audit_records(records)


def _sort_audit_records(records: Iterable[AuditRecord]) -> tuple[AuditRecord, ...]:
    by_id: dict[str, AuditRecord] = {}
    for record in records:
        by_id[record.id] = record
    return tuple(sorted(by_id.values(), key=lambda record: (record.occurred_at, record.id)))


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
    detail: CoreTaskDetailView | None,
) -> tuple[AuditRecord, ...]:
    if detail is None:
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


def _task_detail(
    session_id: str,
    task_ref: TaskRef,
    *,
    task_projection: TaskProjectionService,
) -> CoreTaskDetailView | None:
    try:
        return task_projection.get_task_detail(session_id, task_ref)
    except LookupError:
        return None


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
