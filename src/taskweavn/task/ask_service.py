"""Task-level execution ASK command orchestration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskweavn.interaction import AskAnswer, AskRequest, AskStore
from taskweavn.task.bus import TaskBus
from taskweavn.task.commands import CommandResult
from taskweavn.task.models import TaskRef
from taskweavn.task.stores import TaskStoreError


@runtime_checkable
class TaskAskCommandService(Protocol):
    """Commands that resolve durable execution ASK objects."""

    def answer_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        selected_option_ids: tuple[str, ...] = (),
        text: str | None = None,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CommandResult: ...

    def defer_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CommandResult: ...

    def cancel_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CommandResult: ...


class DefaultTaskAskCommandService:
    """Default Product 1.0 ASK command policy.

    ASK state is written through ``AskStore`` first. TaskBus resume/fail policy
    runs only after the ASK command has durably accepted the user command.
    """

    def __init__(
        self,
        *,
        ask_store: AskStore,
        task_bus: TaskBus | None = None,
    ) -> None:
        self._ask_store = ask_store
        self._task_bus = task_bus

    def answer_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        selected_option_ids: tuple[str, ...] = (),
        text: str | None = None,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CommandResult:
        request = self._ask_store.get(session_id, ask_id)
        answer = AskAnswer(
            ask_id=ask_id,
            session_id=session_id,
            task_id=None if request is None else request.task_id,
            selected_option_ids=selected_option_ids,
            text=text,
            idempotency_key=idempotency_key,
        )
        store_result = self._ask_store.answer(
            session_id,
            ask_id,
            answer,
            idempotency_key=idempotency_key,
        )
        if not store_result.accepted or store_result.ask is None:
            return _rejected(store_result.message, command_id=command_id)

        resume_note = ""
        if store_result.status == "accepted":
            resume_note = self._resume_waiting_task_after_answer(store_result.ask)
        return _accepted(
            _message("ASK answered", resume_note),
            command_id=command_id,
            affected_task_refs=_affected_task_refs(store_result.ask),
        )

    def defer_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CommandResult:
        store_result = self._ask_store.defer(
            session_id,
            ask_id,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        if not store_result.accepted or store_result.ask is None:
            return _rejected(store_result.message, command_id=command_id)

        fail_note = ""
        if store_result.status == "accepted":
            fail_note = self._fail_waiting_task(
                store_result.ask,
                error_ref=f"ask_deferred: {(reason or 'user deferred ASK').strip()}",
            )
        return _accepted(
            _message("ASK deferred", fail_note),
            command_id=command_id,
            affected_task_refs=_affected_task_refs(store_result.ask),
        )

    def cancel_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CommandResult:
        reason = reason.strip()
        if not reason:
            return _rejected("ASK cancel requires reason", command_id=command_id)
        store_result = self._ask_store.cancel(
            session_id,
            ask_id,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        if not store_result.accepted or store_result.ask is None:
            return _rejected(store_result.message, command_id=command_id)

        fail_note = ""
        if store_result.status == "accepted":
            fail_note = self._fail_waiting_task(
                store_result.ask,
                error_ref=f"ask_cancelled: {reason}",
            )
        return _accepted(
            _message("ASK cancelled", fail_note),
            command_id=command_id,
            affected_task_refs=_affected_task_refs(store_result.ask),
        )

    def _resume_waiting_task_after_answer(self, ask: AskRequest) -> str:
        if self._task_bus is None or not ask.blocking or ask.task_id is None:
            return ""
        task = self._task_bus.get(ask.session_id, ask.task_id)
        if task is None:
            return "task resume skipped: task not found"
        if task.status != "waiting_for_user" or task.waiting_for_ask_id != ask.ask_id:
            return "task resume skipped: task is not waiting on this ASK"
        try:
            self._task_bus.resume_after_user(ask.session_id, ask.task_id, ask_id=ask.ask_id)
        except TaskStoreError as exc:
            return f"task resume failed: {exc}"
        return "task resumed"

    def _fail_waiting_task(self, ask: AskRequest, *, error_ref: str) -> str:
        if self._task_bus is None or not ask.blocking or ask.task_id is None:
            return ""
        task = self._task_bus.get(ask.session_id, ask.task_id)
        if task is None:
            return "task fail skipped: task not found"
        if task.status != "waiting_for_user" or task.waiting_for_ask_id != ask.ask_id:
            return "task fail skipped: task is not waiting on this ASK"
        try:
            self._task_bus.fail(ask.session_id, ask.task_id, error_ref=error_ref)
        except TaskStoreError as exc:
            return f"task fail failed: {exc}"
        return "task failed"


def _affected_task_refs(ask: AskRequest) -> tuple[TaskRef, ...]:
    if ask.task_id is None:
        return ()
    return (TaskRef.published(ask.task_id),)


def _accepted(
    message: str,
    *,
    command_id: str | None,
    affected_task_refs: tuple[TaskRef, ...] = (),
) -> CommandResult:
    if command_id is None:
        return CommandResult(
            status="accepted",
            message=message,
            affected_task_refs=affected_task_refs,
        )
    return CommandResult(
        command_id=command_id,
        status="accepted",
        message=message,
        affected_task_refs=affected_task_refs,
    )


def _rejected(message: str, *, command_id: str | None) -> CommandResult:
    if command_id is None:
        return CommandResult(
            status="rejected",
            message=message,
        )
    return CommandResult(
        command_id=command_id,
        status="rejected",
        message=message,
    )


def _message(prefix: str, note: str) -> str:
    if not note:
        return prefix
    return f"{prefix}; {note}"


__all__ = ["DefaultTaskAskCommandService", "TaskAskCommandService"]
