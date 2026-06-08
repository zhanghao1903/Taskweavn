"""Collaborator authoring loop contract models and one-shot profile seam."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.core.loop_profile import LoopTerminalAction
from taskweavn.prompts import COLLABORATOR_AUTHORING_SYSTEM_PROMPT

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

    Slice B only exposes the terminal `finish_authoring` tool. Read/search tool
    names remain contract constants for later slices, but they are not visible
    to the current one-shot LLM call.
    """

    system_prompt: str = COLLABORATOR_AUTHORING_SYSTEM_PROMPT
    profile_id: str = COLLABORATOR_AUTHORING_PROFILE_ID
    terminal_tool_name: str = FINISH_AUTHORING_TOOL_NAME
    allowed_tool_names: tuple[str, ...] = (FINISH_AUTHORING_TOOL_NAME,)

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

    def map_terminal_action(
        self,
        action: LoopTerminalAction,
        context: object,
    ) -> CollaboratorAuthoringLoopResult:
        if action.profile_id != self.profile_id:
            raise ValueError("terminal action profile_id does not match profile")
        if action.tool_name != self.terminal_tool_name:
            raise ValueError("terminal action tool_name does not match finish_authoring")
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
    "CollaboratorAuthoringProfile",
    "CollaboratorAuthoringProfileRequest",
    "CollaboratorContextRequest",
    "CollaboratorContextRequestKind",
    "CollaboratorProposalKind",
]
