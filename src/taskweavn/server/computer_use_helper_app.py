"""Development macOS app scaffold for Plato Computer Use Helper.

The real release helper must eventually be a signed, packaged app with an
embedded runtime. This module intentionally builds only a deterministic dev
``.app`` wrapper around the existing helper CLI so TCC identity, manifest
paths, and launch configuration can be tested before release packaging exists.
"""

from __future__ import annotations

import json
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from plistlib import dump as dump_plist
from typing import Any

DEFAULT_COMPUTER_USE_HELPER_API_VERSION = "plato.computer_use_helper.v1"
DEFAULT_COMPUTER_USE_HELPER_BUNDLE_ID = (
    "com.taskweavn.plato.computer-use-helper.dev"
)
DEFAULT_COMPUTER_USE_HELPER_DISPLAY_NAME = "Plato Computer Use Helper Dev"
DEFAULT_COMPUTER_USE_HELPER_EXECUTABLE = "PlatoComputerUseHelper"
DEFAULT_COMPUTER_USE_HELPER_SIGNING_MODE = "development-app"


@dataclass(frozen=True)
class ComputerUseHelperAppConfig:
    """Inputs for building a dev ``Plato Computer Use Helper.app`` scaffold."""

    app_path: Path
    manifest_path: Path
    token_path: Path | None = None
    python_executable: str = sys.executable
    packaged_executable_path: Path | None = None
    bundle_id: str = DEFAULT_COMPUTER_USE_HELPER_BUNDLE_ID
    display_name: str = DEFAULT_COMPUTER_USE_HELPER_DISPLAY_NAME
    executable_name: str = DEFAULT_COMPUTER_USE_HELPER_EXECUTABLE
    version: str = "0.1.0"
    api_version: str = DEFAULT_COMPUTER_USE_HELPER_API_VERSION
    signing_mode: str = DEFAULT_COMPUTER_USE_HELPER_SIGNING_MODE
    host: str = "127.0.0.1"
    port: int = 0
    computer_use_backend: str = "disabled"
    computer_use_allowed_apps: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComputerUseHelperAppBuildResult:
    """Paths written for a dev helper app scaffold."""

    app_path: Path
    executable_path: Path
    info_plist_path: Path
    launch_config_path: Path
    permission_guide_path: Path
    manifest_path: Path
    token_path: Path | None
    bundle_id: str
    version: str
    api_version: str
    signed: bool
    signing_command: tuple[str, ...] | None = None


def build_computer_use_helper_app(
    config: ComputerUseHelperAppConfig,
) -> ComputerUseHelperAppBuildResult:
    """Build a dev macOS ``.app`` wrapper for the helper CLI."""

    normalized_backend = config.computer_use_backend.strip().lower()
    if normalized_backend == "helper":
        raise ValueError("helper app cannot recursively launch helper backend")

    app_path = config.app_path.expanduser()
    if app_path.suffix != ".app":
        raise ValueError("helper app path must end with .app")

    contents_dir = app_path / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = config.manifest_path.expanduser()
    token_path = None if config.token_path is None else config.token_path.expanduser()
    info_plist_path = contents_dir / "Info.plist"
    launch_config_path = resources_dir / "helper-launch.json"
    permission_guide_path = resources_dir / "permission-guide.md"
    executable_path = macos_dir / config.executable_name

    _write_info_plist(config=config, path=info_plist_path)
    _write_launch_config(
        config=config,
        path=launch_config_path,
        manifest_path=manifest_path,
        token_path=token_path,
        normalized_backend=normalized_backend,
    )
    if config.packaged_executable_path is not None:
        _copy_packaged_executable(
            source_path=config.packaged_executable_path.expanduser(),
            executable_path=executable_path,
        )
    else:
        _write_launcher_script(
            config=config,
            executable_path=executable_path,
        )
    _write_permission_guide(config=config, path=permission_guide_path)
    signing_command = _codesign_helper_app(app_path)

    return ComputerUseHelperAppBuildResult(
        app_path=app_path,
        executable_path=executable_path,
        info_plist_path=info_plist_path,
        launch_config_path=launch_config_path,
        permission_guide_path=permission_guide_path,
        manifest_path=manifest_path,
        token_path=token_path,
        bundle_id=config.bundle_id,
        version=config.version,
        api_version=config.api_version,
        signed=signing_command is not None,
        signing_command=signing_command,
    )


def _write_info_plist(*, config: ComputerUseHelperAppConfig, path: Path) -> None:
    payload: dict[str, Any] = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": config.display_name,
        "CFBundleExecutable": config.executable_name,
        "CFBundleIdentifier": config.bundle_id,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": config.display_name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": config.version,
        "CFBundleVersion": config.version,
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSAppleEventsUsageDescription": (
            "Plato Computer Use Helper controls approved desktop applications "
            "to execute user-confirmed tasks."
        ),
        "NSHighResolutionCapable": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        dump_plist(payload, handle)


def _write_launch_config(
    *,
    config: ComputerUseHelperAppConfig,
    path: Path,
    manifest_path: Path,
    token_path: Path | None,
    normalized_backend: str,
) -> None:
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "development",
        "launcherMode": (
            "packaged-executable"
            if config.packaged_executable_path is not None
            else "external-python-wrapper"
        ),
        "bundleId": config.bundle_id,
        "version": config.version,
        "apiVersion": config.api_version,
        "signingMode": config.signing_mode,
        "bundleSigning": "adhoc-bundle",
        "manifestPath": str(manifest_path),
        "pythonExecutable": config.python_executable,
        "host": config.host,
        "port": config.port,
        "computerUseBackend": normalized_backend,
        "computerUseAllowedApps": list(config.computer_use_allowed_apps),
    }
    if config.packaged_executable_path is not None:
        payload["packagedExecutableSource"] = str(
            config.packaged_executable_path.expanduser()
        )
    if token_path is not None:
        payload["tokenPath"] = str(token_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _copy_packaged_executable(
    *,
    source_path: Path,
    executable_path: Path,
) -> None:
    if not source_path.exists() or not source_path.is_file():
        raise ValueError(f"packaged helper executable not found: {source_path}")
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, executable_path)
    executable_path.chmod(executable_path.stat().st_mode | 0o755)


def _write_launcher_script(
    *,
    config: ComputerUseHelperAppConfig,
    executable_path: Path,
) -> None:
    python_executable = shlex.quote(config.python_executable)
    script = f"""#!/bin/sh
set -eu
exec {python_executable} - "$0" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

from taskweavn.cli.main import app
from taskweavn.server.computer_use_helper_app_entrypoint import build_helper_app_cli_argv

executable_path = Path(sys.argv[1]).resolve()
sys.argv = build_helper_app_cli_argv(executable_path)
app()
PY
"""
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path.write_text(script, encoding="utf-8")
    executable_path.chmod(0o755)


def _write_permission_guide(
    *,
    config: ComputerUseHelperAppConfig,
    path: Path,
) -> None:
    allowed_apps = ", ".join(config.computer_use_allowed_apps) or "none configured"
    launcher_mode = (
        "packaged-executable"
        if config.packaged_executable_path is not None
        else "external-python-wrapper"
    )
    payload = f"""# {config.display_name} Permission Guide

This helper app is the macOS Accessibility permission subject for Plato
computer-use actions.

- Bundle ID: `{config.bundle_id}`
- Version: `{config.version}`
- API version: `{config.api_version}`
- Signing mode: `{config.signing_mode}`
- Bundle signing: `adhoc-bundle`
- Computer-use backend: `{config.computer_use_backend.strip().lower()}`
- Allowed apps: `{allowed_apps}`
- Development Python runtime: `{config.python_executable}`
- Launcher mode: `{launcher_mode}`

Grant Accessibility permission to this helper app, not to Plato, when using the
helper-backed computer-use provider. If the helper is rebuilt with a different
bundle ID, path, or signing identity, macOS may require permission again.

Development note: this scaffold launches the helper through the configured
Python runtime unless `packaged-executable` launcher mode is used. Until release
packaging provides a helper-owned packaged executable, macOS may report or
enforce permissions against that Python runtime. If readiness reports
`external_python_for_app`, grant Accessibility and Automation permissions to the
reported Python runtime or use a packaged helper build.

The dev scaffold ad-hoc signs the full `.app` bundle so Info.plist and
`CFBundleIdentifier` are bound into the code signature. If the helper is rebuilt
at a different path or with a different identity, macOS may require the
Accessibility permission to be refreshed.

The helper listens only on loopback and publishes a startup-token manifest for
Plato to discover. Do not share the manifest token.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _codesign_helper_app(app_path: Path) -> tuple[str, ...] | None:
    if platform.system() != "Darwin":
        return None
    codesign_path = shutil.which("codesign")
    if codesign_path is None:
        return None
    command = (
        codesign_path,
        "--force",
        "--deep",
        "--sign",
        "-",
        "--timestamp=none",
        str(app_path),
    )
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"failed to codesign helper app: {app_path}") from exc
    return command


__all__ = [
    "ComputerUseHelperAppBuildResult",
    "ComputerUseHelperAppConfig",
    "DEFAULT_COMPUTER_USE_HELPER_API_VERSION",
    "DEFAULT_COMPUTER_USE_HELPER_BUNDLE_ID",
    "DEFAULT_COMPUTER_USE_HELPER_DISPLAY_NAME",
    "DEFAULT_COMPUTER_USE_HELPER_EXECUTABLE",
    "build_computer_use_helper_app",
]
