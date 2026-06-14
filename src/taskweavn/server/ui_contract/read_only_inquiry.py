"""Read-Only Inquiry contract models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from taskweavn.server.ui_contract.base import UiContractModel, utcnow
from taskweavn.server.ui_contract.view_models import SessionActivityItemView

ReadOnlyInquiryScopeKind = Literal["session", "plan", "task"]
ReadOnlyInquiryConfidence = Literal["high", "medium", "low"]
ReadOnlyInquiryStatus = Literal[
    "answered",
    "needs_clarification",
    "unsupported",
    "rejected",
]
ReadOnlyInquiryRefKind = Literal[
    "task",
    "plan",
    "result",
    "file",
    "diff",
    "audit_record",
    "audit_evidence",
    "diagnostic",
    "activity",
]
ReadOnlyInquiryEvidenceKind = Literal[
    "workspace_status",
    "file_snapshot",
    "diff_snapshot",
    "result_summary",
    "file_change_summary",
    "audit_record",
    "audit_evidence",
    "diagnostic_summary",
    "activity_item",
    "session_status",
    "task_status",
    "plan_status",
]
ReadOnlyInquiryDisclosure = Literal["public", "partial", "hidden"]
ReadOnlyInquiryWarningCode = Literal[
    "inquiry.context_empty",
    "inquiry.context_partial",
    "inquiry.context_truncated",
    "inquiry.evidence_hidden",
    "inquiry.provider_unavailable",
    "inquiry.unsupported_question",
    "inquiry.no_mutation_boundary",
]


class ReadOnlyInquiryScope(UiContractModel):
    kind: ReadOnlyInquiryScopeKind
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_scope_identity(self) -> ReadOnlyInquiryScope:
        if self.kind == "plan" and self.plan_id is None:
            raise ValueError("plan-scoped inquiry requires planId")
        if self.kind == "task" and self.task_node_id is None:
            raise ValueError("task-scoped inquiry requires taskNodeId")
        return self


class ReadOnlyInquiryRef(UiContractModel):
    kind: ReadOnlyInquiryRefKind
    id: str | None = Field(default=None, min_length=1)
    path: str | None = Field(default=None, min_length=1)
    evidence_id: str | None = Field(default=None, min_length=1)
    label: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def _reject_absolute_or_parent_paths(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("inquiry refs require workspace-relative safe paths")
        return normalized


class ReadOnlyInquiryLimits(UiContractModel):
    max_evidence_items: int | None = Field(default=None, ge=1, le=50)
    max_context_bytes: int | None = Field(default=None, ge=1024, le=262144)
    max_answer_chars: int | None = Field(default=None, ge=128, le=12000)


class ReadOnlyInquiryRequest(UiContractModel):
    inquiry_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    workspace_id: str | None = Field(default=None, min_length=1)
    question: str = Field(min_length=1, max_length=8000)
    scope: ReadOnlyInquiryScope
    refs: tuple[ReadOnlyInquiryRef, ...] = ()
    limits: ReadOnlyInquiryLimits = Field(default_factory=ReadOnlyInquiryLimits)

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("inquiry question must not be blank")
        return stripped


class ReadOnlyInquiryAnswer(UiContractModel):
    title: str | None = Field(default=None, min_length=1)
    body: str = Field(min_length=1)
    confidence: ReadOnlyInquiryConfidence


class ReadOnlyInquiryEvidenceRef(UiContractModel):
    kind: ReadOnlyInquiryEvidenceKind
    ref_id: str = Field(min_length=1)
    parent_ref_id: str | None = Field(default=None, min_length=1)
    label: str = Field(min_length=1)
    disclosure: ReadOnlyInquiryDisclosure = "public"
    truncated: bool = False


class ReadOnlyInquiryWarning(UiContractModel):
    code: ReadOnlyInquiryWarningCode
    message: str = Field(min_length=1)
    ref: ReadOnlyInquiryRef | None = None


class ReadOnlyInquiryResult(UiContractModel):
    inquiry_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    scope: ReadOnlyInquiryScope
    status: ReadOnlyInquiryStatus
    answer: ReadOnlyInquiryAnswer | None = None
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...] = ()
    warnings: tuple[ReadOnlyInquiryWarning, ...] = ()
    activity: SessionActivityItemView | None = None
    generated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _validate_answer_status(self) -> ReadOnlyInquiryResult:
        if self.status == "answered" and self.answer is None:
            raise ValueError("answered inquiry result requires answer")
        return self


__all__ = [
    "ReadOnlyInquiryAnswer",
    "ReadOnlyInquiryConfidence",
    "ReadOnlyInquiryDisclosure",
    "ReadOnlyInquiryEvidenceKind",
    "ReadOnlyInquiryEvidenceRef",
    "ReadOnlyInquiryLimits",
    "ReadOnlyInquiryRef",
    "ReadOnlyInquiryRefKind",
    "ReadOnlyInquiryRequest",
    "ReadOnlyInquiryResult",
    "ReadOnlyInquiryScope",
    "ReadOnlyInquiryScopeKind",
    "ReadOnlyInquiryStatus",
    "ReadOnlyInquiryWarning",
    "ReadOnlyInquiryWarningCode",
]
