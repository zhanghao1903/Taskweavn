"""ASK command helpers for the UI command gateway."""

from __future__ import annotations

from taskweavn.server.ui_contract.command_mapping import (
    _command_response,
)
from taskweavn.server.ui_contract.commands import (
    AnswerAskPayload,
    CancelAskPayload,
    DeferAskPayload,
)
from taskweavn.server.ui_contract.envelopes import CommandRequest, CommandResponse
from taskweavn.server.ui_contract.refs import (
    AffectedObjectImpact,
    AffectedObjectRef,
    AffectedScope,
    ObjectRef,
)
from taskweavn.task.ask_service import TaskAskCommandService
from taskweavn.task.commands import CommandResult as CoreCommandResult


def answer_ask_command(
    ask_commands: TaskAskCommandService | None,
    ask_id: str,
    request: CommandRequest[AnswerAskPayload],
) -> CommandResponse:
    if ask_commands is None:
        return missing_ask_command_service_response(request)
    result = ask_commands.answer_ask(
        request.session_id,
        ask_id,
        selected_option_ids=request.payload.selected_option_ids,
        text=request.payload.text,
        idempotency_key=request.idempotency_key,
        command_id=request.command_id,
    )
    return ask_command_response(
        request,
        result,
        ask_id=ask_id,
        impact="changed",
        reason="ASK was answered.",
    )


def defer_ask_command(
    ask_commands: TaskAskCommandService | None,
    ask_id: str,
    request: CommandRequest[DeferAskPayload],
) -> CommandResponse:
    if ask_commands is None:
        return missing_ask_command_service_response(request)
    result = ask_commands.defer_ask(
        request.session_id,
        ask_id,
        reason=request.payload.reason,
        idempotency_key=request.idempotency_key,
        command_id=request.command_id,
    )
    return ask_command_response(
        request,
        result,
        ask_id=ask_id,
        impact="changed",
        reason="ASK was deferred.",
    )


def cancel_ask_command(
    ask_commands: TaskAskCommandService | None,
    ask_id: str,
    request: CommandRequest[CancelAskPayload],
) -> CommandResponse:
    if ask_commands is None:
        return missing_ask_command_service_response(request)
    result = ask_commands.cancel_ask(
        request.session_id,
        ask_id,
        reason=request.payload.reason,
        idempotency_key=request.idempotency_key,
        command_id=request.command_id,
    )
    return ask_command_response(
        request,
        result,
        ask_id=ask_id,
        impact="changed",
        reason="ASK was cancelled.",
    )


def missing_ask_command_service_response[T](
    request: CommandRequest[T],
) -> CommandResponse:
    return _command_response(
        request,
        CoreCommandResult(
            status="rejected",
            message="ASK command service is not configured",
        ),
    )


def ask_command_response[T](
    request: CommandRequest[T],
    result: CoreCommandResult,
    *,
    ask_id: str,
    impact: AffectedObjectImpact,
    reason: str,
) -> CommandResponse:
    ask_ref = ObjectRef(kind="ask", id=ask_id)
    return _command_response(
        request,
        result,
        object_refs=(ask_ref,),
        affected_objects=(
            AffectedObjectRef(
                ref=ask_ref,
                impact=impact,
                reason=reason,
            ),
        ),
        suggested_queries=("session.snapshot", "asks", "task.tree", "task.detail"),
        affected_scopes=(
            AffectedScope(kind="asks"),
            AffectedScope(kind="task_tree"),
            *(
                AffectedScope(kind="task_detail", task_ref=task_ref)
                for task_ref in result.affected_task_refs
            ),
        ),
    )


__all__ = [
    "answer_ask_command",
    "ask_command_response",
    "cancel_ask_command",
    "defer_ask_command",
    "missing_ask_command_service_response",
]
