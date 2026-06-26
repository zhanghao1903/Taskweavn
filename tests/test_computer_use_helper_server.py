from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from taskweavn.server import (
    ComputerUseHelperInfo,
    ComputerUseHelperManifest,
    ComputerUseHelperServerConfig,
    ComputerUseHelperTransport,
    ComputerUseHelperTransportConfig,
    build_computer_use_helper_server,
    prepare_computer_use_helper_server,
    read_helper_manifest,
    write_helper_manifest,
)
from taskweavn.server.transport import HttpApiRequest
from taskweavn.tools import ComputerUseHelperHttpClient, ScriptedComputerUseBackend
from taskweavn.types import ComputerUseAction, ComputerUseObservation


def test_helper_server_serves_health_and_info() -> None:
    with build_computer_use_helper_server(
        helper_config=ComputerUseHelperTransportConfig(
            info=ComputerUseHelperInfo(
                bundle_id="com.taskweavn.plato.computer-use-helper.dev",
                path="/Users/test/Plato Computer Use Helper Dev.app",
            )
        )
    ) as server:
        health = _request(server, "GET", "/healthz")
        info = _request(server, "GET", "/v1/info")

    assert health.status == 200
    assert health.json["ok"] is True
    assert health.json["name"] == "Plato Computer Use Helper"
    assert info.status == 200
    assert info.json["bundleId"] == "com.taskweavn.plato.computer-use-helper.dev"
    assert info.json["path"].endswith("Plato Computer Use Helper Dev.app")
    assert info.json["apiVersion"] == "plato.computer_use_helper.v1"


def test_helper_server_requires_bearer_token_when_configured() -> None:
    with build_computer_use_helper_server(
        helper_config=ComputerUseHelperTransportConfig(auth_token="secret")
    ) as server:
        rejected = _request(server, "GET", "/v1/info")
        allowed = _request(
            server,
            "GET",
            "/v1/info",
            headers={"authorization": "Bearer secret"},
        )

    assert rejected.status == 401
    assert rejected.json["error"]["code"] == "permission_denied"
    assert allowed.status == 200


def test_helper_server_readiness_maps_backend_observation() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="readiness",
                status="ok",
                summary="helper process can observe frontmost app",
                metadata={
                    "readiness": {"status": "ready"},
                    "diagnostics": {"checkedByProcessPath": "/Helper"},
                },
            )
        ]
    )
    with build_computer_use_helper_server(backend=backend) as server:
        response = _request(server, "GET", "/v1/readiness")

    assert response.status == 200
    assert response.json["status"] == "ready"
    assert response.json["success"] is True
    assert response.json["summary"] == "helper process can observe frontmost app"
    assert response.json["diagnostics"]["checkedByProcessPath"] == "/Helper"
    assert response.json["helper"]["bundleId"].endswith("computer-use-helper.dev")
    assert backend.actions[0].operation == "readiness"


def test_helper_server_forwards_operation_from_http_client() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="type_text",
                status="ok",
                summary="draft typed",
                text_extract="frontmost WeChat",
                metadata={
                    "snapshot_id": "snap-1",
                    "phase": "draft",
                    "evidence": {"safeSummary": "Draft inserted."},
                },
            )
        ]
    )
    with build_computer_use_helper_server(
        backend=backend,
        helper_config=ComputerUseHelperTransportConfig(auth_token="secret"),
    ) as server:
        client = ComputerUseHelperHttpClient(
            endpoint=server.base_url,
            token="secret",
            allowed_apps=("WeChat",),
            allow_coordinate_click=False,
            allow_screenshot=False,
        )
        response = client.execute(
            action=ComputerUseAction(
                operation="type_text",
                instruction="Type a WeChat draft.",
                text="hello",
                metadata={"sessionId": "session-1"},
            )
        )

    assert response["status"] == "ok"
    assert response["summary"] == "draft typed"
    assert response["snapshotId"] == "snap-1"
    assert response["phase"] == "draft"
    assert response["evidence"]["safeSummary"] == "Draft inserted."
    assert backend.actions[0].operation == "type_text"
    assert backend.actions[0].text == "hello"
    assert backend.actions[0].metadata["sessionId"] == "session-1"


def test_helper_transport_rejects_bad_operation_payload() -> None:
    transport = ComputerUseHelperTransport()
    response = transport.handle(
        request=HttpApiRequest(
            method="POST",
            path="/v1/operations/type-text",
            body={"requestId": "req-1", "input": {"instruction": "missing text"}},
        )
    )

    assert response.status_code == 400
    assert response.body["error"]["code"] == "bad_request"


def test_helper_manifest_roundtrip(tmp_path: Path) -> None:
    manifest_path = tmp_path / "computer-use-helper.json"
    manifest = ComputerUseHelperManifest(
        endpoint="http://127.0.0.1:49321",
        token_ref=str(tmp_path / "token.txt"),
        pid=1234,
    )

    write_helper_manifest(manifest_path, manifest)
    loaded = read_helper_manifest(manifest_path)

    assert loaded == manifest


def test_prepare_helper_server_writes_token_manifest_and_serves(
    tmp_path: Path,
) -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="readiness",
                status="ok",
                summary="helper dev server is ready",
                metadata={"readiness": {"status": "ready"}},
            )
        ]
    )
    manifest_path = tmp_path / "computer-use-helper.json"
    helper = prepare_computer_use_helper_server(
        backend=backend,
        config=ComputerUseHelperServerConfig(
            manifest_path=manifest_path,
            info=ComputerUseHelperInfo(path="/dev/Plato Computer Use Helper Dev.app"),
        ),
    )

    try:
        helper.start_in_thread()
        manifest = read_helper_manifest(manifest_path)
        token_ref = manifest.token_ref
        assert token_ref is not None
        token = Path(token_ref).read_text(encoding="utf-8")
        client = ComputerUseHelperHttpClient(
            endpoint=manifest.endpoint,
            token=token,
            allowed_apps=("TextEdit",),
            allow_coordinate_click=False,
            allow_screenshot=False,
        )
        response = client.readiness()
    finally:
        helper.close()

    assert manifest.endpoint == helper.base_url
    assert manifest.pid is not None
    assert manifest.bundle_id == "com.taskweavn.plato.computer-use-helper.dev"
    assert manifest.api_version == "plato.computer_use_helper.v1"
    assert response["status"] == "ready"
    assert response["helper"]["path"] == "/dev/Plato Computer Use Helper Dev.app"


@dataclass(frozen=True)
class _HttpResult:
    status: int
    text: str

    @property
    def json(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.text))


def _request(
    server: Any,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> _HttpResult:
    host, port = server.server_address
    connection = http.client.HTTPConnection(host, port, timeout=5)
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = dict(headers or {})
    if encoded is not None:
        request_headers.setdefault("content-type", "application/json")
    try:
        connection.request(method, path, body=encoded, headers=request_headers)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        return _HttpResult(status=response.status, text=text)
    finally:
        connection.close()


def _observation(
    *,
    operation: str,
    status: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
    text_extract: str | None = None,
) -> ComputerUseObservation:
    return ComputerUseObservation(
        operation=cast(Any, operation),
        status=cast(Any, status),
        success=status == "ok",
        summary=summary,
        metadata=metadata or {},
        text_extract=text_extract,
    )
