"""Store protocols for durable Plan and TaskNode facts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from taskweavn.task.plan_models import Plan, PlanTaskNode
from taskweavn.task.stores import TaskStoreError


class PlanStoreError(TaskStoreError):
    """Raised for durable Plan/TaskNode store consistency failures."""


@runtime_checkable
class PlanTaskNodeStore(Protocol):
    """Persistence boundary for durable TaskNode facts inside a Plan."""

    def get_task_node(self, session_id: str, task_node_id: str) -> PlanTaskNode | None: ...

    def list_task_nodes(self, session_id: str, plan_id: str) -> list[PlanTaskNode]: ...

    def add_task_node(
        self,
        node: PlanTaskNode,
        *,
        expected_plan_version: int | None = None,
    ) -> PlanTaskNode: ...

    def save_task_node(
        self,
        node: PlanTaskNode,
        *,
        expected_version: int,
    ) -> PlanTaskNode: ...


@runtime_checkable
class PlanStore(PlanTaskNodeStore, Protocol):
    """Persistence boundary for durable Plan facts.

    The first implementation owns only durable Plan/TaskNode rows. Legacy
    DraftTaskTree reads stay on DraftTaskStore during the migration.
    """

    def create_plan(
        self,
        plan: Plan,
        task_nodes: Sequence[PlanTaskNode] = (),
    ) -> Plan: ...

    def get_plan(self, session_id: str, plan_id: str) -> Plan | None: ...

    def list_plans(self, session_id: str) -> list[Plan]: ...

    def get_active_plan(self, session_id: str) -> Plan | None: ...

    def save_plan(self, plan: Plan, *, expected_version: int) -> Plan: ...


__all__ = [
    "PlanStore",
    "PlanStoreError",
    "PlanTaskNodeStore",
]
