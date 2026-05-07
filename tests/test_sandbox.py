"""Unit tests for SandboxExecutor — Docker is mocked.

Real-Docker behaviour is covered in test_sandbox_integration.py and gated by
the ``integration`` marker.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from code_agent.runtime.sandbox import (
    RUNS_SUBDIR,
    SCRIPT_FILENAME,
    TRACK_FILENAME,
    SandboxConfig,
    SandboxError,
    SandboxExecutor,
    _build_wrapper_script,
    _diff_snapshots,
    _normalize_relpath,
    _partition_changes,
    _snapshot_workspace,
)
from code_agent.types import CodeAction, CodeExecutionObservation, TrackingConfig

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_snapshot_workspace_skips_code_agent_dir(tmp_path: Path) -> None:
    (tmp_path / "kept.txt").write_text("hi")
    runs = tmp_path / ".code-agent" / "runs" / "x"
    runs.mkdir(parents=True)
    (runs / "noise.txt").write_text("ignore me")

    snap = _snapshot_workspace(tmp_path)
    assert "kept.txt" in snap
    assert all(not k.startswith(".code-agent") for k in snap)


def test_snapshot_workspace_handles_subdirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "c.txt").write_text("body")
    snap = _snapshot_workspace(tmp_path)
    assert "a/b/c.txt" in snap
    sha, size = snap["a/b/c.txt"]
    assert size == len("body")
    assert len(sha) == 64


def test_diff_snapshots_creates_modifies_deletes() -> None:
    before = {
        "stay.txt": ("a" * 64, 5),
        "modify.txt": ("b" * 64, 3),
        "go.txt": ("c" * 64, 7),
    }
    after = {
        "stay.txt": ("a" * 64, 5),
        "modify.txt": ("d" * 64, 4),
        "new.txt": ("e" * 64, 2),
    }
    changes = _diff_snapshots(before, after)
    by_path = {c.path: c for c in changes}
    assert set(by_path) == {"modify.txt", "go.txt", "new.txt"}
    assert by_path["modify.txt"].change_type == "modified"
    assert by_path["modify.txt"].size_delta == 1
    assert by_path["go.txt"].change_type == "deleted"
    assert by_path["go.txt"].size_delta == -7
    assert by_path["new.txt"].change_type == "created"
    assert by_path["new.txt"].before_sha256 is None


def test_normalize_relpath_strips_dot_and_collapses() -> None:
    assert _normalize_relpath("./foo.txt") == "foo.txt"
    assert _normalize_relpath("a/./b.txt") == "a/b.txt"
    assert _normalize_relpath("a//b.txt") == "a/b.txt"
    assert _normalize_relpath(".env") == ".env"  # do NOT strip leading dot of name


def test_partition_changes_splits_by_declared_set() -> None:
    from code_agent.types import FileChange

    changes = [
        FileChange(path="declared.txt", change_type="created", after_sha256="a" * 64, size_delta=1),
        FileChange(path="leaked.log", change_type="created", after_sha256="b" * 64, size_delta=2),
    ]
    inside, outside = _partition_changes(changes, ["./declared.txt"])
    assert [c.path for c in inside] == ["declared.txt"]
    assert [c.path for c in outside] == ["leaked.log"]


# ---------------------------------------------------------------------------
# Wrapper script
# ---------------------------------------------------------------------------


def test_wrapper_script_captures_variables(tmp_path: Path) -> None:
    """End-to-end execute the wrapper *locally* (no Docker) — it's pure Python."""
    import subprocess
    import sys

    script = _build_wrapper_script(
        "x = 42\ny = 'hello'", ["x", "y", "missing"], TRACK_FILENAME
    )
    script_path = tmp_path / SCRIPT_FILENAME
    script_path.write_text(script)
    result = subprocess.run(
        [sys.executable, "-I", str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    track = json.loads((tmp_path / TRACK_FILENAME).read_text())
    assert track == {"x": "42", "y": "'hello'"}  # missing absent


def test_wrapper_script_dumps_on_exception(tmp_path: Path) -> None:
    import subprocess
    import sys

    script = _build_wrapper_script(
        "x = 7\nraise RuntimeError('boom')", ["x"], TRACK_FILENAME
    )
    script_path = tmp_path / SCRIPT_FILENAME
    script_path.write_text(script)
    result = subprocess.run(
        [sys.executable, "-I", str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert b"RuntimeError: boom" in result.stderr
    track = json.loads((tmp_path / TRACK_FILENAME).read_text())
    assert track == {"x": "7"}


def test_wrapper_script_truncates_large_repr(tmp_path: Path) -> None:
    import subprocess
    import sys

    script = _build_wrapper_script("x = 'a' * 5000", ["x"], TRACK_FILENAME)
    script_path = tmp_path / SCRIPT_FILENAME
    script_path.write_text(script)
    subprocess.run(
        [sys.executable, "-I", str(script_path)], cwd=tmp_path, check=True
    )
    track = json.loads((tmp_path / TRACK_FILENAME).read_text())
    assert "<truncated" in track["x"]


# ---------------------------------------------------------------------------
# Lifecycle (mocked docker client)
# ---------------------------------------------------------------------------


def _make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


def test_start_is_idempotent(tmp_path: Path) -> None:
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = MagicMock(name="container")

    ex = SandboxExecutor(workspace_root=_make_workspace(tmp_path), docker_client=client)
    ex.start()
    ex.start()
    assert client.containers.run.call_count == 1


def test_start_lazy_pulls_when_image_missing(tmp_path: Path) -> None:
    client = MagicMock()
    client.images.get.side_effect = RuntimeError("no such image")
    client.containers.run.return_value = MagicMock()

    ex = SandboxExecutor(workspace_root=_make_workspace(tmp_path), docker_client=client)
    ex.start()
    client.images.pull.assert_called_once_with("python:3.12-slim")


def test_start_raises_sandbox_error_when_pull_fails(tmp_path: Path) -> None:
    client = MagicMock()
    client.images.get.side_effect = RuntimeError("missing")
    client.images.pull.side_effect = RuntimeError("network down")

    ex = SandboxExecutor(workspace_root=_make_workspace(tmp_path), docker_client=client)
    with pytest.raises(SandboxError, match="failed to pull"):
        ex.start()


def test_stop_tolerates_missing_container(tmp_path: Path) -> None:
    ex = SandboxExecutor(
        workspace_root=_make_workspace(tmp_path),
        docker_client=MagicMock(),
    )
    ex.stop()  # never started


def test_stop_swallows_remove_errors(tmp_path: Path) -> None:
    container = MagicMock()
    container.remove.side_effect = RuntimeError("daemon hung up")
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container

    ex = SandboxExecutor(workspace_root=_make_workspace(tmp_path), docker_client=client)
    ex.start()
    ex.stop()  # must not raise


def test_execute_before_start_raises(tmp_path: Path) -> None:
    ex = SandboxExecutor(
        workspace_root=_make_workspace(tmp_path),
        docker_client=MagicMock(),
    )
    action = CodeAction(
        intent="x", code="x=1", tracking=TrackingConfig(files=[], variables=[])
    )
    with pytest.raises(SandboxError, match="before start"):
        ex.execute(action)


# ---------------------------------------------------------------------------
# Execute (mocked docker, real filesystem snapshot)
# ---------------------------------------------------------------------------


def _wired_executor(workspace: Path, exec_run_result: Any) -> SandboxExecutor:
    container = MagicMock()
    container.exec_run.return_value = exec_run_result
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container
    ex = SandboxExecutor(workspace_root=workspace, docker_client=client)
    ex.start()
    return ex


def _fake_run_writing(
    workspace: Path,
    *,
    files_to_create: dict[str, str] | None = None,
    track_payload: dict[str, str] | None = None,
    exit_code: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> Any:
    """Build an exec_run() return value whose side effect mimics the
    in-container script writing into the bind-mounted workspace."""

    def side_effect(*args: Any, **kwargs: Any) -> Any:
        # Simulate the script's effects on the host workspace.
        if files_to_create:
            for relpath, body in files_to_create.items():
                target = workspace / relpath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body)
        if track_payload is not None:
            # Recover the per-event run dir from the script path in the cmd.
            cmd = kwargs.get("cmd")
            assert isinstance(cmd, list), "exec_run was not called with cmd list"
            script_container_path = cmd[-1]  # ".../script.py"
            assert script_container_path.endswith(SCRIPT_FILENAME)
            # Strip the container workdir prefix to get the workspace-relative dir.
            rel_script = script_container_path.removeprefix("/workspace/")
            run_subdir = rel_script.rsplit("/", 1)[0]
            (workspace / run_subdir).mkdir(parents=True, exist_ok=True)
            (workspace / run_subdir / TRACK_FILENAME).write_text(
                json.dumps(track_payload), encoding="utf-8"
            )
        result = MagicMock()
        result.exit_code = exit_code
        result.output = (stdout, stderr)
        return result

    return side_effect


def test_execute_records_declared_file_change(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    container = MagicMock()
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container

    ex = SandboxExecutor(workspace_root=ws, docker_client=client)
    ex.start()

    container.exec_run.side_effect = _fake_run_writing(
        ws,
        files_to_create={"out.txt": "hello"},
        track_payload={},
        stdout=b"done\n",
    )

    action = CodeAction(
        intent="write out.txt",
        code="open('out.txt', 'w').write('hello')",
        tracking=TrackingConfig(files=["out.txt"], variables=[]),
    )
    obs = ex.execute(action)
    assert isinstance(obs, CodeExecutionObservation)
    assert obs.exit_code == 0
    assert obs.success is True
    assert obs.stdout == "done\n"
    assert len(obs.declared_changes) == 1
    assert obs.declared_changes[0].path == "out.txt"
    assert obs.declared_changes[0].change_type == "created"
    assert obs.undeclared_changes == []


def test_execute_flags_undeclared_file_change(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    container = MagicMock()
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container
    ex = SandboxExecutor(workspace_root=ws, docker_client=client)
    ex.start()

    container.exec_run.side_effect = _fake_run_writing(
        ws,
        files_to_create={"declared.txt": "ok", "leaked.log": "oops"},
        track_payload={},
    )

    action = CodeAction(
        intent="declared only",
        code="...",
        tracking=TrackingConfig(files=["declared.txt"], variables=[]),
    )
    obs = ex.execute(action)
    assert [c.path for c in obs.declared_changes] == ["declared.txt"]
    assert [c.path for c in obs.undeclared_changes] == ["leaked.log"]


def test_execute_returns_variable_dump(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    container = MagicMock()
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container
    ex = SandboxExecutor(workspace_root=ws, docker_client=client)
    ex.start()

    container.exec_run.side_effect = _fake_run_writing(
        ws, track_payload={"x": "42", "y": "'hi'"}
    )

    action = CodeAction(
        intent="capture xy",
        code="x = 42; y = 'hi'",
        tracking=TrackingConfig(files=[], variables=["x", "y"]),
    )
    obs = ex.execute(action)
    assert obs.variable_dump == {"x": "42", "y": "'hi'"}


def test_execute_marks_timeout_via_exit_code(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    container = MagicMock()
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container
    ex = SandboxExecutor(workspace_root=ws, docker_client=client)
    ex.start()

    container.exec_run.side_effect = _fake_run_writing(
        ws, track_payload={}, exit_code=124, stderr=b"timeout"
    )

    action = CodeAction(
        intent="forever",
        code="while True: pass",
        tracking=TrackingConfig(files=[], variables=[]),
    )
    obs = ex.execute(action)
    assert obs.timed_out is True
    assert obs.success is False


def test_execute_handles_exec_exception(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    container = MagicMock()
    container.exec_run.side_effect = RuntimeError("docker socket gone")
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container
    ex = SandboxExecutor(workspace_root=ws, docker_client=client)
    ex.start()

    action = CodeAction(
        intent="x", code="x=1", tracking=TrackingConfig(files=[], variables=[])
    )
    obs = ex.execute(action)
    assert obs.success is False
    assert obs.blocked_reason == "sandbox_error"
    assert "docker socket gone" in obs.stderr


def test_execute_writes_script_and_invokes_docker_with_python(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    container = MagicMock()
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = container
    ex = SandboxExecutor(workspace_root=ws, docker_client=client)
    ex.start()

    container.exec_run.side_effect = _fake_run_writing(ws, track_payload={})
    action = CodeAction(
        intent="echo",
        code="print('x')",
        tracking=TrackingConfig(files=[], variables=[]),
    )
    ex.execute(action)

    # Script file was written under .code-agent/runs/<event_id>/script.py
    runs_dir = ws / RUNS_SUBDIR / action.event_id
    assert (runs_dir / SCRIPT_FILENAME).exists()
    body = (runs_dir / SCRIPT_FILENAME).read_text()
    assert "print('x')" in body  # the user code is embedded as a literal

    call = container.exec_run.call_args
    cmd = call.kwargs["cmd"]
    assert cmd[0] == "timeout"
    assert "python" in cmd
    assert cmd[-1].endswith(SCRIPT_FILENAME)


# ---------------------------------------------------------------------------
# SandboxConfig
# ---------------------------------------------------------------------------


def test_sandbox_config_defaults() -> None:
    cfg = SandboxConfig()
    assert cfg.image == "python:3.12-slim"
    assert cfg.timeout_seconds == 30
    assert cfg.memory_mb == 512
    assert cfg.cpus == 1.0
    assert cfg.network_mode == "none"


def test_sandbox_config_is_frozen() -> None:
    cfg = SandboxConfig()
    # dataclass(frozen=True) raises FrozenInstanceError on assignment.
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.timeout_seconds = 99  # type: ignore[misc]
