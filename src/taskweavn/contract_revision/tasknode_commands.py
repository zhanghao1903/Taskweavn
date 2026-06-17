"""Adapters from Contract Revision TaskNode commands to existing handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from taskweavn.contract_revision.models import (
    ContractCommandRequest,
    PatchTaskNodePayload,
)
from taskweavn.server.ui_contract.commands import UpdateTaskNodePayload
from taskweavn.server.ui_contract.envelopes import CommandRequest, CommandResponse
from taskweavn.server.ui_contract.gateway_protocols import UiCommandGateway


@dataclass(frozen=True)
class ContractTaskNodeCommandOutcome:
    accepted: bool
    message: str
    command_response: CommandResponse | None = None
    reason_code: str | None = None


class ContractTaskNodeCommandHandler(Protocol):
    def patch_task_node(
        self,
        request: ContractCommandRequest,
        payload: PatchTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome: ...


class UiGatewayContractTaskNodeCommandHandler:
    """Delegate versioned TaskNode patches to the existing UI command gateway."""

    def __init__(self, command_gateway: UiCommandGateway) -> None:
        self._command_gateway = command_gateway

    def patch_task_node(
        self,
        request: ContractCommandRequest,
        payload: PatchTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome:
        if request.task_node_id is None:
            return ContractTaskNodeCommandOutcome(
                accepted=False,
                message="TaskNode target is missing.",
                reason_code="target_not_found",
            )
        command_response = self._command_gateway.update_task_node(
            request.task_node_id,
            CommandRequest[UpdateTaskNodePayload](
                command_id=request.command_id,
                session_id=request.session_id,
                idempotency_key=request.idempotency_key,
                expected_version=request.expected_version,
                payload=UpdateTaskNodePayload(
                    title=payload.title,
                    summary=payload.summary,
                    full_intent=payload.full_intent or payload.intent,
                    constraints=payload.constraints,
                    update_mode=payload.update_mode,
                    preserve_root_id=payload.preserve_root_id,
                ),
            ),
        )
        return _outcome_from_command_response(command_response)


def _outcome_from_command_response(
    command_response: CommandResponse,
) -> ContractTaskNodeCommandOutcome:
    if command_response.ok and command_response.result is not None:
        return ContractTaskNodeCommandOutcome(
            accepted=True,
            message=command_response.result.message,
            command_response=command_response,
        )
    return ContractTaskNodeCommandOutcome(
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
    "ContractTaskNodeCommandHandler",
    "ContractTaskNodeCommandOutcome",
    "UiGatewayContractTaskNodeCommandHandler",
]
