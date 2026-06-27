"""Session Activity query helpers for the UI query gateway."""

from __future__ import annotations

from collections.abc import Callable

from taskweavn.server.ui_contract.ask_projection import AskProjectionService
from taskweavn.server.ui_contract.envelopes import QueryResponse
from taskweavn.server.ui_contract.errors import bad_request, internal_error, not_found
from taskweavn.server.ui_contract.gateway_protocols import SessionReader
from taskweavn.server.ui_contract.plan_projection import PlanProjectionService
from taskweavn.server.ui_contract.plan_read_helpers import (
    active_plan_read_context,
    active_stored_plan,
    archived_plan_views,
    file_change_summary_from_plan_nodes,
    result_from_plan_nodes,
)
from taskweavn.server.ui_contract.query_snapshot_helpers import (
    _confirmations_from_tree,
    _file_change_summary_from_tree,
    _list_main_page_plan_tree,
    _map_optional_task_tree,
    _merge_messages,
    _messages_from_tree,
    _request_id,
    _result_from_tree,
)
from taskweavn.server.ui_contract.session_activity_projection import (
    DefaultSessionActivityProjectionService,
)
from taskweavn.server.ui_contract.view_models import (
    SessionActivityTimelineResult,
    SessionMessageView,
)
from taskweavn.task.plan_stores import PlanStore
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore


def list_session_activity_query(
    session_id: str,
    *,
    activity_projection: DefaultSessionActivityProjectionService,
    ask_projection: AskProjectionService | None,
    authoring_state_store: AuthoringStateStore | None,
    cursor: str | None = None,
    limit: int = 50,
    plan_projection: PlanProjectionService,
    plan_store: PlanStore | None,
    request_id: str | None = None,
    session_messages: Callable[[str], tuple[SessionMessageView, ...]],
    session_reader: SessionReader,
    task_projection: TaskProjectionService,
) -> QueryResponse[SessionActivityTimelineResult]:
    try:
        session = session_reader.get(session_id)
        if session is None:
            return QueryResponse[SessionActivityTimelineResult](
                request_id=request_id or _request_id("activity", session_id),
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
        messages = _merge_messages(
            _messages_from_tree(source_tree),
            session_messages(session.id),
        )
        confirmations = _confirmations_from_tree(source_tree, session_id=session.id)
        pending_asks = (
            () if ask_projection is None else ask_projection.pending_asks(session.id)
        )
        active_ask = (
            None
            if ask_projection is None
            else ask_projection.active_ask(session.id, task_tree=plan_context.task_tree)
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
        activity = activity_projection.project(
            session_id=session.id,
            messages=messages,
            active_plan=plan_context.active_plan,
            archived_plans=archived_plan_views(
                session.id,
                plan_store=plan_store,
                plan_projection=plan_projection,
            ),
            task_tree=plan_context.task_tree,
            pending_asks=pending_asks,
            active_ask=active_ask,
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
