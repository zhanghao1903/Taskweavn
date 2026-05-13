"""Compatibility bridge from stdlib logging to structured logging."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from taskweavn.observability.levels import normalize_level
from taskweavn.observability.manager import get_logging_manager
from taskweavn.observability.models import LogCategory, LogContext


class StructuredLogHandler(logging.FileHandler):
    """FileHandler-shaped bridge used by the legacy channel API.

    Subclassing ``FileHandler`` keeps old tests and cleanup code working. The
    actual write is delegated to ``LoggingManager`` so legacy and new APIs share
    the same sink/rule machinery.
    """

    def __init__(self, path: Path, *, category: LogCategory) -> None:
        self.category = category
        super().__init__(path, encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            data = getattr(record, "data", None)
            context = _context_from_data(data)
            get_logging_manager().emit(
                self.category,
                normalize_level(record.levelno),
                record.getMessage(),
                message=record.getMessage(),
                context=context,
                data=data if isinstance(data, dict) else None,
            )
        except Exception:
            self.handleError(record)


def _context_from_data(data: Any) -> LogContext | None:
    if not isinstance(data, dict):
        return None
    allowed = {
        "session_id",
        "task_id",
        "agent_id",
        "trace_id",
        "action_id",
        "observation_id",
        "message_id",
        "tool_name",
        "model",
        "provider",
        "provider_request_id",
        "workspace_root",
    }
    payload = {
        key: str(value)
        for key, value in data.items()
        if key in allowed and value is not None
    }
    return LogContext.model_validate(payload) if payload else None


__all__ = ["StructuredLogHandler"]
