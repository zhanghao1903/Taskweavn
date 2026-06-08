"""Tests for Collaborator read/search workspace context source."""

from __future__ import annotations

from pathlib import Path

from taskweavn.task import (
    AuthoringReadWorkspaceRequest,
    AuthoringSearchWorkspaceRequest,
    AuthoringSearchWorkspaceScope,
    CollaboratorWorkspaceContextSource,
    InMemoryAuthoringEvidenceStore,
    LocalCollaboratorWorkspaceContextSource,
)


def test_local_workspace_context_source_protocol_conformance(tmp_path: Path) -> None:
    store = InMemoryAuthoringEvidenceStore()
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=store,
    )

    assert isinstance(source, CollaboratorWorkspaceContextSource)


def test_read_workspace_returns_bounded_snippet_and_evidence(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Product 1.0 guidance\nMore detail", encoding="utf-8")
    store = InMemoryAuthoringEvidenceStore()
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=store,
    )

    observation = source.read_workspace(
        session_id="s1",
        loop_id="loop-1",
        request=AuthoringReadWorkspaceRequest(
            paths=("README.md",),
            purpose="Inspect guidance",
            max_snippet_chars=12,
        ),
    )

    file = observation.files[0]
    record = store.get("s1", file.evidence_ref)
    assert observation.evidence_refs == (file.evidence_ref,)
    assert file.path_label == "workspace://current/README.md"
    assert file.content_snippet == "Product 1.0 "
    assert file.content_hash is not None
    assert record is not None
    assert record.path_label == file.path_label
    assert record.snippet == file.content_snippet
    assert record.policy_decision == "allowed"


def test_read_workspace_accepts_safe_labels(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plan.md").write_text("Plan content", encoding="utf-8")
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=InMemoryAuthoringEvidenceStore(),
    )

    observation = source.read_workspace(
        session_id="s1",
        loop_id="loop-1",
        request=AuthoringReadWorkspaceRequest(
            paths=("workspace://current/docs/plan.md",),
            purpose="Inspect selected plan",
        ),
    )

    assert observation.files[0].path_label == "workspace://current/docs/plan.md"
    assert observation.files[0].content_snippet == "Plan content"


def test_read_workspace_protects_taskweavn_metadata(tmp_path: Path) -> None:
    (tmp_path / ".plato").mkdir()
    (tmp_path / ".plato" / "secret.json").write_text("secret", encoding="utf-8")
    store = InMemoryAuthoringEvidenceStore()
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=store,
    )

    observation = source.read_workspace(
        session_id="s1",
        loop_id="loop-1",
        request=AuthoringReadWorkspaceRequest(
            paths=(".plato/secret.json",),
            purpose="Inspect hidden state",
        ),
    )

    file = observation.files[0]
    record = store.get("s1", file.evidence_ref)
    assert file.content_snippet is None
    assert file.omitted_reason is not None
    assert file.path_label == "workspace://current/.plato/secret.json"
    assert record is not None
    assert record.policy_decision == "denied"
    assert record.snippet is None


def test_read_workspace_redacts_raw_absolute_request_path(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("Guidance", encoding="utf-8")
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=InMemoryAuthoringEvidenceStore(),
    )

    observation = source.read_workspace(
        session_id="s1",
        loop_id="loop-1",
        request=AuthoringReadWorkspaceRequest(
            paths=(str(readme),),
            purpose="Inspect guidance",
        ),
    )

    file = observation.files[0]
    assert file.content_snippet is None
    assert file.path_label == "workspace://current/<absolute-path-redacted>"
    assert "raw absolute paths" in (file.omitted_reason or "")
    assert str(tmp_path) not in file.path_label


def test_search_workspace_uses_guidance_scope_and_records_evidence(tmp_path: Path) -> None:
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "plans" / "feature.md").write_text(
        "Acceptance criteria mention collaborator evidence.",
        encoding="utf-8",
    )
    (tmp_path / "notes.txt").write_text(
        "Acceptance criteria outside guidance.",
        encoding="utf-8",
    )
    store = InMemoryAuthoringEvidenceStore()
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=store,
    )

    observation = source.search_workspace(
        session_id="s1",
        loop_id="loop-1",
        request=AuthoringSearchWorkspaceRequest(
            query="collaborator evidence",
            scope=AuthoringSearchWorkspaceScope(path_globs=("docs/plans/**",)),
            max_results=5,
            max_snippet_chars=30,
            purpose="Find accepted plan evidence",
        ),
    )

    result = observation.results[0]
    record = store.get("s1", result.evidence_ref)
    assert result.path_label == "workspace://current/docs/plans/feature.md"
    assert "collaborator evidence" in (result.match_snippet or "")
    assert record is not None
    assert record.operation == "search_workspace"
    assert record.tool_name == "authoring_search_workspace"
    assert record.path_label == result.path_label


def test_search_workspace_skips_full_workspace_glob(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("needle", encoding="utf-8")
    source = LocalCollaboratorWorkspaceContextSource(
        workspace_root=tmp_path,
        evidence_store=InMemoryAuthoringEvidenceStore(),
    )

    observation = source.search_workspace(
        session_id="s1",
        loop_id="loop-1",
        request=AuthoringSearchWorkspaceRequest(
            query="needle",
            scope=AuthoringSearchWorkspaceScope(path_globs=("**/*",)),
            purpose="Avoid full workspace crawl",
        ),
    )

    assert observation.evidence_refs == ()
    assert observation.results == ()
