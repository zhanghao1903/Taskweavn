"""Precision filesystem tools for bounded file operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.tools.base import Tool
from taskweavn.tools.workspace import Workspace
from taskweavn.types.base import BaseAction, BaseObservation
from taskweavn.workspace_inspection import WorkspaceInspectionLimits
from taskweavn.workspace_inspection.precision_files import (
    PrecisionFileService,
    WorkspaceContentHash,
)


class PrecisionFileContentHash(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm: Literal["sha256"] = "sha256"
    value: str

    def to_workspace_hash(self) -> WorkspaceContentHash:
        return WorkspaceContentHash(algorithm=self.algorithm, value=self.value)


class ReadFileRangeAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.0

    path: str = Field(description="Workspace-relative text file path.")
    start_line: int = Field(default=1, ge=1)
    line_count: int | None = Field(default=None, ge=1)


class FileRangeObservation(BaseObservation):
    path: str
    path_label: str
    start_line: int
    end_line: int
    lines: list[dict[str, Any]]
    content_hash: dict[str, str]
    range_hash: dict[str, str]
    warnings: list[dict[str, Any]] = []


class SearchWorkspaceAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.05

    query: str = Field(description="Literal text or filename query.")
    mode: Literal["literal", "filename"] = "literal"
    case_sensitive: bool = False
    include_globs: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    max_files: int | None = Field(default=None, ge=0)
    max_matches: int | None = Field(default=None, ge=0)


class WorkspaceSearchObservation(BaseObservation):
    query: str
    mode: str
    matches: list[dict[str, Any]]
    summary: dict[str, Any]
    warnings: list[dict[str, Any]] = []


class ReplaceFileRangeAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.55

    operation_id: str = Field(description="Stable idempotency key for this mutation.")
    path: str = Field(description="Workspace-relative text file path.")
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    replacement_text: str
    expected_content_hash: PrecisionFileContentHash
    reason: Literal["task_execution", "user_command", "recovery"] = "task_execution"


class AppendFileAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.45

    operation_id: str = Field(description="Stable idempotency key for this mutation.")
    path: str = Field(description="Workspace-relative text file path.")
    content: str
    expected_content_hash: PrecisionFileContentHash
    ensure_trailing_newline: bool = True
    reason: Literal["task_execution", "user_command", "recovery"] = "task_execution"


class PrecisionFileMutationObservation(BaseObservation):
    operation_id: str
    path: str
    path_label: str
    change_type: Literal["modified"]
    changed_line_ranges: list[dict[str, int]]
    before_hash: dict[str, str]
    after_hash: dict[str, str]
    bytes_written: int
    evidence_ref: dict[str, Any]
    replayed: bool = False


class ReadFileRangeTool(Tool[ReadFileRangeAction, FileRangeObservation]):
    name: ClassVar[str] = "read_file_range"
    description: ClassVar[str] = "Read a bounded line range from a UTF-8 workspace file."
    action_type: ClassVar[type[BaseAction]] = ReadFileRangeAction
    observation_type: ClassVar[type[BaseObservation]] = FileRangeObservation

    def __init__(
        self,
        workspace: Workspace,
        *,
        workspace_id: str = "current",
        inspection_db_path: Path | None = None,
        limits: WorkspaceInspectionLimits | None = None,
    ) -> None:
        self._service = _service(
            workspace,
            workspace_id=workspace_id,
            inspection_db_path=inspection_db_path,
            limits=limits,
        )

    def execute(self, action: ReadFileRangeAction) -> FileRangeObservation:
        response = self._service.read_range(
            path=action.path,
            start_line=action.start_line,
            line_count=action.line_count,
        )
        return FileRangeObservation(
            action_id=action.event_id,
            path=response["file"]["relativePath"],
            path_label=response["file"]["pathLabel"],
            start_line=response["range"]["startLine"],
            end_line=response["range"]["endLine"],
            lines=response["lines"],
            content_hash=response["contentHash"],
            range_hash=response["rangeHash"],
            warnings=response["warnings"],
        )


class SearchWorkspaceTool(Tool[SearchWorkspaceAction, WorkspaceSearchObservation]):
    name: ClassVar[str] = "search_workspace"
    description: ClassVar[str] = "Search workspace filenames or UTF-8 text files safely."
    action_type: ClassVar[type[BaseAction]] = SearchWorkspaceAction
    observation_type: ClassVar[type[BaseObservation]] = WorkspaceSearchObservation

    def __init__(
        self,
        workspace: Workspace,
        *,
        workspace_id: str = "current",
        inspection_db_path: Path | None = None,
        limits: WorkspaceInspectionLimits | None = None,
    ) -> None:
        self._service = _service(
            workspace,
            workspace_id=workspace_id,
            inspection_db_path=inspection_db_path,
            limits=limits,
        )

    def execute(self, action: SearchWorkspaceAction) -> WorkspaceSearchObservation:
        response = self._service.search(
            query=action.query,
            mode=action.mode,
            case_sensitive=action.case_sensitive,
            include_globs=action.include_globs,
            exclude_globs=action.exclude_globs,
            max_files=action.max_files,
            max_matches=action.max_matches,
        )
        return WorkspaceSearchObservation(
            action_id=action.event_id,
            query=response["query"],
            mode=response["mode"],
            matches=response["matches"],
            summary=response["summary"],
            warnings=response["warnings"],
        )


class ReplaceFileRangeTool(
    Tool[ReplaceFileRangeAction, PrecisionFileMutationObservation]
):
    name: ClassVar[str] = "replace_file_range"
    description: ClassVar[str] = (
        "Replace a bounded line range after validating the expected file hash."
    )
    action_type: ClassVar[type[BaseAction]] = ReplaceFileRangeAction
    observation_type: ClassVar[type[BaseObservation]] = PrecisionFileMutationObservation

    def __init__(
        self,
        workspace: Workspace,
        *,
        workspace_id: str = "current",
        inspection_db_path: Path | None = None,
        limits: WorkspaceInspectionLimits | None = None,
    ) -> None:
        self._service = _service(
            workspace,
            workspace_id=workspace_id,
            inspection_db_path=inspection_db_path,
            limits=limits,
        )

    def execute(self, action: ReplaceFileRangeAction) -> PrecisionFileMutationObservation:
        response = self._service.replace_range(
            operation_id=action.operation_id,
            path=action.path,
            start_line=action.start_line,
            end_line=action.end_line,
            replacement_text=action.replacement_text,
            expected_content_hash=action.expected_content_hash.to_workspace_hash(),
            reason=action.reason,
        )
        return _mutation_observation(action, response)


class AppendFileTool(Tool[AppendFileAction, PrecisionFileMutationObservation]):
    name: ClassVar[str] = "append_file"
    description: ClassVar[str] = (
        "Append UTF-8 text after validating the expected file hash and operation id."
    )
    action_type: ClassVar[type[BaseAction]] = AppendFileAction
    observation_type: ClassVar[type[BaseObservation]] = PrecisionFileMutationObservation

    def __init__(
        self,
        workspace: Workspace,
        *,
        workspace_id: str = "current",
        inspection_db_path: Path | None = None,
        limits: WorkspaceInspectionLimits | None = None,
    ) -> None:
        self._service = _service(
            workspace,
            workspace_id=workspace_id,
            inspection_db_path=inspection_db_path,
            limits=limits,
        )

    def execute(self, action: AppendFileAction) -> PrecisionFileMutationObservation:
        response = self._service.append(
            operation_id=action.operation_id,
            path=action.path,
            content=action.content,
            expected_content_hash=action.expected_content_hash.to_workspace_hash(),
            ensure_trailing_newline=action.ensure_trailing_newline,
            reason=action.reason,
        )
        return _mutation_observation(action, response)


def _service(
    workspace: Workspace,
    *,
    workspace_id: str,
    inspection_db_path: Path | None,
    limits: WorkspaceInspectionLimits | None,
) -> PrecisionFileService:
    return PrecisionFileService.build(
        workspace_root=workspace.root,
        workspace_id=workspace_id,
        inspection_db_path=(
            inspection_db_path or workspace.root / ".plato" / "inspection.sqlite"
        ),
        limits=limits,
    )


def _mutation_observation(
    action: ReplaceFileRangeAction | AppendFileAction,
    response: dict[str, Any],
) -> PrecisionFileMutationObservation:
    return PrecisionFileMutationObservation(
        action_id=action.event_id,
        operation_id=response["operationId"],
        path=response["file"]["relativePath"],
        path_label=response["file"]["pathLabel"],
        change_type="modified",
        changed_line_ranges=response["changedLineRanges"],
        before_hash=response["beforeHash"],
        after_hash=response["afterHash"],
        bytes_written=response["bytesWritten"],
        evidence_ref=response["evidenceRef"],
        replayed=response["replayed"],
    )
