"""Durable Conversation / Activity helpers for Runtime Input Router outcomes."""

from __future__ import annotations

from typing import Any, Protocol

from taskweavn.interaction import AgentMessage, MessageBus, MessageStreamError
from taskweavn.server.ui_contract.runtime_input import (
    RuntimeInputOutcome,
    RuntimeInputRouteDecision,
    RuntimeInputRouteRequest,
)
from taskweavn.server.ui_contract.view_models import (
    SessionActivityItemView,
    SessionActivityRefView,
)

READ_ONLY_INQUIRY_ACTIVITY_TITLE = "Read-only question answered"
ROUTER_TRACE_TITLE = "Router interpretation"
ROUTER_QUESTION_TITLE = "Router question"
USER_INPUT_TITLE = "User input"


class RuntimeInputActivityPublisher(Protocol):
    """Durable user-visible Conversation / Activity write seam for Router outcomes."""

    def publish_router_conversation(
        self,
        request: RuntimeInputRouteRequest,
        decision: RuntimeInputRouteDecision,
        outcome: RuntimeInputOutcome,
    ) -> None: ...

    def publish_router_activity(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
        *,
        outcome_status: str | None = None,
    ) -> None: ...

    def publish_read_only_answer(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
    ) -> None: ...


class MessageBusRuntimeInputActivityPublisher:
    """Persist Router Conversation and Activity through the existing MessageStream."""

    def __init__(self, message_bus: MessageBus) -> None:
        self._message_bus = message_bus

    def publish_router_conversation(
        self,
        request: RuntimeInputRouteRequest,
        decision: RuntimeInputRouteDecision,
        outcome: RuntimeInputOutcome,
    ) -> None:
        self._publish(_user_input_message(request))
        self._publish(_router_trace_message(request, decision, outcome))
        question_message = _question_card_message(request, decision, outcome)
        if question_message is not None:
            self._publish(question_message)

    def publish_router_activity(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
        *,
        outcome_status: str | None = None,
    ) -> None:
        title = (
            READ_ONLY_INQUIRY_ACTIVITY_TITLE
            if activity.kind == "answer" and activity.side_effect == "no_effect"
            else activity.title
        )
        message = AgentMessage(
            message_id=f"runtime-input-activity-{activity.kind}-{request.command_id}",
            session_id=request.session_id,
            task_id=activity.task_node_id,
            agent_id="router",
            message_type="informational",
            content=activity.body,
            context={
                "title": title,
                "activity_related_refs": [
                    ref.to_contract_dict() for ref in activity.related_refs
                ],
                "runtime_input_activity_kind": activity.kind,
                "runtime_input_side_effect": activity.side_effect,
                "runtime_input_decision_id": activity.source_id,
                "runtime_input_outcome_status": outcome_status,
                "runtime_input_scope_kind": activity.scope_kind,
                "runtime_input_plan_id": activity.plan_id,
                "runtime_input_task_node_id": activity.task_node_id,
                "conversation_render": _text_render(
                    title=title,
                    body=activity.body,
                ),
            },
            related_action_id=activity.source_id,
        )
        self._publish(message)

    def publish_read_only_answer(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
    ) -> None:
        self.publish_router_activity(
            request,
            activity,
            outcome_status="answered",
        )

    def _publish(self, message: AgentMessage) -> None:
        try:
            self._message_bus.publish(message)
        except MessageStreamError as exc:
            if "already exists" not in str(exc):
                raise


def _user_input_message(request: RuntimeInputRouteRequest) -> AgentMessage:
    return AgentMessage(
        message_id=f"runtime-input-user-{request.command_id}",
        session_id=request.session_id,
        task_id=request.selection.task_node_id,
        agent_id="user",
        message_type="informational",
        content=request.content,
        context={
            "title": USER_INPUT_TITLE,
            "conversation_render": _text_render(
                title=USER_INPUT_TITLE,
                body=request.content,
            ),
        },
        related_action_id=request.command_id,
    )


def _router_trace_message(
    request: RuntimeInputRouteRequest,
    decision: RuntimeInputRouteDecision,
    outcome: RuntimeInputOutcome,
) -> AgentMessage:
    body = (
        f"{decision.explanation} Outcome: {outcome.status}. "
        f"Side effect: {decision.side_effect}."
    )
    return AgentMessage(
        message_id=f"runtime-input-trace-{request.command_id}",
        session_id=request.session_id,
        task_id=decision.scope.task_node_id,
        agent_id="router",
        message_type="informational",
        content=body,
        context={
            "title": ROUTER_TRACE_TITLE,
            "activity_related_refs": [
                ref.to_contract_dict() for ref in decision.related_refs
            ],
            "conversation_render": {
                "protocolVersion": "plato.conversation.render.v1",
                "renderKind": "router_trace",
                "routerTrace": {
                    "intent": decision.intent,
                    "scopeKind": decision.scope.kind,
                    "confidence": decision.confidence,
                    "sideEffect": decision.side_effect,
                    "dispatchTarget": decision.dispatch_target,
                    "explanation": decision.explanation,
                    "outcomeStatus": outcome.status,
                },
            },
        },
        related_action_id=decision.id,
    )


def _question_card_message(
    request: RuntimeInputRouteRequest,
    decision: RuntimeInputRouteDecision,
    outcome: RuntimeInputOutcome,
) -> AgentMessage | None:
    if outcome.status != "needs_clarification":
        return None
    card_id = f"runtime-question-{request.command_id}"
    target_ref = _question_target_ref(decision.related_refs)
    message = AgentMessage(
        message_id=card_id,
        session_id=request.session_id,
        task_id=decision.scope.task_node_id,
        agent_id="router",
        message_type="informational",
        content=outcome.user_message,
        context={
            "title": ROUTER_QUESTION_TITLE,
            "conversation_render": {
                "protocolVersion": "plato.conversation.render.v1",
                "renderKind": "question_card",
                "questionCard": {
                    "cardId": card_id,
                    "cardKind": _question_card_kind(decision),
                    "status": "pending",
                    "title": "Plato needs one more detail",
                    "body": outcome.user_message,
                    "questions": [
                        {
                            "id": "answer",
                            "label": "Your answer",
                            "inputHint": "Type the missing information.",
                            "required": True,
                        }
                    ],
                    "options": _question_options(decision),
                    "answerMode": "runtime_input",
                    "targetRef": None
                    if target_ref is None
                    else target_ref.to_contract_dict(),
                },
            },
        },
        related_action_id=decision.id,
    )
    return message


def _question_card_kind(decision: RuntimeInputRouteDecision) -> str:
    for ref in decision.related_refs:
        if ref.kind == "ask":
            return "ask"
        if ref.kind == "confirmation":
            return "confirmation"
    return "clarification"


def _question_target_ref(
    refs: tuple[SessionActivityRefView, ...],
) -> SessionActivityRefView | None:
    for ref in refs:
        if ref.kind in {"ask", "confirmation", "task", "plan", "session"}:
            return ref
    return None


def _question_options(decision: RuntimeInputRouteDecision) -> list[dict[str, str]]:
    if _question_card_kind(decision) != "confirmation":
        return []
    return [
        {
            "id": "yes",
            "label": "Yes",
            "description": "Approve and continue.",
        },
        {
            "id": "no",
            "label": "No",
            "description": "Do not approve this action.",
        },
    ]


def _text_render(*, title: str, body: str) -> dict[str, Any]:
    return {
        "protocolVersion": "plato.conversation.render.v1",
        "renderKind": "text",
        "text": {
            "title": title,
            "body": body,
        },
    }


__all__ = [
    "MessageBusRuntimeInputActivityPublisher",
    "READ_ONLY_INQUIRY_ACTIVITY_TITLE",
    "ROUTER_QUESTION_TITLE",
    "ROUTER_TRACE_TITLE",
    "RuntimeInputActivityPublisher",
    "USER_INPUT_TITLE",
]
