"""LLMClient — thin wrapper around openhands-sdk's LLM plus a litellm-backed chat path.

The openhands wrapper handles single-shot completions (used by audit / RAG
later). For the ReAct loop we go straight through ``litellm.completion`` so we
can ship our own Pydantic ``Action`` schemas as OpenAI-format tools without
having to subclass openhands' ``Action``/``Observation`` hierarchy.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import litellm
from openhands.sdk import LLM
from openhands.sdk.llm import LLMResponse, Message
from openhands.sdk.tool import ToolDefinition


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation requested by the assistant."""

    id: str
    name: str
    arguments: str  # raw JSON string from the model


@dataclass(frozen=True)
class ChatResponse:
    """Parsed chat completion response."""

    content: str
    tool_calls: list[ToolCall]
    raw_assistant_message: dict[str, Any]


class LLMClient:
    """Configuration + completion entry point for a single LLM."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key
        self._llm = LLM(model=model, api_key=api_key)

    @classmethod
    def from_env(cls, default_model: str = "anthropic/claude-sonnet-4-5-20250929") -> LLMClient:
        """Build a client from ``LLM_MODEL`` and ``LLM_API_KEY`` env vars.

        ``LLM_API_KEY`` is required. ``LLM_MODEL`` falls back to
        ``default_model`` when unset.
        """
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_API_KEY is not set; export it before using LLMClient.from_env()."
            )
        model = os.environ.get("LLM_MODEL", default_model)
        return cls(model=model, api_key=api_key)

    @property
    def model(self) -> str:
        """The fully-qualified model identifier (provider/model)."""
        return self._model

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
    ) -> ChatResponse:
        """Run a chat completion with optional tool schemas, parse out tool_calls.

        ``messages`` and ``tools`` follow the OpenAI chat-completions shape that
        litellm normalizes across providers. The ReAct loop owns the message
        history; this method is stateless on purpose.
        """
        response = litellm.completion(
            model=self._model,
            api_key=self._api_key,
            messages=messages,
            tools=tools,
        )
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        raw_tool_calls = getattr(message, "tool_calls", None) or []
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=tc.function.arguments or "{}",
            )
            for tc in raw_tool_calls
        ]
        # Build a transport-shape dict for re-appending to the message list.
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ]
        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            raw_assistant_message=assistant_msg,
        )


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
