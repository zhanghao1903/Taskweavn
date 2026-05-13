"""Replayable Task interaction timeline.

The timeline layer is read-only. It does not decide Task state; it collects
facts from draft authoring, messages, confirmations, EventStream, file
summaries, and result summaries into a stable chronological view.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import ClassVar, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.core import EventStream
from taskweavn.interaction import AgentMessage, MessageStream
from taskweavn.task.models import DraftToPublishedMapping, TaskRef
from taskweavn.task.projection import (
    FileChangeStore,
    TaskProjectionService,
    TaskSummaryStore,
)
from taskweavn.task.stores import DraftTaskStore
from taskweavn.task.views import TaskDetailView

TimelineEntrySource = Literal["draft", "message", "confirmation", "event", "file", "summary"]


def _new_id() -> str:
    return uuid4().hex


class _FrozenTimelineModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class TaskInteractionEntry(_FrozenTimelineModel):
    entry_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    task_ref: TaskRef
    occurred_at: datetime
    source: TimelineEntrySource
    kind: str = Field(min_length=1)
    actor: str | None = None
    summary: str = Field(min_length=1)
    payload_ref: str | None = None


class TaskInteractionTimeline(_FrozenTimelineModel):
    session_id: str = Field(min_length=1)
    task_ref: TaskRef
    entries: tuple[TaskInteractionEntry, ...] = ()
    cursor: str | None = None


class TaskInteractionSnapshot(_FrozenTimelineModel):
    task_detail: TaskDetailView
    timeline: TaskInteractionTimeline


@runtime_checkable
class DraftPublicationStore(Protocol):
    """Read side for draft-to-published identity lineage."""

    def list_for_draft(
        self,
        session_id: str,
        draft_task_id: str,
    ) -> list[DraftToPublishedMapping]: ...

    def list_for_task(
        self,
        session_id: str,
        task_id: str,
    ) -> list[DraftToPublishedMapping]: ...


@runtime_checkable
class TaskInteractionTimelineService(Protocol):
    def get_timeline(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        include_subtree: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TaskInteractionTimeline: ...

    def get_snapshot(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> TaskInteractionSnapshot: ...


class DefaultTaskInteractionTimelineService:
    """Default timeline service stitched from existing read-side protocols."""

    def __init__(
        self,
        *,
        projection_service: TaskProjectionService,
        draft_store: DraftTaskStore | None = None,
        message_stream: MessageStream | None = None,
        event_stream: EventStream | None = None,
        file_change_store: FileChangeStore | None = None,
        summary_store: TaskSummaryStore | None = None,
        publication_store: DraftPublicationStore | None = None,
    ) -> None:
        self._projection_service = projection_service
        self._draft_store = draft_store
        self._message_stream = message_stream
        self._event_stream = event_stream
        self._file_change_store = file_change_store
        self._summary_store = summary_store
        self._publication_store = publication_store

    def get_timeline(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        include_subtree: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TaskInteractionTimeline:
        entries = self._collect_entries(
            session_id,
            task_ref,
            include_subtree=include_subtree,
            include_mapped_draft=True,
        )
        entries = _sort_entries(entries)
        if cursor is not None:
            entries = _entries_after_cursor(entries, cursor)
        if limit is not None:
            entries = entries[:limit]
        next_cursor = entries[-1].entry_id if entries else cursor
        return TaskInteractionTimeline(
            session_id=session_id,
            task_ref=task_ref,
            entries=tuple(entries),
            cursor=next_cursor,
        )

    def get_snapshot(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> TaskInteractionSnapshot:
        return TaskInteractionSnapshot(
            task_detail=self._projection_service.get_task_detail(session_id, task_ref),
            timeline=self.get_timeline(session_id, task_ref),
        )

    def _collect_entries(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        include_subtree: bool,
        include_mapped_draft: bool,
    ) -> list[TaskInteractionEntry]:
        entries: list[TaskInteractionEntry] = []
        if task_ref.kind == "draft":
            entries.extend(self._draft_entries(session_id, task_ref))
            entries.extend(self._publication_entries_for_draft(session_id, task_ref))
        elif include_mapped_draft:
            entries.extend(self._mapped_draft_entries_for_task(session_id, task_ref))

        entries.extend(self._message_entries(session_id, task_ref))
        entries.extend(self._event_entries(session_id, task_ref))
        entries.extend(self._file_entries(session_id, task_ref, include_subtree=include_subtree))
        entries.extend(self._summary_entries(session_id, task_ref))
        return entries

    def _draft_entries(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> list[TaskInteractionEntry]:
        if self._draft_store is None:
            return []
        node = self._draft_store.get_node(session_id, task_ref.id)
        if node is None:
            return []
        entries = [
            TaskInteractionEntry(
                entry_id=_entry_id("draft", task_ref.id, "created", node.draft_task_id),
                session_id=session_id,
                task_ref=task_ref,
                occurred_at=node.created_at,
                source="draft",
                kind="draft.created",
                actor=node.created_by,
                summary=f"Draft task created: {node.title}",
                payload_ref=node.draft_task_id,
            )
        ]
        if node.updated_at > node.created_at:
            entries.append(
                TaskInteractionEntry(
                    entry_id=_entry_id("draft", task_ref.id, "status", node.version),
                    session_id=session_id,
                    task_ref=task_ref,
                    occurred_at=node.updated_at,
                    source="draft",
                    kind=f"draft.{node.status}",
                    actor=node.created_by,
                    summary=f"Draft task status is {node.status}: {node.title}",
                    payload_ref=node.draft_task_id,
                )
            )
        return entries

    def _publication_entries_for_draft(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> list[TaskInteractionEntry]:
        if self._publication_store is None:
            return []
        return [
            TaskInteractionEntry(
                entry_id=_entry_id(
                    "draft",
                    task_ref.id,
                    "published",
                    mapping.publish_command_id,
                ),
                session_id=session_id,
                task_ref=task_ref,
                occurred_at=mapping.published_at,
                source="draft",
                kind="draft.published",
                actor="system",
                summary=f"Draft task published as {mapping.task_id}",
                payload_ref=mapping.publish_command_id,
            )
            for mapping in self._publication_store.list_for_draft(session_id, task_ref.id)
        ]

    def _mapped_draft_entries_for_task(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> list[TaskInteractionEntry]:
        if self._publication_store is None:
            return []
        entries: list[TaskInteractionEntry] = []
        for mapping in self._publication_store.list_for_task(session_id, task_ref.id):
            draft_ref = TaskRef.draft(mapping.draft_task_id)
            entries.extend(
                self._collect_entries(
                    session_id,
                    draft_ref,
                    include_subtree=False,
                    include_mapped_draft=False,
                )
            )
        return entries

    def _message_entries(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> list[TaskInteractionEntry]:
        if self._message_stream is None:
            return []
        return [
            _entry_from_message(message, task_ref)
            for message in self._message_stream.list_for_task(task_ref.id)
            if message.session_id == session_id
        ]

    def _event_entries(self, session_id: str, task_ref: TaskRef) -> list[TaskInteractionEntry]:
        if task_ref.kind != "published" or self._event_stream is None:
            return []
        iter_for_task = getattr(self._event_stream, "iter_for_task", None)
        if not callable(iter_for_task):
            return []
        return [
            TaskInteractionEntry(
                entry_id=_entry_id("event", task_ref.id, event.event_id),
                session_id=session_id,
                task_ref=task_ref,
                occurred_at=event.timestamp,
                source="event",
                kind=f"event.{event.kind}",
                actor=getattr(event, "source", None),
                summary=f"{event.kind} recorded",
                payload_ref=event.event_id,
            )
            for event in iter_for_task(task_ref.id)
        ]

    def _file_entries(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        include_subtree: bool,
    ) -> list[TaskInteractionEntry]:
        if task_ref.kind != "published" or self._file_change_store is None:
            return []
        return [
            TaskInteractionEntry(
                entry_id=_entry_id("file", task_ref.id, change.change_id),
                session_id=session_id,
                task_ref=task_ref,
                occurred_at=change.recorded_at,
                source="file",
                kind=f"file.{change.change_type}",
                actor=None,
                summary=f"{change.path}: {change.summary}",
                payload_ref=change.change_id,
            )
            for change in self._file_change_store.list_for_task(
                session_id,
                task_ref.id,
                recursive=include_subtree,
            )
        ]

    def _summary_entries(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> list[TaskInteractionEntry]:
        if task_ref.kind != "published" or self._summary_store is None:
            return []
        summary = self._summary_store.get(session_id, task_ref.id)
        if summary is None:
            return []
        return [
            TaskInteractionEntry(
                entry_id=_entry_id(
                    "summary",
                    task_ref.id,
                    summary.updated_at.isoformat(),
                ),
                session_id=session_id,
                task_ref=task_ref,
                occurred_at=summary.updated_at,
                source="summary",
                kind="summary.updated",
                actor="system",
                summary=summary.summary,
                payload_ref=task_ref.id,
            )
        ]


def _entry_from_message(message: AgentMessage, task_ref: TaskRef) -> TaskInteractionEntry:
    source: TimelineEntrySource = "message"
    kind = f"message.{message.message_type}"
    if message.message_type == "actionable":
        source = "confirmation"
        kind = "confirmation.created"
    elif message.message_type == "response":
        source = "confirmation"
        kind = "confirmation.resolved"
    return TaskInteractionEntry(
        entry_id=_entry_id("message", task_ref.id, message.message_id),
        session_id=message.session_id,
        task_ref=task_ref,
        occurred_at=message.created_at,
        source=source,
        kind=kind,
        actor=message.agent_id,
        summary=message.content,
        payload_ref=message.message_id,
    )


def _entry_id(*parts: object) -> str:
    return ":".join(str(part) for part in parts)


def _sort_entries(entries: Iterable[TaskInteractionEntry]) -> list[TaskInteractionEntry]:
    return sorted(
        entries,
        key=lambda entry: (
            entry.occurred_at,
            entry.source,
            entry.kind,
            entry.payload_ref or entry.entry_id,
        ),
    )


def _entries_after_cursor(
    entries: list[TaskInteractionEntry],
    cursor: str,
) -> list[TaskInteractionEntry]:
    for index, entry in enumerate(entries):
        if entry.entry_id == cursor:
            return entries[index + 1 :]
    return entries
