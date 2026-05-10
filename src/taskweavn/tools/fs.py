"""Filesystem tools: ReadFile, WriteFile, ListDir.

Each tool owns a :class:`Workspace` and resolves every path through it, so a
malformed path never reads or writes outside the configured root.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.tools.base import Tool
from taskweavn.tools.workspace import Workspace
from taskweavn.types.base import BaseAction, BaseObservation

# baseline_risk values track docs/interaction_layer_design.md Appendix B.

# ---------------------------------------------------------------------------
# Action / Observation types
# ---------------------------------------------------------------------------


class ReadFileAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.0
    path: str = Field(description="Workspace-relative or absolute file path to read.")


class FileContentObservation(BaseObservation):
    path: str
    content: str
    bytes_read: int


class WriteFileAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.3
    path: str = Field(description="Workspace-relative or absolute file path to write.")
    content: str
    create_parents: bool = Field(
        default=True,
        description="Create missing parent directories before writing.",
    )


class FileWriteObservation(BaseObservation):
    path: str
    bytes_written: int
    created: bool = Field(description="True if the file did not exist before this write.")


class ListDirAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.0
    path: str = Field(default=".", description="Directory path to list.")


class DirEntry(BaseModel):
    """One entry in a directory listing. Pure data, not an event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    is_dir: bool
    size: int | None = None


class DirListingObservation(BaseObservation):
    path: str
    entries: list[DirEntry]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


class ReadFileTool(Tool[ReadFileAction, FileContentObservation]):
    name: ClassVar[str] = "read_file"
    description: ClassVar[str] = "Read the UTF-8 contents of a file in the workspace."
    action_type: ClassVar[type[BaseAction]] = ReadFileAction
    observation_type: ClassVar[type[BaseObservation]] = FileContentObservation

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def execute(self, action: ReadFileAction) -> FileContentObservation:
        target = self._workspace.resolve(action.path)
        content = target.read_text(encoding="utf-8")
        return FileContentObservation(
            action_id=action.event_id,
            path=str(target.relative_to(self._workspace.root)),
            content=content,
            bytes_read=len(content.encode("utf-8")),
        )


class WriteFileTool(Tool[WriteFileAction, FileWriteObservation]):
    name: ClassVar[str] = "write_file"
    description: ClassVar[str] = (
        "Write UTF-8 content to a file in the workspace, replacing any existing content."
    )
    action_type: ClassVar[type[BaseAction]] = WriteFileAction
    observation_type: ClassVar[type[BaseObservation]] = FileWriteObservation

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def execute(self, action: WriteFileAction) -> FileWriteObservation:
        target = self._workspace.resolve(action.path)
        existed = target.exists()
        if action.create_parents:
            target.parent.mkdir(parents=True, exist_ok=True)
        encoded = action.content.encode("utf-8")
        target.write_bytes(encoded)
        return FileWriteObservation(
            action_id=action.event_id,
            path=str(target.relative_to(self._workspace.root)),
            bytes_written=len(encoded),
            created=not existed,
        )


class ListDirTool(Tool[ListDirAction, DirListingObservation]):
    name: ClassVar[str] = "list_dir"
    description: ClassVar[str] = "List the immediate entries of a directory in the workspace."
    action_type: ClassVar[type[BaseAction]] = ListDirAction
    observation_type: ClassVar[type[BaseObservation]] = DirListingObservation

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def execute(self, action: ListDirAction) -> DirListingObservation:
        target = self._workspace.resolve(action.path)
        if not target.is_dir():
            raise NotADirectoryError(f"{target} is not a directory.")
        entries = sorted(self._iter_entries(target), key=lambda e: (not e.is_dir, e.name))
        return DirListingObservation(
            action_id=action.event_id,
            path=str(target.relative_to(self._workspace.root)) or ".",
            entries=entries,
        )

    @staticmethod
    def _iter_entries(directory: Path) -> list[DirEntry]:
        results: list[DirEntry] = []
        for child in directory.iterdir():
            is_dir = child.is_dir()
            size = None if is_dir else child.stat().st_size
            results.append(DirEntry(name=child.name, is_dir=is_dir, size=size))
        return results
