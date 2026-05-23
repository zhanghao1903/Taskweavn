"""Framework-neutral HTTP transport for Plato UI contract gateways."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qsl, unquote, urlsplit

from pydantic import ValidationError

from taskweavn.server.client_logs import ClientErrorLogSink
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import (
    ApiError,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    CommandRequest,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    QueryResponse,
    ResolveConfirmationPayload,
    UiCommandGateway,
    UiQueryGateway,
    UpdateTaskNodePayload,
)
from taskweavn.server.ui_events import ResyncOnlyEventSource, UiEventSource, sse_stream

_JSON_HEADERS = {"content-type": "application/json"}
_SSE_HEADERS = {
    "cache-control": "no-cache",
    "connection": "keep-alive",
    "content-type": "text/event-stream",
}


class SessionLifecycleGateway(Protocol):
    """Small session lifecycle boundary used by the local Main Page sidecar."""

    def list_sessions(self) -> dict[str, Any]: ...

    def create_session(self, name: str) -> dict[str, Any]: ...

    def rename_session(self, session_id: str, name: str) -> dict[str, Any]: ...

    def delete_session(self, session_id: str) -> dict[str, Any]: ...


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
    ) -> None:
        self._query_gateway = query_gateway
        self._command_gateway = command_gateway
        self._event_source = event_source or ResyncOnlyEventSource()
        self._auth = auth
        self._client_error_log_sink = client_error_log_sink
        self._session_lifecycle_gateway = session_lifecycle_gateway

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
                            "snapshot_url_template": (
                                "/api/v1/sessions/{sessionId}/snapshot"
                            ),
                            "events_url_template": (
                                "/api/v1/sessions/{sessionId}/events"
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
                return _contract_response(
                    self._query_gateway.get_session_snapshot(route.session_id)
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
                return _contract_response(
                    self._command_gateway.append_session_input(append_session_request)
                )
            if route_name == "generate_task_tree":
                generate_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[GenerateTaskTreePayload],
                )
                if isinstance(generate_request, HttpApiResponse):
                    return generate_request
                return _contract_response(
                    self._command_gateway.generate_task_tree(generate_request)
                )
            if route_name == "update_task_node":
                update_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[UpdateTaskNodePayload],
                )
                if isinstance(update_request, HttpApiResponse):
                    return update_request
                return _contract_response(
                    self._command_gateway.update_task_node(route.task_node_id, update_request)
                )
            if route_name == "append_task_input":
                append_task_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[AppendTaskInputPayload],
                )
                if isinstance(append_task_request, HttpApiResponse):
                    return append_task_request
                return _contract_response(
                    self._command_gateway.append_task_input(
                        route.task_node_id,
                        append_task_request,
                    )
                )
            if route_name == "publish_task_tree":
                publish_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[PublishTaskTreePayload],
                )
                if isinstance(publish_request, HttpApiResponse):
                    return publish_request
                return _contract_response(
                    self._command_gateway.publish_task_tree(publish_request)
                )
            if route_name == "resolve_confirmation":
                resolve_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[ResolveConfirmationPayload],
                )
                if isinstance(resolve_request, HttpApiResponse):
                    return resolve_request
                return _contract_response(
                    self._command_gateway.resolve_confirmation(
                        route.confirmation_id,
                        resolve_request,
                    )
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
                events = self._event_source.subscribe(
                    route.session_id,
                    cursor=_request_query(request).get("cursor"),
                )
                return HttpApiResponse(
                    status_code=200,
                    headers=dict(_SSE_HEADERS),
                    body=sse_stream(events),
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


@dataclass(frozen=True)
class _Route:
    name: str
    method: str
    session_id: str = ""
    task_node_id: str = ""
    confirmation_id: str = ""


def _match_route(path: str) -> _Route | None:
    parts = _path_parts(path)
    if parts == ():
        return _Route(name="root", method="GET")
    if parts == ("api", "v1", "health"):
        return _Route(name="health", method="GET")
    if parts == ("api", "v1", "sessions"):
        return _Route(name="sessions", method="*")
    if len(parts) < 4 or parts[:3] != ("api", "v1", "sessions"):
        return None
    session_id = parts[3]
    suffix = parts[4:]
    if suffix == ("snapshot",):
        return _Route(name="snapshot", method="GET", session_id=session_id)
    if suffix == ():
        return _Route(name="rename_session", method="PATCH", session_id=session_id)
    if suffix == ("delete",):
        return _Route(name="delete_session", method="POST", session_id=session_id)
    if suffix == ("input",):
        return _Route(name="append_session_input", method="POST", session_id=session_id)
    if suffix == ("task-tree", "generate"):
        return _Route(name="generate_task_tree", method="POST", session_id=session_id)
    if suffix == ("task-tree", "publish"):
        return _Route(name="publish_task_tree", method="POST", session_id=session_id)
    if suffix == ("events",):
        return _Route(name="events", method="GET", session_id=session_id)
    if suffix == ("client-logs", "errors"):
        return _Route(name="client_error_log", method="POST", session_id=session_id)
    if len(suffix) == 2 and suffix[0] == "tasks":
        return _Route(
            name="update_task_node",
            method="PATCH",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "tasks" and suffix[2] == "input":
        return _Route(
            name="append_task_input",
            method="POST",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "confirmations" and suffix[2] == "respond":
        return _Route(
            name="resolve_confirmation",
            method="POST",
            session_id=session_id,
            confirmation_id=suffix[1],
        )
    return None


def _path_parts(path: str) -> tuple[str, ...]:
    split = urlsplit(path)
    raw_path = split.path or path
    return tuple(unquote(part) for part in raw_path.strip("/").split("/") if part)


def _request_query(request: HttpApiRequest) -> dict[str, str]:
    split = urlsplit(request.path)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update(request.query)
    return query


def _parse_command_request[PayloadT](
    request: HttpApiRequest,
    path_session_id: str,
    request_type: type[CommandRequest[PayloadT]],
) -> CommandRequest[PayloadT] | HttpApiResponse:
    if request.body is None:
        return _error_response(
            400,
            ApiError(code="bad_request", message="request body must be a JSON object"),
            request_id=_request_id_hint(request),
        )
    try:
        parsed = request_type.model_validate(request.body)
    except ValidationError as exc:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="request body does not match command contract",
                details={"errors": exc.errors()},
            ),
            request_id=_request_id_hint(request),
        )
    if parsed.session_id != path_session_id:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="body sessionId must match path sessionId",
                details={
                    "body_session_id": parsed.session_id,
                    "path_session_id": path_session_id,
                },
            ),
            request_id=parsed.command_id,
        )
    return parsed


def _string_body_value(
    request: HttpApiRequest,
    key: str,
    *,
    default: str | None = None,
) -> str | HttpApiResponse:
    raw = None if request.body is None else request.body.get(key)
    if raw is None:
        raw = default
    if not isinstance(raw, str) or not raw.strip():
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message=f"request body field {key!r} must be a non-empty string",
            ),
            request_id=_request_id_hint(request),
        )
    return raw.strip()


def _contract_response(response: QueryResponse[Any] | Any) -> HttpApiResponse:
    return _json_response(response.model_dump(mode="json"))


def _json_response(body: dict[str, Any]) -> HttpApiResponse:
    return HttpApiResponse(status_code=200, headers=dict(_JSON_HEADERS), body=body)


def _error_response(
    status_code: int,
    error: ApiError,
    *,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> HttpApiResponse:
    response_headers = dict(_JSON_HEADERS)
    response_headers.update(headers or {})
    return HttpApiResponse(
        status_code=status_code,
        headers=response_headers,
        body={
            "requestId": request_id,
            "ok": False,
            "data": None,
            "error": error.model_dump(mode="json"),
        },
    )


def _request_id_hint(request: HttpApiRequest) -> str | None:
    headers = _normalize_headers(request.headers)
    if "x-request-id" in headers:
        return headers["x-request-id"]
    if request.body is None:
        return None
    for key in ("requestId", "request_id", "commandId", "command_id"):
        raw = request.body.get(key)
        if isinstance(raw, str):
            return raw
    return None


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


__all__ = [
    "PlatoUiHttpTransport",
    "SidecarAuth",
]
