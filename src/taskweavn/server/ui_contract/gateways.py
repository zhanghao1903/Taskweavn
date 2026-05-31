"""Framework-neutral UI query gateway protocols and defaults."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from taskweavn.core.session import Session
from taskweavn.interaction import AgentMessage
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
from taskweavn.server.ui_contract.mapping import (
    map_agent_message_view,
    map_confirmation_action_view,
    map_file_change_summary_view,
    map_result_card_view,
    map_session_message_view,
    map_task_tree_view,
)
from taskweavn.server.ui_contract.refs import AffectedObjectRef, AffectedScope, ObjectRef
from taskweavn.server.ui_contract.snapshots import MainPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    AuditLinkView,
    ConfirmationActionView,
    FileChangeSummaryView,
    ProjectSummary,
    ResultCardView,
    SessionMessageView,
    SessionStatus,
    SessionSummary,
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
    TaskTreeView as CoreTaskTreeView,
)


@runtime_checkable
class SessionReader(Protocol):
    """Read subset of SessionManager needed by UI query gateways."""

    def get(self, session_id: str) -> Session | None: ...

    def list(self) -> list[Session]: ...


@runtime_checkable
class ProjectProvider(Protocol):
    def get_project(self) -> ProjectSummary: ...


@runtime_checkable
class WorkflowProvider(Protocol):
    def list_workflows(self) -> tuple[WorkflowSummary, ...]: ...

    def get_workflow(self, session: Session) -> WorkflowSummary: ...


@runtime_checkable
class AuditLinkProvider(Protocol):
    def list_for_session(self, session_id: str) -> tuple[AuditLinkView, ...]: ...


@runtime_checkable
class SessionMessageProvider(Protocol):
    def list_for_session(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> Iterable[AgentMessage]: ...


@runtime_checkable
class TaskRefResolver(Protocol):
    """Resolve frontend taskNodeId into a backend TaskRef."""

    def resolve(self, session_id: str, task_node_id: str) -> TaskRef: ...


@runtime_checkable
class UiQueryGateway(Protocol):
    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]: ...


@runtime_checkable
class UiCommandGateway(Protocol):
    def append_session_input(
        self,
        request: CommandRequest[AppendSessionInputPayload],
    ) -> CommandResponse: ...

    def generate_task_tree(
        self,
        request: CommandRequest[GenerateTaskTreePayload],
    ) -> CommandResponse: ...

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[UpdateTaskNodePayload],
    ) -> CommandResponse: ...

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[AppendTaskInputPayload],
    ) -> CommandResponse: ...

    def publish_task_tree(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse: ...

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[RetryTaskPayload],
    ) -> CommandResponse: ...

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[ResolveConfirmationPayload],
    ) -> CommandResponse: ...


@dataclass(frozen=True)
class StaticProjectProvider:
    project: ProjectSummary = ProjectSummary(id="local", name="Local Project")

    def get_project(self) -> ProjectSummary:
        return self.project


@dataclass(frozen=True)
class StaticWorkflowProvider:
    workflow: WorkflowSummary = WorkflowSummary(
        id="task_authoring",
        name="Task authoring",
        description="Turn user intent into a Task Tree.",
        input_hint="Describe what you want Plato to do.",
        delivery_kind="task_tree",
    )

    def list_workflows(self) -> tuple[WorkflowSummary, ...]:
        return (self.workflow,)

    def get_workflow(self, session: Session) -> WorkflowSummary:
        return self.workflow


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
        session_message_provider: SessionMessageProvider | None = None,
        authoring_state_store: AuthoringStateStore | None = None,
    ) -> None:
        self._session_reader = session_reader
        self._task_projection = task_projection
        self._project_provider = project_provider or StaticProjectProvider()
        self._workflow_provider = workflow_provider or StaticWorkflowProvider()
        self._audit_link_provider = audit_link_provider
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
                        impact="superseded",
                        reason="Manual retry was requested for this failed Task.",
                    ),
                    *(
                        AffectedObjectRef(
                            ref=ObjectRef(kind="published_task", id=task_id),
                            impact="created",
                            reason="Retry attempt was published.",
                        )
                        for task_id in result.published_task_ids
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
