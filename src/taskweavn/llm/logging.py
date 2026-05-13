"""Structured logging helpers for LLM providers."""

from __future__ import annotations

from typing import Any

from taskweavn.llm.contracts import ChatRequest, ChatResponse, RetryRecord
from taskweavn.observability import LogContext, get_object_logger

_LLM_LOGGER = get_object_logger("llm")


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


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return str(value) if value is not None else None


__all__ = [
    "llm_context_from_request",
    "log_llm_request",
    "log_llm_response",
    "log_llm_retry",
]
