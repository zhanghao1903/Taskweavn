"""Application assembly for Plato Main Page local backend integration."""

from __future__ import annotations

import contextlib
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from taskweavn.contract_revision import (
    ContractCommandIdempotencyStore,
    ContractRevisionCommandService,
    GuidanceFactStore,
    MessageBusContractRevisionActivityPublisher,
    SqliteContractCommandIdempotencyStore,
    SqliteGuidanceFactStore,
    UiGatewayContractInteractionCommandHandler,
    UiGatewayContractTaskNodeCommandHandler,
)
from taskweavn.core import (
    Session,
    SessionManager,
    WorkspaceLayout,
)
from taskweavn.execution_plane import (
    EmbeddedTaskApiService,
    SqliteExecutionPlaneStore,
)
from taskweavn.interaction import (
    AskStore,
    InProcessMessageBus,
    SqliteAskStore,
    SqliteMessageStream,
)
from taskweavn.llm.agent_config import AgentLlmRole
from taskweavn.llm.agent_resolver import SettingsBackedAgentLlmResolver
from taskweavn.observability import LogContext
from taskweavn.runtime_config import (
    DefaultRuntimeConfigMutationService,
    EffectiveRuntimeConfig,
    RuntimeConfigChangeStore,
    RuntimeConfigMutationServiceConfig,
    RuntimeConfigScope,
    SqliteRuntimeConfigChangeStore,
)
from taskweavn.server.ask_recovery import DefaultAskRecoveryService
from taskweavn.server.client_logs import FileClientErrorLogSink
from taskweavn.server.computer_use_runtime import (
    build_execution_env_registry,
    build_execution_plane_runtime_handlers,
)
from taskweavn.server.diagnostics_export import DefaultDiagnosticExportGateway
from taskweavn.server.main_page_agent import build_agent_loop_resident_default_agent
from taskweavn.server.main_page_audit_events import (
    FRONTEND_ERROR_LOG_FILENAME,
    AuditEventClientErrorLogSink,
    AuditEventCommandGateway,
    task_lifecycle_event_callback,
    ui_event_store,
)
from taskweavn.server.main_page_logging import configure_sidecar_logging
from taskweavn.server.main_page_sessions import (
    MainPageSessionLifecycleGateway,
    MainPageTaskRefResolver,
    resolve_configured_session,
)
from taskweavn.server.main_page_usage import task_plan_resolver
from taskweavn.server.multi_workspace import (
    MultiWorkspacePlatoUiHttpTransport,
    WorkspaceRegistryEntry,
    WorkspaceRuntime,
    WorkspaceRuntimeRegistry,
)
from taskweavn.server.read_only_inquiry import DefaultReadOnlyInquiryService
from taskweavn.server.read_only_inquiry_answer_provider import (
    GuardedLLMReadOnlyInquiryAnswerProvider,
)
from taskweavn.server.read_only_inquiry_diagnostics import (
    DefaultDiagnosticSupportContextProvider,
)
from taskweavn.server.runtime_config_consumers import (
    runtime_computer_use_settings_from_config,
    runtime_context_settings_from_config,
    runtime_execution_settings_from_config,
    runtime_read_only_inquiry_settings_from_config,
)
from taskweavn.server.runtime_config_gateway import DefaultRuntimeConfigGateway
from taskweavn.server.runtime_input_activity import (
    MessageBusRuntimeInputActivityPublisher,
)
from taskweavn.server.runtime_input_llm_router import LLMRuntimeInputRoutePlanner
from taskweavn.server.runtime_input_router import DefaultRuntimeInputRouter
from taskweavn.server.settings_config import (
    DefaultSettingsConfigGateway,
    effective_web_search_settings,
    file_settings_config_store_for,
)
from taskweavn.server.sidecar import (
    LocalSidecarConfig,
    LocalSidecarServer,
    SidecarTransport,
)
from taskweavn.server.task_stop_recovery import (
    CompositeSnapshotRecoveryService,
    DefaultTaskStopRecoveryService,
    recover_interrupted_running_tasks_on_startup,
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
)
from taskweavn.server.ui_http import PlatoUiHttpTransport, SidecarAuth
from taskweavn.server.ui_http_settings import (
    SettingsConfigGateway,
    SettingsReadinessGateway,
)
from taskweavn.server.ui_http_usage import DefaultTokenUsageSummaryGateway
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
    DefaultPlanLifecycleCommandService,
    DefaultPlanPublisher,
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
    PlanTaskNodeLifecycleSync,
    RawTaskStore,
    ResidentDefaultAgent,
    SqliteAuthoringCommandIdempotencyStore,
    SqliteAuthoringStateStore,
    SqliteDraftTaskStore,
    SqlitePlanStore,
    SqliteRawTaskStore,
    SqliteTaskBus,
    SqliteTaskExecutionSummaryStore,
    StaticCapabilityCatalog,
    TaskExecutionSummaryStore,
    TaskExecutionSummaryViewStore,
    TaskExecutionTickResult,
)
from taskweavn.tools import ComputerUseBackend
from taskweavn.usage import SqliteTokenUsageStore, UsageRecordingLLM
from taskweavn.web_retrieval import TavilyWebSearchProvider, WebSearchProvider
from taskweavn.workspace_inspection import DefaultWorkspaceInspectionGateway

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
    context_checkpoint_interval_steps: int = 5
    context_max_prior_messages: int = 200
    context_budget_max_events: int = 20
    context_budget_max_tool_results: int = 10
    context_budget_max_file_snippets: int = 6
    context_budget_max_file_snippet_chars: int = 8_000
    context_budget_max_rendered_chars: int = 60_000
    enable_execution_dispatcher: bool = True
    execution_dispatcher_max_ticks_per_trigger: int = 10
    enable_session_logging: bool = True
    logging_level: str = "INFO"
    logging_profile: str | None = None
    workspace_registry: tuple[WorkspaceRegistryEntry, ...] = ()
    current_workspace_id: str | None = None
    global_settings_root: Path | None = None
    enable_read_only_inquiry_llm: bool = True
    enable_computer_use_tool: bool = False
    computer_use_backend_name: str = "disabled"
    computer_use_allowed_apps: tuple[str, ...] = ()


@dataclass(frozen=True)
class MainPageSidecarDependencies:
    """Injectable dependencies for tests and future packaging assembly."""

    llm: CollaboratorLLM | None = None
    llm_factory: Callable[[Path], CollaboratorLLM] | None = None
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
    computer_use_backend: ComputerUseBackend | None = None
    guidance_store: GuidanceFactStore | None = None


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
    plan_store: SqlitePlanStore
    plan_lifecycle_sync: PlanTaskNodeLifecycleSync
    raw_task_store: RawTaskStore
    draft_store: DraftTaskStore
    authoring_state_store: AuthoringStateStore | None
    authoring_idempotency_store: AuthoringCommandIdempotencyStore | None
    ui_command_idempotency_store: UiCommandResponseIdempotencyStore | None
    contract_revision_idempotency_store: ContractCommandIdempotencyStore | None
    guidance_store: GuidanceFactStore | None
    event_source: UiEventSource
    result_summary_store: TaskExecutionSummaryStore
    execution_plane_store: SqliteExecutionPlaneStore | None
    token_usage_store: SqliteTokenUsageStore
    runtime_config_change_store: RuntimeConfigChangeStore | None
    runtime_config: EffectiveRuntimeConfig
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
            on_task_lifecycle_committed=task_lifecycle_event_callback(
                ui_event_store(self.event_source),
                plan_lifecycle_sync=self.plan_lifecycle_sync,
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
            self.contract_revision_idempotency_store,
            self.guidance_store,
            self.result_summary_store,
            self.execution_plane_store,
            self.token_usage_store,
            self.runtime_config_change_store,
            self.ask_store,
            self.plan_store,
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
        guidance_store = dependencies.guidance_store or SqliteGuidanceFactStore(
            layout.workspace_contract_revision_db
        )
        contract_revision_idempotency_store = SqliteContractCommandIdempotencyStore(
            layout.workspace_contract_revision_db
        )
        task_bus = SqliteTaskBus(layout.workspace_tasks_db)
        token_usage_store = SqliteTokenUsageStore(layout.workspace_usage_db)
        settings_store = file_settings_config_store_for(
            workspace_root=config.workspace_root,
            global_settings_root=config.global_settings_root,
        )
        agent_llms = _workspace_agent_llms(
            config,
            dependencies,
            settings_store=settings_store,
            token_usage_store=token_usage_store,
            task_bus=task_bus,
        )
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
        plan_store = SqlitePlanStore(layout.workspace_authoring_db)
        plan_lifecycle_sync = PlanTaskNodeLifecycleSync(plan_store)
        plan_publisher = DefaultPlanPublisher(
            plan_store=plan_store,
            task_publisher=task_publisher,
        )
        plan_lifecycle_commands = DefaultPlanLifecycleCommandService(
            plan_store=plan_store,
            authoring_state_store=authoring_state_store,
            message_bus=message_bus,
        )
        authoring_command_service = DefaultAuthoringCommandService(
            raw_task_store=raw_task_store,
            draft_store=draft_store,
            message_bus=message_bus,
            task_publisher=task_publisher,
            authoring_state_store=authoring_state_store,
            plan_store=plan_store,
            idempotency_store=authoring_idempotency_store,
        )
        capability_catalog = dependencies.capability_catalog or _default_capability_catalog()
        result_summary_store = dependencies.result_summary_store or SqliteTaskExecutionSummaryStore(
            layout.workspace_results_db
        )
        settings_config_gateway = (
            dependencies.settings_config_gateway
            or DefaultSettingsConfigGateway(
                workspace_root=config.workspace_root,
                logging_enabled=config.enable_session_logging,
                logging_level=config.logging_level,
                selected_logging_profile=config.logging_profile,
                store=settings_store,
            )
        )
        event_source = dependencies.event_source or SqliteUiEventSource(
            layout.workspace_ui_events_db
        )
        event_store = ui_event_store(event_source)
        current_workspace_id = config.current_workspace_id or "current"
        runtime_config_change_store = SqliteRuntimeConfigChangeStore(
            layout.workspace_runtime_config_db
        )
        runtime_config_mutation_service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=runtime_config_change_store)
        )
        runtime_config_gateway = DefaultRuntimeConfigGateway.from_process_inputs(
            _runtime_config_process_values(config),
            workspace_id=current_workspace_id,
            change_store=runtime_config_change_store,
        )
        runtime_config = runtime_config_gateway.effective(
            RuntimeConfigScope(
                level="workspace",
                workspace_id=current_workspace_id,
            )
        )
        runtime_execution_settings = runtime_execution_settings_from_config(
            runtime_config
        )
        runtime_context_settings = runtime_context_settings_from_config(runtime_config)
        runtime_computer_use_settings = runtime_computer_use_settings_from_config(
            runtime_config
        )
        runtime_read_only_inquiry_settings = (
            runtime_read_only_inquiry_settings_from_config(runtime_config)
        )
        recover_interrupted_running_tasks_on_startup(
            task_bus=task_bus,
            session_ids=(session.id for session in session_manager.list()),
            on_task_recovered=task_lifecycle_event_callback(
                event_store,
                plan_lifecycle_sync=plan_lifecycle_sync,
            ),
        )
        default_agent = dependencies.default_agent
        if default_agent is None and config.enable_default_agent:
            default_agent = build_agent_loop_resident_default_agent(
                layout=layout,
                llm=agent_llms.execution,
                task_bus=task_bus,
                ask_store=ask_store,
                message_bus=message_bus,
                max_steps=runtime_execution_settings.default_agent_max_steps,
                context_settings=runtime_context_settings,
                result_summary_store=result_summary_store,
                ui_event_store=event_store,
                settings_store=settings_store,
                enable_computer_use_tool=runtime_computer_use_settings.enabled,
                computer_use_backend=dependencies.computer_use_backend,
                contract_guidance_store=guidance_store,
            )
        execution_dispatcher = FixedRouteExecutionDispatcher(
            task_bus=task_bus,
            default_agent=default_agent,
            max_ticks_per_trigger=(
                runtime_execution_settings.execution_dispatcher_max_ticks_per_trigger
            ),
            enabled=runtime_execution_settings.execution_dispatcher_enabled,
            result_summary_store=result_summary_store,
            message_bus=message_bus,
            on_task_lifecycle_committed=task_lifecycle_event_callback(
                event_store,
                plan_lifecycle_sync=plan_lifecycle_sync,
            ),
        )
        execution_plane_store = SqliteExecutionPlaneStore(
            layout.meta_dir / "execution_plane.sqlite"
        )
        execution_plane_runtime_handlers = build_execution_plane_runtime_handlers(
            layout=layout,
            task_bus=task_bus,
            message_bus=message_bus,
            message_stream=message_stream,
            execution_plane_store=execution_plane_store,
            computer_use_settings=runtime_computer_use_settings,
            computer_use_backend=dependencies.computer_use_backend,
        )
        execution_plane_service = EmbeddedTaskApiService(
            task_bus=task_bus,
            store=execution_plane_store,
            env_registry=build_execution_env_registry(
                computer_use_settings=runtime_computer_use_settings,
            ),
            summary_store=result_summary_store,
            default_session_id=session.id if session is not None else "execution-plane",
            runtime_handlers=execution_plane_runtime_handlers,
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
            llm=agent_llms.collaborator,
            context_builder=context_builder,
            command_service=authoring_command_service,
            workspace_context_source=workspace_context_source,
        )
        collaborator = DefaultCollaboratorApiAdapter(
            collaborator_service=collaborator_service,
            command_service=authoring_command_service,
            template_registry=InMemoryCollaboratorTemplateRegistry(),
            message_bus=message_bus,
            raw_task_store=raw_task_store,
        )
        task_commands = DefaultTaskCommandService(
            task_store=task_bus,
            draft_store=draft_store,
            message_bus=message_bus,
            published_task_interrupter=task_bus,
            published_task_retrier=task_bus,
            published_task_confirmation_resumer=task_bus,
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
            audit_config_provider=WorkspaceAuditConfigProvider(
                runtime_config_gateway=runtime_config_gateway,
            ),
            audit_log_provider=WorkspaceAuditLogProvider(),
            task_timeline_service=task_timeline,
            session_message_provider=message_stream,
            authoring_state_store=authoring_state_store,
            raw_task_store=raw_task_store,
            ask_projection=DefaultAskProjectionService(ask_store),
            snapshot_cursor_provider=_snapshot_cursor_provider(event_source),
            plan_store=plan_store,
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
            plan_store=plan_store,
            plan_publisher=plan_publisher,
            plan_lifecycle_commands=plan_lifecycle_commands,
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
            on_task_lifecycle_committed=task_lifecycle_event_callback(
                event_store,
                plan_lifecycle_sync=plan_lifecycle_sync,
            ),
        )
        task_stop_recovery = DefaultTaskStopRecoveryService(
            task_bus=task_bus,
            on_task_lifecycle_committed=task_lifecycle_event_callback(
                event_store,
                plan_lifecycle_sync=plan_lifecycle_sync,
            ),
        )
        ui_command_idempotency_store = (
            dependencies.ui_command_idempotency_store
            or SqliteUiCommandResponseIdempotencyStore(layout.workspace_ui_commands_db)
        )
        workspace_inspection_gateway = DefaultWorkspaceInspectionGateway.build(
            workspace_root=config.workspace_root,
            workspace_id=current_workspace_id,
            inspection_db_path=layout.workspace_inspection_db,
        )
        diagnostic_support_provider = DefaultDiagnosticSupportContextProvider()
        read_only_inquiry_service = (
            DefaultReadOnlyInquiryService(
                query_gateway,
                workspace_inspection_gateway=workspace_inspection_gateway,
                diagnostic_support_provider=diagnostic_support_provider,
                answer_provider=GuardedLLMReadOnlyInquiryAnswerProvider(
                    agent_llms.read_only_inquiry,
                    web_search_provider=_read_only_inquiry_web_search_provider(
                        settings_store
                    ),
                ),
            )
            if runtime_read_only_inquiry_settings.llm_enabled
            else None
        )
        contract_revision_service = ContractRevisionCommandService(
            idempotency_store=contract_revision_idempotency_store,
            guidance_store=guidance_store,
            workspace_id=config.current_workspace_id or "current",
            plan_store=plan_store,
            interaction_handler=UiGatewayContractInteractionCommandHandler(
                command_gateway,
                execution_trigger_gateway=execution_dispatcher,
            ),
            task_node_handler=UiGatewayContractTaskNodeCommandHandler(
                command_gateway,
                plan_store=plan_store,
            ),
            activity_publisher=MessageBusContractRevisionActivityPublisher(
                message_bus
            ),
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
            snapshot_recovery_gateway=CompositeSnapshotRecoveryService(
                ask_recovery,
                task_stop_recovery,
            ),
            settings_readiness_gateway=(
                dependencies.settings_readiness_gateway or settings_config_gateway
            ),
            settings_config_gateway=settings_config_gateway,
            diagnostic_export_gateway=DefaultDiagnosticExportGateway(
                workspace_root=config.workspace_root,
            ),
            workspace_inspection_gateway=workspace_inspection_gateway,
            token_usage_gateway=DefaultTokenUsageSummaryGateway(
                store=token_usage_store,
                workspace_id=config.current_workspace_id or "current",
            ),
            runtime_config_gateway=runtime_config_gateway,
            runtime_config_mutation_service=runtime_config_mutation_service,
            runtime_input_router=DefaultRuntimeInputRouter(
                query_gateway=query_gateway,
                command_gateway=command_gateway,
                execution_trigger_gateway=execution_dispatcher,
                read_only_inquiry_service=read_only_inquiry_service,
                workspace_inspection_gateway=workspace_inspection_gateway,
                diagnostic_support_provider=diagnostic_support_provider,
                activity_publisher=MessageBusRuntimeInputActivityPublisher(
                    message_bus
                ),
                contract_revision_service=contract_revision_service,
                route_planner=LLMRuntimeInputRoutePlanner(agent_llms.router),
            ),
            execution_plane_service=execution_plane_service,
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
        plan_store=plan_store,
        plan_lifecycle_sync=plan_lifecycle_sync,
        raw_task_store=raw_task_store,
        draft_store=draft_store,
        authoring_state_store=authoring_state_store,
        authoring_idempotency_store=authoring_idempotency_store,
        ui_command_idempotency_store=ui_command_idempotency_store,
        contract_revision_idempotency_store=contract_revision_idempotency_store,
        guidance_store=guidance_store,
        event_source=event_source,
        result_summary_store=result_summary_store,
        execution_plane_store=execution_plane_store,
        token_usage_store=token_usage_store,
        runtime_config_change_store=runtime_config_change_store,
        runtime_config=runtime_config,
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
    current_workspace_id = config.current_workspace_id or "current"
    entry = WorkspaceRegistryEntry(
        workspace_id=current_workspace_id,
        root_path=config.workspace_root,
        label=config.workspace_root.name or "Current Workspace",
        is_current=True,
    )

    def runtime_factory(
        registry_entry: WorkspaceRegistryEntry,
    ) -> MainPageWorkspaceRuntime:
        del registry_entry
        return runtime

    registry = WorkspaceRuntimeRegistry(
        entries=(entry,),
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
            current_workspace_id=entry.workspace_id,
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
        plan_store=runtime.plan_store,
        plan_lifecycle_sync=runtime.plan_lifecycle_sync,
        raw_task_store=runtime.raw_task_store,
        draft_store=runtime.draft_store,
        authoring_state_store=runtime.authoring_state_store,
        authoring_idempotency_store=runtime.authoring_idempotency_store,
        ui_command_idempotency_store=runtime.ui_command_idempotency_store,
        contract_revision_idempotency_store=(
            runtime.contract_revision_idempotency_store
        ),
        guidance_store=runtime.guidance_store,
        event_source=runtime.event_source,
        result_summary_store=runtime.result_summary_store,
        execution_plane_store=runtime.execution_plane_store,
        token_usage_store=runtime.token_usage_store,
        runtime_config_change_store=runtime.runtime_config_change_store,
        runtime_config=runtime.runtime_config,
        default_agent=runtime.default_agent,
        execution_dispatcher=runtime.execution_dispatcher,
        query_gateway=runtime.query_gateway,
        command_gateway=runtime.command_gateway,
        transport=runtime.transport,
        server=server,
        _close_callback=close_callback,
    )


def _runtime_config_process_values(config: MainPageSidecarConfig) -> dict[str, object]:
    values: dict[str, object] = {
        "agent_loop.default_max_steps": config.default_agent_max_steps,
        "context_manager.checkpoint_interval_steps": (
            config.context_checkpoint_interval_steps
        ),
        "context_manager.max_prior_messages": config.context_max_prior_messages,
        "context_manager.budget.max_events": config.context_budget_max_events,
        "context_manager.budget.max_tool_results": (
            config.context_budget_max_tool_results
        ),
        "context_manager.budget.max_file_snippets": (
            config.context_budget_max_file_snippets
        ),
        "context_manager.budget.max_file_snippet_chars": (
            config.context_budget_max_file_snippet_chars
        ),
        "context_manager.budget.max_rendered_chars": (
            config.context_budget_max_rendered_chars
        ),
        "execution_dispatcher.enabled": config.enable_execution_dispatcher,
        "execution_dispatcher.max_ticks_per_trigger": (
            config.execution_dispatcher_max_ticks_per_trigger
        ),
        "task_api.enabled": True,
        "task_api.require_valid_session": True,
        "computer_use.enabled": config.enable_computer_use_tool,
        "computer_use.backend": config.computer_use_backend_name,
        "computer_use.allowed_apps": config.computer_use_allowed_apps,
        "read_only_inquiry.llm_enabled": config.enable_read_only_inquiry_llm,
        "logging.level": config.logging_level,
    }
    if config.logging_profile is not None:
        values["logging.profile"] = config.logging_profile
    return values


@dataclass(frozen=True)
class _WorkspaceAgentLlms:
    execution: Any
    collaborator: Any
    read_only_inquiry: Any
    router: Any


def _workspace_agent_llms(
    config: MainPageSidecarConfig,
    dependencies: MainPageSidecarDependencies,
    *,
    settings_store: Any,
    token_usage_store: SqliteTokenUsageStore,
    task_bus: SqliteTaskBus,
) -> _WorkspaceAgentLlms:
    shared_llm = _workspace_llm_if_configured(config.workspace_root, dependencies)
    workspace_id = config.current_workspace_id or "current"
    plan_resolver = task_plan_resolver(task_bus)
    if shared_llm is not None:
        usage_llm = UsageRecordingLLM(
            shared_llm,
            workspace_id=workspace_id,
            sink=token_usage_store,
            task_plan_resolver=plan_resolver,
        )
        return _WorkspaceAgentLlms(
            execution=usage_llm,
            collaborator=usage_llm,
            read_only_inquiry=usage_llm,
            router=usage_llm,
        )

    resolver = SettingsBackedAgentLlmResolver(
        settings_store=settings_store,
        base_env=os.environ,
        workspace_id=workspace_id,
        usage_sink=token_usage_store,
        task_plan_resolver=plan_resolver,
    )

    def client(role: AgentLlmRole) -> Any:
        return resolver.client_for(role)

    return _WorkspaceAgentLlms(
        execution=client("execution_agent"),
        collaborator=client("collaborator"),
        read_only_inquiry=client("read_only_inquiry"),
        router=client("runtime_input_router"),
    )


def _workspace_llm_if_configured(
    workspace_root: Path,
    dependencies: MainPageSidecarDependencies,
) -> CollaboratorLLM | None:
    if dependencies.llm_factory is not None:
        return dependencies.llm_factory(workspace_root)
    return dependencies.llm


def _read_only_inquiry_web_search_provider(
    settings_store: Any,
) -> WebSearchProvider | None:
    settings = effective_web_search_settings(
        config=settings_store.read_config(),
        base_env=os.environ,
        store=settings_store,
    )
    if settings.status != "ready" or settings.provider != "tavily":
        return None
    return TavilyWebSearchProvider(api_key=settings.api_key or "")


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


def _snapshot_cursor_provider(
    event_source: UiEventSource,
) -> UiEventCursorProvider | None:
    if isinstance(event_source, UiEventCursorProvider):
        return event_source
    return None


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
