"""Structured logging helpers for LLM providers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from taskweavn.llm.contracts import ChatRequest, ChatResponse, RetryRecord
from taskweavn.observability import LogContext, get_object_logger

_LLM_LOGGER = get_object_logger("llm")
_LLM_IO_LOGGER = get_object_logger("llm_io")


def llm_context_from_request(request: ChatRequest, *, provider: str) -> LogContext:
    """Build a structured log context from provider-neutral request metadata."""
    metadata = request.metadata
    return LogContext(
        session_id=_metadata_str(metadata, "session_id"),
        task_id=_metadata_str(metadata, "task_id"),
        agent_id=_metadata_str(metadata, "agent_id"),
        trace_id=_metadata_str(metadata, "trace_id"),
        model=request.model,
        provider=provider,
    )


def log_llm_request(
    provider: str,
    request: ChatRequest,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit one provider request event."""
    payload: dict[str, Any] = {
        "provider": provider,
        "model": request.model,
        "request_purpose": request.metadata.get("request_purpose"),
        "message_count": len(request.messages),
        "tool_count": len(request.tools) if request.tools else 0,
        "timeout_seconds": request.timeout_seconds,
        "thinking_enabled": bool(request.thinking and request.thinking.enabled),
    }
    if request.thinking is not None:
        payload["thinking_effort"] = request.thinking.effort
    if extra:
        payload.update(extra)
    _LLM_LOGGER.info(
        "request",
        context=llm_context_from_request(request, provider=provider),
        data=payload,
    )


def log_llm_response(
    response: ChatResponse,
    *,
    request: ChatRequest,
    provider: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit one provider response event."""
    context = llm_context_from_request(request, provider=provider).model_copy(
        update={"provider_request_id": response.provider_request_id}
    )
    payload: dict[str, Any] = {
        "provider": response.provider_name or provider,
        "model": request.model,
        "content_length": len(response.content),
        "tool_calls": [{"id": tc.id, "name": tc.name} for tc in response.tool_calls],
        "has_reasoning_content": response.reasoning_content is not None,
        "retry_count": response.retry_count,
    }
    if response.usage is not None:
        payload["usage"] = response.usage.model_dump(mode="json", exclude_none=True)
    if extra:
        payload.update(extra)
    _LLM_LOGGER.info("response", context=context, data=payload)


def log_llm_retry(record: RetryRecord) -> None:
    """Emit one provider retry event."""
    _LLM_LOGGER.warning(
        "retry",
        context=LogContext(
            provider=record.provider_name,
            model=record.model,
        ),
        data={
            "provider": record.provider_name,
            "model": record.model,
            "attempt": record.attempt,
            "max_attempts": record.max_attempts,
            "classification": record.classification.value,
            "delay_seconds": record.delay_seconds,
            "error_type": record.error_type,
            "error_summary": record.error_summary,
        },
    )


def log_agent_llm_input(
    *,
    agent_kind: str,
    request_purpose: str,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
    context: LogContext | None = None,
) -> None:
    """Emit the application-level LLM input sent by one agent domain."""
    tool_payload = [dict(tool) for tool in tools] if tools is not None else None
    _LLM_IO_LOGGER.info(
        "agent_input",
        context=context,
        data={
            "input": {
                "messages": [dict(message) for message in messages],
                "tools": tool_payload,
            },
        },
    )
    _LLM_LOGGER.info(
        "agent_input",
        context=context,
        data={
            "agent_kind": agent_kind,
            "request_purpose": request_purpose,
            "message_count": len(messages),
            "tool_count": len(tools) if tools is not None else 0,
            "metadata": dict(metadata or {}),
        },
    )


def log_agent_llm_output(
    *,
    agent_kind: str,
    request_purpose: str,
    response: ChatResponse,
    metadata: Mapping[str, Any] | None = None,
    context: LogContext | None = None,
) -> None:
    """Emit the application-level LLM output observed by one agent domain."""
    provider_request_id = getattr(response, "provider_request_id", None)
    provider_name = getattr(response, "provider_name", None)
    reasoning_content = getattr(response, "reasoning_content", None)
    retry_count = getattr(response, "retry_count", 0)
    tool_calls = getattr(response, "tool_calls", ())
    usage = getattr(response, "usage", None)
    resolved_context = context
    if context is not None and provider_request_id is not None:
        resolved_context = context.model_copy(
            update={"provider_request_id": provider_request_id}
        )
    tool_call_payload = [
        {
            "id": tool_call.id,
            "name": tool_call.name,
            "arguments": tool_call.arguments,
        }
        for tool_call in tool_calls
    ]
    _LLM_IO_LOGGER.info(
        "agent_output",
        context=resolved_context,
        data={
            "output": {
                "content": response.content,
                "reasoning_content": reasoning_content,
                "raw_assistant_message": _raw_assistant_message_payload(response),
                "tool_calls": tool_call_payload,
            },
        },
    )
    _LLM_LOGGER.info(
        "agent_output",
        context=resolved_context,
        data={
            "agent_kind": agent_kind,
            "request_purpose": request_purpose,
            "content_length": len(response.content),
            "has_reasoning_content": reasoning_content is not None,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "name": tool_call.name,
                }
                for tool_call in tool_calls
            ],
            "provider": provider_name,
            "provider_request_id": provider_request_id,
            "retry_count": retry_count,
            "usage": (
                usage.model_dump(mode="json", exclude_none=True)
                if usage is not None
                else None
            ),
            "metadata": dict(metadata or {}),
        },
    )


def _raw_assistant_message_payload(response: ChatResponse) -> dict[str, Any]:
    raw_message = getattr(
        response,
        "raw_assistant_message",
        {"role": "assistant", "content": response.content},
    )
    payload = dict(raw_message)
    if payload.get("content") == response.content:
        payload.pop("content", None)
        payload["content_omitted"] = "duplicate_of_content"
    return payload


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return str(value) if value is not None else None


__all__ = [
    "llm_context_from_request",
    "log_agent_llm_input",
    "log_agent_llm_output",
    "log_llm_request",
    "log_llm_response",
    "log_llm_retry",
]
