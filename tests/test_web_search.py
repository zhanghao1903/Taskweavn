"""Tests for execution web search provider and tool integration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskweavn.core import SqliteEventStream, WorkspaceLayout
from taskweavn.core.loop import FINISH_TOOL_NAME
from taskweavn.llm.contracts import ChatResponse, ToolCall
from taskweavn.server.main_page_agent import build_agent_loop_resident_default_agent
from taskweavn.server.settings_config import FileSettingsConfigStore
from taskweavn.task import InMemoryTaskBus, TaskDomain
from taskweavn.tools import WebSearchAction, WebSearchObservation, WebSearchTool
from taskweavn.web_retrieval import (
    TavilyWebSearchProvider,
    WebSearchProviderError,
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
)


class _FakeProvider:
    provider = "fake"

    def __init__(self) -> None:
        self.requests: list[WebSearchRequest] = []

    def search(self, request: WebSearchRequest) -> WebSearchResponse:
        self.requests.append(request)
        return WebSearchResponse(
            provider=self.provider,
            query=request.query,
            results=(
                WebSearchResult(
                    title="Tavily API credits",
                    url="https://docs.tavily.com/documentation/api-credits",
                    snippet="Basic Search costs one API credit.",
                    source=self.provider,
                ),
            ),
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


NOW = datetime(2026, 6, 14, 0, 0, tzinfo=UTC)


def test_tavily_provider_normalizes_bounded_basic_search_response() -> None:
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
                            "title": "DeepSeek docs",
                            "url": "https://api-docs.deepseek.com/",
                            "content": "Current public docs.",
                            "published_date": "2026-06-01",
                        },
                        {
                            "title": "skip invalid",
                            "url": "file:///private",
                            "content": "invalid URL should be ignored",
                        },
                    ]
                }
            ).encode("utf-8"),
        )

    provider = TavilyWebSearchProvider(
        api_key="tvly-secret",
        transport=transport,
    )

    response = provider.search(
        WebSearchRequest(
            query="DeepSeek docs",
            max_results=5,
            include_domains=("api-docs.deepseek.com",),
        )
    )

    assert seen_request["payload"] == {
        "query": "DeepSeek docs",
        "search_depth": "basic",
        "max_results": 5,
        "include_domains": ["api-docs.deepseek.com"],
        "exclude_domains": [],
    }
    assert seen_request["headers"]["Authorization"] == "Bearer tvly-secret"
    assert response.provider == "tavily"
    assert len(response.results) == 1
    assert response.results[0].url == "https://api-docs.deepseek.com/"
    assert response.results[0].published_at == "2026-06-01"


def test_tavily_provider_maps_rate_limit_without_leaking_secret() -> None:
    def transport(
        endpoint: str,
        payload: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        del endpoint, payload, headers, timeout_seconds
        return 429, b'{"error":"rate limit"}'

    provider = TavilyWebSearchProvider(
        api_key="tvly-secret",
        transport=transport,
    )

    try:
        provider.search(WebSearchRequest(query="pricing"))
    except WebSearchProviderError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive test guard.
        raise AssertionError("expected rate-limit error")

    assert "rate limit" in message.lower()
    assert "tvly-secret" not in message


def test_web_search_tool_returns_external_evidence_observation() -> None:
    provider = _FakeProvider()
    action = WebSearchAction(
        query="Tavily credits",
        max_results=3,
        include_domains=("docs.tavily.com",),
    )

    observation = WebSearchTool(provider, default_max_results=5).execute(action)

    assert provider.requests[0].max_results == 3
    assert provider.requests[0].include_domains == ("docs.tavily.com",)
    assert isinstance(observation, WebSearchObservation)
    assert observation.action_id == action.event_id
    assert observation.provider == "fake"
    assert observation.summary["resultCount"] == 1
    assert observation.results[0]["url"] == "https://docs.tavily.com/documentation/api-credits"


def test_default_agent_registers_web_search_only_when_settings_ready(
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
        intent="Find current Tavily API credits.",
        required_capability="general",
        claimed_by="default_agent",
        created_by="tester",
    )
    llm = _StubLLM(
        [
            _tool_response(
                "web_search",
                {"query": "Tavily API credits"},
                call_id="search-1",
            ),
            _finish_response("Used source URLs."),
        ]
    )
    provider = _FakeProvider()
    agent = build_agent_loop_resident_default_agent(
        layout=layout,
        llm=llm,
        task_bus=InMemoryTaskBus([task]),
        settings_store=store,
        settings_env={},
        web_search_provider=provider,
    )

    result = agent.run(task)

    assert result.ok
    assert provider.requests[0].max_results == 4
    tool_names = {tool["function"]["name"] for tool in llm.calls[0]["tools"] or []}
    assert "web_search" in tool_names
    context_text = "\n".join(
        str(message.get("content", "")) for message in llm.calls[0]["messages"]
    )
    assert "Treat web_search results as external evidence" in context_text
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        observations = [
            event
            for event in stream.iter_for_task("task-1")
            if isinstance(event, WebSearchObservation)
        ]
    assert len(observations) == 1
    assert observations[0].query == "Tavily API credits"


def test_default_agent_omits_web_search_when_settings_disabled(tmp_path: Path) -> None:
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
        settings_store=FileSettingsConfigStore(tmp_path),
        settings_env={},
        web_search_provider=_FakeProvider(),
    )

    result = agent.run(task)

    assert result.ok
    tool_names = {tool["function"]["name"] for tool in llm.calls[0]["tools"] or []}
    assert "web_search" not in tool_names


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
