"""Durable Activity helpers for Runtime Input Router outcomes."""

from __future__ import annotations

from typing import Protocol

from taskweavn.interaction import AgentMessage, MessageBus, MessageStreamError
from taskweavn.server.ui_contract.runtime_input import RuntimeInputRouteRequest
from taskweavn.server.ui_contract.view_models import SessionActivityItemView

READ_ONLY_INQUIRY_ACTIVITY_TITLE = "Read-only question answered"


class RuntimeInputActivityPublisher(Protocol):
    """Durable user-visible Activity write seam for Router outcomes."""

    def publish_read_only_answer(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
    ) -> None: ...


class MessageBusRuntimeInputActivityPublisher:
    """Persist read-only Router answers through the existing MessageStream."""

    def __init__(self, message_bus: MessageBus) -> None:
        self._message_bus = message_bus

    def publish_read_only_answer(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
    ) -> None:
        message = AgentMessage(
            message_id=f"runtime-input-answer-{request.command_id}",
            session_id=request.session_id,
            task_id=request.selection.task_node_id,
            agent_id="router",
            message_type="informational",
            content=activity.body,
            context={
                "title": READ_ONLY_INQUIRY_ACTIVITY_TITLE,
                "activity_related_refs": [
                    ref.to_contract_dict() for ref in activity.related_refs
                ],
                "runtime_input_activity_kind": "answer",
                "runtime_input_side_effect": "no_effect",
                "read_only_answer_title": activity.title,
                "runtime_input_decision_id": activity.source_id,
            },
            related_action_id=activity.source_id,
        )
        try:
            self._message_bus.publish(message)
        except MessageStreamError as exc:
            if "already exists" not in str(exc):
                raise


__all__ = [
    "MessageBusRuntimeInputActivityPublisher",
    "READ_ONLY_INQUIRY_ACTIVITY_TITLE",
    "RuntimeInputActivityPublisher",
]
