"""Tests for Collaborator authoring loop contract models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from taskweavn.task import (
    AUTHORING_READ_WORKSPACE_TOOL_NAME,
    AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
    COLLABORATOR_AUTHORING_ALLOWED_TOOL_NAMES,
    COLLABORATOR_AUTHORING_FORBIDDEN_TOOL_NAMES,
    COLLABORATOR_AUTHORING_PROFILE_ID,
    FINISH_AUTHORING_TOOL_NAME,
    CollaboratorAuthoringLoopResult,
    CollaboratorContextRequest,
    default_collaborator_template,
)


def test_collaborator_profile_names_are_contract_only_for_slice_a() -> None:
    assert COLLABORATOR_AUTHORING_PROFILE_ID == "collaborator_authoring"
    assert COLLABORATOR_AUTHORING_ALLOWED_TOOL_NAMES == (
        AUTHORING_READ_WORKSPACE_TOOL_NAME,
        AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
        FINISH_AUTHORING_TOOL_NAME,
    )
    assert "write_file" in COLLABORATOR_AUTHORING_FORBIDDEN_TOOL_NAMES
    assert "shell" in COLLABORATOR_AUTHORING_FORBIDDEN_TOOL_NAMES

    template = default_collaborator_template()
    assert template.llm_visible_tool_pools == ()


def test_waiting_for_context_result_is_not_authoring_proposal() -> None:
    context_request = CollaboratorContextRequest(
        kind="workspace_selection",
        reason="Need the relevant plan file before authoring.",
        candidate_path_labels=("workspace://current/docs/plans/example.md",),
    )

    result = CollaboratorAuthoringLoopResult.waiting_for_context(
        reason="No selected guidance file.",
        requested_context=context_request,
        candidate_evidence_refs=("evidence-1",),
    )

    assert result.status == "waiting_for_context"
    assert result.requested_context == context_request
    assert result.proposal_kind is None
    assert result.proposal is None
    assert result.authoring_command_result_ref is None


def test_loop_result_payloads_are_status_specific() -> None:
    finished = CollaboratorAuthoringLoopResult.finished_result(
        proposal_kind="raw_task",
        proposal={"intent_summary": "Write docs"},
        evidence_refs=("evidence-1",),
        authoring_command_result_ref="command-result-1",
    )
    rejected = CollaboratorAuthoringLoopResult.rejected_result(
        reason="Step limit exceeded.",
        error_ref="error-1",
        evidence_refs=("evidence-1",),
    )

    assert finished.status == "finished"
    assert finished.proposal_kind == "raw_task"
    assert finished.authoring_command_result_ref == "command-result-1"
    assert rejected.status == "rejected"
    assert rejected.error_ref == "error-1"

    with pytest.raises(ValidationError, match="proposal_kind and proposal"):
        CollaboratorAuthoringLoopResult(status="finished")

    with pytest.raises(ValidationError, match="requested_context"):
        CollaboratorAuthoringLoopResult(
            status="waiting_for_context",
            reason="Need context.",
        )

    with pytest.raises(ValidationError, match="requires reason"):
        CollaboratorAuthoringLoopResult(status="rejected")


def test_context_request_rejects_raw_absolute_path_labels() -> None:
    with pytest.raises(ValidationError, match="workspace://current"):
        CollaboratorContextRequest(
            kind="workspace_selection",
            reason="Need a safe path label.",
            requested_path_labels=("/Users/example/project/README.md",),
        )
