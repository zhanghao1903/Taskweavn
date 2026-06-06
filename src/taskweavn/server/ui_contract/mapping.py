"""Mapping adapters from server-core Task projections to Plato UI contracts."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal

from taskweavn.interaction import AgentMessage
from taskweavn.server.ui_contract.view_models import (
    ConfirmationActionView as ContractConfirmationActionView,
)
from taskweavn.server.ui_contract.view_models import (
    ConfirmationOptionView as ContractConfirmationOptionView,
)
from taskweavn.server.ui_contract.view_models import (
    ExecutionStatus,
    FileChangeItemView,
    FileChangeSummaryView,
    MessageKind,
    ResultCardView,
    ResultSectionView,
    TaskNodeBadges,
    TaskNodeCardView,
    TaskNodePermissions,
    TaskNodeStatus,
    TaskTreeStatus,
)
from taskweavn.server.ui_contract.view_models import (
    SessionMessageView as ContractSessionMessageView,
)
from taskweavn.server.ui_contract.view_models import (
    TaskTreeView as ContractTaskTreeView,
)
from taskweavn.task import views as task_views
from taskweavn.task.models import TaskRef

_DEFAULT_TREE_TITLE = "Task Tree"
_SYNTHETIC_TREE_ID_TEMPLATE = "session:{session_id}:task-tree"
_ContractFileChangeType = Literal["created", "modified", "deleted", "renamed"]


def map_task_tree_view(
    view: task_views.TaskTreeView,
    *,
    tree_id: str | None = None,
    title: str = _DEFAULT_TREE_TITLE,
    status: TaskTreeStatus | None = None,
    version: int = 1,
) -> ContractTaskTreeView:
    """Map server-core TaskTreeView into the transport-facing contract shape."""

    nodes = tuple(
        map_task_node_card(node, display_index=index + 1)
        for index, node in enumerate(view.nodes)
    )
    return ContractTaskTreeView(
        id=tree_id or _synthetic_tree_id(view.session_id),
        session_id=view.session_id,
        title=title,
        status=status or derive_task_tree_status(nodes),
        nodes=nodes,
        version=version,
    )


def map_task_node_card(
    view: task_views.TaskCardView,
    *,
    display_index: int | None = None,
) -> TaskNodeCardView:
    """Map a server-core Task card into the frontend card contract."""

    return TaskNodeCardView(
        id=view.task_ref.id,
        task_ref=view.task_ref,
        parent_id=view.parent_ref.id if view.parent_ref is not None else None,
        title=view.title,
        summary=view.intent_preview,
        status=map_task_node_status(view.status, confirmation=view.confirmation),
        execution=map_task_execution_status(view.status),
        depth=view.depth,
        order_index=view.order_index,
        display_index=(
            display_index if display_index is not None else view.order_index + 1
        ),
        result_ref=view.result_ref,
        error_ref=view.error_ref,
        interruption_requested=view.interrupt_requested,
        badges=map_task_badges(view.badges),
        permissions=map_task_permissions(view.permissions),
        version=1,
    )


def map_task_badges(view: task_views.TaskCardBadges) -> TaskNodeBadges:
    return TaskNodeBadges(
        pending_confirmation_count=view.pending_confirmation_count,
        unread_message_count=view.unread_message_count,
        direct_file_change_count=view.direct_file_change_count,
        subtree_file_change_count=view.subtree_file_change_count,
    )


def map_task_permissions(view: task_views.TaskCardPermissions) -> TaskNodePermissions:
    return TaskNodePermissions(
        can_edit=view.can_edit,
        can_append_guidance=view.can_append_guidance,
        can_resolve_confirmation=view.can_resolve_confirmation,
        can_publish=view.can_publish,
        can_cancel=view.can_cancel,
        can_retry=view.can_retry,
    )


def map_session_message_view(
    view: task_views.SessionMessageView,
) -> ContractSessionMessageView:
    kind = _map_message_kind(view.message_type)
    return ContractSessionMessageView(
        id=view.message_id,
        session_id=view.session_id,
        task_node_id=view.task_ref.id if view.task_ref is not None else None,
        task_ref=view.task_ref,
        kind=kind,
        title=_message_title(view.message_type),
        body=view.content_summary,
        created_at=view.created_at,
        related_confirmation_id=view.related_confirmation_id,
        related_command_id=view.related_action_id,
    )


def map_agent_message_view(message: AgentMessage) -> ContractSessionMessageView:
    """Map an interaction-layer AgentMessage into the UI message contract."""

    task_ref = _task_ref_from_agent_message(message)
    kind = _agent_message_kind(message)
    return ContractSessionMessageView(
        id=message.message_id,
        session_id=message.session_id,
        task_node_id=None if task_ref is None else task_ref.id,
        task_ref=task_ref,
        kind=kind,
        title=_agent_message_title(message, kind),
        body=message.content,
        created_at=message.created_at,
        related_confirmation_id=(
            message.parent_message_id if message.message_type == "response" else None
        ),
        related_command_id=message.related_action_id,
    )


def map_confirmation_action_view(
    view: task_views.ConfirmationActionView,
    *,
    session_id: str,
) -> ContractConfirmationActionView:
    options = tuple(map_confirmation_option_view(option) for option in view.options)
    default_option_value = _default_option_value(
        view.default_option_id,
        source_options=view.options,
    )
    return ContractConfirmationActionView(
        id=view.confirmation_id,
        session_id=session_id,
        task_node_id=view.task_ref.id,
        task_ref=view.task_ref,
        title="Confirmation required",
        body=view.prompt,
        options=options,
        default_option_value=default_option_value,
        status=view.status,
        risk_label=view.risk_summary,
    )


def map_confirmation_option_view(
    view: task_views.ConfirmationOptionView,
) -> ContractConfirmationOptionView:
    return ContractConfirmationOptionView(
        value=view.value,
        label=view.label,
        tone="primary" if view.is_default else "secondary",
    )


def map_file_change_item(view: task_views.TaskFileChangeSummary) -> FileChangeItemView:
    return FileChangeItemView(
        path=view.path,
        change_type=_map_file_change_type(view.change_type),
        summary=view.summary,
        owner_task_node_id=view.owner_task_ref.id,
    )


def map_file_change_summary_view(
    changes: Iterable[task_views.TaskFileChangeSummary],
    *,
    session_id: str,
    task_ref: TaskRef | None = None,
    recursive: bool,
    summary: str | None = None,
) -> FileChangeSummaryView:
    items = tuple(map_file_change_item(change) for change in changes)
    return FileChangeSummaryView(
        session_id=session_id,
        task_node_id=task_ref.id if task_ref is not None else None,
        recursive=recursive,
        changed_files=items,
        summary=summary or _file_change_summary_text(items),
    )


def map_result_card_view(
    view: task_views.TaskSummaryView,
    *,
    session_id: str,
) -> ResultCardView:
    sections: list[ResultSectionView] = []
    if view.failure_reason is not None:
        sections.append(
            ResultSectionView(
                title="Failure reason",
                body=view.failure_reason,
                kind="text",
            )
        )
    if view.follow_up_suggestions:
        sections.append(
            ResultSectionView(
                title="Follow-up suggestions",
                body="\n".join(f"- {item}" for item in view.follow_up_suggestions),
                kind="list",
            )
        )
    if view.artifact_refs:
        sections.append(
            ResultSectionView(
                title="Artifacts",
                body="\n".join(view.artifact_refs),
                kind="link",
            )
        )
    return ResultCardView(
        id=f"result:{view.task_ref.kind}:{view.task_ref.id}",
        session_id=session_id,
        task_node_id=view.task_ref.id,
        title="Task result",
        summary=view.summary,
        sections=tuple(sections),
        updated_at=view.updated_at,
    )


def map_task_node_status(
    status: task_views.TaskViewStatus,
    *,
    confirmation: task_views.ConfirmationActionView | None = None,
) -> TaskNodeStatus:
    if confirmation is not None and confirmation.status == "pending":
        return "waiting_user"
    if status == "waiting_for_user":
        return "waiting_user"
    if status == "pending":
        return "queued"
    if status in {"draft", "running", "done", "failed", "cancelled"}:
        return status
    raise ValueError(f"unsupported task view status: {status!r}")


def map_task_execution_status(status: task_views.TaskViewStatus) -> ExecutionStatus:
    if status == "draft":
        return "not_started"
    if status in {
        "pending",
        "running",
        "waiting_for_user",
        "done",
        "failed",
        "cancelled",
    }:
        return status
    raise ValueError(f"unsupported task view status: {status!r}")


def derive_task_tree_status(nodes: Sequence[TaskNodeCardView]) -> TaskTreeStatus:
    if not nodes:
        return "draft"
    statuses = {node.status for node in nodes}
    if "running" in statuses or "waiting_user" in statuses:
        return "running"
    if statuses == {"done"}:
        return "completed"
    if "failed" in statuses:
        return "failed"
    if statuses & {"queued", "done"}:
        return "published"
    return "draft"


def _synthetic_tree_id(session_id: str) -> str:
    return _SYNTHETIC_TREE_ID_TEMPLATE.format(session_id=session_id)


def _map_message_kind(message_type: task_views.TaskMessageViewType) -> MessageKind:
    if message_type == "confirmation":
        return "actionable"
    return "informational"


def _message_title(message_type: task_views.TaskMessageViewType) -> str:
    return {
        "user": "User message",
        "agent": "Agent message",
        "system": "System message",
        "confirmation": "Confirmation required",
        "result": "Result",
    }[message_type]


def _task_ref_from_agent_message(message: AgentMessage) -> TaskRef | None:
    if message.task_id is None:
        return None
    if message.context.get("task_ref_kind") == "draft":
        return TaskRef.draft(message.task_id)
    return TaskRef.published(message.task_id)


def _agent_message_kind(message: AgentMessage) -> MessageKind:
    if message.context.get("ui_kind") == "error":
        return "error"
    if message.message_type == "actionable":
        return "actionable"
    if message.message_type == "response":
        return "response"
    return "informational"


def _agent_message_title(message: AgentMessage, kind: MessageKind) -> str:
    title = message.context.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    if kind == "actionable":
        return "Confirmation required"
    if kind == "response":
        return "User response"
    if kind == "error":
        return "Error"
    if message.agent_id == "user":
        return "User message"
    if message.agent_id == "system":
        return "System message"
    return "Agent message"


def _default_option_value(
    default_option_id: str | None,
    *,
    source_options: Sequence[task_views.ConfirmationOptionView],
) -> str | None:
    if default_option_id is None:
        return None
    for option in source_options:
        if option.option_id == default_option_id:
            return option.value
    return None


def _map_file_change_type(
    change_type: task_views.FileChangeType,
) -> _ContractFileChangeType:
    if change_type == "unknown":
        return "modified"
    return change_type


def _file_change_summary_text(items: Sequence[FileChangeItemView]) -> str:
    if not items:
        return "No file changes."
    if len(items) == 1:
        return "1 file changed."
    return f"{len(items)} files changed."
