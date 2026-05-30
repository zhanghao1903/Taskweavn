"""Tests for the framework-neutral Plato UI HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from taskweavn.server import (
    HttpApiRequest,
    InMemoryUiCommandResponseIdempotencyStore,
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
from taskweavn.task import ExecutionDispatchRequestResult

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


def test_session_lifecycle_routes_dispatch_to_gateway() -> None:
    lifecycle = _SessionLifecycleGateway()
    transport = _transport(session_lifecycle_gateway=lifecycle)

    listed = transport.handle(HttpApiRequest(method="GET", path="/api/v1/sessions"))
    created = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions",
            body={"name": "New session"},
        )
    )
    renamed = transport.handle(
        HttpApiRequest(
            method="PATCH",
            path="/api/v1/sessions/session%201",
            body={"name": "Renamed"},
        )
    )
    deleted = transport.handle(
        HttpApiRequest(method="POST", path="/api/v1/sessions/session%201/delete")
    )

    assert listed.status_code == 200
    assert _dict_body(listed.body)["data"]["sessions"][0]["id"] == "session-1"
    assert created.status_code == 200
    assert _dict_body(created.body)["data"]["sessionId"] == "created-session"
    assert renamed.status_code == 200
    assert _dict_body(renamed.body)["data"]["session"]["name"] == "Renamed"
    assert deleted.status_code == 200
    assert _dict_body(deleted.body)["data"]["nextSessionId"] == "next-session"
    assert lifecycle.calls == [
        ("list",),
        ("create", "New session"),
        ("rename", "session 1", "Renamed"),
        ("delete", "session 1"),
    ]


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


def test_publish_start_immediately_requests_execution_dispatch() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/publish",
            body=_command_body(
                "session 1",
                {"taskTreeId": "tree-1", "startImmediately": True},
                command_id="publish-1",
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["result"]["debugRefs"]["dispatchStatus"] == "queued"
    assert body["result"]["debugRefs"]["dispatchReason"] == (
        "publish_start_immediately"
    )
    assert body["refresh"]["waitForEvents"] is True
    assert execution.calls == [
        ("session 1", "publish_start_immediately", "publish-1")
    ]


def test_publish_start_immediately_false_does_not_dispatch() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/publish",
            body=_command_body(
                "session 1",
                {"taskTreeId": "tree-1", "startImmediately": False},
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert "dispatchStatus" not in body["result"]["debugRefs"]
    assert execution.calls == []


def test_execution_dispatch_route_returns_accepted_command_response() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/execution/dispatch",
            body=_command_body("session 1", {}),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["result"]["status"] == "accepted"
    assert body["result"]["debugRefs"]["dispatchStatus"] == "queued"
    assert body["refresh"]["waitForEvents"] is True
    assert body["refresh"]["suggestedQueries"] == ["session.snapshot", "task.tree"]
    assert execution.calls == [("session 1", "manual_control_route", "command-1")]


def test_execution_dispatch_route_rejects_disabled_dispatcher() -> None:
    execution = _ExecutionTriggerGateway(status="disabled")
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/execution/dispatch",
            body=_command_body("session 1", {}, command_id="dispatch-1"),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["result"]["status"] == "rejected"
    assert body["error"]["code"] == "command_rejected"
    assert body["error"]["details"]["dispatch_status"] == "disabled"
    assert body["refresh"]["waitForEvents"] is False


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


def test_command_route_replays_idempotent_response_before_gateway_dispatch() -> None:
    commands = _CommandGateway()
    transport = _transport(
        commands=commands,
        command_idempotency_store=InMemoryUiCommandResponseIdempotencyStore(),
    )

    first = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build a site"},
                command_id="command-1",
                idempotency_key="idem-1",
            ),
        )
    )
    replay = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build a site"},
                command_id="command-2",
                idempotency_key="idem-1",
            ),
        )
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert _dict_body(replay.body) == _dict_body(first.body)
    assert commands.calls == ["generate_task_tree"]


def test_command_route_rejects_idempotency_key_reused_for_different_payload() -> None:
    commands = _CommandGateway()
    transport = _transport(
        commands=commands,
        command_idempotency_store=InMemoryUiCommandResponseIdempotencyStore(),
    )

    first = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build a site"},
                command_id="command-1",
                idempotency_key="idem-1",
            ),
        )
    )
    conflict = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build another site"},
                command_id="command-2",
                idempotency_key="idem-1",
            ),
        )
    )
    body = _dict_body(conflict.body)

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert body["requestId"] == "command-2"
    assert body["error"]["code"] == "idempotency_conflict"
    assert body["error"]["details"] == {
        "idempotency_key": "idem-1",
        "route": "generate_task_tree",
    }
    assert commands.calls == ["generate_task_tree"]


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


def test_client_error_log_route_dispatches_to_sink() -> None:
    sink = _ClientErrorSink()
    transport = _transport(client_error_log_sink=sink)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/client-logs/errors",
            body={
                "entry": {
                    "level": "error",
                    "message": "snapshot failed",
                    "namespace": "main-page",
                }
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"] == {"stored": True}
    assert sink.calls == [
        (
            "session 1",
            {
                "entry": {
                    "level": "error",
                    "message": "snapshot failed",
                    "namespace": "main-page",
                }
            },
        )
    ]


def test_client_error_log_route_rejects_empty_body() -> None:
    transport = _transport(client_error_log_sink=_ClientErrorSink())

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/client-logs/errors",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"


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


@dataclass
class _ClientErrorSink:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def write_error(self, session_id: str, payload: dict[str, Any]) -> None:
        self.calls.append((session_id, payload))


@dataclass
class _SessionLifecycleGateway:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def list_sessions(self) -> dict[str, Any]:
        self.calls.append(("list",))
        return {"sessions": [{"id": "session-1", "name": "Session 1"}]}

    def create_session(self, name: str) -> dict[str, Any]:
        self.calls.append(("create", name))
        return {"sessionId": "created-session", "session": {"name": name}}

    def rename_session(self, session_id: str, name: str) -> dict[str, Any]:
        self.calls.append(("rename", session_id, name))
        return {"sessionId": session_id, "session": {"id": session_id, "name": name}}

    def delete_session(self, session_id: str) -> dict[str, Any]:
        self.calls.append(("delete", session_id))
        return {"deletedSessionId": session_id, "nextSessionId": "next-session"}


@dataclass
class _ExecutionTriggerGateway:
    status: str = "queued"
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)

    def request_dispatch(
        self,
        session_id: str,
        *,
        reason: str,
        request_id: str | None = None,
    ) -> ExecutionDispatchRequestResult:
        self.calls.append((session_id, reason, request_id))
        return ExecutionDispatchRequestResult(
            status=self.status,  # type: ignore[arg-type]
            session_id=session_id,
            reason=reason,  # type: ignore[arg-type]
            request_id=request_id,
            message=f"dispatch {self.status}",
            error_ref=None if self.status == "queued" else self.status,
        )


def _transport(
    *,
    query: _QueryGateway | None = None,
    commands: _CommandGateway | None = None,
    event_source: StaticUiEventSource | None = None,
    auth: SidecarAuth | None = None,
    client_error_log_sink: _ClientErrorSink | None = None,
    session_lifecycle_gateway: _SessionLifecycleGateway | None = None,
    command_idempotency_store: InMemoryUiCommandResponseIdempotencyStore | None = None,
    execution_trigger_gateway: _ExecutionTriggerGateway | None = None,
) -> PlatoUiHttpTransport:
    return PlatoUiHttpTransport(
        query_gateway=query or _QueryGateway(),
        command_gateway=commands or _CommandGateway(),
        event_source=event_source,
        auth=auth,
        client_error_log_sink=client_error_log_sink,
        session_lifecycle_gateway=session_lifecycle_gateway,
        command_idempotency_store=command_idempotency_store,
        execution_trigger_gateway=execution_trigger_gateway,
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


def _command_body(
    session_id: str,
    payload: dict[str, object],
    *,
    command_id: str = "command-1",
    idempotency_key: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "commandId": command_id,
        "sessionId": session_id,
        "payload": payload,
    }
    if idempotency_key is not None:
        body["idempotencyKey"] = idempotency_key
    return body


def _dict_body(body: dict[str, Any] | str) -> dict[str, Any]:
    assert isinstance(body, dict)
    return body


def _str_body(body: dict[str, Any] | str) -> str:
    assert isinstance(body, str)
    return body
