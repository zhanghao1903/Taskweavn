"""Server transport adapters for TaskWeavn."""

from importlib import import_module
from typing import Any

from taskweavn.server.api_publish import (
    ApiPublishHttpTransport,
)
from taskweavn.server.client_logs import ClientErrorLogSink, FileClientErrorLogSink
from taskweavn.server.settings_config import (
    SETTINGS_CONFIG_SCHEMA_VERSION,
    SETTINGS_CONFIG_UPDATE_SCHEMA_VERSION,
    DefaultSettingsConfigGateway,
    FileSettingsConfigStore,
)
from taskweavn.server.transport import (
    ApiErrorBody,
    HttpApiRequest,
    HttpApiResponse,
)
from taskweavn.server.ui_command_idempotency import (
    InMemoryUiCommandResponseIdempotencyStore,
    SqliteUiCommandResponseIdempotencyStore,
    UiCommandResponseIdempotencyRecord,
    UiCommandResponseIdempotencyStore,
    UiCommandResponseIdempotencyStoreError,
)
from taskweavn.server.ui_events import (
    ResyncOnlyEventSource,
    SqliteUiEventSource,
    StaticUiEventSource,
    UiEventCursorProvider,
    UiEventSource,
    UiEventSourceError,
    UiEventStore,
    sse_frame,
    sse_stream,
)

__all__ = [
    "ApiErrorBody",
    "ApiPublishHttpTransport",
    "HttpApiRequest",
    "HttpApiResponse",
    "InMemoryUiCommandResponseIdempotencyStore",
    "LocalSidecarConfig",
    "LocalSidecarServer",
    "DEFAULT_PLATO_SIDECAR_PORT",
    "ClientErrorLogSink",
    "DIAGNOSTIC_EXPORT_SCHEMA_VERSION",
    "SETTINGS_CONFIG_SCHEMA_VERSION",
    "SETTINGS_CONFIG_UPDATE_SCHEMA_VERSION",
    "DefaultDiagnosticExportGateway",
    "DefaultSettingsConfigGateway",
    "DiagnosticExportFailure",
    "DiagnosticExportSessionNotFound",
    "FileSettingsConfigStore",
    "FileClientErrorLogSink",
    "MainPageSidecarApp",
    "MainPageSidecarConfig",
    "MainPageSidecarDependencies",
    "MainPageWorkspaceRuntime",
    "MainPageSessionLifecycleGateway",
    "MainPageTaskRefResolver",
    "PlatoUiHttpTransport",
    "ResyncOnlyEventSource",
    "SidecarAuth",
    "SqliteUiEventSource",
    "SqliteUiCommandResponseIdempotencyStore",
    "StaticUiEventSource",
    "UiEventCursorProvider",
    "UiEventSource",
    "UiEventSourceError",
    "UiEventStore",
    "UiCommandResponseIdempotencyRecord",
    "UiCommandResponseIdempotencyStore",
    "UiCommandResponseIdempotencyStoreError",
    "WorkspaceRegistryEntry",
    "build_agent_loop_resident_default_agent",
    "build_main_page_sidecar_app",
    "build_main_page_workspace_runtime",
    "sse_frame",
    "sse_stream",
]

_LAZY_EXPORTS = {
    "DEFAULT_PLATO_SIDECAR_PORT": "taskweavn.server.main_page",
    "DIAGNOSTIC_EXPORT_SCHEMA_VERSION": "taskweavn.server.diagnostics_export",
    "DefaultDiagnosticExportGateway": "taskweavn.server.diagnostics_export",
    "DiagnosticExportFailure": "taskweavn.server.diagnostics_export",
    "DiagnosticExportSessionNotFound": "taskweavn.server.diagnostics_export",
    "LocalSidecarConfig": "taskweavn.server.sidecar",
    "LocalSidecarServer": "taskweavn.server.sidecar",
    "MainPageSessionLifecycleGateway": "taskweavn.server.main_page",
    "MainPageSidecarApp": "taskweavn.server.main_page",
    "MainPageSidecarConfig": "taskweavn.server.main_page",
    "MainPageSidecarDependencies": "taskweavn.server.main_page",
    "MainPageWorkspaceRuntime": "taskweavn.server.main_page",
    "MainPageTaskRefResolver": "taskweavn.server.main_page",
    "PlatoUiHttpTransport": "taskweavn.server.ui_http",
    "SidecarAuth": "taskweavn.server.ui_http",
    "WorkspaceRegistryEntry": "taskweavn.server.main_page",
    "build_agent_loop_resident_default_agent": "taskweavn.server.main_page",
    "build_main_page_sidecar_app": "taskweavn.server.main_page",
    "build_main_page_workspace_runtime": "taskweavn.server.main_page",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
