"""Private helpers for UI query snapshot projection."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal, cast

from taskweavn.core.session import Session
from taskweavn.interaction import AskStatus
from taskweavn.server.ui_contract.ask_projection import AskProjectionService
from taskweavn.server.ui_contract.envelopes import QueryResponse
from taskweavn.server.ui_contract.errors import internal_error, not_found
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditLinkProvider,
    ProjectProvider,
    SessionReader,
    SnapshotCursorProvider,
    WorkflowProvider,
)
from taskweavn.server.ui_contract.mapping import (
    map_confirmation_action_view,
    map_file_change_summary_view,
    map_result_card_view,
    map_session_message_view,
    map_task_tree_view,
)
from taskweavn.server.ui_contract.plan_projection import PlanProjectionService
from taskweavn.server.ui_contract.plan_read_helpers import (
    active_plan_read_context,
    active_stored_plan,
    archived_plan_views,
    file_change_summary_from_plan_nodes,
    result_from_plan_nodes,
)
from taskweavn.server.ui_contract.snapshots import MainPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    AskRequestView,
    AuditLinkView,
    ConfirmationActionView,
    ConfirmationOptionView,
    FileChangeSummaryView,
    PlanningAskView,
    PlanningDiagnosticView,
    PlanningState,
    PlanningView,
    PlanView,
    ProjectSummary,
    ResultCardView,
    SessionMessageView,
    SessionStatus,
    SessionSummary,
    TaskTreeView,
    WorkflowSummary,
)
from taskweavn.task.authoring import RawTask
from taskweavn.task.plan_stores import PlanStore
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore, RawTaskStore
from taskweavn.task.views import (
    ConfirmationActionView as CoreConfirmationActionView,
)
from taskweavn.task.views import (
    SessionMessageView as CoreSessionMessageView,
)
from taskweavn.task.views import (
    TaskTreeView as CoreTaskTreeView,
)


def get_session_snapshot_query(
    session_id: str,
    *,
    ask_projection: AskProjectionService | None,
    audit_link_provider: AuditLinkProvider | None,
    authoring_state_store: AuthoringStateStore | None,
    plan_projection: PlanProjectionService,
    plan_store: PlanStore | None,
    project_provider: ProjectProvider,
    raw_task_store: RawTaskStore | None,
    request_id: str | None,
    session_messages: Callable[[str], tuple[SessionMessageView, ...]],
    session_reader: SessionReader,
    snapshot_cursor_provider: SnapshotCursorProvider | None,
    task_projection: TaskProjectionService,
    workflow_provider: WorkflowProvider,
) -> QueryResponse[MainPageSnapshot]:
    try:
        session = session_reader.get(session_id)
        if session is None:
            return QueryResponse[MainPageSnapshot](
                request_id=request_id or _request_id("snapshot", session_id),
                ok=False,
                data=None,
                error=not_found("session not found", session_id=session_id),
                cursor=None,
            )

        source_tree = _list_main_page_plan_tree(task_projection, session.id)
        task_tree = _map_optional_task_tree(
            source_tree,
            authoring_state_store=authoring_state_store,
        )
        stored_plan = active_stored_plan(
            session.id,
            plan_store=plan_store,
            authoring_state_store=authoring_state_store,
        )
        plan_context = active_plan_read_context(
            task_tree,
            stored_plan=stored_plan,
            plan_projection=plan_projection,
        )
        active_plan = plan_context.active_plan
        task_tree = plan_context.task_tree
        archived_plans = archived_plan_views(
            session.id,
            plan_store=plan_store,
            plan_projection=plan_projection,
        )
        messages = _merge_messages(
            _messages_from_tree(source_tree),
            session_messages(session.id),
            _archived_plan_messages(archived_plans),
        )
        confirmations = _confirmations_from_tree(source_tree, session_id=session.id)
        planning = _planning_for_session(
            session.id,
            task_tree=task_tree,
            authoring_state_store=authoring_state_store,
            raw_task_store=raw_task_store,
        )
        pending_asks = (
            () if ask_projection is None else ask_projection.pending_asks(session.id)
        )
        active_ask = (
            None
            if ask_projection is None
            else ask_projection.active_ask(session.id, task_tree=task_tree)
        )
        result = (
            result_from_plan_nodes(
                plan_context.stored_plan_nodes,
                session_id=session.id,
                task_projection=task_projection,
            )
            if plan_context.stored_plan_nodes is not None
            else None
        )
        if result is None and plan_context.legacy_fallback_allowed:
            result = _result_from_tree(
                source_tree,
                session_id=session.id,
                task_projection=task_projection,
            )
        file_change_summary = (
            file_change_summary_from_plan_nodes(
                plan_context.stored_plan_nodes,
                session_id=session.id,
                task_projection=task_projection,
            )
            if plan_context.stored_plan_nodes is not None
            else None
        )
        if file_change_summary is None and plan_context.legacy_fallback_allowed:
            file_change_summary = _file_change_summary_from_tree(
                source_tree,
                session_id=session.id,
                task_projection=task_projection,
            )
        project = project_provider.get_project()
        workflow = workflow_provider.get_workflow(session)
        workflows = workflow_provider.list_workflows()
        session_summary = _session_summary(
            session,
            project=project,
            workflow=workflow,
            status=_derive_session_status(
                session,
                task_tree=task_tree,
                confirmations=confirmations,
                messages=messages,
                active_ask=active_ask,
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
                    status=(
                        "new"
                        if candidate.id != session.id
                        else session_summary.status
                    ),
                )
                for candidate in session_reader.list()
            ),
            session=session_summary,
            planning=planning,
            active_plan=active_plan,
            archived_plans=archived_plans,
            task_tree=task_tree,
            messages=messages,
            pending_confirmations=confirmations,
            pending_asks=pending_asks,
            active_ask=active_ask,
            result=result,
            file_change_summary=file_change_summary,
            audit_links=_audit_links(audit_link_provider, session.id),
            cursor=_snapshot_cursor(
                session,
                cursor_provider=snapshot_cursor_provider,
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


def _audit_links(
    audit_link_provider: AuditLinkProvider | None,
    session_id: str,
) -> tuple[AuditLinkView, ...]:
    if audit_link_provider is None:
        return ()
    return audit_link_provider.list_for_session(session_id)


def _planning_for_session(
    session_id: str,
    *,
    authoring_state_store: AuthoringStateStore | None,
    raw_task_store: RawTaskStore | None,
    task_tree: TaskTreeView | None,
) -> PlanningView | None:
    active = (
        authoring_state_store.get_active(session_id)
        if authoring_state_store is not None
        else None
    )
    raw_task = _active_raw_task(
        session_id,
        authoring_state_store=authoring_state_store,
        raw_task_store=raw_task_store,
    )
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


def _active_raw_task(
    session_id: str,
    *,
    authoring_state_store: AuthoringStateStore | None,
    raw_task_store: RawTaskStore | None,
) -> RawTask | None:
    if raw_task_store is None:
        return None
    if authoring_state_store is not None:
        active = authoring_state_store.get_active(session_id)
        if active.active_raw_task_id is not None:
            raw_task = raw_task_store.get(session_id, active.active_raw_task_id)
            if raw_task is not None:
                return raw_task
    raw_tasks = raw_task_store.list_for_session(session_id)
    return raw_tasks[-1] if raw_tasks else None


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


def _list_main_page_plan_tree(
    task_projection: TaskProjectionService,
    session_id: str,
) -> CoreTaskTreeView:
    plan_tree = cast(
        Callable[[str], CoreTaskTreeView] | None,
        getattr(task_projection, "list_plan_tree", None),
    )
    if plan_tree is not None:
        return plan_tree(session_id)
    return task_projection.list_task_tree(session_id)


def _is_draft_tree(source: CoreTaskTreeView) -> bool:
    return all(node.task_ref.kind == "draft" for node in source.nodes)


def _planning_from_raw_task(
    raw_task: RawTask,
    *,
    task_tree: TaskTreeView | None = None,
    dirty_authoring_state: bool = False,
    authoring_state_cancelled: bool = False,
) -> PlanningView:
    answered_ask_ids = {answer.ask_id for answer in raw_task.answers}
    ask_status: Literal["pending", "superseded"] = (
        "superseded" if task_tree is not None else "pending"
    )
    return PlanningView(
        state=(
            _planning_state_for_task_tree(task_tree)
            if task_tree is not None
            else _planning_state(raw_task)
        ),
        source_raw_task_id=raw_task.raw_task_id,
        title=_planning_title(raw_task),
        summary=raw_task.intent_summary or raw_task.user_input,
        asks=tuple(
            PlanningAskView(
                id=ask.ask_id,
                question=ask.question,
                reason=ask.reason,
                required=ask.required,
                options=tuple(
                    ConfirmationOptionView(
                        value=option.value,
                        label=option.label,
                    )
                    for option in ask.options
                ),
                status="answered" if ask.ask_id in answered_ask_ids else ask_status,
            )
            for ask in raw_task.asks
        ),
        validation=None,
        diagnostics=_planning_diagnostics(
            dirty_authoring_state=dirty_authoring_state,
            authoring_state_cancelled=authoring_state_cancelled,
        ),
    )


def _planning_diagnostics(
    *,
    dirty_authoring_state: bool,
    authoring_state_cancelled: bool,
) -> tuple[PlanningDiagnosticView, ...]:
    diagnostics: list[PlanningDiagnosticView] = []
    if dirty_authoring_state:
        diagnostics.append(
            PlanningDiagnosticView(
                code="dirty_authoring_state",
                severity="warning",
                message=(
                    "Authoring ASK state is still active even though a TaskTree "
                    "already exists."
                ),
            )
        )
    if authoring_state_cancelled:
        diagnostics.append(
            PlanningDiagnosticView(
                code="authoring_state_cancelled",
                severity="info",
                message=(
                    "The previous authoring flow was closed; RawTask facts are "
                    "kept for traceability."
                ),
            )
        )
    return tuple(diagnostics)


def _planning_state_for_task_tree(task_tree: TaskTreeView) -> PlanningState:
    if task_tree.status == "draft":
        return "draft_ready"
    return "published"


def _planning_state(raw_task: RawTask) -> PlanningState:
    if raw_task.status == "created":
        return "capturing_input"
    if raw_task.status == "awaiting_user":
        return "awaiting_user"
    if raw_task.status == "ready_to_plan":
        return "ready_to_plan"
    if raw_task.status == "assessing":
        return "assessing"
    if raw_task.status == "rejected":
        return "rejected"
    return "unknown"


def _planning_title(raw_task: RawTask) -> str:
    if raw_task.status == "awaiting_user":
        return "Planning questions"
    if raw_task.intent_summary is not None:
        return raw_task.intent_summary
    return "Understanding goal"


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


def _archived_plan_messages(
    plans: Sequence[PlanView],
) -> tuple[SessionMessageView, ...]:
    return tuple(
        SessionMessageView(
            id=f"message:archived-plan:{plan.id}:{plan.version}",
            session_id=plan.session_id,
            kind="informational",
            title="Plan archived",
            body=_archived_plan_message_body(plan),
        )
        for plan in plans
    )


def _archived_plan_message_body(plan: PlanView) -> str:
    lines = [
        f"**{plan.title}**",
        "",
        plan.summary,
        "",
        f"{plan.task_count} task{'s' if plan.task_count != 1 else ''} moved to Session history.",
    ]
    if plan.task_nodes:
        lines.extend(("", "Tasks:"))
        lines.extend(
            f"- Task {node.display_index}: {node.title} ({node.status})"
            for node in plan.task_nodes
        )
    return "\n".join(lines)


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
    active_ask: AskRequestView | None = None,
    planning: PlanningView | None = None,
) -> SessionStatus:
    if active_ask is not None:
        return "waiting_user"
    if planning is not None and any(ask.status == "pending" for ask in planning.asks):
        return "waiting_user"
    if confirmations:
        return "waiting_user"
    if task_tree is not None:
        if any(node.execution == "waiting_for_user" for node in task_tree.nodes):
            return "waiting_user"
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


def _ask_statuses(status: str | None) -> tuple[AskStatus, ...] | None:
    if status is None or not status.strip():
        return None
    allowed: set[AskStatus] = {"pending", "answered", "deferred", "cancelled", "expired"}
    statuses: list[AskStatus] = []
    for raw in status.split(","):
        value = raw.strip()
        if value not in allowed:
            raise ValueError(f"unsupported ASK status filter: {value!r}")
        statuses.append(value)
    return tuple(statuses)


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


def _snapshot_cursor(
    session: Session,
    *,
    cursor_provider: SnapshotCursorProvider | None = None,
) -> str | None:
    if cursor_provider is not None:
        return cursor_provider.latest_cursor(session.id)
    return f"snapshot:{session.id}:{session.last_active_at.isoformat()}"


def _request_id(prefix: str, subject: str) -> str:
    return f"{prefix}:{subject}"
