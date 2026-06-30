"""Manual package-backed WeChat Desktop smoke.

Default mode opens WeChat, focuses a contact, drafts a message, and observes
the current chat. It does not submit the draft unless both --allow-submit and
--confirm-submit SEND are provided.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any, cast

from app_control_protocol import ToolEvent, ToolObservation
from computer_use_macos import ComputerUseClient
from wechat_desktop_tool import (
    WeChatDesktopTool,
    draft_message_command,
    focus_contact_command,
    observe_current_chat_command,
    open_wechat_command,
    submit_draft_command,
)


class RecordingObserver:
    """Collect package ToolEvent rows for smoke evidence."""

    def __init__(self) -> None:
        self.events: list[ToolEvent] = []

    def on_event(self, event: ToolEvent) -> None:
        self.events.append(event)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    observer = RecordingObserver()
    observations: list[ToolObservation] = []
    config = _build_config(args)

    app_control = ComputerUseClient.from_config(config)
    tool = WeChatDesktopTool.from_config(app_control, config)
    smoke_id = args.smoke_id or f"wechat-tool-smoke-{uuid.uuid4().hex[:12]}"
    metadata = {
        "smokeId": smoke_id,
        "source": "manual_wechat_desktop_tool_smoke",
    }

    steps = [
        open_wechat_command(
            command_id=f"{smoke_id}:open",
            timeout_ms=args.timeout_ms,
            metadata=metadata,
        ),
        focus_contact_command(
            args.contact,
            command_id=f"{smoke_id}:focus",
            timeout_ms=args.timeout_ms,
            metadata=metadata,
        ),
        draft_message_command(
            args.message,
            command_id=f"{smoke_id}:draft",
            timeout_ms=args.timeout_ms,
            idempotency_key=args.idempotency_key,
            metadata={**metadata, "messageHash": _hash_text(args.message)},
        ),
        observe_current_chat_command(
            command_id=f"{smoke_id}:observe",
            timeout_ms=args.timeout_ms,
            metadata=metadata,
        ),
    ]

    exit_code = 0
    submit_requested = bool(args.allow_submit)
    submit_confirmed = args.confirm_submit == "SEND"
    submit_attempted = False
    submit_succeeded = False
    for command in steps:
        observation = tool.run_command(command, observer=observer)
        observations.append(observation)
        if not observation.success:
            exit_code = 1
            break

    if exit_code == 0 and args.allow_submit:
        if not submit_confirmed:
            observations.append(
                _manual_failure(
                    command_id=f"{smoke_id}:submit",
                    summary="Submit blocked: --confirm-submit SEND is required.",
                    failure_kind="submit_not_confirmed",
                )
            )
            exit_code = 2
        else:
            submit_attempted = True
            observations.append(
                tool.run_command(
                    submit_draft_command(
                        command_id=f"{smoke_id}:submit",
                        timeout_ms=args.timeout_ms,
                        idempotency_key=args.idempotency_key,
                        metadata=metadata,
                    ),
                    observer=observer,
                )
            )
            submit_succeeded = observations[-1].success
            if not submit_succeeded:
                exit_code = 1

    evidence = {
        "kind": "wechat_desktop_tool_manual_smoke",
        "smokeId": smoke_id,
        "contact": args.contact,
        "messagePreview": args.message[:120],
        "messageHash": _hash_text(args.message),
        "submitRequested": submit_requested,
        "submitConfirmed": submit_confirmed,
        "submitAttempted": submit_attempted,
        "submitted": submit_succeeded,
        "config": {
            "backend": args.backend,
            "allowedApps": _split_csv(args.allowed_apps),
            "helperManifestPath": args.helper_manifest_path,
            "helperAppPath": args.helper_app_path,
            "helperAutoLaunch": args.helper_auto_launch,
        },
        "events": [_serialize(event) for event in observer.events],
        "observations": [_serialize(observation) for observation in observations],
    }
    if args.evidence_output is not None:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return exit_code


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("direct", "helper"), default="direct")
    parser.add_argument("--allowed-apps", default="WeChat")
    parser.add_argument("--helper-manifest-path")
    parser.add_argument("--helper-app-path")
    parser.add_argument("--helper-endpoint")
    parser.add_argument("--helper-token")
    parser.add_argument("--helper-auto-launch", action="store_true")
    parser.add_argument("--contact", default="文件传输助手")
    parser.add_argument("--message", required=True)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--idempotency-key")
    parser.add_argument("--smoke-id")
    parser.add_argument("--allow-submit", action="store_true")
    parser.add_argument("--confirm-submit", default="")
    parser.add_argument("--evidence-output", type=Path)
    return parser.parse_args(argv)


def _build_config(args: argparse.Namespace) -> dict[str, Any]:
    allowed_apps = _split_csv(args.allowed_apps)
    return {
        "computer_use": {
            "backend": args.backend,
            "allowed_apps": allowed_apps,
            "allow_coordinate_click": False,
            "screen_recording_required": False,
            "timeout_ms": args.timeout_ms,
        },
        "helper": {
            "manifest_path": args.helper_manifest_path,
            "helper_app_path": args.helper_app_path,
            "endpoint": args.helper_endpoint,
            "token": args.helper_token,
            "allowed_apps": allowed_apps,
            "auto_launch": args.helper_auto_launch,
        },
        "wechat": {
            "app_name": "WeChat",
            "bundle_id": "com.tencent.xinWeChat",
            "submit_key": "Return",
            "default_timeout_ms": args.timeout_ms,
        },
    }


def _manual_failure(
    *,
    command_id: str,
    summary: str,
    failure_kind: str,
) -> ToolObservation:
    return ToolObservation(
        command_id=command_id,
        tool="wechat.desktop",
        operation="submit_draft",
        status="failed",
        success=False,
        summary=summary,
        observation={},
        evidence={},
        timing={},
        failure_kind=failure_kind,
        message=summary,
        recovery_hint="Pass --allow-submit --confirm-submit SEND to submit.",
        retryable=False,
        error=None,
        metadata={},
    )


def _serialize(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(cast(Any, value))
    if isinstance(value, dict):
        return {str(key): _serialize(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
