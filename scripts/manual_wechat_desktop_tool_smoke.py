"""Manual package-backed WeChat Desktop smoke through the local Helper service.

The script connects to the Unix socket service published by Plato Computer Use
Helper and adapts it to the app-control protocol. No-submit mode follows the SDK
granular contact/draft/observe flow. Submit mode invokes Plato's semantic
``WeChatDesktopTool`` with its durable SQLite send-boundary guard. It requires
``--allow-focus-select`` for contact selection and never submits unless both
``--allow-submit`` and ``--confirm-submit SEND`` are present.
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
    WeChatDesktopTool as PackageWeChatDesktopTool,
)
from wechat_desktop_tool import (
    draft_message_command,
    observe_current_chat_command,
    open_contact_command,
    open_wechat_command,
)

from taskweavn.integrations.app_control.service_manifest import (
    AppControlServiceManifest,
)
from taskweavn.integrations.wechat_tool import (
    SqliteSendBoundaryStore,
    managed_send_boundary_key,
)
from taskweavn.tools import (
    WeChatDesktopTool as PlatoWeChatDesktopTool,
)
from taskweavn.tools import (
    WeChatDesktopToolClientProtocol,
    WeChatDesktopToolConfig,
)
from taskweavn.types.wechat_desktop import (
    WeChatDesktopAction,
    WeChatDesktopObservation,
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
    observations: list[object] = []
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
        tool = PackageWeChatDesktopTool.from_config(app_control, tool_config)
    except Exception as exc:
        print(f"wechat desktop smoke setup failed: {exc}", file=sys.stderr)
        return 2

    exit_code = 0
    submit_requested = bool(args.allow_submit)
    submit_confirmed = args.confirm_submit == "SEND"
    submit_attempted = False
    submit_succeeded = False
    send_replayed = False

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

    if exit_code == 0 and args.readiness_only:
        pass
    elif exit_code == 0 and args.allow_submit:
        if not submit_confirmed:
            observations.append(
                _manual_failure(
                    command_id=f"{smoke_id}:send",
                    operation="send_message",
                    summary="Submit blocked: --confirm-submit SEND is required.",
                    failure_kind="submit_not_confirmed",
                )
            )
            exit_code = 2
        elif not args.allow_focus_select:
            observations.append(
                _manual_failure(
                    command_id=f"{smoke_id}:contact-mode",
                    operation="send_message",
                    summary=(
                        "Contact selection was not authorized. The smoke requires "
                        "--allow-focus-select."
                    ),
                    failure_kind="contact_selection_not_authorized",
                    recovery_hint="Pass --allow-focus-select for semantic send_message.",
                )
            )
            exit_code = 2
        else:
            try:
                managed_observation = _run_managed_send(
                    args,
                    package_tool=tool,
                    metadata=metadata,
                )
            except ValueError as exc:
                observations.append(
                    _manual_failure(
                        command_id=f"{smoke_id}:managed-send",
                        operation="send_message",
                        summary=str(exc),
                        failure_kind="managed_send_precondition_failed",
                        recovery_hint="Fix the managed send arguments; no send occurred.",
                    )
                )
                exit_code = 2
            else:
                observations.append(managed_observation)
                send_replayed = _plato_send_replayed(managed_observation)
                submit_attempted = _plato_send_attempted(managed_observation)
                submit_succeeded = _plato_send_submitted(managed_observation)
                if not managed_observation.success:
                    exit_code = 1
    elif exit_code == 0:
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
                        recovery_hint=(
                            "Pass --allow-focus-select to run package contact selection."
                        ),
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
        "replayed": send_replayed,
        "readinessOnly": args.readiness_only,
        "config": {
            "transport": "unix_socket",
            "socketPath": socket_path,
            "manifestPath": str(Path(args.manifest_path).expanduser())
            if args.manifest_path
            else None,
            "configPath": str(_existing_config_or_none(args.config))
            if _existing_config_or_none(args.config)
            else None,
            "serviceTimeoutSeconds": service_timeout,
            "searchHotkey": _split_csv(args.search_hotkey),
            "searchClearHotkey": _split_csv(args.search_clear_hotkey),
            "effectDb": str(args.effect_db) if args.effect_db else None,
            "sessionId": args.session_id,
            "taskId": args.task_id,
            "managedSendKeyHash": (
                None
                if not args.session_id or not args.task_id
                else _hash_text(managed_send_boundary_key(args.session_id, args.task_id))
            ),
            "replayOnly": args.replay_only,
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
        "--manifest-path",
        default=os.environ.get("PLATO_COMPUTER_USE_HELPER_MANIFEST"),
        help="Plato Helper endpoint manifest; replaces socket/token inputs.",
    )
    parser.add_argument(
        "--socket-path",
        default=(
            os.environ.get("WECHAT_TOOL_SOCKET_PATH") or os.environ.get("APP_CONTROL_SOCKET_PATH")
        ),
    )
    parser.add_argument("--token", default=os.environ.get("WECHAT_TOOL_TOKEN"))
    parser.add_argument("--token-file", default=os.environ.get("WECHAT_TOOL_TOKEN_FILE"))
    parser.add_argument("--search-hotkey", default="Command,K")
    parser.add_argument("--search-clear-hotkey", default="Command,A")
    parser.add_argument("--contact", default="文件传输助手")
    parser.add_argument("--message", required=True)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--effect-db", type=Path)
    parser.add_argument("--session-id")
    parser.add_argument("--task-id")
    parser.add_argument(
        "--readiness-only",
        action="store_true",
        help="Run Helper readiness and exit without opening or operating WeChat.",
    )
    parser.add_argument(
        "--replay-only",
        action="store_true",
        help="Refuse to execute unless the managed send record already exists.",
    )
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
            "allow_coordinate_click": True,
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
    if args.manifest_path:
        if args.socket_path or args.token or args.token_file:
            raise ValueError("--manifest-path is mutually exclusive with socket/token inputs")
        manifest = AppControlServiceManifest.load(Path(args.manifest_path).expanduser())
        return (
            str(manifest.endpoint),
            manifest.read_token(),
            args.timeout_ms / 1000.0,
        )

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
            metadata={**metadata, "messageHash": _hash_text(args.message)},
        ),
        observe_current_chat_command(
            command_id=f"{smoke_id}:observe",
            timeout_ms=args.timeout_ms,
            metadata=metadata,
        ),
    ]


def _run_managed_send(
    args: argparse.Namespace,
    *,
    package_tool: PackageWeChatDesktopTool,
    metadata: dict[str, str],
) -> WeChatDesktopObservation:
    if args.effect_db is None or not args.session_id or not args.task_id:
        raise ValueError("managed submit requires --effect-db, --session-id, and --task-id")
    key = managed_send_boundary_key(args.session_id, args.task_id)
    store = SqliteSendBoundaryStore(args.effect_db)
    if (
        args.replay_only
        and store.get(
            scope_id=args.session_id,
            idempotency_key=key,
        )
        is None
    ):
        store.close()
        raise ValueError("--replay-only refused because no managed send record exists")
    product_tool = PlatoWeChatDesktopTool(
        client=cast(WeChatDesktopToolClientProtocol, package_tool),
        config=WeChatDesktopToolConfig(default_timeout_ms=args.timeout_ms),
        send_boundary_store=store,
        send_boundary_scope=args.session_id,
        send_boundary_key=key,
    )
    try:
        return product_tool.execute(
            WeChatDesktopAction(
                operation="send_message",
                contact=args.contact,
                message=args.message,
                verify_after_submit=True,
                timeout_ms=args.timeout_ms,
                metadata={
                    **metadata,
                    "sessionId": args.session_id,
                    "taskId": args.task_id,
                    "taskType": "communication.wechat.send_message",
                },
            )
        )
    finally:
        product_tool.shutdown()


def _plato_send_attempted(observation: WeChatDesktopObservation) -> bool:
    if _plato_send_replayed(observation):
        return False
    package_observation = observation.metadata.get("observation")
    if not isinstance(package_observation, dict):
        return False
    return (
        package_observation.get("sendAttempted") is True
        or package_observation.get("submitted") is True
    )


def _plato_send_submitted(observation: WeChatDesktopObservation) -> bool:
    if _plato_send_replayed(observation):
        return False
    package_observation = observation.metadata.get("observation")
    if isinstance(package_observation, dict):
        submitted = package_observation.get("submitted")
        if isinstance(submitted, bool):
            return submitted
    return observation.success


def _plato_send_replayed(observation: WeChatDesktopObservation) -> bool:
    boundary = observation.metadata.get("send_boundary")
    return isinstance(boundary, dict) and boundary.get("replayed") is True


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
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _redact_evidence(model_dump(mode="json"))
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
            elif normalized in {"messages", "nodes", "visiblemessages", "textextract"}:
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
