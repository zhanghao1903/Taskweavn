"""Tests for ASK UI projection helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from taskweavn.interaction import AskRequest, InMemoryAskStore
from taskweavn.server.ui_contract.ask_projection import (
    DefaultAskProjectionService,
    select_active_ask,
)
from taskweavn.server.ui_contract.view_models import TaskNodeCardView, TaskTreeView
from taskweavn.task import TaskRef

NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def test_projection_maps_pending_asks_and_prioritizes_waiting_task_active_ask() -> None:
    store = InMemoryAskStore(
        [
            _ask("ask-other", task_id="other", created_at=NOW),
            _ask("ask-waiting", task_id="task-1", created_at=NOW + timedelta(seconds=1)),
        ]
    )
    service = DefaultAskProjectionService(store)
    tree = TaskTreeView(
        id="tree-1",
        session_id="s1",
        title="Task Tree",
        status="running",
        nodes=(
            _node("task-1", execution="waiting_for_user", status="waiting_user"),
            _node("other", execution="pending", status="queued"),
        ),
    )

    result = service.list_asks("s1", statuses=("pending",), task_tree=tree)

    assert [ask.id for ask in result.asks] == ["ask-other", "ask-waiting"]
    assert result.active_ask is not None
    assert result.active_ask.id == "ask-waiting"
    assert result.active_ask.task_ref == TaskRef.published("task-1")


def test_projection_matches_plan_node_id_to_published_task_ref() -> None:
    store = InMemoryAskStore(
        [
            _ask(
                "ask-waiting",
                task_id="published-task-1",
                created_at=NOW + timedelta(seconds=1),
            ),
        ]
    )
    service = DefaultAskProjectionService(store)
    tree = TaskTreeView(
        id="tree-1",
        session_id="s1",
        title="Task Tree",
        status="running",
        nodes=(
            _node(
                "plan-node-1",
                execution="waiting_for_user",
                status="waiting_user",
                task_ref=TaskRef.published("published-task-1"),
            ),
        ),
    )

    result = service.list_asks(
        "s1",
        statuses=("pending",),
        task_id="plan-node-1",
        task_tree=tree,
    )

    assert [ask.id for ask in result.asks] == ["ask-waiting"]
    assert result.active_ask is not None
    assert result.active_ask.id == "ask-waiting"
    assert result.active_ask.task_node_id == "published-task-1"


def test_projection_get_ask_returns_view() -> None:
    store = InMemoryAskStore([_ask("ask-1", task_id="task-1")])
    service = DefaultAskProjectionService(store)

    view = service.get_ask("s1", "ask-1")

    assert view is not None
    assert view.id == "ask-1"
    assert view.task_node_id == "task-1"
    assert view.status == "pending"


def test_select_active_ask_falls_back_to_oldest_blocking_pending() -> None:
    store = InMemoryAskStore(
        [
            _ask("ask-new", task_id="task-2", created_at=NOW + timedelta(seconds=1)),
            _ask("ask-old", task_id="task-1", created_at=NOW),
        ]
    )
    asks = DefaultAskProjectionService(store).pending_asks("s1")

    active = select_active_ask(asks)

    assert active is not None
    assert active.id == "ask-old"


def test_select_active_ask_ignores_non_waiting_asks_when_task_tree_exists() -> None:
    store = InMemoryAskStore(
        [
            _ask("ask-other", task_id="other", created_at=NOW),
            _ask(
                "ask-session",
                task_id=None,
                blocking=False,
                created_at=NOW + timedelta(seconds=1),
            ),
        ]
    )
    asks = DefaultAskProjectionService(store).pending_asks("s1")
    tree = TaskTreeView(
        id="tree-1",
        session_id="s1",
        title="Task Tree",
        status="running",
        nodes=(_node("task-1", execution="pending", status="queued"),),
    )

    active = select_active_ask(asks, task_tree=tree)

    assert active is None


def _ask(
    ask_id: str,
    *,
    task_id: str | None,
    blocking: bool = True,
    created_at: datetime = NOW,
) -> AskRequest:
    return AskRequest(
        ask_id=ask_id,
        session_id="s1",
        task_id=task_id,
        question="What should the agent use?",
        reason="The agent needs user-owned missing information.",
        blocking=blocking,
        created_at=created_at,
    )


def _node(
    task_id: str,
    *,
    execution: str,
    status: str,
    task_ref: TaskRef | None = None,
) -> TaskNodeCardView:
    resolved_task_ref = task_ref or TaskRef.published(task_id)
    return TaskNodeCardView(
        id=task_id,
        task_ref=resolved_task_ref,
        title=f"Task {task_id}",
        summary=f"Do {task_id}.",
        status=status,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )
