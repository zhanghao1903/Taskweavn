"""Adapters from legacy DraftTaskTree facts to durable Plan facts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from taskweavn.task.models import DraftTaskNode, DraftTaskTree, TaskRef
from taskweavn.task.plan_models import (
    Plan,
    PlanStatus,
    PlanTaskNode,
    PlanTaskNodeReadiness,
)


def build_plan_from_draft_tree(
    tree: DraftTaskTree,
    nodes: Sequence[DraftTaskNode],
    *,
    source_raw_task_id: str | None = None,
) -> tuple[Plan, tuple[PlanTaskNode, ...]]:
    """Create a durable flat Plan representation for a DraftTaskTree.

    This intentionally reuses DraftTaskNode ids as PlanTaskNode ids so existing
    task detail and audit links do not need an identity translation layer during
    the Plan/TaskNode migration.
    """

    ordered_nodes = _preorder_nodes(tree, nodes)
    title = tree.title or _fallback_title(ordered_nodes)
    summary = tree.summary or _fallback_summary(ordered_nodes)
    plan = Plan(
        session_id=tree.session_id,
        source_raw_task_id=source_raw_task_id,
        source_draft_tree_id=tree.draft_tree_id,
        title=title,
        objective=summary,
        summary=summary,
        status=_plan_status(ordered_nodes),
        created_by=tree.created_by,
        created_at=tree.created_at,
        updated_at=tree.updated_at,
    )
    plan_nodes = tuple(
        _plan_node(node, plan=plan, task_index=task_index, order_index=order_index)
        for order_index, (node, task_index) in enumerate(ordered_nodes)
    )
    return plan, plan_nodes


def _preorder_nodes(
    tree: DraftTaskTree,
    nodes: Sequence[DraftTaskNode],
) -> tuple[tuple[DraftTaskNode, str], ...]:
    children_by_parent: dict[str | None, list[DraftTaskNode]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_draft_task_id].append(node)
    for siblings in children_by_parent.values():
        siblings.sort(key=lambda node: (node.order_index, node.created_at, node.draft_task_id))

    ordered: list[tuple[DraftTaskNode, str]] = []

    def walk(parent_id: str | None, prefix: str) -> None:
        for index, node in enumerate(children_by_parent.get(parent_id, []), start=1):
            task_index = f"{prefix}.{index}" if prefix else str(index)
            ordered.append((node, task_index))
            walk(node.draft_task_id, task_index)

    root_ids = {node.draft_task_id for node in tree.root_nodes}
    if root_ids:
        root_nodes = [node for node in children_by_parent[None] if node.draft_task_id in root_ids]
        children_by_parent[None] = root_nodes
    walk(None, "")
    return tuple(ordered)


def _plan_node(
    node: DraftTaskNode,
    *,
    plan: Plan,
    task_index: str,
    order_index: int,
) -> PlanTaskNode:
    return PlanTaskNode(
        task_node_id=node.draft_task_id,
        plan_id=plan.plan_id,
        session_id=node.session_id,
        task_index=task_index,
        order_index=order_index,
        title=node.title,
        intent=node.intent,
        summary=node.summary or node.intent,
        instructions=node.instructions or "",
        required_capability=node.required_capability,
        constraints=node.constraints,
        acceptance_criteria=node.acceptance_criteria,
        readiness=_node_readiness(node),
        execution="pending" if node.status == "published" else "not_started",
        draft_ref=TaskRef.draft(node.draft_task_id),
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def _node_readiness(node: DraftTaskNode) -> PlanTaskNodeReadiness:
    if node.status == "accepted":
        return "approved"
    if node.status in {"draft", "published", "cancelled"}:
        return node.status
    return "unknown"


def _plan_status(nodes: tuple[tuple[DraftTaskNode, str], ...]) -> PlanStatus:
    if not nodes:
        return "draft"
    statuses = {node.status for node, _task_index in nodes}
    if statuses == {"published"}:
        return "published"
    if statuses <= {"accepted", "published"}:
        return "approved"
    if statuses == {"cancelled"}:
        return "cancelled"
    return "draft"


def _fallback_title(nodes: tuple[tuple[DraftTaskNode, str], ...]) -> str:
    if not nodes:
        return "Task plan"
    return nodes[0][0].title


def _fallback_summary(nodes: tuple[tuple[DraftTaskNode, str], ...]) -> str:
    if not nodes:
        return "Task plan"
    titles = [node.title for node, _task_index in nodes[:2]]
    if len(nodes) == 1:
        return f"1-task plan covering {titles[0]}."
    if len(nodes) == 2:
        return f"2-task plan covering {titles[0]} and {titles[1]}."
    return (
        f"{len(nodes)}-task plan covering "
        f"{titles[0]}, {titles[1]}, and {len(nodes) - 2} more."
    )


__all__ = ["build_plan_from_draft_tree"]
