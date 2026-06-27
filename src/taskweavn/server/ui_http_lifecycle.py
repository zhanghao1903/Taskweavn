"""Root, health, and session lifecycle HTTP helpers."""

from __future__ import annotations

from typing import Any, Protocol

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError
from taskweavn.server.ui_http_query_params import _string_body_value
from taskweavn.server.ui_http_responses import (
    _error_response,
    _json_response,
    _request_id_hint,
)


class SessionLifecycleGateway(Protocol):
    """Small session lifecycle boundary used by the local Main Page sidecar."""

    def list_sessions(self) -> dict[str, Any]: ...

    def create_session(self, name: str) -> dict[str, Any]: ...

    def rename_session(self, session_id: str, name: str) -> dict[str, Any]: ...

    def delete_session(self, session_id: str) -> dict[str, Any]: ...


def _root_response() -> HttpApiResponse:
    return _json_response(
        {
            "ok": True,
            "data": {
                "name": "Plato Sidecar",
                "version": "0.1.0",
                "api_base_path": "/api/v1",
                "health_url": "/api/v1/health",
                "settings_readiness_url": "/api/v1/settings/readiness",
                "settings_config_url": "/api/v1/settings/config",
                "runtime_config_schema_url": "/api/v1/runtime/config/schema",
                "runtime_config_effective_url": "/api/v1/runtime/config/effective",
                "runtime_config_explain_url_template": (
                    "/api/v1/runtime/config/explain?key={key}"
                ),
                "runtime_config_changes_url": "/api/v1/runtime/config/changes",
                "runtime_config_snapshot_url_template": (
                    "/api/v1/runtime/config/snapshots/{configHash}"
                ),
                "settings_readiness_recheck_url": (
                    "/api/v1/settings/readiness/recheck"
                ),
                "snapshot_url_template": "/api/v1/sessions/{sessionId}/snapshot",
                "activity_url_template": "/api/v1/sessions/{sessionId}/activity",
                "runtime_input_route_url_template": (
                    "/api/v1/sessions/{sessionId}/runtime-input/route"
                ),
                "events_url_template": "/api/v1/sessions/{sessionId}/events",
                "dispatch_url_template": (
                    "/api/v1/sessions/{sessionId}/execution/dispatch"
                ),
                "diagnostics_export_url_template": (
                    "/api/v1/sessions/{sessionId}/diagnostics/export"
                ),
                "token_usage_summary_url_template": (
                    "/api/v1/usage/token-summary?dimension={dimension}"
                ),
                "task_api_url": "/api/v1/tasks",
                "task_api_url_template": "/api/v1/tasks/{executionId}",
            },
            "error": None,
        }
    )


def _health_response() -> HttpApiResponse:
    return _json_response(
        {
            "ok": True,
            "data": {
                "name": "Plato Sidecar",
                "version": "0.1.0",
            },
            "error": None,
        }
    )


def _session_lifecycle_response(
    request: HttpApiRequest,
    *,
    gateway: SessionLifecycleGateway | None,
    route_name: str,
    session_id: str | None = None,
) -> HttpApiResponse:
    lifecycle = _require_session_lifecycle(request, gateway)
    if isinstance(lifecycle, HttpApiResponse):
        return lifecycle

    if route_name == "sessions":
        return _sessions_response(request, lifecycle)
    if route_name == "rename_session" and session_id is not None:
        return _rename_session_response(request, lifecycle, session_id)
    if route_name == "delete_session" and session_id is not None:
        return _delete_session_response(lifecycle, session_id)

    return _error_response(
        500,
        ApiError(
            code="internal_error",
            message="session lifecycle route dispatch fell through",
            retryable=True,
            details={"route": route_name},
        ),
        request_id=_request_id_hint(request),
    )


def _sessions_response(
    request: HttpApiRequest,
    lifecycle: SessionLifecycleGateway,
) -> HttpApiResponse:
    if request.method.upper() == "GET":
        return _json_response(
            {
                "ok": True,
                "data": lifecycle.list_sessions(),
                "error": None,
            }
        )
    if request.method.upper() != "POST":
        return _error_response(
            405,
            ApiError(
                code="bad_request",
                message="sessions requires GET or POST",
                details={"allowed_methods": ["GET", "POST"]},
            ),
            request_id=_request_id_hint(request),
            headers={"allow": "GET, POST"},
        )
    name = _string_body_value(request, "name", default="New session")
    if isinstance(name, HttpApiResponse):
        return name
    return _json_response(
        {
            "ok": True,
            "data": lifecycle.create_session(name),
            "error": None,
        }
    )


def _rename_session_response(
    request: HttpApiRequest,
    lifecycle: SessionLifecycleGateway,
    session_id: str,
) -> HttpApiResponse:
    name = _string_body_value(request, "name")
    if isinstance(name, HttpApiResponse):
        return name
    return _json_response(
        {
            "ok": True,
            "data": lifecycle.rename_session(session_id, name),
            "error": None,
        }
    )


def _delete_session_response(
    lifecycle: SessionLifecycleGateway,
    session_id: str,
) -> HttpApiResponse:
    return _json_response(
        {
            "ok": True,
            "data": lifecycle.delete_session(session_id),
            "error": None,
        }
    )


def _require_session_lifecycle(
    request: HttpApiRequest,
    gateway: SessionLifecycleGateway | None,
) -> SessionLifecycleGateway | HttpApiResponse:
    if gateway is not None:
        return gateway
    return _error_response(
        501,
        ApiError(
            code="internal_error",
            message="session lifecycle gateway is not configured",
        ),
        request_id=_request_id_hint(request),
    )
