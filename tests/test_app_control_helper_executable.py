from __future__ import annotations

import sys
from typing import Any

from computer_use_macos import _coordinate_click

from taskweavn.server.app_control_helper_executable import main


def test_frozen_helper_entrypoint_supports_package_worker_command() -> None:
    original_argv = sys.argv
    try:
        result = main(
            [
                "-c",
                "import sys; assert sys.argv == ['-c', 'payload']",
                "payload",
            ]
        )
    finally:
        sys.argv = original_argv

    assert result == 0


def test_frozen_helper_entrypoint_supports_unbuffered_package_worker() -> None:
    original_argv = sys.argv
    try:
        result = main(
            [
                "-u",
                "-c",
                "import sys; assert sys.argv == ['-c', 'payload']",
                "payload",
            ]
        )
    finally:
        sys.argv = original_argv

    assert result == 0


def test_frozen_helper_entrypoint_supports_coordinate_click_module(
    monkeypatch: Any,
) -> None:
    calls: list[list[str]] = []

    def fake_coordinate_click_main(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr(_coordinate_click, "main", fake_coordinate_click_main)

    result = main(
        [
            "-u",
            "-m",
            "computer_use_macos._coordinate_click",
            "120",
            "240",
        ]
    )

    assert result == 0
    assert calls == [["120", "240"]]


def test_frozen_helper_entrypoint_rejects_unknown_worker_module(capsys: Any) -> None:
    result = main(["-m", "untrusted.worker", "payload"])

    assert result == 2
    assert "unsupported Helper worker module" in capsys.readouterr().err
