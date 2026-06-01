"""Application assembly for Plato Main Page local backend integration."""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskweavn.core import (
    AgentLoop,
    LoopResult,
    Session,
    SessionManager,
    SqliteEventStream,
    WorkspaceLayout,
)
from taskweavn.interaction import (
    InProcessMessageBus,
    SqliteMessageStream,
)
from taskweavn.observability import (
    LogArchiveManifest,
    LogRule,
    build_disabled_logging_config,
    build_session_logging_config,
    get_logging_manager,
)
from taskweavn.observability.models import LOG_CATEGORIES
from taskweavn.runtime import LocalRuntime
from taskweavn.server.client_logs import FileClientErrorLogSink
from taskweavn.server.sidecar import LocalSidecarConfig, LocalSidecarServer
from taskweavn.server.ui_command_idempotency import (
    SqliteUiCommandResponseIdempotencyStore,
    UiCommandResponseIdempotencyStore,
)
from taskweavn.server.ui_contract import (
    DefaultUiCommandGateway,
    DefaultUiQueryGateway,
    WorkspaceAuditConfigProvider,
    WorkspaceAuditEventProvider,
    WorkspaceAuditLogProvider,
)
from taskweavn.server.ui_events import ResyncOnlyEventSource, UiEventSource
from taskweavn.server.ui_http import PlatoUiHttpTransport, SidecarAuth
from taskweavn.task import (
    DEFAULT_FIXED_ROUTE_AGENT_ID,
    AgentLoopResidentDefaultAgent,
    AuthoringCommandIdempotencyStore,
    AuthoringStateStore,
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
    EventStreamFileChangeStore,
    FixedRouteExecutionDispatcher,
    FixedRouteTaskExecutor,
    FixedRouteTaskExecutorConfig,
    InMemoryCollaboratorTemplateRegistry,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    RawTaskStore,
    ResidentDefaultAgent,
    SqliteAuthoringCommandIdempotencyStore,
    SqliteAuthoringStateStore,
    SqliteDraftTaskStore,
    SqliteRawTaskStore,
    SqliteTaskBus,
    SqliteTaskExecutionSummaryStore,
    StaticCapabilityCatalog,
    TaskExecutionSummaryStore,
    TaskExecutionSummaryViewStore,
    TaskExecutionTickResult,
    TaskRef,
)
from taskweavn.tools import (
    ListDirTool,
    ReadFileTool,
    RunCommandTool,
    Tool,
    Workspace,
    WriteFileTool,
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
    enable_default_agent: bool = True
    default_agent_max_steps: int = 20
    enable_execution_dispatcher: bool = True
    execution_dispatcher_max_ticks_per_trigger: int = 10
    enable_session_logging: bool = True
    logging_level: str = "INFO"
    logging_profile: str | None = None


@dataclass(frozen=True)
class MainPageSidecarDependencies:
    """Injectable dependencies for tests and future packaging assembly."""

    llm: CollaboratorLLM
    capability_catalog: CapabilityCatalog | None = None
    event_source: UiEventSource | None = None
    raw_task_store: RawTaskStore | None = None
    draft_store: DraftTaskStore | None = None
    authoring_state_store: AuthoringStateStore | None = None
    authoring_idempotency_store: AuthoringCommandIdempotencyStore | None = None
    ui_command_idempotency_store: UiCommandResponseIdempotencyStore | None = None
    result_summary_store: TaskExecutionSummaryStore | None = None
    default_agent: ResidentDefaultAgent | None = None


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
    authoring_state_store: AuthoringStateStore | None
    authoring_idempotency_store: AuthoringCommandIdempotencyStore | None
    ui_command_idempotency_store: UiCommandResponseIdempotencyStore | None
    result_summary_store: TaskExecutionSummaryStore
    default_agent: ResidentDefaultAgent | None
    execution_dispatcher: FixedRouteExecutionDispatcher | None
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

    def run_fixed_route_tick(
        self,
        session_id: str,
        *,
        default_agent_id: str = DEFAULT_FIXED_ROUTE_AGENT_ID,
    ) -> TaskExecutionTickResult:
        executor = FixedRouteTaskExecutor(
            task_bus=self.task_bus,
            default_agent=self.default_agent,
            config=FixedRouteTaskExecutorConfig(
                session_id=session_id,
                default_agent_id=default_agent_id,
            ),
            result_summary_store=self.result_summary_store,
            message_bus=self.message_bus,
        )
        return executor.tick()

    def close(self) -> None:
        if self.execution_dispatcher is not None:
            with contextlib.suppress(Exception):
                self.execution_dispatcher.stop()
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
        for store in (
            self.authoring_state_store,
            self.authoring_idempotency_store,
            self.ui_command_idempotency_store,
            self.result_summary_store,
            self.draft_store,
            self.raw_task_store,
        ):
            close = getattr(store, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    close()
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
        logging_initializer = _configure_sidecar_logging(config)
        if session is not None:
            logging_initializer(session)
        message_stream = SqliteMessageStream(layout.workspace_messages_db)
        message_bus = InProcessMessageBus(message_stream)
        task_bus = SqliteTaskBus(layout.workspace_tasks_db)
        (
            raw_task_store,
            draft_store,
            authoring_state_store,
            authoring_idempotency_store,
        ) = _authoring_stores(
            layout,
            dependencies,
        )
        task_publisher = DefaultTaskPublisher(
            task_bus=task_bus,
            draft_store=draft_store,
        )
        authoring_command_service = DefaultAuthoringCommandService(
            raw_task_store=raw_task_store,
            draft_store=draft_store,
            message_bus=message_bus,
            task_publisher=task_publisher,
            authoring_state_store=authoring_state_store,
            idempotency_store=authoring_idempotency_store,
        )
        capability_catalog = dependencies.capability_catalog or _default_capability_catalog()
        result_summary_store = dependencies.result_summary_store or SqliteTaskExecutionSummaryStore(
            layout.workspace_results_db
        )
        default_agent = dependencies.default_agent
        if default_agent is None and config.enable_default_agent:
            default_agent = build_agent_loop_resident_default_agent(
                layout=layout,
                llm=dependencies.llm,
                max_steps=config.default_agent_max_steps,
                result_summary_store=result_summary_store,
            )
        execution_dispatcher = FixedRouteExecutionDispatcher(
            task_bus=task_bus,
            default_agent=default_agent,
            max_ticks_per_trigger=config.execution_dispatcher_max_ticks_per_trigger,
            enabled=config.enable_execution_dispatcher,
            result_summary_store=result_summary_store,
            message_bus=message_bus,
        )
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
            file_change_store=EventStreamFileChangeStore(layout),
            summary_store=TaskExecutionSummaryViewStore(result_summary_store),
            authoring_state_store=authoring_state_store,
        )
        query_gateway = DefaultUiQueryGateway(
            session_reader=session_manager,
            task_projection=task_projection,
            audit_event_provider=WorkspaceAuditEventProvider(layout),
            audit_config_provider=WorkspaceAuditConfigProvider(),
            audit_log_provider=WorkspaceAuditLogProvider(),
            session_message_provider=message_stream,
            authoring_state_store=authoring_state_store,
        )
        command_gateway = DefaultUiCommandGateway(
            collaborator=collaborator,
            task_commands=task_commands,
            task_ref_resolver=MainPageTaskRefResolver(
                draft_store=draft_store,
                task_bus=task_bus,
            ),
            authoring_state_store=authoring_state_store,
        )
        ui_command_idempotency_store = (
            dependencies.ui_command_idempotency_store
            or SqliteUiCommandResponseIdempotencyStore(layout.workspace_ui_commands_db)
        )
        transport = PlatoUiHttpTransport(
            query_gateway=query_gateway,
            command_gateway=command_gateway,
            event_source=dependencies.event_source or ResyncOnlyEventSource(),
            auth=None if config.auth_token is None else SidecarAuth(config.auth_token),
            client_error_log_sink=FileClientErrorLogSink(layout),
            session_lifecycle_gateway=MainPageSessionLifecycleGateway(
                session_manager=session_manager,
                configure_session_logging=logging_initializer,
            ),
            command_idempotency_store=ui_command_idempotency_store,
            execution_trigger_gateway=execution_dispatcher,
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
        authoring_state_store=authoring_state_store,
        authoring_idempotency_store=authoring_idempotency_store,
        ui_command_idempotency_store=ui_command_idempotency_store,
        result_summary_store=result_summary_store,
        default_agent=default_agent,
        execution_dispatcher=execution_dispatcher,
        query_gateway=query_gateway,
        command_gateway=command_gateway,
        transport=transport,
        server=server,
    )


def _authoring_stores(
    layout: WorkspaceLayout,
    dependencies: MainPageSidecarDependencies,
) -> tuple[
    RawTaskStore,
    DraftTaskStore,
    AuthoringStateStore | None,
    AuthoringCommandIdempotencyStore | None,
]:
    if dependencies.raw_task_store is None and dependencies.draft_store is None:
        authoring_db = layout.workspace_authoring_db
        return (
            SqliteRawTaskStore(authoring_db),
            SqliteDraftTaskStore(authoring_db),
            dependencies.authoring_state_store or SqliteAuthoringStateStore(authoring_db),
            dependencies.authoring_idempotency_store
            or SqliteAuthoringCommandIdempotencyStore(authoring_db),
        )

    return (
        dependencies.raw_task_store or InMemoryRawTaskStore(),
        dependencies.draft_store or InMemoryDraftTaskStore(),
        dependencies.authoring_state_store,
        dependencies.authoring_idempotency_store,
    )


def build_agent_loop_resident_default_agent(
    *,
    layout: WorkspaceLayout,
    llm: Any,
    max_steps: int = 20,
    result_summary_store: TaskExecutionSummaryStore | None = None,
) -> AgentLoopResidentDefaultAgent:
    """Build the resident Default Agent used by the fixed-route sidecar bridge."""

    return AgentLoopResidentDefaultAgent(
        loop_factory=lambda task: _SessionAgentLoopRunner(
            layout=layout,
            llm=llm,
            session_id=task.session_id,
            max_steps=max_steps,
        ),
        result_summary_store=result_summary_store,
    )


@dataclass(frozen=True)
class _SessionAgentLoopRunner:
    """Create one AgentLoop run with session-scoped workspace and events."""

    layout: WorkspaceLayout
    llm: Any
    session_id: str
    max_steps: int

    def run(self, task: str, *, task_id: str | None = None) -> LoopResult:
        self.layout.bootstrap_session(self.session_id)
        workspace = Workspace(self.layout.session_project_dir(self.session_id))
        runtime = LocalRuntime()
        tools: list[Tool[Any, Any]] = [
            ReadFileTool(workspace),
            WriteFileTool(workspace),
            ListDirTool(workspace),
            RunCommandTool(workspace),
        ]
        for tool in tools:
            tool.register(runtime)

        event_stream = SqliteEventStream(self.layout.session_events_db(self.session_id))
        try:
            loop = AgentLoop(
                llm=self.llm,
                runtime=runtime,
                tools=tools,
                event_stream=event_stream,
                max_steps=self.max_steps,
                session_id=self.session_id,
                workspace_root=workspace.root,
            )
            return loop.run(task, task_id=task_id)
        finally:
            event_stream.close()


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

    def list_sessions(self) -> dict[str, object]:
        return {"sessions": [_session_payload(session) for session in self.session_manager.list()]}

    def create_session(self, name: str) -> dict[str, object]:
        session = self.session_manager.create(name)
        if self.configure_session_logging is not None:
            self.configure_session_logging(session)
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


def _configure_sidecar_logging(
    config: MainPageSidecarConfig,
) -> Callable[[Session], None]:
    """Enable debug-phase session archives under each workspace session dir."""
    manager = get_logging_manager()
    if not config.enable_session_logging:
        manager.apply_config(build_disabled_logging_config(config.workspace_root / ".logs"))
        return lambda session: None

    base = build_session_logging_config(config.workspace_root, level=config.logging_level)
    sinks = dict(base.sinks)
    session_sink = sinks["session_file"]
    sinks["session_file"] = session_sink.model_copy(
        update={
            "path_template": (
                "{archive_root}/sessions/{session_id}/.session/logs/"
                "{category}.jsonl"
            )
        }
    )
    global_config_sink = sinks["global_config_file"]
    sinks["global_config_file"] = global_config_sink.model_copy(
        update={
            "path_template": (
                "{archive_root}/.code-agent/logs/global/{category}.jsonl"
            )
        }
    )
    rules = dict(base.rules)
    rules["config"] = LogRule(
        category="config",
        level="INFO",
        sinks=("global_config_file",),
        payload_mode="summary",
    )
    manager.apply_config(
        base.model_copy(update={"sinks": sinks, "rules": rules})
    )

    def initialize(session: Session) -> None:
        if config.logging_profile is not None:
            manager.apply_profile(session.id, config.logging_profile)
        _write_sidecar_session_log_manifest(session)

    return initialize


def _write_sidecar_session_log_manifest(session: Session) -> LogArchiveManifest:
    """Write the manifest where Audit Page already looks for session logs."""
    manager = get_logging_manager()
    log_dir = session.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = log_dir / "manifest.json"
    existing = None
    if manifest_path.exists():
        with contextlib.suppress(Exception):
            existing = LogArchiveManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
    manifest = LogArchiveManifest(
        session_id=session.id,
        created_at=(
            existing.created_at
            if existing is not None
            else datetime.now(tz=UTC)
        ),
        closed_at=None if existing is None else existing.closed_at,
        config_hash=manager.config_hash(),
        archive_root=str(log_dir),
        files={category: f"{category}.jsonl" for category in LOG_CATEGORIES},
        templates={},
        rotation={
            "enabled": True,
            "max_bytes": 10 * 1024 * 1024,
            "backup_count": 5,
        },
    )
    manifest_path.write_text(
        manifest.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    return manifest


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
    "build_agent_loop_resident_default_agent",
    "build_main_page_sidecar_app",
]
