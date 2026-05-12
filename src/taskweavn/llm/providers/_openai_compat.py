"""Helpers for OpenAI-compatible chat completion responses."""

from __future__ import annotations

from typing import Any

from taskweavn.llm.contracts import ChatResponse, LLMUsage, ToolCall


def parse_openai_compatible_response(
    response: Any,
    *,
    provider_name: str,
) -> ChatResponse:
    """Parse an OpenAI/LiteLLM-style response object into ``ChatResponse``."""
    choice = response.choices[0]
    message = choice.message
    content = _str_or_default(getattr(message, "content", None), "")
    reasoning_content = _optional_str(getattr(message, "reasoning_content", None))
    tool_calls = _parse_tool_calls(getattr(message, "tool_calls", None))

    assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
    if reasoning_content is not None:
        assistant_msg["reasoning_content"] = reasoning_content
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
        reasoning_content=reasoning_content,
        provider_name=provider_name,
        provider_request_id=_optional_str(getattr(response, "id", None)),
        usage=_parse_usage(getattr(response, "usage", None)),
        raw_response_metadata=_parse_metadata(response),
    )


def _parse_tool_calls(raw_tool_calls: Any) -> list[ToolCall]:
    if raw_tool_calls is None:
        return []
    if not isinstance(raw_tool_calls, list):
        try:
            raw_tool_calls = list(raw_tool_calls)
        except TypeError:
            return []

    parsed: list[ToolCall] = []
    for tc in raw_tool_calls:
        function = getattr(tc, "function", None)
        name = _str_or_default(getattr(function, "name", None), "")
        if not name:
            continue
        parsed.append(
            ToolCall(
                id=_str_or_default(getattr(tc, "id", None), ""),
                name=name,
                arguments=_str_or_default(getattr(function, "arguments", None), "{}"),
            )
        )
    return parsed


def _parse_usage(raw: Any) -> LLMUsage | None:
    if raw is None:
        return None

    usage = LLMUsage(
        input_tokens=_maybe_int(raw, "prompt_tokens", "input_tokens"),
        output_tokens=_maybe_int(raw, "completion_tokens", "output_tokens"),
        total_tokens=_maybe_int(raw, "total_tokens"),
        reasoning_tokens=_nested_int(raw, "completion_tokens_details", "reasoning_tokens"),
        cached_tokens=_nested_int(raw, "prompt_tokens_details", "cached_tokens"),
    )
    if all(value is None for value in usage.model_dump().values()):
        return None
    return usage


def _parse_metadata(response: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("model", "system_fingerprint", "created"):
        value = getattr(response, key, None)
        if isinstance(value, str | int | float | bool):
            metadata[key] = value
    return metadata


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _str_or_default(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _maybe_int(obj: Any, *names: str) -> int | None:
    for name in names:
        value = getattr(obj, name, None)
        if isinstance(value, int):
            return value
        if isinstance(obj, dict):
            raw = obj.get(name)
            if isinstance(raw, int):
                return raw
    return None


def _nested_int(obj: Any, container_name: str, name: str) -> int | None:
    container = getattr(obj, container_name, None)
    if isinstance(obj, dict):
        container = obj.get(container_name)
    if container is None:
        return None
    return _maybe_int(container, name)


__all__ = ["parse_openai_compatible_response"]
