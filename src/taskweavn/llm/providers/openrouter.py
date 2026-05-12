"""OpenRouter provider with explicit provider routing support."""

from __future__ import annotations

from typing import Any

import litellm

from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    ProviderCapabilities,
    ProviderRoutingConfig,
    RetryPolicy,
)
from taskweavn.llm.providers._openai_compat import parse_openai_compatible_response
from taskweavn.llm.retry import BaseLLMProvider
from taskweavn.observability.setup import get_channel_logger

_LLM_LOGGER = get_channel_logger("llm")


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter chat provider.

    First version keeps transport through LiteLLM while making the provider
    routing body explicit and testable.
    """

    name = "openrouter"
    capabilities = ProviderCapabilities(
        chat=True,
        tool_calls=True,
        provider_routing=True,
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        provider_routing: ProviderRoutingConfig | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(retry_policy=retry_policy)
        self._api_key = api_key
        self._provider_routing = provider_routing

    def _chat_once(self, request: ChatRequest) -> ChatResponse:
        routing = request.provider_routing or self._provider_routing
        extra_body = _extra_body(routing)
        _LLM_LOGGER.info(
            "request",
            extra={
                "data": {
                    "provider": self.name,
                    "model": request.model,
                    "message_count": len(request.messages),
                    "tool_count": len(request.tools) if request.tools else 0,
                    "provider_routing": extra_body.get("provider"),
                }
            },
        )
        kwargs: dict[str, Any] = {
            "model": request.model,
            "api_key": self._api_key,
            "messages": request.messages,
            "tools": request.tools,
        }
        if extra_body:
            kwargs["extra_body"] = extra_body

        response = litellm.completion(**kwargs)
        parsed = parse_openai_compatible_response(response, provider_name=self.name)
        _LLM_LOGGER.info(
            "response",
            extra={
                "data": {
                    "provider": self.name,
                    "model": request.model,
                    "retry_count": parsed.retry_count,
                    "provider_routing": extra_body.get("provider"),
                    "tool_calls": [{"id": tc.id, "name": tc.name} for tc in parsed.tool_calls],
                }
            },
        )
        return parsed


def _extra_body(routing: ProviderRoutingConfig | None) -> dict[str, Any]:
    if routing is None:
        return {}
    provider_payload = routing.to_openrouter_dict()
    return {"provider": provider_payload} if provider_payload else {}


__all__ = ["OpenRouterProvider"]
