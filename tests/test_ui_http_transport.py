"""Tests for the framework-neutral Plato UI HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from taskweavn.server import (
    HttpApiRequest,
    PlatoUiHttpTransport,
    SidecarAuth,
    StaticUiEventSource,
)
from taskweavn.server.ui_contract import (
    CommandRequest,
    CommandResponse,
    CommandResult,
    MainPageSnapshot,
    ProjectSummary,
    QueryResponse,
    SessionSummary,
    UiEvent,
    WorkflowSummary,
)

NOW = datetime(2026, 5, 21, 9, 0, tzinfo=UTC)


def test_root_route_returns_sidecar_api_hint() -> None:
    transport = _transport()

    response = transport.handle(HttpApiRequest(method="GET", path="/"))
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["name"] == "Plato Sidecar"
    assert body["data"]["api_base_path"] == "/api/v1"
    assert body["data"]["health_url"] == "/api/v1/health"
    assert body["data"]["snapshot_url_template"] == (
        "/api/v1/sessions/{sessionId}/snapshot"
    )


def test_health_route_returns_sidecar_identity() -> None:
    transport = _transport()

    response = transport.handle(HttpApiRequest(method="GET", path="/api/v1/health"))
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"] == {"name": "Plato Sidecar", "version": "0.1.0"}


def test_snapshot_route_decodes_session_and_returns_contract_json() -> None:
    query = _QueryGateway()
    transport = _transport(query=query)

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/sessions/session%201/snapshot")
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert query.snapshot_calls == ["session 1"]
    assert body["ok"] is True
    assert body["data"]["session"]["id"] == "session 1"
    assert body["data"]["generatedAt"] == "2026-05-21T09:00:00Z"


def test_command_routes_validate_and_dispatch_to_gateway_methods() -> None:
    commands = _CommandGateway()
    transport = _transport(commands=commands)

    cases = (
        (
            "POST",
            "/api/v1/sessions/session%201/input",
            _command_body("session 1", {"content": "Build a site", "mode": "generate_task_tree"}),
            "append_session_input",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/task-tree/generate",
            _command_body("session 1", {"prompt": "Build a site"}),
            "generate_task_tree",
        ),
        (
            "PATCH",
            "/api/v1/sessions/session%201/tasks/task%201",
            _command_body("session 1", {"summary": "Updated"}),
            "update_task_node:task 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/tasks/task%201/input",
            _command_body("session 1", {"content": "Use calmer copy", "mode": "guidance"}),
            "append_task_input:task 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/task-tree/publish",
            _command_body("session 1", {"taskTreeId": "tree-1", "startImmediately": True}),
            "publish_task_tree",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/confirmations/confirm%201/respond",
            _command_body("session 1", {"value": "yes"}),
            "resolve_confirmation:confirm 1",
        ),
    )

    for method, path, body, _expected_call in cases:
        response = transport.handle(HttpApiRequest(method=method, path=path, body=body))
        assert response.status_code == 200
        assert _dict_body(response.body)["result"]["status"] == "accepted"

    assert commands.calls == [case[3] for case in cases]


def test_command_route_rejects_path_body_session_mismatch() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/input",
            body=_command_body("other-session", {"content": "Build", "mode": "global_guidance"}),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["details"] == {
        "body_session_id": "other-session",
        "path_session_id": "session-1",
    }


def test_command_route_rejects_invalid_body_with_validation_details() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/input",
            body=_command_body("session-1", {"content": "", "mode": "global_guidance"}),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["details"]["errors"]


def test_method_mismatch_and_unknown_route_return_transport_errors() -> None:
    transport = _transport()

    wrong_method = transport.handle(
        HttpApiRequest(method="POST", path="/api/v1/sessions/session-1/snapshot")
    )
    unknown = transport.handle(HttpApiRequest(method="GET", path="/api/v1/unknown"))

    assert wrong_method.status_code == 405
    assert wrong_method.headers["allow"] == "GET"
    assert _dict_body(wrong_method.body)["error"]["code"] == "bad_request"
    assert unknown.status_code == 404
    assert _dict_body(unknown.body)["error"]["code"] == "not_found"


def test_auth_requires_bearer_for_json_routes_and_query_token_for_sse() -> None:
    event = UiEvent(session_id="session-1", event_type="message.appended", cursor="cursor-1")
    transport = _transport(
        auth=SidecarAuth("secret-token"),
        event_source=StaticUiEventSource((event,)),
    )

    rejected = transport.handle(HttpApiRequest(method="GET", path="/api/v1/health"))
    allowed = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/health",
            headers={"authorization": "Bearer secret-token"},
        )
    )
    sse = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/sessions/session-1/events?token=secret-token",
        )
    )

    assert rejected.status_code == 401
    assert allowed.status_code == 200
    assert sse.status_code == 200
    assert sse.headers["content-type"] == "text/event-stream"
    assert "event: message.appended" in _str_body(sse.body)


def test_event_route_uses_resync_fallback_by_default() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/sessions/session-1/events?cursor=old")
    )
    body = _str_body(response.body)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"
    assert "event: session.resync_required" in body
    assert '"cursor":"old"' in body


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

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"resolve_confirmation:{confirmation_id}")
        return _accepted(request.command_id)


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


def _command_body(session_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "commandId": "command-1",
        "sessionId": session_id,
        "payload": payload,
    }


def _dict_body(body: dict[str, Any] | str) -> dict[str, Any]:
    assert isinstance(body, dict)
    return body


def _str_body(body: dict[str, Any] | str) -> str:
    assert isinstance(body, str)
    return body
