"""Framework-neutral UI query gateway protocols and defaults."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from taskweavn.core.session import Session
from taskweavn.observability.models import LogArchiveManifest
from taskweavn.server.ui_contract.audit_disclosure import (
    DefaultAuditPayloadDisclosureService,
    _no_payload,
    _record_partial_reason,
)
from taskweavn.server.ui_contract.commands import (
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    UpdateTaskNodePayload,
)
from taskweavn.server.ui_contract.envelopes import (
    CommandRequest,
    CommandResponse,
    CommandResult,
    QueryResponse,
    RefreshHint,
)
from taskweavn.server.ui_contract.errors import (
    bad_request,
    command_rejected,
    internal_error,
    not_found,
)
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditConfigProvider,
    AuditEventProvider,
    AuditLinkProvider,
    AuditLogProvider,
    AuditPayloadDisclosureService,
    PayloadDisclosureResult,
    ProjectProvider,
    SessionMessageProvider,
    SessionReader,
    TaskRefResolver,
    UiCommandGateway,
    UiQueryGateway,
    WorkflowProvider,
)
from taskweavn.server.ui_contract.gateway_providers import (
    StaticProjectProvider,
    StaticWorkflowProvider,
    WorkspaceAuditEventProvider,
)
from taskweavn.server.ui_contract.mapping import (
    map_agent_message_view,
    map_confirmation_action_view,
    map_file_change_summary_view,
    map_result_card_view,
    map_session_message_view,
    map_task_tree_view,
)
from taskweavn.server.ui_contract.refs import AffectedObjectRef, AffectedScope, ObjectRef
from taskweavn.server.ui_contract.snapshots import AuditPageSnapshot, MainPageSnapshot
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
    AuditLinkView,
    AuditLogEvidenceScope,
    AuditOverview,
    AuditPageRequestView,
    AuditPartialPageState,
    AuditReadyPageState,
    AuditRecord,
    AuditRecordDetail,
    AuditRecordFlags,
    AuditRecordKind,
    AuditRecordsResult,
    AuditReference,
    AuditResultScope,
    AuditSessionScope,
    AuditSeverity,
    AuditTaskScope,
    AuditVerdict,
    ConfirmationActionView,
    EffectiveConfigSummary,
    EvidenceDetail,
    EvidenceRef,
    EvidenceSummary,
    FileChangeSummaryView,
    MainPageReturnTarget,
    ProjectSummary,
    RelatedLogsLink,
    ResultCardView,
    SessionMessageView,
    SessionStatus,
    SessionSummary,
    TaskNodeCardView,
    TaskTreeView,
    WorkflowSummary,
)
from taskweavn.task.collaborator_api import CollaboratorApiAdapter
from taskweavn.task.commands import CommandResult as CoreCommandResult
from taskweavn.task.commands import TaskCommandService, TaskGuidanceMode
from taskweavn.task.models import TaskNodePatch, TaskRef
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore
from taskweavn.task.views import (
    ConfirmationActionView as CoreConfirmationActionView,
)
from taskweavn.task.views import (
    SessionMessageView as CoreSessionMessageView,
)
from taskweavn.task.views import (
    TaskCardView as CoreTaskCardView,
)
from taskweavn.task.views import (
    TaskTreeView as CoreTaskTreeView,
)
from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation

__all__ = [
    "AuditConfigProvider",
    "AuditEventProvider",
    "AuditLinkProvider",
    "AuditLogProvider",
    "AuditPayloadDisclosureService",
    "DefaultAuditPayloadDisclosureService",
    "DefaultUiCommandGateway",
    "DefaultUiQueryGateway",
    "PayloadDisclosureResult",
    "ProjectProvider",
    "SessionMessageProvider",
    "SessionReader",
    "StaticProjectProvider",
    "StaticWorkflowProvider",
    "TaskRefResolver",
    "UiCommandGateway",
    "UiQueryGateway",
    "WorkflowProvider",
    "WorkspaceAuditConfigProvider",
    "WorkspaceAuditEventProvider",
    "WorkspaceAuditLogProvider",
]


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


class DefaultUiQueryGateway:
    """Default read gateway for Plato Main Page snapshots."""

    def __init__(
        self,
        *,
        session_reader: SessionReader,
        task_projection: TaskProjectionService,
        project_provider: ProjectProvider | None = None,
        workflow_provider: WorkflowProvider | None = None,
        audit_link_provider: AuditLinkProvider | None = None,
        audit_event_provider: AuditEventProvider | None = None,
        audit_config_provider: AuditConfigProvider | None = None,
        audit_log_provider: AuditLogProvider | None = None,
        audit_payload_disclosure_service: AuditPayloadDisclosureService | None = None,
        session_message_provider: SessionMessageProvider | None = None,
        authoring_state_store: AuthoringStateStore | None = None,
    ) -> None:
        self._session_reader = session_reader
        self._task_projection = task_projection
        self._project_provider = project_provider or StaticProjectProvider()
        self._workflow_provider = workflow_provider or StaticWorkflowProvider()
        self._audit_link_provider = audit_link_provider
        self._audit_event_provider = audit_event_provider
        self._audit_config_provider = audit_config_provider
        self._audit_log_provider = audit_log_provider
        self._audit_payload_disclosure_service = (
            audit_payload_disclosure_service
            or DefaultAuditPayloadDisclosureService(
                audit_event_provider=audit_event_provider,
            )
        )
        self._session_message_provider = session_message_provider
        self._authoring_state_store = authoring_state_store

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
        try:
            session = self._session_reader.get(session_id)
            if session is None:
                return QueryResponse[MainPageSnapshot](
                    request_id=request_id or _request_id("snapshot", session_id),
                    ok=False,
                    data=None,
                    error=not_found("session not found", session_id=session_id),
                    cursor=None,
                )

            source_tree = self._task_projection.list_task_tree(session.id)
            task_tree = _map_optional_task_tree(
                source_tree,
                authoring_state_store=self._authoring_state_store,
            )
            messages = _merge_messages(
                _messages_from_tree(source_tree),
                self._session_messages(session.id),
            )
            confirmations = _confirmations_from_tree(source_tree, session_id=session.id)
            result = _result_from_tree(
                source_tree,
                session_id=session.id,
                task_projection=self._task_projection,
            )
            file_change_summary = _file_change_summary_from_tree(
                source_tree,
                session_id=session.id,
                task_projection=self._task_projection,
            )
            project = self._project_provider.get_project()
            workflow = self._workflow_provider.get_workflow(session)
            workflows = self._workflow_provider.list_workflows()
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
            snapshot = MainPageSnapshot(
                project=project,
                workflows=workflows,
                workflow=workflow,
                sessions=tuple(
                    _session_summary(
                        candidate,
                        project=project,
                        workflow=workflow,
                        status="new" if candidate.id != session.id else session_summary.status,
                    )
                    for candidate in self._session_reader.list()
                ),
                session=session_summary,
                task_tree=task_tree,
                messages=messages,
                pending_confirmations=confirmations,
                result=result,
                file_change_summary=file_change_summary,
                audit_links=self._audit_links(session.id),
                cursor=_snapshot_cursor(session),
            )
            return QueryResponse[MainPageSnapshot](
                request_id=request_id or _request_id("snapshot", session.id),
                ok=True,
                data=snapshot,
                error=None,
                cursor=snapshot.cursor,
            )
        except Exception as exc:
            return QueryResponse[MainPageSnapshot](
                request_id=request_id or _request_id("snapshot", session_id),
                ok=False,
                data=None,
                error=internal_error(
                    "Unable to load session snapshot",
                    error_type=type(exc).__name__,
                ),
                cursor=None,
            )

    def get_audit_snapshot(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        entry: str | None = None,
        filter_kind: str = "all",
        record_id: str | None = None,
        include_detail: bool | None = None,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AuditPageSnapshot]:
        try:
            checked_filter = _audit_filter_kind(filter_kind)
            checked_entry = _audit_entry_kind(entry, task_node_id=task_node_id)
            bundle = self._audit_projection(session_id, task_node_id=task_node_id)
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
            selected_record = (
                _audit_record_detail(
                    _require_audit_record(bundle.records, record_id),
                    session=bundle.session,
                    log_provider=self._audit_log_provider,
                    payload_disclosure_service=self._audit_payload_disclosure_service,
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
                    self._audit_config_provider,
                ),
                related_logs=_related_logs(
                    bundle.session,
                    task_node_id=task_node_id,
                    record_id=record_id,
                    log_provider=self._audit_log_provider,
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

    def list_audit_records(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        filter_kind: str = "all",
        kind: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        include_hidden_reasons: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordsResult]:
        try:
            del include_hidden_reasons
            checked_filter = _audit_filter_kind(filter_kind)
            checked_kind = _audit_record_kind(kind)
            bundle = self._audit_projection(session_id, task_node_id=task_node_id)
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

    def get_audit_record_detail(
        self,
        session_id: str,
        record_id: str,
        *,
        include_evidence: bool = False,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordDetail]:
        try:
            bundle = self._audit_projection(session_id, task_node_id=None)
            record = _require_audit_record(bundle.records, record_id)
            return QueryResponse[AuditRecordDetail](
                request_id=request_id or _request_id("audit.record", record_id),
                ok=True,
                data=_audit_record_detail(
                    record,
                    session=bundle.session,
                    log_provider=self._audit_log_provider,
                    payload_disclosure_service=self._audit_payload_disclosure_service,
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

    def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        *,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[EvidenceDetail]:
        try:
            bundle = self._audit_projection(session_id, task_node_id=None)
            record, evidence_ref = _require_evidence_ref(bundle.records, evidence_id)
            return QueryResponse[EvidenceDetail](
                request_id=request_id or _request_id("audit.evidence", evidence_id),
                ok=True,
                data=_evidence_detail(
                    record,
                    evidence_ref,
                    session=bundle.session,
                    payload_disclosure_service=self._audit_payload_disclosure_service,
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

    def _audit_projection(
        self,
        session_id: str,
        *,
        task_node_id: str | None,
    ) -> _AuditProjectionBundle:
        session = self._session_reader.get(session_id)
        if session is None:
            raise LookupError("session not found")

        source_tree = self._task_projection.list_task_tree(session.id)
        task_tree = _map_optional_task_tree(
            source_tree,
            authoring_state_store=self._authoring_state_store,
        )
        selected_task = _selected_task(task_tree, task_node_id)
        if task_node_id is not None and selected_task is None:
            raise LookupError("task not found")

        project = self._project_provider.get_project()
        workflow = self._workflow_provider.get_workflow(session)
        confirmations = _confirmations_from_tree(source_tree, session_id=session.id)
        messages = _merge_messages(
            _messages_from_tree(source_tree),
            self._session_messages(session.id),
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
        return _AuditProjectionBundle(
            session=session,
            session_summary=session_summary,
            project=project,
            workflow=workflow,
            source_tree=source_tree,
            task_tree=task_tree,
            selected_task=selected_task,
            records=_audit_records_from_projection(
                source_tree,
                session_id=session.id,
                task_node_id=task_node_id,
                messages=messages,
                task_projection=self._task_projection,
                event_provider=self._audit_event_provider,
                config_provider=self._audit_config_provider,
                log_provider=self._audit_log_provider,
                session=session,
            ),
        )

    def _audit_links(self, session_id: str) -> tuple[AuditLinkView, ...]:
        if self._audit_link_provider is None:
            return ()
        return self._audit_link_provider.list_for_session(session_id)

    def _session_messages(self, session_id: str) -> tuple[SessionMessageView, ...]:
        if self._session_message_provider is None:
            return ()
        return tuple(
            map_agent_message_view(message)
            for message in self._session_message_provider.list_for_session(session_id)
        )


class DefaultUiCommandGateway:
    """Default command gateway that wraps server-core command services."""

    def __init__(
        self,
        *,
        collaborator: CollaboratorApiAdapter,
        task_commands: TaskCommandService,
        task_ref_resolver: TaskRefResolver,
        authoring_state_store: AuthoringStateStore | None = None,
    ) -> None:
        self._collaborator = collaborator
        self._task_commands = task_commands
        self._task_ref_resolver = task_ref_resolver
        self._authoring_state_store = authoring_state_store

    def append_session_input(
        self,
        request: CommandRequest[AppendSessionInputPayload],
    ) -> CommandResponse:
        try:
            result = self._collaborator.append_session_message(
                session_id=request.session_id,
                content=request.payload.content,
                idempotency_key=request.idempotency_key,
            )
            return _command_response(
                request,
                result,
                suggested_queries=("session.snapshot", "session.messages", "task.tree"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="task_tree"),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def generate_task_tree(
        self,
        request: CommandRequest[GenerateTaskTreePayload],
    ) -> CommandResponse:
        try:
            object_refs: tuple[ObjectRef, ...] = ()
            affected_objects: tuple[AffectedObjectRef, ...] = ()
            if request.payload.raw_task_id is not None:
                raw_ref = ObjectRef(kind="raw_task", id=request.payload.raw_task_id)
                object_refs = (raw_ref,)
                affected_objects = (
                    AffectedObjectRef(
                        ref=raw_ref,
                        impact="changed",
                        reason="TaskTree generation consumed this RawTask.",
                    ),
                )
                result = self._collaborator.generate_task_tree(
                    session_id=request.session_id,
                    raw_task_id=request.payload.raw_task_id,
                    idempotency_key=request.idempotency_key,
                )
            else:
                raw_result = self._collaborator.append_session_message(
                    session_id=request.session_id,
                    content=request.payload.prompt or "",
                    source_message_id=request.command_id,
                    idempotency_key=_child_idempotency_key(
                        request.idempotency_key,
                        "raw",
                    ),
                )
                if raw_result.accepted:
                    tree_result = self._collaborator.generate_task_tree(
                        session_id=request.session_id,
                        raw_task_id=None,
                        idempotency_key=_child_idempotency_key(
                            request.idempotency_key,
                            "tree",
                        ),
                    )
                    result = _merge_prompt_task_tree_results(
                        raw_result,
                        tree_result,
                    )
                else:
                    result = raw_result
            return _command_response(
                request,
                result,
                object_refs=object_refs,
                affected_objects=affected_objects,
                suggested_queries=("session.snapshot", "task.tree", "session.messages"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="task_tree"),
                    AffectedScope(kind="messages"),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[UpdateTaskNodePayload],
    ) -> CommandResponse:
        try:
            task_ref = self._resolve_task_ref(request.session_id, task_node_id)
            result = self._task_commands.update_task_node(
                request.session_id,
                task_ref,
                _task_node_patch(request.payload),
                expected_version=request.expected_version,
            )
            return _command_response(
                request,
                result,
                suggested_queries=_update_suggested_queries(request.payload),
                affected_scopes=_update_affected_scopes(task_ref, request.payload),
            )
        except LookupError as exc:
            return _command_not_found_response(request, str(exc))
        except Exception as exc:
            return _command_exception_response(request, exc)

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[AppendTaskInputPayload],
    ) -> CommandResponse:
        try:
            task_ref = self._resolve_task_ref(request.session_id, task_node_id)
            if task_ref.kind == "draft":
                result = self._collaborator.append_task_message(
                    session_id=request.session_id,
                    task_ref=task_ref,
                    content=request.payload.content,
                )
            else:
                result = self._task_commands.append_task_message(
                    request.session_id,
                    task_ref,
                    request.payload.content,
                    mode=_guidance_mode(request.payload.mode),
                )
            return _command_response(
                request,
                result,
                suggested_queries=("session.snapshot", "session.messages", "task.detail"),
                affected_scopes=(
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="task_detail", task_ref=task_ref),
                ),
            )
        except LookupError as exc:
            return _command_not_found_response(request, str(exc))
        except Exception as exc:
            return _command_exception_response(request, exc)

    def publish_task_tree(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse:
        try:
            draft_tree_id = self._resolve_publish_draft_tree_id(request)
            tree_ref = ObjectRef(kind="draft_tree", id=draft_tree_id)
            result = self._collaborator.publish_task_tree(
                session_id=request.session_id,
                draft_tree_id=draft_tree_id,
                expected_version=request.expected_version,
                idempotency_key=request.idempotency_key,
                start_immediately=request.payload.start_immediately,
            )
            if result.accepted and self._authoring_state_store is not None:
                self._authoring_state_store.mark_published(
                    request.session_id,
                    draft_tree_id,
                )
            return _command_response(
                request,
                result,
                object_refs=(tree_ref,),
                affected_objects=(
                    AffectedObjectRef(
                        ref=tree_ref,
                        impact="changed",
                        reason="Draft tree publish was requested.",
                    ),
                ),
                suggested_queries=("session.snapshot", "task.tree"),
                affected_scopes=(
                    AffectedScope(kind="session"),
                    AffectedScope(kind="task_tree"),
                ),
            )
        except _TaskTreeIdentityError as exc:
            return _command_bad_request_response(request, str(exc), **exc.details)
        except Exception as exc:
            return _command_exception_response(request, exc)

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[RetryTaskPayload],
    ) -> CommandResponse:
        try:
            task_ref = self._resolve_task_ref(request.session_id, task_node_id)
            if task_ref.kind != "published":
                result = CoreCommandResult(
                    status="rejected",
                    message="only published failed tasks can be retried",
                )
                return _command_response(request, result)
            result = self._task_commands.retry_task(
                request.session_id,
                task_ref.id,
                request.payload.instruction,
            )
            return _command_response(
                request,
                result,
                object_refs=(ObjectRef(kind="published_task", id=task_ref.id),),
                affected_objects=(
                    AffectedObjectRef(
                        ref=ObjectRef(kind="published_task", id=task_ref.id),
                        impact="changed",
                        reason="Manual retry moved this failed Task back to pending.",
                    ),
                ),
                suggested_queries=("session.snapshot", "task.tree", "task.detail"),
                affected_scopes=(
                    AffectedScope(kind="task_tree"),
                    AffectedScope(kind="task_detail", task_ref=task_ref),
                ),
            )
        except LookupError as exc:
            return _command_not_found_response(request, str(exc))
        except Exception as exc:
            return _command_exception_response(request, exc)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[ResolveConfirmationPayload],
    ) -> CommandResponse:
        try:
            result = self._task_commands.resolve_confirmation(
                request.session_id,
                confirmation_id,
                request.payload.value,
                note=request.payload.note,
            )
            confirmation_ref = ObjectRef(kind="message", id=confirmation_id)
            return _command_response(
                request,
                result,
                object_refs=(confirmation_ref,),
                affected_objects=(
                    AffectedObjectRef(
                        ref=confirmation_ref,
                        impact="changed",
                        reason="Confirmation was resolved.",
                    ),
                ),
                suggested_queries=(
                    "session.snapshot",
                    "session.messages",
                    "confirmations",
                    "task.detail",
                ),
                affected_scopes=(
                    AffectedScope(kind="messages"),
                    AffectedScope(kind="confirmations"),
                    *(
                        AffectedScope(kind="task_detail", task_ref=task_ref)
                        for task_ref in result.affected_task_refs
                    ),
                ),
            )
        except Exception as exc:
            return _command_exception_response(request, exc)

    def _resolve_task_ref(self, session_id: str, task_node_id: str) -> TaskRef:
        return self._task_ref_resolver.resolve(session_id, task_node_id)

    def _resolve_publish_draft_tree_id(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> str:
        provided = request.payload.task_tree_id
        if self._authoring_state_store is None:
            if provided is None:
                raise _TaskTreeIdentityError(
                    "publish requires a draft tree id when active authoring state is unavailable",
                    reason="missing_task_tree_identity",
                    session_id=request.session_id,
                )
            if provided == _synthetic_task_tree_id(request.session_id):
                raise _TaskTreeIdentityError(
                    "synthetic task tree id cannot be published without active authoring state",
                    reason="synthetic_task_tree_identity_unresolved",
                    session_id=request.session_id,
                    provided_task_tree_id=provided,
                )
            return provided

        active = self._authoring_state_store.get_active(request.session_id)
        active_id = active.active_draft_tree_id
        if (
            active.active_state == "published"
            and active_id is not None
            and request.idempotency_key is not None
            and provided in {None, active_id, _synthetic_task_tree_id(request.session_id)}
        ):
            return active_id
        if active.active_state != "draft_tree" or active_id is None:
            raise _TaskTreeIdentityError(
                "publish requires an active draft tree",
                reason="no_active_draft_tree",
                session_id=request.session_id,
                active_state=active.active_state,
            )

        if provided in {None, active_id, _synthetic_task_tree_id(request.session_id)}:
            return active_id

        raise _TaskTreeIdentityError(
            "publish draft tree identity does not match the active draft tree",
            reason="invalid_task_tree_identity",
            session_id=request.session_id,
            provided_task_tree_id=provided,
            active_draft_tree_id=active_id,
        )


def _child_idempotency_key(idempotency_key: str | None, suffix: str) -> str | None:
    if idempotency_key is None:
        return None
    return f"{idempotency_key}:{suffix}"


class _TaskTreeIdentityError(ValueError):
    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.details = details


def _map_optional_task_tree(
    source: CoreTaskTreeView,
    *,
    authoring_state_store: AuthoringStateStore | None = None,
) -> TaskTreeView | None:
    if not source.nodes:
        return None
    tree_id = None
    if authoring_state_store is not None and _is_draft_tree(source):
        active = authoring_state_store.get_active(source.session_id)
        if active.active_state == "draft_tree" and active.active_draft_tree_id is not None:
            tree_id = active.active_draft_tree_id
    return map_task_tree_view(source, tree_id=tree_id)


def _is_draft_tree(source: CoreTaskTreeView) -> bool:
    return all(node.task_ref.kind == "draft" for node in source.nodes)


def _synthetic_task_tree_id(session_id: str) -> str:
    return f"session:{session_id}:task-tree"


def _messages_from_tree(source: CoreTaskTreeView) -> tuple[SessionMessageView, ...]:
    messages: list[CoreSessionMessageView] = []
    seen: set[str] = set()
    for node in source.nodes:
        if node.latest_message is None or node.latest_message.message_id in seen:
            continue
        messages.append(node.latest_message)
        seen.add(node.latest_message.message_id)
    messages.sort(key=lambda message: (message.created_at, message.message_id))
    return tuple(map_session_message_view(message) for message in messages)


def _merge_messages(
    *groups: Sequence[SessionMessageView],
) -> tuple[SessionMessageView, ...]:
    by_id: dict[str, SessionMessageView] = {}
    for group in groups:
        for message in group:
            # Later groups are intentionally richer. In the default snapshot path,
            # task-tree latest messages come first and raw session MessageStream
            # messages come second, preserving execution context titles/kinds.
            by_id[message.id] = message
    return tuple(
        sorted(
            by_id.values(),
            key=lambda message: (message.created_at, message.id),
        )
    )


def _confirmations_from_tree(
    source: CoreTaskTreeView,
    *,
    session_id: str,
) -> tuple[ConfirmationActionView, ...]:
    confirmations: list[CoreConfirmationActionView] = []
    seen: set[str] = set()
    for node in source.nodes:
        if node.confirmation is None or node.confirmation.confirmation_id in seen:
            continue
        confirmations.append(node.confirmation)
        seen.add(node.confirmation.confirmation_id)
    return tuple(
        map_confirmation_action_view(confirmation, session_id=session_id)
        for confirmation in confirmations
    )


def _result_from_tree(
    source: CoreTaskTreeView,
    *,
    session_id: str,
    task_projection: TaskProjectionService,
) -> ResultCardView | None:
    for node in reversed(source.nodes):
        if node.task_ref.kind != "published":
            continue
        if (
            node.status not in {"done", "failed"}
            and node.result_ref is None
            and node.error_ref is None
        ):
            continue
        try:
            detail = task_projection.get_task_detail(session_id, node.task_ref)
        except LookupError:
            continue
        if detail.result_summary is not None:
            return map_result_card_view(detail.result_summary, session_id=session_id)
    return None


def _file_change_summary_from_tree(
    source: CoreTaskTreeView,
    *,
    session_id: str,
    task_projection: TaskProjectionService,
) -> FileChangeSummaryView | None:
    candidates = [
        node
        for node in source.nodes
        if node.task_ref.kind == "published" and node.badges.subtree_file_change_count > 0
    ]
    root_candidates = [node for node in candidates if node.parent_ref is None]
    for node in reversed(root_candidates or candidates):
        try:
            detail = task_projection.get_task_detail(session_id, node.task_ref)
        except LookupError:
            continue
        if detail.file_changes:
            return map_file_change_summary_view(
                detail.file_changes,
                session_id=session_id,
                task_ref=node.task_ref,
                recursive=True,
            )
    return None


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


def _derive_session_status(
    session: Session,
    *,
    task_tree: TaskTreeView | None,
    confirmations: Sequence[ConfirmationActionView],
    messages: Sequence[SessionMessageView],
) -> SessionStatus:
    if confirmations:
        return "waiting_user"
    if task_tree is not None:
        if task_tree.status == "draft":
            return "draft_ready"
        if task_tree.status == "published":
            return "running"
        if task_tree.status == "running":
            return "running"
        if task_tree.status == "completed":
            return "completed"
        if task_tree.status == "failed":
            return "failed"
    if session.status == "awaiting_user":
        return "waiting_user"
    if session.status == "finished":
        return "completed"
    if messages:
        return "understanding"
    return "new"


def _session_summary(
    session: Session,
    *,
    project: ProjectSummary,
    workflow: WorkflowSummary,
    status: SessionStatus,
) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        project_id=project.id,
        workflow_id=workflow.id,
        name=session.name,
        status=status,
        created_at=session.created_at,
        updated_at=session.last_active_at,
        workspace_label="Isolated session workspace",
    )


def _snapshot_cursor(session: Session) -> str:
    return f"snapshot:{session.id}:{session.last_active_at.isoformat()}"


def _request_id(prefix: str, subject: str) -> str:
    return f"{prefix}:{subject}"


def _safe_token(value: str) -> str:
    return _ID_SAFE_RE.sub("-", value).strip("-") or "item"


def _command_response[T](
    request: CommandRequest[T],
    result: CoreCommandResult,
    *,
    object_refs: tuple[ObjectRef, ...] = (),
    affected_objects: tuple[AffectedObjectRef, ...] = (),
    suggested_queries: tuple[str, ...] = (),
    affected_scopes: tuple[AffectedScope, ...] = (),
) -> CommandResponse:
    contract_result = CommandResult(
        command_id=request.command_id,
        status=result.status,
        message=result.message,
        affected_task_refs=result.affected_task_refs,
        object_refs=_object_refs_for_result(result, extra=object_refs),
        affected_objects=_affected_objects_for_result(result, extra=affected_objects),
        emitted_message_ids=result.emitted_message_ids,
        published_task_ids=result.published_task_ids,
        debug_refs=_debug_refs(request, result),
    )
    refresh = RefreshHint(
        wait_for_events=result.accepted,
        suggested_queries=suggested_queries,
        affected_task_refs=result.affected_task_refs,
        affected_scopes=affected_scopes,
    )
    if result.accepted:
        return CommandResponse(
            request_id=request.command_id,
            ok=True,
            result=contract_result,
            error=None,
            refresh=refresh,
        )
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=contract_result,
        error=command_rejected(result.message),
        refresh=refresh.model_copy(update={"wait_for_events": False}),
    )


def _merge_prompt_task_tree_results(
    raw_result: CoreCommandResult,
    tree_result: CoreCommandResult,
) -> CoreCommandResult:
    return CoreCommandResult(
        command_id=tree_result.command_id,
        status=tree_result.status,
        message=tree_result.message,
        affected_task_refs=tree_result.affected_task_refs,
        emitted_message_ids=_dedupe_ids(
            (*raw_result.emitted_message_ids, *tree_result.emitted_message_ids)
        ),
        published_task_ids=tree_result.published_task_ids,
    )


def _command_not_found_response[T](
    request: CommandRequest[T],
    message: str,
) -> CommandResponse:
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=None,
        error=not_found(message),
        refresh=RefreshHint(wait_for_events=False),
    )


def _command_bad_request_response[T](
    request: CommandRequest[T],
    message: str,
    **details: object,
) -> CommandResponse:
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=None,
        error=bad_request(message, **details),
        refresh=RefreshHint(wait_for_events=False),
    )


def _command_exception_response[T](
    request: CommandRequest[T],
    exc: Exception,
) -> CommandResponse:
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=None,
        error=internal_error(
            "Unable to process command",
            error_type=type(exc).__name__,
        ),
        refresh=RefreshHint(wait_for_events=False),
    )


def _object_refs_for_result(
    result: CoreCommandResult,
    *,
    extra: tuple[ObjectRef, ...],
) -> tuple[ObjectRef, ...]:
    refs = [ObjectRef(kind="command", id=result.command_id), *extra]
    refs.extend(_object_ref_for_task_ref(ref) for ref in result.affected_task_refs)
    refs.extend(
        ObjectRef(kind="published_task", id=task_id) for task_id in result.published_task_ids
    )
    return _dedupe_object_refs(refs)


def _affected_objects_for_result(
    result: CoreCommandResult,
    *,
    extra: tuple[AffectedObjectRef, ...],
) -> tuple[AffectedObjectRef, ...]:
    affected = [*extra]
    affected.extend(
        AffectedObjectRef(
            ref=_object_ref_for_task_ref(ref),
            impact="changed",
        )
        for ref in result.affected_task_refs
    )
    affected.extend(
        AffectedObjectRef(
            ref=ObjectRef(kind="published_task", id=task_id),
            impact="created",
        )
        for task_id in result.published_task_ids
    )
    return tuple(affected)


def _object_ref_for_task_ref(task_ref: TaskRef) -> ObjectRef:
    if task_ref.kind == "draft":
        return ObjectRef(kind="draft_task", id=task_ref.id)
    return ObjectRef(kind="published_task", id=task_ref.id)


def _dedupe_object_refs(refs: list[ObjectRef]) -> tuple[ObjectRef, ...]:
    seen: set[tuple[str, str]] = set()
    result: list[ObjectRef] = []
    for ref in refs:
        key = (ref.kind, ref.id)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return tuple(result)


def _dedupe_ids(ids: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def _debug_refs[T](request: CommandRequest[T], result: CoreCommandResult) -> dict[str, str]:
    refs: dict[str, str] = {}
    if result.command_id != request.command_id:
        refs["backendCommandId"] = result.command_id
    if request.idempotency_key is not None:
        refs["idempotencyKey"] = request.idempotency_key
    return refs


def _task_node_patch(payload: UpdateTaskNodePayload) -> TaskNodePatch:
    children_ops: tuple[dict[str, object], ...] = ()
    if payload.update_mode != "node_fields":
        children_ops = (
            {
                "op": payload.update_mode,
                "preserve_root_id": payload.preserve_root_id,
            },
        )
    return TaskNodePatch(
        title=payload.title,
        intent=payload.full_intent or payload.summary,
        constraints_add=payload.constraints or (),
        children_ops=children_ops,
    )


def _update_suggested_queries(payload: UpdateTaskNodePayload) -> tuple[str, ...]:
    if payload.update_mode == "node_fields":
        return ("session.snapshot", "task.detail")
    return ("session.snapshot", "task.tree", "task.detail")


def _update_affected_scopes(
    task_ref: TaskRef,
    payload: UpdateTaskNodePayload,
) -> tuple[AffectedScope, ...]:
    if payload.update_mode in {"replace_children", "replace_subtree"}:
        return (
            AffectedScope(kind="task_subtree", task_ref=task_ref),
            AffectedScope(kind="task_detail", task_ref=task_ref),
        )
    return (AffectedScope(kind="task_detail", task_ref=task_ref),)


def _guidance_mode(mode: str) -> TaskGuidanceMode:
    if mode == "clarification_answer":
        return "clarification"
    if mode == "revision_request":
        return "correction"
    return "guidance"
