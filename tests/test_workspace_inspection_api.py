"""Contract tests for Product 1.1 workspace inspection routes."""

from __future__ import annotations

import http.client
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

from taskweavn.core import WorkspaceLayout
from taskweavn.server import (
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    WorkspaceRegistryEntry,
    build_main_page_sidecar_app,
)


def test_workspace_inspection_status_diff_and_file_are_workspace_scoped(
    tmp_path: Path,
) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    _seed_git_workspace(workspace_a, "alpha")
    _seed_git_workspace(workspace_b, "bravo")
    (workspace_a / "app.txt").write_text("alpha\nchanged in workspace a\n", encoding="utf-8")
    (workspace_b / "app.txt").write_text("bravo\nchanged in workspace b\n", encoding="utf-8")

    app = _multi_workspace_app(workspace_a, workspace_b)
    try:
        status_a = _request(app, "GET", "/api/v1/workspaces/ws-a/inspection/status")
        status_b = _request(app, "GET", "/api/v1/workspaces/ws-b/inspection/status")
        diff_a = _request(
            app,
            "GET",
            "/api/v1/workspaces/ws-a/inspection/diff?"
            + urlencode({"path": "app.txt"}),
        )
        file_a = _request(
            app,
            "GET",
            "/api/v1/workspaces/ws-a/files/content?"
            + urlencode({"path": "app.txt", "lineCount": "10"}),
        )
    finally:
        app.close()

    assert status_a.status == 200
    assert status_b.status == 200
    assert status_a.json["data"]["workspaceId"] == "ws-a"
    assert status_b.json["data"]["workspaceId"] == "ws-b"
    assert status_a.json["data"]["repository"]["status"] == "dirty"
    assert status_a.json["data"]["files"][0]["pathLabel"] == "workspace://ws-a/app.txt"
    assert status_b.json["data"]["files"][0]["pathLabel"] == "workspace://ws-b/app.txt"
    assert diff_a.status == 200
    assert diff_a.json["data"]["isAvailable"] is True
    assert diff_a.json["data"]["file"]["pathLabel"] == "workspace://ws-a/app.txt"
    assert "changed in workspace a" in diff_a.text
    assert "changed in workspace b" not in diff_a.text
    assert file_a.status == 200
    assert file_a.json["data"]["content"]["lines"][1]["text"] == "changed in workspace a"
    assert str(workspace_a) not in status_a.text + diff_a.text + file_a.text
    assert str(workspace_b) not in status_a.text + diff_a.text + file_a.text
    assert ".plato" not in status_a.text


def test_workspace_inspection_non_git_status_is_safe(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app = _single_workspace_app(workspace)
    try:
        response = _request(app, "GET", "/api/v1/inspection/status")
    finally:
        app.close()

    assert response.status == 200
    assert response.json["data"]["workspaceId"] == "current"
    assert response.json["data"]["repository"]["status"] == "not_git"
    assert response.json["data"]["files"] == []
    assert str(workspace) not in response.text


def test_workspace_inspection_rejects_private_metadata_and_traversal(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _seed_git_workspace(workspace, "alpha")
    app = _single_workspace_app(workspace)
    try:
        protected = _request(
            app,
            "GET",
            "/api/v1/files/content?" + urlencode({"path": ".plato/workspace.sqlite"}),
        )
        traversal = _request(
            app,
            "GET",
            "/api/v1/files/content?" + urlencode({"path": "../secret.txt"}),
        )
    finally:
        app.close()

    assert protected.status == 400
    assert traversal.status == 400
    assert protected.json["error"]["details"]["product_error_category"] == (
        "input_validation"
    )
    assert traversal.json["error"]["details"]["recovery_actions"] == [
        "edit_input",
        "open_audit",
    ]
    assert str(workspace) not in protected.text + traversal.text


def test_workspace_inspection_captures_file_evidence_in_dedicated_store(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _seed_git_workspace(workspace, "alpha")
    (workspace / "app.txt").write_text("alpha\ncaptured line\n", encoding="utf-8")

    app = _single_workspace_app(workspace)
    try:
        capture = _request(
            app,
            "POST",
            "/api/v1/inspection/evidence",
            body={
                "kind": "file_snapshot",
                "reason": "audit_record",
                "path": "app.txt",
                "lineRange": {"startLine": 1, "lineCount": 5},
            },
        )
        evidence_id = capture.json["data"]["evidenceRef"]["evidenceId"]
        captured_file = _request(
            app,
            "GET",
            "/api/v1/files/content?" + urlencode({"evidenceId": evidence_id}),
        )
    finally:
        app.close()

    assert capture.status == 200
    assert capture.json["data"]["evidenceRef"]["kind"] == "file_snapshot"
    assert capture.json["data"]["descriptor"]["pathLabel"] == "workspace://current/app.txt"
    assert WorkspaceLayout(workspace).workspace_inspection_db.is_file()
    assert captured_file.status == 200
    assert captured_file.json["data"]["source"] == "captured_evidence"
    assert captured_file.json["data"]["evidenceRef"]["evidenceId"] == evidence_id
    assert captured_file.json["data"]["content"]["lines"][1]["text"] == "captured line"
    assert str(workspace) not in capture.text + captured_file.text


def _single_workspace_app(workspace: Path) -> Any:
    return build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace,
            port=0,
            enable_default_agent=False,
            enable_execution_dispatcher=False,
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )


def _multi_workspace_app(workspace_a: Path, workspace_b: Path) -> Any:
    return build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace_a,
            port=0,
            enable_default_agent=False,
            enable_execution_dispatcher=False,
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


def _seed_git_workspace(workspace: Path, initial_text: str) -> None:
    workspace.mkdir(parents=True)
    (workspace / "app.txt").write_text(f"{initial_text}\n", encoding="utf-8")
    _git(workspace, "init")
    _git(workspace, "config", "user.email", "plato@example.invalid")
    _git(workspace, "config", "user.name", "Plato Test")
    _git(workspace, "add", "app.txt")
    _git(workspace, "commit", "-m", "initial")


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=True,
        capture_output=True,
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
        return _LLMResponse("{}")


@dataclass(frozen=True)
class _LLMResponse:
    content: str
