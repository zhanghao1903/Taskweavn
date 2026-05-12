"""Tests for SqliteMessageStream (Phase 3.3).

Covers the four aggregation axes from design doc §7.1.1 plus relationship
queries (parent / response / thread / pending). Aggregation correctness is
the headline verification target — if any of these break, the message-table
contract is broken.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from taskweavn.interaction import (
    AgentMessage,
    MessageStream,
    MessageStreamError,
    RiskAssessment,
    SqliteMessageStream,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def stream(tmp_path: Path) -> SqliteMessageStream:
    return SqliteMessageStream(tmp_path / "messages.sqlite")


def _msg(
    *,
    session: str = "sess1",
    task: str | None = "task-A",
    agent: str = "agent",
    type_: str = "informational",
    content: str = "x",
    parent: str | None = None,
    risk: RiskAssessment | None = None,
    related_action: str | None = None,
    requires_response: bool = False,
    response_source: str | None = None,
    response_value: str | None = None,
    created_at: datetime | None = None,
) -> AgentMessage:
    kwargs: dict[str, object] = {
        "session_id": session,
        "task_id": task,
        "agent_id": agent,
        "message_type": type_,
        "content": content,
        "parent_message_id": parent,
        "risk_assessment": risk,
        "related_action_id": related_action,
        "requires_response": requires_response,
        "response_source": response_source,
        "response_value": response_value,
    }
    if created_at is not None:
        kwargs["created_at"] = created_at
    return AgentMessage.model_validate(kwargs)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_stream_satisfies_protocol(stream: SqliteMessageStream) -> None:
    assert isinstance(stream, MessageStream)


# ---------------------------------------------------------------------------
# Persistence + round-trip
# ---------------------------------------------------------------------------


def test_round_trip_preserves_all_fields(stream: SqliteMessageStream) -> None:
    risk = RiskAssessment(
        baseline=0.5, dynamic=0.8, rationale=("llm flagged",), assessor="llm"
    )
    original = _msg(
        type_="actionable",
        content="ok to delete?",
        requires_response=True,
        risk=risk,
        related_action="evt-123",
    )
    stream._insert(original)
    fetched = stream.get(original.message_id)
    assert fetched is not None
    assert fetched == original


def test_persistence_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "messages.sqlite"
    s1 = SqliteMessageStream(db)
    m = _msg(content="kept")
    s1._insert(m)
    s1.close()

    s2 = SqliteMessageStream(db)
    try:
        assert len(s2) == 1
        got = s2.get(m.message_id)
        assert got is not None
        assert got.content == "kept"
    finally:
        s2.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    s = SqliteMessageStream(tmp_path / "m.sqlite")
    s.close()
    s.close()


def test_context_manager(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    with SqliteMessageStream(db) as s:
        s._insert(_msg())
    with pytest.raises(sqlite3.ProgrammingError):
        s._insert(_msg())


def test_creates_parent_dir(tmp_path: Path) -> None:
    db = tmp_path / "deep" / "nest" / "messages.sqlite"
    s = SqliteMessageStream(db)
    try:
        assert db.parent.is_dir()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Aggregation: session × time
# ---------------------------------------------------------------------------


def test_list_for_session_orders_by_time_then_id(
    stream: SqliteMessageStream,
) -> None:
    # Three messages with the *same* timestamp — id breaks the tie.
    same = datetime.now(UTC).replace(microsecond=0)
    a = _msg(content="a", created_at=same)
    b = _msg(content="b", created_at=same)
    c = _msg(content="c", created_at=same)
    stream._insert(a)
    stream._insert(b)
    stream._insert(c)

    contents = [m.content for m in stream.list_for_session("sess1")]
    assert contents == ["a", "b", "c"]


def test_list_for_session_filters_by_type(stream: SqliteMessageStream) -> None:
    stream._insert(_msg(type_="informational", content="info"))
    p = _msg(type_="actionable", content="ask", requires_response=True)
    stream._insert(p)
    stream._insert(
        _msg(
            type_="response",
            content="yes",
            parent=p.message_id,
            agent="user",
            response_source="user",
            response_value="yes",
        )
    )

    only_actionable = list(stream.list_for_session("sess1", types=["actionable"]))
    assert [m.content for m in only_actionable] == ["ask"]


def test_list_for_session_filters_since(stream: SqliteMessageStream) -> None:
    old = datetime.now(UTC) - timedelta(hours=1)
    stream._insert(_msg(content="old", created_at=old))
    time.sleep(0.001)
    stream._insert(_msg(content="new"))
    cutoff = old + timedelta(minutes=1)
    contents = [m.content for m in stream.list_for_session("sess1", since=cutoff)]
    assert contents == ["new"]


def test_list_for_session_isolates_by_session(
    stream: SqliteMessageStream,
) -> None:
    stream._insert(_msg(session="sess1", content="a"))
    stream._insert(_msg(session="sess2", content="b"))
    s1 = [m.content for m in stream.list_for_session("sess1")]
    s2 = [m.content for m in stream.list_for_session("sess2")]
    assert s1 == ["a"]
    assert s2 == ["b"]


def test_list_for_session_limit(stream: SqliteMessageStream) -> None:
    for i in range(5):
        stream._insert(_msg(content=f"m{i}"))
    contents = [m.content for m in stream.list_for_session("sess1", limit=3)]
    assert contents == ["m0", "m1", "m2"]


# ---------------------------------------------------------------------------
# Aggregation: task × time
# ---------------------------------------------------------------------------


def test_list_for_task_pulls_only_that_task(stream: SqliteMessageStream) -> None:
    stream._insert(_msg(task="task-A", content="a1"))
    stream._insert(_msg(task="task-B", content="b1"))
    stream._insert(_msg(task="task-A", content="a2"))
    contents = [m.content for m in stream.list_for_task("task-A")]
    assert contents == ["a1", "a2"]


def test_list_for_task_spans_sessions(stream: SqliteMessageStream) -> None:
    """Phase 4 multi-agent: one task, multiple sessions.

    Even with Phase 3 single-session reality, the index supports the read,
    so we lock that contract here.
    """
    stream._insert(_msg(session="sessA", task="task-XYZ", content="from-A"))
    stream._insert(_msg(session="sessB", task="task-XYZ", content="from-B"))
    contents = [m.content for m in stream.list_for_task("task-XYZ")]
    assert sorted(contents) == ["from-A", "from-B"]


# ---------------------------------------------------------------------------
# Aggregation: agent × time
# ---------------------------------------------------------------------------


def test_list_for_agent(stream: SqliteMessageStream) -> None:
    stream._insert(_msg(agent="agent", content="a1"))
    p = _msg(agent="agent", type_="actionable", content="ask")
    stream._insert(p)
    stream._insert(
        _msg(
            agent="user",
            type_="response",
            content="yes",
            parent=p.message_id,
            response_source="user",
            response_value="yes",
        )
    )
    user_msgs = [m.content for m in stream.list_for_agent("user")]
    assert user_msgs == ["yes"]
    agent_msgs = [m.content for m in stream.list_for_agent("agent")]
    assert agent_msgs == ["a1", "ask"]


def test_list_for_agent_with_session_filter(stream: SqliteMessageStream) -> None:
    stream._insert(_msg(session="sess1", agent="agent", content="a"))
    stream._insert(_msg(session="sess2", agent="agent", content="b"))
    only = [
        m.content
        for m in stream.list_for_agent("agent", session_id="sess2")
    ]
    assert only == ["b"]


# ---------------------------------------------------------------------------
# Relationship queries
# ---------------------------------------------------------------------------


def test_pending_actionable_excludes_answered(
    stream: SqliteMessageStream,
) -> None:
    p1 = _msg(type_="actionable", content="ask1", requires_response=True)
    p2 = _msg(type_="actionable", content="ask2", requires_response=True)
    stream._insert(p1)
    stream._insert(p2)
    stream._insert(
        _msg(
            type_="response",
            content="yes",
            parent=p1.message_id,
            agent="user",
            response_source="user",
            response_value="yes",
        )
    )
    pending = stream.pending_actionable("sess1")
    assert [m.content for m in pending] == ["ask2"]


def test_pending_actionable_with_task_filter(stream: SqliteMessageStream) -> None:
    stream._insert(
        _msg(task="task-A", type_="actionable", content="A-ask")
    )
    stream._insert(
        _msg(task="task-B", type_="actionable", content="B-ask")
    )
    pending_a = stream.pending_actionable("sess1", task_id="task-A")
    assert [m.content for m in pending_a] == ["A-ask"]


def test_response_for_returns_first(stream: SqliteMessageStream) -> None:
    p = _msg(type_="actionable", content="ask")
    stream._insert(p)
    first = _msg(
        type_="response",
        content="initial",
        parent=p.message_id,
        agent="user",
        response_source="user",
        response_value="initial",
    )
    stream._insert(first)
    # Second response — e.g. a retract — kept on the table for audit.
    time.sleep(0.001)
    stream._insert(
        _msg(
            type_="response",
            content="<RETRACT>",
            parent=p.message_id,
            agent="user",
            response_source="user",
            response_value="<RETRACT>",
        )
    )
    got = stream.response_for(p.message_id)
    assert got is not None
    assert got.message_id == first.message_id


def test_response_for_returns_none_when_pending(
    stream: SqliteMessageStream,
) -> None:
    p = _msg(type_="actionable", content="ask")
    stream._insert(p)
    assert stream.response_for(p.message_id) is None


def test_thread_returns_anchor_plus_replies(
    stream: SqliteMessageStream,
) -> None:
    p = _msg(type_="actionable", content="ask")
    stream._insert(p)
    r = _msg(
        type_="response",
        content="yes",
        parent=p.message_id,
        agent="user",
        response_source="user",
        response_value="yes",
    )
    stream._insert(r)
    items = stream.thread(p.message_id)
    assert [m.message_id for m in items] == [p.message_id, r.message_id]


# ---------------------------------------------------------------------------
# Write integrity
# ---------------------------------------------------------------------------


def test_response_requires_existing_parent(stream: SqliteMessageStream) -> None:
    orphan = _msg(
        type_="response",
        content="yes",
        parent="does-not-exist",
        agent="user",
        response_source="user",
        response_value="yes",
    )
    with pytest.raises(MessageStreamError, match="not found"):
        stream._insert(orphan)


def test_response_requires_parent_set(stream: SqliteMessageStream) -> None:
    with pytest.raises(MessageStreamError, match="parent_message_id"):
        stream._insert(
            _msg(
                type_="response",
                content="yes",
                parent=None,
                agent="user",
                response_source="user",
                response_value="yes",
            )
        )


def test_response_parent_must_be_actionable(
    stream: SqliteMessageStream,
) -> None:
    info = _msg(type_="informational", content="hi")
    stream._insert(info)
    with pytest.raises(MessageStreamError, match="actionable"):
        stream._insert(
            _msg(
                type_="response",
                content="huh",
                parent=info.message_id,
                agent="user",
                response_source="user",
                response_value="huh",
            )
        )


def test_duplicate_message_id_rejected(stream: SqliteMessageStream) -> None:
    m = _msg()
    stream._insert(m)
    with pytest.raises(MessageStreamError, match="already exists"):
        stream._insert(m)


# ---------------------------------------------------------------------------
# Cross-stream join (events ⊕ messages by task_id)
# ---------------------------------------------------------------------------


def test_messages_filterable_by_task_for_cross_stream_join(
    stream: SqliteMessageStream,
) -> None:
    """Locks the contract that messages can be enumerated by task — the
    other half of the join (events.iter_for_task) is tested in
    test_sqlite_event_stream.py."""
    stream._insert(_msg(task="run1", content="m1"))
    stream._insert(_msg(task="run2", content="m2"))
    contents = [m.content for m in stream.list_for_task("run1")]
    assert contents == ["m1"]
