"""Contract tests for multi-workspace sidecar routing."""

from __future__ import annotations

import http.client
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from taskweavn.core import WorkspaceLayout
from taskweavn.server import (
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    WorkspaceRegistryEntry,
    build_main_page_sidecar_app,
)


def test_single_workspace_catalog_uses_safe_current_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "current-workspace"
    _seed_session(workspace, session_id="current-session", name="Current session")

    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace,
            port=0,
            current_workspace_id="current",
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        response = _request(app, "GET", "/api/v1/workspaces")
    finally:
        app.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["currentWorkspaceId"] == "current"
    assert str(workspace) not in response.text
    workspaces = response.json["data"]["workspaces"]
    assert len(workspaces) == 1
    assert workspaces[0]["workspaceId"] == "current"
    assert workspaces[0]["label"] == "current-workspace"
    assert workspaces[0]["status"] == "available"
    assert workspaces[0]["isCurrent"] is True
    assert workspaces[0]["sessionCount"] == 1
    assert workspaces[0]["updatedAt"]
    assert workspaces[0]["recentSessions"] == [
        {
            "id": "current-session",
            "workspaceId": "current",
            "workspaceLabel": "current-workspace",
            "name": "Current session",
            "createdAt": workspaces[0]["recentSessions"][0]["createdAt"],
            "updatedAt": workspaces[0]["recentSessions"][0]["updatedAt"],
            "status": "active",
        }
    ]


def test_multi_workspace_catalog_omits_raw_paths_and_marks_missing(
    tmp_path: Path,
) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    missing_workspace = tmp_path / "missing"
    _seed_session(workspace_a, session_id="shared-session", name="A shared")
    _seed_session(workspace_b, session_id="other-session", name="B other")

    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace_a,
            port=0,
            workspace_registry=(
                WorkspaceRegistryEntry(
                    workspace_id="ws-a",
                    root_path=workspace_a,
                    label="Workspace A",
                    is_current=True,
                ),
                WorkspaceRegistryEntry(
                    workspace_id="ws-b",
                    root_path=workspace_b,
                    label="Workspace B",
                ),
                WorkspaceRegistryEntry(
                    workspace_id="ws-missing",
                    root_path=missing_workspace,
                    label="Missing Workspace",
                ),
            ),
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        response = _request(app, "GET", "/api/v1/workspaces")
    finally:
        app.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["currentWorkspaceId"] == "ws-a"
    assert str(workspace_a) not in response.text
    assert str(workspace_b) not in response.text
    workspaces = {
        workspace["workspaceId"]: workspace
        for workspace in response.json["data"]["workspaces"]
    }
    assert workspaces["ws-a"]["status"] == "available"
    assert workspaces["ws-a"]["sessionCount"] == 1
    assert workspaces["ws-a"]["recentSessions"][0]["workspaceId"] == "ws-a"
    assert workspaces["ws-missing"]["status"] == "unavailable"
    assert workspaces["ws-missing"]["recentSessions"] == []


def test_workspace_scoped_snapshot_routes_duplicate_session_ids(
    tmp_path: Path,
) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    _seed_session(workspace_a, session_id="shared-session", name="A shared")
    _seed_session(workspace_b, session_id="shared-session", name="B shared")

    app = _multi_workspace_app(workspace_a, workspace_b)
    try:
        snapshot_a = _request(
            app,
            "GET",
            "/api/v1/workspaces/ws-a/sessions/shared-session/snapshot",
        )
        snapshot_b = _request(
            app,
            "GET",
            "/api/v1/workspaces/ws-b/sessions/shared-session/snapshot",
        )
        compatibility_snapshot = _request(
            app,
            "GET",
            "/api/v1/sessions/shared-session/snapshot",
        )
    finally:
        app.close()

    assert snapshot_a.status == 200
    assert snapshot_b.status == 200
    assert snapshot_a.json["data"]["session"]["name"] == "A shared"
    assert snapshot_b.json["data"]["session"]["name"] == "B shared"
    assert compatibility_snapshot.json["data"]["session"]["name"] == "A shared"


def test_workspace_scoped_command_writes_to_routed_workspace(
    tmp_path: Path,
) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    _seed_session(workspace_a, session_id="shared-session", name="A shared")
    _seed_session(workspace_b, session_id="shared-session", name="B shared")

    app = _multi_workspace_app(workspace_a, workspace_b)
    try:
        command = _request(
            app,
            "POST",
            "/api/v1/workspaces/ws-b/sessions/shared-session/input",
            body={
                "commandId": "append-ws-b",
                "sessionId": "shared-session",
                "payload": {
                    "content": "Only workspace B should receive this.",
                    "mode": "global_guidance",
                },
            },
        )
        snapshot_a = _request(
            app,
            "GET",
            "/api/v1/workspaces/ws-a/sessions/shared-session/snapshot",
        )
        snapshot_b = _request(
            app,
            "GET",
            "/api/v1/workspaces/ws-b/sessions/shared-session/snapshot",
        )
    finally:
        app.close()

    assert command.status == 200
    assert command.json["ok"] is True
    assert "Only workspace B" not in snapshot_a.text
    assert "Only workspace B" in snapshot_b.text


def test_unknown_workspace_returns_safe_error(
    tmp_path: Path,
) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    _seed_session(workspace_a, session_id="shared-session", name="A shared")
    _seed_session(workspace_b, session_id="shared-session", name="B shared")

    app = _multi_workspace_app(workspace_a, workspace_b)
    try:
        response = _request(
            app,
            "GET",
            "/api/v1/workspaces/ws-missing/sessions/shared-session/snapshot",
        )
    finally:
        app.close()

    assert response.status == 404
    assert response.json["error"]["details"]["product_error_category"] == (
        "workspace_unavailable"
    )
    assert response.json["error"]["details"]["recovery_actions"] == [
        "open_workspace"
    ]
    assert str(workspace_a) not in response.text
    assert str(workspace_b) not in response.text


def _multi_workspace_app(workspace_a: Path, workspace_b: Path) -> Any:
    return build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace_a,
            port=0,
            workspace_registry=(
                WorkspaceRegistryEntry(
                    workspace_id="ws-a",
                    root_path=workspace_a,
                    label="Workspace A",
                    is_current=True,
                ),
                WorkspaceRegistryEntry(
                    workspace_id="ws-b",
                    root_path=workspace_b,
                    label="Workspace B",
                ),
            ),
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )


def _seed_session(workspace_root: Path, *, session_id: str, name: str) -> None:
    layout = WorkspaceLayout(workspace_root)
    layout.bootstrap()
    layout.bootstrap_session(session_id)
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(layout.registry_db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                last_active_at  TEXT NOT NULL,
                status          TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_last_active
                ON sessions(last_active_at DESC);
            """
        )
        conn.execute(
            "INSERT INTO sessions(id, name, created_at, last_active_at, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, name, now, now, "active"),
        )


@dataclass(frozen=True)
class _HttpResult:
    status: int
    text: str

    @property
    def json(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.text))


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


class _StubLLM:
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> object:
        del messages, tools, metadata
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
