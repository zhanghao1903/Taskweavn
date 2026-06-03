"""Tests for task-level ASK command orchestration."""

from __future__ import annotations

from taskweavn.interaction import AskRequest, InMemoryAskStore
from taskweavn.task import DefaultTaskAskCommandService, InMemoryTaskBus, TaskDomain


def test_answer_ask_persists_answer_and_resumes_waiting_task() -> None:
    store = InMemoryAskStore([_ask()])
    bus = _waiting_bus()
    service = DefaultTaskAskCommandService(ask_store=store, task_bus=bus)

    result = service.answer_ask(
        "s1",
        "ask-1",
        text="Use the existing workspace.",
        idempotency_key="answer-1",
        command_id="cmd-answer",
    )

    request = store.get("s1", "ask-1")
    answer = store.get_answer("s1", "ask-1")
    task = bus.get("s1", "task-1")

    assert result.accepted is True
    assert result.command_id == "cmd-answer"
    assert "task resumed" in result.message
    assert request is not None
    assert request.status == "answered"
    assert answer is not None
    assert answer.text == "Use the existing workspace."
    assert task is not None
    assert task.status == "pending"
    assert task.waiting_for_ask_id is None
    assert task.claimed_by is None


def test_idempotent_answer_replay_does_not_resume_task_twice() -> None:
    store = InMemoryAskStore([_ask()])
    bus = _waiting_bus()
    service = DefaultTaskAskCommandService(ask_store=store, task_bus=bus)

    first = service.answer_ask(
        "s1",
        "ask-1",
        text="Use the existing workspace.",
        idempotency_key="answer-1",
    )
    replay = service.answer_ask(
        "s1",
        "ask-1",
        text="Use the existing workspace.",
        idempotency_key="answer-1",
    )

    assert first.accepted is True
    assert replay.accepted is True
    assert "task resumed" in first.message
    assert "task resumed" not in replay.message
    assert "not waiting" not in replay.message


def test_duplicate_answer_without_idempotency_is_rejected() -> None:
    store = InMemoryAskStore([_ask()])
    bus = _waiting_bus()
    service = DefaultTaskAskCommandService(ask_store=store, task_bus=bus)

    accepted = service.answer_ask("s1", "ask-1", text="Use existing files.")
    rejected = service.answer_ask("s1", "ask-1", text="Use different files.")

    assert accepted.accepted is True
    assert rejected.accepted is False
    assert rejected.message == "ASK is not pending: answered"


def test_defer_ask_fails_waiting_task() -> None:
    store = InMemoryAskStore([_ask()])
    bus = _waiting_bus()
    service = DefaultTaskAskCommandService(ask_store=store, task_bus=bus)

    result = service.defer_ask("s1", "ask-1", reason="Need more context later.")

    request = store.get("s1", "ask-1")
    task = bus.get("s1", "task-1")

    assert result.accepted is True
    assert "task failed" in result.message
    assert request is not None
    assert request.status == "deferred"
    assert task is not None
    assert task.status == "failed"
    assert task.error_ref == "ask_deferred: Need more context later."


def test_cancel_ask_fails_waiting_task() -> None:
    store = InMemoryAskStore([_ask()])
    bus = _waiting_bus()
    service = DefaultTaskAskCommandService(ask_store=store, task_bus=bus)

    result = service.cancel_ask("s1", "ask-1", reason="User cancelled the ASK.")

    request = store.get("s1", "ask-1")
    task = bus.get("s1", "task-1")

    assert result.accepted is True
    assert "task failed" in result.message
    assert request is not None
    assert request.status == "cancelled"
    assert task is not None
    assert task.status == "failed"
    assert task.error_ref == "ask_cancelled: User cancelled the ASK."


def _waiting_bus() -> InMemoryTaskBus:
    bus = InMemoryTaskBus([_task()])
    assert bus.claim_next("s1", capability="general", agent_id="agent-1") is not None
    bus.wait_for_user("s1", "task-1", ask_id="ask-1")
    return bus


def _ask() -> AskRequest:
    return AskRequest(
        ask_id="ask-1",
        session_id="s1",
        task_id="task-1",
        question="Which workspace facts should be used?",
        reason="The agent needs user-owned missing information.",
    )


def _task() -> TaskDomain:
    return TaskDomain(
        task_id="task-1",
        session_id="s1",
        root_id="task-1",
        intent="Use user input.",
        required_capability="general",
        created_by="tester",
    )
