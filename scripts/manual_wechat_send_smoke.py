#!/usr/bin/env python3
"""Manual smoke runner for the Local macOS WeChat Send MVP.

The script talks to a running Plato sidecar over localhost HTTP. It is intended
for one controlled developer-machine smoke, not CI.

Default behavior is safe: it drafts the WeChat message and rejects the
confirmation, proving the no-send path. To send a real message, pass both
``--response confirm`` and ``--allow-send``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

WECHAT_SEND_TASK_TYPE = "communication.wechat.send_message"
WECHAT_SEND_CAPABILITY = "communication.wechat_desktop_send"
_HELPER_IDENTITY_KEYS = ("bundleId", "version", "apiVersion", "path", "signingMode")
_HELPER_MANIFEST_KEYS = ("endpoint", "bundleId", "version", "apiVersion", "pid")
_SENSITIVE_KEY_PARTS = ("api_key", "authorization", "password", "secret", "token")

ResponseMode = Literal["reject", "confirm", "prompt"]


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    session_id: str
    contact: str
    message: str
    idempotency_key: str
    response: ResponseMode
    allow_send: bool
    timeout_seconds: float
    poll_seconds: float
    preflight_only: bool = False
    helper_manifest: Path | None = None
    evidence_output: Path | None = None


@dataclass(frozen=True)
class SmokeResult:
    execution_id: str
    task_id: str
    confirmation_id: str | None
    final_status: str
    result_kind: str | None
    error_code: str | None
    evidence_count: int
    terminal_replay_status: str
    terminal_replay_same_execution: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "executionId": self.execution_id,
            "taskId": self.task_id,
            "confirmationId": self.confirmation_id,
            "finalStatus": self.final_status,
            "resultKind": self.result_kind,
            "errorCode": self.error_code,
            "evidenceCount": self.evidence_count,
            "terminalReplayStatus": self.terminal_replay_status,
            "terminalReplaySameExecution": self.terminal_replay_same_execution,
        }


@dataclass(frozen=True)
class PreflightResult:
    sidecar_ok: bool
    sidecar_name: str | None
    computer_use_status: str | None
    package_readiness_status: str | None
    accessibility_trusted: bool | None
    setup_hint: str | None
    computer_use_ready: bool | None = None
    computer_use_backend: str | None = None
    computer_use_helper: dict[str, object] | None = None
    computer_use_diagnostics: dict[str, object] | None = None
    helper_manifest: dict[str, object] | None = None
    helper_status: str | None = None
    failure_kind: str | None = None
    wechat_app_status: str | None = None
    wechat_app_success: bool | None = None
    wechat_app_phase: str | None = None
    wechat_app_summary: str | None = None
    wechat_app_failure_kind: str | None = None
    wechat_app_setup_hint: str | None = None
    wechat_app_recovery_actions: tuple[str, ...] = ()
    wechat_app_diagnostics: dict[str, object] | None = None

    @property
    def ready(self) -> bool:
        if not self.sidecar_ok:
            return False
        if self.wechat_app_success is False:
            return False
        if self.computer_use_ready is not None:
            base_ready = self.computer_use_ready
        elif self.package_readiness_status == "ready":
            base_ready = True
        else:
            base_ready = (
                self.computer_use_status == "ok" and self.accessibility_trusted is True
            )
        if self.wechat_app_success is True:
            return base_ready
        return base_ready

    def as_dict(self) -> dict[str, object]:
        return {
            "sidecarOk": self.sidecar_ok,
            "sidecarName": self.sidecar_name,
            "computerUseStatus": self.computer_use_status,
            "packageReadinessStatus": self.package_readiness_status,
            "accessibilityTrusted": self.accessibility_trusted,
            "setupHint": self.setup_hint,
            "computerUseReady": self.computer_use_ready,
            "computerUseBackend": self.computer_use_backend,
            "computerUseHelper": self.computer_use_helper,
            "computerUseDiagnostics": self.computer_use_diagnostics,
            "helperManifest": self.helper_manifest,
            "helperStatus": self.helper_status,
            "failureKind": self.failure_kind,
            "wechatAppStatus": self.wechat_app_status,
            "wechatAppSuccess": self.wechat_app_success,
            "wechatAppPhase": self.wechat_app_phase,
            "wechatAppSummary": self.wechat_app_summary,
            "wechatAppFailureKind": self.wechat_app_failure_kind,
            "wechatAppSetupHint": self.wechat_app_setup_hint,
            "wechatAppRecoveryActions": list(self.wechat_app_recovery_actions),
            "wechatAppDiagnostics": self.wechat_app_diagnostics,
            "ready": self.ready,
        }


def main() -> int:
    config = _parse_args()
    try:
        if config.preflight_only:
            preflight = run_preflight(config)
            write_evidence_output(config, kind="preflight", result=preflight.as_dict())
            print(json.dumps(preflight.as_dict(), ensure_ascii=False, indent=2))
            return 0 if preflight.ready else 1
        result = run_smoke(config)
    except SmokeError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        if exc.details:
            print(json.dumps(exc.details, ensure_ascii=False, indent=2), file=sys.stderr)
        write_failure_evidence_output(config, exc)
        return 1

    write_evidence_output(config, kind="smoke", result=result.as_dict())
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    replay_ok = (
        result.terminal_replay_same_execution
        and result.terminal_replay_status == result.final_status
    )
    if config.response == "confirm":
        sent = result.final_status == "done" and result.result_kind == "wechat_send_result"
        return 0 if sent and replay_ok else 1
    rejected = result.final_status == "failed" and result.error_code == "wechat_send_rejected"
    return 0 if rejected and replay_ok else 1


def run_preflight(
    config: SmokeConfig,
    *,
    readiness_checker: Callable[[], dict[str, Any]] | None = None,
) -> PreflightResult:
    health = _request_json(config.base_url, "GET", "/api/v1/health")
    health_data = _require_data(health, "health")
    readiness_payload = (
        readiness_checker()
        if readiness_checker is not None
        else _sidecar_computer_use_readiness(config)
    )
    if not isinstance(readiness_payload, dict):
        raise SmokeError("computer-use readiness result was not an object.")

    if "ready" in readiness_payload or "backend" in readiness_payload:
        result = _preflight_from_sidecar_readiness(
            health_data=health_data,
            computer_use=readiness_payload,
        )
        return _with_helper_wechat_app_readiness(config, result)

    metadata = readiness_payload.get("metadata")
    readiness = {}
    if isinstance(metadata, dict):
        raw_readiness = metadata.get("readiness")
        if isinstance(raw_readiness, dict):
            readiness = raw_readiness

    result = PreflightResult(
        sidecar_ok=True,
        sidecar_name=_optional_str(health_data, "name"),
        computer_use_status=_optional_str(readiness_payload, "status"),
        package_readiness_status=_optional_str(readiness, "status"),
        accessibility_trusted=_optional_bool(readiness, "accessibility_trusted"),
        setup_hint=_optional_str(readiness, "setup_hint"),
    )
    return _with_helper_wechat_app_readiness(config, result)


def _preflight_from_sidecar_readiness(
    *,
    health_data: dict[str, Any],
    computer_use: dict[str, Any],
) -> PreflightResult:
    diagnostics = computer_use.get("diagnostics")
    readiness = {}
    if isinstance(diagnostics, dict):
        raw_readiness = diagnostics.get("readiness")
        if isinstance(raw_readiness, dict):
            readiness = raw_readiness

    operation_status = _optional_str(computer_use, "operationStatus")
    status = _optional_str(computer_use, "status")
    return PreflightResult(
        sidecar_ok=True,
        sidecar_name=_optional_str(health_data, "name"),
        computer_use_status=operation_status or status,
        package_readiness_status=status,
        accessibility_trusted=_optional_bool(readiness, "accessibility_trusted"),
        setup_hint=_optional_str(computer_use, "setupHint")
        or _optional_str(readiness, "setup_hint"),
        computer_use_ready=_optional_bool(computer_use, "ready"),
        computer_use_backend=_optional_str(computer_use, "backend"),
        computer_use_helper=_safe_helper_identity(computer_use.get("helper")),
        computer_use_diagnostics=_safe_diagnostics(diagnostics),
        helper_status=_optional_str(computer_use, "helperStatus"),
        failure_kind=_optional_str(computer_use, "failureKind"),
    )


def _with_helper_wechat_app_readiness(
    config: SmokeConfig,
    result: PreflightResult,
) -> PreflightResult:
    if config.helper_manifest is None:
        return result
    helper_manifest: dict[str, object] | None = None
    try:
        helper_manifest = _safe_helper_manifest(
            _read_helper_manifest(config.helper_manifest.expanduser())
        )
    except SmokeError as exc:
        return replace(
            result,
            helper_manifest=None,
            wechat_app_status="failed",
            wechat_app_success=False,
            wechat_app_phase="helper_manifest",
            wechat_app_summary=str(exc),
            wechat_app_failure_kind="helper_manifest_unavailable",
            wechat_app_setup_hint=(
                "Start or relaunch Plato Computer Use Helper, then rerun "
                "helper-backed preflight before publishing a WeChat task."
            ),
            wechat_app_recovery_actions=(
                "start_or_relaunch_helper",
                "rerun_helper_preflight",
            ),
            wechat_app_diagnostics=_safe_diagnostics(
                {
                    "error": str(exc),
                    "details": exc.details,
                }
            ),
        )
    if not result.ready:
        return replace(
            result,
            helper_manifest=helper_manifest,
            wechat_app_status="skipped",
            wechat_app_success=False,
            wechat_app_phase="helper_package_readiness",
            wechat_app_summary=(
                "Skipped WeChat app readiness because helper package readiness "
                "is not ready."
            ),
            wechat_app_failure_kind=result.failure_kind or "helper_not_ready",
            wechat_app_setup_hint=result.setup_hint
            or "Fix helper readiness, then rerun helper-backed preflight.",
            wechat_app_recovery_actions=(
                "fix_helper_readiness",
                "rerun_helper_preflight",
            ),
            wechat_app_diagnostics=_safe_diagnostics(
                {
                    "computerUseStatus": result.computer_use_status,
                    "packageReadinessStatus": result.package_readiness_status,
                    "helperStatus": result.helper_status,
                    "failureKind": result.failure_kind,
                }
            ),
        )
    try:
        payload = _helper_wechat_app_readiness(config)
    except SmokeError as exc:
        return replace(
            result,
            helper_manifest=helper_manifest,
            wechat_app_status="failed",
            wechat_app_success=False,
            wechat_app_phase="helper_app_readiness",
            wechat_app_summary=str(exc),
            wechat_app_failure_kind="helper_app_unavailable",
            wechat_app_setup_hint=(
                "Start or relaunch Plato Computer Use Helper, then rerun "
                "helper-backed preflight before publishing a WeChat task."
            ),
            wechat_app_recovery_actions=(
                "start_or_relaunch_helper",
                "rerun_helper_preflight",
            ),
            wechat_app_diagnostics=_safe_diagnostics(
                {
                    "error": str(exc),
                    "details": exc.details,
                }
            ),
        )
    diagnostics = payload.get("diagnostics")
    app_status = _optional_str(payload, "status")
    app_success = _optional_bool(payload, "success")
    if app_success is None and app_status is not None:
        app_success = app_status == "ready"
    return replace(
        result,
        helper_manifest=helper_manifest,
        wechat_app_status=app_status,
        wechat_app_success=app_success,
        wechat_app_phase=_optional_str(payload, "phase"),
        wechat_app_summary=_optional_str(payload, "summary"),
        wechat_app_failure_kind=_optional_str(payload, "failureKind"),
        wechat_app_setup_hint=_optional_str(payload, "setupHint"),
        wechat_app_recovery_actions=_optional_str_tuple(payload, "recoveryActions"),
        wechat_app_diagnostics=(
            dict(diagnostics) if isinstance(diagnostics, dict) else None
        ),
    )


def write_evidence_output(
    config: SmokeConfig,
    *,
    kind: Literal["preflight", "smoke", "failure"],
    result: dict[str, object],
) -> None:
    if config.evidence_output is None:
        return
    payload = {
        "kind": kind,
        "generatedAt": dt.datetime.now(dt.UTC).isoformat(),
        "config": {
            "sessionId": config.session_id or None,
            "idempotencyKey": config.idempotency_key,
            "response": config.response,
            "allowSend": config.allow_send,
            "preflightOnly": config.preflight_only,
            "helperManifestProvided": config.helper_manifest is not None,
            "contactProvided": bool(config.contact),
            "messageChars": len(config.message),
        },
        "result": result,
        "redaction": {
            "contact": "not_written",
            "messageText": "not_written",
        },
    }
    config.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    config.evidence_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_failure_evidence_output(config: SmokeConfig, exc: SmokeError) -> None:
    write_evidence_output(
        config,
        kind="failure",
        result={
            "message": _redact_value(str(exc), config),
            "details": _redact_value(exc.details, config),
        },
    )


def _redact_value(value: object, config: SmokeConfig) -> object:
    if isinstance(value, str):
        text = value
        if config.contact:
            text = text.replace(config.contact, "[redacted-contact]")
        if config.message:
            text = text.replace(config.message, "[redacted-message]")
        return text
    if isinstance(value, dict):
        return {
            str(key): _redact_value(child, config)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(child, config) for child in value]
    if isinstance(value, tuple):
        return [_redact_value(child, config) for child in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def run_smoke(config: SmokeConfig) -> SmokeResult:
    if config.response == "confirm" and not config.allow_send:
        raise SmokeError(
            "--response confirm requires --allow-send because it sends a real WeChat message."
        )

    task_request = build_task_request(config)
    print("Publishing WeChat send task...")
    first = _request_json(config.base_url, "POST", "/api/v1/tasks", task_request)
    execution = _require_data(first, "publish")
    execution_id = _required_str(execution, "executionId")
    task_id = _required_str(execution, "taskId")
    first_status = _required_str(execution, "status")
    print(f"Execution {execution_id} status: {first_status}")
    if first_status != "waiting_for_user":
        raise SmokeError(
            "Expected first publish to wait for confirmation.",
            details={"execution": execution},
        )

    confirmation = _wait_for_confirmation(config, task_id)
    confirmation_id = _required_str(confirmation, "id")
    print("\nConfirmation:")
    print(f"- id: {confirmation_id}")
    print(f"- title: {_optional_str(confirmation, 'title')}")
    print(f"- body: {_optional_str(confirmation, 'body')}")
    print(f"- response: {config.response}")

    response_value = _resolve_response(config)
    _respond_confirmation(config, confirmation_id, response_value)

    print("Replaying same idempotency key to resume execution...")
    second = _request_json(config.base_url, "POST", "/api/v1/tasks", task_request)
    resumed = _require_data(second, "resume")
    final_status = _required_str(resumed, "status")
    print(f"Execution {execution_id} final status: {final_status}")

    result_kind: str | None = None
    error_code: str | None = None
    if final_status == "done":
        result = _request_json(config.base_url, "GET", f"/api/v1/tasks/{execution_id}/result")
        result_data = _require_data(result, "result")
        payload = result_data.get("structuredPayload")
        if isinstance(payload, dict):
            result_kind = _optional_str(payload, "kind")
    elif final_status == "failed":
        error = _request_json(config.base_url, "GET", f"/api/v1/tasks/{execution_id}/error")
        error_data = _require_data(error, "error")
        error_code = _optional_str(error_data, "code")

    evidence = _request_json(config.base_url, "GET", f"/api/v1/tasks/{execution_id}/evidence")
    evidence_data = _require_data(evidence, "evidence")
    evidence_items = evidence_data.get("items")
    evidence_count = len(evidence_items) if isinstance(evidence_items, list) else 0
    replay_status, replay_same_execution = _replay_terminal_task(
        config,
        task_request=task_request,
        execution_id=execution_id,
    )

    return SmokeResult(
        execution_id=execution_id,
        task_id=task_id,
        confirmation_id=confirmation_id,
        final_status=final_status,
        result_kind=result_kind,
        error_code=error_code,
        evidence_count=evidence_count,
        terminal_replay_status=replay_status,
        terminal_replay_same_execution=replay_same_execution,
    )


def build_task_request(config: SmokeConfig) -> dict[str, object]:
    return {
        "idempotencyKey": config.idempotency_key,
        "requester": {
            "kind": "external_app",
            "id": "manual-wechat-smoke",
            "displayName": "Manual WeChat smoke",
            "trustScope": "local-developer-machine",
        },
        "externalRef": {
            "system": "manual_smoke",
            "kind": "wechat_message",
            "id": config.idempotency_key,
        },
        "taskType": WECHAT_SEND_TASK_TYPE,
        "intent": "Send one confirmation-gated WeChat message from local macOS.",
        "input": {
            "contactDisplayName": config.contact,
            "messageText": config.message,
            "operatorNote": "Manual Local macOS WeChat Send MVP smoke.",
        },
        "policy": {
            "requiredCapability": WECHAT_SEND_CAPABILITY,
            "allowedTools": ["computer_use", "wechat_desktop"],
            "requiresHumanConfirmation": True,
            "riskLevel": "high",
        },
        "evidence": {
            "required": ["result_summary", "tool_observation"],
            "optional": [],
            "redactForDiagnostics": True,
        },
        "callback": {"mode": "none"},
        "metadata": {
            "sessionId": config.session_id,
            "manualSmoke": True,
        },
    }


def _replay_terminal_task(
    config: SmokeConfig,
    *,
    task_request: dict[str, object],
    execution_id: str,
) -> tuple[str, bool]:
    print("Replaying terminal idempotency key to verify no duplicate side effect...")
    replay = _request_json(config.base_url, "POST", "/api/v1/tasks", task_request)
    replay_data = _require_data(replay, "terminal replay")
    replay_execution_id = _required_str(replay_data, "executionId")
    replay_status = _required_str(replay_data, "status")
    return replay_status, replay_execution_id == execution_id


def _wait_for_confirmation(config: SmokeConfig, task_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + config.timeout_seconds
    while True:
        snapshot = _request_json(
            config.base_url,
            "GET",
            f"/api/v1/sessions/{config.session_id}/snapshot",
        )
        data = _require_data(snapshot, "snapshot")
        pending = data.get("pendingConfirmations")
        if isinstance(pending, list):
            for item in pending:
                if not isinstance(item, dict):
                    continue
                if item.get("status") == "pending" and item.get("taskNodeId") == task_id:
                    return item
        if time.monotonic() >= deadline:
            raise SmokeError(
                "Timed out waiting for pending confirmation in session snapshot.",
                details={"taskId": task_id, "pendingConfirmations": pending},
            )
        time.sleep(config.poll_seconds)


def _resolve_response(config: SmokeConfig) -> Literal["confirm", "reject"]:
    if config.response == "reject":
        return "reject"
    if config.response == "confirm":
        return "confirm"
    print("\nType exactly 'confirm' to send, or 'reject' to cancel.")
    value = input("confirmation response> ").strip().lower()
    if value not in {"confirm", "reject"}:
        raise SmokeError("Manual response must be exactly 'confirm' or 'reject'.")
    if value == "confirm" and not config.allow_send:
        raise SmokeError("Interactive confirm requires --allow-send.")
    return "confirm" if value == "confirm" else "reject"


def _respond_confirmation(
    config: SmokeConfig,
    confirmation_id: str,
    value: Literal["confirm", "reject"],
) -> None:
    response = _request_json(
        config.base_url,
        "POST",
        f"/api/v1/sessions/{config.session_id}/confirmations/{confirmation_id}/respond",
        {
            "commandId": f"manual-wechat-smoke-{value}-{uuid.uuid4().hex}",
            "sessionId": config.session_id,
            "payload": {
                "value": value,
                "note": f"Manual WeChat smoke response: {value}.",
            },
        },
    )
    if response.get("ok") is not True:
        raise SmokeError("Confirmation response was rejected.", details=response)


def _request_json(
    base_url: str,
    method: str,
    path: str,
    body: dict[str, object] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    encoded_body = None
    headers = {"Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    if body is not None:
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=encoded_body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        raise SmokeError(
            f"HTTP {exc.code} from {method} {path}",
            details=parsed if isinstance(parsed, dict) else {"payload": parsed},
        ) from exc
    except urllib.error.URLError as exc:
        raise SmokeError(f"Request failed for {method} {path}: {exc}") from exc
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Response was not JSON for {method} {path}.") from exc
    if not isinstance(parsed, dict):
        raise SmokeError(f"Response JSON was not an object for {method} {path}.")
    return parsed


def _require_data(response: dict[str, Any], label: str) -> dict[str, Any]:
    if response.get("ok") is not True:
        raise SmokeError(f"{label} response was not ok.", details=response)
    data = response.get("data")
    if not isinstance(data, dict):
        raise SmokeError(f"{label} response did not contain object data.", details=response)
    return data


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SmokeError(f"Expected non-empty string field: {key}", details=payload)
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _optional_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    return value if isinstance(value, bool) else None


def _optional_str_tuple(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _safe_helper_identity(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    safe: dict[str, object] = {}
    for key in _HELPER_IDENTITY_KEYS:
        raw = value.get(key)
        if isinstance(raw, str) and raw:
            safe[key] = raw[:500]
    return safe or None


def _safe_helper_manifest(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    safe: dict[str, object] = {}
    for key in _HELPER_MANIFEST_KEYS:
        raw = value.get(key)
        if isinstance(raw, str) and raw:
            safe[key] = raw[:500]
        elif isinstance(raw, int):
            safe[key] = raw
    return safe or None


def _safe_diagnostics(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    safe = {
        str(key)[:80]: _safe_diagnostic_value(nested)
        for key, nested in list(value.items())[:20]
        if not _is_sensitive_key(str(key))
    }
    return safe or None


def _safe_diagnostic_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _safe_diagnostic_value(nested)
            for key, nested in list(value.items())[:20]
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [_safe_diagnostic_value(item) for item in list(value)[:20]]
    return str(value)[:500]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _sidecar_computer_use_readiness(config: SmokeConfig) -> dict[str, Any]:
    readiness = _request_json(config.base_url, "GET", "/api/v1/settings/readiness")
    data = _require_data(readiness, "settings readiness")
    computer_use = data.get("computerUse")
    if not isinstance(computer_use, dict):
        raise SmokeError("settings readiness response did not include computerUse.")
    return computer_use


def _helper_wechat_app_readiness(config: SmokeConfig) -> dict[str, Any]:
    if config.helper_manifest is None:
        raise SmokeError("helper manifest is required for helper WeChat app readiness.")
    manifest_path = config.helper_manifest.expanduser()
    manifest = _read_helper_manifest(manifest_path)
    endpoint = _required_manifest_str(manifest, "endpoint", manifest_path)
    token = _optional_str(manifest, "token")
    token_ref = _optional_str(manifest, "tokenRef") or _optional_str(
        manifest,
        "token_ref",
    )
    if token is None and token_ref is not None:
        token = _read_helper_token(manifest_path, token_ref)

    headers = {"Authorization": f"Bearer {token}"} if token else None
    return _request_json(
        endpoint,
        "POST",
        "/v1/apps/wechat/readiness",
        {
            "requestId": f"manual-wechat-preflight-{uuid.uuid4().hex}",
        },
        extra_headers=headers,
    )


def _read_helper_manifest(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SmokeError(f"helper manifest unavailable: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SmokeError(f"helper manifest was not JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise SmokeError("helper manifest must be a JSON object.")
    return parsed


def _read_helper_token(manifest_path: Path, token_ref: str) -> str:
    token_path = Path(token_ref).expanduser()
    if not token_path.is_absolute():
        token_path = manifest_path.parent / token_path
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SmokeError(f"helper token unavailable: {token_path}") from exc
    if not token:
        raise SmokeError(f"helper token is empty: {token_path}")
    return token


def _required_manifest_str(
    manifest: dict[str, Any],
    key: str,
    path: Path,
) -> str:
    value = _optional_str(manifest, key)
    if value is None:
        raise SmokeError(f"helper manifest {path} requires {key}.")
    return value


def _parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Running Plato sidecar base URL.")
    parser.add_argument("--session-id", help="Existing Plato session id.")
    parser.add_argument("--contact", help="Controlled WeChat test contact.")
    parser.add_argument("--message", help="Non-sensitive test message.")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Check sidecar and local macOS readiness without publishing a task.",
    )
    parser.add_argument(
        "--helper-manifest",
        type=Path,
        help=(
            "Optional Plato Computer Use Helper manifest. With --preflight-only, "
            "also checks WeChat app/window readiness through the helper; this may "
            "open or focus WeChat."
        ),
    )
    parser.add_argument(
        "--idempotency-key",
        default=f"manual-wechat-smoke-{uuid.uuid4().hex}",
        help="Stable key for publish/resume replay. Defaults to a new key.",
    )
    parser.add_argument(
        "--response",
        choices=("reject", "confirm", "prompt"),
        default="reject",
        help="Confirmation response. Default is reject/no-send.",
    )
    parser.add_argument(
        "--allow-send",
        action="store_true",
        help="Required when response is confirm or interactive confirm.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument(
        "--evidence-output",
        type=Path,
        help=(
            "Optional JSON file for durable smoke evidence. Contact and message "
            "text are redacted."
        ),
    )
    args = parser.parse_args()
    if not args.preflight_only:
        _require_cli_arg(args.session_id, "--session-id")
        _require_cli_arg(args.contact, "--contact")
        _require_cli_arg(args.message, "--message")
    return SmokeConfig(
        base_url=args.base_url,
        session_id=args.session_id or "",
        contact=args.contact or "",
        message=args.message or "",
        idempotency_key=args.idempotency_key,
        response=args.response,
        allow_send=args.allow_send,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
        preflight_only=args.preflight_only,
        helper_manifest=args.helper_manifest,
        evidence_output=args.evidence_output,
    )


def _require_cli_arg(value: str | None, name: str) -> None:
    if value is None or not value.strip():
        raise SystemExit(f"{name} is required unless --preflight-only is set")


class SmokeError(Exception):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


if __name__ == "__main__":
    raise SystemExit(main())
