"""LLMClient facade over provider-backed chat and legacy OpenHands completion.

The facade preserves the original ``LLMClient.chat(messages, tools)`` shape
while delegating transport to an ``LLMProvider``. ``complete`` and token
counting still use OpenHands SDK for compatibility until providers grow those
capabilities directly.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from openhands.sdk import LLM
from openhands.sdk.llm import LLMResponse, Message
from openhands.sdk.tool import ToolDefinition

from taskweavn.llm.config import (
    DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
    load_client_config_from_env,
)
from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    LLMProvider,
    ProviderRoutingConfig,
    RetryPolicy,
    ThinkingConfig,
    ToolCall,
)
from taskweavn.llm.providers.litellm import LiteLLMProvider


class LLMClient:
    """Configuration + completion entry point for a single LLM."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        *,
        provider: LLMProvider | None = None,
        retry_policy: RetryPolicy | None = None,
        thinking: ThinkingConfig | None = None,
        provider_routing: ProviderRoutingConfig | None = None,
        request_timeout_seconds: float | None = DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        if request_timeout_seconds is not None and request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive or None")
        self._model = model
        self._api_key = api_key
        self._provider = provider or LiteLLMProvider(
            api_key=api_key,
            retry_policy=retry_policy,
        )
        self._thinking = thinking
        self._provider_routing = provider_routing
        self._request_timeout_seconds = request_timeout_seconds
        self._llm = LLM(model=model, api_key=api_key)

    @classmethod
    def from_env(cls, default_model: str = "anthropic/claude-sonnet-4-5-20250929") -> LLMClient:
        """Build a client from environment variables."""
        config = load_client_config_from_env(default_model)
        return cls(
            model=config.model,
            api_key=config.api_key,
            provider=config.provider,
            thinking=config.thinking,
            provider_routing=config.provider_routing,
            request_timeout_seconds=config.request_timeout_seconds,
        )

    @property
    def model(self) -> str:
        """The fully-qualified model identifier (provider/model)."""
        return self._model

    @property
    def request_timeout_seconds(self) -> float | None:
        """Default per-provider request timeout for chat calls."""
        return self._request_timeout_seconds

    def complete(
        self,
        messages: list[Message],
        tools: Sequence[ToolDefinition[Any, Any]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request via openhands-sdk and return its response."""
        return self._llm.completion(messages=messages, tools=tools)

    def count_tokens(self, messages: list[Message]) -> int:
        """Rough token count for a message list — used by the Phase 3 budget."""
        return self._llm.get_token_count(messages)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        thinking: ThinkingConfig | None = None,
        provider_routing: ProviderRoutingConfig | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatResponse:
        """Run a chat completion with optional tool schemas, parse out tool_calls.

        ``messages`` and ``tools`` follow the OpenAI chat-completions shape.
        The ReAct loop owns the message history; providers own transport.
        """
        request = ChatRequest(
            model=self._model,
            messages=messages,
            tools=tools,
            timeout_seconds=(
                self._request_timeout_seconds
                if timeout_seconds is None
                else timeout_seconds
            ),
            thinking=thinking or self._thinking,
            provider_routing=provider_routing or self._provider_routing,
            metadata=metadata or {},
        )
        return self._provider.chat(request)


def tool_schema_from_action(
    *,
    name: str,
    description: str,
    action_type: type[Any],
) -> dict[str, Any]:
    """Build an OpenAI-format tool schema from a Pydantic Action class.

    The Action's JSON schema becomes the ``parameters`` block. We strip event
    bookkeeping fields (``event_id``, ``timestamp``, ``source``) so the model
    only sees what it actually has to choose.
    """
    raw = action_type.model_json_schema()
    properties = dict(raw.get("properties", {}))
    required = list(raw.get("required", []))
    for hidden in ("event_id", "timestamp", "source"):
        properties.pop(hidden, None)
        if hidden in required:
            required.remove(hidden)
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def parse_tool_arguments(raw_arguments: str) -> dict[str, Any]:
    """Parse a tool_call's ``arguments`` JSON string into a dict.

    Empty or whitespace-only strings become ``{}``. Invalid JSON raises so the
    loop can convert it into a structured error observation.
    """
    stripped = raw_arguments.strip()
    if not stripped:
        return {}
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError(f"tool arguments must decode to an object, got {type(parsed).__name__}")
    return parsed


__all__ = [
    "ChatResponse",
    "LLMClient",
    "ToolCall",
    "parse_tool_arguments",
    "tool_schema_from_action",
]
