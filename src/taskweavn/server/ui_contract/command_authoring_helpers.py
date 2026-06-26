"""Authoring state helpers for the UI command gateway."""

from __future__ import annotations

from taskweavn.server.ui_contract.command_mapping import (
    _synthetic_task_tree_id,
    _TaskTreeIdentityError,
)
from taskweavn.server.ui_contract.commands import PublishTaskTreePayload
from taskweavn.server.ui_contract.envelopes import CommandRequest
from taskweavn.task.authoring import RawTask
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
    "authoring_context_is_superseded",
    "latest_raw_task",
    "raw_task_all_asks_answered",
    "raw_task_ready_for_planning",
    "resolve_publish_draft_tree_id",
    "session_has_published_task_tree",
]
