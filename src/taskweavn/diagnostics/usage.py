"""Token usage diagnostic projection."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any


def collect_token_usage_summary(
    *,
    usage_db_path: Path,
    session_id: str,
    max_events: int = 50,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Return redaction-ready token usage summary for diagnostics."""

    if not usage_db_path.exists():
        return None, ("token usage store is not present",)
    try:
        conn = sqlite3.connect(str(usage_db_path))
        conn.row_factory = sqlite3.Row
        session_rows = conn.execute(
            """
            SELECT *
            FROM llm_usage_events
            WHERE session_id = ?
            ORDER BY occurred_at DESC, usage_event_id DESC
            LIMIT ?
            """,
            (session_id, max(0, max_events)),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM llm_usage_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
    except sqlite3.Error as exc:
        return None, (f"{type(exc).__name__}: token usage store could not be read",)
    finally:
        with suppress(UnboundLocalError):
            conn.close()

    rows = [_summary_row(row) for row in session_rows]
    payload = {
        "schemaVersion": "plato.token_usage.diagnostic_summary.v1",
        "sessionId": session_id,
        "eventCount": total,
        "includedEventCount": len(rows),
        "totals": _totals(rows),
        "recentEvents": rows,
    }
    warnings: list[str] = []
    if total > len(rows):
        warnings.append(f"token usage summary truncated to {len(rows)} of {total} events")
    return payload, tuple(warnings)


def _summary_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "usageEventId": row["usage_event_id"],
        "occurredAt": row["occurred_at"],
        "workspaceId": row["workspace_id"],
        "sessionId": row["session_id"],
        "planId": row["plan_id"],
        "taskNodeId": row["task_node_id"],
        "agentRunId": row["agent_run_id"],
        "requestPurpose": row["request_purpose"],
        "provider": row["provider"],
        "model": row["model"],
        "inputTokens": row["input_tokens"],
        "outputTokens": row["output_tokens"],
        "totalTokens": row["total_tokens"],
        "reasoningTokens": row["reasoning_tokens"],
        "cachedTokens": row["cached_tokens"],
        "cacheHitTokens": row["cache_hit_tokens"],
        "cacheMissTokens": row["cache_miss_tokens"],
        "cacheHitRatio": row["cache_hit_ratio"],
        "usageSource": row["usage_source"],
        "cacheRateSource": row["cache_rate_source"],
    }


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hit_rows = [row for row in rows if row["cacheHitTokens"] is not None]
    hit_tokens = _sum_known(row["cacheHitTokens"] for row in rows)
    miss_tokens = _sum_known(row["cacheMissTokens"] for row in rows)
    cache_hit_ratio = None
    cache_rate_source = "unavailable"
    if (
        hit_rows
        and all(row["cacheMissTokens"] is not None for row in hit_rows)
        and hit_tokens is not None
        and miss_tokens is not None
        and hit_tokens + miss_tokens > 0
    ):
        cache_hit_ratio = hit_tokens / (hit_tokens + miss_tokens)
        cache_rate_source = "hit_miss_tokens"
    elif hit_tokens is not None:
        input_tokens = _sum_known(row["inputTokens"] for row in rows)
        if input_tokens is not None and input_tokens > 0:
            cache_hit_ratio = hit_tokens / input_tokens
            cache_rate_source = "input_tokens"

    return {
        "callCount": len(rows),
        "unknownUsageCallCount": sum(
            1 for row in rows if row["usageSource"] == "unavailable"
        ),
        "inputTokens": _sum_known(row["inputTokens"] for row in rows),
        "outputTokens": _sum_known(row["outputTokens"] for row in rows),
        "totalTokens": _sum_known(row["totalTokens"] for row in rows),
        "reasoningTokens": _sum_known(row["reasoningTokens"] for row in rows),
        "cachedTokens": _sum_known(row["cachedTokens"] for row in rows),
        "cacheHitTokens": hit_tokens,
        "cacheMissTokens": miss_tokens,
        "cacheHitRatio": cache_hit_ratio,
        "cacheRateSource": cache_rate_source,
    }


def _sum_known(values: Iterable[int | None]) -> int | None:
    known = [value for value in values if isinstance(value, int)]
    return sum(known) if known else None


__all__ = ["collect_token_usage_summary"]
