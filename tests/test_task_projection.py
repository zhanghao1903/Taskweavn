"""Tests for default Task projection service."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    ActiveAuthoringState,
    DefaultTaskProjectionService,
    DraftTaskNode,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskDispatchConstraints,
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


class _AuthoringStateStore:
    def __init__(self, state: ActiveAuthoringState) -> None:
        self._state = state

    def get_active(self, session_id: str) -> ActiveAuthoringState:
        return self._state

    def set_active_raw_task(self, session_id: str, raw_task_id: str) -> None:
        raise NotImplementedError

    def set_active_draft_tree(
        self,
        session_id: str,
        raw_task_id: str | None,
        draft_tree_id: str,
    ) -> None:
        raise NotImplementedError

    def mark_published(self, session_id: str, draft_tree_id: str) -> None:
        raise NotImplementedError


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
        answered_ids = {
            message.parent_message_id
            for message in self._messages
            if message.message_type == "response" and message.parent_message_id is not None
        }
        return [
            message
            for message in self._messages
            if message.session_id == session_id
            and message.task_id == task_id
            and message.message_type == "actionable"
            and message.message_id not in answered_ids
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
    result_ref: str | None = None,
    error_ref: str | None = None,
    metadata: dict[str, object] | None = None,
) -> TaskDomain:
    root_id = task_id if parent_id is None else "root"
    waiting_for_ask_id = (
        f"ask:{task_id}" if status == "waiting_for_user" else None
    )
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        parent_id=parent_id,
        root_id=root_id,
        order_index=order,
        intent=f"{task_id} intent",
        required_capability="general",
        dispatch_constraints=(
            TaskDispatchConstraints(metadata=metadata) if metadata is not None else None
        ),
        created_by="user",
        status=status,  # type: ignore[arg-type]
        result_ref=result_ref,
        error_ref=error_ref,
        waiting_for_ask_id=waiting_for_ask_id,
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


def test_failed_task_projection_keeps_original_task_and_exposes_retry() -> None:
    failed = _task("root", status="failed", error_ref="error:root")
    child = _task("child", parent_id="root", order=0)
    service = DefaultTaskProjectionService(task_store=_TaskStore([failed, child]))

    tree = service.list_task_tree("s1", include_drafts=False)

    assert [node.task_ref.id for node in tree.nodes] == ["root", "child"]
    assert tree.nodes[0].parent_ref is None
    assert tree.nodes[0].root_ref == TaskRef.published("root")
    assert tree.nodes[0].status == "failed"
    assert any(action.kind == "retry" for action in tree.nodes[0].primary_actions)
    assert tree.nodes[0].badges.child_count == 1
    assert tree.nodes[1].parent_ref == TaskRef.published("root")
    assert tree.nodes[1].root_ref == TaskRef.published("root")
    assert tree.nodes[1].depth == 1


def test_retry_metadata_no_longer_replaces_failed_task_projection() -> None:
    failed = _task("failed", status="failed", error_ref="error:failed")
    retry_a = _task("retry-a", metadata={"retry_of": "failed"})
    retry_b = _task("retry-b", metadata={"retry_of": "failed"})
    service = DefaultTaskProjectionService(
        task_store=_TaskStore([failed, retry_b, retry_a])
    )

    tree = service.list_task_tree("s1", include_drafts=False)

    assert [node.task_ref.id for node in tree.nodes] == ["failed", "retry-a", "retry-b"]


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


def test_draft_projection_uses_only_active_draft_tree_when_state_store_is_configured() -> None:
    draft_a = DraftTaskNode(
        draft_task_id="draft-a",
        session_id="s1",
        draft_tree_id="tree-a",
        title="Inactive draft",
        intent="Old plan",
        required_capability="planning",
    )
    draft_b = DraftTaskNode(
        draft_task_id="draft-b",
        session_id="s1",
        draft_tree_id="tree-b",
        title="Active draft",
        intent="Current plan",
        required_capability="planning",
    )
    draft_store = _DraftStore(
        [
            DraftTaskTree(draft_tree_id="tree-a", session_id="s1", root_nodes=(draft_a,)),
            DraftTaskTree(draft_tree_id="tree-b", session_id="s1", root_nodes=(draft_b,)),
        ]
    )
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="s1",
            active_raw_task_id="raw-1",
            active_draft_tree_id="tree-b",
            active_state="draft_tree",
        )
    )
    service = DefaultTaskProjectionService(
        task_store=_TaskStore([]),
        draft_store=draft_store,
        authoring_state_store=state_store,
    )

    tree = service.list_task_tree("s1", include_published=False)

    assert [node.task_ref.id for node in tree.nodes] == ["draft-b"]


def test_draft_projection_hides_drafts_without_active_draft_tree() -> None:
    draft = DraftTaskNode(
        draft_task_id="draft-a",
        session_id="s1",
        draft_tree_id="tree-a",
        title="Inactive draft",
        intent="Old plan",
        required_capability="planning",
    )
    draft_store = _DraftStore(
        [DraftTaskTree(draft_tree_id="tree-a", session_id="s1", root_nodes=(draft,))]
    )
    state_store = _AuthoringStateStore(ActiveAuthoringState(session_id="s1"))
    service = DefaultTaskProjectionService(
        task_store=_TaskStore([]),
        draft_store=draft_store,
        authoring_state_store=state_store,
    )

    tree = service.list_task_tree("s1", include_published=False)

    assert tree.nodes == ()


def test_published_permissions_follow_status() -> None:
    tasks = [
        _task("pending", status="pending"),
        _task("running", status="running"),
        _task("waiting", status="waiting_for_user"),
        _task("done", status="done"),
        _task("failed", status="failed"),
    ]
    service = DefaultTaskProjectionService(task_store=_TaskStore(tasks))

    pending = service.get_task_card("s1", TaskRef.published("pending"))
    running = service.get_task_card("s1", TaskRef.published("running"))
    waiting = service.get_task_card("s1", TaskRef.published("waiting"))
    done = service.get_task_card("s1", TaskRef.published("done"))
    failed = service.get_task_card("s1", TaskRef.published("failed"))

    assert pending.permissions.can_edit is True
    assert pending.permissions.can_cancel is True
    assert running.permissions.can_append_guidance is True
    assert waiting.status == "waiting_for_user"
    assert waiting.permissions.can_resolve_confirmation is False
    assert waiting.permissions.readonly_reason == "task is waiting for user input"
    assert done.permissions.readonly_reason == "task is done"
    assert failed.permissions.can_retry is True


def test_published_projection_preserves_result_and_error_refs() -> None:
    tasks = [
        _task("done", status="done", result_ref="result:done"),
        _task("failed", status="failed", error_ref="error:failed"),
    ]
    service = DefaultTaskProjectionService(task_store=_TaskStore(tasks))

    done = service.get_task_card("s1", TaskRef.published("done"))
    failed = service.get_task_card("s1", TaskRef.published("failed"))

    assert done.status == "done"
    assert done.result_ref == "result:done"
    assert done.error_ref is None
    assert failed.status == "failed"
    assert failed.result_ref is None
    assert failed.error_ref == "error:failed"


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


def test_projection_drops_resolved_confirmation_from_pending_views() -> None:
    root = _task("root")
    confirmation = AgentMessage(
        message_id="confirmation-1",
        session_id="s1",
        task_id="root",
        message_type="actionable",
        content="Proceed?",
        action_options=["yes", "no"],
        requires_response=True,
    )
    response = AgentMessage(
        session_id="s1",
        task_id="root",
        agent_id="user",
        parent_message_id=confirmation.message_id,
        message_type="response",
        content="yes",
        response_source="user",
        response_value="yes",
    )
    service = DefaultTaskProjectionService(
        task_store=_TaskStore([root]),
        message_stream=_MessageStream([confirmation, response]),
    )

    card = service.get_task_card("s1", TaskRef.published("root"))
    detail = service.get_task_detail("s1", TaskRef.published("root"))

    assert card.badges.pending_confirmation_count == 0
    assert card.confirmation is None
    assert detail.confirmations == ()


def test_get_task_card_missing_task_raises() -> None:
    service = DefaultTaskProjectionService(task_store=_TaskStore([]))

    try:
        service.get_task_card("s1", TaskRef.published("missing"))
    except LookupError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected missing task to raise LookupError")
