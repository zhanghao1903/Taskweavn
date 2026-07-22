"""Agent-loop tool wrapper for the published ``wechat-desktop-tool`` package."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Protocol, cast

from app_control_protocol import AppControlClient, ToolCommand, ToolObservation
from app_control_protocol.json_types import JsonValue, to_json_value
from wechat_desktop_tool import (
    WeChatDesktopConfig,
    build_wechat_tool,
    draft_message_command,
    focus_contact_command,
    inspect_window_command,
    list_contacts_command,
    list_conversations_command,
    observe_current_chat_command,
    open_contact_command,
    open_wechat_command,
    read_contact_messages_command,
    read_visible_messages_command,
    send_message_command,
    submit_draft_command,
)

from taskweavn.integrations.app_control import (
    AppControlClientFactory,
    AppControlClientFactoryConfig,
    RecordingToolObserver,
)
from taskweavn.integrations.wechat_tool import (
    SendBoundaryClaim,
    SendBoundaryStore,
    SendBoundaryStoreError,
    wechat_tool_observation_to_plato,
)
from taskweavn.observability import emit_runtime_action, emit_runtime_observation, monotonic_ms
from taskweavn.tools.base import Tool
from taskweavn.types.base import BaseAction, BaseObservation
from taskweavn.types.wechat_desktop import (
    WeChatDesktopAction,
    WeChatDesktopObservation,
    WeChatDesktopStatus,
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
        "Use granular operations for inspect, read, open-contact, and draft flows. "
        "For an exact authorized send, use one send_message call; Plato supplies "
        "the managed send key. Do not invent contacts or message text."
    )
    action_type: ClassVar[type[BaseAction]] = WeChatDesktopAction
    observation_type: ClassVar[type[BaseObservation]] = WeChatDesktopObservation

    def __init__(
        self,
        *,
        client: WeChatDesktopToolClientProtocol | None = None,
        config: WeChatDesktopToolConfig | None = None,
        send_boundary_store: SendBoundaryStore | None = None,
        send_boundary_scope: str | None = None,
        send_boundary_key: str | None = None,
    ) -> None:
        self._config = config or WeChatDesktopToolConfig()
        if send_boundary_store is not None and not send_boundary_scope:
            raise ValueError("send_boundary_scope is required with send_boundary_store")
        if send_boundary_store is None and (
            send_boundary_scope is not None or send_boundary_key is not None
        ):
            raise ValueError("send_boundary_store is required for managed send idempotency")
        self._send_boundary_store = send_boundary_store
        self._send_boundary_scope = send_boundary_scope
        self._send_boundary_key = send_boundary_key
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
        if action.operation != "send_message" or self._send_boundary_store is None:
            return self._execute_package(action, idempotency_key=None)
        return self._execute_send_once(action)

    def shutdown(self) -> None:
        if self._send_boundary_store is not None:
            self._send_boundary_store.close()

    def _execute_send_once(
        self,
        action: WeChatDesktopAction,
    ) -> WeChatDesktopObservation:
        assert self._send_boundary_store is not None
        assert self._send_boundary_scope is not None
        if self._send_boundary_key is None:
            return _send_boundary_failure(
                action,
                failure_kind="idempotency_key_missing",
                summary="WeChat send was not attempted because no managed send key exists.",
                message="The task has no stable send-boundary idempotency key.",
                recovery_hint="Create a TaskBus-backed send task before calling send_message.",
                status="failed",
                send_attempted=False,
            )

        request_hash = _send_request_hash(action, config=self._config)
        try:
            claim = self._send_boundary_store.claim(
                scope_id=self._send_boundary_scope,
                idempotency_key=self._send_boundary_key,
                request_hash=request_hash,
            )
        except SendBoundaryStoreError as exc:
            return _send_boundary_failure(
                action,
                failure_kind="idempotency_store_unavailable",
                summary="WeChat send was not attempted because effect state is unavailable.",
                message=str(exc),
                recovery_hint="Restore the session effect store before starting a new send task.",
                status="failed",
                send_attempted=False,
            )

        if claim.status != "acquired":
            return _observation_from_send_claim(
                action,
                claim=claim,
                key=self._send_boundary_key,
            )

        observation = self._execute_package(
            action,
            idempotency_key=self._send_boundary_key,
        )
        state = _terminal_send_boundary_state(observation)
        try:
            self._send_boundary_store.complete(
                scope_id=self._send_boundary_scope,
                idempotency_key=self._send_boundary_key,
                request_hash=request_hash,
                state=state,
                observation=observation,
            )
        except SendBoundaryStoreError as exc:
            return _send_boundary_failure(
                action,
                failure_kind="send_outcome_unknown",
                summary=(
                    "WeChat send outcome is unknown because the effect result could not "
                    "be recorded durably. The command will not be replayed."
                ),
                message=str(exc),
                recovery_hint="Inspect WeChat manually before creating any new send task.",
                status="unknown",
                send_attempted=_send_attempted(observation),
                prior_observation=observation,
                key=self._send_boundary_key,
            )
        return observation.model_copy(
            update={
                "metadata": {
                    **observation.metadata,
                    "send_boundary": {
                        "state": state,
                        "replayed": False,
                        "idempotencyKeyHash": _hash_text(self._send_boundary_key),
                    },
                }
            }
        )

    def _execute_package(
        self,
        action: WeChatDesktopAction,
        *,
        idempotency_key: str | None,
    ) -> WeChatDesktopObservation:
        started_at = time.monotonic()
        if self._client is None:
            observation = WeChatDesktopObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="not_available",
                summary="WeChat Desktop package tool is not available.",
                metadata={
                    "error": self._load_error or "package client creation failed",
                    "failure_kind": "package_tool_unavailable",
                    "message": self._load_error or "package client creation failed",
                    "retryable": False,
                    "observation": {"sendAttempted": False},
                },
            )
            _emit_wechat_observation_log(
                action=action,
                observation=observation,
                started_at=started_at,
                package_events=(),
                idempotency_key=idempotency_key,
            )
            return observation
        command = _action_to_command(action, idempotency_key=idempotency_key)
        observer = RecordingToolObserver()
        _emit_wechat_action_log(action, command, idempotency_key=idempotency_key)
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
                    "failure_kind": "package_client_error",
                    "message": str(exc),
                    "retryable": False,
                    "observation": {"sendAttempted": None},
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
                idempotency_key=idempotency_key,
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
            idempotency_key=idempotency_key,
        )
        return observation


def _action_to_command(
    action: WeChatDesktopAction,
    *,
    idempotency_key: str | None,
) -> ToolCommand:
    common = _command_kwargs(action, idempotency_key=idempotency_key)
    if action.operation == "open_wechat":
        return open_wechat_command(**common)
    if action.operation == "inspect_window":
        return inspect_window_command(
            include_raw=action.include_raw,
            include_actionables=action.include_actionables,
            **common,
        )
    if action.operation == "list_contacts":
        return list_contacts_command(
            limit=action.limit,
            page_token=action.page_token,
            **common,
        )
    if action.operation == "list_conversations":
        return list_conversations_command(
            limit=action.limit,
            page_token=action.page_token,
            **common,
        )
    if action.operation == "open_contact":
        assert action.contact is not None
        return open_contact_command(action.contact, **common)
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
    if action.operation == "read_contact_messages":
        assert action.contact is not None
        return read_contact_messages_command(
            action.contact,
            limit=action.limit,
            **common,
        )
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


def _command_kwargs(
    action: WeChatDesktopAction,
    *,
    idempotency_key: str | None,
) -> dict[str, Any]:
    metadata = _json_metadata(action.metadata)
    return {
        "command_id": action.event_id,
        "timeout_ms": action.timeout_ms,
        "idempotency_key": idempotency_key,
        "metadata": metadata or None,
    }


def _json_metadata(metadata: dict[str, Any]) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    for key, value in metadata.items():
        payload[str(key)] = to_json_value(value)
    return payload


def _send_request_hash(
    action: WeChatDesktopAction,
    *,
    config: WeChatDesktopToolConfig,
) -> str:
    payload = {
        "operation": action.operation,
        "contact": action.contact,
        "message": action.message,
        "method": action.method,
        "verifyAfterSubmit": action.verify_after_submit,
        "verifyLimit": action.verify_limit,
        "appName": config.app_name,
        "bundleId": config.bundle_id,
        "submitKey": config.submit_key,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _terminal_send_boundary_state(
    observation: WeChatDesktopObservation,
) -> Literal["completed", "unknown"]:
    if observation.success:
        return "completed"
    if _send_attempted(observation) is False:
        return "completed"
    return "unknown"


def _send_attempted(observation: WeChatDesktopObservation) -> bool | None:
    nested = observation.metadata.get("observation")
    if isinstance(nested, dict):
        value = nested.get("sendAttempted")
        if isinstance(value, bool):
            return value
    protocol = observation.metadata.get("protocol")
    if isinstance(protocol, dict):
        value = protocol.get("sendAttempted")
        if isinstance(value, bool):
            return value
    return None


def _observation_from_send_claim(
    action: WeChatDesktopAction,
    *,
    claim: SendBoundaryClaim,
    key: str,
) -> WeChatDesktopObservation:
    boundary = {
        "state": claim.record.state,
        "replayed": claim.status == "replay",
        "idempotencyKeyHash": _hash_text(key),
    }
    if claim.record.reconciliation is not None:
        boundary.update(
            {
                "resolution": "manual_reconciliation",
                "reconciliationSource": claim.record.reconciliation.source,
            }
        )
        if claim.record.reconciled_at is not None:
            boundary["reconciledAt"] = claim.record.reconciled_at.isoformat()
    if claim.status == "conflict":
        return _send_boundary_failure(
            action,
            failure_kind="idempotency_conflict",
            summary=(
                "WeChat send was not attempted because this send key belongs to different content."
            ),
            message="The managed send key was reused with a different request.",
            recovery_hint="Create a new TaskBus send task for changed content.",
            status="failed",
            send_attempted=False,
            key=key,
        )
    if claim.status == "replay" and claim.record.observation is not None:
        previous = claim.record.observation
        reconciled = claim.record.reconciliation is not None
        summary = (
            "Idempotent replay: manual reconciliation confirmed the prior send. "
            "No additional WeChat send was attempted."
            if reconciled
            else (f"Idempotent replay: {previous.summary} No additional WeChat send was attempted.")
        )
        return previous.model_copy(
            update={
                "action_id": action.event_id,
                "success": True if reconciled else previous.success,
                "status": "ok" if reconciled else previous.status,
                "summary": _bounded_string(summary, limit=2_000) or summary,
                "metadata": {
                    **previous.metadata,
                    "replay_original_status": previous.status,
                    "send_boundary": boundary,
                },
            }
        )
    if claim.status == "unknown" and claim.record.observation is not None:
        previous = claim.record.observation
        return _send_boundary_failure(
            action,
            failure_kind=_metadata_string(previous.metadata, "failure_kind")
            or "send_outcome_unknown",
            summary=("A previous WeChat send outcome is unknown. The command was not replayed."),
            message=_metadata_string(previous.metadata, "message")
            or "The previous send may have reached the submit boundary.",
            recovery_hint=_metadata_string(previous.metadata, "recovery_hint")
            or "Inspect WeChat manually before creating any new send task.",
            status="unknown",
            send_attempted=_send_attempted(previous),
            prior_observation=previous,
            key=key,
        )
    return _send_boundary_failure(
        action,
        failure_kind="send_in_progress",
        summary=(
            "A WeChat send with this key is already in progress or was interrupted. "
            "The command was not replayed."
        ),
        message="No terminal send-boundary record is available.",
        recovery_hint="Inspect WeChat manually before creating any new send task.",
        status="unknown",
        send_attempted=None,
        key=key,
    )


def _send_boundary_failure(
    action: WeChatDesktopAction,
    *,
    failure_kind: str,
    summary: str,
    message: str,
    recovery_hint: str,
    status: WeChatDesktopStatus,
    send_attempted: bool | None,
    prior_observation: WeChatDesktopObservation | None = None,
    key: str | None = None,
) -> WeChatDesktopObservation:
    metadata: dict[str, Any] = {
        "failure_kind": failure_kind,
        "message": message,
        "recovery_hint": recovery_hint,
        "retryable": False,
        "observation": {"sendAttempted": send_attempted},
        "send_boundary": {
            "state": "unknown" if status == "unknown" else "rejected",
            "replayed": key is not None,
            "idempotencyKeyHash": None if key is None else _hash_text(key),
        },
    }
    if prior_observation is not None:
        metadata["prior_observation"] = prior_observation.model_dump(mode="json")
    return WeChatDesktopObservation(
        action_id=action.event_id,
        success=False,
        operation="send_message",
        status=status,
        summary=summary,
        metadata=metadata,
    )


def _hash_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _diagnostics(client: WeChatDesktopToolClientProtocol) -> dict[str, str]:
    return {
        "platform": sys.platform,
        "packageClientClass": f"{type(client).__module__}.{type(client).__qualname__}",
    }


def _emit_wechat_action_log(
    action: WeChatDesktopAction,
    command: ToolCommand,
    *,
    idempotency_key: str | None,
) -> None:
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
        idempotency_key=idempotency_key,
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
    idempotency_key: str | None,
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
            f"WeChat Desktop {action.operation} completed with status {observation.status}."
        ),
        observation_id=observation.event_id,
        duration_ms=monotonic_ms(started_at),
        idempotency_key=idempotency_key,
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
