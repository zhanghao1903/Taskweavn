"""Application assembly for Plato Main Page local backend integration."""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast

from taskweavn.core import (
    Session,
    SessionManager,
    WorkspaceLayout,
)
from taskweavn.interaction import (
    AskStore,
    InProcessMessageBus,
    SqliteAskStore,
    SqliteMessageStream,
)
from taskweavn.observability import LogContext
from taskweavn.observability.main_page_trace import main_page_trace
from taskweavn.server.ask_recovery import DefaultAskRecoveryService
from taskweavn.server.client_logs import FileClientErrorLogSink
from taskweavn.server.diagnostics_export import DefaultDiagnosticExportGateway
from taskweavn.server.main_page_agent import build_agent_loop_resident_default_agent
from taskweavn.server.main_page_audit_events import (
    FRONTEND_ERROR_LOG_FILENAME,
    AuditEventClientErrorLogSink,
    AuditEventCommandGateway,
    emit_task_lifecycle_task_node_changed,
    ui_event_store,
)
from taskweavn.server.main_page_logging import configure_sidecar_logging
from taskweavn.server.main_page_sessions import (
    MainPageSessionLifecycleGateway,
    MainPageTaskRefResolver,
    resolve_configured_session,
)
from taskweavn.server.multi_workspace import (
    MultiWorkspacePlatoUiHttpTransport,
    WorkspaceRegistryEntry,
    WorkspaceRuntime,
    WorkspaceRuntimeRegistry,
)
from taskweavn.server.settings_config import DefaultSettingsConfigGateway
from taskweavn.server.sidecar import (
    LocalSidecarConfig,
    LocalSidecarServer,
    SidecarTransport,
)
from taskweavn.server.task_timeline import WorkspaceTaskInteractionTimelineService
from taskweavn.server.ui_command_idempotency import (
    SqliteUiCommandResponseIdempotencyStore,
    UiCommandResponseIdempotencyStore,
)
from taskweavn.server.ui_contract import (
    DefaultUiCommandGateway,
    DefaultUiQueryGateway,
    UiCommandGateway,
    WorkspaceAuditConfigProvider,
    WorkspaceAuditEventProvider,
    WorkspaceAuditLogProvider,
)
from taskweavn.server.ui_contract.ask_projection import DefaultAskProjectionService
from taskweavn.server.ui_events import (
    SqliteUiEventSource,
    UiEventCursorProvider,
    UiEventSource,
    UiEventStore,
)
from taskweavn.server.ui_http import PlatoUiHttpTransport, SidecarAuth
from taskweavn.server.ui_http_settings import (
    SettingsConfigGateway,
    SettingsReadinessGateway,
)
from taskweavn.task import (
    DEFAULT_FIXED_ROUTE_AGENT_ID,
    AuthoringCommandIdempotencyStore,
    AuthoringStateStore,
    CapabilityCatalog,
    CollaboratorLLM,
    DefaultAuthoringCommandService,
    DefaultAuthoringContextBuilder,
    DefaultCollaboratorApiAdapter,
    DefaultCollaboratorAuthoringService,
    DefaultTaskAskCommandService,
    DefaultTaskCommandService,
    DefaultTaskProjectionService,
    DefaultTaskPublisher,
    DraftPublicationStore,
    DraftTaskStore,
    EventStreamFileChangeStore,
    FixedRouteExecutionDispatcher,
    FixedRouteTaskExecutor,
    FixedRouteTaskExecutorConfig,
    InMemoryAuthoringEvidenceStore,
    InMemoryCollaboratorTemplateRegistry,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    LocalCollaboratorWorkspaceContextSource,
    RawTaskStore,
    ResidentDefaultAgent,
    SqliteAuthoringCommandIdempotencyStore,
    SqliteAuthoringStateStore,
    SqliteDraftTaskStore,
    SqliteRawTaskStore,
    SqliteTaskBus,
    SqliteTaskExecutionSummaryStore,
    StaticCapabilityCatalog,
    TaskDomain,
    TaskExecutionSummaryStore,
    TaskExecutionSummaryViewStore,
    TaskExecutionTickResult,
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
    workspace_registry: tuple[WorkspaceRegistryEntry, ...] = ()
    current_workspace_id: str | None = None


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
    settings_readiness_gateway: SettingsReadinessGateway | None = None
    settings_config_gateway: SettingsConfigGateway | None = None
    default_agent: ResidentDefaultAgent | None = None
    ask_store: AskStore | None = None


@dataclass
class MainPageWorkspaceRuntime:
    """Owns one workspace's composed Main Page backend runtime."""

    layout: WorkspaceLayout
    session: Session | None
    session_manager: SessionManager
    message_stream: SqliteMessageStream
    message_bus: InProcessMessageBus
    ask_store: AskStore
    task_bus: SqliteTaskBus
    raw_task_store: RawTaskStore
    draft_store: DraftTaskStore
    authoring_state_store: AuthoringStateStore | None
    authoring_idempotency_store: AuthoringCommandIdempotencyStore | None
    ui_command_idempotency_store: UiCommandResponseIdempotencyStore | None
    event_source: UiEventSource
    result_summary_store: TaskExecutionSummaryStore
    default_agent: ResidentDefaultAgent | None
    execution_dispatcher: FixedRouteExecutionDispatcher | None
    query_gateway: DefaultUiQueryGateway
    command_gateway: UiCommandGateway
    transport: SidecarTransport

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
            on_task_lifecycle_committed=_task_lifecycle_event_callback(
                ui_event_store(self.event_source)
            ),
        )
        return executor.tick()

    def close(self) -> None:
        if self.execution_dispatcher is not None:
            with contextlib.suppress(Exception):
                self.execution_dispatcher.stop()
        with contextlib.suppress(Exception):
            self.message_bus.close()
        close_event_source = getattr(self.event_source, "close", None)
        if close_event_source is not None:
            with contextlib.suppress(Exception):
                close_event_source()
        with contextlib.suppress(Exception):
            self.message_stream.close()
        with contextlib.suppress(Exception):
            self.task_bus.close()
        for store in (
            self.authoring_state_store,
            self.authoring_idempotency_store,
            self.ui_command_idempotency_store,
            self.result_summary_store,
            self.ask_store,
            self.draft_store,
            self.raw_task_store,
        ):
            close = getattr(store, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    close()
        with contextlib.suppress(Exception):
            self.session_manager.close()


@dataclass
class MainPageSidecarApp(MainPageWorkspaceRuntime):
    """Owns the composed Main Page backend and local sidecar lifecycle."""

    server: LocalSidecarServer
    _close_callback: Callable[[], None] | None = field(default=None, repr=False)
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
        if self._close_callback is not None:
            self._close_callback()
            return
        super().close()

    def __enter__(self) -> MainPageSidecarApp:
        self.start_in_thread()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def build_main_page_workspace_runtime(
    config: MainPageSidecarConfig,
    dependencies: MainPageSidecarDependencies,
) -> MainPageWorkspaceRuntime:
    """Build one workspace runtime for Plato Main Page."""

    layout = WorkspaceLayout(config.workspace_root)
    session_manager = SessionManager(layout)
    try:
        session = resolve_configured_session(session_manager, config.session_id)
        logging_initializer = configure_sidecar_logging(
            workspace_root=config.workspace_root,
            enable_session_logging=config.enable_session_logging,
            logging_level=config.logging_level,
            logging_profile=config.logging_profile,
        )
        if session is not None:
            logging_initializer(session)
        message_stream = SqliteMessageStream(layout.workspace_messages_db)
        message_bus = InProcessMessageBus(
            message_stream,
            default_context=(
                LogContext(session_id=session.id) if session is not None else None
            ),
        )
        ask_store = dependencies.ask_store or SqliteAskStore(layout.workspace_asks_db)
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
        event_source = dependencies.event_source or SqliteUiEventSource(
            layout.workspace_ui_events_db
        )
        event_store = ui_event_store(event_source)
        _recover_interrupted_running_tasks(
            task_bus=task_bus,
            session_manager=session_manager,
            event_store=event_store,
        )
        default_agent = dependencies.default_agent
        if default_agent is None and config.enable_default_agent:
            default_agent = build_agent_loop_resident_default_agent(
                layout=layout,
                llm=dependencies.llm,
                task_bus=task_bus,
                ask_store=ask_store,
                max_steps=config.default_agent_max_steps,
                result_summary_store=result_summary_store,
                ui_event_store=event_store,
            )
        execution_dispatcher = FixedRouteExecutionDispatcher(
            task_bus=task_bus,
            default_agent=default_agent,
            max_ticks_per_trigger=config.execution_dispatcher_max_ticks_per_trigger,
            enabled=config.enable_execution_dispatcher,
            result_summary_store=result_summary_store,
            message_bus=message_bus,
            on_task_lifecycle_committed=_task_lifecycle_event_callback(event_store),
        )
        context_builder = DefaultAuthoringContextBuilder(
            raw_task_store=raw_task_store,
            draft_store=draft_store,
            capability_catalog=capability_catalog,
            message_stream=message_stream,
        )
        authoring_evidence_store = InMemoryAuthoringEvidenceStore()
        workspace_context_source = LocalCollaboratorWorkspaceContextSource(
            workspace_root=config.workspace_root,
            evidence_store=authoring_evidence_store,
        )
        collaborator_service = DefaultCollaboratorAuthoringService(
            llm=dependencies.llm,
            context_builder=context_builder,
            command_service=authoring_command_service,
            workspace_context_source=workspace_context_source,
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
            published_task_interrupter=task_bus,
            published_task_retrier=task_bus,
            task_publisher=task_publisher,
        )
        ask_commands = DefaultTaskAskCommandService(
            ask_store=ask_store,
            task_bus=task_bus,
        )
        file_change_store = EventStreamFileChangeStore(layout)
        summary_view_store = TaskExecutionSummaryViewStore(result_summary_store)
        task_projection = DefaultTaskProjectionService(
            task_store=task_bus,
            draft_store=draft_store,
            message_stream=message_stream,
            file_change_store=file_change_store,
            summary_store=summary_view_store,
            authoring_state_store=authoring_state_store,
        )
        task_timeline = WorkspaceTaskInteractionTimelineService(
            layout=layout,
            projection_service=task_projection,
            draft_store=draft_store,
            message_stream=message_stream,
            file_change_store=file_change_store,
            summary_store=summary_view_store,
            publication_store=(
                draft_store if isinstance(draft_store, DraftPublicationStore) else None
            ),
        )
        query_gateway = DefaultUiQueryGateway(
            session_reader=session_manager,
            task_projection=task_projection,
            audit_event_provider=WorkspaceAuditEventProvider(layout),
            audit_config_provider=WorkspaceAuditConfigProvider(),
            audit_log_provider=WorkspaceAuditLogProvider(),
            task_timeline_service=task_timeline,
            session_message_provider=message_stream,
            authoring_state_store=authoring_state_store,
            raw_task_store=raw_task_store,
            ask_projection=DefaultAskProjectionService(ask_store),
            snapshot_cursor_provider=_snapshot_cursor_provider(event_source),
        )
        core_command_gateway = DefaultUiCommandGateway(
            collaborator=collaborator,
            task_commands=task_commands,
            task_ref_resolver=MainPageTaskRefResolver(
                draft_store=draft_store,
                task_bus=task_bus,
            ),
            authoring_state_store=authoring_state_store,
            raw_task_store=raw_task_store,
            ask_commands=ask_commands,
            task_projection=task_projection,
        )
        command_gateway: UiCommandGateway = AuditEventCommandGateway(
            inner=core_command_gateway,
            event_store=event_store,
        )
        ask_recovery = DefaultAskRecoveryService(
            raw_task_store=raw_task_store,
            collaborator=collaborator,
            authoring_state_store=authoring_state_store,
            ask_store=ask_store,
            task_bus=task_bus,
            execution_trigger_gateway=execution_dispatcher,
            on_task_lifecycle_committed=_task_lifecycle_event_callback(event_store),
        )
        ui_command_idempotency_store = (
            dependencies.ui_command_idempotency_store
            or SqliteUiCommandResponseIdempotencyStore(layout.workspace_ui_commands_db)
        )
        settings_config_gateway = (
            dependencies.settings_config_gateway
            or DefaultSettingsConfigGateway(
                workspace_root=config.workspace_root,
                logging_enabled=config.enable_session_logging,
                logging_level=config.logging_level,
                selected_logging_profile=config.logging_profile,
            )
        )
        transport = PlatoUiHttpTransport(
            query_gateway=query_gateway,
            command_gateway=command_gateway,
            event_source=event_source,
            auth=None if config.auth_token is None else SidecarAuth(config.auth_token),
            client_error_log_sink=AuditEventClientErrorLogSink(
                inner=FileClientErrorLogSink(
                    layout,
                    filename=FRONTEND_ERROR_LOG_FILENAME,
                ),
                event_store=event_store,
            ),
            session_lifecycle_gateway=MainPageSessionLifecycleGateway(
                session_manager=session_manager,
                configure_session_logging=logging_initializer,
                ui_event_store=event_store,
            ),
            command_idempotency_store=ui_command_idempotency_store,
            execution_trigger_gateway=execution_dispatcher,
            snapshot_recovery_gateway=ask_recovery,
            settings_readiness_gateway=(
                dependencies.settings_readiness_gateway or settings_config_gateway
            ),
            settings_config_gateway=settings_config_gateway,
            diagnostic_export_gateway=DefaultDiagnosticExportGateway(
                workspace_root=config.workspace_root,
            ),
        )
    except Exception:
        session_manager.close()
        raise

    return MainPageWorkspaceRuntime(
        layout=layout,
        session=session,
        session_manager=session_manager,
        message_stream=message_stream,
        message_bus=message_bus,
        ask_store=ask_store,
        task_bus=task_bus,
        raw_task_store=raw_task_store,
        draft_store=draft_store,
        authoring_state_store=authoring_state_store,
        authoring_idempotency_store=authoring_idempotency_store,
        ui_command_idempotency_store=ui_command_idempotency_store,
        event_source=event_source,
        result_summary_store=result_summary_store,
        default_agent=default_agent,
        execution_dispatcher=execution_dispatcher,
        query_gateway=query_gateway,
        command_gateway=command_gateway,
        transport=transport,
    )


def build_main_page_sidecar_app(
    config: MainPageSidecarConfig,
    dependencies: MainPageSidecarDependencies,
) -> MainPageSidecarApp:
    """Build the local sidecar target for Plato Main Page."""

    if config.workspace_registry:
        return _build_multi_workspace_sidecar_app(config, dependencies)

    runtime = build_main_page_workspace_runtime(config, dependencies)
    server = LocalSidecarServer(
        runtime.transport,
        config=LocalSidecarConfig(host=config.host, port=config.port),
    )
    return _sidecar_app_from_runtime(runtime, server)


def _build_multi_workspace_sidecar_app(
    config: MainPageSidecarConfig,
    dependencies: MainPageSidecarDependencies,
) -> MainPageSidecarApp:
    current_workspace_id = _current_workspace_id(
        config.workspace_registry,
        configured_id=config.current_workspace_id,
    )

    def runtime_factory(entry: WorkspaceRegistryEntry) -> MainPageWorkspaceRuntime:
        runtime_config = replace(
            config,
            workspace_root=entry.root_path,
            session_id=(
                config.session_id
                if entry.workspace_id == current_workspace_id
                else None
            ),
            workspace_registry=(),
            current_workspace_id=None,
            port=0,
        )
        return build_main_page_workspace_runtime(runtime_config, dependencies)

    registry = WorkspaceRuntimeRegistry(
        entries=config.workspace_registry,
        current_workspace_id=current_workspace_id,
        runtime_factory=cast(
            Callable[[WorkspaceRegistryEntry], WorkspaceRuntime],
            runtime_factory,
        ),
    )
    current_runtime = cast(
        MainPageWorkspaceRuntime,
        registry.get_runtime(current_workspace_id),
    )
    transport = MultiWorkspacePlatoUiHttpTransport(
        registry=registry,
        auth=None if config.auth_token is None else SidecarAuth(config.auth_token),
    )
    server = LocalSidecarServer(
        transport,
        config=LocalSidecarConfig(host=config.host, port=config.port),
    )
    return _sidecar_app_from_runtime(
        replace(current_runtime, transport=transport),
        server,
        close_callback=registry.close_all,
    )


def _current_workspace_id(
    entries: tuple[WorkspaceRegistryEntry, ...],
    *,
    configured_id: str | None,
) -> str:
    if configured_id is not None:
        return configured_id
    for entry in entries:
        if entry.is_current:
            return entry.workspace_id
    return entries[0].workspace_id


def _sidecar_app_from_runtime(
    runtime: MainPageWorkspaceRuntime,
    server: LocalSidecarServer,
    *,
    close_callback: Callable[[], None] | None = None,
) -> MainPageSidecarApp:
    return MainPageSidecarApp(
        layout=runtime.layout,
        session=runtime.session,
        session_manager=runtime.session_manager,
        message_stream=runtime.message_stream,
        message_bus=runtime.message_bus,
        ask_store=runtime.ask_store,
        task_bus=runtime.task_bus,
        raw_task_store=runtime.raw_task_store,
        draft_store=runtime.draft_store,
        authoring_state_store=runtime.authoring_state_store,
        authoring_idempotency_store=runtime.authoring_idempotency_store,
        ui_command_idempotency_store=runtime.ui_command_idempotency_store,
        event_source=runtime.event_source,
        result_summary_store=runtime.result_summary_store,
        default_agent=runtime.default_agent,
        execution_dispatcher=runtime.execution_dispatcher,
        query_gateway=runtime.query_gateway,
        command_gateway=runtime.command_gateway,
        transport=runtime.transport,
        server=server,
        _close_callback=close_callback,
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


def _task_lifecycle_event_callback(
    event_store: UiEventStore | None,
) -> Callable[[TaskDomain], None]:
    def emit(task: TaskDomain) -> None:
        emit_task_lifecycle_task_node_changed(
            event_store,
            session_id=task.session_id,
            task_id=task.task_id,
        )

    return emit


def _snapshot_cursor_provider(
    event_source: UiEventSource,
) -> UiEventCursorProvider | None:
    if isinstance(event_source, UiEventCursorProvider):
        return event_source
    return None


def _recover_interrupted_running_tasks(
    *,
    task_bus: SqliteTaskBus,
    session_manager: SessionManager,
    event_store: UiEventStore | None,
) -> None:
    sessions = session_manager.list()
    main_page_trace(
        "sidecar.recover_interrupted_running.scan_start",
        session_count=len(sessions),
    )
    for session in sessions:
        recovered_tasks = task_bus.recover_interrupted_running_tasks(session.id)
        main_page_trace(
            "sidecar.recover_interrupted_running.session_result",
            recovered_task_ids=tuple(task.task_id for task in recovered_tasks),
            recovered_task_count=len(recovered_tasks),
            session_id=session.id,
        )
        for task in recovered_tasks:
            emit_task_lifecycle_task_node_changed(
                event_store,
                session_id=task.session_id,
                task_id=task.task_id,
            )


__all__ = [
    "DEFAULT_PLATO_SIDECAR_PORT",
    "MainPageSidecarApp",
    "MainPageSidecarConfig",
    "MainPageSidecarDependencies",
    "MainPageWorkspaceRuntime",
    "MainPageSessionLifecycleGateway",
    "MainPageTaskRefResolver",
    "WorkspaceRegistryEntry",
    "build_agent_loop_resident_default_agent",
    "build_main_page_sidecar_app",
    "build_main_page_workspace_runtime",
]
