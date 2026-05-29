"""Server-core projection/read models for Task-first views.

These are not backend Task facts and not transport-facing UI contracts. They
are stable server-core read models projected
from TaskDomain, DraftTaskNode, MessageStream, confirmations, files, summaries,
and permission rules. The Plato API layer maps them into
``taskweavn.server.ui_contract`` models before exposing JSON to the frontend.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.task.models import TaskRef

TaskViewStatus = Literal["draft", "pending", "running", "done", "failed", "cancelled"]
TaskCardActionKind = Literal[
    "confirm",
    "edit",
    "append_guidance",
    "publish",
    "cancel",
    "retry",
    "open_detail",
]
TaskMessageViewType = Literal["user", "agent", "system", "confirmation", "result"]
FileChangeType = Literal["created", "modified", "deleted", "renamed", "unknown"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class _FrozenView(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class TaskCardBadges(_FrozenView):
    pending_confirmation_count: int = Field(default=0, ge=0)
    unread_message_count: int = Field(default=0, ge=0)
    direct_file_change_count: int = Field(default=0, ge=0)
    subtree_file_change_count: int = Field(default=0, ge=0)
    child_count: int = Field(default=0, ge=0)
    done_child_count: int = Field(default=0, ge=0)
    failed_child_count: int = Field(default=0, ge=0)
    risk_level: str | None = None

    @model_validator(mode="after")
    def _validate_child_counts(self) -> TaskCardBadges:
        if self.done_child_count + self.failed_child_count > self.child_count:
            raise ValueError("done_child_count + failed_child_count must be <= child_count")
        return self


class TaskCardPermissions(_FrozenView):
    can_edit: bool = False
    can_append_guidance: bool = False
    can_resolve_confirmation: bool = False
    can_publish: bool = False
    can_cancel: bool = False
    can_retry: bool = False
    readonly_reason: str | None = None


class TaskCardAction(_FrozenView):
    action_id: str = Field(default_factory=_new_id, min_length=1)
    kind: TaskCardActionKind
    label: str = Field(min_length=1)
    disabled: bool = False
    reason: str | None = None


class TaskProgressView(_FrozenView):
    child_count: int = Field(default=0, ge=0)
    done_child_count: int = Field(default=0, ge=0)
    failed_child_count: int = Field(default=0, ge=0)
    running_child_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_child_counts(self) -> TaskProgressView:
        total_known = (
            self.done_child_count + self.failed_child_count + self.running_child_count
        )
        if total_known > self.child_count:
            raise ValueError("known child counts must be <= child_count")
        return self


class ConfirmationOptionView(_FrozenView):
    option_id: str = Field(default_factory=_new_id, min_length=1)
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    description: str | None = None
    is_default: bool = False


class ConfirmationActionView(_FrozenView):
    confirmation_id: str = Field(default_factory=_new_id, min_length=1)
    task_ref: TaskRef
    prompt: str = Field(min_length=1)
    options: tuple[ConfirmationOptionView, ...] = Field(default_factory=tuple)
    default_option_id: str | None = Field(default=None, min_length=1)
    risk_summary: str | None = None
    status: Literal["pending", "resolved", "expired"] = "pending"

    @model_validator(mode="after")
    def _validate_default_option(self) -> ConfirmationActionView:
        if self.default_option_id is None:
            return self
        option_ids = {option.option_id for option in self.options}
        if self.default_option_id not in option_ids:
            raise ValueError("default_option_id must reference one of options")
        return self


class SessionMessageView(_FrozenView):
    message_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    task_ref: TaskRef | None = None
    message_type: TaskMessageViewType
    content_summary: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)
    related_confirmation_id: str | None = None
    related_action_id: str | None = None


class TaskFileChangeSummary(_FrozenView):
    change_id: str = Field(default_factory=_new_id, min_length=1)
    owner_task_ref: TaskRef
    path: str = Field(min_length=1)
    change_type: FileChangeType = "unknown"
    summary: str = Field(min_length=1)
    from_subtree: bool = False
    recorded_at: datetime = Field(default_factory=_utcnow)


class TaskSummaryView(_FrozenView):
    task_ref: TaskRef
    summary: str = Field(min_length=1)
    failure_reason: str | None = None
    follow_up_suggestions: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    updated_at: datetime = Field(default_factory=_utcnow)


class TaskCardView(_FrozenView):
    task_ref: TaskRef
    parent_ref: TaskRef | None = None
    root_ref: TaskRef

    title: str = Field(min_length=1)
    intent_preview: str = Field(min_length=1)
    status: TaskViewStatus
    depth: int = Field(default=0, ge=0)
    order_index: int = Field(default=0, ge=0)
    result_ref: str | None = Field(default=None, min_length=1)
    error_ref: str | None = Field(default=None, min_length=1)

    badges: TaskCardBadges = Field(default_factory=TaskCardBadges)
    permissions: TaskCardPermissions = Field(default_factory=TaskCardPermissions)
    primary_actions: tuple[TaskCardAction, ...] = Field(default_factory=tuple)

    confirmation: ConfirmationActionView | None = None
    latest_message: SessionMessageView | None = None
    file_summary: TaskFileChangeSummary | None = None
    progress: TaskProgressView | None = None

    @model_validator(mode="after")
    def _validate_refs(self) -> TaskCardView:
        if self.depth == 0 and self.parent_ref is not None:
            raise ValueError("root card must not have parent_ref")
        if self.depth > 0 and self.parent_ref is None:
            raise ValueError("non-root card must have parent_ref")
        if self.status == "draft" and self.task_ref.kind != "draft":
            raise ValueError("draft status requires a draft task_ref")
        return self


class TaskTreeView(_FrozenView):
    session_id: str = Field(min_length=1)
    nodes: tuple[TaskCardView, ...] = Field(default_factory=tuple)
    generated_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _validate_unique_nodes(self) -> TaskTreeView:
        seen: set[tuple[str, str]] = set()
        for node in self.nodes:
            key = (node.task_ref.kind, node.task_ref.id)
            if key in seen:
                raise ValueError("TaskTreeView nodes must have unique task_ref values")
            seen.add(key)
        return self


class TaskDetailView(_FrozenView):
    card: TaskCardView
    full_intent: str = Field(min_length=1)
    constraints: tuple[str, ...] = ()
    messages: tuple[SessionMessageView, ...] = ()
    confirmations: tuple[ConfirmationActionView, ...] = ()
    file_changes: tuple[TaskFileChangeSummary, ...] = ()
    result_summary: TaskSummaryView | None = None
    timeline_cursor: str | None = None
