#!/usr/bin/env python3
"""Manual preflight for the Plato Computer Use Helper app.

This script validates the helper-backed macOS computer-use path without
publishing a task and without sending any external message. It is meant to be
run before the WeChat send smoke so helper identity, TCC permissions, manifest
publication, and optional app-specific WeChat readiness are checked in one
repeatable command.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskweavn.tools import ComputerUseHelperBackend, ComputerUseHelperBackendConfig
from taskweavn.types import ComputerUseObservation

DEFAULT_HELPER_APP_PATH = Path("~/Applications/Plato Computer Use Helper Dev.app")
DEFAULT_HELPER_MANIFEST_PATH = Path(
    "~/Library/Application Support/PlatoDev/computer-use-helper.json"
)
DEFAULT_EXPECTED_BUNDLE_ID = "com.taskweavn.plato.computer-use-helper.dev"
DEFAULT_EXPECTED_API_VERSION = "plato.computer_use_helper.v1"
MACOS_ACCESSIBILITY_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)
MACOS_AUTOMATION_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
)
_SAFE_MANIFEST_KEYS = ("endpoint", "bundleId", "version", "apiVersion", "pid")


@dataclass(frozen=True)
class HelperPreflightConfig:
    helper_manifest: Path = DEFAULT_HELPER_MANIFEST_PATH
    helper_app_path: Path = DEFAULT_HELPER_APP_PATH
    helper_auto_launch: bool = True
    helper_launch_timeout_seconds: float = 90.0
    helper_launch_poll_interval_seconds: float = 0.2
    expected_bundle_id: str = DEFAULT_EXPECTED_BUNDLE_ID
    expected_api_version: str = DEFAULT_EXPECTED_API_VERSION
    allowed_apps: tuple[str, ...] = ("WeChat", "TextEdit")
    timeout_seconds: float = 10.0
    check_wechat_app: bool = False
    open_permission_settings: bool = False
    restart_helper: bool = False
    helper_restart_wait_seconds: float = 5.0
    evidence_output: Path | None = None


@dataclass(frozen=True)
class HelperPreflightResult:
    helper_observation: dict[str, Any]
    helper_ready: bool
    package_readiness_status: str | None
    accessibility_trusted: bool | None
    helper_status: str | None
    failure_kind: str | None
    runtime_identity: dict[str, Any] | None
    setup_hint: str | None
    recovery_actions: tuple[str, ...]
    helper_manifest: dict[str, Any] | None = None
    wechat_app_status: str | None = None
    wechat_app_success: bool | None = None
    wechat_app_phase: str | None = None
    wechat_app_summary: str | None = None
    wechat_app_failure_kind: str | None = None
    wechat_app_setup_hint: str | None = None
    wechat_app_recovery_actions: tuple[str, ...] = ()
    wechat_app_diagnostics: dict[str, Any] | None = None

    @property
    def ready(self) -> bool:
        if not self.helper_ready:
            return False
        if self.wechat_app_success is None:
            return True
        return self.wechat_app_success

    def as_dict(self) -> dict[str, Any]:
        return {
            "helperObservation": self.helper_observation,
            "helperReady": self.helper_ready,
            "packageReadinessStatus": self.package_readiness_status,
            "accessibilityTrusted": self.accessibility_trusted,
            "helperStatus": self.helper_status,
            "failureKind": self.failure_kind,
            "runtimeIdentity": self.runtime_identity,
            "setupHint": self.setup_hint,
            "recoveryActions": list(self.recovery_actions),
            "helperManifest": self.helper_manifest,
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


class HelperPreflightError(RuntimeError):
    """A sanitized helper preflight failure."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}


def main() -> int:
    config = _parse_args()
    return _run(config)


def _run(config: HelperPreflightConfig) -> int:
    helper_restart = (
        _restart_helper_from_manifest(config) if config.restart_helper else None
    )
    try:
        result = run_helper_preflight(config)
    except HelperPreflightError as exc:
        payload = {"error": str(exc), "details": exc.details, "ready": False}
        payload["helperSignature"] = _helper_signature_diagnostics(config)
        payload["permissionSubject"] = _permission_subject_from_payload(
            config,
            payload,
        )
        if helper_restart is not None:
            payload["helperRestart"] = helper_restart
        _write_evidence(config, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    payload = result.as_dict()
    payload["helperSignature"] = _helper_signature_diagnostics(config)
    payload["permissionSubject"] = _permission_subject_from_payload(config, payload)
    if helper_restart is not None:
        payload["helperRestart"] = helper_restart
    if config.open_permission_settings and not result.ready:
        payload["permissionSettings"] = _open_permission_settings(
            result.recovery_actions + result.wechat_app_recovery_actions
        )
    _write_evidence(config, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ready else 1


def run_helper_preflight(config: HelperPreflightConfig) -> HelperPreflightResult:
    backend = ComputerUseHelperBackend(
        config=ComputerUseHelperBackendConfig(
            endpoint_manifest_path=config.helper_manifest.expanduser(),
            helper_app_path=config.helper_app_path.expanduser(),
            helper_auto_launch=config.helper_auto_launch,
            helper_launch_timeout_seconds=config.helper_launch_timeout_seconds,
            helper_launch_poll_interval_seconds=(
                config.helper_launch_poll_interval_seconds
            ),
            expected_bundle_id=config.expected_bundle_id,
            expected_api_version=config.expected_api_version,
            allowed_apps=config.allowed_apps,
            timeout_seconds=config.timeout_seconds,
        )
    )
    observation = backend.readiness()
    result = _result_from_observation(config, observation)
    if not config.check_wechat_app:
        return result
    if not result.helper_ready:
        return _with_skipped_wechat_readiness(result)
    try:
        payload = _helper_wechat_app_readiness(config)
    except HelperPreflightError as exc:
        return _with_failed_wechat_readiness(result, exc)
    return _with_wechat_readiness_payload(result, payload)


def _result_from_observation(
    config: HelperPreflightConfig,
    observation: ComputerUseObservation,
) -> HelperPreflightResult:
    observation_payload = observation.model_dump(mode="json")
    metadata = observation.metadata
    readiness = _dict(metadata.get("readiness"))
    diagnostics = _dict(metadata.get("diagnostics"))
    runtime_identity = _dict(diagnostics.get("runtimeIdentity"))
    package_status = _optional_str(readiness, "status")
    helper_status = _optional_str(metadata, "helper_status")
    recovery_actions = _string_tuple(metadata.get("recovery_actions"))
    setup_hint = _optional_str(metadata, "setup_hint") or _optional_str(
        readiness,
        "setup_hint",
    )
    helper_ready = (
        observation.success
        and observation.status == "ok"
        and (package_status in (None, "ready"))
    )
    helper_manifest = _read_manifest_safe(config.helper_manifest)
    return HelperPreflightResult(
        helper_observation=observation_payload,
        helper_ready=helper_ready,
        package_readiness_status=package_status,
        accessibility_trusted=_optional_bool(readiness, "accessibility_trusted"),
        helper_status=helper_status,
        failure_kind=_optional_str(metadata, "failure_kind"),
        runtime_identity=runtime_identity,
        setup_hint=setup_hint,
        recovery_actions=recovery_actions,
        helper_manifest=helper_manifest,
    )


def _with_skipped_wechat_readiness(
    result: HelperPreflightResult,
) -> HelperPreflightResult:
    return HelperPreflightResult(
        **{
            **result.__dict__,
            "wechat_app_status": "skipped",
            "wechat_app_success": False,
            "wechat_app_phase": "helper_package_readiness",
            "wechat_app_summary": (
                "Skipped WeChat app readiness because helper package readiness "
                "is not ready."
            ),
            "wechat_app_failure_kind": result.failure_kind or "helper_not_ready",
            "wechat_app_setup_hint": result.setup_hint
            or "Fix helper readiness, then rerun helper preflight.",
            "wechat_app_recovery_actions": (
                "fix_helper_readiness",
                "rerun_helper_preflight",
            ),
            "wechat_app_diagnostics": {
                "packageReadinessStatus": result.package_readiness_status,
                "helperStatus": result.helper_status,
                "failureKind": result.failure_kind,
            },
        }
    )


def _with_failed_wechat_readiness(
    result: HelperPreflightResult,
    exc: HelperPreflightError,
) -> HelperPreflightResult:
    return HelperPreflightResult(
        **{
            **result.__dict__,
            "wechat_app_status": "failed",
            "wechat_app_success": False,
            "wechat_app_phase": "helper_app_readiness",
            "wechat_app_summary": str(exc),
            "wechat_app_failure_kind": "helper_app_unavailable",
            "wechat_app_setup_hint": (
                "Start or relaunch Plato Computer Use Helper, then rerun "
                "helper preflight before publishing a WeChat task."
            ),
            "wechat_app_recovery_actions": (
                "start_or_relaunch_helper",
                "rerun_helper_preflight",
            ),
            "wechat_app_diagnostics": {"error": str(exc), "details": exc.details},
        }
    )


def _with_wechat_readiness_payload(
    result: HelperPreflightResult,
    payload: dict[str, Any],
) -> HelperPreflightResult:
    diagnostics = _dict(payload.get("diagnostics"))
    status = _optional_str(payload, "status")
    success = _optional_bool(payload, "success")
    if success is None and status is not None:
        success = status == "ready" or status == "ok"
    recovery_actions = _string_tuple(
        payload.get("recoveryActions") or payload.get("recovery_actions")
    )
    return HelperPreflightResult(
        **{
            **result.__dict__,
            "wechat_app_status": status,
            "wechat_app_success": success,
            "wechat_app_phase": _optional_str(payload, "phase")
            or _optional_str(diagnostics, "phase"),
            "wechat_app_summary": _optional_str(payload, "summary"),
            "wechat_app_failure_kind": _optional_str(payload, "failureKind")
            or _optional_str(payload, "failure_kind")
            or _optional_str(diagnostics, "failureKind")
            or _optional_str(diagnostics, "failure_kind"),
            "wechat_app_setup_hint": _optional_str(payload, "setupHint")
            or _optional_str(payload, "setup_hint"),
            "wechat_app_recovery_actions": recovery_actions,
            "wechat_app_diagnostics": diagnostics,
        }
    )


def _helper_wechat_app_readiness(config: HelperPreflightConfig) -> dict[str, Any]:
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
        body={"requestId": f"manual-helper-preflight-{uuid.uuid4().hex}"},
        extra_headers=headers,
        timeout_seconds=config.timeout_seconds,
    )


def _request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = _decode_http_error(exc)
        raise HelperPreflightError(
            f"helper request failed with HTTP {exc.code}",
            details=details,
        ) from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise HelperPreflightError(
            f"helper request failed: {type(exc).__name__}",
            details={"error": str(exc)},
        ) from exc
    if not isinstance(parsed, dict):
        raise HelperPreflightError("helper response was not a JSON object.")
    return parsed


def _decode_http_error(exc: urllib.error.HTTPError) -> dict[str, Any]:
    try:
        parsed = json.loads(exc.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": exc.code, "reason": exc.reason}
    if isinstance(parsed, dict):
        return parsed
    return {"status": exc.code, "reason": exc.reason}


def _read_manifest_safe(path: Path) -> dict[str, Any] | None:
    try:
        return _safe_manifest(_read_helper_manifest(path.expanduser()))
    except HelperPreflightError:
        return None


def _read_helper_manifest(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise HelperPreflightError(f"helper manifest unavailable: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HelperPreflightError(f"helper manifest was not JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise HelperPreflightError("helper manifest must be a JSON object.")
    return parsed


def _safe_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: manifest[key]
        for key in _SAFE_MANIFEST_KEYS
        if key in manifest and isinstance(manifest[key], str | int)
    }


def _read_helper_token(manifest_path: Path, token_ref: str) -> str:
    token_path = Path(token_ref).expanduser()
    if not token_path.is_absolute():
        token_path = manifest_path.parent / token_path
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise HelperPreflightError(f"helper token unavailable: {token_path}") from exc
    if not token:
        raise HelperPreflightError(f"helper token is empty: {token_path}")
    return token


def _required_manifest_str(
    manifest: dict[str, Any],
    key: str,
    path: Path,
) -> str:
    value = _optional_str(manifest, key)
    if value is None:
        raise HelperPreflightError(f"helper manifest {path} requires {key}.")
    return value


def _write_evidence(config: HelperPreflightConfig, payload: dict[str, Any]) -> None:
    if config.evidence_output is None:
        return
    evidence = {
        "kind": "computer_use_helper_preflight",
        "helperManifestPath": str(config.helper_manifest.expanduser()),
        "helperAppPath": str(config.helper_app_path.expanduser()),
        "checkWeChatApp": config.check_wechat_app,
        "result": payload,
    }
    config.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    config.evidence_output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _permission_subject_from_payload(
    config: HelperPreflightConfig,
    payload: dict[str, Any],
) -> dict[str, Any]:
    helper_app_path = str(config.helper_app_path.expanduser())
    helper_observation = _dict(payload.get("helperObservation"))
    metadata = _dict(helper_observation.get("metadata"))
    helper_metadata = _dict(metadata.get("helper"))
    helper_manifest = _dict(payload.get("helperManifest"))
    runtime_identity = _dict(payload.get("runtimeIdentity"))
    helper_signature = _dict(payload.get("helperSignature"))
    return {
        "expectedBundleId": config.expected_bundle_id,
        "helperAppPath": helper_app_path,
        "manifestBundleId": _optional_str(helper_manifest, "bundleId"),
        "helperBundleId": _optional_str(helper_metadata, "bundleId"),
        "runtimeMode": _optional_str(runtime_identity, "mode"),
        "effectiveExecutable": _optional_str(
            runtime_identity,
            "effectiveExecutable",
        ),
        "accessibilityTrusted": payload.get("accessibilityTrusted")
        if isinstance(payload.get("accessibilityTrusted"), bool)
        else None,
        "packageReadinessStatus": payload.get("packageReadinessStatus")
        if isinstance(payload.get("packageReadinessStatus"), str)
        else None,
        "helperStatus": payload.get("helperStatus")
        if isinstance(payload.get("helperStatus"), str)
        else None,
        "signature": helper_signature or None,
        "recoveryActions": list(_string_tuple(payload.get("recoveryActions"))),
        "operatorInstruction": (
            "Grant or refresh macOS Accessibility and Automation permissions "
            f"for {helper_app_path}, restart the helper, then rerun "
            "helper-only preflight before publishing a computer-use task."
        ),
    }


def _helper_signature_diagnostics(config: HelperPreflightConfig) -> dict[str, Any]:
    app_path = str(config.helper_app_path.expanduser())
    base: dict[str, Any] = {
        "checked": False,
        "appPath": app_path,
        "expectedBundleId": config.expected_bundle_id,
    }
    if sys.platform != "darwin":
        return {**base, "status": "skipped", "reason": "not_macos"}

    codesign_path = shutil.which("codesign")
    if codesign_path is None:
        return {**base, "status": "skipped", "reason": "codesign_unavailable"}

    try:
        result = subprocess.run(
            [codesign_path, "-dv", "--verbose=4", app_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            **base,
            "checked": True,
            "status": "failed",
            "reason": "codesign_failed",
            "error": str(exc),
        }

    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    identifier = _parse_codesign_value(output, "Identifier")
    info_plist_bound = "Info.plist entries=" in output and (
        "Info.plist=not bound" not in output
    )
    sealed_resources = "Sealed Resources version=" in output
    identifier_matches_expected = identifier == config.expected_bundle_id
    status = (
        "ok"
        if result.returncode == 0
        and identifier_matches_expected
        and info_plist_bound
        and sealed_resources
        else "mismatch"
    )
    return {
        **base,
        "checked": True,
        "status": status,
        "returnCode": result.returncode,
        "identifier": identifier,
        "identifierMatchesExpected": identifier_matches_expected,
        "infoPlistBound": info_plist_bound,
        "sealedResources": sealed_resources,
        "signature": _parse_codesign_value(output, "Signature"),
        "teamIdentifier": _parse_codesign_value(output, "TeamIdentifier"),
    }


def _parse_codesign_value(output: str, key: str) -> str | None:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _open_permission_settings(recovery_actions: tuple[str, ...]) -> dict[str, Any]:
    urls: list[str] = []
    if "open_macos_privacy_accessibility" in recovery_actions:
        urls.append(MACOS_ACCESSIBILITY_SETTINGS_URL)
    if "open_macos_privacy_automation" in recovery_actions:
        urls.append(MACOS_AUTOMATION_SETTINGS_URL)
    if not urls:
        urls.append(MACOS_ACCESSIBILITY_SETTINGS_URL)

    opened: list[str] = []
    errors: list[dict[str, str]] = []
    for url in urls:
        try:
            _open_settings_url(url)
        except Exception as exc:  # noqa: BLE001 - manual recovery must be sanitized.
            errors.append({"url": url, "error": str(exc)})
        else:
            opened.append(url)
    return {
        "attempted": True,
        "opened": opened,
        "errors": errors,
    }


def _restart_helper_from_manifest(config: HelperPreflightConfig) -> dict[str, Any]:
    manifest_path = config.helper_manifest.expanduser()
    try:
        manifest = _read_helper_manifest(manifest_path)
    except HelperPreflightError as exc:
        return {
            "attempted": True,
            "terminated": False,
            "reason": "manifest_unavailable",
            "error": str(exc),
        }

    bundle_id = _optional_str(manifest, "bundleId")
    if bundle_id != config.expected_bundle_id:
        return {
            "attempted": True,
            "terminated": False,
            "reason": "bundle_id_mismatch",
            "bundleId": bundle_id,
            "expectedBundleId": config.expected_bundle_id,
        }

    pid = manifest.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return {
            "attempted": True,
            "terminated": False,
            "reason": "manifest_pid_unavailable",
            "bundleId": bundle_id,
        }

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {
            "attempted": True,
            "terminated": False,
            "reason": "process_not_found",
            "pid": pid,
            "bundleId": bundle_id,
        }
    except PermissionError as exc:
        return {
            "attempted": True,
            "terminated": False,
            "reason": "permission_denied",
            "pid": pid,
            "bundleId": bundle_id,
            "error": str(exc),
        }
    except OSError as exc:
        return {
            "attempted": True,
            "terminated": False,
            "reason": "termination_failed",
            "pid": pid,
            "bundleId": bundle_id,
            "error": str(exc),
        }

    exited = _wait_for_pid_exit(
        pid,
        timeout_seconds=config.helper_restart_wait_seconds,
    )
    return {
        "attempted": True,
        "terminated": True,
        "reason": "sigterm_sent",
        "pid": pid,
        "bundleId": bundle_id,
        "waitedForExit": exited,
    }


def _wait_for_pid_exit(
    pid: int,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float = 0.1,
) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        if time.monotonic() >= deadline:
            return False
        time.sleep(max(0.05, poll_interval_seconds))


def _open_settings_url(
    url: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    runner(
        ["/usr/bin/open", url],
        check=True,
        capture_output=True,
        text=True,
    )


def _parse_args() -> HelperPreflightConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--helper-manifest",
        type=Path,
        default=DEFAULT_HELPER_MANIFEST_PATH,
        help="Plato Computer Use Helper manifest path.",
    )
    parser.add_argument(
        "--helper-app-path",
        type=Path,
        default=DEFAULT_HELPER_APP_PATH,
        help="Stable Plato Computer Use Helper.app path for auto-launch.",
    )
    parser.add_argument(
        "--no-helper-auto-launch",
        action="store_true",
        help="Do not launch the helper app when the manifest is missing/stale.",
    )
    parser.add_argument(
        "--helper-launch-timeout-seconds",
        type=float,
        default=90.0,
        help="Maximum time to wait for helper manifest publication.",
    )
    parser.add_argument(
        "--helper-launch-poll-seconds",
        type=float,
        default=0.2,
        help="Poll interval while waiting for helper manifest publication.",
    )
    parser.add_argument(
        "--allowed-apps",
        default="WeChat,TextEdit",
        help="Comma-separated helper allowlist for preflight policy.",
    )
    parser.add_argument(
        "--check-wechat-app",
        action="store_true",
        help=(
            "Also call helper WeChat window readiness. This may open or focus "
            "WeChat, but it does not send a message."
        ),
    )
    parser.add_argument(
        "--open-permission-settings",
        action="store_true",
        help=(
            "When preflight is not ready, open the relevant macOS Privacy & "
            "Security panes. This is best-effort and never sends a message."
        ),
    )
    parser.add_argument(
        "--restart-helper",
        action="store_true",
        help=(
            "Before preflight, send SIGTERM to the helper PID recorded in the "
            "manifest, but only when the manifest bundle id matches the expected "
            "helper bundle id. The helper backend may then auto-launch the stable "
            "helper app and refresh the manifest."
        ),
    )
    parser.add_argument(
        "--helper-restart-wait-seconds",
        type=float,
        default=5.0,
        help="Maximum time to wait for the old helper PID to exit after SIGTERM.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--evidence-output", type=Path)
    args = parser.parse_args()
    return HelperPreflightConfig(
        helper_manifest=args.helper_manifest,
        helper_app_path=args.helper_app_path,
        helper_auto_launch=not args.no_helper_auto_launch,
        helper_launch_timeout_seconds=args.helper_launch_timeout_seconds,
        helper_launch_poll_interval_seconds=args.helper_launch_poll_seconds,
        allowed_apps=_parse_allowed_apps(args.allowed_apps),
        timeout_seconds=args.timeout_seconds,
        check_wechat_app=args.check_wechat_app,
        open_permission_settings=args.open_permission_settings,
        restart_helper=args.restart_helper,
        helper_restart_wait_seconds=args.helper_restart_wait_seconds,
        evidence_output=args.evidence_output,
    )


def _parse_allowed_apps(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_str(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) else None


def _optional_bool(mapping: dict[str, Any], key: str) -> bool | None:
    value = mapping.get(key)
    return value if isinstance(value, bool) else None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, list | tuple):
        return tuple(item for item in value if isinstance(item, str))
    return ()


if __name__ == "__main__":
    sys.exit(main())
