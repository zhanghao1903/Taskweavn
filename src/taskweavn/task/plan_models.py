"""Durable Plan and TaskNode domain models.

These models are storage-facing Product 1.1 facts. They intentionally sit
beside, rather than inside, the legacy DraftTaskTree models so the migration can
add durable Plan storage without changing the existing DraftTaskTree read path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.task.models import TaskRef

PlanStatus = Literal[
    "draft",
    "reviewing",
    "approved",
    "published",
    "running",
    "finalizing",
    "awaiting_acceptance",
    "accepted",
    "follow_up_needed",
    "failed",
    "cancelled",
    "archived",
]
PlanFinalizationStatus = Literal[
    "not_started",
    "pending",
    "running",
    "skipped",
    "done",
    "failed",
]
PlanOutcomeStatus = Literal[
    "succeeded",
    "succeeded_with_warnings",
    "partially_completed",
    "failed",
    "cancelled",
]
PlanSuggestedNextActionKind = Literal[
    "follow_up_plan",
    "open_file",
    "open_audit",
    "custom",
]
PlanTaskNodeReadiness = Literal[
    "draft",
    "reviewing",
    "approved",
    "published",
    "cancelled",
    "unknown",
]
PlanTaskNodeExecutionStatus = Literal[
    "not_started",
    "pending",
    "running",
    "waiting_for_user",
    "done",
    "failed",
    "cancelled",
    "unknown",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class _FrozenPlanModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class PlanContextPolicy(_FrozenPlanModel):
    include_prior_plan_summaries: bool = True
    include_session_guidance: bool = True
    include_completed_task_summaries: bool = True
    include_file_change_rollup: bool = True
    max_prior_plan_summaries: int = Field(default=3, ge=0)
    context_budget_hint: int | None = Field(default=None, ge=1)


class PlanFinalizationState(_FrozenPlanModel):
    status: PlanFinalizationStatus = "not_started"
    required: bool = True
    result_summary_id: str | None = Field(default=None, min_length=1)
    file_rollup_id: str | None = Field(default=None, min_length=1)
    context_summary_id: str | None = Field(default=None, min_length=1)
    warnings: tuple[str, ...] = ()


class PlanSuggestedNextAction(_FrozenPlanModel):
    kind: PlanSuggestedNextActionKind = "custom"
    label: str = Field(min_length=1)
    ref: str | None = Field(default=None, min_length=1)


class PlanOutcome(_FrozenPlanModel):
    status: PlanOutcomeStatus
    summary: str = Field(min_length=1)
    completed_task_count: int = Field(default=0, ge=0)
    failed_task_count: int = Field(default=0, ge=0)
    skipped_task_count: int = Field(default=0, ge=0)
    file_change_summary_id: str | None = Field(default=None, min_length=1)
    audit_summary_id: str | None = Field(default=None, min_length=1)
    suggested_next_actions: tuple[PlanSuggestedNextAction, ...] = ()
    created_at: datetime = Field(default_factory=_utcnow)


class Plan(_FrozenPlanModel):
    plan_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    source_raw_task_id: str | None = Field(default=None, min_length=1)
    source_draft_tree_id: str | None = Field(default=None, min_length=1)

    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    status: PlanStatus = "draft"
    version: int = Field(default=1, ge=1)
    task_node_ids: tuple[str, ...] = ()

    context_policy: PlanContextPolicy = Field(default_factory=PlanContextPolicy)
    finalization: PlanFinalizationState = Field(default_factory=PlanFinalizationState)
    outcome: PlanOutcome | None = None

    created_by: str = Field(default="collaborator_agent", min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    archived_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_timestamps(self) -> Plan:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if self.archived_at is not None and self.archived_at < self.created_at:
            raise ValueError("archived_at must be >= created_at")
        return self


class PlanTaskNode(_FrozenPlanModel):
    task_node_id: str = Field(default_factory=_new_id, min_length=1)
    plan_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)

    task_index: str = Field(min_length=1)
    order_index: int = Field(default=0, ge=0)
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    instructions: str = ""

    required_capability: str | None = Field(default=None, min_length=1)
    depends_on: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()

    readiness: PlanTaskNodeReadiness = "draft"
    execution: PlanTaskNodeExecutionStatus = "not_started"
    draft_ref: TaskRef | None = None
    published_ref: TaskRef | None = None
    result_ref: str | None = Field(default=None, min_length=1)
    error_ref: str | None = Field(default=None, min_length=1)
    file_summary_ref: str | None = Field(default=None, min_length=1)
    audit_ref: str | None = Field(default=None, min_length=1)

    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _validate_timestamps_and_dependencies(self) -> PlanTaskNode:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if self.task_node_id in self.depends_on:
            raise ValueError("PlanTaskNode must not depend on itself")
        return self


__all__ = [
    "Plan",
    "PlanContextPolicy",
    "PlanFinalizationState",
    "PlanFinalizationStatus",
    "PlanOutcome",
    "PlanOutcomeStatus",
    "PlanStatus",
    "PlanSuggestedNextAction",
    "PlanSuggestedNextActionKind",
    "PlanTaskNode",
    "PlanTaskNodeExecutionStatus",
    "PlanTaskNodeReadiness",
]
