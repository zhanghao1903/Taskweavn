"""Session — a long-running, resumable conversation tied to a workspace (Phase 3.1).

A session has:

* a short opaque ``id`` (8 hex chars) used as both directory name and
  CLI-facing handle;
* a human ``name`` so users can list / pick by description;
* a lifecycle ``status`` driving CLI defaults (where does ``continue`` resume?);
* persistent state on disk under :class:`WorkspaceLayout`.

The dataclass is *passive* — path properties only. Mutation goes through
:class:`taskweavn.core.session_manager.SessionManager` so the on-disk
registry stays the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from taskweavn.core.workspace_layout import WorkspaceLayout

#: Lifecycle states. ``active`` is the steady state; ``awaiting_user`` means
#: the loop suspended on an ``ask_user`` call and will resume on next input;
#: ``finished`` means an ``agent_finish`` was reached; ``archived`` is a
#: soft-delete marker the user sets manually.
#:
#: Phase 3.8 made the live truth derived — see
#: :func:`taskweavn.core.session_status.derive_session_status`. The
#: ``Session.status`` field is the *stored hint* (carries the ``archived``
#: override and the create-time default) and may lag the truth between
#: events. Read paths that need the live value should call the deriver.
SessionStatus = Literal["active", "awaiting_user", "finished", "archived"]


def new_session_id() -> str:
    """Generate a short hex id. 8 chars = 32 bits, plenty for human-scale use."""
    return uuid4().hex[:8]


@dataclass(frozen=True)
class Session:
    """Metadata for one conversational session."""

    id: str
    name: str
    workspace_root: Path
    created_at: datetime
    last_active_at: datetime
    status: SessionStatus = "active"

    # ------------------------------------------------------------------
    # Path helpers — derived, never stored in the registry.
    # ------------------------------------------------------------------

    @property
    def layout(self) -> WorkspaceLayout:
        return WorkspaceLayout(self.workspace_root)

    @property
    def session_dir(self) -> Path:
        return self.layout.session_dir(self.id)

    @property
    def meta_dir(self) -> Path:
        return self.layout.session_meta_dir(self.id)

    @property
    def project_dir(self) -> Path:
        return self.layout.session_project_dir(self.id)

    @property
    def events_db_path(self) -> Path:
        return self.layout.session_events_db(self.id)

    @property
    def thoughts_db_path(self) -> Path:
        return self.layout.session_thoughts_db(self.id)

    @property
    def messages_db_path(self) -> Path:
        """Workspace-scoped messages.sqlite. Returns the same path for every
        session in the workspace; per-session reads filter on ``session_id``."""
        return self.layout.workspace_messages_db

    @property
    def plan_path(self) -> Path:
        return self.layout.session_plan_path(self.id)

    @property
    def logs_dir(self) -> Path:
        return self.layout.session_logs_dir(self.id)
