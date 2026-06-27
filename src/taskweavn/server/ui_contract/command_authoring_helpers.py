"""Authoring state helpers for the UI command gateway."""

from __future__ import annotations

from taskweavn.server.ui_contract.command_mapping import (
    _command_response,
    _synthetic_task_tree_id,
    _TaskTreeIdentityError,
)
from taskweavn.server.ui_contract.commands import (
    AnswerAuthoringAskBatchPayload,
    PublishTaskTreePayload,
)
from taskweavn.server.ui_contract.envelopes import CommandRequest, CommandResponse
from taskweavn.server.ui_contract.refs import (
    AffectedObjectRef,
    AffectedScope,
    ObjectRef,
)
from taskweavn.task.authoring import RawTask
from taskweavn.task.commands import CommandResult as CoreCommandResult
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore, RawTaskStore


def latest_raw_task(
    raw_task_store: RawTaskStore | None,
    session_id: str,
) -> RawTask | None:
    if raw_task_store is None:
        return None
    raw_tasks = raw_task_store.list_for_session(session_id)
    return raw_tasks[-1] if raw_tasks else None


def raw_task_ready_for_planning(
    raw_task_store: RawTaskStore | None,
    session_id: str,
    raw_task_id: str,
) -> bool:
    if raw_task_store is None:
        return True
    raw_task = raw_task_store.get(session_id, raw_task_id)
    return raw_task is not None and raw_task.ready_for_planning


def raw_task_all_asks_answered(
    raw_task_store: RawTaskStore | None,
    session_id: str,
    raw_task_id: str,
) -> bool:
    if raw_task_store is None:
        return False
    raw_task = raw_task_store.get(session_id, raw_task_id)
    if raw_task is None or not raw_task.asks:
        return False
    answered_ask_ids = {answer.ask_id for answer in raw_task.answers}
    return all(ask.ask_id in answered_ask_ids for ask in raw_task.asks)


def stale_authoring_context_response(
    raw_task_id: str,
    request: CommandRequest[AnswerAuthoringAskBatchPayload],
) -> CommandResponse:
    raw_ref = ObjectRef(kind="raw_task", id=raw_task_id)
    ask_refs = authoring_ask_refs(request)
    result = CoreCommandResult(
        status="rejected",
        message=(
            "stale_authoring_context: authoring ASK was superseded "
            "by the active TaskTree"
        ),
    )
    return _command_response(
        request,
        result,
        object_refs=(raw_ref, *ask_refs),
        affected_objects=(
            AffectedObjectRef(
                ref=raw_ref,
                impact="superseded",
                reason="stale_authoring_context",
            ),
            *(
                AffectedObjectRef(
                    ref=ask_ref,
                    impact="superseded",
                    reason="stale_authoring_context",
                )
                for ask_ref in ask_refs
            ),
        ),
        suggested_queries=("session.snapshot", "session.messages", "task.tree"),
        affected_scopes=(
            AffectedScope(kind="session"),
            AffectedScope(kind="messages"),
            AffectedScope(kind="task_tree"),
        ),
    )


def answered_authoring_ask_batch_response(
    raw_task_id: str,
    request: CommandRequest[AnswerAuthoringAskBatchPayload],
    result: CoreCommandResult,
) -> CommandResponse:
    raw_ref = ObjectRef(kind="raw_task", id=raw_task_id)
    ask_refs = authoring_ask_refs(request)
    return _command_response(
        request,
        result,
        object_refs=(raw_ref, *ask_refs),
        affected_objects=(
            AffectedObjectRef(
                ref=raw_ref,
                impact="changed",
                reason="RawTask authoring ASK answers were submitted.",
            ),
            *(
                AffectedObjectRef(
                    ref=ask_ref,
                    impact="changed",
                    reason="RawTask authoring ASK was answered.",
                )
                for ask_ref in ask_refs
            ),
        ),
        suggested_queries=("session.snapshot", "session.messages", "task.tree"),
        affected_scopes=(
            AffectedScope(kind="session"),
            AffectedScope(kind="messages"),
            AffectedScope(kind="task_tree"),
        ),
    )


def authoring_ask_refs(
    request: CommandRequest[AnswerAuthoringAskBatchPayload],
) -> tuple[ObjectRef, ...]:
    return tuple(
        ObjectRef(kind="raw_task_ask", id=answer.ask_id)
        for answer in request.payload.answers
    )


def authoring_context_is_superseded(
    authoring_state_store: AuthoringStateStore | None,
    task_projection: TaskProjectionService | None,
    session_id: str,
) -> bool:
    if authoring_state_store is None:
        return session_has_published_task_tree(task_projection, session_id)
    active = authoring_state_store.get_active(session_id)
    if active.active_state in {"draft_tree", "published", "cancelled"}:
        return True
    return active.active_state == "raw_task" and session_has_published_task_tree(
        task_projection,
        session_id,
    )


def session_has_published_task_tree(
    task_projection: TaskProjectionService | None,
    session_id: str,
) -> bool:
    if task_projection is None:
        return False
    try:
        tree = task_projection.list_task_tree(
            session_id,
            include_drafts=False,
            include_published=True,
        )
    except Exception:  # noqa: BLE001 - stale detection must not crash commands.
        return False
    return bool(tree.nodes)


def resolve_publish_draft_tree_id(
    authoring_state_store: AuthoringStateStore | None,
    request: CommandRequest[PublishTaskTreePayload],
) -> str:
    provided = request.payload.task_tree_id
    if authoring_state_store is None:
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

    active = authoring_state_store.get_active(request.session_id)
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


__all__ = [
    "answered_authoring_ask_batch_response",
    "authoring_context_is_superseded",
    "authoring_ask_refs",
    "latest_raw_task",
    "raw_task_all_asks_answered",
    "raw_task_ready_for_planning",
    "resolve_publish_draft_tree_id",
    "session_has_published_task_tree",
    "stale_authoring_context_response",
]
