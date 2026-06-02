"""HTTP response helpers for Plato UI transport."""

from __future__ import annotations

from typing import Any

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError, QueryResponse

_JSON_HEADERS = {"content-type": "application/json"}

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
