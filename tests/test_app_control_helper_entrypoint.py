from __future__ import annotations

import json
from pathlib import Path

import pytest

from taskweavn.server.app_control_helper import (
    _parse_allowed_apps,
    _parse_args,
    _parse_bundle_ids,
)


def test_helper_entrypoint_parses_fixed_process_inputs() -> None:
    args = _parse_args(
        [
            "--socket-path",
            "/tmp/plato.sock",
            "--token-path",
            "/tmp/plato.token",
            "--manifest-path",
            "/tmp/plato.json",
            "--bundle-id",
            "com.taskweavn.plato.computer-use-helper.dev",
            "--app-path",
            "/Applications/Plato Computer Use Helper Dev.app",
            "--allowed-apps",
            "WeChat, TextEdit",
            "--allowed-app-bundle-ids-json",
            json.dumps({"WeChat": "com.tencent.xinWeChat"}),
            "--timeout-ms",
            "12000",
        ]
    )

    assert str(args.socket_path) == "/tmp/plato.sock"
    assert args.bundle_id == "com.taskweavn.plato.computer-use-helper.dev"
    assert args.app_path == Path("/Applications/Plato Computer Use Helper Dev.app")
    assert _parse_allowed_apps(args.allowed_apps) == ("WeChat", "TextEdit")
    assert _parse_bundle_ids(args.allowed_app_bundle_ids_json) == {
        "WeChat": "com.tencent.xinWeChat"
    }
    assert args.timeout_ms == 12_000


def test_helper_entrypoint_rejects_invalid_timeout() -> None:
    with pytest.raises(SystemExit):
        _parse_args(
            [
                "--socket-path",
                "/tmp/plato.sock",
                "--token-path",
                "/tmp/plato.token",
                "--manifest-path",
                "/tmp/plato.json",
                "--bundle-id",
                "com.taskweavn.plato.computer-use-helper.dev",
                "--timeout-ms",
                "0",
            ]
        )


def test_helper_entrypoint_rejects_non_string_bundle_id_values() -> None:
    with pytest.raises(ValueError, match="string-to-string"):
        _parse_bundle_ids('{"WeChat": 1}')
