"""HTTP adapter for Product 1.1 workspace inspection routes."""

from __future__ import annotations

from typing import Any, Protocol

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError
from taskweavn.server.ui_http_query_params import _int_query, _request_query
from taskweavn.server.ui_http_responses import (
    _error_response,
    _json_response,
    _request_id_hint,
)
from taskweavn.workspace_inspection.gateway import WorkspaceInspectionInputError
from taskweavn.workspace_inspection.path_policy import WorkspaceInspectionPathError


class WorkspaceInspectionGateway(Protocol):
    """HTTP-facing Product 1.1 workspace inspection gateway."""

    def status(self, *, max_files: int | None = None) -> dict[str, Any]: ...

    def diff(
        self,
        *,
        path: str,
        base: str = "head",
        context_lines: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Any]: ...

    def file_content(
        self,
        *,
        path: str | None,
        start_line: int = 1,
        line_count: int | None = None,
        evidence_id: str | None = None,
    ) -> dict[str, Any]: ...

    def capture_evidence(self, request: dict[str, Any]) -> dict[str, Any]: ...


def _workspace_inspection_response(
    request: HttpApiRequest,
    *,
    route_name: str,
    gateway: WorkspaceInspectionGateway | None,
) -> HttpApiResponse:
    if gateway is None:
        return _error_response(
            503,
            ApiError(
                code="internal_error",
                message="workspace inspection gateway is not configured",
                retryable=True,
                details=_workspace_inspection_error_details(
                    "workspace_inspection_unavailable",
                    ("export_diagnostics",),
                ),
            ),
            request_id=_request_id_hint(request),
        )
    try:
        query = _request_query(request)
        if route_name == "workspace_inspection_status":
            data = gateway.status(max_files=_optional_int_query(query, "maxFiles"))
        elif route_name == "workspace_inspection_diff":
            path = _required_query(query, "path")
            data = gateway.diff(
                path=path,
                base=query.get("base", "head"),
                context_lines=_optional_int_query(query, "contextLines"),
                max_bytes=_optional_int_query(query, "maxBytes"),
            )
        elif route_name == "workspace_file_content":
            data = gateway.file_content(
                path=query.get("path"),
                start_line=_int_query(query, "startLine", default=1),
                line_count=_optional_int_query(query, "lineCount"),
                evidence_id=query.get("evidenceId"),
            )
        elif route_name == "workspace_inspection_evidence":
            if request.body is None:
                raise WorkspaceInspectionInputError("request body must be a JSON object")
            data = gateway.capture_evidence(request.body)
        else:
            return _error_response(
                404,
                ApiError(code="not_found", message="unknown inspection route"),
                request_id=_request_id_hint(request),
            )
        return _json_response({"ok": True, "data": data, "error": None})
    except (WorkspaceInspectionInputError, WorkspaceInspectionPathError, ValueError) as exc:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message=str(exc),
                details=_workspace_inspection_error_details(
                    "input_validation",
                    ("edit_input", "open_audit"),
                ),
            ),
            request_id=_request_id_hint(request),
        )


def _required_query(query: dict[str, str], key: str) -> str:
    value = query.get(key)
    if value is None or not value.strip():
        raise WorkspaceInspectionInputError(f"{key} is required")
    return value


def _optional_int_query(query: dict[str, str], key: str) -> int | None:
    raw = query.get(key)
    if raw is None or raw == "":
        return None
    return int(raw)


def _workspace_inspection_error_details(
    category: str,
    actions: tuple[str, ...],
) -> dict[str, object]:
    return {
        "product_error_category": category,
        "recovery_actions": list(actions),
        "productCategory": category,
        "recoveryActions": list(actions),
    }


__all__ = [
    "WorkspaceInspectionGateway",
    "_workspace_inspection_response",
]
