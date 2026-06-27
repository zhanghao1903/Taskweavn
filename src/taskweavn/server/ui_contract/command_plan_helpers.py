"""Plan command helpers for the UI command gateway."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import unquote

from taskweavn.server.ui_contract.view_models import TaskNodeCardView, TaskTreeView
from taskweavn.task.plan_models import Plan, PlanFinalizationState, PlanTaskNode


def archived_plan(plan: Plan | None) -> bool:
    return plan is not None and (
        plan.status == "archived" or plan.archived_at is not None
    )


def legacy_plan_id(session_id: str) -> str:
    return f"plan:legacy:{session_id}"


def normalize_plan_id(plan_id: str) -> str:
    return unquote(plan_id)


def is_legacy_plan_id(session_id: str, plan_id: str) -> bool:
    return plan_id == legacy_plan_id(session_id)


def archived_legacy_plan_from_task_tree(
    task_tree: TaskTreeView,
    *,
    expected_version: int | None,
) -> tuple[Plan, tuple[PlanTaskNode, ...]]:
    now = datetime.now(UTC)
    plan = Plan(
        plan_id=legacy_plan_id(task_tree.session_id),
        session_id=task_tree.session_id,
        title=task_tree.title,
        objective=task_tree.summary or task_tree.title,
        summary=task_tree.summary or task_tree.title,
        status="archived",
        version=expected_version or task_tree.version,
        finalization=PlanFinalizationState(status="skipped", required=False),
        created_at=now,
        updated_at=now,
        archived_at=now,
    )
    nodes = tuple(
        archived_legacy_plan_node(
            node,
            plan_id=plan.plan_id,
            session_id=plan.session_id,
            order_index=index,
            now=now,
        )
        for index, node in enumerate(task_tree.nodes)
    )
    return plan, nodes


def archived_legacy_plan_node(
    node: TaskNodeCardView,
    *,
    plan_id: str,
    session_id: str,
    order_index: int,
    now: datetime,
) -> PlanTaskNode:
    task_ref = node.task_ref
    return PlanTaskNode(
        task_node_id=node.id,
        plan_id=plan_id,
        session_id=session_id,
        task_index=node.task_index or str(order_index + 1),
        order_index=order_index,
        title=node.title,
        intent=node.intent or node.title,
        summary=node.summary or node.title,
        instructions=node.instructions or "",
        acceptance_criteria=node.acceptance_criteria,
        readiness=(
            "published"
            if task_ref is not None and task_ref.kind == "published"
            else "draft"
        ),
        execution=node.execution,
        draft_ref=task_ref if task_ref is not None and task_ref.kind == "draft" else None,
        published_ref=(
            task_ref if task_ref is not None and task_ref.kind == "published" else None
        ),
        result_ref=node.result_ref,
        error_ref=node.error_ref,
        version=node.version,
        created_at=now,
        updated_at=now,
    )


__all__ = [
    "archived_legacy_plan_from_task_tree",
    "archived_legacy_plan_node",
    "archived_plan",
    "is_legacy_plan_id",
    "legacy_plan_id",
    "normalize_plan_id",
]
