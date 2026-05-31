"""Context snapshot store contracts and in-memory implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskweavn.context.models import ContextSnapshot, ContextTrace


@runtime_checkable
class ContextStore(Protocol):
    def save_snapshot(self, snapshot: ContextSnapshot) -> ContextSnapshot: ...

    def save_trace(self, trace: ContextTrace) -> ContextTrace: ...

    def get_snapshot(self, snapshot_id: str) -> ContextSnapshot | None: ...

    def get_trace(self, trace_id: str) -> ContextTrace | None: ...

    def list_snapshots_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        agent_run_id: str | None = None,
    ) -> list[ContextSnapshot]: ...


class InMemoryContextStore:
    """Process-local ContextStore for tests and non-durable callers."""

    def __init__(self) -> None:
        self._snapshots: dict[str, ContextSnapshot] = {}
        self._traces: dict[str, ContextTrace] = {}

    def save_snapshot(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        self._snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def save_trace(self, trace: ContextTrace) -> ContextTrace:
        self._traces[trace.trace_id] = trace
        return trace

    def get_snapshot(self, snapshot_id: str) -> ContextSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def get_trace(self, trace_id: str) -> ContextTrace | None:
        return self._traces.get(trace_id)

    def list_snapshots_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        agent_run_id: str | None = None,
    ) -> list[ContextSnapshot]:
        snapshots = [
            snapshot
            for snapshot in self._snapshots.values()
            if snapshot.session_id == session_id and snapshot.task_id == task_id
        ]
        if agent_run_id is not None:
            snapshots = [
                snapshot for snapshot in snapshots if snapshot.agent_run_id == agent_run_id
            ]
        return sorted(snapshots, key=lambda snapshot: (snapshot.turn_index, snapshot.created_at))
