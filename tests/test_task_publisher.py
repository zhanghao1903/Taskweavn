"""Tests for TaskPublisher contracts and TaskBus-backed publishing."""

from __future__ import annotations

import pytest

from taskweavn.task import (
    DefaultTaskPublisher,
    DraftTaskNode,
    InMemoryDraftTaskStore,
    InMemoryTaskBus,
    NormalizedTaskNode,
    NormalizedTaskTree,
    PublisherRef,
    PublishRequest,
    PublishSource,
    TaskBus,
    TaskDomain,
    TaskPublisher,
    TaskPublishOptions,
)
from taskweavn.task.stores import TaskStore


def test_task_bus_and_publisher_protocol_conformance() -> None:
    bus = InMemoryTaskBus()
    publisher = DefaultTaskPublisher(task_bus=bus)

    assert isinstance(bus, TaskBus)
    assert isinstance(bus, TaskStore)
    assert isinstance(publisher, TaskPublisher)


@pytest.mark.parametrize(
    "kind",
    ["user", "collaborator", "pipeline", "scheduler", "api", "custom_tree", "agent"],
)
def test_publish_request_supports_all_publisher_kinds(kind: str) -> None:
    publisher = PublisherRef(kind=kind)  # type: ignore[arg-type]
    tree = NormalizedTaskTree(
        root_nodes=(_node("root"),),
        source=publisher,
    )

    request = PublishRequest(
        session_id="s1",
        publisher=publisher,
        source=PublishSource(source_type="custom_tree"),
        task_tree=tree,
    )

    assert request.publisher.kind == kind


def test_normalized_tree_rejects_duplicate_node_ids() -> None:
    publisher = PublisherRef(kind="custom_tree")

    with pytest.raises(ValueError, match="duplicate normalized task node id"):
        NormalizedTaskTree(
            root_nodes=(
                _node(
                    "root",
                    children=(_node("root", parent_id="root"),),
                ),
            ),
            source=publisher,
        )


def test_normalized_tree_rejects_parent_mismatch() -> None:
    publisher = PublisherRef(kind="custom_tree")

    with pytest.raises(ValueError, match="expected 'root'"):
        NormalizedTaskTree(
            root_nodes=(
                _node(
                    "root",
                    children=(_node("child", parent_id="wrong"),),
                ),
            ),
            source=publisher,
        )


def test_publish_request_requires_task_tree_or_natural_language() -> None:
    with pytest.raises(ValueError, match="requires task_tree or natural_language_input"):
        PublishRequest(
            session_id="s1",
            publisher=PublisherRef(kind="api"),
        )


def test_preview_does_not_write_task_bus() -> None:
    bus = InMemoryTaskBus()
    publisher = DefaultTaskPublisher(task_bus=bus)
    request = _request()

    preview = publisher.preview(request)

    assert preview.ok
    assert preview.task_count == 2
    assert preview.root_count == 1
    assert bus.list_for_session("s1") == []


def test_publish_writes_pending_tasks_through_task_bus() -> None:
    bus = InMemoryTaskBus()
    publisher = DefaultTaskPublisher(task_bus=bus)
    request = _request()

    result = publisher.publish(request)
    tasks = bus.list_for_session("s1")
    root = bus.list_children("s1", None)[0]
    child = bus.list_children("s1", root.task_id)[0]

    assert result.accepted
    assert result.root_task_ids == (root.task_id,)
    assert result.published_task_ids == tuple(task.task_id for task in tasks)
    assert root.status == "pending"
    assert root.root_id == root.task_id
    assert child.parent_id == root.task_id
    assert child.root_id == root.task_id
    assert child.required_capability == "testing"
    assert child.dispatch_constraints is not None
    assert child.dispatch_constraints.preferred_agent_id == "agent.test"
    assert child.dispatch_constraints.metadata["publisher_kind"] == "custom_tree"
    assert child.dispatch_constraints.metadata["source_node_id"] == "child"
    assert child.dispatch_constraints.metadata["title"] == "Child"


def test_dry_run_publish_is_skipped_without_writing_task_bus() -> None:
    bus = InMemoryTaskBus()
    publisher = DefaultTaskPublisher(task_bus=bus)
    request = _request(dry_run=True)

    result = publisher.publish(request)

    assert result.skipped
    assert result.reason == "dry run"
    assert bus.list_for_session("s1") == []


def test_publish_draft_tree_converts_accepted_draft_to_published_tasks() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            DraftTaskNode(
                draft_task_id="root",
                session_id="s1",
                draft_tree_id="placeholder",
                title="Root",
                intent="Do root",
                required_capability="general",
            )
        ],
    )
    draft_store.add_node(
        "s1",
        tree.draft_tree_id,
        DraftTaskNode(
            draft_task_id="child",
            session_id="s1",
            draft_tree_id=tree.draft_tree_id,
            parent_draft_task_id="root",
            title="Child",
            intent="Do child",
            required_capability="testing",
        ),
        expected_tree_version=tree.version,
    )
    tree = draft_store.get_tree("s1", tree.draft_tree_id)
    draft_store.mark_accepted("s1", tree.draft_tree_id, expected_version=tree.version)
    bus = InMemoryTaskBus()
    publisher = DefaultTaskPublisher(task_bus=bus, draft_store=draft_store)

    result = publisher.publish_draft_tree("s1", tree.draft_tree_id)

    assert len(result.root_task_ids) == 1
    assert {mapping.draft_task_id for mapping in result.mappings} == {"root", "child"}
    assert {task.required_capability for task in bus.list_for_session("s1")} == {
        "general",
        "testing",
    }


def test_retry_failed_task_publishes_retry_root() -> None:
    failed = TaskDomain(
        task_id="failed",
        session_id="s1",
        root_id="failed",
        intent="Original",
        required_capability="general",
        status="failed",
        created_by="tester",
    )
    bus = InMemoryTaskBus([failed])
    publisher = DefaultTaskPublisher(task_bus=bus)

    result = publisher.retry_task("s1", "failed", "Retry with safer steps")
    retry = [task for task in bus.list_for_session("s1") if task.task_id != "failed"][0]

    assert result.root_task_ids == (retry.task_id,)
    assert retry.intent == "Retry with safer steps"
    assert retry.dispatch_constraints is not None
    assert retry.dispatch_constraints.metadata["retry_of"] == "failed"


def _request(*, dry_run: bool = False) -> PublishRequest:
    publisher = PublisherRef(kind="custom_tree", actor_id="user-1")
    tree = NormalizedTaskTree(
        root_nodes=(
            _node(
                "root",
                children=(
                    _node(
                        "child",
                        parent_id="root",
                        capability="testing",
                        agent_ref="agent.test",
                    ),
                ),
            ),
        ),
        source=publisher,
        source_ref="custom-1",
    )
    return PublishRequest(
        session_id="s1",
        publisher=publisher,
        source=PublishSource(source_type="custom_tree", source_id="custom-1"),
        task_tree=tree,
        options=TaskPublishOptions(dry_run=dry_run),
        idempotency_key="publish-1",
    )


def _node(
    node_id: str,
    *,
    parent_id: str | None = None,
    capability: str = "general",
    agent_ref: str | None = None,
    children: tuple[NormalizedTaskNode, ...] = (),
) -> NormalizedTaskNode:
    return NormalizedTaskNode(
        node_id=node_id,
        parent_id=parent_id,
        title=node_id.title(),
        intent=f"Do {node_id}",
        required_capability=capability,
        agent_ref=agent_ref,
        children=children,
    )
