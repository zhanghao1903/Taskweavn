"""Tests for durable Conversation-native ASK card projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from taskweavn.server.ui_contract.conversation_ask_projection import (
    project_conversation_ask_messages,
)
from taskweavn.server.ui_contract.view_models import (
    AskAnswerView,
    AskOptionView,
    AskRequestView,
    TaskTreeView,
)
from taskweavn.task import (
    RawTask,
    RawTaskAnswer,
    RawTaskAnswerOption,
    RawTaskAsk,
)

NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)


def test_authoring_ask_projects_one_stable_group_card_with_selected_answers() -> None:
    raw_task = RawTask(
        raw_task_id="raw-1",
        session_id="session-1",
        source_message_id="source-1",
        user_input="Build a student courseware.",
        status="assessing",
        asks=(
            RawTaskAsk(
                ask_id="audience",
                raw_task_id="raw-1",
                question="Who is the audience?",
                reason="The audience controls the tone.",
                options=(
                    RawTaskAnswerOption(
                        option_id="grade-seven",
                        value="grade-7",
                        label="Grade seven",
                    ),
                    RawTaskAnswerOption(
                        option_id="grade-nine",
                        value="grade-9",
                        label="Grade nine",
                    ),
                ),
                created_at=NOW,
            ),
            RawTaskAsk(
                ask_id="style",
                raw_task_id="raw-1",
                question="What visual style?",
                reason="The style controls the presentation.",
                created_at=NOW + timedelta(seconds=1),
            ),
        ),
        answers=(
            RawTaskAnswer(
                answer_id="answer-audience",
                raw_task_id="raw-1",
                ask_id="audience",
                value="grade-7",
                source_message_id="answer-message",
                created_at=NOW + timedelta(minutes=1),
            ),
            RawTaskAnswer(
                answer_id="answer-style",
                raw_task_id="raw-1",
                ask_id="style",
                value="Playful",
                source_message_id="answer-message",
                created_at=NOW + timedelta(minutes=1),
            ),
        ),
        created_at=NOW,
        updated_at=NOW + timedelta(minutes=1),
    )

    messages = project_conversation_ask_messages(raw_tasks=(raw_task,))

    assert len(messages) == 1
    message = messages[0]
    assert message.id == "conversation-ask:authoring:raw-1"
    assert message.conversation_visibility == "visible"
    assert message.conversation_render is not None
    assert message.conversation_render.render_kind == "ask_card"
    card = message.conversation_render.ask_card
    assert card is not None
    assert card.domain == "authoring"
    assert card.status == "answered"
    assert card.can_answer is False
    assert card.questions[0].options[0].selected is True
    assert card.questions[1].answer_text == "Playful"


def test_execution_ask_card_uses_ask_id_and_preserves_answer_selection() -> None:
    ask = AskRequestView(
        id="ask-1",
        session_id="session-1",
        task_node_id="task-1",
        question="Where should Plato deploy?",
        reason="Deployment needs a target.",
        suggested_options=(
            AskOptionView(id="vercel", label="Vercel"),
            AskOptionView(id="other", label="Other"),
        ),
        answer_type="single_choice",
        allow_free_text=True,
        allow_no_option_with_text=True,
        blocking=True,
        status="answered",
        answer_id="answer-1",
        answer=AskAnswerView(
            id="answer-1",
            selected_option_ids=("vercel",),
            text=None,
            created_at=NOW + timedelta(minutes=1),
        ),
        created_at=NOW,
        answered_at=NOW + timedelta(minutes=1),
    )

    messages = project_conversation_ask_messages(execution_asks=(ask,))

    assert len(messages) == 1
    message = messages[0]
    assert message.id == "conversation-ask:execution:ask-1"
    assert message.task_node_id == "task-1"
    assert message.conversation_render is not None
    card = message.conversation_render.ask_card
    assert card is not None
    assert card.domain == "execution"
    assert card.status == "answered"
    assert card.ask_id == "ask-1"
    assert card.questions[0].options[0].selected is True
    assert card.questions[0].options[1].selected is False


def test_unanswered_authoring_ask_is_superseded_after_plan_exists() -> None:
    raw_task = RawTask(
        raw_task_id="raw-1",
        session_id="session-1",
        source_message_id="source-1",
        user_input="Build something.",
        status="awaiting_user",
        asks=(
            RawTaskAsk(
                ask_id="scope",
                raw_task_id="raw-1",
                question="What scope?",
                reason="Scope is required.",
                created_at=NOW,
            ),
        ),
        created_at=NOW,
        updated_at=NOW,
    )
    message = project_conversation_ask_messages(
        raw_tasks=(raw_task,),
        task_tree=TaskTreeView(
            id="tree-1",
            session_id="session-1",
            title="Plan",
            status="draft",
        ),
    )[0]

    assert message.conversation_render is not None
    assert message.conversation_render.ask_card is not None
    assert message.conversation_render.ask_card.status == "superseded"
    assert message.conversation_render.ask_card.can_answer is False
