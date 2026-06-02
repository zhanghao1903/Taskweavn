"""Framework-neutral HTTP transport for Plato UI contract gateways."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from taskweavn.server.client_logs import ClientErrorLogSink
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_command_idempotency import (
    UiCommandResponseIdempotencyRecord,
    UiCommandResponseIdempotencyStore,
)
from taskweavn.server.ui_contract import (
    ApiError,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    CommandRequest,
    CommandResponse,
    CommandResult,
    DispatchExecutionPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    RefreshHint,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    UiCommandGateway,
    UiQueryGateway,
    UpdateTaskNodePayload,
)
from taskweavn.server.ui_events import ResyncOnlyEventSource, UiEventSource, sse_stream
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
from taskweavn.server.ui_http_routes import _match_route, _Route
from taskweavn.task import (
    ExecutionDispatchRequestResult,
    ExecutionTriggerGateway,
)

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
        command_idempotency_store: UiCommandResponseIdempotencyStore | None = None,
        execution_trigger_gateway: ExecutionTriggerGateway | None = None,
    ) -> None:
        self._query_gateway = query_gateway
        self._command_gateway = command_gateway
        self._event_source = event_source or ResyncOnlyEventSource()
        self._auth = auth
        self._client_error_log_sink = client_error_log_sink
        self._session_lifecycle_gateway = session_lifecycle_gateway
        self._command_idempotency_store = command_idempotency_store
        self._execution_trigger_gateway = execution_trigger_gateway

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
                            "dispatch_url_template": (
                                "/api/v1/sessions/{sessionId}/execution/dispatch"
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
                return self._command_response(
                    route,
                    append_session_request,
                    lambda: self._command_gateway.append_session_input(
                        append_session_request
                    ),
                )
            if route_name == "generate_task_tree":
                generate_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[GenerateTaskTreePayload],
                )
                if isinstance(generate_request, HttpApiResponse):
                    return generate_request
                return self._command_response(
                    route,
                    generate_request,
                    lambda: self._command_gateway.generate_task_tree(generate_request),
                )
            if route_name == "update_task_node":
                update_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[UpdateTaskNodePayload],
                )
                if isinstance(update_request, HttpApiResponse):
                    return update_request
                return self._command_response(
                    route,
                    update_request,
                    lambda: self._command_gateway.update_task_node(
                        route.task_node_id,
                        update_request,
                    ),
                )
            if route_name == "append_task_input":
                append_task_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[AppendTaskInputPayload],
                )
                if isinstance(append_task_request, HttpApiResponse):
                    return append_task_request
                return self._command_response(
                    route,
                    append_task_request,
                    lambda: self._command_gateway.append_task_input(
                        route.task_node_id,
                        append_task_request,
                    ),
                )
            if route_name == "publish_task_tree":
                publish_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[PublishTaskTreePayload],
                )
                if isinstance(publish_request, HttpApiResponse):
                    return publish_request
                return self._command_response(
                    route,
                    publish_request,
                    lambda: self._publish_task_tree_with_optional_dispatch(
                        publish_request
                    ),
                )
            if route_name == "retry_task":
                retry_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[RetryTaskPayload],
                )
                if isinstance(retry_request, HttpApiResponse):
                    return retry_request
                return self._command_response(
                    route,
                    retry_request,
                    lambda: self._retry_task_with_optional_dispatch(
                        route.task_node_id,
                        retry_request,
                    ),
                )
            if route_name == "dispatch_execution":
                dispatch_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[DispatchExecutionPayload],
                )
                if isinstance(dispatch_request, HttpApiResponse):
                    return dispatch_request
                return self._command_response(
                    route,
                    dispatch_request,
                    lambda: self._dispatch_execution(dispatch_request),
                )
            if route_name == "resolve_confirmation":
                resolve_request = _parse_command_request(
                    request,
                    route.session_id,
                    CommandRequest[ResolveConfirmationPayload],
                )
                if isinstance(resolve_request, HttpApiResponse):
                    return resolve_request
                return self._command_response(
                    route,
                    resolve_request,
                    lambda: self._command_gateway.resolve_confirmation(
                        route.confirmation_id,
                        resolve_request,
                    ),
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

    def _publish_task_tree_with_optional_dispatch(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse:
        response = self._command_gateway.publish_task_tree(request)
        if not response.ok or response.result is None:
            return response
        if not request.payload.start_immediately:
            return response
        if self._execution_trigger_gateway is None:
            return response

        try:
            dispatch_result = self._execution_trigger_gateway.request_dispatch(
                request.session_id,
                reason="publish_start_immediately",
                request_id=request.command_id,
            )
        except Exception as exc:  # noqa: BLE001 - publish must remain successful.
            dispatch_result = ExecutionDispatchRequestResult(
                status="health_error",
                session_id=request.session_id,
                reason="publish_start_immediately",
                request_id=request.command_id,
                message="execution dispatch failed after publish",
                error_ref=type(exc).__name__,
            )
        return _with_dispatch_debug_refs(response, dispatch_result)

    def _retry_task_with_optional_dispatch(
        self,
        task_node_id: str,
        request: CommandRequest[RetryTaskPayload],
    ) -> CommandResponse:
        response = self._command_gateway.retry_task(task_node_id, request)
        if (
            not response.ok
            or response.result is None
            or not request.payload.start_immediately
            or self._execution_trigger_gateway is None
        ):
            return response
        try:
            dispatch_result = self._execution_trigger_gateway.request_dispatch(
                request.session_id,
                reason="retry_start_immediately",
                request_id=request.command_id,
            )
        except Exception as exc:  # noqa: BLE001 - retry publish must remain successful.
            dispatch_result = ExecutionDispatchRequestResult(
                status="health_error",
                session_id=request.session_id,
                reason="retry_start_immediately",
                request_id=request.command_id,
                message="execution dispatch failed after retry",
                error_ref=type(exc).__name__,
            )
        return _with_dispatch_debug_refs(response, dispatch_result)

    def _dispatch_execution(
        self,
        request: CommandRequest[DispatchExecutionPayload],
    ) -> CommandResponse:
        if self._execution_trigger_gateway is None:
            return CommandResponse(
                request_id=request.command_id,
                ok=False,
                result=None,
                error=ApiError(
                    code="internal_error",
                    message="execution trigger gateway is not configured",
                ),
                refresh=RefreshHint(wait_for_events=False),
            )

        try:
            dispatch_result = self._execution_trigger_gateway.request_dispatch(
                request.session_id,
                reason=request.payload.reason,
                request_id=request.command_id,
            )
        except Exception as exc:  # noqa: BLE001 - command boundary must structure errors.
            dispatch_result = ExecutionDispatchRequestResult(
                status="health_error",
                session_id=request.session_id,
                reason=request.payload.reason,
                request_id=request.command_id,
                message="execution dispatch failed",
                error_ref=type(exc).__name__,
            )

        result = _command_result_from_dispatch(request, dispatch_result)
        refresh = RefreshHint(
            wait_for_events=dispatch_result.accepted,
            suggested_queries=("session.snapshot", "task.tree"),
        )
        if dispatch_result.accepted:
            return CommandResponse(
                request_id=request.command_id,
                ok=True,
                result=result,
                error=None,
                refresh=refresh,
            )
        return CommandResponse(
            request_id=request.command_id,
            ok=False,
            result=result,
            error=ApiError(
                code="command_rejected",
                message=dispatch_result.message,
                retryable=dispatch_result.status == "closed",
                details={
                    "dispatch_status": dispatch_result.status,
                    "dispatch_reason": dispatch_result.reason,
                    "error_ref": dispatch_result.error_ref,
                },
            ),
            refresh=refresh.model_copy(update={"wait_for_events": False}),
        )

    def _command_response(
        self,
        route: _Route,
        request: CommandRequest[Any],
        dispatch: Callable[[], Any],
    ) -> HttpApiResponse:
        idempotency_key = request.idempotency_key
        if idempotency_key is None or self._command_idempotency_store is None:
            return _contract_response(dispatch())

        request_hash = _command_request_hash(route, request)
        try:
            cached = self._command_idempotency_store.get(
                request.session_id,
                idempotency_key,
            )
        except Exception as exc:
            return _error_response(
                500,
                ApiError(
                    code="internal_error",
                    message="UI command idempotency store is unavailable",
                    retryable=True,
                    details={"error_type": type(exc).__name__},
                ),
                request_id=request.command_id,
            )

        if cached is not None:
            if cached.request_hash != request_hash:
                return _error_response(
                    409,
                    ApiError(
                        code="idempotency_conflict",
                        message=(
                            "idempotencyKey was reused for a different command request"
                        ),
                        details={
                            "idempotency_key": idempotency_key,
                            "route": route.name,
                        },
                    ),
                    request_id=request.command_id,
                )
            return cached.to_response()

        response = _contract_response(dispatch())
        try:
            self._command_idempotency_store.put(
                UiCommandResponseIdempotencyRecord.from_response(
                    session_id=request.session_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                )
            )
        except Exception:
            return response
        return response


def _command_result_from_dispatch(
    request: CommandRequest[Any],
    dispatch_result: ExecutionDispatchRequestResult,
) -> CommandResult:
    return CommandResult(
        command_id=request.command_id,
        status="accepted" if dispatch_result.accepted else "rejected",
        message=dispatch_result.message,
        debug_refs=_dispatch_debug_refs(dispatch_result),
    )


def _with_dispatch_debug_refs(
    response: CommandResponse,
    dispatch_result: ExecutionDispatchRequestResult,
) -> CommandResponse:
    if response.result is None:
        return response
    result = response.result.model_copy(
        update={
            "debug_refs": {
                **response.result.debug_refs,
                **_dispatch_debug_refs(dispatch_result),
            }
        }
    )
    refresh = response.refresh.model_copy(
        update={
            "wait_for_events": response.refresh.wait_for_events
            or dispatch_result.accepted,
            "suggested_queries": _dedupe_strs(
                (
                    *response.refresh.suggested_queries,
                    "session.snapshot",
                    "task.tree",
                )
            ),
        }
    )
    return response.model_copy(update={"result": result, "refresh": refresh})


def _dispatch_debug_refs(
    dispatch_result: ExecutionDispatchRequestResult,
) -> dict[str, str]:
    refs: dict[str, str] = {
        "dispatchStatus": dispatch_result.status,
        "dispatchReason": dispatch_result.reason,
    }
    if dispatch_result.error_ref:
        refs["dispatchErrorRef"] = dispatch_result.error_ref
    return refs


def _dedupe_strs(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _command_request_hash(route: _Route, request: CommandRequest[Any]) -> str:
    payload = {
        "route": route.name,
        "session_id": request.session_id,
        "task_node_id": route.task_node_id or None,
        "confirmation_id": route.confirmation_id or None,
        "expected_version": request.expected_version,
        "payload": request.payload.model_dump(mode="json"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "PlatoUiHttpTransport",
    "SidecarAuth",
]
