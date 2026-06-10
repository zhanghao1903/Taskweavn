"""Workspace inspection gateway orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskweavn.workspace_inspection.git_provider import ControlledGitCliInspectionProvider
from taskweavn.workspace_inspection.limits import WorkspaceInspectionLimits
from taskweavn.workspace_inspection.path_policy import (
    WorkspaceInspectionPathError,
    WorkspaceInspectionPathPolicy,
)
from taskweavn.workspace_inspection.store import (
    InspectionEvidenceNotFoundError,
    SqliteInspectionEvidenceStore,
)


class WorkspaceInspectionInputError(ValueError):
    """Raised when an inspection request is invalid."""


@dataclass(frozen=True)
class DefaultWorkspaceInspectionGateway:
    """Product 1.1 read-only workspace inspection gateway."""

    workspace_root: Path
    workspace_id: str
    store: SqliteInspectionEvidenceStore
    limits: WorkspaceInspectionLimits = WorkspaceInspectionLimits()

    @classmethod
    def build(
        cls,
        *,
        workspace_root: Path,
        workspace_id: str,
        inspection_db_path: Path,
        limits: WorkspaceInspectionLimits | None = None,
    ) -> DefaultWorkspaceInspectionGateway:
        configured_limits = limits or WorkspaceInspectionLimits()
        return cls(
            workspace_root=workspace_root,
            workspace_id=workspace_id,
            limits=configured_limits,
            store=SqliteInspectionEvidenceStore(
                inspection_db_path,
                limits=configured_limits,
            ),
        )

    def status(self, *, max_files: int | None = None) -> dict[str, Any]:
        return self._provider().status(max_files=max_files)

    def diff(
        self,
        *,
        path: str,
        base: str = "head",
        context_lines: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Any]:
        path_ref = self._path_policy().resolve_required(path)
        return self._provider().diff(
            path_ref,
            base=base,
            context_lines=context_lines,
            max_bytes=max_bytes,
        )

    def file_content(
        self,
        *,
        path: str | None,
        start_line: int = 1,
        line_count: int | None = None,
        evidence_id: str | None = None,
    ) -> dict[str, Any]:
        if evidence_id:
            return self._captured_file_content(evidence_id)
        path_ref = self._path_policy().resolve_required(path)
        return self._provider().file_content(
            path_ref,
            start_line=start_line,
            line_count=line_count,
        )

    def capture_evidence(self, request: dict[str, Any]) -> dict[str, Any]:
        kind = _string_value(request, "kind")
        if kind not in {"git_status_snapshot", "diff_snapshot", "file_snapshot"}:
            raise WorkspaceInspectionInputError("unsupported evidence kind")
        reason = _string_value(request, "reason")
        if reason not in {
            "task_result",
            "audit_record",
            "diagnostic_export",
            "manual_capture",
        }:
            raise WorkspaceInspectionInputError("unsupported evidence reason")
        if kind == "git_status_snapshot":
            payload = self.status()
            descriptor = {
                "kind": kind,
                "truncated": bool(payload["summary"]["hasMore"]),
            }
            source = "git_status"
            path_label = None
        elif kind == "diff_snapshot":
            path = _string_value(request, "path")
            payload = self.diff(path=path)
            descriptor = {
                "kind": kind,
                "pathLabel": payload["file"]["pathLabel"],
                "contentHash": payload.get("contentHash"),
                "truncated": bool(payload["stats"]["truncated"]),
            }
            source = "git_diff"
            path_label = str(payload["file"]["pathLabel"])
        else:
            path = _string_value(request, "path")
            line_range = request.get("lineRange")
            start_line = 1
            line_count = None
            if isinstance(line_range, dict):
                start_line = _int_value(line_range, "startLine", default=1)
                line_count = _optional_int_value(line_range, "lineCount")
            payload = self.file_content(
                path=path,
                start_line=start_line,
                line_count=line_count,
            )
            descriptor = {
                "kind": kind,
                "pathLabel": payload["file"]["pathLabel"],
                "contentHash": payload.get("contentHash"),
                "truncated": bool(payload["range"]["truncated"]),
            }
            source = "file_content"
            path_label = str(payload["file"]["pathLabel"])

        evidence_ref = self.store.capture(
            workspace_id=self.workspace_id,
            kind=kind,
            source=source,
            payload=payload,
            descriptor=descriptor,
            path_label=path_label,
        )
        return {
            "schemaVersion": "plato.workspace_inspection.evidence_capture.v1",
            "workspaceId": self.workspace_id,
            "capturedAt": evidence_ref["createdAt"],
            "evidenceRef": evidence_ref,
            "descriptor": descriptor,
        }

    def _captured_file_content(self, evidence_id: str) -> dict[str, Any]:
        try:
            record = self.store.get(evidence_id)
        except InspectionEvidenceNotFoundError as exc:
            raise WorkspaceInspectionInputError("inspection evidence not found") from exc
        if record["kind"] != "file_snapshot":
            raise WorkspaceInspectionInputError("inspection evidence is not a file snapshot")
        payload = record["payload"]
        if not isinstance(payload, dict) or payload.get("omitted") is True:
            raise WorkspaceInspectionInputError("inspection evidence payload is unavailable")
        response = dict(payload)
        response["source"] = "captured_evidence"
        response["evidenceRef"] = {
            "evidenceId": record["evidenceId"],
            "kind": record["kind"],
            "workspaceId": record["workspaceId"],
            **({"pathLabel": record["pathLabel"]} if record["pathLabel"] else {}),
            "createdAt": record["capturedAt"],
        }
        return response

    def _path_policy(self) -> WorkspaceInspectionPathPolicy:
        return WorkspaceInspectionPathPolicy(
            workspace_root=self.workspace_root,
            workspace_id=self.workspace_id,
        )

    def _provider(self) -> ControlledGitCliInspectionProvider:
        return ControlledGitCliInspectionProvider(
            workspace_root=self.workspace_root,
            workspace_id=self.workspace_id,
            limits=self.limits,
        )


def _string_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceInspectionInputError(f"{key} is required")
    return value


def _int_value(payload: dict[str, Any], key: str, *, default: int) -> int:
    value = payload.get(key, default)
    if not isinstance(value, int):
        raise WorkspaceInspectionInputError(f"{key} must be an integer")
    return value


def _optional_int_value(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise WorkspaceInspectionInputError(f"{key} must be an integer")
    return value


def to_input_error(exc: Exception) -> WorkspaceInspectionInputError:
    if isinstance(exc, WorkspaceInspectionInputError):
        return exc
    if isinstance(exc, WorkspaceInspectionPathError):
        return WorkspaceInspectionInputError(str(exc))
    return WorkspaceInspectionInputError(type(exc).__name__)
