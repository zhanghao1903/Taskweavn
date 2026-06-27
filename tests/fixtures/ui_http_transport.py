"""Shared fixtures for Plato UI HTTP transport tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from taskweavn.runtime_config import (
    DefaultRuntimeConfigMutationService,
    RuntimeConfigActor,
    RuntimeConfigMutationServiceConfig,
    SqliteRuntimeConfigChangeStore,
)
from taskweavn.server import (
    InMemoryUiCommandResponseIdempotencyStore,
    PlatoUiHttpTransport,
    SidecarAuth,
    UiEventSource,
)
from taskweavn.server.runtime_config_gateway import DefaultRuntimeConfigGateway
from taskweavn.server.settings_config import SettingsConfigValidationError
from taskweavn.server.ui_contract import (
    ApiError,
    AskListResult,
    AskRequestView,
    AuditEntryContext,
    AuditOverview,
    AuditPageRequestView,
    AuditPageSnapshot,
    AuditRecord,
    AuditRecordDetail,
    AuditRecordsResult,
    AuditSessionScope,
    CommandRequest,
    CommandResponse,
    CommandResult,
    EvidenceDetail,
    EvidenceRef,
    MainPageReturnTarget,
    MainPageSnapshot,
    ProjectSummary,
    QueryResponse,
    RuntimeInputDecisionScope,
    RuntimeInputOutcome,
    RuntimeInputRouteDecision,
    RuntimeInputRouteRequest,
    RuntimeInputRouteResult,
    SessionActivityTimelineResult,
    SessionSummary,
    WorkflowSummary,
)
from taskweavn.task import ExecutionDispatchRequestResult

NOW = datetime(2026, 5, 21, 9, 0, tzinfo=UTC)


@dataclass
class _QueryGateway:
    snapshot_calls: list[str] = field(default_factory=list)
    activity_calls: list[tuple[str, int, str | None]] = field(default_factory=list)
    ask_calls: list[tuple[Any, ...]] = field(default_factory=list)
    audit_calls: list[tuple[Any, ...]] = field(default_factory=list)

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
        self.snapshot_calls.append(session_id)
        project = ProjectSummary(id="local", name="Local")
        workflow = WorkflowSummary(id="authoring", name="Authoring")
        session = SessionSummary(
            id=session_id,
            project_id=project.id,
            workflow_id=workflow.id,
            name="Session",
            status="new",
            created_at=NOW,
            updated_at=NOW,
        )
        snapshot = MainPageSnapshot(
            project=project,
            workflows=(workflow,),
            workflow=workflow,
            sessions=(session,),
            session=session,
            cursor="cursor-1",
            generated_at=NOW,
        )
        return QueryResponse[MainPageSnapshot](
            request_id=request_id or "request-snapshot",
            ok=True,
            data=snapshot,
            cursor=snapshot.cursor,
        )

    def list_session_activity(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[SessionActivityTimelineResult]:
        self.activity_calls.append((session_id, limit, cursor))
        timeline = SessionActivityTimelineResult(
            session_id=session_id,
            total_count=0,
            generated_at=NOW,
        )
        return QueryResponse[SessionActivityTimelineResult](
            request_id=request_id or "request-session-activity",
            ok=True,
            data=timeline,
            cursor=timeline.next_cursor,
        )

    def list_asks(
        self,
        session_id: str,
        *,
        status: str | None = None,
        task_node_id: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AskListResult]:
        self.ask_calls.append(("list", session_id, status, task_node_id))
        ask = _ask_view(session_id, ask_id="ask 1", task_node_id=task_node_id)
        return QueryResponse[AskListResult](
            request_id=request_id or "request-asks",
            ok=True,
            data=AskListResult(session_id=session_id, asks=(ask,), active_ask=ask),
        )

    def get_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[AskRequestView]:
        self.ask_calls.append(("detail", session_id, ask_id))
        return QueryResponse[AskRequestView](
            request_id=request_id or "request-ask-detail",
            ok=True,
            data=_ask_view(session_id, ask_id=ask_id, task_node_id="task 1"),
        )

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
    ) -> QueryResponse[AuditPageSnapshot]:
        del cursor
        self.audit_calls.append(
            (
                "snapshot",
                session_id,
                task_node_id,
                entry,
                filter_kind,
                record_id,
                include_detail,
                limit,
            )
        )
        snapshot = AuditPageSnapshot(
            request=AuditPageRequestView(
                filter="files",
                record_id="record 1",
                include_detail=True,
                limit=25,
            ),
            scope=AuditSessionScope(session_id=session_id),
            entry_context=AuditEntryContext(
                kind="from_task",
                session_id=session_id,
                task_node_id=task_node_id,
                source_route=f"/sessions/{session_id}",
                preferred_filter="files",
                preferred_record_id="record 1",
            ),
            return_target=MainPageReturnTarget(
                route_name="main.sessionFallback",
                session_id=session_id,
                task_node_id=task_node_id,
                focus="task",
                record_id="record 1",
            ),
            session=_session_summary(session_id),
            overview=AuditOverview(
                verdict="warning",
                completeness="partial",
                summary="Audit projection is partial.",
                record_counts={"all": 1, "files": 1},
                important_record_ids=("record 1",),
                generated_by="projection",
                updated_at=NOW,
            ),
            records=(_audit_record(session_id),),
            selected_record=_audit_record_detail(session_id),
            generated_at=NOW,
        )
        return QueryResponse[AuditPageSnapshot](
            request_id=request_id or "request-audit-snapshot",
            ok=True,
            data=snapshot,
            cursor=snapshot.cursor,
        )

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
    ) -> QueryResponse[AuditRecordsResult]:
        del from_time, to_time, limit, cursor
        self.audit_calls.append(
            (
                "records",
                session_id,
                task_node_id,
                filter_kind,
                kind,
                include_hidden_reasons,
            )
        )
        return QueryResponse[AuditRecordsResult](
            request_id=request_id or "request-audit-records",
            ok=True,
            data=AuditRecordsResult(
                records=(_audit_record(session_id),),
                total_count=1,
            ),
        )

    def get_audit_record_detail(
        self,
        session_id: str,
        record_id: str,
        *,
        include_evidence: bool = False,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordDetail]:
        self.audit_calls.append(
            (
                "detail",
                session_id,
                record_id,
                include_evidence,
                include_sanitized_payload,
            )
        )
        return QueryResponse[AuditRecordDetail](
            request_id=request_id or "request-audit-detail",
            ok=True,
            data=_audit_record_detail(session_id),
        )

    def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        *,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[EvidenceDetail]:
        self.audit_calls.append(
            ("evidence", session_id, evidence_id, include_sanitized_payload)
        )
        return QueryResponse[EvidenceDetail](
            request_id=request_id or "request-evidence-detail",
            ok=True,
            data=EvidenceDetail(
                id=evidence_id,
                kind="file_change",
                label="File change",
                summary="Changed src/App.tsx.",
                source="task_projection",
                body="Changed src/App.tsx.",
            ),
        )


@dataclass
class _CommandGateway:
    calls: list[str] = field(default_factory=list)
    reject_ask_answer: bool = False

    def append_session_input(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("append_session_input")
        return _accepted(request.command_id)

    def generate_task_tree(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("generate_task_tree")
        return _accepted(request.command_id)

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"update_task_node:{task_node_id}")
        return _accepted(request.command_id)

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"append_task_input:{task_node_id}")
        return _accepted(request.command_id)

    def publish_task_tree(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("publish_task_tree")
        return _accepted(request.command_id)

    def archive_plan(
        self,
        plan_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"archive_plan:{plan_id}")
        return _accepted(request.command_id)

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"retry_task:{task_node_id}")
        return _accepted(request.command_id)

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"stop_task:{task_node_id}")
        return _accepted(request.command_id)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"resolve_confirmation:{confirmation_id}")
        return _accepted(request.command_id)

    def answer_ask(
        self,
        ask_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"answer_ask:{ask_id}")
        if self.reject_ask_answer:
            return _rejected(request.command_id, message="ASK is not pending: answered")
        return _accepted(request.command_id)

    def answer_authoring_ask_batch(
        self,
        raw_task_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"answer_authoring_ask_batch:{raw_task_id}")
        return _accepted(request.command_id)

    def repair_authoring_state(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("repair_authoring_state")
        return _accepted(request.command_id)

    def defer_ask(
        self,
        ask_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"defer_ask:{ask_id}")
        return _accepted(request.command_id)

    def cancel_ask(
        self,
        ask_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"cancel_ask:{ask_id}")
        return _accepted(request.command_id)


@dataclass
class _ClientErrorSink:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def write_error(self, session_id: str, payload: dict[str, Any]) -> None:
        self.calls.append((session_id, payload))


@dataclass
class _SessionLifecycleGateway:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def list_sessions(self) -> dict[str, Any]:
        self.calls.append(("list",))
        return {"sessions": [{"id": "session-1", "name": "Session 1"}]}

    def create_session(self, name: str) -> dict[str, Any]:
        self.calls.append(("create", name))
        return {"sessionId": "created-session", "session": {"name": name}}

    def rename_session(self, session_id: str, name: str) -> dict[str, Any]:
        self.calls.append(("rename", session_id, name))
        return {"sessionId": session_id, "session": {"id": session_id, "name": name}}

    def delete_session(self, session_id: str) -> dict[str, Any]:
        self.calls.append(("delete", session_id))
        return {"deletedSessionId": session_id, "nextSessionId": "next-session"}


def _session_summary(session_id: str) -> SessionSummary:
    return SessionSummary(
        id=session_id,
        project_id="local",
        workflow_id="authoring",
        name="Session",
        status="running",
        created_at=NOW,
        updated_at=NOW,
    )


def _audit_record(session_id: str) -> AuditRecord:
    return AuditRecord(
        id="record 1",
        scope=AuditSessionScope(session_id=session_id),
        kind="file_change",
        filter_kind="files",
        title="File changed",
        summary="Changed src/App.tsx.",
        actor="tool",
        source_label="Task projection",
        occurred_at=NOW,
        severity="warning",
        confidence="medium",
        verdict="warning",
        evidence_refs=(
            EvidenceRef(
                id="evidence 1",
                kind="file_change",
                label="File change",
                summary="Changed src/App.tsx.",
            ),
        ),
    )


def _audit_record_detail(session_id: str) -> AuditRecordDetail:
    return AuditRecordDetail(
        **_audit_record(session_id).model_dump(),
        body="Changed src/App.tsx.",
        why_it_matters="File changes must be attributable.",
    )


def _ask_view(
    session_id: str,
    *,
    ask_id: str,
    task_node_id: str | None,
) -> AskRequestView:
    return AskRequestView(
        id=ask_id,
        session_id=session_id,
        task_node_id=task_node_id,
        question="Which deployment target should be used?",
        reason="The agent needs a user-owned deployment decision.",
        answer_type="free_text",
        allow_free_text=True,
        allow_no_option_with_text=True,
        blocking=True,
        status="pending",
        created_at=NOW,
    )


@dataclass
class _ExecutionTriggerGateway:
    status: str = "queued"
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)

    def request_dispatch(
        self,
        session_id: str,
        *,
        reason: str,
        request_id: str | None = None,
    ) -> ExecutionDispatchRequestResult:
        self.calls.append((session_id, reason, request_id))
        return ExecutionDispatchRequestResult(
            status=self.status,  # type: ignore[arg-type]
            session_id=session_id,
            reason=reason,  # type: ignore[arg-type]
            request_id=request_id,
            message=f"dispatch {self.status}",
            error_ref=None if self.status == "queued" else self.status,
        )


@dataclass
class _RuntimeInputRouter:
    calls: list[RuntimeInputRouteRequest] = field(default_factory=list)

    def route(
        self,
        request: RuntimeInputRouteRequest,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        self.calls.append(request)
        return QueryResponse[RuntimeInputRouteResult](
            request_id=request.command_id,
            ok=True,
            data=RuntimeInputRouteResult(
                session_id=request.session_id,
                decision=RuntimeInputRouteDecision(
                    intent="question",
                    scope=RuntimeInputDecisionScope(kind="session"),
                    confidence="high",
                    side_effect="no_effect",
                    dispatch_target="read_only_inquiry",
                    explanation="Question route.",
                ),
                outcome=RuntimeInputOutcome(
                    status="answered",
                    user_message="Answered without side effects.",
                ),
            ),
        )


@dataclass
class _SnapshotRecoveryGateway:
    raises: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def recover_session(self, session_id: str) -> object:
        self.calls.append(session_id)
        if self.raises is not None:
            raise self.raises
        return {"recovered": True}


@dataclass
class _SettingsReadinessGateway:
    calls: int = 0

    def get_readiness(self) -> dict[str, Any]:
        self.calls += 1
        return {
            "schemaVersion": "plato.settings_readiness.v1",
            "status": "ready",
        }


@dataclass
class _SettingsConfigGateway:
    validation_error: SettingsConfigValidationError | None = None
    config_calls: int = 0
    recheck_calls: int = 0
    update_calls: list[dict[str, Any]] = field(default_factory=list)

    def get_config(self) -> dict[str, Any]:
        self.config_calls += 1
        return {
            "schemaVersion": "plato.settings_config.v1",
            "llm": {
                "provider": "deepseek",
                "apiKeyConfigured": False,
            },
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.update_calls.append(payload)
        if self.validation_error is not None:
            raise self.validation_error
        return {
            "schemaVersion": "plato.settings_config_update.v1",
            "config": {
                "schemaVersion": "plato.settings_config.v1",
                "llm": {
                    "provider": "deepseek",
                    "apiKeyConfigured": True,
                },
            },
            "readiness": {
                "schemaVersion": "plato.settings_readiness.v1",
                "status": "ready",
            },
        }

    def get_readiness(self) -> dict[str, Any]:
        return self.recheck_readiness()

    def recheck_readiness(self) -> dict[str, Any]:
        self.recheck_calls += 1
        return {
            "schemaVersion": "plato.settings_readiness.v1",
            "status": "ready",
        }


@dataclass
class _DiagnosticExportGateway:
    calls: list[str] = field(default_factory=list)

    def export_session(self, session_id: str) -> dict[str, Any]:
        self.calls.append(session_id)
        return {
            "schemaVersion": "plato.diagnostics_export.v1",
            "bundleId": f"diagnostic-bundle-{session_id}",
            "bundleDir": "/tmp/bundle",
            "bundleDirLabel": "workspace://current/.plato/diagnostics/bundle",
            "zipPath": "/tmp/bundle.zip",
            "zipPathLabel": "workspace://current/.plato/diagnostics/bundle.zip",
            "manifestPath": "/tmp/bundle/manifest.json",
            "manifestPathLabel": (
                "workspace://current/.plato/diagnostics/bundle/manifest.json"
            ),
            "createdAt": "2026-05-21T09:00:00Z",
            "redactionProfile": "product_1_0_default",
            "includedSections": ["session"],
            "sections": [{"name": "session", "status": "included", "warnings": []}],
            "warnings": [],
            "fileCount": 1,
        }


@dataclass(frozen=True)
class _RuntimeConfigTransportFixture:
    service: DefaultRuntimeConfigMutationService
    store: SqliteRuntimeConfigChangeStore
    transport: PlatoUiHttpTransport


def _transport(
    *,
    query: _QueryGateway | None = None,
    commands: _CommandGateway | None = None,
    event_source: UiEventSource | None = None,
    auth: SidecarAuth | None = None,
    client_error_log_sink: _ClientErrorSink | None = None,
    session_lifecycle_gateway: _SessionLifecycleGateway | None = None,
    command_idempotency_store: InMemoryUiCommandResponseIdempotencyStore | None = None,
    execution_trigger_gateway: _ExecutionTriggerGateway | None = None,
    snapshot_recovery_gateway: _SnapshotRecoveryGateway | None = None,
    settings_readiness_gateway: _SettingsReadinessGateway | None = None,
    settings_config_gateway: _SettingsConfigGateway | None = None,
    diagnostic_export_gateway: _DiagnosticExportGateway | None = None,
    runtime_input_router: _RuntimeInputRouter | None = None,
    runtime_config_gateway: DefaultRuntimeConfigGateway | None = None,
    runtime_config_mutation_service: DefaultRuntimeConfigMutationService | None = None,
) -> PlatoUiHttpTransport:
    return PlatoUiHttpTransport(
        query_gateway=query or _QueryGateway(),
        command_gateway=commands or _CommandGateway(),
        event_source=event_source,
        auth=auth,
        client_error_log_sink=client_error_log_sink,
        session_lifecycle_gateway=session_lifecycle_gateway,
        command_idempotency_store=command_idempotency_store,
        execution_trigger_gateway=execution_trigger_gateway,
        snapshot_recovery_gateway=snapshot_recovery_gateway,
        settings_readiness_gateway=settings_readiness_gateway,
        settings_config_gateway=settings_config_gateway,
        diagnostic_export_gateway=diagnostic_export_gateway,
        runtime_input_router=runtime_input_router,
        runtime_config_gateway=runtime_config_gateway,
        runtime_config_mutation_service=runtime_config_mutation_service,
    )


@contextmanager
def _runtime_config_transport_fixture(
    db_path: Any,
    *,
    process_inputs: dict[str, object] | None = None,
    workspace_id: str = "workspace-1",
) -> Iterator[_RuntimeConfigTransportFixture]:
    with SqliteRuntimeConfigChangeStore(db_path) as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )
        transport = _transport(
            runtime_config_gateway=DefaultRuntimeConfigGateway.from_process_inputs(
                process_inputs or {},
                workspace_id=workspace_id,
                change_store=store,
            ),
            runtime_config_mutation_service=service,
        )
        yield _RuntimeConfigTransportFixture(
            service=service,
            store=store,
            transport=transport,
        )


def _accepted(command_id: str) -> CommandResponse:
    return CommandResponse(
        request_id=f"request-{command_id}",
        ok=True,
        result=CommandResult(
            command_id=command_id,
            status="accepted",
            message="accepted",
        ),
    )


def _runtime_config_actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="UI HTTP runtime config tests",
    )


def _runtime_config_ts() -> datetime:
    return datetime(2026, 6, 24, 18, 0, tzinfo=UTC)


def _rejected(command_id: str, *, message: str) -> CommandResponse:
    return CommandResponse(
        request_id=f"request-{command_id}",
        ok=False,
        result=CommandResult(
            command_id=command_id,
            status="rejected",
            message=message,
        ),
        error=ApiError(code="command_rejected", message=message),
    )


def _command_body(
    session_id: str,
    payload: dict[str, object],
    *,
    command_id: str = "command-1",
    idempotency_key: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "commandId": command_id,
        "sessionId": session_id,
        "payload": payload,
    }
    if idempotency_key is not None:
        body["idempotencyKey"] = idempotency_key
    return body


def _dict_body(body: dict[str, Any] | str) -> dict[str, Any]:
    assert isinstance(body, dict)
    return body


def _str_body(body: dict[str, Any] | str) -> str:
    assert isinstance(body, str)
    return body
