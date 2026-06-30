"""Map app-control protocol observations into Plato tool observations."""

from __future__ import annotations

from typing import Any

from app_control_protocol import ToolObservation

from taskweavn.types.computer_use import (
    ComputerUseObservation,
    ComputerUseOperation,
    ComputerUseStatus,
)


def app_control_observation_to_computer_use(
    observation: ToolObservation,
    *,
    action_id: str | None = None,
    operation: ComputerUseOperation,
) -> ComputerUseObservation:
    """Convert a protocol observation to the current Plato computer-use shape."""

    status = _map_protocol_status(_status_value(observation.status))
    metadata = _protocol_metadata(observation)
    text_extract = _optional_string(
        observation.observation.get("textExtract")
        or observation.observation.get("text_extract")
    )
    snapshot_id = _optional_string(
        observation.observation.get("snapshotId")
        or observation.observation.get("snapshot_id")
    )
    if snapshot_id:
        metadata["snapshot_id"] = snapshot_id
    return ComputerUseObservation(
        action_id=action_id,
        success=status == "ok",
        operation=operation,
        status=status,
        summary=observation.summary,
        text_extract=text_extract,
        metadata=metadata,
    )


def _protocol_metadata(observation: ToolObservation) -> dict[str, Any]:
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


def _map_protocol_status(status: str) -> ComputerUseStatus:
    if status == "ok":
        return "ok"
    if status == "permission_missing":
        return "needs_user"
    if status == "not_ready":
        return "needs_user"
    if status == "not_found":
        return "failed"
    if status == "timeout":
        return "failed"
    if status == "unknown":
        return "failed"
    if status == "failed":
        return "failed"
    return "not_available"


def _status_value(value: object) -> str:
    enum_value = getattr(value, "value", value)
    return enum_value if isinstance(enum_value, str) else str(enum_value)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
