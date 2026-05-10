"""Integration tests for SandboxExecutor — exercises real Docker.

Skipped automatically when:

* the ``docker`` SDK can't connect to a daemon, or
* the ``python:3.12-slim`` image isn't available locally and pulling fails,
  or
* explicitly skipped via ``pytest -m 'not integration'``.

Each test runs with the ``integration`` marker so CI can opt in/out.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from taskweavn.runtime.sandbox import SandboxConfig, SandboxExecutor
from taskweavn.types import CodeAction, TrackingConfig


def _docker_available() -> bool:
    try:
        import docker  # type: ignore[import-untyped]
    except ImportError:
        return False
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        return False
    return True


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_available(), reason="Docker daemon not reachable"),
]


@pytest.fixture()
def executor(tmp_path: Path) -> Iterator[SandboxExecutor]:
    ws = tmp_path / "ws"
    ws.mkdir()
    # Shorter timeout so a runaway test doesn't pin CI.
    cfg = SandboxConfig(timeout_seconds=10, memory_mb=256)
    ex = SandboxExecutor(workspace_root=ws, config=cfg)
    ex.start()
    try:
        yield ex
    finally:
        ex.stop()


def test_real_docker_writes_declared_file(
    executor: SandboxExecutor, tmp_path: Path
) -> None:
    action = CodeAction(
        intent="write greeting",
        code="open('hello.txt', 'w').write('hi from sandbox')",
        tracking=TrackingConfig(files=["hello.txt"], variables=[]),
    )
    obs = executor.execute(action)
    assert obs.success is True, obs.stderr
    assert obs.exit_code == 0
    assert obs.timed_out is False
    assert [c.path for c in obs.declared_changes] == ["hello.txt"]
    assert obs.undeclared_changes == []
    assert (executor.workspace_root / "hello.txt").read_text() == "hi from sandbox"


def test_real_docker_captures_variables(executor: SandboxExecutor) -> None:
    action = CodeAction(
        intent="compute",
        code="n = 6 * 7\nname = 'agent'",
        tracking=TrackingConfig(files=[], variables=["n", "name"]),
    )
    obs = executor.execute(action)
    assert obs.success is True, obs.stderr
    assert obs.variable_dump == {"n": "42", "name": "'agent'"}


def test_real_docker_flags_undeclared_writes(executor: SandboxExecutor) -> None:
    action = CodeAction(
        intent="declared only",
        code=(
            "open('declared.txt', 'w').write('ok')\n"
            "open('leaked.log', 'w').write('oops')"
        ),
        tracking=TrackingConfig(files=["declared.txt"], variables=[]),
    )
    obs = executor.execute(action)
    assert obs.success is True, obs.stderr
    declared_paths = sorted(c.path for c in obs.declared_changes)
    undeclared_paths = sorted(c.path for c in obs.undeclared_changes)
    assert declared_paths == ["declared.txt"]
    assert undeclared_paths == ["leaked.log"]


def test_real_docker_propagates_stdout_and_stderr(executor: SandboxExecutor) -> None:
    action = CodeAction(
        intent="print stuff",
        code="import sys\nprint('out')\nprint('err', file=sys.stderr)",
        tracking=TrackingConfig(files=[], variables=[]),
    )
    obs = executor.execute(action)
    assert obs.success is True
    assert "out" in obs.stdout
    assert "err" in obs.stderr


def test_real_docker_marks_python_exception_as_failure(
    executor: SandboxExecutor,
) -> None:
    action = CodeAction(
        intent="raise",
        code="raise RuntimeError('nope')",
        tracking=TrackingConfig(files=[], variables=[]),
    )
    obs = executor.execute(action)
    assert obs.success is False
    assert obs.exit_code != 0
    assert "RuntimeError: nope" in obs.stderr
    assert obs.timed_out is False


def test_real_docker_enforces_timeout(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = SandboxConfig(timeout_seconds=2, memory_mb=256)
    ex = SandboxExecutor(workspace_root=ws, config=cfg)
    ex.start()
    try:
        action = CodeAction(
            intent="forever",
            code="while True: pass",
            tracking=TrackingConfig(files=[], variables=[]),
        )
        obs = ex.execute(action)
        assert obs.timed_out is True
        assert obs.success is False
    finally:
        ex.stop()


def test_real_docker_network_isolated(executor: SandboxExecutor) -> None:
    """`network_mode=none` should make outbound DNS/TCP fail."""
    action = CodeAction(
        intent="probe network",
        code=(
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('8.8.8.8', 53), timeout=2)\n"
            "    print('REACHED')\n"
            "except OSError as e:\n"
            "    print(f'BLOCKED:{type(e).__name__}')\n"
        ),
        tracking=TrackingConfig(files=[], variables=[]),
    )
    obs = executor.execute(action)
    assert "BLOCKED" in obs.stdout
    assert "REACHED" not in obs.stdout


def test_real_docker_state_does_not_leak_between_actions(
    executor: SandboxExecutor,
) -> None:
    """Each docker exec is a fresh interpreter — Python globals must NOT persist."""
    first = CodeAction(
        intent="set x",
        code="x = 99",
        tracking=TrackingConfig(files=[], variables=["x"]),
    )
    obs1 = executor.execute(first)
    assert obs1.variable_dump == {"x": "99"}

    second = CodeAction(
        intent="read x from previous",
        code="print(x)",  # NameError expected
        tracking=TrackingConfig(files=[], variables=[]),
    )
    obs2 = executor.execute(second)
    assert obs2.success is False
    assert "NameError" in obs2.stderr


def test_real_docker_state_shared_via_files(executor: SandboxExecutor) -> None:
    """The supported channel for cross-action state is declared file IO."""
    write = CodeAction(
        intent="persist counter",
        code="open('state.txt', 'w').write('17')",
        tracking=TrackingConfig(files=["state.txt"], variables=[]),
    )
    obs1 = executor.execute(write)
    assert obs1.success is True

    read = CodeAction(
        intent="resume counter",
        code="n = int(open('state.txt').read()); print(n + 1)",
        tracking=TrackingConfig(files=["state.txt"], variables=["n"]),
    )
    obs2 = executor.execute(read)
    assert obs2.success is True
    assert "18" in obs2.stdout
    assert obs2.variable_dump == {"n": "17"}
