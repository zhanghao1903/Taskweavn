"""Tests for SqliteEventStream (Phase 3.1)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from taskweavn.core import EventStream, SqliteEventStream
from taskweavn.types.common import (
    AgentFinishAction,
    AgentFinishObservation,
    ErrorObservation,
)


def _action(answer: str = "done") -> AgentFinishAction:
    return AgentFinishAction(final_answer=answer)


def _observation(answer: str = "done") -> AgentFinishObservation:
    return AgentFinishObservation(final_answer=answer)


def test_protocol_conformance(tmp_path: Path) -> None:
    store = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        assert isinstance(store, EventStream)
    finally:
        store.close()


def test_append_and_iter_round_trip(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        a = _action("hello")
        o = _observation("hello")
        stream.append(a)
        stream.append(o)

        events = list(stream)
        assert len(events) == 2
        assert isinstance(events[0], AgentFinishAction)
        assert events[0].final_answer == "hello"
        assert isinstance(events[1], AgentFinishObservation)
        assert events[1].final_answer == "hello"
    finally:
        stream.close()


def test_event_id_and_timestamp_preserved(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        a = _action()
        stream.append(a)
        (got,) = list(stream)
        assert got.event_id == a.event_id
        assert got.timestamp == a.timestamp
    finally:
        stream.close()


def test_len(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        assert len(stream) == 0
        stream.append(_action())
        stream.append(_observation())
        assert len(stream) == 2
    finally:
        stream.close()


def test_persistence_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "events.sqlite"
    s1 = SqliteEventStream(db)
    a = _action("kept")
    s1.append(a)
    s1.close()

    s2 = SqliteEventStream(db)
    try:
        assert len(s2) == 1
        (got,) = list(s2)
        assert isinstance(got, AgentFinishAction)
        assert got.final_answer == "kept"
        assert got.event_id == a.event_id
    finally:
        s2.close()


def test_replay_filters_by_kind(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        stream.append(_action())
        stream.append(_observation())
        stream.append(
            ErrorObservation(error_type="boom", message="x")
        )
        kinds = [e.kind for e in stream.replay(kinds=["AgentFinishObservation"])]
        assert kinds == ["AgentFinishObservation"]
        kinds = [
            e.kind
            for e in stream.replay(
                kinds=["AgentFinishObservation", "ErrorObservation"]
            )
        ]
        assert sorted(kinds) == ["AgentFinishObservation", "ErrorObservation"]
    finally:
        stream.close()


def test_replay_filters_by_since(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        old_ts = datetime.now(UTC) - timedelta(hours=1)
        # Pydantic frozen — build a fresh instance via model_copy.
        a_old = _action("old").model_copy(update={"timestamp": old_ts})
        a_new = _action("new")
        stream.append(a_old)
        stream.append(a_new)

        cutoff = old_ts + timedelta(minutes=1)
        answers = [
            e.final_answer
            for e in stream.replay(since=cutoff)
            if isinstance(e, AgentFinishAction)
        ]
        assert answers == ["new"]
    finally:
        stream.close()


def test_replay_combines_filters(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        old_ts = datetime.now(UTC) - timedelta(hours=1)
        stream.append(_action("old").model_copy(update={"timestamp": old_ts}))
        stream.append(_action("new"))
        stream.append(_observation("obs"))

        cutoff = old_ts + timedelta(minutes=1)
        kinds = [
            e.kind
            for e in stream.replay(
                since=cutoff, kinds=["AgentFinishAction"]
            )
        ]
        assert kinds == ["AgentFinishAction"]
    finally:
        stream.close()


def test_iter_returns_in_insertion_order(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        ids = []
        for i in range(5):
            a = _action(f"step {i}")
            stream.append(a)
            ids.append(a.event_id)
        assert [e.event_id for e in stream] == ids
    finally:
        stream.close()


def test_close_idempotent(tmp_path: Path) -> None:
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    stream.close()
    stream.close()


def test_context_manager_closes_connection(tmp_path: Path) -> None:
    db = tmp_path / "events.sqlite"
    with SqliteEventStream(db) as stream:
        stream.append(_action())
    with pytest.raises(sqlite3.ProgrammingError):
        stream.append(_action())


def test_creates_parent_directory(tmp_path: Path) -> None:
    db = tmp_path / "deep" / "nest" / "events.sqlite"
    stream = SqliteEventStream(db)
    try:
        assert db.parent.is_dir()
        stream.append(_action())
        assert len(stream) == 1
    finally:
        stream.close()


# ---------------------------------------------------------------------------
# Phase 3.3 — task_id tagging and per-task replay.
# ---------------------------------------------------------------------------


def test_append_accepts_task_id_kwarg(tmp_path: Path) -> None:
    """``append(event, task_id=...)`` is the documented extension over the Protocol.

    Untagged appends keep working — the column defaults to NULL, and the
    Protocol-typed signature ``append(event)`` is still source-compatible.
    """
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        stream.append(_action("a"), task_id="task-1")
        stream.append(_action("b"))  # no kwarg → NULL row
        assert len(stream) == 2
    finally:
        stream.close()


def test_iter_for_task_filters(tmp_path: Path) -> None:
    """``iter_for_task`` returns only events tagged with the requested id, in order."""
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        stream.append(_action("first"), task_id="t1")
        stream.append(_action("other"), task_id="t2")
        stream.append(_observation("first-obs"), task_id="t1")
        stream.append(_action("again"), task_id="t2")

        t1_events = list(stream.iter_for_task("t1"))
        assert [getattr(e, "final_answer", None) for e in t1_events] == [
            "first",
            "first-obs",
        ]

        t2_events = list(stream.iter_for_task("t2"))
        assert [e.final_answer for e in t2_events if isinstance(e, AgentFinishAction)] == [
            "other",
            "again",
        ]
    finally:
        stream.close()


def test_iter_for_task_excludes_untagged(tmp_path: Path) -> None:
    """Rows with task_id=NULL must not leak into a per-task replay."""
    stream = SqliteEventStream(tmp_path / "events.sqlite")
    try:
        stream.append(_action("tagged"), task_id="t1")
        stream.append(_action("orphan"))  # NULL task_id

        tagged = [
            e.final_answer
            for e in stream.iter_for_task("t1")
            if isinstance(e, AgentFinishAction)
        ]
        assert tagged == ["tagged"]

        # An empty task id query returns nothing — NULLs do not match "".
        empty = list(stream.iter_for_task(""))
        assert empty == []
    finally:
        stream.close()


def test_task_id_column_added_on_pre_3_3_db(tmp_path: Path) -> None:
    """Open an old-shape DB, then re-open with the new code: ALTER TABLE runs."""
    db = tmp_path / "events.sqlite"

    # Hand-roll a pre-3.3 schema (no task_id column, no index).
    legacy = sqlite3.connect(str(db), isolation_level=None)
    legacy.execute(
        """
        CREATE TABLE events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id  TEXT    NOT NULL,
            kind      TEXT    NOT NULL,
            family    TEXT    NOT NULL,
            timestamp TEXT    NOT NULL,
            payload   TEXT    NOT NULL
        )
        """
    )
    legacy.execute(
        "INSERT INTO events(event_id, kind, family, timestamp, payload) "
        "VALUES (?, ?, ?, ?, ?)",
        ("legacy-id", "AgentFinishAction", "action", "2026-01-01T00:00:00+00:00",
         '{"event_id": "legacy-id", "timestamp": "2026-01-01T00:00:00+00:00", '
         '"final_answer": "legacy"}'),
    )
    legacy.close()

    # Re-open with the new code — migration must add the column.
    stream = SqliteEventStream(db)
    try:
        cur = stream._conn.execute("PRAGMA table_info(events)")  # noqa: SLF001
        column_names = {row[1] for row in cur.fetchall()}
        assert "task_id" in column_names

        # Existing row stays readable; its task_id is NULL, so iter_for_task
        # with any non-empty id returns nothing for it.
        assert len(stream) == 1
        assert list(stream.iter_for_task("anything")) == []

        # Newly tagged rows route correctly.
        stream.append(_action("post-migration"), task_id="t-after")
        post = [
            e.final_answer
            for e in stream.iter_for_task("t-after")
            if isinstance(e, AgentFinishAction)
        ]
        assert post == ["post-migration"]
    finally:
        stream.close()
