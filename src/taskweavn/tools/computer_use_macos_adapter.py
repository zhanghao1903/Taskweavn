"""Adapter from Plato's computer-use contract to ``computer-use-macos``.

The package boundary is protocol-first: Plato sends ``ToolCommand`` envelopes
and receives ``ToolObservation`` facts. Product authorization, task lifecycle,
and UI projection stay outside the package.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from app_control_protocol import AppControlClient, ToolCommand, ToolObservation
from app_control_protocol.json_types import JsonValue, to_json_value
from computer_use_macos import (
    accessibility_query_command,
    click_command,
    focus_app_command,
    hotkey_command,
    observe_command,
    open_app_command,
    press_key_command,
    readiness_command,
    type_text_command,
    wait_command,
)

from taskweavn.integrations.app_control import (
    AppControlClientFactory,
    AppControlClientFactoryConfig,
    RecordingToolObserver,
    app_control_observation_to_computer_use,
)
from taskweavn.observability import emit_computer_use_api, monotonic_ms
from taskweavn.tools.computer_use import ComputerUseBackend
from taskweavn.types.computer_use import (
    ComputerUseAction,
    ComputerUseObservation,
)


class MacOSComputerUseClientProtocol(Protocol):
    """Subset of the new package client used by Plato."""

    def run_command(
        self,
        command: ToolCommand | dict[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation: ...


@dataclass(frozen=True)
class MacOSComputerUseBackendConfig:
    """Runtime options passed to ``computer-use-macos``."""

    allowed_apps: tuple[str, ...] = ()
    enabled: bool = True
    backend: str = "direct"
    allow_coordinate_click: bool = False
    screen_recording_required: bool = False
    max_text_chars: int = 4_000
    timeout_ms: int = 10_000
    allowed_app_bundle_ids: dict[str, str] | None = None
    helper_manifest_path: Path | None = None
    helper_app_path: Path | None = None
    helper_bundle_id: str | None = None
    helper_endpoint: str | None = None
    helper_token: str | None = None
    helper_auto_launch: bool = False


class MacOSComputerUseBackend(ComputerUseBackend):
    """Plato backend adapter over the published macOS package."""

    def __init__(
        self,
        *,
        client: MacOSComputerUseClientProtocol | None = None,
        config: MacOSComputerUseBackendConfig | None = None,
    ) -> None:
        self._config = config or MacOSComputerUseBackendConfig()
        self._import_error: str | None = None
        self._client: MacOSComputerUseClientProtocol | None = client
        if client is None and self._config.enabled:
            self._client = self._load_client()

    def _load_client(self) -> MacOSComputerUseClientProtocol | None:
        try:
            factory = AppControlClientFactory(
                AppControlClientFactoryConfig(
                    backend=self._config.backend,
                    allowed_apps=self._config.allowed_apps,
                    allowed_app_bundle_ids=self._config.allowed_app_bundle_ids,
                    allow_coordinate_click=self._config.allow_coordinate_click,
                    screen_recording_required=self._config.screen_recording_required,
                    timeout_ms=self._config.timeout_ms,
                    helper_manifest_path=self._config.helper_manifest_path,
                    helper_app_path=self._config.helper_app_path,
                    helper_bundle_id=self._config.helper_bundle_id,
                    helper_endpoint=self._config.helper_endpoint,
                    helper_token=self._config.helper_token,
                    helper_auto_launch=self._config.helper_auto_launch,
                )
            )
            return cast(MacOSComputerUseClientProtocol, factory.create_client())
        except Exception as exc:  # noqa: BLE001 - optional package boundary.
            self._import_error = f"{type(exc).__name__}: {exc}"
            return None

    def readiness(self, *, action_id: str | None = None) -> ComputerUseObservation:
        action_kwargs: dict[str, object] = {
            "operation": "readiness",
            "instruction": "Check macOS app-control readiness.",
        }
        if action_id is not None:
            action_kwargs["event_id"] = action_id
        return self.execute(
            ComputerUseAction.model_validate(action_kwargs)
        )

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        started_at = time.monotonic()
        if self._client is None:
            observation = ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="not_available",
                summary="macOS computer-use package is not available.",
                metadata={"error": self._import_error or "package client creation failed"},
            )
            _emit_computer_use_log(
                action=action,
                observation=observation,
                started_at=started_at,
                backend=self._config.backend,
                package_events=(),
            )
            return observation
        command = _action_to_command(action, max_text_chars=self._config.max_text_chars)
        observer = RecordingToolObserver()
        try:
            result = self._client.run_command(command, observer=observer)
        except Exception as exc:  # noqa: BLE001 - sanitize package boundary.
            observation = ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="failed",
                summary=f"macOS computer-use operation failed: {type(exc).__name__}",
                metadata={
                    "error": str(exc),
                    "adapterProcessExecutable": sys.executable,
                    "tool_events": _tool_event_summaries(observer.events),
                },
            )
            _emit_computer_use_log(
                action=action,
                observation=observation,
                started_at=started_at,
                backend=self._config.backend,
                package_events=observer.events,
            )
            return observation
        observation = app_control_observation_to_computer_use(
            result,
            action_id=action.event_id,
            operation=action.operation,
        )
        observation.metadata.setdefault("diagnostics", _diagnostics(self._client))
        observation.metadata["tool_events"] = _tool_event_summaries(observer.events)
        _emit_computer_use_log(
            action=action,
            observation=observation,
            started_at=started_at,
            backend=self._config.backend,
            package_events=observer.events,
        )
        return observation


def _action_to_command(action: ComputerUseAction, *, max_text_chars: int) -> ToolCommand:
    timeout_ms = max(1, int(action.timeout_seconds * 1000))
    metadata = _command_metadata(action)
    command_id = action.event_id
    bundle_id = _string_metadata(action, "bundle_id")
    target_app = _target_app(action)
    if action.operation == "readiness":
        return readiness_command(
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "open_app":
        assert action.target is not None
        return open_app_command(
            action.target,
            bundle_id=bundle_id,
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "focus_app":
        assert action.target is not None
        return focus_app_command(
            action.target,
            bundle_id=bundle_id,
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "observe":
        return observe_command(
            target_app=target_app,
            bundle_id=bundle_id,
            include_visible_text=_bool_metadata(action, "include_visible_text"),
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "accessibility_query":
        return accessibility_query_command(
            target_app=target_app,
            bundle_id=bundle_id,
            root=_dict_metadata(action, "root"),
            query=_dict_metadata(action, "query"),
            include_raw=_bool_metadata(action, "include_raw"),
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "type_text":
        assert action.text is not None
        return type_text_command(
            action.text[:max_text_chars],
            target_app=target_app,
            bundle_id=bundle_id,
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "click":
        return click_command(
            action.target,
            target_app=target_app,
            bundle_id=bundle_id,
            selector=_dict_metadata(action, "selector"),
            coordinates=_coordinates(action),
            snapshot_id=_string_metadata(action, "snapshot_id"),
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "press_key":
        if len(action.keys) > 1:
            return hotkey_command(
                action.keys,
                target_app=target_app,
                bundle_id=bundle_id,
                command_id=command_id,
                timeout_ms=timeout_ms,
                metadata=metadata,
            )
        return press_key_command(
            action.keys[0],
            target_app=target_app,
            bundle_id=bundle_id,
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    if action.operation == "wait":
        return wait_command(
            seconds=action.timeout_seconds,
            command_id=command_id,
            timeout_ms=timeout_ms,
            metadata=metadata,
        )
    raise ValueError(f"unsupported computer-use operation: {action.operation}")


def _command_metadata(action: ComputerUseAction) -> dict[str, JsonValue]:
    metadata: dict[str, JsonValue] = {
        "platoActionId": action.event_id,
        "platoOperation": action.operation,
    }
    for key, value in action.metadata.items():
        if key in {
            "target_app",
            "bundle_id",
            "root",
            "query",
            "include_raw",
            "selector",
            "snapshot_id",
            "include_visible_text",
        }:
            continue
        metadata[key] = to_json_value(value)
    return metadata


def _target_app(action: ComputerUseAction) -> str | None:
    return _string_metadata(action, "target_app") or (
        action.target
        if action.operation in {"observe", "accessibility_query", "type_text"}
        else None
    )


def _string_metadata(action: ComputerUseAction, key: str) -> str | None:
    value = action.metadata.get(key)
    return value if isinstance(value, str) and value else None


def _bool_metadata(action: ComputerUseAction, key: str) -> bool | None:
    value = action.metadata.get(key)
    return value if isinstance(value, bool) else None


def _dict_metadata(action: ComputerUseAction, key: str) -> dict[str, JsonValue] | None:
    value = action.metadata.get(key)
    if not isinstance(value, dict):
        return None
    return {str(item_key): to_json_value(item_value) for item_key, item_value in value.items()}


def _coordinates(action: ComputerUseAction) -> tuple[int, int] | None:
    if action.x is None or action.y is None:
        return None
    return (action.x, action.y)


def _diagnostics(client: AppControlClient | MacOSComputerUseClientProtocol) -> dict[str, str]:
    diagnostics = {
        "checkedByProcessPath": sys.executable,
        "adapterProcessExecutable": sys.executable,
        "packageClientClass": (
            f"{client.__class__.__module__}.{client.__class__.__qualname__}"
        )[:500],
    }
    if sys.argv:
        diagnostics["adapterArgv0"] = sys.argv[0][:500]
    return diagnostics


def _emit_computer_use_log(
    *,
    action: ComputerUseAction,
    observation: ComputerUseObservation,
    started_at: float,
    backend: str,
    package_events: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> None:
    emit_computer_use_api(
        session_id=_metadata_string(action.metadata, "sessionId", "session_id"),
        task_id=_metadata_string(action.metadata, "taskId", "task_id"),
        execution_id=_metadata_string(action.metadata, "executionId", "execution_id"),
        workspace_id=_metadata_string(action.metadata, "workspaceId", "workspace_id"),
        operation=action.operation,
        phase="command.observe",
        status=observation.status,
        success=observation.success,
        safe_summary=(
            f"macOS computer-use {action.operation} completed with status "
            f"{observation.status}."
        ),
        backend=backend,
        request_id=action.event_id,
        duration_ms=monotonic_ms(started_at),
        timeout_seconds=action.timeout_seconds,
        failure_kind=_metadata_string(observation.metadata, "failure_kind"),
        error_message=_metadata_string(observation.metadata, "message")
        or _metadata_string(observation.metadata, "error"),
        recovery_hint=_metadata_string(observation.metadata, "recovery_hint"),
        click_attempted=_bool_nested_metadata(observation.metadata, "evidence", "clickAttempted"),
        idempotency_key=_metadata_string(action.metadata, "idempotencyKey", "idempotency_key"),
        message_text=action.text,
        message_chars=len(action.text) if action.text is not None else None,
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


def _bool_nested_metadata(
    metadata: dict[str, Any],
    parent_key: str,
    child_key: str,
) -> bool | None:
    parent = metadata.get(parent_key)
    if not isinstance(parent, dict):
        return None
    value = parent.get(child_key)
    return value if isinstance(value, bool) else None


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
    "MacOSComputerUseBackend",
    "MacOSComputerUseBackendConfig",
    "MacOSComputerUseClientProtocol",
]
