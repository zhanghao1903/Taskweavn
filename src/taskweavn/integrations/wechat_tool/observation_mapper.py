"""Map wechat-desktop-tool observations into Plato tool observations."""

from __future__ import annotations

from typing import Any

from app_control_protocol import ToolObservation

from taskweavn.types.wechat_desktop import (
    WeChatDesktopObservation,
    WeChatDesktopOperation,
    WeChatDesktopStatus,
)


def wechat_tool_observation_to_plato(
    observation: ToolObservation,
    *,
    action_id: str | None,
    operation: WeChatDesktopOperation,
) -> WeChatDesktopObservation:
    """Convert a package ToolObservation to the current Plato tool shape."""

    status = _map_status(_status_value(observation.status))
    metadata = _metadata(observation)
    text_extract = _optional_string(
        observation.observation.get("textExtract")
        or observation.observation.get("text_extract")
    )
    return WeChatDesktopObservation(
        action_id=action_id,
        success=status == "ok",
        operation=operation,
        status=status,
        summary=observation.summary,
        text_extract=text_extract,
        metadata=metadata,
    )


def _metadata(observation: ToolObservation) -> dict[str, Any]:
    payload = observation.to_dict()
    metadata: dict[str, Any] = {
        "protocol": {
            "schema": payload.get("schema"),
            "commandId": payload.get("commandId"),
            "tool": payload.get("tool"),
            "operation": payload.get("operation"),
            "status": payload.get("status"),
            "success": payload.get("success"),
            "timing": payload.get("timing") or {},
        },
        "observation": dict(observation.observation),
    }
    if observation.evidence:
        metadata["evidence"] = dict(observation.evidence)
    if observation.failure_kind:
        metadata["failure_kind"] = observation.failure_kind
    if observation.message:
        metadata["message"] = observation.message
    if observation.recovery_hint:
        metadata["recovery_hint"] = observation.recovery_hint
    if observation.retryable is not None:
        metadata["retryable"] = observation.retryable
    if observation.error is not None:
        error = (
            observation.error.to_dict()
            if hasattr(observation.error, "to_dict")
            else observation.error
        )
        metadata["error"] = error
    if observation.metadata:
        metadata["package_metadata"] = dict(observation.metadata)
    return metadata


def _map_status(status: str) -> WeChatDesktopStatus:
    if status == "ok":
        return "ok"
    if status in {"not_ready", "permission_missing"}:
        return "needs_user"
    if status in {"unknown"}:
        return "unknown"
    if status in {"not_found", "timeout", "failed"}:
        return "failed"
    return "not_available"


def _status_value(value: object) -> str:
    enum_value = getattr(value, "value", value)
    return enum_value if isinstance(enum_value, str) else str(enum_value)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
