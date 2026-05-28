"""Tests for Main Page real-backend sidecar application assembly."""

from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from typing import Any, cast

import pytest

from taskweavn.core import SessionManager, SessionManagerError, WorkspaceLayout
from taskweavn.server import (
    DEFAULT_PLATO_SIDECAR_PORT,
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    MainPageTaskRefResolver,
    build_main_page_sidecar_app,
)
from taskweavn.task import DraftTaskNode, InMemoryDraftTaskStore, SqliteTaskBus, TaskRef


def test_main_page_sidecar_config_uses_stable_dev_port_by_default(
    tmp_path: Any,
) -> None:
    config = MainPageSidecarConfig(workspace_root=tmp_path)

    assert config.port == DEFAULT_PLATO_SIDECAR_PORT


def test_build_main_page_sidecar_app_starts_without_session_and_frontend_creates_one(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=tmp_path,
            port=0,
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        listed = _request(app, "GET", "/api/v1/sessions")
        created = _request(app, "POST", "/api/v1/sessions", body={"name": "Demo session"})
        session_id = created.json["data"]["sessionId"]
        response = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
    finally:
        app.close()

    assert app.session is None
    assert listed.status == 200
    assert listed.json["data"]["sessions"] == []
    assert created.json["data"]["session"]["name"] == "Demo session"
    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["session"]["id"] == session_id
    assert response.json["data"]["session"]["status"] == "new"
    assert response.json["data"]["taskTree"] is None


def test_build_main_page_sidecar_app_reuses_existing_session(tmp_path: Any) -> None:
    layout = WorkspaceLayout(tmp_path)
    manager = SessionManager(layout)
    try:
        session = manager.create("Existing")
    finally:
        manager.close()

    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, session_id=session.id, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        assert app.session is not None
        assert app.session.id == session.id
        assert app.session.name == "Existing"
    finally:
        app.close()


def test_main_page_sidecar_app_session_lifecycle_routes(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        first = _request(app, "POST", "/api/v1/sessions", body={"name": "First"})
        first_id = first.json["data"]["sessionId"]
        created = _request(
            app,
            "POST",
            "/api/v1/sessions",
            body={"name": "Second"},
        )
        created_id = created.json["data"]["sessionId"]
        renamed = _request(
            app,
            "PATCH",
            f"/api/v1/sessions/{created_id}",
            body={"name": "Renamed"},
        )
        deleted = _request(
            app,
            "POST",
            f"/api/v1/sessions/{created_id}/delete",
        )
        snapshot = _request(app, "GET", f"/api/v1/sessions/{first_id}/snapshot")
    finally:
        app.close()

    assert created.status == 200
    assert created.json["data"]["session"]["name"] == "Second"
    assert renamed.status == 200
    assert renamed.json["data"]["session"]["name"] == "Renamed"
    assert deleted.status == 200
    assert deleted.json["data"]["deletedSessionId"] == created_id
    assert snapshot.json["data"]["sessions"][0]["id"] == first_id


def test_build_main_page_sidecar_app_rejects_unknown_session_id(tmp_path: Any) -> None:
    with pytest.raises(SessionManagerError, match="no such session"):
        build_main_page_sidecar_app(
            MainPageSidecarConfig(workspace_root=tmp_path, session_id="missing"),
            MainPageSidecarDependencies(llm=_StubLLM()),
        )


def test_main_page_sidecar_app_routes_session_input_to_real_services(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        session_id = _create_session(app)
        command = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/input",
            body={
                "commandId": "command-1",
                "sessionId": session_id,
                "payload": {
                    "content": "Build a quiet personal website.",
                    "mode": "global_guidance",
                },
            },
        )
        snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
        raw_tasks = app.raw_task_store.list_for_session(session_id)
    finally:
        app.close()

    assert command.status == 200
    assert command.json["ok"] is True
    assert command.json["result"]["status"] == "accepted"
    assert raw_tasks[0].intent_summary == "Build a quiet website"
    assert snapshot.json["data"]["session"]["status"] == "understanding"
    assert snapshot.json["data"]["messages"][0]["body"] == (
        "Build a quiet personal website."
    )


def test_main_page_sidecar_app_generates_task_tree_from_prompt(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(
            llm=_StubLLM(
                [
                    """
                    {
                      "intent_summary": "Build a quiet website",
                      "feasibility": {
                        "status": "ready",
                        "confidence": 0.95,
                        "suggested_next_action": "generate_task_tree"
                      },
                      "constraints": ["quiet visual style"]
                    }
                    """,
                    """
                    {
                      "assistant_message": "Drafted the first TaskTree.",
                      "roots": [
                        {
                          "title": "Plan structure",
                          "intent": "Plan the website structure.",
                          "required_capability": "general"
                        }
                      ]
                    }
                    """,
                ]
            )
        ),
    )
    try:
        session_id = _create_session(app)
        command = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/generate",
            body={
                "commandId": "generate-1",
                "sessionId": session_id,
                "payload": {"prompt": "Build a quiet personal website."},
            },
        )
        snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
    finally:
        app.close()

    assert command.status == 200
    assert command.json["ok"] is True
    assert snapshot.json["data"]["taskTree"]["nodes"][0]["title"] == "Plan structure"
    assert snapshot.json["data"]["taskTree"]["nodes"][0]["taskRef"]["kind"] == "draft"


def test_main_page_sidecar_app_recovers_draft_tree_after_restart_and_publishes(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(
            llm=_StubLLM(
                [
                    """
                    {
                      "intent_summary": "Build a quiet website",
                      "feasibility": {
                        "status": "ready",
                        "confidence": 0.95,
                        "suggested_next_action": "generate_task_tree"
                      },
                      "constraints": ["quiet visual style"]
                    }
                    """,
                    """
                    {
                      "assistant_message": "Drafted the first TaskTree.",
                      "roots": [
                        {
                          "title": "Plan structure",
                          "intent": "Plan the website structure.",
                          "required_capability": "general"
                        }
                      ]
                    }
                    """,
                ]
            )
        ),
    )
    try:
        session_id = _create_session(app)
        generate = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/generate",
            body={
                "commandId": "generate-restart",
                "sessionId": session_id,
                "payload": {"prompt": "Build a quiet personal website."},
            },
        )
        first_snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
        assert app.authoring_state_store is not None
        active_before_restart = app.authoring_state_store.get_active(session_id)
    finally:
        app.close()

    restarted = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        recovered_snapshot = _request(
            restarted,
            "GET",
            f"/api/v1/sessions/{session_id}/snapshot",
        )
        publish = _request(
            restarted,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/publish",
            body={
                "commandId": "publish-recovered",
                "sessionId": session_id,
                "payload": {"startImmediately": False},
            },
        )
        assert restarted.authoring_state_store is not None
        active_after_publish = restarted.authoring_state_store.get_active(session_id)
        published_tasks = restarted.task_bus.list_for_session(session_id)
    finally:
        restarted.close()

    assert generate.status == 200
    assert generate.json["ok"] is True
    assert active_before_restart.active_state == "draft_tree"
    assert active_before_restart.active_draft_tree_id is not None
    assert WorkspaceLayout(tmp_path).workspace_authoring_db.is_file()
    assert first_snapshot.json["data"]["taskTree"]["id"] == (
        active_before_restart.active_draft_tree_id
    )
    assert recovered_snapshot.status == 200
    assert recovered_snapshot.json["ok"] is True
    assert recovered_snapshot.json["data"]["taskTree"]["id"] == (
        active_before_restart.active_draft_tree_id
    )
    assert recovered_snapshot.json["data"]["taskTree"]["nodes"][0]["title"] == (
        "Plan structure"
    )
    assert publish.status == 200
    assert publish.json["ok"] is True
    assert {"kind": "draft_tree", "id": active_before_restart.active_draft_tree_id} in (
        publish.json["result"]["objectRefs"]
    )
    assert publish.json["result"]["publishedTaskIds"]
    assert active_after_publish.active_state == "published"
    assert len(published_tasks) == 1


def test_main_page_sidecar_app_writes_frontend_error_log_file(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        session_id = _create_session(app)
        response = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/client-logs/errors",
            body={
                "entry": {
                    "createdAt": "2026-05-22T00:00:00.000Z",
                    "level": "error",
                    "message": "render.failed",
                    "namespace": "app-error-boundary",
                }
            },
        )
        log_path = (
            WorkspaceLayout(tmp_path).session_logs_dir(session_id)
            / "frontend-errors.jsonl"
        )
        rows = [json.loads(line) for line in log_path.read_text().splitlines()]
    finally:
        app.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert rows[0]["sessionId"] == session_id
    assert rows[0]["payload"]["entry"]["message"] == "render.failed"


def test_main_page_task_ref_resolver_prefers_draft_then_published(tmp_path: Any) -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "session-1",
        [
            DraftTaskNode(
                session_id="session-1",
                draft_tree_id="placeholder",
                title="Draft",
                intent="Draft task",
                required_capability="general",
            )
        ],
    )
    draft_id = tree.root_nodes[0].draft_task_id
    task_bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        resolver = MainPageTaskRefResolver(draft_store=draft_store, task_bus=task_bus)

        assert resolver.resolve("session-1", draft_id) == TaskRef.draft(draft_id)
        with pytest.raises(LookupError, match="not found"):
            resolver.resolve("session-1", "missing")
    finally:
        task_bus.close()


@dataclass(frozen=True)
class _HttpResult:
    status: int
    text: str

    @property
    def json(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.text))


class _StubLLM:
    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> _LLMResponse:
        if self._responses:
            return _LLMResponse(self._responses.pop(0))
        return _LLMResponse(
            """
            {
              "intent_summary": "Build a quiet website",
              "feasibility": {
                "status": "ready",
                "confidence": 0.95,
                "suggested_next_action": "generate_task_tree"
              },
              "constraints": ["quiet visual style"]
            }
            """
        )


@dataclass(frozen=True)
class _LLMResponse:
    content: str


def _request(
    app: Any,
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
) -> _HttpResult:
    app.start_in_thread()
    raw_body = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if raw_body is None else {"content-type": "application/json"}
    host, port = app.server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=raw_body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        return _HttpResult(status=response.status, text=raw.decode("utf-8"))
    finally:
        conn.close()


def _create_session(app: Any, name: str = "Demo session") -> str:
    response = _request(app, "POST", "/api/v1/sessions", body={"name": name})
    return cast(str, response.json["data"]["sessionId"])
