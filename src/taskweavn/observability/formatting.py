"""Structured log formatting."""

from __future__ import annotations

import json
from typing import Any

from taskweavn.observability.models import LogEvent


def event_to_dict(event: LogEvent, *, include_legacy_msg: bool = True) -> dict[str, Any]:
    """Convert a log event to a JSON-serializable dictionary."""
    payload = event.model_dump(mode="json", exclude_none=True)
    if include_legacy_msg:
        payload["msg"] = event.event
    return payload


def event_to_json(event: LogEvent, *, include_legacy_msg: bool = True) -> str:
    """Render a log event as one JSONL line."""
    return json.dumps(
        event_to_dict(event, include_legacy_msg=include_legacy_msg),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def event_to_pretty(event: LogEvent) -> str:
    """Render one event for console/debug display."""
    context = event.context
    pieces = [
        event.ts.strftime("%H:%M:%S"),
        event.level.ljust(8),
        f"{event.category}.{event.event}",
    ]
    if context.session_id:
        pieces.append(f"session={context.session_id}")
    if context.task_id:
        pieces.append(f"task={context.task_id}")
    if context.tool_name:
        pieces.append(f"tool={context.tool_name}")
    if context.model:
        pieces.append(f"model={context.model}")
    return " ".join(pieces)


__all__ = ["event_to_dict", "event_to_json", "event_to_pretty"]
