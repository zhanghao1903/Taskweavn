"""LLM adapter layer."""

from openhands.sdk.llm import LLMResponse, Message
from openhands.sdk.tool import ToolDefinition

from taskweavn.llm.client import (
    ChatResponse,
    LLMClient,
    ToolCall,
    parse_tool_arguments,
    tool_schema_from_action,
)
from taskweavn.llm.config import (
    DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
    LLMClientConfig,
    build_provider,
    load_client_config_from_env,
)
from taskweavn.llm.contracts import (
    ChatRequest,
    ErrorClassification,
    LLMProvider,
    LLMUsage,
    ProviderCapabilities,
    ProviderRoutingConfig,
    RetryPolicy,
    RetryRecord,
    ThinkingConfig,
    TokenCountRequest,
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
from taskweavn.llm.providers import DeepSeekProvider, LiteLLMProvider, OpenRouterProvider

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS",
    "DeepSeekProvider",
    "ErrorClassification",
    "LLMAuthError",
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
