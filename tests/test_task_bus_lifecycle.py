"""Tests for in-memory TaskBus execution lifecycle."""

from __future__ import annotations

from taskweavn.task import InMemoryTaskBus, TaskDomain


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


def _task(task_id: str, *, required_capability: str = "general") -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        root_id=task_id,
        intent=f"Do {task_id}",
        required_capability=required_capability,
        created_by="tester",
    )
