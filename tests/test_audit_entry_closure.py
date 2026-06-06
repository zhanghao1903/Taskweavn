"""Focused tests for Product 1.0 Audit entry closure."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from taskweavn.core import Session, SqliteEventStream, WorkspaceLayout
from taskweavn.server.task_timeline import WorkspaceTaskInteractionTimelineService
from taskweavn.server.ui_contract import DefaultUiQueryGateway
from taskweavn.task import (
    EventStreamFileChangeStore,
    TaskCardBadges,
    TaskCardView,
    TaskDetailView,
    TaskFileChangeSummary,
    TaskInteractionEntry,
    TaskInteractionSnapshot,
    TaskInteractionTimeline,
    TaskRef,
    TaskSummaryView,
    TaskTreeView,
)
from taskweavn.tools.fs import WriteFileAction

NOW = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)


class _SessionReader:
    def __init__(self, sessions: list[Session]) -> None:
        self._sessions = {session.id: session for session in sessions}

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list(self) -> list[Session]:
        return list(self._sessions.values())


class _Projection:
    def __init__(
        self,
        tree: TaskTreeView,
        *,
        details: dict[str, TaskDetailView] | None = None,
    ) -> None:
        self._tree = tree
        self._details = details or {}

    def list_task_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> TaskTreeView:
        return self._tree

    def get_task_card(self, session_id: str, task_ref: TaskRef) -> TaskCardView:
        return self._details[task_ref.id].card

    def get_task_detail(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        message_limit: int = 100,
    ) -> TaskDetailView:
        return self._details[task_ref.id]


class _TimelineService:
    def __init__(
        self,
        entries: tuple[TaskInteractionEntry, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self._entries = entries
        self._error = error

    def get_timeline(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        include_subtree: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TaskInteractionTimeline:
        if self._error is not None:
            raise self._error
        return TaskInteractionTimeline(
            session_id=session_id,
            task_ref=task_ref,
            entries=self._entries,
            cursor=cursor,
        )

    def get_snapshot(
        self,
        session_id: str,
        task_ref: TaskRef,
    ) -> TaskInteractionSnapshot:
        raise NotImplementedError


def test_audit_records_project_timeline_closure_evidence() -> None:
    task_ref = TaskRef.published("root")
    card = _card(status="done", badges=TaskCardBadges(direct_file_change_count=1))
    change = TaskFileChangeSummary(
        change_id="change-1",
        owner_task_ref=task_ref,
        path="src/App.tsx",
        change_type="modified",
        summary="Modified src/App.tsx.",
        recorded_at=NOW + timedelta(minutes=3),
    )
    summary = TaskSummaryView(
        task_ref=task_ref,
        summary="Built the requested page.",
        updated_at=NOW + timedelta(minutes=4),
    )
    entries = (
        _entry("summary:root", task_ref, source="summary", kind="summary.updated", minutes=4),
        _entry(
            "draft:root:published:publish-1",
            TaskRef.draft("draft-root"),
            source="draft",
            kind="draft.published",
            minutes=0,
            summary="Draft task published as root",
            payload_ref="publish-1",
        ),
        _entry(
            "file:root:change-1",
            task_ref,
            source="file",
            kind="file.modified",
            minutes=3,
            summary="src/App.tsx: Modified src/App.tsx.",
            payload_ref="change-1",
        ),
        _entry(
            "message:root:message-1",
            task_ref,
            source="message",
            kind="message.informational",
            actor="user",
            minutes=1,
            summary="Please keep the page accessible.",
            payload_ref="message-1",
        ),
        _entry(
            "message:root:confirmation-1",
            task_ref,
            source="confirmation",
            kind="confirmation.created",
            minutes=2,
            summary="Create project files?",
            payload_ref="confirmation-1",
        ),
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            TaskTreeView(session_id="session-1", nodes=(card,)),
            details={
                "root": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    file_changes=(change,),
                    result_summary=summary,
                )
            },
        ),
        task_timeline_service=_TimelineService(entries),
    )

    response = gateway.list_audit_records(
        "session-1",
        task_node_id="root",
        limit=20,
    )

    assert response.ok is True
    assert response.data is not None
    records = {record.id: record for record in response.data.records}
    draft_id = "record-timeline-draft-draft:root:published:publish-1"
    expected_ids = [
        draft_id,
        "record-message-message-1",
        "record-confirmation-confirmation-1",
        "record-file-change-1",
        "record-result-published-root",
    ]
    for record_id in expected_ids:
        assert record_id in records
    assert records["record-message-message-1"].source_label == "Message stream"
    assert records["record-message-message-1"].actor == "user"
    assert records["record-confirmation-confirmation-1"].kind == "confirmation"
    assert records["record-file-change-1"].evidence_refs[0].label == (
        "Timeline file change"
    )
    assert records["record-result-published-root"].summary == "Built the requested page."
    ids = [record.id for record in response.data.records]
    positions = {record_id: ids.index(record_id) for record_id in expected_ids}
    assert positions[draft_id] < positions["record-message-message-1"]
    assert positions["record-message-message-1"] < positions[
        "record-confirmation-confirmation-1"
    ]
    assert positions["record-confirmation-confirmation-1"] < positions[
        "record-file-change-1"
    ]
    assert positions["record-file-change-1"] < positions["record-result-published-root"]


def test_audit_snapshot_degrades_when_timeline_source_fails() -> None:
    task_ref = TaskRef.published("root")
    card = _card(status="running")
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            TaskTreeView(session_id="session-1", nodes=(card,)),
            details={
                "root": TaskDetailView(card=card, full_intent=card.intent_preview),
            },
        ),
        task_timeline_service=_TimelineService(
            error=RuntimeError("raw sqlite payload /tmp/secret-prompt")
        ),
    )

    response = gateway.get_audit_snapshot("session-1", task_node_id=task_ref.id)

    assert response.ok is True
    assert response.data is not None
    records = {record.id: record for record in response.data.records}
    record = records["record-system-source-unavailable-task-timeline"]
    assert response.data.page_state.kind == "partial"
    assert "RuntimeError" in record.summary
    assert "secret-prompt" not in record.summary
    assert "record-task-published-root" in records


def test_workspace_timeline_provider_reads_session_event_stream(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    layout.bootstrap_session("session-1")
    task_ref = TaskRef.published("root")
    card = _card(status="running")
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        stream.append(
            WriteFileAction(
                event_id="action-write",
                timestamp=NOW,
                path="src/App.tsx",
                content="hello",
            ),
            task_id=task_ref.id,
        )
    service = WorkspaceTaskInteractionTimelineService(
        layout=layout,
        projection_service=_Projection(
            TaskTreeView(session_id="session-1", nodes=(card,)),
            details={
                "root": TaskDetailView(card=card, full_intent=card.intent_preview),
            },
        ),
        file_change_store=EventStreamFileChangeStore(layout),
    )

    timeline = service.get_timeline("session-1", task_ref)

    assert any(
        entry.source == "event" and entry.payload_ref == "action-write"
        for entry in timeline.entries
    )


def _session(session_id: str = "session-1") -> Session:
    return Session(
        id=session_id,
        name="Audit session",
        workspace_root=Path("/workspace"),
        created_at=NOW,
        last_active_at=NOW,
        status="active",
    )


def _card(
    *,
    status: str,
    badges: TaskCardBadges | None = None,
) -> TaskCardView:
    task_ref = TaskRef.published("root")
    return TaskCardView(
        task_ref=task_ref,
        root_ref=task_ref,
        title="Build website",
        intent_preview="Build a personal website",
        status=status,  # type: ignore[arg-type]
        badges=badges or TaskCardBadges(),
    )


def _entry(
    entry_id: str,
    task_ref: TaskRef,
    *,
    source: str,
    kind: str,
    minutes: int,
    summary: str | None = None,
    actor: str | None = "system",
    payload_ref: str | None = None,
) -> TaskInteractionEntry:
    return TaskInteractionEntry(
        entry_id=entry_id,
        session_id="session-1",
        task_ref=task_ref,
        occurred_at=NOW + timedelta(minutes=minutes),
        source=source,  # type: ignore[arg-type]
        kind=kind,
        actor=actor,
        summary=summary or "Timeline entry",
        payload_ref=payload_ref,
    )
