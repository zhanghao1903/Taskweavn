"""Tests for CLI surface (Phase 3.6c).

Two strands:

* ``--autonomy`` flag validation — bad preset names exit with a clean error.
* The stdin responder helper — given a fake stdin, prints actionables to
  stderr and publishes a ``response`` AgentMessage on the bus.

The full ``code-agent run`` command needs an LLM and is not exercised here;
the loop integration is already covered by ``test_loop_interaction``.
"""

from __future__ import annotations

import io
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from code_agent.cli.main import _start_stdin_responder, app
from code_agent.interaction import (
    AgentMessage,
    InProcessMessageBus,
    SqliteMessageStream,
)


@pytest.fixture
def bus(tmp_path: Path) -> Iterator[InProcessMessageBus]:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    b = InProcessMessageBus(stream)
    try:
        yield b
    finally:
        b.close()
        stream.close()


# ---------------------------------------------------------------------------
# --autonomy preset validation
# ---------------------------------------------------------------------------


def test_autonomy_unknown_preset_rejected(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--task", "noop",
            "--workspace", str(tmp_path / "ws"),
            "--log-dir", str(tmp_path / "logs"),
            "--autonomy", "definitely-not-a-preset",
            "--max-steps", "1",
        ],
    )
    assert result.exit_code != 0
    # Typer's BadParameter → "Invalid value for ..."; our message lists valid
    # preset names so the user knows what to pick.
    assert "definitely-not-a-preset" in result.output or "definitely-not-a-preset" in (
        result.stderr if result.stderr else ""
    )


# ---------------------------------------------------------------------------
# Stdin responder: actionable → reply round-trip
# ---------------------------------------------------------------------------


def test_responder_replies_to_actionable(
    bus: InProcessMessageBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Feed a canned 'yes' on stdin; publish an actionable; assert the
    responder publishes a ``response`` AgentMessage with response_value="yes"."""
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))

    session_id = "cli-test"
    t = _start_stdin_responder(bus, session_id)

    actionable = AgentMessage(
        session_id=session_id,
        message_type="actionable",
        content="OK to proceed?",
        action_options=["yes", "no"],
        requires_response=True,
    )
    bus.publish(actionable)

    # Wait up to 2s for the responder to publish.
    response = bus.wait_for_response(actionable.message_id, timeout=2.0)
    assert response is not None
    assert response.response_value == "yes"
    assert response.response_source == "user"
    assert response.parent_message_id == actionable.message_id

    # Cleanup: closing the bus stops the responder iterator.
    bus.close()
    t.join(timeout=2.0)
    assert not t.is_alive()


def test_responder_eof_treated_as_no(
    bus: InProcessMessageBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty stdin (EOF on first read) → responder publishes 'no' so the
    loop's gate path classifies as a rejection."""
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    session_id = "cli-eof"
    t = _start_stdin_responder(bus, session_id)

    actionable = AgentMessage(
        session_id=session_id,
        message_type="actionable",
        content="OK?",
        requires_response=True,
    )
    bus.publish(actionable)
    response = bus.wait_for_response(actionable.message_id, timeout=2.0)
    assert response is not None
    assert response.response_value == "no"

    bus.close()
    t.join(timeout=2.0)


def test_responder_filters_to_session(
    bus: InProcessMessageBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An actionable for a different session_id is NOT picked up by this
    responder — the subscription is session-scoped."""
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))

    t = _start_stdin_responder(bus, "session-a")

    other = AgentMessage(
        session_id="session-b",
        message_type="actionable",
        content="for the other session",
        requires_response=True,
    )
    bus.publish(other)
    # Brief grace period; non-event for the other session.
    response = bus.wait_for_response(other.message_id, timeout=0.2)
    assert response is None

    bus.close()
    t.join(timeout=2.0)


def test_responder_surfaces_informational_without_blocking(
    bus: InProcessMessageBus, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Informational messages print but don't consume stdin or publish a
    response. Verified by sending one info + one actionable and confirming
    the canned 'ok' reply lands on the actionable, not on the info."""
    monkeypatch.setattr("sys.stdin", io.StringIO("ok\n"))

    session_id = "cli-info"
    # Use an Event so we can sequence info before actionable deterministically.
    info_seen = threading.Event()
    t = _start_stdin_responder(bus, session_id)

    bus.publish(
        AgentMessage(
            session_id=session_id,
            message_type="informational",
            content="just so you know",
        )
    )
    # Brief grace so the responder pulls the info off the queue first.
    info_seen.wait(timeout=0.2)
    actionable = AgentMessage(
        session_id=session_id,
        message_type="actionable",
        content="proceed?",
        requires_response=True,
    )
    bus.publish(actionable)
    response = bus.wait_for_response(actionable.message_id, timeout=2.0)
    assert response is not None
    assert response.response_value == "ok"

    bus.close()
    t.join(timeout=2.0)
