"""Plan-level publisher that adapts durable Plans to TaskPublisher requests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.task.models import TaskRef
from taskweavn.task.plan_models import Plan, PlanTaskNode
from taskweavn.task.plan_stores import PlanStore
from taskweavn.task.publisher import (
    NormalizedTaskNode,
    NormalizedTaskTree,
    PublisherRef,
    PublishRequest,
    PublishResult,
    PublishSource,
    TaskPublisher,
    TaskPublishOptions,
)
from taskweavn.task.stores import VersionConflictError


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class _FrozenPlanPublisherModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class PublishPlanCommand(_FrozenPlanPublisherModel):
    """Command boundary for publishing a durable Plan to executable Tasks."""

    command_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    publisher: PublisherRef = Field(
        default_factory=lambda: PublisherRef(kind="collaborator", actor_id="collaborator")
    )
    expected_plan_version: int | None = Field(default=None, ge=1)
    idempotency_key: str = Field(min_length=1)
    publish_options: TaskPublishOptions = Field(default_factory=TaskPublishOptions)


class PlanTaskPublishMapping(_FrozenPlanPublisherModel):
    session_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    task_node_id: str = Field(min_length=1)
    task_index: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    published_at: datetime = Field(default_factory=_utcnow)
    publish_command_id: str = Field(min_length=1)


class PublishPlanResult(_FrozenPlanPublisherModel):
    command_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    published_task_ids: tuple[str, ...] = ()
    root_task_ids: tuple[str, ...] = ()
    mappings: tuple[PlanTaskPublishMapping, ...] = ()
    skipped: bool = False
    reason: str | None = Field(default=None, min_length=1)

    @property
    def accepted(self) -> bool:
        return not self.skipped


@runtime_checkable
class PlanPublisher(Protocol):
    """Publishes durable Plans while legacy DraftTaskTree publishing remains intact."""

    def publish_plan(self, command: PublishPlanCommand) -> PublishPlanResult: ...


class DefaultPlanPublisher:
    """Default Plan publisher backed by PlanStore and the existing TaskPublisher."""

    def __init__(
        self,
        *,
        plan_store: PlanStore,
        task_publisher: TaskPublisher,
    ) -> None:
        self._plan_store = plan_store
        self._task_publisher = task_publisher

    def publish_plan(self, command: PublishPlanCommand) -> PublishPlanResult:
        plan = self._require_plan(command)
        nodes = self._plan_store.list_task_nodes(command.session_id, command.plan_id)
        if not nodes:
            return _skipped(command, plan.plan_id, reason="plan has no TaskNodes")
        if plan.status in {"cancelled", "archived"}:
            return _skipped(
                command,
                plan.plan_id,
                reason=f"plan status {plan.status!r} cannot be published",
            )

        existing = _existing_lineage(command, nodes)
        if existing is not None:
            if plan.status != "published":
                self._plan_store.save_plan(
                    plan.model_copy(update={"status": "published"}),
                    expected_version=plan.version,
                )
            return existing
        if any(node.published_ref is not None for node in nodes):
            return _skipped(command, plan.plan_id, reason="plan is partially published")

        request = _publish_request(command, plan, nodes)
        result = self._task_publisher.publish(request)
        if result.skipped:
            return PublishPlanResult(
                command_id=command.command_id,
                request_id=result.request_id,
                session_id=command.session_id,
                plan_id=command.plan_id,
                skipped=True,
                reason=result.reason or "task publisher skipped plan publish",
            )

        node_task_ids = _node_task_ids(result)
        mappings = _mappings_from_result(command, nodes, node_task_ids)
        for node in nodes:
            task_id = node_task_ids[node.task_node_id]
            self._save_published_node(node, task_id)
        self._plan_store.save_plan(
            plan.model_copy(update={"status": "published"}),
            expected_version=plan.version,
        )

        return PublishPlanResult(
            command_id=command.command_id,
            request_id=result.request_id,
            session_id=command.session_id,
            plan_id=command.plan_id,
            published_task_ids=result.published_task_ids,
            root_task_ids=result.root_task_ids,
            mappings=mappings,
        )

    def _require_plan(self, command: PublishPlanCommand) -> Plan:
        plan = self._plan_store.get_plan(command.session_id, command.plan_id)
        if plan is None:
            raise LookupError(f"Plan {command.plan_id!r} not found")
        if command.expected_plan_version is not None and (
            plan.version != command.expected_plan_version
        ):
            raise VersionConflictError(
                f"stale version for {command.plan_id!r}: "
                f"expected {command.expected_plan_version}, current {plan.version}"
            )
        return plan

    def _save_published_node(self, node: PlanTaskNode, task_id: str) -> None:
        published = TaskRef.published(task_id)
        if (
            node.published_ref == published
            and node.readiness == "published"
            and node.execution == "pending"
        ):
            return
        self._plan_store.save_task_node(
            node.model_copy(
                update={
                    "published_ref": published,
                    "readiness": "published",
                    "execution": "pending",
                    "result_ref": None,
                    "error_ref": None,
                }
            ),
            expected_version=node.version,
        )


def _publish_request(
    command: PublishPlanCommand,
    plan: Plan,
    nodes: list[PlanTaskNode],
) -> PublishRequest:
    tree = NormalizedTaskTree(
        root_nodes=tuple(_normalized_node(node) for node in _ordered_nodes(nodes)),
        source=command.publisher,
        source_ref=plan.plan_id,
        metadata={
            "plan_id": plan.plan_id,
            "plan_title": plan.title,
            "source_raw_task_id": plan.source_raw_task_id,
            "source_draft_tree_id": plan.source_draft_tree_id,
        },
    )
    return PublishRequest(
        request_id=command.command_id,
        session_id=command.session_id,
        publisher=command.publisher,
        source=PublishSource(
            source_type="plan",
            source_id=plan.plan_id,
            metadata={"plan_version": plan.version},
        ),
        task_tree=tree,
        options=command.publish_options,
        idempotency_key=command.idempotency_key,
    )


def _normalized_node(node: PlanTaskNode) -> NormalizedTaskNode:
    return NormalizedTaskNode(
        node_id=node.task_node_id,
        title=node.title,
        intent=node.intent,
        summary=node.summary,
        instructions=node.instructions or None,
        acceptance_criteria=node.acceptance_criteria,
        required_capability=node.required_capability or "general",
        metadata={
            "plan_id": node.plan_id,
            "task_node_id": node.task_node_id,
            "task_index": node.task_index,
            "depends_on": tuple(node.depends_on),
            "constraints": tuple(node.constraints),
        },
    )


def _ordered_nodes(nodes: list[PlanTaskNode]) -> tuple[PlanTaskNode, ...]:
    return tuple(
        sorted(
            nodes,
            key=lambda node: (node.order_index, node.task_index, node.task_node_id),
        )
    )


def _node_task_ids(result: PublishResult) -> dict[str, str]:
    raw = result.metadata.get("node_task_ids", {})
    if not isinstance(raw, dict):
        raise ValueError("publish result metadata missing node_task_ids")
    return {str(key): str(value) for key, value in raw.items()}


def _mappings_from_result(
    command: PublishPlanCommand,
    nodes: list[PlanTaskNode],
    node_task_ids: dict[str, str],
) -> tuple[PlanTaskPublishMapping, ...]:
    return tuple(
        PlanTaskPublishMapping(
            session_id=command.session_id,
            plan_id=command.plan_id,
            task_node_id=node.task_node_id,
            task_index=node.task_index,
            task_id=node_task_ids[node.task_node_id],
            publish_command_id=command.command_id,
        )
        for node in _ordered_nodes(nodes)
    )


def _existing_lineage(
    command: PublishPlanCommand,
    nodes: list[PlanTaskNode],
) -> PublishPlanResult | None:
    if not nodes or not all(node.published_ref is not None for node in nodes):
        return None
    mappings: list[PlanTaskPublishMapping] = []
    for node in _ordered_nodes(nodes):
        published_ref = node.published_ref
        if published_ref is None:
            return None
        mappings.append(
            PlanTaskPublishMapping(
                session_id=command.session_id,
                plan_id=command.plan_id,
                task_node_id=node.task_node_id,
                task_index=node.task_index,
                task_id=published_ref.id,
                publish_command_id=command.command_id,
            )
        )
    task_ids = tuple(mapping.task_id for mapping in mappings)
    return PublishPlanResult(
        command_id=command.command_id,
        request_id=command.command_id,
        session_id=command.session_id,
        plan_id=command.plan_id,
        published_task_ids=task_ids,
        root_task_ids=task_ids,
        mappings=tuple(mappings),
    )


def _skipped(command: PublishPlanCommand, plan_id: str, *, reason: str) -> PublishPlanResult:
    return PublishPlanResult(
        command_id=command.command_id,
        request_id=command.command_id,
        session_id=command.session_id,
        plan_id=plan_id,
        skipped=True,
        reason=reason,
    )


__all__ = [
    "DefaultPlanPublisher",
    "PlanPublisher",
    "PlanTaskPublishMapping",
    "PublishPlanCommand",
    "PublishPlanResult",
]
