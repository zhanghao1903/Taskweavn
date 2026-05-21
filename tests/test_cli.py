"""Tests for CLI surface (Phase 3.6c).

Two strands:

* ``--autonomy`` flag validation — bad preset names exit with a clean error.
* The stdin responder helper — given a fake stdin, prints actionables to
  stderr and publishes a ``response`` AgentMessage on the bus.

The full ``taskweavn run`` command needs an LLM and is not exercised here;
the loop integration is already covered by ``test_loop_interaction``.
"""

from __future__ import annotations

import io
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from taskweavn.cli.main import (
    _build_risk_assessor,
    _plato_frontend_command,
    _plato_frontend_env,
    _plato_sidecar_env_lines,
    _start_stdin_responder,
    app,
)
from taskweavn.interaction import (
    AgentMessage,
    BaselineOnlyAssessor,
    CompositeAssessor,
    InProcessMessageBus,
    LLMRiskAssessor,
    SqliteMessageStream,
)
from taskweavn.observability import LogContext, configure_session_logging, get_logging_manager


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


def test_logging_profile_unknown_rejected_before_llm_allocation(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--task", "noop",
            "--workspace", str(tmp_path / "ws"),
            "--log-dir", str(tmp_path / "logs"),
            "--logging-profile", "not-a-profile",
            "--max-steps", "1",
        ],
    )

    assert result.exit_code != 0
    assert "not-a-profile" in result.output


def test_logging_profiles_command_lists_builtins() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["logging", "profiles"])

    assert result.exit_code == 0
    assert "debug-llm" in result.output
    assert "full-debug" in result.output


def test_logging_manifest_command_prints_session_manifest(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="s1")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "logging",
            "manifest",
            "--log-dir", str(tmp_path / "logs"),
            "--session-id", "s1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["session_id"] == "s1"
    assert payload["files"]["llm"] == "llm.jsonl"


def test_logging_render_command_pretty_prints_jsonl(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="s1")
    get_logging_manager().emit(
        "llm",
        "INFO",
        "request",
        context=LogContext(session_id="s1", model="deepseek-chat"),
        data={"message_count": 1},
    )
    log_file = tmp_path / "logs" / "sessions" / "s1" / "llm.jsonl"

    runner = CliRunner()
    result = runner.invoke(app, ["logging", "render", str(log_file)])

    assert result.exit_code == 0
    assert "INFO" in result.output
    assert "llm.request" in result.output
    assert "session=s1" in result.output
    assert "model=deepseek-chat" in result.output


def test_plato_sidecar_env_lines_include_vite_runtime_settings() -> None:
    lines = _plato_sidecar_env_lines(
        base_url="http://127.0.0.1:53123",
        session_id="session-live",
    )

    assert "baseUrl=http://127.0.0.1:53123" in lines[0]
    assert "sessionId=session-live" in lines[1]
    assert "[plato-sidecar] health=http://127.0.0.1:53123/api/v1/health" in lines
    assert (
        "[plato-sidecar] snapshot="
        "http://127.0.0.1:53123/api/v1/sessions/session-live/snapshot"
    ) in lines
    assert "VITE_PLATO_API_MODE=http" in lines
    assert "VITE_PLATO_API_BASE_URL=http://127.0.0.1:53123" in lines
    assert "VITE_PLATO_SESSION_ID=session-live" in lines


def test_plato_frontend_env_sets_http_runtime() -> None:
    env = _plato_frontend_env(
        base_url="http://127.0.0.1:53123",
        session_id="session-live",
    )

    assert env["VITE_PLATO_API_MODE"] == "http"
    assert env["VITE_PLATO_API_BASE_URL"] == "http://127.0.0.1:53123"
    assert env["VITE_PLATO_SESSION_ID"] == "session-live"


def test_plato_frontend_command_runs_vite_on_requested_host_port() -> None:
    assert _plato_frontend_command(host="127.0.0.1", port=5174) == [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        "5174",
    ]


def test_plato_dev_rejects_missing_frontend_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plato-dev",
            "--workspace", str(tmp_path / "workspace"),
            "--frontend-dir", str(tmp_path / "missing-frontend"),
        ],
    )

    assert result.exit_code == 1
    assert "frontend dir not found" in result.stderr


# ---------------------------------------------------------------------------
# Stdin responder: actionable → reply round-trip
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# --risk-assessor flag → assessor builder
# ---------------------------------------------------------------------------


class _FakeLLM:
    """Stand-in for LLMClient — _build_risk_assessor only stores the
    reference; nothing in the builder actually calls .chat()."""

    def chat(self, *a: object, **k: object) -> object:  # pragma: no cover
        raise AssertionError("builder should not invoke the LLM")


def test_build_risk_assessor_baseline() -> None:
    a = _build_risk_assessor("baseline", _FakeLLM())  # type: ignore[arg-type]
    assert isinstance(a, BaselineOnlyAssessor)


def test_build_risk_assessor_llm() -> None:
    a = _build_risk_assessor("llm", _FakeLLM())  # type: ignore[arg-type]
    assert isinstance(a, LLMRiskAssessor)


def test_build_risk_assessor_composite_layers_baseline_and_llm() -> None:
    a = _build_risk_assessor("composite", _FakeLLM())  # type: ignore[arg-type]
    assert isinstance(a, CompositeAssessor)
    types_in_chain = [type(x) for x in a.assessors]
    assert BaselineOnlyAssessor in types_in_chain
    assert LLMRiskAssessor in types_in_chain


def test_build_risk_assessor_rejects_unknown() -> None:
    import typer

    with pytest.raises(typer.BadParameter, match="risk assessor"):
        _build_risk_assessor("nonsense", _FakeLLM())  # type: ignore[arg-type]


def test_risk_assessor_unknown_via_cli(tmp_path: Path) -> None:
    """End-to-end: an invalid --risk-assessor exits with BadParameter even
    when --autonomy is unset (the validator runs unconditionally so the
    error surfaces before the agent allocates any resources)."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--task", "noop",
            "--workspace", str(tmp_path / "ws"),
            "--log-dir", str(tmp_path / "logs"),
            "--autonomy", "risk_gated",
            "--risk-assessor", "definitely-not-a-thing",
            "--max-steps", "1",
        ],
    )
    assert result.exit_code != 0
    assert "definitely-not-a-thing" in result.output


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
