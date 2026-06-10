"""Tests for in-memory authoring stores."""

from __future__ import annotations

import pytest

from taskweavn.task import (
    DraftTaskNode,
    DraftTaskStatus,
    DraftTaskStore,
    DraftToPublishedMapping,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    RawTask,
    RawTaskStore,
    TaskNodePatch,
    TaskStoreError,
    VersionConflictError,
)


def _raw_task(raw_task_id: str = "raw1", session_id: str = "s1") -> RawTask:
    return RawTask(
        raw_task_id=raw_task_id,
        session_id=session_id,
        source_message_id=f"msg-{raw_task_id}",
        user_input="Build a small docs site",
    )


def _draft_node(
    draft_task_id: str,
    *,
    session_id: str = "s1",
    draft_tree_id: str = "placeholder",
    parent_draft_task_id: str | None = None,
    order_index: int = 0,
    status: DraftTaskStatus = "draft",
) -> DraftTaskNode:
    return DraftTaskNode(
        draft_task_id=draft_task_id,
        session_id=session_id,
        draft_tree_id=draft_tree_id,
        parent_draft_task_id=parent_draft_task_id,
        order_index=order_index,
        title=f"Task {draft_task_id}",
        intent=f"Do {draft_task_id}",
        required_capability="general",
        status=status,
    )


def test_raw_task_store_protocol_conformance() -> None:
    assert isinstance(InMemoryRawTaskStore(), RawTaskStore)


def test_raw_task_store_create_get_list_and_save() -> None:
    store = InMemoryRawTaskStore()
    raw = store.create(_raw_task())
    changed = raw.model_copy(update={"intent_summary": "Build docs"})

    saved = store.save(changed, expected_version=1)

    assert saved.version == 2
    assert saved.intent_summary == "Build docs"
    assert store.get("s1", raw.raw_task_id) == saved
    assert store.list_for_session("s1") == [saved]


def test_raw_task_store_rejects_stale_version() -> None:
    store = InMemoryRawTaskStore([_raw_task()])

    with pytest.raises(VersionConflictError, match="stale version"):
        store.save(_raw_task(), expected_version=2)


def test_raw_task_store_is_session_isolated() -> None:
    store = InMemoryRawTaskStore([_raw_task("raw1", "s1"), _raw_task("raw1", "s2")])
    s1_raw = store.get("s1", "raw1")
    s2_raw = store.get("s2", "raw1")

    assert s1_raw is not None
    assert s2_raw is not None
    assert s1_raw.session_id == "s1"
    assert s2_raw.session_id == "s2"
    assert len(store.list_for_session("s1")) == 1


def test_draft_task_store_protocol_conformance() -> None:
    assert isinstance(InMemoryDraftTaskStore(), DraftTaskStore)


def test_draft_store_creates_tree_and_normalizes_roots() -> None:
    store = InMemoryDraftTaskStore()

    tree = store.create_tree(
        "s1",
        [_draft_node("b", order_index=2), _draft_node("a", order_index=1)],
        title="Release plan",
        summary="Prepare release artifacts.",
    )

    assert tree.session_id == "s1"
    assert tree.title == "Release plan"
    assert tree.summary == "Prepare release artifacts."
    assert [node.draft_task_id for node in tree.root_nodes] == ["a", "b"]
    assert {node.draft_tree_id for node in tree.root_nodes} == {tree.draft_tree_id}
    assert store.get_tree("s1", tree.draft_tree_id) == tree


def test_draft_store_adds_and_traverses_children() -> None:
    store = InMemoryDraftTaskStore()
    tree = store.create_tree("s1", [_draft_node("root")])
    root = tree.root_nodes[0]

    child = store.add_node(
        "s1",
        tree.draft_tree_id,
        _draft_node("child", parent_draft_task_id=root.draft_task_id),
        expected_tree_version=tree.version,
    )

    assert child.parent_draft_task_id == root.draft_task_id
    assert child.draft_tree_id == tree.draft_tree_id
    assert store.list_children("s1", tree.draft_tree_id, root.draft_task_id) == [child]
    assert {node.draft_task_id for node in store.list_nodes("s1", tree.draft_tree_id)} == {
        "root",
        "child",
    }


def test_draft_store_rejects_stale_tree_version_on_add() -> None:
    store = InMemoryDraftTaskStore()
    tree = store.create_tree("s1", [_draft_node("root")])

    with pytest.raises(VersionConflictError, match="stale version"):
        store.add_node(
            "s1",
            tree.draft_tree_id,
            _draft_node("child", parent_draft_task_id="root"),
            expected_tree_version=tree.version + 1,
        )


def test_draft_store_updates_node_and_tree_version() -> None:
    store = InMemoryDraftTaskStore()
    tree = store.create_tree("s1", [_draft_node("root", order_index=0)])

    updated = store.update_node(
        "s1",
        "root",
        TaskNodePatch(
            title="Better title",
            summary="Short summary.",
            instructions="Do the careful version.",
            acceptance_criteria=("Criterion one",),
            constraints_add=("must use tests",),
        ),
        expected_version=1,
    )

    assert updated.version == 2
    assert updated.title == "Better title"
    assert updated.summary == "Short summary."
    assert updated.instructions == "Do the careful version."
    assert updated.acceptance_criteria == ("Criterion one",)
    assert updated.constraints == ("must use tests",)
    assert store.get_tree("s1", tree.draft_tree_id).version == 2


def test_draft_store_rejects_stale_node_version() -> None:
    store = InMemoryDraftTaskStore()
    store.create_tree("s1", [_draft_node("root")])

    with pytest.raises(VersionConflictError):
        store.update_node("s1", "root", TaskNodePatch(title="New"), expected_version=2)


def test_draft_store_marks_accepted_readonly() -> None:
    store = InMemoryDraftTaskStore()
    tree = store.create_tree("s1", [_draft_node("root")])

    accepted = store.mark_accepted("s1", tree.draft_tree_id, expected_version=tree.version)
    accepted_node = store.get_node("s1", "root")

    assert accepted.version == 2
    assert accepted_node is not None
    assert accepted_node.status == "accepted"
    with pytest.raises(TaskStoreError, match="cannot be edited"):
        store.update_node("s1", "root", TaskNodePatch(title="Nope"), expected_version=2)


def test_draft_store_marks_published_and_indexes_mappings() -> None:
    store = InMemoryDraftTaskStore()
    tree = store.create_tree("s1", [_draft_node("root")])
    mapping = DraftToPublishedMapping(
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        draft_task_id="root",
        task_id="task-root",
        publish_command_id="cmd1",
    )

    published = store.mark_published("s1", tree.draft_tree_id, [mapping])
    published_node = store.get_node("s1", "root")

    assert published.version == 2
    assert published_node is not None
    assert published_node.status == "published"
    assert store.list_for_draft("s1", "root") == [mapping]
    assert store.list_for_task("s1", "task-root") == [mapping]


def test_draft_store_rejects_stale_tree_version_on_publish() -> None:
    store = InMemoryDraftTaskStore()
    tree = store.create_tree("s1", [_draft_node("root")])

    with pytest.raises(VersionConflictError, match="stale version"):
        store.mark_published("s1", tree.draft_tree_id, [], expected_version=tree.version + 1)


def test_draft_store_rejects_cancelled_tree_publish() -> None:
    store = InMemoryDraftTaskStore()
    tree = store.create_tree("s1", [_draft_node("root", status="cancelled")])

    with pytest.raises(TaskStoreError, match="cancelled"):
        store.mark_published("s1", tree.draft_tree_id, [])
