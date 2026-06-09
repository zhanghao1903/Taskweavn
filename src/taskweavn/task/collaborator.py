"""Collaborator authoring service: LLM proposal to authoring commands."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from taskweavn.prompts import COLLABORATOR_AUTHORING_SYSTEM_PROMPT
from taskweavn.task.authoring import (
    ActorRef,
    AuthoringCommandBatch,
    AuthoringCommandError,
    AuthoringCommandResult,
    AuthoringContext,
    DraftTaskNodeProposal,
    DraftTaskPatchProposal,
    DraftTaskTreeOperation,
    DraftTaskTreeProposal,
    FeasibilityReport,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    PlanProposal,
    PlanTaskNodeProposal,
    RawTaskOperation,
)
from taskweavn.task.authoring_context import AuthoringContextBuilder
from taskweavn.task.authoring_service import AuthoringCommandService
from taskweavn.task.collaborator_loop import (
    CollaboratorAuthoringLoopResult,
    CollaboratorAuthoringOperation,
    CollaboratorAuthoringProfile,
    CollaboratorAuthoringProfileRequest,
    CollaboratorProposalKind,
)
from taskweavn.task.collaborator_profile_runner import CollaboratorAuthoringProfileRunner
from taskweavn.task.collaborator_workspace_context import CollaboratorWorkspaceContextSource
from taskweavn.task.models import TaskRef

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_SYSTEM_PROMPT = COLLABORATOR_AUTHORING_SYSTEM_PROMPT
COLLABORATOR_TEMPLATE_ID = "system.collaborator"
COLLABORATOR_CAPABILITY = "task_authoring"
COLLABORATOR_COMMAND_PROTOCOL = "authoring.v1"


class _FrozenCollaboratorModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class RawTaskAskProposal(_FrozenCollaboratorModel):
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required: bool = True
    options: tuple[dict[str, Any], ...] = ()


class RawTaskProposal(_FrozenCollaboratorModel):
    """Structured LLM proposal for RawTask feasibility and clarification."""

    kind: str = "raw_task"
    intent_summary: str = Field(min_length=1)
    feasibility: FeasibilityReport
    asks: tuple[RawTaskAskProposal, ...] = ()
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


class CollaboratorAgentTemplate(_FrozenCollaboratorModel):
    """System template metadata for the built-in Collaborator Agent.

    The template is intentionally metadata-only. It describes the system role
    available in a session, while actual state changes still go through
    CollaboratorAuthoringService and AuthoringCommandService.
    """

    template_id: str = COLLABORATOR_TEMPLATE_ID
    capability: str = COLLABORATOR_CAPABILITY
    display_name: str = "Collaborator"
    description: str = "Helps users turn natural language goals into Plans."
    command_protocol: str = COLLABORATOR_COMMAND_PROTOCOL
    capability_catalog: str = "execution.capabilities.readonly"
    default_autonomy: str = "manual_or_collaborative"
    llm_visible_tool_pools: tuple[str, ...] = ()


@runtime_checkable
class CollaboratorTemplateRegistry(Protocol):
    """Session-scoped registry for built-in Collaborator templates."""

    def register(
        self,
        session_id: str,
        template: CollaboratorAgentTemplate,
    ) -> CollaboratorAgentTemplate: ...

    def get(
        self,
        session_id: str,
        template_id: str = COLLABORATOR_TEMPLATE_ID,
    ) -> CollaboratorAgentTemplate | None: ...

    def list_for_session(self, session_id: str) -> tuple[CollaboratorAgentTemplate, ...]: ...


class InMemoryCollaboratorTemplateRegistry:
    """Process-local template registry used by early API/server tests."""

    def __init__(self) -> None:
        self._templates: dict[tuple[str, str], CollaboratorAgentTemplate] = {}

    def register(
        self,
        session_id: str,
        template: CollaboratorAgentTemplate,
    ) -> CollaboratorAgentTemplate:
        _validate_session_id(session_id)
        key = (session_id, template.template_id)
        current = self._templates.get(key)
        if current is not None and current != template:
            raise ValueError(
                f"collaborator template {template.template_id!r} already registered"
            )
        self._templates[key] = template
        return template

    def get(
        self,
        session_id: str,
        template_id: str = COLLABORATOR_TEMPLATE_ID,
    ) -> CollaboratorAgentTemplate | None:
        _validate_session_id(session_id)
        return self._templates.get((session_id, template_id))

    def list_for_session(self, session_id: str) -> tuple[CollaboratorAgentTemplate, ...]:
        _validate_session_id(session_id)
        templates = [
            template
            for (registered_session_id, _), template in self._templates.items()
            if registered_session_id == session_id
        ]
        return tuple(sorted(templates, key=lambda template: template.template_id))


def default_collaborator_template() -> CollaboratorAgentTemplate:
    """Return the built-in Collaborator template.

    The empty ``llm_visible_tool_pools`` tuple is part of the contract:
    Collaborator plans with read-only capability descriptors, not by mounting
    workspace file/shell tools or low-level system mutation tools.
    """

    return CollaboratorAgentTemplate()


def register_system_collaborator(
    session_id: str,
    registry: CollaboratorTemplateRegistry,
    *,
    template: CollaboratorAgentTemplate | None = None,
) -> CollaboratorAgentTemplate:
    """Register the built-in Collaborator template for one session."""

    return registry.register(session_id, template or default_collaborator_template())


@runtime_checkable
class CollaboratorLLM(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...


@runtime_checkable
class CollaboratorAuthoringService(Protocol):
    """Natural-language authoring entrypoint backed by structured commands."""

    def create_raw_task_from_message(
        self,
        *,
        session_id: str,
        source_message_id: str,
        user_input: str,
        idempotency_key: str | None = None,
    ) -> AuthoringCommandResult: ...

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> AuthoringCommandResult: ...

    def refine_task_node(
        self,
        *,
        session_id: str,
        selected_task_ref: TaskRef,
        instruction: str,
    ) -> AuthoringCommandResult: ...


class DefaultCollaboratorAuthoringService:
    """Default Collaborator service using structured JSON proposals."""

    def __init__(
        self,
        *,
        llm: CollaboratorLLM,
        context_builder: AuthoringContextBuilder,
        command_service: AuthoringCommandService,
        actor: ActorRef | None = None,
        profile: CollaboratorAuthoringProfile | None = None,
        workspace_context_source: CollaboratorWorkspaceContextSource | None = None,
        max_context_steps: int = 3,
    ) -> None:
        self._llm = llm
        self._context_builder = context_builder
        self._command_service = command_service
        self._actor = actor or ActorRef(actor_id="collaborator", kind="collaborator")
        self._profile = profile or CollaboratorAuthoringProfile()
        self._profile_runner = CollaboratorAuthoringProfileRunner(
            llm=self._llm,
            profile=self._profile,
            actor_id=self._actor.actor_id,
            workspace_context_source=workspace_context_source,
            max_context_steps=max_context_steps,
        )

    def create_raw_task_from_message(
        self,
        *,
        session_id: str,
        source_message_id: str,
        user_input: str,
        idempotency_key: str | None = None,
    ) -> AuthoringCommandResult:
        context = self._context_builder.build_session_context(session_id)
        try:
            loop_result = self._run_one_shot(
                operation="create_raw_task",
                proposal_kind="raw_task",
                task="Assess the user input and return a raw_task proposal.",
                session_id=session_id,
                request_purpose="collaborator.create_raw_task",
                payload={
                    "user_input": user_input,
                    "context": _context_payload(context),
                },
                parse_response=_raw_task_payload_from_response,
            )
            proposal = RawTaskProposal.model_validate(
                _finished_proposal(loop_result, expected_kind="raw_task")
            )
            operations = [
                RawTaskOperation(
                    op="create",
                    payload={
                        "source_message_id": source_message_id,
                        "user_input": user_input,
                        "intent_summary": proposal.intent_summary,
                        "constraints": proposal.constraints,
                        "assumptions": proposal.assumptions,
                    },
                ),
                RawTaskOperation(
                    op="record_feasibility",
                    payload={"feasibility": proposal.feasibility.model_dump(mode="json")},
                ),
            ]
            operations.extend(
                RawTaskOperation(
                    op="add_clarification_ask",
                    payload={
                        "question": ask.question,
                        "reason": ask.reason,
                        "required": ask.required,
                        "options": ask.options,
                    },
                )
                for ask in proposal.asks
            )
            command = MutateRawTaskCommand(
                session_id=session_id,
                actor=self._actor,
                idempotency_key=idempotency_key,
                operations=tuple(operations),
            )
            return self._command_service.submit(
                AuthoringCommandBatch(
                    session_id=session_id,
                    actor=self._actor,
                    idempotency_key=idempotency_key,
                    commands=(command,),
                )
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as authoring result
            return _proposal_error("raw_task", exc)

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> AuthoringCommandResult:
        context = self._context_builder.build_session_context(
            session_id,
            raw_task_id=raw_task_id,
        )
        if context.raw_task_id is None:
            return _proposal_error(
                "draft_task_tree",
                ValueError("RawTask is required before generating a draft Plan"),
            )
        try:
            loop_result = self._run_one_shot(
                operation="generate_task_tree",
                proposal_kind="draft_task_tree",
                task="Generate a draft Plan proposal for the selected RawTask.",
                session_id=session_id,
                request_purpose="collaborator.generate_task_tree",
                payload={"context": _context_payload(context)},
                parse_response=_json_from_response,
            )
            proposal = _draft_tree_proposal_from_payload(
                _finished_proposal(loop_result, expected_kind="draft_task_tree")
            )
            command = MutateDraftTaskTreeCommand(
                session_id=session_id,
                raw_task_id=context.raw_task_id,
                actor=self._actor,
                idempotency_key=idempotency_key,
                operations=(
                    DraftTaskTreeOperation(
                        op="create_tree",
                        payload={"roots": _proposal_roots(proposal)},
                    ),
                ),
            )
            return self._command_service.submit(
                AuthoringCommandBatch(
                    session_id=session_id,
                    actor=self._actor,
                    idempotency_key=idempotency_key,
                    commands=(command,),
                )
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as authoring result
            return _proposal_error("draft_task_tree", exc)

    def refine_task_node(
        self,
        *,
        session_id: str,
        selected_task_ref: TaskRef,
        instruction: str,
    ) -> AuthoringCommandResult:
        context = self._context_builder.build_task_context(session_id, selected_task_ref)
        if context.selected_node is None:
            return _proposal_error("draft_task_patch", ValueError("selected node missing"))
        try:
            loop_result = self._run_one_shot(
                operation="refine_task_node",
                proposal_kind="draft_task_patch",
                task="Refine only the selected draft task node using the instruction.",
                session_id=session_id,
                request_purpose="collaborator.refine_task_node",
                payload={
                    "instruction": instruction,
                    "context": _context_payload(context),
                },
                parse_response=_json_from_response,
            )
            proposal = DraftTaskPatchProposal.model_validate(
                _finished_proposal(loop_result, expected_kind="draft_task_patch")
            )
            command = MutateDraftTaskTreeCommand(
                session_id=session_id,
                draft_tree_id=context.selected_node.draft_tree_id,
                actor=self._actor,
                operations=(
                    DraftTaskTreeOperation(
                        op="patch_node",
                        payload={
                            "draft_task_id": selected_task_ref.id,
                            "patch": proposal.patch.model_dump(mode="json"),
                        },
                    ),
                ),
            )
            return self._command_service.submit(
                AuthoringCommandBatch(
                    session_id=session_id,
                    actor=self._actor,
                    commands=(command,),
                )
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as authoring result
            return _proposal_error("draft_task_patch", exc)

    def _run_one_shot(
        self,
        *,
        operation: CollaboratorAuthoringOperation,
        proposal_kind: CollaboratorProposalKind,
        task: str,
        session_id: str,
        request_purpose: str,
        payload: dict[str, Any],
        parse_response: Callable[[str], dict[str, Any]],
    ) -> CollaboratorAuthoringLoopResult:
        request = CollaboratorAuthoringProfileRequest(
            session_id=session_id,
            operation=operation,
            proposal_kind=proposal_kind,
            request_purpose=request_purpose,
            task=task,
            payload=payload,
        )
        return self._profile_runner.run(
            request=request,
            parse_response=parse_response,
        )


def _json_from_response(content: str) -> dict[str, Any]:
    match = _JSON_OBJECT_RE.search(content.strip())
    if match is None:
        raise ValueError("LLM response did not contain a JSON object")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def _raw_task_payload_from_response(content: str) -> dict[str, Any]:
    return _normalize_raw_task_payload(_json_from_response(content))


def _finished_proposal(
    result: CollaboratorAuthoringLoopResult,
    *,
    expected_kind: CollaboratorProposalKind,
) -> dict[str, Any]:
    if result.status != "finished":
        reason = f": {result.reason}" if result.reason else ""
        raise ValueError(f"Collaborator loop did not finish: {result.status}{reason}")
    if result.proposal_kind != expected_kind:
        raise ValueError(
            f"Collaborator loop returned {result.proposal_kind}, expected {expected_kind}"
        )
    if result.proposal is None:
        raise ValueError("Collaborator loop finished without a proposal")
    return result.proposal


def _normalize_raw_task_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept common LLM wrapper shapes while preserving strict domain input.

    Real models often return ``{"raw_task": {...}}`` and include generated ids
    or timestamps. Authoring commands own those fields, so the collaborator
    parser should discard them instead of rejecting an otherwise valid proposal.
    """

    raw_task = payload.get("raw_task")
    secondary = raw_task if isinstance(raw_task, dict) else payload

    normalized: dict[str, Any] = {"kind": payload.get("kind", "raw_task")}
    intent_summary = _first_present(
        payload,
        secondary,
        keys=(
            "intent_summary",
            "summary",
            "title",
            "task_title",
            "goal",
            "description",
            "user_goal",
        ),
    )
    if intent_summary is not None:
        normalized["intent_summary"] = intent_summary

    asks = _normalize_raw_task_asks(
        _first_present(payload, secondary, keys=("asks", "questions", "clarifications"))
    )

    feasibility = _first_present(
        payload,
        secondary,
        keys=("feasibility", "feasibility_report", "assessment"),
    )
    if feasibility is not None:
        normalized["feasibility"] = _normalize_feasibility(feasibility, asks=asks)

    if asks:
        normalized["asks"] = asks

    for key in ("constraints", "assumptions"):
        value = _first_present(payload, secondary, keys=(key,))
        if value is not None:
            normalized[key] = _normalize_text_sequence(value)

    return normalized


def _normalize_feasibility(
    value: Any,
    *,
    asks: tuple[dict[str, Any], ...],
) -> Any:
    if isinstance(value, str):
        status = _feasibility_status_from_text(value)
        report: dict[str, Any] = {
            "status": status,
            "confidence": _default_confidence(status),
            "reasons": (value,),
        }
        if status in {"needs_clarification", "needs_user_permission"}:
            report["missing_inputs"] = _ask_questions(asks) or (value,)
        return report
    if not isinstance(value, dict):
        return value

    normalized = dict(value)
    raw_status: Any = normalized.get("status")
    if isinstance(raw_status, str):
        normalized["status"] = _feasibility_status_from_text(raw_status)
    status_value: Any = normalized.get("status")
    if isinstance(status_value, str) and "confidence" not in normalized:
        normalized["confidence"] = _default_confidence(status_value)
    if (
        status_value in {"needs_clarification", "needs_user_permission"}
        and not normalized.get("missing_inputs")
        and not normalized.get("required_permissions")
    ):
        normalized["missing_inputs"] = _ask_questions(asks)
    return normalized


def _feasibility_status_from_text(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    ready = {"feasible", "ready", "yes", "can_do", "supported", "可行", "可以"}
    partial = {"partially_feasible", "partial", "partly_feasible", "部分可行"}
    clarification = {
        "needs_clarification",
        "need_clarification",
        "clarification",
        "needs_more_info",
        "need_more_info",
        "unclear",
        "需要澄清",
        "需要补充信息",
    }
    permission = {
        "needs_user_permission",
        "need_user_permission",
        "permission_required",
        "requires_permission",
        "需要授权",
    }
    unsupported = {
        "not_supported",
        "unsupported",
        "infeasible",
        "unfeasible",
        "not_feasible",
        "不可行",
        "不支持",
    }
    unsafe = {"unsafe", "dangerous", "risk", "不安全"}
    if normalized in ready:
        return "ready"
    if normalized in partial:
        return "partially_feasible"
    if normalized in clarification:
        return "needs_clarification"
    if normalized in permission:
        return "needs_user_permission"
    if normalized in unsupported:
        return "not_supported"
    if normalized in unsafe:
        return "unsafe"
    if "clarification" in normalized or "more_info" in normalized:
        return "needs_clarification"
    if "permission" in normalized:
        return "needs_user_permission"
    if "unsafe" in normalized or "danger" in normalized:
        return "unsafe"
    if "unsupported" in normalized or "not_feasible" in normalized:
        return "not_supported"
    return "ready"


def _default_confidence(status: str) -> float:
    if status == "ready":
        return 0.8
    if status == "partially_feasible":
        return 0.6
    if status in {"needs_clarification", "needs_user_permission"}:
        return 0.5
    return 0.7


def _normalize_raw_task_asks(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_ask_from_text(value),)
    if isinstance(value, dict):
        return (_normalize_raw_task_ask_dict(value),)
    if not isinstance(value, (list, tuple)):
        return ()

    asks: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            asks.append(_ask_from_text(item))
        elif isinstance(item, dict):
            asks.append(_normalize_raw_task_ask_dict(item))
    return tuple(asks)


def _normalize_raw_task_ask_dict(value: dict[str, Any]) -> dict[str, Any]:
    ask = dict(value)
    question = ask.get("question") or ask.get("content") or ask.get("text")
    if question is not None:
        ask["question"] = question
    ask.setdefault("reason", "Clarify the user's intended task.")
    if "options" in ask:
        ask["options"] = _normalize_answer_options(ask["options"])
    return ask


def _ask_from_text(value: str) -> dict[str, Any]:
    return {
        "question": value,
        "reason": "Clarify the user's intended task.",
        "required": True,
    }


def _normalize_answer_options(value: Any) -> Any:
    if isinstance(value, str):
        return ({"label": value, "value": value},)
    if not isinstance(value, (list, tuple)):
        return value
    options: list[Any] = []
    for option in value:
        if isinstance(option, str):
            options.append({"label": option, "value": option})
        else:
            options.append(option)
    return tuple(options)


def _normalize_text_sequence(value: Any) -> Any:
    if isinstance(value, str):
        return (value,)
    return value


def _ask_questions(asks: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    return tuple(
        question
        for ask in asks
        if isinstance((question := ask.get("question")), str) and question.strip()
    )


def _first_present(
    primary: dict[str, Any],
    secondary: dict[str, Any],
    *,
    keys: tuple[str, ...],
) -> Any | None:
    for source in (primary, secondary):
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
    return None


def _proposal_error(kind: str, exc: Exception) -> AuthoringCommandResult:
    code = "invalid_llm_proposal"
    if isinstance(exc, json.JSONDecodeError):
        message = f"{kind} proposal is not valid JSON: {exc.msg}"
    elif isinstance(exc, ValidationError):
        message = f"{kind} proposal failed validation: {exc}"
    else:
        message = f"{kind} proposal failed: {exc}"
    return AuthoringCommandResult(
        ok=False,
        errors=(AuthoringCommandError(code=code, message=message),),
    )


def _context_payload(context: AuthoringContext) -> dict[str, Any]:
    payload = context.model_dump(mode="json")
    if not isinstance(payload, dict):
        raise TypeError("AuthoringContext JSON dump must be an object")
    return payload


def _proposal_roots(proposal: DraftTaskTreeProposal) -> list[dict[str, Any]]:
    return [_proposal_node(root) for root in proposal.roots]


def _draft_tree_proposal_from_payload(payload: object) -> DraftTaskTreeProposal:
    if isinstance(payload, dict) and (
        payload.get("schema_version") == "plato.plan.proposal.v1"
        or "tasks" in payload
    ):
        return _draft_tree_from_plan_proposal(PlanProposal.model_validate(payload))
    return _flatten_draft_task_tree_proposal(DraftTaskTreeProposal.model_validate(payload))


def _draft_tree_from_plan_proposal(proposal: PlanProposal) -> DraftTaskTreeProposal:
    indexed = tuple(enumerate(proposal.tasks, start=1))
    ordered = sorted(
        indexed,
        key=lambda item: (item[1].task_index if item[1].task_index is not None else item[0]),
    )
    return DraftTaskTreeProposal(
        roots=tuple(_draft_node_from_plan_task(task) for _, task in ordered),
        assistant_message=proposal.assistant_message,
    )


def _draft_node_from_plan_task(task: PlanTaskNodeProposal) -> DraftTaskNodeProposal:
    intent_parts = [task.intent]
    if task.summary is not None and task.summary.strip() != task.intent.strip():
        intent_parts.append(f"Summary: {task.summary}")
    if task.instructions is not None:
        intent_parts.append(f"Instructions: {task.instructions}")
    if task.acceptance_criteria:
        intent_parts.append(
            "Acceptance criteria: " + "; ".join(task.acceptance_criteria)
        )
    constraints = list(task.constraints)
    if task.depends_on:
        constraints.append("Depends on: " + ", ".join(task.depends_on))
    return DraftTaskNodeProposal(
        title=task.title,
        intent="\n".join(intent_parts),
        required_capability=task.required_capability,
        constraints=tuple(constraints),
        rationale=task.rationale,
    )


def _flatten_draft_task_tree_proposal(
    proposal: DraftTaskTreeProposal,
) -> DraftTaskTreeProposal:
    flat: list[DraftTaskNodeProposal] = []

    def visit(
        node: DraftTaskNodeProposal,
        ancestors: tuple[DraftTaskNodeProposal, ...],
    ) -> None:
        flat.append(_flat_draft_node(node, ancestors))
        for child in node.children:
            visit(child, (*ancestors, node))

    for root in proposal.roots:
        visit(root, ())
    return DraftTaskTreeProposal(
        roots=tuple(flat),
        assistant_message=proposal.assistant_message,
    )


def _flat_draft_node(
    node: DraftTaskNodeProposal,
    ancestors: tuple[DraftTaskNodeProposal, ...],
) -> DraftTaskNodeProposal:
    intent = node.intent
    if ancestors:
        ancestor_path = " > ".join(ancestor.title for ancestor in ancestors)
        intent = f"{intent}\nContext: originally grouped under {ancestor_path}."
    return DraftTaskNodeProposal(
        title=node.title,
        intent=intent,
        required_capability=node.required_capability,
        constraints=node.constraints,
        rationale=node.rationale,
    )


def _proposal_node(node: Any) -> dict[str, Any]:
    return {
        "title": node.title,
        "intent": node.intent,
        "required_capability": node.required_capability,
        "constraints": list(node.constraints),
        "rationale": node.rationale,
        "children": [_proposal_node(child) for child in node.children],
    }


def _validate_session_id(session_id: str) -> None:
    if not session_id.strip():
        raise ValueError("session_id must not be blank")
