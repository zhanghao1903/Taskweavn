"""ASK tool for execution-time user questions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from taskweavn.interaction import AskOption, AskQuestion, AskRequest, AskStore
from taskweavn.tools.base import Tool
from taskweavn.types.ask import AskUserAction, AskUserObservation

if TYPE_CHECKING:  # pragma: no cover
    from taskweavn.task.bus import TaskBus


@dataclass(frozen=True)
class AskUserTool(Tool[AskUserAction, AskUserObservation]):
    """Create a durable blocking ASK and move the active Task to waiting."""

    name = "ask_user"
    description = (
        "Ask the user for missing, user-owned information that blocks this Task. "
        "Use only when execution cannot continue safely without a user answer."
    )
    action_type = AskUserAction
    observation_type = AskUserObservation

    ask_store: AskStore
    task_bus: TaskBus
    session_id: str
    task_id: str
    agent_id: str = "default_agent"

    def execute(self, action: AskUserAction) -> AskUserObservation:
        created = self.ask_store.create(
            AskRequest(
                session_id=self.session_id,
                task_id=self.task_id,
                agent_id=self.agent_id,
                question=action.question,
                reason=action.reason,
                questions=_ask_questions(action),
                suggested_options=_ask_options(action),
                answer_type=action.answer_type,
                allow_free_text=action.allow_free_text,
                allow_no_option_with_text=action.allow_no_option_with_text,
                blocking=True,
                created_by="agent",
            )
        )
        self.task_bus.wait_for_user(
            self.session_id,
            self.task_id,
            ask_id=created.ask_id,
        )
        return AskUserObservation(
            action_id=action.event_id,
            ask_id=created.ask_id,
            session_id=self.session_id,
            task_id=self.task_id,
            question=created.question,
            reason=created.reason,
            message=f"waiting_for_user: ask_id={created.ask_id}",
        )


def _ask_options(action: AskUserAction) -> tuple[AskOption, ...]:
    if not action.suggested_options:
        return ()
    return tuple(
        AskOption(option_id=f"option-{index}", label=label)
        for index, label in enumerate(action.suggested_options, start=1)
    )


def _ask_questions(action: AskUserAction) -> tuple[AskQuestion, ...]:
    if not action.questions:
        return ()
    return tuple(
        AskQuestion(
            question_id=question.question_id or f"question-{index}",
            question=question.question,
            input_hint=question.input_hint,
            required=question.required,
        )
        for index, question in enumerate(action.questions, start=1)
    )


__all__ = ["AskUserTool"]
