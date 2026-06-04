"""Tests for best-effort ASK continuation recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from taskweavn.interaction import AskAnswer, AskRequest, InMemoryAskStore
from taskweavn.server.ask_recovery import DefaultAskRecoveryService
from taskweavn.task import (
    CommandResult,
    InMemoryRawTaskStore,
    InMemoryTaskBus,
    RawTask,
    RawTaskAnswer,
    RawTaskAsk,
    TaskDomain,
)
from taskweavn.task.collaborator_api import CollaboratorApiAdapter
from taskweavn.task.execution import ExecutionDispatchRequestResult


def test_recovery_generates_task_tree_for_answered_authoring_ask() -> None:
    raw_store = InMemoryRawTaskStore([_answered_raw_task()])
    collaborator = _Collaborator()
    service = DefaultAskRecoveryService(
        raw_task_store=raw_store,
        collaborator=cast(CollaboratorApiAdapter, collaborator),
    )

    result = service.recover_session("s1")

    assert result.authoring_raw_task_ids == ("raw-1",)
    assert collaborator.calls == [
        {
            "idempotency_key": "ask-recovery:s1:raw-1:task-tree",
            "raw_task_id": "raw-1",
            "session_id": "s1",
        }
    ]


def test_recovery_skips_authoring_raw_task_with_unanswered_required_ask() -> None:
    raw_store = InMemoryRawTaskStore([_awaiting_raw_task()])
    collaborator = _Collaborator()
    service = DefaultAskRecoveryService(
        raw_task_store=raw_store,
        collaborator=cast(CollaboratorApiAdapter, collaborator),
    )

    result = service.recover_session("s1")

    assert result.authoring_raw_task_ids == ()
    assert collaborator.calls == []


def test_recovery_resumes_answered_execution_ask_and_dispatches() -> None:
    ask_store = InMemoryAskStore([_execution_ask()])
    ask_store.answer(
        "s1",
        "ask-1",
        AskAnswer(
            ask_id="ask-1",
            session_id="s1",
            task_id="task-1",
            text="Use the default.",
        ),
    )
    task_bus = _waiting_bus()
    dispatcher = _ExecutionTrigger()
    committed: list[tuple[str, str]] = []
    service = DefaultAskRecoveryService(
        ask_store=ask_store,
        task_bus=task_bus,
        execution_trigger_gateway=dispatcher,
        on_task_lifecycle_committed=lambda task: committed.append(
            (task.task_id, task.status)
        ),
    )

    result = service.recover_session("s1")

    task = task_bus.get("s1", "task-1")
    assert task is not None
    assert task.status == "pending"
    assert task.waiting_for_ask_id is None
    assert result.execution_resumed_task_ids == ("task-1",)
    assert result.execution_dispatch_ask_ids == ("ask-1",)
    assert dispatcher.calls == [
        ("s1", "startup_recovery", "ask-recovery:s1:ask-1")
    ]
    assert committed == [("task-1", "pending")]


def test_recovery_dispatches_pending_task_after_answer_resume_was_already_applied() -> None:
    ask_store = InMemoryAskStore([_execution_ask()])
    ask_store.answer(
        "s1",
        "ask-1",
        AskAnswer(
            ask_id="ask-1",
            session_id="s1",
            task_id="task-1",
            text="Use the default.",
        ),
    )
    task_bus = InMemoryTaskBus([_task()])
    dispatcher = _ExecutionTrigger()
    service = DefaultAskRecoveryService(
        ask_store=ask_store,
        task_bus=task_bus,
        execution_trigger_gateway=dispatcher,
    )

    result = service.recover_session("s1")

    assert result.execution_resumed_task_ids == ()
    assert result.execution_dispatch_ask_ids == ("ask-1",)
    assert dispatcher.calls == [
        ("s1", "startup_recovery", "ask-recovery:s1:ask-1")
    ]


@dataclass
class _Collaborator:
    calls: list[dict[str, str | None]] = field(default_factory=list)

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult:
        self.calls.append(
            {
                "idempotency_key": idempotency_key,
                "raw_task_id": raw_task_id,
                "session_id": session_id,
            }
        )
        return CommandResult(status="accepted", message="draft task tree generated")


@dataclass
class _ExecutionTrigger:
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)

    def request_dispatch(
        self,
        session_id: str,
        *,
        reason: str,
        request_id: str | None = None,
    ) -> ExecutionDispatchRequestResult:
        self.calls.append((session_id, reason, request_id))
        return ExecutionDispatchRequestResult(
            status="queued",
            session_id=session_id,
            reason="startup_recovery",
            request_id=request_id,
        )


def _answered_raw_task() -> RawTask:
    ask = RawTaskAsk(
        ask_id="raw-ask-1",
        raw_task_id="raw-1",
        question="Which target should be used?",
        reason="The plan needs a target.",
    )
    answer = RawTaskAnswer(
        answer_id="raw-answer-1",
        raw_task_id="raw-1",
        ask_id="raw-ask-1",
        value="Use the default target.",
        source_message_id="message-answer-1",
    )
    return RawTask(
        raw_task_id="raw-1",
        session_id="s1",
        source_message_id="message-1",
        user_input="Build a site.",
        status="assessing",
        asks=(ask,),
        answers=(answer,),
    )


def _awaiting_raw_task() -> RawTask:
    ask = RawTaskAsk(
        ask_id="raw-ask-1",
        raw_task_id="raw-1",
        question="Which target should be used?",
        reason="The plan needs a target.",
    )
    return RawTask(
        raw_task_id="raw-1",
        session_id="s1",
        source_message_id="message-1",
        user_input="Build a site.",
        status="awaiting_user",
        asks=(ask,),
    )


def _execution_ask() -> AskRequest:
    return AskRequest(
        ask_id="ask-1",
        session_id="s1",
        task_id="task-1",
        question="Which target should be used?",
        reason="The task needs a user-owned decision.",
    )


def _waiting_bus() -> InMemoryTaskBus:
    task_bus = InMemoryTaskBus([_task()])
    task_bus.claim_next("s1", capability="general", agent_id="agent-1")
    task_bus.wait_for_user("s1", "task-1", ask_id="ask-1")
    return task_bus


def _task() -> TaskDomain:
    return TaskDomain(
        task_id="task-1",
        session_id="s1",
        root_id="task-1",
        intent="Build the first slice.",
        required_capability="general",
        created_by="test",
    )
