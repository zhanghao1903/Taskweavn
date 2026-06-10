"""LLM usage recording helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from typing import Any, Protocol
from uuid import uuid4

from taskweavn.llm.contracts import ChatResponse, LLMUsage
from taskweavn.usage.models import (
    CacheRateSource,
    TokenUsageEvent,
    UsageSource,
    utcnow_iso,
)

TaskPlanResolver = Callable[[str | None, str | None], str | None]

_SAFE_METADATA_KEYS = {
    "agent_id",
    "agent_kind",
    "component",
    "context_checkpoint_reason",
    "context_delta_reason",
    "context_render_mode",
    "context_renderer_version",
    "context_snapshot_id",
    "context_stable_prefix_hash",
    "loop_id",
    "loop_profile_id",
    "step",
    "terminal_tool_name",
}
_PATH_LIKE_RE = re.compile(r"(^/|^[A-Za-z]:\\|workspace://|\\.plato|\\.taskweavn)")


class TokenUsageRecorder(Protocol):
    def record_response(
        self,
        response: ChatResponse,
        *,
        metadata: Mapping[str, Any],
        model: str | None,
    ) -> None: ...


class TokenUsageEventSink(Protocol):
    def put(self, event: TokenUsageEvent) -> None: ...


class UsageRecordingLLM:
    """Thin decorator that records provider usage without changing LLM behavior."""

    def __init__(
        self,
        inner: Any,
        *,
        workspace_id: str,
        sink: TokenUsageEventSink,
        task_plan_resolver: TaskPlanResolver | None = None,
    ) -> None:
        self._inner = inner
        self._workspace_id = workspace_id
        self._sink = sink
        self._task_plan_resolver = task_plan_resolver

    @property
    def model(self) -> str | None:
        model = getattr(self._inner, "model", None)
        return model if isinstance(model, str) else None

    @property
    def request_timeout_seconds(self) -> float | None:
        value = getattr(self._inner, "request_timeout_seconds", None)
        return value if isinstance(value, int | float) else None

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        response = self._inner.chat(
            messages=messages,
            tools=tools,
            metadata=metadata,
            **kwargs,
        )
        if isinstance(response, ChatResponse):
            event = normalize_usage_event(
                response,
                workspace_id=self._workspace_id,
                metadata=metadata or {},
                model=self.model,
                task_plan_resolver=self._task_plan_resolver,
            )
            with suppress(Exception):
                self._sink.put(event)
        return response

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.complete(*args, **kwargs)

    def count_tokens(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.count_tokens(*args, **kwargs)


def normalize_usage_event(
    response: ChatResponse,
    *,
    workspace_id: str,
    metadata: Mapping[str, Any],
    model: str | None,
    task_plan_resolver: TaskPlanResolver | None = None,
) -> TokenUsageEvent:
    """Normalize one provider response into the Product 1.1 usage ledger."""

    usage = response.usage
    session_id = _metadata_str(metadata, "session_id")
    task_node_id = _metadata_str(metadata, "task_node_id") or _metadata_str(
        metadata,
        "task_id",
    )
    plan_id = _metadata_str(metadata, "plan_id")
    if plan_id is None and task_plan_resolver is not None:
        plan_id = task_plan_resolver(session_id, task_node_id)

    cache_hit_ratio, cache_rate_source = _cache_hit_ratio(usage)

    return TokenUsageEvent(
        usage_event_id=f"usage-{uuid4().hex}",
        occurred_at=utcnow_iso(),
        workspace_id=workspace_id,
        session_id=session_id,
        plan_id=plan_id,
        task_node_id=task_node_id,
        agent_run_id=_metadata_str(metadata, "agent_run_id"),
        request_purpose=_metadata_str(metadata, "request_purpose") or "unknown",
        provider=response.provider_name,
        model=model or _metadata_str(metadata, "model"),
        provider_request_id_hash=_hash_or_none(response.provider_request_id),
        input_tokens=None if usage is None else usage.input_tokens,
        output_tokens=None if usage is None else usage.output_tokens,
        total_tokens=_total_tokens(usage),
        reasoning_tokens=None if usage is None else usage.reasoning_tokens,
        cached_tokens=None if usage is None else usage.cached_tokens,
        cache_hit_tokens=None if usage is None else usage.cache_hit_tokens,
        cache_miss_tokens=None if usage is None else usage.cache_miss_tokens,
        cache_hit_ratio=cache_hit_ratio,
        usage_source=_usage_source(usage),
        cache_rate_source=cache_rate_source,
        metadata=_safe_metadata(metadata),
    )


def _usage_source(usage: LLMUsage | None) -> UsageSource:
    if usage is None:
        return "unavailable"
    if usage.total_tokens is not None and (
        usage.input_tokens is not None or usage.output_tokens is not None
    ):
        return "provider_reported"
    return "provider_partial"


def _total_tokens(usage: LLMUsage | None) -> int | None:
    if usage is None:
        return None
    if usage.total_tokens is not None:
        return usage.total_tokens
    if usage.input_tokens is not None and usage.output_tokens is not None:
        return usage.input_tokens + usage.output_tokens
    return None


def _cache_hit_ratio(usage: LLMUsage | None) -> tuple[float | None, CacheRateSource]:
    if usage is None or usage.cache_hit_tokens is None:
        return None, "unavailable"
    if usage.cache_miss_tokens is not None:
        denominator = usage.cache_hit_tokens + usage.cache_miss_tokens
        if denominator > 0:
            return usage.cache_hit_tokens / denominator, "hit_miss_tokens"
    if usage.input_tokens is not None and usage.input_tokens > 0:
        return usage.cache_hit_tokens / usage.input_tokens, "input_tokens"
    return None, "unavailable"


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _hash_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _safe_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in sorted(_SAFE_METADATA_KEYS):
        value = metadata.get(key)
        if isinstance(value, str):
            if not value or _PATH_LIKE_RE.search(value):
                continue
            safe[key] = value[:160]
        elif isinstance(value, bool | int | float):
            safe[key] = value
    return safe
