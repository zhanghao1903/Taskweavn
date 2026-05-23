"""Tests for Session + SessionManager (Phase 3.1)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from taskweavn.core import (
    Session,
    SessionManager,
    SessionManagerError,
    WorkspaceLayout,
    new_session_id,
)


@pytest.fixture
def manager(tmp_path: Path) -> SessionManager:
    return SessionManager(WorkspaceLayout(tmp_path))


def test_new_session_id_is_short_hex() -> None:
    sid = new_session_id()
    assert len(sid) == 8
    assert all(c in "0123456789abcdef" for c in sid)
    # Two ids in a row should differ.
    assert new_session_id() != new_session_id()


def test_create_returns_active_session(manager: SessionManager) -> None:
    s = manager.create("personal site")
    assert isinstance(s, Session)
    assert s.name == "personal site"
    assert s.status == "active"
    assert s.created_at == s.last_active_at
    assert s.workspace_root == manager.layout.root


def test_create_bootstraps_session_dirs(manager: SessionManager) -> None:
    s = manager.create("site")
    assert s.meta_dir.is_dir()
    assert s.project_dir.is_dir()
    assert s.logs_dir.is_dir()


def test_create_rejects_empty_name(manager: SessionManager) -> None:
    with pytest.raises(SessionManagerError):
        manager.create("   ")


def test_get_returns_none_for_missing(manager: SessionManager) -> None:
    assert manager.get("deadbeef") is None


def test_require_raises_for_missing(manager: SessionManager) -> None:
    with pytest.raises(SessionManagerError):
        manager.require("deadbeef")


def test_get_round_trips(manager: SessionManager) -> None:
    s = manager.create("site")
    fetched = manager.require(s.id)
    assert fetched == s


def test_list_orders_by_recency(manager: SessionManager) -> None:
    a = manager.create("first")
    time.sleep(0.01)
    b = manager.create("second")
    listed = manager.list()
    assert [s.id for s in listed] == [b.id, a.id]
    # touch the older one — it should bubble up.
    time.sleep(0.01)
    manager.touch(a.id)
    listed = manager.list()
    assert [s.id for s in listed] == [a.id, b.id]


def test_touch_updates_last_active(manager: SessionManager) -> None:
    s = manager.create("site")
    time.sleep(0.01)
    refreshed = manager.touch(s.id)
    assert refreshed.last_active_at > s.last_active_at


def test_touch_unknown_raises(manager: SessionManager) -> None:
    with pytest.raises(SessionManagerError):
        manager.touch("nope")


def test_rename_updates_name_and_activity(manager: SessionManager) -> None:
    s = manager.create("site")
    time.sleep(0.01)
    refreshed = manager.rename(s.id, "renamed site")

    assert refreshed.name == "renamed site"
    assert refreshed.last_active_at > s.last_active_at
    assert manager.require(s.id).name == "renamed site"


def test_rename_rejects_empty_name(manager: SessionManager) -> None:
    s = manager.create("site")
    with pytest.raises(SessionManagerError):
        manager.rename(s.id, " ")


def test_delete_removes_registry_row_and_archives_directory(manager: SessionManager) -> None:
    first = manager.create("first")
    second = manager.create("second")
    first_dir = first.session_dir

    next_session = manager.delete(first.id)

    assert next_session is not None
    assert next_session.id == second.id
    assert manager.get(first.id) is None
    assert not first_dir.exists()
    archive_root = manager.layout.meta_dir / "deleted-sessions"
    assert any(path.name.startswith(first.id) for path in archive_root.iterdir())


def test_mark_status_round_trip(manager: SessionManager) -> None:
    s = manager.create("site")
    refreshed = manager.mark_status(s.id, "awaiting_user")
    assert refreshed.status == "awaiting_user"
    assert manager.require(s.id).status == "awaiting_user"


def test_mark_status_rejects_invalid(manager: SessionManager) -> None:
    s = manager.create("site")
    with pytest.raises(SessionManagerError):
        manager.mark_status(s.id, "nonsense")  # type: ignore[arg-type]


def test_persistence_across_reopen(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    mgr = SessionManager(layout)
    s = mgr.create("kept")
    mgr.close()

    reopened = SessionManager(layout)
    fetched = reopened.require(s.id)
    assert fetched.id == s.id
    assert fetched.name == "kept"
    reopened.close()


def test_session_manager_is_context_manager(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    with SessionManager(layout) as mgr:
        s = mgr.create("ctx")
        assert mgr.require(s.id).id == s.id


def test_session_path_helpers_match_layout(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    mgr = SessionManager(layout)
    s = mgr.create("paths")
    try:
        assert s.events_db_path == layout.session_events_db(s.id)
        assert s.thoughts_db_path == layout.session_thoughts_db(s.id)
        assert s.plan_path == layout.session_plan_path(s.id)
        assert s.session_dir == layout.session_dir(s.id)
        assert s.project_dir == layout.session_project_dir(s.id)
    finally:
        mgr.close()
