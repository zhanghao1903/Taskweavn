"""Skill governance policy helpers."""

from __future__ import annotations

from taskweavn.context.models import ExecutionControls
from taskweavn.skills.models import (
    SkillDescriptor,
    SkillPermissionMergeResult,
    SkillPermissionOutcome,
    SkillPermissionOutcomeKind,
)


def merge_skill_controls(
    *,
    base: ExecutionControls,
    descriptor: SkillDescriptor,
) -> SkillPermissionMergeResult:
    """Merge skill tool policy into runtime controls without granting authority."""

    outcomes: list[SkillPermissionOutcome] = []
    if descriptor.trust_level == "untrusted":
        outcomes.append(
            SkillPermissionOutcome(
                kind="blocked_untrusted_skill",
                skill_id=descriptor.skill_id,
                reason="skill trust level is untrusted",
            )
        )
        return SkillPermissionMergeResult(controls=base, outcomes=tuple(outcomes))

    base_allowed = set(base.allowed_tools)
    base_denied = set(base.denied_tools)
    skill_denied = set(descriptor.tool_policy.denied_tools)
    requested = set(descriptor.tool_policy.requested_tools)
    effective_allowed = tuple(
        tool for tool in base.allowed_tools if tool not in skill_denied
    )
    effective_denied = _ordered_union(base.denied_tools, descriptor.tool_policy.denied_tools)
    for tool in descriptor.tool_policy.denied_tools:
        kind: SkillPermissionOutcomeKind = (
            "narrowed_by_skill" if tool in base_allowed else "denied_by_skill"
        )
        outcomes.append(
            SkillPermissionOutcome(
                kind=kind,
                skill_id=descriptor.skill_id,
                tool=tool,
                reason="skill explicitly denies this tool",
            )
        )
    for tool in descriptor.tool_policy.requested_tools:
        if tool in base_denied:
            outcomes.append(
                SkillPermissionOutcome(
                    kind="denied_by_runtime",
                    skill_id=descriptor.skill_id,
                    tool=tool,
                    reason="runtime denies this tool",
                )
            )
            continue
        if tool in skill_denied:
            outcomes.append(
                SkillPermissionOutcome(
                    kind="denied_by_skill",
                    skill_id=descriptor.skill_id,
                    tool=tool,
                    reason="skill denies this requested tool",
                )
            )
            continue
        if tool not in base_allowed:
            outcomes.append(
                SkillPermissionOutcome(
                    kind="denied_by_runtime",
                    skill_id=descriptor.skill_id,
                    tool=tool,
                    reason="runtime did not grant this requested tool",
                )
            )
            continue
        outcomes.append(
            SkillPermissionOutcome(
                kind="granted_by_runtime",
                skill_id=descriptor.skill_id,
                tool=tool,
                reason="requested tool was already allowed by runtime",
            )
        )
    for tool in descriptor.tool_policy.requires_approval:
        if tool in requested or not requested:
            outcomes.append(
                SkillPermissionOutcome(
                    kind="approval_required_by_skill",
                    skill_id=descriptor.skill_id,
                    tool=tool,
                    reason="skill requires approval for this tool/action",
                )
            )
    effective_requires_approval = _ordered_union(
        base.requires_approval,
        descriptor.tool_policy.requires_approval,
    )
    effective_file_scopes = _merge_file_scopes(
        base.file_scopes,
        descriptor.tool_policy.file_scopes,
    )
    controls = ExecutionControls(
        allowed_tools=effective_allowed,
        denied_tools=effective_denied,
        requires_approval=effective_requires_approval,
        pending_approval=base.pending_approval,
        file_scopes=effective_file_scopes,
    )
    return SkillPermissionMergeResult(controls=controls, outcomes=tuple(outcomes))


def denied_required_tools(result: SkillPermissionMergeResult) -> tuple[str, ...]:
    return tuple(
        outcome.tool
        for outcome in result.outcomes
        if outcome.kind == "denied_by_runtime" and outcome.tool is not None
    )


def _ordered_union(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for item in (*left, *right):
        if item not in values:
            values.append(item)
    return tuple(values)


def _merge_file_scopes(base: tuple[str, ...], skill: tuple[str, ...]) -> tuple[str, ...]:
    if base and skill:
        skill_set = set(skill)
        return tuple(scope for scope in base if scope in skill_set)
    if base:
        return base
    return skill
