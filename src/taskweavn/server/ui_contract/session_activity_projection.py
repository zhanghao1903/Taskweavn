"""Session Conversation / Activity projection helpers."""

from __future__ import annotations

from collections.abc import Sequence

from taskweavn.server.runtime_input_activity import READ_ONLY_INQUIRY_ACTIVITY_TITLE
from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.server.ui_contract.view_models import (
    AskRequestView,
    ConfirmationActionView,
    FileChangeSummaryView,
    PlanView,
    ResultCardView,
    SessionActivityItemKind,
    SessionActivityItemView,
    SessionActivityRefView,
    SessionActivitySideEffect,
    SessionActivitySourceKind,
    SessionActivityTimelineResult,
    SessionMessageView,
    TaskNodeCardView,
    TaskTreeView,
)

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


class DefaultSessionActivityProjectionService:
    """Project user-readable Activity from existing safe UI facts."""

    def project(
        self,
        *,
        session_id: str,
        messages: Sequence[SessionMessageView] = (),
        active_plan: PlanView | None = None,
        task_tree: TaskTreeView | None = None,
        pending_asks: Sequence[AskRequestView] = (),
        active_ask: AskRequestView | None = None,
        confirmations: Sequence[ConfirmationActionView] = (),
        result: ResultCardView | None = None,
        file_change_summary: FileChangeSummaryView | None = None,
        limit: int = _DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> SessionActivityTimelineResult:
        items: list[SessionActivityItemView] = []
        items.extend(_message_items(messages))
        if active_plan is not None:
            items.append(_plan_item(active_plan))
            items.extend(_task_items(active_plan.task_nodes, session_id=session_id))
        elif task_tree is not None:
            items.extend(_task_items(task_tree.nodes, session_id=session_id))
        items.extend(_ask_items(pending_asks, active_ask=active_ask))
        items.extend(_confirmation_items(confirmations))
        if result is not None:
            items.append(_result_item(result))
        if file_change_summary is not None:
            items.append(_file_summary_item(file_change_summary))

        ordered = _dedupe_and_order(items)
        page, next_cursor = _page_items(ordered, limit=limit, cursor=cursor)
        return SessionActivityTimelineResult(
            session_id=session_id,
            items=tuple(page),
            next_cursor=next_cursor,
            total_count=len(ordered),
        )


def _message_items(
    messages: Sequence[SessionMessageView],
) -> tuple[SessionActivityItemView, ...]:
    return tuple(_message_item(message) for message in messages)


def _message_item(message: SessionMessageView) -> SessionActivityItemView:
    kind = _message_activity_kind(message)
    side_effect = _message_side_effect(message, kind)
    activity_id = f"activity:message:{message.id}"
    source_kind: SessionActivitySourceKind = "message_stream"
    source_id = message.id
    runtime_kind = _runtime_input_activity_kind(message)
    if runtime_kind is not None:
        source_kind = "router"
        source_id = message.related_command_id or message.id
        activity_id = f"activity:runtime-input:{source_id}:{runtime_kind}"
    elif message.title == READ_ONLY_INQUIRY_ACTIVITY_TITLE:
        source_kind = "router"
        source_id = message.related_command_id or message.id
        activity_id = f"activity:inquiry:{source_id}"
    related_refs = (
        message.activity_related_refs
        if message.activity_related_refs
        else (_message_ref(message),)
    )
    return SessionActivityItemView(
        id=activity_id,
        session_id=message.session_id,
        kind=kind,
        title=message.title,
        body=message.body,
        occurred_at=message.created_at,
        scope_kind="task" if message.task_node_id is not None else "session",
        task_node_id=message.task_node_id,
        side_effect=side_effect,
        related_refs=related_refs,
        source_kind=source_kind,
        source_id=source_id,
    )


def _message_activity_kind(message: SessionMessageView) -> SessionActivityItemKind:
    runtime_kind = _runtime_input_activity_kind(message)
    if runtime_kind is not None:
        return runtime_kind
    if message.title == READ_ONLY_INQUIRY_ACTIVITY_TITLE:
        return "answer"
    if message.kind == "response":
        return "answer"
    if message.kind == "actionable":
        return "confirmation_requested"
    if message.kind == "error":
        return "recovery_note"
    if message.title.lower().startswith("user"):
        return "user_input"
    return "execution_update"


def _message_side_effect(
    message: SessionMessageView,
    kind: SessionActivityItemKind,
) -> SessionActivitySideEffect:
    del message
    if kind == "user_input":
        return "context_effect"
    if kind == "guidance_recorded":
        return "context_effect"
    if kind in {"ask_answered", "confirmation_resolved"}:
        return "resume_effect"
    if kind == "confirmation_requested":
        return "authorization_effect"
    if kind == "recovery_note":
        return "state_effect"
    if kind in {"answer", "router_interpretation"}:
        return "no_effect"
    return "state_effect"


def _runtime_input_activity_kind(
    message: SessionMessageView,
) -> SessionActivityItemKind | None:
    # Runtime Input activity kind is carried in the original AgentMessage
    # context and mapped into the user-facing title/body/refs. The current
    # SessionMessageView intentionally exposes only safe fields, so route using
    # reserved titles emitted by runtime publishers.
    title = message.title.lower()
    if title == "guidance recorded":
        return "guidance_recorded"
    if title == "ask answered":
        return "ask_answered"
    if title == "confirmation resolved":
        return "confirmation_resolved"
    if title in {"task created", "execution work created"}:
        return "task_created"
    if title == "task changed":
        return "task_changed"
    if title == "task removed":
        return "task_removed"
    if title == "user input":
        return "user_input"
    if title in {
        "router interpretation",
        "runtime input routed",
        "runtime input needs clarification",
        "runtime input unsupported",
        "runtime command routed",
    }:
        return "router_interpretation"
    return None


def _plan_item(plan: PlanView) -> SessionActivityItemView:
    return SessionActivityItemView(
        id=f"activity:plan:{plan.id}:{plan.status}:{plan.version}",
        session_id=plan.session_id,
        kind="plan_updated",
        title="Plan updated",
        body=f"{plan.title}: {plan.summary}",
        scope_kind="plan",
        plan_id=plan.id,
        side_effect="state_effect",
        related_refs=(_plan_ref(plan),),
        source_kind="plan_projection",
        source_id=plan.id,
    )


def _task_items(
    nodes: Sequence[TaskNodeCardView],
    *,
    session_id: str,
) -> tuple[SessionActivityItemView, ...]:
    return tuple(_task_item(node, session_id=session_id) for node in nodes)


def _task_item(node: TaskNodeCardView, *, session_id: str) -> SessionActivityItemView:
    kind = _task_activity_kind(node)
    return SessionActivityItemView(
        id=f"activity:task:{node.id}:{node.status}:{node.execution}:{node.version}",
        session_id=session_id,
        kind=kind,
        title=_task_activity_title(node, kind),
        body=node.summary,
        scope_kind="task",
        plan_id=node.plan_id,
        task_node_id=node.id,
        side_effect="state_effect",
        related_refs=(_task_ref(node),),
        source_kind="task_projection",
        source_id=node.id,
    )


def _task_activity_kind(node: TaskNodeCardView) -> SessionActivityItemKind:
    if node.status in {"draft", "queued"}:
        return "task_created"
    if node.status in {"failed", "cancelled"}:
        return "recovery_note"
    return "execution_update"


def _task_activity_title(
    node: TaskNodeCardView,
    kind: SessionActivityItemKind,
) -> str:
    if kind == "task_created":
        return f"Task {node.display_index} created"
    if kind == "recovery_note":
        return f"Task {node.display_index} needs attention"
    return f"Task {node.display_index} updated"


def _ask_items(
    asks: Sequence[AskRequestView],
    *,
    active_ask: AskRequestView | None,
) -> tuple[SessionActivityItemView, ...]:
    by_id = {ask.id: ask for ask in asks}
    if active_ask is not None:
        by_id[active_ask.id] = active_ask
    return tuple(_ask_item(ask) for ask in by_id.values())


def _ask_item(ask: AskRequestView) -> SessionActivityItemView:
    return SessionActivityItemView(
        id=f"activity:ask:{ask.id}:{ask.status}",
        session_id=ask.session_id,
        kind="ask_asked",
        title="ASK requested",
        body=ask.question,
        occurred_at=ask.created_at,
        scope_kind="task" if ask.task_node_id is not None else "session",
        task_node_id=ask.task_node_id,
        side_effect="resume_effect",
        related_refs=(_ask_ref(ask),),
        source_kind="ask_projection",
        source_id=ask.id,
    )


def _confirmation_items(
    confirmations: Sequence[ConfirmationActionView],
) -> tuple[SessionActivityItemView, ...]:
    return tuple(_confirmation_item(confirmation) for confirmation in confirmations)


def _confirmation_item(
    confirmation: ConfirmationActionView,
) -> SessionActivityItemView:
    return SessionActivityItemView(
        id=f"activity:confirmation:{confirmation.id}:{confirmation.status}",
        session_id=confirmation.session_id,
        kind="confirmation_requested",
        title=confirmation.title,
        body=confirmation.body,
        occurred_at=confirmation.created_at,
        scope_kind="task",
        task_node_id=confirmation.task_node_id,
        side_effect="authorization_effect",
        related_refs=(_confirmation_ref(confirmation),),
        source_kind="confirmation_projection",
        source_id=confirmation.id,
    )


def _result_item(result: ResultCardView) -> SessionActivityItemView:
    return SessionActivityItemView(
        id=f"activity:result:{result.id}",
        session_id=result.session_id,
        kind="result_ready",
        title=result.title,
        body=result.summary,
        occurred_at=result.updated_at,
        scope_kind="task" if result.task_node_id is not None else "session",
        task_node_id=result.task_node_id,
        side_effect="evidence_effect",
        related_refs=(_result_ref(result),),
        source_kind="result_projection",
        source_id=result.id,
    )


def _file_summary_item(
    summary: FileChangeSummaryView,
) -> SessionActivityItemView:
    return SessionActivityItemView(
        id=f"activity:file-summary:{summary.session_id}:{summary.task_node_id or 'session'}",
        session_id=summary.session_id,
        kind="file_summary",
        title="File changes ready",
        body=summary.summary,
        occurred_at=summary.updated_at,
        scope_kind="task" if summary.task_node_id is not None else "session",
        task_node_id=summary.task_node_id,
        side_effect="evidence_effect",
        related_refs=tuple(
            SessionActivityRefView(
                kind="file",
                id=item.path,
                label=item.path,
            )
            for item in summary.changed_files[:10]
        ),
        source_kind="file_projection",
        source_id=summary.task_node_id or summary.session_id,
    )


def _message_ref(message: SessionMessageView) -> SessionActivityRefView:
    return SessionActivityRefView(
        kind="message",
        id=message.id,
        label=message.title,
        object_ref=ObjectRef(kind="message", id=message.id),
    )


def _plan_ref(plan: PlanView) -> SessionActivityRefView:
    return SessionActivityRefView(
        kind="plan",
        id=plan.id,
        label=plan.title,
        object_ref=ObjectRef(kind="plan", id=plan.id),
    )


def _task_ref(node: TaskNodeCardView) -> SessionActivityRefView:
    object_ref = None
    if node.task_ref is not None:
        object_ref = ObjectRef(
            kind="draft_task" if node.task_ref.kind == "draft" else "published_task",
            id=node.task_ref.id,
        )
    return SessionActivityRefView(
        kind="task",
        id=node.id,
        label=node.title,
        object_ref=object_ref,
    )


def _ask_ref(ask: AskRequestView) -> SessionActivityRefView:
    return SessionActivityRefView(
        kind="ask",
        id=ask.id,
        label="ASK",
        object_ref=ObjectRef(kind="ask", id=ask.id),
    )


def _confirmation_ref(
    confirmation: ConfirmationActionView,
) -> SessionActivityRefView:
    return SessionActivityRefView(
        kind="confirmation",
        id=confirmation.id,
        label="Confirmation",
    )


def _result_ref(result: ResultCardView) -> SessionActivityRefView:
    return SessionActivityRefView(
        kind="result",
        id=result.id,
        label=result.title,
    )


def _dedupe_and_order(
    items: Sequence[SessionActivityItemView],
) -> tuple[SessionActivityItemView, ...]:
    by_id: dict[str, SessionActivityItemView] = {}
    for item in items:
        if not item.session_id:
            continue
        by_id[item.id] = item
    return tuple(
        sorted(
            by_id.values(),
            key=lambda item: (item.occurred_at, item.id),
            reverse=True,
        )
    )


def _page_items(
    items: Sequence[SessionActivityItemView],
    *,
    limit: int,
    cursor: str | None,
) -> tuple[tuple[SessionActivityItemView, ...], str | None]:
    checked_limit = min(max(limit, 1), _MAX_LIMIT)
    offset = _cursor_offset(cursor)
    page = tuple(items[offset : offset + checked_limit])
    next_offset = offset + checked_limit
    next_cursor = str(next_offset) if next_offset < len(items) else None
    return page, next_cursor


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None or cursor == "":
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise ValueError("Activity cursor must be an integer offset") from exc
    if value < 0:
        raise ValueError("Activity cursor must be non-negative")
    return value


__all__ = ["DefaultSessionActivityProjectionService"]
