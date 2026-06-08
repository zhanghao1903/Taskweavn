"""Shell tool: RunCommand.

Executes a shell command in a working directory inside the workspace,
captures stdout/stderr, enforces a wall-clock timeout. Phase 2.2 swaps the
direct ``subprocess`` call for a sandboxed runtime; the Action and
Observation shapes stay identical.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import ClassVar

from pydantic import Field

from taskweavn.tools.base import Tool
from taskweavn.tools.workspace import PathProtectedWorkspaceError, Workspace
from taskweavn.types.base import BaseAction, BaseObservation

DEFAULT_TIMEOUT_SECONDS = 30.0


class RunCommandAction(BaseAction):
    # See docs/interaction_layer_design.md Appendix B.
    baseline_risk: ClassVar[float] = 0.5
    command: str = Field(description="Shell command to execute (run via /bin/sh -c).")
    cwd: str = Field(
        default=".",
        description="Workspace-relative directory to run the command in.",
    )
    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        gt=0,
        description="Wall-clock timeout. The process is killed if it overruns.",
    )


class CommandResultObservation(BaseObservation):
    command: str
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = Field(default=False)


class RunCommandTool(Tool[RunCommandAction, CommandResultObservation]):
    name: ClassVar[str] = "run_command"
    description: ClassVar[str] = (
        "Run a shell command in the workspace and capture stdout, stderr, exit code."
    )
    action_type: ClassVar[type[BaseAction]] = RunCommandAction
    observation_type: ClassVar[type[BaseObservation]] = CommandResultObservation

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def execute(self, action: RunCommandAction) -> CommandResultObservation:
        cwd = self._workspace.resolve(action.cwd)
        if not cwd.is_dir():
            raise NotADirectoryError(f"cwd is not a directory: {cwd}")
        self._reject_protected_path_references(action.command)
        try:
            completed = subprocess.run(  # noqa: S602 — `shell=True` is intentional
                action.command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=action.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResultObservation(
                action_id=action.event_id,
                success=False,
                command=action.command,
                cwd=str(self._relative(cwd)),
                exit_code=-1,
                stdout=exc.stdout.decode("utf-8", "replace") if exc.stdout else "",
                stderr=exc.stderr.decode("utf-8", "replace") if exc.stderr else "",
                timed_out=True,
            )
        return CommandResultObservation(
            action_id=action.event_id,
            success=completed.returncode == 0,
            command=action.command,
            cwd=str(self._relative(cwd)),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _relative(self, path: Path) -> Path:
        try:
            return path.relative_to(self._workspace.root)
        except ValueError:
            return path

    def _reject_protected_path_references(self, command: str) -> None:
        protected_root = self._workspace.root / ".taskweavn"
        protected_fragments = (
            ".taskweavn",
            protected_root.as_posix(),
            str(protected_root),
        )
        if any(fragment and fragment in command for fragment in protected_fragments):
            raise PathProtectedWorkspaceError(
                "Command references workspace-private metadata."
            )
