"""Tests for the helper-owned executable build seam."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from taskweavn.server.computer_use_helper_executable import (
    ComputerUseHelperExecutableBuildConfig,
    ComputerUseHelperExecutableBuildError,
    build_computer_use_helper_executable,
    build_pyinstaller_command,
)


def test_build_pyinstaller_command_uses_helper_entrypoint(tmp_path: Path) -> None:
    config = ComputerUseHelperExecutableBuildConfig(
        output_dir=tmp_path / "dist",
        build_dir=tmp_path / "build",
        spec_dir=tmp_path / "spec",
        python_executable="/opt/python/bin/python3",
        entrypoint_path=tmp_path / "entrypoint.py",
        collect_submodules=("taskweavn", "macos_computer_use"),
        hidden_imports=("taskweavn.cli.main",),
    )

    assert build_pyinstaller_command(config) == (
        "/opt/python/bin/python3",
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "PlatoComputerUseHelper",
        "--distpath",
        str(tmp_path / "dist"),
        "--workpath",
        str(tmp_path / "build"),
        "--specpath",
        str(tmp_path / "spec"),
        "--clean",
        "--noconfirm",
        "--collect-submodules",
        "taskweavn",
        "--collect-submodules",
        "macos_computer_use",
        "--hidden-import",
        "taskweavn.cli.main",
        str(tmp_path / "entrypoint.py"),
    )


def test_build_pyinstaller_command_collects_macos_package_by_default(
    tmp_path: Path,
) -> None:
    config = ComputerUseHelperExecutableBuildConfig(
        output_dir=tmp_path / "dist",
        build_dir=tmp_path / "build",
        spec_dir=tmp_path / "spec",
        python_executable="/opt/python/bin/python3",
        entrypoint_path=tmp_path / "entrypoint.py",
    )

    command = build_pyinstaller_command(config)

    assert _collect_submodule_values(command) == [
        "taskweavn",
        "macos_computer_use",
    ]


def test_build_computer_use_helper_executable_requires_pyinstaller(
    tmp_path: Path,
) -> None:
    def runner(
        args: Sequence[str],
        *,
        cwd: Path | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")

    with pytest.raises(
        ComputerUseHelperExecutableBuildError,
        match="PyInstaller is not available",
    ):
        build_computer_use_helper_executable(
            ComputerUseHelperExecutableBuildConfig(
                output_dir=tmp_path / "dist",
                build_dir=tmp_path / "build",
                spec_dir=tmp_path / "spec",
            ),
            runner=runner,
        )


def test_build_computer_use_helper_executable_returns_output_path(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(
        args: Sequence[str],
        *,
        cwd: Path | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(args))
        if "-c" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="",
                stderr="",
            )
        output_path = tmp_path / "dist" / "PlatoComputerUseHelper"
        output_path.write_text("#!/bin/sh\necho helper\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="built",
            stderr="",
        )

    result = build_computer_use_helper_executable(
        ComputerUseHelperExecutableBuildConfig(
            output_dir=tmp_path / "dist",
            build_dir=tmp_path / "build",
            spec_dir=tmp_path / "spec",
            python_executable="/opt/python/bin/python3",
            entrypoint_path=tmp_path / "entrypoint.py",
        ),
        runner=runner,
    )

    assert result.executable_path == tmp_path / "dist" / "PlatoComputerUseHelper"
    assert result.stdout == "built"
    assert calls[0][0] == "/opt/python/bin/python3"
    assert calls[1] == result.command


def _collect_submodule_values(command: tuple[str, ...]) -> list[str]:
    return [
        command[index + 1]
        for index, value in enumerate(command)
        if value == "--collect-submodules"
    ]


def test_build_computer_use_helper_executable_requires_expected_output(
    tmp_path: Path,
) -> None:
    def runner(
        args: Sequence[str],
        *,
        cwd: Path | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with pytest.raises(
        ComputerUseHelperExecutableBuildError,
        match="without producing the expected helper executable",
    ):
        build_computer_use_helper_executable(
            ComputerUseHelperExecutableBuildConfig(
                output_dir=tmp_path / "dist",
                build_dir=tmp_path / "build",
                spec_dir=tmp_path / "spec",
            ),
            runner=runner,
        )
