"""Collaborator authoring loop contract models.

Slice A only defines the result/profile-facing shapes. It does not wire these
models into the current Collaborator service and does not register tools.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

AUTHORING_READ_WORKSPACE_TOOL_NAME = "authoring_read_workspace"
AUTHORING_SEARCH_WORKSPACE_TOOL_NAME = "authoring_search_workspace"
COLLABORATOR_AUTHORING_PROFILE_ID = "collaborator_authoring"
FINISH_AUTHORING_TOOL_NAME = "finish_authoring"

COLLABORATOR_AUTHORING_ALLOWED_TOOL_NAMES: tuple[str, ...] = (
    AUTHORING_READ_WORKSPACE_TOOL_NAME,
    AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
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


def _validate_workspace_labels(labels: tuple[str, ...]) -> None:
    for label in labels:
        if not label.startswith(_WORKSPACE_LABEL_PREFIX):
            raise ValueError("path labels must use workspace://current labels")
        if label.startswith("/"):
            raise ValueError("path labels must not expose raw absolute paths")


__all__ = [
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
    "CollaboratorContextRequest",
    "CollaboratorContextRequestKind",
    "CollaboratorProposalKind",
]
