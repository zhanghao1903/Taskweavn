"""Tests for SQLite-backed TaskBus."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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


def test_reads_legacy_null_confirmation_payload_field(tmp_path: Path) -> None:
    db = tmp_path / "tasks.sqlite"
    first = SqliteTaskBus(db)
    try:
        first.publish(_root("root"))
    finally:
        first.close()

    with sqlite3.connect(db) as conn:
        payload = json.loads(
            conn.execute(
                "SELECT payload FROM tasks WHERE session_id = ? AND task_id = ?",
                ("s1", "root"),
            ).fetchone()[0]
        )
        payload["waiting_for_confirmation_id"] = None
        conn.execute(
            "UPDATE tasks SET payload = ? WHERE session_id = ? AND task_id = ?",
            (json.dumps(payload), "s1", "root"),
        )

    second = SqliteTaskBus(db)
    try:
        loaded = second.get("s1", "root")
    finally:
        second.close()

    assert loaded is not None
    assert loaded.task_id == "root"
    assert loaded.status == "pending"


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


def test_retry_failed_task_in_place_before_child_runs(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
        bus.fail("s1", "root", error_ref="error:root")
        bus.publish(_child("child", parent_id="root", root_id="root"))

        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None

        retried = bus.retry("s1", "root", instruction="Try safer steps")
        retry_claim = bus.claim_next("s1", capability="general", agent_id="agent-1")

        assert retried.task_id == "root"
        assert retried.status == "pending"
        assert retried.error_ref is None
        assert "Retry instruction" in retried.intent
        assert retry_claim is not None
        assert retry_claim.task_id == "root"
        bus.complete("s1", "root", result_ref="result:root")

        child = bus.claim_next("s1", capability="general", agent_id="agent-1")

        assert child is not None
        assert child.task_id == "child"
    finally:
        bus.close()


def test_retry_preserves_original_queue_position(
    tmp_path: Path,
) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root", created_at=_time(0)))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
        bus.fail("s1", "root", error_ref="error:root")
        bus.publish(_root("later", created_at=_time(1)))
        bus.retry("s1", "root")

        claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")

        assert claimed is not None
        assert claimed.task_id == "root"
    finally:
        bus.close()


def test_waiting_for_user_round_trip_resume_and_claim(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")
        assert claimed is not None

        waiting = bus.wait_for_user("s1", "root", ask_id="ask-1")
        loaded_waiting = bus.get("s1", "root")

        assert waiting.status == "waiting_for_user"
        assert waiting.waiting_for_ask_id == "ask-1"
        assert waiting.waiting_for_user_since is not None
        assert loaded_waiting == waiting
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None

        resumed = bus.resume_after_user("s1", "root", ask_id="ask-1")
        retry_claim = bus.claim_next("s1", capability="general", agent_id="agent-2")

        assert resumed.status == "pending"
        assert resumed.waiting_for_ask_id is None
        assert resumed.waiting_for_user_since is None
        assert resumed.claimed_by is None
        assert resumed.started_at is None
        assert retry_claim is not None
        assert retry_claim.task_id == "root"
        assert retry_claim.claimed_by == "agent-2"
    finally:
        bus.close()


def test_waiting_for_confirmation_round_trip_resume_and_claim(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")
        assert claimed is not None

        waiting = bus.wait_for_confirmation(
            "s1",
            "root",
            confirmation_id="confirmation-1",
        )
        loaded_waiting = bus.get("s1", "root")

        assert waiting.status == "waiting_for_user"
        assert waiting.waiting_for_confirmation_id == "confirmation-1"
        assert waiting.waiting_for_ask_id is None
        assert waiting.waiting_for_user_since is not None
        assert loaded_waiting == waiting
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None

        resumed = bus.resume_after_confirmation(
            "s1",
            "root",
            confirmation_id="confirmation-1",
        )
        retry_claim = bus.claim_next("s1", capability="general", agent_id="agent-2")

        assert resumed.status == "pending"
        assert resumed.waiting_for_confirmation_id is None
        assert resumed.waiting_for_ask_id is None
        assert resumed.waiting_for_user_since is None
        assert resumed.claimed_by is None
        assert resumed.started_at is None
        assert retry_claim is not None
        assert retry_claim.task_id == "root"
        assert retry_claim.claimed_by == "agent-2"
    finally:
        bus.close()


def test_waiting_for_user_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "tasks.sqlite"
    first = SqliteTaskBus(db)
    try:
        first.publish(_root("root"))
        assert first.claim_next("s1", capability="general", agent_id="agent-1") is not None
        first.wait_for_user("s1", "root", ask_id="ask-1")
    finally:
        first.close()

    second = SqliteTaskBus(db)
    try:
        loaded = second.get("s1", "root")

        assert loaded is not None
        assert loaded.status == "waiting_for_user"
        assert loaded.waiting_for_ask_id == "ask-1"
        assert loaded.waiting_for_user_since is not None
        assert second.claim_next("s1", capability="general", agent_id="agent-1") is None
    finally:
        second.close()


def test_waiting_for_confirmation_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "tasks.sqlite"
    first = SqliteTaskBus(db)
    try:
        first.publish(_root("root"))
        assert first.claim_next("s1", capability="general", agent_id="agent-1") is not None
        first.wait_for_confirmation("s1", "root", confirmation_id="confirmation-1")
    finally:
        first.close()

    second = SqliteTaskBus(db)
    try:
        loaded = second.get("s1", "root")

        assert loaded is not None
        assert loaded.status == "waiting_for_user"
        assert loaded.waiting_for_confirmation_id == "confirmation-1"
        assert loaded.waiting_for_ask_id is None
        assert loaded.waiting_for_user_since is not None
        assert second.claim_next("s1", capability="general", agent_id="agent-1") is None
    finally:
        second.close()


def test_waiting_parent_keeps_child_blocked(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        bus.publish(_child("child", parent_id="root", root_id="root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None

        bus.wait_for_user("s1", "root", ask_id="ask-1")

        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None
    finally:
        bus.close()


def test_waiting_task_can_fail_and_retry_clears_ask_linkage(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
        bus.wait_for_user("s1", "root", ask_id="ask-1")

        failed = bus.fail("s1", "root", error_ref="error:ask-timeout")
        retried = bus.retry("s1", "root")

        assert failed.status == "failed"
        assert failed.error_ref == "error:ask-timeout"
        assert failed.waiting_for_ask_id is None
        assert failed.waiting_for_user_since is None
        assert retried.status == "pending"
        assert retried.waiting_for_ask_id is None
        assert retried.waiting_for_user_since is None
    finally:
        bus.close()


def test_waiting_task_can_fail_and_retry_clears_confirmation_linkage(
    tmp_path: Path,
) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
        bus.wait_for_confirmation("s1", "root", confirmation_id="confirmation-1")

        failed = bus.fail("s1", "root", error_ref="error:confirmation-timeout")
        retried = bus.retry("s1", "root")

        assert failed.status == "failed"
        assert failed.error_ref == "error:confirmation-timeout"
        assert failed.waiting_for_confirmation_id is None
        assert failed.waiting_for_user_since is None
        assert retried.status == "pending"
        assert retried.waiting_for_confirmation_id is None
        assert retried.waiting_for_user_since is None
    finally:
        bus.close()


def test_resume_after_user_requires_matching_active_ask(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
        bus.wait_for_user("s1", "root", ask_id="ask-1")

        with pytest.raises(TaskStoreError, match="does not match"):
            bus.resume_after_user("s1", "root", ask_id="other-ask")
    finally:
        bus.close()


def test_resume_after_confirmation_requires_matching_active_confirmation(
    tmp_path: Path,
) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
        bus.wait_for_confirmation("s1", "root", confirmation_id="confirmation-1")

        with pytest.raises(TaskStoreError, match="does not match"):
            bus.resume_after_confirmation(
                "s1",
                "root",
                confirmation_id="other-confirmation",
            )
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


def test_interrupt_pending_task_persists_cancelled_failure(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))

        stopped = bus.request_interrupt(
            "s1",
            "root",
            reason="user requested stop",
            request_id="stop-1",
        )
        loaded = bus.get("s1", "root")

        assert stopped.status == "failed"
        assert stopped.error_ref == "cancelled: user requested stop"
        assert stopped.interrupt_requested is True
        assert stopped.interrupt_request_id == "stop-1"
        assert stopped.interrupt_requested_by == "user"
        assert stopped.interrupt_requested_at is not None
        assert stopped.completed_at is not None
        assert loaded == stopped
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None
    finally:
        bus.close()


def test_interrupt_running_task_persists_active_intent(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None

        stopped = bus.request_interrupt(
            "s1",
            "root",
            reason="stop after safe point",
            request_id="stop-running",
        )
        loaded = bus.get("s1", "root")

        assert stopped.status == "running"
        assert stopped.error_ref is None
        assert stopped.interrupt_requested is True
        assert stopped.interrupt_request_id == "stop-running"
        assert stopped.interrupt_reason == "stop after safe point"
        assert loaded == stopped
    finally:
        bus.close()


def test_recover_interrupted_running_task_persists_cancelled_failure(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tasks.sqlite"
    bus = SqliteTaskBus(db_path)
    try:
        bus.publish(_root("root"))
        assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
        bus.request_interrupt(
            "s1",
            "root",
            reason="user requested stop",
            request_id="stop-running",
        )

        recovered = bus.recover_interrupted_running_tasks("s1")
        loaded = bus.get("s1", "root")

        assert len(recovered) == 1
        assert recovered[0].status == "failed"
        assert recovered[0].error_ref == (
            "cancelled: user requested stop; safe_point=sidecar_recovery"
        )
        assert recovered[0].interrupt_requested is True
        assert recovered[0].completed_at is not None
        assert loaded == recovered[0]
    finally:
        bus.close()

    reopened = SqliteTaskBus(db_path)
    try:
        persisted = reopened.get("s1", "root")
    finally:
        reopened.close()

    assert persisted is not None
    assert persisted.status == "failed"
    assert persisted.error_ref == (
        "cancelled: user requested stop; safe_point=sidecar_recovery"
    )


def test_interrupt_terminal_task_is_rejected(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        bus.claim_next("s1", capability="general", agent_id="agent-1")
        bus.complete("s1", "root", result_ref="result:root")

        with pytest.raises(TaskStoreError, match="pending or running"):
            bus.request_interrupt("s1", "root", reason="user requested stop")
    finally:
        bus.close()


def test_retry_clears_interrupt_intent(tmp_path: Path) -> None:
    bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        bus.publish(_root("root"))
        bus.request_interrupt("s1", "root", reason="user requested stop")

        retried = bus.retry("s1", "root")

        assert retried.status == "pending"
        assert retried.error_ref is None
        assert retried.interrupt_requested is False
        assert retried.interrupt_request_id is None
        assert retried.interrupt_reason is None
        assert retried.interrupt_requested_by is None
        assert retried.interrupt_requested_at is None
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
    created_at: datetime | None = None,
) -> TaskDomain:
    kwargs: dict[str, Any] = {"created_at": created_at} if created_at is not None else {}
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
        **kwargs,
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


def _time(seconds: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
