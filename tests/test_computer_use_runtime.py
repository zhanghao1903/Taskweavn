from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.execution_plane import LOCAL_MACOS_APP_CONTROL_ENV_ID
from taskweavn.server.computer_use_runtime import (
    build_computer_use_runtime,
    build_execution_env_registry,
    parse_computer_use_allowed_apps,
    resolve_computer_use_runtime,
)
from taskweavn.server.runtime_config_consumers import RuntimeComputerUseSettings
from taskweavn.tools import MacOSComputerUseBackend


def test_parse_computer_use_allowed_apps_from_csv() -> None:
    assert parse_computer_use_allowed_apps("WeChat, TextEdit,, Finder ") == (
        "WeChat",
        "TextEdit",
        "Finder",
    )


def test_parse_computer_use_allowed_apps_from_sequence() -> None:
    assert parse_computer_use_allowed_apps(["WeChat", " ", "TextEdit"]) == (
        "WeChat",
        "TextEdit",
    )


def test_build_computer_use_runtime_defaults_disabled() -> None:
    runtime = build_computer_use_runtime(backend_name=None)

    assert runtime.enabled is False
    assert runtime.backend is None
    assert runtime.backend_name == "disabled"
    assert runtime.allowed_apps == ()


def test_build_computer_use_runtime_supports_macos_backend() -> None:
    runtime = build_computer_use_runtime(
        backend_name="macos",
        allowed_apps="WeChat,TextEdit",
    )

    assert runtime.enabled is True
    assert runtime.backend_name == "macos"
    assert runtime.allowed_apps == ("WeChat", "TextEdit")
    assert isinstance(runtime.backend, MacOSComputerUseBackend)


def test_resolve_computer_use_runtime_builds_backend_from_settings() -> None:
    runtime = resolve_computer_use_runtime(
        computer_use_settings=RuntimeComputerUseSettings(
            enabled=True,
            backend="macos",
            allowed_apps=("WeChat",),
            allow_coordinate_click=True,
            config_hash="hash-1",
        ),
        computer_use_backend=None,
    )

    assert runtime.enabled is True
    assert runtime.backend_name == "macos"
    assert runtime.allowed_apps == ("WeChat",)
    assert isinstance(runtime.backend, MacOSComputerUseBackend)
    assert runtime.app_control_config is not None
    assert runtime.app_control_config.allow_coordinate_click is True


def test_build_computer_use_runtime_supports_helper_backend() -> None:
    manifest_path = Path("/tmp/app-control-service.json")
    runtime = build_computer_use_runtime(
        backend_name="helper",
        allowed_apps="WeChat,TextEdit",
        helper_manifest_path=str(manifest_path),
    )

    assert runtime.enabled is True
    assert runtime.backend_name == "helper"
    assert runtime.allowed_apps == ("WeChat", "TextEdit")
    assert isinstance(runtime.backend, MacOSComputerUseBackend)
    assert runtime.app_control_config is not None
    assert runtime.app_control_config.backend == "helper"
    assert runtime.app_control_config.helper_manifest_path == manifest_path


def test_build_computer_use_runtime_passes_electron_owned_manifest(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "helper.json"

    runtime = build_computer_use_runtime(
        backend_name="helper",
        helper_manifest_path=str(manifest_path),
    )

    assert isinstance(runtime.backend, MacOSComputerUseBackend)
    assert runtime.app_control_config is not None
    assert runtime.app_control_config.helper_manifest_path == manifest_path


def test_build_computer_use_runtime_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="disabled, helper, macos"):
        build_computer_use_runtime(backend_name="browser")


def test_build_execution_env_registry_uses_local_macos_app_control_when_enabled() -> None:
    registry = build_execution_env_registry(
        computer_use_settings=RuntimeComputerUseSettings(
            enabled=True,
            backend="helper",
            allowed_apps=("WeChat",),
            allow_coordinate_click=True,
            config_hash="hash-1",
        )
    )

    [env] = registry.list()

    assert env.env_id == LOCAL_MACOS_APP_CONTROL_ENV_ID
    assert env.display_name == "Local macOS App Control"
    assert "computer_use" in env.capabilities
    assert "communication.wechat_desktop_send" in env.capabilities
    assert "wechat_desktop" in env.tool_pool


def test_build_execution_env_registry_does_not_advertise_wechat_without_runtime() -> None:
    registry = build_execution_env_registry(
        computer_use_settings=RuntimeComputerUseSettings(
            enabled=True,
            backend="helper",
            allowed_apps=("WeChat",),
            allow_coordinate_click=True,
            config_hash="hash-1",
        ),
        computer_use_available=False,
    )

    [env] = registry.list()

    assert env.env_id == "local-default"
    assert "computer_use" not in env.capabilities
    assert "communication.wechat_desktop_send" not in env.capabilities
    assert "wechat_desktop" not in env.tool_pool


def test_build_execution_env_registry_keeps_default_env_when_disabled() -> None:
    registry = build_execution_env_registry(
        computer_use_settings=RuntimeComputerUseSettings(
            enabled=False,
            backend="disabled",
            allowed_apps=(),
            allow_coordinate_click=False,
            config_hash="hash-1",
        )
    )

    [env] = registry.list()

    assert env.env_id == "local-default"
    assert "communication.wechat_desktop_send" not in env.capabilities
