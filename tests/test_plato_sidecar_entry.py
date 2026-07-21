from __future__ import annotations

import pytest

from taskweavn.server.plato_sidecar import _parse_args


def test_plato_sidecar_parse_args_reads_read_only_inquiry_llm_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", "1")

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.enable_read_only_inquiry_llm is True


def test_plato_sidecar_parse_args_defaults_read_only_inquiry_llm_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", raising=False)

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.enable_read_only_inquiry_llm is True


def test_plato_sidecar_parse_args_can_disable_read_only_inquiry_llm_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", "0")

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.enable_read_only_inquiry_llm is False


def test_plato_sidecar_parse_args_can_disable_read_only_inquiry_llm_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM", raising=False)

    args = _parse_args(
        [
            "--workspace",
            "/tmp/workspace",
            "--port",
            "0",
            "--disable-read-only-inquiry-llm",
        ]
    )

    assert args.enable_read_only_inquiry_llm is False


def test_plato_sidecar_parse_args_reads_computer_use_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATO_COMPUTER_USE_BACKEND", "macos")
    monkeypatch.setenv("PLATO_COMPUTER_USE_ALLOWED_APPS", "WeChat,TextEdit")
    monkeypatch.setenv("PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK", "0")

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.computer_use_backend == "macos"
    assert args.computer_use_allowed_apps == "WeChat,TextEdit"
    assert args.computer_use_allow_coordinate_click is False


def test_plato_sidecar_defaults_coordinate_click_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK", raising=False)

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.computer_use_allow_coordinate_click is True


def test_plato_sidecar_parse_args_computer_use_flags_override_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATO_COMPUTER_USE_BACKEND", "disabled")
    monkeypatch.setenv("PLATO_COMPUTER_USE_ALLOWED_APPS", "TextEdit")

    args = _parse_args(
        [
            "--workspace",
            "/tmp/workspace",
            "--port",
            "0",
            "--computer-use-backend",
            "macos",
            "--computer-use-allowed-apps",
            "WeChat",
        ]
    )

    assert args.computer_use_backend == "macos"
    assert args.computer_use_allowed_apps == "WeChat"


def test_plato_sidecar_parse_args_reads_electron_owned_helper_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATO_COMPUTER_USE_HELPER_MANIFEST", "/tmp/helper.json")

    args = _parse_args(["--workspace", "/tmp/workspace", "--port", "0"])

    assert args.computer_use_helper_manifest == "/tmp/helper.json"
    assert not hasattr(args, "computer_use_helper_app_path")
    assert not hasattr(args, "computer_use_helper_auto_launch")
