"""Tests for execution web fetch provider and tool integration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from taskweavn.core import SqliteEventStream, WorkspaceLayout
from taskweavn.core.loop import FINISH_TOOL_NAME
from taskweavn.llm.contracts import ChatResponse, ToolCall
from taskweavn.server.main_page_agent import build_agent_loop_resident_default_agent
from taskweavn.server.settings_config import FileSettingsConfigStore
from taskweavn.task import InMemoryTaskBus, TaskDomain
from taskweavn.tools import WebFetchAction, WebFetchObservation, WebFetchTool
from taskweavn.web_retrieval import (
    TavilyWebFetchProvider,
    WebFetchFailedResult,
    WebFetchRequest,
    WebFetchResponse,
    WebFetchResult,
)
from taskweavn.web_retrieval.url_policy import (
    WebFetchUrlPolicyError,
    normalize_public_fetch_urls,
)

NOW = datetime(2026, 6, 14, 0, 0, tzinfo=UTC)


class _FakeFetchProvider:
    provider = "fake"

    def __init__(self) -> None:
        self.requests: list[WebFetchRequest] = []

    def fetch(self, request: WebFetchRequest) -> WebFetchResponse:
        self.requests.append(request)
        return WebFetchResponse(
            provider=self.provider,
            urls=request.urls,
            results=(
                WebFetchResult(
                    url=request.urls[0],
                    title="Tavily Extract",
                    content="Extracted source text.",
                    content_hash="hash-1",
                    chars=22,
                    source=self.provider,
                ),
            ),
            failed_results=(),
            retrieved_at=NOW,
        )


class _StubLLM:
    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = iter(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append({"messages": messages, "tools": tools, "metadata": metadata})
        return next(self._responses)


def test_tavily_fetch_provider_normalizes_extract_response() -> None:
    seen_request: dict[str, Any] = {}

    def transport(
        endpoint: str,
        payload: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        seen_request.update(
            {
                "endpoint": endpoint,
                "headers": dict(headers),
                "payload": json.loads(payload.decode("utf-8")),
                "timeout": timeout_seconds,
            }
        )
        return (
            200,
            json.dumps(
                {
                    "results": [
                        {
                            "url": "https://docs.tavily.com/documentation/api-reference/endpoint/extract",
                            "title": "Extract API",
                            "raw_content": "Extracted markdown body.",
                        }
                    ],
                    "failed_results": [
                        {
                            "url": "https://example.com/missing",
                            "error": "not_found",
                            "message": "not found",
                        }
                    ],
                }
            ).encode("utf-8"),
        )

    provider = TavilyWebFetchProvider(api_key="tvly-secret", transport=transport)

    response = provider.fetch(
        WebFetchRequest(
            urls=("https://docs.tavily.com/documentation/api-reference/endpoint/extract",),
            query="credits",
            max_chars_per_url=12000,
            max_total_chars=24000,
        )
    )

    assert seen_request["payload"] == {
        "urls": ["https://docs.tavily.com/documentation/api-reference/endpoint/extract"],
        "extract_depth": "basic",
        "format": "markdown",
        "include_images": False,
        "query": "credits",
        "chunks_per_source": 3,
    }
    assert seen_request["headers"]["Authorization"] == "Bearer tvly-secret"
    assert response.provider == "tavily"
    assert response.results[0].title == "Extract API"
    assert response.results[0].content == "Extracted markdown body."
    assert response.results[0].content_hash is not None
    assert response.failed_results == (
        WebFetchFailedResult(
            url="https://example.com/missing",
            error_code="not_found",
            message="not found",
        ),
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://10.0.0.1/",
        "http://[::1]/",
        "https://printer.local/status",
        "https://user:password@example.com/private",
    ],
)
def test_web_fetch_url_policy_rejects_non_public_targets(url: str) -> None:
    with pytest.raises(WebFetchUrlPolicyError):
        normalize_public_fetch_urls((url,))


def test_web_fetch_tool_returns_bounded_external_evidence_observation() -> None:
    provider = _FakeFetchProvider()
    action = WebFetchAction(
        urls=(
            "https://docs.tavily.com/documentation/api-reference/endpoint/extract#response",
        ),
        query="extract API",
    )

    observation = WebFetchTool(provider, default_max_urls=3).execute(action)

    assert provider.requests[0].urls == (
        "https://docs.tavily.com/documentation/api-reference/endpoint/extract",
    )
    assert provider.requests[0].query == "extract API"
    assert isinstance(observation, WebFetchObservation)
    assert observation.action_id == action.event_id
    assert observation.provider == "fake"
    assert observation.summary["resultCount"] == 1
    assert observation.results[0]["content"] == "Extracted source text."


def test_default_agent_registers_web_fetch_only_when_settings_ready(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout(tmp_path)
    store = FileSettingsConfigStore(tmp_path)
    store.write_config(
        {
            "webSearch": {
                "enabled": True,
                "provider": "tavily",
                "mode": "basic",
                "maxResults": 4,
                "fetchEnabled": True,
                "fetchMaxUrls": 2,
                "fetchMaxCharsPerUrl": 6000,
                "fetchMaxTotalChars": 12000,
            }
        }
    )
    store.write_web_search_secret(
        provider="tavily",
        api_key="tvly-stored-secret",
        updated_at=NOW,
    )
    task = TaskDomain(
        task_id="task-1",
        session_id="session-1",
        root_id="task-1",
        intent="Read current Tavily Extract docs.",
        required_capability="general",
        claimed_by="default_agent",
        created_by="tester",
    )
    llm = _StubLLM(
        [
            _tool_response(
                "web_fetch",
                {
                    "urls": [
                        "https://docs.tavily.com/documentation/api-reference/endpoint/extract"
                    ],
                    "query": "extract endpoint",
                },
                call_id="fetch-1",
            ),
            _finish_response("Used extracted source content."),
        ]
    )
    provider = _FakeFetchProvider()
    agent = build_agent_loop_resident_default_agent(
        layout=layout,
        llm=llm,
        task_bus=InMemoryTaskBus([task]),
        settings_store=store,
        settings_env={},
        web_fetch_provider=provider,
    )

    result = agent.run(task)

    assert result.ok
    assert provider.requests[0].max_chars_per_url == 6000
    assert provider.requests[0].max_total_chars == 12000
    tool_names = {tool["function"]["name"] for tool in llm.calls[0]["tools"] or []}
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names
    context_text = "\n".join(
        str(message.get("content", "")) for message in llm.calls[0]["messages"]
    )
    assert "Treat web_fetch page content as external evidence" in context_text
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        observations = [
            event
            for event in stream.iter_for_task("task-1")
            if isinstance(event, WebFetchObservation)
        ]
    assert len(observations) == 1
    assert observations[0].urls == [
        "https://docs.tavily.com/documentation/api-reference/endpoint/extract"
    ]


def test_default_agent_omits_web_fetch_when_fetch_toggle_disabled(
    tmp_path: Path,
) -> None:
    store = FileSettingsConfigStore(tmp_path)
    store.write_config(
        {
            "webSearch": {
                "enabled": True,
                "provider": "tavily",
                "mode": "basic",
                "maxResults": 4,
                "fetchEnabled": False,
            }
        }
    )
    store.write_web_search_secret(
        provider="tavily",
        api_key="tvly-stored-secret",
        updated_at=NOW,
    )
    task = TaskDomain(
        task_id="task-1",
        session_id="session-1",
        root_id="task-1",
        intent="Finish.",
        required_capability="general",
        claimed_by="default_agent",
        created_by="tester",
    )
    llm = _StubLLM([_finish_response("done")])
    agent = build_agent_loop_resident_default_agent(
        layout=WorkspaceLayout(tmp_path),
        llm=llm,
        task_bus=InMemoryTaskBus([task]),
        settings_store=store,
        settings_env={},
        web_fetch_provider=_FakeFetchProvider(),
    )

    result = agent.run(task)

    assert result.ok
    tool_names = {tool["function"]["name"] for tool in llm.calls[0]["tools"] or []}
    assert "web_search" in tool_names
    assert "web_fetch" not in tool_names


def _tool_response(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    call_id: str,
) -> ChatResponse:
    args = json.dumps(arguments)
    return ChatResponse(
        content="",
        raw_assistant_message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": args},
                }
            ],
        },
        tool_calls=[ToolCall(id=call_id, name=tool_name, arguments=args)],
    )


def _finish_response(answer: str) -> ChatResponse:
    return _tool_response(FINISH_TOOL_NAME, {"final_answer": answer}, call_id="finish-1")
