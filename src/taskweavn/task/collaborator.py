"""Collaborator authoring service: LLM proposal to authoring commands."""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from taskweavn.task.authoring import (
    ActorRef,
    AuthoringCommandBatch,
    AuthoringCommandError,
    AuthoringCommandResult,
    AuthoringContext,
    DraftTaskPatchProposal,
    DraftTaskTreeOperation,
    DraftTaskTreeProposal,
    FeasibilityReport,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    RawTaskOperation,
)
from taskweavn.task.authoring_context import AuthoringContextBuilder
from taskweavn.task.authoring_service import AuthoringCommandService
from taskweavn.task.models import TaskRef

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_SYSTEM_PROMPT = """You are TaskWeavn's Collaborator Agent.
Return JSON only. Convert user intent into the requested authoring proposal.
Use only capability ids provided in context. Do not emit workspace file edits.
"""
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
    description: str = "Helps users turn natural language goals into Task Trees."
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
    ) -> AuthoringCommandResult: ...

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str,
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
    ) -> None:
        self._llm = llm
        self._context_builder = context_builder
        self._command_service = command_service
        self._actor = actor or ActorRef(actor_id="collaborator", kind="collaborator")

    def create_raw_task_from_message(
        self,
        *,
        session_id: str,
        source_message_id: str,
        user_input: str,
    ) -> AuthoringCommandResult:
        context = self._context_builder.build_session_context(session_id)
        response = self._chat(
            task="Assess the user input and return a raw_task proposal.",
            payload={
                "user_input": user_input,
                "context": _context_payload(context),
            },
        )
        try:
            proposal = RawTaskProposal.model_validate(_json_from_response(response))
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
                operations=tuple(operations),
            )
            return self._command_service.submit(
                AuthoringCommandBatch(
                    session_id=session_id,
                    actor=self._actor,
                    commands=(command,),
                )
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as authoring result
            return _proposal_error("raw_task", exc)

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str,
    ) -> AuthoringCommandResult:
        context = self._context_builder.build_session_context(
            session_id,
            raw_task_id=raw_task_id,
        )
        response = self._chat(
            task="Generate a draft task tree proposal for the selected RawTask.",
            payload={"context": _context_payload(context)},
        )
        try:
            proposal = DraftTaskTreeProposal.model_validate(_json_from_response(response))
            command = MutateDraftTaskTreeCommand(
                session_id=session_id,
                raw_task_id=raw_task_id,
                actor=self._actor,
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
        response = self._chat(
            task="Refine only the selected draft task node using the instruction.",
            payload={
                "instruction": instruction,
                "context": _context_payload(context),
            },
        )
        try:
            proposal = DraftTaskPatchProposal.model_validate(_json_from_response(response))
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

    def _chat(self, *, task: str, payload: dict[str, Any]) -> str:
        response = self._llm.chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"task": task, **payload},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            tools=None,
            metadata={"component": "collaborator_authoring"},
        )
        content = response.content
        if not isinstance(content, str):
            raise TypeError("LLM response content must be a string")
        return content


def _json_from_response(content: str) -> dict[str, Any]:
    match = _JSON_OBJECT_RE.search(content.strip())
    if match is None:
        raise ValueError("LLM response did not contain a JSON object")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


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
