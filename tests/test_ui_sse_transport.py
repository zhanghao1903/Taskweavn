"""Tests for Plato UI SSE event helpers."""

from __future__ import annotations

from taskweavn.server import ResyncOnlyEventSource, StaticUiEventSource, sse_frame, sse_stream
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


def test_resync_only_event_source_uses_fallback_cursor_without_input_cursor() -> None:
    source = ResyncOnlyEventSource(reason="not wired")

    events = tuple(source.subscribe("session-1"))

    assert len(events) == 1
    assert events[0].event_type == "session.resync_required"
    assert events[0].cursor == "resync:session-1"
    assert events[0].payload["reason"] == "not wired"
