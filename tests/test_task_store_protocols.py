"""Tests for Task store Protocol boundaries."""

from __future__ import annotations

from taskweavn.task import (
    DraftTaskNode,
    DraftTaskStore,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskDomain,
    TaskNodePatch,
    TaskStore,
)


class _FakeTaskStore:
    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        return None

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        return []

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        return []


class _FakeDraftTaskStore:
    def create_tree(
        self,
        session_id: str,
        roots: list[DraftTaskNode],
        *,
        title: str | None = None,
        summary: str | None = None,
    ) -> DraftTaskTree:
        return DraftTaskTree(
            session_id=session_id,
            draft_tree_id="tree1",
            title=title,
            summary=summary,
            root_nodes=tuple(roots),
        )

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        root = DraftTaskNode(
            session_id=session_id,
            draft_tree_id=draft_tree_id,
            title="Root",
            intent="Do work",
            required_capability="general",
        )
        return DraftTaskTree(session_id=session_id, draft_tree_id=draft_tree_id, root_nodes=(root,))

    def list_trees(self, session_id: str) -> list[DraftTaskTree]:
        return []

    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]:
        return []

    def list_children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]:
        return []

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None:
        return None

    def add_node(
        self,
        session_id: str,
        draft_tree_id: str,
        node: DraftTaskNode,
        *,
        expected_tree_version: int,
    ) -> DraftTaskNode:
        return node.model_copy(
            update={"session_id": session_id, "draft_tree_id": draft_tree_id}
        )

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode:
        return DraftTaskNode(
            draft_task_id=draft_task_id,
            session_id=session_id,
            draft_tree_id="tree1",
            title=patch.title or "Root",
            intent=patch.intent or "Do work",
            required_capability=patch.required_capability or "general",
            version=expected_version + 1,
        )

    def mark_accepted(
        self,
        session_id: str,
        draft_tree_id: str,
        *,
        expected_version: int,
    ) -> DraftTaskTree:
        return self.get_tree(session_id, draft_tree_id)

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
        *,
        expected_version: int | None = None,
    ) -> DraftTaskTree:
        root = DraftTaskNode(
            session_id=session_id,
            draft_tree_id=draft_tree_id,
            title="Root",
            intent=f"Published {len(mappings)} tasks",
            required_capability="general",
            status="published",
        )
        return DraftTaskTree(session_id=session_id, draft_tree_id=draft_tree_id, root_nodes=(root,))


def test_task_store_protocol_conformance() -> None:
    assert isinstance(_FakeTaskStore(), TaskStore)


def test_draft_task_store_protocol_conformance() -> None:
    assert isinstance(_FakeDraftTaskStore(), DraftTaskStore)
