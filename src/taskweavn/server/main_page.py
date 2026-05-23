"""Application assembly for Plato Main Page local backend integration."""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass, field
from pathlib import Path

from taskweavn.core import Session, SessionManager, WorkspaceLayout
from taskweavn.interaction import (
    InProcessMessageBus,
    SqliteMessageStream,
)
from taskweavn.server.client_logs import FileClientErrorLogSink
from taskweavn.server.sidecar import LocalSidecarConfig, LocalSidecarServer
from taskweavn.server.ui_contract import (
    DefaultUiCommandGateway,
    DefaultUiQueryGateway,
)
from taskweavn.server.ui_events import ResyncOnlyEventSource, UiEventSource
from taskweavn.server.ui_http import PlatoUiHttpTransport, SidecarAuth
from taskweavn.task import (
    CapabilityCatalog,
    CollaboratorLLM,
    DefaultAuthoringCommandService,
    DefaultAuthoringContextBuilder,
    DefaultCollaboratorApiAdapter,
    DefaultCollaboratorAuthoringService,
    DefaultTaskCommandService,
    DefaultTaskProjectionService,
    DefaultTaskPublisher,
    DraftTaskStore,
    InMemoryCollaboratorTemplateRegistry,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    RawTaskStore,
    SqliteTaskBus,
    StaticCapabilityCatalog,
    TaskRef,
)

DEFAULT_PLATO_SIDECAR_PORT = 52789


@dataclass(frozen=True)
class MainPageSidecarConfig:
    """Runtime configuration for the local Main Page sidecar app."""

    workspace_root: Path
    session_id: str | None = None
    session_name: str = "Plato session"
    host: str = "127.0.0.1"
    port: int = DEFAULT_PLATO_SIDECAR_PORT
    auth_token: str | None = None


@dataclass(frozen=True)
class MainPageSidecarDependencies:
    """Injectable dependencies for tests and future packaging assembly."""

    llm: CollaboratorLLM
    capability_catalog: CapabilityCatalog | None = None
    event_source: UiEventSource | None = None
    raw_task_store: RawTaskStore | None = None
    draft_store: DraftTaskStore | None = None


@dataclass
class MainPageSidecarApp:
    """Owns the composed Main Page backend and local sidecar lifecycle."""

    layout: WorkspaceLayout
    session: Session | None
    session_manager: SessionManager
    message_stream: SqliteMessageStream
    message_bus: InProcessMessageBus
    task_bus: SqliteTaskBus
    raw_task_store: RawTaskStore
    draft_store: DraftTaskStore
    query_gateway: DefaultUiQueryGateway
    command_gateway: DefaultUiCommandGateway
    transport: PlatoUiHttpTransport
    server: LocalSidecarServer
    _server_thread: threading.Thread | None = field(default=None, init=False)

    @property
    def base_url(self) -> str:
        return self.server.base_url

    def start_in_thread(self) -> threading.Thread:
        self._server_thread = self.server.start_in_thread()
        return self._server_thread

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def close(self) -> None:
        if self._server_thread is not None:
            with contextlib.suppress(Exception):
                self.server.shutdown()
        with contextlib.suppress(Exception):
            self.server.server_close()
        with contextlib.suppress(Exception):
            self.message_bus.close()
        with contextlib.suppress(Exception):
            self.message_stream.close()
        with contextlib.suppress(Exception):
            self.task_bus.close()
        with contextlib.suppress(Exception):
            self.session_manager.close()

    def __enter__(self) -> MainPageSidecarApp:
        self.start_in_thread()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def build_main_page_sidecar_app(
    config: MainPageSidecarConfig,
    dependencies: MainPageSidecarDependencies,
) -> MainPageSidecarApp:
    """Build the first local sidecar target for Plato Main Page."""

    layout = WorkspaceLayout(config.workspace_root)
    session_manager = SessionManager(layout)
    try:
        session = _resolve_session(session_manager, config)
        message_stream = SqliteMessageStream(layout.workspace_messages_db)
        message_bus = InProcessMessageBus(message_stream)
        task_bus = SqliteTaskBus(layout.workspace_tasks_db)
        raw_task_store = dependencies.raw_task_store or InMemoryRawTaskStore()
        draft_store = dependencies.draft_store or InMemoryDraftTaskStore()
        task_publisher = DefaultTaskPublisher(
            task_bus=task_bus,
            draft_store=draft_store,
        )
        authoring_command_service = DefaultAuthoringCommandService(
            raw_task_store=raw_task_store,
            draft_store=draft_store,
            message_bus=message_bus,
            task_publisher=task_publisher,
        )
        capability_catalog = dependencies.capability_catalog or _default_capability_catalog()
        context_builder = DefaultAuthoringContextBuilder(
            raw_task_store=raw_task_store,
            draft_store=draft_store,
            capability_catalog=capability_catalog,
            message_stream=message_stream,
        )
        collaborator_service = DefaultCollaboratorAuthoringService(
            llm=dependencies.llm,
            context_builder=context_builder,
            command_service=authoring_command_service,
        )
        collaborator = DefaultCollaboratorApiAdapter(
            collaborator_service=collaborator_service,
            command_service=authoring_command_service,
            template_registry=InMemoryCollaboratorTemplateRegistry(),
            message_bus=message_bus,
        )
        task_commands = DefaultTaskCommandService(
            task_store=task_bus,
            draft_store=draft_store,
            message_bus=message_bus,
            task_publisher=task_publisher,
        )
        task_projection = DefaultTaskProjectionService(
            task_store=task_bus,
            draft_store=draft_store,
            message_stream=message_stream,
        )
        query_gateway = DefaultUiQueryGateway(
            session_reader=session_manager,
            task_projection=task_projection,
            session_message_provider=message_stream,
        )
        command_gateway = DefaultUiCommandGateway(
            collaborator=collaborator,
            task_commands=task_commands,
            task_ref_resolver=MainPageTaskRefResolver(
                draft_store=draft_store,
                task_bus=task_bus,
            ),
        )
        transport = PlatoUiHttpTransport(
            query_gateway=query_gateway,
            command_gateway=command_gateway,
            event_source=dependencies.event_source or ResyncOnlyEventSource(),
            auth=None if config.auth_token is None else SidecarAuth(config.auth_token),
            client_error_log_sink=FileClientErrorLogSink(layout),
            session_lifecycle_gateway=MainPageSessionLifecycleGateway(
                session_manager=session_manager,
            ),
        )
        server = LocalSidecarServer(
            transport,
            config=LocalSidecarConfig(host=config.host, port=config.port),
        )
    except Exception:
        session_manager.close()
        raise

    return MainPageSidecarApp(
        layout=layout,
        session=session,
        session_manager=session_manager,
        message_stream=message_stream,
        message_bus=message_bus,
        task_bus=task_bus,
        raw_task_store=raw_task_store,
        draft_store=draft_store,
        query_gateway=query_gateway,
        command_gateway=command_gateway,
        transport=transport,
        server=server,
    )


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

    def list_sessions(self) -> dict[str, object]:
        return {
            "sessions": [_session_payload(session) for session in self.session_manager.list()]
        }

    def create_session(self, name: str) -> dict[str, object]:
        session = self.session_manager.create(name)
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


def _resolve_session(
    session_manager: SessionManager,
    config: MainPageSidecarConfig,
) -> Session | None:
    if config.session_id is not None:
        return session_manager.require(config.session_id)
    return None


def _default_capability_catalog() -> StaticCapabilityCatalog:
    return StaticCapabilityCatalog(
        (
            "general",
            "writing",
            "coding",
            "testing",
            "research",
        )
    )


def _session_payload(session: Session) -> dict[str, object]:
    return {
        "id": session.id,
        "name": session.name,
        "createdAt": session.created_at.isoformat(),
        "updatedAt": session.last_active_at.isoformat(),
        "status": session.status,
    }


__all__ = [
    "DEFAULT_PLATO_SIDECAR_PORT",
    "MainPageSidecarApp",
    "MainPageSidecarConfig",
    "MainPageSidecarDependencies",
    "MainPageSessionLifecycleGateway",
    "MainPageTaskRefResolver",
    "build_main_page_sidecar_app",
]
