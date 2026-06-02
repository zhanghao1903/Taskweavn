"""Tests for Plato UI SSE event helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.server import (
    ResyncOnlyEventSource,
    SqliteUiEventSource,
    StaticUiEventSource,
    UiEventSourceError,
    UiEventStore,
    sse_frame,
    sse_stream,
)
from taskweavn.server.ui_contract import UiEvent
from taskweavn.task import TaskRef


def test_sse_frame_serializes_event_with_alias_json() -> None:
    event = UiEvent(
        event_id="event-1",
        session_id="session-1",
        event_type="message.appended",
        cursor="cursor-1",
        task_node_ids=("task-1",),
        task_refs=(TaskRef.draft("task-1"),),
        message_ids=("message-1",),
    )

    frame = sse_frame(event)

    assert frame.startswith("id: cursor-1\nevent: message.appended\ndata: ")
    assert '"eventId":"event-1"' in frame
    assert '"taskNodeIds":["task-1"]' in frame
    assert frame.endswith("\n\n")


def test_sse_stream_concatenates_frames() -> None:
    first = UiEvent(session_id="session-1", event_type="message.appended", cursor="c1")
    second = UiEvent(session_id="session-1", event_type="command.completed", cursor="c2")

    stream = sse_stream((first, second))

    assert stream.count("\n\n") == 2
    assert "event: message.appended" in stream
    assert "event: command.completed" in stream


def test_static_event_source_replays_after_cursor_and_resyncs_unknown_cursor() -> None:
    first = UiEvent(session_id="session-1", event_type="message.appended", cursor="c1")
    second = UiEvent(session_id="session-1", event_type="command.completed", cursor="c2")
    other = UiEvent(session_id="session-2", event_type="message.appended", cursor="c3")
    source = StaticUiEventSource((first, second, other))

    replay = tuple(source.subscribe("session-1", cursor="c1"))
    resync = tuple(source.subscribe("session-1", cursor="missing"))

    assert replay == (second,)
    assert len(resync) == 1
    assert resync[0].event_type == "session.resync_required"
    assert resync[0].cursor == "missing"


def test_sqlite_ui_event_source_protocol_conformance(tmp_path: Path) -> None:
    source = SqliteUiEventSource(tmp_path / "ui_events.sqlite")
    try:
        assert isinstance(source, UiEventStore)
    finally:
        source.close()


def test_sqlite_ui_event_source_persists_and_replays_after_cursor(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ui_events.sqlite"
    first = UiEvent(
        event_id="event-1",
        session_id="session-1",
        event_type="message.appended",
        cursor="cursor-1",
    )
    second = UiEvent(
        event_id="event-2",
        session_id="session-1",
        event_type="audit.records_changed",
        cursor="cursor-2",
    )
    other = UiEvent(
        event_id="event-3",
        session_id="session-2",
        event_type="audit.records_changed",
        cursor="cursor-3",
    )
    source = SqliteUiEventSource(db_path)
    try:
        source.append(first)
        source.append(second)
        source.append(other)
    finally:
        source.close()

    reopened = SqliteUiEventSource(db_path)
    try:
        replay = tuple(reopened.subscribe("session-1", cursor="cursor-1"))
        all_events = tuple(reopened.subscribe("session-1"))
    finally:
        reopened.close()

    assert replay == (second,)
    assert all_events == (first, second)


def test_sqlite_ui_event_source_resyncs_unknown_cursor(tmp_path: Path) -> None:
    source = SqliteUiEventSource(tmp_path / "ui_events.sqlite")
    try:
        events = tuple(source.subscribe("session-1", cursor="missing"))
    finally:
        source.close()

    assert len(events) == 1
    assert events[0].event_type == "session.resync_required"
    assert events[0].cursor == "missing"
    assert (
        events[0].payload["reason"]
        == "cursor is not available in workspace UI event source"
    )


def test_sqlite_ui_event_source_replays_session_events_after_unknown_cursor(
    tmp_path: Path,
) -> None:
    source = SqliteUiEventSource(tmp_path / "ui_events.sqlite")
    try:
        first = source.append(
            UiEvent(
                event_id="event-1",
                session_id="session-1",
                event_type="message.appended",
                cursor="cursor-1",
            )
        )
        second = source.append(
            UiEvent(
                event_id="event-2",
                session_id="session-1",
                event_type="audit.records_changed",
                cursor="cursor-2",
            )
        )
        source.append(
            UiEvent(
                event_id="event-3",
                session_id="session-2",
                event_type="audit.records_changed",
                cursor="cursor-3",
            )
        )
        events = tuple(source.subscribe("session-1", cursor="snapshot:session-1"))
    finally:
        source.close()

    assert [event.event_type for event in events] == [
        "session.resync_required",
        "message.appended",
        "audit.records_changed",
    ]
    assert events[0].cursor == "snapshot:session-1"
    assert events[1:] == (first, second)


def test_sqlite_ui_event_source_rejects_duplicate_session_cursor(
    tmp_path: Path,
) -> None:
    source = SqliteUiEventSource(tmp_path / "ui_events.sqlite")
    try:
        source.append(
            UiEvent(
                event_id="event-1",
                session_id="session-1",
                event_type="message.appended",
                cursor="cursor-1",
            )
        )
        with pytest.raises(UiEventSourceError):
            source.append(
                UiEvent(
                    event_id="event-2",
                    session_id="session-1",
                    event_type="audit.records_changed",
                    cursor="cursor-1",
                )
            )
    finally:
        source.close()


def test_resync_only_event_source_uses_fallback_cursor_without_input_cursor() -> None:
    source = ResyncOnlyEventSource(reason="not wired")

    events = tuple(source.subscribe("session-1"))

    assert len(events) == 1
    assert events[0].event_type == "session.resync_required"
    assert events[0].cursor == "resync:session-1"
    assert events[0].payload["reason"] == "not wired"
