"""Tests for durable execution ASK stores."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from taskweavn.interaction import (
    AskAnswer,
    AskOption,
    AskQuestion,
    AskRequest,
    AskStore,
    InMemoryAskStore,
    SqliteAskStore,
)


def test_ask_store_protocol_conformance(tmp_path: Path) -> None:
    assert isinstance(InMemoryAskStore(), AskStore)
    store = SqliteAskStore(tmp_path / "asks.sqlite")
    try:
        assert isinstance(store, AskStore)
    finally:
        store.close()


def test_create_get_and_list_for_session(tmp_path: Path) -> None:
    _run_for_each_store(tmp_path, _assert_create_get_and_list_for_session)


def test_answer_records_canonical_answer_and_rejects_duplicate(tmp_path: Path) -> None:
    _run_for_each_store(tmp_path, _assert_answer_records_and_rejects_duplicate)


def test_answer_replays_same_idempotency_key(tmp_path: Path) -> None:
    _run_for_each_store(tmp_path, _assert_answer_replays_same_idempotency_key)


def test_invalid_option_is_rejected_and_ask_stays_pending(tmp_path: Path) -> None:
    _run_for_each_store(tmp_path, _assert_invalid_option_rejected)


def test_defer_cancel_and_expire_transitions(tmp_path: Path) -> None:
    _run_for_each_store(tmp_path, _assert_terminal_transitions)


def test_sqlite_store_persists_pending_and_answered_asks(tmp_path: Path) -> None:
    db = tmp_path / "asks.sqlite"
    first = SqliteAskStore(db)
    request = _choice_ask("ask-1")
    try:
        first.create(request)
        result = first.answer(
            "s1",
            "ask-1",
            _answer("ask-1", selected=("yes",)),
            idempotency_key="answer-1",
        )
        assert result.accepted
    finally:
        first.close()

    second = SqliteAskStore(db)
    try:
        loaded = second.get("s1", "ask-1")
        answer = second.get_answer("s1", "ask-1")

        assert loaded is not None
        assert loaded.status == "answered"
        assert result.answer is not None
        assert loaded.answer_id == result.answer.answer_id
        assert answer is not None
        assert answer.selected_option_ids == ("yes",)
    finally:
        second.close()


def test_sqlite_store_persists_batched_questions(tmp_path: Path) -> None:
    db = tmp_path / "asks.sqlite"
    first = SqliteAskStore(db)
    try:
        first.create(
            _text_ask("ask-batch").model_copy(
                update={
                    "questions": (
                        AskQuestion(
                            question_id="role",
                            question="What is your professional role?",
                            input_hint="Designer, engineer, product manager...",
                        ),
                        AskQuestion(
                            question_id="goal",
                            question="What is the main portfolio goal?",
                        ),
                    )
                }
            )
        )
    finally:
        first.close()

    second = SqliteAskStore(db)
    try:
        loaded = second.get("s1", "ask-batch")

        assert loaded is not None
        assert [question.question_id for question in loaded.questions] == [
            "role",
            "goal",
        ]
        assert loaded.questions[0].input_hint == (
            "Designer, engineer, product manager..."
        )
    finally:
        second.close()


def _assert_create_get_and_list_for_session(store: AskStore) -> None:
    first = store.create(_choice_ask("ask-1", task_id="task-a"))
    store.create(_choice_ask("ask-2", task_id="task-b"))
    store.create(_text_ask("ask-3", task_id="task-a"))

    assert store.get("s1", "ask-1") == first
    assert [ask.ask_id for ask in store.list_for_session("s1")] == [
        "ask-1",
        "ask-2",
        "ask-3",
    ]
    assert [
        ask.ask_id
        for ask in store.list_for_session(
            "s1",
            statuses=("pending",),
            task_id="task-a",
        )
    ] == ["ask-1", "ask-3"]


def _assert_answer_records_and_rejects_duplicate(store: AskStore) -> None:
    store.create(_choice_ask("ask-1"))

    result = store.answer("s1", "ask-1", _answer("ask-1", selected=("yes",)))
    duplicate = store.answer("s1", "ask-1", _answer("ask-1", selected=("no",)))
    stored_answer = store.get_answer("s1", "ask-1")

    assert result.status == "accepted"
    assert result.ask is not None
    assert result.ask.status == "answered"
    assert duplicate.status == "rejected"
    assert "not pending" in duplicate.message
    assert stored_answer is not None
    assert stored_answer.selected_option_ids == ("yes",)


def _assert_answer_replays_same_idempotency_key(store: AskStore) -> None:
    store.create(_choice_ask("ask-1"))

    first = store.answer(
        "s1",
        "ask-1",
        _answer("ask-1", selected=("yes",)),
        idempotency_key="answer-1",
    )
    replay = store.answer(
        "s1",
        "ask-1",
        _answer("ask-1", selected=("no",)),
        idempotency_key="answer-1",
    )

    assert first.status == "accepted"
    assert replay.status == "replayed"
    assert replay.answer is not None
    assert replay.answer.selected_option_ids == ("yes",)


def _assert_invalid_option_rejected(store: AskStore) -> None:
    store.create(_choice_ask("ask-1"))

    result = store.answer("s1", "ask-1", _answer("ask-1", selected=("missing",)))
    loaded = store.get("s1", "ask-1")

    assert result.status == "rejected"
    assert "unknown option" in result.message
    assert loaded is not None
    assert loaded.status == "pending"


def _assert_terminal_transitions(store: AskStore) -> None:
    store.create(_choice_ask("defer-ask"))
    store.create(_choice_ask("cancel-ask"))
    store.create(_choice_ask("expire-ask"))

    deferred = store.defer(
        "s1",
        "defer-ask",
        reason="answer later",
        idempotency_key="defer-1",
    )
    deferred_replay = store.defer(
        "s1",
        "defer-ask",
        reason="different reason",
        idempotency_key="defer-1",
    )
    cancelled = store.cancel("s1", "cancel-ask", reason="not needed")
    expired = store.expire("s1", "expire-ask", reason="too old")

    assert deferred.status == "accepted"
    assert deferred.ask is not None
    assert deferred.ask.status == "deferred"
    assert deferred.ask.resume_hint == "answer later"
    assert deferred_replay.status == "replayed"
    assert cancelled.ask is not None
    assert cancelled.ask.status == "cancelled"
    assert expired.ask is not None
    assert expired.ask.status == "expired"


def _run_for_each_store(
    tmp_path: Path,
    assertion: Callable[[AskStore], None],
) -> None:
    assertion(InMemoryAskStore())
    sqlite = SqliteAskStore(tmp_path / f"{assertion.__name__}.sqlite")
    try:
        assertion(sqlite)
    finally:
        sqlite.close()


def _choice_ask(ask_id: str, *, task_id: str = "task-1") -> AskRequest:
    return AskRequest(
        ask_id=ask_id,
        session_id="s1",
        task_id=task_id,
        question="Choose an option",
        reason="Need a deterministic choice",
        suggested_options=(
            AskOption(option_id="yes", label="Yes"),
            AskOption(option_id="no", label="No"),
        ),
        answer_type="single_choice",
        allow_free_text=False,
        allow_no_option_with_text=False,
    )


def _text_ask(ask_id: str, *, task_id: str = "task-1") -> AskRequest:
    return AskRequest(
        ask_id=ask_id,
        session_id="s1",
        task_id=task_id,
        question="Provide text",
        reason="Need a textual answer",
        answer_type="free_text",
    )


def _answer(
    ask_id: str,
    *,
    selected: tuple[str, ...] = (),
    text: str | None = None,
) -> AskAnswer:
    return AskAnswer(
        ask_id=ask_id,
        session_id="s1",
        task_id="task-1",
        selected_option_ids=selected,
        text=text,
    )
