"""Tests for filesystem tools (1.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.runtime import LocalRuntime
from taskweavn.tools import (
    DirListingObservation,
    FileContentObservation,
    FileWriteObservation,
    ListDirAction,
    ListDirTool,
    PathOutsideWorkspaceError,
    ReadFileAction,
    ReadFileTool,
    Workspace,
    WriteFileAction,
    WriteFileTool,
)
from taskweavn.types import ErrorObservation


@pytest.fixture()
def workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def test_read_file_returns_content(workspace: Workspace) -> None:
    (workspace.root / "hello.txt").write_text("hi there")
    obs = ReadFileTool(workspace).execute(ReadFileAction(path="hello.txt"))

    assert isinstance(obs, FileContentObservation)
    assert obs.content == "hi there"
    assert obs.bytes_read == 8
    assert obs.path == "hello.txt"


def test_read_file_via_runtime_path_traversal_becomes_error(
    workspace: Workspace,
) -> None:
    rt = LocalRuntime()
    ReadFileTool(workspace).register(rt)
    obs = rt.execute(ReadFileAction(path="../escape.txt"))

    assert isinstance(obs, ErrorObservation)
    assert obs.error_type == "execution_error"
    assert "outside" in obs.message.lower()


def test_read_file_direct_traversal_raises(workspace: Workspace) -> None:
    with pytest.raises(PathOutsideWorkspaceError):
        ReadFileTool(workspace).execute(ReadFileAction(path="../escape.txt"))


def test_write_file_creates_new_file(workspace: Workspace) -> None:
    obs = WriteFileTool(workspace).execute(
        WriteFileAction(path="out/note.txt", content="hello")
    )

    assert isinstance(obs, FileWriteObservation)
    assert obs.created is True
    assert obs.bytes_written == 5
    assert (workspace.root / "out" / "note.txt").read_text() == "hello"


def test_write_file_overwrites(workspace: Workspace) -> None:
    target = workspace.root / "x.txt"
    target.write_text("old")
    obs = WriteFileTool(workspace).execute(
        WriteFileAction(path="x.txt", content="new")
    )
    assert obs.created is False
    assert target.read_text() == "new"


def test_write_file_skips_parent_creation_when_disabled(
    workspace: Workspace,
) -> None:
    rt = LocalRuntime()
    WriteFileTool(workspace).register(rt)
    obs = rt.execute(
        WriteFileAction(
            path="missing/dir/x.txt",
            content="hi",
            create_parents=False,
        )
    )
    assert isinstance(obs, ErrorObservation)
    assert obs.error_type == "execution_error"


def test_list_dir_returns_sorted_entries(workspace: Workspace) -> None:
    (workspace.root / "a.txt").write_text("a")
    (workspace.root / "b.txt").write_text("bb")
    (workspace.root / "subdir").mkdir()

    obs = ListDirTool(workspace).execute(ListDirAction(path="."))
    assert isinstance(obs, DirListingObservation)

    names = [entry.name for entry in obs.entries]
    # Directories first, then files alphabetically.
    assert names == ["subdir", "a.txt", "b.txt"]
    sizes = {entry.name: entry.size for entry in obs.entries}
    assert sizes["a.txt"] == 1
    assert sizes["b.txt"] == 2
    assert sizes["subdir"] is None


def test_list_dir_on_file_errors(workspace: Workspace) -> None:
    (workspace.root / "f.txt").write_text("x")
    rt = LocalRuntime()
    ListDirTool(workspace).register(rt)
    obs = rt.execute(ListDirAction(path="f.txt"))
    assert isinstance(obs, ErrorObservation)
    assert obs.error_type == "execution_error"
