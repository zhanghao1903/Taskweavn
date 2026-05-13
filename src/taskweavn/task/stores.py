"""Store protocols for Task domain and draft authoring facts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskweavn.task.models import (
    DraftTaskNode,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskDomain,
    TaskNodePatch,
)


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
class DraftTaskStore(Protocol):
    """Persistence boundary for unpublished Task authoring facts."""

    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree: ...

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree: ...

    def list_trees(self, session_id: str) -> list[DraftTaskTree]: ...

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None: ...

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode: ...

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
    ) -> DraftTaskTree: ...
