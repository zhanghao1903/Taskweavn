"""Tests for durable Plan / TaskNode stores."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from taskweavn.task import (
    DraftTaskNode,
    Plan,
    PlanStore,
    PlanStoreError,
    PlanTaskNode,
    SqliteDraftTaskStore,
    SqlitePlanStore,
    TaskRef,
    VersionConflictError,
)


def _plan(
    plan_id: str = "plan-1",
    *,
    session_id: str = "session-1",
    source_draft_tree_id: str | None = None,
) -> Plan:
    return Plan(
        plan_id=plan_id,
        session_id=session_id,
        source_draft_tree_id=source_draft_tree_id,
        title="Website publishing plan",
        objective="Explain how to publish a website.",
        summary="A plan covering domain, hosting, DNS, deployment, and verification.",
        created_by="collaborator_agent",
    )


def _node(
    task_node_id: str,
    *,
    plan_id: str = "plan-1",
    session_id: str = "session-1",
    task_index: str = "1",
    order_index: int = 0,
    depends_on: tuple[str, ...] = (),
) -> PlanTaskNode:
    return PlanTaskNode(
        task_node_id=task_node_id,
        plan_id=plan_id,
        session_id=session_id,
        task_index=task_index,
        order_index=order_index,
        title=f"Task {task_index}",
        intent=f"Do Task {task_index}",
        summary=f"Summary for Task {task_index}",
        instructions=f"Instructions for Task {task_index}",
        required_capability="workspace.basic",
        depends_on=depends_on,
        constraints=("Keep it local first.",),
        acceptance_criteria=("The explanation is clear.",),
        draft_ref=TaskRef.draft(f"draft-{task_index}"),
    )


def _draft_node(
    draft_task_id: str,
    *,
    session_id: str = "session-1",
    draft_tree_id: str = "placeholder",
) -> DraftTaskNode:
    return DraftTaskNode(
        draft_task_id=draft_task_id,
        session_id=session_id,
        draft_tree_id=draft_tree_id,
        title="Legacy draft task",
        intent="Keep legacy DraftTaskTree readable.",
        required_capability="workspace.basic",
    )


def test_sqlite_plan_store_protocol_conformance(tmp_path: Path) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        assert isinstance(store, PlanStore)
    finally:
        store.close()


def test_sqlite_plan_store_persists_plan_and_task_nodes_after_reopen(
    tmp_path: Path,
) -> None:
    db = tmp_path / "authoring.sqlite"
    first = SqlitePlanStore(db)
    try:
        plan = _plan()
        node_one = _node("node-1", task_index="1", order_index=1)
        node_two = _node(
            "node-2",
            task_index="2",
            order_index=2,
            depends_on=("node-1",),
        )
        saved = first.create_plan(plan, (node_two, node_one))

        assert saved.task_node_ids == ("node-1", "node-2")
        assert first.get_active_plan("session-1") == saved
    finally:
        first.close()

    second = SqlitePlanStore(db)
    try:
        loaded = second.get_plan("session-1", "plan-1")
        nodes = second.list_task_nodes("session-1", "plan-1")

        assert loaded == saved
        assert [node.task_node_id for node in nodes] == ["node-1", "node-2"]
        assert nodes[0].draft_ref == TaskRef.draft("draft-1")
        assert nodes[1].depends_on == ("node-1",)
    finally:
        second.close()


def test_sqlite_plan_store_migrates_error_ref_column(tmp_path: Path) -> None:
    db = tmp_path / "authoring.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
            CREATE TABLE plan_schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE plans (
                session_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                source_raw_task_id TEXT,
                source_draft_tree_id TEXT,
                title TEXT NOT NULL,
                objective TEXT NOT NULL,
                summary TEXT NOT NULL,
                status TEXT NOT NULL,
                context_policy_json TEXT NOT NULL,
                finalization_json TEXT NOT NULL,
                outcome_json TEXT,
                version INTEGER NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT,
                PRIMARY KEY (session_id, plan_id)
            );
            CREATE TABLE plan_task_nodes (
                session_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                task_node_id TEXT NOT NULL,
                task_index TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                intent TEXT NOT NULL,
                summary TEXT NOT NULL,
                instructions TEXT NOT NULL,
                required_capability TEXT,
                depends_on_json TEXT NOT NULL,
                constraints_json TEXT NOT NULL,
                acceptance_criteria_json TEXT NOT NULL,
                readiness TEXT NOT NULL,
                execution TEXT NOT NULL,
                draft_ref_json TEXT,
                published_ref_json TEXT,
                result_ref TEXT,
                file_summary_ref TEXT,
                audit_ref TEXT,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (session_id, task_node_id)
            );
            """
        )
    finally:
        conn.close()

    store = SqlitePlanStore(db)
    try:
        store.create_plan(
            _plan("plan-migrated"),
            (_node("node-migrated", plan_id="plan-migrated"),),
        )
        node = store.get_task_node("session-1", "node-migrated")
        assert node is not None
        assert node.error_ref is None
    finally:
        store.close()

    conn = sqlite3.connect(db)
    try:
        columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(plan_task_nodes)")
        }
        assert "error_ref" in columns
    finally:
        conn.close()


def test_sqlite_plan_store_rejects_duplicate_task_index(tmp_path: Path) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        store.create_plan(_plan(), (_node("node-1"),))

        with pytest.raises(PlanStoreError, match="PlanTaskNode already exists"):
            store.add_task_node(
                _node("node-2", task_index="1", order_index=2),
                expected_plan_version=1,
            )
    finally:
        store.close()


def test_sqlite_plan_store_rejects_unknown_task_node_dependencies(
    tmp_path: Path,
) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        with pytest.raises(ValueError, match="unknown depends_on"):
            store.create_plan(_plan(), (_node("node-1", depends_on=("missing",)),))
    finally:
        store.close()


def test_sqlite_plan_store_rejects_stale_plan_and_task_node_versions(
    tmp_path: Path,
) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        created = store.create_plan(_plan(), (_node("node-1"),))
        saved = store.save_plan(
            created.model_copy(update={"summary": "Updated plan summary."}),
            expected_version=1,
        )

        assert saved.version == 2

        with pytest.raises(VersionConflictError, match="stale version"):
            store.save_plan(
                saved.model_copy(update={"summary": "Stale update."}),
                expected_version=1,
            )

        node = store.get_task_node("session-1", "node-1")
        assert node is not None
        running = store.save_task_node(
            node.model_copy(update={"execution": "running"}),
            expected_version=1,
        )

        assert running.version == 2

        with pytest.raises(VersionConflictError, match="stale version"):
            store.save_task_node(
                running.model_copy(update={"execution": "done"}),
                expected_version=1,
            )
    finally:
        store.close()


def test_sqlite_plan_store_keeps_legacy_draft_tree_read_path(
    tmp_path: Path,
) -> None:
    db = tmp_path / "authoring.sqlite"
    legacy = SqliteDraftTaskStore(db)
    try:
        legacy_tree = legacy.create_tree(
            "session-1",
            [_draft_node("legacy-node-1")],
            title="Legacy tree",
            summary="Legacy DraftTaskTree remains the read path.",
        )
    finally:
        legacy.close()

    plan_store = SqlitePlanStore(db)
    try:
        plan_store.create_plan(
            _plan(source_draft_tree_id=legacy_tree.draft_tree_id),
            (_node("node-1"),),
        )
    finally:
        plan_store.close()

    reopened_legacy = SqliteDraftTaskStore(db)
    try:
        loaded = reopened_legacy.get_tree("session-1", legacy_tree.draft_tree_id)

        assert loaded == legacy_tree
        assert loaded.root_nodes[0].draft_task_id == "legacy-node-1"
    finally:
        reopened_legacy.close()
