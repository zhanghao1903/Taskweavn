"""Stable LLM provider contracts.

The public facade remains :class:`taskweavn.llm.client.LLMClient`; this module
defines the lower-level request/response objects that providers implement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from openhands.sdk.llm import LLMResponse, Message
from openhands.sdk.tool import ToolDefinition
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ErrorClassification(StrEnum):
    """Provider failure classes used by retry and error reporting."""

    RETRYABLE = "retryable"
    FATAL_AUTH = "fatal_auth"
    FATAL_REQUEST = "fatal_request"
    FATAL_CAPABILITY = "fatal_capability"
    RATE_LIMIT = "rate_limit"
    CONTEXT_LIMIT = "context_limit"
    UNKNOWN = "unknown"


class ProviderCapabilities(BaseModel):
    """Capability flags for a concrete LLM provider/model family."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chat: bool = True
    completion: bool = False
    token_count: bool = False
    tool_calls: bool = True
    thinking: bool = False
    reasoning_content_output: bool = False
    reasoning_content_input: bool = False
    provider_routing: bool = False


class ThinkingConfig(BaseModel):
    """Provider-neutral thinking-mode request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    effort: str = "high"
    expose_reasoning_to_ui: bool = False

    @field_validator("effort")
    @classmethod
    def _validate_effort(cls, value: str) -> str:
        if value not in {"high", "max"}:
            raise ValueError("effort must be 'high' or 'max'")
        return value


class ProviderRoutingConfig(BaseModel):
    """Provider routing policy, currently used by OpenRouter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order: tuple[str, ...] = ()
    only: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    allow_fallbacks: bool = False
    require_parameters: bool = True
    data_collection: str | None = None
    zdr: bool | None = None

    @field_validator("data_collection")
    @classmethod
    def _validate_data_collection(cls, value: str | None) -> str | None:
        if value is not None and value not in {"allow", "deny"}:
            raise ValueError("data_collection must be 'allow' or 'deny'")
        return value

    def to_openrouter_dict(self) -> dict[str, Any]:
        """Serialize non-empty fields into OpenRouter's provider object."""
        payload: dict[str, Any] = {
            "allow_fallbacks": self.allow_fallbacks,
            "require_parameters": self.require_parameters,
        }
        if self.order:
            payload["order"] = list(self.order)
        if self.only:
            payload["only"] = list(self.only)
        if self.ignore:
            payload["ignore"] = list(self.ignore)
        if self.data_collection is not None:
            payload["data_collection"] = self.data_collection
        if self.zdr is not None:
            payload["zdr"] = self.zdr
        return payload


class RetryPolicy(BaseModel):
    """Retry policy for provider transport calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_status: tuple[int, ...] = (408, 409, 425, 429, 500, 502, 503, 504)

    @model_validator(mode="after")
    def _validate_policy(self) -> RetryPolicy:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must be non-negative")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must be non-negative")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max_delay_seconds must be >= initial_delay_seconds")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")
        return self


class LLMUsage(BaseModel):
    """Token usage metadata when a provider returns it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    cache_hit_tokens: int | None = None
    cache_miss_tokens: int | None = None
    cache_hit_ratio: float | None = None


class RetryRecord(BaseModel):
    """One retry attempt record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt: int
    max_attempts: int
    classification: ErrorClassification
    provider_name: str
    model: str
    delay_seconds: float
    error_type: str
    error_summary: str


class ChatRequest(BaseModel):
    """Provider-neutral chat request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    thinking: ThinkingConfig | None = None
    provider_routing: ProviderRoutingConfig | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timeout_seconds")
    @classmethod
    def _validate_timeout_seconds(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("timeout_seconds must be positive or None")
        return value


class CompletionRequest(BaseModel):
    """Placeholder contract for legacy completion calls."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    messages: list[Message]
    tools: Sequence[ToolDefinition[Any, Any]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenCountRequest(BaseModel):
    """Placeholder contract for provider token counting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    messages: list[Message]


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation requested by the assistant."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ChatResponse:
    """Parsed chat completion response.

    The first three fields are the pre-provider API and must remain positional
    for existing tests and stubs.
    """

    content: str
    tool_calls: list[ToolCall]
    raw_assistant_message: dict[str, Any]
    reasoning_content: str | None = None
    provider_name: str | None = None
    provider_request_id: str | None = None
    usage: LLMUsage | None = None
    retry_count: int = 0
    retry_records: tuple[RetryRecord, ...] = ()
    raw_response_metadata: dict[str, Any] = field(default_factory=dict)


CompletionResponse = LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Transport-specific LLM provider."""

    name: str
    capabilities: ProviderCapabilities

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Run a chat completion."""
        ...

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Run a legacy completion request, if supported."""
        ...

    def count_tokens(self, request: TokenCountRequest) -> int:
        """Count tokens, if supported."""
        ...


__all__ = [
    "ChatRequest",
    "ChatResponse",
    "CompletionRequest",
    "CompletionResponse",
    "ErrorClassification",
    "LLMProvider",
    "LLMUsage",
    "ProviderCapabilities",
    "ProviderRoutingConfig",
    "RetryPolicy",
    "RetryRecord",
    "ThinkingConfig",
    "TokenCountRequest",
    "ToolCall",
]
