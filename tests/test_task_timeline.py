"""Tests for replayable Task interaction timelines."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    DefaultTaskInteractionTimelineService,
    DraftPublicationStore,
    DraftTaskNode,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskCardView,
    TaskDetailView,
    TaskFileChangeSummary,
    TaskInteractionTimelineService,
    TaskNodePatch,
    TaskRef,
    TaskSummaryView,
    TaskTreeView,
)
from taskweavn.tools.fs import FileContentObservation, ReadFileAction

BASE = datetime(2026, 5, 13, 10, 0, tzinfo=UTC)


class _DraftStore:
    def __init__(self, nodes: list[DraftTaskNode]) -> None:
        self.nodes = {node.draft_task_id: node for node in nodes}

    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree:
        return DraftTaskTree(session_id=session_id, draft_tree_id="tree1", root_nodes=tuple(roots))

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        roots = tuple(node for node in self.nodes.values() if node.session_id == session_id)
        return DraftTaskTree(session_id=session_id, draft_tree_id=draft_tree_id, root_nodes=roots)

    def list_trees(self, session_id: str) -> list[DraftTaskTree]:
        return [self.get_tree(session_id, "tree1")]

    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]:
        return [
            node
            for node in self.nodes.values()
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
        node = self.nodes.get(draft_task_id)
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
        self.nodes[node.draft_task_id] = node
        return node

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode:
        return self.nodes[draft_task_id]

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
        self.messages = messages

    def get(self, message_id: str) -> AgentMessage | None:
        return next(
            (message for message in self.messages if message.message_id == message_id),
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
        return iter([message for message in self.messages if message.session_id == session_id])

    def list_for_task(
        self,
        task_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        messages = [message for message in self.messages if message.task_id == task_id]
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
        return iter([message for message in self.messages if message.agent_id == agent_id])

    def pending_actionable(
        self, session_id: str, *, task_id: str | None = None
    ) -> list[AgentMessage]:
        return [
            message
            for message in self.messages
            if message.session_id == session_id
            and message.task_id == task_id
            and message.message_type == "actionable"
        ]

    def response_for(self, message_id: str) -> AgentMessage | None:
        return next(
            (
                message
                for message in self.messages
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
                for message in self.messages
                if message.parent_message_id == message_id
            ],
        ]

    def __len__(self) -> int:
        return len(self.messages)


class _PublicationStore:
    def __init__(self, mappings: list[DraftToPublishedMapping]) -> None:
        self.mappings = mappings

    def list_for_draft(
        self,
        session_id: str,
        draft_task_id: str,
    ) -> list[DraftToPublishedMapping]:
        return [
            mapping
            for mapping in self.mappings
            if mapping.session_id == session_id and mapping.draft_task_id == draft_task_id
        ]

    def list_for_task(
        self,
        session_id: str,
        task_id: str,
    ) -> list[DraftToPublishedMapping]:
        return [
            mapping
            for mapping in self.mappings
            if mapping.session_id == session_id and mapping.task_id == task_id
        ]


class _EventStream:
    def __init__(self, events_by_task: dict[str, list[object]]) -> None:
        self.events_by_task = events_by_task

    def iter_for_task(self, task_id: str) -> Iterator[object]:
        return iter(self.events_by_task.get(task_id, []))


class _FileStore:
    def __init__(self, changes: list[TaskFileChangeSummary]) -> None:
        self.changes = changes

    def list_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        recursive: bool = False,
    ) -> list[TaskFileChangeSummary]:
        if recursive:
            return self.changes
        return [change for change in self.changes if not change.from_subtree]


class _SummaryStore:
    def __init__(self, summary: TaskSummaryView | None) -> None:
        self.summary = summary

    def get(self, session_id: str, task_id: str) -> TaskSummaryView | None:
        return self.summary


class _ProjectionService:
    def get_task_detail(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        message_limit: int = 100,
    ) -> TaskDetailView:
        card = TaskCardView(
            task_ref=task_ref,
            root_ref=task_ref,
            title="Task",
            intent_preview="Task intent",
            status="draft" if task_ref.kind == "draft" else "pending",
        )
        return TaskDetailView(card=card, full_intent="Task intent")

    def get_task_card(self, session_id: str, task_ref: TaskRef) -> TaskCardView:
        return self.get_task_detail(session_id, task_ref).card

    def list_task_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> TaskTreeView:
        return TaskTreeView(session_id=session_id)


def _draft_node() -> DraftTaskNode:
    return DraftTaskNode(
        draft_task_id="d1",
        session_id="s1",
        draft_tree_id="tree1",
        title="Draft release task",
        intent="Prepare release notes",
        required_capability="writing",
        created_at=BASE,
        updated_at=BASE + timedelta(minutes=1),
    )


def test_timeline_service_protocol_conformance() -> None:
    service = DefaultTaskInteractionTimelineService(projection_service=_ProjectionService())
    assert isinstance(service, TaskInteractionTimelineService)
    assert isinstance(_PublicationStore([]), DraftPublicationStore)


def test_draft_timeline_includes_draft_messages_and_publish_mapping() -> None:
    mapping = DraftToPublishedMapping(
        session_id="s1",
        draft_tree_id="tree1",
        draft_task_id="d1",
        task_id="t1",
        publish_command_id="cmd1",
        published_at=BASE + timedelta(minutes=4),
    )
    messages = [
        AgentMessage(
            session_id="s1",
            task_id="d1",
            agent_id="user",
            message_type="informational",
            content="Add a safety constraint",
            created_at=BASE + timedelta(minutes=2),
        ),
        AgentMessage(
            session_id="s1",
            task_id="d1",
            message_type="actionable",
            content="Publish?",
            created_at=BASE + timedelta(minutes=3),
        ),
    ]
    service = DefaultTaskInteractionTimelineService(
        projection_service=_ProjectionService(),
        draft_store=_DraftStore([_draft_node()]),
        message_stream=_MessageStream(messages),
        publication_store=_PublicationStore([mapping]),
    )

    timeline = service.get_timeline("s1", TaskRef.draft("d1"))

    assert [entry.kind for entry in timeline.entries] == [
        "draft.created",
        "draft.draft",
        "message.informational",
        "confirmation.created",
        "draft.published",
    ]
    assert timeline.entries[-1].summary == "Draft task published as t1"


def test_published_timeline_stitches_draft_events_files_and_summary() -> None:
    mapping = DraftToPublishedMapping(
        session_id="s1",
        draft_tree_id="tree1",
        draft_task_id="d1",
        task_id="t1",
        publish_command_id="cmd1",
        published_at=BASE + timedelta(minutes=2),
    )
    action = ReadFileAction(
        event_id="a1",
        path="README.md",
        timestamp=BASE + timedelta(minutes=3),
    )
    observation = FileContentObservation(
        event_id="o1",
        action_id="a1",
        path="README.md",
        content="hello",
        bytes_read=5,
        timestamp=BASE + timedelta(minutes=4),
    )
    change = TaskFileChangeSummary(
        owner_task_ref=TaskRef.published("t1"),
        path="README.md",
        change_type="modified",
        summary="Updated README",
        recorded_at=BASE + timedelta(minutes=5),
    )
    summary = TaskSummaryView(
        task_ref=TaskRef.published("t1"),
        summary="Task completed",
        updated_at=BASE + timedelta(minutes=6),
    )
    service = DefaultTaskInteractionTimelineService(
        projection_service=_ProjectionService(),
        draft_store=_DraftStore([_draft_node()]),
        event_stream=_EventStream({"t1": [action, observation]}),  # type: ignore[arg-type]
        file_change_store=_FileStore([change]),
        summary_store=_SummaryStore(summary),
        publication_store=_PublicationStore([mapping]),
    )

    timeline = service.get_timeline("s1", TaskRef.published("t1"), include_subtree=True)

    assert [entry.kind for entry in timeline.entries] == [
        "draft.created",
        "draft.draft",
        "draft.published",
        "event.ReadFileAction",
        "event.FileContentObservation",
        "file.modified",
        "summary.updated",
    ]
    assert timeline.entries[3].payload_ref == "a1"
    assert timeline.entries[-1].summary == "Task completed"


def test_timeline_limit_and_snapshot() -> None:
    messages = [
        AgentMessage(
            session_id="s1",
            task_id="d1",
            message_type="informational",
            content="first",
            created_at=BASE,
        ),
        AgentMessage(
            session_id="s1",
            task_id="d1",
            message_type="informational",
            content="second",
            created_at=BASE + timedelta(minutes=1),
        ),
    ]
    service = DefaultTaskInteractionTimelineService(
        projection_service=_ProjectionService(),
        message_stream=_MessageStream(messages),
    )

    timeline = service.get_timeline("s1", TaskRef.draft("d1"), limit=1)
    snapshot = service.get_snapshot("s1", TaskRef.draft("d1"))

    assert len(timeline.entries) == 1
    assert timeline.entries[0].summary == "first"
    assert snapshot.task_detail.card.task_ref == TaskRef.draft("d1")
    assert [entry.summary for entry in snapshot.timeline.entries] == ["first", "second"]


def test_timeline_cursor_resumes_after_returned_entry() -> None:
    messages = [
        AgentMessage(
            session_id="s1",
            task_id="d1",
            message_type="informational",
            content="first",
            created_at=BASE,
        ),
        AgentMessage(
            session_id="s1",
            task_id="d1",
            message_type="informational",
            content="second",
            created_at=BASE + timedelta(minutes=1),
        ),
        AgentMessage(
            session_id="s1",
            task_id="d1",
            message_type="informational",
            content="third",
            created_at=BASE + timedelta(minutes=2),
        ),
    ]
    service = DefaultTaskInteractionTimelineService(
        projection_service=_ProjectionService(),
        message_stream=_MessageStream(messages),
    )

    first_page = service.get_timeline("s1", TaskRef.draft("d1"), limit=1)
    second_page = service.get_timeline(
        "s1",
        TaskRef.draft("d1"),
        cursor=first_page.cursor,
    )

    assert [entry.summary for entry in first_page.entries] == ["first"]
    assert [entry.summary for entry in second_page.entries] == ["second", "third"]
