"""Skill governance contracts for Product 1.1."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field

from taskweavn.context.models import ContextModel, ExecutionControls, ExecutionGuidance

SkillSourceScope = Literal["internal", "repo", "workspace", "user", "managed"]
SkillTrustLevel = Literal["trusted", "repo_trusted", "user_trusted", "untrusted"]
SkillActivationTrigger = Literal[
    "explicit_user",
    "task_capability_match",
    "router_or_collaborator",
    "policy_required",
    "agent_requested",
]
SkillActivationScope = Literal["task_run", "session", "workflow"]
SkillActivationStatus = Literal[
    "candidate",
    "policy_checked",
    "active",
    "blocked",
    "completed",
    "expired",
]
SkillPermissionOutcomeKind = Literal[
    "granted_by_runtime",
    "narrowed_by_skill",
    "approval_required_by_skill",
    "denied_by_runtime",
    "denied_by_skill",
    "blocked_untrusted_skill",
]
SkillResourceKind = Literal["reference", "script", "asset", "template"]


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_skill_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class SkillModel(ContextModel):
    """Base model for immutable skill governance contracts."""


class SkillResourceRef(SkillModel):
    ref_id: str = Field(min_length=1)
    kind: SkillResourceKind
    path: str = Field(min_length=1)
    description: str | None = None
    content_hash: str | None = None
    can_act_as_instruction: bool = False


class SkillToolPolicy(SkillModel):
    requested_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    requires_approval: tuple[str, ...] = ()
    file_scopes: tuple[str, ...] = ()


class SkillDescriptor(SkillModel):
    skill_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_scope: SkillSourceScope
    source_ref: str = Field(min_length=1)
    root_path: str | None = None
    skill_file_path: str | None = None
    instruction_body: str | None = None
    content_hash: str = Field(min_length=1)
    enabled: bool = True
    implicit_invocation: bool = True
    trust_level: SkillTrustLevel
    tool_policy: SkillToolPolicy = Field(default_factory=SkillToolPolicy)
    context_requirements: tuple[str, ...] = ()
    resource_refs: tuple[SkillResourceRef, ...] = ()
    risk_tags: tuple[str, ...] = ()
    output_contract: str | None = None


class SkillRegistrySnapshot(SkillModel):
    registry_id: str = Field(default_factory=lambda: new_skill_id("skill_registry"))
    workspace_id: str | None = None
    descriptors: tuple[SkillDescriptor, ...]
    scanned_at: datetime = Field(default_factory=utcnow)
    warnings: tuple[str, ...] = ()


class SkillActivation(SkillModel):
    activation_id: str = Field(default_factory=lambda: new_skill_id("skill_activation"))
    session_id: str = Field(min_length=1)
    task_id: str | None = Field(default=None, min_length=1)
    agent_run_id: str | None = Field(default=None, min_length=1)
    skill_id: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    activated_by: SkillActivationTrigger
    activation_reason: str = Field(min_length=1)
    trigger_ref: str | None = Field(default=None, min_length=1)
    scope: SkillActivationScope = "task_run"
    status: SkillActivationStatus = "candidate"
    budget_chars: int = Field(default=12_000, ge=0)
    loaded_sections: tuple[str, ...] = ()
    loaded_resource_refs: tuple[str, ...] = ()
    denied_requirements: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime | None = None


class SkillContextSegment(SkillModel):
    activation_id: str = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    activation_reason: str = Field(min_length=1)
    rendered_summary: str = Field(min_length=1)
    rendered_instruction_excerpt: str | None = None
    loaded_resource_refs: tuple[str, ...] = ()
    char_estimate: int = Field(default=0, ge=0)
    token_estimate: int = Field(default=0, ge=0)
    truncated: bool = False
    truncation_reason: str | None = None


class SkillPermissionOutcome(SkillModel):
    kind: SkillPermissionOutcomeKind
    skill_id: str = Field(min_length=1)
    tool: str | None = None
    reason: str = Field(min_length=1)


class SkillPermissionMergeResult(SkillModel):
    controls: ExecutionControls
    outcomes: tuple[SkillPermissionOutcome, ...] = ()


class SkillContextBudget(SkillModel):
    max_skill_index_chars: int = Field(default=8_000, ge=0)
    max_active_skill_summary_chars: int = Field(default=2_000, ge=0)
    max_active_skill_body_chars: int = Field(default=12_000, ge=0)
    max_skill_resource_chars: int = Field(default=16_000, ge=0)


class SkillContextSourceResult(SkillModel):
    guidance: ExecutionGuidance
    segments: tuple[SkillContextSegment, ...] = ()
    permission_merge: SkillPermissionMergeResult | None = None
