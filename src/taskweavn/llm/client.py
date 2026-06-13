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


class _LazyOpenHandsLLM:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs
        self._instance: Any | None = None

    def completion(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve().completion(*args, **kwargs)

    def get_token_count(self, *args: Any, **kwargs: Any) -> int:
        return self._resolve().get_token_count(*args, **kwargs)

    def _resolve(self) -> Any:
        if self._instance is None:
            from openhands.sdk import LLM as OpenHandsLLM

            self._instance = OpenHandsLLM(*self._args, **self._kwargs)
        return self._instance


LLM = _LazyOpenHandsLLM


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
        if provider is None:
            from taskweavn.llm.providers.litellm import LiteLLMProvider

            provider = LiteLLMProvider(
                api_key=api_key,
                retry_policy=retry_policy,
            )
        self._provider = provider
        self._thinking = thinking
        self._provider_routing = provider_routing
        self._request_timeout_seconds = request_timeout_seconds
        self._llm: Any = LLM(model=model, api_key=api_key)

    @classmethod
    def from_env(cls, default_model: str = "deepseek-v4-pro") -> LLMClient:
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
        messages: list[Any],
        tools: Sequence[Any] | None = None,
    ) -> Any:
        """Send a chat completion request via openhands-sdk and return its response."""
        return self._llm.completion(messages=messages, tools=tools)

    def count_tokens(self, messages: list[Any]) -> int:
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

class LazyLLMClient:
    """Delay provider setup until the first model request.

    The Plato sidecar can start before first-run settings are complete. Keeping
    provider validation lazy lets the UI open and report missing configuration
    instead of failing the local runtime before a user can fix it.
    """

    def __init__(self, default_model: str = "deepseek-v4-pro") -> None:
        self._default_model = default_model
        self._client: LLMClient | None = None

    @property
    def model(self) -> str:
        import os

        return os.environ.get("LLM_MODEL", self._default_model)

    @property
    def request_timeout_seconds(self) -> float | None:
        if self._client is None:
            return DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS
        return self._client.request_timeout_seconds

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        return self._resolve().chat(
            messages=messages,
            tools=tools,
            metadata=metadata,
            **kwargs,
        )

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve().complete(*args, **kwargs)

    def count_tokens(self, *args: Any, **kwargs: Any) -> Any:
        return self._resolve().count_tokens(*args, **kwargs)

    def _resolve(self) -> LLMClient:
        if self._client is None:
            self._client = LLMClient.from_env(self._default_model)
        return self._client


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
    "LazyLLMClient",
    "LLMClient",
    "ToolCall",
    "parse_tool_arguments",
    "tool_schema_from_action",
]
