"""Tests for SQLite-backed authoring stores."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from taskweavn.task import (
    DraftTaskNode,
    DraftTaskStatus,
    DraftTaskStore,
    DraftToPublishedMapping,
    FeasibilityReport,
    RawTask,
    RawTaskAnswer,
    RawTaskAsk,
    RawTaskStore,
    SqliteDraftTaskStore,
    SqliteRawTaskStore,
    TaskNodePatch,
    TaskStoreError,
    VersionConflictError,
)


def _raw_task(raw_task_id: str = "raw1", session_id: str = "s1") -> RawTask:
    ask = RawTaskAsk(
        ask_id=f"ask-{raw_task_id}",
        raw_task_id=raw_task_id,
        question="Which site style should Plato use?",
        required=False,
        reason="Theme choice affects the generated plan.",
    )
    answer = RawTaskAnswer(
        answer_id=f"answer-{raw_task_id}",
        raw_task_id=raw_task_id,
        ask_id=ask.ask_id,
        value="minimal portfolio",
        source_message_id=f"answer-msg-{raw_task_id}",
    )
    return RawTask(
        raw_task_id=raw_task_id,
        session_id=session_id,
        source_message_id=f"msg-{raw_task_id}",
        user_input="Build a small docs site",
        status="ready_to_plan",
        intent_summary="Build docs",
        feasibility=FeasibilityReport(
            status="ready",
            confidence=0.9,
            reasons=("Static site generation is supported.",),
        ),
        asks=(ask,),
        answers=(answer,),
        constraints=("use sqlite",),
        assumptions=("local first",),
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


def test_sqlite_raw_task_store_protocol_conformance(tmp_path: Path) -> None:
    store = SqliteRawTaskStore(tmp_path / "authoring.sqlite")
    try:
        assert isinstance(store, RawTaskStore)
    finally:
        store.close()


def test_sqlite_raw_task_create_save_and_reopen(tmp_path: Path) -> None:
    db = tmp_path / "authoring.sqlite"
    first = SqliteRawTaskStore(db)
    try:
        raw = first.create(_raw_task())
        changed = raw.model_copy(update={"intent_summary": "Build docs site"})
        saved = first.save(changed, expected_version=1)

        assert saved.version == 2
        assert saved.intent_summary == "Build docs site"
        assert first.list_for_session("s1") == [saved]
    finally:
        first.close()

    second = SqliteRawTaskStore(db)
    try:
        loaded = second.get("s1", "raw1")

        assert loaded == saved
        assert loaded is not None
        assert loaded.feasibility is not None
        assert loaded.feasibility.status == "ready"
        assert loaded.asks[0].question == "Which site style should Plato use?"
        assert loaded.answers[0].value == "minimal portfolio"
    finally:
        second.close()


def test_sqlite_raw_task_rejects_duplicate_and_stale_version(tmp_path: Path) -> None:
    store = SqliteRawTaskStore(tmp_path / "authoring.sqlite")
    try:
        store.create(_raw_task())

        with pytest.raises(TaskStoreError, match="already exists"):
            store.create(_raw_task())

        with pytest.raises(VersionConflictError, match="stale version"):
            store.save(_raw_task(), expected_version=2)
    finally:
        store.close()


def test_sqlite_raw_task_store_is_session_isolated(tmp_path: Path) -> None:
    store = SqliteRawTaskStore(tmp_path / "authoring.sqlite")
    try:
        store.create(_raw_task("raw1", "s1"))
        store.create(_raw_task("raw1", "s2"))

        assert len(store.list_for_session("s1")) == 1
        assert store.get("s1", "raw1") is not None
        assert store.get("s2", "raw1") is not None
    finally:
        store.close()


def test_sqlite_draft_task_store_protocol_conformance(tmp_path: Path) -> None:
    store = SqliteDraftTaskStore(tmp_path / "authoring.sqlite")
    try:
        assert isinstance(store, DraftTaskStore)
    finally:
        store.close()


def test_sqlite_draft_store_creates_tree_and_reopens_roots(tmp_path: Path) -> None:
    db = tmp_path / "authoring.sqlite"
    first = SqliteDraftTaskStore(db)
    try:
        tree = first.create_tree(
            "s1",
            [_draft_node("b", order_index=2), _draft_node("a", order_index=1)],
        )

        assert [node.draft_task_id for node in tree.root_nodes] == ["a", "b"]
        assert {node.draft_tree_id for node in tree.root_nodes} == {tree.draft_tree_id}
    finally:
        first.close()

    second = SqliteDraftTaskStore(db)
    try:
        loaded = second.get_tree("s1", tree.draft_tree_id)

        assert loaded == tree
        assert [node.draft_task_id for node in second.list_nodes("s1", tree.draft_tree_id)] == [
            "a",
            "b",
        ]
    finally:
        second.close()


def test_sqlite_draft_store_adds_updates_and_reopens_nodes(tmp_path: Path) -> None:
    db = tmp_path / "authoring.sqlite"
    first = SqliteDraftTaskStore(db)
    try:
        tree = first.create_tree("s1", [_draft_node("root")])
        root = tree.root_nodes[0]
        child = first.add_node(
            "s1",
            tree.draft_tree_id,
            _draft_node("child", parent_draft_task_id=root.draft_task_id),
            expected_tree_version=tree.version,
        )
        updated = first.update_node(
            "s1",
            "child",
            TaskNodePatch(
                title="Better child",
                constraints_add=("must use tests",),
            ),
            expected_version=child.version,
        )

        assert updated.version == 2
        assert updated.title == "Better child"
        assert updated.constraints == ("must use tests",)
    finally:
        first.close()

    second = SqliteDraftTaskStore(db)
    try:
        loaded_child = second.get_node("s1", "child")

        assert loaded_child == updated
        assert second.list_children("s1", tree.draft_tree_id, "root") == [updated]
        assert second.get_tree("s1", tree.draft_tree_id).version == 3
    finally:
        second.close()


def test_sqlite_draft_store_rejects_stale_tree_and_node_versions(
    tmp_path: Path,
) -> None:
    store = SqliteDraftTaskStore(tmp_path / "authoring.sqlite")
    try:
        tree = store.create_tree("s1", [_draft_node("root")])

        with pytest.raises(VersionConflictError, match="stale version"):
            store.add_node(
                "s1",
                tree.draft_tree_id,
                _draft_node("child", parent_draft_task_id="root"),
                expected_tree_version=tree.version + 1,
            )

        with pytest.raises(VersionConflictError, match="stale version"):
            store.update_node(
                "s1",
                "root",
                TaskNodePatch(title="New title"),
                expected_version=2,
            )
    finally:
        store.close()


def test_sqlite_draft_store_marks_accepted_readonly_and_reopens(
    tmp_path: Path,
) -> None:
    db = tmp_path / "authoring.sqlite"
    first = SqliteDraftTaskStore(db)
    try:
        tree = first.create_tree("s1", [_draft_node("root")])
        accepted = first.mark_accepted(
            "s1",
            tree.draft_tree_id,
            expected_version=tree.version,
        )

        assert accepted.version == 2
        accepted_root = first.get_node("s1", "root")
        assert accepted_root is not None
        assert accepted_root.status == "accepted"
        with pytest.raises(TaskStoreError, match="cannot be edited"):
            first.update_node("s1", "root", TaskNodePatch(title="Nope"), expected_version=2)
    finally:
        first.close()

    second = SqliteDraftTaskStore(db)
    try:
        root = second.get_node("s1", "root")

        assert root is not None
        assert root.status == "accepted"
        assert second.get_tree("s1", tree.draft_tree_id).version == 2
    finally:
        second.close()


def test_sqlite_draft_store_publishes_mappings_and_reopens(
    tmp_path: Path,
) -> None:
    db = tmp_path / "authoring.sqlite"
    first = SqliteDraftTaskStore(db)
    try:
        tree = first.create_tree("s1", [_draft_node("root")])
        mapping = DraftToPublishedMapping(
            session_id="s1",
            draft_tree_id=tree.draft_tree_id,
            draft_task_id="root",
            task_id="task-root",
            publish_command_id="cmd1",
        )

        published = first.mark_published("s1", tree.draft_tree_id, [mapping])

        assert published.version == 2
        published_root = first.get_node("s1", "root")
        assert published_root is not None
        assert published_root.status == "published"
    finally:
        first.close()

    second = SqliteDraftTaskStore(db)
    try:
        root = second.get_node("s1", "root")

        assert root is not None
        assert root.status == "published"
        assert second.get_tree("s1", tree.draft_tree_id).version == 2
        assert second.list_for_draft("s1", "root") == [mapping]
        assert second.list_for_task("s1", "task-root") == [mapping]
    finally:
        second.close()


def test_sqlite_draft_store_rejects_duplicate_node_and_cancelled_publish(
    tmp_path: Path,
) -> None:
    store = SqliteDraftTaskStore(tmp_path / "authoring.sqlite")
    try:
        tree = store.create_tree("s1", [_draft_node("root", status="cancelled")])

        with pytest.raises(TaskStoreError, match="already exists"):
            store.add_node(
                "s1",
                tree.draft_tree_id,
                _draft_node("root"),
                expected_tree_version=tree.version,
            )

        with pytest.raises(TaskStoreError, match="cancelled"):
            store.mark_published("s1", tree.draft_tree_id, [])
    finally:
        store.close()


def test_sqlite_authoring_store_context_manager_closes_connection(
    tmp_path: Path,
) -> None:
    with SqliteRawTaskStore(tmp_path / "authoring.sqlite") as store:
        store.create(_raw_task())

    with pytest.raises(sqlite3.ProgrammingError):
        store.list_for_session("s1")
