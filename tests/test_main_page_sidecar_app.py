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


def test_build_main_page_sidecar_app_creates_session_and_serves_empty_snapshot(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=tmp_path,
            session_name="Demo session",
            port=0,
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        response = _request(app, "GET", f"/api/v1/sessions/{app.session.id}/snapshot")
    finally:
        app.close()

    assert app.session.name == "Demo session"
    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["session"]["id"] == app.session.id
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
        assert app.session.id == session.id
        assert app.session.name == "Existing"
    finally:
        app.close()


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
        command = _request(
            app,
            "POST",
            f"/api/v1/sessions/{app.session.id}/input",
            body={
                "commandId": "command-1",
                "sessionId": app.session.id,
                "payload": {
                    "content": "Build a quiet personal website.",
                    "mode": "global_guidance",
                },
            },
        )
        snapshot = _request(app, "GET", f"/api/v1/sessions/{app.session.id}/snapshot")
        raw_tasks = app.raw_task_store.list_for_session(app.session.id)
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
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> _LLMResponse:
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
