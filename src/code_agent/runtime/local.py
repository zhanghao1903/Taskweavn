"""LocalRuntime — executes Actions in the current process via registered executors.

Executors register themselves keyed by Action class. Phase 1.4 wires the
file/shell tools into a LocalRuntime; Phase 2.2 introduces a sandboxed
runtime for ``CodeAction``.
"""

from __future__ import annotations

from collections.abc import Callable

from code_agent.types.base import BaseAction, BaseObservation
from code_agent.types.common import ErrorObservation

Executor = Callable[[BaseAction], BaseObservation]


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
        executor = self._executors.get(type(action))
        if executor is None:
            return ErrorObservation(
                action_id=action.event_id,
                error_type="no_executor",
                message=f"No executor registered for action type {type(action).__name__!r}.",
            )
        try:
            return executor(action)
        except Exception as exc:  # noqa: BLE001 — Runtime contract: never raise.
            return ErrorObservation(
                action_id=action.event_id,
                error_type="execution_error",
                message=f"{type(exc).__name__}: {exc}",
            )
