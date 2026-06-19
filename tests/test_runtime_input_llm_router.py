from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from taskweavn.llm.contracts import ChatResponse
from taskweavn.observability import configure_session_logging
from taskweavn.server.runtime_input_llm_router import (
    LLMRuntimeInputRoutePlanner,
    RuntimeInputRouteProposal,
    validate_route_proposal,
)
from taskweavn.server.ui_contract.read_only_inquiry import ReadOnlyInquiryRef
from taskweavn.server.ui_contract.runtime_input import (
    RuntimeInputRouteRequest,
    RuntimeInputSelection,
)


def test_llm_runtime_input_route_planner_parses_read_only_file_refs() -> None:
    llm = _StubLLM(
        {
            "intent": "question",
            "dispatchTarget": "read_only_inquiry",
            "scopeKind": "session",
            "sideEffect": "no_effect",
            "confidence": "high",
            "visibleReasoningSummary": "The user asks for an answer from README.",
            "userMessage": "I can answer this from README.",
            "readOnlyRefs": [
                {
                    "kind": "file",
                    "path": "README.md",
                    "label": "README",
                }
            ],
        }
    )
    planner = LLMRuntimeInputRoutePlanner(llm=llm)

    result = planner.plan(
        _request("How do I start this project?"),
        allowed_dispatch_targets=(
            "read_only_inquiry",
            "record_guidance",
            "execution_handoff",
            "clarification",
            "unsupported",
        ),
        active_ask=False,
        active_confirmation=False,
    )

    assert result.status == "planned"
    assert result.proposal is not None
    assert result.proposal.dispatch_target == "read_only_inquiry"
    assert result.proposal.read_only_refs[0].kind == "file"
    assert result.proposal.read_only_refs[0].path == "README.md"
    assert llm.calls[0]["metadata"]["agent_id"] == "runtime_input_router"
    assert llm.calls[0]["tools"] is None


def test_llm_runtime_input_route_planner_fails_closed_for_invalid_json() -> None:
    planner = LLMRuntimeInputRoutePlanner(llm=_RawStubLLM("not json"))

    result = planner.plan(
        _request("Route this"),
        allowed_dispatch_targets=("read_only_inquiry",),
        active_ask=False,
        active_confirmation=False,
    )

    assert result.status == "unavailable"
    assert result.proposal is None


def test_llm_runtime_input_route_planner_writes_split_agent_logs(
    tmp_path: Path,
) -> None:
    configure_session_logging(tmp_path / "logs", session_id="session-1")
    llm = _StubLLM(
        {
            "intent": "question",
            "dispatchTarget": "read_only_inquiry",
            "sideEffect": "no_effect",
            "confidence": "high",
            "visibleReasoningSummary": "Answer from session facts.",
            "userMessage": "I can answer this without changing files.",
        }
    )
    planner = LLMRuntimeInputRoutePlanner(llm=llm)

    result = planner.plan(
        _request("课件是否已经完成了？"),
        allowed_dispatch_targets=("read_only_inquiry",),
        active_ask=False,
        active_confirmation=False,
    )

    assert result.status == "planned"
    meta_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "llm.jsonl"
    )
    io_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "llm_io.jsonl"
    )
    assert [row["event"] for row in meta_rows[-2:]] == [
        "agent_input",
        "agent_output",
    ]
    assert [row["event"] for row in io_rows[-2:]] == [
        "agent_input",
        "agent_output",
    ]
    assert meta_rows[-2]["data"]["request_purpose"] == "runtime_input.route.plan"
    assert "messages" not in meta_rows[-2]["data"]
    assert (
        "课件是否已经完成了？"
        in io_rows[-2]["data"]["input"]["messages"][1]["content"]
    )
    assert "content" not in meta_rows[-1]["data"]
    assert "read_only_inquiry" in io_rows[-1]["data"]["output"]["content"]


def test_validate_route_proposal_rejects_low_confidence_mutation() -> None:
    proposal = RuntimeInputRouteProposal(
        intent="execution_request",
        dispatch_target="execution_handoff",
        side_effect="state_effect",
        confidence="low",
        visible_reasoning_summary="The request asks for workspace-changing work.",
        user_message="Execution work should be created.",
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning == "low-confidence mutation is not allowed"


def test_validate_route_proposal_rejects_refs_on_mutating_dispatch() -> None:
    proposal = RuntimeInputRouteProposal(
        intent="execution_request",
        dispatch_target="execution_handoff",
        side_effect="state_effect",
        confidence="high",
        visible_reasoning_summary="The user asked for file edits.",
        user_message="Execution work should be created.",
        read_only_refs=(
            ReadOnlyInquiryRef(
                kind="file",
                path="README.md",
                label="README",
            ),
        ),
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning == "read-only refs are only allowed for read_only_inquiry"


def _request(content: str) -> RuntimeInputRouteRequest:
    return RuntimeInputRouteRequest(
        command_id="route-1",
        session_id="session-1",
        workspace_id="workspace-1",
        content=content,
        selection=RuntimeInputSelection(scope_kind="session"),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@dataclass
class _StubLLM:
    payload: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "metadata": metadata,
                **kwargs,
            }
        )
        return ChatResponse(
            content=json.dumps(self.payload),
            tool_calls=[],
            raw_assistant_message={"role": "assistant", "content": "json"},
        )


@dataclass
class _RawStubLLM:
    content: str

    def chat(self, *args: Any, **kwargs: Any) -> ChatResponse:
        return ChatResponse(
            content=self.content,
            tool_calls=[],
            raw_assistant_message={"role": "assistant", "content": self.content},
        )
