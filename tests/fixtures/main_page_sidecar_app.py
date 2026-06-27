"""Shared fixtures for Main Page sidecar app tests."""

from __future__ import annotations

import http.client
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from taskweavn.llm.contracts import ChatResponse, ToolCall
from taskweavn.server import (
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    build_main_page_sidecar_app,
)
from taskweavn.task import TaskDomain, TaskRunResult


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
        self.calls = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> _LLMResponse:
        self.calls += 1
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


class _AgentLoopLLM:
    def __init__(self, final_answer: str) -> None:
        self.final_answer = final_answer
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": list(messages),
                "tools": tools,
                "metadata": metadata,
            }
        )
        return ChatResponse(
            content=self.final_answer,
            tool_calls=[],
            raw_assistant_message={
                "role": "assistant",
                "content": self.final_answer,
            },
        )


class _AgentLoopSequencedLLM:
    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": list(messages),
                "tools": tools,
                "metadata": metadata,
            }
        )
        if not self._responses:
            raise AssertionError("_AgentLoopSequencedLLM ran out of responses")
        return self._responses.pop(0)


def _agent_loop_tool_call_response(
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


@dataclass
class _FakeDefaultAgent:
    result: TaskRunResult
    seen: list[str] | None = None

    def run(self, task: TaskDomain) -> TaskRunResult:
        if self.seen is None:
            self.seen = []
        self.seen.append(task.task_id)
        return self.result


@dataclass(frozen=True)
class _LLMResponse:
    content: str


def _build_stubbed_sidecar_app(
    workspace_root: Any,
    *,
    llm: Any | None = None,
    **config_kwargs: Any,
) -> Any:
    config_values = {
        "workspace_root": workspace_root,
        "port": 0,
        **config_kwargs,
    }
    return build_main_page_sidecar_app(
        MainPageSidecarConfig(**config_values),
        MainPageSidecarDependencies(llm=_StubLLM() if llm is None else llm),
    )


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


def _read_jsonl(path: Any) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _computer_use_task_request(
    *,
    session_id: str,
    idempotency_key: str,
) -> dict[str, object]:
    return {
        "idempotencyKey": idempotency_key,
        "requester": {"kind": "test", "id": "computer-use-test"},
        "externalRef": {
            "system": "test",
            "kind": "computer_use",
            "id": idempotency_key,
        },
        "taskType": "desktop.demo.computer_use",
        "intent": "Use local computer-use to inspect desktop state.",
        "input": {
            "summary": "Observe local desktop.",
            "instructions": "Use computer_use observe once, then finish.",
        },
        "policy": {
            "requiredCapability": "computer_use",
            "allowedTools": ["computer_use"],
            "riskLevel": "high",
        },
        "metadata": {"sessionId": session_id},
    }


def _published_task(task_id: str, *, session_id: str) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id=session_id,
        root_id=task_id,
        intent=f"Run {task_id}",
        required_capability="general",
        created_by="test",
    )


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _first_task_status(app: Any, session_id: str) -> str | None:
    tasks = app.task_bus.list_for_session(session_id)
    return None if not tasks else tasks[0].status
