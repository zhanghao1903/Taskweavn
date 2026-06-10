"""Tests for Task UI command mapping service."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from taskweavn.interaction import AgentMessage, MessageStream, Subscription
from taskweavn.task import (
    CommandResult,
    DefaultTaskCommandService,
    DraftTaskNode,
    DraftTaskStore,
    DraftTaskTree,
    DraftToPublishedMapping,
    PublishedTaskEditor,
    PublishedTaskInterrupter,
    PublishedTaskRetrier,
    TaskCommandService,
    TaskDomain,
    TaskNodePatch,
    TaskPublisher,
    TaskPublishResult,
    TaskRef,
    TaskStore,
)


class _TaskStore:
    def __init__(self, tasks: list[TaskDomain]) -> None:
        self.tasks = tasks

    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        return next(
            (
                task
                for task in self.tasks
                if task.session_id == session_id and task.task_id == task_id
            ),
            None,
        )

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        return [task for task in self.tasks if task.session_id == session_id]

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        return [
            task
            for task in self.tasks
            if task.session_id == session_id and task.parent_id == parent_id
        ]


class _DraftStore:
    def __init__(self, nodes: list[DraftTaskNode]) -> None:
        self.nodes = {node.draft_task_id: node for node in nodes}
        self.last_expected_version: int | None = None

    def create_tree(
        self,
        session_id: str,
        roots: list[DraftTaskNode],
        *,
        title: str | None = None,
        summary: str | None = None,
    ) -> DraftTaskTree:
        return DraftTaskTree(
            session_id=session_id,
            draft_tree_id="tree1",
            title=title,
            summary=summary,
            root_nodes=tuple(roots),
        )

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        roots = tuple(node for node in self.nodes.values() if node.session_id == session_id)
        return DraftTaskTree(session_id=session_id, draft_tree_id=draft_tree_id, root_nodes=roots)

    def list_trees(self, session_id: str) -> list[DraftTaskTree]:
        return [self.get_tree(session_id, "tree1")]

    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]:
        return [
            node
            for node in self.nodes.values()
            if node.session_id == session_id and node.draft_tree_id == draft_tree_id
        ]

    def list_children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]:
        return [
            node
            for node in self.list_nodes(session_id, draft_tree_id)
            if node.parent_draft_task_id == parent_draft_task_id
        ]

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None:
        node = self.nodes.get(draft_task_id)
        if node is None or node.session_id != session_id:
            return None
        return node

    def add_node(
        self,
        session_id: str,
        draft_tree_id: str,
        node: DraftTaskNode,
        *,
        expected_tree_version: int,
    ) -> DraftTaskNode:
        self.nodes[node.draft_task_id] = node
        return node

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode:
        self.last_expected_version = expected_version
        node = self.nodes[draft_task_id]
        updated = node.model_copy(
            update={
                "title": patch.title or node.title,
                "intent": patch.intent or node.intent,
                "version": expected_version + 1,
            }
        )
        self.nodes[draft_task_id] = updated
        return updated

    def mark_accepted(
        self,
        session_id: str,
        draft_tree_id: str,
        *,
        expected_version: int,
    ) -> DraftTaskTree:
        return self.get_tree(session_id, draft_tree_id)

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
        *,
        expected_version: int | None = None,
    ) -> DraftTaskTree:
        return self.get_tree(session_id, draft_tree_id)


class _MessageStream:
    def __init__(self, messages: list[AgentMessage]) -> None:
        self.messages = messages

    def get(self, message_id: str) -> AgentMessage | None:
        return next(
            (message for message in self.messages if message.message_id == message_id),
            None,
        )

    def list_for_session(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        return iter([message for message in self.messages if message.session_id == session_id])

    def list_for_task(
        self,
        task_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        return iter([message for message in self.messages if message.task_id == task_id])

    def list_for_agent(
        self,
        agent_id: str,
        *,
        session_id: str | None = None,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        return iter([message for message in self.messages if message.agent_id == agent_id])

    def pending_actionable(
        self, session_id: str, *, task_id: str | None = None
    ) -> list[AgentMessage]:
        return [
            message
            for message in self.messages
            if message.session_id == session_id
            and message.task_id == task_id
            and message.message_type == "actionable"
        ]

    def response_for(self, message_id: str) -> AgentMessage | None:
        return next(
            (
                message
                for message in self.messages
                if message.parent_message_id == message_id and message.message_type == "response"
            ),
            None,
        )

    def thread(self, message_id: str) -> list[AgentMessage]:
        parent = self.get(message_id)
        if parent is None:
            return []
        return [
            parent,
            *[
                message
                for message in self.messages
                if message.parent_message_id == message_id
            ],
        ]

    def __len__(self) -> int:
        return len(self.messages)


class _Bus:
    def __init__(self, stream: _MessageStream) -> None:
        self._stream = stream
        self.published: list[AgentMessage] = []

    def publish(self, message: AgentMessage) -> None:
        self.published.append(message)
        self._stream.messages.append(message)

    def subscribe(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
    ) -> Subscription:
        raise NotImplementedError

    def wait_for_response(
        self,
        message_id: str,
        timeout: float | None,
    ) -> AgentMessage | None:
        return self._stream.response_for(message_id)

    @property
    def stream(self) -> MessageStream:
        return self._stream


class _PublishedEditor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, TaskNodePatch]] = []

    def update_task_node(
        self,
        session_id: str,
        task_id: str,
        patch: TaskNodePatch,
    ) -> TaskDomain:
        self.calls.append((session_id, task_id, patch))
        return _task(task_id, status="pending").model_copy(
            update={"intent": patch.intent or "edited"}
        )


class _PublishedRetrier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def retry(
        self,
        session_id: str,
        task_id: str,
        *,
        instruction: str | None = None,
    ) -> TaskDomain:
        self.calls.append((session_id, task_id, instruction))
        return _task(task_id, status="pending")


class _PublishedInterrupter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str | None]] = []

    def request_interrupt(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
        request_id: str | None = None,
    ) -> TaskDomain:
        self.calls.append((session_id, task_id, reason, request_id))
        task = _task(task_id, status="running").model_copy(
            update={
                "interrupt_requested": True,
                "interrupt_request_id": request_id,
                "interrupt_reason": reason,
            }
        )
        return task


class _Publisher:
    kind: Any = "collaborator"

    def __init__(self) -> None:
        self.publish_calls: list[tuple[str, str]] = []
        self.retry_calls: list[tuple[str, str, str | None]] = []

    def preview(self, request: Any) -> Any:
        raise NotImplementedError

    def publish(self, request: Any) -> Any:
        raise NotImplementedError

    def publish_draft_tree(self, session_id: str, draft_tree_id: str) -> TaskPublishResult:
        self.publish_calls.append((session_id, draft_tree_id))
        return TaskPublishResult(root_task_ids=("published-root",))

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> TaskPublishResult:
        self.retry_calls.append((session_id, task_id, instruction))
        return TaskPublishResult(root_task_ids=("retry-root",))


def _task(task_id: str, *, status: str = "pending") -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        root_id=task_id,
        intent=f"{task_id} intent",
        required_capability="general",
        created_by="user",
        status=status,  # type: ignore[arg-type]
    )


def _draft(status: str = "draft") -> DraftTaskNode:
    return DraftTaskNode(
        draft_task_id="d1",
        session_id="s1",
        draft_tree_id="tree1",
        title="Draft",
        intent="Draft intent",
        required_capability="general",
        status=status,  # type: ignore[arg-type]
    )


def test_command_service_protocol_conformance() -> None:
    service = DefaultTaskCommandService(task_store=_TaskStore([]))
    assert isinstance(service, TaskCommandService)
    assert isinstance(_TaskStore([]), TaskStore)
    assert isinstance(_DraftStore([_draft()]), DraftTaskStore)
    assert isinstance(_PublishedEditor(), PublishedTaskEditor)
    assert isinstance(_PublishedInterrupter(), PublishedTaskInterrupter)
    assert isinstance(_Publisher(), TaskPublisher)


def test_command_result_is_frozen_and_has_accepted_property() -> None:
    result = CommandResult(status="accepted", message="ok")
    assert result.accepted is True
    with pytest.raises(ValidationError):
        result.status = "rejected"


def test_update_draft_task_uses_draft_store_and_version() -> None:
    draft_store = _DraftStore([_draft()])
    service = DefaultTaskCommandService(
        task_store=_TaskStore([]),
        draft_store=draft_store,
    )

    result = service.update_task_node(
        "s1",
        TaskRef.draft("d1"),
        TaskNodePatch(title="Updated"),
    )

    assert result.accepted is True
    assert result.affected_task_refs == (TaskRef.draft("d1"),)
    assert draft_store.nodes["d1"].title == "Updated"
    assert draft_store.last_expected_version == 1


def test_update_draft_task_rejects_non_draft_status() -> None:
    service = DefaultTaskCommandService(
        task_store=_TaskStore([]),
        draft_store=_DraftStore([_draft(status="published")]),
    )

    result = service.update_task_node("s1", TaskRef.draft("d1"), TaskNodePatch(title="Nope"))

    assert result.accepted is False
    assert "status is published" in result.message


def test_update_published_pending_task_uses_editor() -> None:
    editor = _PublishedEditor()
    service = DefaultTaskCommandService(
        task_store=_TaskStore([_task("t1", status="pending")]),
        published_task_editor=editor,
    )

    result = service.update_task_node(
        "s1",
        TaskRef.published("t1"),
        TaskNodePatch(intent="Edited intent"),
    )

    assert result.accepted is True
    assert result.affected_task_refs == (TaskRef.published("t1"),)
    assert editor.calls[0][1] == "t1"


def test_update_published_running_task_rejected() -> None:
    service = DefaultTaskCommandService(task_store=_TaskStore([_task("t1", status="running")]))

    result = service.update_task_node("s1", TaskRef.published("t1"), TaskNodePatch(intent="Nope"))

    assert result.accepted is False
    assert "pending" in result.message


def test_append_task_message_publishes_user_message() -> None:
    stream = _MessageStream([])
    bus = _Bus(stream)
    service = DefaultTaskCommandService(task_store=_TaskStore([]), message_bus=bus)

    result = service.append_task_message(
        "s1",
        TaskRef.draft("d1"),
        "Please keep tests isolated",
        mode="guidance",
    )

    assert result.accepted is True
    assert len(bus.published) == 1
    message = bus.published[0]
    assert message.agent_id == "user"
    assert message.task_id == "d1"
    assert message.context["mode"] == "guidance"
    assert message.context["task_ref_kind"] == "draft"


def test_resolve_confirmation_publishes_response() -> None:
    parent = AgentMessage(
        message_id="confirmation-1",
        session_id="s1",
        task_id="t1",
        message_type="actionable",
        content="Proceed?",
        requires_response=True,
    )
    bus = _Bus(_MessageStream([parent]))
    service = DefaultTaskCommandService(task_store=_TaskStore([]), message_bus=bus)

    result = service.resolve_confirmation(
        "s1", "confirmation-1", "yes", note="Looks good"
    )

    assert result.accepted is True
    assert result.affected_task_refs == (TaskRef.published("t1"),)
    response = bus.published[0]
    assert response.message_type == "response"
    assert response.parent_message_id == "confirmation-1"
    assert response.response_value == "yes"
    assert response.content == "Looks good"


def test_resolve_confirmation_rejects_already_resolved_confirmation() -> None:
    parent = AgentMessage(
        message_id="confirmation-1",
        session_id="s1",
        task_id="t1",
        message_type="actionable",
        content="Proceed?",
        requires_response=True,
    )
    existing_response = AgentMessage(
        session_id="s1",
        task_id="t1",
        agent_id="user",
        parent_message_id=parent.message_id,
        message_type="response",
        content="yes",
        response_source="user",
        response_value="yes",
    )
    bus = _Bus(_MessageStream([parent, existing_response]))
    service = DefaultTaskCommandService(task_store=_TaskStore([]), message_bus=bus)

    result = service.resolve_confirmation("s1", "confirmation-1", "no")

    assert result.accepted is False
    assert "already resolved" in result.message
    assert bus.published == []


def test_resolve_confirmation_preserves_draft_task_ref_context() -> None:
    parent = AgentMessage(
        message_id="confirmation-draft",
        session_id="s1",
        task_id="d1",
        message_type="actionable",
        content="Accept draft option?",
        requires_response=True,
        context={"task_ref_kind": "draft"},
    )
    service = DefaultTaskCommandService(
        task_store=_TaskStore([]),
        message_bus=_Bus(_MessageStream([parent])),
    )

    result = service.resolve_confirmation("s1", "confirmation-draft", "yes")

    assert result.accepted is True
    assert result.affected_task_refs == (TaskRef.draft("d1"),)


def test_resolve_confirmation_rejects_non_actionable() -> None:
    parent = AgentMessage(
        message_id="info1",
        session_id="s1",
        task_id="t1",
        message_type="informational",
        content="FYI",
    )
    service = DefaultTaskCommandService(
        task_store=_TaskStore([]),
        message_bus=_Bus(_MessageStream([parent])),
    )

    result = service.resolve_confirmation("s1", "info1", "yes")

    assert result.accepted is False
    assert "actionable" in result.message


def test_publish_task_tree_uses_publisher_boundary() -> None:
    publisher = _Publisher()
    service = DefaultTaskCommandService(
        task_store=_TaskStore([]),
        task_publisher=publisher,
    )

    result = service.publish_task_tree("s1", "tree1")

    assert result.accepted is True
    assert publisher.publish_calls == [("s1", "tree1")]
    assert result.published_task_ids == ("published-root",)


def test_retry_failed_task_requeues_same_published_task() -> None:
    retrier = _PublishedRetrier()
    assert isinstance(retrier, PublishedTaskRetrier)
    message_bus = _Bus(_MessageStream([]))
    service = DefaultTaskCommandService(
        task_store=_TaskStore([_task("failed", status="failed")]),
        message_bus=message_bus,
        published_task_retrier=retrier,
    )

    result = service.retry_task("s1", "failed", "Try safer path")

    assert result.accepted is True
    assert retrier.calls == [("s1", "failed", "Try safer path")]
    assert result.affected_task_refs == (TaskRef.published("failed"),)
    assert result.published_task_ids == ()
    assert len(result.emitted_message_ids) == 1
    assert message_bus.published[0].task_id == "failed"
    assert message_bus.published[0].content == "Try safer path"


def test_retry_non_failed_task_rejected() -> None:
    service = DefaultTaskCommandService(task_store=_TaskStore([_task("pending", status="pending")]))

    result = service.retry_task("s1", "pending")

    assert result.accepted is False
    assert "failed" in result.message


def test_stop_running_task_records_interrupt_and_publishes_message() -> None:
    interrupter = _PublishedInterrupter()
    message_bus = _Bus(_MessageStream([]))
    service = DefaultTaskCommandService(
        task_store=_TaskStore([_task("running", status="running")]),
        message_bus=message_bus,
        published_task_interrupter=interrupter,
    )

    result = service.stop_task(
        "s1",
        "running",
        reason="Stop after safe point",
        request_id="stop-1",
    )

    assert result.accepted is True
    assert interrupter.calls == [("s1", "running", "Stop after safe point", "stop-1")]
    assert result.affected_task_refs == (TaskRef.published("running"),)
    assert len(result.emitted_message_ids) == 1
    message = message_bus.published[0]
    assert message.task_id == "running"
    assert message.content == "Stop requested: Stop after safe point"
    assert message.context["mode"] == "stop"
    assert message.context["interrupt_request_id"] == "stop-1"


def test_stop_terminal_task_rejected() -> None:
    service = DefaultTaskCommandService(task_store=_TaskStore([_task("done", status="done")]))

    result = service.stop_task("s1", "done")

    assert result.accepted is False
    assert "pending or running" in result.message
