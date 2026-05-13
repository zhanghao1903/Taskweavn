"""Command mapping for Task-first UI actions.

The command layer translates UI intent into backend boundaries. It does not
own Task truth: draft edits go to DraftTaskStore, user-visible messages go to
MessageBus, and publishing/retry go through a TaskPublisher boundary.
"""

from __future__ import annotations

from typing import ClassVar, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.interaction import AgentMessage, MessageBus
from taskweavn.task.models import (
    DraftToPublishedMapping,
    TaskDomain,
    TaskNodePatch,
    TaskRef,
)
from taskweavn.task.stores import DraftTaskStore, TaskStore

TaskGuidanceMode = Literal["guidance", "constraint", "clarification", "correction"]
CommandStatus = Literal["accepted", "rejected"]


def _new_id() -> str:
    return uuid4().hex


class _FrozenCommandModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class TaskPublishResult(_FrozenCommandModel):
    """Result from publishing draft/retry tasks through a publisher boundary."""

    root_task_ids: tuple[str, ...] = ()
    mappings: tuple[DraftToPublishedMapping, ...] = ()
    rejected_task_ids: tuple[str, ...] = ()


class CommandResult(_FrozenCommandModel):
    """Uniform command result returned to UI/server callers."""

    command_id: str = Field(default_factory=_new_id)
    status: CommandStatus
    message: str
    affected_task_refs: tuple[TaskRef, ...] = ()
    emitted_message_ids: tuple[str, ...] = ()
    published_task_ids: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


@runtime_checkable
class PublishedTaskEditor(Protocol):
    """Boundary for editing a published but not-yet-running Task."""

    def update_task_node(
        self,
        session_id: str,
        task_id: str,
        patch: TaskNodePatch,
    ) -> TaskDomain: ...


@runtime_checkable
class TaskPublisher(Protocol):
    """Boundary for publish/retry flows that should later call TaskBus."""

    def publish_draft_tree(self, session_id: str, draft_tree_id: str) -> TaskPublishResult: ...

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> TaskPublishResult: ...


@runtime_checkable
class TaskCommandService(Protocol):
    def update_task_node(
        self,
        session_id: str,
        task_ref: TaskRef,
        patch: TaskNodePatch,
        *,
        expected_version: int | None = None,
    ) -> CommandResult: ...

    def append_task_message(
        self,
        session_id: str,
        task_ref: TaskRef,
        content: str,
        *,
        mode: TaskGuidanceMode,
    ) -> CommandResult: ...

    def resolve_confirmation(
        self,
        session_id: str,
        confirmation_id: str,
        value: str,
        *,
        note: str | None = None,
    ) -> CommandResult: ...

    def publish_task_tree(self, session_id: str, draft_tree_id: str) -> CommandResult: ...

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> CommandResult: ...


class DefaultTaskCommandService:
    """Default command mapper for Task-first UI operations."""

    def __init__(
        self,
        *,
        task_store: TaskStore,
        draft_store: DraftTaskStore | None = None,
        message_bus: MessageBus | None = None,
        published_task_editor: PublishedTaskEditor | None = None,
        task_publisher: TaskPublisher | None = None,
    ) -> None:
        self._task_store = task_store
        self._draft_store = draft_store
        self._message_bus = message_bus
        self._published_task_editor = published_task_editor
        self._task_publisher = task_publisher

    def update_task_node(
        self,
        session_id: str,
        task_ref: TaskRef,
        patch: TaskNodePatch,
        *,
        expected_version: int | None = None,
    ) -> CommandResult:
        if task_ref.kind == "draft":
            return self._update_draft_task(session_id, task_ref, patch, expected_version)
        return self._update_published_task(session_id, task_ref, patch)

    def append_task_message(
        self,
        session_id: str,
        task_ref: TaskRef,
        content: str,
        *,
        mode: TaskGuidanceMode,
    ) -> CommandResult:
        if self._message_bus is None:
            return _rejected("message bus is not configured")
        if not content.strip():
            return _rejected("task message content must not be empty")
        message = AgentMessage(
            session_id=session_id,
            task_id=task_ref.id,
            agent_id="user",
            message_type="informational",
            content=content,
            context={"mode": mode, "task_ref_kind": task_ref.kind},
        )
        self._message_bus.publish(message)
        return _accepted(
            "task message appended",
            affected_task_refs=(task_ref,),
            emitted_message_ids=(message.message_id,),
        )

    def resolve_confirmation(
        self,
        session_id: str,
        confirmation_id: str,
        value: str,
        *,
        note: str | None = None,
    ) -> CommandResult:
        if self._message_bus is None:
            return _rejected("message bus is not configured")
        parent = self._message_bus.stream.get(confirmation_id)
        if parent is None:
            return _rejected(f"confirmation {confirmation_id!r} not found")
        if parent.session_id != session_id:
            return _rejected("confirmation belongs to a different session")
        if parent.message_type != "actionable":
            return _rejected("confirmation must reference an actionable message")
        if not value.strip():
            return _rejected("confirmation value must not be empty")

        response = AgentMessage(
            session_id=session_id,
            task_id=parent.task_id,
            agent_id="user",
            parent_message_id=parent.message_id,
            message_type="response",
            content=note or value,
            response_source="user",
            response_value=value,
        )
        self._message_bus.publish(response)
        affected = _task_ref_for_message(parent)
        return _accepted(
            "confirmation resolved",
            affected_task_refs=affected,
            emitted_message_ids=(response.message_id,),
        )

    def publish_task_tree(self, session_id: str, draft_tree_id: str) -> CommandResult:
        if self._task_publisher is None:
            return _rejected("task publisher is not configured")
        result = self._task_publisher.publish_draft_tree(session_id, draft_tree_id)
        return _accepted(
            "draft task tree published",
            affected_task_refs=tuple(
                TaskRef.published(task_id) for task_id in result.root_task_ids
            ),
            published_task_ids=result.root_task_ids,
        )

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> CommandResult:
        task = self._task_store.get(session_id, task_id)
        if task is None:
            return _rejected(f"task {task_id!r} not found")
        if task.status != "failed":
            return _rejected("only failed tasks can be retried")
        if self._task_publisher is None:
            return _rejected("task publisher is not configured")
        result = self._task_publisher.retry_task(session_id, task_id, instruction)
        return _accepted(
            "retry task published",
            affected_task_refs=tuple(
                TaskRef.published(task_id) for task_id in result.root_task_ids
            ),
            published_task_ids=result.root_task_ids,
        )

    def _update_draft_task(
        self,
        session_id: str,
        task_ref: TaskRef,
        patch: TaskNodePatch,
        expected_version: int | None,
    ) -> CommandResult:
        if self._draft_store is None:
            return _rejected("draft store is not configured")
        node = self._draft_store.get_node(session_id, task_ref.id)
        if node is None:
            return _rejected(f"draft task {task_ref.id!r} not found")
        if node.status != "draft":
            return _rejected(f"draft task cannot be edited while status is {node.status}")
        updated = self._draft_store.update_node(
            session_id,
            task_ref.id,
            patch,
            expected_version=expected_version or node.version,
        )
        return _accepted(
            "draft task updated",
            affected_task_refs=(TaskRef.draft(updated.draft_task_id),),
        )

    def _update_published_task(
        self,
        session_id: str,
        task_ref: TaskRef,
        patch: TaskNodePatch,
    ) -> CommandResult:
        task = self._task_store.get(session_id, task_ref.id)
        if task is None:
            return _rejected(f"task {task_ref.id!r} not found")
        if task.status != "pending":
            return _rejected("only pending published tasks can be edited")
        if self._published_task_editor is None:
            return _rejected("published task editor is not configured")
        updated = self._published_task_editor.update_task_node(session_id, task_ref.id, patch)
        return _accepted(
            "published task updated",
            affected_task_refs=(TaskRef.published(updated.task_id),),
        )


def _accepted(
    message: str,
    *,
    affected_task_refs: tuple[TaskRef, ...] = (),
    emitted_message_ids: tuple[str, ...] = (),
    published_task_ids: tuple[str, ...] = (),
) -> CommandResult:
    return CommandResult(
        status="accepted",
        message=message,
        affected_task_refs=affected_task_refs,
        emitted_message_ids=emitted_message_ids,
        published_task_ids=published_task_ids,
    )


def _rejected(message: str) -> CommandResult:
    return CommandResult(status="rejected", message=message)


def _task_ref_for_message(message: AgentMessage) -> tuple[TaskRef, ...]:
    if message.task_id is None:
        return ()
    kind = message.context.get("task_ref_kind")
    if kind == "draft":
        return (TaskRef.draft(message.task_id),)
    return (TaskRef.published(message.task_id),)
