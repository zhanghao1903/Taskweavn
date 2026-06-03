"""LiteLLM provider preserving TaskWeavn's legacy chat behavior."""

from __future__ import annotations

from typing import Any

import litellm

from taskweavn.llm.contracts import ChatRequest, ChatResponse, ProviderCapabilities, RetryPolicy
from taskweavn.llm.logging import log_llm_request, log_llm_response
from taskweavn.llm.providers._openai_compat import parse_openai_compatible_response
from taskweavn.llm.retry import BaseLLMProvider


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
        if request.timeout_seconds is not None:
            kwargs["timeout"] = request.timeout_seconds

        response = litellm.completion(**kwargs)
        parsed = parse_openai_compatible_response(response, provider_name=self.name)
        _log_response(parsed, request)
        return parsed


def _log_request(provider: str, request: ChatRequest) -> None:
    log_llm_request(provider, request)


def _log_response(response: ChatResponse, request: ChatRequest) -> None:
    log_llm_response(response, request=request, provider=response.provider_name or "litellm")


__all__ = ["LiteLLMProvider"]
