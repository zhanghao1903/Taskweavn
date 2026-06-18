"""Adapters from Contract Revision commands to existing interaction handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from taskweavn.contract_revision.models import (
    ContractCommandRequest,
    ResolveAskPayload,
    ResolveConfirmationContractPayload,
)
from taskweavn.server.ui_contract.commands import (
    AnswerAskPayload,
    ResolveConfirmationPayload,
)
from taskweavn.server.ui_contract.envelopes import CommandRequest, CommandResponse
from taskweavn.server.ui_contract.gateway_protocols import UiCommandGateway
from taskweavn.server.ui_http_commands import _answer_ask_with_resume_dispatch
from taskweavn.task import ExecutionTriggerGateway


@dataclass(frozen=True)
class ContractInteractionCommandOutcome:
    accepted: bool
    message: str
    command_response: CommandResponse | None = None
    reason_code: str | None = None


class ContractInteractionCommandHandler(Protocol):
    def resolve_ask(
        self,
        request: ContractCommandRequest,
        payload: ResolveAskPayload,
    ) -> ContractInteractionCommandOutcome: ...

    def resolve_confirmation(
        self,
        request: ContractCommandRequest,
        payload: ResolveConfirmationContractPayload,
    ) -> ContractInteractionCommandOutcome: ...


class UiGatewayContractInteractionCommandHandler:
    """Delegate routed interaction commands to the existing UI command gateway."""

    def __init__(
        self,
        command_gateway: UiCommandGateway,
        *,
        execution_trigger_gateway: ExecutionTriggerGateway | None = None,
    ) -> None:
        self._command_gateway = command_gateway
        self._execution_trigger_gateway = execution_trigger_gateway

    def resolve_ask(
        self,
        request: ContractCommandRequest,
        payload: ResolveAskPayload,
    ) -> ContractInteractionCommandOutcome:
        if request.ask_id is None:
            return ContractInteractionCommandOutcome(
                accepted=False,
                message="ASK target is missing.",
                reason_code="target_not_found",
            )
        command_response = _answer_ask_with_resume_dispatch(
            self._command_gateway,
            self._execution_trigger_gateway,
            request.ask_id,
            CommandRequest[AnswerAskPayload](
                command_id=request.command_id,
                session_id=request.session_id,
                idempotency_key=request.idempotency_key,
                expected_version=request.expected_version,
                payload=AnswerAskPayload(
                    selected_option_ids=payload.selected_option_ids,
                    text=payload.text,
                ),
            ),
        )
        return _outcome_from_command_response(command_response)

    def resolve_confirmation(
        self,
        request: ContractCommandRequest,
        payload: ResolveConfirmationContractPayload,
    ) -> ContractInteractionCommandOutcome:
        if request.confirmation_id is None:
            return ContractInteractionCommandOutcome(
                accepted=False,
                message="Confirmation target is missing.",
                reason_code="target_not_found",
            )
        command_response = self._command_gateway.resolve_confirmation(
            request.confirmation_id,
            CommandRequest[ResolveConfirmationPayload](
                command_id=request.command_id,
                session_id=request.session_id,
                idempotency_key=request.idempotency_key,
                expected_version=request.expected_version,
                payload=ResolveConfirmationPayload(
                    value=payload.value,
                    note=payload.note,
                ),
            ),
        )
        return _outcome_from_command_response(command_response)


def _outcome_from_command_response(
    command_response: CommandResponse,
) -> ContractInteractionCommandOutcome:
    if command_response.ok and command_response.result is not None:
        return ContractInteractionCommandOutcome(
            accepted=True,
            message=command_response.result.message,
            command_response=command_response,
        )
    return ContractInteractionCommandOutcome(
        accepted=False,
        message=command_response.error.message
        if command_response.error is not None
        else "Command was rejected.",
        command_response=command_response,
        reason_code=command_response.error.code
        if command_response.error is not None
        else "command_rejected",
    )


__all__ = [
    "ContractInteractionCommandHandler",
    "ContractInteractionCommandOutcome",
    "UiGatewayContractInteractionCommandHandler",
]
