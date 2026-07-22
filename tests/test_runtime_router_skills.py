"""Runtime Router skill artifact tests."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

importlib.import_module("taskweavn.context")

_skills = importlib.import_module("taskweavn.skills")
SkillRegistry = _skills.SkillRegistry
SkillRegistryConfig = _skills.SkillRegistryConfig
SkillRootConfig = _skills.SkillRootConfig


RUNTIME_SKILLS_ROOT = Path(__file__).parents[1] / "src" / "taskweavn" / "runtime_skills"

EXPECTED_ROUTER_SKILL_IDS = {
    "internal:router-core",
    "internal:router-control-commands",
    "internal:router-read-only-inquiry",
    "internal:router-task-authoring",
    "internal:router-wechat-send",
}


def test_runtime_router_skills_are_scannable_with_stable_ids() -> None:
    registry = SkillRegistry.scan(
        SkillRegistryConfig(
            roots=(
                SkillRootConfig(
                    root_path=RUNTIME_SKILLS_ROOT,
                    source_scope="internal",
                    trust_level="trusted",
                ),
            ),
            workspace_id="workspace-1",
        )
    )

    descriptors = registry.list_descriptors()
    descriptor_ids = {descriptor.skill_id for descriptor in descriptors}

    assert registry.snapshot.warnings == ()
    assert descriptor_ids >= EXPECTED_ROUTER_SKILL_IDS
    for descriptor in descriptors:
        if descriptor.skill_id in EXPECTED_ROUTER_SKILL_IDS:
            assert descriptor.source_scope == "internal"
            assert descriptor.trust_level == "trusted"
            assert descriptor.enabled is True
            assert descriptor.implicit_invocation is True
            assert "runtime_input_router" in descriptor.context_requirements


def test_runtime_router_skill_manifests_match_frontmatter_ids() -> None:
    for skill_dir in sorted(RUNTIME_SKILLS_ROOT.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        manifest_file = skill_dir / "manifest.json"

        assert skill_file.exists(), skill_dir
        assert manifest_file.exists(), skill_dir

        frontmatter = skill_file.read_text(encoding="utf-8").split("---", 2)[1]
        skill_id_line = next(
            line for line in frontmatter.splitlines() if line.startswith("skill_id:")
        )
        frontmatter_skill_id = skill_id_line.split(":", 1)[1].strip()
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

        assert manifest["schemaVersion"] == "plato.runtime_skill.v1"
        assert manifest["skillId"] == frontmatter_skill_id


def test_wechat_router_skill_requires_confirmation_and_slots() -> None:
    manifest = json.loads(
        (RUNTIME_SKILLS_ROOT / "router-wechat-send" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["kind"] == "router_capability"
    assert manifest["capabilities"] == ["communication.wechat.send_message"]
    assert manifest["requiredSlots"] == ["contactDisplayName", "messageText"]
    assert manifest["riskLevel"] == "high"
    assert manifest["requiresHumanConfirmation"] is True
    assert "execution_handoff" in manifest["allowedDispatchTargets"]
