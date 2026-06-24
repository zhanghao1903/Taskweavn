"""Runtime Input Router contract models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from taskweavn.server.ui_contract.base import UiContractModel, utcnow
from taskweavn.server.ui_contract.envelopes import CommandResponse
from taskweavn.server.ui_contract.product_errors import ProductRecoveryAction
from taskweavn.server.ui_contract.read_only_inquiry import (
    ReadOnlyInquiryRef,
    ReadOnlyInquiryResult,
)
from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.server.ui_contract.view_models import (
    SessionActivityItemView,
    SessionActivityRefView,
    SessionActivitySideEffect,
)

RuntimeInputMode = Literal["auto", "ask", "guide", "change"]
RuntimeInputIntent = Literal[
    "question",
    "guidance",
    "command",
    "ask_answer",
    "confirmation_response",
    "execution_request",
    "clarification",
    "unsupported",
]
RuntimeInputConfidence = Literal["high", "medium", "low"]
RuntimeInputDispatchTarget = Literal[
    "read_only_inquiry",
    "record_guidance",
    "resolve_ask",
    "resolve_confirmation",
    "existing_command",
    "execution_handoff",
    "clarification",
    "unsupported",
]
RuntimeInputOutcomeStatus = Literal[
    "dispatched",
    "answered",
    "needs_clarification",
    "unsupported",
    "rejected",
]
RuntimeInputScopeKind = Literal["session", "plan", "task"]
RuntimeInputPendingClarificationKind = Literal["wechat_send"]
RuntimeInputPendingClarificationSlot = Literal["contactDisplayName", "messageText"]


def _new_router_id() -> str:
    return f"rir-{uuid4().hex}"


class RuntimeInputSelection(UiContractModel):
    scope_kind: RuntimeInputScopeKind
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)
    refs: tuple[ObjectRef, ...] = ()

    @model_validator(mode="after")
    def _validate_scope_identity(self) -> RuntimeInputSelection:
        if self.scope_kind == "plan" and self.plan_id is None:
            raise ValueError("plan-scoped runtime input requires planId")
        if self.scope_kind == "task" and self.task_node_id is None:
            raise ValueError("task-scoped runtime input requires taskNodeId")
        return self


class RuntimeInputPendingClarification(UiContractModel):
    kind: RuntimeInputPendingClarificationKind
    reason_code: str = Field(min_length=1)
    contact_display_name: str | None = Field(default=None, min_length=1)
    message_text: str | None = Field(default=None, min_length=1)
    missing_slots: tuple[RuntimeInputPendingClarificationSlot, ...]
    original_content: str = Field(min_length=1, max_length=8000)

    @model_validator(mode="after")
    def _validate_pending_payload(self) -> RuntimeInputPendingClarification:
        if not self.missing_slots:
            raise ValueError("pending clarification requires at least one missing slot")
        if (
            "contactDisplayName" in self.missing_slots
            and self.contact_display_name is not None
        ):
            raise ValueError("pending contact clarification must not include contact")
        if "messageText" in self.missing_slots and self.message_text is not None:
            raise ValueError("pending message clarification must not include message")
        return self


class RuntimeInputClientState(UiContractModel):
    active_ask_id: str | None = Field(default=None, min_length=1)
    active_confirmation_id: str | None = Field(default=None, min_length=1)
    pending_clarification: RuntimeInputPendingClarification | None = None


class RuntimeInputRouteRequest(UiContractModel):
    command_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    workspace_id: str | None = Field(default=None, min_length=1)
    content: str = Field(min_length=1, max_length=8000)
    mode: RuntimeInputMode = "auto"
    selection: RuntimeInputSelection
    inquiry_refs: tuple[ReadOnlyInquiryRef, ...] = ()
    client_state: RuntimeInputClientState = Field(
        default_factory=RuntimeInputClientState
    )

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("runtime input content must not be blank")
        return stripped


class RuntimeInputDecisionScope(UiContractModel):
    kind: RuntimeInputScopeKind
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_scope_identity(self) -> RuntimeInputDecisionScope:
        if self.kind == "plan" and self.plan_id is None:
            raise ValueError("plan-scoped route decision requires planId")
        if self.kind == "task" and self.task_node_id is None:
            raise ValueError("task-scoped route decision requires taskNodeId")
        return self


class RuntimeInputRouteDecision(UiContractModel):
    id: str = Field(default_factory=_new_router_id, min_length=1)
    intent: RuntimeInputIntent
    scope: RuntimeInputDecisionScope
    confidence: RuntimeInputConfidence
    side_effect: SessionActivitySideEffect
    dispatch_target: RuntimeInputDispatchTarget
    explanation: str = Field(min_length=1)
    related_refs: tuple[SessionActivityRefView, ...] = ()


class RuntimeInputOutcome(UiContractModel):
    status: RuntimeInputOutcomeStatus
    user_message: str = Field(min_length=1)
    recovery_actions: tuple[ProductRecoveryAction, ...] = ()
    pending_clarification: RuntimeInputPendingClarification | None = None


class RuntimeInputRouteResult(UiContractModel):
    session_id: str = Field(min_length=1)
    decision: RuntimeInputRouteDecision
    outcome: RuntimeInputOutcome
    activity: SessionActivityItemView | None = None
    command_response: CommandResponse | None = None
    inquiry_result: ReadOnlyInquiryResult | None = None
    generated_at: datetime = Field(default_factory=utcnow)


__all__ = [
    "RuntimeInputClientState",
    "RuntimeInputConfidence",
    "RuntimeInputDecisionScope",
    "RuntimeInputDispatchTarget",
    "RuntimeInputIntent",
    "RuntimeInputMode",
    "RuntimeInputOutcome",
    "RuntimeInputOutcomeStatus",
    "RuntimeInputPendingClarification",
    "RuntimeInputPendingClarificationKind",
    "RuntimeInputPendingClarificationSlot",
    "RuntimeInputRouteDecision",
    "RuntimeInputRouteRequest",
    "RuntimeInputRouteResult",
    "RuntimeInputScopeKind",
    "RuntimeInputSelection",
]
