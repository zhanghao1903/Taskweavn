from __future__ import annotations

import pytest

from taskweavn.server.computer_use_runtime import (
    build_computer_use_runtime,
    parse_computer_use_allowed_apps,
)
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


def test_build_computer_use_runtime_supports_macos_backend() -> None:
    runtime = build_computer_use_runtime(
        backend_name="macos",
        allowed_apps="WeChat,TextEdit",
    )

    assert runtime.enabled is True
    assert runtime.backend_name == "macos"
    assert isinstance(runtime.backend, MacOSComputerUseBackend)


def test_build_computer_use_runtime_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="unsupported computer-use backend"):
        build_computer_use_runtime(backend_name="browser")
