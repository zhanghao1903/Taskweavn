"""HTTP query and request-body parsing helpers for Plato UI transport."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

from pydantic import ValidationError

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError, CommandRequest
from taskweavn.server.ui_http_responses import _error_response, _request_id_hint


def _request_query(request: HttpApiRequest) -> dict[str, str]:
    split = urlsplit(request.path)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update(request.query)
    return query


def _optional_bool_query(query: dict[str, str], key: str) -> bool | None:
    if key not in query:
        return None
    return _bool_query(query, key, default=False)


def _bool_query(query: dict[str, str], key: str, *, default: bool) -> bool:
    raw = query.get(key)
    if raw is None or raw == "":
        return default
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"query parameter {key!r} must be a boolean")


def _int_query(query: dict[str, str], key: str, *, default: int) -> int:
    raw = query.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"query parameter {key!r} must be an integer") from exc


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

