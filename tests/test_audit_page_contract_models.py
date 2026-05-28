"""Tests for Audit Page backend-to-frontend contract models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from taskweavn.server.ui_contract import (
    AuditConfigScope,
    AuditDisclosure,
    AuditEntryContext,
    AuditFilterView,
    AuditOverview,
    AuditPageRequestView,
    AuditPageSnapshot,
    AuditReadyPageState,
    AuditRecord,
    AuditRecordDetail,
    AuditRecordFlags,
    AuditTaskScope,
    EffectiveConfigSummary,
    EvidenceDetail,
    EvidenceRef,
    MainPageReturnTarget,
    ProjectSummary,
    RelatedLogsLink,
    SanitizedRawPayload,
    SessionSummary,
    WorkflowSummary,
    audit_evidence_hidden,
    audit_record_updated,
    audit_records_changed,
    audit_snapshot_stale,
)
from taskweavn.task import TaskRef

NOW = datetime(2026, 5, 24, 9, 30, tzinfo=UTC)


def _project() -> ProjectSummary:
    return ProjectSummary(id="project-local", name="Local Project")


def _workflow() -> WorkflowSummary:
    return WorkflowSummary(
        id="workflow-task-authoring",
        name="Task authoring",
        description="Turn user intent into a TaskTree.",
    )


def _session() -> SessionSummary:
    return SessionSummary(
        id="session-1",
        project_id="project-local",
        workflow_id="workflow-task-authoring",
        name="Website session",
        status="completed",
        created_at=NOW,
        updated_at=NOW,
    )


def _task_scope() -> AuditTaskScope:
    return AuditTaskScope(
        session_id="session-1",
        task_node_id="task-1",
        task_ref=TaskRef.published("task-1"),
    )


def _audit_record() -> AuditRecord:
    return AuditRecord(
        id="record-file-1",
        scope=_task_scope(),
        kind="file_change",
        filter_kind="files",
        title="File changed",
        summary="Homepage source was updated by the implementation task.",
        actor="tool",
        source_label="File system observation",
        occurred_at=NOW,
        severity="warning",
        confidence="high",
        verdict="warning",
        completeness="complete",
        task_node_id="task-1",
        task_ref=TaskRef.published("task-1"),
        file_path="src/App.tsx",
        evidence_refs=(
            EvidenceRef(
                id="evidence-file-1",
                kind="file_change",
                label="File change summary",
                summary="src/App.tsx modified.",
            ),
        ),
        flags=AuditRecordFlags(partial=False, hidden=False, redacted=False),
    )


def _audit_record_detail() -> AuditRecordDetail:
    record = _audit_record()
    return AuditRecordDetail(
        **record.model_dump(),
        body="The implementation task updated the homepage source file.",
        why_it_matters="The audit links the file change back to the task that caused it.",
        outcome="The file change is visible and attributed.",
    )


def test_audit_page_snapshot_serializes_contract_shape() -> None:
    detail = _audit_record_detail()
    snapshot = AuditPageSnapshot(
        request=AuditPageRequestView(
            filter="files",
            record_id=detail.id,
            include_detail=True,
        ),
        scope=_task_scope(),
        entry_context=AuditEntryContext(
            kind="from_file_change",
            session_id="session-1",
            task_node_id="task-1",
            file_path="src/App.tsx",
            source_route="/sessions/session-1",
            preferred_filter="files",
            preferred_record_id=detail.id,
        ),
        return_target=MainPageReturnTarget(
            route_name="main.sessionFallback",
            session_id="session-1",
            task_node_id="task-1",
            focus="file_change",
            record_id=detail.id,
        ),
        project=_project(),
        workflow=_workflow(),
        session=_session(),
        overview=AuditOverview(
            verdict="warning",
            completeness="complete",
            summary="One file change is fully attributed.",
            key_issue="Review modified source file.",
            record_counts={"all": 1, "files": 1},
            important_record_ids=(detail.id,),
            generated_by="mock",
            updated_at=NOW,
        ),
        filters=(AuditFilterView(kind="files", label="Files", count=1),),
        records=(_audit_record(),),
        selected_record=detail,
        effective_config=EffectiveConfigSummary(
            summary="Default audit profile was active.",
            profile_label="Standard",
            effective_at=NOW,
        ),
        related_logs=(
            RelatedLogsLink(
                label="View related logs",
                href="/sessions/session-1/diagnostics/logs",
                filters={"sessionId": "session-1", "taskNodeId": "task-1"},
            ),
        ),
        page_state=AuditReadyPageState(),
        cursor="cursor-1",
        generated_at=NOW,
    )

    payload = snapshot.model_dump(mode="json")

    assert payload["schemaVersion"] == "plato.audit.v1"
    assert payload["scope"]["taskNodeId"] == "task-1"
    assert payload["entryContext"]["preferredFilter"] == "files"
    assert payload["returnTarget"]["focus"] == "file_change"
    assert payload["overview"]["verdict"] == "warning"
    assert payload["selectedRecord"]["rawPayload"] is None
    assert "selected_record" not in payload


def test_audit_models_reject_unknown_verdict_negative_counts_and_mismatched_detail() -> None:
    with pytest.raises(ValidationError):
        AuditOverview(
            verdict="pass",  # type: ignore[arg-type]
            completeness="complete",
            summary="Backend verdict must be mapped before transport.",
            generated_by="mock",
        )

    with pytest.raises(ValidationError, match="non-negative"):
        AuditOverview(
            verdict="warning",
            completeness="partial",
            summary="Negative counts are invalid.",
            record_counts={"all": -1},
            generated_by="mock",
        )

    with pytest.raises(ValidationError, match="selected_record"):
        AuditPageSnapshot(
            request=AuditPageRequestView(record_id="record-other", include_detail=True),
            scope=_task_scope(),
            entry_context=AuditEntryContext(
                kind="from_task",
                session_id="session-1",
                source_route="/sessions/session-1",
            ),
            return_target=MainPageReturnTarget(
                route_name="main.sessionFallback",
                session_id="session-1",
                focus="task",
            ),
            session=_session(),
            overview=AuditOverview(
                verdict="warning",
                completeness="complete",
                summary="Mismatched detail should fail.",
                generated_by="mock",
            ),
            selected_record=_audit_record_detail(),
        )


def test_audit_contract_keeps_raw_payloads_permission_gated() -> None:
    with pytest.raises(ValidationError, match="config audit scope requires"):
        AuditConfigScope()

    payload = SanitizedRawPayload(
        format="json",
        content='{"safe": true}',
        redactions=("secret",),
    )

    with pytest.raises(ValidationError, match="raw payload requires"):
        AuditRecordDetail(
            **_audit_record().model_dump(),
            body="Body",
            why_it_matters="Reason",
            raw_payload=payload,
        )

    with pytest.raises(ValidationError, match="requires sanitized payload"):
        EvidenceDetail(
            id="evidence-raw-1",
            kind="event",
            label="Sanitized event",
            summary="A sanitized event payload exists.",
            source="event_stream",
            body="Sanitized payload can be requested later.",
            disclosure=AuditDisclosure(
                raw_payload_available=True,
                raw_payload_shown=True,
            ),
        )


def test_audit_event_builders_emit_expected_payloads() -> None:
    scope = _task_scope()

    records_changed = audit_records_changed(
        "session-1",
        cursor="cursor-2",
        scope=scope,
        record_ids=("record-file-1",),
        reason="file_changes_updated",
    )
    record_updated = audit_record_updated(
        "session-1",
        cursor="cursor-3",
        record_id="record-file-1",
        scope=scope,
        kind="file_change",
        verdict="warning",
    )
    evidence_hidden = audit_evidence_hidden(
        "session-1",
        cursor="cursor-4",
        record_id="record-file-1",
        evidence_ids=("evidence-1",),
        reason_code="policy_redaction",
    )
    snapshot_stale = audit_snapshot_stale(
        "session-1",
        cursor="cursor-5",
        scope=scope,
        reason="cursor_expired",
        last_good_cursor="cursor-1",
    )

    assert records_changed.event_type == "audit.records_changed"
    assert records_changed.payload["scope"] == {
        "kind": "task",
        "sessionId": "session-1",
        "taskNodeId": "task-1",
        "taskRef": {"kind": "published", "id": "task-1"},
    }
    assert records_changed.payload["record_ids"] == ("record-file-1",)
    assert record_updated.payload["verdict"] == "warning"
    assert evidence_hidden.payload["reason_code"] == "policy_redaction"
    assert snapshot_stale.payload["last_good_cursor"] == "cursor-1"
