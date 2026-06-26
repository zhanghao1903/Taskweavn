from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.integrations.wechat_desktop import WeChatDesktopHelperAdapter
from taskweavn.server.computer_use_runtime import (
    build_computer_use_runtime,
    build_wechat_runtime_adapter,
    parse_computer_use_allowed_apps,
)
from taskweavn.tools import ComputerUseHelperBackend, MacOSComputerUseBackend
from taskweavn.types import ComputerUseAction


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


def test_build_computer_use_runtime_supports_helper_backend() -> None:
    runtime = build_computer_use_runtime(
        backend_name="helper",
        allowed_apps="WeChat,TextEdit",
        helper_endpoint="http://127.0.0.1:49321",
        helper_token="test-token",
    )

    assert runtime.enabled is True
    assert runtime.backend_name == "helper"
    assert runtime.allowed_apps == ("WeChat", "TextEdit")
    assert isinstance(runtime.backend, ComputerUseHelperBackend)


def test_build_computer_use_runtime_passes_helper_launch_config(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "helper.json"
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"

    runtime = build_computer_use_runtime(
        backend_name="helper",
        helper_manifest_path=str(manifest_path),
        helper_app_path=str(app_path),
        helper_auto_launch=True,
    )

    assert isinstance(runtime.backend, ComputerUseHelperBackend)
    assert runtime.backend._config.endpoint_manifest_path == manifest_path
    assert runtime.backend._config.helper_app_path == app_path
    assert runtime.backend._config.helper_auto_launch is True


def test_build_computer_use_runtime_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="disabled, helper, macos"):
        build_computer_use_runtime(backend_name="browser")


def test_build_wechat_runtime_adapter_uses_helper_wechat_api_client() -> None:
    helper_backend = ComputerUseHelperBackend(client=_FakeHelperWeChatClient())

    adapter = build_wechat_runtime_adapter(helper_backend)

    assert isinstance(adapter, WeChatDesktopHelperAdapter)


class _FakeHelperWeChatClient:
    def readiness(self) -> dict[str, object]:
        return {"status": "ready", "summary": "ready"}

    def execute(self, action: ComputerUseAction) -> dict[str, object]:
        return {"status": "ok", "summary": action.instruction}

    def wechat_draft_message(self, **kwargs: object) -> dict[str, object]:
        return {"status": "ok", "summary": "drafted"}

    def wechat_send_confirmed(self, **kwargs: object) -> dict[str, object]:
        return {"status": "sent", "summary": "sent"}
