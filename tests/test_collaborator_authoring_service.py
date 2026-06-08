"""Tests for CollaboratorAuthoringService proposal mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from taskweavn.core import LoopTerminalAction
from taskweavn.llm import ChatResponse, ToolCall
from taskweavn.observability import configure_session_logging
from taskweavn.prompts import COLLABORATOR_AUTHORING_SYSTEM_PROMPT
from taskweavn.task import (
    ASK_AUTHORING_TOOL_NAME,
    AUTHORING_READ_WORKSPACE_TOOL_NAME,
    AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
    FINISH_AUTHORING_TOOL_NAME,
    CollaboratorAuthoringProfile,
    CollaboratorAuthoringService,
    CollaboratorWorkspaceContextSource,
    DefaultAuthoringCommandService,
    DefaultAuthoringContextBuilder,
    DefaultCollaboratorAuthoringService,
    DraftTaskNode,
    FeasibilityReport,
    InMemoryAuthoringEvidenceStore,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    LocalCollaboratorWorkspaceContextSource,
    RawTask,
    StaticCapabilityCatalog,
    TaskRef,
)


@dataclass
class _StubLLM:
    responses: list[str | ChatResponse]
    calls: list[list[dict[str, Any]]] = field(default_factory=list)
    metadata_calls: list[dict[str, Any] | None] = field(default_factory=list)
    tools_calls: list[list[dict[str, Any]] | None] = field(default_factory=list)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append(messages)
        self.tools_calls.append(tools)
        self.metadata_calls.append(metadata)
        response = self.responses.pop(0)
        if isinstance(response, ChatResponse):
            return response
        content = response
        return ChatResponse(
            content=content,
            tool_calls=[],
            raw_assistant_message={
                "role": "assistant",
                "content": content,
            },
        )


class _SpyProfile(CollaboratorAuthoringProfile):
    def __init__(self) -> None:
        super().__init__()
        self.terminal_actions: list[LoopTerminalAction] = []

    def map_terminal_action(
        self,
        action: LoopTerminalAction,
        context: object,
    ) -> Any:
        self.terminal_actions.append(action)
        return super().map_terminal_action(action, context)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _service(
    llm: _StubLLM,
    *,
    raw_store: InMemoryRawTaskStore | None = None,
    draft_store: InMemoryDraftTaskStore | None = None,
    profile: CollaboratorAuthoringProfile | None = None,
    workspace_context_source: CollaboratorWorkspaceContextSource | None = None,
    max_context_steps: int = 3,
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
            profile=profile,
            workspace_context_source=workspace_context_source,
            max_context_steps=max_context_steps,
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
    assert llm.tools_calls == [None]
    assert llm.metadata_calls[0] is not None
    assert llm.metadata_calls[0]["loop_profile_id"] == "collaborator_authoring"
    assert llm.metadata_calls[0]["terminal_tool_name"] == "finish_authoring"


def test_create_raw_task_from_message_routes_through_finish_profile() -> None:
    llm = _StubLLM(
        [
            """
            {
              "kind": "raw_task",
              "intent_summary": "Write docs",
              "feasibility": {"status": "ready", "confidence": 0.9}
            }
            """
        ]
    )
    profile = _SpyProfile()
    service, raw_store, _ = _service(llm, profile=profile)

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Write docs",
    )

    assert result.ok
    assert raw_store.list_for_session("s1")[0].intent_summary == "Write docs"
    assert len(profile.terminal_actions) == 1
    action = profile.terminal_actions[0]
    assert action.tool_name == "finish_authoring"
    assert action.arguments["proposal_kind"] == "raw_task"
    assert AUTHORING_READ_WORKSPACE_TOOL_NAME in profile.allowed_tool_names
    assert AUTHORING_SEARCH_WORKSPACE_TOOL_NAME in profile.allowed_tool_names
    assert ASK_AUTHORING_TOOL_NAME in profile.allowed_tool_names
    assert llm.tools_calls == [None]


def test_create_raw_task_from_message_dispatches_ask_authoring_tool(
    tmp_path: Path,
) -> None:
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=InMemoryAuthoringEvidenceStore(),
    )
    llm = _StubLLM(
        [
            _tool_call_response(
                ASK_AUTHORING_TOOL_NAME,
                {
                    "intent_summary": "Build a website",
                    "question": "Who is the audience?",
                    "reason": "Audience changes the task plan.",
                    "options": [
                        {"label": "Developers", "value": "developers"},
                    ],
                },
                call_id="ask-1",
            ),
        ]
    )
    service, raw_store, _ = _service(
        llm,
        workspace_context_source=source,
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Build a website",
    )
    raw = raw_store.list_for_session("s1")[0]
    tool_names = _tool_names(llm.tools_calls[0] or [])

    assert result.ok
    assert raw.intent_summary == "Build a website"
    assert raw.status == "awaiting_user"
    assert raw.feasibility is not None
    assert raw.feasibility.status == "needs_clarification"
    assert raw.asks[0].question == "Who is the audience?"
    assert raw.asks[0].options[0].label == "Developers"
    assert tool_names == {
        AUTHORING_READ_WORKSPACE_TOOL_NAME,
        AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
        ASK_AUTHORING_TOOL_NAME,
        FINISH_AUTHORING_TOOL_NAME,
    }


def test_create_raw_task_from_message_dispatches_workspace_read_then_finish(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text(
        "Product guidance: preserve focused backend contracts.",
        encoding="utf-8",
    )
    evidence_store = InMemoryAuthoringEvidenceStore()
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=evidence_store,
    )
    profile = _SpyProfile()
    llm = _StubLLM(
        [
            _tool_call_response(
                AUTHORING_READ_WORKSPACE_TOOL_NAME,
                {
                    "paths": ["README.md"],
                    "purpose": "Inspect accepted project guidance",
                    "max_snippet_chars": 80,
                },
                call_id="read-1",
            ),
            _tool_call_response(
                FINISH_AUTHORING_TOOL_NAME,
                {
                    "proposal_kind": "raw_task",
                    "proposal": {
                        "kind": "raw_task",
                        "intent_summary": "Preserve focused backend contracts",
                        "feasibility": {
                            "status": "ready",
                            "confidence": 0.9,
                        },
                    },
                },
                call_id="finish-1",
            ),
        ]
    )
    service, raw_store, _ = _service(
        llm,
        profile=profile,
        workspace_context_source=source,
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Plan the backend contract work",
    )
    raw = raw_store.list_for_session("s1")[0]
    evidence = evidence_store.list_for_session("s1")
    first_tool_names = _tool_names(llm.tools_calls[0] or [])
    tool_message = next(
        message for message in llm.calls[1] if message.get("role") == "tool"
    )

    assert result.ok
    assert raw.intent_summary == "Preserve focused backend contracts"
    assert first_tool_names == {
        AUTHORING_READ_WORKSPACE_TOOL_NAME,
        AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
        ASK_AUTHORING_TOOL_NAME,
        FINISH_AUTHORING_TOOL_NAME,
    }
    assert evidence[0].tool_name == AUTHORING_READ_WORKSPACE_TOOL_NAME
    assert evidence[0].path_label == "workspace://current/README.md"
    assert "workspace://current/README.md" in tool_message["content"]
    assert profile.terminal_actions[0].tool_call_id == "finish-1"
    assert profile.terminal_actions[0].arguments["evidence_refs"] == [
        evidence[0].evidence_id
    ]


def test_create_raw_task_from_message_dispatches_workspace_read_then_ask(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text(
        "Product guidance: ask when requirements are underspecified.",
        encoding="utf-8",
    )
    evidence_store = InMemoryAuthoringEvidenceStore()
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=evidence_store,
    )
    profile = _SpyProfile()
    llm = _StubLLM(
        [
            _tool_call_response(
                AUTHORING_READ_WORKSPACE_TOOL_NAME,
                {
                    "paths": ["README.md"],
                    "purpose": "Inspect ask policy",
                    "max_snippet_chars": 80,
                },
                call_id="read-1",
            ),
            _tool_call_response(
                ASK_AUTHORING_TOOL_NAME,
                {
                    "intent_summary": "Plan an underspecified feature",
                    "question": "Which user workflow should this feature support first?",
                    "reason": (
                        "The workspace guidance says to ask when requirements are "
                        "underspecified."
                    ),
                    "missing_inputs": ["first workflow"],
                },
                call_id="ask-1",
            ),
        ]
    )
    service, raw_store, _ = _service(
        llm,
        profile=profile,
        workspace_context_source=source,
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Plan the feature",
    )
    raw = raw_store.list_for_session("s1")[0]
    evidence = evidence_store.list_for_session("s1")

    assert result.ok
    assert raw.status == "awaiting_user"
    assert raw.asks[0].question == (
        "Which user workflow should this feature support first?"
    )
    assert profile.terminal_actions[0].tool_name == ASK_AUTHORING_TOOL_NAME
    assert profile.terminal_actions[0].tool_call_id == "ask-1"
    assert profile.terminal_actions[0].arguments["evidence_refs"] == [
        evidence[0].evidence_id
    ]


def test_create_raw_task_from_message_dispatches_workspace_search_then_finish(
    tmp_path: Path,
) -> None:
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "plans" / "feature.md").write_text(
        "Collaborator search evidence should guide authoring.",
        encoding="utf-8",
    )
    evidence_store = InMemoryAuthoringEvidenceStore()
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=evidence_store,
    )
    llm = _StubLLM(
        [
            _tool_call_response(
                AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
                {
                    "query": "search evidence",
                    "scope": {"path_globs": ["docs/plans/**"]},
                    "purpose": "Find project guidance",
                },
                call_id="search-1",
            ),
            _tool_call_response(
                FINISH_AUTHORING_TOOL_NAME,
                {
                    "proposal_kind": "raw_task",
                    "proposal": {
                        "kind": "raw_task",
                        "intent_summary": "Use collaborator search evidence",
                        "feasibility": {
                            "status": "ready",
                            "confidence": 0.88,
                        },
                    },
                },
                call_id="finish-1",
            ),
        ]
    )
    service, raw_store, _ = _service(
        llm,
        workspace_context_source=source,
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Plan with workspace guidance",
    )
    evidence = evidence_store.list_for_session("s1")
    tool_message = next(
        message for message in llm.calls[1] if message.get("role") == "tool"
    )

    assert result.ok
    assert raw_store.list_for_session("s1")[0].intent_summary == (
        "Use collaborator search evidence"
    )
    assert evidence[0].tool_name == AUTHORING_SEARCH_WORKSPACE_TOOL_NAME
    assert evidence[0].path_label == "workspace://current/docs/plans/feature.md"
    assert "Collaborator search evidence" in tool_message["content"]


def test_create_raw_task_from_message_rejects_context_step_limit(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("Guidance", encoding="utf-8")
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=InMemoryAuthoringEvidenceStore(),
    )
    llm = _StubLLM(
        [
            _tool_call_response(
                AUTHORING_READ_WORKSPACE_TOOL_NAME,
                {
                    "paths": ["README.md"],
                    "purpose": "Inspect guidance",
                },
                call_id="read-1",
            )
        ]
    )
    service, raw_store, _ = _service(
        llm,
        workspace_context_source=source,
        max_context_steps=0,
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Plan docs",
    )

    assert not result.ok
    assert result.errors[0].code == "invalid_llm_proposal"
    assert "step limit" in result.errors[0].message
    assert not raw_store.list_for_session("s1")


def test_collaborator_logs_agent_llm_input_and_output(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="s1")
    response_content = """
    {
      "kind": "raw_task",
      "intent_summary": "Write docs for developers",
      "feasibility": {
        "status": "ready",
        "confidence": 0.93
      }
    }
    """
    llm = _StubLLM([response_content])
    service, _, _ = _service(llm)

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Write docs for developers",
    )

    assert result.ok
    rows = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "llm.jsonl")
    agent_rows = [
        row for row in rows if row["event"] in {"agent_input", "agent_output"}
    ]
    assert [row["event"] for row in agent_rows] == ["agent_input", "agent_output"]
    input_row, output_row = agent_rows

    assert input_row["context"] == {"session_id": "s1", "agent_id": "collaborator"}
    assert input_row["data"]["agent_kind"] == "collaborator"
    assert input_row["data"]["request_purpose"] == "collaborator.create_raw_task"
    assert input_row["data"]["messages"][0]["content"] == COLLABORATOR_AUTHORING_SYSTEM_PROMPT
    assert "Write docs for developers" in input_row["data"]["messages"][1]["content"]
    assert input_row["data"]["metadata"]["session_id"] == "s1"

    assert output_row["context"] == {"session_id": "s1", "agent_id": "collaborator"}
    assert output_row["data"]["agent_kind"] == "collaborator"
    assert output_row["data"]["request_purpose"] == "collaborator.create_raw_task"
    assert output_row["data"]["content"] == response_content
    assert output_row["data"]["raw_assistant_message"]["content_omitted"] == (
        "duplicate_of_content"
    )
    assert "content" not in output_row["data"]["raw_assistant_message"]


def test_collaborator_prompt_contains_exact_authoring_protocols() -> None:
    llm = _StubLLM(
        [
            """
            {
              "intent_summary": "Write docs",
              "feasibility": {"status": "ready", "confidence": 0.9}
            }
            """
        ]
    )
    service, _, _ = _service(llm)

    service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Write docs",
    )

    system_prompt = llm.calls[0][0]["content"]
    assert system_prompt == COLLABORATOR_AUTHORING_SYSTEM_PROMPT
    assert "System role and positioning:" in system_prompt
    assert "You are a built-in system collaborator" in system_prompt
    assert "Why this work matters:" in system_prompt
    assert "first structured boundary" in system_prompt
    assert "product-facing contract" in system_prompt
    assert "Work scenario:" in system_prompt
    assert "Authoring lifecycle:" in system_prompt
    assert "RawTaskProposal" in system_prompt
    assert "DraftTaskTreeProposal" in system_prompt
    assert "DraftTaskPatchProposal" in system_prompt
    assert "RawTaskProposal dependency rules:" in system_prompt
    assert "DraftTaskTreeProposal dependency rules:" in system_prompt
    assert "DraftTaskPatchProposal dependency rules:" in system_prompt
    assert "Do not return feasibility as a string" in system_prompt
    assert "Never return asks as a string list" in system_prompt
    assert "Do not generate ids, timestamps" in system_prompt
    assert '"ready", "needs_clarification", "needs_user_permission"' in system_prompt
    assert "Final checklist before returning:" in system_prompt


def test_create_raw_task_from_message_accepts_wrapped_raw_task_payload() -> None:
    service, raw_store, _ = _service(
        _StubLLM(
            [
                """
                {
                  "raw_task": {
                    "task_id": "task-2026-05-20T17:44:44Z",
                    "title": "Design a simple professional personal website",
                    "constraints": ["simple", "professional"],
                    "created_at": "2026-05-20T17:44:44Z"
                  },
                  "feasibility": {
                    "status": "ready",
                    "confidence": 0.88
                  }
                }
                """
            ]
        )
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="Design a simple professional personal website",
    )
    raw = raw_store.list_for_session("s1")[0]

    assert result.ok
    assert raw.intent_summary == "Design a simple professional personal website"
    assert raw.status == "ready_to_plan"
    assert raw.constraints == ("simple", "professional")


def test_create_raw_task_from_message_accepts_string_feasibility_and_asks() -> None:
    service, raw_store, _ = _service(
        _StubLLM(
            [
                """
                {
                  "raw_task": {
                    "title": "Design a concise professional personal website"
                  },
                  "feasibility": "Feasible",
                  "asks": [
                    "请确认网站的目标受众。",
                    "需要展示哪些主要信息？"
                  ],
                  "constraints": "简洁专业"
                }
                """
            ]
        )
    )

    result = service.create_raw_task_from_message(
        session_id="s1",
        source_message_id="m1",
        user_input="帮我设计一个简洁专业的个人网站",
    )
    raw = raw_store.list_for_session("s1")[0]

    assert result.ok
    assert raw.intent_summary == "Design a concise professional personal website"
    assert raw.status == "awaiting_user"
    assert raw.feasibility is not None
    assert raw.feasibility.status == "ready"
    assert raw.constraints == ("简洁专业",)
    assert [ask.question for ask in raw.asks] == [
        "请确认网站的目标受众。",
        "需要展示哪些主要信息？",
    ]


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


def _tool_call_response(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    call_id: str,
    thought: str = "",
) -> ChatResponse:
    raw_arguments = json.dumps(arguments)
    return ChatResponse(
        content=thought,
        tool_calls=[ToolCall(id=call_id, name=tool_name, arguments=raw_arguments)],
        raw_assistant_message={
            "role": "assistant",
            "content": thought,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": raw_arguments,
                    },
                }
            ],
        },
    )


def _tool_names(tools: list[dict[str, Any]]) -> set[str]:
    return {tool["function"]["name"] for tool in tools}
