"""SQLite-backed token usage analytics ledger."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskweavn.usage.models import (
    CacheRateSource,
    TokenUsageEvent,
    TokenUsageSummary,
    TokenUsageSummaryResponse,
    UsageAggregationDimension,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_usage_events (
    usage_event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    session_id TEXT NULL,
    plan_id TEXT NULL,
    task_node_id TEXT NULL,
    agent_run_id TEXT NULL,
    request_purpose TEXT NOT NULL,
    provider TEXT NULL,
    model TEXT NULL,
    provider_request_id_hash TEXT NULL,
    input_tokens INTEGER NULL,
    output_tokens INTEGER NULL,
    total_tokens INTEGER NULL,
    reasoning_tokens INTEGER NULL,
    cached_tokens INTEGER NULL,
    cache_hit_tokens INTEGER NULL,
    cache_miss_tokens INTEGER NULL,
    cache_hit_ratio REAL NULL,
    usage_source TEXT NOT NULL,
    cache_rate_source TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_workspace_time
    ON llm_usage_events(workspace_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_usage_session_time
    ON llm_usage_events(workspace_id, session_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_usage_task_time
    ON llm_usage_events(workspace_id, session_id, task_node_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_usage_plan_time
    ON llm_usage_events(workspace_id, session_id, plan_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_usage_provider_model_time
    ON llm_usage_events(workspace_id, provider, model, occurred_at);
"""

_EVENT_COLUMNS = (
    "usage_event_id",
    "occurred_at",
    "workspace_id",
    "session_id",
    "plan_id",
    "task_node_id",
    "agent_run_id",
    "request_purpose",
    "provider",
    "model",
    "provider_request_id_hash",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "reasoning_tokens",
    "cached_tokens",
    "cache_hit_tokens",
    "cache_miss_tokens",
    "cache_hit_ratio",
    "usage_source",
    "cache_rate_source",
    "metadata_json",
)


@dataclass(frozen=True)
class TokenUsageFilter:
    workspace_id: str
    session_id: str | None = None
    plan_id: str | None = None
    task_node_id: str | None = None
    from_time: str | None = None
    to_time: str | None = None
    provider: str | None = None
    model: str | None = None


class SqliteTokenUsageStore:
    """Durable workspace-local token usage store."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(path),
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.executescript(_SCHEMA)

    def put(self, event: TokenUsageEvent) -> None:
        values = event.model_dump(mode="json", by_alias=False)
        values["metadata_json"] = json.dumps(
            values.pop("metadata"),
            ensure_ascii=False,
            sort_keys=True,
        )
        placeholders = ", ".join("?" for _ in _EVENT_COLUMNS)
        columns = ", ".join(_EVENT_COLUMNS)
        self._conn.execute(
            f"INSERT OR REPLACE INTO llm_usage_events({columns}) VALUES ({placeholders})",
            tuple(values[column] for column in _EVENT_COLUMNS),
        )

    def list_events(
        self,
        filters: TokenUsageFilter,
        *,
        limit: int = 100,
    ) -> tuple[TokenUsageEvent, ...]:
        where, params = _where(filters)
        cursor = self._conn.execute(
            f"""
            SELECT {", ".join(_EVENT_COLUMNS)}
            FROM llm_usage_events
            WHERE {where}
            ORDER BY occurred_at DESC, usage_event_id DESC
            LIMIT ?
            """,
            (*params, max(0, limit)),
        )
        return tuple(_event_from_row(row) for row in cursor.fetchall())

    def summarize(
        self,
        *,
        dimension: UsageAggregationDimension,
        filters: TokenUsageFilter,
    ) -> TokenUsageSummaryResponse:
        events = self._matching_events(filters)
        rows = _summaries_for_dimension(dimension, events, filters.workspace_id)
        totals = _summary_from_events(
            dimension=dimension,
            group_id="total",
            label="Total",
            events=events,
            workspace_id=filters.workspace_id,
        )
        return TokenUsageSummaryResponse(
            dimension=dimension,
            totals=totals,
            rows=tuple(rows),
        )

    def close(self) -> None:
        self._conn.close()

    def _matching_events(self, filters: TokenUsageFilter) -> tuple[TokenUsageEvent, ...]:
        where, params = _where(filters)
        cursor = self._conn.execute(
            f"""
            SELECT {", ".join(_EVENT_COLUMNS)}
            FROM llm_usage_events
            WHERE {where}
            ORDER BY occurred_at ASC, usage_event_id ASC
            """,
            params,
        )
        return tuple(_event_from_row(row) for row in cursor.fetchall())


def _where(filters: TokenUsageFilter) -> tuple[str, tuple[Any, ...]]:
    clauses = ["workspace_id = ?"]
    params: list[Any] = [filters.workspace_id]
    for column, value in (
        ("session_id", filters.session_id),
        ("plan_id", filters.plan_id),
        ("task_node_id", filters.task_node_id),
        ("provider", filters.provider),
        ("model", filters.model),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    if filters.from_time is not None:
        clauses.append("occurred_at >= ?")
        params.append(filters.from_time)
    if filters.to_time is not None:
        clauses.append("occurred_at <= ?")
        params.append(filters.to_time)
    return " AND ".join(clauses), tuple(params)


def _event_from_row(row: sqlite3.Row) -> TokenUsageEvent:
    data = {column: row[column] for column in _EVENT_COLUMNS}
    metadata_json = data.pop("metadata_json")
    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else {}
    return TokenUsageEvent(**data, metadata=metadata)


def _summaries_for_dimension(
    dimension: UsageAggregationDimension,
    events: tuple[TokenUsageEvent, ...],
    workspace_id: str,
) -> list[TokenUsageSummary]:
    groups: dict[str, list[TokenUsageEvent]] = {}
    for event in events:
        group_id = _dimension_id(dimension, event)
        if group_id is None:
            continue
        groups.setdefault(group_id, []).append(event)
    return [
        _summary_from_events(
            dimension=dimension,
            group_id=group_id,
            label=_dimension_label(dimension, group_id),
            events=tuple(group_events),
            workspace_id=workspace_id,
        )
        for group_id, group_events in sorted(
            groups.items(),
            key=lambda item: (_last_occurred_at(tuple(item[1])) or "", item[0]),
            reverse=True,
        )
    ]


def _dimension_id(
    dimension: UsageAggregationDimension,
    event: TokenUsageEvent,
) -> str | None:
    if dimension == "workspace":
        return event.workspace_id
    if dimension == "session":
        return event.session_id
    if dimension == "plan":
        return event.plan_id
    return event.task_node_id


def _dimension_label(dimension: UsageAggregationDimension, group_id: str) -> str:
    if dimension == "workspace":
        return "Workspace"
    if dimension == "session":
        return f"Session {group_id}"
    if dimension == "plan":
        return f"Plan {group_id}"
    return f"Task {group_id}"


def _summary_from_events(
    *,
    dimension: UsageAggregationDimension,
    group_id: str,
    label: str,
    events: tuple[TokenUsageEvent, ...],
    workspace_id: str,
) -> TokenUsageSummary:
    first_event = events[0] if events else None
    session_id = _single_value(event.session_id for event in events)
    plan_id = _single_value(event.plan_id for event in events)
    task_node_id = _single_value(event.task_node_id for event in events)
    cache_hit_ratio, cache_rate_source = _aggregate_cache_rate(events)
    return TokenUsageSummary(
        dimension=dimension,
        id=group_id,
        label=label,
        workspace_id=workspace_id,
        session_id=session_id,
        plan_id=plan_id,
        task_node_id=task_node_id,
        call_count=len(events),
        unknown_usage_call_count=sum(
            1 for event in events if event.usage_source == "unavailable"
        ),
        input_tokens=_sum_known(event.input_tokens for event in events),
        output_tokens=_sum_known(event.output_tokens for event in events),
        total_tokens=_sum_known(event.total_tokens for event in events),
        reasoning_tokens=_sum_known(event.reasoning_tokens for event in events),
        cached_tokens=_sum_known(event.cached_tokens for event in events),
        cache_hit_tokens=_sum_known(event.cache_hit_tokens for event in events),
        cache_miss_tokens=_sum_known(event.cache_miss_tokens for event in events),
        cache_hit_ratio=cache_hit_ratio,
        cache_rate_source=cache_rate_source,
        first_occurred_at=None if first_event is None else first_event.occurred_at,
        last_occurred_at=_last_occurred_at(events),
    )


def _sum_known(values: Iterable[int | None]) -> int | None:
    known = [value for value in values if isinstance(value, int)]
    return sum(known) if known else None


def _aggregate_cache_rate(
    events: tuple[TokenUsageEvent, ...],
) -> tuple[float | None, CacheRateSource]:
    hit_events = tuple(event for event in events if event.cache_hit_tokens is not None)
    hit_tokens = _sum_known(event.cache_hit_tokens for event in events)
    miss_tokens = _sum_known(event.cache_miss_tokens for event in events)
    if (
        hit_events
        and all(event.cache_miss_tokens is not None for event in hit_events)
        and hit_tokens is not None
        and miss_tokens is not None
    ):
        denominator = hit_tokens + miss_tokens
        if denominator > 0:
            return hit_tokens / denominator, "hit_miss_tokens"
    input_tokens = _sum_known(event.input_tokens for event in events)
    if hit_tokens is not None and input_tokens is not None and input_tokens > 0:
        return hit_tokens / input_tokens, "input_tokens"
    return None, "unavailable"


def _single_value(values: Iterable[str | None]) -> str | None:
    known = {value for value in values if isinstance(value, str)}
    if len(known) == 1:
        return next(iter(known))
    return None


def _last_occurred_at(events: tuple[TokenUsageEvent, ...]) -> str | None:
    return max((event.occurred_at for event in events), default=None)
