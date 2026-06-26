"""Prototype HTTP transport for Plato Computer Use Helper.

This module implements the repo-local helper server contract before a real
macOS ``.app`` wrapper exists. It deliberately depends on the generic
``ComputerUseBackend`` seam so tests can use fake/scripted backends and CI does
not need macOS UI permissions.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from os import getpid
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendActionFingerprint,
)
from taskweavn.integrations.wechat_desktop.models import (
    WeChatContactResolution,
    WeChatDraftState,
    WeChatOperationResult,
    WeChatReadiness,
    WeChatSendAttemptResult,
    WeChatSendTaskInput,
)
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
    api_version: str = "plato.computer_use_helper.v1"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "endpoint": self.endpoint,
            "bundleId": self.bundle_id,
            "version": self.version,
            "apiVersion": self.api_version,
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


@dataclass(frozen=True)
class ComputerUseHelperServerConfig:
    """Startup config for a local helper server process."""

    manifest_path: Path
    token_path: Path | None = None
    host: str = "127.0.0.1"
    port: int = 0
    auth_token: str | None = None
    info: ComputerUseHelperInfo = ComputerUseHelperInfo()


@dataclass
class ComputerUseHelperServerHandle:
    """Running helper server plus the manifest it published."""

    server: LocalSidecarServer
    manifest_path: Path
    token_path: Path
    manifest: ComputerUseHelperManifest
    auth_token: str

    @property
    def base_url(self) -> str:
        return self.server.base_url

    def start_in_thread(self) -> None:
        self.server.start_in_thread()

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self) -> ComputerUseHelperServerHandle:
        self.start_in_thread()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


class WeChatHelperAdapter(Protocol):
    """WeChat-specific app adapter hosted by the helper process."""

    def readiness(self) -> WeChatReadiness: ...

    def open_or_focus(self) -> WeChatOperationResult: ...

    def resolve_contact(
        self,
        task_input: WeChatSendTaskInput,
    ) -> WeChatContactResolution: ...

    def draft_message(
        self,
        resolution: WeChatContactResolution,
        message_text: str,
    ) -> WeChatDraftState: ...

    def send_after_confirmation(
        self,
        fingerprint: WeChatSendActionFingerprint,
        *,
        contact_summary: str,
        message_preview: str,
    ) -> WeChatSendAttemptResult: ...

    def window_readiness(self) -> WeChatOperationResult: ...


class ComputerUseHelperTransport:
    """Framework-neutral route handler for the helper local API."""

    def __init__(
        self,
        *,
        backend: ComputerUseBackend | None = None,
        wechat_adapter: WeChatHelperAdapter | None = None,
        config: ComputerUseHelperTransportConfig | None = None,
    ) -> None:
        self._backend = backend or DisabledComputerUseBackend(
            "computer-use helper backend is not configured"
        )
        self._wechat_adapter = wechat_adapter
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
        if request.method == "POST" and parts == (
            "v1",
            "apps",
            "wechat",
            "readiness",
        ):
            return self._wechat_app_readiness_response(request.body)
        if request.method == "POST" and parts == (
            "v1",
            "apps",
            "wechat",
            "draft-message",
        ):
            return self._wechat_draft_response(request.body)
        if request.method == "POST" and parts == (
            "v1",
            "apps",
            "wechat",
            "send-confirmed",
        ):
            return self._wechat_send_confirmed_response(request.body)
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

    def _wechat_app_readiness_response(
        self,
        body: dict[str, Any] | None,
    ) -> HttpApiResponse:
        if self._wechat_adapter is None:
            return _json_response(
                _wechat_not_available_body(
                    request_id=_request_id(body),
                    operation="wechat.readiness",
                    helper_info=self._config.info,
                )
            )
        readiness = self._wechat_adapter.readiness()
        if readiness.status != "ready":
            return _json_response(
                _wechat_readiness_body(
                    request_id=_request_id(body),
                    operation="wechat.readiness",
                    readiness=readiness,
                    helper_info=self._config.info,
                )
            )
        opened = self._wechat_adapter.open_or_focus()
        if opened.status != "ok":
            return _json_response(
                _wechat_operation_failure_body(
                    request_id=_request_id(body),
                    operation="wechat.readiness",
                    phase="open_app",
                    result=opened,
                    helper_info=self._config.info,
                )
            )
        window = self._wechat_adapter.window_readiness()
        if window.status != "ok":
            return _json_response(
                _wechat_operation_failure_body(
                    request_id=_request_id(body),
                    operation="wechat.readiness",
                    phase="window_readiness",
                    result=window,
                    helper_info=self._config.info,
                )
            )
        return _json_response(
            _wechat_app_readiness_body(
                request_id=_request_id(body),
                opened=opened,
                window=window,
                helper_info=self._config.info,
            )
        )

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
        response = _observation_to_helper_body(
            observation,
            request_id=_string(body.get("requestId")) or action.event_id,
        )
        response["helper"] = _info_body(self._config.info)
        return _json_response(response)

    def _wechat_draft_response(self, body: dict[str, Any] | None) -> HttpApiResponse:
        if self._wechat_adapter is None:
            return _json_response(
                _wechat_not_available_body(
                    request_id=_request_id(body),
                    operation="wechat.draft_message",
                    helper_info=self._config.info,
                )
            )
        if body is None:
            return _error_response(400, "bad_request", "request body is required")
        try:
            task_input = _wechat_task_input_from_body(body)
        except ValueError as exc:
            return _error_response(400, "bad_request", str(exc))

        readiness = self._wechat_adapter.readiness()
        if readiness.status != "ready":
            return _json_response(
                _wechat_readiness_body(
                    request_id=_request_id(body),
                    operation="wechat.draft_message",
                    readiness=readiness,
                    helper_info=self._config.info,
                )
            )
        opened = self._wechat_adapter.open_or_focus()
        if opened.status != "ok":
            return _json_response(
                _wechat_operation_failure_body(
                    request_id=_request_id(body),
                    operation="wechat.draft_message",
                    phase="open_app",
                    result=opened,
                    helper_info=self._config.info,
                )
            )
        resolution = self._wechat_adapter.resolve_contact(task_input)
        if resolution.status != "resolved" or resolution.selected is None:
            return _json_response(
                _wechat_contact_failure_body(
                    request_id=_request_id(body),
                    operation="wechat.draft_message",
                    resolution=resolution,
                    helper_info=self._config.info,
                )
            )
        draft = self._wechat_adapter.draft_message(
            resolution,
            task_input.message_text,
        )
        if draft.status != "drafted":
            return _json_response(
                _wechat_draft_failure_body(
                    request_id=_request_id(body),
                    draft=draft,
                    helper_info=self._config.info,
                )
            )
        try:
            fingerprint = WeChatSendActionFingerprint.from_draft(
                execution_id=_execution_id(body),
                idempotency_key=_idempotency_key(body),
                draft_state=draft,
                app_identity=_wechat_app_identity(body),
            )
        except ValueError as exc:
            return _error_response(400, "bad_request", str(exc))
        return _json_response(
            _wechat_draft_success_body(
                request_id=_request_id(body),
                task_input=task_input,
                resolution=resolution,
                draft=draft,
                fingerprint=fingerprint,
                helper_info=self._config.info,
            )
        )

    def _wechat_send_confirmed_response(
        self,
        body: dict[str, Any] | None,
    ) -> HttpApiResponse:
        if self._wechat_adapter is None:
            return _json_response(
                _wechat_not_available_body(
                    request_id=_request_id(body),
                    operation="wechat.send_confirmed",
                    helper_info=self._config.info,
                )
            )
        if body is None:
            return _error_response(400, "bad_request", "request body is required")
        try:
            fingerprint = _wechat_fingerprint_from_body(body)
            contact_summary = _wechat_contact_summary_from_body(body)
            message_preview = _wechat_message_preview_from_body(body)
            _validate_wechat_confirmation_proof(body, fingerprint)
        except ValueError as exc:
            return _error_response(400, "bad_request", str(exc))

        attempt = self._wechat_adapter.send_after_confirmation(
            fingerprint,
            contact_summary=contact_summary,
            message_preview=message_preview,
        )
        return _json_response(
            _wechat_send_attempt_body(
                request_id=_request_id(body),
                attempt=attempt,
                contact_summary=contact_summary,
                message_preview=message_preview,
                helper_info=self._config.info,
            )
        )


def build_computer_use_helper_server(
    *,
    backend: ComputerUseBackend | None = None,
    wechat_adapter: WeChatHelperAdapter | None = None,
    helper_config: ComputerUseHelperTransportConfig | None = None,
    server_config: LocalSidecarConfig | None = None,
) -> LocalSidecarServer:
    """Build a loopback-only helper prototype server."""

    return LocalSidecarServer(
        ComputerUseHelperTransport(
            backend=backend,
            wechat_adapter=wechat_adapter,
            config=helper_config,
        ),
        config=server_config,
    )


def prepare_computer_use_helper_server(
    *,
    backend: ComputerUseBackend | None = None,
    config: ComputerUseHelperServerConfig,
) -> ComputerUseHelperServerHandle:
    """Prepare a helper server and publish its startup manifest.

    The server is bound before the manifest is written, so callers can use port
    ``0`` and still publish the resolved endpoint. The caller decides whether
    to run it in-thread or foreground via the returned handle.
    """

    from taskweavn.server.computer_use_helper_wechat import (
        build_default_wechat_helper_adapter,
    )

    auth_token = config.auth_token or secrets.token_urlsafe(32)
    token_path = config.token_path or config.manifest_path.with_suffix(".token")
    server = build_computer_use_helper_server(
        backend=backend,
        wechat_adapter=build_default_wechat_helper_adapter(backend),
        helper_config=ComputerUseHelperTransportConfig(
            auth_token=auth_token,
            info=config.info,
        ),
        server_config=LocalSidecarConfig(host=config.host, port=config.port),
    )
    write_helper_token(token_path, auth_token)
    manifest = ComputerUseHelperManifest(
        endpoint=server.base_url,
        token_ref=str(token_path),
        pid=getpid(),
        bundle_id=config.info.bundle_id,
        version=config.info.version,
        api_version=config.info.api_version,
    )
    write_helper_manifest(config.manifest_path, manifest)
    return ComputerUseHelperServerHandle(
        server=server,
        manifest_path=config.manifest_path,
        token_path=token_path,
        manifest=manifest,
        auth_token=auth_token,
    )


def write_helper_token(path: Path, token: str) -> None:
    """Write a helper startup token with owner-only permissions where possible."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        return


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
        api_version=_string(raw.get("apiVersion"))
        or _string(raw.get("api_version"))
        or "plato.computer_use_helper.v1",
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


def _wechat_task_input_from_body(body: dict[str, Any]) -> WeChatSendTaskInput:
    raw_input = body.get("input")
    if not isinstance(raw_input, dict):
        raise ValueError("request input must be a JSON object")
    contact = _string(raw_input.get("contactDisplayName")) or _string(
        raw_input.get("contact_display_name")
    )
    message = _string(raw_input.get("messageText")) or _string(
        raw_input.get("message_text")
    )
    if contact is None:
        raise ValueError("input.contactDisplayName is required")
    if message is None:
        raise ValueError("input.messageText is required")
    external_ref = raw_input.get("externalRef") or raw_input.get("external_ref")
    if not isinstance(external_ref, dict):
        external_ref = None
    return WeChatSendTaskInput(
        contact_display_name=contact,
        message_text=message,
        contact_alias=_string(raw_input.get("contactAlias"))
        or _string(raw_input.get("contact_alias")),
        external_ref=cast(dict[str, str] | None, external_ref),
        operator_note=_string(raw_input.get("operatorNote"))
        or _string(raw_input.get("operator_note")),
    )


def _wechat_fingerprint_from_body(body: dict[str, Any]) -> WeChatSendActionFingerprint:
    raw_input = body.get("input")
    if not isinstance(raw_input, dict):
        raise ValueError("request input must be a JSON object")
    raw = raw_input.get("actionFingerprintPayload") or raw_input.get(
        "action_fingerprint_payload"
    )
    if not isinstance(raw, dict):
        raise ValueError("input.actionFingerprintPayload is required")
    return WeChatSendActionFingerprint(
        execution_id=_required_string(raw, "execution_id"),
        idempotency_key=_required_string(raw, "idempotency_key"),
        contact_summary_hash=_required_string(raw, "contact_summary_hash"),
        message_hash=_required_string(raw, "message_hash"),
        draft_observation_ref=_string(raw.get("draft_observation_ref")),
        app_identity=_required_string(raw, "app_identity"),
    )


def _wechat_contact_summary_from_body(body: dict[str, Any]) -> str:
    raw_input = body.get("input")
    if not isinstance(raw_input, dict):
        raise ValueError("request input must be a JSON object")
    value = _string(raw_input.get("contactSummary")) or _string(
        raw_input.get("contact_summary")
    )
    if value is None:
        raise ValueError("input.contactSummary is required")
    return value


def _wechat_message_preview_from_body(body: dict[str, Any]) -> str:
    raw_input = body.get("input")
    if not isinstance(raw_input, dict):
        raise ValueError("request input must be a JSON object")
    value = _string(raw_input.get("messagePreview")) or _string(
        raw_input.get("message_preview")
    )
    if value is None:
        raise ValueError("input.messagePreview is required")
    return value


def _validate_wechat_confirmation_proof(
    body: dict[str, Any],
    fingerprint: WeChatSendActionFingerprint,
) -> None:
    raw_input = body.get("input")
    if not isinstance(raw_input, dict):
        raise ValueError("request input must be a JSON object")
    proof = raw_input.get("confirmationProof") or raw_input.get("confirmation_proof")
    if not isinstance(proof, dict):
        raise ValueError("input.confirmationProof is required")
    decision = _string(proof.get("decision")) or _string(proof.get("responseValue"))
    if decision not in {"confirm", "approve_session"}:
        raise ValueError("confirmationProof.decision must be confirm")
    source = _string(proof.get("source")) or _string(proof.get("responseSource"))
    if source != "user":
        raise ValueError("confirmationProof.source must be user")
    digest = _string(proof.get("actionFingerprint")) or _string(
        proof.get("action_fingerprint")
    )
    if digest != fingerprint.digest():
        raise ValueError("confirmationProof.actionFingerprint does not match")


def _wechat_not_available_body(
    *,
    request_id: str | None,
    operation: str,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "operation": operation,
        "status": "not_available",
        "success": False,
        "summary": "WeChat helper adapter is not configured.",
        "failureKind": "capability_not_available",
        "phase": "readiness",
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": "Helper process has no WeChat app adapter.",
            "targetApp": "WeChat",
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": {},
        "helper": _info_body(helper_info),
    }


def _wechat_readiness_body(
    *,
    request_id: str | None,
    operation: str,
    readiness: WeChatReadiness,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "operation": operation,
        "status": _wechat_status(readiness.status),
        "success": False,
        "summary": readiness.summary,
        "failureKind": _wechat_failure_kind(readiness.status),
        "phase": "readiness",
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": readiness.summary,
            "targetApp": readiness.app_name,
            "observationRef": readiness.observation_ref,
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": {"setupHint": readiness.setup_hint}
        if readiness.setup_hint
        else {},
        "helper": _info_body(helper_info),
    }


def _wechat_operation_failure_body(
    *,
    request_id: str | None,
    operation: str,
    phase: str,
    result: WeChatOperationResult,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    diagnostics = result.metadata or {}
    body: dict[str, Any] = {
        "requestId": request_id,
        "operation": operation,
        "status": _wechat_status(result.status),
        "success": False,
        "summary": result.summary,
        "failureKind": _operation_failure_kind(result),
        "phase": phase,
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": result.summary,
            "targetApp": "WeChat",
            "observationRef": result.observation_ref,
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": diagnostics,
        "helper": _info_body(helper_info),
    }
    setup_hint = _string(diagnostics.get("setupHint")) or _string(
        diagnostics.get("setup_hint")
    )
    if setup_hint is not None:
        body["setupHint"] = setup_hint
    recovery_actions = _recovery_actions_from_diagnostics(diagnostics)
    if recovery_actions:
        body["recoveryActions"] = list(recovery_actions)
    return body


def _wechat_app_readiness_body(
    *,
    request_id: str | None,
    opened: WeChatOperationResult,
    window: WeChatOperationResult,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    summary = "WeChat Desktop is open and its main window is automation-ready."
    return {
        "requestId": request_id,
        "operation": "wechat.readiness",
        "status": "ready",
        "success": True,
        "summary": summary,
        "phase": "window_readiness",
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": summary,
            "targetApp": "WeChat",
            "observationRef": window.observation_ref or opened.observation_ref,
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": {
            "openSummary": opened.summary,
            "windowSummary": window.summary,
            **(opened.metadata or {}),
            **(window.metadata or {}),
        },
        "helper": _info_body(helper_info),
    }


def _wechat_contact_failure_body(
    *,
    request_id: str | None,
    operation: str,
    resolution: WeChatContactResolution,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "operation": operation,
        "status": _wechat_status(resolution.status),
        "success": False,
        "summary": resolution.reason or "WeChat contact was not resolved safely.",
        "failureKind": f"contact_{resolution.status}",
        "phase": "contact_resolution",
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": resolution.reason
            or "WeChat contact was not resolved safely.",
            "targetApp": "WeChat",
            "candidates": [candidate.summary() for candidate in resolution.candidates],
            "observationRef": resolution.observation_ref,
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": resolution.diagnostics or {},
        "helper": _info_body(helper_info),
    }


def _wechat_draft_failure_body(
    *,
    request_id: str | None,
    draft: WeChatDraftState,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "operation": "wechat.draft_message",
        "status": "failed",
        "success": False,
        "summary": draft.reason or "WeChat draft failed.",
        "failureKind": "draft_failed",
        "phase": "draft",
        "draftState": _draft_state_body(draft),
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": draft.reason or "WeChat draft failed.",
            "targetApp": "WeChat",
            "targetContact": draft.contact_summary,
            "observationRef": draft.draft_observation_ref,
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": {},
        "helper": _info_body(helper_info),
    }


def _wechat_draft_success_body(
    *,
    request_id: str | None,
    task_input: WeChatSendTaskInput,
    resolution: WeChatContactResolution,
    draft: WeChatDraftState,
    fingerprint: WeChatSendActionFingerprint,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "operation": "wechat.draft_message",
        "status": "ok",
        "success": True,
        "summary": f"Drafted message for contact {draft.contact_summary}.",
        "failureKind": None,
        "phase": "draft",
        "risk": {
            "level": "high",
            "requiresConfirmation": True,
            "reason": "External message send requires confirmation.",
            "actionFingerprint": fingerprint.digest(),
        },
        "input": {
            "contactDisplayName": task_input.contact_display_name,
            "messagePreview": draft.message_preview,
        },
        "contactResolution": {
            "status": resolution.status,
            "selected": resolution.selected.summary() if resolution.selected else None,
            "observationRef": resolution.observation_ref,
        },
        "draftState": _draft_state_body(draft),
        "actionFingerprint": fingerprint.digest(),
        "actionFingerprintPayload": fingerprint.to_safe_context(),
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": "WeChat contact resolved and draft inserted.",
            "targetApp": "WeChat",
            "targetContact": draft.contact_summary,
            "messagePreview": draft.message_preview,
            "observationRef": draft.draft_observation_ref,
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": resolution.diagnostics or {},
        "helper": _info_body(helper_info),
    }


def _wechat_send_attempt_body(
    *,
    request_id: str | None,
    attempt: WeChatSendAttemptResult,
    contact_summary: str,
    message_preview: str,
    helper_info: ComputerUseHelperInfo,
) -> dict[str, Any]:
    success = attempt.status == "sent"
    return {
        "requestId": request_id,
        "operation": "wechat.send_confirmed",
        "status": attempt.status,
        "success": success,
        "summary": attempt.summary,
        "failureKind": None if success else _attempt_failure_kind(attempt),
        "phase": (attempt.metadata or {}).get("phase") or "keyboard_submit",
        "evidence": {
            "kind": "computer_use_operation",
            "safeSummary": attempt.summary,
            "targetApp": "WeChat",
            "targetContact": contact_summary,
            "messagePreview": message_preview,
            "observationRef": attempt.send_observation_ref,
            "redaction": "no_raw_chat_history",
        },
        "diagnostics": attempt.metadata or {},
        "helper": _info_body(helper_info),
    }


def _draft_state_body(draft: WeChatDraftState) -> dict[str, Any]:
    return {
        "status": draft.status,
        "contactSummary": draft.contact_summary,
        "messageHash": draft.message_hash,
        "messagePreview": draft.message_preview,
        "draftObservationRef": draft.draft_observation_ref,
        "reason": draft.reason,
    }


def _request_id(body: dict[str, Any] | None) -> str | None:
    if body is None:
        return None
    return _string(body.get("requestId")) or _string(body.get("request_id"))


def _idempotency_key(body: dict[str, Any]) -> str:
    value = _string(body.get("idempotencyKey")) or _string(body.get("idempotency_key"))
    if value is None:
        raise ValueError("idempotencyKey is required")
    return value


def _execution_id(body: dict[str, Any]) -> str:
    raw_caller = body.get("caller")
    if isinstance(raw_caller, dict):
        for key in ("taskExecutionId", "task_execution_id", "executionId"):
            value = _string(raw_caller.get(key))
            if value is not None:
                return value
    request_id = _request_id(body)
    if request_id is None:
        raise ValueError("caller.taskExecutionId or requestId is required")
    return request_id


def _wechat_app_identity(body: dict[str, Any]) -> str:
    raw_input = body.get("input")
    if isinstance(raw_input, dict):
        value = _string(raw_input.get("appIdentity")) or _string(
            raw_input.get("app_identity")
        )
        if value is not None:
            return value
    return "com.tencent.xinWeChat"


def _wechat_status(status: str) -> str:
    if status in {"ready", "ok", "resolved", "drafted"}:
        return "ok"
    if status in {"needs_user", "ambiguous"}:
        return "needs_user"
    if status in {"wechat_missing", "not_observable", "not_available"}:
        return "not_available"
    return "failed"


def _wechat_failure_kind(status: str) -> str:
    if status in {"ready", "ok", "resolved", "drafted"}:
        return ""
    if status == "wechat_missing":
        return "app_not_installed"
    if status in {"not_observable", "not_available"}:
        return "missing_accessibility"
    if status == "not_logged_in":
        return "app_needs_user"
    if status == "needs_user":
        return "needs_user"
    return status


def _operation_failure_kind(result: WeChatOperationResult) -> str:
    if result.metadata:
        failure_kind = result.metadata.get("failure_kind")
        if isinstance(failure_kind, str) and failure_kind:
            return failure_kind
    return _wechat_failure_kind(result.status)


def _attempt_failure_kind(attempt: WeChatSendAttemptResult) -> str:
    if attempt.metadata:
        failure_kind = attempt.metadata.get("failure_kind")
        if isinstance(failure_kind, str) and failure_kind:
            return failure_kind
    if attempt.status == "not_sent":
        return "send_not_attempted"
    if attempt.status == "unknown":
        return "send_unknown"
    return "send_failed"


def _required_string(raw: dict[str, Any], key: str) -> str:
    value = _string(raw.get(key))
    if value is None:
        raise ValueError(f"input.actionFingerprintPayload.{key} is required")
    return value


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _recovery_actions_from_diagnostics(
    diagnostics: dict[str, str],
) -> tuple[str, ...]:
    value = diagnostics.get("recoveryActions") or diagnostics.get("recovery_actions")
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


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
    "ComputerUseHelperServerConfig",
    "ComputerUseHelperServerHandle",
    "ComputerUseHelperTransport",
    "ComputerUseHelperTransportConfig",
    "build_computer_use_helper_server",
    "prepare_computer_use_helper_server",
    "read_helper_manifest",
    "write_helper_manifest",
    "write_helper_token",
]
