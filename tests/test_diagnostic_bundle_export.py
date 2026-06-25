from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from taskweavn.cli.main import app
from taskweavn.core import Session, SessionManager, SqliteEventStream, WorkspaceLayout
from taskweavn.diagnostics import (
    DiagnosticBundleExporter,
    DiagnosticExportOptions,
    redact_diagnostic_payload,
)
from taskweavn.interaction import AgentMessage, InProcessMessageBus, SqliteMessageStream
from taskweavn.observability import LogArchiveManifest
from taskweavn.server.ui_contract import task_node_changed
from taskweavn.server.ui_events import SqliteUiEventSource
from taskweavn.task import SqliteTaskBus, SqliteTaskExecutionSummaryStore
from taskweavn.task.models import TaskDomain, TaskRef
from taskweavn.task.result_summary import TaskExecutionSummary
from taskweavn.tools.fs import FileWriteObservation, WriteFileAction
from taskweavn.workspace_inspection import DefaultWorkspaceInspectionGateway

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_diagnostic_bundle_export_writes_redacted_manifest_and_sections(
    tmp_path: Path,
) -> None:
    layout, session = _workspace_with_failed_task(tmp_path)

    result = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=layout.root,
            session_id=session.id,
            output_dir=tmp_path / "diagnostics",
            create_zip=False,
            created_at=NOW,
            max_messages=10,
            max_events=10,
            max_log_entries_per_category=10,
        )
    ).export()

    assert result.zip_path is None
    manifest_path = result.bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == "diagnostic_bundle.v1"
    assert manifest["bundleId"] == f"diagnostic-bundle-{session.id}-20260605T120000Z"
    assert set(manifest["includedSections"]) >= {
        "session",
        "tasks",
        "results",
        "messages",
        "audit",
        "workspace_inspection",
        "events",
        "ui_events",
        "logs",
        "config",
        "frontend",
        "environment",
    }

    manifest_files = {entry["path"] for entry in manifest["files"]}
    actual_files = {
        file.relative_to(result.bundle_dir).as_posix()
        for file in result.bundle_dir.rglob("*")
        if file.is_file()
    }
    assert actual_files == manifest_files
    assert {
        "manifest.json",
        "session/summary.json",
        "session/tasks.json",
        "session/results.json",
        "session/messages.summary.json",
        "audit/summary.json",
        "audit/records.summary.json",
        "inspection/evidence.summary.json",
        "events/events.summary.jsonl",
        "events/ui-events.summary.jsonl",
        "logs/manifest.json",
        "logs/llm.summary.jsonl",
        "config/effective-summary.json",
        "frontend/client-errors.summary.jsonl",
    }.issubset(manifest_files)

    bundle_text = "\n".join(
        file.read_text(encoding="utf-8")
        for file in result.bundle_dir.rglob("*")
        if file.is_file()
    )
    assert "secret-value" not in bundle_text
    assert "raw prompt should not ship" not in bundle_text
    assert str(layout.root) not in bundle_text
    assert "workspace://current" in bundle_text
    assert "<redacted>" in bundle_text
    assert "<omitted>" in bundle_text

    tasks = json.loads((result.bundle_dir / "session/tasks.json").read_text(encoding="utf-8"))
    assert tasks["tasks"][0]["taskId"] == "task-1"
    assert tasks["tasks"][0]["retryEligible"] is True
    product_error = tasks["tasks"][0]["productError"]
    assert product_error["productCategory"] == "task_execution_failed"
    assert product_error["recoveryActions"] == [
        "retry_task",
        "open_audit",
        "export_diagnostics",
    ]
    assert product_error["auditRef"] == {
        "scope": "task",
        "sessionId": session.id,
        "taskId": "task-1",
        "recordId": "record-result-published-task-1",
        "evidenceId": "evidence-record-result-published-task-1",
        "filter": "results",
    }
    assert product_error["diagnosticRefs"] == {
        "sessionId": session.id,
        "taskId": "task-1",
        "errorRef": "error-1",
        "path": "workspace://current/secret.txt",
        "auditRecordId": "record-result-published-task-1",
        "auditEvidenceId": "evidence-record-result-published-task-1",
    }

    inspection = json.loads(
        (result.bundle_dir / "inspection/evidence.summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert inspection["schemaVersion"] == (
        "plato.workspace_inspection.diagnostic_summary.v1"
    )
    assert inspection["records"][0]["evidenceRef"]["kind"] == "file_snapshot"
    assert inspection["records"][0]["evidenceRef"]["pathLabel"] == (
        "workspace://current/secret.txt"
    )
    assert inspection["records"][0]["payloadSummary"]["previewLines"][0]["text"] == (
        "api_key=<redacted>"
    )
    support_summary = inspection["supportSummary"]
    assert support_summary["schemaVersion"] == (
        "plato.workspace_inspection.support_summary.v1"
    )
    assert support_summary["recordCount"] == 1
    assert support_summary["recordsByKind"] == {"file_snapshot": 1}
    assert support_summary["availableEvidenceKinds"] == ["file_snapshot"]
    assert support_summary["hasFileEvidence"] is True
    assert support_summary["hasDiffEvidence"] is False
    assert support_summary["hasGitStatusEvidence"] is False
    assert support_summary["previewLimits"] == {
        "maxPreviewChars": 200,
        "maxPreviewLines": 20,
    }
    assert any(
        limitation
        == "Raw unified diffs and full file contents are intentionally excluded."
        for limitation in support_summary["limitations"]
    )


def test_diagnostic_bundle_marks_missing_sources_without_failing(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path / "workspace")
    with SessionManager(layout) as manager:
        session = manager.create("Empty")

    result = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=layout.root,
            session_id=session.id,
            output_dir=tmp_path / "diagnostics",
            create_zip=False,
            created_at=NOW,
        )
    ).export()

    manifest = json.loads((result.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    section_status = {section["name"]: section["status"] for section in manifest["sections"]}
    assert section_status["session"] == "included"
    assert section_status["messages"] == "missing"
    assert section_status["events"] == "missing"
    assert section_status["logs"] == "missing"
    assert section_status["config"] == "missing"
    assert section_status["frontend"] == "missing"
    assert section_status["workspace_inspection"] == "missing"


def test_diagnostic_bundle_exports_runtime_input_route_descriptors(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout(tmp_path / "workspace")
    layout.bootstrap()
    with SessionManager(layout) as manager:
        session = manager.create("Runtime input diagnostics")
    _write_runtime_input_messages(layout, session)

    result = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=layout.root,
            session_id=session.id,
            output_dir=tmp_path / "diagnostics",
            create_zip=False,
            created_at=NOW,
        )
    ).export()

    manifest = json.loads((result.bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "runtime_input" in manifest["includedSections"]
    assert "router/runtime-input.summary.json" in {
        entry["path"] for entry in manifest["files"]
    }

    summary_text = (result.bundle_dir / "router/runtime-input.summary.json").read_text(
        encoding="utf-8"
    )
    assert str(layout.root) not in summary_text
    assert "secret-value" not in summary_text
    assert "workspace://current/private.txt" in summary_text
    summary = json.loads(summary_text)
    assert summary["schemaVersion"] == "plato.runtime_input.diagnostic_summary.v1"
    assert summary["routeCount"] == 2
    assert summary["redactionPolicy"] == {
        "llmProviderData": "excluded",
        "modelInputData": "excluded",
        "rawLogsIncluded": False,
        "rawSqlRowsIncluded": False,
        "source": "MessageStream safe Router context",
    }

    routes = {route["commandId"]: route for route in summary["routes"]}
    route = routes["route-1"]
    assert route["decisionIds"] == ["decision-1"]
    assert route["conversationMessageIds"] == [
        "runtime-input-user-route-1",
        "runtime-input-trace-route-1",
    ]
    assert route["activityMessageIds"] == ["runtime-input-activity-answer-route-1"]
    assert route["auditRefs"]["recordIds"] == [
        "record-message-runtime-input-user-route-1",
        "record-message-runtime-input-trace-route-1",
        "record-message-runtime-input-activity-answer-route-1",
    ]
    assert route["intent"] == "question"
    assert route["sideEffect"] == "no_effect"
    assert route["dispatchTarget"] == "read_only_inquiry"
    assert route["outcomeStatus"] == "answered"
    assert route["diagnosticDescriptor"] == {
        "kind": "runtime_input_route",
        "linksActivity": True,
        "linksAuditRecord": True,
        "linksDownstreamCommand": False,
        "linksRouterDecision": True,
        "linksUserInput": True,
        "redacted": True,
    }

    command_route = routes["route-2"]
    assert command_route["downstreamCommandIds"] == ["route-2"]
    assert command_route["contractCommandKinds"] == ["record_guidance"]
    assert command_route["contractCommandStatuses"] == ["accepted"]
    assert command_route["diagnosticDescriptor"]["linksDownstreamCommand"] is True


def test_diagnostic_bundle_allows_repeated_export_in_same_second(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout(tmp_path / "workspace")
    with SessionManager(layout) as manager:
        session = manager.create("Repeat export")

    output_dir = tmp_path / "diagnostics"
    first = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=layout.root,
            session_id=session.id,
            output_dir=output_dir,
            create_zip=False,
            created_at=datetime(2026, 6, 5, 12, 0, 0, 100, tzinfo=UTC),
        )
    ).export()
    second = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=layout.root,
            session_id=session.id,
            output_dir=output_dir,
            create_zip=False,
            created_at=datetime(2026, 6, 5, 12, 0, 0, 200, tzinfo=UTC),
        )
    ).export()

    assert first.bundle_id != second.bundle_id
    assert first.bundle_dir.exists()
    assert second.bundle_dir.exists()


def test_diagnostic_redaction_masks_secrets_paths_and_raw_payloads(tmp_path: Path) -> None:
    payload = {
        "api_key": "secret-value",
        "path": str(tmp_path / "workspace" / "file.txt"),
        "prompt": "raw prompt should not ship",
        "nested": {"toolArguments": {"content": "secret-value"}},
    }

    redacted = redact_diagnostic_payload(
        payload,
        workspace_root=tmp_path / "workspace",
    )

    assert redacted == {
        "api_key": "<redacted>",
        "nested": {"toolArguments": "<omitted>"},
        "path": "workspace://current/file.txt",
        "prompt": "<omitted>",
    }


def test_diagnostics_export_cli_writes_bundle_directory(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path / "workspace")
    with SessionManager(layout) as manager:
        session = manager.create("CLI export")

    result = CliRunner().invoke(
        app,
        [
            "diagnostics",
            "export",
            "--workspace",
            str(layout.root),
            "--session-id",
            session.id,
            "--output",
            str(tmp_path / "diagnostics"),
            "--no-zip",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bundleId"].startswith(f"diagnostic-bundle-{session.id}-")
    assert payload["zipPath"] is None
    assert (Path(payload["bundleDir"]) / "manifest.json").exists()


def _workspace_with_failed_task(tmp_path: Path) -> tuple[WorkspaceLayout, Session]:
    layout = WorkspaceLayout(tmp_path / "workspace")
    layout.bootstrap()
    with SessionManager(layout) as manager:
        session = manager.create("Diagnostic export")
    _write_failed_task(layout, session)
    _write_message(layout, session)
    _write_events(layout, session)
    _write_ui_event(layout, session)
    _write_logs(layout, session)
    _write_inspection_evidence(layout)
    return layout, session


def _write_failed_task(layout: WorkspaceLayout, session: Session) -> None:
    with SqliteTaskBus(layout.workspace_tasks_db) as bus:
        task = TaskDomain(
            task_id="task-1",
            session_id=session.id,
            root_id="task-1",
            intent=f"Write a report from {layout.root}/private-note.txt",
            required_capability="coding",
            created_by="tester",
        )
        bus.publish(task)
        bus.claim_next(session.id, capability="coding", agent_id="agent")
        bus.fail(session.id, "task-1", error_ref="error-1")

    with SqliteTaskExecutionSummaryStore(layout.workspace_results_db) as store:
        store.put(
            TaskExecutionSummary(
                summary_id="error-1",
                session_id=session.id,
                task_id="task-1",
                kind="error",
                source="execution_bridge",
                title="Task execution failed",
                summary="Task execution failed with ExecutionError.",
                error_type="ExecutionError",
                error_message="Task execution failed with ExecutionError.",
                metadata={
                    "api_key": "secret-value",
                    "logPath": str(layout.session_meta_dir(session.id)),
                    "productCategory": "task_execution_failed",
                    "recoveryActions": [
                        "retry_task",
                        "open_audit",
                        "export_diagnostics",
                    ],
                    "severity": "recoverable",
                    "userMessageKey": "task.execution_failed",
                    "diagnosticRefs": {
                        "sessionId": session.id,
                        "taskId": "task-1",
                        "errorRef": "error-1",
                        "path": str(layout.root / "secret.txt"),
                    },
                },
            )
        )


def _write_message(layout: WorkspaceLayout, session: Session) -> None:
    stream = SqliteMessageStream(layout.workspace_messages_db)
    bus = InProcessMessageBus(stream)
    try:
        bus.publish(
            AgentMessage(
                session_id=session.id,
                task_id="task-1",
                message_type="informational",
                content=f"Check {layout.root}/secret.txt with token secret-value.",
                context={
                    "authorization": "secret-value",
                    "prompt": "raw prompt should not ship",
                    "path": str(layout.root / "secret.txt"),
                },
            )
        )
    finally:
        bus.close()
        stream.close()


def _write_runtime_input_messages(layout: WorkspaceLayout, session: Session) -> None:
    stream = SqliteMessageStream(layout.workspace_messages_db)
    bus = InProcessMessageBus(stream)
    try:
        bus.publish(
            AgentMessage(
                message_id="runtime-input-user-route-1",
                session_id=session.id,
                agent_id="user",
                message_type="informational",
                content=(
                    f"Can you inspect {layout.root}/private.txt with "
                    "api_key=secret-value?"
                ),
                context={
                    "title": "User input",
                    "conversation_render": {
                        "protocolVersion": "plato.conversation.render.v1",
                        "renderKind": "text",
                        "text": {
                            "title": "User input",
                            "body": (
                                f"Can you inspect {layout.root}/private.txt with "
                                "api_key=secret-value?"
                            ),
                        },
                    },
                },
                related_action_id="route-1",
            )
        )
        bus.publish(
            AgentMessage(
                message_id="runtime-input-trace-route-1",
                session_id=session.id,
                agent_id="router",
                message_type="informational",
                content="Input was answered through Read-Only Inquiry Context.",
                context={
                    "title": "Router interpretation",
                    "activity_related_refs": [
                        {
                            "kind": "session",
                            "id": f"session:{session.id}:status",
                            "label": "Session status",
                        }
                    ],
                    "conversation_render": {
                        "protocolVersion": "plato.conversation.render.v1",
                        "renderKind": "router_trace",
                        "routerTrace": {
                            "intent": "question",
                            "scopeKind": "session",
                            "confidence": "high",
                            "sideEffect": "no_effect",
                            "dispatchTarget": "read_only_inquiry",
                            "explanation": (
                                f"Looked at {layout.root}/private.txt while "
                                "redacting api_key=secret-value."
                            ),
                            "outcomeStatus": "answered",
                        },
                    },
                },
                related_action_id="decision-1",
            )
        )
        bus.publish(
            AgentMessage(
                message_id="runtime-input-activity-answer-route-1",
                session_id=session.id,
                agent_id="router",
                message_type="informational",
                content="Answered without mutating workspace files.",
                context={
                    "title": "Read-only question answered",
                    "activity_related_refs": [
                        {
                            "kind": "session",
                            "id": f"session:{session.id}:status",
                            "label": "Session status",
                        }
                    ],
                    "runtime_input_activity_kind": "answer",
                    "runtime_input_side_effect": "no_effect",
                    "runtime_input_decision_id": "decision-1",
                    "runtime_input_outcome_status": "answered",
                    "runtime_input_scope_kind": "session",
                },
                related_action_id="decision-1",
            )
        )
        bus.publish(
            AgentMessage(
                message_id="contract-revision-route-2",
                session_id=session.id,
                agent_id="router",
                message_type="informational",
                content="Guidance recorded: keep diffs small.",
                context={
                    "title": "Guidance recorded",
                    "runtime_input_activity_kind": "guidance_recorded",
                    "runtime_input_side_effect": "context_effect",
                    "contract_command_id": "route-2",
                    "contract_command_kind": "record_guidance",
                    "contract_command_status": "accepted",
                    "contract_guidance_id": "guidance-1",
                },
                related_action_id="route-2",
            )
        )
    finally:
        bus.close()
        stream.close()


def _write_events(layout: WorkspaceLayout, session: Session) -> None:
    action = WriteFileAction(
        event_id="action-1",
        path=str(layout.root / "secret.txt"),
        content="api_key=secret-value",
    )
    observation = FileWriteObservation(
        event_id="observation-1",
        action_id="action-1",
        path=str(layout.root / "secret.txt"),
        bytes_written=20,
        created=True,
    )
    with SqliteEventStream(layout.session_events_db(session.id)) as stream:
        stream.append(action, task_id="task-1")
        stream.append(observation, task_id="task-1")


def _write_ui_event(layout: WorkspaceLayout, session: Session) -> None:
    event = task_node_changed(
        session.id,
        cursor="cursor-1",
        task_refs=(TaskRef.published("task-1"),),
        reason="fixture",
    )
    with SqliteUiEventSource(layout.workspace_ui_events_db) as source:
        source.append(event)


def _write_logs(layout: WorkspaceLayout, session: Session) -> None:
    session.logs_dir.mkdir(parents=True, exist_ok=True)
    manifest = LogArchiveManifest(
        session_id=session.id,
        created_at=NOW,
        config_hash="hash-1",
        active_config_path=str(layout.root / ".plato" / "logging.json"),
        archive_root=str(session.logs_dir),
        files={
            "llm": "llm.jsonl",
            "frontend": "frontend-errors.jsonl",
        },
    )
    (session.logs_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    (session.logs_dir / "llm.jsonl").write_text(
        json.dumps(
            {
                "ts": NOW.isoformat(),
                "level": "INFO",
                "category": "llm",
                "event": "request",
                "message": "llm request",
                "context": {"session_id": session.id, "provider": "deepseek"},
                "data": {
                    "authorization": "secret-value",
                    "prompt": "raw prompt should not ship",
                    "path": str(layout.root / "prompt.txt"),
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (session.logs_dir / "frontend-errors.jsonl").write_text(
        json.dumps(
            {
                "receivedAt": NOW.isoformat(),
                "sessionId": session.id,
                "payload": {
                    "name": "TypeError",
                    "message": "token secret-value failed",
                    "stack": f"stack at {layout.root}/frontend/App.tsx",
                    "route": str(layout.session_dir(session.id)),
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_inspection_evidence(layout: WorkspaceLayout) -> None:
    (layout.root / "secret.txt").write_text(
        "api_key=secret-value\n",
        encoding="utf-8",
    )
    gateway = DefaultWorkspaceInspectionGateway.build(
        workspace_root=layout.root,
        workspace_id="current",
        inspection_db_path=layout.workspace_inspection_db,
    )
    gateway.capture_evidence(
        {
            "kind": "file_snapshot",
            "reason": "diagnostic_export",
            "path": "secret.txt",
            "lineRange": {
                "startLine": 1,
                "lineCount": 5,
            },
        }
    )
