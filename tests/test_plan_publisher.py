"""Tests for publishing durable Plans through the legacy TaskPublisher boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.task import (
    DefaultPlanPublisher,
    DefaultTaskPublisher,
    DraftTaskNode,
    InMemoryDraftTaskStore,
    InMemoryTaskBus,
    Plan,
    PlanPublisher,
    PlanTaskNode,
    PublishPlanCommand,
    SqlitePlanStore,
    TaskRef,
    VersionConflictError,
)


def _plan(plan_id: str = "plan-1", *, status: str = "approved") -> Plan:
    return Plan(
        plan_id=plan_id,
        session_id="session-1",
        title="Website publishing plan",
        objective="Publish a small website.",
        summary="A two-task plan covering files and deployment.",
        status=status,  # type: ignore[arg-type]
    )


def _node(
    task_node_id: str,
    *,
    task_index: str,
    order_index: int,
    published_ref: TaskRef | None = None,
) -> PlanTaskNode:
    return PlanTaskNode(
        task_node_id=task_node_id,
        plan_id="plan-1",
        session_id="session-1",
        task_index=task_index,
        order_index=order_index,
        title=f"Task {task_index}",
        intent=f"Do task {task_index}",
        summary=f"Summary {task_index}",
        instructions=f"Instructions {task_index}",
        required_capability="workspace.basic",
        constraints=("Use the selected workspace.",),
        acceptance_criteria=("Task is complete.",),
        published_ref=published_ref,
    )


def _store(tmp_path: Path, plan: Plan, nodes: tuple[PlanTaskNode, ...]) -> SqlitePlanStore:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    store.create_plan(plan, nodes)
    return store


def _publisher(store: SqlitePlanStore) -> tuple[DefaultPlanPublisher, InMemoryTaskBus]:
    bus = InMemoryTaskBus()
    task_publisher = DefaultTaskPublisher(task_bus=bus)
    return DefaultPlanPublisher(plan_store=store, task_publisher=task_publisher), bus


def test_plan_publisher_protocol_conformance(tmp_path: Path) -> None:
    store = _store(tmp_path, _plan(), (_node("node-1", task_index="1", order_index=1),))
    try:
        publisher, _bus = _publisher(store)

        assert isinstance(publisher, PlanPublisher)
    finally:
        store.close()


def test_publish_plan_maps_flat_task_nodes_to_published_tasks(
    tmp_path: Path,
) -> None:
    store = _store(
        tmp_path,
        _plan(),
        (
            _node("node-2", task_index="2", order_index=2),
            _node("node-1", task_index="1", order_index=1),
        ),
    )
    try:
        publisher, bus = _publisher(store)

        result = publisher.publish_plan(
            PublishPlanCommand(
                command_id="publish-plan-1",
                session_id="session-1",
                plan_id="plan-1",
                expected_plan_version=1,
                idempotency_key="publish-plan-1",
            )
        )
        tasks = bus.list_for_session("session-1")
        loaded_plan = store.get_plan("session-1", "plan-1")
        loaded_nodes = store.list_task_nodes("session-1", "plan-1")

        assert result.accepted
        assert result.root_task_ids == result.published_task_ids
        assert [mapping.task_node_id for mapping in result.mappings] == ["node-1", "node-2"]
        assert [task.order_index for task in tasks] == [0, 1]
        assert [task.intent for task in tasks] == ["Do task 1", "Do task 2"]
        assert all(task.parent_id is None for task in tasks)
        assert tasks[0].dispatch_constraints is not None
        assert tasks[0].dispatch_constraints.metadata["source_type"] == "plan"
        assert tasks[0].dispatch_constraints.metadata["plan_id"] == "plan-1"
        assert loaded_plan is not None
        assert loaded_plan.status == "published"
        assert [node.readiness for node in loaded_nodes] == ["published", "published"]
        assert [node.execution for node in loaded_nodes] == ["pending", "pending"]
        assert [node.published_ref for node in loaded_nodes] == [
            TaskRef.published(result.mappings[0].task_id),
            TaskRef.published(result.mappings[1].task_id),
        ]
    finally:
        store.close()


def test_publish_plan_replays_existing_lineage_without_duplicate_tasks(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path, _plan(), (_node("node-1", task_index="1", order_index=1),))
    try:
        publisher, bus = _publisher(store)
        command = PublishPlanCommand(
            command_id="publish-plan-1",
            session_id="session-1",
            plan_id="plan-1",
            idempotency_key="publish-plan-1",
        )
        first = publisher.publish_plan(command)
        replay = publisher.publish_plan(
            command.model_copy(update={"command_id": "publish-plan-2"})
        )

        assert first.accepted
        assert replay.accepted
        assert replay.published_task_ids == first.published_task_ids
        assert len(bus.list_for_session("session-1")) == 1
    finally:
        store.close()


def test_publish_plan_rejects_partial_existing_lineage(tmp_path: Path) -> None:
    store = _store(
        tmp_path,
        _plan(),
        (
            _node(
                "node-1",
                task_index="1",
                order_index=1,
                published_ref=TaskRef.published("task-existing"),
            ),
            _node("node-2", task_index="2", order_index=2),
        ),
    )
    try:
        publisher, bus = _publisher(store)

        result = publisher.publish_plan(
            PublishPlanCommand(
                session_id="session-1",
                plan_id="plan-1",
                idempotency_key="publish-plan-1",
            )
        )

        assert result.skipped
        assert result.reason == "plan is partially published"
        assert bus.list_for_session("session-1") == []
    finally:
        store.close()


def test_publish_plan_checks_expected_plan_version(tmp_path: Path) -> None:
    store = _store(tmp_path, _plan(), (_node("node-1", task_index="1", order_index=1),))
    try:
        publisher, _bus = _publisher(store)

        with pytest.raises(VersionConflictError, match="stale version"):
            publisher.publish_plan(
                PublishPlanCommand(
                    session_id="session-1",
                    plan_id="plan-1",
                    expected_plan_version=2,
                    idempotency_key="publish-plan-1",
                )
            )
    finally:
        store.close()


def test_plan_publish_keeps_legacy_draft_tree_publish_compatible() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "session-1",
        [
            DraftTaskNode(
                draft_task_id="legacy-root",
                session_id="session-1",
                draft_tree_id="placeholder",
                title="Legacy root",
                intent="Publish legacy root",
                required_capability="general",
            )
        ],
    )
    draft_store.mark_accepted("session-1", tree.draft_tree_id, expected_version=tree.version)
    bus = InMemoryTaskBus()
    legacy_publisher = DefaultTaskPublisher(task_bus=bus, draft_store=draft_store)

    result = legacy_publisher.publish_draft_tree("session-1", tree.draft_tree_id)

    assert len(result.root_task_ids) == 1
    assert result.mappings[0].draft_task_id == "legacy-root"
    assert len(bus.list_for_session("session-1")) == 1
