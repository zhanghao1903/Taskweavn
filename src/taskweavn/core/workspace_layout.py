"""Workspace layout — canonical paths for a multi-session workspace (Phase 3.1).

A *workspace* is the user-facing root that owns one or more *sessions*. The
layout is::

    <workspace_root>/
      .taskweavn/
        workspace.sqlite           # session registry
        sessions/
          <session_id>/             # session-private metadata
            events.sqlite
            thoughts.sqlite
            plan.md
            logs/
      shared/                       # cross-session collaboration (Phase 3.5)
      ... user project files ...    # the project root the agent works in

The workspace root is the agent's project directory. Session-private metadata
lives under ``.taskweavn/sessions/<id>/`` and normal workspace tools must not
read or write that internal tree.

This module is pure path math — :class:`WorkspaceLayout` doesn't open any
files or databases. :class:`taskweavn.core.session_manager.SessionManager`
uses it as the source of truth for "where does X live."
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceLayout:
    """Canonical path resolver for a workspace root."""

    root: Path

    # ------------------------------------------------------------------
    # Workspace-level
    # ------------------------------------------------------------------

    @property
    def meta_dir(self) -> Path:
        return self.root / ".taskweavn"

    @property
    def registry_db_path(self) -> Path:
        return self.meta_dir / "workspace.sqlite"

    @property
    def workspace_messages_db(self) -> Path:
        """Workspace-scoped message log. Per Phase 3.3 design:
        message rows from every session live here, with row-level
        ``session_id`` isolation. Cross-session reads (Phase 4) read
        directly; per-session reads filter by ``session_id``."""
        return self.meta_dir / "messages.sqlite"

    @property
    def workspace_tasks_db(self) -> Path:
        """Workspace-scoped published Task store.

        Published Tasks are row-isolated by ``session_id`` but live at the
        workspace level so cross-session projections can be added later.
        """
        return self.meta_dir / "tasks.sqlite"

    @property
    def workspace_authoring_db(self) -> Path:
        """Workspace-scoped authoring store for RawTask and DraftTaskTree facts."""
        return self.meta_dir / "authoring.sqlite"

    @property
    def workspace_asks_db(self) -> Path:
        """Workspace-scoped execution ASK store."""
        return self.meta_dir / "asks.sqlite"

    @property
    def workspace_ui_commands_db(self) -> Path:
        """Workspace-scoped UI command response idempotency store."""
        return self.meta_dir / "ui_commands.sqlite"

    @property
    def workspace_ui_events_db(self) -> Path:
        """Workspace-scoped UI event replay store for sidecar SSE transport."""
        return self.meta_dir / "ui_events.sqlite"

    @property
    def workspace_results_db(self) -> Path:
        """Workspace-scoped task execution result/error summary store."""
        return self.meta_dir / "results.sqlite"

    @property
    def shared_dir(self) -> Path:
        return self.root / "shared"

    @property
    def sessions_root(self) -> Path:
        return self.meta_dir / "sessions"

    # ------------------------------------------------------------------
    # Session-level (parameterized by id)
    # ------------------------------------------------------------------

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_root / session_id

    def session_meta_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id)

    def session_project_dir(self, session_id: str) -> Path:
        """Project root — the agent's view of its selected workspace."""
        del session_id
        return self.root

    def session_events_db(self, session_id: str) -> Path:
        return self.session_meta_dir(session_id) / "events.sqlite"

    def session_thoughts_db(self, session_id: str) -> Path:
        return self.session_meta_dir(session_id) / "thoughts.sqlite"

    def session_context_db(self, session_id: str) -> Path:
        return self.session_meta_dir(session_id) / "context.sqlite"

    def session_plan_path(self, session_id: str) -> Path:
        return self.session_meta_dir(session_id) / "plan.md"

    def session_logs_dir(self, session_id: str) -> Path:
        return self.session_meta_dir(session_id) / "logs"

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self) -> None:
        """Create the workspace skeleton if it doesn't exist. Idempotent."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(exist_ok=True)
        self.shared_dir.mkdir(exist_ok=True)
        self.sessions_root.mkdir(exist_ok=True)

    def bootstrap_session(self, session_id: str) -> None:
        """Create the per-session directory tree. Idempotent."""
        self.session_meta_dir(session_id).mkdir(parents=True, exist_ok=True)
        self.session_logs_dir(session_id).mkdir(exist_ok=True)
        self.session_project_dir(session_id).mkdir(exist_ok=True)
