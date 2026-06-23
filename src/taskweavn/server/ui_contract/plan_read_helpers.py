"""Plan-aware read helpers for Product 1.1 query gateway migration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from taskweavn.server.ui_contract.audit_page_state import _selected_task
from taskweavn.server.ui_contract.mapping import (
    map_file_change_summary_view,
    map_result_card_view,
)
from taskweavn.server.ui_contract.plan_projection import PlanProjectionService
from taskweavn.server.ui_contract.view_models import (
    FileChangeSummaryView,
    PlanView,
    ResultCardView,
    TaskNodeCardView,
    TaskTreeView,
)
from taskweavn.task.plan_models import Plan, PlanTaskNode
from taskweavn.task.plan_stores import PlanStore
from taskweavn.task.projection import TaskProjectionService
from taskweavn.task.stores import AuthoringStateStore


@dataclass(frozen=True)
class StoredPlanContext:
    plan: Plan
    task_nodes: list[PlanTaskNode]


@dataclass(frozen=True)
class ActivePlanReadContext:
    active_plan: PlanView | None
    task_tree: TaskTreeView | None
    stored_plan_nodes: list[PlanTaskNode] | None
    legacy_fallback_allowed: bool = True


@dataclass(frozen=True)
class AuditTaskReadContext:
    task_tree: TaskTreeView | None
    selected_task: TaskNodeCardView | None
    record_source_task_node_id: str | None
    task_node_ids_by_legacy_id: dict[str, str]

    @property
    def record_task_node_id(self) -> str | None:
        return None if self.selected_task is None else self.selected_task.id


def active_stored_plan(
    session_id: str,
    *,
    plan_store: PlanStore | None,
    authoring_state_store: AuthoringStateStore | None,
) -> StoredPlanContext | None:
    if plan_store is None:
        return None
    plan = None
    if authoring_state_store is not None:
        active = authoring_state_store.get_active(session_id)
        if active.active_plan_id is not None:
            plan = plan_store.get_plan(session_id, active.active_plan_id)
    if plan is None:
        plan = plan_store.get_active_plan(session_id)
    if plan is None:
        legacy_plan = plan_store.get_plan(session_id, _legacy_plan_id(session_id))
        if _archived_plan(legacy_plan):
            plan = legacy_plan
    if plan is None:
        return None
    try:
        nodes = plan_store.list_task_nodes(session_id, plan.plan_id)
    except LookupError:
        return None
    return StoredPlanContext(plan=plan, task_nodes=nodes)


def _archived_plan(plan: Plan | None) -> bool:
    return plan is not None and (
        plan.status == "archived" or plan.archived_at is not None
    )


def _legacy_plan_id(session_id: str) -> str:
    return f"plan:legacy:{session_id}"


def active_plan_read_context(
    legacy_task_tree: TaskTreeView | None,
    *,
    stored_plan: StoredPlanContext | None,
    plan_projection: PlanProjectionService,
) -> ActivePlanReadContext:
    active_plan: PlanView | None
    stored_plan_nodes: list[PlanTaskNode] | None = None
    if stored_plan is not None:
        if _archived_plan(stored_plan.plan):
            return ActivePlanReadContext(
                active_plan=None,
                task_tree=None,
                stored_plan_nodes=None,
                legacy_fallback_allowed=False,
            )
        stored_plan_nodes = stored_plan.task_nodes
        active_plan = plan_projection.project_stored_plan(
            stored_plan.plan,
            stored_plan.task_nodes,
        )
    else:
        active_plan = (
            plan_projection.project_legacy_task_tree(legacy_task_tree)
            if legacy_task_tree is not None
            else None
        )
    task_tree = None if active_plan is None else active_plan.task_tree_projection
    return ActivePlanReadContext(
        active_plan=active_plan,
        task_tree=task_tree,
        stored_plan_nodes=stored_plan_nodes,
    )


def archived_plan_views(
    session_id: str,
    *,
    plan_store: PlanStore | None,
    plan_projection: PlanProjectionService,
    limit: int = 10,
) -> tuple[PlanView, ...]:
    if plan_store is None or limit <= 0:
        return ()
    archived = [
        plan for plan in plan_store.list_plans(session_id) if _archived_plan(plan)
    ]
    archived.sort(
        key=lambda plan: (plan.archived_at or plan.updated_at, plan.plan_id),
        reverse=True,
    )
    views: list[PlanView] = []
    for plan in archived[:limit]:
        try:
            nodes = plan_store.list_task_nodes(session_id, plan.plan_id)
        except LookupError:
            continue
        views.append(plan_projection.project_stored_plan(plan, nodes))
    return tuple(views)


def audit_task_read_context(
    *,
    task_node_id: str | None,
    legacy_task_tree: TaskTreeView | None,
    stored_plan: StoredPlanContext | None,
    plan_projection: PlanProjectionService,
) -> AuditTaskReadContext:
    if stored_plan is not None:
        if _archived_plan(stored_plan.plan):
            return AuditTaskReadContext(
                task_tree=None,
                selected_task=None,
                record_source_task_node_id=None,
                task_node_ids_by_legacy_id={},
            )
        plan_tree = plan_projection.project_stored_plan(
            stored_plan.plan,
            stored_plan.task_nodes,
        ).task_tree_projection
        task_node_ids_by_legacy_id = _audit_task_node_ids_by_legacy_id(plan_tree)
        selected = _selected_task(plan_tree, task_node_id)
        if selected is not None:
            return AuditTaskReadContext(
                task_tree=plan_tree,
                selected_task=selected,
                record_source_task_node_id=_legacy_task_node_id_for_audit(selected),
                task_node_ids_by_legacy_id=task_node_ids_by_legacy_id,
            )
        if task_node_id is None:
            return AuditTaskReadContext(
                task_tree=plan_tree,
                selected_task=None,
                record_source_task_node_id=None,
                task_node_ids_by_legacy_id=task_node_ids_by_legacy_id,
            )

    selected = _selected_task(legacy_task_tree, task_node_id)
    return AuditTaskReadContext(
        task_tree=legacy_task_tree,
        selected_task=selected,
        record_source_task_node_id=task_node_id,
        task_node_ids_by_legacy_id={},
    )


def result_from_plan_nodes(
    nodes: Sequence[PlanTaskNode] | None,
    *,
    session_id: str,
    task_projection: TaskProjectionService,
) -> ResultCardView | None:
    if not nodes:
        return None
    for node in reversed(_ordered_plan_nodes(nodes)):
        if node.published_ref is None:
            continue
        if (
            node.execution not in {"done", "failed"}
            and node.result_ref is None
            and node.error_ref is None
        ):
            continue
        try:
            detail = task_projection.get_task_detail(session_id, node.published_ref)
        except LookupError:
            continue
        if detail.result_summary is not None:
            return map_result_card_view(
                detail.result_summary,
                session_id=session_id,
            ).model_copy(update={"task_node_id": node.task_node_id})
    return None


def file_change_summary_from_plan_nodes(
    nodes: Sequence[PlanTaskNode] | None,
    *,
    session_id: str,
    task_projection: TaskProjectionService,
) -> FileChangeSummaryView | None:
    if not nodes:
        return None
    plan_nodes = _ordered_plan_nodes(nodes)
    owner_node_ids = {
        node.published_ref.id: node.task_node_id
        for node in plan_nodes
        if node.published_ref is not None
    }
    preferred = [node for node in plan_nodes if node.file_summary_ref is not None]
    candidates = preferred or [
        node for node in plan_nodes if node.published_ref is not None
    ]
    for node in reversed(candidates):
        if node.published_ref is None:
            continue
        try:
            detail = task_projection.get_task_detail(session_id, node.published_ref)
        except LookupError:
            continue
        if detail.file_changes:
            summary = map_file_change_summary_view(
                detail.file_changes,
                session_id=session_id,
                task_ref=node.published_ref,
                recursive=True,
            )
            return summary.model_copy(
                update={
                    "task_node_id": node.task_node_id,
                    "changed_files": tuple(
                        item.model_copy(
                            update={
                                "owner_task_node_id": owner_node_ids.get(
                                    item.owner_task_node_id or "",
                                    item.owner_task_node_id,
                                )
                            }
                        )
                        for item in summary.changed_files
                    ),
                }
            )
    return None


def _ordered_plan_nodes(nodes: Sequence[PlanTaskNode]) -> tuple[PlanTaskNode, ...]:
    return tuple(
        sorted(
            nodes,
            key=lambda node: (node.order_index, node.task_index, node.task_node_id),
        )
    )


def _legacy_task_node_id_for_audit(node: TaskNodeCardView) -> str:
    if node.task_ref is not None:
        return node.task_ref.id
    return node.id


def _audit_task_node_ids_by_legacy_id(
    task_tree: TaskTreeView | None,
) -> dict[str, str]:
    if task_tree is None:
        return {}
    return {
        node.task_ref.id: node.id
        for node in task_tree.nodes
        if node.task_ref is not None and node.task_ref.id != node.id
    }


__all__ = [
    "ActivePlanReadContext",
    "AuditTaskReadContext",
    "StoredPlanContext",
    "active_plan_read_context",
    "active_stored_plan",
    "audit_task_read_context",
    "file_change_summary_from_plan_nodes",
    "result_from_plan_nodes",
]
