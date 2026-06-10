"""Safe workspace-relative path policy for inspection reads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from taskweavn.core.workspace_layout import PROTECTED_WORKSPACE_METADATA_DIR_NAMES


class WorkspaceInspectionPathError(ValueError):
    """Raised when an inspection path is not safe to resolve."""


@dataclass(frozen=True)
class WorkspacePathRef:
    relative_path: str
    path_label: str
    resolved_path: Path

    def to_contract(self) -> dict[str, str]:
        return {
            "relativePath": self.relative_path,
            "pathLabel": self.path_label,
        }


@dataclass(frozen=True)
class WorkspaceInspectionPathPolicy:
    workspace_root: Path
    workspace_id: str

    def root_label(self) -> str:
        return f"workspace://{self.workspace_id}"

    def resolve_required(self, raw_path: str | None) -> WorkspacePathRef:
        if raw_path is None or raw_path.strip() == "":
            raise WorkspaceInspectionPathError("path is required")
        return self.resolve(raw_path)

    def resolve(self, raw_path: str) -> WorkspacePathRef:
        relative_path = self._normalize_relative_path(raw_path)
        root = self.workspace_root.expanduser().resolve()
        target = (root / relative_path).resolve(strict=False)
        if target != root and root not in target.parents:
            raise WorkspaceInspectionPathError("path resolves outside workspace")
        return WorkspacePathRef(
            relative_path=relative_path,
            path_label=f"workspace://{self.workspace_id}/{relative_path}",
            resolved_path=target,
        )

    def _normalize_relative_path(self, raw_path: str) -> str:
        if any(ord(char) < 32 for char in raw_path):
            raise WorkspaceInspectionPathError("path contains control characters")
        if "\\" in raw_path:
            raise WorkspaceInspectionPathError("path must use POSIX separators")
        path = PurePosixPath(raw_path)
        if path.is_absolute():
            raise WorkspaceInspectionPathError("absolute paths are not allowed")
        parts = tuple(part for part in path.parts if part not in ("", "."))
        if not parts:
            raise WorkspaceInspectionPathError("path is required")
        if any(part == ".." for part in parts):
            raise WorkspaceInspectionPathError("path traversal is not allowed")
        if parts[0] in PROTECTED_WORKSPACE_METADATA_DIR_NAMES:
            raise WorkspaceInspectionPathError("workspace metadata is protected")
        return "/".join(parts)
