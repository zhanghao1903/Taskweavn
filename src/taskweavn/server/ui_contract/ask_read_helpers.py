"""ASK read helpers used by the UI query gateway."""

from __future__ import annotations

from taskweavn.server.ui_contract.ask_projection import AskProjectionService
from taskweavn.server.ui_contract.envelopes import QueryResponse
from taskweavn.server.ui_contract.errors import bad_request, internal_error, not_found
from taskweavn.server.ui_contract.gateway_protocols import SessionReader
from taskweavn.server.ui_contract.main_page_read_helpers import (
    _ask_statuses,
    _list_main_page_plan_tree,
    _map_optional_task_tree,
    _request_id,
)
from taskweavn.server.ui_contract.view_models import (
    AskListResult,
    AskRequestView,
    TaskTreeView,
)
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore


def list_asks_response(
    session_id: str,
    *,
    ask_projection: AskProjectionService | None,
    authoring_state_store: AuthoringStateStore | None,
    request_id: str | None,
    session_reader: SessionReader,
    status: str | None,
    task_node_id: str | None,
    task_projection: TaskProjectionService,
) -> QueryResponse[AskListResult]:
    try:
        if ask_projection is None:
            return QueryResponse[AskListResult](
                request_id=request_id or _request_id("asks", session_id),
                ok=True,
                data=AskListResult(session_id=session_id),
                error=None,
            )
        session = session_reader.get(session_id)
        if session is None:
            return QueryResponse[AskListResult](
                request_id=request_id or _request_id("asks", session_id),
                ok=False,
                data=None,
                error=not_found("session not found", session_id=session_id),
            )
        task_tree = _map_optional_task_tree(
            _list_main_page_plan_tree(task_projection, session.id),
            authoring_state_store=authoring_state_store,
        )
        result = ask_projection.list_asks(
            session.id,
            statuses=_ask_statuses(status),
            task_id=task_node_id,
            task_tree=task_tree,
        )
        return QueryResponse[AskListResult](
            request_id=request_id or _request_id("asks", session.id),
            ok=True,
            data=result,
            error=None,
        )
    except ValueError as exc:
        return QueryResponse[AskListResult](
            request_id=request_id or _request_id("asks", session_id),
            ok=False,
            data=None,
            error=bad_request(str(exc), session_id=session_id),
        )
    except Exception as exc:
        return QueryResponse[AskListResult](
            request_id=request_id or _request_id("asks", session_id),
            ok=False,
            data=None,
            error=internal_error(
                "Unable to load ASK list",
                error_type=type(exc).__name__,
            ),
        )


def get_ask_response(
    session_id: str,
    ask_id: str,
    *,
    ask_projection: AskProjectionService | None,
    request_id: str | None,
) -> QueryResponse[AskRequestView]:
    try:
        ask = None if ask_projection is None else ask_projection.get_ask(
            session_id,
            ask_id,
        )
        if ask is None:
            return QueryResponse[AskRequestView](
                request_id=request_id or _request_id("ask", ask_id),
                ok=False,
                data=None,
                error=not_found("ASK not found", session_id=session_id, ask_id=ask_id),
            )
        return QueryResponse[AskRequestView](
            request_id=request_id or _request_id("ask", ask_id),
            ok=True,
            data=ask,
            error=None,
        )
    except Exception as exc:
        return QueryResponse[AskRequestView](
            request_id=request_id or _request_id("ask", ask_id),
            ok=False,
            data=None,
            error=internal_error(
                "Unable to load ASK",
                error_type=type(exc).__name__,
            ),
        )


def pending_asks(
    session_id: str,
    *,
    ask_projection: AskProjectionService | None,
) -> tuple[AskRequestView, ...]:
    if ask_projection is None:
        return ()
    return ask_projection.pending_asks(session_id)


def active_ask(
    session_id: str,
    *,
    ask_projection: AskProjectionService | None,
    task_tree: TaskTreeView | None,
) -> AskRequestView | None:
    if ask_projection is None:
        return None
    return ask_projection.active_ask(session_id, task_tree=task_tree)
