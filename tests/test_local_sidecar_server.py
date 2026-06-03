"""Tests for the stdlib local Plato sidecar binding."""

from __future__ import annotations

import http.client
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from taskweavn.server import (
    LocalSidecarConfig,
    LocalSidecarServer,
    PlatoUiHttpTransport,
    SidecarAuth,
    StaticUiEventSource,
)
from taskweavn.server.sidecar import _SidecarRequestHandler
from taskweavn.server.transport import HttpApiResponse
from taskweavn.server.ui_contract import (
    AuditPageSnapshot,
    AuditRecordDetail,
    AuditRecordsResult,
    CommandRequest,
    CommandResponse,
    CommandResult,
    EvidenceDetail,
    MainPageSnapshot,
    ProjectSummary,
    QueryResponse,
    SessionSummary,
    UiEvent,
    WorkflowSummary,
)

NOW = datetime(2026, 5, 21, 10, 0, tzinfo=UTC)


def test_local_sidecar_root_serves_api_hint() -> None:
    with _server() as server:
        response = _request(server, "GET", "/")

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["name"] == "Plato Sidecar"
    assert response.json["data"]["health_url"] == "/api/v1/health"


def test_local_sidecar_serves_health_over_loopback() -> None:
    with _server() as server:
        response = _request(server, "GET", "/api/v1/health")

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"] == {"name": "Plato Sidecar", "version": "0.1.0"}


def test_local_sidecar_routes_snapshot_and_command_requests() -> None:
    query = _QueryGateway()
    commands = _CommandGateway()
    with _server(query=query, commands=commands) as server:
        snapshot = _request(server, "GET", "/api/v1/sessions/session%201/snapshot")
        command = _request(
            server,
            "POST",
            "/api/v1/sessions/session%201/input",
            body={
                "commandId": "command-1",
                "sessionId": "session 1",
                "payload": {
                    "content": "Build a site",
                    "mode": "generate_task_tree",
                },
            },
        )

    assert snapshot.status == 200
    assert snapshot.json["data"]["session"]["id"] == "session 1"
    assert command.status == 200
    assert command.json["result"]["status"] == "accepted"
    assert query.snapshot_calls == ["session 1"]
    assert commands.calls == ["append_session_input"]


def test_local_sidecar_rejects_malformed_json_before_transport_dispatch() -> None:
    commands = _CommandGateway()
    with _server(commands=commands) as server:
        response = _request_raw(
            server,
            "POST",
            "/api/v1/sessions/session-1/input",
            body=b"{not-json",
            headers={"content-type": "application/json"},
        )

    assert response.status == 400
    assert response.json["error"]["code"] == "bad_request"
    assert commands.calls == []


def test_local_sidecar_serves_sse_events() -> None:
    event = UiEvent(session_id="session-1", event_type="message.appended", cursor="cursor-1")
    with _server(event_source=StaticUiEventSource((event,))) as server:
        response = _request(server, "GET", "/api/v1/sessions/session-1/events")

    assert response.status == 200
    assert response.headers["content-type"] == "text/event-stream"
    assert "event: message.appended" in response.text
    assert '"sessionId":"session-1"' in response.text


def test_local_sidecar_supports_bearer_auth_and_query_token_for_sse() -> None:
    event = UiEvent(session_id="session-1", event_type="message.appended", cursor="cursor-1")
    with _server(
        auth=SidecarAuth("secret"),
        event_source=StaticUiEventSource((event,)),
    ) as server:
        rejected = _request(server, "GET", "/api/v1/health")
        allowed = _request(
            server,
            "GET",
            "/api/v1/health",
            headers={"authorization": "Bearer secret"},
        )
        sse = _request(server, "GET", "/api/v1/sessions/session-1/events?token=secret")

    assert rejected.status == 401
    assert allowed.status == 200
    assert sse.status == 200
    assert "event: message.appended" in sse.text


def test_local_sidecar_rejects_non_loopback_origin() -> None:
    with _server() as server:
        rejected = _request(
            server,
            "GET",
            "/api/v1/health",
            headers={"origin": "https://evil.example"},
        )
        allowed = _request(
            server,
            "OPTIONS",
            "/api/v1/health",
            headers={"origin": "http://localhost:5173"},
        )

    assert rejected.status == 403
    assert rejected.json["error"]["code"] == "permission_denied"
    assert allowed.status == 204
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_local_sidecar_refuses_remote_bind_by_default() -> None:
    with pytest.raises(ValueError, match="loopback"):
        LocalSidecarServer(
            _transport(),
            config=LocalSidecarConfig(host="0.0.0.0"),
        )


def test_local_sidecar_suppresses_client_disconnect_during_response_write() -> None:
    handler = _FakeDisconnectingHandler()

    handler._send_response(
        HttpApiResponse(
            status_code=200,
            headers={"content-type": "text/plain"},
            body="client already went away",
        )
    )

    assert handler.sent_status_codes == [200]


def test_local_sidecar_suppresses_client_disconnect_before_request_dispatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with _server() as server:
        try:
            raise ConnectionResetError("connection reset by peer")
        except ConnectionResetError:
            server._server.handle_error(None, ("127.0.0.1", 60519))  # noqa: SLF001

    captured = capsys.readouterr()
    assert "ConnectionResetError" not in captured.err


@dataclass(frozen=True)
class _HttpResult:
    status: int
    headers: dict[str, str]
    text: str

    @property
    def json(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.text))


@dataclass
class _QueryGateway:
    snapshot_calls: list[str] = field(default_factory=list)

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
        self.snapshot_calls.append(session_id)
        project = ProjectSummary(id="local", name="Local")
        workflow = WorkflowSummary(id="authoring", name="Authoring")
        session = SessionSummary(
            id=session_id,
            project_id=project.id,
            workflow_id=workflow.id,
            name="Session",
            status="new",
            created_at=NOW,
            updated_at=NOW,
        )
        snapshot = MainPageSnapshot(
            project=project,
            workflows=(workflow,),
            workflow=workflow,
            sessions=(session,),
            session=session,
            cursor="cursor-1",
            generated_at=NOW,
        )
        return QueryResponse[MainPageSnapshot](
            request_id=request_id or "request-snapshot",
            ok=True,
            data=snapshot,
            cursor=snapshot.cursor,
        )

    def get_audit_snapshot(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        entry: str | None = None,
        filter_kind: str = "all",
        record_id: str | None = None,
        include_detail: bool | None = None,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AuditPageSnapshot]:
        raise NotImplementedError

    def list_audit_records(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        filter_kind: str = "all",
        kind: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        include_hidden_reasons: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordsResult]:
        raise NotImplementedError

    def get_audit_record_detail(
        self,
        session_id: str,
        record_id: str,
        *,
        include_evidence: bool = False,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordDetail]:
        raise NotImplementedError

    def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        *,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[EvidenceDetail]:
        raise NotImplementedError


@dataclass
class _CommandGateway:
    calls: list[str] = field(default_factory=list)

    def append_session_input(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("append_session_input")
        return _accepted(request.command_id)

    def generate_task_tree(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("generate_task_tree")
        return _accepted(request.command_id)

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"update_task_node:{task_node_id}")
        return _accepted(request.command_id)

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"append_task_input:{task_node_id}")
        return _accepted(request.command_id)

    def publish_task_tree(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("publish_task_tree")
        return _accepted(request.command_id)

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"retry_task:{task_node_id}")
        return _accepted(request.command_id)

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"stop_task:{task_node_id}")
        return _accepted(request.command_id)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"resolve_confirmation:{confirmation_id}")
        return _accepted(request.command_id)


class _BrokenPipeWriter:
    def write(self, data: bytes) -> int:
        raise BrokenPipeError("client disconnected")


class _FakeDisconnectingHandler(_SidecarRequestHandler):
    def __init__(self) -> None:
        self.command = "GET"
        self.sent_headers: list[tuple[str, str]] = []
        self.sent_status_codes: list[int] = []
        self.wfile = cast(Any, _BrokenPipeWriter())

    def send_response(self, code: int, message: str | None = None) -> None:
        self.sent_status_codes.append(code)

    def send_header(self, keyword: str, value: str) -> None:
        self.sent_headers.append((keyword, value))

    def end_headers(self) -> None:
        return


def _server(
    *,
    query: _QueryGateway | None = None,
    commands: _CommandGateway | None = None,
    event_source: StaticUiEventSource | None = None,
    auth: SidecarAuth | None = None,
) -> LocalSidecarServer:
    return LocalSidecarServer(
        _transport(
            query=query,
            commands=commands,
            event_source=event_source,
            auth=auth,
        )
    )


def _transport(
    *,
    query: _QueryGateway | None = None,
    commands: _CommandGateway | None = None,
    event_source: StaticUiEventSource | None = None,
    auth: SidecarAuth | None = None,
) -> PlatoUiHttpTransport:
    return PlatoUiHttpTransport(
        query_gateway=query or _QueryGateway(),
        command_gateway=commands or _CommandGateway(),
        event_source=event_source,
        auth=auth,
    )


def _accepted(command_id: str) -> CommandResponse:
    return CommandResponse(
        request_id=f"request-{command_id}",
        ok=True,
        result=CommandResult(
            command_id=command_id,
            status="accepted",
            message="accepted",
        ),
    )


def _request(
    server: LocalSidecarServer,
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> _HttpResult:
    raw_body = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = dict(headers or {})
    if raw_body is not None:
        request_headers.setdefault("content-type", "application/json")
    return _request_raw(server, method, path, body=raw_body, headers=request_headers)


def _request_raw(
    server: LocalSidecarServer,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> _HttpResult:
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        raw = response.read()
        return _HttpResult(
            status=response.status,
            headers={key.lower(): value for key, value in response.getheaders()},
            text=raw.decode("utf-8"),
        )
    finally:
        conn.close()
