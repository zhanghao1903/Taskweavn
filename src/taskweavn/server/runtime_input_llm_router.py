"""LLM-assisted planner for Runtime Input Router decisions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from taskweavn.llm.contracts import ChatResponse
from taskweavn.llm.logging import log_agent_llm_input, log_agent_llm_output
from taskweavn.observability import LogContext, get_object_logger
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
from taskweavn.skills.registry import SkillRegistry, SkillRegistryConfig, SkillRootConfig

RouterPlannerStatus = Literal["planned", "unavailable", "invalid"]
RouterCommandKind = Literal[
    "stop_task",
    "retry_task",
    "resume_task",
    "cancel_task",
    "record_guidance",
    "patch_task_node",
    "create_task_node",
    "delete_task_node",
]
RouterTaskRiskLevel = Literal["low", "medium", "high"]
RouterConfirmationResolution = Literal["confirmed", "rejected"]
RouterReadOnlyContextKind = Literal["session_summary", "task_detail", "file", "diff"]
_WECHAT_SEND_TASK_TYPE = "communication.wechat.send_message"
_WECHAT_SEND_CAPABILITY = "communication.wechat_desktop_send"
_RUNTIME_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "runtime_skills"
_ENABLED_COMMAND_DRAFT_KINDS = {"stop_task", "retry_task"}
_WECHAT_BULK_MARKERS = ("、", "，", ",", "和", "及", "以及")
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


class RouterCommandDraft(UiContractModel):
    command_kind: RouterCommandKind
    target_scope_kind: RuntimeInputScopeKind
    target_task_node_id: str | None = Field(default=None, min_length=1)
    target_plan_id: str | None = Field(default=None, min_length=1)
    rationale: str = Field(min_length=1, max_length=1200)

    @field_validator("rationale")
    @classmethod
    def _safe_rationale(cls, value: str) -> str:
        return _safe_text(value)


class RouterTaskPolicyDraft(UiContractModel):
    required_capability: str = Field(min_length=1)
    requires_human_confirmation: bool = False
    risk_level: RouterTaskRiskLevel = "medium"


class RouterTaskRequestDraft(UiContractModel):
    task_type: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_.:-]+$")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=4000)
    input: dict[str, Any] = Field(default_factory=dict)
    policy: RouterTaskPolicyDraft
    capability: str | None = Field(default=None, min_length=1)

    @field_validator("instructions")
    @classmethod
    def _safe_instructions(cls, value: str) -> str:
        return _safe_text(value)


class RouterAskAnswerDraft(UiContractModel):
    ask_id: str | None = Field(default=None, min_length=1)
    answer_text: str = Field(min_length=1, max_length=4000)

    @field_validator("answer_text")
    @classmethod
    def _safe_answer_text(cls, value: str) -> str:
        return _safe_text(value)


class RouterConfirmationResponseDraft(UiContractModel):
    confirmation_id: str | None = Field(default=None, min_length=1)
    resolution: RouterConfirmationResolution
    rationale: str | None = Field(default=None, min_length=1, max_length=1200)

    @field_validator("rationale")
    @classmethod
    def _safe_optional_rationale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value)


class RouterReadOnlyContextRequest(UiContractModel):
    context_kind: RouterReadOnlyContextKind
    query: str = Field(min_length=1, max_length=1200)
    refs: tuple[ReadOnlyInquiryRef, ...] = ()

    @field_validator("query")
    @classmethod
    def _safe_query(cls, value: str) -> str:
        return _safe_text(value)


class RouterSkillPromptSegment(UiContractModel):
    skill_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    output_contract: str | None = Field(default=None, min_length=1)
    instruction_excerpt: str | None = Field(default=None, min_length=1)
    truncated: bool = False


class RouterSkillPromptContext(UiContractModel):
    segments: tuple[RouterSkillPromptSegment, ...] = ()
    source: Literal["builtin_runtime_skills", "explicit"] = "explicit"
    max_instruction_chars: int = Field(default=2400, ge=0)

    @property
    def activated_skill_ids(self) -> tuple[str, ...]:
        return tuple(segment.skill_id for segment in self.segments)

    def to_prompt_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "skillId": segment.skill_id,
                "name": segment.name,
                "description": segment.description,
                "contentHash": segment.content_hash,
                "outputContract": segment.output_contract,
                "instructionExcerpt": segment.instruction_excerpt,
                "truncated": segment.truncated,
            }
            for segment in self.segments
        ]


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
    route_source: Literal["llm_planner"] = "llm_planner"
    activated_skill_ids: tuple[str, ...] = ()
    command_draft: RouterCommandDraft | None = None
    task_request_draft: RouterTaskRequestDraft | None = None
    ask_answer_draft: RouterAskAnswerDraft | None = None
    confirmation_response_draft: RouterConfirmationResponseDraft | None = None
    requested_read_only_context: RouterReadOnlyContextRequest | None = None

    @field_validator("visible_reasoning_summary", "user_message")
    @classmethod
    def _safe_summary(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("activated_skill_ids")
    @classmethod
    def _safe_skill_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value)
        if any(not item for item in cleaned):
            raise ValueError("activatedSkillIds must not contain blank ids")
        return cleaned

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
    skill_prompt_context: RouterSkillPromptContext = field(
        default_factory=lambda: build_builtin_router_skill_prompt_context()
    )

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
            skill_prompt_context=self.skill_prompt_context,
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
        _log_router_request(
            request,
            allowed_dispatch_targets=allowed_dispatch_targets,
            active_ask=active_ask,
            active_confirmation=active_confirmation,
            context=log_context,
        )
        _log_router_config(
            timeout_seconds=self.timeout_seconds,
            context=log_context,
        )
        _log_router_skills(self.skill_prompt_context, context=log_context)
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
            _log_router_proposal(proposal, context=log_context)
            warning = validate_route_proposal(
                proposal,
                allowed_dispatch_targets=allowed_dispatch_targets,
                active_ask=active_ask,
                active_confirmation=active_confirmation,
            )
            if warning is not None:
                _log_router_validation(
                    status="invalid",
                    warning=warning,
                    context=log_context,
                )
                return RouterPlannerResult(status="invalid", warning=warning)
            _log_router_validation(
                status="valid",
                warning=None,
                context=log_context,
            )
            return RouterPlannerResult(status="planned", proposal=proposal)
        except Exception as exc:  # noqa: BLE001 - Router must fail closed.
            _log_router_fallback(
                reason="planner_unavailable",
                warning=f"{type(exc).__name__}",
                context=log_context,
            )
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
    if (
        proposal.dispatch_target != "read_only_inquiry"
        and proposal.requested_read_only_context is not None
    ):
        return "read-only context requests are only allowed for read_only_inquiry"
    if proposal.dispatch_target != "existing_command" and proposal.command_draft is not None:
        return "command draft is only allowed for existing_command"
    if proposal.dispatch_target == "existing_command":
        warning = _validate_command_draft(proposal.command_draft)
        if warning is not None:
            return warning
    if (
        proposal.dispatch_target != "execution_handoff"
        and proposal.task_request_draft is not None
    ):
        return "task request draft is only allowed for execution_handoff"
    if proposal.dispatch_target == "execution_handoff":
        warning = _validate_task_request_draft(proposal.task_request_draft)
        if warning is not None:
            return warning
    if proposal.dispatch_target != "resolve_ask" and proposal.ask_answer_draft is not None:
        return "ASK answer draft is only allowed for resolve_ask"
    if proposal.dispatch_target == "resolve_ask" and proposal.ask_answer_draft is None:
        return "resolve_ask requires ASK answer draft"
    if (
        proposal.dispatch_target != "resolve_confirmation"
        and proposal.confirmation_response_draft is not None
    ):
        return "confirmation response draft is only allowed for resolve_confirmation"
    if (
        proposal.dispatch_target == "resolve_confirmation"
        and proposal.confirmation_response_draft is None
    ):
        return "resolve_confirmation requires confirmation response draft"
    return None


def build_builtin_router_skill_prompt_context(
    *,
    max_instruction_chars: int = 2400,
    root_path: Path | None = None,
) -> RouterSkillPromptContext:
    root = root_path or _RUNTIME_SKILLS_ROOT
    registry = SkillRegistry.scan(
        SkillRegistryConfig(
            roots=(
                SkillRootConfig(
                    root_path=root,
                    source_scope="internal",
                    trust_level="trusted",
                ),
            ),
        )
    )
    segments: list[RouterSkillPromptSegment] = []
    for descriptor in registry.list_descriptors():
        if "runtime_input_router" not in descriptor.context_requirements:
            continue
        excerpt, truncated = _skill_excerpt(
            Path(descriptor.skill_file_path) if descriptor.skill_file_path else None,
            max_instruction_chars=max_instruction_chars,
        )
        segments.append(
            RouterSkillPromptSegment(
                skill_id=descriptor.skill_id,
                name=descriptor.name,
                description=descriptor.description,
                content_hash=descriptor.content_hash,
                output_contract=descriptor.output_contract,
                instruction_excerpt=excerpt or None,
                truncated=truncated,
            )
        )
    return RouterSkillPromptContext(
        segments=tuple(segments),
        source="builtin_runtime_skills",
        max_instruction_chars=max_instruction_chars,
    )


def _validate_command_draft(command_draft: RouterCommandDraft | None) -> str | None:
    if command_draft is None:
        return "existing_command requires command draft"
    if command_draft.command_kind not in _ENABLED_COMMAND_DRAFT_KINDS:
        return f"command draft kind {command_draft.command_kind!r} is not enabled"
    if command_draft.target_scope_kind == "task" and command_draft.target_task_node_id is None:
        return "task-scoped command draft requires target task node id"
    if command_draft.target_scope_kind == "plan" and command_draft.target_plan_id is None:
        return "plan-scoped command draft requires target plan id"
    return None


def _validate_task_request_draft(
    task_request_draft: RouterTaskRequestDraft | None,
) -> str | None:
    if task_request_draft is None:
        return "execution_handoff requires task request draft"
    if task_request_draft.task_type == _WECHAT_SEND_TASK_TYPE:
        return _validate_wechat_task_request_draft(task_request_draft)
    return None


def _validate_wechat_task_request_draft(
    task_request_draft: RouterTaskRequestDraft,
) -> str | None:
    contact = task_request_draft.input.get("contactDisplayName")
    if not isinstance(contact, str) or not contact.strip():
        return "WeChat send task draft requires contactDisplayName"
    message = task_request_draft.input.get("messageText")
    if not isinstance(message, str) or not message.strip():
        return "WeChat send task draft requires messageText"
    if any(marker in contact for marker in _WECHAT_BULK_MARKERS):
        return "WeChat send task draft must target one contact"
    policy = task_request_draft.policy
    if policy.required_capability != _WECHAT_SEND_CAPABILITY:
        return "WeChat send task draft requires communication.wechat_desktop_send capability"
    if not policy.requires_human_confirmation:
        return "WeChat send task draft requires human confirmation"
    if policy.risk_level != "high":
        return "WeChat send task draft must be high risk"
    return None


def _messages(
    request: RuntimeInputRouteRequest,
    *,
    allowed_dispatch_targets: tuple[RuntimeInputDispatchTarget, ...],
    active_ask: bool,
    active_confirmation: bool,
    skill_prompt_context: RouterSkillPromptContext,
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
        "routerSkills": skill_prompt_context.to_prompt_payload(),
        "outputSchema": {
            "format": "json_object",
            "readOnlyRefs": "optional refs with kind=file or diff and safe workspace-relative path",
            "taskRequestDraft": (
                "required for execution_handoff; WeChat sends must include "
                "taskType=communication.wechat.send_message, input.contactDisplayName, "
                "input.messageText, policy.requiredCapability="
                "communication.wechat_desktop_send, "
                "policy.requiresHumanConfirmation=true, policy.riskLevel=high"
            ),
            "commandDraft": (
                "required for existing_command; enabled kinds: stop_task, retry_task"
            ),
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You are Plato's Runtime Input Router planner. Return only JSON. "
                "Use the routerSkills payload as capability semantics and examples. "
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


def _log_router_request(
    request: RuntimeInputRouteRequest,
    *,
    allowed_dispatch_targets: tuple[RuntimeInputDispatchTarget, ...],
    active_ask: bool,
    active_confirmation: bool,
    context: LogContext,
) -> None:
    get_object_logger("runtime").info(
        "runtime_input_router_request",
        message="runtime input router request",
        context=context,
        data={
            "session_id": request.session_id,
            "workspace_id": request.workspace_id,
            "scope_kind": request.selection.scope_kind,
            "mode": request.mode,
            "content_length": len(request.content),
            "content_sha256_12": _short_hash(request.content),
            "allowed_dispatch_targets": allowed_dispatch_targets,
            "active_ask": active_ask,
            "active_confirmation": active_confirmation,
        },
    )


def _log_router_config(
    *,
    timeout_seconds: float | None,
    context: LogContext,
) -> None:
    get_object_logger("runtime").info(
        "runtime_input_router_config",
        message="runtime input router config",
        context=context,
        data={
            "router_mode": "llm_planner",
            "config_scope": "app/global",
            "source": "app_settings",
            "planner_timeout_seconds": timeout_seconds,
        },
    )


def _log_router_skills(
    skill_prompt_context: RouterSkillPromptContext,
    *,
    context: LogContext,
) -> None:
    get_object_logger("runtime").info(
        "runtime_input_router_skills",
        message="runtime input router skills",
        context=context,
        data={
            "source": skill_prompt_context.source,
            "activated_skill_ids": skill_prompt_context.activated_skill_ids,
            "skill_count": len(skill_prompt_context.segments),
            "max_instruction_chars": skill_prompt_context.max_instruction_chars,
            "skills": [
                {
                    "skill_id": segment.skill_id,
                    "content_hash": segment.content_hash,
                    "truncated": segment.truncated,
                }
                for segment in skill_prompt_context.segments
            ],
        },
    )


def _log_router_proposal(
    proposal: RuntimeInputRouteProposal,
    *,
    context: LogContext,
) -> None:
    get_object_logger("runtime").info(
        "runtime_input_router_proposal",
        message="runtime input router proposal",
        context=context,
        data={
            "route_source": proposal.route_source,
            "activated_skill_ids": proposal.activated_skill_ids,
            "intent": proposal.intent,
            "dispatch_target": proposal.dispatch_target,
            "side_effect": proposal.side_effect,
            "confidence": proposal.confidence,
            "needs_clarification": proposal.needs_clarification,
            "has_task_request_draft": proposal.task_request_draft is not None,
            "task_type": (
                None
                if proposal.task_request_draft is None
                else proposal.task_request_draft.task_type
            ),
            "requires_confirmation": _proposal_requires_confirmation(proposal),
        },
    )


def _log_router_validation(
    *,
    status: Literal["valid", "invalid"],
    warning: str | None,
    context: LogContext,
) -> None:
    get_object_logger("runtime").info(
        "runtime_input_router_validation",
        message="runtime input router validation",
        context=context,
        data={
            "status": status,
            "warning": warning,
        },
    )


def _log_router_fallback(
    *,
    reason: str,
    warning: str,
    context: LogContext,
) -> None:
    get_object_logger("runtime").warning(
        "runtime_input_router_fallback",
        message="runtime input router fallback",
        context=context,
        data={
            "reason": reason,
            "warning": warning,
        },
    )


def _proposal_requires_confirmation(proposal: RuntimeInputRouteProposal) -> bool | None:
    if proposal.task_request_draft is None:
        return None
    return proposal.task_request_draft.policy.requires_human_confirmation


def _skill_excerpt(
    skill_file: Path | None,
    *,
    max_instruction_chars: int,
) -> tuple[str, bool]:
    if skill_file is None or not skill_file.exists() or not skill_file.is_file():
        return "", False
    raw = skill_file.read_text(encoding="utf-8")
    body = _strip_frontmatter(raw).strip()
    return _truncate_text(body, max_instruction_chars)


def _strip_frontmatter(raw: str) -> str:
    if not raw.startswith("---\n"):
        return raw
    end = raw.find("\n---", 4)
    if end == -1:
        return raw
    return raw[end + 4 :].lstrip("\n")


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return "", bool(text)
    if len(text) <= max_chars:
        return text, False
    suffix = "\n[truncated by router skill budget]"
    return text[: max(0, max_chars - len(suffix))].rstrip() + suffix, True


def _short_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:12]


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


def _safe_text(value: str) -> str:
    stripped = " ".join(value.strip().split())
    if _looks_like_hidden_reasoning(stripped):
        raise ValueError("hidden reasoning is not allowed")
    return stripped


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
    "RouterAskAnswerDraft",
    "RouterCommandDraft",
    "RouterConfirmationResponseDraft",
    "RouterPlannerResult",
    "RouterReadOnlyContextRequest",
    "RouterSkillPromptContext",
    "RouterSkillPromptSegment",
    "RouterTaskPolicyDraft",
    "RouterTaskRequestDraft",
    "RuntimeInputRoutePlanner",
    "RuntimeInputRouteProposal",
    "build_builtin_router_skill_prompt_context",
    "validate_route_proposal",
]
