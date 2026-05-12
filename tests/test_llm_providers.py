"""Concrete provider behavior tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from taskweavn.llm import (
    ChatRequest,
    ProviderRoutingConfig,
    ThinkingConfig,
)
from taskweavn.llm.errors import LLMCapabilityError
from taskweavn.llm.providers.deepseek import DeepSeekProvider
from taskweavn.llm.providers.openrouter import OpenRouterProvider


def _fake_response(
    *,
    content: str = "",
    reasoning_content: str | None = None,
    tool_calls: list[dict[str, str]] | None = None,
) -> Any:
    msg = MagicMock()
    msg.content = content
    if reasoning_content is not None:
        msg.reasoning_content = reasoning_content
    else:
        del msg.reasoning_content
    if tool_calls:
        parsed = []
        for tc in tool_calls:
            item = MagicMock()
            item.id = tc["id"]
            item.function.name = tc["name"]
            item.function.arguments = tc["arguments"]
            parsed.append(item)
        msg.tool_calls = parsed
    else:
        msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    response.id = "req-1"
    return response


class _FakeDeepSeekClient:
    def __init__(self, response: Any) -> None:
        self.kwargs: dict[str, Any] | None = None
        self.chat = MagicMock()
        self.chat.completions.create = self._create
        self._response = response

    def _create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self._response


def test_deepseek_thinking_request_and_reasoning_tool_call_preserved() -> None:
    client = _FakeDeepSeekClient(
        _fake_response(
            reasoning_content="internal",
            tool_calls=[{"id": "c1", "name": "read_file", "arguments": "{}"}],
        )
    )
    provider = DeepSeekProvider(api_key="sk", client=client)
    result = provider.chat(
        ChatRequest(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": "read"}],
            tools=[{"type": "function"}],
            thinking=ThinkingConfig(enabled=True, effort="high"),
        )
    )

    assert client.kwargs is not None
    assert client.kwargs["reasoning_effort"] == "high"
    assert client.kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert result.reasoning_content == "internal"
    assert result.raw_assistant_message["reasoning_content"] == "internal"
    assert result.raw_assistant_message["tool_calls"][0]["id"] == "c1"


def test_deepseek_reasoner_rejects_tools_before_network_call() -> None:
    client = _FakeDeepSeekClient(_fake_response(content="never"))
    provider = DeepSeekProvider(api_key="sk", client=client)
    with pytest.raises(LLMCapabilityError, match="does not support tool calls"):
        provider.chat(
            ChatRequest(
                model="deepseek-reasoner",
                messages=[],
                tools=[{"type": "function"}],
            )
        )
    assert client.kwargs is None


def test_deepseek_reasoner_strips_reasoning_content_from_input() -> None:
    client = _FakeDeepSeekClient(_fake_response(content="ok", reasoning_content="r"))
    provider = DeepSeekProvider(api_key="sk", client=client)
    provider.chat(
        ChatRequest(
            model="deepseek-reasoner",
            messages=[
                {"role": "assistant", "content": "x", "reasoning_content": "old"},
            ],
        )
    )
    assert client.kwargs is not None
    assert "reasoning_content" not in client.kwargs["messages"][0]


@patch("taskweavn.llm.providers.openrouter.litellm")
def test_openrouter_provider_routing_is_sent(mock_litellm: MagicMock) -> None:
    mock_litellm.completion.return_value = _fake_response(content="ok")
    provider = OpenRouterProvider(
        api_key="sk",
        provider_routing=ProviderRoutingConfig(
            only=("deepinfra/turbo",),
            order=("deepinfra/turbo",),
            allow_fallbacks=False,
            require_parameters=True,
        ),
    )
    result = provider.chat(ChatRequest(model="deepseek/deepseek-r1", messages=[]))
    assert result.content == "ok"
    mock_litellm.completion.assert_called_once_with(
        model="deepseek/deepseek-r1",
        api_key="sk",
        messages=[],
        tools=None,
        extra_body={
            "provider": {
                "allow_fallbacks": False,
                "require_parameters": True,
                "order": ["deepinfra/turbo"],
                "only": ["deepinfra/turbo"],
            }
        },
    )
