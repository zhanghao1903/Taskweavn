"""Tests for Task UI projection ViewModels."""

from __future__ import annotations

from datetime import UTC

import pytest
from pydantic import ValidationError

from taskweavn.task import (
    ConfirmationActionView,
    ConfirmationOptionView,
    SessionMessageView,
    TaskCardAction,
    TaskCardBadges,
    TaskCardPermissions,
    TaskCardView,
    TaskDetailView,
    TaskFileChangeSummary,
    TaskProgressView,
    TaskRef,
    TaskSummaryView,
    TaskTreeView,
)


def _draft_card(task_id: str = "d1", *, order_index: int = 0) -> TaskCardView:
    ref = TaskRef.draft(task_id)
    return TaskCardView(
        task_ref=ref,
        root_ref=ref,
        title="Prepare release",
        intent_preview="Prepare release notes",
        status="draft",
        order_index=order_index,
        permissions=TaskCardPermissions(can_edit=True, can_publish=True),
        primary_actions=(
            TaskCardAction(kind="edit", label="Edit"),
            TaskCardAction(kind="publish", label="Publish"),
        ),
    )


def test_task_card_badges_default_to_zero() -> None:
    badges = TaskCardBadges()
    assert badges.pending_confirmation_count == 0
    assert badges.direct_file_change_count == 0


def test_task_card_badges_reject_inconsistent_child_counts() -> None:
    with pytest.raises(ValidationError, match="child_count"):
        TaskCardBadges(child_count=1, done_child_count=1, failed_child_count=1)


def test_task_progress_rejects_too_many_known_children() -> None:
    with pytest.raises(ValidationError, match="child_count"):
        TaskProgressView(child_count=1, done_child_count=1, running_child_count=1)


def test_draft_card_uses_draft_ref() -> None:
    card = _draft_card()
    assert card.task_ref == TaskRef.draft("d1")
    assert card.parent_ref is None
    assert card.depth == 0
    assert card.permissions.can_publish is True


def test_draft_status_rejects_published_ref() -> None:
    ref = TaskRef.published("t1")
    with pytest.raises(ValidationError, match="draft task_ref"):
        TaskCardView(
            task_ref=ref,
            root_ref=ref,
            title="Prepare release",
            intent_preview="Prepare release notes",
            status="draft",
        )


def test_child_card_requires_parent_ref() -> None:
    ref = TaskRef.published("t2")
    root = TaskRef.published("t1")
    with pytest.raises(ValidationError, match="parent_ref"):
        TaskCardView(
            task_ref=ref,
            root_ref=root,
            title="Draft changelog",
            intent_preview="Draft changelog",
            status="pending",
            depth=1,
        )


def test_confirmation_default_option_must_exist() -> None:
    option = ConfirmationOptionView(option_id="yes", label="Yes", value="yes")
    confirmation = ConfirmationActionView(
        task_ref=TaskRef.draft("d1"),
        prompt="Publish?",
        options=(option,),
        default_option_id="yes",
    )
    assert confirmation.default_option_id == "yes"

    with pytest.raises(ValidationError, match="default_option_id"):
        ConfirmationActionView(
            task_ref=TaskRef.draft("d1"),
            prompt="Publish?",
            options=(option,),
            default_option_id="missing",
        )


def test_message_view_carries_task_ref_and_timestamp() -> None:
    message = SessionMessageView(
        session_id="s1",
        task_ref=TaskRef.draft("d1"),
        message_type="user",
        content_summary="Please make this safer",
    )
    assert message.task_ref == TaskRef.draft("d1")
    assert message.created_at.tzinfo is UTC


def test_file_change_summary_marks_subtree_rollup() -> None:
    summary = TaskFileChangeSummary(
        owner_task_ref=TaskRef.published("t-child"),
        path="README.md",
        change_type="modified",
        summary="Updated usage notes",
        from_subtree=True,
    )
    assert summary.from_subtree is True


def test_tree_view_rejects_duplicate_task_refs() -> None:
    card = _draft_card("d1")
    with pytest.raises(ValidationError, match="unique"):
        TaskTreeView(session_id="s1", nodes=(card, card))


def test_detail_view_groups_card_related_views() -> None:
    card = _draft_card()
    message = SessionMessageView(
        session_id="s1",
        task_ref=card.task_ref,
        message_type="user",
        content_summary="Keep changes isolated",
    )
    file_change = TaskFileChangeSummary(
        owner_task_ref=card.task_ref,
        path="docs/release.md",
        change_type="created",
        summary="Created release draft",
    )
    result = TaskSummaryView(task_ref=card.task_ref, summary="Draft ready")
    detail = TaskDetailView(
        card=card,
        full_intent="Prepare release notes with isolated test paths.",
        constraints=("Do not touch main workspace files",),
        messages=(message,),
        file_changes=(file_change,),
        result_summary=result,
    )
    assert detail.card is card
    assert detail.messages == (message,)
    assert detail.result_summary is result


def test_view_models_are_frozen() -> None:
    card = _draft_card()
    with pytest.raises(ValidationError):
        card.title = "Tamper"
