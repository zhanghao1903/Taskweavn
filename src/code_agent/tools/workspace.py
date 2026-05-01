"""Workspace — the per-session sandbox root that scopes all filesystem access.

Every fs tool resolves the path it receives *through* a Workspace. Paths that
escape the root (via ``..`` or absolute paths pointing outside) raise
:class:`PathOutsideWorkspaceError`. This is a defense-in-depth check, not a
security boundary — Phase 2.2 introduces a real sandbox runtime.
"""

from __future__ import annotations

from pathlib import Path


class PathOutsideWorkspaceError(ValueError):
    """Raised when a tool tries to touch a path outside the Workspace root."""


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
        return candidate
