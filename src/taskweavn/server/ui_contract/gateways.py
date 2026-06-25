"""Framework-neutral UI query gateway protocols and defaults."""

from __future__ import annotations

from taskweavn.server.ui_contract.ask_projection import AskProjectionService
from taskweavn.server.ui_contract.ask_read_helpers import (
    active_ask,
    get_ask_response,
    list_asks_response,
    pending_asks,
)
from taskweavn.server.ui_contract.audit_disclosure import (
    DefaultAuditPayloadDisclosureService,
)
from taskweavn.server.ui_contract.audit_projection import (
    WorkspaceAuditConfigProvider,
    WorkspaceAuditLogProvider,
)
from taskweavn.server.ui_contract.audit_read_helpers import (
    AuditReadDependencies,
    get_audit_record_detail_response,
    get_audit_snapshot_response,
    get_evidence_detail_response,
    list_audit_records_response,
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
from taskweavn.server.ui_contract.main_page_read_helpers import (
    _archived_plan_messages,
    _confirmations_from_tree,
    _derive_session_status,
    _file_change_summary_from_tree,
    _list_main_page_plan_tree,
    _map_optional_task_tree,
    _merge_messages,
    _messages_from_tree,
    _planning_from_raw_task,
    _request_id,
    _result_from_tree,
    _session_summary,
    _snapshot_cursor,
)
from taskweavn.server.ui_contract.mapping import map_agent_message_view
from taskweavn.server.ui_contract.plan_projection import (
    DefaultPlanProjectionService,
    PlanProjectionService,
)
from taskweavn.server.ui_contract.plan_read_helpers import (
    active_plan_read_context,
    active_stored_plan,
    archived_plan_views,
    file_change_summary_from_plan_nodes,
    result_from_plan_nodes,
)
from taskweavn.server.ui_contract.session_activity_projection import (
    DefaultSessionActivityProjectionService,
)
from taskweavn.server.ui_contract.snapshots import AuditPageSnapshot, MainPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    AskListResult,
    AskRequestView,
    AuditLinkView,
    AuditRecordDetail,
    AuditRecordsResult,
    EvidenceDetail,
    PlanningView,
    SessionActivityTimelineResult,
    SessionMessageView,
    TaskTreeView,
)
from taskweavn.task.authoring import RawTask
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
        self._audit_read_deps = AuditReadDependencies(
            session_reader=self._session_reader,
            task_projection=self._task_projection,
            authoring_state_store=self._authoring_state_store,
            plan_store=self._plan_store,
            plan_projection=self._plan_projection,
            project_provider=self._project_provider,
            workflow_provider=self._workflow_provider,
            task_timeline_service=self._task_timeline_service,
            audit_event_provider=self._audit_event_provider,
            audit_config_provider=self._audit_config_provider,
            audit_log_provider=self._audit_log_provider,
            audit_payload_disclosure_service=self._audit_payload_disclosure_service,
            session_messages=self._session_messages,
        )

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

            source_tree = _list_main_page_plan_tree(self._task_projection, session.id)
            task_tree = _map_optional_task_tree(
                source_tree,
                authoring_state_store=self._authoring_state_store,
            )
            stored_plan = active_stored_plan(
                session.id,
                plan_store=self._plan_store,
                authoring_state_store=self._authoring_state_store,
            )
            plan_context = active_plan_read_context(
                task_tree,
                stored_plan=stored_plan,
                plan_projection=self._plan_projection,
            )
            active_plan = plan_context.active_plan
            task_tree = plan_context.task_tree
            archived_plans = archived_plan_views(
                session.id,
                plan_store=self._plan_store,
                plan_projection=self._plan_projection,
            )
            messages = _merge_messages(
                _messages_from_tree(source_tree),
                self._session_messages(session.id),
                _archived_plan_messages(archived_plans),
            )
            confirmations = _confirmations_from_tree(source_tree, session_id=session.id)
            planning = self._planning(session.id, task_tree=task_tree)
            pending_ask_views = pending_asks(
                session.id,
                ask_projection=self._ask_projection,
            )
            active_ask_view = active_ask(
                session.id,
                ask_projection=self._ask_projection,
                task_tree=task_tree,
            )
            result = (
                result_from_plan_nodes(
                    plan_context.stored_plan_nodes,
                    session_id=session.id,
                    task_projection=self._task_projection,
                )
                if plan_context.stored_plan_nodes is not None
                else None
            )
            if result is None and plan_context.legacy_fallback_allowed:
                result = _result_from_tree(
                    source_tree,
                    session_id=session.id,
                    task_projection=self._task_projection,
                )
            file_change_summary = (
                file_change_summary_from_plan_nodes(
                    plan_context.stored_plan_nodes,
                    session_id=session.id,
                    task_projection=self._task_projection,
                )
                if plan_context.stored_plan_nodes is not None
                else None
            )
            if (
                file_change_summary is None
                and plan_context.legacy_fallback_allowed
            ):
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
                    active_ask=active_ask_view,
                    planning=planning,
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
                planning=planning,
                active_plan=active_plan,
                task_tree=task_tree,
                messages=messages,
                pending_confirmations=confirmations,
                pending_asks=pending_ask_views,
                active_ask=active_ask_view,
                result=result,
                file_change_summary=file_change_summary,
                audit_links=self._audit_links(session.id),
                cursor=_snapshot_cursor(
                    session,
                    cursor_provider=self._snapshot_cursor_provider,
                ),
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

    def list_session_activity(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[SessionActivityTimelineResult]:
        try:
            session = self._session_reader.get(session_id)
            if session is None:
                return QueryResponse[SessionActivityTimelineResult](
                    request_id=request_id or _request_id("activity", session_id),
                    ok=False,
                    data=None,
                    error=not_found("session not found", session_id=session_id),
                    cursor=None,
                )

            source_tree = _list_main_page_plan_tree(self._task_projection, session.id)
            task_tree = _map_optional_task_tree(
                source_tree,
                authoring_state_store=self._authoring_state_store,
            )
            stored_plan = active_stored_plan(
                session.id,
                plan_store=self._plan_store,
                authoring_state_store=self._authoring_state_store,
            )
            plan_context = active_plan_read_context(
                task_tree,
                stored_plan=stored_plan,
                plan_projection=self._plan_projection,
            )
            messages = _merge_messages(
                _messages_from_tree(source_tree),
                self._session_messages(session.id),
            )
            confirmations = _confirmations_from_tree(source_tree, session_id=session.id)
            pending_ask_views = pending_asks(
                session.id,
                ask_projection=self._ask_projection,
            )
            active_ask_view = active_ask(
                session.id,
                ask_projection=self._ask_projection,
                task_tree=plan_context.task_tree,
            )
            result = (
                result_from_plan_nodes(
                    plan_context.stored_plan_nodes,
                    session_id=session.id,
                    task_projection=self._task_projection,
                )
                if plan_context.stored_plan_nodes is not None
                else None
            )
            if result is None and plan_context.legacy_fallback_allowed:
                result = _result_from_tree(
                    source_tree,
                    session_id=session.id,
                    task_projection=self._task_projection,
                )
            file_change_summary = (
                file_change_summary_from_plan_nodes(
                    plan_context.stored_plan_nodes,
                    session_id=session.id,
                    task_projection=self._task_projection,
                )
                if plan_context.stored_plan_nodes is not None
                else None
            )
            if (
                file_change_summary is None
                and plan_context.legacy_fallback_allowed
            ):
                file_change_summary = _file_change_summary_from_tree(
                    source_tree,
                    session_id=session.id,
                    task_projection=self._task_projection,
                )
            activity = self._activity_projection.project(
                session_id=session.id,
                messages=messages,
                active_plan=plan_context.active_plan,
                archived_plans=archived_plan_views(
                    session.id,
                    plan_store=self._plan_store,
                    plan_projection=self._plan_projection,
                ),
                task_tree=plan_context.task_tree,
                pending_asks=pending_ask_views,
                active_ask=active_ask_view,
                confirmations=confirmations,
                result=result,
                file_change_summary=file_change_summary,
                limit=limit,
                cursor=cursor,
            )
            return QueryResponse[SessionActivityTimelineResult](
                request_id=request_id or _request_id("activity", session_id),
                ok=True,
                data=activity,
                error=None,
                cursor=activity.next_cursor,
            )
        except ValueError as exc:
            return QueryResponse[SessionActivityTimelineResult](
                request_id=request_id or _request_id("activity", session_id),
                ok=False,
                data=None,
                error=bad_request(str(exc), session_id=session_id),
                cursor=None,
            )
        except Exception as exc:  # noqa: BLE001 - gateway returns typed errors.
            return QueryResponse[SessionActivityTimelineResult](
                request_id=request_id or _request_id("activity", session_id),
                ok=False,
                data=None,
                error=internal_error(
                    "failed to build session activity timeline",
                    error_type=type(exc).__name__,
                ),
                cursor=None,
            )

    def list_asks(
        self,
        session_id: str,
        *,
        status: str | None = None,
        task_node_id: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AskListResult]:
        return list_asks_response(
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
        return get_ask_response(
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
        return get_audit_snapshot_response(
            session_id,
            cursor=cursor,
            deps=self._audit_read_deps,
            entry=entry,
            filter_kind=filter_kind,
            include_detail=include_detail,
            limit=limit,
            record_id=record_id,
            request_id=request_id,
            task_node_id=task_node_id,
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
        return list_audit_records_response(
            session_id,
            cursor=cursor,
            deps=self._audit_read_deps,
            filter_kind=filter_kind,
            from_time=from_time,
            include_hidden_reasons=include_hidden_reasons,
            kind=kind,
            limit=limit,
            request_id=request_id,
            task_node_id=task_node_id,
            to_time=to_time,
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
        return get_audit_record_detail_response(
            session_id,
            record_id,
            deps=self._audit_read_deps,
            include_evidence=include_evidence,
            include_sanitized_payload=include_sanitized_payload,
            request_id=request_id,
        )

    def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        *,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[EvidenceDetail]:
        return get_evidence_detail_response(
            session_id,
            evidence_id,
            deps=self._audit_read_deps,
            include_sanitized_payload=include_sanitized_payload,
            request_id=request_id,
        )

    def _audit_links(self, session_id: str) -> tuple[AuditLinkView, ...]:
        if self._audit_link_provider is None:
            return ()
        return self._audit_link_provider.list_for_session(session_id)

    def _planning(
        self,
        session_id: str,
        *,
        task_tree: TaskTreeView | None,
    ) -> PlanningView | None:
        active = (
            self._authoring_state_store.get_active(session_id)
            if self._authoring_state_store is not None
            else None
        )
        raw_task = self._active_raw_task(session_id)
        if raw_task is None:
            return None
        return _planning_from_raw_task(
            raw_task,
            task_tree=task_tree,
            dirty_authoring_state=(
                task_tree is not None
                and active is not None
                and active.active_state == "raw_task"
            ),
            authoring_state_cancelled=(
                task_tree is not None
                and active is not None
                and active.active_state == "cancelled"
            ),
        )

    def _active_raw_task(self, session_id: str) -> RawTask | None:
        if self._raw_task_store is None:
            return None
        if self._authoring_state_store is not None:
            active = self._authoring_state_store.get_active(session_id)
            if active.active_raw_task_id is not None:
                raw_task = self._raw_task_store.get(session_id, active.active_raw_task_id)
                if raw_task is not None:
                    return raw_task
        raw_tasks = self._raw_task_store.list_for_session(session_id)
        return raw_tasks[-1] if raw_tasks else None

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
