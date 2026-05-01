"""Tests for RunCommandTool (1.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_agent.runtime import LocalRuntime
from code_agent.tools import (
    CommandResultObservation,
    RunCommandAction,
    RunCommandTool,
    Workspace,
)
from code_agent.types import ErrorObservation


@pytest.fixture()
def workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def test_run_command_captures_stdout(workspace: Workspace) -> None:
    obs = RunCommandTool(workspace).execute(
        RunCommandAction(command="echo hello")
    )
    assert isinstance(obs, CommandResultObservation)
    assert obs.exit_code == 0
    assert obs.success is True
    assert obs.stdout.strip() == "hello"
    assert obs.stderr == ""
    assert obs.timed_out is False


def test_run_command_captures_nonzero_exit(workspace: Workspace) -> None:
    obs = RunCommandTool(workspace).execute(
        RunCommandAction(command="false")
    )
    assert obs.success is False
    assert obs.exit_code != 0
    assert obs.timed_out is False


def test_run_command_respects_cwd(workspace: Workspace) -> None:
    (workspace.root / "sub").mkdir()
    (workspace.root / "sub" / "marker.txt").write_text("ok")
    obs = RunCommandTool(workspace).execute(
        RunCommandAction(command="ls marker.txt", cwd="sub")
    )
    assert obs.success is True
    assert "marker.txt" in obs.stdout


def test_run_command_timeout(workspace: Workspace) -> None:
    obs = RunCommandTool(workspace).execute(
        RunCommandAction(command="sleep 5", timeout_seconds=0.2)
    )
    assert obs.timed_out is True
    assert obs.success is False
    assert obs.exit_code == -1


def test_run_command_cwd_outside_workspace_via_runtime(workspace: Workspace) -> None:
    rt = LocalRuntime()
    RunCommandTool(workspace).register(rt)
    obs = rt.execute(RunCommandAction(command="echo x", cwd=".."))
    assert isinstance(obs, ErrorObservation)
    assert "outside" in obs.message.lower()


def test_run_command_captures_stderr(workspace: Workspace) -> None:
    obs = RunCommandTool(workspace).execute(
        RunCommandAction(command="echo oops 1>&2; false")
    )
    assert obs.exit_code != 0
    assert "oops" in obs.stderr
