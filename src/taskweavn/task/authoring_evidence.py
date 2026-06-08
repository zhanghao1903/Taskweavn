"""Authoring evidence contracts for Collaborator workspace-informed planning."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

AuthoringEvidenceOperation = Literal["read_workspace", "search_workspace"]
AuthoringEvidencePolicyDecision = Literal["allowed", "denied", "omitted"]
AuthoringEvidenceToolName = Literal[
    "authoring_read_workspace",
    "authoring_search_workspace",
]

_WORKSPACE_LABEL_PREFIX = "workspace://current"


def _new_id() -> str:
    return uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _FrozenAuthoringEvidenceModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class AuthoringEvidenceRecord(_FrozenAuthoringEvidenceModel):
    """Diagnostic-safe evidence record for authoring read/search observations."""

    evidence_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    loop_id: str = Field(min_length=1)
    operation: AuthoringEvidenceOperation
    tool_name: AuthoringEvidenceToolName
    purpose: str = Field(min_length=1)
    path_label: str = Field(min_length=1)
    content_hash: str | None = Field(default=None, min_length=1)
    snippet: str | None = Field(default=None, min_length=1)
    omitted_reason: str | None = Field(default=None, min_length=1)
    policy_decision: AuthoringEvidencePolicyDecision
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _validate_record(self) -> AuthoringEvidenceRecord:
        if not self.path_label.startswith(_WORKSPACE_LABEL_PREFIX):
            raise ValueError("path_label must use workspace://current labels")
        if self.path_label.startswith("/"):
            raise ValueError("path_label must not expose raw absolute paths")
        if self.policy_decision in {"denied", "omitted"} and self.omitted_reason is None:
            raise ValueError("denied or omitted evidence requires omitted_reason")
        if self.policy_decision == "allowed" and self.omitted_reason is not None:
            raise ValueError("allowed evidence must not include omitted_reason")
        return self


@runtime_checkable
class AuthoringEvidenceStore(Protocol):
    """Authoritative source for authoring read/search evidence records."""

    def put(self, record: AuthoringEvidenceRecord) -> AuthoringEvidenceRecord: ...

    def get(
        self,
        session_id: str,
        evidence_id: str,
    ) -> AuthoringEvidenceRecord | None: ...

    def list_for_loop(
        self,
        session_id: str,
        loop_id: str,
    ) -> tuple[AuthoringEvidenceRecord, ...]: ...

    def list_for_session(self, session_id: str) -> tuple[AuthoringEvidenceRecord, ...]: ...


__all__ = [
    "AuthoringEvidenceOperation",
    "AuthoringEvidencePolicyDecision",
    "AuthoringEvidenceRecord",
    "AuthoringEvidenceStore",
    "AuthoringEvidenceToolName",
]
