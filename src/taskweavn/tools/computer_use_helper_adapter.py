"""Adapter from Plato's computer-use contract to Plato Computer Use Helper.

The helper process is the stable macOS permission subject. This backend keeps
Plato on the product/control-plane side of the boundary and forwards bounded
computer-use operations over a local helper API.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from taskweavn.tools.computer_use import ComputerUseBackend
from taskweavn.types.computer_use import (
    ComputerUseAction,
    ComputerUseObservation,
    ComputerUseOperation,
    ComputerUseStatus,
)

HelperTransport = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]
HelperAppLauncher = Callable[[Path], None]


class ComputerUseHelperClientProtocol(Protocol):
    """Subset of the helper API consumed by Plato."""

    def readiness(self) -> Mapping[str, Any]: ...

    def execute(self, action: ComputerUseAction) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ComputerUseHelperBackendConfig:
    """Connection and policy options for the helper-backed computer-use runtime."""

    endpoint: str | None = None
    token: str | None = None
    endpoint_manifest_path: Path | None = None
    helper_app_path: Path | None = None
    helper_auto_launch: bool = False
    helper_launch_timeout_seconds: float = 10.0
    helper_launch_poll_interval_seconds: float = 0.2
    helper_app_launcher: HelperAppLauncher | None = None
    expected_bundle_id: str | None = None
    expected_api_version: str | None = "plato.computer_use_helper.v1"
    allowed_apps: tuple[str, ...] = ()
    allow_coordinate_click: bool = False
    allow_screenshot: bool = False
    timeout_seconds: float = 10.0

    @classmethod
    def from_environment(
        cls,
        *,
        allowed_apps: tuple[str, ...] = (),
        allow_coordinate_click: bool = False,
        allow_screenshot: bool = False,
    ) -> ComputerUseHelperBackendConfig:
        """Build config from the current process environment."""

        manifest = os.environ.get("PLATO_COMPUTER_USE_HELPER_MANIFEST")
        helper_app_path = os.environ.get("PLATO_COMPUTER_USE_HELPER_APP_PATH")
        return cls(
            endpoint=os.environ.get("PLATO_COMPUTER_USE_HELPER_ENDPOINT"),
            token=os.environ.get("PLATO_COMPUTER_USE_HELPER_TOKEN"),
            endpoint_manifest_path=Path(manifest).expanduser() if manifest else None,
            helper_app_path=(
                Path(helper_app_path).expanduser() if helper_app_path else None
            ),
            helper_auto_launch=_env_bool(
                "PLATO_COMPUTER_USE_HELPER_AUTO_LAUNCH",
                default=False,
            ),
            expected_bundle_id=os.environ.get(
                "PLATO_COMPUTER_USE_HELPER_EXPECTED_BUNDLE_ID"
            ),
            expected_api_version=os.environ.get(
                "PLATO_COMPUTER_USE_HELPER_EXPECTED_API_VERSION",
                "plato.computer_use_helper.v1",
            ),
            allowed_apps=allowed_apps,
            allow_coordinate_click=allow_coordinate_click,
            allow_screenshot=allow_screenshot,
        )


class ComputerUseHelperBackend(ComputerUseBackend):
    """Computer-use backend that delegates operations to a local helper app."""

    def __init__(
        self,
        *,
        client: ComputerUseHelperClientProtocol | None = None,
        config: ComputerUseHelperBackendConfig | None = None,
    ) -> None:
        self._config = config or ComputerUseHelperBackendConfig.from_environment()
        self._setup_error: str | None = None
        self._setup_failure_kind = "helper_not_available"
        self._client = client or self._load_client()

    def _load_client(self) -> ComputerUseHelperClientProtocol | None:
        endpoint = self._config.endpoint
        token = self._config.token
        if self._config.endpoint_manifest_path is not None:
            manifest = self._read_manifest_or_launch_helper()
            if manifest is None:
                return None
            manifest_client = self._client_from_manifest(
                manifest,
                endpoint_override=endpoint,
                token_override=token,
            )
            if manifest_client is None:
                return None
            return manifest_client
        if not endpoint:
            self._setup_error = (
                "Plato Computer Use Helper endpoint is not configured. "
                "Set PLATO_COMPUTER_USE_HELPER_MANIFEST or "
                "PLATO_COMPUTER_USE_HELPER_ENDPOINT."
            )
            return None
        return self._build_client(endpoint=endpoint, token=token)

    def _client_from_manifest(
        self,
        manifest: Mapping[str, Any],
        *,
        endpoint_override: str | None = None,
        token_override: str | None = None,
    ) -> ComputerUseHelperClientProtocol | None:
        manifest_error = _helper_identity_error(
            manifest,
            expected_bundle_id=self._config.expected_bundle_id,
            expected_api_version=self._config.expected_api_version,
        )
        if manifest_error is not None:
            self._setup_error = manifest_error.message
            self._setup_failure_kind = manifest_error.failure_kind
            return None
        endpoint = endpoint_override or _string(manifest.get("endpoint"))
        token = token_override or _string(manifest.get("token"))
        token_ref = _string(manifest.get("tokenRef")) or _string(
            manifest.get("token_ref")
        )
        if token is None and token_ref:
            try:
                token = Path(token_ref).expanduser().read_text(encoding="utf-8").strip()
            except OSError as exc:
                self._setup_error = f"helper token unavailable: {exc}"
                return None
        if not endpoint:
            self._setup_error = "helper manifest does not include an endpoint."
            return None
        return self._build_client(endpoint=endpoint, token=token)

    def _build_client(
        self,
        *,
        endpoint: str,
        token: str | None,
    ) -> ComputerUseHelperClientProtocol:
        return ComputerUseHelperHttpClient(
            endpoint=endpoint,
            token=token,
            allowed_apps=self._config.allowed_apps,
            allow_coordinate_click=self._config.allow_coordinate_click,
            allow_screenshot=self._config.allow_screenshot,
            timeout_seconds=self._config.timeout_seconds,
        )

    def _relaunch_helper_and_reload_client(
        self,
        *,
        initial_error: Exception,
    ) -> ComputerUseHelperClientProtocol | None:
        if (
            not self._config.helper_auto_launch
            or self._config.endpoint_manifest_path is None
            or self._config.helper_app_path is None
        ):
            return None
        manifest = self._launch_helper_and_read_manifest(
            manifest_path=self._config.endpoint_manifest_path,
            initial_error=initial_error,
            require_refreshed_manifest=True,
        )
        if manifest is None:
            return None
        client = self._client_from_manifest(
            manifest,
            endpoint_override=self._config.endpoint,
            token_override=self._config.token,
        )
        if client is not None:
            self._client = client
        return client

    def _read_manifest_or_launch_helper(self) -> dict[str, Any] | None:
        assert self._config.endpoint_manifest_path is not None
        manifest_path = self._config.endpoint_manifest_path
        try:
            return _read_manifest(manifest_path)
        except OSError as exc:
            initial_error: Exception = exc
            self._setup_error = f"helper manifest unavailable: {exc}"
        except ValueError as exc:
            initial_error = exc
            self._setup_error = str(exc)
        if not self._config.helper_auto_launch:
            return None
        if self._config.helper_app_path is None:
            self._setup_error = (
                f"{self._setup_error}; helper auto-launch is enabled but "
                "PLATO_COMPUTER_USE_HELPER_APP_PATH is not configured."
            )
            return None
        return self._launch_helper_and_read_manifest(
            manifest_path=manifest_path,
            initial_error=initial_error,
            require_refreshed_manifest=False,
        )

    def _launch_helper_and_read_manifest(
        self,
        *,
        manifest_path: Path,
        initial_error: Exception,
        require_refreshed_manifest: bool,
    ) -> dict[str, Any] | None:
        assert self._config.helper_app_path is not None
        app_path = self._config.helper_app_path.expanduser()
        if not app_path.exists():
            self._setup_failure_kind = "helper_not_installed"
            self._setup_error = f"helper app not found: {app_path}"
            return None
        previous_manifest: dict[str, Any] | None = None
        if require_refreshed_manifest:
            try:
                previous_manifest = _read_manifest(manifest_path)
            except (OSError, ValueError):
                previous_manifest = None
        launcher = self._config.helper_app_launcher or _default_helper_app_launcher
        try:
            launcher(app_path)
        except Exception as exc:  # noqa: BLE001 - helper launch errors are sanitized.
            self._setup_failure_kind = "helper_not_running"
            self._setup_error = f"helper app launch failed: {exc}"
            return None

        deadline = time.monotonic() + max(
            0.0,
            self._config.helper_launch_timeout_seconds,
        )
        last_error = initial_error
        while True:
            try:
                manifest = _read_manifest(manifest_path)
                if (
                    not require_refreshed_manifest
                    or previous_manifest is None
                    or manifest != previous_manifest
                ):
                    return manifest
                last_error = RuntimeError(
                    "helper app has not refreshed stale manifest yet"
                )
            except (OSError, ValueError) as exc:
                last_error = exc
            if time.monotonic() >= deadline:
                self._setup_failure_kind = "helper_not_running"
                self._setup_error = (
                    "helper app launched but did not publish manifest "
                    f"{manifest_path}: {last_error}"
                )
                return None
            time.sleep(max(0.05, self._config.helper_launch_poll_interval_seconds))

    def readiness(self, *, action_id: str | None = None) -> ComputerUseObservation:
        if self._client is None:
            return _helper_unavailable(
                action_id=action_id,
                setup_error=self._setup_error,
                failure_kind=self._setup_failure_kind,
            )
        try:
            response = self._client.readiness()
        except Exception as exc:  # noqa: BLE001 - helper boundary must sanitize.
            refreshed_client = self._relaunch_helper_and_reload_client(
                initial_error=exc,
            )
            if refreshed_client is not None:
                try:
                    response = refreshed_client.readiness()
                except Exception as retry_exc:  # noqa: BLE001
                    return ComputerUseObservation(
                        action_id=action_id,
                        success=False,
                        operation="readiness",
                        status="failed",
                        summary=(
                            "Plato Computer Use Helper readiness failed after "
                            f"relaunch: {type(retry_exc).__name__}"
                        ),
                        metadata={
                            "provider": "helper",
                            "failure_kind": "helper_not_running",
                            "error": str(retry_exc),
                            "previous_error": str(exc),
                        },
                    )
                return _helper_response_to_observation(
                    operation="readiness",
                    action_id=action_id,
                    response=response,
                    expected_bundle_id=self._config.expected_bundle_id,
                    expected_api_version=self._config.expected_api_version,
                )
            return ComputerUseObservation(
                action_id=action_id,
                success=False,
                operation="readiness",
                status="failed",
                summary=f"Plato Computer Use Helper readiness failed: {type(exc).__name__}",
                metadata={
                    "provider": "helper",
                    "failure_kind": "helper_not_running",
                    "error": str(exc),
                },
            )
        return _helper_response_to_observation(
            operation="readiness",
            action_id=action_id,
            response=response,
            expected_bundle_id=self._config.expected_bundle_id,
            expected_api_version=self._config.expected_api_version,
        )

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        if action.operation == "readiness":
            return self.readiness(action_id=action.event_id)
        if self._client is None:
            return _helper_unavailable(
                action_id=action.event_id,
                operation=action.operation,
                setup_error=self._setup_error,
                failure_kind=self._setup_failure_kind,
            )
        try:
            response = self._client.execute(action)
        except Exception as exc:  # noqa: BLE001 - helper boundary must sanitize.
            refreshed_client = self._relaunch_helper_and_reload_client(
                initial_error=exc,
            )
            if refreshed_client is not None:
                try:
                    response = refreshed_client.execute(action)
                except Exception as retry_exc:  # noqa: BLE001
                    return ComputerUseObservation(
                        action_id=action.event_id,
                        success=False,
                        operation=action.operation,
                        status="failed",
                        summary=(
                            "Plato Computer Use Helper operation failed after "
                            f"relaunch: {type(retry_exc).__name__}"
                        ),
                        metadata={
                            "provider": "helper",
                            "failure_kind": "helper_not_running",
                            "error": str(retry_exc),
                            "previous_error": str(exc),
                        },
                    )
                return _helper_response_to_observation(
                    operation=action.operation,
                    action_id=action.event_id,
                    response=response,
                    expected_bundle_id=self._config.expected_bundle_id,
                    expected_api_version=self._config.expected_api_version,
                )
            return ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="failed",
                summary=f"Plato Computer Use Helper operation failed: {type(exc).__name__}",
                metadata={
                    "provider": "helper",
                    "failure_kind": "helper_not_running",
                    "error": str(exc),
                },
            )
        return _helper_response_to_observation(
            operation=action.operation,
            action_id=action.event_id,
            response=response,
            expected_bundle_id=self._config.expected_bundle_id,
            expected_api_version=self._config.expected_api_version,
        )

    @property
    def helper_client(self) -> ComputerUseHelperClientProtocol | None:
        """Return the loaded helper client for higher-level helper APIs."""

        return self._client


class ComputerUseHelperHttpClient:
    """HTTP client for the local Plato Computer Use Helper API."""

    def __init__(
        self,
        *,
        endpoint: str,
        token: str | None,
        allowed_apps: tuple[str, ...],
        allow_coordinate_click: bool,
        allow_screenshot: bool,
        timeout_seconds: float = 10.0,
        transport: HelperTransport | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/") + "/"
        self._token = token
        self._allowed_apps = allowed_apps
        self._allow_coordinate_click = allow_coordinate_click
        self._allow_screenshot = allow_screenshot
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def readiness(self) -> Mapping[str, Any]:
        return self._request("GET", "/v1/readiness", None)

    def execute(self, action: ComputerUseAction) -> Mapping[str, Any]:
        return self._request("POST", _operation_path(action.operation), self._payload(action))

    def wechat_draft_message(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        caller: Mapping[str, str],
        contact_display_name: str,
        message_text: str,
        contact_alias: str | None = None,
        operator_note: str | None = None,
        external_ref: Mapping[str, str] | None = None,
        app_identity: str | None = None,
    ) -> Mapping[str, Any]:
        """Ask the helper to resolve a WeChat contact and insert a draft only."""

        payload: dict[str, Any] = {
            "requestId": request_id,
            "idempotencyKey": idempotency_key,
            "caller": dict(caller),
            "operation": "wechat.draft_message",
            "input": {
                "contactDisplayName": contact_display_name,
                "messageText": message_text,
                "contactAlias": contact_alias,
                "operatorNote": operator_note,
                "externalRef": dict(external_ref or {}),
                "appIdentity": app_identity,
            },
            "policy": self._policy(requires_confirmation_before_send=True),
        }
        return self._request("POST", "/v1/apps/wechat/draft-message", payload)

    def wechat_send_confirmed(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        caller: Mapping[str, str],
        action_fingerprint_payload: Mapping[str, Any],
        action_fingerprint: str,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str,
    ) -> Mapping[str, Any]:
        """Ask the helper to submit an already drafted WeChat message."""

        payload: dict[str, Any] = {
            "requestId": request_id,
            "idempotencyKey": idempotency_key,
            "caller": dict(caller),
            "operation": "wechat.send_confirmed",
            "input": {
                "actionFingerprintPayload": dict(action_fingerprint_payload),
                "contactSummary": contact_summary,
                "messagePreview": message_preview,
                "confirmationProof": {
                    "confirmationId": confirmation_id,
                    "decision": "confirm",
                    "source": "user",
                    "actionFingerprint": action_fingerprint,
                },
            },
            "policy": self._policy(requires_confirmation_before_send=False),
        }
        return self._request("POST", "/v1/apps/wechat/send-confirmed", payload)

    def _payload(self, action: ComputerUseAction) -> dict[str, Any]:
        caller = {
            key: action.metadata[key]
            for key in ("workspaceId", "sessionId", "taskExecutionId", "taskId")
            if isinstance(action.metadata.get(key), str)
        }
        return {
            "requestId": action.event_id,
            "idempotencyKey": _string(action.metadata.get("idempotencyKey"))
            or _string(action.metadata.get("idempotency_key"))
            or action.event_id,
            "caller": caller,
            "operation": action.operation,
            "input": {
                "instruction": action.instruction,
                "target": action.target,
                "text": action.text,
                "keys": list(action.keys),
                "x": action.x,
                "y": action.y,
                "timeoutSeconds": action.timeout_seconds,
                "metadata": action.metadata,
            },
            "policy": {
                **self._policy(requires_confirmation_before_send=True),
            },
        }

    def _policy(self, *, requires_confirmation_before_send: bool) -> dict[str, Any]:
        return {
            "allowedApps": list(self._allowed_apps),
            "allowCoordinateClick": self._allow_coordinate_click,
            "allowScreenshot": self._allow_screenshot,
            "requiresConfirmationBeforeSend": requires_confirmation_before_send,
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport(method, path, payload)
        url = urljoin(self._endpoint, path.lstrip("/"))
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"helper returned HTTP {exc.code}: {_bounded(detail)}") from exc
        except URLError as exc:
            raise RuntimeError(f"helper connection failed: {exc.reason}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("helper returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("helper response must be a JSON object")
        return parsed


def _read_manifest(path: Path) -> dict[str, Any]:
    raw = path.expanduser().read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("helper manifest must be a JSON object")
    return parsed


def _default_helper_app_launcher(app_path: Path) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("helper app auto-launch is only supported on macOS")
    completed = subprocess.run(  # noqa: S603 - fixed executable and args.
        ["/usr/bin/open", "-gj", str(app_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"open returned {completed.returncode}: {_bounded(detail or 'no output')}"
        )


def _operation_path(operation: ComputerUseOperation) -> str:
    return {
        "observe": "/v1/operations/observe",
        "open_app": "/v1/operations/open-app",
        "click": "/v1/operations/click",
        "type_text": "/v1/operations/type-text",
        "press_key": "/v1/operations/press-key",
        "wait": "/v1/operations/wait",
        "readiness": "/v1/readiness",
    }[operation]


def _helper_unavailable(
    *,
    action_id: str | None,
    setup_error: str | None,
    failure_kind: str = "helper_not_available",
    operation: ComputerUseOperation = "readiness",
) -> ComputerUseObservation:
    return ComputerUseObservation(
        action_id=action_id,
        success=False,
        operation=operation,
        status="not_available",
        summary="Plato Computer Use Helper is not available.",
        metadata={
            "provider": "helper",
            "failure_kind": failure_kind,
            "setup_hint": setup_error or "Configure and start Plato Computer Use Helper.",
        },
    )


@dataclass(frozen=True)
class _HelperIdentityError:
    message: str
    failure_kind: str
    helper_status: str


def _helper_response_to_observation(
    *,
    operation: ComputerUseOperation,
    action_id: str | None,
    response: Mapping[str, Any],
    expected_bundle_id: str | None,
    expected_api_version: str | None,
) -> ComputerUseObservation:
    identity_error = _helper_identity_error(
        response.get("helper") if isinstance(response.get("helper"), dict) else response,
        expected_bundle_id=expected_bundle_id,
        expected_api_version=expected_api_version,
    )
    if identity_error is not None:
        return ComputerUseObservation(
            action_id=action_id,
            success=False,
            operation=operation,
            status="not_available",
            summary="Plato Computer Use Helper identity check failed.",
            metadata={
                "provider": "helper",
                "helper_status": identity_error.helper_status,
                "failure_kind": identity_error.failure_kind,
                "setup_hint": identity_error.message,
                "helper": _helper_identity_metadata(response),
            },
        )
    helper_status = _string(response.get("status")) or "failed"
    status = _map_helper_status(helper_status)
    metadata = _metadata_from_response(response)
    metadata["helper_status"] = helper_status
    metadata["provider"] = "helper"
    return ComputerUseObservation(
        action_id=action_id,
        success=status == "ok",
        operation=operation,
        status=status,
        summary=_summary_from_response(response, helper_status),
        text_extract=_string(response.get("textExtract"))
        or _string(response.get("text_extract")),
        metadata=metadata,
    )


def _metadata_from_response(response: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    raw_metadata = response.get("metadata")
    if isinstance(raw_metadata, dict):
        metadata.update(raw_metadata)
    for source_key, target_key in (
        ("snapshotId", "snapshot_id"),
        ("snapshot_id", "snapshot_id"),
        ("failureKind", "failure_kind"),
        ("failure_kind", "failure_kind"),
        ("phase", "phase"),
        ("risk", "risk"),
        ("setupHint", "setup_hint"),
        ("setup_hint", "setup_hint"),
        ("recoveryActions", "recovery_actions"),
        ("recovery_actions", "recovery_actions"),
        ("evidence", "evidence"),
        ("diagnostics", "diagnostics"),
    ):
        value = response.get(source_key)
        if value is not None:
            metadata[target_key] = value
    helper = response.get("helper")
    if isinstance(helper, dict):
        metadata["helper"] = _helper_identity_metadata(helper)
    return metadata


def _map_helper_status(status: str) -> ComputerUseStatus:
    if status in {"ready", "ok", "sent"}:
        return "ok"
    if status == "blocked":
        return "blocked"
    if status in {"needs_user", "app_needs_user"}:
        return "needs_user"
    if status in {
        "not_available",
        "helper_not_installed",
        "helper_not_running",
        "helper_untrusted",
        "helper_version_mismatch",
        "missing_accessibility",
        "missing_screen_recording",
        "automation_not_authorized",
        "app_not_allowed",
        "app_not_installed",
    }:
        return "not_available"
    return "failed"


def _summary_from_response(response: Mapping[str, Any], helper_status: str) -> str:
    summary = _string(response.get("summary"))
    if summary:
        return summary
    if helper_status == "ready":
        return "Plato Computer Use Helper is ready."
    return f"Plato Computer Use Helper returned {helper_status}."


def _helper_identity_error(
    raw: object,
    *,
    expected_bundle_id: str | None,
    expected_api_version: str | None,
) -> _HelperIdentityError | None:
    if expected_bundle_id is None and expected_api_version is None:
        return None
    if not isinstance(raw, Mapping):
        return _HelperIdentityError(
            message="helper identity metadata is missing",
            failure_kind="helper_untrusted",
            helper_status="helper_untrusted",
        )
    bundle_id = _string(raw.get("bundleId")) or _string(raw.get("bundle_id"))
    api_version = _string(raw.get("apiVersion")) or _string(raw.get("api_version"))
    if expected_bundle_id is not None and bundle_id != expected_bundle_id:
        return _HelperIdentityError(
            message=(
                "helper bundle id mismatch: "
                f"expected {expected_bundle_id}, got {bundle_id or 'unknown'}"
            ),
            failure_kind="helper_untrusted",
            helper_status="helper_untrusted",
        )
    if expected_api_version is not None and api_version != expected_api_version:
        return _HelperIdentityError(
            message=(
                "helper API version mismatch: "
                f"expected {expected_api_version}, got {api_version or 'unknown'}"
            ),
            failure_kind="helper_version_mismatch",
            helper_status="helper_version_mismatch",
        )
    return None


def _helper_identity_metadata(raw: Mapping[str, Any]) -> dict[str, str]:
    helper = raw.get("helper")
    source = helper if isinstance(helper, dict) else raw
    metadata: dict[str, str] = {}
    for source_key, target_key in (
        ("bundleId", "bundleId"),
        ("bundle_id", "bundleId"),
        ("version", "version"),
        ("apiVersion", "apiVersion"),
        ("api_version", "apiVersion"),
        ("path", "path"),
        ("signingMode", "signingMode"),
        ("signing_mode", "signingMode"),
    ):
        value = _string(source.get(source_key))
        if value is not None:
            metadata[target_key] = value
    return metadata


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _bounded(value: str, *, limit: int = 1_000) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}..."


def _env_bool(name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


__all__ = [
    "ComputerUseHelperBackend",
    "ComputerUseHelperBackendConfig",
    "ComputerUseHelperClientProtocol",
    "ComputerUseHelperHttpClient",
]
