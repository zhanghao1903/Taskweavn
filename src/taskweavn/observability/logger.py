"""Object-aware structured logger API."""

from __future__ import annotations

from taskweavn.observability.levels import LogLevel
from taskweavn.observability.manager import LogData, get_logging_manager
from taskweavn.observability.models import LogCategory, LogContext


class ObjectLogger:
    """Category-bound structured logger."""

    def __init__(self, category: LogCategory) -> None:
        self.category = category

    def enabled(self, level: LogLevel | str | int, *, context: LogContext | None = None) -> bool:
        """Return whether the manager would emit this level/context."""
        return get_logging_manager().is_enabled(self.category, level, context)

    def log(
        self,
        level: LogLevel | str | int,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        """Emit a structured event if enabled."""
        get_logging_manager().emit(
            self.category,
            level,
            event,
            message=message,
            context=context,
            data=data,
        )

    def trace(
        self,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        self.log("TRACE", event, message=message, context=context, data=data)

    def debug(
        self,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        self.log("DEBUG", event, message=message, context=context, data=data)

    def info(
        self,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        self.log("INFO", event, message=message, context=context, data=data)

    def warning(
        self,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        self.log("WARNING", event, message=message, context=context, data=data)

    def error(
        self,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        self.log("ERROR", event, message=message, context=context, data=data)

    def critical(
        self,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        self.log("CRITICAL", event, message=message, context=context, data=data)


def get_object_logger(category: LogCategory) -> ObjectLogger:
    """Return an object-aware logger for a category."""
    return ObjectLogger(category)


__all__ = ["ObjectLogger", "get_object_logger"]
