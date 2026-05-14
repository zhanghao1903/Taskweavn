"""Store protocols and in-memory implementations for Task authoring facts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol, runtime_checkable
from uuid import uuid4

from taskweavn.task.authoring import RawTask
from taskweavn.task.models import (
    DraftTaskNode,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskDomain,
    TaskNodePatch,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class TaskStoreError(RuntimeError):
    """Base error for task store consistency violations."""


class VersionConflictError(TaskStoreError):
    """Raised when expected_version does not match the stored object version."""


@runtime_checkable
class TaskStore(Protocol):
    """Read side for published Task facts.

    The first implementation may be backed by an in-memory TaskBus view or a
    SQLite store. Callers should depend on this read protocol, not storage.
    """

    def get(self, session_id: str, task_id: str) -> TaskDomain | None: ...

    def list_for_session(self, session_id: str) -> list[TaskDomain]: ...

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]: ...


@runtime_checkable
class RawTaskStore(Protocol):
    """Persistence boundary for RawTask authoring facts."""

    def create(self, raw_task: RawTask) -> RawTask: ...

    def get(self, session_id: str, raw_task_id: str) -> RawTask | None: ...

    def list_for_session(self, session_id: str) -> list[RawTask]: ...

    def save(self, raw_task: RawTask, *, expected_version: int) -> RawTask: ...


@runtime_checkable
class DraftTaskStore(Protocol):
    """Persistence boundary for unpublished Task authoring facts."""

    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree: ...

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree: ...

    def list_trees(self, session_id: str) -> list[DraftTaskTree]: ...

    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]: ...

    def list_children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]: ...

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None: ...

    def add_node(
        self,
        session_id: str,
        draft_tree_id: str,
        node: DraftTaskNode,
        *,
        expected_tree_version: int,
    ) -> DraftTaskNode: ...

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode: ...

    def mark_accepted(
        self,
        session_id: str,
        draft_tree_id: str,
        *,
        expected_version: int,
    ) -> DraftTaskTree: ...

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
        *,
        expected_version: int | None = None,
    ) -> DraftTaskTree: ...


class InMemoryRawTaskStore:
    """Process-local RawTaskStore used by early authoring flows and tests."""

    def __init__(self, raw_tasks: list[RawTask] | None = None) -> None:
        self._lock = RLock()
        self._raw_tasks: dict[tuple[str, str], RawTask] = {}
        for raw_task in raw_tasks or []:
            self.create(raw_task)

    def create(self, raw_task: RawTask) -> RawTask:
        key = (raw_task.session_id, raw_task.raw_task_id)
        with self._lock:
            if key in self._raw_tasks:
                raise TaskStoreError(f"RawTask {raw_task.raw_task_id!r} already exists")
            self._raw_tasks[key] = raw_task
            return raw_task

    def get(self, session_id: str, raw_task_id: str) -> RawTask | None:
        with self._lock:
            return self._raw_tasks.get((session_id, raw_task_id))

    def list_for_session(self, session_id: str) -> list[RawTask]:
        with self._lock:
            return sorted(
                (
                    raw_task
                    for raw_task in self._raw_tasks.values()
                    if raw_task.session_id == session_id
                ),
                key=lambda raw_task: (
                    raw_task.created_at,
                    raw_task.updated_at,
                    raw_task.raw_task_id,
                ),
            )

    def save(self, raw_task: RawTask, *, expected_version: int) -> RawTask:
        key = (raw_task.session_id, raw_task.raw_task_id)
        with self._lock:
            current = self._raw_tasks.get(key)
            if current is None:
                raise LookupError(f"RawTask {raw_task.raw_task_id!r} not found")
            _check_version(current.version, expected_version, raw_task.raw_task_id)
            updated = _copy_raw_task(
                raw_task,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=_utcnow(),
            )
            self._raw_tasks[key] = updated
            return updated


class InMemoryDraftTaskStore:
    """Process-local DraftTaskStore with version checks and lineage indexes."""

    def __init__(self, trees: list[DraftTaskTree] | None = None) -> None:
        self._lock = RLock()
        self._trees: dict[tuple[str, str], DraftTaskTree] = {}
        self._nodes: dict[tuple[str, str], DraftTaskNode] = {}
        self._node_tree: dict[tuple[str, str], str] = {}
        self._mappings_by_draft: dict[
            tuple[str, str], list[DraftToPublishedMapping]
        ] = defaultdict(list)
        self._mappings_by_task: dict[
            tuple[str, str], list[DraftToPublishedMapping]
        ] = defaultdict(list)
        for tree in trees or []:
            self._load_tree(tree)

    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree:
        if not roots:
            raise ValueError("draft tree requires at least one root")
        draft_tree_id = _new_id()
        normalized_roots = tuple(
            _copy_node(
                root,
                session_id=session_id,
                draft_tree_id=draft_tree_id,
                parent_draft_task_id=None,
            )
            for root in roots
        )
        tree = DraftTaskTree(
            session_id=session_id,
            draft_tree_id=draft_tree_id,
            root_nodes=_sort_nodes(normalized_roots),
            created_by=normalized_roots[0].created_by,
        )
        with self._lock:
            self._load_tree(tree)
            return tree

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        with self._lock:
            tree = self._trees.get((session_id, draft_tree_id))
            if tree is None:
                raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
            return tree

    def list_trees(self, session_id: str) -> list[DraftTaskTree]:
        with self._lock:
            return sorted(
                (tree for tree in self._trees.values() if tree.session_id == session_id),
                key=lambda tree: (tree.created_at, tree.draft_tree_id),
            )

    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]:
        with self._lock:
            self.get_tree(session_id, draft_tree_id)
            return list(_sort_nodes(
                node
                for node in self._nodes.values()
                if node.session_id == session_id and node.draft_tree_id == draft_tree_id
            ))

    def list_children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]:
        with self._lock:
            self.get_tree(session_id, draft_tree_id)
            if parent_draft_task_id is not None:
                parent = self.get_node(session_id, parent_draft_task_id)
                if parent is None or parent.draft_tree_id != draft_tree_id:
                    raise LookupError(f"DraftTaskNode {parent_draft_task_id!r} not found")
            return list(_sort_nodes(
                node
                for node in self._nodes.values()
                if node.session_id == session_id
                and node.draft_tree_id == draft_tree_id
                and node.parent_draft_task_id == parent_draft_task_id
            ))

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None:
        with self._lock:
            node = self._nodes.get((session_id, draft_task_id))
            if node is None or node.session_id != session_id:
                return None
            return node

    def add_node(
        self,
        session_id: str,
        draft_tree_id: str,
        node: DraftTaskNode,
        *,
        expected_tree_version: int,
    ) -> DraftTaskNode:
        with self._lock:
            tree = self.get_tree(session_id, draft_tree_id)
            _check_version(tree.version, expected_tree_version, draft_tree_id)
            key = (session_id, node.draft_task_id)
            if key in self._nodes:
                raise TaskStoreError(f"DraftTaskNode {node.draft_task_id!r} already exists")
            if node.parent_draft_task_id is not None:
                parent = self.get_node(session_id, node.parent_draft_task_id)
                if parent is None or parent.draft_tree_id != draft_tree_id:
                    raise LookupError(
                        f"parent DraftTaskNode {node.parent_draft_task_id!r} not found"
                    )
            normalized = _copy_node(
                node,
                session_id=session_id,
                draft_tree_id=draft_tree_id,
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
            self._nodes[key] = normalized
            self._node_tree[key] = draft_tree_id
            self._bump_tree(session_id, draft_tree_id)
            return normalized

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode:
        with self._lock:
            node = self.get_node(session_id, draft_task_id)
            if node is None:
                raise LookupError(f"DraftTaskNode {draft_task_id!r} not found")
            if node.status != "draft":
                raise TaskStoreError(f"draft task cannot be edited while status is {node.status}")
            if patch.children_ops:
                raise TaskStoreError("children_ops are handled by explicit tree operations")
            if patch.status == "published":
                raise TaskStoreError("published status must be set through mark_published")
            _check_version(node.version, expected_version, draft_task_id)
            updated = _copy_node(
                node,
                title=patch.title or node.title,
                intent=patch.intent or node.intent,
                required_capability=patch.required_capability or node.required_capability,
                constraints=_patched_constraints(node, patch),
                status=patch.status or node.status,
                version=node.version + 1,
                updated_at=_utcnow(),
            )
            self._nodes[(session_id, draft_task_id)] = updated
            self._bump_tree(session_id, node.draft_tree_id)
            return updated

    def mark_accepted(
        self,
        session_id: str,
        draft_tree_id: str,
        *,
        expected_version: int,
    ) -> DraftTaskTree:
        with self._lock:
            tree = self.get_tree(session_id, draft_tree_id)
            _check_version(tree.version, expected_version, draft_tree_id)
            for node in self.list_nodes(session_id, draft_tree_id):
                if node.status not in {"draft", "accepted"}:
                    raise TaskStoreError(
                        f"cannot accept draft tree with {node.status} node "
                        f"{node.draft_task_id!r}"
                    )
            for node in self.list_nodes(session_id, draft_tree_id):
                if node.status == "draft":
                    self._nodes[(session_id, node.draft_task_id)] = _copy_node(
                        node,
                        status="accepted",
                        version=node.version + 1,
                        updated_at=_utcnow(),
                    )
            return self._bump_tree(session_id, draft_tree_id)

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
        *,
        expected_version: int | None = None,
    ) -> DraftTaskTree:
        with self._lock:
            tree = self.get_tree(session_id, draft_tree_id)
            if expected_version is not None:
                _check_version(tree.version, expected_version, draft_tree_id)
            nodes = self.list_nodes(session_id, draft_tree_id)
            for node in nodes:
                if node.status == "cancelled":
                    raise TaskStoreError(
                        f"cannot publish cancelled node {node.draft_task_id!r}"
                    )
            for mapping in mappings:
                if mapping.session_id != session_id or mapping.draft_tree_id != draft_tree_id:
                    raise ValueError("mapping session_id and draft_tree_id must match tree")
                if self.get_node(session_id, mapping.draft_task_id) is None:
                    raise LookupError(
                        f"mapped DraftTaskNode {mapping.draft_task_id!r} not found"
                    )
            for node in nodes:
                if node.status != "published":
                    self._nodes[(session_id, node.draft_task_id)] = _copy_node(
                        node,
                        status="published",
                        version=node.version + 1,
                        updated_at=_utcnow(),
                    )
            for mapping in mappings:
                self._mappings_by_draft[(session_id, mapping.draft_task_id)].append(mapping)
                self._mappings_by_task[(session_id, mapping.task_id)].append(mapping)
            return self._bump_tree(session_id, draft_tree_id)

    def list_for_draft(
        self,
        session_id: str,
        draft_task_id: str,
    ) -> list[DraftToPublishedMapping]:
        with self._lock:
            return list(self._mappings_by_draft.get((session_id, draft_task_id), []))

    def list_for_task(
        self,
        session_id: str,
        task_id: str,
    ) -> list[DraftToPublishedMapping]:
        with self._lock:
            return list(self._mappings_by_task.get((session_id, task_id), []))

    def _load_tree(self, tree: DraftTaskTree) -> None:
        key = (tree.session_id, tree.draft_tree_id)
        if key in self._trees:
            raise TaskStoreError(f"DraftTaskTree {tree.draft_tree_id!r} already exists")
        self._trees[key] = tree
        for node in tree.root_nodes:
            node_key = (node.session_id, node.draft_task_id)
            if node_key in self._nodes:
                raise TaskStoreError(f"DraftTaskNode {node.draft_task_id!r} already exists")
            self._nodes[node_key] = node
            self._node_tree[node_key] = tree.draft_tree_id

    def _bump_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        current = self._trees[(session_id, draft_tree_id)]
        roots = _sort_nodes(
            node
            for node in self._nodes.values()
            if node.session_id == session_id
            and node.draft_tree_id == draft_tree_id
            and node.parent_draft_task_id is None
        )
        updated = _copy_tree(
            current,
            root_nodes=roots,
            version=current.version + 1,
            updated_at=_utcnow(),
        )
        self._trees[(session_id, draft_tree_id)] = updated
        return updated


def _check_version(current: int, expected: int, object_id: str) -> None:
    if current != expected:
        raise VersionConflictError(
            f"stale version for {object_id!r}: expected {expected}, current {current}"
        )


def _copy_raw_task(raw_task: RawTask, **updates: object) -> RawTask:
    return RawTask.model_validate({**raw_task.model_dump(), **updates})


def _copy_node(node: DraftTaskNode, **updates: object) -> DraftTaskNode:
    return DraftTaskNode.model_validate({**node.model_dump(), **updates})


def _copy_tree(tree: DraftTaskTree, **updates: object) -> DraftTaskTree:
    return DraftTaskTree.model_validate({**tree.model_dump(), **updates})


def _sort_nodes(nodes: Iterable[DraftTaskNode]) -> tuple[DraftTaskNode, ...]:
    return tuple(
        sorted(
            nodes,
            key=lambda node: (
                node.parent_draft_task_id or "",
                node.order_index,
                node.created_at,
                node.draft_task_id,
            ),
        )
    )


def _patched_constraints(node: DraftTaskNode, patch: TaskNodePatch) -> tuple[str, ...]:
    removed = set(patch.constraints_remove)
    constraints = [constraint for constraint in node.constraints if constraint not in removed]
    for constraint in patch.constraints_add:
        if constraint not in constraints:
            constraints.append(constraint)
    return tuple(constraints)
