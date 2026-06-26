"""Entrypoint helpers for a packaged Plato Computer Use Helper app executable."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast


def build_helper_app_cli_argv(executable_path: Path) -> list[str]:
    """Build the helper CLI argv from a helper app executable path.

    The executable is expected to live at ``<App>.app/Contents/MacOS/<name>``.
    Both the development shell wrapper and a future packaged helper-owned
    executable use this contract so launch behavior stays identical.
    """

    resolved_executable_path = executable_path.expanduser().resolve()
    contents_dir = resolved_executable_path.parents[1]
    launch_config = _load_launch_config(contents_dir / "Resources" / "helper-launch.json")
    app_path = contents_dir.parent

    argv = [
        "taskweavn",
        "computer-use-helper",
        "--manifest-path",
        _required_str(launch_config, "manifestPath"),
        "--host",
        _required_str(launch_config, "host"),
        "--port",
        str(_required_int(launch_config, "port")),
        "--computer-use-backend",
        _required_str(launch_config, "computerUseBackend"),
        "--helper-path",
        str(app_path),
        "--helper-bundle-id",
        _required_str(launch_config, "bundleId"),
        "--helper-version",
        _required_str(launch_config, "version"),
        "--helper-api-version",
        _required_str(launch_config, "apiVersion"),
        "--helper-signing-mode",
        _required_str(launch_config, "signingMode"),
    ]

    token_path = _optional_str(launch_config.get("tokenPath"))
    if token_path:
        argv.extend(["--token-path", token_path])

    allowed_apps = _string_list(launch_config.get("computerUseAllowedApps"))
    if allowed_apps:
        argv.extend(["--computer-use-allowed-apps", ",".join(allowed_apps)])

    return argv


def main() -> None:
    """Run the helper CLI from the packaged app executable context."""

    from taskweavn.cli.main import app

    sys.argv = build_helper_app_cli_argv(Path(sys.argv[0]))
    app()


def _load_launch_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"helper launch config must be a JSON object: {path}")
    return cast(dict[str, Any], payload)


def _required_str(config: Mapping[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"helper launch config requires string field: {key}")
    return value


def _required_int(config: Mapping[str, Any], key: str) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"helper launch config requires integer field: {key}")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("helper launch config optional string field is invalid")
    return value


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("helper launch config string list field is invalid")
    return value


if __name__ == "__main__":
    main()

