"""Tests for InMemoryEventStream (1.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from taskweavn.core import EventStream, InMemoryEventStream
from taskweavn.types import BaseAction, BaseObservation


class _NoteAction(BaseAction):
    text: str


class _NoteObservation(BaseObservation):
    echoed: str


def test_implements_protocol() -> None:
    stream = InMemoryEventStream()
    assert isinstance(stream, EventStream)


def test_append_and_len() -> None:
    stream = InMemoryEventStream()
    assert len(stream) == 0
    stream.append(_NoteAction(text="a"))
    stream.append(_NoteAction(text="b"))
    assert len(stream) == 2


def test_iter_returns_events_in_append_order() -> None:
    stream = InMemoryEventStream()
    a = _NoteAction(text="first")
    b = _NoteAction(text="second")
    c = _NoteObservation(echoed="ack", action_id=a.event_id)
    for ev in (a, b, c):
        stream.append(ev)

    assert [ev.event_id for ev in stream] == [a.event_id, b.event_id, c.event_id]


def test_iter_is_a_snapshot() -> None:
    """Appending after starting iteration must not affect the active iterator."""
    stream = InMemoryEventStream()
    stream.append(_NoteAction(text="one"))
    iterator = iter(stream)
    stream.append(_NoteAction(text="two"))
    items = list(iterator)
    assert len(items) == 1
    # ...but a fresh iter sees both.
    assert len(list(stream)) == 2


def test_replay_filters_by_kind() -> None:
    stream = InMemoryEventStream()
    a = _NoteAction(text="x")
    b = _NoteObservation(echoed="y", action_id=a.event_id)
    stream.append(a)
    stream.append(b)

    only_actions = list(stream.replay(kinds=["_NoteAction"]))
    assert [ev.event_id for ev in only_actions] == [a.event_id]

    only_obs = list(stream.replay(kinds=["_NoteObservation"]))
    assert [ev.event_id for ev in only_obs] == [b.event_id]


def test_replay_filters_by_since() -> None:
    stream = InMemoryEventStream()
    a = _NoteAction(text="old")
    stream.append(a)
    cutoff = datetime.now(UTC) + timedelta(microseconds=1)
    # Sleep semantics: use a known later timestamp by constructing a new event
    # whose default timestamp is after `cutoff`.
    later_event = _NoteAction(
        text="new",
        timestamp=cutoff + timedelta(seconds=1),
    )
    stream.append(later_event)

    fresh = list(stream.replay(since=cutoff))
    assert [ev.event_id for ev in fresh] == [later_event.event_id]


def test_replay_with_no_filters_returns_everything() -> None:
    stream = InMemoryEventStream()
    events = [_NoteAction(text=str(i)) for i in range(3)]
    for ev in events:
        stream.append(ev)
    assert [ev.event_id for ev in stream.replay()] == [ev.event_id for ev in events]
