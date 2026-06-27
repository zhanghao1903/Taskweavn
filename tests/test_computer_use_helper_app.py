"""Tests for the dev Plato Computer Use Helper .app scaffold."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from plistlib import load as load_plist

import pytest

from taskweavn.server.computer_use_helper_app import (
    ComputerUseHelperAppConfig,
    build_computer_use_helper_app,
)
from taskweavn.server.computer_use_helper_app_entrypoint import build_helper_app_cli_argv


def test_build_computer_use_helper_app_writes_dev_bundle(tmp_path: Path) -> None:
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"
    manifest_path = tmp_path / "state" / "computer-use-helper.json"
    token_path = tmp_path / "state" / "computer-use-helper.token"

    result = build_computer_use_helper_app(
        ComputerUseHelperAppConfig(
            app_path=app_path,
            manifest_path=manifest_path,
            token_path=token_path,
            python_executable="/usr/bin/python3",
            computer_use_backend="macos",
            computer_use_allowed_apps=("WeChat", "TextEdit"),
        )
    )

    assert result.app_path == app_path
    assert result.manifest_path == manifest_path
    assert result.token_path == token_path
    assert result.info_plist_path.exists()
    assert result.launch_config_path.exists()
    assert result.permission_guide_path.exists()
    assert result.executable_path.exists()
    assert result.executable_path.stat().st_mode & stat.S_IXUSR
    assert isinstance(result.signed, bool)

    with result.info_plist_path.open("rb") as handle:
        plist = load_plist(handle)
    assert plist["CFBundleIdentifier"] == (
        "com.taskweavn.plato.computer-use-helper.dev"
    )
    assert plist["CFBundleExecutable"] == "PlatoComputerUseHelper"
    assert plist["LSUIElement"] is True

    launch_config = json.loads(result.launch_config_path.read_text(encoding="utf-8"))
    assert launch_config["schemaVersion"] == 1
    assert launch_config["mode"] == "development"
    assert launch_config["launcherMode"] == "external-python-wrapper"
    assert launch_config["manifestPath"] == str(manifest_path)
    assert launch_config["tokenPath"] == str(token_path)
    assert launch_config["pythonExecutable"] == "/usr/bin/python3"
    assert launch_config["computerUseBackend"] == "macos"
    assert launch_config["computerUseAllowedApps"] == ["WeChat", "TextEdit"]
    assert launch_config["apiVersion"] == "plato.computer_use_helper.v1"
    assert launch_config["signingMode"] == "development-app"
    assert launch_config["bundleSigning"] == "adhoc-bundle"

    launcher = result.executable_path.read_text(encoding="utf-8")
    assert "build_helper_app_cli_argv" in launcher
    assert "taskweavn.server.computer_use_helper_app_entrypoint" in launcher
    assert "/usr/bin/python3" in launcher

    permission_guide = result.permission_guide_path.read_text(encoding="utf-8")
    assert "# Plato Computer Use Helper Dev Permission Guide" in permission_guide
    assert "Bundle ID: `com.taskweavn.plato.computer-use-helper.dev`" in permission_guide
    assert "Computer-use backend: `macos`" in permission_guide
    assert "Allowed apps: `WeChat, TextEdit`" in permission_guide
    assert "Development Python runtime: `/usr/bin/python3`" in permission_guide
    assert "Launcher mode: `external-python-wrapper`" in permission_guide
    assert "Bundle signing: `adhoc-bundle`" in permission_guide
    assert "Grant Accessibility permission to this helper app" in permission_guide
    assert "ad-hoc signs the full `.app` bundle" in permission_guide
    assert "external_python_for_app" in permission_guide


def test_helper_app_entrypoint_builds_cli_argv_from_launch_config(
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"
    manifest_path = tmp_path / "state" / "computer-use-helper.json"
    token_path = tmp_path / "state" / "computer-use-helper.token"

    result = build_computer_use_helper_app(
        ComputerUseHelperAppConfig(
            app_path=app_path,
            manifest_path=manifest_path,
            token_path=token_path,
            python_executable="/usr/bin/python3",
            port=49152,
            computer_use_backend="macos",
            computer_use_allowed_apps=("WeChat", "TextEdit"),
        )
    )

    assert build_helper_app_cli_argv(result.executable_path) == [
        "taskweavn",
        "computer-use-helper",
        "--manifest-path",
        str(manifest_path),
        "--host",
        "127.0.0.1",
        "--port",
        "49152",
        "--computer-use-backend",
        "macos",
        "--helper-path",
        str(app_path),
        "--helper-bundle-id",
        "com.taskweavn.plato.computer-use-helper.dev",
        "--helper-version",
        "0.1.0",
        "--helper-api-version",
        "plato.computer_use_helper.v1",
        "--helper-signing-mode",
        "development-app",
        "--token-path",
        str(token_path),
        "--computer-use-allowed-apps",
        "WeChat,TextEdit",
    ]


def test_build_computer_use_helper_app_can_copy_packaged_executable(
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"
    manifest_path = tmp_path / "state" / "computer-use-helper.json"
    packaged_executable = tmp_path / "dist" / "PlatoComputerUseHelper"
    packaged_executable.parent.mkdir(parents=True)
    packaged_executable.write_text("#!/bin/sh\necho packaged-helper\n", encoding="utf-8")
    packaged_executable.chmod(0o755)

    result = build_computer_use_helper_app(
        ComputerUseHelperAppConfig(
            app_path=app_path,
            manifest_path=manifest_path,
            packaged_executable_path=packaged_executable,
            computer_use_backend="macos",
            computer_use_allowed_apps=("WeChat",),
        )
    )

    assert result.executable_path.read_text(encoding="utf-8") == (
        "#!/bin/sh\necho packaged-helper\n"
    )
    assert result.executable_path.stat().st_mode & stat.S_IXUSR
    launch_config = json.loads(result.launch_config_path.read_text(encoding="utf-8"))
    assert launch_config["launcherMode"] == "packaged-executable"
    assert launch_config["packagedExecutableSource"] == str(packaged_executable)
    permission_guide = result.permission_guide_path.read_text(encoding="utf-8")
    assert "Launcher mode: `packaged-executable`" in permission_guide


def test_build_computer_use_helper_app_requires_existing_packaged_executable(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="packaged helper executable not found"):
        build_computer_use_helper_app(
            ComputerUseHelperAppConfig(
                app_path=tmp_path / "Plato Computer Use Helper Dev.app",
                manifest_path=tmp_path / "computer-use-helper.json",
                packaged_executable_path=tmp_path / "missing-helper",
            )
        )


def test_build_computer_use_helper_app_rejects_recursive_backend(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="recursively launch helper backend"):
        build_computer_use_helper_app(
            ComputerUseHelperAppConfig(
                app_path=tmp_path / "Plato Computer Use Helper Dev.app",
                manifest_path=tmp_path / "computer-use-helper.json",
                computer_use_backend="helper",
            )
        )


def test_build_computer_use_helper_app_requires_app_suffix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must end with .app"):
        build_computer_use_helper_app(
            ComputerUseHelperAppConfig(
                app_path=tmp_path / "Plato Computer Use Helper Dev",
                manifest_path=tmp_path / "computer-use-helper.json",
            )
        )
