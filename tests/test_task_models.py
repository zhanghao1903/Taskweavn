"""Tests for Task domain and draft authoring models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from taskweavn.task import (
    DraftTaskNode,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskDispatchConstraints,
    TaskDomain,
    TaskNodePatch,
    TaskRef,
)


def test_task_ref_factory_methods() -> None:
    assert TaskRef.draft("d1") == TaskRef(kind="draft", id="d1")
    assert TaskRef.published("t1") == TaskRef(kind="published", id="t1")


def test_task_ref_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        TaskRef(kind="other", id="x")  # type: ignore[arg-type]


def test_task_ref_is_frozen() -> None:
    ref = TaskRef.published("t1")
    with pytest.raises(ValidationError):
        ref.id = "t2"


def test_task_domain_root_task_requires_matching_root_id() -> None:
    task = TaskDomain(
        task_id="root",
        session_id="s1",
        root_id="root",
        intent="Prepare release notes",
        required_capability="writing",
        created_by="user",
    )
    assert task.parent_id is None
    assert task.status == "pending"
    assert task.created_at.tzinfo is UTC


def test_task_domain_rejects_mismatched_root_id_for_root() -> None:
    with pytest.raises(ValidationError, match="root_id"):
        TaskDomain(
            task_id="root",
            session_id="s1",
            root_id="other",
            intent="Prepare release notes",
            required_capability="writing",
            created_by="user",
        )


def test_task_domain_allows_child_with_parent_and_root() -> None:
    task = TaskDomain(
        task_id="child",
        session_id="s1",
        parent_id="root",
        root_id="root",
        order_index=1,
        intent="Draft changelog",
        required_capability="writing",
        created_by="collaborator_agent",
    )
    assert task.parent_id == "root"
    assert task.root_id == "root"


def test_task_domain_carries_dispatch_constraints() -> None:
    constraints = TaskDispatchConstraints(
        preferred_agent_id="writer-1",
        required_capabilities=("writing", "review"),
        metadata={"reason": "domain expert"},
    )
    task = TaskDomain(
        task_id="root",
        session_id="s1",
        root_id="root",
        intent="Prepare release notes",
        required_capability="writing",
        created_by="user",
        dispatch_constraints=constraints,
    )
    assert task.dispatch_constraints is constraints


def test_task_domain_waiting_for_user_requires_active_ask_linkage() -> None:
    with pytest.raises(ValidationError, match="waiting_for_ask_id"):
        TaskDomain(
            task_id="root",
            session_id="s1",
            root_id="root",
            intent="Prepare release notes",
            required_capability="writing",
            created_by="user",
            status="waiting_for_user",
        )


def test_task_domain_rejects_stale_active_ask_linkage() -> None:
    with pytest.raises(ValidationError, match="active ASK linkage"):
        TaskDomain(
            task_id="root",
            session_id="s1",
            root_id="root",
            intent="Prepare release notes",
            required_capability="writing",
            created_by="user",
            waiting_for_ask_id="ask-1",
        )


def test_task_domain_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        TaskDomain.model_validate(
            {
                "task_id": "root",
                "session_id": "s1",
                "root_id": "root",
                "intent": "Prepare release notes",
                "required_capability": "writing",
                "created_by": "user",
                "selected": True,
            }
        )


def test_task_node_patch_is_minimal_and_frozen() -> None:
    patch = TaskNodePatch(intent="Add smoke test", constraints_add=("safe workspace",))
    assert patch.intent == "Add smoke test"
    assert patch.constraints_add == ("safe workspace",)
    with pytest.raises(ValidationError):
        patch.intent = "tamper"


def test_draft_task_node_defaults() -> None:
    node = DraftTaskNode(
        session_id="s1",
        draft_tree_id="tree1",
        title="Draft changelog",
        intent="Prepare changelog draft",
        required_capability="writing",
    )
    assert node.status == "draft"
    assert node.version == 1
    assert node.created_by == "collaborator_agent"
    assert node.updated_at >= node.created_at


def test_draft_task_node_rejects_updated_before_created() -> None:
    created = datetime(2026, 1, 2, tzinfo=UTC)
    updated = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="updated_at"):
        DraftTaskNode(
            session_id="s1",
            draft_tree_id="tree1",
            title="Draft changelog",
            intent="Prepare changelog draft",
            required_capability="writing",
            created_at=created,
            updated_at=updated,
        )


def test_draft_task_tree_validates_root_nodes() -> None:
    root = DraftTaskNode(
        draft_task_id="d1",
        session_id="s1",
        draft_tree_id="tree1",
        title="Prepare release",
        intent="Prepare release notes",
        required_capability="writing",
    )
    tree = DraftTaskTree(
        draft_tree_id="tree1",
        session_id="s1",
        root_nodes=(root,),
    )
    assert tree.root_nodes == (root,)


def test_draft_task_tree_rejects_session_mismatch() -> None:
    root = DraftTaskNode(
        draft_task_id="d1",
        session_id="s2",
        draft_tree_id="tree1",
        title="Prepare release",
        intent="Prepare release notes",
        required_capability="writing",
    )
    with pytest.raises(ValidationError, match="session_id"):
        DraftTaskTree(
            draft_tree_id="tree1",
            session_id="s1",
            root_nodes=(root,),
        )


def test_draft_task_tree_rejects_non_root_root_node() -> None:
    root = DraftTaskNode(
        draft_task_id="d1",
        session_id="s1",
        draft_tree_id="tree1",
        parent_draft_task_id="parent",
        title="Prepare release",
        intent="Prepare release notes",
        required_capability="writing",
    )
    with pytest.raises(ValidationError, match="parent_draft_task_id"):
        DraftTaskTree(
            draft_tree_id="tree1",
            session_id="s1",
            root_nodes=(root,),
        )


def test_draft_task_tree_rejects_duplicate_root_order() -> None:
    first = DraftTaskNode(
        draft_task_id="d1",
        session_id="s1",
        draft_tree_id="tree1",
        order_index=0,
        title="Prepare release",
        intent="Prepare release notes",
        required_capability="writing",
    )
    second = DraftTaskNode(
        draft_task_id="d2",
        session_id="s1",
        draft_tree_id="tree1",
        order_index=0,
        title="Validate release",
        intent="Run checks",
        required_capability="testing",
    )
    with pytest.raises(ValidationError, match="order_index"):
        DraftTaskTree(
            draft_tree_id="tree1",
            session_id="s1",
            root_nodes=(first, second),
        )


def test_draft_to_published_mapping_carries_lineage() -> None:
    mapping = DraftToPublishedMapping(
        session_id="s1",
        draft_tree_id="tree1",
        draft_task_id="d1",
        task_id="t1",
        publish_command_id="cmd1",
    )
    assert mapping.draft_task_id == "d1"
    assert mapping.task_id == "t1"
    assert mapping.published_at.tzinfo is UTC
