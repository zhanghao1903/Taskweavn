"""Safe navigation links for read-only inquiry evidence refs."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from taskweavn.server.ui_contract.read_only_inquiry import (
    ReadOnlyInquiryEvidenceKind,
    ReadOnlyInquiryEvidenceRef,
    ReadOnlyInquiryRequest,
)
from taskweavn.server.ui_contract.view_models import (
    SessionActivityRefKind,
    SessionActivityRefView,
)


def activity_ref_from_evidence(
    ref: ReadOnlyInquiryEvidenceRef,
    request: ReadOnlyInquiryRequest,
) -> SessionActivityRefView:
    kind_by_evidence: dict[ReadOnlyInquiryEvidenceKind, SessionActivityRefKind] = {
        "session_status": "session",
        "plan_status": "plan",
        "task_status": "task",
        "result_summary": "result",
        "file_change_summary": "file",
        "file_snapshot": "file",
        "diff_snapshot": "file",
        "audit_record": "audit",
        "audit_evidence": "audit",
        "diagnostic_summary": "diagnostic",
        "activity_item": "message",
        "workspace_status": "diagnostic",
    }
    return SessionActivityRefView(
        kind=kind_by_evidence.get(ref.kind, "diagnostic"),
        id=ref.ref_id,
        label=ref.label,
        href=activity_href(ref, request),
    )


def activity_href(
    ref: ReadOnlyInquiryEvidenceRef,
    request: ReadOnlyInquiryRequest,
) -> str | None:
    if ref.kind == "file_snapshot":
        return _workspace_inspection_href(ref, request, view="file")
    if ref.kind == "diff_snapshot":
        return _workspace_inspection_href(ref, request, view="diff")
    if ref.kind == "audit_record":
        return _audit_href(request, record_id=ref.ref_id)
    if ref.kind == "audit_evidence":
        return _audit_href(
            request,
            record_id=ref.parent_ref_id,
            evidence_id=ref.ref_id if ref.parent_ref_id is not None else None,
        )
    return None


def _workspace_inspection_href(
    ref: ReadOnlyInquiryEvidenceRef,
    request: ReadOnlyInquiryRequest,
    *,
    view: str,
) -> str | None:
    if request.workspace_id is None:
        return None
    path = _safe_workspace_relative_path(ref.label)
    if path is None and ref.kind == "diff_snapshot":
        path = _safe_workspace_relative_path(ref.ref_id)
    if view == "diff" and path is None:
        return None
    query = {
        "evidenceId": None if path is not None else ref.ref_id,
        "path": path,
        "returnSessionId": request.session_id,
        "returnTaskNodeId": request.scope.task_node_id,
        "sessionId": request.session_id,
        "taskNodeId": request.scope.task_node_id,
        "view": view,
    }
    return _url(
        f"/workspaces/{quote(request.workspace_id, safe='')}/inspection",
        query,
    )


def _audit_href(
    request: ReadOnlyInquiryRequest,
    *,
    record_id: str | None,
    evidence_id: str | None = None,
) -> str:
    is_task_scope = request.scope.task_node_id is not None
    base = (
        "/sessions/"
        f"{quote(request.session_id, safe='')}"
        f"/tasks/{quote(request.scope.task_node_id or '', safe='')}/audit"
        if is_task_scope
        else f"/sessions/{quote(request.session_id, safe='')}/audit"
    )
    query = {
        "entry": "from_task" if is_task_scope else "from_session",
        "recordId": record_id,
        "evidenceId": evidence_id,
        "returnFocus": "task" if is_task_scope else "session",
        "returnSessionId": request.session_id,
        "returnTaskNodeId": request.scope.task_node_id,
        "workspaceId": request.workspace_id,
    }
    return _url(base, query)


def _safe_workspace_relative_path(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    if normalized.startswith("workspace://"):
        _, _, normalized = normalized.removeprefix("workspace://").partition("/")
    if not normalized or normalized.startswith("/"):
        return None
    if ".." in normalized.split("/"):
        return None
    if "://" in normalized:
        return None
    return normalized


def _url(path: str, query: dict[str, str | None]) -> str:
    params = {
        key: value
        for key, value in query.items()
        if value is not None and value != ""
    }
    if not params:
        return path
    return f"{path}?{urlencode(params)}"


__all__ = ["activity_href", "activity_ref_from_evidence"]
