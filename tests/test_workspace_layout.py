"""Tests for WorkspaceLayout (Phase 3.1)."""

from __future__ import annotations

from pathlib import Path

from taskweavn.core import WorkspaceLayout


def test_layout_paths_are_derived_from_root(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    assert layout.meta_dir == tmp_path / ".plato"
    assert layout.registry_db_path == tmp_path / ".plato" / "workspace.sqlite"
    assert layout.shared_dir == tmp_path / "shared"
    assert layout.sessions_root == tmp_path / ".plato" / "sessions"


def test_workspace_messages_db_is_workspace_scoped(tmp_path: Path) -> None:
    """Phase 3.3: messages.sqlite lives next to workspace.sqlite (one DB per
    workspace, row-level session isolation)."""
    layout = WorkspaceLayout(tmp_path)
    assert layout.workspace_messages_db == tmp_path / ".plato" / "messages.sqlite"
    # Sibling of the registry — same parent dir.
    assert (
        layout.workspace_messages_db.parent == layout.registry_db_path.parent
    )


def test_workspace_tasks_db_is_workspace_scoped(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    assert layout.workspace_tasks_db == tmp_path / ".plato" / "tasks.sqlite"
    assert layout.workspace_tasks_db.parent == layout.registry_db_path.parent


def test_workspace_authoring_db_is_workspace_scoped(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    assert layout.workspace_authoring_db == tmp_path / ".plato" / "authoring.sqlite"
    assert layout.workspace_authoring_db.parent == layout.registry_db_path.parent


def test_workspace_asks_db_is_workspace_scoped(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    assert layout.workspace_asks_db == tmp_path / ".plato" / "asks.sqlite"
    assert layout.workspace_asks_db.parent == layout.registry_db_path.parent


def test_workspace_ui_events_db_is_workspace_scoped(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    assert layout.workspace_ui_events_db == tmp_path / ".plato" / "ui_events.sqlite"
    assert layout.workspace_ui_events_db.parent == layout.registry_db_path.parent


def test_session_paths(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    sid = "abc12345"
    assert layout.session_dir(sid) == tmp_path / ".plato" / "sessions" / sid
    assert layout.session_meta_dir(sid) == tmp_path / ".plato" / "sessions" / sid
    assert layout.session_project_dir(sid) == tmp_path
    assert (
        layout.session_events_db(sid)
        == tmp_path / ".plato" / "sessions" / sid / "events.sqlite"
    )
    assert (
        layout.session_thoughts_db(sid)
        == tmp_path / ".plato" / "sessions" / sid / "thoughts.sqlite"
    )
    assert (
        layout.session_tool_effects_db(sid)
        == tmp_path / ".plato" / "sessions" / sid / "tool_effects.sqlite"
    )
    assert (
        layout.session_plan_path(sid)
        == tmp_path / ".plato" / "sessions" / sid / "plan.md"
    )
    assert (
        layout.session_logs_dir(sid)
        == tmp_path / ".plato" / "sessions" / sid / "logs"
    )


def test_bootstrap_creates_skeleton(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path / "ws")
    layout.bootstrap()
    assert layout.root.is_dir()
    assert layout.meta_dir.is_dir()
    assert layout.shared_dir.is_dir()
    assert layout.sessions_root.is_dir()
    # Re-bootstrap must be idempotent.
    layout.bootstrap()
    assert layout.root.is_dir()


def test_bootstrap_migrates_legacy_taskweavn_meta_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    legacy = workspace / ".taskweavn"
    legacy.mkdir(parents=True)
    (legacy / "workspace.sqlite").write_text("legacy")

    layout = WorkspaceLayout(workspace)
    layout.bootstrap()

    assert not legacy.exists()
    assert (workspace / ".plato" / "workspace.sqlite").read_text() == "legacy"


def test_bootstrap_migrates_legacy_code_agent_logs(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    legacy_logs = workspace / ".code-agent" / "logs" / "global"
    legacy_logs.mkdir(parents=True)
    (legacy_logs / "config.jsonl").write_text("{}\n")

    layout = WorkspaceLayout(workspace)
    layout.bootstrap()

    assert not (workspace / ".code-agent").exists()
    assert (workspace / ".plato" / "logs" / "global" / "config.jsonl").exists()


def test_bootstrap_session_creates_meta_and_project(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    layout.bootstrap()
    sid = "abc12345"
    layout.bootstrap_session(sid)
    assert layout.session_meta_dir(sid).is_dir()
    assert layout.session_logs_dir(sid).is_dir()
    assert layout.session_project_dir(sid).is_dir()
    # Idempotent.
    layout.bootstrap_session(sid)
    assert layout.session_project_dir(sid).is_dir()


def test_layout_is_frozen(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    import dataclasses

    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        layout.root = tmp_path / "other"  # type: ignore[misc]
