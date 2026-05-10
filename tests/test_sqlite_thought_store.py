"""Tests for SqliteThoughtStore (Phase 2.4)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from taskweavn.memory import (
    NullThoughtStore,
    SqliteThoughtStore,
    ThoughtRecord,
    ThoughtStore,
)


def _record(
    *,
    event_id: str = "ev-1",
    phase: str = "reason",
    content: str = "thinking...",
    metadata: dict[str, object] | None = None,
) -> ThoughtRecord:
    return ThoughtRecord(
        event_id=event_id,
        phase=phase,
        content=content,
        timestamp=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
        metadata=metadata or {},
    )


def test_protocol_conformance(tmp_path: Path) -> None:
    store = SqliteThoughtStore(tmp_path / "thoughts.sqlite")
    try:
        assert isinstance(store, ThoughtStore)
        # Null store also conforms — sanity-check the Protocol shape.
        assert isinstance(NullThoughtStore(), ThoughtStore)
    finally:
        store.close()


def test_write_and_iter_round_trip(tmp_path: Path) -> None:
    store = SqliteThoughtStore(tmp_path / "thoughts.sqlite")
    try:
        store.write(_record(event_id="ev-1", phase="plan", content="step 1"))
        store.write(_record(event_id="ev-1", phase="reason", content="step 2"))
        store.write(_record(event_id="ev-2", phase="plan", content="other"))

        ev1 = list(store.iter_for_event("ev-1"))
        assert [r.content for r in ev1] == ["step 1", "step 2"]
        assert [r.phase for r in ev1] == ["plan", "reason"]

        ev2 = list(store.iter_for_event("ev-2"))
        assert [r.content for r in ev2] == ["other"]

        assert len(store) == 3
    finally:
        store.close()


def test_phase_allow_list_filters_writes(tmp_path: Path) -> None:
    store = SqliteThoughtStore(
        tmp_path / "thoughts.sqlite", phases=["plan", "reflect"]
    )
    try:
        store.write(_record(phase="plan", content="kept"))
        store.write(_record(phase="reason", content="dropped"))
        store.write(_record(phase="reflect", content="kept2"))

        assert len(store) == 2
        contents = [r.content for r in store.iter_for_event("ev-1")]
        assert contents == ["kept", "kept2"]
    finally:
        store.close()


def test_metadata_round_trips_as_json(tmp_path: Path) -> None:
    store = SqliteThoughtStore(tmp_path / "thoughts.sqlite")
    try:
        store.write(
            _record(metadata={"score": 0.9, "labels": ["a", "b"], "nested": {"k": 1}})
        )
        (got,) = list(store.iter_for_event("ev-1"))
        assert got.metadata == {"score": 0.9, "labels": ["a", "b"], "nested": {"k": 1}}
    finally:
        store.close()


def test_persistence_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "thoughts.sqlite"
    store = SqliteThoughtStore(db)
    store.write(_record(content="persisted"))
    store.close()

    reopened = SqliteThoughtStore(db)
    try:
        assert len(reopened) == 1
        (got,) = list(reopened.iter_for_event("ev-1"))
        assert got.content == "persisted"
    finally:
        reopened.close()


def test_iter_returns_empty_for_unknown_event(tmp_path: Path) -> None:
    store = SqliteThoughtStore(tmp_path / "thoughts.sqlite")
    try:
        assert list(store.iter_for_event("missing")) == []
    finally:
        store.close()


def test_context_manager_closes_connection(tmp_path: Path) -> None:
    db = tmp_path / "thoughts.sqlite"
    with SqliteThoughtStore(db) as store:
        store.write(_record())
    # After exit the connection should be closed; further use raises.
    with pytest.raises(sqlite3.ProgrammingError):
        store.write(_record())


def test_close_is_idempotent(tmp_path: Path) -> None:
    store = SqliteThoughtStore(tmp_path / "thoughts.sqlite")
    store.close()
    store.close()  # second call must not raise


def test_creates_parent_directory(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "dirs" / "thoughts.sqlite"
    store = SqliteThoughtStore(db)
    try:
        assert db.parent.is_dir()
        store.write(_record())
        assert len(store) == 1
    finally:
        store.close()


def test_db_path_property(tmp_path: Path) -> None:
    db = tmp_path / "thoughts.sqlite"
    store = SqliteThoughtStore(db)
    try:
        assert store.db_path == db
    finally:
        store.close()
