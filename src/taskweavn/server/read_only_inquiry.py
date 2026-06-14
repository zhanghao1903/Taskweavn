"""Read-only inquiry service for answer-only runtime input."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from taskweavn.server.read_only_inquiry_answer_provider import (
    ReadOnlyInquiryAnswerProvider,
)
from taskweavn.server.read_only_inquiry_diagnostics import (
    DiagnosticSupportContextProvider,
)
from taskweavn.server.read_only_inquiry_links import activity_ref_from_evidence
from taskweavn.server.ui_contract.envelopes import QueryResponse
from taskweavn.server.ui_contract.gateway_protocols import UiQueryGateway
from taskweavn.server.ui_contract.read_only_inquiry import (
    ReadOnlyInquiryAnswer,
    ReadOnlyInquiryEvidenceKind,
    ReadOnlyInquiryEvidenceRef,
    ReadOnlyInquiryRef,
    ReadOnlyInquiryRequest,
    ReadOnlyInquiryResult,
    ReadOnlyInquiryStatus,
    ReadOnlyInquiryWarning,
)
from taskweavn.server.ui_contract.snapshots import MainPageSnapshot
from taskweavn.server.ui_contract.view_models import (
    FileChangeSummaryView,
    PlanningDiagnosticView,
    PlanView,
    ResultCardView,
    SessionActivityItemView,
    TaskNodeCardView,
)


class ReadOnlyInquiryService(Protocol):
    def answer(
        self,
        request: ReadOnlyInquiryRequest,
    ) -> QueryResponse[ReadOnlyInquiryResult]: ...


class WorkspaceInspectionContextProvider(Protocol):
    def file_content(
        self,
        *,
        path: str | None,
        start_line: int = 1,
        line_count: int | None = None,
        evidence_id: str | None = None,
    ) -> dict[str, Any]: ...

    def diff(
        self,
        *,
        path: str,
        base: str = "head",
        context_lines: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DefaultReadOnlyInquiryService:
    """Bounded no-mutation inquiry implementation over existing UI projections."""

    query_gateway: UiQueryGateway
    workspace_inspection_gateway: WorkspaceInspectionContextProvider | None = None
    diagnostic_support_provider: DiagnosticSupportContextProvider | None = None
    answer_provider: ReadOnlyInquiryAnswerProvider | None = None

    def answer(
        self,
        request: ReadOnlyInquiryRequest,
    ) -> QueryResponse[ReadOnlyInquiryResult]:
        snapshot_response = self.query_gateway.get_session_snapshot(
            request.session_id,
            request_id=request.inquiry_id,
        )
        if not snapshot_response.ok or snapshot_response.data is None:
            return _result_response(
                request,
                status="unsupported",
                warning=ReadOnlyInquiryWarning(
                    code="inquiry.context_empty",
                    message="Session context is not available for read-only inquiry.",
                ),
            )

        return _answer_from_snapshot(
            request,
            snapshot_response.data,
            self.query_gateway,
            self.workspace_inspection_gateway,
            self.diagnostic_support_provider,
            self.answer_provider,
        )


def _answer_from_snapshot(
    request: ReadOnlyInquiryRequest,
    snapshot: MainPageSnapshot,
    query_gateway: UiQueryGateway,
    workspace_inspection_gateway: WorkspaceInspectionContextProvider | None,
    diagnostic_support_provider: DiagnosticSupportContextProvider | None,
    answer_provider: ReadOnlyInquiryAnswerProvider | None,
) -> QueryResponse[ReadOnlyInquiryResult]:
    if request.scope.kind == "task":
        task = _find_task(snapshot, request.scope.task_node_id)
        if task is None:
            return _result_response(
                request,
                status="needs_clarification",
                warning=ReadOnlyInquiryWarning(
                    code="inquiry.context_empty",
                    message="The selected task is not available in the current session.",
                ),
            )
        answer, evidence = _task_answer(snapshot, task)
    elif request.scope.kind == "plan":
        plan = _find_plan(snapshot, request.scope.plan_id)
        if plan is None:
            return _result_response(
                request,
                status="needs_clarification",
                warning=ReadOnlyInquiryWarning(
                    code="inquiry.context_empty",
                    message="The selected plan is not available in the current session.",
                ),
            )
        answer, evidence = _plan_answer(snapshot, plan)
    else:
        answer, evidence = _session_answer(snapshot)

    answer, evidence, warnings = _append_ref_summaries(
        request,
        answer,
        evidence,
        snapshot,
        query_gateway,
        workspace_inspection_gateway,
        diagnostic_support_provider,
    )
    status: ReadOnlyInquiryStatus = "answered"
    if answer_provider is not None:
        provider_result = answer_provider.answer(
            request=request,
            baseline_answer=answer,
            evidence_refs=evidence,
            warnings=warnings,
        )
        status = provider_result.status
        answer = provider_result.answer
        evidence = provider_result.evidence_refs
        warnings = provider_result.warnings
    activity = _activity(request, answer, evidence) if answer is not None else None
    return _result_response(
        request,
        status=status,
        answer=answer,
        evidence_refs=evidence,
        warnings=warnings,
        activity=activity,
    )


def _session_answer(
    snapshot: MainPageSnapshot,
) -> tuple[ReadOnlyInquiryAnswer, tuple[ReadOnlyInquiryEvidenceRef, ...]]:
    session = snapshot.session
    body_parts = [f"Session '{session.name}' is {session.status}."]
    evidence = [
        _evidence(
            "session_status",
            f"session:{session.id}:status",
            f"Session {session.name}",
        )
    ]
    if snapshot.active_plan is not None:
        plan = snapshot.active_plan
        body_parts.append(
            f"Active plan '{plan.title}' is {plan.status} with {plan.task_count} tasks."
        )
        evidence.append(_plan_evidence(plan))
    _append_result_and_file_summary(body_parts, evidence, snapshot)
    return (
        ReadOnlyInquiryAnswer(
            title="Session status",
            body=" ".join(body_parts),
            confidence="medium",
        ),
        tuple(evidence),
    )


def _plan_answer(
    snapshot: MainPageSnapshot,
    plan: PlanView,
) -> tuple[ReadOnlyInquiryAnswer, tuple[ReadOnlyInquiryEvidenceRef, ...]]:
    rollup = plan.execution_rollup
    body_parts = [
        (
            f"Plan '{plan.title}' is {plan.status} with {plan.task_count} tasks. "
            f"Execution rollup: {rollup.done} done, {rollup.running} running, "
            f"{rollup.failed} failed, {rollup.pending} pending."
        )
    ]
    evidence = [_plan_evidence(plan)]
    if plan.outcome is not None:
        body_parts.append(f"Outcome: {plan.outcome.summary}")
        evidence.append(
            _evidence(
                "plan_status",
                f"plan:{plan.id}:outcome",
                f"Plan outcome: {plan.title}",
            )
        )
    _append_result_and_file_summary(body_parts, evidence, snapshot)
    return (
        ReadOnlyInquiryAnswer(
            title="Plan status",
            body=" ".join(body_parts),
            confidence="high",
        ),
        tuple(evidence),
    )


def _task_answer(
    snapshot: MainPageSnapshot,
    task: TaskNodeCardView,
) -> tuple[ReadOnlyInquiryAnswer, tuple[ReadOnlyInquiryEvidenceRef, ...]]:
    body_parts = [
        (
            f"Task {task.display_index} '{task.title}' is {task.status}; "
            f"execution is {task.execution}. {task.summary}"
        )
    ]
    if task.result_ref is not None:
        body_parts.append(f"Result ref: {task.result_ref}.")
    if task.error_ref is not None:
        body_parts.append(f"Error ref: {task.error_ref}.")
    evidence = [
        _evidence(
            "task_status",
            f"task:{task.id}:status",
            f"Task {task.display_index}: {task.title}",
        )
    ]
    _append_result_and_file_summary(body_parts, evidence, snapshot, task_node_id=task.id)
    return (
        ReadOnlyInquiryAnswer(
            title=f"Task {task.display_index} status",
            body=" ".join(body_parts),
            confidence="high",
        ),
        tuple(evidence),
    )


def _append_result_and_file_summary(
    body_parts: list[str],
    evidence: list[ReadOnlyInquiryEvidenceRef],
    snapshot: MainPageSnapshot,
    *,
    task_node_id: str | None = None,
) -> None:
    result = snapshot.result
    if result is not None and _matches_task_scope(result, task_node_id):
        body_parts.append(f"Result: {result.summary}")
        evidence.append(
            _evidence("result_summary", result.id, f"Result: {result.title}")
        )
    summary = snapshot.file_change_summary
    if summary is not None and _matches_task_scope(summary, task_node_id):
        body_parts.append(f"Files: {summary.summary}")
        evidence.append(
            _evidence(
                "file_change_summary",
                f"file-summary:{summary.session_id}:{summary.task_node_id or 'session'}",
                "File change summary",
            )
        )


def _append_ref_summaries(
    request: ReadOnlyInquiryRequest,
    answer: ReadOnlyInquiryAnswer,
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...],
    snapshot: MainPageSnapshot,
    query_gateway: UiQueryGateway,
    workspace_inspection_gateway: WorkspaceInspectionContextProvider | None,
    diagnostic_support_provider: DiagnosticSupportContextProvider | None,
) -> tuple[
    ReadOnlyInquiryAnswer,
    tuple[ReadOnlyInquiryEvidenceRef, ...],
    tuple[ReadOnlyInquiryWarning, ...],
]:
    if not request.refs:
        return answer, evidence_refs, ()

    body_parts = [answer.body]
    evidence = list(evidence_refs)
    warnings: list[ReadOnlyInquiryWarning] = []
    for ref in request.refs:
        if ref.kind == "audit_record":
            if ref.id is None:
                warnings.append(_partial_warning("Audit record ref has no id.", ref))
                continue
            audit_response = query_gateway.get_audit_record_detail(
                request.session_id,
                ref.id,
                include_evidence=False,
                include_sanitized_payload=False,
                request_id=request.inquiry_id,
            )
            if not audit_response.ok or audit_response.data is None:
                warnings.append(_partial_warning("Audit record is not available.", ref))
                continue
            record = audit_response.data
            verdict = record.verdict or "not_available"
            body_parts.append(
                f"Audit record '{record.title}' has verdict {verdict}: {record.summary}"
            )
            evidence.append(
                ReadOnlyInquiryEvidenceRef(
                    kind="audit_record",
                    ref_id=record.id,
                    label=record.title,
                    disclosure="partial" if record.flags.partial else "public",
                    truncated=False,
                )
            )
        elif ref.kind == "audit_evidence":
            evidence_id = ref.evidence_id or ref.id
            if evidence_id is None:
                warnings.append(_partial_warning("Audit evidence ref has no id.", ref))
                continue
            evidence_response = query_gateway.get_evidence_detail(
                request.session_id,
                evidence_id,
                include_sanitized_payload=False,
                request_id=request.inquiry_id,
            )
            if not evidence_response.ok or evidence_response.data is None:
                warnings.append(_partial_warning("Audit evidence is not available.", ref))
                continue
            detail = evidence_response.data
            parent_record_id = _audit_record_id_for_evidence(
                query_gateway,
                request.session_id,
                detail.id,
                request_id=request.inquiry_id,
            )
            body_parts.append(
                f"Audit evidence '{detail.label}' from {detail.source}: {detail.summary}"
            )
            evidence.append(
                ReadOnlyInquiryEvidenceRef(
                    kind="audit_evidence",
                    ref_id=detail.id,
                    parent_ref_id=parent_record_id,
                    label=detail.label,
                    disclosure="hidden" if detail.hidden else "partial",
                    truncated=False,
                )
            )
        elif ref.kind == "activity":
            activity_response = query_gateway.list_session_activity(
                request.session_id,
                limit=request.limits.max_evidence_items or 12,
                request_id=request.inquiry_id,
            )
            if not activity_response.ok or activity_response.data is None:
                warnings.append(_partial_warning("Activity context is not available.", ref))
                continue
            activity = _find_activity(activity_response.data.items, ref.id)
            if activity is None:
                warnings.append(_partial_warning("Activity item is not available.", ref))
                continue
            body_parts.append(f"Activity '{activity.title}': {activity.body}")
            evidence.append(
                ReadOnlyInquiryEvidenceRef(
                    kind="activity_item",
                    ref_id=activity.id,
                    label=activity.title,
                    disclosure=activity.disclosure_level,
                    truncated=False,
                )
            )
        elif ref.kind == "result":
            summary = _result_ref_summary(ref, snapshot)
            if summary.warning is not None:
                warnings.append(summary.warning)
                continue
            body_parts.append(summary.body)
            evidence.append(summary.evidence)
        elif ref.kind == "file":
            summary = _file_ref_summary(ref, workspace_inspection_gateway)
            if summary.warning is not None:
                warnings.append(summary.warning)
                continue
            body_parts.append(summary.body)
            evidence.append(summary.evidence)
        elif ref.kind == "diff":
            summary = _diff_ref_summary(ref, workspace_inspection_gateway)
            if summary.warning is not None:
                warnings.append(summary.warning)
                continue
            body_parts.append(summary.body)
            evidence.append(summary.evidence)
        elif ref.kind == "diagnostic":
            summary = _diagnostic_ref_summary(
                ref,
                request,
                snapshot,
                diagnostic_support_provider,
            )
            if summary.warning is not None:
                warnings.append(summary.warning)
                continue
            body_parts.append(summary.body)
            evidence.append(summary.evidence)

    confidence = answer.confidence if not warnings else "medium" if evidence else "low"
    return (
        ReadOnlyInquiryAnswer(
            title=answer.title,
            body=" ".join(body_parts),
            confidence=confidence,
        ),
        tuple(evidence),
        tuple(warnings),
    )


def _find_activity(
    items: tuple[SessionActivityItemView, ...],
    item_id: str | None,
) -> SessionActivityItemView | None:
    if item_id is None:
        return items[0] if items else None
    for item in items:
        if item.id == item_id:
            return item
    return None


def _diagnostic_ref_summary(
    ref: ReadOnlyInquiryRef,
    request: ReadOnlyInquiryRequest,
    snapshot: MainPageSnapshot,
    diagnostic_support_provider: DiagnosticSupportContextProvider | None,
) -> _RefSummary:
    diagnostics = (
        snapshot.planning.diagnostics if snapshot.planning is not None else ()
    )
    diagnostic = _find_diagnostic(diagnostics, ref.id)
    if diagnostic is None:
        support_descriptor = (
            None
            if diagnostic_support_provider is None
            else diagnostic_support_provider.describe(
                session_id=request.session_id,
                workspace_id=request.workspace_id,
                diagnostic_id=ref.id,
            )
        )
        if support_descriptor is not None:
            return _RefSummary(
                body=(
                    f"Diagnostic support '{support_descriptor.label}': "
                    f"{support_descriptor.summary}"
                ),
                evidence=ReadOnlyInquiryEvidenceRef(
                    kind="diagnostic_summary",
                    ref_id=support_descriptor.ref_id,
                    label=support_descriptor.label,
                    disclosure=support_descriptor.disclosure,
                    truncated=support_descriptor.truncated,
                ),
            )
        return _warning_summary(
            "Diagnostic descriptor is not available in the current session context.",
            ref,
        )
    body = (
        f"Diagnostic '{diagnostic.code}' is {diagnostic.severity}: "
        f"{diagnostic.message}"
    )
    return _RefSummary(
        body=body,
        evidence=ReadOnlyInquiryEvidenceRef(
            kind="diagnostic_summary",
            ref_id=f"diagnostic:{diagnostic.code}",
            label=diagnostic.code.replace("_", " "),
            disclosure="partial",
            truncated=False,
        ),
    )


def _find_diagnostic(
    diagnostics: tuple[PlanningDiagnosticView, ...],
    diagnostic_id: str | None,
) -> PlanningDiagnosticView | None:
    if diagnostic_id is None:
        return diagnostics[0] if diagnostics else None
    normalized_id = diagnostic_id.removeprefix("diagnostic:")
    for diagnostic in diagnostics:
        if diagnostic.code == normalized_id:
            return diagnostic
    return None


def _audit_record_id_for_evidence(
    query_gateway: UiQueryGateway,
    session_id: str,
    evidence_id: str,
    *,
    request_id: str,
) -> str | None:
    records_response = query_gateway.list_audit_records(
        session_id,
        limit=50,
        request_id=request_id,
    )
    if not records_response.ok or records_response.data is None:
        return None
    for record in records_response.data.records:
        if any(evidence.id == evidence_id for evidence in record.evidence_refs):
            return record.id
    return None


def _result_ref_summary(
    ref: ReadOnlyInquiryRef,
    snapshot: MainPageSnapshot,
) -> _RefSummary:
    result = snapshot.result
    if result is None:
        return _warning_summary("Result summary is not available.", ref)
    if ref.id is not None and ref.id not in {result.id, f"result:{result.id}"}:
        return _warning_summary("Result summary is not available.", ref)

    return _RefSummary(
        body=f"Result '{result.title}': {result.summary}",
        evidence=ReadOnlyInquiryEvidenceRef(
            kind="result_summary",
            ref_id=result.id,
            label=result.title,
            disclosure="public",
            truncated=False,
        ),
    )


@dataclass(frozen=True)
class _RefSummary:
    body: str
    evidence: ReadOnlyInquiryEvidenceRef
    warning: ReadOnlyInquiryWarning | None = None


def _file_ref_summary(
    ref: ReadOnlyInquiryRef,
    workspace_inspection_gateway: WorkspaceInspectionContextProvider | None,
) -> _RefSummary:
    if workspace_inspection_gateway is None:
        return _warning_summary("File refs require workspace inspection.", ref)
    if ref.path is None and ref.evidence_id is None:
        return _warning_summary("File ref has no path or evidence id.", ref)

    try:
        payload = workspace_inspection_gateway.file_content(
            path=ref.path,
            line_count=20,
            evidence_id=ref.evidence_id,
        )
    except Exception:  # noqa: BLE001 - do not expose provider internals to users.
        return _warning_summary("File context is not available.", ref)

    file_info = _dict(payload.get("file"))
    range_info = _dict(payload.get("range"))
    path_label = _string(file_info.get("pathLabel")) or ref.label
    unavailable = _string(payload.get("unavailableReason"))
    if unavailable is not None:
        return _warning_summary(f"File context is unavailable: {unavailable}.", ref)

    lines = _list(_dict(payload.get("content")).get("lines"))
    preview = _preview_lines(lines)
    total_lines = _int(range_info.get("totalLines"))
    truncated = bool(range_info.get("truncated"))
    line_summary = (
        f"{total_lines} lines" if total_lines is not None else f"{len(lines)} visible lines"
    )
    body = f"File '{path_label}' is available with {line_summary}."
    if preview:
        body = f"{body} Preview: {preview}"

    return _RefSummary(
        body=body,
        evidence=ReadOnlyInquiryEvidenceRef(
            kind="file_snapshot",
            ref_id=(
                ref.path
                or _string(_dict(payload.get("evidenceRef")).get("evidenceId"))
                or _string(payload.get("contentHash"))
                or path_label
            ),
            label=path_label,
            disclosure="partial" if truncated else "public",
            truncated=truncated,
        ),
    )


def _diff_ref_summary(
    ref: ReadOnlyInquiryRef,
    workspace_inspection_gateway: WorkspaceInspectionContextProvider | None,
) -> _RefSummary:
    if workspace_inspection_gateway is None:
        return _warning_summary("Diff refs require workspace inspection.", ref)
    if ref.path is None:
        return _warning_summary("Diff ref has no path.", ref)

    try:
        payload = workspace_inspection_gateway.diff(path=ref.path, max_bytes=32_768)
    except Exception:  # noqa: BLE001 - do not expose provider internals to users.
        return _warning_summary("Diff context is not available.", ref)

    file_info = _dict(payload.get("file"))
    stats = _dict(payload.get("stats"))
    path_label = _string(file_info.get("pathLabel")) or ref.label
    if payload.get("isAvailable") is not True:
        reason = _string(payload.get("unavailableReason")) or "unavailable"
        return _warning_summary(f"Diff context is unavailable: {reason}.", ref)

    additions = _int(stats.get("additions")) or 0
    deletions = _int(stats.get("deletions")) or 0
    hunk_count = _int(stats.get("hunkCount")) or 0
    truncated = bool(stats.get("truncated"))
    body = (
        f"Diff for '{path_label}' has {additions} additions, "
        f"{deletions} deletions, and {hunk_count} hunks."
    )
    return _RefSummary(
        body=body,
        evidence=ReadOnlyInquiryEvidenceRef(
            kind="diff_snapshot",
            ref_id=ref.path or _string(payload.get("contentHash")) or path_label,
            label=path_label,
            disclosure="partial" if truncated else "public",
            truncated=truncated,
        ),
    )


def _warning_summary(message: str, ref: ReadOnlyInquiryRef) -> _RefSummary:
    return _RefSummary(
        body="",
        evidence=ReadOnlyInquiryEvidenceRef(
            kind="diagnostic_summary",
            ref_id=ref.id or ref.path or ref.label,
            label=ref.label,
            disclosure="partial",
            truncated=False,
        ),
        warning=_partial_warning(message, ref),
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _preview_lines(lines: list[Any]) -> str:
    preview: list[str] = []
    for line in lines[:3]:
        text = _string(_dict(line).get("text"))
        if text is not None:
            preview.append(text)
    return " / ".join(preview)


def _partial_warning(
    message: str,
    ref: ReadOnlyInquiryRef,
) -> ReadOnlyInquiryWarning:
    return ReadOnlyInquiryWarning(
        code="inquiry.context_partial",
        message=message,
        ref=ref,
    )


def _matches_task_scope(
    value: ResultCardView | FileChangeSummaryView,
    task_node_id: str | None,
) -> bool:
    return task_node_id is None or value.task_node_id in {None, task_node_id}


def _find_plan(snapshot: MainPageSnapshot, plan_id: str | None) -> PlanView | None:
    plan = snapshot.active_plan
    if plan is None:
        return None
    if plan_id is None or plan.id == plan_id:
        return plan
    return None


def _find_task(
    snapshot: MainPageSnapshot,
    task_node_id: str | None,
) -> TaskNodeCardView | None:
    if task_node_id is None:
        return None
    if snapshot.active_plan is not None:
        for task in snapshot.active_plan.task_nodes:
            if task.id == task_node_id:
                return task
    if snapshot.task_tree is not None:
        for task in snapshot.task_tree.nodes:
            if task.id == task_node_id:
                return task
    return None


def _activity(
    request: ReadOnlyInquiryRequest,
    answer: ReadOnlyInquiryAnswer,
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...],
) -> SessionActivityItemView:
    return SessionActivityItemView(
        id=f"activity:inquiry:{request.inquiry_id}",
        session_id=request.session_id,
        kind="answer",
        title=answer.title or "Read-only answer",
        body=answer.body,
        scope_kind=request.scope.kind,
        plan_id=request.scope.plan_id,
        task_node_id=request.scope.task_node_id,
        side_effect="no_effect",
        related_refs=tuple(
            activity_ref_from_evidence(ref, request) for ref in evidence_refs
        ),
        source_kind="router",
        source_id=request.inquiry_id,
        disclosure_level="public",
    )


def _plan_evidence(plan: PlanView) -> ReadOnlyInquiryEvidenceRef:
    return _evidence("plan_status", f"plan:{plan.id}:status", f"Plan {plan.title}")


def _evidence(
    kind: ReadOnlyInquiryEvidenceKind,
    ref_id: str,
    label: str,
) -> ReadOnlyInquiryEvidenceRef:
    return ReadOnlyInquiryEvidenceRef(
        kind=kind,
        ref_id=ref_id,
        label=label,
    )


def _result_response(
    request: ReadOnlyInquiryRequest,
    *,
    status: ReadOnlyInquiryStatus,
    answer: ReadOnlyInquiryAnswer | None = None,
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...] = (),
    warning: ReadOnlyInquiryWarning | None = None,
    warnings: tuple[ReadOnlyInquiryWarning, ...] = (),
    activity: SessionActivityItemView | None = None,
) -> QueryResponse[ReadOnlyInquiryResult]:
    all_warnings = warnings if warning is None else (*warnings, warning)
    return QueryResponse[ReadOnlyInquiryResult](
        request_id=request.inquiry_id,
        ok=True,
        data=ReadOnlyInquiryResult(
            inquiry_id=request.inquiry_id,
            session_id=request.session_id,
            scope=request.scope,
            status=status,
            answer=answer,
            evidence_refs=evidence_refs,
            warnings=all_warnings,
            activity=activity,
        ),
    )


__all__ = [
    "DefaultReadOnlyInquiryService",
    "DiagnosticSupportContextProvider",
    "ReadOnlyInquiryService",
    "WorkspaceInspectionContextProvider",
]
