"""LLM-assisted planner for Runtime Input Router decisions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from taskweavn.llm.contracts import ChatResponse
from taskweavn.llm.logging import log_agent_llm_input, log_agent_llm_output
from taskweavn.observability import LogContext
from taskweavn.server.ui_contract.base import UiContractModel
from taskweavn.server.ui_contract.read_only_inquiry import ReadOnlyInquiryRef
from taskweavn.server.ui_contract.runtime_input import (
    RuntimeInputConfidence,
    RuntimeInputDispatchTarget,
    RuntimeInputIntent,
    RuntimeInputRouteRequest,
    RuntimeInputScopeKind,
)
from taskweavn.server.ui_contract.view_models import SessionActivitySideEffect

RouterPlannerStatus = Literal["planned", "unavailable", "invalid"]
_MUTATING_TARGETS = {
    "record_guidance",
    "resolve_ask",
    "resolve_confirmation",
    "existing_command",
    "execution_handoff",
}


class RuntimeInputRoutePlanner(Protocol):
    def plan(
        self,
        request: RuntimeInputRouteRequest,
        *,
        allowed_dispatch_targets: tuple[RuntimeInputDispatchTarget, ...],
        active_ask: bool,
        active_confirmation: bool,
    ) -> RouterPlannerResult: ...


class RouterClarificationQuestion(UiContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    input_hint: str | None = Field(default=None, min_length=1)
    required: bool = True


class RouterClarificationOption(UiContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str | None = Field(default=None, min_length=1)


class RouterClarification(UiContractModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    questions: tuple[RouterClarificationQuestion, ...] = ()
    options: tuple[RouterClarificationOption, ...] = ()


class RuntimeInputRouteProposal(UiContractModel):
    intent: RuntimeInputIntent
    dispatch_target: RuntimeInputDispatchTarget
    scope_kind: RuntimeInputScopeKind | None = None
    side_effect: SessionActivitySideEffect
    confidence: RuntimeInputConfidence
    visible_reasoning_summary: str = Field(min_length=1, max_length=1200)
    user_message: str = Field(min_length=1, max_length=4000)
    needs_clarification: bool = False
    clarification: RouterClarification | None = None
    read_only_refs: tuple[ReadOnlyInquiryRef, ...] = ()

    @field_validator("visible_reasoning_summary", "user_message")
    @classmethod
    def _safe_summary(cls, value: str) -> str:
        stripped = " ".join(value.strip().split())
        if _looks_like_hidden_reasoning(stripped):
            raise ValueError("hidden reasoning is not allowed")
        return stripped

    @model_validator(mode="after")
    def _validate_clarification(self) -> RuntimeInputRouteProposal:
        if self.needs_clarification and self.clarification is None:
            raise ValueError("needsClarification requires clarification")
        return self


@dataclass(frozen=True)
class RouterPlannerResult:
    status: RouterPlannerStatus
    proposal: RuntimeInputRouteProposal | None = None
    warning: str | None = None


@dataclass(frozen=True)
class LLMRuntimeInputRoutePlanner:
    """No-mutation LLM route planner with deterministic validation."""

    llm: Any
    timeout_seconds: float | None = 30.0

    def plan(
        self,
        request: RuntimeInputRouteRequest,
        *,
        allowed_dispatch_targets: tuple[RuntimeInputDispatchTarget, ...],
        active_ask: bool,
        active_confirmation: bool,
    ) -> RouterPlannerResult:
        messages = _messages(
            request,
            allowed_dispatch_targets=allowed_dispatch_targets,
            active_ask=active_ask,
            active_confirmation=active_confirmation,
        )
        metadata = {
            "agent_kind": "router",
            "agent_id": "runtime_input_router",
            "request_purpose": "runtime_input.route.plan",
            "session_id": request.session_id,
        }
        log_context = LogContext(
            session_id=request.session_id,
            agent_id="runtime_input_router",
        )
        try:
            log_agent_llm_input(
                agent_kind="router",
                request_purpose="runtime_input.route.plan",
                messages=messages,
                tools=None,
                metadata=metadata,
                context=log_context,
            )
            response = self.llm.chat(
                messages=messages,
                tools=None,
                metadata=metadata,
                timeout_seconds=self.timeout_seconds,
            )
            if isinstance(response, ChatResponse):
                log_agent_llm_output(
                    agent_kind="router",
                    request_purpose="runtime_input.route.plan",
                    response=response,
                    metadata=metadata,
                    context=log_context,
                )
            raw_content = _response_content(response)
            proposal = RuntimeInputRouteProposal.model_validate(
                _json_object(raw_content)
            )
            warning = validate_route_proposal(
                proposal,
                allowed_dispatch_targets=allowed_dispatch_targets,
                active_ask=active_ask,
                active_confirmation=active_confirmation,
            )
            if warning is not None:
                return RouterPlannerResult(status="invalid", warning=warning)
            return RouterPlannerResult(status="planned", proposal=proposal)
        except Exception as exc:  # noqa: BLE001 - Router must fail closed.
            return RouterPlannerResult(
                status="unavailable",
                warning=f"router planner unavailable: {type(exc).__name__}",
            )


def validate_route_proposal(
    proposal: RuntimeInputRouteProposal,
    *,
    allowed_dispatch_targets: tuple[RuntimeInputDispatchTarget, ...],
    active_ask: bool,
    active_confirmation: bool,
) -> str | None:
    """Validate that an LLM proposal stays inside Router policy boundaries."""

    if proposal.dispatch_target not in allowed_dispatch_targets:
        return f"dispatch target {proposal.dispatch_target!r} is not allowed"
    if proposal.confidence == "low" and proposal.dispatch_target in _MUTATING_TARGETS:
        return "low-confidence mutation is not allowed"
    if proposal.dispatch_target == "resolve_ask" and not active_ask:
        return "resolve_ask requires active ASK"
    if proposal.dispatch_target == "resolve_confirmation" and not active_confirmation:
        return "resolve_confirmation requires active confirmation"
    expected_side_effect = _side_effect_for_dispatch(proposal.dispatch_target)
    if expected_side_effect is not None and proposal.side_effect != expected_side_effect:
        return (
            f"dispatch target {proposal.dispatch_target!r} requires "
            f"side effect {expected_side_effect!r}"
        )
    if proposal.dispatch_target != "read_only_inquiry" and proposal.read_only_refs:
        return "read-only refs are only allowed for read_only_inquiry"
    return None


def _messages(
    request: RuntimeInputRouteRequest,
    *,
    allowed_dispatch_targets: tuple[RuntimeInputDispatchTarget, ...],
    active_ask: bool,
    active_confirmation: bool,
) -> list[dict[str, str]]:
    payload = {
        "sessionId": request.session_id,
        "workspaceId": request.workspace_id,
        "content": request.content,
        "mode": request.mode,
        "selection": request.selection.to_contract_dict(),
        "activeAsk": active_ask,
        "activeConfirmation": active_confirmation,
        "allowedDispatchTargets": list(allowed_dispatch_targets),
        "outputSchema": {
            "format": "json_object",
            "readOnlyRefs": "optional refs with kind=file or diff and safe workspace-relative path",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You are Plato's Runtime Input Router planner. Return only JSON. "
                "You may classify user input and request read-only refs, but you "
                "must not execute tools, mutate files, or invent backend commands. "
                "Use read_only_inquiry for questions that can be answered from "
                "session/task facts or safe workspace file/diff context. Use "
                "execution_handoff only when the user asks Plato to create, edit, "
                "run, or produce workspace-changing work. Do not include hidden "
                "chain-of-thought; visibleReasoningSummary must be a short user-safe "
                "summary."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        },
    ]


def _json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("router planner response must be a JSON object")
    return parsed


def _response_content(response: Any) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("router planner response content is empty")
    return content


def _side_effect_for_dispatch(
    dispatch_target: RuntimeInputDispatchTarget,
) -> SessionActivitySideEffect | None:
    if dispatch_target in {"read_only_inquiry", "clarification", "unsupported"}:
        return "no_effect"
    if dispatch_target == "record_guidance":
        return "context_effect"
    if dispatch_target == "execution_handoff":
        return "state_effect"
    if dispatch_target == "resolve_ask":
        return "resume_effect"
    if dispatch_target == "resolve_confirmation":
        return "authorization_effect"
    if dispatch_target == "existing_command":
        return "state_effect"
    return None


def _looks_like_hidden_reasoning(value: str) -> bool:
    lowered = value.lower()
    return "chain of thought" in lowered or "<thinking" in lowered


__all__ = [
    "LLMRuntimeInputRoutePlanner",
    "RouterPlannerResult",
    "RuntimeInputRoutePlanner",
    "RuntimeInputRouteProposal",
    "validate_route_proposal",
]
