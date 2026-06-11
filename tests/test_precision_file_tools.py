"""Tests for Product 1.1 precision file tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.runtime import LocalRuntime
from taskweavn.tools import (
    AppendFileAction,
    AppendFileTool,
    PrecisionFileContentHash,
    PrecisionFileMutationObservation,
    ReadFileRangeAction,
    ReadFileRangeTool,
    ReplaceFileRangeAction,
    ReplaceFileRangeTool,
    SearchWorkspaceAction,
    SearchWorkspaceTool,
    Workspace,
    WorkspaceSearchObservation,
)
from taskweavn.types import ErrorObservation
from taskweavn.workspace_inspection import (
    SqliteInspectionEvidenceStore,
    SqlitePrecisionFileOperationStore,
    WorkspaceContentHash,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def _hash_for(path: Path) -> PrecisionFileContentHash:
    current = WorkspaceContentHash.from_bytes(path.read_bytes())
    return PrecisionFileContentHash(value=current.value)


def test_read_file_range_returns_lines_and_hashes(workspace: Workspace) -> None:
    target = workspace.root / "notes.md"
    target.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    obs = ReadFileRangeTool(workspace).execute(
        ReadFileRangeAction(path="notes.md", start_line=2, line_count=2)
    )

    assert obs.path == "notes.md"
    assert obs.start_line == 2
    assert obs.end_line == 3
    assert [line["text"] for line in obs.lines] == ["two", "three"]
    assert obs.content_hash["algorithm"] == "sha256"
    assert obs.range_hash["algorithm"] == "sha256"


def test_search_workspace_finds_literal_and_skips_private_metadata(
    workspace: Workspace,
) -> None:
    (workspace.root / "src").mkdir()
    (workspace.root / "src" / "app.ts").write_text(
        "export const title = 'Plato';\n",
        encoding="utf-8",
    )
    (workspace.root / ".plato").mkdir()
    (workspace.root / ".plato" / "secret.txt").write_text(
        "Plato should be ignored\n",
        encoding="utf-8",
    )

    obs = SearchWorkspaceTool(workspace).execute(
        SearchWorkspaceAction(query="Plato", mode="literal")
    )

    assert isinstance(obs, WorkspaceSearchObservation)
    assert [match["file"]["relativePath"] for match in obs.matches] == ["src/app.ts"]
    assert obs.summary["matchCount"] == 1


def test_replace_file_range_writes_evidence_and_supports_replay(
    workspace: Workspace,
) -> None:
    target = workspace.root / "src.py"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    db_path = workspace.root / ".plato" / "inspection.sqlite"
    tool = ReplaceFileRangeTool(
        workspace,
        workspace_id="session:s1",
        inspection_db_path=db_path,
    )
    action = ReplaceFileRangeAction(
        operation_id="op-replace-1",
        path="src.py",
        start_line=2,
        end_line=2,
        replacement_text="BETA",
        expected_content_hash=_hash_for(target),
    )

    first = tool.execute(action)
    second = tool.execute(action)

    assert isinstance(first, PrecisionFileMutationObservation)
    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"
    assert first.replayed is False
    assert second.replayed is True
    assert first.evidence_ref["evidenceId"] == second.evidence_ref["evidenceId"]
    evidence = SqliteInspectionEvidenceStore(db_path).get(
        first.evidence_ref["evidenceId"]
    )
    assert evidence["kind"] == "line_replace_snapshot"
    operation = SqlitePrecisionFileOperationStore(db_path).get("op-replace-1")
    assert operation is not None
    assert operation["status"] == "completed"


def test_replace_file_range_rejects_stale_hash_via_runtime(
    workspace: Workspace,
) -> None:
    target = workspace.root / "src.py"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    stale_hash = _hash_for(target)
    target.write_text("alpha\nchanged\n", encoding="utf-8")

    runtime = LocalRuntime()
    ReplaceFileRangeTool(workspace).register(runtime)
    obs = runtime.execute(
        ReplaceFileRangeAction(
            operation_id="op-stale-1",
            path="src.py",
            start_line=2,
            end_line=2,
            replacement_text="BETA",
            expected_content_hash=stale_hash,
        )
    )

    assert isinstance(obs, ErrorObservation)
    assert obs.error_type == "execution_error"
    assert "workspace.file_drift" in obs.message
    assert target.read_text(encoding="utf-8") == "alpha\nchanged\n"


def test_append_file_is_idempotent_and_conflicts_on_changed_request(
    workspace: Workspace,
) -> None:
    target = workspace.root / "notes.txt"
    target.write_text("one", encoding="utf-8")
    db_path = workspace.root / ".plato" / "inspection.sqlite"
    tool = AppendFileTool(workspace, inspection_db_path=db_path)
    action = AppendFileAction(
        operation_id="op-append-1",
        path="notes.txt",
        content="two\n",
        expected_content_hash=_hash_for(target),
    )

    first = tool.execute(action)
    second = tool.execute(action)

    assert first.replayed is False
    assert second.replayed is True
    assert first.changed_line_ranges == [{"startLine": 2, "endLine": 2}]
    assert target.read_text(encoding="utf-8") == "one\ntwo\n"

    runtime = LocalRuntime()
    AppendFileTool(workspace, inspection_db_path=db_path).register(runtime)
    conflict = runtime.execute(
        AppendFileAction(
            operation_id="op-append-1",
            path="notes.txt",
            content="three\n",
            expected_content_hash=_hash_for(target),
        )
    )
    assert isinstance(conflict, ErrorObservation)
    assert "operation id reused" in conflict.message


def test_precision_tools_reject_private_metadata_path(workspace: Workspace) -> None:
    (workspace.root / ".plato").mkdir()
    (workspace.root / ".plato" / "workspace.sqlite").write_text(
        "private",
        encoding="utf-8",
    )
    runtime = LocalRuntime()
    ReadFileRangeTool(workspace).register(runtime)

    obs = runtime.execute(
        ReadFileRangeAction(path=".plato/workspace.sqlite", start_line=1)
    )

    assert isinstance(obs, ErrorObservation)
    assert "workspace metadata is protected" in obs.message
