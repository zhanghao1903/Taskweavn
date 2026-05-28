"""Server transport adapters for TaskWeavn."""

from taskweavn.server.api_publish import (
    ApiPublishHttpTransport,
)
from taskweavn.server.client_logs import ClientErrorLogSink, FileClientErrorLogSink
from taskweavn.server.main_page import (
    DEFAULT_PLATO_SIDECAR_PORT,
    MainPageSessionLifecycleGateway,
    MainPageSidecarApp,
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    MainPageTaskRefResolver,
    build_main_page_sidecar_app,
)
from taskweavn.server.sidecar import LocalSidecarConfig, LocalSidecarServer
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
    StaticUiEventSource,
    UiEventSource,
    sse_frame,
    sse_stream,
)
from taskweavn.server.ui_http import PlatoUiHttpTransport, SidecarAuth

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
    "FileClientErrorLogSink",
    "MainPageSidecarApp",
    "MainPageSidecarConfig",
    "MainPageSidecarDependencies",
    "MainPageSessionLifecycleGateway",
    "MainPageTaskRefResolver",
    "PlatoUiHttpTransport",
    "ResyncOnlyEventSource",
    "SidecarAuth",
    "SqliteUiCommandResponseIdempotencyStore",
    "StaticUiEventSource",
    "UiEventSource",
    "UiCommandResponseIdempotencyRecord",
    "UiCommandResponseIdempotencyStore",
    "UiCommandResponseIdempotencyStoreError",
    "build_main_page_sidecar_app",
    "sse_frame",
    "sse_stream",
]
