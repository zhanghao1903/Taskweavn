"""Tests for TaskBus lifecycle sync into durable PlanTaskNode facts."""

from __future__ import annotations

from pathlib import Path

from taskweavn.task import (
    Plan,
    PlanTaskNode,
    PlanTaskNodeLifecycleSync,
    SqlitePlanStore,
    TaskDomain,
    TaskRef,
)


def _plan() -> Plan:
    return Plan(
        plan_id="plan-1",
        session_id="session-1",
        title="Lifecycle plan",
        objective="Track execution lifecycle.",
        summary="Track execution lifecycle.",
        status="published",
    )


def _node() -> PlanTaskNode:
    return PlanTaskNode(
        task_node_id="node-1",
        plan_id="plan-1",
        session_id="session-1",
        task_index="1",
        title="Run task",
        intent="Run the published task.",
        summary="Run the published task.",
        instructions="Run it.",
        required_capability="general",
        readiness="published",
        execution="pending",
        published_ref=TaskRef.published("task-1"),
    )


def _task(
    status: str,
    *,
    result_ref: str | None = None,
    error_ref: str | None = None,
) -> TaskDomain:
    return TaskDomain(
        task_id="task-1",
        session_id="session-1",
        root_id="task-1",
        intent="Run the published task.",
        summary="Run the published task.",
        instructions="Run it.",
        required_capability="general",
        status=status,  # type: ignore[arg-type]
        result_ref=result_ref,
        error_ref=error_ref,
        created_by="test",
    )


def test_plan_lifecycle_sync_persists_done_task_and_rolls_up_plan_status(
    tmp_path: Path,
) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        store.create_plan(_plan(), (_node(),))
        sync = PlanTaskNodeLifecycleSync(store)

        saved = sync.sync_task(_task("done", result_ref="result:task-1"))

        assert saved is not None
        node = store.get_task_node("session-1", "node-1")
        plan = store.get_plan("session-1", "plan-1")
        assert node is not None
        assert plan is not None
        assert node.execution == "done"
        assert node.result_ref == "result:task-1"
        assert node.error_ref is None
        assert plan.status == "awaiting_acceptance"
    finally:
        store.close()


def test_plan_lifecycle_sync_persists_failed_task_error_ref(
    tmp_path: Path,
) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        store.create_plan(_plan(), (_node(),))
        sync = PlanTaskNodeLifecycleSync(store)

        saved = sync.sync_task(_task("failed", error_ref="error:task-1"))

        assert saved is not None
        node = store.get_task_node("session-1", "node-1")
        plan = store.get_plan("session-1", "plan-1")
        assert node is not None
        assert plan is not None
        assert node.execution == "failed"
        assert node.result_ref is None
        assert node.error_ref == "error:task-1"
        assert plan.status == "failed"
    finally:
        store.close()


def test_plan_lifecycle_sync_ignores_unmapped_tasks(tmp_path: Path) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        store.create_plan(_plan(), (_node(),))
        sync = PlanTaskNodeLifecycleSync(store)

        saved = sync.sync_task(
            _task("done", result_ref="result:missing").model_copy(
                update={"task_id": "missing-task", "root_id": "missing-task"}
            )
        )

        node = store.get_task_node("session-1", "node-1")
        assert saved is None
        assert node is not None
        assert node.execution == "pending"
        assert node.result_ref is None
    finally:
        store.close()
