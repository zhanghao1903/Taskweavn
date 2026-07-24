"""Projection helpers for authoring ASK answer conversation messages."""

from __future__ import annotations

import re

from taskweavn.interaction import AgentMessage
from taskweavn.server.ui_contract.view_models import SessionMessageView
from taskweavn.task.authoring import RawTask
from taskweavn.task.stores import RawTaskStore


def project_authoring_ask_answer_message_view(
    view: SessionMessageView,
    message: AgentMessage,
    *,
    raw_task_store: RawTaskStore | None,
) -> SessionMessageView:
    if not _is_authoring_ask_answer_message(message):
        return view
    body = _authoring_ask_answer_body(message, raw_task_store=raw_task_store)
    return view.model_copy(
        update={
            "title": "ASK answered",
            "body": body,
            "conversation_visibility": "activity_only",
        }
    )


def _is_authoring_ask_answer_message(message: AgentMessage) -> bool:
    if message.agent_id != "user":
        return False
    return (
        message.context.get("surface") == "raw_task_ask"
        and message.context.get("operation")
        in {"answerRawTaskAsk", "answerRawTaskAskBatch"}
    )


def _authoring_ask_answer_body(
    message: AgentMessage,
    *,
    raw_task_store: RawTaskStore | None,
) -> str:
    if raw_task_store is None:
        return message.content
    raw_task_id = message.context.get("raw_task_id")
    if not isinstance(raw_task_id, str) or not raw_task_id:
        return message.content
    raw_task = raw_task_store.get(message.session_id, raw_task_id)
    if raw_task is None:
        return message.content
    ask_ids = _authoring_answer_ask_ids(message)
    values = _authoring_answer_values(message.content, answer_count=len(ask_ids))
    if not ask_ids or len(values) != len(ask_ids):
        return message.content
    labels = tuple(
        _authoring_answer_label(raw_task, ask_id=ask_id, value=value)
        for ask_id, value in zip(ask_ids, values, strict=True)
    )
    if len(labels) == 1:
        return labels[0]
    return "\n".join(f"{index}. {label}" for index, label in enumerate(labels, 1))


def _authoring_answer_ask_ids(message: AgentMessage) -> tuple[str, ...]:
    ask_id = message.context.get("ask_id")
    if isinstance(ask_id, str) and ask_id:
        return (ask_id,)
    ask_ids = message.context.get("ask_ids")
    if not isinstance(ask_ids, list | tuple):
        return ()
    return tuple(value for value in ask_ids if isinstance(value, str) and value)


def _authoring_answer_values(content: str, *, answer_count: int) -> tuple[str, ...]:
    if answer_count == 1:
        return (content.strip(),)
    values: list[str] = []
    for line in content.splitlines():
        value = line.strip()
        if not value:
            continue
        match = re.match(r"^\d+\.\s*(.+)$", value)
        values.append(match.group(1).strip() if match else value)
    return tuple(values)


def _authoring_answer_label(raw_task: RawTask, *, ask_id: str, value: str) -> str:
    ask = next(
        (candidate for candidate in raw_task.asks if candidate.ask_id == ask_id),
        None,
    )
    if ask is None:
        return value
    for option in ask.options:
        if value in {option.option_id, option.value, option.label}:
            return option.label
    return value
