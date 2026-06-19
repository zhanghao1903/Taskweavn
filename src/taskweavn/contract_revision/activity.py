"""Activity publication helpers for Contract Revision commands."""

from __future__ import annotations

from typing import Protocol

from taskweavn.contract_revision.models import ContractCommandResult
from taskweavn.interaction import AgentMessage, MessageBus, MessageStreamError


class ContractRevisionActivityPublisher(Protocol):
    def publish_command_activity(self, result: ContractCommandResult) -> None: ...


class MessageBusContractRevisionActivityPublisher:
    """Persist Contract Revision Activity through the existing MessageStream."""

    def __init__(self, message_bus: MessageBus) -> None:
        self._message_bus = message_bus

    def publish_command_activity(self, result: ContractCommandResult) -> None:
        if result.activity is None or result.status not in {"accepted", "noop"}:
            return
        message = AgentMessage(
            message_id=f"contract-revision-{result.command_id}",
            session_id=result.session_id,
            task_id=result.task_node_id,
            agent_id="router",
            message_type="informational",
            content=result.activity.body,
            context={
                "title": result.activity.title,
                "activity_related_refs": [
                    ref.to_contract_dict() for ref in result.activity.related_refs
                ],
                "runtime_input_activity_kind": _activity_kind(result),
                "runtime_input_side_effect": result.side_effect,
                "contract_command_id": result.command_id,
                "contract_command_kind": result.command_kind,
                "contract_command_status": result.status,
                "contract_guidance_id": result.guidance_id,
                "contract_ask_id": result.ask_id,
                "contract_confirmation_id": result.confirmation_id,
                "contract_plan_id": result.plan_id,
                "contract_task_node_id": result.task_node_id,
            },
            related_action_id=result.command_id,
        )
        try:
            self._message_bus.publish(message)
        except MessageStreamError as exc:
            if "already exists" not in str(exc):
                raise


def _activity_kind(result: ContractCommandResult) -> str:
    if result.command_kind == "record_guidance":
        return "guidance_recorded"
    if result.command_kind == "resolve_ask":
        return "ask_answered"
    if result.command_kind == "resolve_confirmation":
        return "confirmation_resolved"
    if result.command_kind == "create_task_node":
        return "task_created"
    if result.command_kind == "create_execution_task":
        return "task_created"
    if result.command_kind == "delete_task_node":
        return "task_removed"
    if result.command_kind == "patch_task_node":
        return "task_changed"
    return "router_interpretation"


__all__ = [
    "ContractRevisionActivityPublisher",
    "MessageBusContractRevisionActivityPublisher",
]
