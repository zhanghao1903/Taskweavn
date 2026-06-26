from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from taskweavn.tools import (
    ComputerUseHelperBackend,
    ComputerUseHelperBackendConfig,
    ComputerUseHelperHttpClient,
)
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
    assert observation.metadata["diagnostics"]["checkedByProcessPath"].endswith(
        "Helper.app"
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
