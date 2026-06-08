"""Workspace — the project root that scopes normal filesystem access.

Every fs tool resolves the path it receives *through* a Workspace. Paths that
escape the root (via ``..`` or absolute paths pointing outside) raise
:class:`PathOutsideWorkspaceError`. This is a defense-in-depth check, not a
security boundary — Phase 2.2 introduces a real sandbox runtime.

Workspace-private metadata under ``.taskweavn/`` is also blocked from normal
tool path access so Product 1.0 can use the selected workspace root as the
agent cwd without exposing session databases, logs, or diagnostic payloads.
"""

from __future__ import annotations

from pathlib import Path


class PathOutsideWorkspaceError(ValueError):
    """Raised when a tool tries to touch a path outside the Workspace root."""


class PathProtectedWorkspaceError(ValueError):
    """Raised when a tool tries to touch workspace-private metadata."""


class Workspace:
    """Resolves all relative paths against a single root directory."""

    def __init__(self, root: str | Path) -> None:
        resolved = Path(root).expanduser().resolve()
        if not resolved.is_dir():
            raise NotADirectoryError(f"Workspace root must exist: {resolved}")
        self.root = resolved

    def resolve(self, path: str | Path) -> Path:
        """Resolve ``path`` (relative or absolute) and confirm it stays in-bounds."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.expanduser().resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise PathOutsideWorkspaceError(
                f"Path {path!r} resolves to {candidate}, which is outside the "
                f"workspace root {self.root}."
            )
        if self.is_protected_path(candidate):
            raise PathProtectedWorkspaceError(
                f"Path {path!r} resolves to workspace-private metadata."
            )
        return candidate

    def is_protected_path(self, path: str | Path) -> bool:
        """Return true when ``path`` is inside the internal metadata tree."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.expanduser().resolve()
        protected_root = self.root / ".taskweavn"
        return candidate == protected_root or protected_root in candidate.parents
