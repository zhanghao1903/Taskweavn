"""Workspace-backed Task timeline source for server assembly."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass

from taskweavn.core import SqliteEventStream, WorkspaceLayout
from taskweavn.interaction import MessageStream
from taskweavn.task.models import TaskRef
from taskweavn.task.projection import (
    FileChangeStore,
    TaskProjectionService,
    TaskSummaryStore,
)
from taskweavn.task.stores import DraftTaskStore
from taskweavn.task.timeline import (
    DefaultTaskInteractionTimelineService,
    DraftPublicationStore,
    TaskInteractionSnapshot,
    TaskInteractionTimeline,
)


@dataclass(frozen=True)
class WorkspaceTaskInteractionTimelineService:
    """Read a Task timeline from workspace stores for the requested session."""

    layout: WorkspaceLayout
    projection_service: TaskProjectionService
    draft_store: DraftTaskStore | None = None
    message_stream: MessageStream | None = None
    file_change_store: FileChangeStore | None = None
    summary_store: TaskSummaryStore | None = None
    publication_store: DraftPublicationStore | None = None

    def get_timeline(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        include_subtree: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TaskInteractionTimeline:
        db_path = self.layout.session_events_db(session_id)
        stream_context = SqliteEventStream(db_path) if db_path.exists() else nullcontext(None)
        with stream_context as event_stream:
            service = DefaultTaskInteractionTimelineService(
                projection_service=self.projection_service,
                draft_store=self.draft_store,
                message_stream=self.message_stream,
                event_stream=event_stream,
                file_change_store=self.file_change_store,
                summary_store=self.summary_store,
                publication_store=self.publication_store,
            )
            return service.get_timeline(
                session_id,
                task_ref,
                include_subtree=include_subtree,
                limit=limit,
                cursor=cursor,
            )

    def get_snapshot(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> TaskInteractionSnapshot:
        return TaskInteractionSnapshot(
            task_detail=self.projection_service.get_task_detail(session_id, task_ref),
            timeline=self.get_timeline(session_id, task_ref),
        )


__all__ = ["WorkspaceTaskInteractionTimelineService"]
