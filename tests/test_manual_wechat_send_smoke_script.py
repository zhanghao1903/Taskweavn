from __future__ import annotations

import importlib.util
import json
import sys
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from urllib.parse import urlsplit

import pytest

from taskweavn.execution_plane import (
    WECHAT_SEND_CAPABILITY,
    EmbeddedTaskApiService,
    InMemoryExecutionEnvRegistry,
    InMemoryExecutionPlaneStore,
    SqliteWeChatSendBoundaryStore,
    WeChatSendRuntimeHandler,
    default_local_execution_env,
)
from taskweavn.integrations.wechat_desktop import (
    FakeWeChatDesktopAdapter,
    WeChatContactCandidate,
    WeChatContactResolution,
)
from taskweavn.interaction import AgentMessage, InProcessMessageBus, SqliteMessageStream
from taskweavn.server import HttpApiRequest, PlatoUiHttpTransport
from taskweavn.task import InMemoryTaskBus


def test_manual_wechat_smoke_task_request_uses_required_contract() -> None:
    module = _load_script()
    config = module.SmokeConfig(
        base_url="http://127.0.0.1:53123",
        session_id="session-1",
        contact="测试联系人",
        message="这是一条测试消息。",
        idempotency_key="manual-smoke-key",
        response="reject",
        allow_send=False,
        timeout_seconds=1.0,
        poll_seconds=0.1,
    )

    request = module.build_task_request(config)

    assert request["taskType"] == "communication.wechat.send_message"
    assert request["idempotencyKey"] == "manual-smoke-key"
    assert request["input"] == {
        "contactDisplayName": "测试联系人",
        "messageText": "这是一条测试消息。",
        "operatorNote": "Manual Local macOS WeChat Send MVP smoke.",
    }
    assert request["policy"] == {
        "requiredCapability": "communication.wechat_desktop_send",
        "allowedTools": ["computer_use", "wechat_desktop"],
        "requiresHumanConfirmation": True,
        "riskLevel": "high",
    }
    assert request["metadata"] == {"sessionId": "session-1", "manualSmoke": True}


def test_manual_wechat_smoke_reject_response_is_safe_without_allow_send() -> None:
    module = _load_script()
    config = module.SmokeConfig(
        base_url="http://127.0.0.1:53123",
        session_id="session-1",
        contact="测试联系人",
        message="这是一条测试消息。",
        idempotency_key="manual-smoke-key",
        response="reject",
        allow_send=False,
        timeout_seconds=1.0,
        poll_seconds=0.1,
    )

    assert module._resolve_response(config) == "reject"


def test_manual_wechat_smoke_confirm_requires_explicit_allow_send() -> None:
    module = _load_script()
    config = module.SmokeConfig(
        base_url="http://127.0.0.1:53123",
        session_id="session-1",
        contact="测试联系人",
        message="这是一条测试消息。",
        idempotency_key="manual-smoke-key",
        response="confirm",
        allow_send=False,
        timeout_seconds=1.0,
        poll_seconds=0.1,
    )

    with pytest.raises(module.SmokeError, match="requires --allow-send"):
        module.run_smoke(config)


def test_manual_wechat_smoke_preflight_passes_with_ready_sidecar(
    tmp_path: Path,
) -> None:
    module = _load_script()
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())

    with _fake_wechat_sidecar(tmp_path, adapter=adapter) as base_url:
        result = module.run_preflight(
            module.SmokeConfig(
                base_url=base_url,
                session_id="",
                contact="",
                message="",
                idempotency_key="manual-smoke-preflight",
                response="reject",
                allow_send=False,
                timeout_seconds=2.0,
                poll_seconds=0.01,
                preflight_only=True,
            )
        )

    assert result.ready is True
    assert result.sidecar_name == "Plato Sidecar"
    assert result.computer_use_status == "ok"
    assert result.package_readiness_status == "ready"
    assert result.computer_use_ready is True
    assert result.computer_use_backend == "helper"
    assert result.helper_status == "ready"


def test_manual_wechat_smoke_preflight_fails_when_accessibility_is_missing(
    tmp_path: Path,
) -> None:
    module = _load_script()
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())

    with _fake_wechat_sidecar(tmp_path, adapter=adapter) as base_url:
        result = module.run_preflight(
            module.SmokeConfig(
                base_url=base_url,
                session_id="",
                contact="",
                message="",
                idempotency_key="manual-smoke-preflight",
                response="reject",
                allow_send=False,
                timeout_seconds=2.0,
                poll_seconds=0.01,
                preflight_only=True,
            ),
            readiness_checker=lambda: {
                "backend": "helper",
                "ready": False,
                "status": "missing_accessibility",
                "operationStatus": "needs_user",
                "helperStatus": "missing_accessibility",
                "failureKind": "missing_accessibility",
                "setupHint": "Grant Accessibility permission.",
            },
        )

    assert result.ready is False
    assert result.computer_use_ready is False
    assert result.computer_use_status == "needs_user"
    assert result.package_readiness_status == "missing_accessibility"
    assert result.computer_use_backend == "helper"
    assert result.helper_status == "missing_accessibility"
    assert result.failure_kind == "missing_accessibility"


def test_manual_wechat_smoke_preflight_checks_helper_wechat_app_readiness(
    tmp_path: Path,
) -> None:
    module = _load_script()
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())
    helper_response = {
        "requestId": "wechat-ready-1",
        "operation": "wechat.readiness",
        "status": "ready",
        "success": True,
        "summary": "WeChat Desktop is open and its main window is automation-ready.",
        "phase": "window_readiness",
        "diagnostics": {"windowSummary": "Fake window ready."},
    }

    with (
        _fake_wechat_sidecar(tmp_path, adapter=adapter) as base_url,
        _fake_wechat_helper(tmp_path, response=helper_response) as helper,
    ):
        result = module.run_preflight(
            module.SmokeConfig(
                base_url=base_url,
                session_id="",
                contact="",
                message="",
                idempotency_key="manual-smoke-preflight",
                response="reject",
                allow_send=False,
                timeout_seconds=2.0,
                poll_seconds=0.01,
                preflight_only=True,
                helper_manifest=helper.manifest_path,
            )
        )

    assert result.ready is True
    assert result.wechat_app_status == "ready"
    assert result.wechat_app_success is True
    assert result.wechat_app_phase == "window_readiness"
    assert result.wechat_app_summary == (
        "WeChat Desktop is open and its main window is automation-ready."
    )
    assert result.wechat_app_diagnostics == {"windowSummary": "Fake window ready."}
    assert helper.requests == [
        ("POST", "/v1/apps/wechat/readiness", "Bearer helper-token")
    ]


def test_manual_wechat_smoke_preflight_fails_on_helper_wechat_window_blocker(
    tmp_path: Path,
) -> None:
    module = _load_script()
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())
    helper_response = {
        "requestId": "wechat-ready-2",
        "operation": "wechat.readiness",
        "status": "needs_user",
        "success": False,
        "summary": "WeChat main window is unavailable.",
        "failureKind": "needs_user",
        "phase": "window_readiness",
        "setupHint": "Open the WeChat main window.",
        "recoveryActions": [
            "open_wechat_main_window",
            "rerun_helper_preflight",
        ],
        "diagnostics": {"error": "cannot get window 1"},
    }

    with (
        _fake_wechat_sidecar(tmp_path, adapter=adapter) as base_url,
        _fake_wechat_helper(tmp_path, response=helper_response) as helper,
    ):
        result = module.run_preflight(
            module.SmokeConfig(
                base_url=base_url,
                session_id="",
                contact="",
                message="",
                idempotency_key="manual-smoke-preflight",
                response="reject",
                allow_send=False,
                timeout_seconds=2.0,
                poll_seconds=0.01,
                preflight_only=True,
                helper_manifest=helper.manifest_path,
            )
        )

    assert result.ready is False
    assert result.computer_use_ready is True
    assert result.wechat_app_status == "needs_user"
    assert result.wechat_app_success is False
    assert result.wechat_app_phase == "window_readiness"
    assert result.wechat_app_failure_kind == "needs_user"
    assert result.wechat_app_summary == "WeChat main window is unavailable."
    assert result.wechat_app_setup_hint == "Open the WeChat main window."
    assert result.wechat_app_recovery_actions == (
        "open_wechat_main_window",
        "rerun_helper_preflight",
    )
    assert result.wechat_app_diagnostics == {"error": "cannot get window 1"}


def test_manual_wechat_smoke_evidence_output_redacts_contact_and_message(
    tmp_path: Path,
) -> None:
    module = _load_script()
    evidence_path = tmp_path / "evidence" / "wechat-smoke.json"
    config = module.SmokeConfig(
        base_url="http://127.0.0.1:53123",
        session_id="session-1",
        contact="真实联系人不应写入",
        message="真实消息正文不应写入",
        idempotency_key="manual-smoke-key",
        response="reject",
        allow_send=False,
        timeout_seconds=1.0,
        poll_seconds=0.1,
        evidence_output=evidence_path,
    )

    module.write_evidence_output(
        config,
        kind="smoke",
        result={
            "executionId": "exec-1",
            "taskId": "task-1",
            "confirmationId": "confirm-1",
            "finalStatus": "failed",
            "resultKind": None,
            "errorCode": "wechat_send_rejected",
            "evidenceCount": 2,
        },
    )

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "smoke"
    assert payload["config"]["contactProvided"] is True
    assert payload["config"]["messageChars"] == len("真实消息正文不应写入")
    assert payload["redaction"] == {
        "contact": "not_written",
        "messageText": "not_written",
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "真实联系人不应写入" not in serialized
    assert "真实消息正文不应写入" not in serialized


def test_manual_wechat_smoke_failure_evidence_is_written_and_redacted(
    tmp_path: Path,
) -> None:
    module = _load_script()
    evidence_path = tmp_path / "evidence" / "wechat-smoke-failure.json"
    config = module.SmokeConfig(
        base_url="http://127.0.0.1:53123",
        session_id="session-1",
        contact="真实联系人不应写入",
        message="真实消息正文不应写入",
        idempotency_key="manual-smoke-key",
        response="reject",
        allow_send=False,
        timeout_seconds=1.0,
        poll_seconds=0.1,
        evidence_output=evidence_path,
    )
    error = module.SmokeError(
        "Failed before sending 真实消息正文不应写入",
        details={
            "contact": "真实联系人不应写入",
            "nested": ["真实消息正文不应写入"],
        },
    )

    module.write_failure_evidence_output(config, error)

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "failure"
    assert payload["result"]["message"] == "Failed before sending [redacted-message]"
    assert payload["result"]["details"] == {
        "contact": "[redacted-contact]",
        "nested": ["[redacted-message]"],
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "真实联系人不应写入" not in serialized
    assert "真实消息正文不应写入" not in serialized


def test_manual_wechat_smoke_reject_path_against_fake_http_sidecar(
    tmp_path: Path,
) -> None:
    module = _load_script()
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())

    with _fake_wechat_sidecar(tmp_path, adapter=adapter) as base_url:
        result = module.run_smoke(
            module.SmokeConfig(
                base_url=base_url,
                session_id="session-1",
                contact="张三",
                message="这是一条 fake HTTP smoke 消息。",
                idempotency_key="manual-smoke-reject",
                response="reject",
                allow_send=False,
                timeout_seconds=2.0,
                poll_seconds=0.01,
            )
        )

    assert result.final_status == "failed"
    assert result.error_code == "wechat_send_rejected"
    assert result.evidence_count >= 1
    assert result.terminal_replay_status == "failed"
    assert result.terminal_replay_same_execution is True
    assert _send_call_count(adapter) == 0


def test_manual_wechat_smoke_confirm_path_against_fake_http_sidecar(
    tmp_path: Path,
) -> None:
    module = _load_script()
    adapter = FakeWeChatDesktopAdapter(contact_resolution=_resolved_contact())

    with _fake_wechat_sidecar(tmp_path, adapter=adapter) as base_url:
        result = module.run_smoke(
            module.SmokeConfig(
                base_url=base_url,
                session_id="session-1",
                contact="张三",
                message="这是一条 fake HTTP smoke 消息。",
                idempotency_key="manual-smoke-confirm",
                response="confirm",
                allow_send=True,
                timeout_seconds=2.0,
                poll_seconds=0.01,
            )
        )

    assert result.final_status == "done"
    assert result.result_kind == "wechat_send_result"
    assert result.evidence_count >= 1
    assert result.terminal_replay_status == "done"
    assert result.terminal_replay_same_execution is True
    assert _send_call_count(adapter) == 1


def _load_script() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "manual_wechat_send_smoke.py"
    )
    spec = importlib.util.spec_from_file_location("manual_wechat_send_smoke", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class _FakeSidecarState:
    transport: PlatoUiHttpTransport
    task_bus: InMemoryTaskBus
    message_bus: InProcessMessageBus
    session_id: str = "session-1"
    computer_use_readiness: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "backend": "helper",
            "allowedApps": ["WeChat"],
            "configured": True,
            "ready": True,
            "status": "ready",
            "operationStatus": "ok",
            "helperStatus": "ready",
            "summary": "Plato Computer Use Helper is ready.",
            "recoveryActions": [],
        }
    )


class _FakeSidecarServer(ThreadingHTTPServer):
    state: _FakeSidecarState


def _fake_wechat_sidecar(
    tmp_path: Path,
    *,
    adapter: FakeWeChatDesktopAdapter,
) -> _FakeSidecarContext:
    task_bus = InMemoryTaskBus()
    message_stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    message_bus = InProcessMessageBus(message_stream)
    execution_store = InMemoryExecutionPlaneStore()
    boundary_store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    service = EmbeddedTaskApiService(
        task_bus=task_bus,
        store=execution_store,
        env_registry=InMemoryExecutionEnvRegistry(
            (
                default_local_execution_env(
                    capabilities=(WECHAT_SEND_CAPABILITY,),
                    tool_pool=("computer_use", "wechat_desktop"),
                ),
            )
        ),
        runtime_handlers=(
            WeChatSendRuntimeHandler(
                task_bus=task_bus,
                message_bus=message_bus,
                message_stream=message_stream,
                execution_store=execution_store,
                boundary_store=boundary_store,
                adapter=adapter,
            ),
        ),
    )
    transport = PlatoUiHttpTransport(
        query_gateway=cast(Any, object()),
        command_gateway=cast(Any, object()),
        execution_plane_service=service,
    )
    server = _FakeSidecarServer(("127.0.0.1", 0), _FakeSidecarHandler)
    server.state = _FakeSidecarState(
        transport=transport,
        task_bus=task_bus,
        message_bus=message_bus,
    )
    return _FakeSidecarContext(server)


@dataclass
class _FakeHelperState:
    response: dict[str, Any]
    token: str = "helper-token"
    requests: list[tuple[str, str, str | None]] = field(default_factory=list)


class _FakeHelperServer(ThreadingHTTPServer):
    state: _FakeHelperState


def _fake_wechat_helper(
    tmp_path: Path,
    *,
    response: dict[str, Any],
) -> _FakeHelperContext:
    server = _FakeHelperServer(("127.0.0.1", 0), _FakeHelperHandler)
    server.state = _FakeHelperState(response=response)
    return _FakeHelperContext(server, tmp_path)


class _FakeHelperContext:
    def __init__(self, server: _FakeHelperServer, tmp_path: Path) -> None:
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._state_dir = tmp_path / "helper"
        self.manifest_path = self._state_dir / "computer-use-helper.json"
        self.requests = server.state.requests

    def __enter__(self) -> _FakeHelperContext:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        token_path = self._state_dir / "computer-use-helper.token"
        token_path.write_text(self._server.state.token, encoding="utf-8")
        self._thread.start()
        host, port = self._server.server_address[:2]
        host_text = host.decode("utf-8") if isinstance(host, bytes) else str(host)
        self.manifest_path.write_text(
            json.dumps(
                {
                    "endpoint": f"http://{host_text}:{port}",
                    "tokenRef": str(token_path),
                    "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                    "apiVersion": "plato.computer_use_helper.v1",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._server.shutdown()
        self._thread.join(timeout=2.0)
        self._server.server_close()


class _FakeHelperHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self._handle()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle(self) -> None:
        server = cast(_FakeHelperServer, self.server)
        path = urlsplit(self.path).path
        auth = self.headers.get("authorization")
        server.state.requests.append((self.command, path, auth))
        if auth != f"Bearer {server.state.token}":
            self._write_json(
                401,
                {
                    "error": {
                        "code": "permission_denied",
                        "message": "invalid helper token",
                    }
                },
            )
            return
        if self.command == "POST" and path == "/v1/apps/wechat/readiness":
            self._read_body()
            self._write_json(200, server.state.response)
            return
        self._write_json(404, {"error": {"code": "not_found"}})

    def _read_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        parsed = json.loads(raw.decode("utf-8"))
        assert isinstance(parsed, dict)
        return parsed

    def _write_json(self, status_code: int, body: object) -> None:
        payload = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _FakeSidecarContext:
    def __init__(self, server: _FakeSidecarServer) -> None:
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self._thread.start()
        host, port = self._server.server_address[:2]
        host_text = host.decode("utf-8") if isinstance(host, bytes) else str(host)
        return f"http://{host_text}:{port}"

    def __exit__(self, *exc_info: object) -> None:
        self._server.shutdown()
        self._thread.join(timeout=2.0)
        self._server.server_close()


class _FakeSidecarHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle(self) -> None:
        server = cast(_FakeSidecarServer, self.server)
        path = urlsplit(self.path).path
        if (
            self.command == "GET"
            and path == f"/api/v1/sessions/{server.state.session_id}/snapshot"
        ):
            self._write_json(
                200,
                {
                    "ok": True,
                    "data": {
                        "pendingConfirmations": _pending_confirmations(server.state),
                    },
                    "error": None,
                },
            )
            return

        if self.command == "GET" and path == "/api/v1/settings/readiness":
            self._write_json(
                200,
                {
                    "ok": True,
                    "data": {
                        "schemaVersion": "plato.settings_readiness.v1",
                        "status": "ready",
                        "computerUse": server.state.computer_use_readiness,
                    },
                    "error": None,
                },
            )
            return

        if (
            self.command == "POST"
            and path.startswith(f"/api/v1/sessions/{server.state.session_id}/")
            and path.endswith("/respond")
        ):
            self._handle_confirmation_response(server.state, path)
            return

        body = self._read_body()
        response = server.state.transport.handle(
            HttpApiRequest(method=self.command, path=self.path, body=body)
        )
        self._write_json(response.status_code, response.body)

    def _handle_confirmation_response(
        self,
        state: _FakeSidecarState,
        path: str,
    ) -> None:
        body = self._read_body()
        confirmation_id = path.split("/")[-2]
        payload = body.get("payload") if body is not None else None
        value = payload.get("value") if isinstance(payload, dict) else None
        if value not in {"confirm", "reject"}:
            self._write_json(
                400,
                {
                    "ok": False,
                    "data": None,
                    "error": {"code": "bad_request", "message": "invalid response"},
                },
            )
            return
        task = next(
            (
                item
                for item in state.task_bus.list_for_session(state.session_id)
                if item.waiting_for_confirmation_id == confirmation_id
            ),
            None,
        )
        if task is None:
            self._write_json(
                404,
                {
                    "ok": False,
                    "data": None,
                    "error": {"code": "not_found", "message": "confirmation not found"},
                },
            )
            return
        state.message_bus.publish(
            AgentMessage(
                session_id=state.session_id,
                task_id=task.task_id,
                agent_id="user",
                parent_message_id=confirmation_id,
                message_type="response",
                content=value,
                response_source="user",
                response_value=value,
            )
        )
        self._write_json(
            200,
            {
                "ok": True,
                "data": {"status": "accepted", "confirmationId": confirmation_id},
                "error": None,
            },
        )

    def _read_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        parsed = json.loads(raw.decode("utf-8"))
        assert isinstance(parsed, dict)
        return parsed

    def _write_json(self, status_code: int, body: object) -> None:
        payload = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _pending_confirmations(state: _FakeSidecarState) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for task in state.task_bus.list_for_session(state.session_id):
        if task.status != "waiting_for_user" or task.waiting_for_confirmation_id is None:
            continue
        items.append(
            {
                "id": task.waiting_for_confirmation_id,
                "taskNodeId": task.task_id,
                "status": "pending",
                "title": "WeChat send confirmation",
                "body": "Confirm or reject the fake WeChat send smoke.",
                "options": [],
            }
        )
    return items


def _resolved_contact() -> WeChatContactResolution:
    return WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(
            display_name="张三",
            subtitle="测试联系人",
            confidence=0.96,
        ),
    )


def _send_call_count(adapter: FakeWeChatDesktopAdapter) -> int:
    return sum(1 for name, _payload in adapter.calls if name == "send_after_confirmation")
