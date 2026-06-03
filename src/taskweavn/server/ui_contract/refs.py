"""Reference and impact models shared by UI command/event contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from taskweavn.server.ui_contract.base import UiContractModel
from taskweavn.task.models import TaskRef

ObjectRefKind = Literal[
    "raw_task",
    "raw_task_ask",
    "draft_task",
    "draft_tree",
    "draft_subtree",
    "published_task",
    "ask",
    "message",
    "command",
]
AffectedObjectImpact = Literal[
    "changed",
    "created",
    "deleted",
    "may_need_update",
    "needs_review",
    "invalidated",
    "replaced",
    "superseded",
]
AffectedScopeKind = Literal[
    "session",
    "task_tree",
    "task_subtree",
    "task_detail",
    "messages",
    "confirmations",
    "asks",
]


class ObjectRef(UiContractModel):
    """Stable reference to a backend fact without exposing the fact itself."""

    kind: ObjectRefKind
    id: str = Field(min_length=1)


class AffectedObjectRef(UiContractModel):
    """A referenced object plus how a command affected it."""

    ref: ObjectRef
    impact: AffectedObjectImpact
    reason: str | None = None


class AffectedScope(UiContractModel):
    """Coarse refresh scope for UI invalidation."""

    kind: AffectedScopeKind
    task_ref: TaskRef | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _validate_task_scope(self) -> AffectedScope:
        if self.kind in {"task_subtree", "task_detail"} and self.task_ref is None:
            raise ValueError(f"{self.kind} scope requires task_ref")
        return self
