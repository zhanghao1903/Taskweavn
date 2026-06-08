"""Acceptance tests for Collaborator workspace context dispatch through sidecar."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
from typing import Any, cast

from taskweavn.llm import ChatRequest, ChatResponse, LLMClient, ProviderCapabilities, ToolCall
from taskweavn.server import (
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    build_main_page_sidecar_app,
)


class _ForcedCollaboratorProvider:
    """Provider-shaped deterministic LLM for sidecar acceptance checks."""

    name = "forced_collaborator_acceptance_provider"
    capabilities = ProviderCapabilities(chat=True, tool_calls=True)

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        call_number = len(self.requests)
        if call_number == 1:
            return _tool_response(
                "authoring_read_workspace",
                {
                    "paths": ["README.md"],
                    "purpose": "Read workspace entry guidance before authoring.",
                    "max_snippet_chars": 200,
                },
                call_id="forced-read-1",
            )
        if call_number == 2:
            return _tool_response(
                "authoring_search_workspace",
                {
                    "query": "workspace-informed authoring",
                    "scope": {"path_globs": ["docs/plans/**"]},
                    "purpose": "Search accepted plan guidance before finishing.",
                    "max_results": 5,
                    "max_snippet_chars": 200,
                },
                call_id="forced-search-1",
            )
        if call_number == 3:
            return _tool_response(
                "finish_authoring",
                {
                    "proposal_kind": "raw_task",
                    "proposal": {
                        "kind": "raw_task",
                        "intent_summary": "Use workspace-informed authoring guidance",
                        "feasibility": {
                            "status": "ready",
                            "confidence": 0.91,
                            "reasons": ["README and plan evidence were available."],
                        },
                        "constraints": ["read-only collaborator context"],
                        "assumptions": ["workspace guidance is sufficient"],
                    },
                },
                call_id="forced-finish-1",
            )
        raise AssertionError(f"unexpected provider call {call_number}")

    def complete(self, request: object) -> object:
        raise NotImplementedError

    def count_tokens(self, request: object) -> int:
        return 0


def test_collaborator_sidecar_acceptance_forced_read_search_finish(
    tmp_path: Path,
) -> None:
    _seed_workspace_guidance(tmp_path)
    provider = _ForcedCollaboratorProvider()
    llm = LLMClient(
        model="forced/collaborator-acceptance",
        api_key="test-key",
        provider=provider,
    )
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=tmp_path,
            port=0,
            enable_default_agent=False,
            enable_execution_dispatcher=False,
        ),
        MainPageSidecarDependencies(llm=llm),
    )
    try:
        session_id = _create_session(app)
        command_status, command_text, command = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/input",
            body={
                "commandId": "command-collaborator-sidecar-acceptance",
                "sessionId": session_id,
                "payload": {
                    "content": "Plan this feature using workspace guidance.",
                    "mode": "global_guidance",
                },
            },
        )
        snapshot_status, snapshot_text, snapshot = _request(
            app,
            "GET",
            f"/api/v1/sessions/{session_id}/snapshot",
        )
        raw_tasks = app.raw_task_store.list_for_session(session_id)
    finally:
        app.close()

    tool_names = {
        tool["function"]["name"]
        for tool in (provider.requests[0].tools or [])
    }
    second_messages = json.dumps(provider.requests[1].messages, ensure_ascii=False)
    third_messages = json.dumps(provider.requests[2].messages, ensure_ascii=False)

    assert command_status == 200
    assert command["ok"] is True, command_text
    assert command["result"]["status"] == "accepted", command_text
    assert snapshot_status == 200
    assert snapshot["data"]["session"]["status"] == "understanding", snapshot_text
    assert len(raw_tasks) == 1
    assert raw_tasks[0].intent_summary == "Use workspace-informed authoring guidance"
    assert raw_tasks[0].status == "ready_to_plan"
    assert len(provider.requests) == 3
    assert tool_names == {
        "authoring_read_workspace",
        "authoring_search_workspace",
        "finish_authoring",
    }
    assert not {"write_file", "run_command", "shell", "execute_code"} & tool_names
    assert "workspace://current/README.md" in second_messages
    assert "workspace-informed authoring" in third_messages
    assert "workspace://current/docs/plans/feature.md" in third_messages
    assert str(tmp_path) not in second_messages
    assert str(tmp_path) not in third_messages
    assert str(tmp_path) not in snapshot_text
    assert ".taskweavn/secret" not in second_messages
    assert ".taskweavn/secret" not in third_messages


def _seed_workspace_guidance(workspace: Path) -> None:
    (workspace / "README.md").write_text(
        "This workspace requires workspace-informed authoring before task planning.\n",
        encoding="utf-8",
    )
    (workspace / "docs" / "plans").mkdir(parents=True)
    (workspace / "docs" / "plans" / "feature.md").write_text(
        "Accepted plan: collaborator should use workspace-informed authoring evidence.\n",
        encoding="utf-8",
    )
    (workspace / ".taskweavn").mkdir()
    (workspace / ".taskweavn" / "secret.txt").write_text(
        "must not be read",
        encoding="utf-8",
    )


def _tool_response(
    name: str,
    arguments: dict[str, Any],
    *,
    call_id: str,
) -> ChatResponse:
    raw_arguments = json.dumps(arguments)
    return ChatResponse(
        content="",
        tool_calls=[ToolCall(id=call_id, name=name, arguments=raw_arguments)],
        raw_assistant_message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": raw_arguments},
                }
            ],
        },
        provider_name="forced_collaborator_acceptance_provider",
        provider_request_id=call_id,
    )


def _create_session(app: Any) -> str:
    status, text, response = _request(
        app,
        "POST",
        "/api/v1/sessions",
        body={"name": "Collaborator sidecar acceptance"},
    )
    assert status == 200, text
    return cast(str, response["data"]["sessionId"])


def _request(
    app: Any,
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
) -> tuple[int, str, dict[str, Any]]:
    app.start_in_thread()
    raw_body = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if raw_body is None else {"content-type": "application/json"}
    host, port = app.server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=raw_body, headers=headers)
        response = conn.getresponse()
        text = response.read().decode("utf-8")
        parsed = json.loads(text) if text else {}
        return response.status, text, cast(dict[str, Any], parsed)
    finally:
        conn.close()
