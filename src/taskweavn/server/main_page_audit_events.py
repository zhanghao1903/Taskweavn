"""Audit event adapters for the Plato Main Page sidecar."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from taskweavn.observability.main_page_trace import main_page_trace
from taskweavn.server.client_logs import FileClientErrorLogSink
from taskweavn.server.ui_contract import (
    AnswerAskPayload,
    AnswerAuthoringAskBatchPayload,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    AuditConfigScope,
    AuditConfirmationScope,
    AuditLogEvidenceScope,
    AuditTaskScope,
    CancelAskPayload,
    CommandRequest,
    CommandResponse,
    DeferAskPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    RepairAuthoringStatePayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
    UiCommandGateway,
    UpdateTaskNodePayload,
    audit_records_changed,
    task_node_changed,
)
from taskweavn.server.ui_events import (
    UiEventSource,
    UiEventSourceError,
    UiEventStore,
)
from taskweavn.task import TaskRef

FRONTEND_ERROR_LOG_FILENAME = "frontend-errors.jsonl"
_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


@dataclass(frozen=True)
class AuditEventCommandGateway:
    """Decorate UI commands that change Audit Page-backed source facts."""

    inner: UiCommandGateway
    event_store: UiEventStore | None = None

    def append_session_input(
        self,
        request: CommandRequest[AppendSessionInputPayload],
    ) -> CommandResponse:
        return self.inner.append_session_input(request)

    def generate_task_tree(
        self,
        request: CommandRequest[GenerateTaskTreePayload],
    ) -> CommandResponse:
        return self.inner.generate_task_tree(request)

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[UpdateTaskNodePayload],
    ) -> CommandResponse:
        return self.inner.update_task_node(task_node_id, request)

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[AppendTaskInputPayload],
    ) -> CommandResponse:
        return self.inner.append_task_input(task_node_id, request)

    def publish_task_tree(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse:
        return self.inner.publish_task_tree(request)

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[RetryTaskPayload],
    ) -> CommandResponse:
        return self.inner.retry_task(task_node_id, request)

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[StopTaskPayload],
    ) -> CommandResponse:
        return self.inner.stop_task(task_node_id, request)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[ResolveConfirmationPayload],
    ) -> CommandResponse:
        response = self.inner.resolve_confirmation(confirmation_id, request)
        if response.ok and response.result is not None:
            emit_confirmation_audit_records_changed(
                self.event_store,
                session_id=request.session_id,
                confirmation_id=confirmation_id,
                task_ref=response.result.affected_task_refs[0]
                if response.result.affected_task_refs
                else None,
            )
        return response

    def answer_ask(
        self,
        ask_id: str,
        request: CommandRequest[AnswerAskPayload],
    ) -> CommandResponse:
        return self.inner.answer_ask(ask_id, request)

    def answer_authoring_ask_batch(
        self,
        raw_task_id: str,
        request: CommandRequest[AnswerAuthoringAskBatchPayload],
    ) -> CommandResponse:
        return self.inner.answer_authoring_ask_batch(raw_task_id, request)

    def repair_authoring_state(
        self,
        request: CommandRequest[RepairAuthoringStatePayload],
    ) -> CommandResponse:
        return self.inner.repair_authoring_state(request)

    def defer_ask(
        self,
        ask_id: str,
        request: CommandRequest[DeferAskPayload],
    ) -> CommandResponse:
        return self.inner.defer_ask(ask_id, request)

    def cancel_ask(
        self,
        ask_id: str,
        request: CommandRequest[CancelAskPayload],
    ) -> CommandResponse:
        return self.inner.cancel_ask(ask_id, request)


@dataclass(frozen=True)
class AuditEventClientErrorLogSink:
    """Append frontend error logs and emit an audit invalidation."""

    inner: FileClientErrorLogSink
    event_store: UiEventStore | None = None

    def write_error(self, session_id: str, payload: dict[str, Any]) -> None:
        self.inner.write_error(session_id, payload)
        emit_log_archive_audit_records_changed(
            self.event_store,
            session_id=session_id,
            filename=self.inner.filename,
        )


def ui_event_store(event_source: UiEventSource) -> UiEventStore | None:
    if isinstance(event_source, UiEventStore):
        return event_source
    return None


def emit_agent_loop_audit_records_changed(
    event_store: UiEventStore | None,
    *,
    session_id: str,
    task_id: str,
) -> None:
    """Emit the first runtime Audit Page invalidation after AgentLoop writes events."""
    _emit_audit_records_changed(
        event_store,
        session_id=session_id,
        cursor_source=f"agent_loop:{task_id}",
        scope=AuditTaskScope(
            session_id=session_id,
            task_node_id=task_id,
            task_ref=TaskRef.published(task_id),
        ),
        reason="agent_loop_event_stream_updated",
    )


def emit_task_lifecycle_task_node_changed(
    event_store: UiEventStore | None,
    *,
    session_id: str,
    task_id: str,
) -> None:
    """Emit a Main Page invalidation after TaskBus lifecycle facts are committed."""
    if event_store is None:
        return

    event = task_node_changed(
        session_id,
        cursor=f"task_lifecycle:{task_id}:{session_id}:{uuid4().hex}",
        task_refs=(TaskRef.published(task_id),),
        reason="task_lifecycle_committed",
    )
    main_page_trace(
        "task_lifecycle.event.emit",
        event_id=event.event_id,
        event_type=event.event_type,
        reason="task_lifecycle_committed",
        session_id=session_id,
        task_id=task_id,
    )
    with contextlib.suppress(UiEventSourceError):
        event_store.append(event)


def emit_confirmation_audit_records_changed(
    event_store: UiEventStore | None,
    *,
    session_id: str,
    confirmation_id: str,
    task_ref: TaskRef | None = None,
) -> None:
    _emit_audit_records_changed(
        event_store,
        session_id=session_id,
        cursor_source=f"confirmation:{confirmation_id}",
        scope=AuditConfirmationScope(
            session_id=session_id,
            confirmation_id=confirmation_id,
            task_node_id=None if task_ref is None else task_ref.id,
        ),
        record_ids=(f"record-confirmation-{confirmation_id}",),
        reason="confirmation_resolved",
    )


def emit_config_manifest_audit_records_changed(
    event_store: UiEventStore | None,
    *,
    session_id: str,
) -> None:
    _emit_audit_records_changed(
        event_store,
        session_id=session_id,
        cursor_source="config_manifest",
        scope=AuditConfigScope(session_id=session_id, config_key="logging"),
        record_ids=("record-config-logging-manifest",),
        reason="config_manifest_updated",
    )


def emit_log_archive_audit_records_changed(
    event_store: UiEventStore | None,
    *,
    session_id: str,
    filename: str,
) -> None:
    record_id = f"record-log-{_safe_token(filename)}"
    _emit_audit_records_changed(
        event_store,
        session_id=session_id,
        cursor_source=f"log_archive:{filename}",
        scope=AuditLogEvidenceScope(
            session_id=session_id,
            evidence_id=f"evidence-{record_id}",
        ),
        record_ids=(record_id,),
        reason="log_archive_updated",
    )


def _emit_audit_records_changed(
    event_store: UiEventStore | None,
    *,
    session_id: str,
    cursor_source: str,
    scope: object,
    reason: str,
    record_ids: tuple[str, ...] = (),
) -> None:
    if event_store is None:
        return

    event = audit_records_changed(
        session_id,
        cursor=f"audit:{cursor_source}:{session_id}:{uuid4().hex}",
        scope=scope,
        record_ids=record_ids,
        reason=reason,
    )
    with contextlib.suppress(UiEventSourceError):
        event_store.append(event)


def _safe_token(value: str) -> str:
    return _ID_SAFE_RE.sub("-", value).strip("-") or "item"


__all__ = [
    "FRONTEND_ERROR_LOG_FILENAME",
    "AuditEventClientErrorLogSink",
    "AuditEventCommandGateway",
    "emit_agent_loop_audit_records_changed",
    "emit_config_manifest_audit_records_changed",
    "emit_confirmation_audit_records_changed",
    "emit_log_archive_audit_records_changed",
    "emit_task_lifecycle_task_node_changed",
    "ui_event_store",
]
