"""Tests for ThoughtStore Protocol and NullThoughtStore (1.2)."""

from __future__ import annotations

from code_agent.memory import NullThoughtStore, ThoughtRecord, ThoughtStore


def test_null_store_implements_protocol() -> None:
    store = NullThoughtStore()
    assert isinstance(store, ThoughtStore)


def test_null_store_drops_writes() -> None:
    store = NullThoughtStore()
    store.write(ThoughtRecord(event_id="abc", phase="plan", content="thinking..."))
    store.write(ThoughtRecord(event_id="def", phase="reflect", content="hmm"))
    assert len(store) == 0


def test_null_store_iter_yields_nothing() -> None:
    store = NullThoughtStore()
    store.write(ThoughtRecord(event_id="abc", phase="plan", content="x"))
    assert list(store.iter_for_event("abc")) == []


def test_thought_record_defaults() -> None:
    record = ThoughtRecord(event_id="abc", phase="plan", content="hello")
    assert record.metadata == {}
    assert record.timestamp.tzinfo is not None  # UTC-aware


def test_thought_record_is_frozen() -> None:
    import pytest
    from pydantic import ValidationError

    record = ThoughtRecord(event_id="abc", phase="plan", content="hello")
    with pytest.raises(ValidationError):
        record.content = "mutated"
