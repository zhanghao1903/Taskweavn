"""Adapter from Plato's computer-use contract to Plato Computer Use Helper.

The helper process is the stable macOS permission subject. This backend keeps
Plato on the product/control-plane side of the boundary and forwards bounded
computer-use operations over a local helper API.
"""

from __future__ import annotations

import json
import os
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
        return cls(
            endpoint=os.environ.get("PLATO_COMPUTER_USE_HELPER_ENDPOINT"),
            token=os.environ.get("PLATO_COMPUTER_USE_HELPER_TOKEN"),
            endpoint_manifest_path=Path(manifest).expanduser() if manifest else None,
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
        self._client = client or self._load_client()

    def _load_client(self) -> ComputerUseHelperClientProtocol | None:
        endpoint = self._config.endpoint
        token = self._config.token
        if self._config.endpoint_manifest_path is not None:
            try:
                manifest = _read_manifest(self._config.endpoint_manifest_path)
            except OSError as exc:
                self._setup_error = f"helper manifest unavailable: {exc}"
                return None
            except ValueError as exc:
                self._setup_error = str(exc)
                return None
            endpoint = endpoint or _string(manifest.get("endpoint"))
            token = token or _string(manifest.get("token"))
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
            self._setup_error = (
                "Plato Computer Use Helper endpoint is not configured. "
                "Set PLATO_COMPUTER_USE_HELPER_MANIFEST or "
                "PLATO_COMPUTER_USE_HELPER_ENDPOINT."
            )
            return None
        return ComputerUseHelperHttpClient(
            endpoint=endpoint,
            token=token,
            allowed_apps=self._config.allowed_apps,
            allow_coordinate_click=self._config.allow_coordinate_click,
            allow_screenshot=self._config.allow_screenshot,
            timeout_seconds=self._config.timeout_seconds,
        )

    def readiness(self, *, action_id: str | None = None) -> ComputerUseObservation:
        if self._client is None:
            return _helper_unavailable(action_id=action_id, setup_error=self._setup_error)
        try:
            response = self._client.readiness()
        except Exception as exc:  # noqa: BLE001 - helper boundary must sanitize.
            return ComputerUseObservation(
                action_id=action_id,
                success=False,
                operation="readiness",
                status="failed",
                summary=f"Plato Computer Use Helper readiness failed: {type(exc).__name__}",
                metadata={"error": str(exc)},
            )
        return _helper_response_to_observation(
            operation="readiness",
            action_id=action_id,
            response=response,
        )

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        if action.operation == "readiness":
            return self.readiness(action_id=action.event_id)
        if self._client is None:
            return _helper_unavailable(
                action_id=action.event_id,
                operation=action.operation,
                setup_error=self._setup_error,
            )
        try:
            response = self._client.execute(action)
        except Exception as exc:  # noqa: BLE001 - helper boundary must sanitize.
            return ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="failed",
                summary=f"Plato Computer Use Helper operation failed: {type(exc).__name__}",
                metadata={"error": str(exc)},
            )
        return _helper_response_to_observation(
            operation=action.operation,
            action_id=action.event_id,
            response=response,
        )


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
                "allowedApps": list(self._allowed_apps),
                "allowCoordinateClick": self._allow_coordinate_click,
                "allowScreenshot": self._allow_screenshot,
                "requiresConfirmationBeforeSend": True,
            },
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
            "failure_kind": "helper_not_available",
            "setup_hint": setup_error or "Configure and start Plato Computer Use Helper.",
        },
    )


def _helper_response_to_observation(
    *,
    operation: ComputerUseOperation,
    action_id: str | None,
    response: Mapping[str, Any],
) -> ComputerUseObservation:
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
        ("evidence", "evidence"),
        ("diagnostics", "diagnostics"),
    ):
        value = response.get(source_key)
        if value is not None:
            metadata[target_key] = value
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


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _bounded(value: str, *, limit: int = 1_000) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}..."


__all__ = [
    "ComputerUseHelperBackend",
    "ComputerUseHelperBackendConfig",
    "ComputerUseHelperClientProtocol",
    "ComputerUseHelperHttpClient",
]
