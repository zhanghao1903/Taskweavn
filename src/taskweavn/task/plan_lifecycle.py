"""Synchronize TaskBus lifecycle facts back into durable PlanTaskNode rows."""

from __future__ import annotations

from collections.abc import Sequence

from taskweavn.task.models import TaskDomain, TaskRef
from taskweavn.task.plan_models import (
    Plan,
    PlanStatus,
    PlanTaskNode,
    PlanTaskNodeExecutionStatus,
)
from taskweavn.task.plan_stores import PlanStore


class PlanTaskNodeLifecycleSync:
    """Best-effort sync from published Task facts to durable PlanTaskNode facts."""

    def __init__(self, plan_store: PlanStore) -> None:
        self._plan_store = plan_store

    def sync_task(self, task: TaskDomain) -> PlanTaskNode | None:
        match = self._find_node(task.session_id, task.task_id)
        if match is None:
            return None
        plan, node = match
        updated = _node_from_task(node, task)
        saved = node
        if updated != node:
            saved = self._save_task_node(updated, expected_version=node.version)
        self._sync_plan_status(plan.session_id, plan.plan_id)
        return saved

    def _find_node(
        self,
        session_id: str,
        task_id: str,
    ) -> tuple[Plan, PlanTaskNode] | None:
        published_ref = TaskRef.published(task_id)
        plans = self._candidate_plans(session_id)
        for plan in plans:
            nodes = self._plan_store.list_task_nodes(session_id, plan.plan_id)
            for node in nodes:
                if node.published_ref == published_ref:
                    return plan, node
        return None

    def _candidate_plans(self, session_id: str) -> tuple[Plan, ...]:
        active = self._plan_store.get_active_plan(session_id)
        plans = self._plan_store.list_plans(session_id)
        if active is None:
            return tuple(reversed(plans))
        rest = [plan for plan in plans if plan.plan_id != active.plan_id]
        return (active, *reversed(rest))

    def _save_task_node(
        self,
        node: PlanTaskNode,
        *,
        expected_version: int,
    ) -> PlanTaskNode:
        return self._plan_store.save_task_node(node, expected_version=expected_version)

    def _sync_plan_status(self, session_id: str, plan_id: str) -> None:
        plan = self._plan_store.get_plan(session_id, plan_id)
        if plan is None:
            return
        nodes = self._plan_store.list_task_nodes(session_id, plan_id)
        status = _plan_status_from_nodes(plan, nodes)
        if status == plan.status:
            return
        self._plan_store.save_plan(
            plan.model_copy(update={"status": status}),
            expected_version=plan.version,
        )


def _node_from_task(node: PlanTaskNode, task: TaskDomain) -> PlanTaskNode:
    execution = _execution_from_task(task)
    return node.model_copy(
        update={
            "execution": execution,
            "result_ref": task.result_ref if execution == "done" else None,
            "error_ref": task.error_ref if execution == "failed" else None,
        }
    )


def _execution_from_task(task: TaskDomain) -> PlanTaskNodeExecutionStatus:
    if task.status in {"pending", "running", "waiting_for_user", "done", "failed"}:
        return task.status
    return "unknown"


def _plan_status_from_nodes(plan: Plan, nodes: Sequence[PlanTaskNode]) -> PlanStatus:
    if plan.status in {"cancelled", "archived"}:
        return plan.status
    if not nodes:
        return plan.status
    executions = {node.execution for node in nodes}
    if "failed" in executions:
        return "failed"
    if executions <= {"done"}:
        return "awaiting_acceptance"
    if executions & {"pending", "running", "waiting_for_user"}:
        return "running"
    return plan.status

__all__ = ["PlanTaskNodeLifecycleSync"]
