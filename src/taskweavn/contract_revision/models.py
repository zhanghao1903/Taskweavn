"""Contract Revision command models."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from taskweavn.server.ui_contract.base import to_camel, utcnow
from taskweavn.server.ui_contract.envelopes import CommandResponse
from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.server.ui_contract.view_models import (
    SessionActivityRefView,
    SessionActivitySideEffect,
)

ContractCommandKind = Literal[
    "record_guidance",
    "patch_task_node",
    "create_task_node",
    "delete_task_node",
    "create_execution_task",
    "resolve_ask",
    "resolve_confirmation",
]
ContractCommandStatus = Literal[
    "accepted",
    "rejected",
    "needs_confirmation",
    "conflict",
    "noop",
    "unsupported",
]
ContractCommandScopeKind = Literal["session", "plan", "task", "ask", "confirmation"]
ContractCommandSource = Literal[
    "runtime_input",
    "explicit_ui",
    "system_recovery",
    "test_fixture",
]
GuidanceKind = Literal[
    "preference",
    "constraint",
    "instruction",
    "correction",
    "context_note",
]


class ContractRevisionModel(BaseModel):
    """Frozen internal contract model with frontend-compatible aliases."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        validate_assignment=True,
    )


def new_contract_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class RecordGuidancePayload(ContractRevisionModel):
    guidance_text: str = Field(min_length=1, max_length=8000)
    guidance_kind: GuidanceKind = "instruction"
    applies_to_future_tasks: bool = False
    expires_at: datetime | None = None

    @field_validator("guidance_text", mode="before")
    @classmethod
    def _strip_guidance_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("guidance_text must not be blank")
        return stripped


class ResolveAskPayload(ContractRevisionModel):
    selected_option_ids: tuple[str, ...] = ()
    text: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_answer_content(self) -> ResolveAskPayload:
        if not self.selected_option_ids and self.text is None:
            raise ValueError("resolve ASK payload requires selected option or text")
        return self


class ResolveConfirmationContractPayload(ContractRevisionModel):
    value: str = Field(min_length=1)
    note: str | None = Field(default=None, min_length=1)


class PatchTaskNodePayload(ContractRevisionModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    intent: str | None = Field(default=None, min_length=1)
    full_intent: str | None = Field(default=None, min_length=1)
    constraints: tuple[str, ...] | None = None
    update_mode: Literal["node_fields", "replace_children", "replace_subtree"] = (
        "node_fields"
    )
    preserve_root_id: bool = True

    @model_validator(mode="after")
    def _validate_non_empty_patch(self) -> PatchTaskNodePayload:
        if (
            self.title is None
            and self.summary is None
            and self.intent is None
            and self.full_intent is None
            and self.constraints is None
        ):
            raise ValueError("patch task node payload must contain at least one field")
        if self.intent is not None and self.full_intent is not None:
            raise ValueError("patch task node payload cannot set intent and full_intent")
        return self


class CreateTaskNodePayload(ContractRevisionModel):
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    instructions: str = ""
    required_capability: str | None = Field(default="general", min_length=1)
    constraints: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    after_task_node_id: str | None = Field(default=None, min_length=1)


class CreateExecutionTaskPayload(ContractRevisionModel):
    intent: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    instructions: str = ""
    required_capability: str | None = Field(default="general", min_length=1)
    constraints: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()


class DeleteTaskNodePayload(ContractRevisionModel):
    reason: str | None = Field(default=None, min_length=1)


class ContractCommandRequest(ContractRevisionModel):
    command_id: str = Field(default_factory=lambda: new_contract_id("ccmd"), min_length=1)
    idempotency_key: str = Field(min_length=1)
    command_kind: ContractCommandKind
    workspace_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    scope_kind: ContractCommandScopeKind
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)
    ask_id: str | None = Field(default=None, min_length=1)
    confirmation_id: str | None = Field(default=None, min_length=1)
    source: ContractCommandSource = "runtime_input"
    router_decision_id: str | None = Field(default=None, min_length=1)
    input_message_ref: ObjectRef | None = None
    expected_version: int | None = Field(default=None, ge=1)
    payload: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_scope_identity(self) -> ContractCommandRequest:
        if self.scope_kind == "plan" and self.plan_id is None:
            raise ValueError("plan-scoped contract command requires plan_id")
        if self.scope_kind == "task" and self.task_node_id is None:
            raise ValueError("task-scoped contract command requires task_node_id")
        if self.scope_kind == "ask" and self.ask_id is None:
            raise ValueError("ask-scoped contract command requires ask_id")
        if self.scope_kind == "confirmation" and self.confirmation_id is None:
            raise ValueError(
                "confirmation-scoped contract command requires confirmation_id"
            )
        return self


class ContractCommandActivityDescriptor(ContractRevisionModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    related_refs: tuple[SessionActivityRefView, ...] = ()
    disclosure_level: Literal["public", "partial", "hidden"] = "public"


class ContractCommandAuditDescriptor(ContractRevisionModel):
    command_id: str = Field(min_length=1)
    command_kind: ContractCommandKind
    status: ContractCommandStatus
    side_effect: SessionActivitySideEffect
    scope_kind: ContractCommandScopeKind
    session_id: str = Field(min_length=1)
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)
    target_ref: ObjectRef | None = None
    summary: str = Field(min_length=1)


class ContractCommandDiagnosticDescriptor(ContractRevisionModel):
    kind: Literal["contract_revision_command"] = "contract_revision_command"
    command_kind: ContractCommandKind
    status: ContractCommandStatus
    side_effect: SessionActivitySideEffect
    scope_kind: ContractCommandScopeKind
    reason_code: str | None = Field(default=None, min_length=1)
    router_decision_id: str | None = Field(default=None, min_length=1)
    preview: str | None = None
    truncated: bool = False


class ContractCommandResult(ContractRevisionModel):
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    command_kind: ContractCommandKind
    status: ContractCommandStatus
    side_effect: SessionActivitySideEffect
    scope_kind: ContractCommandScopeKind
    session_id: str = Field(min_length=1)
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)
    ask_id: str | None = Field(default=None, min_length=1)
    confirmation_id: str | None = Field(default=None, min_length=1)
    refs: tuple[SessionActivityRefView, ...] = ()
    activity: ContractCommandActivityDescriptor | None = None
    audit: ContractCommandAuditDescriptor | None = None
    diagnostics: ContractCommandDiagnosticDescriptor | None = None
    command_response: CommandResponse | None = None
    new_version: int | None = Field(default=None, ge=1)
    reason_code: str | None = Field(default=None, min_length=1)
    message_key: str | None = Field(default=None, min_length=1)
    guidance_id: str | None = Field(default=None, min_length=1)

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


class GuidanceFact(ContractRevisionModel):
    guidance_id: str = Field(default_factory=lambda: new_contract_id("guidance"))
    workspace_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    scope_kind: Literal["session", "plan", "task"]
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)
    guidance_kind: GuidanceKind
    guidance_text: str = Field(min_length=1, max_length=8000)
    applies_to_future_tasks: bool = False
    source_command_id: str = Field(min_length=1)
    source_router_decision_id: str | None = Field(default=None, min_length=1)
    source_message_ref: ObjectRef | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utcnow)
    archived_at: datetime | None = None

    @field_validator("guidance_text", mode="before")
    @classmethod
    def _strip_guidance_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("guidance_text must not be blank")
        return stripped

    @model_validator(mode="after")
    def _validate_scope_identity(self) -> GuidanceFact:
        if self.scope_kind == "plan" and self.plan_id is None:
            raise ValueError("plan-scoped guidance requires plan_id")
        if self.scope_kind == "task" and self.task_node_id is None:
            raise ValueError("task-scoped guidance requires task_node_id")
        return self


class ContractCommandRecord(ContractRevisionModel):
    session_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    command_kind: ContractCommandKind
    request_hash: str = Field(min_length=1)
    status: ContractCommandStatus
    result: ContractCommandResult | None = None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None


__all__ = [
    "ContractCommandActivityDescriptor",
    "ContractCommandAuditDescriptor",
    "ContractCommandDiagnosticDescriptor",
    "ContractCommandKind",
    "ContractCommandRecord",
    "ContractCommandRequest",
    "ContractCommandResult",
    "ContractCommandScopeKind",
    "ContractCommandSource",
    "ContractCommandStatus",
    "ContractRevisionModel",
    "CreateExecutionTaskPayload",
    "CreateTaskNodePayload",
    "DeleteTaskNodePayload",
    "GuidanceFact",
    "GuidanceKind",
    "PatchTaskNodePayload",
    "RecordGuidancePayload",
    "ResolveAskPayload",
    "ResolveConfirmationContractPayload",
    "new_contract_id",
]
