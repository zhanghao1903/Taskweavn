"""Framework-neutral UI query gateway protocols and defaults."""

from __future__ import annotations

from collections.abc import Sequence

from taskweavn.core.session import Session
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
    _page_audit_records,
    _related_logs,
    _require_audit_record,
    _require_evidence_ref,
    _selected_task,
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
from taskweavn.server.ui_contract.snapshots import AuditPageSnapshot, MainPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    AuditLinkView,
    AuditPageRequestView,
    AuditRecordDetail,
    AuditRecordsResult,
    ConfirmationActionView,
    EvidenceDetail,
    FileChangeSummaryView,
    ProjectSummary,
    ResultCardView,
    SessionMessageView,
    SessionStatus,
    SessionSummary,
    TaskTreeView,
    WorkflowSummary,
)
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore
from taskweavn.task.views import (
    ConfirmationActionView as CoreConfirmationActionView,
)
from taskweavn.task.views import (
    SessionMessageView as CoreSessionMessageView,
)
from taskweavn.task.views import (
    TaskTreeView as CoreTaskTreeView,
)

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
