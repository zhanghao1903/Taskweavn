"""Default provider implementations for Plato UI contract gateways."""

from __future__ import annotations

from dataclasses import dataclass

from taskweavn.core import SqliteEventStream, WorkspaceLayout
from taskweavn.core.session import Session
from taskweavn.server.ui_contract.view_models import ProjectSummary, WorkflowSummary
from taskweavn.types.base import BaseEvent


@dataclass(frozen=True)
class StaticProjectProvider:
    project: ProjectSummary = ProjectSummary(id="local", name="Local Project")

    def get_project(self) -> ProjectSummary:
        return self.project


@dataclass(frozen=True)
class StaticWorkflowProvider:
    workflow: WorkflowSummary = WorkflowSummary(
        id="task_authoring",
        name="Task authoring",
        description="Turn user intent into a Task Tree.",
        input_hint="Describe what you want Plato to do.",
        delivery_kind="task_tree",
    )

    def list_workflows(self) -> tuple[WorkflowSummary, ...]:
        return (self.workflow,)

    def get_workflow(self, session: Session) -> WorkflowSummary:
        return self.workflow


@dataclass(frozen=True)
class WorkspaceAuditEventProvider:
    """Read Audit Page execution evidence from a session ``events.sqlite``."""

    layout: WorkspaceLayout

    def list_for_session(
        self,
        session: Session,
        *,
        task_node_id: str | None = None,
    ) -> tuple[BaseEvent, ...]:
        db_path = self.layout.session_events_db(session.id)
        if not db_path.exists():
            return ()
        with SqliteEventStream(db_path) as stream:
            if task_node_id is not None:
                return tuple(stream.iter_for_task(task_node_id))
            return tuple(stream.replay())
