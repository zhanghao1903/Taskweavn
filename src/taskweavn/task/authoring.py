"""Collaborator Agent authoring contracts and deterministic validation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.interaction import AgentMessage
from taskweavn.task.models import DraftTaskNode, DraftTaskTree, TaskNodePatch, TaskRef

AuthoringMode = Literal["session", "task"]
AuthoringCommandStatus = Literal["accepted", "rejected"]
FeasibilityNextAction = Literal[
    "generate_task_tree",
    "ask_user",
    "offer_alternatives",
    "decline",
]
FeasibilityStatus = Literal[
    "ready",
    "needs_clarification",
    "needs_user_permission",
    "partially_feasible",
    "not_supported",
    "unsafe",
]
DraftTaskValidationSeverity = Literal["error", "warning"]
DraftPatchScope = Literal["selected_node", "subtree"]
RawTaskStatus = Literal[
    "created",
    "assessing",
    "awaiting_user",
    "ready_to_plan",
    "converted",
    "rejected",
    "cancelled",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class _FrozenAuthoringModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class RawTaskAnswerOption(_FrozenAuthoringModel):
    """User-selectable answer option for a RawTask clarification ask."""

    option_id: str = Field(default_factory=_new_id, min_length=1)
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    description: str | None = None


class RawTaskAsk(_FrozenAuthoringModel):
    """Clarification request attached to a RawTask, not directly to TaskBus."""

    ask_id: str = Field(default_factory=_new_id, min_length=1)
    raw_task_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    options: tuple[RawTaskAnswerOption, ...] = ()
    required: bool = True
    reason: str = Field(min_length=1)
    created_by: str = Field(default="collaborator_agent", min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)


class RawTaskAnswer(_FrozenAuthoringModel):
    """User answer to one RawTaskAsk."""

    answer_id: str = Field(default_factory=_new_id, min_length=1)
    raw_task_id: str = Field(min_length=1)
    ask_id: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_message_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)


class FeasibilityReport(_FrozenAuthoringModel):
    """Structured feasibility assessment for RawTask authoring.

    This is intentionally not a yes/no verdict. It tells the authoring layer
    whether to draft, ask, offer alternatives, or decline.
    """

    status: FeasibilityStatus
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    suggested_next_action: FeasibilityNextAction = "ask_user"

    @model_validator(mode="before")
    @classmethod
    def _default_next_action(cls, data: object) -> object:
        if not isinstance(data, dict) or "suggested_next_action" in data:
            return data
        status = data.get("status")
        defaults: dict[object, FeasibilityNextAction] = {
            "ready": "generate_task_tree",
            "partially_feasible": "offer_alternatives",
            "needs_clarification": "ask_user",
            "needs_user_permission": "ask_user",
            "not_supported": "offer_alternatives",
            "unsafe": "decline",
        }
        return {**data, "suggested_next_action": defaults.get(status, "ask_user")}

    @model_validator(mode="after")
    def _validate_status_payload(self) -> FeasibilityReport:
        if (
            self.status in {"needs_clarification", "needs_user_permission"}
            and not self.missing_inputs
            and not self.required_permissions
        ):
            raise ValueError(
                "clarification or permission status requires missing inputs or permissions"
            )
        if self.status == "ready" and self.suggested_next_action != "generate_task_tree":
            raise ValueError("ready feasibility must suggest generate_task_tree")
        if self.status == "unsafe" and self.suggested_next_action != "decline":
            raise ValueError("unsafe feasibility must suggest decline")
        return self


class RawTask(_FrozenAuthoringModel):
    """Durable authoring object produced from task-like user intent."""

    raw_task_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    source_message_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    status: RawTaskStatus = "created"

    intent_summary: str | None = Field(default=None, min_length=1)
    feasibility: FeasibilityReport | None = None
    asks: tuple[RawTaskAsk, ...] = ()
    answers: tuple[RawTaskAnswer, ...] = ()
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    version: int = Field(default=1, ge=1)
    created_by: str = Field(default="user", min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @property
    def unanswered_ask_ids(self) -> tuple[str, ...]:
        answered = {answer.ask_id for answer in self.answers}
        return tuple(
            ask.ask_id for ask in self.asks if ask.required and ask.ask_id not in answered
        )

    @property
    def ready_for_planning(self) -> bool:
        return self.status == "ready_to_plan"

    @model_validator(mode="after")
    def _validate_raw_task(self) -> RawTask:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")

        ask_ids: set[str] = set()
        for ask in self.asks:
            if ask.raw_task_id != self.raw_task_id:
                raise ValueError("RawTaskAsk raw_task_id must match RawTask")
            if ask.ask_id in ask_ids:
                raise ValueError("RawTaskAsk ask_id values must be unique")
            ask_ids.add(ask.ask_id)

        for answer in self.answers:
            if answer.raw_task_id != self.raw_task_id:
                raise ValueError("RawTaskAnswer raw_task_id must match RawTask")
            if answer.ask_id not in ask_ids:
                raise ValueError("RawTaskAnswer must reference an existing RawTaskAsk")

        if self.status == "awaiting_user" and not self.unanswered_ask_ids:
            raise ValueError("awaiting_user RawTask requires at least one unanswered ask")

        if self.status == "ready_to_plan":
            if self.feasibility is None:
                raise ValueError("ready_to_plan RawTask requires feasibility")
            if self.feasibility.status not in {"ready", "partially_feasible"}:
                raise ValueError("ready_to_plan RawTask requires ready feasibility")

        if (
            self.status == "rejected"
            and self.feasibility is not None
            and self.feasibility.status not in {"not_supported", "unsafe"}
        ):
            raise ValueError("rejected RawTask requires unsupported or unsafe feasibility")

        return self


class AuthoringContext(_FrozenAuthoringModel):
    """Read-only context passed into one Collaborator invocation."""

    session_id: str = Field(min_length=1)
    mode: AuthoringMode
    selected_task_ref: TaskRef | None = None
    draft_trees: tuple[DraftTaskTree, ...] = ()
    selected_node: DraftTaskNode | None = None
    ancestors: tuple[DraftTaskNode, ...] = ()
    children: tuple[DraftTaskNode, ...] = ()
    recent_messages: tuple[AgentMessage, ...] = ()
    capabilities: tuple[str, ...] = ()
    constraints: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_selected_task(self) -> AuthoringContext:
        if self.mode == "task" and self.selected_task_ref is None:
            raise ValueError("task authoring context requires selected_task_ref")
        if self.selected_node is not None:
            if self.selected_task_ref != TaskRef.draft(self.selected_node.draft_task_id):
                raise ValueError("selected_node must match selected_task_ref")
            if self.selected_node.session_id != self.session_id:
                raise ValueError("selected_node session_id must match context session_id")
        return self


class DraftTaskNodeProposal(_FrozenAuthoringModel):
    """LLM proposal shape before ids and tree metadata are assigned."""

    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    required_capability: str = Field(min_length=1)
    constraints: tuple[str, ...] = ()
    rationale: str | None = None
    children: tuple[DraftTaskNodeProposal, ...] = ()


class DraftTaskTreeProposal(_FrozenAuthoringModel):
    roots: tuple[DraftTaskNodeProposal, ...] = Field(min_length=1)
    assistant_message: str = Field(min_length=1)


class DraftTaskPatchProposal(_FrozenAuthoringModel):
    patch: TaskNodePatch
    assistant_message: str = Field(min_length=1)
    affected_scope: DraftPatchScope = "selected_node"


class TaskNodeOption(_FrozenAuthoringModel):
    option_id: str = Field(default_factory=_new_id, min_length=1)
    label: str = Field(min_length=1)
    description: str | None = None
    patch: TaskNodePatch | None = None
    message: str | None = None

    @model_validator(mode="after")
    def _validate_effect(self) -> TaskNodeOption:
        if self.patch is None and self.message is None:
            raise ValueError("task node option requires patch or message")
        return self


class TaskNodeOptionSet(_FrozenAuthoringModel):
    session_id: str = Field(min_length=1)
    task_ref: TaskRef
    options: tuple[TaskNodeOption, ...] = Field(min_length=1)
    prompt: str | None = None


class DraftTaskValidationIssue(_FrozenAuthoringModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: DraftTaskValidationSeverity = "error"
    draft_task_id: str | None = Field(default=None, min_length=1)
    path: tuple[str, ...] = ()


class DraftTaskTreeValidation(_FrozenAuthoringModel):
    draft_tree_id: str = Field(min_length=1)
    valid: bool = True
    errors: tuple[DraftTaskValidationIssue, ...] = ()
    warnings: tuple[DraftTaskValidationIssue, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _default_valid(cls, data: object) -> object:
        if not isinstance(data, dict) or "valid" in data:
            return data
        errors = data.get("errors", ())
        return {**data, "valid": not bool(errors)}

    @model_validator(mode="after")
    def _validate_valid_matches_errors(self) -> DraftTaskTreeValidation:
        if self.valid != (not self.errors):
            raise ValueError("valid must match whether validation has errors")
        return self


class AuthoringCommandResult(_FrozenAuthoringModel):
    command_id: str = Field(default_factory=_new_id, min_length=1)
    status: AuthoringCommandStatus
    message: str = Field(min_length=1)
    draft_tree_id: str | None = Field(default=None, min_length=1)
    affected_task_refs: tuple[TaskRef, ...] = ()
    emitted_message_ids: tuple[str, ...] = ()
    validation: DraftTaskTreeValidation | None = None

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


@runtime_checkable
class CapabilityCatalog(Protocol):
    def all(self) -> tuple[str, ...]: ...

    def contains(self, capability: str) -> bool: ...


class StaticCapabilityCatalog:
    """Small deterministic capability catalog for early authoring tests."""

    def __init__(self, capabilities: Iterable[str]) -> None:
        seen: set[str] = set()
        ordered: list[str] = []
        for capability in capabilities:
            normalized = capability.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        self._capabilities = tuple(ordered)

    def all(self) -> tuple[str, ...]:
        return self._capabilities

    def contains(self, capability: str) -> bool:
        return capability.strip() in self._capabilities


class DraftTaskTreeValidator:
    """Deterministic validator for draft trees before publish."""

    def __init__(
        self,
        *,
        capability_catalog: CapabilityCatalog,
        max_depth: int = 8,
        max_nodes: int = 100,
        publishable_statuses: tuple[str, ...] = ("draft", "accepted"),
    ) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        if max_nodes < 1:
            raise ValueError("max_nodes must be >= 1")
        self._capability_catalog = capability_catalog
        self._max_depth = max_depth
        self._max_nodes = max_nodes
        self._publishable_statuses = publishable_statuses

    def validate_tree(self, tree: DraftTaskTree) -> DraftTaskTreeValidation:
        errors: list[DraftTaskValidationIssue] = []
        warnings: list[DraftTaskValidationIssue] = []
        nodes = list(tree.root_nodes)
        if len(nodes) > self._max_nodes:
            errors.append(
                _issue(
                    "max_nodes_exceeded",
                    f"draft tree has {len(nodes)} nodes, max is {self._max_nodes}",
                )
            )

        root_orders: set[int] = set()
        seen_ids: set[str] = set()
        for node in nodes:
            if node.draft_task_id in seen_ids:
                errors.append(
                    _issue(
                        "duplicate_node_id",
                        f"duplicate draft task id {node.draft_task_id!r}",
                        node,
                    )
                )
            seen_ids.add(node.draft_task_id)
            if node.session_id != tree.session_id:
                errors.append(
                    _issue(
                        "session_mismatch",
                        "draft task session_id must match tree session_id",
                        node,
                    )
                )
            if node.draft_tree_id != tree.draft_tree_id:
                errors.append(
                    _issue(
                        "tree_mismatch",
                        "draft task draft_tree_id must match tree draft_tree_id",
                        node,
                    )
                )
            if node.parent_draft_task_id is not None:
                errors.append(
                    _issue(
                        "root_parent",
                        "root draft task must not have parent_draft_task_id",
                        node,
                    )
                )
            if node.order_index in root_orders:
                errors.append(
                    _issue(
                        "duplicate_sibling_order",
                        f"duplicate root order_index {node.order_index}",
                        node,
                    )
                )
            root_orders.add(node.order_index)
            errors.extend(self._validate_node_content(node))

        if len(nodes) >= self._max_nodes:
            warnings.append(
                DraftTaskValidationIssue(
                    code="node_count_near_limit",
                    message="draft tree is at or near the configured node limit",
                    severity="warning",
                )
            )
        return DraftTaskTreeValidation(
            draft_tree_id=tree.draft_tree_id,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def validate_proposal(
        self,
        proposal: DraftTaskTreeProposal,
        *,
        draft_tree_id: str = "proposal",
    ) -> DraftTaskTreeValidation:
        errors: list[DraftTaskValidationIssue] = []
        count = 0

        def visit(node: DraftTaskNodeProposal, path: tuple[str, ...]) -> None:
            nonlocal count
            count += 1
            if len(path) > self._max_depth:
                errors.append(
                    DraftTaskValidationIssue(
                        code="max_depth_exceeded",
                        message=f"proposal depth {len(path)} exceeds max {self._max_depth}",
                        path=path,
                    )
                )
            if not node.title.strip():
                errors.append(_proposal_issue("empty_title", "title must not be blank", path))
            if not node.intent.strip():
                errors.append(_proposal_issue("empty_intent", "intent must not be blank", path))
            if not self._capability_catalog.contains(node.required_capability):
                errors.append(
                    _proposal_issue(
                        "unknown_capability",
                        f"unknown capability {node.required_capability!r}",
                        path,
                    )
                )
            for index, child in enumerate(node.children):
                visit(child, (*path, str(index)))

        for index, root in enumerate(proposal.roots):
            visit(root, (str(index),))

        if count > self._max_nodes:
            errors.append(
                DraftTaskValidationIssue(
                    code="max_nodes_exceeded",
                    message=f"proposal has {count} nodes, max is {self._max_nodes}",
                )
            )
        return DraftTaskTreeValidation(
            draft_tree_id=draft_tree_id,
            errors=tuple(errors),
        )

    def _validate_node_content(
        self,
        node: DraftTaskNode,
    ) -> list[DraftTaskValidationIssue]:
        errors: list[DraftTaskValidationIssue] = []
        if not node.title.strip():
            errors.append(_issue("empty_title", "title must not be blank", node))
        if not node.intent.strip():
            errors.append(_issue("empty_intent", "intent must not be blank", node))
        if not node.required_capability.strip():
            errors.append(
                _issue("empty_capability", "required_capability must not be blank", node)
            )
        elif not self._capability_catalog.contains(node.required_capability):
            errors.append(
                _issue(
                    "unknown_capability",
                    f"unknown capability {node.required_capability!r}",
                    node,
                )
            )
        if node.status not in self._publishable_statuses:
            errors.append(
                _issue(
                    "status_not_publishable",
                    f"draft task status {node.status!r} is not publishable",
                    node,
                )
            )
        return errors


def _issue(
    code: str,
    message: str,
    node: DraftTaskNode | None = None,
) -> DraftTaskValidationIssue:
    return DraftTaskValidationIssue(
        code=code,
        message=message,
        draft_task_id=None if node is None else node.draft_task_id,
    )


def _proposal_issue(
    code: str,
    message: str,
    path: tuple[str, ...],
) -> DraftTaskValidationIssue:
    return DraftTaskValidationIssue(code=code, message=message, path=path)
