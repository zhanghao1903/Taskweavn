"""Log level helpers for TaskWeavn observability."""

from __future__ import annotations

import logging
from typing import Literal

LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "OFF"]

TRACE_VALUE = 5
OFF_VALUE = 10_000

_LEVEL_VALUES: dict[LogLevel, int] = {
    "TRACE": TRACE_VALUE,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "OFF": OFF_VALUE,
}

_INT_TO_LEVEL: dict[int, LogLevel] = {
    TRACE_VALUE: "TRACE",
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
    OFF_VALUE: "OFF",
}


def normalize_level(value: str | int | LogLevel) -> LogLevel:
    """Normalize a string/int logging level into TaskWeavn's level names."""
    if isinstance(value, int):
        if value in _INT_TO_LEVEL:
            return _INT_TO_LEVEL[value]
        if value <= TRACE_VALUE:
            return "TRACE"
        if value <= logging.DEBUG:
            return "DEBUG"
        if value <= logging.INFO:
            return "INFO"
        if value <= logging.WARNING:
            return "WARNING"
        if value <= logging.ERROR:
            return "ERROR"
        if value <= logging.CRITICAL:
            return "CRITICAL"
        return "OFF"

    normalized = value.strip().upper()
    if normalized in _LEVEL_VALUES:
        return normalized
    raise ValueError(f"unknown log level {value!r}")


def level_value(level: str | int | LogLevel) -> int:
    """Return the numeric severity value for a TaskWeavn log level."""
    return _LEVEL_VALUES[normalize_level(level)]


def level_enabled(
    event_level: str | int | LogLevel,
    configured_level: str | int | LogLevel,
) -> bool:
    """Return whether an event at ``event_level`` should pass ``configured_level``."""
    configured = normalize_level(configured_level)
    if configured == "OFF":
        return False
    return level_value(event_level) >= level_value(configured)


__all__ = [
    "LogLevel",
    "OFF_VALUE",
    "TRACE_VALUE",
    "level_enabled",
    "level_value",
    "normalize_level",
]
