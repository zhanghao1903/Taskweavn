"""Transport-facing ViewModels consumed by the Plato frontend."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from taskweavn.server.ui_contract.base import UiContractModel, utcnow
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
TaskTreeStatus = Literal["draft", "published", "running", "completed", "failed"]
TaskNodeStatus = Literal[
    "draft",
    "queued",
    "running",
    "waiting_user",
    "done",
    "failed",
    "cancelled",
]
MessageKind = Literal["informational", "actionable", "response", "error"]


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
    task_ref: TaskRef | None = None
    parent_id: str | None = None
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    status: TaskNodeStatus
    depth: int = Field(default=0, ge=0)
    order_index: int = Field(default=0, ge=0)
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
    status: TaskTreeStatus
    nodes: tuple[TaskNodeCardView, ...] = ()
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate_unique_nodes(self) -> TaskTreeView:
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("TaskTreeView nodes must have unique ids")
        return self


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
