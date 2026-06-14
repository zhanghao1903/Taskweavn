"""HTTP helpers for Runtime Input Router requests."""

from __future__ import annotations

from pydantic import ValidationError

from taskweavn.server.runtime_input_router import RuntimeInputRouter
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError, RuntimeInputRouteRequest
from taskweavn.server.ui_http_responses import (
    _contract_response,
    _error_response,
    _request_id_hint,
)


def _runtime_input_route_response(
    request: HttpApiRequest,
    *,
    session_id: str,
    workspace_id: str | None = None,
    router: RuntimeInputRouter | None,
) -> HttpApiResponse:
    if router is None:
        return _error_response(
            503,
            ApiError(
                code="internal_error",
                message="runtime input router is not configured",
                details={"route": "runtime_input_route"},
            ),
            request_id=_request_id_hint(request),
        )
    if request.body is None:
        return _error_response(
            400,
            ApiError(code="bad_request", message="request body must be a JSON object"),
            request_id=_request_id_hint(request),
        )
    body = dict(request.body)
    if workspace_id:
        body_workspace_id = body.get("workspaceId", body.get("workspace_id"))
        if body_workspace_id is not None and body_workspace_id != workspace_id:
            return _error_response(
                400,
                ApiError(
                    code="bad_request",
                    message="body workspaceId must match path workspaceId",
                    details={
                        "body_workspace_id": body_workspace_id,
                        "path_workspace_id": workspace_id,
                    },
                ),
                request_id=_request_id_hint(request),
            )
        body["workspaceId"] = workspace_id
    try:
        route_request = RuntimeInputRouteRequest.model_validate(body)
    except ValidationError as exc:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="request body does not match runtime input route contract",
                details={"errors": exc.errors()},
            ),
            request_id=_request_id_hint(request),
        )
    if route_request.session_id != session_id:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="body sessionId must match path sessionId",
                details={
                    "body_session_id": route_request.session_id,
                    "path_session_id": session_id,
                },
            ),
            request_id=route_request.command_id,
        )
    return _contract_response(router.route(route_request))


__all__ = ["_runtime_input_route_response"]
