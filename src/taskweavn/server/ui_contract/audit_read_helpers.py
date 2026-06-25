"""Audit read helpers used by the UI query gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from taskweavn.server.ui_contract.audit_projection import (
    _audit_entry_context,
    _audit_entry_kind,
    _audit_filter_kind,
    _audit_filters,
    _audit_overview,
    _audit_page_state,
    _audit_record_detail,
    _audit_record_kind,
    _audit_records_from_projection,
    _audit_return_target,
    _audit_scope,
    _AuditProjectionBundle,
    _effective_config,
    _evidence_detail,
    _filter_audit_records,
    _normalize_audit_record_task_identity,
    _page_audit_records,
    _related_logs,
    _require_audit_record,
    _require_evidence_ref,
)
from taskweavn.server.ui_contract.envelopes import QueryResponse
from taskweavn.server.ui_contract.errors import bad_request, internal_error, not_found
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditConfigProvider,
    AuditEventProvider,
    AuditLogProvider,
    AuditPayloadDisclosureService,
    ProjectProvider,
    SessionReader,
    WorkflowProvider,
)
from taskweavn.server.ui_contract.main_page_read_helpers import (
    _confirmations_from_tree,
    _derive_session_status,
    _map_optional_task_tree,
    _merge_messages,
    _messages_from_tree,
    _request_id,
    _session_summary,
)
from taskweavn.server.ui_contract.plan_projection import PlanProjectionService
from taskweavn.server.ui_contract.plan_read_helpers import (
    active_stored_plan,
    audit_task_read_context,
)
from taskweavn.server.ui_contract.snapshots import AuditPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    AuditPageRequestView,
    AuditPermissions,
    AuditRecordDetail,
    AuditRecordsResult,
    EvidenceDetail,
    SessionMessageView,
)
from taskweavn.task.plan_stores import PlanStore
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore
from taskweavn.task.timeline import TaskInteractionTimelineService


@dataclass(frozen=True, kw_only=True)
class AuditReadDependencies:
    session_reader: SessionReader
    task_projection: TaskProjectionService
    authoring_state_store: AuthoringStateStore | None
    plan_store: PlanStore | None
    plan_projection: PlanProjectionService
    project_provider: ProjectProvider
    workflow_provider: WorkflowProvider
    task_timeline_service: TaskInteractionTimelineService | None
    audit_event_provider: AuditEventProvider | None
    audit_config_provider: AuditConfigProvider | None
    audit_log_provider: AuditLogProvider | None
    audit_payload_disclosure_service: AuditPayloadDisclosureService
    session_messages: Callable[[str], tuple[SessionMessageView, ...]]


def get_audit_snapshot_response(
    session_id: str,
    *,
    cursor: str | None,
    deps: AuditReadDependencies,
    entry: str | None,
    filter_kind: str,
    include_detail: bool | None,
    limit: int,
    record_id: str | None,
    request_id: str | None,
    task_node_id: str | None,
) -> QueryResponse[AuditPageSnapshot]:
    try:
        checked_filter = _audit_filter_kind(filter_kind)
        checked_entry = _audit_entry_kind(entry, task_node_id=task_node_id)
        bundle = audit_projection_bundle(session_id, deps=deps, task_node_id=task_node_id)
        filtered = _filter_audit_records(
            bundle.records,
            filter_kind=checked_filter,
            kind=None,
            from_time=None,
            to_time=None,
        )
        page_records, next_cursor = _page_audit_records(
            filtered,
            limit=limit,
            cursor=cursor,
        )
        should_include_detail = (
            record_id is not None if include_detail is None else include_detail
        )
        related_logs = _related_logs(
            bundle.session,
            task_node_id=bundle.record_task_node_id,
            record_id=record_id,
            log_provider=deps.audit_log_provider,
        )
        selected_record = (
            _audit_record_detail(
                _require_audit_record(bundle.records, record_id),
                session=bundle.session,
                log_provider=deps.audit_log_provider,
                payload_disclosure_service=deps.audit_payload_disclosure_service,
                include_evidence=True,
                include_sanitized_payload=False,
            )
            if record_id is not None and should_include_detail
            else None
        )
        snapshot = AuditPageSnapshot(
            request=AuditPageRequestView(
                filter=checked_filter,
                record_id=record_id,
                include_detail=should_include_detail,
                limit=limit,
                cursor=cursor,
            ),
            scope=_audit_scope(
                bundle.session.id,
                task_node_id=task_node_id,
                selected_task=bundle.selected_task,
            ),
            entry_context=_audit_entry_context(
                bundle.session.id,
                entry=checked_entry,
                task_node_id=task_node_id,
                selected_task=bundle.selected_task,
                filter_kind=checked_filter,
                record_id=record_id,
            ),
            return_target=_audit_return_target(
                bundle.session_summary,
                task_node_id=task_node_id,
                record_id=record_id,
            ),
            project=bundle.project,
            workflow=bundle.workflow,
            session=bundle.session_summary,
            selected_task=bundle.selected_task,
            overview=_audit_overview(bundle.records),
            filters=_audit_filters(bundle.records),
            records=page_records,
            selected_record=selected_record,
            effective_config=_effective_config(
                bundle.session,
                bundle.records,
                deps.audit_config_provider,
            ),
            related_logs=related_logs,
            permissions=AuditPermissions(
                can_open_related_logs=any(link.enabled for link in related_logs),
            ),
            page_state=_audit_page_state(bundle.records, filtered),
            cursor=next_cursor,
        )
        return QueryResponse[AuditPageSnapshot](
            request_id=request_id or _request_id("audit.snapshot", session_id),
            ok=True,
            data=snapshot,
            error=None,
            cursor=snapshot.cursor,
        )
    except LookupError as exc:
        return QueryResponse[AuditPageSnapshot](
            request_id=request_id or _request_id("audit.snapshot", session_id),
            ok=False,
            data=None,
            error=not_found(str(exc), session_id=session_id),
            cursor=None,
        )
    except ValueError as exc:
        return QueryResponse[AuditPageSnapshot](
            request_id=request_id or _request_id("audit.snapshot", session_id),
            ok=False,
            data=None,
            error=bad_request(str(exc), session_id=session_id),
            cursor=None,
        )
    except Exception as exc:
        return QueryResponse[AuditPageSnapshot](
            request_id=request_id or _request_id("audit.snapshot", session_id),
            ok=False,
            data=None,
            error=internal_error(
                "Unable to load audit snapshot",
                error_type=type(exc).__name__,
            ),
            cursor=None,
        )


def list_audit_records_response(
    session_id: str,
    *,
    cursor: str | None,
    deps: AuditReadDependencies,
    filter_kind: str,
    from_time: str | None,
    include_hidden_reasons: bool,
    kind: str | None,
    limit: int,
    request_id: str | None,
    task_node_id: str | None,
    to_time: str | None,
) -> QueryResponse[AuditRecordsResult]:
    try:
        del include_hidden_reasons
        checked_filter = _audit_filter_kind(filter_kind)
        checked_kind = _audit_record_kind(kind)
        bundle = audit_projection_bundle(session_id, deps=deps, task_node_id=task_node_id)
        filtered = _filter_audit_records(
            bundle.records,
            filter_kind=checked_filter,
            kind=checked_kind,
            from_time=from_time,
            to_time=to_time,
        )
        page_records, next_cursor = _page_audit_records(
            filtered,
            limit=limit,
            cursor=cursor,
        )
        return QueryResponse[AuditRecordsResult](
            request_id=request_id or _request_id("audit.records", session_id),
            ok=True,
            data=AuditRecordsResult(
                records=page_records,
                next_cursor=next_cursor,
                total_count=len(filtered),
            ),
            error=None,
            cursor=next_cursor,
        )
    except LookupError as exc:
        return QueryResponse[AuditRecordsResult](
            request_id=request_id or _request_id("audit.records", session_id),
            ok=False,
            data=None,
            error=not_found(str(exc), session_id=session_id),
            cursor=None,
        )
    except ValueError as exc:
        return QueryResponse[AuditRecordsResult](
            request_id=request_id or _request_id("audit.records", session_id),
            ok=False,
            data=None,
            error=bad_request(str(exc), session_id=session_id),
            cursor=None,
        )
    except Exception as exc:
        return QueryResponse[AuditRecordsResult](
            request_id=request_id or _request_id("audit.records", session_id),
            ok=False,
            data=None,
            error=internal_error(
                "Unable to list audit records",
                error_type=type(exc).__name__,
            ),
            cursor=None,
        )


def get_audit_record_detail_response(
    session_id: str,
    record_id: str,
    *,
    deps: AuditReadDependencies,
    include_evidence: bool,
    include_sanitized_payload: bool,
    request_id: str | None,
) -> QueryResponse[AuditRecordDetail]:
    try:
        bundle = audit_projection_bundle(session_id, deps=deps, task_node_id=None)
        record = _require_audit_record(bundle.records, record_id)
        return QueryResponse[AuditRecordDetail](
            request_id=request_id or _request_id("audit.record", record_id),
            ok=True,
            data=_audit_record_detail(
                record,
                session=bundle.session,
                log_provider=deps.audit_log_provider,
                payload_disclosure_service=deps.audit_payload_disclosure_service,
                include_evidence=include_evidence,
                include_sanitized_payload=include_sanitized_payload,
            ),
            error=None,
            cursor=None,
        )
    except LookupError as exc:
        return QueryResponse[AuditRecordDetail](
            request_id=request_id or _request_id("audit.record", record_id),
            ok=False,
            data=None,
            error=not_found(str(exc), session_id=session_id, record_id=record_id),
            cursor=None,
        )
    except Exception as exc:
        return QueryResponse[AuditRecordDetail](
            request_id=request_id or _request_id("audit.record", record_id),
            ok=False,
            data=None,
            error=internal_error(
                "Unable to load audit record detail",
                error_type=type(exc).__name__,
            ),
            cursor=None,
        )


def get_evidence_detail_response(
    session_id: str,
    evidence_id: str,
    *,
    deps: AuditReadDependencies,
    include_sanitized_payload: bool,
    request_id: str | None,
) -> QueryResponse[EvidenceDetail]:
    try:
        bundle = audit_projection_bundle(session_id, deps=deps, task_node_id=None)
        record, evidence_ref = _require_evidence_ref(bundle.records, evidence_id)
        return QueryResponse[EvidenceDetail](
            request_id=request_id or _request_id("audit.evidence", evidence_id),
            ok=True,
            data=_evidence_detail(
                record,
                evidence_ref,
                session=bundle.session,
                payload_disclosure_service=deps.audit_payload_disclosure_service,
                include_sanitized_payload=include_sanitized_payload,
            ),
            error=None,
            cursor=None,
        )
    except LookupError as exc:
        return QueryResponse[EvidenceDetail](
            request_id=request_id or _request_id("audit.evidence", evidence_id),
            ok=False,
            data=None,
            error=not_found(str(exc), session_id=session_id, evidence_id=evidence_id),
            cursor=None,
        )
    except Exception as exc:
        return QueryResponse[EvidenceDetail](
            request_id=request_id or _request_id("audit.evidence", evidence_id),
            ok=False,
            data=None,
            error=internal_error(
                "Unable to load evidence detail",
                error_type=type(exc).__name__,
            ),
            cursor=None,
        )


def audit_projection_bundle(
    session_id: str,
    *,
    deps: AuditReadDependencies,
    task_node_id: str | None,
) -> _AuditProjectionBundle:
    session = deps.session_reader.get(session_id)
    if session is None:
        raise LookupError("session not found")

    source_tree = deps.task_projection.list_task_tree(session.id)
    task_tree = _map_optional_task_tree(
        source_tree,
        authoring_state_store=deps.authoring_state_store,
    )
    stored_plan = active_stored_plan(
        session.id,
        plan_store=deps.plan_store,
        authoring_state_store=deps.authoring_state_store,
    )
    audit_context = audit_task_read_context(
        task_node_id=task_node_id,
        legacy_task_tree=task_tree,
        stored_plan=stored_plan,
        plan_projection=deps.plan_projection,
    )
    task_tree = audit_context.task_tree
    selected_task = audit_context.selected_task
    if task_node_id is not None and selected_task is None:
        raise LookupError("task not found")

    project = deps.project_provider.get_project()
    workflow = deps.workflow_provider.get_workflow(session)
    confirmations = _confirmations_from_tree(source_tree, session_id=session.id)
    messages = _merge_messages(
        _messages_from_tree(source_tree),
        deps.session_messages(session.id),
    )
    session_summary = _session_summary(
        session,
        project=project,
        workflow=workflow,
        status=_derive_session_status(
            session,
            task_tree=task_tree,
            confirmations=confirmations,
            messages=messages,
        ),
    )
    records = _audit_records_from_projection(
        source_tree,
        session_id=session.id,
        task_node_id=audit_context.record_source_task_node_id,
        messages=messages,
        task_projection=deps.task_projection,
        task_timeline_service=deps.task_timeline_service,
        event_provider=deps.audit_event_provider,
        config_provider=deps.audit_config_provider,
        log_provider=deps.audit_log_provider,
        session=session,
    )
    records = _normalize_audit_record_task_identity(
        records,
        task_node_ids_by_legacy_id=audit_context.task_node_ids_by_legacy_id,
    )
    return _AuditProjectionBundle(
        session=session,
        session_summary=session_summary,
        project=project,
        workflow=workflow,
        source_tree=source_tree,
        task_tree=task_tree,
        selected_task=selected_task,
        record_task_node_id=audit_context.record_task_node_id,
        records=records,
    )
