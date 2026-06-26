"""Build seam for a helper-owned Plato Computer Use Helper executable."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from taskweavn.server.computer_use_helper_app import (
    DEFAULT_COMPUTER_USE_HELPER_EXECUTABLE,
)


class CommandRunner(Protocol):
    """Small subprocess seam used by tests and the CLI."""

    def __call__(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class ComputerUseHelperExecutableBuildConfig:
    """Inputs for building the helper app executable with PyInstaller."""

    output_dir: Path
    build_dir: Path
    spec_dir: Path
    executable_name: str = DEFAULT_COMPUTER_USE_HELPER_EXECUTABLE
    python_executable: str = sys.executable
    entrypoint_path: Path = field(
        default_factory=lambda: Path(__file__).with_name(
            "computer_use_helper_app_entrypoint.py"
        )
    )
    collect_submodules: tuple[str, ...] = ("taskweavn",)
    hidden_imports: tuple[str, ...] = ()
    clean: bool = True
    noconfirm: bool = True


@dataclass(frozen=True)
class ComputerUseHelperExecutableBuildResult:
    """Result of a helper executable build command."""

    executable_path: Path
    command: tuple[str, ...]
    stdout: str
    stderr: str


class ComputerUseHelperExecutableBuildError(RuntimeError):
    """Raised when the helper executable cannot be built."""


def build_pyinstaller_command(
    config: ComputerUseHelperExecutableBuildConfig,
) -> tuple[str, ...]:
    """Return the PyInstaller command for the helper entrypoint."""

    command: list[str] = [
        config.python_executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        config.executable_name,
        "--distpath",
        str(config.output_dir.expanduser()),
        "--workpath",
        str(config.build_dir.expanduser()),
        "--specpath",
        str(config.spec_dir.expanduser()),
    ]
    if config.clean:
        command.append("--clean")
    if config.noconfirm:
        command.append("--noconfirm")
    for module_name in config.collect_submodules:
        command.extend(["--collect-submodules", module_name])
    for module_name in config.hidden_imports:
        command.extend(["--hidden-import", module_name])
    command.append(str(config.entrypoint_path.expanduser()))
    return tuple(command)


def build_computer_use_helper_executable(
    config: ComputerUseHelperExecutableBuildConfig,
    *,
    runner: CommandRunner = subprocess.run,
) -> ComputerUseHelperExecutableBuildResult:
    """Build the helper-owned executable with PyInstaller.

    PyInstaller is intentionally optional. The build fails with a clear,
    actionable error when the selected Python runtime does not provide it.
    """

    output_dir = config.output_dir.expanduser()
    build_dir = config.build_dir.expanduser()
    spec_dir = config.spec_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    availability = runner(
        [
            config.python_executable,
            "-c",
            (
                "import importlib.util, sys; "
                "sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
            ),
        ],
        cwd=None,
        check=False,
        capture_output=True,
        text=True,
    )
    if availability.returncode != 0:
        raise ComputerUseHelperExecutableBuildError(
            "PyInstaller is not available for the selected Python runtime. "
            "Install PyInstaller in that runtime, then rerun the helper "
            "executable build."
        )

    command = build_pyinstaller_command(config)
    completed = runner(
        command,
        cwd=None,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ComputerUseHelperExecutableBuildError(
            "PyInstaller failed while building Plato Computer Use Helper "
            f"(exit={completed.returncode}).\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    executable_path = output_dir / config.executable_name
    if not executable_path.exists() or not executable_path.is_file():
        raise ComputerUseHelperExecutableBuildError(
            "PyInstaller completed without producing the expected helper "
            f"executable: {executable_path}"
        )

    return ComputerUseHelperExecutableBuildResult(
        executable_path=executable_path,
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )

