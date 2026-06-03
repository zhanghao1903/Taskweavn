"""Application assembly for Plato Main Page local backend integration."""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass, field
from pathlib import Path

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
from taskweavn.server.client_logs import FileClientErrorLogSink
from taskweavn.server.main_page_agent import build_agent_loop_resident_default_agent
from taskweavn.server.main_page_audit_events import (
    FRONTEND_ERROR_LOG_FILENAME,
    AuditEventClientErrorLogSink,
    AuditEventCommandGateway,
    ui_event_store,
)
from taskweavn.server.main_page_logging import configure_sidecar_logging
from taskweavn.server.main_page_sessions import (
    MainPageSessionLifecycleGateway,
    MainPageTaskRefResolver,
    resolve_configured_session,
)
from taskweavn.server.sidecar import LocalSidecarConfig, LocalSidecarServer
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
    UiEventSource,
)
from taskweavn.server.ui_http import PlatoUiHttpTransport, SidecarAuth
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
    ask_store: AskStore | None = None


@dataclass
class MainPageSidecarApp:
    """Owns the composed Main Page backend and local sidecar lifecycle."""

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
        message_bus = InProcessMessageBus(message_stream)
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
            published_task_interrupter=task_bus,
            published_task_retrier=task_bus,
            task_publisher=task_publisher,
        )
        ask_commands = DefaultTaskAskCommandService(
            ask_store=ask_store,
            task_bus=task_bus,
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
            ask_projection=DefaultAskProjectionService(ask_store),
        )
        core_command_gateway = DefaultUiCommandGateway(
            collaborator=collaborator,
            task_commands=task_commands,
            task_ref_resolver=MainPageTaskRefResolver(
                draft_store=draft_store,
                task_bus=task_bus,
            ),
            authoring_state_store=authoring_state_store,
            ask_commands=ask_commands,
        )
        command_gateway: UiCommandGateway = AuditEventCommandGateway(
            inner=core_command_gateway,
            event_store=event_store,
        )
        ui_command_idempotency_store = (
            dependencies.ui_command_idempotency_store
            or SqliteUiCommandResponseIdempotencyStore(layout.workspace_ui_commands_db)
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
