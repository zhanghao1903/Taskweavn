"""Tests for SQLite-backed TaskBus."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from taskweavn.task import (
    SqliteTaskBus,
    TaskBus,
    TaskDispatchConstraints,
    TaskDomain,
    TaskStatus,
    TaskStore,
)
from taskweavn.task.stores import TaskStoreError


def test_protocol_conformance(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        assert isinstance(bus, TaskBus)
        assert isinstance(bus, TaskStore)
    finally:
        bus.close()


def test_publish_and_get_round_trip(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    task = _root("root", metadata={"source": "test"})
    try:
        published = bus.publish(task)
        loaded = bus.get("s1", "root")

        assert published == task
        assert loaded == task
        assert loaded is not None
        assert loaded.dispatch_constraints is not None
        assert loaded.dispatch_constraints.metadata["source"] == "test"
    finally:
        bus.close()


def test_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "tasks.sqlite"
    first = SqliteTaskBus(db)
    try:
        first.publish(_root("root"))
    finally:
        first.close()

    second = SqliteTaskBus(db)
    try:
        loaded = second.get("s1", "root")
        assert loaded is not None
        assert loaded.task_id == "root"
        assert loaded.session_id == "s1"
        assert loaded.intent == "Do root"
        assert loaded.required_capability == "general"
    finally:
        second.close()


def test_context_manager_closes_connection(tmp_path: Path) -> None:
    with SqliteTaskBus(tmp_path / "nested" / "tasks.sqlite") as bus:
        bus.publish(_root("root"))

    with pytest.raises(sqlite3.ProgrammingError):
        bus.list_for_session("s1")


def test_list_for_session_is_ordered_and_isolated(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("b", order_index=1))
        bus.publish(_root("a", order_index=0))
        bus.publish(_root("other", session_id="s2"))

        # Session listing follows the existing InMemoryTaskBus contract:
        # chronological first, then order_index as a tie-breaker.
        assert [task.task_id for task in bus.list_for_session("s1")] == ["b", "a"]
        assert [task.task_id for task in bus.list_for_session("s2")] == ["other"]
    finally:
        bus.close()


def test_list_children_orders_roots_and_children(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    root = _root("root")
    child_b = _child("child-b", parent_id="root", root_id="root", order_index=1)
    child_a = _child("child-a", parent_id="root", root_id="root", order_index=0)
    try:
        bus.publish(root)
        bus.publish(child_b)
        bus.publish(child_a)

        assert [task.task_id for task in bus.list_children("s1", None)] == ["root"]
        assert [task.task_id for task in bus.list_children("s1", "root")] == [
            "child-a",
            "child-b",
        ]
    finally:
        bus.close()


def test_duplicate_task_is_rejected(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))

        with pytest.raises(TaskStoreError, match="already exists"):
            bus.publish(_root("root"))
    finally:
        bus.close()


def test_child_requires_existing_parent(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        with pytest.raises(TaskStoreError, match="parent task 'missing' not found"):
            bus.publish(_child("child", parent_id="missing", root_id="missing"))
    finally:
        bus.close()


def test_child_root_id_must_match_parent(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))

        with pytest.raises(TaskStoreError, match="root_id must match"):
            bus.publish(_child("child", parent_id="root", root_id="other-root"))
    finally:
        bus.close()


def test_non_pending_publish_is_rejected(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        with pytest.raises(TaskStoreError, match="must enter TaskBus as pending"):
            bus.publish(_root("root", status="done"))
    finally:
        bus.close()


def test_claim_next_moves_first_eligible_task_to_running(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("general-a", order_index=1))
        bus.publish(_root("special", capability="special", order_index=0))
        bus.publish(_root("general-b", order_index=0))

        claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")

        assert claimed is not None
        # Claim order follows TaskBus listing: created_at first, then order_index.
        assert claimed.task_id == "general-a"
        assert claimed.status == "running"
        assert claimed.claimed_by == "agent-1"
        assert claimed.started_at is not None
        assert bus.get("s1", "general-a") == claimed

        assert bus.claim_next("s1", capability="missing", agent_id="agent-1") is None
    finally:
        bus.close()


def test_claim_next_waits_for_parent_done(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        bus.publish(_child("child", parent_id="root", root_id="root"))

        claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")
        assert claimed is not None
        assert claimed.task_id == "root"
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None

        bus.complete("s1", "root", result_ref="result:root")
        child = bus.claim_next("s1", capability="general", agent_id="agent-1")

        assert child is not None
        assert child.task_id == "child"
    finally:
        bus.close()


def test_complete_running_task_records_result(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")
        assert claimed is not None

        completed = bus.complete("s1", "root", result_ref="result:root")

        assert completed.status == "done"
        assert completed.result_ref == "result:root"
        assert completed.error_ref is None
        assert completed.completed_at is not None
        assert bus.get("s1", "root") == completed
    finally:
        bus.close()


def test_complete_requires_running_task(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))

        with pytest.raises(TaskStoreError, match="only running tasks"):
            bus.complete("s1", "root")
    finally:
        bus.close()


def test_fail_running_task_records_error(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None

        failed = bus.fail("s1", "root", error_ref="error:root")

        assert failed.status == "failed"
        assert failed.error_ref == "error:root"
        assert failed.result_ref is None
        assert failed.completed_at is not None
    finally:
        bus.close()


def test_skip_marks_pending_task_failed_with_reason(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))

        skipped = bus.skip("s1", "root", reason="user skipped optional work")

        assert skipped.status == "failed"
        assert skipped.error_ref == "skipped: user skipped optional work"
        assert skipped.completed_at is not None
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None
    finally:
        bus.close()


def test_lifecycle_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "tasks.sqlite"
    first = SqliteTaskBus(db)
    try:
        first.publish(_root("root"))
        assert first.claim_next("s1", capability="general", agent_id="agent-1") is not None
        first.complete("s1", "root", result_ref="result:root")
    finally:
        first.close()

    second = SqliteTaskBus(db)
    try:
        loaded = second.get("s1", "root")
        assert loaded is not None
        assert loaded.status == "done"
        assert loaded.result_ref == "result:root"
        assert loaded.claimed_by == "agent-1"
    finally:
        second.close()


def _root(
    task_id: str,
    *,
    session_id: str = "s1",
    order_index: int = 0,
    status: TaskStatus = "pending",
    capability: str = "general",
    metadata: dict[str, object] | None = None,
) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id=session_id,
        root_id=task_id,
        order_index=order_index,
        intent=f"Do {task_id}",
        required_capability=capability,
        status=status,
        created_by="tester",
        dispatch_constraints=TaskDispatchConstraints(
            required_capabilities=(capability,),
            metadata=dict(metadata or {"title": task_id.title()}),
        ),
    )


def _child(
    task_id: str,
    *,
    parent_id: str,
    root_id: str,
    order_index: int = 0,
) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        parent_id=parent_id,
        root_id=root_id,
        order_index=order_index,
        intent=f"Do {task_id}",
        required_capability="general",
        created_by="tester",
    )
