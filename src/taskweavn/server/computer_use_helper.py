"""Prototype HTTP transport for Plato Computer Use Helper.

This module implements the repo-local helper server contract before a real
macOS ``.app`` wrapper exists. It deliberately depends on the generic
``ComputerUseBackend`` seam so tests can use fake/scripted backends and CI does
not need macOS UI permissions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from taskweavn.server.sidecar import LocalSidecarConfig, LocalSidecarServer
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.tools import ComputerUseBackend, DisabledComputerUseBackend
from taskweavn.types import ComputerUseAction, ComputerUseObservation
from taskweavn.types.computer_use import ComputerUseOperation

_JSON_HEADERS = {"content-type": "application/json"}
_OPERATION_BY_PATH: dict[tuple[str, ...], ComputerUseOperation] = {
    ("v1", "operations", "observe"): "observe",
    ("v1", "operations", "open-app"): "open_app",
    ("v1", "operations", "click"): "click",
    ("v1", "operations", "type-text"): "type_text",
    ("v1", "operations", "press-key"): "press_key",
    ("v1", "operations", "wait"): "wait",
}


@dataclass(frozen=True)
class ComputerUseHelperManifest:
    """Connection manifest written by a running helper process."""

    endpoint: str
    token_ref: str | None = None
    pid: int | None = None
    bundle_id: str = "com.taskweavn.plato.computer-use-helper.dev"
    version: str = "0.1.0"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "endpoint": self.endpoint,
            "bundleId": self.bundle_id,
            "version": self.version,
        }
        if self.token_ref is not None:
            data["tokenRef"] = self.token_ref
        if self.pid is not None:
            data["pid"] = self.pid
        return data


@dataclass(frozen=True)
class ComputerUseHelperInfo:
    """Static helper identity returned by ``/v1/info`` and readiness."""

    bundle_id: str = "com.taskweavn.plato.computer-use-helper.dev"
    version: str = "0.1.0"
    api_version: str = "plato.computer_use_helper.v1"
    path: str | None = None
    signing_mode: str = "development"


@dataclass(frozen=True)
class ComputerUseHelperTransportConfig:
    """Runtime config for the helper HTTP transport."""

    auth_token: str | None = None
    info: ComputerUseHelperInfo = ComputerUseHelperInfo()


class ComputerUseHelperTransport:
    """Framework-neutral route handler for the helper local API."""

    def __init__(
        self,
        *,
        backend: ComputerUseBackend | None = None,
        config: ComputerUseHelperTransportConfig | None = None,
    ) -> None:
        self._backend = backend or DisabledComputerUseBackend(
            "computer-use helper backend is not configured"
        )
        self._config = config or ComputerUseHelperTransportConfig()

    def handle(self, request: HttpApiRequest) -> HttpApiResponse:
        auth_response = self._authorize(request)
        if auth_response is not None:
            return auth_response

        parts = _path_parts(request.path)
        if request.method == "GET" and parts == ():
            return _json_response(
                {
                    "ok": True,
                    "name": "Plato Computer Use Helper",
                    "healthUrl": "/healthz",
                    "readinessUrl": "/v1/readiness",
                }
            )
        if request.method == "GET" and parts == ("healthz",):
            return _json_response(
                {
                    "ok": True,
                    "name": "Plato Computer Use Helper",
                    "version": self._config.info.version,
                }
            )
        if request.method == "GET" and parts == ("v1", "info"):
            return _json_response(_info_body(self._config.info))
        if request.method == "GET" and parts == ("v1", "readiness"):
            return _json_response(self._readiness_body(request_id=None))
        if request.method == "POST" and parts in _OPERATION_BY_PATH:
            return self._operation_response(_OPERATION_BY_PATH[parts], request.body)
        return _error_response(404, "not_found", f"helper route not found: {request.path}")

    def _authorize(self, request: HttpApiRequest) -> HttpApiResponse | None:
        token = self._config.auth_token
        if token is None:
            return None
        headers = {key.lower(): value for key, value in request.headers.items()}
        if headers.get("authorization") == f"Bearer {token}":
            return None
        return _error_response(401, "permission_denied", "invalid helper token")

    def _readiness_body(self, *, request_id: str | None) -> dict[str, Any]:
        observation = self._backend.execute(
            ComputerUseAction(
                operation="readiness",
                instruction="Check Plato Computer Use Helper readiness.",
            )
        )
        body = _observation_to_helper_body(observation, request_id=request_id)
        body["helper"] = _info_body(self._config.info)
        return body

    def _operation_response(
        self,
        operation: ComputerUseOperation,
        body: dict[str, Any] | None,
    ) -> HttpApiResponse:
        if body is None:
            return _error_response(400, "bad_request", "request body is required")
        try:
            action = _action_from_helper_body(operation, body)
        except ValueError as exc:
            return _error_response(400, "bad_request", str(exc))
        observation = self._backend.execute(action)
        return _json_response(
            _observation_to_helper_body(
                observation,
                request_id=_string(body.get("requestId")) or action.event_id,
            )
        )


def build_computer_use_helper_server(
    *,
    backend: ComputerUseBackend | None = None,
    helper_config: ComputerUseHelperTransportConfig | None = None,
    server_config: LocalSidecarConfig | None = None,
) -> LocalSidecarServer:
    """Build a loopback-only helper prototype server."""

    return LocalSidecarServer(
        ComputerUseHelperTransport(backend=backend, config=helper_config),
        config=server_config,
    )


def write_helper_manifest(path: Path, manifest: ComputerUseHelperManifest) -> None:
    """Write a helper endpoint manifest with owner-only permissions where possible."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Some filesystems ignore chmod. The caller still gets a valid manifest.
        return


def read_helper_manifest(path: Path) -> ComputerUseHelperManifest:
    """Read a helper endpoint manifest."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("helper manifest must be a JSON object")
    endpoint = _string(raw.get("endpoint"))
    if endpoint is None:
        raise ValueError("helper manifest requires endpoint")
    return ComputerUseHelperManifest(
        endpoint=endpoint,
        token_ref=_string(raw.get("tokenRef")) or _string(raw.get("token_ref")),
        pid=_int(raw.get("pid")),
        bundle_id=_string(raw.get("bundleId"))
        or _string(raw.get("bundle_id"))
        or "com.taskweavn.plato.computer-use-helper.dev",
        version=_string(raw.get("version")) or "0.1.0",
    )


def _action_from_helper_body(
    operation: ComputerUseOperation,
    body: dict[str, Any],
) -> ComputerUseAction:
    raw_input = body.get("input")
    if not isinstance(raw_input, dict):
        raise ValueError("request input must be a JSON object")
    metadata = raw_input.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    caller = body.get("caller")
    merged_metadata = dict(cast(dict[str, Any], metadata))
    if isinstance(caller, dict):
        for key, value in caller.items():
            if isinstance(key, str) and isinstance(value, str):
                merged_metadata.setdefault(key, value)
    idempotency_key = _string(body.get("idempotencyKey")) or _string(
        body.get("idempotency_key")
    )
    if idempotency_key:
        merged_metadata.setdefault("idempotencyKey", idempotency_key)
    action_kwargs: dict[str, Any] = {
        "operation": operation,
        "instruction": _string(raw_input.get("instruction")) or f"Run {operation}.",
        "target": _string(raw_input.get("target")),
        "text": _string(raw_input.get("text")),
        "keys": _string_tuple(raw_input.get("keys")),
        "x": _int(raw_input.get("x")),
        "y": _int(raw_input.get("y")),
        "timeout_seconds": _float(raw_input.get("timeoutSeconds"))
        or _float(raw_input.get("timeout_seconds"))
        or 5.0,
        "require_confirmation": bool(raw_input.get("requireConfirmation", False)),
        "metadata": merged_metadata,
    }
    request_id = _string(body.get("requestId"))
    if request_id is not None:
        action_kwargs["event_id"] = request_id
    return ComputerUseAction(**action_kwargs)


def _observation_to_helper_body(
    observation: ComputerUseObservation,
    *,
    request_id: str | None,
) -> dict[str, Any]:
    metadata = dict(observation.metadata)
    body: dict[str, Any] = {
        "requestId": request_id or observation.action_id,
        "operation": observation.operation,
        "status": _helper_status(observation),
        "success": observation.success,
        "summary": observation.summary,
        "metadata": metadata,
    }
    if observation.text_extract is not None:
        body["textExtract"] = observation.text_extract
    if observation.screenshot_ref is not None:
        body["screenshotRef"] = observation.screenshot_ref
    for metadata_key, body_key in (
        ("failure_kind", "failureKind"),
        ("phase", "phase"),
        ("risk", "risk"),
        ("evidence", "evidence"),
        ("diagnostics", "diagnostics"),
        ("snapshot_id", "snapshotId"),
    ):
        value = metadata.get(metadata_key)
        if value is not None:
            body[body_key] = value
    return body


def _helper_status(observation: ComputerUseObservation) -> str:
    if observation.operation == "readiness":
        readiness = observation.metadata.get("readiness")
        if isinstance(readiness, dict):
            status = _string(readiness.get("status"))
            if status:
                return status
    if observation.status == "ok":
        return "ok"
    if observation.status == "not_available":
        return _string(observation.metadata.get("failure_kind")) or "not_available"
    return observation.status


def _info_body(info: ComputerUseHelperInfo) -> dict[str, Any]:
    body: dict[str, Any] = {
        "bundleId": info.bundle_id,
        "version": info.version,
        "apiVersion": info.api_version,
        "signingMode": info.signing_mode,
    }
    if info.path is not None:
        body["path"] = info.path
    return body


def _path_parts(path: str) -> tuple[str, ...]:
    parsed = urlsplit(path)
    return tuple(part for part in parsed.path.split("/") if part)


def _json_response(body: dict[str, Any], *, status_code: int = 200) -> HttpApiResponse:
    return HttpApiResponse(status_code=status_code, headers=dict(_JSON_HEADERS), body=body)


def _error_response(status_code: int, code: str, message: str) -> HttpApiResponse:
    return _json_response(
        {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "details": {},
            },
        },
        status_code=status_code,
    )


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _float(value: Any) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


__all__ = [
    "ComputerUseHelperInfo",
    "ComputerUseHelperManifest",
    "ComputerUseHelperTransport",
    "ComputerUseHelperTransportConfig",
    "build_computer_use_helper_server",
    "read_helper_manifest",
    "write_helper_manifest",
]
