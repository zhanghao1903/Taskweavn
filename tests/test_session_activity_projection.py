"""Tests for Session Conversation / Activity projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from taskweavn.server.ui_contract import (
    AskRequestView,
    ConfirmationActionView,
    FileChangeItemView,
    FileChangeSummaryView,
    PlanView,
    ResultCardView,
    SessionMessageView,
    TaskNodeCardView,
)
from taskweavn.server.ui_contract.session_activity_projection import (
    DefaultSessionActivityProjectionService,
)

NOW = datetime(2026, 6, 14, 0, 0, tzinfo=UTC)


def test_project_session_activity_from_safe_ui_facts() -> None:
    projection = DefaultSessionActivityProjectionService()
    response = projection.project(
        session_id="session-1",
        messages=(
            SessionMessageView(
                id="message-1",
                session_id="session-1",
                task_node_id=None,
                kind="informational",
                title="User message",
                body="Build a docs site",
                created_at=NOW,
            ),
        ),
        active_plan=_plan(),
        pending_asks=(
            AskRequestView(
                id="ask-1",
                session_id="session-1",
                task_node_id="task-1",
                question="Which audience should the docs target?",
                reason="The plan needs a target reader.",
                answer_type="free_text",
                allow_free_text=True,
                allow_no_option_with_text=True,
                blocking=True,
                status="pending",
                created_at=NOW + timedelta(minutes=1),
            ),
        ),
        confirmations=(
            ConfirmationActionView(
                id="confirmation-1",
                session_id="session-1",
                task_node_id="task-1",
                title="Publish plan?",
                body="Confirm the draft plan before execution.",
                status="pending",
                created_at=NOW + timedelta(minutes=2),
            ),
        ),
        result=ResultCardView(
            id="result-1",
            session_id="session-1",
            task_node_id="task-1",
            title="Result ready",
            summary="Docs outline was created.",
            updated_at=NOW + timedelta(minutes=3),
        ),
        file_change_summary=FileChangeSummaryView(
            session_id="session-1",
            task_node_id="task-1",
            recursive=False,
            changed_files=(
                FileChangeItemView(
                    path="docs/index.md",
                    change_type="created",
                    summary="Created docs index.",
                ),
            ),
            summary="1 file changed.",
            updated_at=NOW + timedelta(minutes=4),
        ),
    )

    assert response.session_id == "session-1"
    assert response.total_count == 7
    assert response.next_cursor is None
    assert {item.kind for item in response.items} == {
        "file_summary",
        "result_ready",
        "confirmation_requested",
        "ask_asked",
        "plan_updated",
        "task_created",
        "user_input",
    }
    by_kind = {item.kind: item for item in response.items}
    assert by_kind["file_summary"].related_refs[0].id == "docs/index.md"
    assert by_kind["result_ready"].side_effect == "evidence_effect"
    assert by_kind["ask_asked"].related_refs[0].object_ref is not None
    assert by_kind["ask_asked"].related_refs[0].object_ref.kind == "ask"
    task_item = next(item for item in response.items if item.kind == "task_created")
    assert task_item.task_node_id == "task-1"
    assert by_kind["user_input"].side_effect == "context_effect"


def test_project_session_activity_pages_by_offset_cursor() -> None:
    projection = DefaultSessionActivityProjectionService()
    messages = tuple(
        SessionMessageView(
            id=f"message-{index}",
            session_id="session-1",
            task_node_id=None,
            kind="informational",
            title="User message",
            body=f"Message {index}",
            created_at=NOW + timedelta(minutes=index),
        )
        for index in range(3)
    )

    first_page = projection.project(
        session_id="session-1",
        messages=messages,
        limit=2,
    )
    second_page = projection.project(
        session_id="session-1",
        messages=messages,
        limit=2,
        cursor=first_page.next_cursor,
    )

    assert [item.source_id for item in first_page.items] == ["message-2", "message-1"]
    assert first_page.next_cursor == "2"
    assert [item.source_id for item in second_page.items] == ["message-0"]
    assert second_page.next_cursor is None


def test_project_session_activity_rejects_invalid_cursor() -> None:
    projection = DefaultSessionActivityProjectionService()

    with pytest.raises(ValueError, match="integer offset"):
        projection.project(session_id="session-1", cursor="newest")


def _plan() -> PlanView:
    task = TaskNodeCardView(
        id="task-1",
        plan_id="plan-1",
        task_index="1",
        title="Draft docs outline",
        summary="Create a docs outline.",
        status="draft",
        execution="not_started",
        display_index=1,
        version=1,
    )
    return PlanView(
        id="plan-1",
        session_id="session-1",
        title="Docs plan",
        summary="Draft the documentation structure.",
        objective="Create documentation.",
        status="draft",
        task_count=1,
        task_node_ids=("task-1",),
        task_nodes=(task,),
        version=1,
    )
