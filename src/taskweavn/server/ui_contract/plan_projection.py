"""Projection service for Product 1.1 PlanView compatibility."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.server.ui_contract.view_models import (
    ExecutionRollupView,
    PlanFinalizationView,
    PlanOutcomeView,
    PlanPermissions,
    PlanUiStatus,
    PlanView,
    TaskNodeCardView,
    TaskNodePermissions,
    TaskNodeStatus,
    TaskTreeStatus,
    TaskTreeView,
)
from taskweavn.task.plan_models import Plan, PlanOutcome, PlanTaskNode


class PlanProjectionService(Protocol):
    """Project current task planning facts into the Product 1.1 Plan contract."""

    def project_legacy_task_tree(self, task_tree: TaskTreeView) -> PlanView:
        """Project an existing TaskTreeView into a synthetic active Plan."""

    def project_stored_plan(
        self,
        plan: Plan,
        task_nodes: Sequence[PlanTaskNode],
        *,
        task_tree_projection: TaskTreeView | None = None,
    ) -> PlanView:
        """Project a durable Plan and TaskNodes into the active Plan view."""


class DefaultPlanProjectionService:
    """Default projection-only PlanView adapter for legacy task projections."""

    def project_legacy_task_tree(self, task_tree: TaskTreeView) -> PlanView:
        plan_id = _legacy_plan_id(task_tree.session_id)
        task_nodes = _flat_task_nodes(task_tree.nodes, plan_id=plan_id)
        task_tree_projection = _task_tree_projection(task_tree, plan_id=plan_id)
        summary = task_tree.summary or _fallback_plan_summary(task_nodes)
        return PlanView(
            id=plan_id,
            session_id=task_tree.session_id,
            title=task_tree.title,
            summary=summary,
            objective=summary,
            status=_plan_status_from_task_tree(task_tree.status),
            task_count=len(task_nodes),
            task_node_ids=tuple(node.id for node in task_nodes),
            task_nodes=task_nodes,
            execution_rollup=_execution_rollup(task_nodes),
            finalization=PlanFinalizationView(status="skipped", required=False),
            permissions=_plan_permissions(task_nodes, task_tree.status),
            task_tree_projection=task_tree_projection,
            source_kind=_source_kind(task_tree),
            source_ref=_source_ref(task_tree),
            version=task_tree.version,
        )

    def project_stored_plan(
        self,
        plan: Plan,
        task_nodes: Sequence[PlanTaskNode],
        *,
        task_tree_projection: TaskTreeView | None = None,
    ) -> PlanView:
        nodes = _task_nodes_from_plan(
            plan,
            task_nodes,
            task_tree_projection=task_tree_projection,
        )
        projection = task_tree_projection or _task_tree_from_plan(plan, nodes)
        if projection is not None:
            projection = projection.model_copy(
                update={
                    "title": plan.title,
                    "summary": plan.summary,
                    "nodes": nodes,
                    "status": _task_tree_status_from_nodes(nodes),
                    "version": plan.version,
                }
            )
        return PlanView(
            id=plan.plan_id,
            session_id=plan.session_id,
            title=plan.title,
            summary=plan.summary,
            objective=plan.objective,
            status=_plan_status_from_plan(plan),
            task_count=len(nodes),
            task_node_ids=tuple(node.id for node in nodes),
            task_nodes=nodes,
            execution_rollup=_execution_rollup(nodes),
            finalization=_finalization_view(plan),
            outcome=_outcome_view(plan.outcome),
            permissions=_stored_plan_permissions(plan, nodes),
            task_tree_projection=projection,
            source_kind="plan_store",
            source_ref=ObjectRef(kind="plan", id=plan.plan_id),
            version=plan.version,
        )


def _legacy_plan_id(session_id: str) -> str:
    return f"plan:legacy:{session_id}"


def _flat_task_nodes(
    nodes: tuple[TaskNodeCardView, ...],
    *,
    plan_id: str,
) -> tuple[TaskNodeCardView, ...]:
    return tuple(
        node.model_copy(
            update={
                "plan_id": node.plan_id or plan_id,
                "parent_id": None,
                "task_index": node.task_index or str(index + 1),
                "depth": 0,
                "order_index": index,
                "display_index": index + 1,
            }
        )
        for index, node in enumerate(nodes)
    )


def _task_tree_projection(task_tree: TaskTreeView, *, plan_id: str) -> TaskTreeView:
    return task_tree.model_copy(
        update={
            "nodes": tuple(
                node.model_copy(
                    update={
                        "plan_id": node.plan_id or plan_id,
                        "task_index": node.task_index or str(index + 1),
                    }
                )
                for index, node in enumerate(task_tree.nodes)
            )
        }
    )


def _plan_status_from_task_tree(status: str) -> PlanUiStatus:
    mapping: dict[str, PlanUiStatus] = {
        "draft": "draft",
        "published": "published",
        "running": "running",
        "completed": "ready_for_review",
        "failed": "failed",
    }
    return mapping.get(status, "unknown")


def _plan_status_from_plan(plan: Plan) -> PlanUiStatus:
    mapping: dict[str, PlanUiStatus] = {
        "draft": "draft",
        "reviewing": "reviewing",
        "approved": "ready_to_publish",
        "published": "published",
        "running": "running",
        "finalizing": "finalizing",
        "awaiting_acceptance": "ready_for_review",
        "accepted": "accepted",
        "follow_up_needed": "follow_up_needed",
        "failed": "failed",
        "cancelled": "cancelled",
        "archived": "cancelled",
    }
    return mapping.get(plan.status, "unknown")


def _task_nodes_from_plan(
    plan: Plan,
    task_nodes: Sequence[PlanTaskNode],
    *,
    task_tree_projection: TaskTreeView | None = None,
) -> tuple[TaskNodeCardView, ...]:
    ordered = tuple(
        sorted(
            task_nodes,
            key=lambda node: (node.order_index, node.task_index, node.task_node_id),
        )
    )
    live_cards = _cards_by_task_ref(task_tree_projection)
    return tuple(
        _task_node_card_from_plan(
            plan,
            node,
            live_card=_live_card(node, live_cards),
            order_index=index,
        )
        for index, node in enumerate(ordered)
    )


def _task_node_card_from_plan(
    plan: Plan,
    node: PlanTaskNode,
    *,
    live_card: TaskNodeCardView | None,
    order_index: int,
) -> TaskNodeCardView:
    payload: dict[str, object] = {
        "id": node.task_node_id,
        "plan_id": plan.plan_id,
        "task_ref": node.published_ref or node.draft_ref,
        "parent_id": None,
        "task_index": node.task_index,
        "title": node.title,
        "summary": node.summary,
        "intent": node.intent,
        "instructions": node.instructions or None,
        "acceptance_criteria": node.acceptance_criteria,
        "status": (
            live_card.status if live_card is not None else _task_status_from_plan_node(node)
        ),
        "execution": live_card.execution if live_card is not None else node.execution,
        "depth": 0,
        "order_index": order_index,
        "display_index": order_index + 1,
        "result_ref": live_card.result_ref if live_card is not None else node.result_ref,
        "error_ref": live_card.error_ref if live_card is not None else node.error_ref,
        "interruption_requested": (
            live_card.interruption_requested if live_card is not None else False
        ),
        "permissions": _task_permissions_from_plan_node(node),
        "version": node.version,
    }
    if live_card is not None:
        payload["badges"] = live_card.badges
    return TaskNodeCardView.model_validate(payload)


def _cards_by_task_ref(
    task_tree_projection: TaskTreeView | None,
) -> dict[tuple[str, str], TaskNodeCardView]:
    if task_tree_projection is None:
        return {}
    return {
        (node.task_ref.kind, node.task_ref.id): node
        for node in task_tree_projection.nodes
        if node.task_ref is not None
    }


def _live_card(
    node: PlanTaskNode,
    cards_by_ref: dict[tuple[str, str], TaskNodeCardView],
) -> TaskNodeCardView | None:
    task_ref = node.published_ref or node.draft_ref
    if task_ref is None:
        return None
    return cards_by_ref.get((task_ref.kind, task_ref.id))


def _task_status_from_plan_node(node: PlanTaskNode) -> TaskNodeStatus:
    if node.execution == "waiting_for_user":
        return "waiting_user"
    if node.execution == "running":
        return "running"
    if node.execution == "done":
        return "done"
    if node.execution == "failed":
        return "failed"
    if node.execution == "cancelled":
        return "cancelled"
    if node.execution == "pending":
        return "queued"
    if node.readiness == "published":
        return "queued"
    if node.readiness == "cancelled":
        return "cancelled"
    return "draft"


def _task_permissions_from_plan_node(node: PlanTaskNode) -> TaskNodePermissions:
    editable = node.readiness in {"draft", "reviewing", "approved"}
    return TaskNodePermissions(
        can_edit=editable,
        can_append_guidance=editable,
        can_publish=editable,
        can_cancel=node.readiness not in {"published", "cancelled"},
        can_retry=node.execution == "failed",
    )


def _task_tree_from_plan(
    plan: Plan,
    nodes: tuple[TaskNodeCardView, ...],
) -> TaskTreeView:
    return TaskTreeView(
        id=plan.source_draft_tree_id or f"plan:{plan.plan_id}:task-tree",
        session_id=plan.session_id,
        title=plan.title,
        summary=plan.summary,
        status=_task_tree_status_from_nodes(nodes),
        nodes=nodes,
        version=plan.version,
    )


def _task_tree_status_from_nodes(nodes: tuple[TaskNodeCardView, ...]) -> TaskTreeStatus:
    if not nodes:
        return "draft"
    statuses = {node.status for node in nodes}
    if statuses <= {"done"}:
        return "completed"
    if "failed" in statuses:
        return "failed"
    if "running" in statuses or "waiting_user" in statuses or "queued" in statuses:
        return "running"
    if statuses <= {"cancelled"}:
        return "failed"
    return "draft"


def _execution_rollup(nodes: tuple[TaskNodeCardView, ...]) -> ExecutionRollupView:
    counts = {
        "not_started": 0,
        "pending": 0,
        "running": 0,
        "done": 0,
        "failed": 0,
        "cancelled": 0,
        "unknown": 0,
    }
    blocked_by_confirmation = 0
    for node in nodes:
        execution = node.execution
        if execution == "waiting_for_user":
            blocked_by_confirmation += 1
            counts["pending"] += 1
        elif execution in counts:
            counts[execution] += 1
        else:
            counts["unknown"] += 1
    return ExecutionRollupView(
        total=len(nodes),
        not_started=counts["not_started"],
        pending=counts["pending"],
        running=counts["running"],
        done=counts["done"],
        failed=counts["failed"],
        cancelled=counts["cancelled"],
        unknown=counts["unknown"],
        blocked_by_confirmation=blocked_by_confirmation,
    )


def _finalization_view(plan: Plan) -> PlanFinalizationView:
    return PlanFinalizationView(
        status=plan.finalization.status,
        required=plan.finalization.required,
        summary_ref=plan.finalization.result_summary_id,
        file_rollup_ref=plan.finalization.file_rollup_id,
        context_summary_ref=plan.finalization.context_summary_id,
        warnings=plan.finalization.warnings,
    )


def _outcome_view(outcome: PlanOutcome | None) -> PlanOutcomeView | None:
    if outcome is None:
        return None
    return PlanOutcomeView(
        status=outcome.status,
        summary=outcome.summary,
        completed_task_count=outcome.completed_task_count,
        failed_task_count=outcome.failed_task_count,
        skipped_task_count=outcome.skipped_task_count,
        file_change_summary_ref=outcome.file_change_summary_id,
        audit_summary_ref=outcome.audit_summary_id,
    )


def _plan_permissions(
    nodes: tuple[TaskNodeCardView, ...],
    status: str,
) -> PlanPermissions:
    return PlanPermissions(
        can_edit=any(node.permissions.can_edit for node in nodes),
        can_publish=status == "draft"
        and any(node.permissions.can_publish for node in nodes),
        can_append_guidance=any(node.permissions.can_append_guidance for node in nodes),
        can_request_execution=status in {"draft", "published"},
    )


def _stored_plan_permissions(
    plan: Plan,
    nodes: tuple[TaskNodeCardView, ...],
) -> PlanPermissions:
    editable = plan.status in {"draft", "reviewing", "approved"}
    return PlanPermissions(
        can_edit=editable,
        can_publish=editable and any(node.permissions.can_publish for node in nodes),
        can_append_guidance=editable
        and any(node.permissions.can_append_guidance for node in nodes),
        can_create_task_node=editable,
        can_delete_task_node=editable,
        can_request_execution=plan.status in {"draft", "approved", "published"},
    )


def _fallback_plan_summary(nodes: tuple[TaskNodeCardView, ...]) -> str:
    if not nodes:
        return "Task plan"
    titles = [node.title for node in nodes[:2]]
    if len(nodes) == 1:
        return f"1-task plan covering {titles[0]}."
    if len(nodes) == 2:
        return f"2-task plan covering {titles[0]} and {titles[1]}."
    return f"{len(nodes)}-task plan covering {titles[0]}, {titles[1]}, and {len(nodes) - 2} more."


def _source_kind(
    task_tree: TaskTreeView,
) -> Literal["legacy_draft_tree", "legacy_published_task_tree"]:
    if task_tree.status == "draft":
        return "legacy_draft_tree"
    return "legacy_published_task_tree"


def _source_ref(task_tree: TaskTreeView) -> ObjectRef | None:
    if task_tree.status != "draft":
        return None
    return ObjectRef(kind="draft_tree", id=task_tree.id)
