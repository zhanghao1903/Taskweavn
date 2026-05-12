"""DeepSeek provider with thinking-mode support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    ErrorClassification,
    ProviderCapabilities,
    RetryPolicy,
)
from taskweavn.llm.errors import LLMCapabilityError
from taskweavn.llm.providers._openai_compat import parse_openai_compatible_response
from taskweavn.llm.retry import BaseLLMProvider
from taskweavn.observability.setup import get_channel_logger

_LLM_LOGGER = get_channel_logger("llm")
_DEFAULT_BASE_URL = "https://api.deepseek.com"


@dataclass(frozen=True)
class DeepSeekModelProfile:
    tool_calls: bool
    thinking: bool
    reasoning_content_input: bool


_MODEL_PROFILES: dict[str, DeepSeekModelProfile] = {
    "deepseek-chat": DeepSeekModelProfile(
        tool_calls=True,
        thinking=False,
        reasoning_content_input=False,
    ),
    "deepseek-reasoner": DeepSeekModelProfile(
        tool_calls=False,
        thinking=True,
        reasoning_content_input=False,
    ),
    "deepseek-v4-pro": DeepSeekModelProfile(
        tool_calls=True,
        thinking=True,
        reasoning_content_input=True,
    ),
}


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek provider using the OpenAI-compatible SDK path."""

    name = "deepseek"
    capabilities = ProviderCapabilities(
        chat=True,
        tool_calls=True,
        thinking=True,
        reasoning_content_output=True,
        reasoning_content_input=True,
    )

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        client: Any | None = None,
        client_factory: Callable[..., Any] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(retry_policy=retry_policy)
        self._api_key = api_key
        self._base_url = base_url
        self._client = client
        self._client_factory = client_factory

    def _chat_once(self, request: ChatRequest) -> ChatResponse:
        profile = _profile_for_model(request.model)
        thinking_enabled = bool(request.thinking and request.thinking.enabled)
        if request.tools and not profile.tool_calls:
            raise LLMCapabilityError(
                f"DeepSeek model {request.model!r} does not support tool calls",
                provider_name=self.name,
                model=request.model,
                classification=ErrorClassification.FATAL_CAPABILITY,
            )
        if thinking_enabled and not profile.thinking:
            raise LLMCapabilityError(
                f"DeepSeek model {request.model!r} does not support thinking mode",
                provider_name=self.name,
                model=request.model,
                classification=ErrorClassification.FATAL_CAPABILITY,
            )

        messages = _normalize_messages(
            request.messages,
            allow_reasoning_content_input=profile.reasoning_content_input,
        )
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "tools": request.tools,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if thinking_enabled:
            assert request.thinking is not None
            kwargs["reasoning_effort"] = request.thinking.effort
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        elif profile.thinking:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        elif request.temperature is not None:
            kwargs["temperature"] = request.temperature

        _LLM_LOGGER.info(
            "request",
            extra={
                "data": {
                    "provider": self.name,
                    "model": request.model,
                    "message_count": len(messages),
                    "tool_count": len(request.tools) if request.tools else 0,
                    "thinking_enabled": thinking_enabled,
                    "thinking_effort": request.thinking.effort if request.thinking else None,
                }
            },
        )
        response = self._client_for_call().chat.completions.create(**kwargs)
        parsed = parse_openai_compatible_response(response, provider_name=self.name)
        _LLM_LOGGER.info(
            "response",
            extra={
                "data": {
                    "provider": self.name,
                    "model": request.model,
                    "has_reasoning_content": parsed.reasoning_content is not None,
                    "retry_count": parsed.retry_count,
                    "tool_calls": [{"id": tc.id, "name": tc.name} for tc in parsed.tool_calls],
                }
            },
        )
        return parsed

    def _client_for_call(self) -> Any:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            self._client = self._client_factory(api_key=self._api_key, base_url=self._base_url)
            return self._client

        from openai import OpenAI

        self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client


def _profile_for_model(model: str) -> DeepSeekModelProfile:
    if model in _MODEL_PROFILES:
        return _MODEL_PROFILES[model]
    if "reasoner" in model:
        return _MODEL_PROFILES["deepseek-reasoner"]
    if "v4" in model or "thinking" in model:
        return _MODEL_PROFILES["deepseek-v4-pro"]
    return _MODEL_PROFILES["deepseek-chat"]


def _normalize_messages(
    messages: list[dict[str, Any]],
    *,
    allow_reasoning_content_input: bool,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        copy = dict(message)
        if not allow_reasoning_content_input:
            copy.pop("reasoning_content", None)
        normalized.append(copy)
    return normalized


__all__ = ["DeepSeekProvider", "DeepSeekModelProfile"]
