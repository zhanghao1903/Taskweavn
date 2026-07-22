"""Structured runtime observability helpers."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from typing import Any, Literal

from taskweavn.observability.logger import get_object_logger
from taskweavn.observability.models import LogContext

RUNTIME_OBSERVABILITY_SCHEMA = "plato.runtime_observability.v1"
DEFAULT_APP_CONTROL_ENV_ID = "local_macos_app_control"

RuntimeRecordType = Literal[
    "runtime_action",
    "runtime_observation",
    "computer_use_api",
]

_RUNTIME_LOGGER = get_object_logger("runtime")


def emit_runtime_action(
    *,
    session_id: str | None,
    task_id: str | None,
    execution_id: str | None,
    task_type: str,
    runtime: str,
    phase: str,
    operation: str,
    status: str,
    success: bool,
    safe_summary: str,
    workspace_id: str | None = None,
    env_id: str = DEFAULT_APP_CONTROL_ENV_ID,
    required_capability: str | None = None,
    action_id: str | None = None,
    evidence_id: str | None = None,
    confirmation_id: str | None = None,
    send_boundary_status: str | None = None,
    failure_kind: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    recovery_hint: str | None = None,
    attempt: int | None = None,
    duration_ms: int | None = None,
    timeout_seconds: float | None = None,
    idempotency_key: str | None = None,
    message_text: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Emit one structured runtime action record."""

    _emit_runtime_record(
        record_type="runtime_action",
        session_id=session_id,
        task_id=task_id,
        action_id=action_id,
        data=_runtime_data(
            record_type="runtime_action",
            workspace_id=workspace_id,
            execution_id=execution_id,
            task_type=task_type,
            runtime=runtime,
            env_id=env_id,
            required_capability=required_capability,
            phase=phase,
            operation=operation,
            status=status,
            success=success,
            safe_summary=safe_summary,
            action_id=action_id,
            evidence_id=evidence_id,
            confirmation_id=confirmation_id,
            send_boundary_status=send_boundary_status,
            failure_kind=failure_kind,
            error_code=error_code,
            error_message=error_message,
            recovery_hint=recovery_hint,
            attempt=attempt,
            duration_ms=duration_ms,
            timeout_seconds=timeout_seconds,
            idempotency_key=idempotency_key,
            message_text=message_text,
            metadata=metadata,
        ),
    )


def emit_runtime_observation(
    *,
    session_id: str | None,
    task_id: str | None,
    execution_id: str | None,
    task_type: str,
    runtime: str,
    phase: str,
    operation: str,
    status: str,
    success: bool,
    safe_summary: str,
    workspace_id: str | None = None,
    env_id: str = DEFAULT_APP_CONTROL_ENV_ID,
    required_capability: str | None = None,
    observation_id: str | None = None,
    evidence_id: str | None = None,
    confirmation_id: str | None = None,
    send_boundary_status: str | None = None,
    failure_kind: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    recovery_hint: str | None = None,
    attempt: int | None = None,
    duration_ms: int | None = None,
    timeout_seconds: float | None = None,
    idempotency_key: str | None = None,
    message_text: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Emit one structured runtime observation record."""

    _emit_runtime_record(
        record_type="runtime_observation",
        session_id=session_id,
        task_id=task_id,
        observation_id=observation_id,
        data=_runtime_data(
            record_type="runtime_observation",
            workspace_id=workspace_id,
            execution_id=execution_id,
            task_type=task_type,
            runtime=runtime,
            env_id=env_id,
            required_capability=required_capability,
            phase=phase,
            operation=operation,
            status=status,
            success=success,
            safe_summary=safe_summary,
            observation_id=observation_id,
            evidence_id=evidence_id,
            confirmation_id=confirmation_id,
            send_boundary_status=send_boundary_status,
            failure_kind=failure_kind,
            error_code=error_code,
            error_message=error_message,
            recovery_hint=recovery_hint,
            attempt=attempt,
            duration_ms=duration_ms,
            timeout_seconds=timeout_seconds,
            idempotency_key=idempotency_key,
            message_text=message_text,
            metadata=metadata,
        ),
    )


def emit_computer_use_api(
    *,
    operation: str,
    phase: str,
    status: str,
    success: bool,
    safe_summary: str,
    backend: str = "helper",
    method: str | None = None,
    path: str | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    execution_id: str | None = None,
    workspace_id: str | None = None,
    helper_bundle_id: str | None = None,
    helper_version: str | None = None,
    helper_endpoint_id: str | None = None,
    duration_ms: int | None = None,
    timeout_seconds: float | None = None,
    failure_kind: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    recovery_hint: str | None = None,
    click_attempted: bool | None = None,
    send_attempted: bool | None = None,
    idempotency_key: str | None = None,
    message_text: str | None = None,
    contact_display_name: str | None = None,
    message_chars: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Emit one structured computer-use API boundary record."""

    data = _drop_none(
        {
            "schema": RUNTIME_OBSERVABILITY_SCHEMA,
            "recordType": "computer_use_api",
            "backend": backend,
            "method": method,
            "path": path,
            "operation": operation,
            "phase": phase,
            "requestId": request_id,
            "workspaceId": workspace_id,
            "taskExecutionId": execution_id,
            "status": status,
            "success": success,
            "safeSummary": safe_summary,
            "durationMs": duration_ms,
            "timeoutSeconds": timeout_seconds,
            "failureKind": failure_kind,
            "errorCode": error_code,
            "errorMessage": _bounded(error_message),
            "recoveryHint": _bounded(recovery_hint),
            "clickAttempted": click_attempted,
            "sendAttempted": send_attempted,
            "idempotencyKeyHash": hash_text(idempotency_key),
            "messageHash": hash_text(message_text),
            "messageChars": message_chars
            if message_chars is not None
            else _message_chars(message_text),
            "contactDisplayName": contact_display_name,
            "helperEndpointId": helper_endpoint_id,
            "helperBundleId": helper_bundle_id,
            "helperVersion": helper_version,
            "metadata": dict(metadata or {}),
            "redaction": {
                "helperToken": "not_logged",
                "rawRequestBody": "not_logged",
                "rawResponseBody": "not_logged",
                "message": "hash_and_length_only",
                "accessibilityTree": "not_logged",
                "screenshot": "not_logged",
            },
        }
    )
    _emit_runtime_record(
        record_type="computer_use_api",
        session_id=session_id,
        task_id=task_id,
        data=data,
    )


def monotonic_ms(started_at: float) -> int:
    """Return elapsed monotonic milliseconds from ``started_at``."""

    return max(0, int((time.monotonic() - started_at) * 1000))


def hash_text(value: str | None) -> str | None:
    """Return a stable SHA-256 prefix for sensitive text."""

    if value is None:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _emit_runtime_record(
    *,
    record_type: RuntimeRecordType,
    session_id: str | None,
    task_id: str | None,
    data: Mapping[str, Any],
    action_id: str | None = None,
    observation_id: str | None = None,
) -> None:
    level = "ERROR" if data.get("success") is False else "DEBUG"
    _RUNTIME_LOGGER.log(
        level,
        record_type,
        message=str(data.get("safeSummary") or record_type),
        context=LogContext(
            session_id=session_id,
            task_id=task_id,
            action_id=action_id,
            observation_id=observation_id,
        ),
        data=data,
    )


def _runtime_data(
    *,
    record_type: RuntimeRecordType,
    workspace_id: str | None,
    execution_id: str | None,
    task_type: str,
    runtime: str,
    env_id: str,
    required_capability: str | None,
    phase: str,
    operation: str,
    status: str,
    success: bool,
    safe_summary: str,
    action_id: str | None = None,
    observation_id: str | None = None,
    evidence_id: str | None = None,
    confirmation_id: str | None = None,
    send_boundary_status: str | None = None,
    failure_kind: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    recovery_hint: str | None = None,
    attempt: int | None = None,
    duration_ms: int | None = None,
    timeout_seconds: float | None = None,
    idempotency_key: str | None = None,
    message_text: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _drop_none(
        {
            "schema": RUNTIME_OBSERVABILITY_SCHEMA,
            "recordType": record_type,
            "workspaceId": workspace_id,
            "executionId": execution_id,
            "taskType": task_type,
            "runtime": runtime,
            "envId": env_id,
            "requiredCapability": required_capability,
            "phase": phase,
            "operation": operation,
            "status": status,
            "success": success,
            "safeSummary": safe_summary,
            "actionId": action_id,
            "observationId": observation_id,
            "evidenceId": evidence_id,
            "confirmationId": confirmation_id,
            "sendBoundaryStatus": send_boundary_status,
            "failureKind": failure_kind,
            "errorCode": error_code,
            "errorMessage": _bounded(error_message),
            "recoveryHint": _bounded(recovery_hint),
            "attempt": attempt,
            "durationMs": duration_ms,
            "timeoutSeconds": timeout_seconds,
            "idempotencyKeyHash": hash_text(idempotency_key),
            "messageHash": hash_text(message_text),
            "messageChars": _message_chars(message_text),
            "metadata": dict(metadata or {}),
            "redaction": {
                "message": "hash_and_length_only",
                "accessibilityTree": "not_logged",
                "screenshot": "not_logged",
            },
        }
    )


def _message_chars(value: str | None) -> int | None:
    return len(value) if value is not None else None


def _bounded(value: str | None, *, limit: int = 500) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return f"{value[: limit - 1]}..."


def _drop_none(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


__all__ = [
    "DEFAULT_APP_CONTROL_ENV_ID",
    "RUNTIME_OBSERVABILITY_SCHEMA",
    "emit_computer_use_api",
    "emit_runtime_action",
    "emit_runtime_observation",
    "hash_text",
    "monotonic_ms",
]
