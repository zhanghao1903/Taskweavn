"""Provider contract model tests."""

from __future__ import annotations

import pytest

from taskweavn.llm import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderRoutingConfig,
    RetryPolicy,
    ThinkingConfig,
    ToolCall,
)
from taskweavn.llm.providers.litellm import LiteLLMProvider


def test_provider_protocol_conformance() -> None:
    provider = LiteLLMProvider(api_key="sk")
    assert isinstance(provider, LLMProvider)


def test_chat_response_preserves_legacy_fields() -> None:
    response = ChatResponse(
        content="hello",
        tool_calls=[ToolCall(id="c1", name="read_file", arguments="{}")],
        raw_assistant_message={"role": "assistant", "content": "hello"},
    )
    assert response.content == "hello"
    assert response.tool_calls[0].name == "read_file"
    assert response.raw_assistant_message["role"] == "assistant"
    assert response.retry_count == 0


def test_thinking_config_validates_effort() -> None:
    assert ThinkingConfig(enabled=True, effort="max").effort == "max"
    with pytest.raises(ValueError, match="effort"):
        ThinkingConfig(enabled=True, effort="medium")


def test_provider_routing_openrouter_payload_omits_empty_fields() -> None:
    routing = ProviderRoutingConfig(
        only=("deepinfra/turbo",),
        order=("deepinfra/turbo",),
        allow_fallbacks=False,
        require_parameters=True,
        data_collection="deny",
    )
    assert routing.to_openrouter_dict() == {
        "allow_fallbacks": False,
        "require_parameters": True,
        "order": ["deepinfra/turbo"],
        "only": ["deepinfra/turbo"],
        "data_collection": "deny",
    }


def test_provider_routing_rejects_bad_data_collection() -> None:
    with pytest.raises(ValueError, match="data_collection"):
        ProviderRoutingConfig(data_collection="maybe")


def test_retry_policy_validation() -> None:
    assert RetryPolicy(max_attempts=1).max_attempts == 1
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="max_delay_seconds"):
        RetryPolicy(initial_delay_seconds=2, max_delay_seconds=1)


def test_chat_request_rejects_unknown_field() -> None:
    with pytest.raises(ValueError):
        ChatRequest(model="m", messages=[], extra_field=True)  # type: ignore[call-arg]


def test_chat_request_validates_timeout_seconds() -> None:
    assert ChatRequest(model="m", messages=[], timeout_seconds=1.5).timeout_seconds == 1.5
    with pytest.raises(ValueError, match="timeout_seconds"):
        ChatRequest(model="m", messages=[], timeout_seconds=0)
