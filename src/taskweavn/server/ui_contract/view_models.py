"""Transport-facing ViewModels consumed by the Plato frontend."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from taskweavn.server.ui_contract.base import UiContractModel, utcnow
from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.task.models import TaskRef

SessionStatus = Literal[
    "new",
    "understanding",
    "draft_ready",
    "running",
    "waiting_user",
    "completed",
    "failed",
]
PlanningState = Literal[
    "empty",
    "capturing_input",
    "assessing",
    "awaiting_user",
    "ready_to_plan",
    "draft_ready",
    "published",
    "rejected",
    "cancelled",
    "unknown",
]
TaskTreeStatus = Literal["draft", "published", "running", "completed", "failed"]
PlanUiStatus = Literal[
    "draft",
    "reviewing",
    "ready_to_publish",
    "published",
    "running",
    "finalizing",
    "ready_for_review",
    "accepted",
    "follow_up_needed",
    "failed",
    "cancelled",
    "unknown",
]
TaskNodeStatus = Literal[
    "draft",
    "queued",
    "running",
    "waiting_user",
    "done",
    "failed",
    "cancelled",
]
ExecutionStatus = Literal[
    "not_started",
    "pending",
    "running",
    "waiting_for_user",
    "done",
    "failed",
    "cancelled",
    "unknown",
]
MessageKind = Literal["informational", "actionable", "response", "error"]
AskAnswerType = Literal["free_text", "single_choice", "multi_choice", "boolean"]
AskRequestStatus = Literal["pending", "answered", "deferred", "cancelled", "expired"]
SessionActivityItemKind = Literal[
    "user_input",
    "answer",
    "guidance_recorded",
    "plan_updated",
    "task_created",
    "task_changed",
    "task_removed",
    "ask_asked",
    "ask_answered",
    "confirmation_requested",
    "confirmation_resolved",
    "execution_update",
    "result_ready",
    "file_summary",
    "recovery_note",
    "router_interpretation",
]
SessionActivityScopeKind = Literal["session", "plan", "task"]
SessionActivitySideEffect = Literal[
    "no_effect",
    "context_effect",
    "state_effect",
    "authorization_effect",
    "resume_effect",
    "execution_request",
    "evidence_effect",
]
SessionActivityRefKind = Literal[
    "session",
    "plan",
    "task",
    "ask",
    "confirmation",
    "message",
    "result",
    "file",
    "audit",
    "diagnostic",
]
SessionActivitySourceKind = Literal[
    "message_stream",
    "plan_projection",
    "task_projection",
    "ask_projection",
    "confirmation_projection",
    "result_projection",
    "file_projection",
    "router",
    "system",
]
SessionActivityDisclosureLevel = Literal["public", "partial", "hidden"]
ConversationRenderKind = Literal["text", "router_trace", "question_card"]
ConversationQuestionCardKind = Literal["clarification", "ask", "confirmation"]
ConversationQuestionCardStatus = Literal["pending", "answered", "cancelled", "expired"]
ConversationQuestionAnswerMode = Literal[
    "runtime_input",
    "ask_command",
    "confirmation_command",
]


class ProjectSummary(UiContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class WorkflowSummary(UiContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    input_hint: str | None = None
    delivery_kind: Literal[
        "task_tree",
        "execution_result",
        "result_card",
        "audit_review",
    ] | None = None


class SessionSummary(UiContractModel):
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    workspace_label: str | None = None

    @model_validator(mode="after")
    def _validate_timestamps(self) -> SessionSummary:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self


class TaskNodeBadges(UiContractModel):
    pending_confirmation_count: int = Field(default=0, ge=0)
    unread_message_count: int = Field(default=0, ge=0)
    direct_file_change_count: int = Field(default=0, ge=0)
    subtree_file_change_count: int = Field(default=0, ge=0)


class TaskNodePermissions(UiContractModel):
    can_edit: bool = False
    can_append_guidance: bool = False
    can_resolve_confirmation: bool = False
    can_publish: bool = False
    can_cancel: bool = False
    can_retry: bool = False


class TaskNodeCardView(UiContractModel):
    id: str = Field(min_length=1)
    plan_id: str | None = Field(default=None, min_length=1)
    task_ref: TaskRef | None = None
    parent_id: str | None = None
    task_index: str | None = Field(default=None, min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    intent: str | None = Field(default=None, min_length=1)
    instructions: str | None = Field(default=None, min_length=1)
    acceptance_criteria: tuple[str, ...] = ()
    status: TaskNodeStatus
    execution: ExecutionStatus = "unknown"
    depth: int = Field(default=0, ge=0)
    order_index: int = Field(default=0, ge=0)
    display_index: int = Field(default=1, ge=1)
    result_ref: str | None = Field(default=None, min_length=1)
    error_ref: str | None = Field(default=None, min_length=1)
    interruption_requested: bool = False
    badges: TaskNodeBadges = Field(default_factory=TaskNodeBadges)
    permissions: TaskNodePermissions = Field(default_factory=TaskNodePermissions)
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate_parent_depth(self) -> TaskNodeCardView:
        if self.depth == 0 and self.parent_id is not None:
            raise ValueError("root TaskNodeCardView must not have parent_id")
        if self.depth > 0 and self.parent_id is None:
            raise ValueError("child TaskNodeCardView requires parent_id")
        return self


class TaskTreeView(UiContractModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str | None = None
    status: TaskTreeStatus
    nodes: tuple[TaskNodeCardView, ...] = ()
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate_unique_nodes(self) -> TaskTreeView:
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("TaskTreeView nodes must have unique ids")
        return self


class ExecutionRollupView(UiContractModel):
    total: int = Field(default=0, ge=0)
    not_started: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    running: int = Field(default=0, ge=0)
    done: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    cancelled: int = Field(default=0, ge=0)
    unknown: int = Field(default=0, ge=0)
    blocked_by_confirmation: int = Field(default=0, ge=0)


class PlanFinalizationView(UiContractModel):
    status: Literal[
        "not_started",
        "pending",
        "running",
        "skipped",
        "done",
        "failed",
    ] = "not_started"
    required: bool = False
    summary_ref: str | None = Field(default=None, min_length=1)
    file_rollup_ref: str | None = Field(default=None, min_length=1)
    context_summary_ref: str | None = Field(default=None, min_length=1)
    warnings: tuple[str, ...] = ()


class PlanOutcomeView(UiContractModel):
    status: Literal[
        "succeeded",
        "succeeded_with_warnings",
        "partially_completed",
        "failed",
        "cancelled",
    ]
    summary: str = Field(min_length=1)
    completed_task_count: int = Field(default=0, ge=0)
    failed_task_count: int = Field(default=0, ge=0)
    skipped_task_count: int = Field(default=0, ge=0)
    result_ref: str | None = Field(default=None, min_length=1)
    file_change_summary_ref: str | None = Field(default=None, min_length=1)
    audit_summary_ref: str | None = Field(default=None, min_length=1)


class PlanPermissions(UiContractModel):
    can_edit: bool = False
    can_publish: bool = False
    can_append_guidance: bool = False
    can_create_task_node: bool = False
    can_delete_task_node: bool = False
    can_request_execution: bool = False
    readonly_reason: str | None = Field(default=None, min_length=1)


class PlanView(UiContractModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    status: PlanUiStatus = "unknown"
    task_count: int = Field(default=0, ge=0)
    task_node_ids: tuple[str, ...] = ()
    task_nodes: tuple[TaskNodeCardView, ...] = ()
    execution_rollup: ExecutionRollupView = Field(default_factory=ExecutionRollupView)
    finalization: PlanFinalizationView = Field(default_factory=PlanFinalizationView)
    outcome: PlanOutcomeView | None = None
    permissions: PlanPermissions = Field(default_factory=PlanPermissions)
    task_tree_projection: TaskTreeView | None = None
    source_kind: Literal[
        "plan_store",
        "legacy_draft_tree",
        "legacy_published_task_tree",
        "synthetic",
    ] = "synthetic"
    source_ref: ObjectRef | None = None
    version: int = Field(default=1, ge=1)
    archived_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_task_identity(self) -> PlanView:
        ids = tuple(node.id for node in self.task_nodes)
        if self.task_nodes and self.task_node_ids and ids != self.task_node_ids:
            raise ValueError("PlanView task_nodes must match task_node_ids order")
        if self.task_nodes and self.task_count != len(self.task_nodes):
            raise ValueError("PlanView task_count must match task_nodes length")
        if not self.task_nodes and self.task_node_ids and self.task_count != len(
            self.task_node_ids
        ):
            raise ValueError("PlanView task_count must match task_node_ids length")
        if len(self.task_node_ids) != len(set(self.task_node_ids)):
            raise ValueError("PlanView task_node_ids must be unique")
        return self


class SessionActivityRefView(UiContractModel):
    kind: SessionActivityRefKind
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    href: str | None = Field(default=None, min_length=1)
    object_ref: ObjectRef | None = None


class ConversationTextView(UiContractModel):
    title: str | None = Field(default=None, min_length=1)
    body: str = Field(min_length=1)


class ConversationRouterTraceView(UiContractModel):
    intent: str = Field(min_length=1)
    scope_kind: SessionActivityScopeKind
    confidence: str = Field(min_length=1)
    side_effect: SessionActivitySideEffect
    dispatch_target: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    outcome_status: str = Field(min_length=1)


class ConversationQuestionInputView(UiContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    input_hint: str | None = Field(default=None, min_length=1)
    required: bool = True


class ConversationQuestionOptionView(UiContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str | None = Field(default=None, min_length=1)


class ConversationQuestionCardView(UiContractModel):
    card_id: str = Field(min_length=1)
    card_kind: ConversationQuestionCardKind
    status: ConversationQuestionCardStatus
    title: str = Field(min_length=1)
    body: str | None = Field(default=None, min_length=1)
    questions: tuple[ConversationQuestionInputView, ...] = ()
    options: tuple[ConversationQuestionOptionView, ...] = ()
    answer_mode: ConversationQuestionAnswerMode
    target_ref: SessionActivityRefView | None = None


class ConversationRenderView(UiContractModel):
    protocol_version: Literal["plato.conversation.render.v1"] = (
        "plato.conversation.render.v1"
    )
    render_kind: ConversationRenderKind
    text: ConversationTextView | None = None
    router_trace: ConversationRouterTraceView | None = None
    question_card: ConversationQuestionCardView | None = None


class SessionMessageView(UiContractModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_node_id: str | None = None
    task_ref: TaskRef | None = None
    kind: MessageKind
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utcnow)
    related_confirmation_id: str | None = None
    related_command_id: str | None = None
    activity_related_refs: tuple[SessionActivityRefView, ...] = ()
    conversation_render: ConversationRenderView | None = None


class SessionActivityItemView(UiContractModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    kind: SessionActivityItemKind
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=utcnow)
    scope_kind: SessionActivityScopeKind
    plan_id: str | None = Field(default=None, min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)
    side_effect: SessionActivitySideEffect = "no_effect"
    related_refs: tuple[SessionActivityRefView, ...] = ()
    source_kind: SessionActivitySourceKind
    source_id: str | None = Field(default=None, min_length=1)
    disclosure_level: SessionActivityDisclosureLevel = "public"

    @model_validator(mode="after")
    def _validate_scope_identity(self) -> SessionActivityItemView:
        if self.scope_kind == "task" and self.task_node_id is None:
            raise ValueError("task-scoped Activity item requires task_node_id")
        if self.scope_kind == "plan" and self.plan_id is None:
            raise ValueError("plan-scoped Activity item requires plan_id")
        return self


class SessionActivityTimelineResult(UiContractModel):
    session_id: str = Field(min_length=1)
    items: tuple[SessionActivityItemView, ...] = ()
    next_cursor: str | None = None
    total_count: int = Field(default=0, ge=0)
    generated_at: datetime = Field(default_factory=utcnow)


class ConfirmationOptionView(UiContractModel):
    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    tone: Literal["primary", "secondary", "danger"] | None = None


class ConfirmationActionView(UiContractModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_node_id: str = Field(min_length=1)
    task_ref: TaskRef | None = None
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    options: tuple[ConfirmationOptionView, ...] = ()
    default_option_value: str | None = None
    status: Literal["pending", "resolved", "expired"] = "pending"
    risk_label: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_resolution(self) -> ConfirmationActionView:
        if self.status == "resolved" and self.resolved_at is None:
            raise ValueError("resolved confirmation requires resolved_at")
        return self


class ValidationSummaryView(UiContractModel):
    state: Literal["not_started", "running", "passed", "warning", "failed"]
    summary: str = Field(min_length=1)
    issues: tuple[str, ...] = ()


class PlanningAskView(UiContractModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required: bool = True
    options: tuple[ConfirmationOptionView, ...] = ()
    status: Literal["pending", "answered", "expired", "superseded"] = "pending"


class PlanningDiagnosticView(UiContractModel):
    code: Literal["dirty_authoring_state", "authoring_state_cancelled"]
    severity: Literal["info", "warning"]
    message: str = Field(min_length=1)


class PlanningView(UiContractModel):
    state: PlanningState
    source_raw_task_id: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    asks: tuple[PlanningAskView, ...] = ()
    validation: ValidationSummaryView | None = None
    diagnostics: tuple[PlanningDiagnosticView, ...] = ()


class AskOptionView(UiContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str | None = None


class AskQuestionView(UiContractModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    input_hint: str | None = Field(default=None, min_length=1)
    required: bool = True


class AskRequestView(UiContractModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_node_id: str | None = Field(default=None, min_length=1)
    task_ref: TaskRef | None = None
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    questions: tuple[AskQuestionView, ...] = ()
    suggested_options: tuple[AskOptionView, ...] = ()
    answer_type: AskAnswerType
    allow_free_text: bool
    allow_no_option_with_text: bool
    blocking: bool
    attachments_supported: Literal[False] = False
    status: AskRequestStatus
    answer_id: str | None = Field(default=None, min_length=1)
    resume_hint: str | None = Field(default=None, min_length=1)
    created_at: datetime
    answered_at: datetime | None = None
    deferred_at: datetime | None = None
    cancelled_at: datetime | None = None
    expired_at: datetime | None = None


class AskListResult(UiContractModel):
    session_id: str = Field(min_length=1)
    asks: tuple[AskRequestView, ...] = ()
    active_ask: AskRequestView | None = None


class ResultSectionView(UiContractModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    kind: Literal["text", "list", "metric", "link"] | None = None


class ResultCardView(UiContractModel):
    id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_node_id: str | None = None
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    sections: tuple[ResultSectionView, ...] = ()
    updated_at: datetime = Field(default_factory=utcnow)


class FileChangeItemView(UiContractModel):
    path: str = Field(min_length=1)
    change_type: Literal["created", "modified", "deleted", "renamed"]
    summary: str | None = None
    owner_task_node_id: str | None = None


class FileChangeSummaryView(UiContractModel):
    session_id: str = Field(min_length=1)
    task_node_id: str | None = None
    recursive: bool
    changed_files: tuple[FileChangeItemView, ...] = ()
    summary: str = Field(min_length=1)
    updated_at: datetime = Field(default_factory=utcnow)


class AuditLinkView(UiContractModel):
    label: str = Field(min_length=1)
    href: str = Field(min_length=1)
    severity: Literal["info", "warning", "danger"] | None = None


AuditVerdict = Literal[
    "passed",
    "warning",
    "failed",
    "inconclusive",
    "not_available",
]
AuditCompleteness = Literal[
    "not_started",
    "running",
    "partial",
    "complete",
    "failed",
    "hidden",
]
AuditFilterKind = Literal[
    "all",
    "confirmations",
    "actions",
    "risks",
    "files",
    "results",
    "system",
    "config",
    "logs",
]
AuditRecordKind = Literal[
    "confirmation",
    "action",
    "observation",
    "risk",
    "file_change",
    "result",
    "message",
    "config_change",
    "audit_verdict",
    "system",
    "log_evidence",
]
AuditActorKind = Literal["user", "agent", "tool", "system", "audit_agent"]
AuditSeverity = Literal["info", "success", "warning", "danger"]
AuditConfidence = Literal["high", "medium", "low", "unknown"]
EvidenceKind = Literal[
    "message",
    "event",
    "action",
    "observation",
    "file_change",
    "result",
    "audit_observation",
    "config_snapshot",
    "log_excerpt",
]
AuditEvidenceSource = Literal[
    "event_stream",
    "message_stream",
    "task_projection",
    "workspace_inspection",
    "audit_agent",
    "config_store",
    "log_archive",
    "mock",
]


class AuditSessionScope(UiContractModel):
    kind: Literal["session"] = "session"
    session_id: str = Field(min_length=1)


class AuditWorkflowScope(UiContractModel):
    kind: Literal["workflow"] = "workflow"
    workflow_id: str = Field(min_length=1)
    project_id: str | None = None


class AuditTaskScope(UiContractModel):
    kind: Literal["task"] = "task"
    session_id: str = Field(min_length=1)
    task_node_id: str = Field(min_length=1)
    task_ref: TaskRef | None = None


class AuditActionScope(UiContractModel):
    kind: Literal["action"] = "action"
    session_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    task_node_id: str | None = None


class AuditConfirmationScope(UiContractModel):
    kind: Literal["confirmation"] = "confirmation"
    session_id: str = Field(min_length=1)
    confirmation_id: str = Field(min_length=1)
    task_node_id: str | None = None


class AuditFileScope(UiContractModel):
    kind: Literal["file"] = "file"
    session_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    task_node_id: str | None = None


class AuditResultScope(UiContractModel):
    kind: Literal["result"] = "result"
    session_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    task_node_id: str | None = None


class AuditConfigScope(UiContractModel):
    kind: Literal["config"] = "config"
    session_id: str | None = None
    workflow_id: str | None = None
    config_key: str | None = None

    @model_validator(mode="after")
    def _validate_anchor(self) -> AuditConfigScope:
        if self.session_id is None and self.workflow_id is None and self.config_key is None:
            raise ValueError("config audit scope requires session_id, workflow_id, or config_key")
        return self


class AuditLogEvidenceScope(UiContractModel):
    kind: Literal["log_evidence"] = "log_evidence"
    session_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    task_node_id: str | None = None


type AuditScope = Annotated[
    AuditSessionScope
    | AuditWorkflowScope
    | AuditTaskScope
    | AuditActionScope
    | AuditConfirmationScope
    | AuditFileScope
    | AuditResultScope
    | AuditConfigScope
    | AuditLogEvidenceScope,
    Field(discriminator="kind"),
]


class AuditEntryContext(UiContractModel):
    kind: Literal[
        "from_session",
        "from_task",
        "from_confirmation",
        "from_result",
        "from_file_change",
    ]
    session_id: str = Field(min_length=1)
    task_node_id: str | None = None
    task_ref: TaskRef | None = None
    confirmation_id: str | None = None
    result_id: str | None = None
    file_path: str | None = None
    source_route: str = Field(min_length=1)
    preferred_filter: AuditFilterKind | None = None
    preferred_record_id: str | None = None


class MainPageReturnTarget(UiContractModel):
    route_name: Literal["main.session", "main.sessionFallback"]
    session_id: str = Field(min_length=1)
    project_id: str | None = None
    workflow_id: str | None = None
    task_node_id: str | None = None
    focus: Literal["session", "task", "confirmation", "result", "file_change"]
    record_id: str | None = None


class AuditPageRequestView(UiContractModel):
    filter: AuditFilterKind = "all"
    record_id: str | None = None
    include_detail: bool = False
    include_sanitized_payload: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None


class AuditOverview(UiContractModel):
    verdict: AuditVerdict
    completeness: AuditCompleteness
    summary: str = Field(min_length=1)
    key_issue: str | None = None
    record_counts: dict[AuditFilterKind, int] = Field(default_factory=dict)
    important_record_ids: tuple[str, ...] = ()
    hidden_evidence_count: int = Field(default=0, ge=0)
    partial_reason: str | None = None
    generated_by: Literal["audit_agent", "projection", "rules", "mock"]
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("record_counts")
    @classmethod
    def _validate_record_counts(
        cls,
        value: dict[AuditFilterKind, int],
    ) -> dict[AuditFilterKind, int]:
        negative_counts = [count for count in value.values() if count < 0]
        if negative_counts:
            raise ValueError("audit record counts must be non-negative")
        return value


class AuditFilterView(UiContractModel):
    kind: AuditFilterKind
    label: str = Field(min_length=1)
    count: int = Field(default=0, ge=0)
    enabled: bool = True
    disabled_reason: str | None = None


class AuditLoadingPageState(UiContractModel):
    kind: Literal["loading"] = "loading"
    message: str = Field(min_length=1)


class AuditReadyPageState(UiContractModel):
    kind: Literal["ready"] = "ready"


class AuditEmptyPageState(UiContractModel):
    kind: Literal["empty"] = "empty"
    reason: str = Field(min_length=1)


class AuditPartialPageState(UiContractModel):
    kind: Literal["partial"] = "partial"
    reason: str = Field(min_length=1)


class AuditHiddenEvidencePageState(UiContractModel):
    kind: Literal["hidden_evidence"] = "hidden_evidence"
    reason: str = Field(min_length=1)
    hidden_count: int = Field(ge=1)


class AuditPermissionDeniedPageState(UiContractModel):
    kind: Literal["permission_denied"] = "permission_denied"
    reason: str = Field(min_length=1)


class AuditErrorPageState(UiContractModel):
    kind: Literal["error"] = "error"
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False


class AuditStalePageState(UiContractModel):
    kind: Literal["stale"] = "stale"
    reason: str = Field(min_length=1)


type AuditPageState = Annotated[
    AuditLoadingPageState
    | AuditReadyPageState
    | AuditEmptyPageState
    | AuditPartialPageState
    | AuditHiddenEvidencePageState
    | AuditPermissionDeniedPageState
    | AuditErrorPageState
    | AuditStalePageState,
    Field(discriminator="kind"),
]


class AuditPermissions(UiContractModel):
    can_view_audit: bool = True
    can_view_evidence: bool = True
    can_view_hidden_evidence_reason: bool = False
    can_open_related_logs: bool = False
    readonly_reason: str | None = None


class EvidenceRef(UiContractModel):
    id: str = Field(min_length=1)
    kind: EvidenceKind
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    available: bool = True
    hidden: bool = False
    redacted: bool = False


class AuditRecordFlags(UiContractModel):
    partial: bool = False
    hidden: bool = False
    redacted: bool = False
    stale: bool = False
    user_visible: bool = True


class AuditRecord(UiContractModel):
    id: str = Field(min_length=1)
    scope: AuditScope
    kind: AuditRecordKind
    filter_kind: AuditFilterKind

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    actor: AuditActorKind
    source_label: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=utcnow)

    severity: AuditSeverity = "info"
    confidence: AuditConfidence = "unknown"
    verdict: AuditVerdict | None = None
    completeness: AuditCompleteness = "complete"

    task_node_id: str | None = None
    task_ref: TaskRef | None = None
    action_id: str | None = None
    confirmation_id: str | None = None
    result_id: str | None = None
    file_path: str | None = None
    config_key: str | None = None

    evidence_refs: tuple[EvidenceRef, ...] = ()
    related_record_ids: tuple[str, ...] = ()
    flags: AuditRecordFlags = Field(default_factory=AuditRecordFlags)


class AuditReference(UiContractModel):
    kind: Literal[
        "task",
        "message",
        "confirmation",
        "action",
        "observation",
        "file",
        "result",
        "config",
        "log",
        "external",
    ]
    label: str = Field(min_length=1)
    href: str | None = None
    ref: ObjectRef | None = None


class AuditDisclosure(UiContractModel):
    raw_payload_available: bool = False
    raw_payload_shown: bool = False
    redaction_reason: str | None = None
    hidden_reason: str | None = None
    partial_reason: str | None = None
    permission_reason: str | None = None

    @model_validator(mode="after")
    def _validate_raw_payload_disclosure(self) -> AuditDisclosure:
        if self.raw_payload_shown and not self.raw_payload_available:
            raise ValueError("shown raw payload must also be available")
        return self


class EvidenceSummary(EvidenceRef):
    source: AuditEvidenceSource
    occurred_at: datetime | None = None


class SanitizedRawPayload(UiContractModel):
    format: Literal["json", "text"]
    content: str = Field(min_length=1)
    redactions: tuple[str, ...] = ()


class EvidenceDetail(EvidenceSummary):
    body: str = Field(min_length=1)
    sanitized_payload: SanitizedRawPayload | None = None
    disclosure: AuditDisclosure = Field(default_factory=AuditDisclosure)

    @model_validator(mode="after")
    def _validate_payload_matches_disclosure(self) -> EvidenceDetail:
        if self.sanitized_payload is not None and not self.disclosure.raw_payload_shown:
            raise ValueError("sanitized payload requires raw_payload_shown disclosure")
        if self.disclosure.raw_payload_shown and self.sanitized_payload is None:
            raise ValueError("raw_payload_shown disclosure requires sanitized payload")
        return self


class RelatedLogsLink(UiContractModel):
    label: str = Field(min_length=1)
    href: str = Field(min_length=1)
    filters: dict[str, str | None] = Field(default_factory=dict)
    enabled: bool = True
    disabled_reason: str | None = None


class AuditRecordDetail(AuditRecord):
    body: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    outcome: str | None = None
    references: tuple[AuditReference, ...] = ()
    evidence: tuple[EvidenceSummary, ...] = ()
    disclosure: AuditDisclosure = Field(default_factory=AuditDisclosure)
    related_logs: tuple[RelatedLogsLink, ...] = ()
    raw_payload: SanitizedRawPayload | None = None

    @model_validator(mode="after")
    def _validate_payload_matches_disclosure(self) -> AuditRecordDetail:
        if self.raw_payload is not None and not self.disclosure.raw_payload_shown:
            raise ValueError("raw payload requires raw_payload_shown disclosure")
        if self.disclosure.raw_payload_shown and self.raw_payload is None:
            raise ValueError("raw_payload_shown disclosure requires raw payload")
        return self


class AuditRecordsResult(UiContractModel):
    records: tuple[AuditRecord, ...] = ()
    next_cursor: str | None = None
    total_count: int | None = Field(default=None, ge=0)


class EffectiveConfigSummary(UiContractModel):
    summary: str = Field(min_length=1)
    profile_label: str = Field(min_length=1)
    effective_at: datetime = Field(default_factory=utcnow)
    relevant_record_ids: tuple[str, ...] = ()
    settings_href: str | None = None
