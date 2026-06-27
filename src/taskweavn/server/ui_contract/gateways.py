"""Framework-neutral UI query gateway protocols and defaults."""

from __future__ import annotations

from taskweavn.server.ui_contract.ask_projection import AskProjectionService
from taskweavn.server.ui_contract.audit_disclosure import (
    DefaultAuditPayloadDisclosureService,
)
from taskweavn.server.ui_contract.audit_projection import (
    WorkspaceAuditConfigProvider,
    WorkspaceAuditLogProvider,
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
from taskweavn.server.ui_contract.authoring_answer_projection import (
    project_authoring_ask_answer_message_view,
)
from taskweavn.server.ui_contract.command_gateway import DefaultUiCommandGateway
from taskweavn.server.ui_contract.envelopes import (
    QueryResponse,
)
from taskweavn.server.ui_contract.errors import (
    bad_request,
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
    SnapshotCursorProvider,
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
from taskweavn.server.ui_contract.mapping import map_agent_message_view
from taskweavn.server.ui_contract.plan_projection import (
    DefaultPlanProjectionService,
    PlanProjectionService,
)
from taskweavn.server.ui_contract.plan_read_helpers import (
    active_stored_plan,
    audit_task_read_context,
)
from taskweavn.server.ui_contract.query_activity_helpers import (
    list_session_activity_query,
)
from taskweavn.server.ui_contract.query_ask_helpers import get_ask_query, list_asks_query
from taskweavn.server.ui_contract.query_snapshot_helpers import (
    _confirmations_from_tree,
    _derive_session_status,
    _map_optional_task_tree,
    _merge_messages,
    _messages_from_tree,
    _request_id,
    _session_summary,
    get_session_snapshot_query,
)
from taskweavn.server.ui_contract.session_activity_projection import (
    DefaultSessionActivityProjectionService,
)
from taskweavn.server.ui_contract.snapshots import AuditPageSnapshot, MainPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    AskListResult,
    AskRequestView,
    AuditPageRequestView,
    AuditPermissions,
    AuditRecordDetail,
    AuditRecordsResult,
    EvidenceDetail,
    SessionActivityTimelineResult,
    SessionMessageView,
)
from taskweavn.task.plan_stores import PlanStore
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore, RawTaskStore
from taskweavn.task.timeline import TaskInteractionTimelineService

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
    "SnapshotCursorProvider",
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
        task_timeline_service: TaskInteractionTimelineService | None = None,
        session_message_provider: SessionMessageProvider | None = None,
        authoring_state_store: AuthoringStateStore | None = None,
        raw_task_store: RawTaskStore | None = None,
        ask_projection: AskProjectionService | None = None,
        snapshot_cursor_provider: SnapshotCursorProvider | None = None,
        plan_projection: PlanProjectionService | None = None,
        plan_store: PlanStore | None = None,
    ) -> None:
        self._session_reader = session_reader
        self._task_projection = task_projection
        self._project_provider = project_provider or StaticProjectProvider()
        self._workflow_provider = workflow_provider or StaticWorkflowProvider()
        self._audit_link_provider = audit_link_provider
        self._audit_event_provider = audit_event_provider
        self._audit_config_provider = audit_config_provider
        self._audit_log_provider = audit_log_provider
        self._task_timeline_service = task_timeline_service
        self._audit_payload_disclosure_service = (
            audit_payload_disclosure_service
            or DefaultAuditPayloadDisclosureService(
                audit_event_provider=audit_event_provider,
            )
        )
        self._session_message_provider = session_message_provider
        self._authoring_state_store = authoring_state_store
        self._raw_task_store = raw_task_store
        self._ask_projection = ask_projection
        self._snapshot_cursor_provider = snapshot_cursor_provider
        self._plan_projection = plan_projection or DefaultPlanProjectionService()
        self._plan_store = plan_store
        self._activity_projection = DefaultSessionActivityProjectionService()

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
        return get_session_snapshot_query(
            session_id,
            ask_projection=self._ask_projection,
            audit_link_provider=self._audit_link_provider,
            authoring_state_store=self._authoring_state_store,
            plan_projection=self._plan_projection,
            plan_store=self._plan_store,
            project_provider=self._project_provider,
            raw_task_store=self._raw_task_store,
            request_id=request_id,
            session_messages=self._session_messages,
            session_reader=self._session_reader,
            snapshot_cursor_provider=self._snapshot_cursor_provider,
            task_projection=self._task_projection,
            workflow_provider=self._workflow_provider,
        )

    def list_session_activity(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[SessionActivityTimelineResult]:
        return list_session_activity_query(
            session_id,
            activity_projection=self._activity_projection,
            ask_projection=self._ask_projection,
            authoring_state_store=self._authoring_state_store,
            cursor=cursor,
            limit=limit,
            plan_projection=self._plan_projection,
            plan_store=self._plan_store,
            request_id=request_id,
            session_messages=self._session_messages,
            session_reader=self._session_reader,
            task_projection=self._task_projection,
        )

    def list_asks(
        self,
        session_id: str,
        *,
        status: str | None = None,
        task_node_id: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AskListResult]:
        return list_asks_query(
            session_id,
            ask_projection=self._ask_projection,
            authoring_state_store=self._authoring_state_store,
            request_id=request_id,
            session_reader=self._session_reader,
            status=status,
            task_node_id=task_node_id,
            task_projection=self._task_projection,
        )

    def get_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[AskRequestView]:
        return get_ask_query(
            session_id,
            ask_id,
            ask_projection=self._ask_projection,
            request_id=request_id,
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
            related_logs = _related_logs(
                bundle.session,
                task_node_id=bundle.record_task_node_id,
                record_id=record_id,
                log_provider=self._audit_log_provider,
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
        stored_plan = active_stored_plan(
            session.id,
            plan_store=self._plan_store,
            authoring_state_store=self._authoring_state_store,
        )
        audit_context = audit_task_read_context(
            task_node_id=task_node_id,
            legacy_task_tree=task_tree,
            stored_plan=stored_plan,
            plan_projection=self._plan_projection,
        )
        task_tree = audit_context.task_tree
        selected_task = audit_context.selected_task
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
        records = _audit_records_from_projection(
            source_tree,
            session_id=session.id,
            task_node_id=audit_context.record_source_task_node_id,
            messages=messages,
            task_projection=self._task_projection,
            task_timeline_service=self._task_timeline_service,
            event_provider=self._audit_event_provider,
            config_provider=self._audit_config_provider,
            log_provider=self._audit_log_provider,
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

    def _session_messages(self, session_id: str) -> tuple[SessionMessageView, ...]:
        if self._session_message_provider is None:
            return ()
        return tuple(
            project_authoring_ask_answer_message_view(
                map_agent_message_view(message),
                message,
                raw_task_store=self._raw_task_store,
            )
            for message in self._session_message_provider.list_for_session(session_id)
        )
