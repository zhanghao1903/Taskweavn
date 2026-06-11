"""Tests for Product 1.1 Skill Governance primitives."""

from __future__ import annotations

from pathlib import Path

from taskweavn.context import (
    ContextBuildRequest,
    ControlContextSource,
    InMemoryContextStore,
    SessionContextManager,
    SqliteContextStore,
    TaskContextSource,
)
from taskweavn.core import SessionManager, WorkspaceLayout
from taskweavn.diagnostics import DiagnosticBundleExporter, DiagnosticExportOptions
from taskweavn.skills import (
    InMemorySkillActivationStore,
    SkillActivation,
    SkillContextSource,
    SkillDescriptor,
    SkillRegistry,
    SkillRegistryConfig,
    SkillRootConfig,
    SkillToolPolicy,
    SqliteSkillActivationStore,
    merge_skill_controls,
    precision_file_editing_descriptor,
)
from taskweavn.task import InMemoryTaskBus, TaskDomain


def test_skill_registry_scans_only_configured_roots(tmp_path: Path) -> None:
    skill_root = tmp_path / "runtime-skills"
    skill_dir = skill_root / "precision"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: Precision Editing
description: Prefer bounded line edits for coding tasks.
context_requirements:
  - coding
requested_tools:
  - read_file_range
requires_approval:
  - replace_file_range
output_contract: Report changed line ranges.
---

Use line-scoped reads before writes.
""",
        encoding="utf-8",
    )
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("Reference notes.", encoding="utf-8")
    ignored = tmp_path / ".agents" / "skills" / "dev-skill"
    ignored.mkdir(parents=True)
    (ignored / "SKILL.md").write_text(
        "---\nname: Dev Skill\ndescription: Must not be scanned.\n---\n",
        encoding="utf-8",
    )

    registry = SkillRegistry.scan(
        SkillRegistryConfig(
            roots=(SkillRootConfig(root_path=skill_root, source_scope="repo"),),
            workspace_id="workspace-1",
        )
    )

    descriptors = registry.list_descriptors()
    assert len(descriptors) == 1
    assert descriptors[0].name == "Precision Editing"
    assert descriptors[0].source_scope == "repo"
    assert descriptors[0].tool_policy.requested_tools == ("read_file_range",)
    assert descriptors[0].resource_refs[0].path == "references/guide.md"
    assert registry.find_candidates("coding")[0] == descriptors[0]
    assert "Dev Skill" not in {descriptor.name for descriptor in descriptors}


def test_sqlite_skill_activation_store_round_trips_active_activation(
    tmp_path: Path,
) -> None:
    descriptor = precision_file_editing_descriptor()
    activation = SkillActivation(
        session_id="session-1",
        task_id="task-1",
        agent_run_id="run-1",
        skill_id=descriptor.skill_id,
        content_hash=descriptor.content_hash,
        activated_by="explicit_user",
        activation_reason="test activation",
        status="active",
    )

    with SqliteSkillActivationStore(tmp_path / "skills.sqlite") as store:
        store.save(activation)

    with SqliteSkillActivationStore(tmp_path / "skills.sqlite") as store:
        assert store.get(activation.activation_id) == activation
        assert store.list_for_context(
            session_id="session-1",
            task_id="task-1",
            agent_run_id="run-1",
        ) == (activation,)


def test_skill_permission_policy_never_grants_and_can_narrow_runtime_tools() -> None:
    descriptor = SkillDescriptor(
        skill_id="repo:review",
        name="Review Only",
        description="Review without writes.",
        source_scope="repo",
        source_ref="repo://review",
        content_hash="sha256:review",
        trust_level="repo_trusted",
        tool_policy=SkillToolPolicy(
            requested_tools=("read_file", "write_file"),
            denied_tools=("write_file",),
            requires_approval=("write_file",),
        ),
    )
    result = merge_skill_controls(
        base=ControlContextSource(
            allowed_tools=("read_file", "write_file"),
            denied_tools=("delete_file",),
        ).collect(ContextBuildRequest(session_id="session-1", task_id="task-1")),
        descriptor=descriptor,
    )

    assert result.controls.allowed_tools == ("read_file",)
    assert result.controls.denied_tools == ("delete_file", "write_file")
    assert result.controls.requires_approval == ("write_file",)
    assert {outcome.kind for outcome in result.outcomes} >= {
        "granted_by_runtime",
        "narrowed_by_skill",
        "denied_by_skill",
        "approval_required_by_skill",
    }


def test_skill_context_source_auto_activates_matching_skill_and_traces_it() -> None:
    descriptor = precision_file_editing_descriptor()
    registry = SkillRegistry.from_descriptors((descriptor,))
    activation_store = InMemorySkillActivationStore()
    context_store = InMemoryContextStore()
    bus = InMemoryTaskBus([_task(required_capability="precision_file_tools")])
    manager = SessionContextManager(
        task_source=TaskContextSource(bus),
        control_source=ControlContextSource(
            allowed_tools=(
                "read_file_range",
                "search_workspace",
                "replace_file_range",
                "append_file",
            )
        ),
        skill_source=SkillContextSource(registry, activation_store),
        store=context_store,
    )

    result = manager.build(
        ContextBuildRequest(
            session_id="session-1",
            task_id="task-1",
            agent_run_id="run-1",
            render_mode="start_context",
        )
    )

    assert result.context.guidance.active_skills[0].name == "precision-file-editing"
    assert result.context.controls.requires_approval == ("replace_file_range", "append_file")
    assert result.trace.active_skill_ids == ("internal:precision-file-editing",)
    assert result.trace.skill_activation_ids
    assert result.trace.skill_context_segment_hashes
    assert any(
        outcome.kind == "approval_required_by_skill"
        for outcome in result.trace.skill_permission_outcomes
    )
    assert "precision-file-editing" in result.rendered.user_content
    assert "Prefer line-scoped file operations" in result.rendered.user_content
    assert context_store.get_trace(result.trace.trace_id) == result.trace


def test_skill_context_source_blocks_activation_when_runtime_denies_required_tool() -> None:
    descriptor = precision_file_editing_descriptor()
    registry = SkillRegistry.from_descriptors((descriptor,))
    activation_store = InMemorySkillActivationStore()
    source = SkillContextSource(registry, activation_store)

    result = source.collect(
        ContextBuildRequest(session_id="session-1", task_id="task-1", agent_run_id="run-1"),
        controls=ControlContextSource().collect(
            ContextBuildRequest(session_id="session-1", task_id="task-1", agent_run_id="run-1")
        ),
        required_capability="precision_file_tools",
    )

    assert result.guidance.active_skills == ()
    assert result.segments == ()
    blocked = activation_store.list_for_context(
        session_id="session-1",
        task_id="task-1",
        agent_run_id="run-1",
        statuses=("blocked",),
    )
    assert blocked[0].skill_id == descriptor.skill_id
    assert blocked[0].denied_requirements == (
        "tool:read_file_range",
        "tool:search_workspace",
        "tool:replace_file_range",
        "tool:append_file",
    )


def test_diagnostic_bundle_exports_skill_governance_summary(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path / "workspace")
    layout.bootstrap()
    with SessionManager(layout) as session_manager:
        session = session_manager.create("Skill diagnostics")

    descriptor = precision_file_editing_descriptor()
    registry = SkillRegistry.from_descriptors((descriptor,))
    activation_store = InMemorySkillActivationStore()
    bus = InMemoryTaskBus(
        [_task(session_id=session.id, required_capability="precision_file_tools")]
    )
    with SqliteContextStore(layout.session_context_db(session.id)) as context_store:
        manager = SessionContextManager(
            task_source=TaskContextSource(bus),
            control_source=ControlContextSource(
                allowed_tools=(
                    "read_file_range",
                    "search_workspace",
                    "replace_file_range",
                    "append_file",
                )
            ),
            skill_source=SkillContextSource(registry, activation_store),
            store=context_store,
        )
        manager.build(
            ContextBuildRequest(
                session_id=session.id,
                task_id="task-1",
                agent_run_id="run-1",
                render_mode="start_context",
            )
        )

    result = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=layout.root,
            session_id=session.id,
            output_dir=tmp_path / "diagnostics",
            create_zip=False,
        )
    ).export()

    summary_path = result.bundle_dir / "context/skills.summary.json"
    assert summary_path.exists()
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "Prefer line-scoped file operations" not in summary_text
    assert "precision-file-editing" in summary_text
    assert "approval_required_by_skill" in summary_text
    assert "plato.skill_governance.diagnostic_summary.v1" in summary_text


def _task(
    *,
    session_id: str = "session-1",
    required_capability: str = "general",
) -> TaskDomain:
    return TaskDomain(
        task_id="task-1",
        session_id=session_id,
        root_id="task-1",
        intent="Edit files precisely.",
        required_capability=required_capability,
        created_by="test",
    )
