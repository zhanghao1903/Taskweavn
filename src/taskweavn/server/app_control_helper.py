"""Process entrypoint for Plato's package-backed app-control Helper service."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from taskweavn.integrations.app_control import (
    AppControlServiceHost,
    AppControlServiceHostConfig,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object | None) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    host = AppControlServiceHost(
        AppControlServiceHostConfig(
            socket_path=args.socket_path,
            token_path=args.token_path,
            manifest_path=args.manifest_path,
            bundle_id=args.bundle_id,
            app_path=args.app_path,
            allowed_apps=_parse_allowed_apps(args.allowed_apps),
            allowed_app_bundle_ids=_parse_bundle_ids(args.allowed_app_bundle_ids_json),
            allow_coordinate_click=args.allow_coordinate_click,
            screen_recording_required=args.screen_recording_required,
            timeout_ms=args.timeout_ms,
        )
    )
    try:
        manifest = host.start()
        print(json.dumps(manifest.to_dict(), ensure_ascii=False), flush=True)
        stop_event.wait()
    except Exception as exc:  # noqa: BLE001 - process boundary emits a stable failure.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failureKind": "service_start_failed",
                    "message": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )
        return 1
    finally:
        host.stop()
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start Plato Computer Use Helper's local command service.",
    )
    parser.add_argument("--socket-path", type=Path, required=True)
    parser.add_argument("--token-path", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--app-path", type=Path)
    parser.add_argument("--allowed-apps", default="")
    parser.add_argument("--allowed-app-bundle-ids-json")
    parser.add_argument("--allow-coordinate-click", action="store_true")
    parser.add_argument("--screen-recording-required", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    args = parser.parse_args(argv)
    if args.timeout_ms <= 0:
        parser.error("--timeout-ms must be positive")
    return args


def _parse_allowed_apps(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_bundle_ids(raw: str | None) -> Mapping[str, str] | None:
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("allowed app bundle ids must be valid JSON") from exc
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in payload.items()
    ):
        raise ValueError("allowed app bundle ids must be a string-to-string JSON object")
    return _string_mapping(payload)


def _string_mapping(payload: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value) for key, value in payload.items()}


if __name__ == "__main__":
    raise SystemExit(main())
