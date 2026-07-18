"""Manual package-backed WeChat Desktop smoke through the local service.

The script follows the SDK package example: it connects to a local
``computer-use-macos serve`` process, adapts that service to the app-control
protocol, and then invokes ``WeChatDesktopTool``. It requires
``--allow-focus-select`` for package contact selection and does not submit the
draft unless both ``--allow-submit`` and ``--confirm-submit SEND`` are present.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from app_control_protocol import (
    ProtocolValidationError,
    ToolCommand,
    ToolEvent,
    ToolObservation,
    load_app_control_config,
    validate_protocol_payload,
)
from computer_use_macos import UnixSocketServiceClient, readiness_command
from wechat_desktop_tool import (
    WeChatDesktopTool,
    draft_message_command,
    observe_current_chat_command,
    open_contact_command,
    open_wechat_command,
    submit_draft_command,
)

DEFAULT_CONFIG = "./app-control.toml"
DEFAULT_SOCKET_PATH = "/tmp/app-control.sock"


class LocalServiceAppControlAdapter:
    """Adapt the package Unix-socket client to the app-control client protocol."""

    def __init__(self, service_client: Any) -> None:
        self._service_client = service_client

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        tool_command = _coerce_command(command)
        responses = self._service_client.run_command(
            tool_command.to_dict(),
            action="stream" if observer is not None else "run",
            request_id="smoke_" + uuid.uuid4().hex,
        )
        if not responses:
            raise RuntimeError("local app-control service returned no response")

        final_response: dict[str, Any] | None = None
        for raw_response in responses:
            response = dict(raw_response)
            if response.get("status") == "event":
                _publish_service_event(response, observer)
                continue
            try:
                validate_protocol_payload("service_response", response)
            except ProtocolValidationError as exc:
                raise RuntimeError(f"invalid service response: {exc}") from exc
            final_response = response

        if final_response is None:
            raise RuntimeError("local app-control service returned no final response")
        if not final_response.get("success"):
            raise RuntimeError(str(final_response.get("error", final_response)))

        observation = final_response.get("observation")
        if not isinstance(observation, dict):
            raise RuntimeError("service response does not include an observation")
        try:
            validate_protocol_payload("observation", observation)
        except ProtocolValidationError as exc:
            raise RuntimeError(f"invalid service observation: {exc}") from exc
        return ToolObservation.from_dict(observation)


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
    smoke_id = args.smoke_id or f"wechat-tool-smoke-{uuid.uuid4().hex[:12]}"
    metadata = {
        "smokeId": smoke_id,
        "source": "manual_wechat_desktop_tool_smoke",
    }

    try:
        socket_path, token, service_timeout = _service_settings(args)
        service_client = UnixSocketServiceClient(
            socket_path,
            token=token,
            timeout=service_timeout,
        )
        app_control = LocalServiceAppControlAdapter(service_client)
        tool_config = _tool_config(args)
        tool = WeChatDesktopTool.from_config(app_control, tool_config)
    except Exception as exc:
        print(f"wechat desktop smoke setup failed: {exc}", file=sys.stderr)
        return 2

    exit_code = 0
    submit_requested = bool(args.allow_submit)
    submit_confirmed = args.confirm_submit == "SEND"
    submit_attempted = False
    submit_succeeded = False

    if exit_code == 0:
        observation = app_control.run_command(
            readiness_command(
                command_id=f"{smoke_id}:readiness",
                timeout_ms=args.timeout_ms,
                metadata=metadata,
            ),
            observer=observer,
        )
        observations.append(observation)
        if not observation.success:
            exit_code = 1

    if exit_code == 0:
        command = open_wechat_command(
            command_id=f"{smoke_id}:open",
            timeout_ms=args.timeout_ms,
            metadata=metadata,
        )
        observation = tool.run_command(command, observer=observer)
        observations.append(observation)
        if not observation.success:
            exit_code = 1

    if exit_code == 0:
        if args.allow_focus_select:
            observation = tool.run_command(
                open_contact_command(
                    args.contact,
                    command_id=f"{smoke_id}:open-contact",
                    timeout_ms=args.timeout_ms,
                    metadata=metadata,
                ),
                observer=observer,
            )
            observations.append(observation)
            if not observation.success:
                exit_code = 1
        else:
            observations.append(
                _manual_failure(
                    command_id=f"{smoke_id}:contact-mode",
                    operation="open_contact",
                    summary=(
                        "Contact selection was not authorized. The smoke requires "
                        "--allow-focus-select."
                    ),
                    failure_kind="contact_selection_not_authorized",
                    recovery_hint="Pass --allow-focus-select to run package contact selection.",
                )
            )
            exit_code = 2

    for command in _post_contact_steps(args, smoke_id=smoke_id, metadata=metadata):
        if exit_code != 0:
            break
        observation = tool.run_command(command, observer=observer)
        observations.append(observation)
        if not observation.success:
            exit_code = 1

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
        "allowFocusSelect": args.allow_focus_select,
        "contactSelectionMode": "open_contact" if args.allow_focus_select else "blocked",
        "submitRequested": submit_requested,
        "submitConfirmed": submit_confirmed,
        "submitAttempted": submit_attempted,
        "submitted": submit_succeeded,
        "config": {
            "transport": "unix_socket",
            "socketPath": socket_path,
            "configPath": str(_existing_config_or_none(args.config))
            if _existing_config_or_none(args.config)
            else None,
            "serviceTimeoutSeconds": service_timeout,
            "searchHotkey": _split_csv(args.search_hotkey),
            "searchClearHotkey": _split_csv(args.search_clear_hotkey),
        },
        "events": [_serialize_event(event) for event in observer.events],
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
    parser.add_argument(
        "--config",
        default=(
            os.environ.get("WECHAT_TOOL_CONFIG")
            or os.environ.get("APP_CONTROL_CONFIG")
            or DEFAULT_CONFIG
        ),
    )
    parser.add_argument(
        "--socket-path",
        default=(
            os.environ.get("WECHAT_TOOL_SOCKET_PATH")
            or os.environ.get("APP_CONTROL_SOCKET_PATH")
        ),
    )
    parser.add_argument("--token", default=os.environ.get("WECHAT_TOOL_TOKEN"))
    parser.add_argument("--token-file", default=os.environ.get("WECHAT_TOOL_TOKEN_FILE"))
    parser.add_argument("--search-hotkey", default="Command,K")
    parser.add_argument("--search-clear-hotkey", default="Command,A")
    parser.add_argument("--contact", default="文件传输助手")
    parser.add_argument("--message", required=True)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--idempotency-key")
    parser.add_argument("--smoke-id")
    parser.add_argument("--allow-focus-select", action="store_true")
    parser.add_argument("--allow-submit", action="store_true")
    parser.add_argument("--confirm-submit", default="")
    parser.add_argument("--evidence-output", type=Path)
    return parser.parse_args(argv)


def _tool_config(args: argparse.Namespace) -> str | Path | dict[str, Any] | None:
    config_path = _existing_config_or_none(args.config)
    if config_path is not None:
        return config_path
    return {
        "computer_use": {
            "backend": "direct",
            "allowed_apps": ["WeChat"],
            "allow_coordinate_click": False,
            "screen_recording_required": False,
            "timeout_ms": args.timeout_ms,
        },
        "wechat": {
            "app_name": "WeChat",
            "bundle_id": "com.tencent.xinWeChat",
            "search_hotkey": _split_csv(args.search_hotkey),
            "search_clear_hotkey": _split_csv(args.search_clear_hotkey),
            "clear_key": "Delete",
            "submit_key": "Return",
            "default_timeout_ms": args.timeout_ms,
        },
    }


def _service_settings(args: argparse.Namespace) -> tuple[str, str | None, float]:
    if args.token and args.token_file:
        raise ValueError("--token and --token-file are mutually exclusive")

    socket_path = args.socket_path
    token = args.token
    config_path = _existing_config_or_none(args.config)
    if config_path is not None:
        config = load_app_control_config(config_path)
        helper = config.helper
        if socket_path is None and helper.endpoint:
            if helper.transport != "unix_socket":
                raise ValueError("helper.transport must be unix_socket")
            socket_path = helper.endpoint
        if token is None and not args.token_file:
            token = helper.token

    if socket_path is None:
        socket_path = DEFAULT_SOCKET_PATH
    if token is None and args.token_file:
        token_path = Path(args.token_file).expanduser()
        if not token_path.exists():
            raise ValueError(f"token file does not exist: {token_path}")
        token = token_path.read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError(f"token file is empty: {token_path}")
    return str(socket_path), token, args.timeout_ms / 1000.0


def _post_contact_steps(
    args: argparse.Namespace,
    *,
    smoke_id: str,
    metadata: dict[str, str],
) -> list[ToolCommand]:
    return [
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


def _manual_failure(
    *,
    command_id: str,
    operation: str = "submit_draft",
    summary: str,
    failure_kind: str,
    recovery_hint: str = "Pass --allow-submit --confirm-submit SEND to submit.",
) -> ToolObservation:
    return ToolObservation(
        command_id=command_id,
        tool="wechat.desktop",
        operation=operation,
        status="failed",
        success=False,
        summary=summary,
        observation={},
        evidence={},
        timing={},
        failure_kind=failure_kind,
        message=summary,
        recovery_hint=recovery_hint,
        retryable=False,
        error=None,
        metadata={},
    )


def _serialize(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return _redact_evidence(dataclasses.asdict(cast(Any, value)))
    if isinstance(value, dict):
        return _redact_evidence(value)
    if isinstance(value, (list, tuple)):
        return [_redact_evidence(item) for item in value]
    return value


def _serialize_event(event: ToolEvent) -> dict[str, object]:
    safe_data_keys = {
        "tool",
        "operation",
        "phase",
        "appControlOperation",
        "parentCommandId",
        "appControlCommandId",
    }
    return {
        "command_id": event.command_id,
        "seq": event.seq,
        "event_type": event.event_type,
        "phase": event.phase,
        "status": event.status,
        "summary": event.summary,
        "data": {
            key: value
            for key, value in event.data.items()
            if key in safe_data_keys and isinstance(value, (str, int, float, bool))
        },
        "schema": event.schema,
    }


def _redact_evidence(value: object) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for raw_key, nested in value.items():
            key = str(raw_key)
            normalized = key.replace("_", "").lower()
            if "token" in normalized:
                redacted[key] = "[redacted]"
            elif normalized in {"nodes", "visiblemessages", "textextract"}:
                redacted[key] = {
                    "redacted": True,
                    "count": len(nested) if isinstance(nested, (list, tuple)) else None,
                }
            else:
                redacted[key] = _redact_evidence(nested)
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact_evidence(item) for item in value]
    return value


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, Mapping):
        return ToolCommand.from_dict(dict(command))
    return command


def _publish_service_event(response: dict[str, Any], observer: object | None) -> None:
    try:
        validate_protocol_payload("service_event", response)
    except ProtocolValidationError as exc:
        raise RuntimeError(f"invalid service event: {exc}") from exc
    event_payload = response.get("event")
    if not isinstance(event_payload, dict):
        raise RuntimeError("service event does not include an event payload")
    if observer is None:
        return
    handler = getattr(observer, "on_event", None)
    if callable(handler):
        handler(ToolEvent.from_dict(event_payload))


def _existing_config_or_none(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.exists() else None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
