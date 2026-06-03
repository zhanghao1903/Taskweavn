"""Tests for derived ``Session.status`` (Phase 3.8).

The deriver is a pure read over (event_stream, message_stream, stored
status). Each test sets up a small scenario and asserts the rule it
exercises:

    scenario                                          → expected status
    ───────────────────────────────────────────────────────────────────
    fresh session, empty streams                       → active
    last event is AgentFinishObservation               → finished
    AgentFinishObservation followed by another action  → active
    open confirmation/actionable on the bus            → awaiting_user
    open confirmation/actionable + finish event        → awaiting_user
    stored status == archived                          → archived (sticky)
    archived overrides every other signal              → archived
"""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.core import (
    InMemoryEventStream,
    Session,
    SessionManager,
    WorkspaceLayout,
    derive_session_status,
)
from taskweavn.interaction import (
    AgentMessage,
    InProcessMessageBus,
    SqliteMessageStream,
)
from taskweavn.types.common import AgentFinishAction, AgentFinishObservation

# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------


@pytest.fixture
def manager(tmp_path: Path) -> SessionManager:
    return SessionManager(WorkspaceLayout(tmp_path))


@pytest.fixture
def stream_and_bus(
    tmp_path: Path,
) -> tuple[SqliteMessageStream, InProcessMessageBus]:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus = InProcessMessageBus(stream)
    return stream, bus


def _archived(session: Session) -> Session:
    """Return a copy of ``session`` with stored status == archived. The
    SessionManager has its own :meth:`mark_status` for this; the helper just
    avoids round-tripping through SQL when the test only cares about the
    in-memory hint."""
    return Session(
        id=session.id,
        name=session.name,
        workspace_root=session.workspace_root,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
        status="archived",
    )


# ---------------------------------------------------------------------------
# Default / active
# ---------------------------------------------------------------------------


def test_fresh_session_with_empty_streams_is_active(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """A brand-new session that has emitted nothing and asked nothing is
    ``active``. This is the rule-4 fallback."""
    stream, _bus = stream_and_bus
    session = manager.create("fresh")
    assert (
        derive_session_status(
            session, event_stream=InMemoryEventStream(), message_stream=stream
        )
        == "active"
    )


# ---------------------------------------------------------------------------
# finished
# ---------------------------------------------------------------------------


def test_finished_when_last_event_is_finish_observation(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    stream, _bus = stream_and_bus
    session = manager.create("done")
    events = InMemoryEventStream()
    finish = AgentFinishAction(final_answer="all set")
    events.append(finish)
    events.append(
        AgentFinishObservation(action_id=finish.event_id, final_answer="all set")
    )
    assert (
        derive_session_status(session, event_stream=events, message_stream=stream)
        == "finished"
    )


def test_finished_flips_back_to_active_when_new_action_appended(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """Critical: ``finished`` is determined by the *last* event, not by 'has
    ever finished'. A new task on the same session must read as ``active``
    or the resume story breaks."""
    stream, _bus = stream_and_bus
    session = manager.create("resumed")
    events = InMemoryEventStream()
    finish = AgentFinishAction(final_answer="task 1 done")
    events.append(finish)
    events.append(
        AgentFinishObservation(action_id=finish.event_id, final_answer="task 1 done")
    )
    # New task picks up where the last one left off.
    events.append(AgentFinishAction(final_answer="task 2 in flight"))
    assert (
        derive_session_status(session, event_stream=events, message_stream=stream)
        == "active"
    )


# ---------------------------------------------------------------------------
# awaiting_user
# ---------------------------------------------------------------------------


def test_awaiting_user_when_actionable_is_pending(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    stream, bus = stream_and_bus
    session = manager.create("blocked")
    bus.publish(
        AgentMessage(
            session_id=session.id,
            message_type="actionable",
            content="proceed?",
            requires_response=True,
        )
    )
    assert (
        derive_session_status(
            session, event_stream=InMemoryEventStream(), message_stream=stream
        )
        == "awaiting_user"
    )


def test_actionable_with_response_is_no_longer_awaiting(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """Once a ``response`` arrives, the actionable is closed — derivation
    drops back to active. Verifies our reliance on
    ``MessageStream.pending_actionable`` (which anti-joins on parent_id)."""
    stream, bus = stream_and_bus
    session = manager.create("answered")
    actionable = AgentMessage(
        session_id=session.id,
        message_type="actionable",
        content="proceed?",
        requires_response=True,
    )
    bus.publish(actionable)
    bus.publish(
        AgentMessage(
            session_id=session.id,
            message_type="response",
            content="yes",
            parent_message_id=actionable.message_id,
            response_source="user",
            response_value="yes",
        )
    )
    assert (
        derive_session_status(
            session, event_stream=InMemoryEventStream(), message_stream=stream
        )
        == "active"
    )


def test_awaiting_user_wins_over_finish(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """If a session ended on a finish observation but also left an open
    confirmation/actionable on the bus, the user-facing truth is 'we're
    waiting on you'. Rule 2 deliberately runs before rule 3."""
    stream, bus = stream_and_bus
    session = manager.create("ambiguous")
    events = InMemoryEventStream()
    finish = AgentFinishAction(final_answer="kind of done")
    events.append(finish)
    events.append(
        AgentFinishObservation(action_id=finish.event_id, final_answer="kind of done")
    )
    bus.publish(
        AgentMessage(
            session_id=session.id,
            message_type="actionable",
            content="one more thing?",
            requires_response=True,
        )
    )
    assert (
        derive_session_status(session, event_stream=events, message_stream=stream)
        == "awaiting_user"
    )


def test_actionable_for_other_session_does_not_leak(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """Pending-actionable lookup is session-scoped; an open confirmation for
    a sibling session must not flip *this* session into awaiting_user."""
    stream, bus = stream_and_bus
    sess_a = manager.create("a")
    sess_b = manager.create("b")
    bus.publish(
        AgentMessage(
            session_id=sess_b.id,
            message_type="actionable",
            content="for b",
            requires_response=True,
        )
    )
    assert (
        derive_session_status(
            sess_a, event_stream=InMemoryEventStream(), message_stream=stream
        )
        == "active"
    )


# ---------------------------------------------------------------------------
# archived (sticky override)
# ---------------------------------------------------------------------------


def test_archived_status_is_sticky(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    stream, _bus = stream_and_bus
    session = _archived(manager.create("old"))
    assert (
        derive_session_status(
            session, event_stream=InMemoryEventStream(), message_stream=stream
        )
        == "archived"
    )


def test_archived_beats_pending_actionable(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """Even if there's an unanswered question on the bus, an archived
    session reports ``archived`` — the user has explicitly walked away."""
    stream, bus = stream_and_bus
    session = _archived(manager.create("archived-then-poked"))
    bus.publish(
        AgentMessage(
            session_id=session.id,
            message_type="actionable",
            content="hi?",
            requires_response=True,
        )
    )
    assert (
        derive_session_status(
            session, event_stream=InMemoryEventStream(), message_stream=stream
        )
        == "archived"
    )


def test_archived_beats_finished(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    stream, _bus = stream_and_bus
    session = _archived(manager.create("done-and-archived"))
    events = InMemoryEventStream()
    finish = AgentFinishAction(final_answer="done")
    events.append(finish)
    events.append(
        AgentFinishObservation(action_id=finish.event_id, final_answer="done")
    )
    assert (
        derive_session_status(session, event_stream=events, message_stream=stream)
        == "archived"
    )


# ---------------------------------------------------------------------------
# Stored hint integration via SessionManager
# ---------------------------------------------------------------------------


def test_mark_status_archived_round_trips_to_derivation(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """End-to-end: an archive call through the manager persists the override,
    re-fetches the session, and the deriver still reports ``archived``."""
    stream, _bus = stream_and_bus
    session = manager.create("to-archive")
    manager.mark_status(session.id, "archived")
    refetched = manager.require(session.id)
    assert refetched.status == "archived"
    assert (
        derive_session_status(
            refetched, event_stream=InMemoryEventStream(), message_stream=stream
        )
        == "archived"
    )


def test_stored_active_does_not_force_active(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """The whole point of the deriver: even when the SQL hint says
    ``active`` (the create-time default), if the streams say ``finished``
    the deriver returns ``finished``. The hint never wins outside of
    ``archived``."""
    stream, _bus = stream_and_bus
    session = manager.create("stale-hint")
    assert session.status == "active"  # stored hint
    events = InMemoryEventStream()
    finish = AgentFinishAction(final_answer="done")
    events.append(finish)
    events.append(
        AgentFinishObservation(action_id=finish.event_id, final_answer="done")
    )
    assert (
        derive_session_status(session, event_stream=events, message_stream=stream)
        == "finished"
    )


# ---------------------------------------------------------------------------
# Smoke: a non-finish observation as the tail does NOT trip rule 3
# ---------------------------------------------------------------------------


def test_other_observations_at_tail_do_not_count_as_finished(
    manager: SessionManager,
    stream_and_bus: tuple[SqliteMessageStream, InProcessMessageBus],
) -> None:
    """A loose ``BaseObservation`` (e.g. a tool result) at the tail of the
    stream must not be mistaken for ``AgentFinishObservation``. The isinstance
    check is exact-class on purpose."""
    from taskweavn.types import BaseAction, BaseObservation

    class _StatusTestAction(BaseAction):
        text: str

    class _StatusTestObs(BaseObservation):
        echoed: str

    stream, _bus = stream_and_bus
    session = manager.create("midstream")
    events = InMemoryEventStream()
    a = _StatusTestAction(text="hello")
    events.append(a)
    events.append(_StatusTestObs(echoed="hi", action_id=a.event_id))
    assert (
        derive_session_status(session, event_stream=events, message_stream=stream)
        == "active"
    )
