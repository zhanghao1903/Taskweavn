"""Tests for Workspace path safety (1.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.tools import (
    PathOutsideWorkspaceError,
    PathProtectedWorkspaceError,
    Workspace,
)


def test_root_must_exist(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        Workspace(tmp_path / "missing")


def test_resolve_relative_path(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.txt").write_text("hi")
    ws = Workspace(tmp_path)

    resolved = ws.resolve("sub/file.txt")
    assert resolved == (tmp_path / "sub" / "file.txt").resolve()


def test_resolve_absolute_path_inside_workspace(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    target = tmp_path / "x.txt"
    target.write_text("ok")

    assert ws.resolve(str(target)) == target.resolve()


def test_reject_traversal_via_dotdot(tmp_path: Path) -> None:
    (tmp_path / "inner").mkdir()
    ws = Workspace(tmp_path / "inner")

    with pytest.raises(PathOutsideWorkspaceError):
        ws.resolve("../escape.txt")


def test_reject_absolute_path_outside_workspace(tmp_path: Path) -> None:
    (tmp_path / "inner").mkdir()
    (tmp_path / "outside.txt").write_text("hi")
    ws = Workspace(tmp_path / "inner")

    with pytest.raises(PathOutsideWorkspaceError):
        ws.resolve(str(tmp_path / "outside.txt"))


def test_root_itself_is_allowed(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    assert ws.resolve(".") == tmp_path.resolve()


def test_reject_workspace_private_metadata(tmp_path: Path) -> None:
    (tmp_path / ".plato").mkdir()
    ws = Workspace(tmp_path)

    with pytest.raises(PathProtectedWorkspaceError):
        ws.resolve(".plato/workspace.sqlite")


@pytest.mark.parametrize("dirname", [".taskweavn", ".code-agent"])
def test_reject_legacy_workspace_private_metadata(
    tmp_path: Path,
    dirname: str,
) -> None:
    (tmp_path / dirname).mkdir()
    ws = Workspace(tmp_path)

    with pytest.raises(PathProtectedWorkspaceError):
        ws.resolve(f"{dirname}/workspace.sqlite")
