"""Collaborator authoring loop contract models and one-shot profile seam."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.core.loop_profile import LoopTerminalAction
from taskweavn.prompts import COLLABORATOR_AUTHORING_SYSTEM_PROMPT

AUTHORING_READ_WORKSPACE_TOOL_NAME: Literal["authoring_read_workspace"] = (
    "authoring_read_workspace"
)
AUTHORING_SEARCH_WORKSPACE_TOOL_NAME: Literal["authoring_search_workspace"] = (
    "authoring_search_workspace"
)
ASK_AUTHORING_TOOL_NAME: Literal["ask_authoring"] = "ask_authoring"
COLLABORATOR_AUTHORING_PROFILE_ID: Literal["collaborator_authoring"] = (
    "collaborator_authoring"
)
FINISH_AUTHORING_TOOL_NAME: Literal["finish_authoring"] = "finish_authoring"

COLLABORATOR_AUTHORING_ALLOWED_TOOL_NAMES: tuple[str, ...] = (
    AUTHORING_READ_WORKSPACE_TOOL_NAME,
    AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
    ASK_AUTHORING_TOOL_NAME,
    FINISH_AUTHORING_TOOL_NAME,
)
COLLABORATOR_AUTHORING_FORBIDDEN_TOOL_NAMES: tuple[str, ...] = (
    "write_file",
    "run_command",
    "shell",
    "execute_code",
)

CollaboratorAuthoringLoopState = Literal[
    "running",
    "reading_context",
    "waiting_for_context",
    "finished",
    "rejected",
]
CollaboratorAuthoringLoopStatus = Literal[
    "finished",
    "waiting_for_context",
    "rejected",
]
CollaboratorAuthoringOperation = Literal[
    "create_raw_task",
    "generate_task_tree",
    "refine_task_node",
]
CollaboratorContextRequestKind = Literal[
    "workspace_selection",
    "permission",
    "context_source_unavailable",
]
CollaboratorProposalKind = Literal[
    "raw_task",
    "draft_task_tree",
    "draft_task_patch",
]
CollaboratorAskKind = Literal[
    "clarification",
    "permission",
]

_WORKSPACE_LABEL_PREFIX = "workspace://current"


def _new_id() -> str:
    return uuid4().hex


class _FrozenCollaboratorLoopModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class CollaboratorContextRequest(_FrozenCollaboratorLoopModel):
    """Context request returned when Collaborator cannot proceed safely."""

    request_id: str = Field(default_factory=_new_id, min_length=1)
    kind: CollaboratorContextRequestKind
    reason: str = Field(min_length=1)
    requested_path_labels: tuple[str, ...] = ()
    candidate_path_labels: tuple[str, ...] = ()
    required: bool = True

    @model_validator(mode="after")
    def _validate_path_labels(self) -> CollaboratorContextRequest:
        _validate_workspace_labels(self.requested_path_labels)
        _validate_workspace_labels(self.candidate_path_labels)
        return self


class CollaboratorAuthoringProfileRequest(_FrozenCollaboratorLoopModel):
    """One Collaborator authoring request passed through the profile seam."""

    session_id: str = Field(min_length=1)
    operation: CollaboratorAuthoringOperation
    proposal_kind: CollaboratorProposalKind
    request_purpose: str = Field(min_length=1)
    task: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class CollaboratorAuthoringLoopResult(_FrozenCollaboratorLoopModel):
    """Terminal result surface for the Collaborator authoring profile."""

    status: CollaboratorAuthoringLoopStatus
    proposal_kind: CollaboratorProposalKind | None = None
    proposal: dict[str, Any] | None = None
    evidence_refs: tuple[str, ...] = ()
    authoring_command_result_ref: str | None = Field(default=None, min_length=1)
    reason: str | None = Field(default=None, min_length=1)
    requested_context: CollaboratorContextRequest | None = None
    candidate_evidence_refs: tuple[str, ...] = ()
    error_ref: str | None = Field(default=None, min_length=1)

    @classmethod
    def finished_result(
        cls,
        *,
        proposal_kind: CollaboratorProposalKind,
        proposal: dict[str, Any],
        evidence_refs: tuple[str, ...] = (),
        authoring_command_result_ref: str | None = None,
    ) -> CollaboratorAuthoringLoopResult:
        return cls(
            status="finished",
            proposal_kind=proposal_kind,
            proposal=proposal,
            evidence_refs=evidence_refs,
            authoring_command_result_ref=authoring_command_result_ref,
        )

    @classmethod
    def waiting_for_context(
        cls,
        *,
        reason: str,
        requested_context: CollaboratorContextRequest,
        candidate_evidence_refs: tuple[str, ...] = (),
    ) -> CollaboratorAuthoringLoopResult:
        return cls(
            status="waiting_for_context",
            reason=reason,
            requested_context=requested_context,
            candidate_evidence_refs=candidate_evidence_refs,
        )

    @classmethod
    def rejected_result(
        cls,
        *,
        reason: str,
        error_ref: str | None = None,
        evidence_refs: tuple[str, ...] = (),
    ) -> CollaboratorAuthoringLoopResult:
        return cls(
            status="rejected",
            reason=reason,
            error_ref=error_ref,
            evidence_refs=evidence_refs,
        )

    @model_validator(mode="after")
    def _validate_status_payload(self) -> CollaboratorAuthoringLoopResult:
        if self.status == "finished":
            if self.proposal_kind is None or self.proposal is None:
                raise ValueError("finished result requires proposal_kind and proposal")
            if self.requested_context is not None:
                raise ValueError("finished result must not include requested_context")
            if self.candidate_evidence_refs:
                raise ValueError("finished result must not include candidate_evidence_refs")
        elif self.status == "waiting_for_context":
            if self.reason is None or self.requested_context is None:
                raise ValueError(
                    "waiting_for_context result requires reason and requested_context"
                )
            if self.proposal_kind is not None or self.proposal is not None:
                raise ValueError("waiting_for_context result must not include proposal")
            if self.authoring_command_result_ref is not None:
                raise ValueError(
                    "waiting_for_context result must not include command result ref"
                )
        elif self.status == "rejected":
            if self.reason is None:
                raise ValueError("rejected result requires reason")
            if self.proposal_kind is not None or self.proposal is not None:
                raise ValueError("rejected result must not include proposal")
            if self.requested_context is not None:
                raise ValueError("rejected result must not include requested_context")
        return self


@dataclass
class CollaboratorAuthoringProfile:
    """One-shot Collaborator profile over the shared loop profile seam.

    Slice C defines read/search/ask/finish as the profile boundary. The bounded
    runner decides whether to expose the context tools for a concrete request.
    """

    system_prompt: str = COLLABORATOR_AUTHORING_SYSTEM_PROMPT
    profile_id: str = COLLABORATOR_AUTHORING_PROFILE_ID
    terminal_tool_name: str = FINISH_AUTHORING_TOOL_NAME
    terminal_tool_names: tuple[str, ...] = (
        ASK_AUTHORING_TOOL_NAME,
        FINISH_AUTHORING_TOOL_NAME,
    )
    allowed_tool_names: tuple[str, ...] = COLLABORATOR_AUTHORING_ALLOWED_TOOL_NAMES

    def build_initial_messages(self, request: object) -> list[dict[str, Any]]:
        if not isinstance(request, CollaboratorAuthoringProfileRequest):
            raise TypeError("CollaboratorAuthoringProfile requires authoring request")
        return [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {"task": request.task, **request.payload},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        ]

    def finish_action(
        self,
        *,
        proposal_kind: CollaboratorProposalKind,
        proposal: dict[str, Any],
        evidence_refs: tuple[str, ...] = (),
    ) -> LoopTerminalAction:
        return LoopTerminalAction(
            profile_id=self.profile_id,
            tool_name=self.terminal_tool_name,
            arguments={
                "proposal_kind": proposal_kind,
                "proposal": proposal,
                "evidence_refs": list(evidence_refs),
            },
        )

    def ask_action(
        self,
        *,
        intent_summary: str,
        question: str,
        reason: str,
        ask_kind: CollaboratorAskKind = "clarification",
        required: bool = True,
        options: tuple[dict[str, Any], ...] = (),
        missing_inputs: tuple[str, ...] = (),
        required_permissions: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
    ) -> LoopTerminalAction:
        return LoopTerminalAction(
            profile_id=self.profile_id,
            tool_name=ASK_AUTHORING_TOOL_NAME,
            arguments={
                "intent_summary": intent_summary,
                "ask_kind": ask_kind,
                "question": question,
                "reason": reason,
                "required": required,
                "options": list(options),
                "missing_inputs": list(missing_inputs),
                "required_permissions": list(required_permissions),
                "evidence_refs": list(evidence_refs),
            },
        )

    def tool_schemas(self, *, include_context_tools: bool) -> list[dict[str, Any]]:
        """Return provider-facing tool schemas for this profile."""

        schemas: list[dict[str, Any]] = []
        if include_context_tools:
            schemas.extend(
                [
                    _read_workspace_tool_schema(),
                    _search_workspace_tool_schema(),
                ]
            )
        schemas.append(_ask_authoring_tool_schema())
        schemas.append(_finish_authoring_tool_schema())
        return schemas

    def map_terminal_action(
        self,
        action: LoopTerminalAction,
        context: object,
    ) -> CollaboratorAuthoringLoopResult:
        if action.profile_id != self.profile_id:
            raise ValueError("terminal action profile_id does not match profile")
        if action.tool_name == ASK_AUTHORING_TOOL_NAME:
            return self._map_ask_action(action, context)
        if action.tool_name != self.terminal_tool_name:
            raise ValueError("terminal action tool_name does not match authoring terminal")
        proposal_kind = _proposal_kind_from_argument(action.arguments.get("proposal_kind"))
        proposal = action.arguments.get("proposal")
        if not isinstance(proposal, dict):
            raise ValueError("finish_authoring requires proposal object")
        return CollaboratorAuthoringLoopResult.finished_result(
            proposal_kind=proposal_kind,
            proposal=proposal,
            evidence_refs=_string_tuple_from_argument(
                action.arguments.get("evidence_refs", ())
            ),
        )

    def _map_ask_action(
        self,
        action: LoopTerminalAction,
        context: object,
    ) -> CollaboratorAuthoringLoopResult:
        if not isinstance(context, CollaboratorAuthoringProfileRequest):
            raise TypeError("ask_authoring requires authoring request context")
        if context.operation != "create_raw_task" or context.proposal_kind != "raw_task":
            raise ValueError("ask_authoring is only valid while creating a RawTask")

        intent_summary = _string_from_argument(
            action.arguments.get("intent_summary"),
            field_name="intent_summary",
        )
        question = _string_from_argument(
            action.arguments.get("question"),
            field_name="question",
        )
        reason = _string_from_argument(
            action.arguments.get("reason"),
            field_name="reason",
        )
        ask_kind = _ask_kind_from_argument(action.arguments.get("ask_kind"))
        missing_inputs = _string_tuple_from_argument(
            action.arguments.get("missing_inputs", ())
        )
        required_permissions = _string_tuple_from_argument(
            action.arguments.get("required_permissions", ())
        )
        if ask_kind == "clarification" and not missing_inputs:
            missing_inputs = (question,)
        if ask_kind == "permission" and not required_permissions:
            required_permissions = (reason,)

        proposal = {
            "kind": "raw_task",
            "intent_summary": intent_summary,
            "feasibility": {
                "status": (
                    "needs_user_permission"
                    if ask_kind == "permission"
                    else "needs_clarification"
                ),
                "confidence": _confidence_from_argument(
                    action.arguments.get("confidence", 0.5)
                ),
                "reasons": (reason,),
                "missing_inputs": missing_inputs,
                "required_permissions": required_permissions,
                "suggested_next_action": "ask_user",
            },
            "asks": (
                {
                    "question": question,
                    "reason": reason,
                    "required": _bool_from_argument(
                        action.arguments.get("required", True),
                        field_name="required",
                    ),
                    "options": _options_from_argument(
                        action.arguments.get("options", ())
                    ),
                },
            ),
        }
        return CollaboratorAuthoringLoopResult.finished_result(
            proposal_kind="raw_task",
            proposal=proposal,
            evidence_refs=_string_tuple_from_argument(
                action.arguments.get("evidence_refs", ())
            ),
        )

    def map_rejection(
        self,
        error: Exception,
        context: object,
    ) -> CollaboratorAuthoringLoopResult:
        return CollaboratorAuthoringLoopResult.rejected_result(reason=str(error))


def _validate_workspace_labels(labels: tuple[str, ...]) -> None:
    for label in labels:
        if not label.startswith(_WORKSPACE_LABEL_PREFIX):
            raise ValueError("path labels must use workspace://current labels")
        if label.startswith("/"):
            raise ValueError("path labels must not expose raw absolute paths")


def _proposal_kind_from_argument(value: object) -> CollaboratorProposalKind:
    if value in {"raw_task", "draft_task_tree", "draft_task_patch"}:
        return cast(CollaboratorProposalKind, value)
    raise ValueError("finish_authoring requires valid proposal_kind")


def _ask_kind_from_argument(value: object) -> CollaboratorAskKind:
    if value in {"clarification", "permission"}:
        return cast(CollaboratorAskKind, value)
    if value is None:
        return "clarification"
    raise ValueError("ask_authoring requires valid ask_kind")


def _string_from_argument(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"ask_authoring requires non-empty {field_name}")
    return value


def _confidence_from_argument(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be a number")
    confidence = float(value)
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
    return confidence


def _bool_from_argument(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _options_from_argument(value: object) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("options must be an object sequence")
    options: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("options must be an object sequence")
        options.append(item)
    return tuple(options)


def _string_tuple_from_argument(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        raise ValueError("evidence_refs must be a string sequence")
    refs: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("evidence_refs must be a string sequence")
        refs.append(item)
    return tuple(refs)


def _read_workspace_tool_schema() -> dict[str, Any]:
    return _tool_schema(
        name=AUTHORING_READ_WORKSPACE_TOOL_NAME,
        description=(
            "Read bounded UTF-8 snippets from explicitly named workspace files. "
            "Paths must be relative or workspace://current labels."
        ),
        parameters={
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "purpose": {"type": "string", "minLength": 1},
                "max_snippet_chars": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20000,
                    "default": 4000,
                },
            },
            "required": ["paths", "purpose"],
            "additionalProperties": False,
        },
    )


def _search_workspace_tool_schema() -> dict[str, Any]:
    return _tool_schema(
        name=AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
        description=(
            "Search project guidance files for bounded matching snippets. "
            "The search scope is limited to safe workspace labels and guidance globs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "scope": {
                    "type": "object",
                    "properties": {
                        "path_globs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "selected_folders": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "additionalProperties": False,
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
                "max_snippet_chars": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4000,
                    "default": 500,
                },
                "purpose": {"type": "string", "minLength": 1},
            },
            "required": ["query", "purpose"],
            "additionalProperties": False,
        },
    )


def _ask_authoring_tool_schema() -> dict[str, Any]:
    return _tool_schema(
        name=ASK_AUTHORING_TOOL_NAME,
        description=(
            "Ask the user one RawTask clarification or permission question and "
            "stop authoring until the answer is provided."
        ),
        parameters={
            "type": "object",
            "properties": {
                "intent_summary": {"type": "string", "minLength": 1},
                "ask_kind": {
                    "type": "string",
                    "enum": ["clarification", "permission"],
                    "default": "clarification",
                },
                "question": {"type": "string", "minLength": 1},
                "reason": {"type": "string", "minLength": 1},
                "required": {"type": "boolean", "default": True},
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "minLength": 1},
                            "value": {"type": "string", "minLength": 1},
                            "description": {"type": "string"},
                        },
                        "required": ["label", "value"],
                        "additionalProperties": False,
                    },
                    "default": [],
                },
                "missing_inputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
                "required_permissions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.5,
                },
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
            },
            "required": ["intent_summary", "question", "reason"],
            "additionalProperties": False,
        },
    )


def _finish_authoring_tool_schema() -> dict[str, Any]:
    return _tool_schema(
        name=FINISH_AUTHORING_TOOL_NAME,
        description=(
            "Finish Collaborator authoring with one structured proposal. "
            "Do not call this until enough context has been gathered."
        ),
        parameters={
            "type": "object",
            "properties": {
                "proposal_kind": {
                    "type": "string",
                    "enum": ["raw_task", "draft_task_tree", "draft_task_patch"],
                },
                "proposal": {
                    "type": "object",
                    "additionalProperties": True,
                },
                "evidence_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
            },
            "required": ["proposal_kind", "proposal"],
            "additionalProperties": False,
        },
    )


def _tool_schema(
    *,
    name: str,
    description: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


__all__ = [
    "ASK_AUTHORING_TOOL_NAME",
    "AUTHORING_READ_WORKSPACE_TOOL_NAME",
    "AUTHORING_SEARCH_WORKSPACE_TOOL_NAME",
    "COLLABORATOR_AUTHORING_ALLOWED_TOOL_NAMES",
    "COLLABORATOR_AUTHORING_FORBIDDEN_TOOL_NAMES",
    "COLLABORATOR_AUTHORING_PROFILE_ID",
    "FINISH_AUTHORING_TOOL_NAME",
    "CollaboratorAuthoringLoopResult",
    "CollaboratorAuthoringLoopState",
    "CollaboratorAuthoringLoopStatus",
    "CollaboratorAuthoringOperation",
    "CollaboratorAuthoringProfile",
    "CollaboratorAuthoringProfileRequest",
    "CollaboratorContextRequest",
    "CollaboratorContextRequestKind",
    "CollaboratorProposalKind",
]
