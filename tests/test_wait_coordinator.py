"""Tests for WaitCoordinator (Phase 3.5).

Drives the coordinator with a real :class:`InProcessMessageBus` so the
sync/async + timeout-action × notify_on_proceed matrix is exercised
end-to-end. The bus is the same one the AgentLoop will use.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from taskweavn.interaction import (
    AUTONOMY_PRESETS,
    AgentMessage,
    InProcessMessageBus,
    SqliteMessageStream,
    WaitCoordinator,
    WaitOutcome,
    WaitResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bus(tmp_path: Path) -> Iterator[InProcessMessageBus]:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    b = InProcessMessageBus(stream)
    try:
        yield b
    finally:
        b.close()
        stream.close()


def _publish_actionable(
    bus: InProcessMessageBus,
    *,
    timeout_seconds: float | None = None,
    options: list[str] | None = None,
) -> AgentMessage:
    msg = AgentMessage(
        session_id="s",
        message_type="actionable",
        content="ok?",
        action_options=options or [],
        requires_response=True,
        timeout_seconds=timeout_seconds,
    )
    bus.publish(msg)
    return msg


# ---------------------------------------------------------------------------
# async strategy
# ---------------------------------------------------------------------------


def test_async_returns_pending_immediately(bus: InProcessMessageBus) -> None:
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["full_auto"])
    msg = _publish_actionable(bus)
    start = time.monotonic()
    result = coord.handle_actionable(msg)
    assert (time.monotonic() - start) < 0.05
    assert result.outcome == WaitOutcome.PENDING
    assert result.response_value is None
    assert result.response_source is None
    assert result.notice is None


def test_async_does_not_publish_anything(bus: InProcessMessageBus) -> None:
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["full_auto"])
    msg = _publish_actionable(bus)
    before = len(bus.stream)
    coord.handle_actionable(msg)
    assert len(bus.stream) == before  # PENDING means "do nothing"


# ---------------------------------------------------------------------------
# sync — happy path
# ---------------------------------------------------------------------------


def test_sync_got_response(bus: InProcessMessageBus) -> None:
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    msg = _publish_actionable(bus, timeout_seconds=2.0)

    def reply() -> None:
        time.sleep(0.05)
        bus.publish(
            AgentMessage(
                session_id="s",
                message_type="response",
                content="yes",
                parent_message_id=msg.message_id,
                response_source="user",
                response_value="yes",
            )
        )

    t = threading.Thread(target=reply)
    t.start()
    try:
        result = coord.handle_actionable(msg)
    finally:
        t.join()

    assert result.outcome == WaitOutcome.GOT_RESPONSE
    assert result.response_value == "yes"
    assert result.response_source == "user"
    assert result.response is not None and result.response.parent_message_id == msg.message_id
    assert result.notice is None  # only timeouts publish notices


# ---------------------------------------------------------------------------
# sync — timeout_action="proceed_default"
# ---------------------------------------------------------------------------


def test_sync_timeout_proceed_default_picks_first_option(
    bus: InProcessMessageBus,
) -> None:
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    msg = _publish_actionable(bus, timeout_seconds=0.05, options=["yes", "no"])
    result = coord.handle_actionable(msg)
    assert result.outcome == WaitOutcome.TIMED_OUT_PROCEED
    assert result.response_value == "yes"
    assert result.response_source == "timeout_default"


def test_sync_timeout_proceed_default_no_options_value_is_none(
    bus: InProcessMessageBus,
) -> None:
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    msg = _publish_actionable(bus, timeout_seconds=0.05)  # no options
    result = coord.handle_actionable(msg)
    assert result.outcome == WaitOutcome.TIMED_OUT_PROCEED
    assert result.response_value is None
    assert result.response_source == "timeout_default"


def test_sync_timeout_publishes_notice_when_notify_on(
    bus: InProcessMessageBus,
) -> None:
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    msg = _publish_actionable(bus, timeout_seconds=0.05, options=["yes"])
    result = coord.handle_actionable(msg)
    assert result.notice is not None
    assert result.notice.message_type == "informational"
    assert result.notice.parent_message_id == msg.message_id
    assert result.notice.context["auto_decision"] == "timeout_default"
    assert result.notice.context["selected_value"] == "yes"
    # And the notice is persisted on the stream.
    assert bus.stream.get(result.notice.message_id) is not None


def test_sync_timeout_no_notice_when_notify_off(bus: InProcessMessageBus) -> None:
    behavior = replace(AUTONOMY_PRESETS["risk_gated"], notify_on_proceed=False)
    coord = WaitCoordinator(bus, behavior)
    msg = _publish_actionable(bus, timeout_seconds=0.05, options=["yes"])
    result = coord.handle_actionable(msg)
    assert result.outcome == WaitOutcome.TIMED_OUT_PROCEED
    assert result.notice is None


# ---------------------------------------------------------------------------
# sync — timeout_action="proceed_confident"
# ---------------------------------------------------------------------------


def test_sync_timeout_proceed_confident_falls_back_to_default(
    bus: InProcessMessageBus,
) -> None:
    """Phase 3 collapses confident → default until ConfidenceProvider lands."""
    behavior = replace(
        AUTONOMY_PRESETS["risk_gated"],
        timeout_action="proceed_confident",
    )
    coord = WaitCoordinator(bus, behavior)
    msg = _publish_actionable(bus, timeout_seconds=0.05, options=["a", "b"])
    result = coord.handle_actionable(msg)
    assert result.outcome == WaitOutcome.TIMED_OUT_PROCEED
    assert result.response_value == "a"
    assert result.response_source == "timeout_confident"
    assert result.notice is not None
    assert result.notice.context["auto_decision"] == "timeout_confident"


# ---------------------------------------------------------------------------
# sync — timeout_action="skip"
# ---------------------------------------------------------------------------


def test_sync_timeout_skip_returns_skip_outcome(
    bus: InProcessMessageBus,
) -> None:
    behavior = replace(
        AUTONOMY_PRESETS["risk_gated"],
        timeout_action="skip",
    )
    coord = WaitCoordinator(bus, behavior)
    msg = _publish_actionable(bus, timeout_seconds=0.05, options=["yes"])
    result = coord.handle_actionable(msg)
    assert result.outcome == WaitOutcome.TIMED_OUT_SKIP
    assert result.response_value is None
    assert result.response_source == "timeout_skip"
    assert result.notice is not None
    assert "skipping action" in result.notice.content


# ---------------------------------------------------------------------------
# sync — timeout_action="wait" (recursive wait)
# ---------------------------------------------------------------------------


def test_sync_timeout_wait_keeps_waiting(bus: InProcessMessageBus) -> None:
    """``timeout_action="wait"`` re-enters the bus wait with no timeout, so
    a late reply still wins."""
    behavior = replace(
        AUTONOMY_PRESETS["risk_gated"],
        timeout_action="wait",
    )
    coord = WaitCoordinator(bus, behavior)
    msg = _publish_actionable(bus, timeout_seconds=0.05, options=["a"])

    def reply() -> None:
        # Sleep past the initial 0.05s timeout to force the "wait" recursion.
        time.sleep(0.15)
        bus.publish(
            AgentMessage(
                session_id="s",
                message_type="response",
                content="late",
                parent_message_id=msg.message_id,
                response_source="user",
                response_value="late",
            )
        )

    t = threading.Thread(target=reply)
    t.start()
    try:
        result = coord.handle_actionable(msg)
    finally:
        t.join()
    assert result.outcome == WaitOutcome.GOT_RESPONSE
    assert result.response_value == "late"


def test_sync_timeout_wait_skips_when_bus_closes(
    bus: InProcessMessageBus,
) -> None:
    """If ``wait`` is selected and the bus shuts down with no reply, the
    coordinator must surface SKIP so the loop unwinds cleanly."""
    behavior = replace(
        AUTONOMY_PRESETS["risk_gated"],
        timeout_action="wait",
    )
    coord = WaitCoordinator(bus, behavior)
    msg = _publish_actionable(bus, timeout_seconds=0.05)

    result_holder: list[WaitResult] = []

    def runner() -> None:
        result_holder.append(coord.handle_actionable(msg))

    t = threading.Thread(target=runner)
    t.start()
    time.sleep(0.15)  # let the initial timeout fire and re-enter wait(None)
    bus.close()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert result_holder[0].outcome == WaitOutcome.TIMED_OUT_SKIP


# ---------------------------------------------------------------------------
# Per-message timeout override
# ---------------------------------------------------------------------------


def test_message_timeout_overrides_behavior(bus: InProcessMessageBus) -> None:
    """If ``message.timeout_seconds`` is set, it wins over behavior default."""
    behavior = replace(
        AUTONOMY_PRESETS["risk_gated"], wait_timeout=10.0  # very long
    )
    coord = WaitCoordinator(bus, behavior)
    msg = _publish_actionable(bus, timeout_seconds=0.05, options=["x"])
    start = time.monotonic()
    result = coord.handle_actionable(msg)
    elapsed = time.monotonic() - start
    assert result.outcome == WaitOutcome.TIMED_OUT_PROCEED
    assert elapsed < 1.0  # honored the per-message 0.05, not the 10s default


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_handle_rejects_non_actionable(bus: InProcessMessageBus) -> None:
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    info = AgentMessage(session_id="s", message_type="informational", content="hi")
    bus.publish(info)
    with pytest.raises(ValueError, match="actionable"):
        coord.handle_actionable(info)
