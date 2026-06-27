from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from taskweavn.tools import (
    ComputerUseHelperBackend,
    ComputerUseHelperBackendConfig,
    ComputerUseHelperHttpClient,
)
from taskweavn.tools import computer_use_helper_adapter as helper_adapter_module
from taskweavn.types import ComputerUseAction


class FakeHelperClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.actions: list[ComputerUseAction] = []

    def readiness(self) -> dict[str, Any]:
        return self.response

    def execute(self, action: ComputerUseAction) -> dict[str, Any]:
        self.actions.append(action)
        return self.response


class FailingHelperClient:
    def __init__(self, message: str = "helper connection failed") -> None:
        self.message = message
        self.actions: list[ComputerUseAction] = []

    def readiness(self) -> dict[str, Any]:
        raise RuntimeError(self.message)

    def execute(self, action: ComputerUseAction) -> dict[str, Any]:
        self.actions.append(action)
        raise RuntimeError(self.message)


def test_helper_backend_reports_missing_connection_as_not_available() -> None:
    backend = ComputerUseHelperBackend(
        config=ComputerUseHelperBackendConfig(endpoint=None, token=None)
    )

    observation = backend.execute(
        ComputerUseAction(operation="observe", instruction="Inspect frontmost app.")
    )

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.operation == "observe"
    assert observation.metadata["provider"] == "helper"
    assert observation.metadata["failure_kind"] == "helper_not_available"
    assert "endpoint is not configured" in observation.metadata["setup_hint"]


def test_helper_backend_maps_ready_readiness() -> None:
    backend = ComputerUseHelperBackend(
        client=FakeHelperClient(
            {
                "status": "ready",
                "summary": "Helper ready.",
                "helper": {
                    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                    "apiVersion": "plato.computer_use_helper.v1",
                },
            }
        )
    )

    observation = backend.readiness(action_id="ready-1")

    assert observation.action_id == "ready-1"
    assert observation.success is True
    assert observation.status == "ok"
    assert observation.summary == "Helper ready."
    assert observation.metadata["helper_status"] == "ready"
    assert observation.metadata["provider"] == "helper"


def test_helper_backend_maps_missing_accessibility_to_not_available() -> None:
    backend = ComputerUseHelperBackend(
        client=FakeHelperClient(
            {
                "status": "missing_accessibility",
                "summary": "Accessibility permission is missing.",
                "helper": {"apiVersion": "plato.computer_use_helper.v1"},
                "diagnostics": {"checkedByProcessPath": "/Applications/Helper.app"},
            }
        )
    )

    observation = backend.readiness()

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.metadata["helper_status"] == "missing_accessibility"
    assert observation.metadata["failure_kind"] == "missing_accessibility"
    assert observation.metadata["diagnostics"]["checkedByProcessPath"].endswith(
        "Helper.app"
    )


def test_helper_backend_maps_system_events_probe_failure_recovery_metadata() -> None:
    backend = ComputerUseHelperBackend(
        client=FakeHelperClient(
            {
                "status": "automation_not_authorized",
                "summary": (
                    "Plato Computer Use Helper package is ready, but macOS UI "
                    "observation failed: TimeoutExpired"
                ),
                "failureKind": "helper_system_events_probe_failed",
                "phase": "helper_system_events_probe",
                "setupHint": "Grant Accessibility and Automation permissions.",
                "recoveryActions": [
                    "open_macos_privacy_accessibility",
                    "open_macos_privacy_automation",
                    "restart_helper",
                    "rerun_helper_preflight",
                ],
                "diagnostics": {
                    "systemEventsProbe": {
                        "status": "failed",
                        "metadata": {"failure_kind": "applescript_timeout"},
                    }
                },
                "helper": {"apiVersion": "plato.computer_use_helper.v1"},
            }
        )
    )

    observation = backend.readiness()

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.metadata["helper_status"] == "automation_not_authorized"
    assert observation.metadata["failure_kind"] == "helper_system_events_probe_failed"
    assert observation.metadata["phase"] == "helper_system_events_probe"
    assert observation.metadata["setup_hint"] == (
        "Grant Accessibility and Automation permissions."
    )
    assert observation.metadata["recovery_actions"] == [
        "open_macos_privacy_accessibility",
        "open_macos_privacy_automation",
        "restart_helper",
        "rerun_helper_preflight",
    ]
    assert (
        observation.metadata["diagnostics"]["systemEventsProbe"]["metadata"][
            "failure_kind"
        ]
        == "applescript_timeout"
    )


def test_helper_backend_rejects_unexpected_readiness_api_version() -> None:
    backend = ComputerUseHelperBackend(
        client=FakeHelperClient(
            {
                "status": "ready",
                "summary": "Helper ready.",
                "helper": {
                    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                    "apiVersion": "plato.computer_use_helper.v2",
                },
            }
        )
    )

    observation = backend.readiness()

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.metadata["helper_status"] == "helper_version_mismatch"
    assert observation.metadata["failure_kind"] == "helper_version_mismatch"
    assert "API version mismatch" in observation.metadata["setup_hint"]
    assert observation.metadata["helper"]["apiVersion"] == "plato.computer_use_helper.v2"


def test_helper_backend_maps_operation_result_evidence_and_failure_kind() -> None:
    client = FakeHelperClient(
        {
            "status": "blocked",
            "summary": "External message requires confirmation.",
            "failureKind": "confirmation_missing",
            "phase": "send",
            "risk": {"level": "high", "requiresConfirmation": True},
            "evidence": {"safeSummary": "Draft is present."},
            "metadata": {"targetApp": "WeChat"},
            "helper": {"apiVersion": "plato.computer_use_helper.v1"},
        }
    )
    backend = ComputerUseHelperBackend(client=client)
    action = ComputerUseAction(
        operation="click",
        instruction="Submit message.",
        target="Send",
        metadata={"target_app": "WeChat"},
    )

    observation = backend.execute(action)

    assert client.actions == [action]
    assert observation.success is False
    assert observation.status == "blocked"
    assert observation.metadata["failure_kind"] == "confirmation_missing"
    assert observation.metadata["phase"] == "send"
    assert observation.metadata["risk"]["level"] == "high"
    assert observation.metadata["evidence"]["safeSummary"] == "Draft is present."
    assert observation.metadata["targetApp"] == "WeChat"


def test_helper_http_client_builds_operation_envelope() -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def transport(
        method: str,
        path: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        calls.append((method, path, payload))
        return {
            "status": "ok",
            "summary": "Typed draft.",
            "snapshotId": "snap-1",
            "textExtract": "frontmost WeChat",
        }

    client = ComputerUseHelperHttpClient(
        endpoint="http://127.0.0.1:49321",
        token="secret",
        allowed_apps=("WeChat",),
        allow_coordinate_click=False,
        allow_screenshot=False,
        transport=transport,
    )

    response = client.execute(
        ComputerUseAction(
            operation="type_text",
            instruction="Type a draft only.",
            text="hello",
            metadata={
                "sessionId": "session-1",
                "taskExecutionId": "exec-1",
                "idempotencyKey": "idem-1",
            },
        )
    )

    assert response["summary"] == "Typed draft."
    method, path, payload = calls[0]
    assert method == "POST"
    assert path == "/v1/operations/type-text"
    assert payload is not None
    assert payload["idempotencyKey"] == "idem-1"
    assert payload["caller"] == {
        "sessionId": "session-1",
        "taskExecutionId": "exec-1",
    }
    assert payload["input"]["text"] == "hello"
    assert payload["policy"]["allowedApps"] == ["WeChat"]
    assert payload["policy"]["requiresConfirmationBeforeSend"] is True


def test_helper_http_client_builds_wechat_draft_envelope() -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def transport(
        method: str,
        path: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        calls.append((method, path, payload))
        return {"status": "ok", "summary": "Drafted."}

    client = ComputerUseHelperHttpClient(
        endpoint="http://127.0.0.1:49321",
        token="secret",
        allowed_apps=("WeChat",),
        allow_coordinate_click=False,
        allow_screenshot=False,
        transport=transport,
    )

    response = client.wechat_draft_message(
        request_id="draft-1",
        idempotency_key="idem-1",
        caller={"sessionId": "session-1", "taskExecutionId": "exec-1"},
        contact_display_name="文件传输助手",
        message_text="你好",
    )

    assert response["summary"] == "Drafted."
    method, path, payload = calls[0]
    assert method == "POST"
    assert path == "/v1/apps/wechat/draft-message"
    assert payload is not None
    assert payload["operation"] == "wechat.draft_message"
    assert payload["idempotencyKey"] == "idem-1"
    assert payload["input"]["contactDisplayName"] == "文件传输助手"
    assert payload["input"]["messageText"] == "你好"
    assert payload["policy"]["allowedApps"] == ["WeChat"]
    assert payload["policy"]["requiresConfirmationBeforeSend"] is True


def test_helper_http_client_builds_wechat_send_confirmed_envelope() -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def transport(
        method: str,
        path: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        calls.append((method, path, payload))
        return {"status": "sent", "summary": "Sent."}

    client = ComputerUseHelperHttpClient(
        endpoint="http://127.0.0.1:49321",
        token="secret",
        allowed_apps=("WeChat",),
        allow_coordinate_click=False,
        allow_screenshot=False,
        transport=transport,
    )

    response = client.wechat_send_confirmed(
        request_id="send-1",
        idempotency_key="idem-1",
        caller={"sessionId": "session-1", "taskExecutionId": "exec-1"},
        action_fingerprint_payload={"execution_id": "exec-1"},
        action_fingerprint="fingerprint-1",
        contact_summary="文件传输助手",
        message_preview="你好",
        confirmation_id="confirm-1",
    )

    assert response["summary"] == "Sent."
    method, path, payload = calls[0]
    assert method == "POST"
    assert path == "/v1/apps/wechat/send-confirmed"
    assert payload is not None
    assert payload["operation"] == "wechat.send_confirmed"
    assert payload["input"]["confirmationProof"] == {
        "confirmationId": "confirm-1",
        "decision": "confirm",
        "source": "user",
        "actionFingerprint": "fingerprint-1",
    }
    assert payload["policy"]["requiresConfirmationBeforeSend"] is False


def test_helper_http_client_uses_longer_timeout_for_wechat_app_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeouts: list[float] = []

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"status":"ok","summary":"ok"}'

    def fake_urlopen(_request: object, *, timeout: float) -> FakeResponse:
        timeouts.append(timeout)
        return FakeResponse()

    monkeypatch.setattr(helper_adapter_module, "urlopen", fake_urlopen)

    client = ComputerUseHelperHttpClient(
        endpoint="http://127.0.0.1:49321",
        token="secret",
        allowed_apps=("WeChat",),
        allow_coordinate_click=False,
        allow_screenshot=False,
        timeout_seconds=7.0,
        app_operation_timeout_seconds=77.0,
    )

    client.readiness()
    client.wechat_draft_message(
        request_id="draft-1",
        idempotency_key="idem-1",
        caller={"sessionId": "session-1", "taskExecutionId": "exec-1"},
        contact_display_name="文件传输助手",
        message_text="你好",
    )
    client.wechat_send_confirmed(
        request_id="send-1",
        idempotency_key="idem-1",
        caller={"sessionId": "session-1", "taskExecutionId": "exec-1"},
        action_fingerprint_payload={"execution_id": "exec-1"},
        action_fingerprint="fingerprint-1",
        contact_summary="文件传输助手",
        message_preview="你好",
        confirmation_id="confirm-1",
    )

    assert timeouts == [7.0, 77.0, 77.0]


def test_helper_backend_loads_endpoint_and_token_ref_from_manifest(tmp_path: Path) -> None:
    token_path = tmp_path / "token.txt"
    token_path.write_text("token-from-file\n", encoding="utf-8")
    manifest_path = tmp_path / "helper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "endpoint": "http://127.0.0.1:49321",
                "tokenRef": str(token_path),
                "apiVersion": "plato.computer_use_helper.v1",
            }
        ),
        encoding="utf-8",
    )

    backend = ComputerUseHelperBackend(
        config=ComputerUseHelperBackendConfig(endpoint_manifest_path=manifest_path)
    )

    assert backend._client is not None


def test_helper_backend_auto_launches_app_and_waits_for_manifest(
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"
    app_path.mkdir()
    manifest_path = tmp_path / "helper.json"
    launches: list[Path] = []

    def launcher(path: Path) -> None:
        launches.append(path)
        manifest_path.write_text(
            json.dumps(
                {
                    "endpoint": "http://127.0.0.1:49321",
                    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                    "apiVersion": "plato.computer_use_helper.v1",
                }
            ),
            encoding="utf-8",
        )

    backend = ComputerUseHelperBackend(
        config=ComputerUseHelperBackendConfig(
            endpoint_manifest_path=manifest_path,
            helper_app_path=app_path,
            helper_auto_launch=True,
            helper_launch_timeout_seconds=0.1,
            helper_app_launcher=launcher,
            expected_bundle_id="com.taskweavn.plato.computer-use-helper.dev",
        )
    )

    assert launches == [app_path]
    assert backend._client is not None


def test_helper_backend_relaunches_when_existing_manifest_endpoint_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"
    app_path.mkdir()
    manifest_path = tmp_path / "helper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "endpoint": "http://127.0.0.1:9",
                "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                "apiVersion": "plato.computer_use_helper.v1",
            }
        ),
        encoding="utf-8",
    )
    launches: list[Path] = []
    manifests_seen: list[Mapping[str, Any]] = []

    def launcher(path: Path) -> None:
        launches.append(path)
        manifest_path.write_text(
            json.dumps(
                {
                    "endpoint": "http://127.0.0.1:49322",
                    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                    "apiVersion": "plato.computer_use_helper.v1",
                }
            ),
            encoding="utf-8",
        )

    backend = ComputerUseHelperBackend(
        client=FailingHelperClient(),
        config=ComputerUseHelperBackendConfig(
            endpoint_manifest_path=manifest_path,
            helper_app_path=app_path,
            helper_auto_launch=True,
            helper_launch_timeout_seconds=0.1,
            helper_app_launcher=launcher,
            expected_bundle_id="com.taskweavn.plato.computer-use-helper.dev",
        ),
    )

    def client_from_manifest(
        manifest: Mapping[str, Any],
        *,
        endpoint_override: str | None = None,
        token_override: str | None = None,
    ) -> FakeHelperClient:
        assert endpoint_override is None
        assert token_override is None
        manifests_seen.append(manifest)
        return FakeHelperClient(
            {
                "status": "ready",
                "summary": "Helper relaunched.",
                "helper": {
                    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                    "apiVersion": "plato.computer_use_helper.v1",
                },
            }
        )

    monkeypatch.setattr(backend, "_client_from_manifest", client_from_manifest)

    observation = backend.readiness()

    assert launches == [app_path]
    assert manifests_seen == [
        {
            "endpoint": "http://127.0.0.1:49322",
            "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
            "apiVersion": "plato.computer_use_helper.v1",
        }
    ]
    assert observation.success is True
    assert observation.status == "ok"
    assert observation.summary == "Helper relaunched."


def test_helper_backend_waits_for_refreshed_manifest_after_stale_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"
    app_path.mkdir()
    manifest_path = tmp_path / "helper.json"
    stale_manifest = {
        "endpoint": "http://127.0.0.1:9",
        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
        "apiVersion": "plato.computer_use_helper.v1",
        "pid": 111,
    }
    fresh_manifest = {
        "endpoint": "http://127.0.0.1:49323",
        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
        "apiVersion": "plato.computer_use_helper.v1",
        "pid": 222,
    }
    manifest_path.write_text(json.dumps(stale_manifest), encoding="utf-8")
    launches: list[Path] = []
    sleeps: list[float] = []
    manifests_seen: list[Mapping[str, Any]] = []

    def launcher(path: Path) -> None:
        launches.append(path)

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        manifest_path.write_text(json.dumps(fresh_manifest), encoding="utf-8")

    backend = ComputerUseHelperBackend(
        client=FailingHelperClient(),
        config=ComputerUseHelperBackendConfig(
            endpoint_manifest_path=manifest_path,
            helper_app_path=app_path,
            helper_auto_launch=True,
            helper_launch_timeout_seconds=1.0,
            helper_launch_poll_interval_seconds=0.01,
            helper_app_launcher=launcher,
            expected_bundle_id="com.taskweavn.plato.computer-use-helper.dev",
        ),
    )

    def client_from_manifest(
        manifest: Mapping[str, Any],
        *,
        endpoint_override: str | None = None,
        token_override: str | None = None,
    ) -> FakeHelperClient:
        assert endpoint_override is None
        assert token_override is None
        manifests_seen.append(manifest)
        return FakeHelperClient(
            {
                "status": "ready",
                "summary": "Helper relaunched from refreshed manifest.",
                "helper": {
                    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                    "apiVersion": "plato.computer_use_helper.v1",
                },
            }
        )

    monkeypatch.setattr("taskweavn.tools.computer_use_helper_adapter.time.sleep", sleep)
    monkeypatch.setattr(backend, "_client_from_manifest", client_from_manifest)

    observation = backend.readiness()

    assert launches == [app_path]
    assert sleeps == [0.05]
    assert manifests_seen == [fresh_manifest]
    assert observation.success is True
    assert observation.status == "ok"
    assert observation.summary == "Helper relaunched from refreshed manifest."


def test_helper_backend_reports_missing_helper_app_for_auto_launch(
    tmp_path: Path,
) -> None:
    backend = ComputerUseHelperBackend(
        config=ComputerUseHelperBackendConfig(
            endpoint_manifest_path=tmp_path / "helper.json",
            helper_app_path=tmp_path / "Missing Helper.app",
            helper_auto_launch=True,
        )
    )

    observation = backend.readiness()

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.metadata["failure_kind"] == "helper_not_installed"
    assert "helper app not found" in observation.metadata["setup_hint"]


def test_helper_backend_reads_auto_launch_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "helper.json"
    app_path = tmp_path / "Plato Computer Use Helper Dev.app"
    monkeypatch.setenv("PLATO_COMPUTER_USE_HELPER_MANIFEST", str(manifest_path))
    monkeypatch.setenv("PLATO_COMPUTER_USE_HELPER_APP_PATH", str(app_path))
    monkeypatch.setenv("PLATO_COMPUTER_USE_HELPER_AUTO_LAUNCH", "1")
    monkeypatch.setenv("PLATO_COMPUTER_USE_HELPER_LAUNCH_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("PLATO_COMPUTER_USE_HELPER_LAUNCH_POLL_INTERVAL_SECONDS", "0.5")
    monkeypatch.setenv("PLATO_COMPUTER_USE_HELPER_APP_OPERATION_TIMEOUT_SECONDS", "77")

    config = ComputerUseHelperBackendConfig.from_environment()

    assert config.endpoint_manifest_path == manifest_path
    assert config.helper_app_path == app_path
    assert config.helper_auto_launch is True
    assert config.helper_launch_timeout_seconds == 45
    assert config.helper_launch_poll_interval_seconds == 0.5
    assert config.app_operation_timeout_seconds == 77


def test_helper_backend_rejects_manifest_bundle_mismatch(tmp_path: Path) -> None:
    manifest_path = tmp_path / "helper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "endpoint": "http://127.0.0.1:49321",
                "bundleId": "com.example.untrusted-helper",
                "apiVersion": "plato.computer_use_helper.v1",
            }
        ),
        encoding="utf-8",
    )
    backend = ComputerUseHelperBackend(
        config=ComputerUseHelperBackendConfig(
            endpoint_manifest_path=manifest_path,
            expected_bundle_id="com.taskweavn.plato.computer-use-helper.dev",
        )
    )

    observation = backend.readiness()

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.metadata["failure_kind"] == "helper_untrusted"
    assert "bundle id mismatch" in observation.metadata["setup_hint"]
