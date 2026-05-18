"""TaskPublisher contracts and default TaskBus-backed publisher."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.task.bus import TaskBus
from taskweavn.task.models import (
    DraftTaskNode,
    DraftToPublishedMapping,
    TaskDispatchConstraints,
    TaskDomain,
)
from taskweavn.task.stores import DraftTaskStore

PublisherKind = Literal[
    "user",
    "collaborator",
    "pipeline",
    "scheduler",
    "api",
    "custom_tree",
    "agent",
]
PublishSourceKind = Literal[
    "draft_tree",
    "custom_tree",
    "pipeline",
    "schedule",
    "api",
    "retry",
    "natural_language",
    "unknown",
]
FailurePolicy = Literal["fail_all", "publish_valid"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class _FrozenPublisherModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class PublisherRef(_FrozenPublisherModel):
    """Who is asking to publish executable Tasks."""

    kind: PublisherKind
    actor_id: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)

    @property
    def label(self) -> str:
        return self.actor_id or self.name or self.kind


class PublishSource(_FrozenPublisherModel):
    """Where a publish request came from before normalization."""

    source_type: PublishSourceKind = "unknown"
    source_id: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskPublishOptions(_FrozenPublisherModel):
    """Execution publish options.

    This is separate from ``taskweavn.task.authoring.PublishOptions``: authoring
    options describe the DraftTaskTree boundary, while these options describe
    the normalized PublishedTask publisher boundary.
    """

    dry_run: bool = False
    require_confirmation: bool = True
    allow_pipeline: bool = True
    source_label: str | None = Field(default=None, min_length=1)
    failure_policy: FailurePolicy = "fail_all"


class NormalizedTaskNode(_FrozenPublisherModel):
    """One normalized Task node ready to become a PublishedTask."""

    node_id: str = Field(min_length=1)
    parent_id: str | None = Field(default=None, min_length=1)
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    required_capability: str = Field(min_length=1)
    agent_ref: str | None = Field(default=None, min_length=1)
    children: tuple[NormalizedTaskNode, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedTaskTree(_FrozenPublisherModel):
    """Tree-list normalized before it enters TaskBus."""

    root_nodes: tuple[NormalizedTaskNode, ...] = Field(min_length=1)
    source: PublisherRef
    source_ref: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def root_ids(self) -> tuple[str, ...]:
        return tuple(root.node_id for root in self.root_nodes)

    @property
    def task_count(self) -> int:
        return len(self.iter_nodes())

    def iter_nodes(self) -> tuple[NormalizedTaskNode, ...]:
        nodes: list[NormalizedTaskNode] = []
        for root in self.root_nodes:
            _collect_nodes(root, nodes)
        return tuple(nodes)

    @model_validator(mode="after")
    def _validate_tree(self) -> NormalizedTaskTree:
        seen: set[str] = set()
        for root in self.root_nodes:
            if root.parent_id is not None:
                raise ValueError("root normalized task nodes must not have parent_id")
            _validate_node(root, expected_parent_id=None, seen=seen)
        return self


class PublishRequest(_FrozenPublisherModel):
    """Unified request accepted by TaskPublisher implementations."""

    request_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    publisher: PublisherRef
    source: PublishSource = Field(default_factory=PublishSource)
    task_tree: NormalizedTaskTree | None = None
    natural_language_input: str | None = Field(default=None, min_length=1)
    options: TaskPublishOptions = Field(default_factory=TaskPublishOptions)
    idempotency_key: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_input(self) -> PublishRequest:
        if self.task_tree is None and self.natural_language_input is None:
            raise ValueError("publish request requires task_tree or natural_language_input")
        if self.task_tree is not None and self.task_tree.source != self.publisher:
            raise ValueError("normalized tree source must match request publisher")
        return self


class PublishPreview(_FrozenPublisherModel):
    """Validation-only result; does not write TaskBus."""

    request_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    publisher: PublisherRef
    normalized_tree: NormalizedTaskTree | None = None
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    root_count: int = Field(default=0, ge=0)
    task_count: int = Field(default=0, ge=0)

    @property
    def ok(self) -> bool:
        return self.valid and not self.errors


class PublishResult(_FrozenPublisherModel):
    """Result of publishing normalized Tasks into TaskBus."""

    request_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    publisher: PublisherRef
    published_task_ids: tuple[str, ...] = ()
    root_task_ids: tuple[str, ...] = ()
    skipped: bool = False
    reason: str | None = Field(default=None, min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return not self.skipped


class TaskPublishResult(_FrozenPublisherModel):
    """Compatibility result used by draft-tree publish commands."""

    root_task_ids: tuple[str, ...] = ()
    mappings: tuple[DraftToPublishedMapping, ...] = ()
    rejected_task_ids: tuple[str, ...] = ()


@runtime_checkable
class TaskPublisher(Protocol):
    """Unified publisher boundary plus draft/retry compatibility hooks."""

    kind: PublisherKind

    def preview(self, request: PublishRequest) -> PublishPreview: ...

    def publish(self, request: PublishRequest) -> PublishResult: ...

    def publish_draft_tree(self, session_id: str, draft_tree_id: str) -> TaskPublishResult: ...

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> TaskPublishResult: ...


class DefaultTaskPublisher:
    """Default publisher that writes normalized Tasks through TaskBus."""

    kind: PublisherKind = "collaborator"

    def __init__(
        self,
        *,
        task_bus: TaskBus,
        draft_store: DraftTaskStore | None = None,
        publisher: PublisherRef | None = None,
    ) -> None:
        self._task_bus = task_bus
        self._draft_store = draft_store
        self._publisher = publisher or PublisherRef(kind=self.kind, actor_id="system")
        self.kind = self._publisher.kind

    def preview(self, request: PublishRequest) -> PublishPreview:
        if request.task_tree is None:
            return PublishPreview(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                valid=False,
                errors=("natural-language publish requires authoring before TaskBus publish",),
            )
        errors = _validate_request_tree(request)
        tree = request.task_tree
        return PublishPreview(
            request_id=request.request_id,
            session_id=request.session_id,
            publisher=request.publisher,
            normalized_tree=tree,
            valid=not errors,
            errors=tuple(errors),
            root_count=len(tree.root_nodes),
            task_count=tree.task_count,
        )

    def publish(self, request: PublishRequest) -> PublishResult:
        preview = self.preview(request)
        if not preview.ok:
            return PublishResult(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                skipped=True,
                reason="; ".join(preview.errors) or "publish preview failed",
                idempotency_key=request.idempotency_key,
            )
        if request.options.dry_run:
            return PublishResult(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                skipped=True,
                reason="dry run",
                idempotency_key=request.idempotency_key,
            )

        tree = _require_tree(request)
        node_task_ids = _task_ids_for_request(request, tree)
        root_task_ids = tuple(node_task_ids[root.node_id] for root in tree.root_nodes)
        root_by_node = _root_by_node(tree)
        tasks = _tasks_for_request(
            request,
            tree=tree,
            node_task_ids=node_task_ids,
            root_by_node=root_by_node,
        )
        if request.idempotency_key is not None:
            existing_result = self._result_from_existing_idempotent_tasks(
                request,
                tasks=tasks,
                tree=tree,
                node_task_ids=node_task_ids,
                root_task_ids=root_task_ids,
            )
            if existing_result is not None:
                return existing_result

        published = [self._task_bus.publish(task) for task in tasks]

        return PublishResult(
            request_id=request.request_id,
            session_id=request.session_id,
            publisher=request.publisher,
            published_task_ids=tuple(task.task_id for task in published),
            root_task_ids=root_task_ids,
            idempotency_key=request.idempotency_key,
            metadata={
                "node_task_ids": dict(node_task_ids),
                "source_type": request.source.source_type,
                "published_at": _utcnow().isoformat(),
            },
        )

    def _result_from_existing_idempotent_tasks(
        self,
        request: PublishRequest,
        *,
        tasks: tuple[TaskDomain, ...],
        tree: NormalizedTaskTree,
        node_task_ids: dict[str, str],
        root_task_ids: tuple[str, ...],
    ) -> PublishResult | None:
        existing = {
            task.task_id: self._task_bus.get(request.session_id, task.task_id)
            for task in tasks
        }
        existing_tasks = {task_id: task for task_id, task in existing.items() if task is not None}
        if not existing_tasks:
            return None
        if len(existing_tasks) != len(tasks):
            missing = tuple(task.task_id for task in tasks if task.task_id not in existing_tasks)
            return PublishResult(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                skipped=True,
                reason="incomplete idempotent publish",
                idempotency_key=request.idempotency_key,
                metadata={
                    "node_task_ids": dict(node_task_ids),
                    "source_type": request.source.source_type,
                    "existing_task_ids": tuple(existing_tasks),
                    "missing_task_ids": missing,
                    "skip_idempotency_record": True,
                },
            )
        mismatched = tuple(
            task.task_id
            for task in tasks
            if not _task_matches_expected(existing_tasks[task.task_id], task)
        )
        if mismatched:
            return PublishResult(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                skipped=True,
                reason="idempotent publish target already exists with different task payload",
                idempotency_key=request.idempotency_key,
                metadata={
                    "node_task_ids": dict(node_task_ids),
                    "source_type": request.source.source_type,
                    "mismatched_task_ids": mismatched,
                    "skip_idempotency_record": True,
                },
            )
        return PublishResult(
            request_id=request.request_id,
            session_id=request.session_id,
            publisher=request.publisher,
            published_task_ids=tuple(task.task_id for task in tasks),
            root_task_ids=root_task_ids,
            idempotency_key=request.idempotency_key,
            metadata={
                "node_task_ids": dict(node_task_ids),
                "source_type": request.source.source_type,
                "idempotent_existing_tasks": True,
                "replayed_at": _utcnow().isoformat(),
            },
        )

    def publish_draft_tree(self, session_id: str, draft_tree_id: str) -> TaskPublishResult:
        if self._draft_store is None:
            raise ValueError("draft store is not configured")
        nodes = self._draft_store.list_nodes(session_id, draft_tree_id)
        if not nodes:
            return TaskPublishResult(rejected_task_ids=(draft_tree_id,))
        publisher = PublisherRef(kind="collaborator", actor_id="collaborator")
        tree = NormalizedTaskTree(
            root_nodes=_normalized_roots_from_draft(nodes),
            source=publisher,
            source_ref=draft_tree_id,
            metadata={"draft_tree_id": draft_tree_id},
        )
        request = PublishRequest(
            session_id=session_id,
            publisher=publisher,
            source=PublishSource(source_type="draft_tree", source_id=draft_tree_id),
            task_tree=tree,
        )
        result = self.publish(request)
        if result.skipped:
            return TaskPublishResult(
                rejected_task_ids=tuple(node.draft_task_id for node in nodes),
            )
        node_task_ids = _node_task_ids(result)
        mappings = tuple(
            DraftToPublishedMapping(
                session_id=session_id,
                draft_tree_id=draft_tree_id,
                draft_task_id=node.draft_task_id,
                task_id=node_task_ids[node.draft_task_id],
                publish_command_id=result.request_id,
            )
            for node in nodes
        )
        return TaskPublishResult(root_task_ids=result.root_task_ids, mappings=mappings)

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> TaskPublishResult:
        source = self._task_bus.get(session_id, task_id)
        if source is None or source.status != "failed":
            return TaskPublishResult(rejected_task_ids=(task_id,))
        publisher = PublisherRef(kind="user", actor_id="retry")
        node = NormalizedTaskNode(
            node_id=f"retry:{task_id}",
            title=f"Retry {task_id}",
            intent=instruction or f"Retry failed task: {source.intent}",
            required_capability=source.required_capability,
            metadata={"retry_of": task_id},
        )
        tree = NormalizedTaskTree(
            root_nodes=(node,),
            source=publisher,
            source_ref=task_id,
            metadata={"retry_of": task_id},
        )
        result = self.publish(
            PublishRequest(
                session_id=session_id,
                publisher=publisher,
                source=PublishSource(source_type="retry", source_id=task_id),
                task_tree=tree,
            )
        )
        if result.skipped:
            return TaskPublishResult(rejected_task_ids=(task_id,))
        return TaskPublishResult(root_task_ids=result.root_task_ids)


def _collect_nodes(node: NormalizedTaskNode, nodes: list[NormalizedTaskNode]) -> None:
    nodes.append(node)
    for child in node.children:
        _collect_nodes(child, nodes)


def _validate_node(
    node: NormalizedTaskNode,
    *,
    expected_parent_id: str | None,
    seen: set[str],
) -> None:
    if node.node_id in seen:
        raise ValueError(f"duplicate normalized task node id {node.node_id!r}")
    if node.parent_id != expected_parent_id:
        raise ValueError(
            f"normalized task node {node.node_id!r} has parent_id "
            f"{node.parent_id!r}, expected {expected_parent_id!r}"
        )
    seen.add(node.node_id)
    for child in node.children:
        _validate_node(child, expected_parent_id=node.node_id, seen=seen)


def _validate_request_tree(request: PublishRequest) -> list[str]:
    tree = request.task_tree
    if tree is None:
        return ["publish request has no normalized task tree"]
    errors: list[str] = []
    if tree.source != request.publisher:
        errors.append("normalized tree source must match request publisher")
    for node in tree.iter_nodes():
        if not node.intent.strip():
            errors.append(f"node {node.node_id!r} has empty intent")
        if not node.required_capability.strip():
            errors.append(f"node {node.node_id!r} has empty required_capability")
    return errors


def _task_ids_for_request(
    request: PublishRequest,
    tree: NormalizedTaskTree,
) -> dict[str, str]:
    if request.idempotency_key is None:
        return {node.node_id: _new_id() for node in tree.iter_nodes()}
    return {
        node.node_id: _idempotent_task_id(request, node)
        for node in tree.iter_nodes()
    }


def _idempotent_task_id(request: PublishRequest, node: NormalizedTaskNode) -> str:
    payload = {
        "session_id": request.session_id,
        "publisher_kind": request.publisher.kind,
        "idempotency_key": request.idempotency_key,
        "source_node_id": node.node_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return uuid5(NAMESPACE_URL, f"taskweavn.publish:{encoded}").hex


def _tasks_for_request(
    request: PublishRequest,
    *,
    tree: NormalizedTaskTree,
    node_task_ids: dict[str, str],
    root_by_node: dict[str, str],
) -> tuple[TaskDomain, ...]:
    tasks: list[TaskDomain] = []
    for node in tree.iter_nodes():
        task_id = node_task_ids[node.node_id]
        parent_task_id = None
        if node.parent_id is not None:
            parent_task_id = node_task_ids[node.parent_id]
        root_task_id = node_task_ids[root_by_node[node.node_id]]
        tasks.append(
            TaskDomain(
                task_id=task_id,
                session_id=request.session_id,
                parent_id=parent_task_id,
                root_id=root_task_id,
                order_index=_order_index(tree, node),
                intent=node.intent,
                required_capability=node.required_capability,
                dispatch_constraints=_dispatch_constraints(request, tree, node),
                created_by=request.publisher.label,
            )
        )
    return tuple(tasks)


def _task_matches_expected(existing: TaskDomain, expected: TaskDomain) -> bool:
    if (
        existing.session_id != expected.session_id
        or existing.parent_id != expected.parent_id
        or existing.root_id != expected.root_id
        or existing.order_index != expected.order_index
        or existing.intent != expected.intent
        or existing.required_capability != expected.required_capability
        or existing.created_by != expected.created_by
    ):
        return False
    return _dispatch_constraints_match(
        existing.dispatch_constraints,
        expected.dispatch_constraints,
    )


def _dispatch_constraints_match(
    existing: TaskDispatchConstraints | None,
    expected: TaskDispatchConstraints | None,
) -> bool:
    if existing is None or expected is None:
        return existing == expected
    return (
        existing.required_agent_id == expected.required_agent_id
        and existing.preferred_agent_id == expected.preferred_agent_id
        and existing.required_capabilities == expected.required_capabilities
        and _stable_metadata(existing.metadata) == _stable_metadata(expected.metadata)
    )


def _stable_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key != "publish_request_id"
    }


def _require_tree(request: PublishRequest) -> NormalizedTaskTree:
    if request.task_tree is None:
        raise ValueError("publish request requires normalized task tree")
    return request.task_tree


def _root_by_node(tree: NormalizedTaskTree) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for root in tree.root_nodes:
        _assign_root(root, root.node_id, mapping)
    return mapping


def _assign_root(
    node: NormalizedTaskNode,
    root_id: str,
    mapping: dict[str, str],
) -> None:
    mapping[node.node_id] = root_id
    for child in node.children:
        _assign_root(child, root_id, mapping)


def _order_index(tree: NormalizedTaskTree, node: NormalizedTaskNode) -> int:
    siblings = tree.root_nodes
    if node.parent_id is not None:
        parent = next(parent for parent in tree.iter_nodes() if parent.node_id == node.parent_id)
        siblings = parent.children
    for index, sibling in enumerate(siblings):
        if sibling.node_id == node.node_id:
            return index
    return 0


def _dispatch_constraints(
    request: PublishRequest,
    tree: NormalizedTaskTree,
    node: NormalizedTaskNode,
) -> TaskDispatchConstraints:
    metadata = {
        "publish_request_id": request.request_id,
        "publish_idempotency_key": request.idempotency_key,
        "publisher_kind": request.publisher.kind,
        "publisher_actor_id": request.publisher.actor_id,
        "publisher_name": request.publisher.name,
        "source_type": request.source.source_type,
        "source_id": request.source.source_id,
        "source_metadata": dict(request.source.metadata),
        "source_ref": tree.source_ref,
        "source_node_id": node.node_id,
        "title": node.title,
        **tree.metadata,
        **node.metadata,
    }
    return TaskDispatchConstraints(
        preferred_agent_id=node.agent_ref,
        required_capabilities=(node.required_capability,),
        metadata=metadata,
    )


def _normalized_roots_from_draft(
    nodes: list[DraftTaskNode],
) -> tuple[NormalizedTaskNode, ...]:
    children: dict[str | None, list[DraftTaskNode]] = {}
    for node in nodes:
        children.setdefault(node.parent_draft_task_id, []).append(node)
    return tuple(_normalized_from_draft(root, children) for root in children.get(None, ()))


def _normalized_from_draft(
    node: DraftTaskNode,
    children: dict[str | None, list[DraftTaskNode]],
) -> NormalizedTaskNode:
    return NormalizedTaskNode(
        node_id=node.draft_task_id,
        parent_id=node.parent_draft_task_id,
        title=node.title,
        intent=node.intent,
        required_capability=node.required_capability,
        children=tuple(
            _normalized_from_draft(child, children)
            for child in sorted(
                children.get(node.draft_task_id, ()),
                key=lambda child: (child.order_index, child.created_at, child.draft_task_id),
            )
        ),
        metadata={
            "draft_task_id": node.draft_task_id,
            "draft_tree_id": node.draft_tree_id,
        },
    )


def _node_task_ids(result: PublishResult) -> dict[str, str]:
    raw = result.metadata.get("node_task_ids", {})
    if not isinstance(raw, dict):
        raise ValueError("publish result metadata missing node_task_ids")
    return {str(key): str(value) for key, value in raw.items()}


__all__ = [
    "DefaultTaskPublisher",
    "FailurePolicy",
    "NormalizedTaskNode",
    "NormalizedTaskTree",
    "PublishPreview",
    "PublishRequest",
    "PublishResult",
    "PublishSource",
    "PublishSourceKind",
    "PublisherKind",
    "PublisherRef",
    "TaskPublishOptions",
    "TaskPublishResult",
    "TaskPublisher",
]
