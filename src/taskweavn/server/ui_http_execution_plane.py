"""HTTP shell for the Execution Plane Task API.

The route layer is intentionally thin: it parses JSON-safe request models,
delegates to ``TaskApiService``, and maps service errors to the existing
sidecar response envelope.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from taskweavn.execution_plane import (
    CancelTaskCommand,
    ExecutionPlaneError,
    RetryTaskCommand,
    TaskApiService,
    TaskEventQuery,
    TaskRequest,
)
from taskweavn.execution_plane.errors import ExecutionPlaneErrorCode
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError, ApiErrorCode
from taskweavn.server.ui_http_query_params import _int_query, _request_query
from taskweavn.server.ui_http_responses import (
    _error_response,
    _json_response,
    _request_id_hint,
)


def _execution_plane_response(
    request: HttpApiRequest,
    *,
    route_name: str,
    execution_id: str = "",
    workspace_id: str = "",
    service: TaskApiService | None,
) -> HttpApiResponse:
    if service is None:
        return _error_response(
            503,
            ApiError(
                code="internal_error",
                message="Execution Plane Task API service is not configured",
                details={"route": route_name},
            ),
            request_id=_request_id_hint(request),
        )

    try:
        if route_name == "execution_plane_publish":
            payload = _body(request)
            if workspace_id:
                metadata = dict(_object_value(payload, "metadata"))
                metadata.setdefault("workspaceId", workspace_id)
                payload = {**payload, "metadata": metadata}
            task_request = TaskRequest.model_validate(payload)
            return _ok(service.publish_task(task_request).model_dump(mode="json", by_alias=True))
        if route_name == "execution_plane_get":
            return _ok(service.get_task(execution_id).model_dump(mode="json", by_alias=True))
        if route_name == "execution_plane_cancel":
            cancel_command = CancelTaskCommand.model_validate(_body_or_empty(request))
            return _ok(
                service.cancel_task(
                    execution_id,
                    cancel_command,
                ).model_dump(mode="json", by_alias=True)
            )
        if route_name == "execution_plane_retry":
            retry_command = RetryTaskCommand.model_validate(_body_or_empty(request))
            return _ok(
                service.retry_task(
                    execution_id,
                    retry_command,
                ).model_dump(mode="json", by_alias=True)
            )
        if route_name == "execution_plane_events":
            query = TaskEventQuery(
                limit=_int_query(_request_query(request), "limit", default=100),
                cursor=_request_query(request).get("cursor"),
            )
            return _ok(
                service.list_events(
                    execution_id,
                    query,
                ).model_dump(mode="json", by_alias=True)
            )
        if route_name == "execution_plane_result":
            execution = service.get_task(execution_id)
            if execution.result_ref is None:
                raise ExecutionPlaneError(
                    "result_not_found",
                    "task execution does not have a result_ref",
                    status_code=404,
                    details={"executionId": execution_id},
                )
            return _ok(
                service.get_result(execution.result_ref).model_dump(
                    mode="json",
                    by_alias=True,
                )
            )
        if route_name == "execution_plane_error":
            execution = service.get_task(execution_id)
            if execution.error_ref is None:
                raise ExecutionPlaneError(
                    "result_not_found",
                    "task execution does not have an error_ref",
                    status_code=404,
                    details={"executionId": execution_id},
                )
            return _ok(
                service.get_error(execution.error_ref).model_dump(
                    mode="json",
                    by_alias=True,
                )
            )
        if route_name == "execution_plane_evidence":
            return _ok(service.list_evidence(execution_id).model_dump(mode="json", by_alias=True))
    except ExecutionPlaneError as exc:
        return _service_error_response(request, exc)
    except ValidationError as exc:
        return _validation_error_response(request, exc, route_name)
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

    return _error_response(
        500,
        ApiError(
            code="internal_error",
            message="Execution Plane route dispatch fell through",
            retryable=True,
            details={"route": route_name},
        ),
        request_id=_request_id_hint(request),
    )


def _ok(data: dict[str, Any]) -> HttpApiResponse:
    return _json_response({"ok": True, "data": data, "error": None})


def _body(request: HttpApiRequest) -> dict[str, Any]:
    if request.body is None:
        raise ValueError("request body must be a JSON object")
    return dict(request.body)


def _body_or_empty(request: HttpApiRequest) -> dict[str, Any]:
    return {} if request.body is None else dict(request.body)


def _object_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    raw = payload.get(key)
    return dict(raw) if isinstance(raw, dict) else {}


def _service_error_response(
    request: HttpApiRequest,
    exc: ExecutionPlaneError,
) -> HttpApiResponse:
    return _error_response(
        exc.status_code,
        ApiError(
            code=_api_error_code(exc.code),
            message=exc.message,
            retryable=exc.retryable,
            details={"serviceCode": exc.code, **exc.details},
        ),
        request_id=_request_id_hint(request),
    )


def _validation_error_response(
    request: HttpApiRequest,
    exc: ValidationError,
    route_name: str,
) -> HttpApiResponse:
    return _error_response(
        400,
        ApiError(
            code="bad_request",
            message="Execution Plane request validation failed",
            details={
                "route": route_name,
                "errors": _safe_validation_errors(exc),
            },
        ),
        request_id=_request_id_hint(request),
    )


def _api_error_code(code: ExecutionPlaneErrorCode) -> ApiErrorCode:
    if code == "idempotency_conflict":
        return "idempotency_conflict"
    if code == "permission_denied":
        return "permission_denied"
    if code in {"task_not_found", "result_not_found", "evidence_not_found"}:
        return "not_found"
    if code in {"capability_not_available", "lease_conflict"}:
        return "backend_busy"
    if code in {"task_not_cancellable", "task_not_retryable"}:
        return "command_rejected"
    if code == "execution_failed":
        return "internal_error"
    return "bad_request"


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    return [
        {
            "loc": tuple(str(part) for part in error.get("loc", ())),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in exc.errors(include_url=False)
    ]
