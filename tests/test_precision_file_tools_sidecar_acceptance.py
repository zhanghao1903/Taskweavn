"""Sidecar acceptance coverage for Product 1.1 precision file tools."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from taskweavn.llm.contracts import ChatResponse, ToolCall
from taskweavn.server import (
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    build_main_page_sidecar_app,
)
from taskweavn.task import TaskDomain
from tests.fixtures.sidecar_smoke import request_sidecar


def test_precision_file_mutation_surfaces_in_sidecar_file_summary_and_inspection(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.md"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "plato@example.invalid")
    _git(tmp_path, "config", "user.name", "Plato Test")
    _git(tmp_path, "add", "notes.md")
    _git(tmp_path, "commit", "-m", "seed notes")
    expected_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    llm = _SequencedLLM(
        [
            _tool_call_response(
                "replace_file_range",
                {
                    "operation_id": "precision-smoke-replace-notes",
                    "path": "notes.md",
                    "start_line": 2,
                    "end_line": 2,
                    "replacement_text": "BETA",
                    "expected_content_hash": {
                        "algorithm": "sha256",
                        "value": expected_hash,
                    },
                },
                call_id="call-replace-notes",
            ),
            ChatResponse(
                content="Precision edit completed.",
                tool_calls=[],
                raw_assistant_message={
                    "role": "assistant",
                    "content": "Precision edit completed.",
                },
            ),
        ]
    )
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=llm),
    )
    try:
        session_id = _create_session(app)
        app.task_bus.publish(_published_task("precision-file-task", session_id))

        tick = app.run_fixed_route_tick(session_id)
        snapshot = request_sidecar(
            app,
            "GET",
            f"/api/v1/sessions/{quote(session_id, safe='')}/snapshot",
        )
        file_view = request_sidecar(
            app,
            "GET",
            "/api/v1/workspaces/current/files/content?path=notes.md",
        )
        diff_view = request_sidecar(
            app,
            "GET",
            "/api/v1/workspaces/current/inspection/diff?path=notes.md",
        )
    finally:
        app.close()

    assert tick.status == "completed"
    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
    assert snapshot.status == 200
    file_summary = snapshot.json["data"]["fileChangeSummary"]
    assert file_summary is not None
    assert file_summary["taskNodeId"] == "precision-file-task"
    assert file_summary["changedFiles"][0]["path"] == "notes.md"
    assert file_summary["changedFiles"][0]["changeType"] == "modified"
    assert file_summary["changedFiles"][0]["ownerTaskNodeId"] == (
        "precision-file-task"
    )
    change_summary = file_summary["changedFiles"][0]["summary"]
    assert change_summary.startswith("Modified notes.md lines 2-2 (17 bytes written")
    assert "; evidence " in change_summary
    assert file_view.status == 200
    assert "BETA" in file_view.text
    assert diff_view.status == 200
    assert "BETA" in diff_view.text


def _create_session(app: Any) -> str:
    response = request_sidecar(
        app,
        "POST",
        "/api/v1/sessions",
        body={"name": "Precision smoke"},
    )
    if response.status != 200:
        raise AssertionError(f"session creation failed: {response.text}")
    return cast(str, response.json["data"]["sessionId"])


def _published_task(task_id: str, session_id: str) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id=session_id,
        root_id=task_id,
        intent="Apply a precision file edit.",
        required_capability="general",
        created_by="precision-sidecar-smoke",
    )


class _SequencedLLM:
    def __init__(self, responses: Sequence[ChatResponse]) -> None:
        self._responses = list(responses)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        del messages, tools, metadata
        if not self._responses:
            raise AssertionError("_SequencedLLM ran out of responses")
        return self._responses.pop(0)


def _tool_call_response(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    call_id: str,
) -> ChatResponse:
    raw_arguments = json.dumps(arguments)
    return ChatResponse(
        content="",
        tool_calls=[ToolCall(id=call_id, name=tool_name, arguments=raw_arguments)],
        raw_assistant_message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": raw_arguments,
                    },
                }
            ],
        },
    )


def _git(workspace_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=workspace_root,
        check=True,
        capture_output=True,
    )
