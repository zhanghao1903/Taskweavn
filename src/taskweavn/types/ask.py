"""ASK actions and observations used by execution agents."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from taskweavn.interaction.ask import AskAnswerType
from taskweavn.types.base import BaseAction, BaseObservation


class AskUserQuestionInput(BaseModel):
    """One sub-question in a batched ASK request."""

    question_id: str | None = Field(default=None, min_length=1)
    question: str = Field(min_length=1)
    input_hint: str | None = Field(default=None, min_length=1)
    required: bool = True


class AskUserAction(BaseAction, kind="AskUserAction"):
    """Request user-owned missing information and block the current task."""

    baseline_risk: ClassVar[float] = 0.0

    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    questions: tuple[AskUserQuestionInput, ...] = ()
    suggested_options: tuple[str, ...] = ()
    answer_type: AskAnswerType = "free_text"
    allow_free_text: bool = True
    allow_no_option_with_text: bool = True
    blocking: Literal[True] = True


class AskUserObservation(BaseObservation, kind="AskUserObservation"):
    """Observation returned after durable ASK creation succeeds."""

    ask_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    status: Literal["waiting_for_user"] = "waiting_for_user"
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    message: str = Field(min_length=1)


__all__ = ["AskUserAction", "AskUserObservation", "AskUserQuestionInput"]
