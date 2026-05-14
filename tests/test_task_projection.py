"""Tests for default Task projection service."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    DefaultTaskProjectionService,
    DraftTaskNode,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskDomain,
    TaskFileChangeSummary,
    TaskNodePatch,
    TaskProjectionService,
    TaskRef,
    TaskSummaryView,
)


class _TaskStore:
    def __init__(self, tasks: list[TaskDomain]) -> None:
        self._tasks = tasks

    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        return next(
            (
                task
                for task in self._tasks
                if task.session_id == session_id and task.task_id == task_id
            ),
            None,
        )

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        return [task for task in self._tasks if task.session_id == session_id]

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        return [
            task
            for task in self._tasks
            if task.session_id == session_id and task.parent_id == parent_id
        ]


class _DraftStore:
    def __init__(self, trees: list[DraftTaskTree]) -> None:
        self._trees = trees
        self._nodes = {
            node.draft_task_id: node
            for tree in trees
            for node in tree.root_nodes
        }

    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree:
        tree = DraftTaskTree(
            session_id=session_id,
            draft_tree_id="tree-new",
            root_nodes=tuple(roots),
        )
        self._trees.append(tree)
        return tree

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        return next(tree for tree in self._trees if tree.draft_tree_id == draft_tree_id)

    def list_trees(self, session_id: str) -> list[DraftTaskTree]:
        return [tree for tree in self._trees if tree.session_id == session_id]

    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]:
        return [
            node
            for node in self._nodes.values()
            if node.session_id == session_id and node.draft_tree_id == draft_tree_id
        ]

    def list_children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]:
        return [
            node
            for node in self.list_nodes(session_id, draft_tree_id)
            if node.parent_draft_task_id == parent_draft_task_id
        ]

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None:
        node = self._nodes.get(draft_task_id)
        if node is None or node.session_id != session_id:
            return None
        return node

    def add_node(
        self,
        session_id: str,
        draft_tree_id: str,
        node: DraftTaskNode,
        *,
        expected_tree_version: int,
    ) -> DraftTaskNode:
        self._nodes[node.draft_task_id] = node
        return node

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode:
        node = self._nodes[draft_task_id]
        return node.model_copy(
            update={
                "title": patch.title or node.title,
                "intent": patch.intent or node.intent,
                "version": expected_version + 1,
            }
        )

    def mark_accepted(
        self,
        session_id: str,
        draft_tree_id: str,
        *,
        expected_version: int,
    ) -> DraftTaskTree:
        return self.get_tree(session_id, draft_tree_id)

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
        *,
        expected_version: int | None = None,
    ) -> DraftTaskTree:
        return self.get_tree(session_id, draft_tree_id)


class _MessageStream:
    def __init__(self, messages: list[AgentMessage]) -> None:
        self._messages = messages

    def get(self, message_id: str) -> AgentMessage | None:
        return next(
            (message for message in self._messages if message.message_id == message_id),
            None,
        )

    def list_for_session(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        messages = [message for message in self._messages if message.session_id == session_id]
        if limit is not None:
            messages = messages[:limit]
        return iter(messages)

    def list_for_task(
        self,
        task_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        messages = [message for message in self._messages if message.task_id == task_id]
        if limit is not None:
            messages = messages[:limit]
        return iter(messages)

    def list_for_agent(
        self,
        agent_id: str,
        *,
        session_id: str | None = None,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        messages = [message for message in self._messages if message.agent_id == agent_id]
        if session_id is not None:
            messages = [message for message in messages if message.session_id == session_id]
        if limit is not None:
            messages = messages[:limit]
        return iter(messages)

    def pending_actionable(
        self, session_id: str, *, task_id: str | None = None
    ) -> list[AgentMessage]:
        return [
            message
            for message in self._messages
            if message.session_id == session_id
            and message.task_id == task_id
            and message.message_type == "actionable"
        ]

    def response_for(self, message_id: str) -> AgentMessage | None:
        return next(
            (
                message
                for message in self._messages
                if message.parent_message_id == message_id and message.message_type == "response"
            ),
            None,
        )

    def thread(self, message_id: str) -> list[AgentMessage]:
        parent = self.get(message_id)
        if parent is None:
            return []
        return [
            parent,
            *[
                message
                for message in self._messages
                if message.parent_message_id == message_id
            ],
        ]

    def __len__(self) -> int:
        return len(self._messages)


class _FileChangeStore:
    def __init__(self, direct: dict[str, list[TaskFileChangeSummary]]) -> None:
        self._direct = direct

    def list_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        recursive: bool = False,
    ) -> list[TaskFileChangeSummary]:
        changes = list(self._direct.get(task_id, []))
        if recursive and task_id == "root":
            changes.extend(
                change.model_copy(update={"from_subtree": True})
                for change in self._direct.get("child-a", [])
            )
        return changes


class _SummaryStore:
    def __init__(self, summaries: dict[str, TaskSummaryView]) -> None:
        self._summaries = summaries

    def get(self, session_id: str, task_id: str) -> TaskSummaryView | None:
        return self._summaries.get(task_id)


def _task(
    task_id: str,
    *,
    parent_id: str | None = None,
    order: int = 0,
    status: str = "pending",
) -> TaskDomain:
    root_id = task_id if parent_id is None else "root"
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        parent_id=parent_id,
        root_id=root_id,
        order_index=order,
        intent=f"{task_id} intent",
        required_capability="general",
        created_by="user",
        status=status,  # type: ignore[arg-type]
    )


def test_projection_service_protocol_conformance() -> None:
    service = DefaultTaskProjectionService(task_store=_TaskStore([]))
    assert isinstance(service, TaskProjectionService)


def test_published_tree_projection_is_preorder() -> None:
    root = _task("root")
    child_b = _task("child-b", parent_id="root", order=1)
    child_a = _task("child-a", parent_id="root", order=0)
    service = DefaultTaskProjectionService(task_store=_TaskStore([child_b, root, child_a]))

    tree = service.list_task_tree("s1", include_drafts=False)

    assert [node.task_ref.id for node in tree.nodes] == ["root", "child-a", "child-b"]
    assert [node.depth for node in tree.nodes] == [0, 1, 1]
    assert tree.nodes[1].parent_ref == TaskRef.published("root")


def test_draft_tree_projection_uses_editable_draft_cards() -> None:
    draft = DraftTaskNode(
        draft_task_id="draft-1",
        session_id="s1",
        draft_tree_id="tree1",
        title="Draft plan",
        intent="Create a careful plan",
        required_capability="planning",
    )
    draft_store = _DraftStore(
        [DraftTaskTree(draft_tree_id="tree1", session_id="s1", root_nodes=(draft,))]
    )
    service = DefaultTaskProjectionService(
        task_store=_TaskStore([]),
        draft_store=draft_store,
    )

    tree = service.list_task_tree("s1", include_published=False)

    assert len(tree.nodes) == 1
    assert tree.nodes[0].task_ref == TaskRef.draft("draft-1")
    assert tree.nodes[0].permissions.can_edit is True
    assert tree.nodes[0].permissions.can_publish is True


def test_published_permissions_follow_status() -> None:
    tasks = [
        _task("pending", status="pending"),
        _task("running", status="running"),
        _task("done", status="done"),
        _task("failed", status="failed"),
    ]
    service = DefaultTaskProjectionService(task_store=_TaskStore(tasks))

    pending = service.get_task_card("s1", TaskRef.published("pending"))
    running = service.get_task_card("s1", TaskRef.published("running"))
    done = service.get_task_card("s1", TaskRef.published("done"))
    failed = service.get_task_card("s1", TaskRef.published("failed"))

    assert pending.permissions.can_edit is True
    assert pending.permissions.can_cancel is True
    assert running.permissions.can_append_guidance is True
    assert done.permissions.readonly_reason == "task is done"
    assert failed.permissions.can_retry is True


def test_projection_aggregates_messages_confirmations_files_and_summary() -> None:
    root = _task("root")
    child = _task("child-a", parent_id="root", status="done")
    message = AgentMessage(
        session_id="s1",
        task_id="root",
        agent_id="user",
        message_type="informational",
        content="Please keep this safe",
    )
    actionable = AgentMessage(
        session_id="s1",
        task_id="root",
        message_type="actionable",
        content="Proceed?",
        action_options=["yes", "no"],
        requires_response=True,
    )
    child_change = TaskFileChangeSummary(
        owner_task_ref=TaskRef.published("child-a"),
        path="docs/release.md",
        change_type="modified",
        summary="Updated release notes",
    )
    summary = TaskSummaryView(task_ref=TaskRef.published("root"), summary="Release ready")
    service = DefaultTaskProjectionService(
        task_store=_TaskStore([root, child]),
        message_stream=_MessageStream([message, actionable]),
        file_change_store=_FileChangeStore({"child-a": [child_change]}),
        summary_store=_SummaryStore({"root": summary}),
    )

    card = service.get_task_card("s1", TaskRef.published("root"))
    detail = service.get_task_detail("s1", TaskRef.published("root"))

    assert card.badges.pending_confirmation_count == 1
    assert card.badges.subtree_file_change_count == 1
    assert card.confirmation is not None
    assert card.confirmation.options[0].value == "yes"
    assert detail.messages[-1].message_type == "confirmation"
    assert detail.file_changes[0].from_subtree is True
    assert detail.result_summary is summary


def test_get_task_card_missing_task_raises() -> None:
    service = DefaultTaskProjectionService(task_store=_TaskStore([]))

    try:
        service.get_task_card("s1", TaskRef.published("missing"))
    except LookupError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected missing task to raise LookupError")
