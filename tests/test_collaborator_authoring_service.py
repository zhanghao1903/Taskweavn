"""Tests for CollaboratorAuthoringService proposal mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskweavn.llm import ChatResponse
from taskweavn.task import (
    CollaboratorAuthoringService,
    DefaultAuthoringCommandService,
    DefaultAuthoringContextBuilder,
    DefaultCollaboratorAuthoringService,
    DraftTaskNode,
    FeasibilityReport,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    RawTask,
    StaticCapabilityCatalog,
    TaskRef,
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


def _service(
    llm: _StubLLM,
    *,
    raw_store: InMemoryRawTaskStore | None = None,
    draft_store: InMemoryDraftTaskStore | None = None,
) -> tuple[
    DefaultCollaboratorAuthoringService,
    InMemoryRawTaskStore,
    InMemoryDraftTaskStore,
]:
    raw_store = raw_store or InMemoryRawTaskStore()
    draft_store = draft_store or InMemoryDraftTaskStore()
    context_builder = DefaultAuthoringContextBuilder(
        raw_task_store=raw_store,
        draft_store=draft_store,
        capability_catalog=StaticCapabilityCatalog(["general", "writing", "testing"]),
    )
    command_service = DefaultAuthoringCommandService(
        raw_task_store=raw_store,
        draft_store=draft_store,
    )
    return (
        DefaultCollaboratorAuthoringService(
            llm=llm,
            context_builder=context_builder,
            command_service=command_service,
        ),
        raw_store,
        draft_store,
    )


def test_collaborator_authoring_service_protocol_conformance() -> None:
    service, _, _ = _service(
        _StubLLM(
            [
                """
                {"intent_summary": "Write docs",
                 "feasibility": {"status": "ready", "confidence": 0.9}}
                """
            ]
        )
    )

    assert isinstance(service, CollaboratorAuthoringService)


def test_create_raw_task_from_message_maps_feasibility_to_command_service() -> None:
    llm = _StubLLM(
        [
            """
            {
              "kind": "raw_task",
              "intent_summary": "Write docs for developers",
              "feasibility": {
                "status": "ready",
                "confidence": 0.93,
                "reasons": ["clear enough"]
              },
              "constraints": ["concise"],
              "assumptions": ["developer audience"]
            }
            """
        ]
    )
    service, raw_store, _ = _service(llm)

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Write docs for developers",
    )
    raw = raw_store.list_for_session("s1")[0]

    assert result.ok
    assert raw.intent_summary == "Write docs for developers"
    assert raw.status == "ready_to_plan"
    assert raw.constraints == ("concise",)
    assert "capabilities" in llm.calls[0][1]["content"]


def test_create_raw_task_from_message_can_emit_clarification() -> None:
    service, raw_store, _ = _service(
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
                    {
                      "question": "Who is the audience?",
                      "reason": "Need scope",
                      "options": [
                        {"label": "Developers", "value": "developers"}
                      ]
                    }
                  ]
                }
                """
            ]
        )
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Build a website",
    )
    raw = raw_store.list_for_session("s1")[0]

    assert result.ok
    assert raw.status == "awaiting_user"
    assert raw.asks[0].question == "Who is the audience?"


def test_generate_task_tree_maps_proposal_to_create_tree_command() -> None:
    raw_store = InMemoryRawTaskStore([_raw_task()])
    service, _, draft_store = _service(
        _StubLLM(
            [
                """
                {
                  "assistant_message": "Drafted a plan",
                  "roots": [
                    {
                      "title": "Write docs",
                      "intent": "Write content",
                      "required_capability": "writing",
                      "children": [
                        {
                          "title": "Test examples",
                          "intent": "Run tests",
                          "required_capability": "testing"
                        }
                      ]
                    }
                  ]
                }
                """
            ]
        ),
        raw_store=raw_store,
    )

    result = service.generate_task_tree(session_id="s1", raw_task_id="raw1")
    tree = draft_store.list_trees("s1")[0]

    assert result.ok
    assert len(result.object_refs) == 2
    assert len(draft_store.list_nodes("s1", tree.draft_tree_id)) == 2


def test_refine_task_node_maps_patch_without_rebuilding_tree() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
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
    service, _, draft_store = _service(
        _StubLLM(
            [
                """
                {
                  "assistant_message": "Updated selected node",
                  "patch": {"title": "New title"},
                  "affected_scope": "selected_node"
                }
                """
            ]
        ),
        draft_store=draft_store,
    )

    result = service.refine_task_node(
        session_id="s1",
        selected_task_ref=TaskRef.draft("root"),
        instruction="Make it clearer",
    )
    updated = draft_store.get_node("s1", "root")

    assert result.ok
    assert updated is not None
    assert updated.title == "New title"
    assert len(draft_store.list_trees("s1")) == 1
    assert draft_store.list_trees("s1")[0].draft_tree_id == tree.draft_tree_id


def test_refine_task_node_rejects_invalid_proposal_without_mutating() -> None:
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
    service, _, draft_store = _service(
        _StubLLM(["not json"]),
        draft_store=draft_store,
    )

    result = service.refine_task_node(
        session_id="s1",
        selected_task_ref=TaskRef.draft("root"),
        instruction="Make it clearer",
    )
    node = draft_store.get_node("s1", "root")

    assert not result.ok
    assert result.errors[0].code == "invalid_llm_proposal"
    assert node is not None
    assert node.title == "Old"


def _raw_task() -> RawTask:
    return RawTask(
        raw_task_id="raw1",
        session_id="s1",
        source_message_id="m1",
        user_input="Write docs",
        status="ready_to_plan",
        feasibility=FeasibilityReport(status="ready", confidence=0.9),
    )
