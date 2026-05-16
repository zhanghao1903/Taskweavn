"""Tests for AuthoringContextBuilder."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime

import pytest

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    AuthoringContextBuilder,
    CapabilityDescriptor,
    DefaultAuthoringContextBuilder,
    DraftTaskNode,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    RawTask,
    RawTaskAsk,
    RawTaskStore,
    StaticCapabilityCatalog,
    TaskNodePatch,
    TaskRef,
)


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
        return iter(_limit(messages, limit))

    def list_for_task(
        self,
        task_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        messages = [message for message in self._messages if message.task_id == task_id]
        return iter(_limit(messages, limit))

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
        return iter(_limit(messages, limit))

    def pending_actionable(
        self,
        session_id: str,
        *,
        task_id: str | None = None,
    ) -> list[AgentMessage]:
        return []

    def response_for(self, message_id: str) -> AgentMessage | None:
        return None

    def thread(self, message_id: str) -> list[AgentMessage]:
        return []

    def __len__(self) -> int:
        return len(self._messages)


def _limit(messages: list[AgentMessage], limit: int | None) -> list[AgentMessage]:
    return messages if limit is None else messages[:limit]


def _catalog() -> StaticCapabilityCatalog:
    return StaticCapabilityCatalog(
        [
            CapabilityDescriptor(
                capability_id="writing",
                display_name="Writing",
                summary="Write content and docs",
                applicable_domains=("content",),
                risk_level="low",
                reliability_score=0.9,
            ),
            CapabilityDescriptor(
                capability_id="testing",
                display_name="Testing",
                summary="Run tests and verify quality",
                applicable_domains=("quality",),
                risk_level="low",
            ),
            CapabilityDescriptor(
                capability_id="general",
                display_name="General",
                summary="General planning and coordination",
            ),
        ]
    )


def _raw_task(raw_task_id: str = "raw1") -> RawTask:
    ask = RawTaskAsk(
        ask_id="ask1",
        raw_task_id=raw_task_id,
        question="Who is this for?",
        reason="Need audience",
    )
    return RawTask(
        raw_task_id=raw_task_id,
        session_id="s1",
        source_message_id="m1",
        user_input="Write docs for developers",
        status="awaiting_user",
        intent_summary="write docs",
        asks=(ask,),
    )


def _builder(
    *,
    raw_store: RawTaskStore | None = None,
    draft_store: InMemoryDraftTaskStore | None = None,
    messages: list[AgentMessage] | None = None,
) -> DefaultAuthoringContextBuilder:
    return DefaultAuthoringContextBuilder(
        raw_task_store=raw_store or InMemoryRawTaskStore(),
        draft_store=draft_store or InMemoryDraftTaskStore(),
        capability_catalog=_catalog(),
        message_stream=_MessageStream(messages or []),
        recent_message_limit=2,
        constraints={"locale": "zh-CN"},
    )


def test_context_builder_protocol_conformance() -> None:
    assert isinstance(_builder(), AuthoringContextBuilder)


def test_build_session_context_aggregates_raw_tasks_drafts_messages_and_capabilities() -> None:
    raw_store = InMemoryRawTaskStore([_raw_task()])
    draft_store = InMemoryDraftTaskStore()
    draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Write docs",
                intent="Write content",
                required_capability="writing",
            )
        ],
    )
    builder = _builder(
        raw_store=raw_store,
        draft_store=draft_store,
        messages=[
            AgentMessage(session_id="s1", message_type="informational", content="one"),
            AgentMessage(session_id="s1", message_type="informational", content="two"),
            AgentMessage(session_id="s1", message_type="informational", content="three"),
            AgentMessage(session_id="other", message_type="informational", content="skip"),
        ],
    )

    context = builder.build_session_context("s1")

    assert context.mode == "session"
    assert context.raw_task_id == "raw1"
    assert context.unresolved_asks[0].ask_id == "ask1"
    assert len(context.draft_trees) == 1
    assert [message.content for message in context.recent_messages] == ["one", "two"]
    assert context.capabilities[0].capability_id == "writing"
    assert context.constraints["locale"] == "zh-CN"


def test_build_session_context_uses_explicit_raw_task_id() -> None:
    raw_store = InMemoryRawTaskStore([_raw_task("raw1"), _raw_task("raw2")])
    builder = _builder(raw_store=raw_store)

    context = builder.build_session_context("s1", raw_task_id="raw1")

    assert context.raw_task_id == "raw1"


def test_build_session_context_missing_raw_task_raises() -> None:
    builder = _builder(raw_store=InMemoryRawTaskStore())

    with pytest.raises(LookupError, match="RawTask"):
        builder.build_session_context("s1", raw_task_id="missing")


def test_build_task_context_reconstructs_selected_node_context() -> None:
    raw_store = InMemoryRawTaskStore([_raw_task()])
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Root",
                intent="Plan work",
                required_capability="general",
            )
        ],
    )
    draft_store.add_node(
        "s1",
        tree.draft_tree_id,
        DraftTaskNode(
            draft_task_id="child",
            session_id="s1",
            draft_tree_id=tree.draft_tree_id,
            parent_draft_task_id="root",
            title="Child",
            intent="Run tests",
            required_capability="testing",
        ),
        expected_tree_version=tree.version,
    )
    draft_store.add_node(
        "s1",
        tree.draft_tree_id,
        DraftTaskNode(
            draft_task_id="leaf",
            session_id="s1",
            draft_tree_id=tree.draft_tree_id,
            parent_draft_task_id="child",
            title="Leaf",
            intent="Write test cases",
            required_capability="testing",
        ),
        expected_tree_version=2,
    )
    builder = _builder(
        raw_store=raw_store,
        draft_store=draft_store,
        messages=[
            AgentMessage(
                session_id="s1",
                task_id="child",
                message_type="informational",
                content="task msg",
            ),
            AgentMessage(
                session_id="other",
                task_id="child",
                message_type="informational",
                content="skip",
            ),
        ],
    )

    context = builder.build_task_context("s1", TaskRef.draft("child"))

    assert context.mode == "task"
    assert context.selected_node is not None
    assert context.selected_node.draft_task_id == "child"
    assert [node.draft_task_id for node in context.ancestors] == ["root"]
    assert [node.draft_task_id for node in context.children] == ["leaf"]
    assert [message.content for message in context.recent_messages] == ["task msg"]
    assert context.capabilities[0].capability_id == "testing"


def test_build_task_context_rejects_published_ref() -> None:
    with pytest.raises(ValueError, match="draft"):
        _builder().build_task_context("s1", TaskRef.published("task1"))


def test_context_builder_is_read_only() -> None:
    raw_store = InMemoryRawTaskStore([_raw_task()])
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Root",
                intent="Write content",
                required_capability="writing",
            )
        ],
    )
    raw_before = raw_store.get("s1", "raw1")
    node_before = draft_store.get_node("s1", "root")

    _builder(raw_store=raw_store, draft_store=draft_store).build_session_context("s1")
    _builder(raw_store=raw_store, draft_store=draft_store).build_task_context(
        "s1",
        TaskRef.draft("root"),
    )

    assert raw_store.get("s1", "raw1") == raw_before
    assert draft_store.get_tree("s1", tree.draft_tree_id).version == tree.version
    assert draft_store.get_node("s1", "root") == node_before


def test_context_builder_output_is_independent_from_later_store_mutation() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Root",
                intent="Write content",
                required_capability="writing",
            )
        ],
    )
    context = _builder(draft_store=draft_store).build_task_context("s1", TaskRef.draft("root"))

    draft_store.update_node(
        "s1",
        "root",
        TaskNodePatch(title="Changed"),
        expected_version=1,
    )

    assert tree.version == 1
    assert context.selected_node is not None
    assert context.selected_node.title == "Root"
