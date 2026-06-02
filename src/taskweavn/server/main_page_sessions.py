"""Session lifecycle and task-reference helpers for the Main Page sidecar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from taskweavn.core import Session, SessionManager
from taskweavn.server.main_page_audit_events import (
    emit_config_manifest_audit_records_changed,
)
from taskweavn.server.ui_events import UiEventStore
from taskweavn.task import DraftTaskStore, SqliteTaskBus, TaskRef


@dataclass(frozen=True)
class MainPageTaskRefResolver:
    """Resolve UI task node ids into backend TaskRef values."""

    draft_store: DraftTaskStore
    task_bus: SqliteTaskBus

    def resolve(self, session_id: str, task_node_id: str) -> TaskRef:
        draft_node = self.draft_store.get_node(session_id, task_node_id)
        if draft_node is not None:
            return TaskRef.draft(task_node_id)
        if self.task_bus.get(session_id, task_node_id) is not None:
            return TaskRef.published(task_node_id)
        raise LookupError(f"task node {task_node_id!r} not found")


@dataclass(frozen=True)
class MainPageSessionLifecycleGateway:
    """Session lifecycle commands for the local Main Page sidecar."""

    session_manager: SessionManager
    configure_session_logging: Callable[[Session], None] | None = None
    ui_event_store: UiEventStore | None = None

    def list_sessions(self) -> dict[str, object]:
        return {"sessions": [_session_payload(session) for session in self.session_manager.list()]}

    def create_session(self, name: str) -> dict[str, object]:
        session = self.session_manager.create(name)
        if self.configure_session_logging is not None:
            self.configure_session_logging(session)
        if (session.logs_dir / "manifest.json").is_file():
            emit_config_manifest_audit_records_changed(
                self.ui_event_store,
                session_id=session.id,
            )
        return {"sessionId": session.id, "session": _session_payload(session)}

    def rename_session(self, session_id: str, name: str) -> dict[str, object]:
        session = self.session_manager.rename(session_id, name)
        return {"sessionId": session.id, "session": _session_payload(session)}

    def delete_session(self, session_id: str) -> dict[str, object]:
        next_session = self.session_manager.delete(session_id)
        return {
            "deletedSessionId": session_id,
            "nextSessionId": None if next_session is None else next_session.id,
        }


def resolve_configured_session(
    session_manager: SessionManager,
    session_id: str | None,
) -> Session | None:
    if session_id is not None:
        return session_manager.require(session_id)
    return None


def _session_payload(session: Session) -> dict[str, object]:
    return {
        "id": session.id,
        "name": session.name,
        "createdAt": session.created_at.isoformat(),
        "updatedAt": session.last_active_at.isoformat(),
        "status": session.status,
    }


__all__ = [
    "MainPageSessionLifecycleGateway",
    "MainPageTaskRefResolver",
    "resolve_configured_session",
]
