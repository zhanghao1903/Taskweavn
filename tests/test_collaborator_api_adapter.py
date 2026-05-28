"""Tests for Collaborator template registration and UI/API adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskweavn.interaction import InProcessMessageBus, SqliteMessageStream
from taskweavn.llm import ChatResponse
from taskweavn.task import (
    COLLABORATOR_CAPABILITY,
    COLLABORATOR_COMMAND_PROTOCOL,
    COLLABORATOR_TEMPLATE_ID,
    CollaboratorApiAdapter,
    CollaboratorTemplateRegistry,
    DefaultAuthoringCommandService,
    DefaultAuthoringContextBuilder,
    DefaultCollaboratorApiAdapter,
    DefaultCollaboratorAuthoringService,
    DraftTaskNode,
    DraftToPublishedMapping,
    FeasibilityReport,
    InMemoryCollaboratorTemplateRegistry,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    RawTask,
    StaticCapabilityCatalog,
    TaskPublisher,
    TaskPublishResult,
    TaskRef,
    default_collaborator_template,
)


@dataclass
class _StubLLM:
    responses: list[str]
    calls: list[list[dict[str, Any]]] = field(default_factory=list)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append(messages)
        return ChatResponse(
            content=self.responses.pop(0),
            tool_calls=[],
            raw_assistant_message={},
        )


@dataclass
class _Publisher:
    result: TaskPublishResult
    calls: list[tuple[str, str]] = field(default_factory=list)
    kind: Any = field(default="collaborator", init=False)

    def preview(self, request: Any) -> Any:
        raise NotImplementedError

    def publish(self, request: Any) -> Any:
        raise NotImplementedError

    def publish_draft_tree(self, session_id: str, draft_tree_id: str) -> TaskPublishResult:
        self.calls.append((session_id, draft_tree_id))
        return self.result

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> TaskPublishResult:
        raise NotImplementedError


@dataclass
class _Harness:
    adapter: DefaultCollaboratorApiAdapter
    raw_store: InMemoryRawTaskStore
    draft_store: InMemoryDraftTaskStore
    stream: SqliteMessageStream
    bus: InProcessMessageBus
    registry: InMemoryCollaboratorTemplateRegistry


def _adapter(
    tmp_path: Any,
    llm: _StubLLM,
    *,
    raw_store: InMemoryRawTaskStore | None = None,
    draft_store: InMemoryDraftTaskStore | None = None,
    publisher: TaskPublisher | None = None,
) -> _Harness:
    raw_store = raw_store or InMemoryRawTaskStore()
    draft_store = draft_store or InMemoryDraftTaskStore()
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    context_builder = DefaultAuthoringContextBuilder(
        raw_task_store=raw_store,
        draft_store=draft_store,
        capability_catalog=StaticCapabilityCatalog(["general", "writing", "testing"]),
        message_stream=stream,
    )
    command_service = DefaultAuthoringCommandService(
        raw_task_store=raw_store,
        draft_store=draft_store,
        message_bus=bus,
        task_publisher=publisher,
    )
    collaborator = DefaultCollaboratorAuthoringService(
        llm=llm,
        context_builder=context_builder,
        command_service=command_service,
    )
    registry = InMemoryCollaboratorTemplateRegistry()
    return _Harness(
        adapter=DefaultCollaboratorApiAdapter(
            collaborator_service=collaborator,
            command_service=command_service,
            template_registry=registry,
            message_bus=bus,
        ),
        raw_store=raw_store,
        draft_store=draft_store,
        stream=stream,
        bus=bus,
        registry=registry,
    )


def test_default_collaborator_template_has_no_workspace_tools() -> None:
    template = default_collaborator_template()

    assert template.template_id == COLLABORATOR_TEMPLATE_ID
    assert template.capability == COLLABORATOR_CAPABILITY
    assert template.command_protocol == COLLABORATOR_COMMAND_PROTOCOL
    assert template.llm_visible_tool_pools == ()
    assert "workspace.basic" not in template.llm_visible_tool_pools
    assert "shell" not in template.llm_visible_tool_pools


def test_template_registry_protocol_and_session_start(tmp_path: Any) -> None:
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {"intent_summary": "unused",
                 "feasibility": {"status": "ready", "confidence": 0.9}}
                """
            ]
        ),
    )

    result = harness.adapter.start_session("s1")

    assert isinstance(harness.registry, CollaboratorTemplateRegistry)
    assert isinstance(harness.adapter, CollaboratorApiAdapter)
    assert result.accepted
    assert harness.registry.get("s1") == default_collaborator_template()
    messages = list(harness.stream.list_for_session("s1"))
    assert [message.content for message in messages] == ["Collaborator is ready."]


def test_append_session_message_creates_raw_task_without_exposing_proposal(
    tmp_path: Any,
) -> None:
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {
                  "intent_summary": "Write developer docs",
                  "feasibility": {"status": "ready", "confidence": 0.95},
                  "constraints": ["concise"]
                }
                """
            ]
        ),
    )

    result = harness.adapter.append_session_message(
        session_id="s1",
        content="Write developer docs",
    )
    raw = harness.raw_store.list_for_session("s1")[0]

    assert result.accepted
    assert result.message == "session message processed"
    assert raw.intent_summary == "Write developer docs"
    assert raw.status == "ready_to_plan"
    assert not hasattr(result, "roots")
    assert [message.agent_id for message in harness.stream.list_for_session("s1")] == ["user"]


def test_answer_raw_task_ask_records_answer_and_user_message(tmp_path: Any) -> None:
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {
                  "intent_summary": "Build a website",
                  "feasibility": {
                    "status": "needs_clarification",
                    "confidence": 0.5,
                    "missing_inputs": ["audience"]
                  },
                  "asks": [
                    {"question": "Who is the audience?", "reason": "Need scope"}
                  ]
                }
                """
            ]
        ),
    )
    harness.adapter.append_session_message(session_id="s1", content="Build a website")
    raw = harness.raw_store.list_for_session("s1")[0]
    ask = raw.asks[0]

    result = harness.adapter.answer_raw_task_ask(
        session_id="s1",
        raw_task_id=raw.raw_task_id,
        ask_id=ask.ask_id,
        value="Developers",
        idempotency_key="answer-1",
    )
    updated = harness.raw_store.get("s1", raw.raw_task_id)

    assert result.accepted
    assert updated is not None
    assert updated.status == "assessing"
    assert updated.answers[0].value == "Developers"
    messages = list(harness.stream.list_for_session("s1"))
    assert messages[-1].content == "Developers"
    assert messages[-1].context["operation"] == "answerRawTaskAsk"


def test_generate_task_tree_returns_command_result_refs(tmp_path: Any) -> None:
    raw_store = InMemoryRawTaskStore([_raw_task()])
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {
                  "assistant_message": "Drafted",
                  "roots": [
                    {
                      "title": "Write docs",
                      "intent": "Write content",
                      "required_capability": "writing"
                    }
                  ]
                }
                """
            ]
        ),
        raw_store=raw_store,
    )

    result = harness.adapter.generate_task_tree(session_id="s1", raw_task_id="raw1")
    tree = harness.draft_store.list_trees("s1")[0]

    assert result.accepted
    assert result.affected_task_refs == (TaskRef.draft(tree.root_nodes[0].draft_task_id),)
    assert not result.published_task_ids


def test_append_task_message_refines_selected_draft_node(tmp_path: Any) -> None:
    draft_store = InMemoryDraftTaskStore()
    draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Old",
                intent="Write docs",
                required_capability="writing",
            )
        ],
    )
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {
                  "assistant_message": "Updated",
                  "patch": {"title": "New title"},
                  "affected_scope": "selected_node"
                }
                """
            ]
        ),
        draft_store=draft_store,
    )

    result = harness.adapter.append_task_message(
        session_id="s1",
        task_ref=TaskRef.draft("root"),
        content="Make the title clearer",
    )
    updated = harness.draft_store.get_node("s1", "root")

    assert result.accepted
    assert updated is not None
    assert updated.title == "New title"
    messages = list(harness.stream.list_for_task("root"))
    assert messages[0].context["operation"] == "appendTaskMessage"


def test_append_task_message_rejects_published_task_ref(tmp_path: Any) -> None:
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {"assistant_message": "unused",
                 "patch": {"title": "unused"},
                 "affected_scope": "selected_node"}
                """
            ]
        ),
    )

    result = harness.adapter.append_task_message(
        session_id="s1",
        task_ref=TaskRef.published("task-1"),
        content="Change it",
    )

    assert not result.accepted
    assert result.message == "Collaborator authoring currently supports draft tasks only"


def test_publish_task_tree_uses_authoring_publish_boundary(tmp_path: Any) -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Write docs",
                intent="Write docs",
                required_capability="writing",
            )
        ],
    )
    draft_store.mark_accepted("s1", tree.draft_tree_id, expected_version=tree.version)
    publisher = _Publisher(
        TaskPublishResult(
            root_task_ids=("task-root",),
            mappings=(
                DraftToPublishedMapping(
                    session_id="s1",
                    draft_tree_id=tree.draft_tree_id,
                    draft_task_id="root",
                    task_id="task-root",
                    publish_command_id="publish-1",
                ),
            ),
        )
    )
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {"intent_summary": "unused",
                 "feasibility": {"status": "ready", "confidence": 0.9}}
                """
            ]
        ),
        draft_store=draft_store,
        publisher=publisher,
    )

    result = harness.adapter.publish_task_tree(
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        idempotency_key="publish-1",
    )

    assert result.accepted
    assert result.published_task_ids == ("task-root",)
    assert publisher.calls == [("s1", tree.draft_tree_id)]
    messages = list(harness.stream.list_for_session("s1"))
    assert messages[-1].content == "Draft task tree published."


def test_publish_task_tree_accepts_draft_before_authoring_publish(tmp_path: Any) -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Write docs",
                intent="Write docs",
                required_capability="writing",
            )
        ],
    )
    publisher = _Publisher(
        TaskPublishResult(
            root_task_ids=("task-root",),
            mappings=(
                DraftToPublishedMapping(
                    session_id="s1",
                    draft_tree_id=tree.draft_tree_id,
                    draft_task_id="root",
                    task_id="task-root",
                    publish_command_id="publish-1",
                ),
            ),
        )
    )
    harness = _adapter(
        tmp_path,
        _StubLLM(
            [
                """
                {"intent_summary": "unused",
                 "feasibility": {"status": "ready", "confidence": 0.9}}
                """
            ]
        ),
        draft_store=draft_store,
        publisher=publisher,
    )

    result = harness.adapter.publish_task_tree(
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        idempotency_key="publish-1",
    )

    assert result.accepted
    assert result.published_task_ids == ("task-root",)
    node = draft_store.get_node("s1", "root")
    assert node is not None
    assert node.status == "published"
    assert publisher.calls == [("s1", tree.draft_tree_id)]


def _raw_task() -> RawTask:
    return RawTask(
        raw_task_id="raw1",
        session_id="s1",
        source_message_id="m1",
        user_input="Write docs",
        status="ready_to_plan",
        intent_summary="Write docs",
        feasibility=FeasibilityReport(status="ready", confidence=0.9),
    )
