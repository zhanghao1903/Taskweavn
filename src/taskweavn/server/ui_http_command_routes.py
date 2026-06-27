"""Command HTTP route helpers for Plato UI transport."""

from __future__ import annotations

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_command_idempotency import UiCommandResponseIdempotencyStore
from taskweavn.server.ui_contract import (
    AnswerAskPayload,
    AnswerAuthoringAskBatchPayload,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    ArchivePlanPayload,
    CancelAskPayload,
    CommandRequest,
    DeferAskPayload,
    DispatchExecutionPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    RepairAuthoringStatePayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
    UiCommandGateway,
    UpdateTaskNodePayload,
)
from taskweavn.server.ui_http_commands import (
    _answer_ask_with_resume_dispatch,
    _command_response,
    _dispatch_execution,
    _publish_task_tree_with_optional_dispatch,
    _retry_task_with_optional_dispatch,
)
from taskweavn.server.ui_http_query_params import _parse_command_request
from taskweavn.server.ui_http_routes import _Route
from taskweavn.task import ExecutionTriggerGateway


def _command_route_response(
    request: HttpApiRequest,
    route: _Route,
    *,
    command_gateway: UiCommandGateway,
    command_idempotency_store: UiCommandResponseIdempotencyStore | None,
    execution_trigger_gateway: ExecutionTriggerGateway | None,
) -> HttpApiResponse | None:
    route_name = route.name
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
            lambda: command_gateway.append_session_input(append_session_request),
            command_idempotency_store,
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
            lambda: command_gateway.generate_task_tree(generate_request),
            command_idempotency_store,
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
            lambda: command_gateway.answer_authoring_ask_batch(
                route.raw_task_id,
                answer_authoring_request,
            ),
            command_idempotency_store,
        )
    if route_name == "repair_authoring_state":
        repair_authoring_request = _parse_command_request(
            request,
            route.session_id,
            CommandRequest[RepairAuthoringStatePayload],
        )
        if isinstance(repair_authoring_request, HttpApiResponse):
            return repair_authoring_request
        return _command_response(
            route,
            repair_authoring_request,
            lambda: command_gateway.repair_authoring_state(
                repair_authoring_request
            ),
            command_idempotency_store,
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
            lambda: command_gateway.update_task_node(
                route.task_node_id,
                update_request,
            ),
            command_idempotency_store,
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
            lambda: command_gateway.append_task_input(
                route.task_node_id,
                append_task_request,
            ),
            command_idempotency_store,
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
                command_gateway,
                execution_trigger_gateway,
                publish_request,
            ),
            command_idempotency_store,
        )
    if route_name == "archive_plan":
        archive_request = _parse_command_request(
            request,
            route.session_id,
            CommandRequest[ArchivePlanPayload],
        )
        if isinstance(archive_request, HttpApiResponse):
            return archive_request
        return _command_response(
            route,
            archive_request,
            lambda: command_gateway.archive_plan(route.plan_id, archive_request),
            command_idempotency_store,
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
                command_gateway,
                execution_trigger_gateway,
                route.task_node_id,
                retry_request,
            ),
            command_idempotency_store,
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
            lambda: command_gateway.stop_task(route.task_node_id, stop_request),
            command_idempotency_store,
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
            lambda: _dispatch_execution(execution_trigger_gateway, dispatch_request),
            command_idempotency_store,
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
            lambda: command_gateway.resolve_confirmation(
                route.confirmation_id,
                resolve_request,
            ),
            command_idempotency_store,
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
                command_gateway,
                execution_trigger_gateway,
                route.ask_id,
                answer_request,
            ),
            command_idempotency_store,
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
            lambda: command_gateway.defer_ask(route.ask_id, defer_request),
            command_idempotency_store,
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
            lambda: command_gateway.cancel_ask(route.ask_id, cancel_request),
            command_idempotency_store,
        )
    return None


__all__ = ["_command_route_response"]
