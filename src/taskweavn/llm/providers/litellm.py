"""LiteLLM provider preserving TaskWeavn's legacy chat behavior."""

from __future__ import annotations

from typing import Any

import litellm

from taskweavn.llm.contracts import ChatRequest, ChatResponse, ProviderCapabilities, RetryPolicy
from taskweavn.llm.providers._openai_compat import parse_openai_compatible_response
from taskweavn.llm.retry import BaseLLMProvider
from taskweavn.observability.setup import get_channel_logger

_LLM_LOGGER = get_channel_logger("llm")


class LiteLLMProvider(BaseLLMProvider):
    """Provider wrapper around ``litellm.completion``."""

    name = "litellm"
    capabilities = ProviderCapabilities(chat=True, tool_calls=True)

    def __init__(
        self,
        *,
        api_key: str | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(retry_policy=retry_policy)
        self._api_key = api_key

    def _chat_once(self, request: ChatRequest) -> ChatResponse:
        _log_request(self.name, request)
        kwargs: dict[str, Any] = {
            "model": request.model,
            "api_key": self._api_key,
            "messages": request.messages,
            "tools": request.tools,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        response = litellm.completion(**kwargs)
        parsed = parse_openai_compatible_response(response, provider_name=self.name)
        _log_response(parsed)
        return parsed


def _log_request(provider: str, request: ChatRequest) -> None:
    _LLM_LOGGER.info(
        "request",
        extra={
            "data": {
                "provider": provider,
                "model": request.model,
                "request_purpose": request.metadata.get("request_purpose"),
                "session_id": request.metadata.get("session_id"),
                "task_id": request.metadata.get("task_id"),
                "agent_id": request.metadata.get("agent_id"),
                "message_count": len(request.messages),
                "tool_count": len(request.tools) if request.tools else 0,
                "thinking_enabled": bool(request.thinking and request.thinking.enabled),
            }
        },
    )


def _log_response(response: ChatResponse) -> None:
    _LLM_LOGGER.info(
        "response",
        extra={
            "data": {
                "provider": response.provider_name,
                "content_length": len(response.content),
                "tool_calls": [{"id": tc.id, "name": tc.name} for tc in response.tool_calls],
                "has_reasoning_content": response.reasoning_content is not None,
                "retry_count": response.retry_count,
            }
        },
    )


__all__ = ["LiteLLMProvider"]
