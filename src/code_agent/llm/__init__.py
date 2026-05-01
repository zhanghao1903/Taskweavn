"""LLM adapter layer (built on openhands-sdk + litellm)."""

from openhands.sdk.llm import LLMResponse, Message
from openhands.sdk.tool import ToolDefinition

from code_agent.llm.client import (
    ChatResponse,
    LLMClient,
    ToolCall,
    parse_tool_arguments,
    tool_schema_from_action,
)

__all__ = [
    "ChatResponse",
    "LLMClient",
    "LLMResponse",
    "Message",
    "ToolCall",
    "ToolDefinition",
    "parse_tool_arguments",
    "tool_schema_from_action",
]
