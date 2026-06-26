"""Minimal production entry point for the packaged Plato sidecar."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_STARTUP_TIMING_STARTED_AT = time.perf_counter()


def main(argv: Sequence[str] | None = None) -> int:
    _mark_startup_timing("python_entry_main_begin")
    args = _parse_args(argv)
    _mark_startup_timing(
        "python_entry_args_parsed",
        hasGlobalSettingsRoot=args.global_settings_root is not None,
        host=args.host,
        hasWorkspaceRegistry=args.workspace_registry_json is not None,
        port=args.port,
    )
    return _serve(args)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the local Plato sidecar runtime.",
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--workspace-registry-json",
        help="JSON workspace registry passed by the packaged Electron launcher.",
    )
    parser.add_argument(
        "--global-settings-root",
        type=Path,
        help=(
            "Plato-level settings root. When provided, Settings config is shared "
            "across workspaces."
        ),
    )
    parser.add_argument(
        "--computer-use-backend",
        default=os.environ.get("PLATO_COMPUTER_USE_BACKEND", "disabled"),
        help=(
            "Optional computer-use backend for execution tools. "
            "Valid values: disabled, helper, macos."
        ),
    )
    parser.add_argument(
        "--computer-use-allowed-apps",
        default=os.environ.get("PLATO_COMPUTER_USE_ALLOWED_APPS"),
        help=(
            "Comma-separated macOS app allowlist for computer-use, "
            "for example: WeChat,TextEdit."
        ),
    )
    parser.set_defaults(
        enable_read_only_inquiry_llm=_env_bool(
            "PLATO_ENABLE_READ_ONLY_INQUIRY_LLM",
            default=True,
        )
    )
    parser.add_argument(
        "--enable-read-only-inquiry-llm",
        dest="enable_read_only_inquiry_llm",
        action="store_true",
        help=(
            "Enable guarded LLM-rendered Read-Only Inquiry answers. "
            "This is the default unless PLATO_ENABLE_READ_ONLY_INQUIRY_LLM=0 "
            "or --disable-read-only-inquiry-llm is provided."
        ),
    )
    parser.add_argument(
        "--disable-read-only-inquiry-llm",
        dest="enable_read_only_inquiry_llm",
        action="store_false",
        help="Disable guarded LLM-rendered Read-Only Inquiry answers.",
    )
    return parser.parse_args(argv)


def _serve(args: argparse.Namespace) -> int:
    import_started_at = time.perf_counter()
    _mark_startup_timing("python_sidecar_import_begin")
    from taskweavn.server.computer_use_runtime import build_computer_use_runtime
    from taskweavn.server.main_page import (
        MainPageSidecarConfig,
        MainPageSidecarDependencies,
        WorkspaceRegistryEntry,
        build_main_page_sidecar_app,
    )

    _mark_startup_timing(
        "python_sidecar_import_ready",
        importElapsedMs=(time.perf_counter() - import_started_at) * 1000,
    )
    workspace_registry = _parse_workspace_registry_json(
        args.workspace_registry_json,
        workspace_registry_entry=WorkspaceRegistryEntry,
    )
    _mark_startup_timing(
        "python_sidecar_build_begin",
        workspaceRegistryCount=len(workspace_registry),
    )
    computer_use_runtime = build_computer_use_runtime(
        backend_name=args.computer_use_backend,
        allowed_apps=args.computer_use_allowed_apps,
    )
    sidecar = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=args.workspace,
            host=args.host,
            port=args.port,
            workspace_registry=workspace_registry,
            global_settings_root=args.global_settings_root,
            enable_read_only_inquiry_llm=args.enable_read_only_inquiry_llm,
            enable_computer_use_tool=computer_use_runtime.enabled,
            computer_use_backend_name=computer_use_runtime.backend_name,
            computer_use_allowed_apps=computer_use_runtime.allowed_apps,
        ),
        MainPageSidecarDependencies(
            computer_use_backend=computer_use_runtime.backend,
        ),
    )
    try:
        sidecar.start_in_thread()
        _mark_startup_timing("python_sidecar_server_ready", baseUrl=sidecar.base_url)
        print(json.dumps({"baseUrl": sidecar.base_url}, indent=2), flush=True)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0
    finally:
        _mark_startup_timing("python_sidecar_shutdown")
        sidecar.close()


def _env_bool(name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_workspace_registry_json(
    raw: str | None,
    *,
    workspace_registry_entry: type[Any],
) -> tuple[Any, ...]:
    if raw is None or raw.strip() == "":
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            "workspace registry must be valid JSON"
        ) from exc
    if not isinstance(payload, list):
        raise argparse.ArgumentTypeError("workspace registry must be a JSON array")

    entries: list[Any] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise argparse.ArgumentTypeError(
                f"workspace registry entry {index} must be an object"
            )
        workspace_id = item.get("workspaceId")
        root_path = item.get("rootPath")
        label = item.get("label")
        if not isinstance(workspace_id, str) or not workspace_id:
            raise argparse.ArgumentTypeError(
                f"workspace registry entry {index} missing workspaceId"
            )
        if not isinstance(root_path, str) or not root_path:
            raise argparse.ArgumentTypeError(
                f"workspace registry entry {index} missing rootPath"
            )
        if not isinstance(label, str) or not label:
            raise argparse.ArgumentTypeError(
                f"workspace registry entry {index} missing label"
            )
        entries.append(
            workspace_registry_entry(
                workspace_id=workspace_id,
                root_path=Path(root_path),
                label=label,
                is_current=item.get("isCurrent") is True,
                last_opened_at=(
                    item.get("lastOpenedAt")
                    if isinstance(item.get("lastOpenedAt"), str)
                    else None
                ),
            )
        )
    return tuple(entries)


def _mark_startup_timing(event: str, **attributes: Any) -> None:
    payload = {
        "schemaVersion": "plato.startup_timing.v1",
        "event": event,
        "source": "python-sidecar",
        "startupId": os.environ.get("PLATO_STARTUP_ID"),
        "pid": os.getpid(),
        "timestamp": _iso_timestamp(),
        "elapsedMs": round((time.perf_counter() - _STARTUP_TIMING_STARTED_AT) * 1000, 2),
        **_sanitize_startup_timing_attributes(attributes),
    }
    print(f"[plato-startup-timing] {json.dumps(payload, sort_keys=True)}", flush=True)


def _sanitize_startup_timing_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in attributes.items():
        if not key.replace("_", "").replace("-", "").isalnum() or len(key) > 64:
            continue
        if isinstance(value, str):
            sanitized[key] = value[:160]
        elif isinstance(value, bool | int) or value is None:
            sanitized[key] = value
        elif isinstance(value, float):
            sanitized[key] = round(value, 2)
    return sanitized


def _iso_timestamp() -> str:
    return (
        time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        + f".{int((time.time() % 1) * 1000):03d}Z"
    )


if __name__ == "__main__":
    raise SystemExit(main())
