"""Context Manager v0 models for Product 1.0 execution context assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ContextBuildPurpose = Literal[
    "execution_start",
    "execution_step",
    "recovery",
    "read_only_review",
]
TaskContextVersion = Literal["task_execution_context.v0"]
AskFactStatus = Literal["pending", "answered", "deferred", "cancelled", "expired"]
ContextRenderMode = Literal[
    "full_context",
    "start_context",
    "delta_context",
    "checkpoint_context",
]
ContextSegmentKind = Literal[
    "full_context",
    "stable_prefix",
    "execution_transcript",
    "delta",
    "checkpoint",
]


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_context_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ContextModel(BaseModel):
    """Base model for immutable context contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class ContextBudget(ContextModel):
    max_events: int = Field(default=20, ge=0)
    max_tool_results: int = Field(default=10, ge=0)
    max_file_snippets: int = Field(default=6, ge=0)
    max_file_snippet_chars: int = Field(default=8_000, ge=0)
    max_rendered_chars: int = Field(default=60_000, ge=1)


class ContextBuildRequest(ContextModel):
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    agent_id: str = Field(default="default_agent", min_length=1)
    agent_run_id: str = Field(default_factory=lambda: new_context_id("run"), min_length=1)
    purpose: ContextBuildPurpose = "execution_step"
    render_mode: ContextRenderMode = "full_context"
    render_reason: str | None = None
    writer: bool = True
    turn_index: int = Field(default=0, ge=0)
    budget: ContextBudget = Field(default_factory=ContextBudget)
    runtime_config_hash: str | None = Field(default=None, min_length=1)
    latest_user_instruction: str | None = None
    prior_messages: tuple[dict[str, Any], ...] = ()


class TaskContextIdentity(ContextModel):
    task_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    parent_task_id: str | None = Field(default=None, min_length=1)
    root_task_id: str = Field(min_length=1)
    original_target: str = Field(min_length=1)
    interpreted_goal: str | None = None
    success_criteria: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    required_capability: str | None = None


class CurrentStepContext(ContextModel):
    step_id: str | None = None
    objective: str = Field(min_length=1)
    expected_output: str | None = None


class InterruptionContext(ContextModel):
    requested: bool = False
    request_id: str | None = Field(default=None, min_length=1)
    reason: str | None = None
    requested_by: Literal["user", "system"] | None = None
    requested_at: datetime | None = None


class ExecutionContextState(ContextModel):
    status: Literal["pending", "running", "waiting_for_user", "done", "failed"]
    claimed_by: str | None = None
    current_step: CurrentStepContext | None = None
    latest_user_instruction: str | None = None
    interruption: InterruptionContext | None = None


class EventSummary(ContextModel):
    event_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    family: Literal["action", "observation", "event"]
    timestamp: datetime
    summary: str = Field(min_length=1)
    raw_ref: str | None = None


class ToolResultSummary(ContextModel):
    observation_id: str = Field(min_length=1)
    action_id: str | None = None
    kind: str = Field(min_length=1)
    success: bool
    summary: str = Field(min_length=1)
    raw_ref: str | None = None
    token_estimate: int = Field(default=0, ge=0)
    observed_at: datetime


class WorkspaceRef(ContextModel):
    ref_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    kind: str = Field(default="file", min_length=1)
    reason: str = Field(min_length=1)
    raw_ref: str | None = None


class FileSnippet(ContextModel):
    snippet_id: str = Field(min_length=1)
    workspace_id: str | None = None
    path: str = Field(min_length=1)
    source: Literal[
        "tool_result",
        "workspace_ref",
        "user_attachment",
        "generated_artifact",
        "context_hint",
    ]
    content: str
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    file_hash: str | None = None
    content_hash: str = Field(min_length=1)
    raw_ref: str | None = None
    reason: str = Field(min_length=1)
    token_estimate: int = Field(ge=0)
    observed_at: datetime | None = None
    stale: bool = False
    can_act_as_instruction: bool = False


class AskFact(ContextModel):
    ask_id: str = Field(min_length=1)
    task_id: str | None = Field(default=None, min_length=1)
    status: AskFactStatus
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    selected_option_ids: tuple[str, ...] = ()
    answer_text: str | None = Field(default=None, min_length=1)
    answer_id: str | None = Field(default=None, min_length=1)
    blocking: bool = True
    created_at: datetime
    answered_at: datetime | None = None


class ExecutionFacts(ContextModel):
    recent_events: tuple[EventSummary, ...] = ()
    recent_tool_results: tuple[ToolResultSummary, ...] = ()
    workspace_refs: tuple[WorkspaceRef, ...] = ()
    selected_file_snippets: tuple[FileSnippet, ...] = ()
    ask_facts: tuple[AskFact, ...] = ()
    changed_artifacts: tuple[str, ...] = ()


class ApprovalSummary(ContextModel):
    message_id: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ExecutionControls(ContextModel):
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    requires_approval: tuple[str, ...] = ()
    pending_approval: ApprovalSummary | None = None
    file_scopes: tuple[str, ...] = ()


class SkillSummary(ContextModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_ref: str | None = None
    activation_id: str | None = Field(default=None, min_length=1)
    content_hash: str | None = Field(default=None, min_length=1)
    instruction_excerpt: str | None = Field(default=None, min_length=1)
    resource_refs: tuple[str, ...] = ()
    truncated: bool = False


class ExecutionGuidance(ContextModel):
    project_rules: tuple[str, ...] = ()
    active_skills: tuple[SkillSummary, ...] = ()
    output_requirements: tuple[str, ...] = ()


class ContextTraceRef(ContextModel):
    snapshot_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)


class TaskExecutionContextV0(ContextModel):
    context_version: TaskContextVersion = "task_execution_context.v0"
    task: TaskContextIdentity
    execution: ExecutionContextState
    facts: ExecutionFacts
    controls: ExecutionControls
    guidance: ExecutionGuidance
    trace: ContextTraceRef | None = None


class ContextCandidate(ContextModel):
    candidate_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    raw_ref: str | None = None
    priority: int = 100
    token_estimate: int = Field(default=0, ge=0)
    can_act_as_instruction: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class ContextExclusion(ContextModel):
    candidate_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ContextSkillPermissionOutcome(ContextModel):
    kind: str = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    tool: str | None = None
    reason: str = Field(min_length=1)


class ContextSkillTrace(ContextModel):
    activation_id: str = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    activation_reason: str = Field(min_length=1)
    segment_hash: str = Field(min_length=1)
    truncated: bool = False
    truncation_reason: str | None = None


class ContextMessageSegment(ContextModel):
    kind: ContextSegmentKind
    message_start_index: int = Field(ge=0)
    message_end_index: int = Field(ge=0)
    content_hash: str = Field(min_length=1)
    stable: bool = False


class ContextTrace(ContextModel):
    trace_id: str = Field(default_factory=lambda: new_context_id("trace"), min_length=1)
    snapshot_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    candidates_seen: tuple[str, ...] = ()
    candidates_selected: tuple[str, ...] = ()
    candidates_excluded: tuple[ContextExclusion, ...] = ()
    policy_version: str = Field(min_length=1)
    renderer_version: str = Field(min_length=1)
    render_mode: ContextRenderMode = "full_context"
    stable_prefix_hash: str | None = None
    context_segment_hashes: tuple[str, ...] = ()
    appended_context_message_count: int = Field(default=0, ge=0)
    delta_reason: str | None = None
    checkpoint_reason: str | None = None
    cache_policy_version: str | None = None
    runtime_config_hash: str | None = Field(default=None, min_length=1)
    active_skill_ids: tuple[str, ...] = ()
    active_skill_hashes: tuple[str, ...] = ()
    skill_activation_ids: tuple[str, ...] = ()
    skill_context_segment_hashes: tuple[str, ...] = ()
    skill_permission_outcomes: tuple[ContextSkillPermissionOutcome, ...] = ()
    skill_traces: tuple[ContextSkillTrace, ...] = ()
    skill_truncation_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utcnow)


class ContextSnapshot(ContextModel):
    snapshot_id: str = Field(default_factory=lambda: new_context_id("ctx"), min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    agent_run_id: str = Field(min_length=1)
    purpose: ContextBuildPurpose
    turn_index: int = Field(ge=0)
    context_version: TaskContextVersion = "task_execution_context.v0"
    renderer_version: str = Field(min_length=1)
    rendered_input_hash: str = Field(min_length=1)
    render_mode: ContextRenderMode = "full_context"
    stable_prefix_hash: str | None = None
    context_segment_hashes: tuple[str, ...] = ()
    runtime_config_hash: str | None = Field(default=None, min_length=1)
    task_execution_context: TaskExecutionContextV0
    created_at: datetime = Field(default_factory=utcnow)


class RenderedLlmInput(ContextModel):
    renderer_version: str = Field(min_length=1)
    system_content: str = Field(min_length=1)
    user_content: str = Field(min_length=1)
    messages: tuple[dict[str, Any], ...]
    rendered_input_hash: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    render_mode: ContextRenderMode = "full_context"
    segments: tuple[ContextMessageSegment, ...] = ()
    stable_prefix_hash: str | None = None
    runtime_config_hash: str | None = Field(default=None, min_length=1)


class ContextBuildResult(ContextModel):
    request: ContextBuildRequest
    context: TaskExecutionContextV0
    rendered: RenderedLlmInput
    snapshot: ContextSnapshot
    trace: ContextTrace
