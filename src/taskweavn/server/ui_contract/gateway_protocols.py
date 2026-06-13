"""Protocol definitions for Plato UI contract gateways."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from taskweavn.core.session import Session
from taskweavn.interaction import AgentMessage
from taskweavn.server.ui_contract.commands import (
    AnswerAskPayload,
    AnswerAuthoringAskBatchPayload,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    CancelAskPayload,
    DeferAskPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    RepairAuthoringStatePayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
    UpdateTaskNodePayload,
)
from taskweavn.server.ui_contract.envelopes import (
    CommandRequest,
    CommandResponse,
    QueryResponse,
)
from taskweavn.server.ui_contract.snapshots import AuditPageSnapshot, MainPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    AskListResult,
    AskRequestView,
    AuditDisclosure,
    AuditLinkView,
    AuditRecord,
    AuditRecordDetail,
    AuditRecordsResult,
    EffectiveConfigSummary,
    EvidenceDetail,
    EvidenceRef,
    ProjectSummary,
    RelatedLogsLink,
    SanitizedRawPayload,
    SessionActivityTimelineResult,
    WorkflowSummary,
)
from taskweavn.task.models import TaskRef
from taskweavn.types.base import BaseEvent


@runtime_checkable
class SessionReader(Protocol):
    """Read subset of SessionManager needed by UI query gateways."""

    def get(self, session_id: str) -> Session | None: ...

    def list(self) -> list[Session]: ...


@runtime_checkable
class ProjectProvider(Protocol):
    def get_project(self) -> ProjectSummary: ...


@runtime_checkable
class WorkflowProvider(Protocol):
    def list_workflows(self) -> tuple[WorkflowSummary, ...]: ...

    def get_workflow(self, session: Session) -> WorkflowSummary: ...


@runtime_checkable
class AuditLinkProvider(Protocol):
    def list_for_session(self, session_id: str) -> tuple[AuditLinkView, ...]: ...


@runtime_checkable
class SnapshotCursorProvider(Protocol):
    """Read the latest UI event cursor used as a snapshot subscription boundary."""

    def latest_cursor(self, session_id: str) -> str | None: ...


@runtime_checkable
class AuditEventProvider(Protocol):
    """Read durable execution events for Audit Page projection."""

    def list_for_session(
        self,
        session: Session,
        *,
        task_node_id: str | None = None,
    ) -> Iterable[BaseEvent]: ...


@runtime_checkable
class AuditConfigProvider(Protocol):
    """Read effective config evidence for Audit Page projection."""

    def list_for_session(
        self,
        session: Session,
        *,
        task_node_id: str | None = None,
    ) -> Iterable[AuditRecord]: ...

    def get_effective_config(
        self,
        session: Session,
        *,
        records: Sequence[AuditRecord],
    ) -> EffectiveConfigSummary | None: ...


@runtime_checkable
class AuditLogProvider(Protocol):
    """Read log-archive evidence and links for Audit Page projection."""

    def list_for_session(
        self,
        session: Session,
        *,
        task_node_id: str | None = None,
    ) -> Iterable[AuditRecord]: ...

    def related_logs(
        self,
        session: Session,
        *,
        task_node_id: str | None,
        record_id: str | None,
    ) -> tuple[RelatedLogsLink, ...]: ...


@dataclass(frozen=True)
class PayloadDisclosureResult:
    """Runtime-only sanitized payload plus disclosure metadata."""

    disclosure: AuditDisclosure
    payload: SanitizedRawPayload | None = None


@runtime_checkable
class AuditPayloadDisclosureService(Protocol):
    """Build sanitized Audit Page payloads without persisting them."""

    def build_record_payload(
        self,
        record: AuditRecord,
        *,
        session: Session,
        include_sanitized_payload: bool,
    ) -> PayloadDisclosureResult: ...

    def build_evidence_payload(
        self,
        record: AuditRecord,
        evidence_ref: EvidenceRef,
        *,
        session: Session,
        include_sanitized_payload: bool,
    ) -> PayloadDisclosureResult: ...


@runtime_checkable
class SessionMessageProvider(Protocol):
    def list_for_session(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> Iterable[AgentMessage]: ...


@runtime_checkable
class TaskRefResolver(Protocol):
    """Resolve frontend taskNodeId into a backend TaskRef."""

    def resolve(self, session_id: str, task_node_id: str) -> TaskRef: ...


@runtime_checkable
class UiQueryGateway(Protocol):
    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]: ...

    def list_asks(
        self,
        session_id: str,
        *,
        status: str | None = None,
        task_node_id: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AskListResult]: ...

    def get_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[AskRequestView]: ...

    def list_session_activity(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[SessionActivityTimelineResult]: ...

    def get_audit_snapshot(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        entry: str | None = None,
        filter_kind: str = "all",
        record_id: str | None = None,
        include_detail: bool | None = None,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AuditPageSnapshot]: ...

    def list_audit_records(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        filter_kind: str = "all",
        kind: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        include_hidden_reasons: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordsResult]: ...

    def get_audit_record_detail(
        self,
        session_id: str,
        record_id: str,
        *,
        include_evidence: bool = False,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordDetail]: ...

    def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        *,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[EvidenceDetail]: ...


@runtime_checkable
class UiCommandGateway(Protocol):
    def append_session_input(
        self,
        request: CommandRequest[AppendSessionInputPayload],
    ) -> CommandResponse: ...

    def generate_task_tree(
        self,
        request: CommandRequest[GenerateTaskTreePayload],
    ) -> CommandResponse: ...

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[UpdateTaskNodePayload],
    ) -> CommandResponse: ...

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[AppendTaskInputPayload],
    ) -> CommandResponse: ...

    def publish_task_tree(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse: ...

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[RetryTaskPayload],
    ) -> CommandResponse: ...

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[StopTaskPayload],
    ) -> CommandResponse: ...

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[ResolveConfirmationPayload],
    ) -> CommandResponse: ...

    def answer_ask(
        self,
        ask_id: str,
        request: CommandRequest[AnswerAskPayload],
    ) -> CommandResponse: ...

    def answer_authoring_ask_batch(
        self,
        raw_task_id: str,
        request: CommandRequest[AnswerAuthoringAskBatchPayload],
    ) -> CommandResponse: ...

    def repair_authoring_state(
        self,
        request: CommandRequest[RepairAuthoringStatePayload],
    ) -> CommandResponse: ...

    def defer_ask(
        self,
        ask_id: str,
        request: CommandRequest[DeferAskPayload],
    ) -> CommandResponse: ...

    def cancel_ask(
        self,
        ask_id: str,
        request: CommandRequest[CancelAskPayload],
    ) -> CommandResponse: ...
