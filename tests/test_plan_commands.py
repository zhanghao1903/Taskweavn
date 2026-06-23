"""Tests for durable Plan lifecycle command services."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    ActiveAuthoringState,
    DefaultPlanLifecycleCommandService,
    Plan,
    SqlitePlanStore,
)


@dataclass
class _AuthoringStateStore:
    state: ActiveAuthoringState
    cancelled_sessions: list[str] = field(default_factory=list)

    def get_active(self, session_id: str) -> ActiveAuthoringState:
        return self.state

    def set_active_raw_task(self, session_id: str, raw_task_id: str) -> None:
        raise NotImplementedError

    def set_active_draft_tree(
        self,
        session_id: str,
        raw_task_id: str | None,
        draft_tree_id: str,
        *,
        active_plan_id: str | None = None,
    ) -> None:
        raise NotImplementedError

    def mark_published(self, session_id: str, draft_tree_id: str) -> None:
        raise NotImplementedError

    def cancel_active(self, session_id: str) -> None:
        self.cancelled_sessions.append(session_id)
        self.state = self.state.model_copy(update={"active_state": "cancelled"})


@dataclass
class _MessageBus:
    messages: list[AgentMessage] = field(default_factory=list)

    def publish(self, message: AgentMessage) -> None:
        self.messages.append(message)


def test_archive_plan_updates_store_closes_active_state_and_publishes_message(
    tmp_path: Path,
) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        created = store.create_plan(
            Plan(
                plan_id="plan-1",
                session_id="session-1",
                title="Courseware plan",
                objective="Build a courseware site.",
                summary="Completed courseware plan.",
                status="awaiting_acceptance",
            )
        )
        authoring_state = _AuthoringStateStore(
            ActiveAuthoringState(
                session_id="session-1",
                active_draft_tree_id="draft-tree-1",
                active_plan_id="plan-1",
                active_state="published",
            )
        )
        bus = _MessageBus()
        service = DefaultPlanLifecycleCommandService(
            plan_store=store,
            authoring_state_store=authoring_state,
            message_bus=bus,
        )

        result = service.archive_plan(
            "session-1",
            "plan-1",
            expected_version=created.version,
            reason="user archive",
            request_id="archive-1",
        )

        archived = store.get_plan("session-1", "plan-1")
        assert result.accepted is True
        assert result.command_id == "archive-1"
        assert result.message == "Plan archived."
        assert archived is not None
        assert archived.status == "archived"
        assert archived.archived_at is not None
        assert store.get_active_plan("session-1") is None
        assert authoring_state.cancelled_sessions == ["session-1"]
        assert len(bus.messages) == 1
        assert bus.messages[0].content == "Plan archived: Courseware plan"
        assert bus.messages[0].context["plan_id"] == "plan-1"
        assert result.emitted_message_ids == (bus.messages[0].message_id,)
    finally:
        store.close()


def test_archive_plan_rejects_non_terminal_plan(tmp_path: Path) -> None:
    store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        store.create_plan(
            Plan(
                plan_id="plan-1",
                session_id="session-1",
                title="Running plan",
                objective="Still executing.",
                summary="Not ready for archive.",
                status="running",
            )
        )
        bus = _MessageBus()
        service = DefaultPlanLifecycleCommandService(
            plan_store=store,
            message_bus=bus,
        )

        result = service.archive_plan(
            "session-1",
            "plan-1",
            request_id="archive-1",
        )
        loaded = store.get_plan("session-1", "plan-1")

        assert result.accepted is False
        assert result.message == "Plan status 'running' cannot be archived"
        assert loaded is not None
        assert loaded.status == "running"
        assert bus.messages == []
    finally:
        store.close()
