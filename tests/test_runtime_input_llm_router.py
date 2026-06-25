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
    build_builtin_router_skill_prompt_context,
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


def test_llm_runtime_input_route_planner_parses_wechat_task_request_draft() -> None:
    llm = _StubLLM(
        {
            "intent": "execution_request",
            "dispatchTarget": "execution_handoff",
            "scopeKind": "session",
            "sideEffect": "state_effect",
            "confidence": "high",
            "visibleReasoningSummary": "Create one confirmation-gated WeChat task.",
            "userMessage": "I will create a WeChat send task and ask for confirmation.",
            "activatedSkillIds": ("internal:router-wechat-send",),
            "taskRequestDraft": {
                "taskType": "communication.wechat.send_message",
                "instructions": "Send one confirmation-gated WeChat message.",
                "input": {
                    "contactDisplayName": "文件传输助手",
                    "messageText": "你好",
                },
                "policy": {
                    "requiredCapability": "communication.wechat_desktop_send",
                    "requiresHumanConfirmation": True,
                    "riskLevel": "high",
                },
            },
        }
    )
    planner = LLMRuntimeInputRoutePlanner(llm=llm)

    result = planner.plan(
        _request("给微信的文件传输助手发送“你好”"),
        allowed_dispatch_targets=("execution_handoff", "clarification", "unsupported"),
        active_ask=False,
        active_confirmation=False,
    )

    assert result.status == "planned"
    assert result.proposal is not None
    assert result.proposal.task_request_draft is not None
    assert result.proposal.task_request_draft.task_type == (
        "communication.wechat.send_message"
    )
    assert result.proposal.task_request_draft.input["contactDisplayName"] == (
        "文件传输助手"
    )


def test_llm_runtime_input_route_planner_includes_builtin_router_skills() -> None:
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
        _request("给微信的文件传输助手发送“你好”"),
        allowed_dispatch_targets=("read_only_inquiry",),
        active_ask=False,
        active_confirmation=False,
    )

    assert result.status == "planned"
    payload = json.loads(llm.calls[0]["messages"][1]["content"])
    skill_ids = {skill["skillId"] for skill in payload["routerSkills"]}
    assert "internal:router-core" in skill_ids
    assert "internal:router-wechat-send" in skill_ids
    wechat_skill = next(
        skill
        for skill in payload["routerSkills"]
        if skill["skillId"] == "internal:router-wechat-send"
    )
    assert "communication.wechat.send_message" in wechat_skill["outputContract"]
    assert "Required slots" in wechat_skill["instructionExcerpt"]


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


def test_llm_runtime_input_route_planner_writes_router_summary_logs(
    tmp_path: Path,
) -> None:
    configure_session_logging(tmp_path / "logs", session_id="session-1")
    llm = _StubLLM(
        {
            "intent": "execution_request",
            "dispatchTarget": "execution_handoff",
            "sideEffect": "state_effect",
            "confidence": "high",
            "visibleReasoningSummary": "Create one confirmation-gated WeChat task.",
            "userMessage": "I will create a WeChat send task and ask for confirmation.",
            "activatedSkillIds": ("internal:router-wechat-send",),
            "taskRequestDraft": {
                "taskType": "communication.wechat.send_message",
                "instructions": "Send one confirmation-gated WeChat message.",
                "input": {
                    "contactDisplayName": "文件传输助手",
                    "messageText": "不要出现在 runtime summary log",
                },
                "policy": {
                    "requiredCapability": "communication.wechat_desktop_send",
                    "requiresHumanConfirmation": True,
                    "riskLevel": "high",
                },
            },
        }
    )
    planner = LLMRuntimeInputRoutePlanner(llm=llm)

    result = planner.plan(
        _request("给微信的文件传输助手发送“不要出现在 runtime summary log”"),
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert result.status == "planned"
    runtime_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "runtime.jsonl"
    )
    events = [row["event"] for row in runtime_rows[-5:]]
    assert events == [
        "runtime_input_router_request",
        "runtime_input_router_config",
        "runtime_input_router_skills",
        "runtime_input_router_proposal",
        "runtime_input_router_validation",
    ]
    request_data = runtime_rows[-5]["data"]
    assert request_data["content_length"] > 0
    assert "content_sha256_12" in request_data
    assert "不要出现在 runtime summary log" not in json.dumps(
        runtime_rows,
        ensure_ascii=False,
    )
    assert runtime_rows[-4]["data"]["config_scope"] == "app/global"
    assert runtime_rows[-3]["data"]["skill_count"] >= 5
    assert runtime_rows[-2]["data"]["task_type"] == "communication.wechat.send_message"
    assert runtime_rows[-2]["data"]["requires_confirmation"] is True
    assert runtime_rows[-1]["data"]["status"] == "valid"


def test_llm_runtime_input_route_planner_writes_fallback_summary_log(
    tmp_path: Path,
) -> None:
    configure_session_logging(tmp_path / "logs", session_id="session-1")
    planner = LLMRuntimeInputRoutePlanner(llm=_RawStubLLM("not json"))

    result = planner.plan(
        _request("Route this"),
        allowed_dispatch_targets=("read_only_inquiry",),
        active_ask=False,
        active_confirmation=False,
    )

    assert result.status == "unavailable"
    runtime_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "runtime.jsonl"
    )
    assert runtime_rows[-1]["event"] == "runtime_input_router_fallback"
    assert runtime_rows[-1]["level"] == "WARNING"
    assert runtime_rows[-1]["data"]["reason"] == "planner_unavailable"


def test_builtin_router_skill_prompt_context_filters_execution_skills() -> None:
    context = build_builtin_router_skill_prompt_context()

    skill_ids = set(context.activated_skill_ids)
    assert "internal:router-core" in skill_ids
    assert "internal:router-wechat-send" in skill_ids
    assert "internal:execution-wechat-desktop-send" not in skill_ids


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


def test_validate_route_proposal_rejects_execution_handoff_without_task_draft() -> None:
    proposal = RuntimeInputRouteProposal(
        intent="execution_request",
        dispatch_target="execution_handoff",
        side_effect="state_effect",
        confidence="high",
        visible_reasoning_summary="The user asked for workspace-changing work.",
        user_message="Execution work should be created.",
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning == "execution_handoff requires task request draft"


def test_validate_route_proposal_accepts_wechat_task_request_draft() -> None:
    proposal = _wechat_proposal()

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning is None


def test_validate_route_proposal_rejects_wechat_task_without_contact() -> None:
    proposal = _wechat_proposal(input={"messageText": "你好"})

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning == "WeChat send task draft requires contactDisplayName"


def test_validate_route_proposal_rejects_wechat_task_without_confirmation() -> None:
    proposal = _wechat_proposal(
        policy={
            "requiredCapability": "communication.wechat_desktop_send",
            "requiresHumanConfirmation": False,
            "riskLevel": "high",
        }
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning == "WeChat send task draft requires human confirmation"


def test_validate_route_proposal_rejects_wechat_task_bulk_contact() -> None:
    proposal = _wechat_proposal(
        input={
            "contactDisplayName": "文件传输助手、张三",
            "messageText": "你好",
        }
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("execution_handoff",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning == "WeChat send task draft must target one contact"


def test_validate_route_proposal_requires_command_draft_for_existing_command() -> None:
    proposal = RuntimeInputRouteProposal(
        intent="command",
        dispatch_target="existing_command",
        side_effect="state_effect",
        confidence="high",
        visible_reasoning_summary="The user wants to stop the selected task.",
        user_message="I will stop the selected task.",
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("existing_command",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning == "existing_command requires command draft"


def test_validate_route_proposal_accepts_enabled_command_draft() -> None:
    proposal = RuntimeInputRouteProposal(
        intent="command",
        dispatch_target="existing_command",
        side_effect="state_effect",
        confidence="high",
        visible_reasoning_summary="The user wants to stop the selected task.",
        user_message="I will stop the selected task.",
        command_draft={
            "commandKind": "stop_task",
            "targetScopeKind": "task",
            "targetTaskNodeId": "task-1",
            "rationale": "Stop the selected task.",
        },
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("existing_command",),
        active_ask=False,
        active_confirmation=False,
    )

    assert warning is None


def test_validate_route_proposal_requires_ask_answer_draft() -> None:
    proposal = RuntimeInputRouteProposal(
        intent="ask_answer",
        dispatch_target="resolve_ask",
        side_effect="resume_effect",
        confidence="high",
        visible_reasoning_summary="The user answered the active ASK.",
        user_message="I will answer the active ASK.",
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("resolve_ask",),
        active_ask=True,
        active_confirmation=False,
    )

    assert warning == "resolve_ask requires ASK answer draft"


def test_validate_route_proposal_requires_confirmation_response_draft() -> None:
    proposal = RuntimeInputRouteProposal(
        intent="confirmation_response",
        dispatch_target="resolve_confirmation",
        side_effect="authorization_effect",
        confidence="high",
        visible_reasoning_summary="The user answered the active confirmation.",
        user_message="I will resolve the active confirmation.",
    )

    warning = validate_route_proposal(
        proposal,
        allowed_dispatch_targets=("resolve_confirmation",),
        active_ask=False,
        active_confirmation=True,
    )

    assert warning == "resolve_confirmation requires confirmation response draft"


def _request(content: str) -> RuntimeInputRouteRequest:
    return RuntimeInputRouteRequest(
        command_id="route-1",
        session_id="session-1",
        workspace_id="workspace-1",
        content=content,
        selection=RuntimeInputSelection(scope_kind="session"),
    )


def _wechat_proposal(
    *,
    input: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> RuntimeInputRouteProposal:
    return RuntimeInputRouteProposal(
        intent="execution_request",
        dispatch_target="execution_handoff",
        side_effect="state_effect",
        confidence="high",
        visible_reasoning_summary="Create one confirmation-gated WeChat task.",
        user_message="I will create a WeChat send task and ask for confirmation.",
        activated_skill_ids=("internal:router-wechat-send",),
        task_request_draft={
            "taskType": "communication.wechat.send_message",
            "instructions": "Send one confirmation-gated WeChat message.",
            "input": input
            if input is not None
            else {
                "contactDisplayName": "文件传输助手",
                "messageText": "你好",
            },
            "policy": policy
            if policy is not None
            else {
                "requiredCapability": "communication.wechat_desktop_send",
                "requiresHumanConfirmation": True,
                "riskLevel": "high",
            },
        },
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
