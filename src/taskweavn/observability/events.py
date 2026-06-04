"""Stable event-name taxonomy for structured object logs."""

from __future__ import annotations

from taskweavn.observability.models import LogCategory

LOG_EVENTS_BY_CATEGORY: dict[LogCategory, tuple[str, ...]] = {
    "action": ("emit",),
    "observation": ("emit",),
    "llm": ("agent_input", "agent_output", "request", "response", "retry"),
    "task": (),
    "tool": ("invoke", "result"),
    "bus": (
        "close",
        "publish",
        "response_received",
        "response_timeout",
        "subscribe",
        "wait_closed",
    ),
    "agent": (),
    "session": (),
    "runtime": (),
    "sandbox": (
        "container_remove_failed",
        "container_started",
        "container_stopped",
        "execute_failed",
        "execute_result",
        "execute_start",
        "image_pull_failed",
        "image_pull_start",
    ),
    "audit": ("llm_failed", "parse_failed", "request", "result"),
    "risk": (),
    "gate": ("decision",),
    "wait": (
        "bus_closed",
        "got_response",
        "got_response_after_wait",
        "pending",
        "timeout_proceed",
        "timeout_skip",
    ),
    "config": (
        "level_set",
        "profile_applied",
        "session_archive_closed",
        "updated",
    ),
}


def known_log_events(category: LogCategory) -> tuple[str, ...]:
    """Return the stable event names documented for one category."""
    return LOG_EVENTS_BY_CATEGORY[category]


def is_known_log_event(category: LogCategory, event: str) -> bool:
    """Return whether ``event`` is part of the stable taxonomy."""
    return event in LOG_EVENTS_BY_CATEGORY[category]


__all__ = [
    "LOG_EVENTS_BY_CATEGORY",
    "is_known_log_event",
    "known_log_events",
]
