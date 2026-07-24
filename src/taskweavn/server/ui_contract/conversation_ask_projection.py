"""Project durable Authoring and Execution ASK facts into Conversation cards."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from taskweavn.server.ui_contract.view_models import (
    AskRequestView,
    ConversationAskCardView,
    ConversationAskOptionView,
    ConversationAskQuestionView,
    ConversationAskStatus,
    ConversationRenderView,
    SessionActivityRefView,
    SessionMessageView,
    TaskTreeView,
)
from taskweavn.task.authoring import RawTask, RawTaskAnswer, RawTaskAsk


def project_conversation_ask_messages(
    *,
    raw_tasks: Sequence[RawTask] = (),
    execution_asks: Sequence[AskRequestView] = (),
    task_tree: TaskTreeView | None = None,
) -> tuple[SessionMessageView, ...]:
    """Return stable Conversation cards derived from durable ASK authorities."""

    messages = [
        *(
            _project_authoring_ask_message(raw_task, task_tree=task_tree)
            for raw_task in raw_tasks
            if raw_task.asks
        ),
        *(_project_execution_ask_message(ask) for ask in execution_asks),
    ]
    return tuple(
        sorted(messages, key=lambda message: (message.created_at, message.id))
    )


def _project_authoring_ask_message(
    raw_task: RawTask,
    *,
    task_tree: TaskTreeView | None,
) -> SessionMessageView:
    answers_by_ask_id = {answer.ask_id: answer for answer in raw_task.answers}
    is_answered = all(
        ask.ask_id in answers_by_ask_id for ask in raw_task.asks
    )
    status: ConversationAskStatus = (
        "answered"
        if is_answered
        else "superseded"
        if task_tree is not None
        else "pending"
    )
    created_at = min(ask.created_at for ask in raw_task.asks)
    resolved_at = (
        max(answer.created_at for answer in raw_task.answers)
        if is_answered and raw_task.answers
        else None
    )
    card_id = f"conversation-ask:authoring:{raw_task.raw_task_id}"
    body = raw_task.intent_summary or raw_task.user_input or "Planning clarification"
    card = ConversationAskCardView(
        card_id=card_id,
        domain="authoring",
        status=status,
        title="Planning questions",
        body=body,
        raw_task_id=raw_task.raw_task_id,
        questions=tuple(
            _authoring_question_view(
                ask,
                answer=answers_by_ask_id.get(ask.ask_id),
            )
            for ask in raw_task.asks
        ),
        created_at=created_at,
        resolved_at=resolved_at,
        can_answer=status == "pending",
        readonly_reason=(
            "This planning question was superseded by the current plan."
            if status == "superseded"
            else None
        ),
    )
    return SessionMessageView(
        id=card_id,
        session_id=raw_task.session_id,
        task_node_id=None,
        kind="actionable" if status == "pending" else "informational",
        title="Plato question",
        body=_authoring_fallback_body(raw_task, answers_by_ask_id),
        created_at=created_at,
        conversation_render=ConversationRenderView(
            render_kind="ask_card",
            ask_card=card,
        ),
    )


def _authoring_question_view(
    ask: RawTaskAsk,
    *,
    answer: RawTaskAnswer | None,
) -> ConversationAskQuestionView:
    selected_option_id = _selected_authoring_option_id(ask, answer=answer)
    return ConversationAskQuestionView(
        id=ask.ask_id,
        prompt=ask.question,
        reason=ask.reason,
        required=ask.required,
        answered=answer is not None,
        answer_type="single_choice" if ask.options else "free_text",
        allow_free_text=not ask.options,
        options=tuple(
            ConversationAskOptionView(
                id=option.option_id,
                value=option.value,
                label=option.label,
                description=option.description,
                selected=option.option_id == selected_option_id,
            )
            for option in ask.options
        ),
        answer_text=(
            answer.value
            if answer is not None and selected_option_id is None
            else None
        ),
    )


def _selected_authoring_option_id(
    ask: RawTaskAsk,
    *,
    answer: RawTaskAnswer | None,
) -> str | None:
    if answer is None:
        return None
    for option in ask.options:
        if answer.value in {option.option_id, option.value, option.label}:
            return option.option_id
    return None


def _authoring_fallback_body(
    raw_task: RawTask,
    answers_by_ask_id: dict[str, RawTaskAnswer],
) -> str:
    lines = [raw_task.intent_summary or raw_task.user_input or "Planning questions"]
    for index, ask in enumerate(raw_task.asks, 1):
        lines.append(f"{index}. {ask.question}")
        answer = answers_by_ask_id.get(ask.ask_id)
        if answer is not None:
            lines.append(f"   Answer: {answer.value}")
    return "\n".join(lines)


def _project_execution_ask_message(ask: AskRequestView) -> SessionMessageView:
    card_id = f"conversation-ask:execution:{ask.id}"
    card = ConversationAskCardView(
        card_id=card_id,
        domain="execution",
        status=ask.status,
        title="Task needs input",
        body=ask.reason,
        ask_id=ask.id,
        task_node_id=ask.task_node_id,
        questions=_execution_question_views(ask),
        answer_text=(
            ask.answer.text
            if ask.answer is not None and len(ask.questions) > 1
            else None
        ),
        created_at=ask.created_at,
        resolved_at=_execution_resolved_at(ask),
        can_answer=ask.status == "pending",
        can_defer=ask.status == "pending",
        can_cancel=ask.status == "pending",
        readonly_reason=(
            None if ask.status == "pending" else f"This ASK is {ask.status}."
        ),
    )
    return SessionMessageView(
        id=card_id,
        session_id=ask.session_id,
        task_node_id=ask.task_node_id,
        task_ref=ask.task_ref,
        kind="actionable" if ask.status == "pending" else "informational",
        title="Plato question",
        body=_execution_fallback_body(ask),
        created_at=ask.created_at,
        activity_related_refs=(
            SessionActivityRefView(
                kind="ask",
                id=ask.id,
                label=ask.question,
            ),
        ),
        conversation_render=ConversationRenderView(
            render_kind="ask_card",
            ask_card=card,
        ),
    )


def _execution_question_views(
    ask: AskRequestView,
) -> tuple[ConversationAskQuestionView, ...]:
    selected_ids = (
        set(ask.answer.selected_option_ids) if ask.answer is not None else set()
    )
    if ask.questions:
        return tuple(
            ConversationAskQuestionView(
                id=question.id,
                prompt=question.question,
                reason=ask.reason,
                required=question.required,
                answered=ask.answer is not None,
                answer_type="free_text",
                allow_free_text=True,
                answer_text=(
                    ask.answer.text
                    if ask.answer is not None and len(ask.questions) == 1
                    else None
                ),
            )
            for question in ask.questions
        )
    return (
        ConversationAskQuestionView(
            id=ask.id,
            prompt=ask.question,
            reason=ask.reason,
            required=True,
            answered=ask.answer is not None,
            answer_type=ask.answer_type,
            allow_free_text=ask.allow_free_text or ask.allow_no_option_with_text,
            options=tuple(
                ConversationAskOptionView(
                    id=option.id,
                    value=option.id,
                    label=option.label,
                    description=option.description,
                    selected=option.id in selected_ids,
                )
                for option in ask.suggested_options
            ),
            answer_text=ask.answer.text if ask.answer is not None else None,
        ),
    )


def _execution_resolved_at(ask: AskRequestView) -> datetime | None:
    return (
        ask.answered_at
        or ask.deferred_at
        or ask.cancelled_at
        or ask.expired_at
        or (ask.answer.created_at if ask.answer is not None else None)
    )


def _execution_fallback_body(ask: AskRequestView) -> str:
    lines = [ask.question]
    if ask.answer is not None:
        labels = [
            option.label
            for option in ask.suggested_options
            if option.id in ask.answer.selected_option_ids
        ]
        if labels:
            lines.append(f"Answer: {', '.join(labels)}")
        if ask.answer.text:
            lines.append(f"Answer: {ask.answer.text}")
    return "\n".join(lines)


__all__ = ["project_conversation_ask_messages"]
