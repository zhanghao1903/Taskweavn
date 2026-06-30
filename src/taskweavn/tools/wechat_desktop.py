"""Agent-loop tool wrapper for the published ``wechat-desktop-tool`` package."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, cast

from app_control_protocol import AppControlClient, ToolCommand, ToolObservation
from app_control_protocol.json_types import JsonValue, to_json_value
from wechat_desktop_tool import (
    WeChatDesktopConfig,
    build_wechat_tool,
    draft_message_command,
    focus_contact_command,
    observe_current_chat_command,
    open_wechat_command,
    read_visible_messages_command,
    send_message_command,
    submit_draft_command,
)

from taskweavn.integrations.app_control import (
    AppControlClientFactory,
    AppControlClientFactoryConfig,
    RecordingToolObserver,
)
from taskweavn.integrations.wechat_tool import wechat_tool_observation_to_plato
from taskweavn.observability import emit_runtime_action, emit_runtime_observation, monotonic_ms
from taskweavn.tools.base import Tool
from taskweavn.types.base import BaseAction, BaseObservation
from taskweavn.types.wechat_desktop import (
    WeChatDesktopAction,
    WeChatDesktopObservation,
)
from taskweavn.wechat_task_types import WECHAT_SEND_CAPABILITY


class WeChatDesktopToolClientProtocol(Protocol):
    """Subset of the package tool used by Plato."""

    def run_command(
        self,
        command: ToolCommand | dict[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation: ...


@dataclass(frozen=True)
class WeChatDesktopToolConfig:
    """Config for the package-backed WeChat Desktop tool."""

    app_control: AppControlClientFactoryConfig = field(
        default_factory=lambda: AppControlClientFactoryConfig(
            backend="direct",
            allowed_apps=("WeChat",),
            allowed_app_bundle_ids={"WeChat": "com.tencent.xinWeChat"},
        )
    )
    app_name: str = "WeChat"
    bundle_id: str | None = "com.tencent.xinWeChat"
    submit_key: str = "Return"
    default_timeout_ms: int = 30_000
    max_message_chars: int = 2_000


class WeChatDesktopTool(Tool[WeChatDesktopAction, WeChatDesktopObservation]):
    """Expose WeChat semantic commands to the Agent loop.

    This class does not decide whether a message should be sent. It only runs
    the requested package command and returns the resulting observation.
    """

    name: ClassVar[str] = "wechat_desktop"
    description: ClassVar[str] = (
        "Operate WeChat Desktop through the approved app-control package tool. "
        "Use granular operations: focus_contact, draft_message, request product "
        "confirmation, then submit_draft only after authorization. Do not invent "
        "contacts or message text."
    )
    action_type: ClassVar[type[BaseAction]] = WeChatDesktopAction
    observation_type: ClassVar[type[BaseObservation]] = WeChatDesktopObservation

    def __init__(
        self,
        *,
        client: WeChatDesktopToolClientProtocol | None = None,
        config: WeChatDesktopToolConfig | None = None,
    ) -> None:
        self._config = config or WeChatDesktopToolConfig()
        self._load_error: str | None = None
        self._client: WeChatDesktopToolClientProtocol | None = client
        if client is None:
            self._client = self._load_client()

    def _load_client(self) -> WeChatDesktopToolClientProtocol | None:
        try:
            app_control = AppControlClientFactory(self._config.app_control).create_client()
            wechat = build_wechat_tool(
                cast(AppControlClient, app_control),
                WeChatDesktopConfig(
                    app_name=self._config.app_name,
                    bundle_id=self._config.bundle_id,
                    submit_key=self._config.submit_key,
                    default_timeout_ms=self._config.default_timeout_ms,
                    max_message_chars=self._config.max_message_chars,
                ),
            )
            return cast(WeChatDesktopToolClientProtocol, wechat)
        except Exception as exc:  # noqa: BLE001 - package boundary must be sanitized.
            self._load_error = f"{type(exc).__name__}: {exc}"
            return None

    def execute(self, action: WeChatDesktopAction) -> WeChatDesktopObservation:
        started_at = time.monotonic()
        if self._client is None:
            observation = WeChatDesktopObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="not_available",
                summary="WeChat Desktop package tool is not available.",
                metadata={"error": self._load_error or "package client creation failed"},
            )
            _emit_wechat_observation_log(
                action=action,
                observation=observation,
                started_at=started_at,
                package_events=(),
            )
            return observation
        command = _action_to_command(action)
        observer = RecordingToolObserver()
        _emit_wechat_action_log(action, command)
        try:
            result = self._client.run_command(command, observer=observer)
        except Exception as exc:  # noqa: BLE001 - package boundary must be sanitized.
            observation = WeChatDesktopObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="failed",
                summary=f"WeChat Desktop operation failed: {type(exc).__name__}",
                metadata={
                    "error": str(exc),
                    "command": _safe_command_summary(command),
                    "diagnostics": _diagnostics(self._client),
                    "tool_events": _tool_event_summaries(observer.events),
                },
            )
            _emit_wechat_observation_log(
                action=action,
                observation=observation,
                started_at=started_at,
                package_events=observer.events,
            )
            return observation
        observation = wechat_tool_observation_to_plato(
            result,
            action_id=action.event_id,
            operation=action.operation,
        )
        observation = observation.model_copy(
            update={
                "metadata": {
                    **observation.metadata,
                    "command": _safe_command_summary(command),
                    "diagnostics": _diagnostics(self._client),
                    "tool_events": _tool_event_summaries(observer.events),
                }
            }
        )
        _emit_wechat_observation_log(
            action=action,
            observation=observation,
            started_at=started_at,
            package_events=observer.events,
        )
        return observation


def _action_to_command(action: WeChatDesktopAction) -> ToolCommand:
    common = _command_kwargs(action)
    if action.operation == "open_wechat":
        return open_wechat_command(**common)
    if action.operation == "focus_contact":
        assert action.contact is not None
        return focus_contact_command(action.contact, **common)
    if action.operation == "observe_current_chat":
        return observe_current_chat_command(
            include_visible_messages=action.include_visible_messages,
            **common,
        )
    if action.operation == "read_visible_messages":
        return read_visible_messages_command(limit=action.limit, **common)
    if action.operation == "draft_message":
        assert action.message is not None
        return draft_message_command(action.message, **common)
    if action.operation == "submit_draft":
        return submit_draft_command(method=action.method, **common)
    if action.operation == "send_message":
        assert action.contact is not None
        assert action.message is not None
        return send_message_command(
            contact=action.contact,
            message=action.message,
            verify_after_submit=action.verify_after_submit,
            verify_limit=action.verify_limit,
            **common,
        )
    raise AssertionError(f"unsupported WeChat Desktop operation: {action.operation}")


def _command_kwargs(action: WeChatDesktopAction) -> dict[str, Any]:
    metadata = _json_metadata(action.metadata)
    return {
        "command_id": action.event_id,
        "timeout_ms": action.timeout_ms,
        "idempotency_key": action.idempotency_key,
        "metadata": metadata or None,
    }


def _json_metadata(metadata: dict[str, Any]) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    for key, value in metadata.items():
        payload[str(key)] = to_json_value(value)
    return payload


def _diagnostics(client: WeChatDesktopToolClientProtocol) -> dict[str, str]:
    return {
        "platform": sys.platform,
        "packageClientClass": f"{type(client).__module__}.{type(client).__qualname__}",
    }


def _emit_wechat_action_log(action: WeChatDesktopAction, command: ToolCommand) -> None:
    emit_runtime_action(
        session_id=_metadata_string(action.metadata, "sessionId", "session_id"),
        task_id=_metadata_string(action.metadata, "taskId", "task_id"),
        execution_id=_metadata_string(action.metadata, "executionId", "execution_id"),
        workspace_id=_metadata_string(action.metadata, "workspaceId", "workspace_id"),
        task_type=_metadata_string(action.metadata, "taskType", "task_type")
        or "communication.wechat.desktop",
        runtime="wechat_desktop_tool",
        required_capability=WECHAT_SEND_CAPABILITY,
        phase="command.dispatch",
        operation=action.operation,
        status="running",
        success=True,
        safe_summary=f"WeChat Desktop {action.operation} command dispatched.",
        action_id=action.event_id,
        timeout_seconds=_timeout_seconds(action.timeout_ms),
        idempotency_key=action.idempotency_key,
        message_text=action.message,
        metadata={
            "packageCommand": _safe_command_summary(command),
            "contactProvided": action.contact is not None,
            "messageProvided": action.message is not None,
        },
    )


def _emit_wechat_observation_log(
    *,
    action: WeChatDesktopAction,
    observation: WeChatDesktopObservation,
    started_at: float,
    package_events: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> None:
    emit_runtime_observation(
        session_id=_metadata_string(action.metadata, "sessionId", "session_id"),
        task_id=_metadata_string(action.metadata, "taskId", "task_id"),
        execution_id=_metadata_string(action.metadata, "executionId", "execution_id"),
        workspace_id=_metadata_string(action.metadata, "workspaceId", "workspace_id"),
        task_type=_metadata_string(action.metadata, "taskType", "task_type")
        or "communication.wechat.desktop",
        runtime="wechat_desktop_tool",
        required_capability=WECHAT_SEND_CAPABILITY,
        phase="command.observe",
        operation=action.operation,
        status=observation.status,
        success=observation.success,
        safe_summary=(
            f"WeChat Desktop {action.operation} completed with status "
            f"{observation.status}."
        ),
        observation_id=observation.event_id,
        duration_ms=monotonic_ms(started_at),
        idempotency_key=action.idempotency_key,
        message_text=action.message,
        failure_kind=_metadata_string(observation.metadata, "failure_kind"),
        error_message=_metadata_string(observation.metadata, "message")
        or _metadata_string(observation.metadata, "error"),
        recovery_hint=_metadata_string(observation.metadata, "recovery_hint"),
        metadata={
            "packageEventCount": len(package_events),
            "packageEvents": _tool_event_summaries(package_events),
            "protocol": observation.metadata.get("protocol", {}),
            "diagnostics": observation.metadata.get("diagnostics", {}),
        },
    )


def _metadata_string(metadata: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _timeout_seconds(timeout_ms: int | None) -> float | None:
    if timeout_ms is None:
        return None
    return max(0.001, timeout_ms / 1000)


def _safe_command_summary(command: ToolCommand) -> dict[str, Any]:
    input_keys = sorted(str(key) for key in command.input)
    return {
        "schema": command.schema,
        "commandId": command.command_id,
        "tool": command.tool,
        "operation": command.operation,
        "timeoutMs": command.timeout_ms,
        "idempotencyKeyPresent": bool(command.idempotency_key),
        "inputKeys": input_keys,
        "metadataKeys": sorted(str(key) for key in command.metadata),
    }


def _tool_event_summaries(
    events: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events[:limit]:
        data = event.get("data")
        rows.append(
            {
                "schema": event.get("schema"),
                "commandId": event.get("commandId"),
                "seq": event.get("seq"),
                "type": event.get("type"),
                "phase": event.get("phase"),
                "status": event.get("status"),
                "summary": _bounded_string(event.get("summary")),
                "dataKeys": sorted(str(key) for key in data) if isinstance(data, dict) else [],
            }
        )
    if len(events) > limit:
        rows.append({"truncated": len(events) - limit})
    return rows


def _bounded_string(value: object, *, limit: int = 240) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}..."


__all__ = [
    "WeChatDesktopTool",
    "WeChatDesktopToolClientProtocol",
    "WeChatDesktopToolConfig",
]
