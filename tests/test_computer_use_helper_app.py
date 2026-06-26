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
    assert result.executable_path.exists()
    assert result.executable_path.stat().st_mode & stat.S_IXUSR

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
    assert launch_config["manifestPath"] == str(manifest_path)
    assert launch_config["tokenPath"] == str(token_path)
    assert launch_config["computerUseBackend"] == "macos"
    assert launch_config["computerUseAllowedApps"] == ["WeChat", "TextEdit"]
    assert launch_config["apiVersion"] == "plato.computer_use_helper.v1"

    launcher = result.executable_path.read_text(encoding="utf-8")
    assert "helper-launch.json" in launcher
    assert "computer-use-helper" in launcher
    assert "/usr/bin/python3" in launcher


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
