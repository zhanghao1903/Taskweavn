"""HTTP command dispatch helpers for Plato UI transport."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from taskweavn.server.transport import HttpApiResponse
from taskweavn.server.ui_command_idempotency import (
    UiCommandResponseIdempotencyRecord,
    UiCommandResponseIdempotencyStore,
)
from taskweavn.server.ui_contract import (
    ApiError,
    CommandRequest,
    CommandResponse,
    CommandResult,
    DispatchExecutionPayload,
    PublishTaskTreePayload,
    RefreshHint,
    RetryTaskPayload,
    UiCommandGateway,
)
from taskweavn.server.ui_http_responses import _contract_response, _error_response
from taskweavn.server.ui_http_routes import _Route
from taskweavn.task import ExecutionDispatchRequestResult, ExecutionTriggerGateway


def _publish_task_tree_with_optional_dispatch(
    command_gateway: UiCommandGateway,
    execution_trigger_gateway: ExecutionTriggerGateway | None,
    request: CommandRequest[PublishTaskTreePayload],
) -> CommandResponse:
    response = command_gateway.publish_task_tree(request)
    if not response.ok or response.result is None:
        return response
    if not request.payload.start_immediately:
        return response
    if execution_trigger_gateway is None:
        return response

    try:
        dispatch_result = execution_trigger_gateway.request_dispatch(
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
    command_gateway: UiCommandGateway,
    execution_trigger_gateway: ExecutionTriggerGateway | None,
    task_node_id: str,
    request: CommandRequest[RetryTaskPayload],
) -> CommandResponse:
    response = command_gateway.retry_task(task_node_id, request)
    if (
        not response.ok
        or response.result is None
        or not request.payload.start_immediately
        or execution_trigger_gateway is None
    ):
        return response
    try:
        dispatch_result = execution_trigger_gateway.request_dispatch(
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
    execution_trigger_gateway: ExecutionTriggerGateway | None,
    request: CommandRequest[DispatchExecutionPayload],
) -> CommandResponse:
    if execution_trigger_gateway is None:
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
        dispatch_result = execution_trigger_gateway.request_dispatch(
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
    route: _Route,
    request: CommandRequest[Any],
    dispatch: Callable[[], Any],
    command_idempotency_store: UiCommandResponseIdempotencyStore | None,
) -> HttpApiResponse:
    idempotency_key = request.idempotency_key
    if idempotency_key is None or command_idempotency_store is None:
        return _contract_response(dispatch())

    request_hash = _command_request_hash(route, request)
    try:
        cached = command_idempotency_store.get(
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
                    message="idempotencyKey was reused for a different command request",
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
        command_idempotency_store.put(
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
