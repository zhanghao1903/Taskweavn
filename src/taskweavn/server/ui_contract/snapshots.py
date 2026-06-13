"""Snapshot query models for Plato Main Page and Audit Page."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from taskweavn.server.ui_contract.base import UiContractModel, utcnow
from taskweavn.server.ui_contract.plan_projection import DefaultPlanProjectionService
from taskweavn.server.ui_contract.view_models import (
    AskRequestView,
    AuditEntryContext,
    AuditFilterView,
    AuditLinkView,
    AuditOverview,
    AuditPageRequestView,
    AuditPageState,
    AuditPermissions,
    AuditReadyPageState,
    AuditRecord,
    AuditRecordDetail,
    AuditScope,
    ConfirmationActionView,
    EffectiveConfigSummary,
    FileChangeSummaryView,
    MainPageReturnTarget,
    PlanningView,
    PlanView,
    ProjectSummary,
    RelatedLogsLink,
    ResultCardView,
    SessionMessageView,
    SessionSummary,
    TaskNodeCardView,
    TaskTreeView,
    WorkflowSummary,
)


class MainPageSnapshot(UiContractModel):
    project: ProjectSummary
    workflows: tuple[WorkflowSummary, ...] = Field(min_length=1)
    workflow: WorkflowSummary
    sessions: tuple[SessionSummary, ...] = Field(min_length=1)
    session: SessionSummary
    planning: PlanningView | None = None
    active_plan: PlanView | None = None
    task_tree: TaskTreeView | None = None
    messages: tuple[SessionMessageView, ...] = ()
    pending_confirmations: tuple[ConfirmationActionView, ...] = ()
    pending_asks: tuple[AskRequestView, ...] = ()
    active_ask: AskRequestView | None = None
    result: ResultCardView | None = None
    file_change_summary: FileChangeSummaryView | None = None
    audit_links: tuple[AuditLinkView, ...] = ()
    cursor: str | None = None
    generated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="before")
    @classmethod
    def _populate_active_plan(
        cls,
        values: Any,
    ) -> Any:
        if not isinstance(values, dict):
            return values
        if values.get("active_plan") is not None or values.get("activePlan") is not None:
            return values
        task_tree_value = values.get("task_tree", values.get("taskTree"))
        if task_tree_value is None:
            return values
        task_tree = (
            task_tree_value
            if isinstance(task_tree_value, TaskTreeView)
            else TaskTreeView.model_validate(task_tree_value)
        )
        active_plan = DefaultPlanProjectionService().project_legacy_task_tree(task_tree)
        task_tree_key = "task_tree" if "task_tree" in values else "taskTree"
        return {
            **values,
            "active_plan": active_plan,
            task_tree_key: active_plan.task_tree_projection,
        }


class AuditPageSnapshot(UiContractModel):
    schema_version: Literal["plato.audit.v1"] = "plato.audit.v1"
    request: AuditPageRequestView = Field(default_factory=AuditPageRequestView)
    scope: AuditScope
    entry_context: AuditEntryContext
    return_target: MainPageReturnTarget

    project: ProjectSummary | None = None
    workflow: WorkflowSummary | None = None
    session: SessionSummary
    selected_task: TaskNodeCardView | None = None

    overview: AuditOverview
    filters: tuple[AuditFilterView, ...] = ()
    records: tuple[AuditRecord, ...] = ()
    selected_record: AuditRecordDetail | None = None

    effective_config: EffectiveConfigSummary | None = None
    related_logs: tuple[RelatedLogsLink, ...] = ()
    permissions: AuditPermissions = Field(default_factory=AuditPermissions)
    page_state: AuditPageState = Field(default_factory=AuditReadyPageState)

    cursor: str | None = None
    generated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _validate_selected_record_matches_request(self) -> AuditPageSnapshot:
        if (
            self.request.record_id is not None
            and self.selected_record is not None
            and self.selected_record.id != self.request.record_id
        ):
            raise ValueError("selected_record must match request.record_id")
        return self
