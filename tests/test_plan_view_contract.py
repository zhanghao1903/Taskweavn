"""Focused contract tests for Product 1.1 PlanView compatibility."""

from __future__ import annotations

from datetime import UTC, datetime

from taskweavn.server.ui_contract import (
    DefaultPlanProjectionService,
    MainPageSnapshot,
    PlanningView,
    ProjectSummary,
    SessionSummary,
    TaskNodeCardView,
    TaskNodePermissions,
    TaskTreeView,
    WorkflowSummary,
)

NOW = datetime(2026, 6, 13, 8, 0, tzinfo=UTC)


def test_main_page_snapshot_derives_active_plan_from_legacy_task_tree() -> None:
    workflow = WorkflowSummary(id="workflow-local", name="Workspace")
    session = SessionSummary(
        id="session-1",
        project_id="project-local",
        workflow_id="workflow-local",
        name="Website",
        status="draft_ready",
        created_at=NOW,
        updated_at=NOW,
    )
    task_tree = TaskTreeView(
        id="tree-1",
        session_id="session-1",
        title="Website plan",
        summary="Prepare the website.",
        status="draft",
        nodes=(
            TaskNodeCardView(
                id="task-1",
                title="Draft homepage",
                summary="Create the first page.",
                status="draft",
                execution="not_started",
                parent_id=None,
                order_index=0,
                display_index=1,
                permissions=TaskNodePermissions(
                    can_edit=True,
                    can_append_guidance=True,
                    can_publish=True,
                ),
            ),
        ),
    )

    snapshot = MainPageSnapshot(
        project=ProjectSummary(id="project-local", name="Local Project"),
        workflows=(workflow,),
        workflow=workflow,
        sessions=(session,),
        session=session,
        planning=PlanningView(state="draft_ready"),
        task_tree=task_tree,
    )
    payload = snapshot.model_dump(mode="json")

    assert snapshot.active_plan is not None
    assert snapshot.active_plan.id == "plan:legacy:session-1"
    assert snapshot.active_plan.status == "draft"
    assert snapshot.active_plan.task_count == 1
    assert snapshot.active_plan.task_node_ids == ("task-1",)
    assert snapshot.active_plan.task_nodes[0].plan_id == "plan:legacy:session-1"
    assert snapshot.active_plan.task_nodes[0].task_index == "1"
    assert snapshot.active_plan.task_tree_projection is not None
    assert snapshot.task_tree == snapshot.active_plan.task_tree_projection
    assert payload["activePlan"]["taskNodes"][0]["planId"] == "plan:legacy:session-1"
    assert payload["taskTree"]["nodes"][0]["taskIndex"] == "1"


def test_legacy_plan_projection_flattens_task_nodes_but_keeps_task_tree_projection() -> None:
    task_tree = TaskTreeView(
        id="tree-1",
        session_id="session-1",
        title="Nested legacy tree",
        summary=None,
        status="running",
        nodes=(
            TaskNodeCardView(
                id="root",
                title="Root task",
                summary="Coordinate work.",
                status="running",
                execution="running",
                parent_id=None,
                depth=0,
                order_index=0,
                display_index=1,
            ),
            TaskNodeCardView(
                id="child",
                title="Child task",
                summary="Do one part.",
                status="queued",
                execution="pending",
                parent_id="root",
                depth=1,
                order_index=1,
                display_index=2,
            ),
        ),
    )

    plan = DefaultPlanProjectionService().project_legacy_task_tree(task_tree)

    assert plan.source_kind == "legacy_published_task_tree"
    assert plan.source_ref is None
    assert plan.summary == "2-task plan covering Root task and Child task."
    assert [node.id for node in plan.task_nodes] == ["root", "child"]
    assert [node.task_index for node in plan.task_nodes] == ["1", "2"]
    assert [node.parent_id for node in plan.task_nodes] == [None, None]
    assert [node.depth for node in plan.task_nodes] == [0, 0]
    assert [node.order_index for node in plan.task_nodes] == [0, 1]
    assert plan.execution_rollup.total == 2
    assert plan.execution_rollup.running == 1
    assert plan.execution_rollup.pending == 1
    assert plan.task_tree_projection is not None
    assert plan.task_tree_projection.nodes[1].parent_id == "root"
    assert plan.task_tree_projection.nodes[1].depth == 1
    assert plan.task_tree_projection.nodes[1].task_index == "2"


def test_main_page_snapshot_keeps_no_plan_state_when_task_tree_missing() -> None:
    workflow = WorkflowSummary(id="workflow-local", name="Workspace")
    session = SessionSummary(
        id="session-1",
        project_id="project-local",
        workflow_id="workflow-local",
        name="Website",
        status="new",
        created_at=NOW,
        updated_at=NOW,
    )

    snapshot = MainPageSnapshot(
        project=ProjectSummary(id="project-local", name="Local Project"),
        workflows=(workflow,),
        workflow=workflow,
        sessions=(session,),
        session=session,
        planning=PlanningView(state="empty"),
        task_tree=None,
    )

    assert snapshot.active_plan is None
    assert snapshot.task_tree is None
