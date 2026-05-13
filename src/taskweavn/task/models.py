"""Task domain and draft-task models.

These models intentionally stop before UI projection. ``TaskDomain`` is the
published execution fact used by TaskBus and Agents. ``DraftTaskNode`` and
``DraftTaskTree`` represent user/collaborator authoring facts before publish.
UI cards should be projected from these facts rather than stored here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskStatus = Literal["pending", "running", "done", "failed"]
DraftTaskStatus = Literal["draft", "accepted", "published", "cancelled"]
TaskRefKind = Literal["draft", "published"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class TaskRef(_FrozenModel):
    """Stable UI/projection reference to either a draft or published task."""

    kind: TaskRefKind
    id: str = Field(min_length=1)

    @classmethod
    def draft(cls, draft_task_id: str) -> TaskRef:
        return cls(kind="draft", id=draft_task_id)

    @classmethod
    def published(cls, task_id: str) -> TaskRef:
        return cls(kind="published", id=task_id)


class TaskDispatchConstraints(_FrozenModel):
    """Optional dispatch hints for future TaskBus/Agent assignment work.

    The model is deliberately small in Slice 1. It records assignment intent
    without changing TaskBus claim semantics yet.
    """

    required_agent_id: str | None = Field(default=None, min_length=1)
    preferred_agent_id: str | None = Field(default=None, min_length=1)
    required_capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskDomain(_FrozenModel):
    """Published backend Task fact.

    This object is execution/scheduling state. It should not contain card
    badges, selected/expanded state, unread counters, or UI action layout.
    """

    task_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    parent_id: str | None = Field(default=None, min_length=1)
    root_id: str = Field(min_length=1)
    order_index: int = Field(default=0, ge=0)

    intent: str = Field(min_length=1)
    required_capability: str = Field(min_length=1)
    dispatch_constraints: TaskDispatchConstraints | None = None

    status: TaskStatus = "pending"
    result_ref: str | None = Field(default=None, min_length=1)
    error_ref: str | None = Field(default=None, min_length=1)

    created_by: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_root(self) -> TaskDomain:
        if self.parent_id is None and self.root_id != self.task_id:
            raise ValueError("root task must have root_id == task_id")
        return self


class TaskNodePatch(_FrozenModel):
    """Patch shape shared by draft editing and pending Task editing commands."""

    title: str | None = Field(default=None, min_length=1)
    intent: str | None = Field(default=None, min_length=1)
    required_capability: str | None = Field(default=None, min_length=1)
    constraints_add: tuple[str, ...] = ()
    constraints_remove: tuple[str, ...] = ()
    status: str | None = None
    children_ops: tuple[dict[str, Any], ...] = ()


class DraftTaskNode(_FrozenModel):
    """Unpublished task-authoring fact owned by DraftTaskStore."""

    draft_task_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    draft_tree_id: str = Field(min_length=1)
    parent_draft_task_id: str | None = Field(default=None, min_length=1)
    order_index: int = Field(default=0, ge=0)

    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    required_capability: str = Field(min_length=1)
    constraints: tuple[str, ...] = ()
    rationale: str | None = None

    status: DraftTaskStatus = "draft"
    version: int = Field(default=1, ge=1)
    created_by: str = Field(default="collaborator_agent", min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _validate_timestamps(self) -> DraftTaskNode:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self


class DraftTaskTree(_FrozenModel):
    """One unpublished Task Tree List owned by a Session."""

    draft_tree_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    root_nodes: tuple[DraftTaskNode, ...] = Field(min_length=1)
    created_by: str = Field(default="collaborator_agent", min_length=1)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _validate_roots(self) -> DraftTaskTree:
        seen_order: set[int] = set()
        for node in self.root_nodes:
            if node.session_id != self.session_id:
                raise ValueError("root node session_id must match tree session_id")
            if node.draft_tree_id != self.draft_tree_id:
                raise ValueError("root node draft_tree_id must match tree draft_tree_id")
            if node.parent_draft_task_id is not None:
                raise ValueError("root node parent_draft_task_id must be None")
            if node.order_index in seen_order:
                raise ValueError("root node order_index values must be unique")
            seen_order.add(node.order_index)
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self


class DraftToPublishedMapping(_FrozenModel):
    """Identity lineage from authoring draft node to published Task."""

    session_id: str = Field(min_length=1)
    draft_tree_id: str = Field(min_length=1)
    draft_task_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    published_at: datetime = Field(default_factory=_utcnow)
    publish_command_id: str = Field(min_length=1)
