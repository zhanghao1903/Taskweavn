"""LLM adapter layer."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from openhands.sdk.llm import LLMResponse, Message
    from openhands.sdk.tool import ToolDefinition
else:
    LLMResponse = Any
    Message = Any
    ToolDefinition = Any

from taskweavn.llm.config import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
    LLMClientConfig,
    build_provider,
    load_client_config_from_env,
)
from taskweavn.llm.contracts import (
    ChatRequest,
    ChatResponse,
    ErrorClassification,
    LLMProvider,
    LLMUsage,
    ProviderCapabilities,
    ProviderRoutingConfig,
    RetryPolicy,
    RetryRecord,
    ThinkingConfig,
    TokenCountRequest,
    ToolCall,
)
from taskweavn.llm.errors import (
    LLMAuthError,
    LLMCapabilityError,
    LLMContextLimitError,
    LLMError,
    LLMProviderError,
    LLMRequestError,
    LLMRetryExhaustedError,
    UnsupportedCapabilityError,
)

_LAZY_EXPORTS = {
    "DeepSeekProvider": "taskweavn.llm.providers.deepseek",
    "LazyLLMClient": "taskweavn.llm.client",
    "LLMClient": "taskweavn.llm.client",
    "LiteLLMProvider": "taskweavn.llm.providers.litellm",
    "OpenRouterProvider": "taskweavn.llm.providers.openrouter",
    "parse_tool_arguments": "taskweavn.llm.client",
    "tool_schema_from_action": "taskweavn.llm.client",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "DEFAULT_LLM_PROVIDER",
    "DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS",
    "DeepSeekProvider",
    "ErrorClassification",
    "LLMAuthError",
    "LazyLLMClient",
    "LLMClient",
    "LLMClientConfig",
    "LLMCapabilityError",
    "LLMContextLimitError",
    "LLMError",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "LLMRequestError",
    "LLMRetryExhaustedError",
    "LLMUsage",
    "LiteLLMProvider",
    "Message",
    "OpenRouterProvider",
    "ProviderCapabilities",
    "ProviderRoutingConfig",
    "RetryPolicy",
    "RetryRecord",
    "ThinkingConfig",
    "TokenCountRequest",
    "ToolCall",
    "ToolDefinition",
    "UnsupportedCapabilityError",
    "build_provider",
    "load_client_config_from_env",
    "parse_tool_arguments",
    "tool_schema_from_action",
]
