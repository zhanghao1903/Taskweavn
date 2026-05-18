"""Framework-neutral HTTP adapter for API Task publishing."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from taskweavn.task.api_publisher import ApiAuthContext, ApiPublishRequest, ApiTaskPublisher
from taskweavn.task.publisher import PublishPreview, PublishResult

ApiPublishRoute = Literal["preview", "publish"]


class _FrozenTransportModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class HttpApiRequest(_FrozenTransportModel):
    """Small framework-neutral request shape used by HTTP/RPC adapters."""

    method: str = Field(min_length=1)
    path: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None


class ApiErrorBody(_FrozenTransportModel):
    """Stable transport error body."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class HttpApiResponse(_FrozenTransportModel):
    """Small framework-neutral response shape used by HTTP/RPC adapters."""

    status_code: int = Field(ge=100, le=599)
    headers: dict[str, str] = Field(
        default_factory=lambda: {"content-type": "application/json"}
    )
    body: dict[str, Any]


class ApiPublishHttpTransport:
    """HTTP/RPC-style transport wrapper around ApiTaskPublisher.

    This adapter intentionally does not depend on FastAPI, Starlette, or an
    ASGI server. A concrete web framework can translate its request/response
    objects into these small models while keeping publish semantics in
    ``DefaultApiTaskPublisher``.
    """

    def __init__(self, publisher: ApiTaskPublisher) -> None:
        self._publisher = publisher

    def handle(self, request: HttpApiRequest) -> HttpApiResponse:
        route = _match_route(request.path)
        if route is None:
            return _error_response(
                status_code=404,
                code="not_found",
                message="unknown API publish route",
                request_id=_request_id_hint(request),
            )
        route_kind, session_id = route
        if request.method.upper() != "POST":
            return _error_response(
                status_code=405,
                code="method_not_allowed",
                message="API publish routes require POST",
                request_id=_request_id_hint(request),
                headers={"allow": "POST"},
            )

        auth_or_response = _auth_from_headers(request.headers, session_id=session_id)
        if isinstance(auth_or_response, HttpApiResponse):
            return auth_or_response

        api_request_or_response = _publish_request_from_body(
            request,
            session_id=session_id,
        )
        if isinstance(api_request_or_response, HttpApiResponse):
            return api_request_or_response

        result: PublishPreview | PublishResult
        if route_kind == "preview":
            result = self._publisher.preview(api_request_or_response, auth=auth_or_response)
        else:
            result = self._publisher.publish(api_request_or_response, auth=auth_or_response)
        return _success_response(result)


def _match_route(path: str) -> tuple[ApiPublishRoute, str] | None:
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "api-publish":
        return ("publish", parts[1])
    if (
        len(parts) == 4
        and parts[0] == "sessions"
        and parts[2] == "api-publish"
        and parts[3] == "preview"
    ):
        return ("preview", parts[1])
    return None


def _auth_from_headers(
    headers: dict[str, str],
    *,
    session_id: str,
) -> ApiAuthContext | HttpApiResponse:
    normalized = _normalize_headers(headers)
    actor_id = normalized.get("x-taskweavn-actor-id")
    if actor_id is None or not actor_id.strip():
        return _error_response(
            status_code=401,
            code="missing_actor",
            message="missing x-taskweavn-actor-id header",
        )
    allowed_sessions = _header_tuple(normalized, "x-taskweavn-allowed-sessions")
    if not allowed_sessions:
        allowed_sessions = (session_id,)
    return ApiAuthContext(
        actor_id=actor_id.strip(),
        allowed_session_ids=allowed_sessions,
        allowed_capabilities=_header_tuple(normalized, "x-taskweavn-allowed-capabilities"),
        allowed_agent_refs=_header_tuple(normalized, "x-taskweavn-allowed-agents"),
        metadata={
            "transport": "http",
            "path_session_id": session_id,
        },
    )


def _publish_request_from_body(
    request: HttpApiRequest,
    *,
    session_id: str,
) -> ApiPublishRequest | HttpApiResponse:
    if request.body is None:
        return _error_response(
            status_code=400,
            code="invalid_body",
            message="request body must be a JSON object",
            request_id=_request_id_hint(request),
        )
    body = dict(request.body)
    body_session_id = body.pop("session_id", None)
    if body_session_id is not None and body_session_id != session_id:
        return _error_response(
            status_code=400,
            code="session_mismatch",
            message="body session_id must match path session_id",
            request_id=_request_id_hint(request),
            details={
                "path_session_id": session_id,
                "body_session_id": body_session_id,
            },
        )
    headers = _normalize_headers(request.headers)
    body.setdefault("session_id", session_id)
    if "request_id" not in body and "x-request-id" in headers:
        body["request_id"] = headers["x-request-id"]
    if "idempotency_key" not in body and "idempotency-key" in headers:
        body["idempotency_key"] = headers["idempotency-key"]
    try:
        return ApiPublishRequest.model_validate(body)
    except ValidationError as exc:
        return _error_response(
            status_code=400,
            code="invalid_body",
            message="request body does not match ApiPublishRequest",
            request_id=_request_id_hint(request),
            details={"errors": exc.errors()},
        )


def _success_response(result: PublishPreview | PublishResult) -> HttpApiResponse:
    return HttpApiResponse(
        status_code=200,
        body={
            "ok": True,
            "request_id": result.request_id,
            "data": result.model_dump(mode="json"),
            "error": None,
        },
    )


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> HttpApiResponse:
    response_headers = {"content-type": "application/json"}
    response_headers.update(headers or {})
    return HttpApiResponse(
        status_code=status_code,
        headers=response_headers,
        body={
            "ok": False,
            "request_id": request_id,
            "data": None,
            "error": ApiErrorBody(
                code=code,
                message=message,
                details=dict(details or {}),
            ).model_dump(mode="json"),
        },
    )


def _request_id_hint(request: HttpApiRequest) -> str | None:
    headers = _normalize_headers(request.headers)
    if "x-request-id" in headers:
        return headers["x-request-id"]
    if request.body is None:
        return None
    raw = request.body.get("request_id")
    if isinstance(raw, str):
        return raw
    return None


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def _header_tuple(headers: dict[str, str], key: str) -> tuple[str, ...]:
    raw = headers.get(key)
    if raw is None:
        return ()
    return tuple(value.strip() for value in raw.split(",") if value.strip())


__all__ = [
    "ApiErrorBody",
    "ApiPublishHttpTransport",
    "HttpApiRequest",
    "HttpApiResponse",
]
