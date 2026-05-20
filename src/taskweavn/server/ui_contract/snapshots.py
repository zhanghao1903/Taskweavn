"""Snapshot query models for Plato Main Page."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from taskweavn.server.ui_contract.base import UiContractModel, utcnow
from taskweavn.server.ui_contract.view_models import (
    AuditLinkView,
    ConfirmationActionView,
    FileChangeSummaryView,
    ProjectSummary,
    ResultCardView,
    SessionMessageView,
    SessionSummary,
    TaskTreeView,
    WorkflowSummary,
)


class MainPageSnapshot(UiContractModel):
    project: ProjectSummary
    workflows: tuple[WorkflowSummary, ...] = Field(min_length=1)
    workflow: WorkflowSummary
    sessions: tuple[SessionSummary, ...] = Field(min_length=1)
    session: SessionSummary
    task_tree: TaskTreeView | None = None
    messages: tuple[SessionMessageView, ...] = ()
    pending_confirmations: tuple[ConfirmationActionView, ...] = ()
    result: ResultCardView | None = None
    file_change_summary: FileChangeSummaryView | None = None
    audit_links: tuple[AuditLinkView, ...] = ()
    cursor: str | None = None
    generated_at: datetime = Field(default_factory=utcnow)
