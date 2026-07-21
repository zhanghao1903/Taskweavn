"""Adapt the packaged ``wechat-use`` skill to Plato skill governance."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from importlib.metadata import version

from wechat_desktop_tool import load_wechat_use_skill

from taskweavn.skills.models import (
    SkillDescriptor,
    SkillResourceRef,
    SkillToolPolicy,
)
from taskweavn.wechat_task_types import WECHAT_SEND_CAPABILITY

WECHAT_USE_SKILL_ID = "managed:wechat-use"


@lru_cache(maxsize=1)
def wechat_use_skill_descriptor() -> SkillDescriptor:
    """Load the installed package skill as a trusted execution descriptor."""

    skill = load_wechat_use_skill()
    package_version = version("wechat-desktop-tool")
    source_ref = (
        f"pypi://wechat-desktop-tool/{package_version}/skills/"
        f"{skill.name}@{skill.version}"
    )
    return SkillDescriptor(
        skill_id=WECHAT_USE_SKILL_ID,
        name=skill.name,
        description=skill.description,
        source_scope="managed",
        source_ref=source_ref,
        instruction_body=skill.instructions,
        content_hash=_skill_content_hash(skill.to_dict()),
        trust_level="trusted",
        tool_policy=SkillToolPolicy(
            requested_tools=("wechat_desktop",),
            denied_tools=("computer_use",),
        ),
        context_requirements=("execution_agent", WECHAT_SEND_CAPABILITY),
        resource_refs=tuple(
            SkillResourceRef(
                ref_id=f"{WECHAT_USE_SKILL_ID}:{item.path}",
                kind="reference",
                path=f"{source_ref}/{item.path}",
                content_hash=f"sha256:{item.sha256}",
                can_act_as_instruction=True,
            )
            for item in skill.files
            if item.path.startswith("references/")
        ),
        risk_tags=("external_message", "computer_use", "private_data"),
        output_contract=(
            "Use only registered wechat_desktop semantic operations and preserve "
            "structured status, failure, send-attempt, and recovery evidence."
        ),
    )


def _skill_content_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


__all__ = ["WECHAT_USE_SKILL_ID", "wechat_use_skill_descriptor"]
