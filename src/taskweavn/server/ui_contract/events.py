"""UI event contract models for future SSE transport."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field

from taskweavn.interaction import AgentMessage
from taskweavn.server.ui_contract.base import UiContractModel, utcnow
from taskweavn.task.models import TaskRef

UiEventType = Literal[
    "session.status_changed",
    "session.resync_required",
    "task.tree.changed",
    "task.node.changed",
    "message.appended",
    "confirmation.created",
    "confirmation.resolved",
    "result.updated",
    "file_changes.updated",
    "audit.summary_updated",
    "command.completed",
    "command.failed",
]


def _new_id() -> str:
    return uuid4().hex


class UiEvent(UiContractModel):
    event_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    event_type: UiEventType
    cursor: str = Field(min_length=1)
    task_node_ids: tuple[str, ...] = ()
    task_refs: tuple[TaskRef, ...] = ()
    message_ids: tuple[str, ...] = ()
    command_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


def session_status_changed(
    session_id: str,
    *,
    cursor: str,
    previous_status: str | None = None,
    current_status: str | None = None,
    command_id: str | None = None,
) -> UiEvent:
    payload: dict[str, object] = {}
    if previous_status is not None:
        payload["previous_status"] = previous_status
    if current_status is not None:
        payload["current_status"] = current_status
    return UiEvent(
        session_id=session_id,
        event_type="session.status_changed",
        cursor=cursor,
        command_id=command_id,
        payload=payload,
    )


def resync_required(
    session_id: str,
    *,
    cursor: str,
    reason: str,
) -> UiEvent:
    return UiEvent(
        session_id=session_id,
        event_type="session.resync_required",
        cursor=cursor,
        payload={"reason": reason},
    )


def task_tree_changed(
    session_id: str,
    *,
    cursor: str,
    task_refs: tuple[TaskRef, ...] = (),
    command_id: str | None = None,
    reason: str | None = None,
) -> UiEvent:
    return _task_event(
        session_id,
        event_type="task.tree.changed",
        cursor=cursor,
        task_refs=task_refs,
        command_id=command_id,
        reason=reason,
    )


def task_node_changed(
    session_id: str,
    *,
    cursor: str,
    task_refs: tuple[TaskRef, ...],
    command_id: str | None = None,
    reason: str | None = None,
) -> UiEvent:
    return _task_event(
        session_id,
        event_type="task.node.changed",
        cursor=cursor,
        task_refs=task_refs,
        command_id=command_id,
        reason=reason,
    )


def message_appended(message: AgentMessage, *, cursor: str) -> UiEvent:
    return UiEvent(
        session_id=message.session_id,
        event_type="message.appended",
        cursor=cursor,
        task_node_ids=_task_node_ids_from_message(message),
        task_refs=_task_refs_from_message(message),
        message_ids=(message.message_id,),
        payload={
            "message_type": message.message_type,
            "agent_id": message.agent_id,
        },
    )


def confirmation_created(message: AgentMessage, *, cursor: str) -> UiEvent:
    return UiEvent(
        session_id=message.session_id,
        event_type="confirmation.created",
        cursor=cursor,
        task_node_ids=_task_node_ids_from_message(message),
        task_refs=_task_refs_from_message(message),
        message_ids=(message.message_id,),
        payload={"requires_response": message.requires_response},
    )


def confirmation_resolved(response: AgentMessage, *, cursor: str) -> UiEvent:
    message_ids: tuple[str, ...] = (response.message_id,)
    if response.parent_message_id is not None:
        message_ids = (response.parent_message_id, response.message_id)
    payload: dict[str, object] = {}
    if response.response_value is not None:
        payload["response_value"] = response.response_value
    if response.response_source is not None:
        payload["response_source"] = response.response_source
    return UiEvent(
        session_id=response.session_id,
        event_type="confirmation.resolved",
        cursor=cursor,
        task_node_ids=_task_node_ids_from_message(response),
        task_refs=_task_refs_from_message(response),
        message_ids=message_ids,
        payload=payload,
    )


def result_updated(
    session_id: str,
    *,
    cursor: str,
    task_ref: TaskRef | None = None,
    result_id: str | None = None,
    command_id: str | None = None,
) -> UiEvent:
    payload: dict[str, object] = {}
    if result_id is not None:
        payload["result_id"] = result_id
    return _task_event(
        session_id,
        event_type="result.updated",
        cursor=cursor,
        task_refs=() if task_ref is None else (task_ref,),
        command_id=command_id,
        payload=payload,
    )


def file_changes_updated(
    session_id: str,
    *,
    cursor: str,
    task_ref: TaskRef | None = None,
    recursive: bool = False,
    command_id: str | None = None,
) -> UiEvent:
    return _task_event(
        session_id,
        event_type="file_changes.updated",
        cursor=cursor,
        task_refs=() if task_ref is None else (task_ref,),
        command_id=command_id,
        payload={"recursive": recursive},
    )


def audit_summary_updated(
    session_id: str,
    *,
    cursor: str,
    severity: str | None = None,
) -> UiEvent:
    payload: dict[str, object] = {}
    if severity is not None:
        payload["severity"] = severity
    return UiEvent(
        session_id=session_id,
        event_type="audit.summary_updated",
        cursor=cursor,
        payload=payload,
    )


def command_completed(
    session_id: str,
    *,
    cursor: str,
    command_id: str,
    task_refs: tuple[TaskRef, ...] = (),
) -> UiEvent:
    return _task_event(
        session_id,
        event_type="command.completed",
        cursor=cursor,
        task_refs=task_refs,
        command_id=command_id,
    )


def command_failed(
    session_id: str,
    *,
    cursor: str,
    command_id: str,
    message: str,
    retryable: bool = False,
) -> UiEvent:
    return UiEvent(
        session_id=session_id,
        event_type="command.failed",
        cursor=cursor,
        command_id=command_id,
        payload={"message": message, "retryable": retryable},
    )


def _task_event(
    session_id: str,
    *,
    event_type: UiEventType,
    cursor: str,
    task_refs: tuple[TaskRef, ...],
    command_id: str | None = None,
    reason: str | None = None,
    payload: dict[str, object] | None = None,
) -> UiEvent:
    event_payload = {} if payload is None else dict(payload)
    if reason is not None:
        event_payload["reason"] = reason
    return UiEvent(
        session_id=session_id,
        event_type=event_type,
        cursor=cursor,
        task_node_ids=tuple(ref.id for ref in task_refs),
        task_refs=task_refs,
        command_id=command_id,
        payload=event_payload,
    )


def _task_node_ids_from_message(message: AgentMessage) -> tuple[str, ...]:
    if message.task_id is None:
        return ()
    return (message.task_id,)


def _task_refs_from_message(message: AgentMessage) -> tuple[TaskRef, ...]:
    if message.task_id is None:
        return ()
    if message.context.get("task_ref_kind") == "draft":
        return (TaskRef.draft(message.task_id),)
    return (TaskRef.published(message.task_id),)
