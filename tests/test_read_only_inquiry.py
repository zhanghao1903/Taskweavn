from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError

from taskweavn.server.read_only_inquiry import DefaultReadOnlyInquiryService
from taskweavn.server.read_only_inquiry_answer_provider import (
    ReadOnlyInquiryAnswerProviderResult,
)
from taskweavn.server.read_only_inquiry_diagnostics import (
    DefaultDiagnosticSupportContextProvider,
)
from taskweavn.server.ui_contract import (
    AuditRecord,
    AuditRecordDetail,
    AuditRecordsResult,
    AuditSessionScope,
    EvidenceDetail,
    EvidenceRef,
    ExecutionRollupView,
    FileChangeItemView,
    FileChangeSummaryView,
    MainPageSnapshot,
    PlanningDiagnosticView,
    PlanningView,
    PlanView,
    ProjectSummary,
    QueryResponse,
    ReadOnlyInquiryAnswer,
    ReadOnlyInquiryRef,
    ReadOnlyInquiryRequest,
    ReadOnlyInquiryScope,
    ResultCardView,
    SessionActivityItemView,
    SessionActivityTimelineResult,
    SessionSummary,
    TaskNodeCardView,
    WorkflowSummary,
)

NOW = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)


def test_read_only_inquiry_rejects_unsafe_ref_paths() -> None:
    with pytest.raises(ValidationError, match="workspace-relative safe paths"):
        ReadOnlyInquiryRef(kind="file", path="/Users/example/secret.txt", label="file")

    with pytest.raises(ValidationError, match="workspace-relative safe paths"):
        ReadOnlyInquiryRef(kind="file", path="../secret.txt", label="file")


def test_read_only_inquiry_answers_session_status_with_evidence() -> None:
    query = _QueryGateway()
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-session",
            session_id="session-1",
            question="What is the current status?",
            scope=ReadOnlyInquiryScope(kind="session"),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert "Session 'Session'" in response.data.answer.body
    assert response.data.evidence_refs[0].kind == "session_status"
    assert response.data.activity is not None
    assert response.data.activity.kind == "answer"
    assert response.data.activity.side_effect == "no_effect"
    assert query.calls == [("snapshot", "session-1", "inq-session")]


def test_read_only_inquiry_uses_injected_answer_provider() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    provider = _AnswerProvider()
    service = DefaultReadOnlyInquiryService(
        cast(Any, query),
        answer_provider=provider,
    )

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-provider",
            session_id="session-1",
            question="Explain this task using available evidence.",
            scope=ReadOnlyInquiryScope(
                kind="task",
                plan_id="plan-1",
                task_node_id="task-1",
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert response.data.answer.body == "Provider-rendered answer."
    assert response.data.activity is not None
    assert response.data.activity.body == "Provider-rendered answer."
    assert provider.baseline_body.startswith("Task 1 'Inspect workspace' is done")
    assert [ref.kind for ref in provider.evidence_refs] == [
        "task_status",
        "result_summary",
        "file_change_summary",
    ]


def test_read_only_inquiry_answers_plan_and_task_status_from_snapshot() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    plan_response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-plan",
            session_id="session-1",
            question="How is the plan progressing?",
            scope=ReadOnlyInquiryScope(kind="plan", plan_id="plan-1"),
        )
    )
    task_response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-task",
            session_id="session-1",
            question="What happened on task 1?",
            scope=ReadOnlyInquiryScope(
                kind="task",
                plan_id="plan-1",
                task_node_id="task-1",
            ),
        )
    )

    assert plan_response.data is not None
    assert plan_response.data.status == "answered"
    assert plan_response.data.answer is not None
    assert "1 done" in plan_response.data.answer.body
    assert [ref.kind for ref in plan_response.data.evidence_refs] == [
        "plan_status",
        "result_summary",
        "file_change_summary",
    ]
    assert task_response.data is not None
    assert task_response.data.status == "answered"
    assert task_response.data.answer is not None
    assert "Task 1 'Inspect workspace' is done" in task_response.data.answer.body
    assert [ref.kind for ref in task_response.data.evidence_refs] == [
        "task_status",
        "result_summary",
        "file_change_summary",
    ]


def test_read_only_inquiry_missing_task_needs_clarification() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-missing-task",
            session_id="session-1",
            question="What about this task?",
            scope=ReadOnlyInquiryScope(
                kind="task",
                plan_id="plan-1",
                task_node_id="missing-task",
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "needs_clarification"
    assert response.data.answer is None
    assert response.data.warnings[0].code == "inquiry.context_empty"


def test_read_only_inquiry_summarizes_activity_and_audit_refs() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-refs",
            session_id="session-1",
            workspace_id="workspace-1",
            question="What evidence should I inspect?",
            scope=ReadOnlyInquiryScope(kind="session"),
            refs=(
                ReadOnlyInquiryRef(
                    kind="activity",
                    id="activity:message:1",
                    label="Latest activity",
                ),
                ReadOnlyInquiryRef(
                    kind="audit_record",
                    id="record-1",
                    label="Audit record",
                ),
                ReadOnlyInquiryRef(
                    kind="audit_evidence",
                    evidence_id="evidence-1",
                    label="Audit evidence",
                ),
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert "Activity 'User question'" in response.data.answer.body
    assert "Audit record 'Command failed'" in response.data.answer.body
    assert "Audit evidence 'Error observation'" in response.data.answer.body
    assert [ref.kind for ref in response.data.evidence_refs[-3:]] == [
        "activity_item",
        "audit_record",
        "audit_evidence",
    ]
    assert response.data.activity is not None
    assert response.data.activity.related_refs[-2].href == (
        "/sessions/session-1/audit?entry=from_session&recordId=record-1"
        "&returnFocus=session&returnSessionId=session-1&workspaceId=workspace-1"
    )
    assert response.data.activity.related_refs[-1].href == (
        "/sessions/session-1/audit?entry=from_session&recordId=record-1"
        "&evidenceId=evidence-1&returnFocus=session&returnSessionId=session-1"
        "&workspaceId=workspace-1"
    )
    assert response.data.evidence_refs[-1].parent_ref_id == "record-1"
    assert response.data.warnings == ()


def test_read_only_inquiry_summarizes_explicit_result_ref() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-result",
            session_id="session-1",
            question="What result is available?",
            scope=ReadOnlyInquiryScope(kind="task", plan_id="plan-1", task_node_id="task-1"),
            refs=(
                ReadOnlyInquiryRef(
                    kind="result",
                    id="result-1",
                    label="Workspace result",
                ),
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert "Result 'Workspace result': The workspace has one changed file." in (
        response.data.answer.body
    )
    assert response.data.evidence_refs[-1].kind == "result_summary"
    assert response.data.evidence_refs[-1].ref_id == "result-1"
    assert response.data.activity is not None
    assert response.data.activity.related_refs[-1].kind == "result"
    assert response.data.activity.related_refs[-1].href is None
    assert response.data.warnings == ()


def test_read_only_inquiry_warns_when_explicit_result_ref_is_missing() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-result-missing",
            session_id="session-1",
            question="What result is available?",
            scope=ReadOnlyInquiryScope(kind="session"),
            refs=(
                ReadOnlyInquiryRef(
                    kind="result",
                    id="missing-result",
                    label="Missing result",
                ),
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert "Missing result" not in response.data.answer.body
    assert response.data.warnings[0].message == "Result summary is not available."


def test_read_only_inquiry_summarizes_workspace_file_and_diff_refs() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    inspection = _WorkspaceInspectionGateway()
    service = DefaultReadOnlyInquiryService(
        cast(Any, query),
        workspace_inspection_gateway=inspection,
    )

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-workspace",
            session_id="session-1",
            workspace_id="workspace-1",
            question="What changed in app.txt?",
            scope=ReadOnlyInquiryScope(kind="session"),
            refs=(
                ReadOnlyInquiryRef(kind="file", path="app.txt", label="app.txt"),
                ReadOnlyInquiryRef(kind="diff", path="app.txt", label="app.txt"),
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert "File 'workspace://current/app.txt' is available" in (
        response.data.answer.body
    )
    assert "Preview: first line / second line" in response.data.answer.body
    assert "Diff for 'workspace://current/app.txt' has 2 additions" in (
        response.data.answer.body
    )
    assert [ref.kind for ref in response.data.evidence_refs[-2:]] == [
        "file_snapshot",
        "diff_snapshot",
    ]
    assert response.data.activity is not None
    assert response.data.activity.related_refs[-2].href == (
        "/workspaces/workspace-1/inspection?path=app.txt"
        "&returnSessionId=session-1&sessionId=session-1&view=file"
    )
    assert response.data.activity.related_refs[-1].href == (
        "/workspaces/workspace-1/inspection?path=app.txt"
        "&returnSessionId=session-1&sessionId=session-1&view=diff"
    )
    assert response.data.warnings == ()
    assert inspection.calls == [
        ("file_content", "app.txt", 1, 20, None),
        ("diff", "app.txt", "head", None, 32768),
    ]


def test_read_only_inquiry_summarizes_diagnostic_refs() -> None:
    query = _QueryGateway(
        snapshot=_snapshot("session-1", with_plan=True, with_diagnostics=True)
    )
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-diagnostic",
            session_id="session-1",
            question="What diagnostic should I look at?",
            scope=ReadOnlyInquiryScope(kind="session"),
            refs=(
                ReadOnlyInquiryRef(
                    kind="diagnostic",
                    id="diagnostic:dirty_authoring_state",
                    label="Dirty authoring state",
                ),
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert "Diagnostic 'dirty_authoring_state' is warning" in (
        response.data.answer.body
    )
    diagnostic_ref = response.data.evidence_refs[-1]
    assert diagnostic_ref.kind == "diagnostic_summary"
    assert diagnostic_ref.ref_id == "diagnostic:dirty_authoring_state"
    assert diagnostic_ref.disclosure == "partial"
    assert response.data.warnings == ()


def test_read_only_inquiry_warns_when_diagnostic_ref_is_missing() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    service = DefaultReadOnlyInquiryService(cast(Any, query))

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-missing-diagnostic",
            session_id="session-1",
            question="What diagnostic should I look at?",
            scope=ReadOnlyInquiryScope(kind="session"),
            refs=(
                ReadOnlyInquiryRef(
                    kind="diagnostic",
                    id="diagnostic:dirty_authoring_state",
                    label="Dirty authoring state",
                ),
            ),
        )
    )

    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.warnings[0].code == "inquiry.context_partial"
    assert "Diagnostic descriptor is not available" in response.data.warnings[0].message


def test_read_only_inquiry_summarizes_diagnostic_support_descriptor() -> None:
    query = _QueryGateway(snapshot=_snapshot("session-1", with_plan=True))
    service = DefaultReadOnlyInquiryService(
        cast(Any, query),
        diagnostic_support_provider=DefaultDiagnosticSupportContextProvider(),
    )

    response = service.answer(
        ReadOnlyInquiryRequest(
            inquiry_id="inq-diagnostic-support",
            session_id="session-1",
            workspace_id="workspace-1",
            question="How can I export diagnostics for support?",
            scope=ReadOnlyInquiryScope(kind="session"),
            refs=(
                ReadOnlyInquiryRef(
                    kind="diagnostic",
                    id="diagnostic:bundle_export",
                    label="Diagnostic bundle export",
                ),
            ),
        )
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.status == "answered"
    assert response.data.answer is not None
    assert "Diagnostic support 'Diagnostic bundle export'" in response.data.answer.body
    assert "/api/v1/sessions/session-1/diagnostics/export" in (
        response.data.answer.body
    )
    assert "/Users/" not in response.data.answer.body
    assert "provider payloads" in response.data.answer.body
    diagnostic_ref = response.data.evidence_refs[-1]
    assert diagnostic_ref.kind == "diagnostic_summary"
    assert diagnostic_ref.ref_id == "diagnostic:bundle_export"
    assert diagnostic_ref.disclosure == "partial"
    assert response.data.activity is not None
    assert response.data.activity.related_refs[-1].kind == "diagnostic"
    assert response.data.activity.related_refs[-1].href is None


@dataclass
class _QueryGateway:
    snapshot: MainPageSnapshot | None = None
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
        self.calls.append(("snapshot", session_id, request_id))
        return QueryResponse[MainPageSnapshot](
            request_id=request_id or "snapshot",
            ok=True,
            data=self.snapshot or _snapshot(session_id),
        )

    def list_session_activity(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[SessionActivityTimelineResult]:
        self.calls.append(("activity", session_id, limit, cursor, request_id))
        activity = SessionActivityItemView(
            id="activity:message:1",
            session_id=session_id,
            kind="user_input",
            title="User question",
            body="What changed?",
            occurred_at=NOW,
            scope_kind="session",
            side_effect="no_effect",
            source_kind="message_stream",
            source_id="message-1",
            disclosure_level="public",
        )
        return QueryResponse[SessionActivityTimelineResult](
            request_id=request_id or "activity",
            ok=True,
            data=SessionActivityTimelineResult(
                session_id=session_id,
                items=(activity,),
                total_count=1,
                generated_at=NOW,
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
        self.calls.append(
            (
                "audit_record",
                session_id,
                record_id,
                include_evidence,
                include_sanitized_payload,
                request_id,
            )
        )
        return QueryResponse[AuditRecordDetail](
            request_id=request_id or "audit-record",
            ok=True,
            data=AuditRecordDetail(
                id=record_id,
                scope=AuditSessionScope(session_id=session_id),
                kind="observation",
                filter_kind="actions",
                title="Command failed",
                summary="A command returned a non-zero exit code.",
                actor="tool",
                source_label="EventStream",
                occurred_at=NOW,
                severity="danger",
                confidence="high",
                verdict="failed",
                body="The command failed safely.",
                why_it_matters="Failed command evidence affects trust.",
            ),
        )

    def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        *,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[EvidenceDetail]:
        self.calls.append(
            ("audit_evidence", session_id, evidence_id, include_sanitized_payload, request_id)
        )
        return QueryResponse[EvidenceDetail](
            request_id=request_id or "audit-evidence",
            ok=True,
            data=EvidenceDetail(
                id=evidence_id,
                kind="observation",
                label="Error observation",
                summary="The observation reported invalid arguments.",
                source="event_stream",
                occurred_at=NOW,
                body="Observation summary only.",
            ),
        )

    def list_audit_records(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordsResult]:
        self.calls.append(("audit_records", session_id, limit, cursor, request_id))
        return QueryResponse[AuditRecordsResult](
            request_id=request_id or "audit-records",
            ok=True,
            data=AuditRecordsResult(
                records=(
                    AuditRecord(
                        id="record-1",
                        scope=AuditSessionScope(session_id=session_id),
                        kind="observation",
                        filter_kind="actions",
                        title="Command failed",
                        summary="A command returned a non-zero exit code.",
                        actor="tool",
                        source_label="EventStream",
                        occurred_at=NOW,
                        severity="danger",
                        confidence="high",
                        verdict="failed",
                        evidence_refs=(
                            EvidenceRef(
                                id="evidence-1",
                                kind="observation",
                                label="Error observation",
                                summary="The observation reported invalid arguments.",
                            ),
                        ),
                    ),
                ),
                total_count=1,
            ),
        )


@dataclass
class _WorkspaceInspectionGateway:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def file_content(
        self,
        *,
        path: str | None,
        start_line: int = 1,
        line_count: int | None = None,
        evidence_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("file_content", path, start_line, line_count, evidence_id))
        return {
            "schemaVersion": "plato.workspace_inspection.file_content.v1",
            "workspaceId": "current",
            "file": {
                "path": "app.txt",
                "pathLabel": "workspace://current/app.txt",
                "exists": True,
                "fileKind": "text",
            },
            "range": {
                "startLine": start_line,
                "endLine": 2,
                "totalLines": 2,
                "truncated": False,
            },
            "content": {
                "lines": [
                    {"lineNumber": 1, "text": "first line"},
                    {"lineNumber": 2, "text": "second line"},
                ],
            },
            "contentHash": "sha256:file",
            "warnings": [],
        }

    def diff(
        self,
        *,
        path: str,
        base: str = "head",
        context_lines: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("diff", path, base, context_lines, max_bytes))
        return {
            "schemaVersion": "plato.workspace_inspection.diff.v1",
            "workspaceId": "current",
            "file": {
                "path": "app.txt",
                "pathLabel": "workspace://current/app.txt",
            },
            "base": base,
            "isAvailable": True,
            "hunks": [],
            "stats": {
                "additions": 2,
                "deletions": 1,
                "hunkCount": 1,
                "truncated": False,
            },
            "contentHash": "sha256:diff",
            "warnings": [],
        }


@dataclass
class _AnswerProvider:
    baseline_body: str = ""
    evidence_refs: tuple[Any, ...] = ()

    def answer(
        self,
        *,
        request: ReadOnlyInquiryRequest,
        baseline_answer: ReadOnlyInquiryAnswer,
        evidence_refs: tuple[Any, ...],
        warnings: tuple[Any, ...] = (),
    ) -> ReadOnlyInquiryAnswerProviderResult:
        self.baseline_body = baseline_answer.body
        self.evidence_refs = evidence_refs
        return ReadOnlyInquiryAnswerProviderResult(
            status="answered",
            answer=ReadOnlyInquiryAnswer(
                title="Provider answer",
                body="Provider-rendered answer.",
                confidence="high",
            ),
            evidence_refs=evidence_refs[:1],
            warnings=warnings,
        )


def _snapshot(
    session_id: str,
    *,
    with_plan: bool = False,
    with_diagnostics: bool = False,
) -> MainPageSnapshot:
    project = ProjectSummary(id="project-local", name="Local")
    workflow = WorkflowSummary(id="authoring", name="Authoring")
    session = SessionSummary(
        id=session_id,
        project_id=project.id,
        workflow_id=workflow.id,
        name="Session",
        status="running",
        created_at=NOW,
        updated_at=NOW,
    )
    plan = _plan(session_id) if with_plan else None
    return MainPageSnapshot(
        project=project,
        workflows=(workflow,),
        workflow=workflow,
        sessions=(session,),
        session=session,
        active_plan=plan,
        result=(
            ResultCardView(
                id="result-1",
                session_id=session_id,
                task_node_id="task-1",
                title="Workspace result",
                summary="The workspace has one changed file.",
            )
            if with_plan
            else None
        ),
        file_change_summary=(
            FileChangeSummaryView(
                session_id=session_id,
                task_node_id="task-1",
                recursive=False,
                changed_files=(
                    FileChangeItemView(
                        path="README.md",
                        change_type="modified",
                        summary="Documentation updated.",
                        owner_task_node_id="task-1",
                    ),
                ),
                summary="1 file changed.",
            )
            if with_plan
            else None
        ),
        planning=(
            PlanningView(
                state="draft_ready",
                title="Diagnostic context",
                summary="Safe planning diagnostics.",
                diagnostics=(
                    PlanningDiagnosticView(
                        code="dirty_authoring_state",
                        severity="warning",
                        message=(
                            "Authoring ASK state is still active even though "
                            "a TaskTree already exists."
                        ),
                    ),
                ),
            )
            if with_diagnostics
            else None
        ),
        generated_at=NOW,
    )


def _plan(session_id: str) -> PlanView:
    task = TaskNodeCardView(
        id="task-1",
        plan_id="plan-1",
        task_index="1",
        title="Inspect workspace",
        summary="Review workspace facts.",
        status="done",
        execution="done",
        display_index=1,
        result_ref="result-1",
        version=1,
    )
    return PlanView(
        id="plan-1",
        session_id=session_id,
        title="Inspection plan",
        summary="Inspect the workspace.",
        objective="Answer read-only questions.",
        status="published",
        task_count=1,
        task_node_ids=("task-1",),
        task_nodes=(task,),
        execution_rollup=ExecutionRollupView(total=1, done=1),
        version=1,
    )
