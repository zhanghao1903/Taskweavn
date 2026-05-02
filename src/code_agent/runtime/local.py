"""LocalRuntime — executes Actions in the current process via registered executors.

Executors register themselves keyed by Action class. Phase 1.4 wires the
file/shell tools into a LocalRuntime; Phase 2.2 introduces a sandboxed
runtime for ``CodeAction``.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from code_agent.observability.setup import get_channel_logger
from code_agent.types.base import BaseAction, BaseObservation
from code_agent.types.common import ErrorObservation

Executor = Callable[[BaseAction], BaseObservation]

_TOOL_LOGGER = get_channel_logger("tool")


class LocalRuntime:
    """In-process Runtime backed by a class-keyed executor registry."""

    def __init__(self) -> None:
        self._executors: dict[type[BaseAction], Executor] = {}

    def register(self, action_type: type[BaseAction], executor: Executor) -> None:
        """Bind an executor to an Action subclass.

        Re-registering the same Action type replaces the prior executor — that
        keeps tool composition simple at the cost of giving up duplicate
        detection. Surface a warning later if it bites.
        """
        self._executors[action_type] = executor

    def execute(self, action: BaseAction) -> BaseObservation:
        action_kind = type(action).__name__
        _TOOL_LOGGER.info(
            "invoke",
            extra={
                "data": {
                    "action_kind": action_kind,
                    "action_id": action.event_id,
                    "payload": action.to_dict(),
                }
            },
        )
        start = time.monotonic()
        executor = self._executors.get(type(action))
        if executor is None:
            result: BaseObservation = ErrorObservation(
                action_id=action.event_id,
                error_type="no_executor",
                message=f"No executor registered for action type {action_kind!r}.",
            )
        else:
            try:
                result = executor(action)
            except Exception as exc:  # noqa: BLE001 — Runtime contract: never raise.
                result = ErrorObservation(
                    action_id=action.event_id,
                    error_type="execution_error",
                    message=f"{type(exc).__name__}: {exc}",
                )
        duration_ms = round((time.monotonic() - start) * 1000, 3)
        _TOOL_LOGGER.info(
            "result",
            extra={
                "data": {
                    "action_kind": action_kind,
                    "action_id": action.event_id,
                    "result_kind": type(result).__name__,
                    "success": result.success,
                    "duration_ms": duration_ms,
                }
            },
        )
        return result
