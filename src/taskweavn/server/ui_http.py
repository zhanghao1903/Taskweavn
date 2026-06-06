"""Framework-neutral HTTP transport for Plato UI contract gateways."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from taskweavn.observability.main_page_trace import main_page_trace
from taskweavn.server.client_logs import ClientErrorLogSink
from taskweavn.server.diagnostics_export import (
    DiagnosticExportFailure,
    DiagnosticExportSessionNotFound,
)
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_command_idempotency import UiCommandResponseIdempotencyStore
from taskweavn.server.ui_contract import (
    AnswerAskPayload,
    AnswerAuthoringAskBatchPayload,
    ApiError,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    CancelAskPayload,
    CommandRequest,
    DeferAskPayload,
    DispatchExecutionPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
    UiCommandGateway,
    UiQueryGateway,
    UpdateTaskNodePayload,
)
from taskweavn.server.ui_events import ResyncOnlyEventSource, UiEventSource
from taskweavn.server.ui_http_commands import (
    _answer_ask_with_resume_dispatch,
    _command_response,
    _dispatch_execution,
    _publish_task_tree_with_optional_dispatch,
    _retry_task_with_optional_dispatch,
)
from taskweavn.server.ui_http_query_params import (
    _bool_query,
    _int_query,
    _optional_bool_query,
    _parse_command_request,
    _request_query,
    _string_body_value,
)
from taskweavn.server.ui_http_responses import (
    _contract_response,
    _error_response,
    _json_response,
    _normalize_headers,
    _request_id_hint,
)
from taskweavn.server.ui_http_routes import _match_route
from taskweavn.server.ui_http_settings import (
    SettingsConfigGateway,
    SettingsReadinessGateway,
    _settings_config_response,
    _settings_readiness_recheck_response,
    _settings_readiness_response,
)
from taskweavn.server.ui_http_sse import _sse_response
from taskweavn.task import ExecutionTriggerGateway


class SessionLifecycleGateway(Protocol):
    """Small session lifecycle boundary used by the local Main Page sidecar."""

    def list_sessions(self) -> dict[str, Any]: ...

    def create_session(self, name: str) -> dict[str, Any]: ...

    def rename_session(self, session_id: str, name: str) -> dict[str, Any]: ...

    def delete_session(self, session_id: str) -> dict[str, Any]: ...


class SnapshotRecoveryGateway(Protocol):
    """Best-effort recovery hook that runs before snapshot projection."""

    def recover_session(self, session_id: str) -> object: ...


class DiagnosticExportGateway(Protocol):
    """Local diagnostic bundle export source."""

    def export_session(self, session_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SidecarAuth:
    """Local sidecar bearer-token guard.

    EventSource cannot send custom headers, so SSE routes may use the same token
    as a query parameter while the sidecar is bound to loopback only.
    """

    token: str
    query_token_name: str = "token"

    def authorize(self, request: HttpApiRequest, *, allow_query_token: bool = False) -> bool:
        headers = _normalize_headers(request.headers)
        if headers.get("authorization") == f"Bearer {self.token}":
            return True
        query_token = _request_query(request).get(self.query_token_name)
        return allow_query_token and query_token == self.token


class PlatoUiHttpTransport:
    """HTTP/RPC-style transport wrapper around Plato UI gateways."""

    def __init__(
        self,
        *,
        query_gateway: UiQueryGateway,
        command_gateway: UiCommandGateway,
        event_source: UiEventSource | None = None,
        auth: SidecarAuth | None = None,
        client_error_log_sink: ClientErrorLogSink | None = None,
        session_lifecycle_gateway: SessionLifecycleGateway | None = None,
        command_idempotency_store: UiCommandResponseIdempotencyStore | None = None,
        execution_trigger_gateway: ExecutionTriggerGateway | None = None,
        snapshot_recovery_gateway: SnapshotRecoveryGateway | None = None,
        settings_readiness_gateway: SettingsReadinessGateway | None = None,
        settings_config_gateway: SettingsConfigGateway | None = None,
        diagnostic_export_gateway: DiagnosticExportGateway | None = None,
    ) -> None:
        self._query_gateway = query_gateway
        self._command_gateway = command_gateway
        self._event_source = event_source or ResyncOnlyEventSource()
        self._auth = auth
        self._client_error_log_sink = client_error_log_sink
        self._session_lifecycle_gateway = session_lifecycle_gateway
        self._command_idempotency_store = command_idempotency_store
        self._execution_trigger_gateway = execution_trigger_gateway
        self._snapshot_recovery_gateway = snapshot_recovery_gateway
        self._settings_readiness_gateway = settings_readiness_gateway
        self._settings_config_gateway = settings_config_gateway
        self._diagnostic_export_gateway = diagnostic_export_gateway

    def handle(self, request: HttpApiRequest) -> HttpApiResponse:
        route = _match_route(request.path)
        if route is None:
            return _error_response(
                404,
                ApiError(code="not_found", message="unknown Plato UI route"),
                request_id=_request_id_hint(request),
            )

        route_name = route.name
        allow_query_token = route_name == "events"
        if self._auth is not None and not self._auth.authorize(
            request,
            allow_query_token=allow_query_token,
        ):
            return _error_response(
                401,
                ApiError(code="permission_denied", message="invalid sidecar token"),
                request_id=_request_id_hint(request),
            )

        if route.method != "*" and request.method.upper() != route.method:
            return _error_response(
                405,
                ApiError(
                    code="bad_request",
                    message=f"{route_name} requires {route.method}",
                    details={"allowed_method": route.method},
                ),
                request_id=_request_id_hint(request),
                headers={"allow": route.method},
            )

        if route_name != "events":
            main_page_trace(
                "http.route.request",
                method=request.method.upper(),
                path=_path_without_query(request.path),
                query=_safe_query(request.query),
                route=route_name,
                session_id=route.session_id or None,
                task_node_id=route.task_node_id or None,
            )

        try:
            if route_name == "root":
                return _json_response(
                    {
                        "ok": True,
                        "data": {
                            "name": "Plato Sidecar",
                            "version": "0.1.0",
                            "api_base_path": "/api/v1",
                            "health_url": "/api/v1/health",
                            "settings_readiness_url": (
                                "/api/v1/settings/readiness"
                            ),
                            "settings_config_url": "/api/v1/settings/config",
                            "settings_readiness_recheck_url": (
                                "/api/v1/settings/readiness/recheck"
                            ),
                            "snapshot_url_template": (
                                "/api/v1/sessions/{sessionId}/snapshot"
                            ),
                            "events_url_template": (
                                "/api/v1/sessions/{sessionId}/events"
                            ),
                            "dispatch_url_template": (
                                "/api/v1/sessions/{sessionId}/execution/dispatch"
                            ),
                            "diagnostics_export_url_template": (
                                "/api/v1/sessions/{sessionId}/diagnostics/export"
                            ),
                        },
                        "error": None,
                    }
                )
            if route_name == "health":
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
            if route_name == "settings_readiness":
                return _settings_readiness_response(
                    request,
                    self._settings_readiness_gateway,
                )
            if route_name == "settings_readiness_recheck":
                return _settings_readiness_recheck_response(
                    request,
                    self._settings_config_gateway or self._settings_readiness_gateway,
                )
            if route_name == "settings_config":
                return _settings_config_response(
                    request,
                    self._settings_config_gateway,
                )
            if route_name == "diagnostics_export":
                if self._diagnostic_export_gateway is None:
                    return _error_response(
                        503,
                        ApiError(
                            code="internal_error",
                            message="diagnostic export gateway is not configured",
                            details={"route": route_name},
                        ),
                        request_id=_request_id_hint(request),
                    )
                return _json_response(
                    {
                        "ok": True,
                        "data": self._diagnostic_export_gateway.export_session(
                            route.session_id
                        ),
                        "error": None,
                    }
                )
            if route_name == "sessions":
                lifecycle = self._require_session_lifecycle(request)
                if isinstance(lifecycle, HttpApiResponse):
                    return lifecycle
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
            if route_name == "snapshot":
                self._recover_before_snapshot(route.session_id)
                snapshot_response = self._query_gateway.get_session_snapshot(
                    route.session_id
                )
                main_page_trace(
                    "http.snapshot.response",
                    session_id=route.session_id,
                    **_snapshot_response_summary(snapshot_response),
                )
                return _contract_response(snapshot_response)
            if route_name == "audit_snapshot":
                query = _request_query(request)
                return _contract_response(
                    self._query_gateway.get_audit_snapshot(
                        route.session_id,
                        task_node_id=route.task_node_id or None,
                        entry=query.get("entry"),
                        filter_kind=query.get("filter", "all"),
                        record_id=query.get("recordId"),
                        include_detail=_optional_bool_query(query, "includeDetail"),
                        limit=_int_query(query, "limit", default=50),
                        cursor=query.get("cursor"),
                    )
                )
            if route_name == "asks":
                query = _request_query(request)
                return _contract_response(
                    self._query_gateway.list_asks(
                        route.session_id,
                        status=query.get("status"),
                        task_node_id=query.get("taskNodeId"),
                    )
                )
            if route_name == "ask_detail":
                return _contract_response(
                    self._query_gateway.get_ask(route.session_id, route.ask_id)
                )
            if route_name == "audit_records":
                query = _request_query(request)
                return _contract_response(
                    self._query_gateway.list_audit_records(
                        route.session_id,
                        task_node_id=route.task_node_id or None,
                        filter_kind=query.get("filter", "all"),
                        kind=query.get("kind"),
                        from_time=query.get("from"),
                        to_time=query.get("to"),
                        limit=_int_query(query, "limit", default=50),
                        cursor=query.get("cursor"),
                        include_hidden_reasons=_bool_query(
                            query,
                            "includeHiddenReasons",
                            default=False,
                        ),
                    )
                )
            if route_name == "audit_record_detail":
                query = _request_query(request)
                return _contract_response(
                    self._query_gateway.get_audit_record_detail(
                        route.session_id,
                        route.record_id,
                        include_evidence=_bool_query(
                            query,
                            "includeEvidence",
                            default=False,
                        ),
                        include_sanitized_payload=_bool_query(
                            query,
                            "includeSanitizedPayload",
                            default=False,
                        ),
                    )
                )
            if route_name == "audit_evidence_detail":
                query = _request_query(request)
                return _contract_response(
                    self._query_gateway.get_evidence_detail(
                        route.session_id,
                        route.evidence_id,
                        include_sanitized_payload=_bool_query(
                            query,
                            "includeSanitizedPayload",
                            default=False,
                        ),
                    )
                )
            if route_name == "rename_session":
                lifecycle = self._require_session_lifecycle(request)
                if isinstance(lifecycle, HttpApiResponse):
                    return lifecycle
                name = _string_body_value(request, "name")
                if isinstance(name, HttpApiResponse):
                    return name
                return _json_response(
                    {
                        "ok": True,
                        "data": lifecycle.rename_session(route.session_id, name),
                        "error": None,
                    }
                )
            if route_name == "delete_session":
                lifecycle = self._require_session_lifecycle(request)
                if isinstance(lifecycle, HttpApiResponse):
                    return lifecycle
                return _json_response(
                    {
                        "ok": True,
                        "data": lifecycle.delete_session(route.session_id),
                        "error": None,
                    }
                )
            if route_name == "append_session_input":
                append_session_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[AppendSessionInputPayload],
                )
                if isinstance(append_session_request, HttpApiResponse):
                    return append_session_request
                return _command_response(
                    route,
                    append_session_request,
                    lambda: self._command_gateway.append_session_input(
                        append_session_request
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "generate_task_tree":
                generate_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[GenerateTaskTreePayload],
                )
                if isinstance(generate_request, HttpApiResponse):
                    return generate_request
                return _command_response(
                    route,
                    generate_request,
                    lambda: self._command_gateway.generate_task_tree(generate_request),
                    self._command_idempotency_store,
                )
            if route_name == "answer_authoring_ask_batch":
                answer_authoring_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[AnswerAuthoringAskBatchPayload],
                )
                if isinstance(answer_authoring_request, HttpApiResponse):
                    return answer_authoring_request
                return _command_response(
                    route,
                    answer_authoring_request,
                    lambda: self._command_gateway.answer_authoring_ask_batch(
                        route.raw_task_id,
                        answer_authoring_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "update_task_node":
                update_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[UpdateTaskNodePayload],
                )
                if isinstance(update_request, HttpApiResponse):
                    return update_request
                return _command_response(
                    route,
                    update_request,
                    lambda: self._command_gateway.update_task_node(
                        route.task_node_id,
                        update_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "append_task_input":
                append_task_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[AppendTaskInputPayload],
                )
                if isinstance(append_task_request, HttpApiResponse):
                    return append_task_request
                return _command_response(
                    route,
                    append_task_request,
                    lambda: self._command_gateway.append_task_input(
                        route.task_node_id,
                        append_task_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "publish_task_tree":
                publish_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[PublishTaskTreePayload],
                )
                if isinstance(publish_request, HttpApiResponse):
                    return publish_request
                return _command_response(
                    route,
                    publish_request,
                    lambda: _publish_task_tree_with_optional_dispatch(
                        self._command_gateway,
                        self._execution_trigger_gateway,
                        publish_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "retry_task":
                retry_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[RetryTaskPayload],
                )
                if isinstance(retry_request, HttpApiResponse):
                    return retry_request
                return _command_response(
                    route,
                    retry_request,
                    lambda: _retry_task_with_optional_dispatch(
                        self._command_gateway,
                        self._execution_trigger_gateway,
                        route.task_node_id,
                        retry_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "stop_task":
                stop_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[StopTaskPayload],
                )
                if isinstance(stop_request, HttpApiResponse):
                    return stop_request
                return _command_response(
                    route,
                    stop_request,
                    lambda: self._command_gateway.stop_task(
                        route.task_node_id,
                        stop_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "dispatch_execution":
                dispatch_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[DispatchExecutionPayload],
                )
                if isinstance(dispatch_request, HttpApiResponse):
                    return dispatch_request
                return _command_response(
                    route,
                    dispatch_request,
                    lambda: _dispatch_execution(
                        self._execution_trigger_gateway,
                        dispatch_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "resolve_confirmation":
                resolve_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[ResolveConfirmationPayload],
                )
                if isinstance(resolve_request, HttpApiResponse):
                    return resolve_request
                return _command_response(
                    route,
                    resolve_request,
                    lambda: self._command_gateway.resolve_confirmation(
                        route.confirmation_id,
                        resolve_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "answer_ask":
                answer_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[AnswerAskPayload],
                )
                if isinstance(answer_request, HttpApiResponse):
                    return answer_request
                return _command_response(
                    route,
                    answer_request,
                    lambda: _answer_ask_with_resume_dispatch(
                        self._command_gateway,
                        self._execution_trigger_gateway,
                        route.ask_id,
                        answer_request,
                    ),
                    self._command_idempotency_store,
                )
            if route_name == "defer_ask":
                defer_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[DeferAskPayload],
                )
                if isinstance(defer_request, HttpApiResponse):
                    return defer_request
                return _command_response(
                    route,
                    defer_request,
                    lambda: self._command_gateway.defer_ask(route.ask_id, defer_request),
                    self._command_idempotency_store,
                )
            if route_name == "cancel_ask":
                cancel_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[CancelAskPayload],
                )
                if isinstance(cancel_request, HttpApiResponse):
                    return cancel_request
                return _command_response(
                    route,
                    cancel_request,
                    lambda: self._command_gateway.cancel_ask(route.ask_id, cancel_request),
                    self._command_idempotency_store,
                )
            if route_name == "client_error_log":
                if request.body is None:
                    return _error_response(
                        400,
                        ApiError(
                            code="bad_request",
                            message="request body must be a JSON object",
                        ),
                        request_id=_request_id_hint(request),
                    )
                if self._client_error_log_sink is not None:
                    self._client_error_log_sink.write_error(route.session_id, request.body)
                return _json_response(
                    {
                        "ok": True,
                        "data": {"stored": self._client_error_log_sink is not None},
                        "error": None,
                    }
                )
            if route_name == "events":
                return _sse_response(self._event_source, request, route)
        except DiagnosticExportSessionNotFound:
            return _error_response(
                404,
                ApiError(
                    code="not_found",
                    message="session not found",
                    details={"route": route_name},
                ),
                request_id=_request_id_hint(request),
            )
        except DiagnosticExportFailure:
            return _error_response(
                500,
                ApiError(
                    code="internal_error",
                    message="diagnostic bundle export failed",
                    retryable=True,
                    details={"route": route_name},
                ),
                request_id=_request_id_hint(request),
            )
        except ValueError as exc:
            return _error_response(
                400,
                ApiError(
                    code="bad_request",
                    message=str(exc),
                    details={"route": route_name},
                ),
                request_id=_request_id_hint(request),
            )
        except Exception as exc:
            return _error_response(
                500,
                ApiError(
                    code="internal_error",
                    message="Plato UI transport failed",
                    retryable=True,
                    details={"error_type": type(exc).__name__},
                ),
                request_id=_request_id_hint(request),
            )

        return _error_response(
            500,
            ApiError(
                code="internal_error",
                message="Plato UI route dispatch fell through",
                retryable=True,
                details={"route": route_name},
            ),
            request_id=_request_id_hint(request),
        )

    def _recover_before_snapshot(self, session_id: str) -> None:
        if self._snapshot_recovery_gateway is None:
            return
        try:
            self._snapshot_recovery_gateway.recover_session(session_id)
        except Exception as exc:  # noqa: BLE001 - recovery must not break reads.
            main_page_trace(
                "http.snapshot.recovery_failed",
                error_type=type(exc).__name__,
                session_id=session_id,
            )

    def _require_session_lifecycle(
        self,
        request: HttpApiRequest,
    ) -> SessionLifecycleGateway | HttpApiResponse:
        if self._session_lifecycle_gateway is not None:
            return self._session_lifecycle_gateway
        return _error_response(
            501,
            ApiError(
                code="internal_error",
                message="session lifecycle gateway is not configured",
            ),
            request_id=_request_id_hint(request),
        )


def _safe_query(query: dict[str, str]) -> dict[str, str]:
    return {
        key: "<redacted>" if "token" in key.lower() or key == "cursor" else value
        for key, value in query.items()
    }


def _path_without_query(path: str) -> str:
    return path.split("?", 1)[0]


def _snapshot_response_summary(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None)
    error = getattr(response, "error", None)
    summary: dict[str, Any] = {
        "ok": getattr(response, "ok", None),
        "request_id": getattr(response, "request_id", None),
    }
    if error is not None:
        summary["error_code"] = getattr(error, "code", None)
        summary["error_message"] = getattr(error, "message", None)
        return summary
    if data is None:
        return summary

    session = getattr(data, "session", None)
    task_tree = getattr(data, "task_tree", None)
    nodes = tuple(getattr(task_tree, "nodes", ()) or ())
    summary.update(
        {
            "session_status": getattr(session, "status", None),
            "task_node_count": len(nodes),
            "task_nodes": tuple(_task_node_summary(node) for node in nodes),
            "task_tree_status": getattr(task_tree, "status", None),
        }
    )
    return summary


def _task_node_summary(node: Any) -> dict[str, Any]:
    return {
        "error_ref": getattr(node, "error_ref", None),
        "execution": getattr(node, "execution", None),
        "id": getattr(node, "id", None),
        "interruption_requested": getattr(node, "interruption_requested", None),
        "status": getattr(node, "status", None),
        "title": _short_text(getattr(node, "title", "")),
    }


def _short_text(value: Any, *, limit: int = 80) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}..."


__all__ = [
    "PlatoUiHttpTransport",
    "SidecarAuth",
]
