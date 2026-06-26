"""Token-usage attribution helpers for the Main Page sidecar."""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from taskweavn.task import SqliteTaskBus


def task_plan_resolver(
    task_bus: SqliteTaskBus,
) -> Callable[[str | None, str | None], str | None]:
    """Build a resolver that maps Task nodes to their owning Plan id."""

    def resolve(session_id: str | None, task_node_id: str | None) -> str | None:
        if session_id is None or task_node_id is None:
            return None
        with contextlib.suppress(Exception):
            task = task_bus.get(session_id, task_node_id)
            if task is not None:
                return task.root_id
        return None

    return resolve


__all__ = ["task_plan_resolver"]
