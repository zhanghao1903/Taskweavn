"""Ambient structured logging context."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from taskweavn.observability.models import LogContext

_CURRENT_CONTEXT: ContextVar[LogContext | None] = ContextVar(
    "taskweavn_log_context",
    default=None,
)


def get_log_context() -> LogContext:
    """Return the ambient logging context for the current execution path."""
    return _CURRENT_CONTEXT.get() or LogContext()


def merge_log_context(context: LogContext | None) -> LogContext:
    """Merge explicit event context over the ambient context.

    Call sites should pass only fields they know locally, e.g. ``action_id``.
    Session/run metadata comes from :func:`use_log_context` around the main
    loop. Explicit non-null fields always win.
    """
    base = get_log_context().model_dump()
    if context is None:
        return LogContext.model_validate(base)
    override = context.model_dump()
    base.update({key: value for key, value in override.items() if value is not None})
    return LogContext.model_validate(base)


@contextmanager
def use_log_context(context: LogContext) -> Iterator[None]:
    """Temporarily extend the ambient logging context."""
    merged = merge_log_context(context)
    token = _CURRENT_CONTEXT.set(merged)
    try:
        yield
    finally:
        _CURRENT_CONTEXT.reset(token)


__all__ = ["get_log_context", "merge_log_context", "use_log_context"]
