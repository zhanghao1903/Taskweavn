"""Confirmation tool for known high-risk actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from taskweavn.interaction import AgentMessage, MessageBus
from taskweavn.tools.base import Tool
from taskweavn.types.confirmation import (
    RequestConfirmationAction,
    RequestConfirmationObservation,
)

if TYPE_CHECKING:  # pragma: no cover
    from taskweavn.task.bus import TaskBus


@dataclass(frozen=True)
class RequestConfirmationTool(
    Tool[RequestConfirmationAction, RequestConfirmationObservation]
):
    """Create a blocking confirmation and move the active Task to waiting."""

    name = "request_confirmation"
    description = (
        "Ask the user to approve or reject a known high-risk action before "
        "continuing this Task. Use this when the action is clear but needs "
        "authorization, not when information is missing."
    )
    action_type = RequestConfirmationAction
    observation_type = RequestConfirmationObservation

    message_bus: MessageBus
    task_bus: TaskBus
    session_id: str
    task_id: str
    agent_id: str = "default_agent"

    def execute(self, action: RequestConfirmationAction) -> RequestConfirmationObservation:
        options = _confirmation_options(action)
        message = AgentMessage(
            session_id=self.session_id,
            task_id=self.task_id,
            agent_id=self.agent_id,
            message_type="actionable",
            content=_content(action),
            context=_message_context(action),
            action_options=list(options),
            requires_response=True,
            related_action_id=action.event_id,
        )
        self.message_bus.publish(message)
        self.task_bus.wait_for_confirmation(
            self.session_id,
            self.task_id,
            confirmation_id=message.message_id,
        )
        return RequestConfirmationObservation(
            action_id=action.event_id,
            confirmation_id=message.message_id,
            session_id=self.session_id,
            task_id=self.task_id,
            title=action.title,
            body=action.body,
            message=f"waiting_for_user: confirmation_id={message.message_id}",
        )


def _content(action: RequestConfirmationAction) -> str:
    risk = f"\n\nRisk: {action.risk_label}" if action.risk_label else ""
    return f"{action.title}\n\n{action.body}{risk}"


def _message_context(action: RequestConfirmationAction) -> dict[str, object]:
    context: dict[str, object] = {
        "confirmation_kind": "execution_authorization",
        "risk_label": action.risk_label,
        "default_option": action.default_option,
    }
    context.update(action.context)
    context["risk_label"] = action.risk_label
    context["default_option"] = action.default_option
    return context


def _confirmation_options(action: RequestConfirmationAction) -> tuple[str, ...]:
    seen: set[str] = set()
    options: list[str] = []
    for option in action.options:
        normalized = option.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        options.append(normalized)
    if not options:
        options = ["confirm", "reject"]
    if action.allow_session_approval and "approve_session" not in seen:
        options.append("approve_session")
    return tuple(options)


__all__ = ["RequestConfirmationTool"]
