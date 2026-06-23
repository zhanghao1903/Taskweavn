"""Projection service for Task-first UI views.

The service is intentionally read-only. It combines Task domain facts, draft
authoring facts, messages, file summaries, and result summaries into UI
ViewModels without mutating any backend source.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from taskweavn.interaction import AgentMessage, MessageStream
from taskweavn.task.models import DraftTaskNode, DraftTaskTree, TaskDomain, TaskRef
from taskweavn.task.stores import AuthoringStateStore, DraftTaskStore, TaskStore
from taskweavn.task.views import (
    ConfirmationActionView,
    ConfirmationOptionView,
    SessionMessageView,
    TaskCardAction,
    TaskCardBadges,
    TaskCardPermissions,
    TaskCardView,
    TaskDetailView,
    TaskFileChangeSummary,
    TaskMessageViewType,
    TaskProgressView,
    TaskSummaryView,
    TaskTreeView,
    TaskViewStatus,
)


@runtime_checkable
class FileChangeStore(Protocol):
    def list_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        recursive: bool = False,
    ) -> list[TaskFileChangeSummary]: ...


@runtime_checkable
class TaskSummaryStore(Protocol):
    def get(self, session_id: str, task_id: str) -> TaskSummaryView | None: ...


@runtime_checkable
class TaskProjectionService(Protocol):
    def list_task_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> TaskTreeView: ...

    def get_task_card(self, session_id: str, task_ref: TaskRef) -> TaskCardView: ...

    def get_task_detail(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        message_limit: int = 100,
    ) -> TaskDetailView: ...


class DefaultTaskProjectionService:
    """Default deterministic implementation of TaskProjectionService."""

    def __init__(
        self,
        *,
        task_store: TaskStore,
        draft_store: DraftTaskStore | None = None,
        message_stream: MessageStream | None = None,
        file_change_store: FileChangeStore | None = None,
        summary_store: TaskSummaryStore | None = None,
        authoring_state_store: AuthoringStateStore | None = None,
    ) -> None:
        self._task_store = task_store
        self._draft_store = draft_store
        self._message_stream = message_stream
        self._file_change_store = file_change_store
        self._summary_store = summary_store
        self._authoring_state_store = authoring_state_store

    def list_task_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> TaskTreeView:
        nodes: list[TaskCardView] = []
        if include_drafts and self._draft_store is not None:
            nodes.extend(self._draft_cards(session_id, root_ref=root_ref))
        if include_published:
            nodes.extend(self._published_cards(session_id, root_ref=root_ref))
        title, summary = self._plan_metadata(session_id)
        return TaskTreeView(
            session_id=session_id,
            title=title,
            summary=summary,
            nodes=tuple(nodes),
        )

    def list_plan_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> TaskTreeView:
        """Project the Product 1.1 Plan view as a flat TaskNode list.

        Legacy draft/published stores may still contain parent-child links.
        The main product surface intentionally hides that hierarchy until a
        later TaskNode hierarchy design earns its complexity.
        """

        nodes: list[TaskCardView] = []
        if include_drafts and self._draft_store is not None:
            nodes.extend(self._draft_plan_cards(session_id, root_ref=root_ref))
        if include_published:
            nodes.extend(self._published_plan_cards(session_id, root_ref=root_ref))
        title, summary = self._plan_metadata(session_id)
        return TaskTreeView(
            session_id=session_id,
            title=title,
            summary=summary,
            nodes=tuple(nodes),
        )

    def get_task_card(self, session_id: str, task_ref: TaskRef) -> TaskCardView:
        if task_ref.kind == "draft":
            if self._draft_store is None:
                raise LookupError("draft_store is not configured")
            node = self._draft_store.get_node(session_id, task_ref.id)
            if node is None:
                raise LookupError(f"draft task {task_ref.id!r} not found")
            return self._project_draft_node(node, depth=0, parent_ref=None, root_ref=task_ref)

        tasks = self._task_store.list_for_session(session_id)
        task_by_id = {task.task_id: task for task in tasks}
        task = task_by_id.get(task_ref.id)
        if task is None:
            raise LookupError(f"task {task_ref.id!r} not found")
        depth = self._depth(task, task_by_id)
        parent_ref = TaskRef.published(task.parent_id) if task.parent_id is not None else None
        return self._project_task(
            task,
            tasks=tasks,
            depth=depth,
            parent_ref=parent_ref,
            root_ref=TaskRef.published(task.root_id),
        )

    def get_task_detail(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        message_limit: int = 100,
    ) -> TaskDetailView:
        card = self.get_task_card(session_id, task_ref)
        messages = self._messages_for_ref(session_id, task_ref, limit=message_limit)
        confirmations = self._confirmations_for_ref(session_id, task_ref)
        file_changes = self._file_changes_for_ref(session_id, task_ref, recursive=True)
        result_summary = (
            self._summary_store.get(session_id, task_ref.id)
            if task_ref.kind == "published" and self._summary_store is not None
            else None
        )
        return TaskDetailView(
            card=card,
            full_intent=self._full_intent(session_id, task_ref),
            summary=card.intent_preview,
            instructions=card.instructions,
            acceptance_criteria=card.acceptance_criteria,
            constraints=self._constraints(session_id, task_ref),
            messages=tuple(messages),
            confirmations=tuple(confirmations),
            file_changes=tuple(file_changes),
            result_summary=result_summary,
        )

    # ------------------------------------------------------------------
    # Draft projection
    # ------------------------------------------------------------------

    def _draft_cards(self, session_id: str, *, root_ref: TaskRef | None) -> list[TaskCardView]:
        if self._draft_store is None:
            return []
        if root_ref is not None and root_ref.kind != "draft":
            return []

        cards: list[TaskCardView] = []
        for tree in self._draft_trees_for_projection(session_id):
            roots = sorted(
                tree.root_nodes,
                key=lambda n: (n.order_index, n.created_at, n.draft_task_id),
            )
            for node in roots:
                if root_ref is not None and node.draft_task_id != root_ref.id:
                    continue
                ref = TaskRef.draft(node.draft_task_id)
                cards.append(self._project_draft_node(node, depth=0, parent_ref=None, root_ref=ref))
        return cards

    def _draft_plan_cards(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None,
    ) -> list[TaskCardView]:
        if self._draft_store is None:
            return []
        if root_ref is not None and root_ref.kind != "draft":
            return []

        cards: list[TaskCardView] = []
        for tree in self._draft_trees_for_projection(session_id):
            for node in _ordered_draft_plan_nodes(
                self._draft_store.list_nodes(session_id, tree.draft_tree_id)
            ):
                if root_ref is not None and node.draft_task_id != root_ref.id:
                    continue
                ref = TaskRef.draft(node.draft_task_id)
                cards.append(
                    self._project_draft_node(
                        node,
                        depth=0,
                        parent_ref=None,
                        root_ref=ref,
                    )
                )
        return cards

    def _draft_trees_for_projection(self, session_id: str) -> list[DraftTaskTree]:
        if self._draft_store is None:
            return []
        if self._authoring_state_store is None:
            return self._draft_store.list_trees(session_id)

        active = self._authoring_state_store.get_active(session_id)
        if active.active_state != "draft_tree" or active.active_draft_tree_id is None:
            return []
        return [self._draft_store.get_tree(session_id, active.active_draft_tree_id)]

    def _plan_metadata(self, session_id: str) -> tuple[str | None, str | None]:
        tree = self._draft_tree_for_plan_metadata(session_id)
        if tree is None:
            return None, None
        return tree.title, tree.summary

    def _draft_tree_for_plan_metadata(self, session_id: str) -> DraftTaskTree | None:
        if self._draft_store is None:
            return None
        if self._authoring_state_store is not None:
            active = self._authoring_state_store.get_active(session_id)
            if active.active_draft_tree_id is not None:
                try:
                    return self._draft_store.get_tree(
                        session_id,
                        active.active_draft_tree_id,
                    )
                except LookupError:
                    return None

        trees = self._draft_store.list_trees(session_id)
        if not trees:
            return None
        return max(trees, key=lambda tree: (tree.updated_at, tree.draft_tree_id))

    def _project_draft_node(
        self,
        node: DraftTaskNode,
        *,
        depth: int,
        parent_ref: TaskRef | None,
        root_ref: TaskRef,
    ) -> TaskCardView:
        ref = TaskRef.draft(node.draft_task_id)
        status: TaskViewStatus = "cancelled" if node.status == "cancelled" else "draft"
        can_edit = node.status == "draft"
        content = _draft_content(node)
        permissions = TaskCardPermissions(
            can_edit=can_edit,
            can_append_guidance=can_edit,
            can_publish=can_edit,
            can_cancel=can_edit,
            readonly_reason=None if can_edit else f"draft task is {node.status}",
        )
        return TaskCardView(
            task_ref=ref,
            parent_ref=parent_ref,
            root_ref=root_ref,
            title=node.title,
            intent_preview=content.summary or _preview(content.intent),
            full_intent=content.intent,
            instructions=content.instructions,
            acceptance_criteria=content.acceptance_criteria,
            status=status,
            depth=depth,
            order_index=node.order_index,
            badges=TaskCardBadges(),
            permissions=permissions,
            primary_actions=_actions_for_permissions(permissions),
            latest_message=self._latest_message(node.session_id, ref),
            confirmation=self._pending_confirmation(node.session_id, ref),
        )

    # ------------------------------------------------------------------
    # Published projection
    # ------------------------------------------------------------------

    def _published_cards(self, session_id: str, *, root_ref: TaskRef | None) -> list[TaskCardView]:
        if root_ref is not None and root_ref.kind != "published":
            return []
        tasks = self._task_store.list_for_session(session_id)
        task_by_id = {task.task_id: task for task in tasks}
        children = _children_by_parent(tasks)
        root_ids = (
            [root_ref.id]
            if root_ref is not None
            else [task.task_id for task in _ordered(children[None])]
        )

        cards: list[TaskCardView] = []
        for root_id in root_ids:
            root = task_by_id.get(root_id)
            if root is None:
                continue
            self._append_task_subtree(
                cards,
                root,
                tasks=tasks,
                children=children,
                depth=0,
                parent_ref=None,
                root_ref=TaskRef.published(root.root_id),
            )
        return cards

    def _published_plan_cards(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None,
    ) -> list[TaskCardView]:
        return [
            _flatten_plan_card(card)
            for card in self._published_cards(session_id, root_ref=root_ref)
        ]

    def _append_task_subtree(
        self,
        cards: list[TaskCardView],
        task: TaskDomain,
        *,
        tasks: list[TaskDomain],
        children: dict[str | None, list[TaskDomain]],
        depth: int,
        parent_ref: TaskRef | None,
        root_ref: TaskRef,
    ) -> None:
        task_ref = TaskRef.published(task.task_id)
        child_tasks = _ordered(children[task.task_id])
        cards.append(
            self._project_task(
                task,
                tasks=tasks,
                child_tasks=child_tasks,
                depth=depth,
                parent_ref=parent_ref,
                root_ref=root_ref,
            )
        )
        for child in child_tasks:
            self._append_task_subtree(
                cards,
                child,
                tasks=tasks,
                children=children,
                depth=depth + 1,
                parent_ref=task_ref,
                root_ref=root_ref,
            )

    def _project_task(
        self,
        task: TaskDomain,
        *,
        tasks: list[TaskDomain],
        child_tasks: list[TaskDomain] | None = None,
        depth: int,
        parent_ref: TaskRef | None,
        root_ref: TaskRef,
    ) -> TaskCardView:
        ref = TaskRef.published(task.task_id)
        child_tasks = (
            child_tasks
            if child_tasks is not None
            else [candidate for candidate in tasks if candidate.parent_id == task.task_id]
        )
        permissions = _permissions_for_status(task.status)
        if task.interrupt_requested:
            permissions = permissions.model_copy(
                update={
                    "can_cancel": False,
                    "readonly_reason": permissions.readonly_reason
                    or "task stop already requested",
                }
            )
        direct_file_changes = self._file_changes_for_ref(task.session_id, ref, recursive=False)
        subtree_file_changes = self._file_changes_for_ref(task.session_id, ref, recursive=True)
        content = _task_content(task)
        return TaskCardView(
            task_ref=ref,
            parent_ref=parent_ref,
            root_ref=root_ref,
            title=_title(content.intent),
            intent_preview=content.summary or _preview(content.intent),
            full_intent=content.intent,
            instructions=content.instructions,
            acceptance_criteria=content.acceptance_criteria,
            status=task.status,
            depth=depth,
            order_index=task.order_index,
            result_ref=task.result_ref,
            error_ref=task.error_ref,
            interrupt_requested=task.interrupt_requested,
            badges=TaskCardBadges(
                pending_confirmation_count=len(self._confirmations_for_ref(task.session_id, ref)),
                direct_file_change_count=len(direct_file_changes),
                subtree_file_change_count=len(subtree_file_changes),
                child_count=len(child_tasks),
                done_child_count=sum(1 for child in child_tasks if child.status == "done"),
                failed_child_count=sum(1 for child in child_tasks if child.status == "failed"),
            ),
            permissions=permissions,
            primary_actions=_actions_for_permissions(permissions),
            confirmation=self._pending_confirmation(task.session_id, ref),
            latest_message=self._latest_message(task.session_id, ref),
            file_summary=subtree_file_changes[0] if subtree_file_changes else None,
            progress=(
                TaskProgressView(
                    child_count=len(child_tasks),
                    done_child_count=sum(1 for child in child_tasks if child.status == "done"),
                    failed_child_count=sum(1 for child in child_tasks if child.status == "failed"),
                    running_child_count=sum(
                        1
                        for child in child_tasks
                        if child.status in {"running", "waiting_for_user"}
                    ),
                )
                if child_tasks
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Shared source adapters
    # ------------------------------------------------------------------

    def _latest_message(self, session_id: str, task_ref: TaskRef) -> SessionMessageView | None:
        messages = self._messages_for_ref(session_id, task_ref)
        return messages[-1] if messages else None

    def _messages_for_ref(
        self, session_id: str, task_ref: TaskRef, *, limit: int | None = None
    ) -> list[SessionMessageView]:
        if self._message_stream is None:
            return []
        messages = [
            _message_to_view(message, task_ref)
            for message in self._message_stream.list_for_task(task_ref.id, limit=limit)
            if message.session_id == session_id
        ]
        return messages

    def _confirmations_for_ref(
        self, session_id: str, task_ref: TaskRef
    ) -> list[ConfirmationActionView]:
        if self._message_stream is None:
            return []
        return [
            _actionable_to_confirmation(message, task_ref)
            for message in self._message_stream.pending_actionable(session_id, task_id=task_ref.id)
        ]

    def _pending_confirmation(
        self, session_id: str, task_ref: TaskRef
    ) -> ConfirmationActionView | None:
        confirmations = self._confirmations_for_ref(session_id, task_ref)
        return confirmations[-1] if confirmations else None

    def _file_changes_for_ref(
        self, session_id: str, task_ref: TaskRef, *, recursive: bool
    ) -> list[TaskFileChangeSummary]:
        if task_ref.kind != "published" or self._file_change_store is None:
            return []
        if recursive:
            tasks = self._task_store.list_for_session(session_id)
            task_ids = [task_ref.id]
            task_ids.extend(task.task_id for task in _descendants(task_ref.id, tasks))
            changes: list[TaskFileChangeSummary] = []
            for task_id in task_ids:
                direct = self._file_change_store.list_for_task(
                    session_id,
                    task_id,
                    recursive=False,
                )
                changes.extend(
                    change.model_copy(
                        update={"from_subtree": change.owner_task_ref.id != task_ref.id}
                    )
                    for change in direct
                )
            return sorted(changes, key=lambda change: (change.recorded_at, change.change_id))
        return self._file_change_store.list_for_task(
            session_id,
            task_ref.id,
            recursive=False,
        )

    def _summary_for_ref(self, session_id: str, task_ref: TaskRef) -> TaskSummaryView | None:
        if task_ref.kind != "published" or self._summary_store is None:
            return None
        return self._summary_store.get(session_id, task_ref.id)

    def _full_intent(self, session_id: str, task_ref: TaskRef) -> str:
        if task_ref.kind == "draft":
            if self._draft_store is None:
                raise LookupError("draft_store is not configured")
            node = self._draft_store.get_node(session_id, task_ref.id)
            if node is None:
                raise LookupError(f"draft task {task_ref.id!r} not found")
            return _draft_content(node).intent
        task = self._task_store.get(session_id, task_ref.id)
        if task is None:
            raise LookupError(f"task {task_ref.id!r} not found")
        return _task_content(task).intent

    def _constraints(self, session_id: str, task_ref: TaskRef) -> tuple[str, ...]:
        if task_ref.kind != "draft" or self._draft_store is None:
            return ()
        node = self._draft_store.get_node(session_id, task_ref.id)
        if node is None:
            return ()
        return node.constraints

    def _depth(self, task: TaskDomain, task_by_id: dict[str, TaskDomain]) -> int:
        depth = 0
        current = task
        while current.parent_id is not None:
            parent = task_by_id.get(current.parent_id)
            if parent is None:
                break
            depth += 1
            current = parent
        return depth


def _ordered(tasks: Iterable[TaskDomain]) -> list[TaskDomain]:
    return sorted(tasks, key=lambda t: (t.order_index, t.created_at, t.task_id))


def _ordered_draft_plan_nodes(nodes: Iterable[DraftTaskNode]) -> list[DraftTaskNode]:
    node_list = list(nodes)
    children: dict[str | None, list[DraftTaskNode]] = defaultdict(list)
    by_id = {node.draft_task_id: node for node in node_list}
    for node in node_list:
        parent_id = node.parent_draft_task_id
        children[parent_id if parent_id in by_id else None].append(node)

    ordered: list[DraftTaskNode] = []

    def visit(node: DraftTaskNode) -> None:
        ordered.append(node)
        for child in _ordered_draft_nodes(children[node.draft_task_id]):
            visit(child)

    for root in _ordered_draft_nodes(children[None]):
        visit(root)
    return ordered


def _ordered_draft_nodes(nodes: Iterable[DraftTaskNode]) -> list[DraftTaskNode]:
    return sorted(nodes, key=lambda n: (n.order_index, n.created_at, n.draft_task_id))


def _flatten_plan_card(card: TaskCardView) -> TaskCardView:
    badges = card.badges.model_copy(
        update={
            "child_count": 0,
            "done_child_count": 0,
            "failed_child_count": 0,
        }
    )
    return card.model_copy(
        update={
            "parent_ref": None,
            "root_ref": card.task_ref,
            "depth": 0,
            "badges": badges,
            "progress": None,
        }
    )


@dataclass(frozen=True)
class _ProjectedTaskContent:
    intent: str
    summary: str | None = None
    instructions: str | None = None
    acceptance_criteria: tuple[str, ...] = ()


def _draft_content(node: DraftTaskNode) -> _ProjectedTaskContent:
    parsed = _split_legacy_task_content(node.intent)
    return _ProjectedTaskContent(
        intent=parsed.intent,
        summary=node.summary or parsed.summary,
        instructions=node.instructions or parsed.instructions,
        acceptance_criteria=node.acceptance_criteria or parsed.acceptance_criteria,
    )


def _task_content(task: TaskDomain) -> _ProjectedTaskContent:
    parsed = _split_legacy_task_content(task.intent)
    return _ProjectedTaskContent(
        intent=parsed.intent,
        summary=task.summary or parsed.summary,
        instructions=task.instructions or parsed.instructions,
        acceptance_criteria=task.acceptance_criteria or parsed.acceptance_criteria,
    )


def _split_legacy_task_content(text: str) -> _ProjectedTaskContent:
    intent_lines: list[str] = []
    summary: str | None = None
    instructions: str | None = None
    acceptance_criteria: tuple[str, ...] = ()

    for line in text.splitlines():
        stripped = line.strip()
        summary_value = _strip_legacy_marker(stripped, "summary:")
        if summary_value is not None:
            summary = summary_value or None
            continue

        instructions_value = _strip_legacy_marker(stripped, "instructions:")
        if instructions_value is not None:
            instructions = instructions_value or None
            continue

        criteria_value = _strip_legacy_marker(stripped, "acceptance criteria:")
        if criteria_value is not None:
            acceptance_criteria = _parse_acceptance_criteria(criteria_value)
            continue

        intent_lines.append(line)

    intent = "\n".join(intent_lines).strip() or text.strip()
    return _ProjectedTaskContent(
        intent=intent,
        summary=summary,
        instructions=instructions,
        acceptance_criteria=acceptance_criteria,
    )


def _strip_legacy_marker(text: str, marker: str) -> str | None:
    if text.lower().startswith(marker):
        return text[len(marker) :].strip()
    return None


def _parse_acceptance_criteria(value: str) -> tuple[str, ...]:
    return tuple(
        item.strip(" -\t")
        for item in value.split(";")
        if item.strip(" -\t")
    )


def _children_by_parent(tasks: list[TaskDomain]) -> dict[str | None, list[TaskDomain]]:
    children: dict[str | None, list[TaskDomain]] = defaultdict(list)
    for task in tasks:
        children[task.parent_id].append(task)
    return children


def _descendants(task_id: str, tasks: list[TaskDomain]) -> list[TaskDomain]:
    children = _children_by_parent(tasks)
    result: list[TaskDomain] = []
    stack = list(_ordered(children[task_id]))
    while stack:
        child = stack.pop(0)
        result.append(child)
        stack[0:0] = _ordered(children[child.task_id])
    return result


def _title(intent: str) -> str:
    first_line = intent.strip().splitlines()[0]
    return _preview(first_line, max_len=80)


def _preview(text: str, *, max_len: int = 120) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 3].rstrip()}..."


def _permissions_for_status(status: str) -> TaskCardPermissions:
    if status == "pending":
        return TaskCardPermissions(
            can_edit=True,
            can_append_guidance=True,
            can_cancel=True,
        )
    if status == "running":
        return TaskCardPermissions(
            can_append_guidance=True,
            can_resolve_confirmation=True,
            can_cancel=True,
        )
    if status == "waiting_for_user":
        return TaskCardPermissions(readonly_reason="task is waiting for user input")
    if status == "failed":
        return TaskCardPermissions(can_retry=True, readonly_reason="task failed")
    if status == "done":
        return TaskCardPermissions(readonly_reason="task is done")
    return TaskCardPermissions(readonly_reason=f"unknown status: {status}")


def _actions_for_permissions(permissions: TaskCardPermissions) -> tuple[TaskCardAction, ...]:
    actions: list[TaskCardAction] = []
    if permissions.can_resolve_confirmation:
        actions.append(TaskCardAction(kind="confirm", label="Confirm"))
    if permissions.can_edit:
        actions.append(TaskCardAction(kind="edit", label="Edit"))
    if permissions.can_append_guidance:
        actions.append(TaskCardAction(kind="append_guidance", label="Add guidance"))
    if permissions.can_publish:
        actions.append(TaskCardAction(kind="publish", label="Publish"))
    if permissions.can_cancel:
        actions.append(TaskCardAction(kind="cancel", label="Cancel"))
    if permissions.can_retry:
        actions.append(TaskCardAction(kind="retry", label="Retry"))
    actions.append(TaskCardAction(kind="open_detail", label="Open detail"))
    return tuple(actions)


def _message_to_view(message: AgentMessage, task_ref: TaskRef) -> SessionMessageView:
    if message.message_type == "actionable":
        message_type: TaskMessageViewType = "confirmation"
    elif message.agent_id == "user":
        message_type = "user"
    elif message.agent_id == "system":
        message_type = "system"
    else:
        message_type = "agent"
    return SessionMessageView(
        message_id=message.message_id,
        session_id=message.session_id,
        task_ref=task_ref,
        message_type=message_type,
        content_summary=message.content,
        created_at=message.created_at,
        related_action_id=message.related_action_id,
    )


def _actionable_to_confirmation(message: AgentMessage, task_ref: TaskRef) -> ConfirmationActionView:
    default_value = _confirmation_default_value(message)
    options = tuple(
        ConfirmationOptionView(
            option_id=option,
            label=_confirmation_option_label(option),
            value=option,
            is_default=option == default_value,
        )
        for option in message.action_options
    )
    default_option_id = default_value if default_value is not None else None
    risk_summary = None
    if message.risk_assessment is not None:
        risk_summary = f"risk={message.risk_assessment.final:.2f}"
    return ConfirmationActionView(
        confirmation_id=message.message_id,
        task_ref=task_ref,
        prompt=message.content,
        options=options,
        default_option_id=default_option_id,
        risk_summary=risk_summary,
        status="pending",
    )


def _confirmation_default_value(message: AgentMessage) -> str | None:
    context_default = message.context.get("default_option")
    if isinstance(context_default, str) and context_default in message.action_options:
        return context_default
    return message.action_options[0] if message.action_options else None


def _confirmation_option_label(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "confirm":
        return "Confirm"
    if normalized == "reject":
        return "Reject"
    if normalized == "approve_session":
        return "Approve session"
    if normalized == "yes":
        return "Yes"
    if normalized == "no":
        return "No"
    label = value.strip().replace("_", " ")
    return label[:1].upper() + label[1:] if label else value
