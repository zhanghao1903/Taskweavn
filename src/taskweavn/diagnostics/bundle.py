"""Product 1.0 diagnostic bundle export.

The exporter is intentionally local and read-focused. It packages summaries
from durable workspace stores into one redacted directory, and can optionally
zip that directory for tester/support handoff.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from taskweavn import __version__
from taskweavn.core import Session, SessionManager, WorkspaceLayout
from taskweavn.interaction import AgentMessage, SqliteMessageStream
from taskweavn.observability import LogArchiveManifest
from taskweavn.observability.redaction import redact_payload
from taskweavn.product_errors import product_error_audit_ref_for_task
from taskweavn.server.ui_contract.audit_source_providers import (
    WorkspaceAuditConfigProvider,
    WorkspaceAuditLogProvider,
)
from taskweavn.server.ui_contract.gateway_providers import WorkspaceAuditEventProvider
from taskweavn.server.ui_contract.gateways import DefaultUiQueryGateway
from taskweavn.task.models import TaskDomain
from taskweavn.task.projection import DefaultTaskProjectionService
from taskweavn.task.result_summary import (
    TaskExecutionSummary,
    task_execution_summary_to_task_summary_view,
)
from taskweavn.task.views import TaskSummaryView

SchemaSectionStatus = Literal["included", "partial", "missing", "skipped"]

DIAGNOSTIC_BUNDLE_SCHEMA_VERSION = "diagnostic_bundle.v1"
DIAGNOSTIC_REDACTION_PROFILE = "product_1_0_default"
FRONTEND_ERROR_LOG_FILENAME = "frontend-errors.jsonl"

_SECTION_ORDER = (
    "session",
    "tasks",
    "results",
    "messages",
    "audit",
    "events",
    "ui_events",
    "logs",
    "config",
    "frontend",
    "environment",
)
_OMITTED_VALUE = "<omitted>"
_ABSOLUTE_PATH_VALUE = "<redacted:absolute_path>"
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.:-]+")
_KEY_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
_OMIT_EXACT_KEYS = {
    "content",
    "developerprompt",
    "input",
    "messages",
    "prompt",
    "raw",
    "request",
    "response",
    "stack",
    "stacktrace",
    "systemprompt",
    "traceback",
    "userprompt",
}
_OMIT_KEY_MARKERS = (
    "prompt",
    "providerpayload",
    "rawpayload",
    "requestpayload",
    "responsepayload",
    "toolarguments",
    "toolargs",
)
_SECRET_FRAGMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|credential|password|secret|token)"
    r"(\s*[=:]\s*|\s+)"
    r"([^\s,;]+)"
)


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


class DiagnosticBundleFileEntry(_FrozenModel):
    path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    redacted: bool = True
    source: str = Field(min_length=1)


class DiagnosticBundleSection(_FrozenModel):
    name: str = Field(min_length=1)
    status: SchemaSectionStatus
    files: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class DiagnosticBundleManifest(_FrozenModel):
    schema_version: Literal["diagnostic_bundle.v1"] = Field(
        default="diagnostic_bundle.v1",
        alias="schemaVersion",
    )
    bundle_id: str = Field(alias="bundleId", min_length=1)
    created_at: datetime = Field(alias="createdAt")
    workspace_root_label: str = Field(default="workspace://current", alias="workspaceRootLabel")
    session_id: str = Field(alias="sessionId", min_length=1)
    task_ids: tuple[str, ...] = Field(default=(), alias="taskIds")
    redaction_profile: str = Field(
        default=DIAGNOSTIC_REDACTION_PROFILE,
        alias="redactionProfile",
    )
    included_sections: tuple[str, ...] = Field(default=(), alias="includedSections")
    sections: tuple[DiagnosticBundleSection, ...] = ()
    warnings: tuple[str, ...] = ()
    files: tuple[DiagnosticBundleFileEntry, ...] = ()


@dataclass(frozen=True)
class DiagnosticExportOptions:
    workspace_root: Path
    session_id: str
    output_dir: Path
    create_zip: bool = True
    max_messages: int = 50
    max_events: int = 100
    max_ui_events: int = 100
    max_log_entries_per_category: int = 40
    max_audit_records: int = 100
    created_at: datetime | None = None


@dataclass(frozen=True)
class DiagnosticExportResult:
    bundle_id: str
    bundle_dir: Path
    zip_path: Path | None
    manifest: DiagnosticBundleManifest


class DiagnosticBundleError(RuntimeError):
    """Raised when a bundle cannot be created at all."""


class DiagnosticBundleExporter:
    """Export one Product 1.0 diagnostic bundle for a session."""

    def __init__(self, options: DiagnosticExportOptions) -> None:
        workspace_root = options.workspace_root.expanduser().resolve()
        output_dir = options.output_dir.expanduser().resolve()
        self.options = DiagnosticExportOptions(
            workspace_root=workspace_root,
            session_id=options.session_id,
            output_dir=output_dir,
            create_zip=options.create_zip,
            max_messages=max(0, options.max_messages),
            max_events=max(0, options.max_events),
            max_ui_events=max(0, options.max_ui_events),
            max_log_entries_per_category=max(0, options.max_log_entries_per_category),
            max_audit_records=max(0, options.max_audit_records),
            created_at=options.created_at,
        )
        self.layout = WorkspaceLayout(workspace_root)

    def export(self) -> DiagnosticExportResult:
        created_at = self.options.created_at or datetime.now(UTC)
        bundle_id = _bundle_id(self.options.session_id, created_at)
        bundle_dir = self.options.output_dir / bundle_id
        if bundle_dir.exists():
            raise DiagnosticBundleError(f"diagnostic bundle already exists: {bundle_dir}")

        with SessionManager(self.layout) as session_manager:
            session = session_manager.get(self.options.session_id)
            if session is None:
                raise DiagnosticBundleError(f"session not found: {self.options.session_id}")
            bundle_dir.mkdir(parents=True)

            tasks, task_source_warnings = _safe_read_tasks(
                self.layout.workspace_tasks_db,
                session.id,
            )
            summaries, result_source_warnings = _safe_read_result_summaries(
                self.layout.workspace_results_db,
                session.id,
            )
            writer = _BundleWriter(
                bundle_dir=bundle_dir,
                workspace_root=self.options.workspace_root,
            )
            self._run_collector(
                writer,
                "session",
                lambda: self._collect_session(writer, session, tasks),
            )
            self._run_collector(
                writer,
                "tasks",
                lambda: self._collect_tasks(
                    writer,
                    tasks,
                    summaries,
                    task_source_warnings,
                ),
            )
            self._run_collector(
                writer,
                "results",
                lambda: self._collect_results(
                    writer,
                    tasks,
                    summaries,
                    result_source_warnings,
                ),
            )
            self._run_collector(
                writer,
                "messages",
                lambda: self._collect_messages(writer, session),
            )
            self._run_collector(
                writer,
                "audit",
                lambda: self._collect_audit(
                    writer,
                    session_manager=session_manager,
                    session=session,
                    tasks=tasks,
                    summaries=summaries,
                ),
            )
            self._run_collector(
                writer,
                "events",
                lambda: self._collect_events(writer, session),
            )
            self._run_collector(
                writer,
                "ui_events",
                lambda: self._collect_ui_events(writer, session),
            )
            self._run_collector(
                writer,
                "logs",
                lambda: self._collect_logs(writer, session),
            )
            self._run_collector(
                writer,
                "config",
                lambda: self._collect_config(writer, session),
            )
            self._run_collector(
                writer,
                "frontend",
                lambda: self._collect_frontend_errors(writer, session),
            )
            self._run_collector(
                writer,
                "environment",
                lambda: self._collect_environment(writer),
            )
            manifest = writer.write_manifest(
                bundle_id=bundle_id,
                created_at=created_at,
                session_id=session.id,
                task_ids=tuple(task.task_id for task in tasks),
            )

        zip_path = None
        if self.options.create_zip:
            zip_path = Path(
                shutil.make_archive(
                    str(bundle_dir),
                    "zip",
                    root_dir=bundle_dir,
                )
            )
        return DiagnosticExportResult(
            bundle_id=bundle_id,
            bundle_dir=bundle_dir,
            zip_path=zip_path,
            manifest=manifest,
        )

    def _run_collector(
        self,
        writer: _BundleWriter,
        section: str,
        collect: Any,
    ) -> None:
        try:
            files, warnings = collect()
        except Exception as exc:  # noqa: BLE001 - one source must not break export.
            writer.add_section(
                section,
                "missing",
                (),
                (f"{type(exc).__name__}: collector failed",),
            )
            return
        status: SchemaSectionStatus = "included"
        if warnings and files:
            status = "partial"
        elif warnings and not files:
            status = "missing"
        writer.add_section(section, status, files, warnings)

    def _collect_session(
        self,
        writer: _BundleWriter,
        session: Session,
        tasks: Sequence[TaskDomain],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        task_status_counts: dict[str, int] = {}
        for task in tasks:
            task_status_counts[task.status] = task_status_counts.get(task.status, 0) + 1
        rel_path = writer.write_json(
            "session/summary.json",
            kind="session_summary",
            source="SessionManager",
            payload={
                "sessionId": session.id,
                "name": _preview(session.name, 160),
                "status": session.status,
                "createdAt": session.created_at,
                "lastActiveAt": session.last_active_at,
                "workspaceRootLabel": "workspace://current",
                "sessionDirLabel": (
                    f"workspace://current/.taskweavn/sessions/{session.id}"
                ),
                "taskCount": len(tasks),
                "taskStatusCounts": task_status_counts,
                "hasSessionDirectory": session.session_dir.exists(),
                "hasProjectDirectory": session.project_dir.exists(),
                "hasLogDirectory": session.logs_dir.exists(),
            },
        )
        return (rel_path,), ()

    def _collect_tasks(
        self,
        writer: _BundleWriter,
        tasks: Sequence[TaskDomain],
        summaries: Sequence[TaskExecutionSummary],
        source_warnings: Sequence[str],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        summary_by_id = {summary.summary_id: summary for summary in summaries}
        payload = {
            "taskCount": len(tasks),
            "tasks": [
                {
                    "taskId": task.task_id,
                    "title": _preview(task.intent, 120),
                    "intentPreview": _preview(task.intent, 240),
                    "status": task.status,
                    "parentId": task.parent_id,
                    "rootId": task.root_id,
                    "orderIndex": task.order_index,
                    "requiredCapability": task.required_capability,
                    "resultRef": task.result_ref,
                    "errorRef": task.error_ref,
                    "retryEligible": task.status == "failed",
                    "claimedBy": task.claimed_by,
                    "waitingForAskId": task.waiting_for_ask_id,
                    "interruptRequested": task.interrupt_requested,
                    "interruptRequestedBy": task.interrupt_requested_by,
                    "createdAt": task.created_at,
                    "startedAt": task.started_at,
                    "completedAt": task.completed_at,
                    "productError": _product_error_from_task(task, summary_by_id),
                }
                for task in tasks
            ],
        }
        rel_path = writer.write_json(
            "session/tasks.json",
            kind="task_tree",
            source="TaskBus",
            payload=payload,
        )
        return (rel_path,), tuple(source_warnings)

    def _collect_results(
        self,
        writer: _BundleWriter,
        tasks: Sequence[TaskDomain],
        summaries: Sequence[TaskExecutionSummary],
        source_warnings: Sequence[str],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        task_ids = {task.task_id for task in tasks}
        ref_ids = {
            ref
            for task in tasks
            for ref in (task.result_ref, task.error_ref)
            if ref is not None
        }
        summaries_for_session = [
            summary
            for summary in summaries
            if summary.task_id in task_ids or summary.summary_id in ref_ids
        ]
        summary_by_id = {summary.summary_id: summary for summary in summaries_for_session}
        warnings: list[str] = list(source_warnings)
        missing_refs = sorted(ref for ref in ref_ids if ref not in summary_by_id)
        if missing_refs:
            warnings.append(
                "result summary store did not contain "
                f"{len(missing_refs)} referenced summary record(s)"
            )
        if not self.layout.workspace_results_db.exists():
            warnings.append("result summary store is not present")

        rel_path = writer.write_json(
            "session/results.json",
            kind="result_error_summaries",
            source="TaskExecutionSummaryStore",
            payload={
                "summaryCount": len(summaries_for_session),
                "missingRefs": missing_refs,
                "summaries": [
                    _summary_payload(summary)
                    for summary in sorted(
                        summaries_for_session,
                        key=lambda item: (item.updated_at, item.summary_id),
                    )
                ],
            },
        )
        return (rel_path,), tuple(warnings)

    def _collect_messages(
        self,
        writer: _BundleWriter,
        session: Session,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if not self.layout.workspace_messages_db.exists():
            return (), ("message stream store is not present",)
        warnings: list[str] = []
        with SqliteMessageStream(self.layout.workspace_messages_db) as stream:
            messages = list(stream.list_for_session(session.id))
        selected = _tail(messages, self.options.max_messages)
        if len(messages) > len(selected):
            warnings.append(
                f"message stream truncated from {len(messages)} to {len(selected)} records"
            )
        rel_path = writer.write_json(
            "session/messages.summary.json",
            kind="message_stream_summary",
            source="MessageStream",
            payload={
                "messageCount": len(messages),
                "includedMessageCount": len(selected),
                "truncated": len(messages) > len(selected),
                "messages": [_message_payload(message) for message in selected],
            },
        )
        return (rel_path,), tuple(warnings)

    def _collect_audit(
        self,
        writer: _BundleWriter,
        *,
        session_manager: SessionManager,
        session: Session,
        tasks: Sequence[TaskDomain],
        summaries: Sequence[TaskExecutionSummary],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        warnings: list[str] = []
        message_stream = (
            SqliteMessageStream(self.layout.workspace_messages_db)
            if self.layout.workspace_messages_db.exists()
            else None
        )
        try:
            gateway = _build_audit_gateway(
                session_manager=session_manager,
                layout=self.layout,
                tasks=tasks,
                summaries=summaries,
                message_stream=message_stream,
            )
            snapshot_response = gateway.get_audit_snapshot(
                session.id,
                limit=self.options.max_audit_records,
                include_detail=False,
            )
            files: list[str] = []
            if snapshot_response.ok and snapshot_response.data is not None:
                snapshot = snapshot_response.data
                files.append(
                    writer.write_json(
                        "audit/summary.json",
                        kind="audit_summary",
                        source="UiQueryGateway.get_audit_snapshot",
                        payload={
                            "schemaVersion": snapshot.schema_version,
                            "sessionId": snapshot.session.id,
                            "overview": snapshot.overview,
                            "filters": snapshot.filters,
                            "effectiveConfig": snapshot.effective_config,
                            "relatedLogs": snapshot.related_logs,
                            "permissions": snapshot.permissions,
                            "pageState": snapshot.page_state,
                            "cursor": snapshot.cursor,
                            "generatedAt": snapshot.generated_at,
                        },
                    )
                )
            else:
                warnings.append("audit snapshot query did not return data")

            records_response = gateway.list_audit_records(
                session.id,
                limit=self.options.max_audit_records,
            )
            if records_response.ok and records_response.data is not None:
                result = records_response.data
                if result.next_cursor is not None:
                    warnings.append("audit records truncated by gateway page limit")
                files.append(
                    writer.write_json(
                        "audit/records.summary.json",
                        kind="audit_records_summary",
                        source="UiQueryGateway.list_audit_records",
                        payload={
                            "totalCount": result.total_count,
                            "includedRecordCount": len(result.records),
                            "nextCursor": result.next_cursor,
                            "records": [
                                {
                                    "id": record.id,
                                    "kind": record.kind,
                                    "filterKind": record.filter_kind,
                                    "title": record.title,
                                    "summary": _preview(record.summary, 360),
                                    "actor": record.actor,
                                    "sourceLabel": record.source_label,
                                    "occurredAt": record.occurred_at,
                                    "severity": record.severity,
                                    "confidence": record.confidence,
                                    "completeness": record.completeness,
                                    "taskNodeId": record.task_node_id,
                                    "evidenceRefs": record.evidence_refs,
                                    "flags": record.flags,
                                }
                                for record in result.records
                            ],
                        },
                    )
                )
            else:
                warnings.append("audit records query did not return data")
        finally:
            if message_stream is not None:
                message_stream.close()
        return tuple(files), tuple(warnings)

    def _collect_events(
        self,
        writer: _BundleWriter,
        session: Session,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        db_path = self.layout.session_events_db(session.id)
        if not db_path.exists():
            return (), ("event stream store is not present",)
        rows, total = _read_event_rows(db_path, self.options.max_events)
        warnings: list[str] = []
        if total > len(rows):
            warnings.append(f"event stream truncated from {total} to {len(rows)} records")
        rel_path = writer.write_jsonl(
            "events/events.summary.jsonl",
            kind="event_stream_summary",
            source="EventStream",
            rows=rows,
        )
        return (rel_path,), tuple(warnings)

    def _collect_ui_events(
        self,
        writer: _BundleWriter,
        session: Session,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        db_path = self.layout.workspace_ui_events_db
        if not db_path.exists():
            return (), ("UI event replay store is not present",)
        rows, total = _read_ui_event_rows(db_path, session.id, self.options.max_ui_events)
        warnings: list[str] = []
        if total > len(rows):
            warnings.append(f"UI event stream truncated from {total} to {len(rows)} records")
        rel_path = writer.write_jsonl(
            "events/ui-events.summary.jsonl",
            kind="ui_event_stream_summary",
            source="UiEventSource",
            rows=rows,
        )
        return (rel_path,), tuple(warnings)

    def _collect_logs(
        self,
        writer: _BundleWriter,
        session: Session,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        manifest = _read_log_manifest(session)
        if manifest is None:
            return (), ("session log manifest is not present",)
        files: list[str] = [
            writer.write_json(
                "logs/manifest.json",
                kind="log_archive_manifest",
                source="LogArchiveManifest",
                payload=_manifest_payload(manifest),
            )
        ]
        warnings: list[str] = []
        for category, relative_path in sorted(manifest.files.items()):
            source_path = session.logs_dir / relative_path
            if not source_path.exists():
                warnings.append(f"log category {category!r} file is missing")
                continue
            entries, total = _read_log_summary_rows(
                source_path,
                self.options.max_log_entries_per_category,
            )
            if total > len(entries):
                warnings.append(
                    f"log category {category!r} truncated from {total} to {len(entries)} records"
                )
            if not entries:
                continue
            files.append(
                writer.write_jsonl(
                    f"logs/{_safe_token(category)}.summary.jsonl",
                    kind="log_category_summary",
                    source=f"LogArchive:{category}",
                    rows=entries,
                )
            )
        return tuple(files), tuple(warnings)

    def _collect_config(
        self,
        writer: _BundleWriter,
        session: Session,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        manifest = _read_log_manifest(session)
        if manifest is None:
            return (), ("effective config summary is unavailable because log manifest is missing",)
        rel_path = writer.write_json(
            "config/effective-summary.json",
            kind="effective_config_summary",
            source="LogArchiveManifest",
            payload={
                "profileLabel": "Session log manifest",
                "summary": f"Logging config hash {manifest.config_hash} is active.",
                "effectiveAt": manifest.created_at,
                "configHash": manifest.config_hash,
                "activeConfigPath": manifest.active_config_path,
                "archiveRoot": "session-logs://",
                "fileCount": len(manifest.files),
                "rotation": manifest.rotation,
            },
        )
        return (rel_path,), ()

    def _collect_frontend_errors(
        self,
        writer: _BundleWriter,
        session: Session,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        source_path = session.logs_dir / FRONTEND_ERROR_LOG_FILENAME
        if not source_path.exists():
            return (), ("frontend client error log is not present",)
        rows, total = _read_frontend_error_rows(
            source_path,
            self.options.max_log_entries_per_category,
        )
        warnings: list[str] = []
        if total > len(rows):
            warnings.append(
                f"frontend error log truncated from {total} to {len(rows)} records"
            )
        rel_path = writer.write_jsonl(
            "frontend/client-errors.summary.jsonl",
            kind="frontend_client_errors_summary",
            source="ClientErrorLogSink",
            rows=rows,
        )
        return (rel_path,), tuple(warnings)

    def _collect_environment(
        self,
        writer: _BundleWriter,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        rel_path = writer.write_json(
            "environment/runtime.json",
            kind="runtime_environment_summary",
            source="DiagnosticBundleExporter",
            payload={
                "taskweavnVersion": __version__,
                "pythonVersion": platform.python_version(),
                "pythonImplementation": platform.python_implementation(),
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
        )
        return (rel_path,), ()


class _BundleWriter:
    def __init__(self, *, bundle_dir: Path, workspace_root: Path) -> None:
        self.bundle_dir = bundle_dir
        self.workspace_root = workspace_root
        self.files: list[DiagnosticBundleFileEntry] = []
        self.sections: list[DiagnosticBundleSection] = []

    def write_json(
        self,
        relative_path: str,
        *,
        kind: str,
        source: str,
        payload: Any,
    ) -> str:
        path = self.bundle_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = redact_diagnostic_payload(payload, workspace_root=self.workspace_root)
        path.write_text(_json_dumps(data), encoding="utf-8")
        self.files.append(
            DiagnosticBundleFileEntry(
                path=relative_path,
                kind=kind,
                redacted=True,
                source=source,
            )
        )
        return relative_path

    def write_jsonl(
        self,
        relative_path: str,
        *,
        kind: str,
        source: str,
        rows: Iterable[Any],
    ) -> str:
        path = self.bundle_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            for row in rows:
                data = redact_diagnostic_payload(row, workspace_root=self.workspace_root)
                file.write(json.dumps(data, ensure_ascii=False, sort_keys=True, default=str))
                file.write("\n")
        self.files.append(
            DiagnosticBundleFileEntry(
                path=relative_path,
                kind=kind,
                redacted=True,
                source=source,
            )
        )
        return relative_path

    def add_section(
        self,
        name: str,
        status: SchemaSectionStatus,
        files: Sequence[str],
        warnings: Sequence[str],
    ) -> None:
        self.sections.append(
            DiagnosticBundleSection(
                name=name,
                status=status,
                files=tuple(sorted(files)),
                warnings=tuple(
                    str(
                        normalize_workspace_path(
                            warning,
                            workspace_root=self.workspace_root,
                        )
                    )
                    for warning in warnings
                ),
            )
        )

    def write_manifest(
        self,
        *,
        bundle_id: str,
        created_at: datetime,
        session_id: str,
        task_ids: tuple[str, ...],
    ) -> DiagnosticBundleManifest:
        manifest_entry = DiagnosticBundleFileEntry(
            path="manifest.json",
            kind="diagnostic_bundle_manifest",
            redacted=True,
            source="DiagnosticBundleExporter",
        )
        sections = tuple(sorted(self.sections, key=lambda section: _section_key(section.name)))
        included_sections = tuple(
            section.name
            for section in sections
            if section.status in {"included", "partial"}
        )
        warnings = tuple(
            warning
            for section in sections
            for warning in section.warnings
        )
        files = tuple(
            sorted(
                (manifest_entry, *self.files),
                key=lambda file_entry: file_entry.path,
            )
        )
        manifest = DiagnosticBundleManifest(
            bundleId=bundle_id,
            createdAt=created_at,
            sessionId=session_id,
            taskIds=tuple(sorted(task_ids)),
            includedSections=included_sections,
            sections=sections,
            warnings=warnings,
            files=files,
        )
        (self.bundle_dir / "manifest.json").write_text(
            _json_dumps(manifest.model_dump(mode="json", by_alias=True)),
            encoding="utf-8",
        )
        return manifest


@dataclass(frozen=True)
class _StaticTaskStore:
    tasks: tuple[TaskDomain, ...]

    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        for task in self.tasks:
            if task.session_id == session_id and task.task_id == task_id:
                return task
        return None

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        return sorted(
            (task for task in self.tasks if task.session_id == session_id),
            key=lambda task: (task.created_at, task.order_index, task.task_id),
        )

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        return sorted(
            (
                task
                for task in self.tasks
                if task.session_id == session_id and task.parent_id == parent_id
            ),
            key=lambda task: (task.order_index, task.created_at, task.task_id),
        )


@dataclass(frozen=True)
class _StaticTaskSummaryStore:
    summaries: tuple[TaskExecutionSummary, ...]

    def get(self, session_id: str, task_id: str) -> TaskSummaryView | None:
        matches = [
            summary
            for summary in self.summaries
            if summary.session_id == session_id and summary.task_id == task_id
        ]
        if not matches:
            return None
        matches.sort(key=lambda summary: (summary.updated_at, summary.summary_id))
        return task_execution_summary_to_task_summary_view(matches[-1])


def redact_diagnostic_payload(
    value: Any,
    *,
    workspace_root: Path,
    max_string_length: int = 512,
) -> Any:
    """Apply Product 1.0 default diagnostic redaction."""
    json_ready = _json_ready(redact_payload(value))
    return _sanitize_value(
        json_ready,
        workspace_root=workspace_root,
        max_string_length=max_string_length,
    )


def normalize_workspace_path(value: str, *, workspace_root: Path) -> str:
    """Map local absolute paths to bundle-safe labels."""
    root = workspace_root.expanduser().resolve()
    text = str(value)
    root_text = str(root)
    if text == root_text:
        return "workspace://current"
    if root_text in text:
        return text.replace(root_text, "workspace://current")
    if _looks_like_absolute_path(text):
        return _ABSOLUTE_PATH_VALUE
    return text


def _build_audit_gateway(
    *,
    session_manager: SessionManager,
    layout: WorkspaceLayout,
    tasks: Sequence[TaskDomain],
    summaries: Sequence[TaskExecutionSummary],
    message_stream: SqliteMessageStream | None,
) -> DefaultUiQueryGateway:
    return DefaultUiQueryGateway(
        session_reader=session_manager,
        task_projection=DefaultTaskProjectionService(
            task_store=_StaticTaskStore(tuple(tasks)),
            message_stream=message_stream,
            summary_store=_StaticTaskSummaryStore(tuple(summaries)),
        ),
        audit_event_provider=WorkspaceAuditEventProvider(layout),
        audit_config_provider=WorkspaceAuditConfigProvider(),
        audit_log_provider=WorkspaceAuditLogProvider(),
        session_message_provider=message_stream,
    )


def _safe_read_tasks(
    db_path: Path,
    session_id: str,
) -> tuple[tuple[TaskDomain, ...], tuple[str, ...]]:
    try:
        return _read_tasks(db_path, session_id), ()
    except Exception as exc:  # noqa: BLE001 - source failure is reported in manifest.
        return (), (f"{type(exc).__name__}: task store could not be read",)


def _safe_read_result_summaries(
    db_path: Path,
    session_id: str,
) -> tuple[tuple[TaskExecutionSummary, ...], tuple[str, ...]]:
    try:
        return _read_result_summaries(db_path, session_id), ()
    except Exception as exc:  # noqa: BLE001 - source failure is reported in manifest.
        return (), (f"{type(exc).__name__}: result summary store could not be read",)


def _read_tasks(db_path: Path, session_id: str) -> tuple[TaskDomain, ...]:
    if not db_path.exists():
        return ()
    rows = _select_rows(
        db_path,
        """
        SELECT payload FROM tasks
        WHERE session_id = ?
        ORDER BY created_at ASC, order_index ASC, task_id ASC
        """,
        (session_id,),
    )
    tasks: list[TaskDomain] = []
    for row in rows:
        tasks.append(TaskDomain.model_validate_json(str(row["payload"])))
    return tuple(tasks)


def _read_result_summaries(db_path: Path, session_id: str) -> tuple[TaskExecutionSummary, ...]:
    if not db_path.exists():
        return ()
    rows = _select_rows(
        db_path,
        """
        SELECT payload FROM task_execution_summaries
        WHERE session_id = ?
        ORDER BY updated_at ASC, id ASC
        """,
        (session_id,),
    )
    summaries: list[TaskExecutionSummary] = []
    for row in rows:
        summaries.append(TaskExecutionSummary.model_validate_json(str(row["payload"])))
    return tuple(summaries)


def _read_event_rows(db_path: Path, limit: int) -> tuple[tuple[dict[str, Any], ...], int]:
    total = _row_count(db_path, "events")
    rows = _select_limited_rows(
        db_path,
        """
        SELECT event_id, kind, family, timestamp, task_id, payload
        FROM events
        ORDER BY id ASC
        """,
        limit,
    )
    result = []
    for row in rows:
        result.append(
            {
                "eventId": row["event_id"],
                "kind": row["kind"],
                "family": row["family"],
                "timestamp": row["timestamp"],
                "taskId": row["task_id"],
                "payloadSummary": _parse_json_object(row["payload"]),
            }
        )
    return tuple(result), total


def _read_ui_event_rows(
    db_path: Path,
    session_id: str,
    limit: int,
) -> tuple[tuple[dict[str, Any], ...], int]:
    total = _scalar_count(
        db_path,
        "SELECT COUNT(*) AS count FROM ui_events WHERE session_id = ?",
        (session_id,),
    )
    rows = _select_limited_rows(
        db_path,
        """
        SELECT event_id, event_type, cursor, created_at, payload_json
        FROM ui_events
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        limit,
        (session_id,),
    )
    result = []
    for row in rows:
        result.append(
            {
                "eventId": row["event_id"],
                "eventType": row["event_type"],
                "cursor": row["cursor"],
                "createdAt": row["created_at"],
                "payloadSummary": _parse_json_object(row["payload_json"]),
            }
        )
    return tuple(result), total


def _read_log_summary_rows(path: Path, limit: int) -> tuple[tuple[dict[str, Any], ...], int]:
    lines = _read_non_empty_lines(path)
    selected = _tail(lines, limit)
    rows: list[dict[str, Any]] = []
    for line in selected:
        item = _parse_json_object(line)
        rows.append(
            {
                "ts": item.get("ts"),
                "level": item.get("level"),
                "category": item.get("category"),
                "event": item.get("event") or item.get("msg"),
                "messagePreview": _preview(str(item.get("message") or ""), 240),
                "context": item.get("context", {}),
                "dataSummary": item.get("data", {}),
            }
        )
    return tuple(rows), len(lines)


def _read_frontend_error_rows(path: Path, limit: int) -> tuple[tuple[dict[str, Any], ...], int]:
    lines = _read_non_empty_lines(path)
    selected = _tail(lines, limit)
    rows: list[dict[str, Any]] = []
    for line in selected:
        item = _parse_json_object(line)
        raw_payload = item.get("payload")
        payload: Mapping[str, Any] = (
            raw_payload if isinstance(raw_payload, Mapping) else {}
        )
        rows.append(
            {
                "receivedAt": item.get("receivedAt"),
                "sessionId": item.get("sessionId"),
                "name": payload.get("name"),
                "messagePreview": _preview(str(payload.get("message") or ""), 240),
                "route": payload.get("route"),
                "component": payload.get("component"),
                "metadata": {
                    key: value
                    for key, value in payload.items()
                    if key not in {"message", "name", "stack", "stackTrace"}
                },
            }
        )
    return tuple(rows), len(lines)


def _select_rows(
    db_path: Path,
    sql: str,
    params: Sequence[Any] = (),
) -> tuple[sqlite3.Row, ...]:
    with _connect_readonly(db_path) as conn:
        return tuple(conn.execute(sql, tuple(params)))


def _select_limited_rows(
    db_path: Path,
    sql: str,
    limit: int,
    params: Sequence[Any] = (),
) -> tuple[sqlite3.Row, ...]:
    if limit == 0:
        return ()
    with _connect_readonly(db_path) as conn:
        rows = tuple(conn.execute(sql, tuple(params)))
    return tuple(_tail(rows, limit))


def _row_count(db_path: Path, table_name: str) -> int:
    return _scalar_count(db_path, f"SELECT COUNT(*) AS count FROM {table_name}")


def _scalar_count(
    db_path: Path,
    sql: str,
    params: Sequence[Any] = (),
) -> int:
    with _connect_readonly(db_path) as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
    if row is None:
        return 0
    return int(row["count"])


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_log_manifest(session: Session) -> LogArchiveManifest | None:
    path = session.logs_dir / "manifest.json"
    if not path.exists():
        return None
    try:
        return LogArchiveManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _manifest_payload(manifest: LogArchiveManifest) -> dict[str, Any]:
    payload = manifest.model_dump(mode="json", exclude_none=True)
    payload["archive_root"] = "session-logs://"
    return payload


def _summary_payload(summary: TaskExecutionSummary) -> dict[str, Any]:
    return {
        "summaryId": summary.summary_id,
        "sessionId": summary.session_id,
        "taskId": summary.task_id,
        "kind": summary.kind,
        "source": summary.source,
        "title": summary.title,
        "summary": _preview(summary.summary, 500),
        "stopReason": summary.stop_reason,
        "finalAnswerPreview": (
            None if summary.final_answer is None else _preview(summary.final_answer, 500)
        ),
        "errorType": summary.error_type,
        "errorMessage": summary.error_message,
        "metadata": summary.metadata,
        "createdAt": summary.created_at,
        "updatedAt": summary.updated_at,
    }


def _message_payload(message: AgentMessage) -> dict[str, Any]:
    return {
        "messageId": message.message_id,
        "sessionId": message.session_id,
        "taskId": message.task_id,
        "agentId": message.agent_id,
        "parentMessageId": message.parent_message_id,
        "messageType": message.message_type,
        "contentPreview": _preview(message.content, 240),
        "requiresResponse": message.requires_response,
        "actionOptions": message.action_options,
        "relatedActionId": message.related_action_id,
        "responseSource": message.response_source,
        "responseValuePreview": (
            None if message.response_value is None else _preview(message.response_value, 160)
        ),
        "createdAt": message.created_at,
        "contextSummary": message.context,
    }


def _product_error_from_task(
    task: TaskDomain,
    summary_by_id: Mapping[str, TaskExecutionSummary],
) -> dict[str, Any] | None:
    summary = None
    if task.error_ref is not None:
        summary = summary_by_id.get(task.error_ref)
    if summary is None:
        return None
    details = _product_error_details_from_summary(summary)
    if details is None:
        return None
    return _with_audit_diagnostic_refs(details, task)


def _product_error_details_from_summary(
    summary: TaskExecutionSummary,
) -> dict[str, Any] | None:
    details = summary.metadata.get("productError")
    if isinstance(details, Mapping):
        return dict(details)
    flat_details = {
        key: summary.metadata[key]
        for key in (
            "productCategory",
            "recoveryActions",
            "severity",
            "userMessageKey",
            "diagnosticRefs",
            "auditRef",
            "llmClassification",
            "retryCount",
            "errorType",
        )
        if key in summary.metadata
    }
    if flat_details:
        return flat_details
    category = summary.metadata.get("errorCategory")
    action = summary.metadata.get("recoveryAction")
    if category is None and action is None:
        return None
    return {
        "category": category,
        "recoveryAction": action,
        "retryEligible": summary.metadata.get("retryEligible"),
        "diagnosticRefs": summary.metadata.get("diagnosticRefs"),
    }


def _with_audit_diagnostic_refs(
    details: dict[str, Any],
    task: TaskDomain,
) -> dict[str, Any]:
    result = dict(details)
    audit_ref = result.get("auditRef")
    if not isinstance(audit_ref, Mapping):
        audit_ref = product_error_audit_ref_for_task(
            session_id=task.session_id,
            task_id=task.task_id,
        )
    else:
        audit_ref = dict(audit_ref)
    result["auditRef"] = audit_ref

    diagnostic_refs = result.get("diagnosticRefs")
    refs = dict(diagnostic_refs) if isinstance(diagnostic_refs, Mapping) else {}
    refs.setdefault("errorRef", task.error_ref)
    refs.setdefault("taskId", task.task_id)
    refs.setdefault("sessionId", task.session_id)
    if isinstance(audit_ref.get("recordId"), str):
        refs.setdefault("auditRecordId", audit_ref["recordId"])
    if isinstance(audit_ref.get("evidenceId"), str):
        refs.setdefault("auditEvidenceId", audit_ref["evidenceId"])
    result["diagnosticRefs"] = refs
    return result


def _sanitize_value(
    value: Any,
    *,
    workspace_root: Path,
    max_string_length: int,
    key: str | None = None,
) -> Any:
    if key is not None and _should_omit_key(key):
        return _OMITTED_VALUE
    if isinstance(value, Mapping):
        return {
            str(item_key): _sanitize_value(
                item_value,
                workspace_root=workspace_root,
                max_string_length=max_string_length,
                key=str(item_key),
            )
            for item_key, item_value in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _sanitize_value(
                item,
                workspace_root=workspace_root,
                max_string_length=max_string_length,
            )
            for item in value
        ]
    if isinstance(value, str):
        normalized = normalize_workspace_path(value, workspace_root=workspace_root)
        normalized = _redact_secret_fragments(normalized)
        if len(normalized) > max_string_length:
            return f"{normalized[: max_string_length - 3]}..."
        return normalized
    return value


def _should_omit_key(key: str) -> bool:
    normalized = _KEY_NORMALIZE_RE.sub("", key.lower())
    return normalized in _OMIT_EXACT_KEYS or any(
        marker in normalized for marker in _OMIT_KEY_MARKERS
    )


def _redact_secret_fragments(value: str) -> str:
    return _SECRET_FRAGMENT_RE.sub(r"\1\2<redacted>", value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"parseStatus": "invalid_json", "textPreview": _preview(value, 240)}
    return parsed if isinstance(parsed, dict) else {"valuePreview": _preview(str(parsed), 240)}


def _read_non_empty_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tail[T](items: Sequence[T], limit: int) -> list[T]:
    if limit == 0:
        return []
    if limit < 0 or len(items) <= limit:
        return list(items)
    return list(items[-limit:])


def _preview(value: str, length: int) -> str:
    normalized = " ".join(str(value).split())
    if len(normalized) <= length:
        return normalized
    return f"{normalized[: max(0, length - 3)]}..."


def _bundle_id(session_id: str, created_at: datetime) -> str:
    timestamp = created_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"diagnostic-bundle-{_safe_token(session_id)}-{timestamp}"


def _safe_token(value: str) -> str:
    return _SAFE_ID_RE.sub("-", value).strip("-") or "item"


def _section_key(name: str) -> tuple[int, str]:
    try:
        return (_SECTION_ORDER.index(name), name)
    except ValueError:
        return (len(_SECTION_ORDER), name)


def _looks_like_absolute_path(value: str) -> bool:
    if not value.startswith("/"):
        return False
    return " " not in value and "\n" not in value and "\t" not in value


__all__ = [
    "DIAGNOSTIC_BUNDLE_SCHEMA_VERSION",
    "DIAGNOSTIC_REDACTION_PROFILE",
    "DiagnosticBundleError",
    "DiagnosticBundleExporter",
    "DiagnosticBundleFileEntry",
    "DiagnosticBundleManifest",
    "DiagnosticBundleSection",
    "DiagnosticExportOptions",
    "DiagnosticExportResult",
    "normalize_workspace_path",
    "redact_diagnostic_payload",
]
