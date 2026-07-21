"""Build the stable development Plato Computer Use Helper app bundle."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from plistlib import dump as dump_plist
from plistlib import load as load_plist
from typing import Any

DEV_HELPER_NAME = "Plato Computer Use Helper Dev"
DEV_HELPER_BUNDLE_ID = "com.taskweavn.plato.computer-use-helper.dev"
RELEASE_HELPER_NAME = "Plato Computer Use Helper"
RELEASE_HELPER_BUNDLE_ID = "com.taskweavn.plato.computer-use-helper"
HELPER_EXECUTABLE_NAME = "PlatoComputerUseHelper"


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class DevHelperBuildConfig:
    repo_root: Path
    build_root: Path
    app_path: Path
    python_executable: str = sys.executable
    version: str = "0.1.0"
    app_name: str = DEV_HELPER_NAME
    bundle_id: str = DEV_HELPER_BUNDLE_ID


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    release = args.variant == "release"
    app_name = RELEASE_HELPER_NAME if release else DEV_HELPER_NAME
    bundle_id = RELEASE_HELPER_BUNDLE_ID if release else DEV_HELPER_BUNDLE_ID
    repo_root = args.repo_root.expanduser().resolve()
    build_root = (
        args.build_root
        if args.build_root is not None
        else repo_root / "build" / f"plato-computer-use-helper-{args.variant}"
    )
    app_path = (
        args.app_path
        if args.app_path is not None
        else Path.home() / "Applications" / f"{app_name}.app"
    )
    config = DevHelperBuildConfig(
        repo_root=repo_root,
        build_root=build_root.expanduser().resolve(),
        app_path=app_path.expanduser().resolve(),
        python_executable=args.python_executable,
        version=args.version,
        app_name=app_name,
        bundle_id=bundle_id,
    )
    try:
        app_path = build_dev_helper(config)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"helper build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"appPath": str(app_path)}, ensure_ascii=False))
    return 0


def build_dev_helper(
    config: DevHelperBuildConfig,
    *,
    runner: CommandRunner = subprocess.run,
) -> Path:
    if platform.system() != "Darwin":
        raise ValueError("Plato Computer Use Helper can only be built on macOS")
    entrypoint = (
        config.repo_root
        / "src"
        / "taskweavn"
        / "server"
        / "app_control_helper_executable.py"
    )
    if not entrypoint.is_file():
        raise ValueError(f"Helper executable entrypoint is missing: {entrypoint}")

    build_root = config.build_root
    dist_root = build_root / "dist"
    work_root = build_root / "work"
    spec_root = build_root / "spec"
    staging_app = build_root / f"{config.app_name}.app"
    for path in (dist_root, work_root, spec_root):
        path.mkdir(parents=True, exist_ok=True)
    if staging_app.exists():
        shutil.rmtree(staging_app)

    _require_pyinstaller(config.python_executable, runner=runner)
    completed = runner(
        build_pyinstaller_command(config, entrypoint=entrypoint),
        cwd=config.repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            "PyInstaller failed while building Plato Computer Use Helper "
            f"(exit={completed.returncode}).\n{completed.stderr}"
        )

    generated_app = dist_root / f"{HELPER_EXECUTABLE_NAME}.app"
    generated_executable = (
        generated_app / "Contents" / "MacOS" / HELPER_EXECUTABLE_NAME
    )
    if not generated_executable.is_file():
        raise ValueError(f"PyInstaller app output is missing: {generated_executable}")

    shutil.copytree(generated_app, staging_app, symlinks=True)
    _customize_app_bundle(
        staging_app,
        version=config.version,
        app_name=config.app_name,
        bundle_id=config.bundle_id,
    )
    _codesign(staging_app, runner=runner)

    config.app_path.parent.mkdir(parents=True, exist_ok=True)
    if config.app_path.exists():
        shutil.rmtree(config.app_path)
    shutil.copytree(staging_app, config.app_path, symlinks=True)
    return config.app_path


def build_pyinstaller_command(
    config: DevHelperBuildConfig,
    *,
    entrypoint: Path,
) -> tuple[str, ...]:
    return (
        config.python_executable,
        "-m",
        "PyInstaller",
        "--onedir",
        "--windowed",
        "--osx-bundle-identifier",
        config.bundle_id,
        "--name",
        HELPER_EXECUTABLE_NAME,
        "--distpath",
        str(config.build_root / "dist"),
        "--workpath",
        str(config.build_root / "work"),
        "--specpath",
        str(config.build_root / "spec"),
        "--clean",
        "--noconfirm",
        "--collect-submodules",
        "taskweavn",
        "--collect-all",
        "computer_use_macos",
        "--collect-all",
        "wechat_desktop_tool",
        "--collect-all",
        "app_control_protocol",
        "--hidden-import",
        "ApplicationServices",
        "--hidden-import",
        "objc",
        str(entrypoint),
    )


def _customize_app_bundle(
    app_path: Path,
    *,
    version: str,
    app_name: str = DEV_HELPER_NAME,
    bundle_id: str = DEV_HELPER_BUNDLE_ID,
) -> None:
    contents = app_path / "Contents"
    resources = contents / "Resources"
    resources.mkdir(parents=True, exist_ok=True)
    info_plist_path = contents / "Info.plist"
    with info_plist_path.open("rb") as handle:
        info = load_plist(handle)
    info.update(_info_plist(version, app_name=app_name, bundle_id=bundle_id))
    with info_plist_path.open("wb") as handle:
        dump_plist(info, handle)
    (resources / "permission-guide.md").write_text(
        _permission_guide(
            version,
            app_name=app_name,
            bundle_id=bundle_id,
        ),
        encoding="utf-8",
    )


def _info_plist(
    version: str,
    *,
    app_name: str = DEV_HELPER_NAME,
    bundle_id: str = DEV_HELPER_BUNDLE_ID,
) -> dict[str, Any]:
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": app_name,
        "CFBundleExecutable": HELPER_EXECUTABLE_NAME,
        "CFBundleIdentifier": bundle_id,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": app_name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSAppleEventsUsageDescription": (
            "Plato Computer Use Helper controls approved desktop applications "
            "for tasks requested in Plato."
        ),
        "NSHighResolutionCapable": True,
    }


def _permission_guide(
    version: str,
    *,
    app_name: str = DEV_HELPER_NAME,
    bundle_id: str = DEV_HELPER_BUNDLE_ID,
) -> str:
    return f"""# {app_name}

This app is Plato's stable macOS Accessibility permission subject in development.

- Bundle ID: `{bundle_id}`
- Version: `{version}`
- Runtime: packaged `computer-use-macos` local Unix socket service

Grant Accessibility permission to this app. Rebuild it only when the packaged
computer-use runtime changes; a new signature may require permission again.
"""


def _require_pyinstaller(python_executable: str, *, runner: CommandRunner) -> None:
    completed = runner(
        [
            python_executable,
            "-c",
            (
                "import importlib.util,sys;"
                "sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
            ),
        ],
        cwd=None,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            "PyInstaller is unavailable. Run with the packaging dependency group."
        )


def _codesign(app_path: Path, *, runner: CommandRunner) -> None:
    codesign = shutil.which("codesign")
    if codesign is None:
        raise ValueError("codesign is unavailable")
    completed = runner(
        [
            codesign,
            "--force",
            "--deep",
            "--sign",
            "-",
            "--timestamp=none",
            str(app_path),
        ],
        cwd=None,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"codesign failed for {app_path}: {completed.stderr}")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--variant", choices=("dev", "release"), default="dev")
    parser.add_argument(
        "--build-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--app-path",
        type=Path,
        default=None,
    )
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--version", default="0.1.0")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
