"""Tests for in-memory TaskBus execution lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from taskweavn.task import (
    InMemoryTaskBus,
    TaskDispatchConstraints,
    TaskDomain,
    TaskStatus,
    TaskStoreError,
)


def test_in_memory_task_bus_claim_complete_fail_and_skip() -> None:
    bus = InMemoryTaskBus([
        _task("a"),
        _task("b", required_capability="special"),
        _task("c"),
    ])

    first = bus.claim_next("s1", capability="general", agent_id="agent-1")
    assert first is not None
    assert first.task_id == "a"
    assert first.status == "running"
    assert first.claimed_by == "agent-1"

    completed = bus.complete("s1", "a", result_ref="result:a")
    assert completed.status == "done"
    assert completed.result_ref == "result:a"

    second = bus.claim_next("s1", capability="general", agent_id="agent-1")
    assert second is not None
    assert second.task_id == "c"

    failed = bus.fail("s1", "c", error_ref="error:c")
    assert failed.status == "failed"
    assert failed.error_ref == "error:c"

    skipped = bus.skip("s1", "b", reason="optional")
    assert skipped.status == "failed"
    assert skipped.error_ref == "skipped: optional"


def test_in_memory_task_bus_retry_failed_task_in_place_before_child_runs() -> None:
    bus = InMemoryTaskBus(
        [
            _task("root", status="failed", created_at=_time(0)),
            _task("child", parent_id="root", root_id="root", created_at=_time(1)),
        ]
    )

    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None

    retried = bus.retry("s1", "root", instruction="Use safer steps")
    claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")

    assert retried.task_id == "root"
    assert retried.status == "pending"
    assert retried.error_ref is None
    assert "Retry instruction" in retried.intent
    assert claimed is not None
    assert claimed.task_id == "root"
    bus.complete("s1", "root", result_ref="result:root")

    child = bus.claim_next("s1", capability="general", agent_id="agent-1")

    assert child is not None
    assert child.task_id == "child"


def test_in_memory_task_bus_retry_preserves_original_queue_position() -> None:
    bus = InMemoryTaskBus(
        [
            _task("root", status="failed", created_at=_time(0)),
            _task("later", created_at=_time(1)),
        ]
    )

    bus.retry("s1", "root")
    claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")

    assert claimed is not None
    assert claimed.task_id == "root"


def test_in_memory_task_bus_waits_and_resumes_same_task_identity() -> None:
    bus = InMemoryTaskBus(
        [_task("root", created_at=_time(0)), _task("later", created_at=_time(1))]
    )
    claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")
    assert claimed is not None

    waiting = bus.wait_for_user("s1", "root", ask_id="ask-1")

    assert waiting.status == "waiting_for_user"
    assert waiting.waiting_for_ask_id == "ask-1"
    assert waiting.waiting_for_user_since is not None
    assert waiting.claimed_by == "agent-1"

    next_claim = bus.claim_next("s1", capability="general", agent_id="agent-1")
    assert next_claim is not None
    assert next_claim.task_id == "later"

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


def test_in_memory_task_bus_waits_for_confirmation_and_resumes() -> None:
    bus = InMemoryTaskBus([_task("root")])
    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None

    waiting = bus.wait_for_confirmation(
        "s1",
        "root",
        confirmation_id="confirmation-1",
    )

    assert waiting.status == "waiting_for_user"
    assert waiting.waiting_for_confirmation_id == "confirmation-1"
    assert waiting.waiting_for_ask_id is None
    assert waiting.waiting_for_user_since is not None

    resumed = bus.resume_after_confirmation(
        "s1",
        "root",
        confirmation_id="confirmation-1",
    )

    assert resumed.status == "pending"
    assert resumed.waiting_for_confirmation_id is None
    assert resumed.waiting_for_ask_id is None
    assert resumed.waiting_for_user_since is None


def test_in_memory_task_bus_waiting_parent_keeps_children_blocked() -> None:
    bus = InMemoryTaskBus(
        [
            _task("root"),
            _task("child", parent_id="root", root_id="root", created_at=_time(1)),
        ]
    )
    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None

    bus.wait_for_user("s1", "root", ask_id="ask-1")

    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None


def test_in_memory_task_bus_waiting_task_can_fail_and_retry_clears_ask_linkage() -> None:
    bus = InMemoryTaskBus([_task("root")])
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


def test_in_memory_task_bus_waiting_task_can_fail_and_retry_clears_confirmation_linkage() -> None:
    bus = InMemoryTaskBus([_task("root")])
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


def test_in_memory_task_bus_resume_requires_matching_active_ask() -> None:
    bus = InMemoryTaskBus([_task("root")])
    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
    bus.wait_for_user("s1", "root", ask_id="ask-1")

    with pytest.raises(TaskStoreError, match="does not match"):
        bus.resume_after_user("s1", "root", ask_id="other-ask")


def test_in_memory_task_bus_resume_requires_matching_active_confirmation() -> None:
    bus = InMemoryTaskBus([_task("root")])
    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
    bus.wait_for_confirmation("s1", "root", confirmation_id="confirmation-1")

    with pytest.raises(TaskStoreError, match="does not match"):
        bus.resume_after_confirmation(
            "s1",
            "root",
            confirmation_id="other-confirmation",
        )


def test_in_memory_task_bus_interrupts_pending_task_as_cancelled_failure() -> None:
    bus = InMemoryTaskBus([_task("root")])

    stopped = bus.request_interrupt(
        "s1",
        "root",
        reason="user requested stop",
        request_id="stop-1",
    )

    assert stopped.status == "failed"
    assert stopped.error_ref == "cancelled: user requested stop"
    assert stopped.interrupt_requested is True
    assert stopped.interrupt_request_id == "stop-1"
    assert stopped.interrupt_requested_by == "user"
    assert stopped.interrupt_requested_at is not None
    assert stopped.completed_at is not None
    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is None


def test_in_memory_task_bus_interrupts_running_task_without_terminal_transition() -> None:
    bus = InMemoryTaskBus([_task("root")])
    claimed = bus.claim_next("s1", capability="general", agent_id="agent-1")
    assert claimed is not None

    stopped = bus.request_interrupt(
        "s1",
        "root",
        reason="stop after safe point",
        request_id="stop-running",
    )

    assert stopped.status == "running"
    assert stopped.error_ref is None
    assert stopped.interrupt_requested is True
    assert stopped.interrupt_request_id == "stop-running"
    assert stopped.interrupt_reason == "stop after safe point"


def test_in_memory_task_bus_recovers_stale_interrupted_running_task() -> None:
    bus = InMemoryTaskBus([_task("root")])
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


def test_in_memory_task_bus_rejects_interrupt_for_terminal_task() -> None:
    bus = InMemoryTaskBus([_task("root", status="done")])

    with pytest.raises(TaskStoreError, match="pending or running"):
        bus.request_interrupt("s1", "root", reason="user requested stop")


def test_in_memory_task_bus_retry_clears_interrupt_intent() -> None:
    bus = InMemoryTaskBus([_task("root")])
    bus.request_interrupt("s1", "root", reason="user requested stop", request_id="stop-1")

    retried = bus.retry("s1", "root")

    assert retried.status == "pending"
    assert retried.error_ref is None
    assert retried.interrupt_requested is False
    assert retried.interrupt_request_id is None
    assert retried.interrupt_reason is None
    assert retried.interrupt_requested_by is None
    assert retried.interrupt_requested_at is None


def _task(
    task_id: str,
    *,
    required_capability: str = "general",
    status: TaskStatus = "pending",
    parent_id: str | None = None,
    root_id: str | None = None,
    metadata: dict[str, object] | None = None,
    created_at: datetime | None = None,
) -> TaskDomain:
    kwargs: dict[str, Any] = {"created_at": created_at} if created_at is not None else {}
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        parent_id=parent_id,
        root_id=root_id or task_id,
        intent=f"Do {task_id}",
        required_capability=required_capability,
        status=status,
        created_by="tester",
        dispatch_constraints=(
            TaskDispatchConstraints(metadata=metadata) if metadata is not None else None
        ),
        **kwargs,
    )


def _time(seconds: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
