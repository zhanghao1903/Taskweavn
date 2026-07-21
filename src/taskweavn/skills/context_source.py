"""Skill context source integration for SessionContextManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from taskweavn.context.models import (
    ContextBuildRequest,
    ExecutionControls,
    ExecutionGuidance,
    SkillSummary,
)
from taskweavn.context.policy import estimate_tokens
from taskweavn.skills.activation_store import SkillActivationStore
from taskweavn.skills.models import (
    SkillActivation,
    SkillActivationStatus,
    SkillContextBudget,
    SkillContextSegment,
    SkillContextSourceResult,
    SkillDescriptor,
    SkillPermissionMergeResult,
    SkillPermissionOutcome,
    utcnow,
)
from taskweavn.skills.policy import denied_required_tools, merge_skill_controls
from taskweavn.skills.registry import SkillRegistry


@dataclass(frozen=True)
class SkillContextSource:
    """Collect active Skill context through the same Context Manager boundary."""

    registry: SkillRegistry
    activation_store: SkillActivationStore
    budget: SkillContextBudget = field(default_factory=SkillContextBudget)
    activate_on_required_capability: bool = True

    def collect(
        self,
        request: ContextBuildRequest,
        *,
        controls: ExecutionControls,
        required_capability: str | None = None,
    ) -> SkillContextSourceResult:
        existing = self.activation_store.list_for_context(
            session_id=request.session_id,
            task_id=request.task_id,
            agent_run_id=request.agent_run_id,
            statuses=("active", "blocked", "candidate", "policy_checked"),
        )
        if self.activate_on_required_capability:
            self._ensure_capability_activation(
                request,
                controls=controls,
                required_capability=required_capability,
                existing=existing,
            )

        active = self.activation_store.list_for_context(
            session_id=request.session_id,
            task_id=request.task_id,
            agent_run_id=request.agent_run_id,
            statuses=("active",),
        )
        segments: list[SkillContextSegment] = []
        current_controls = controls
        outcomes: list[SkillPermissionOutcome] = []
        for activation in active:
            descriptor = self.registry.get(activation.skill_id)
            if descriptor is None or descriptor.content_hash != activation.content_hash:
                continue
            merge = merge_skill_controls(base=current_controls, descriptor=descriptor)
            current_controls = merge.controls
            outcomes.extend(merge.outcomes)
            segments.append(self._segment_for_activation(activation, descriptor))

        guidance = ExecutionGuidance(
            active_skills=tuple(_summary_from_segment(segment) for segment in segments),
            output_requirements=tuple(
                descriptor.output_contract
                for segment in segments
                if (descriptor := self.registry.get(segment.skill_id)) is not None
                and descriptor.output_contract
            ),
        )
        permission_merge = SkillPermissionMergeResult(
            controls=current_controls,
            outcomes=tuple(outcomes),
        )
        return SkillContextSourceResult(
            guidance=guidance,
            segments=tuple(segments),
            permission_merge=permission_merge,
        )

    def _ensure_capability_activation(
        self,
        request: ContextBuildRequest,
        *,
        controls: ExecutionControls,
        required_capability: str | None,
        existing: tuple[SkillActivation, ...],
    ) -> None:
        if not required_capability:
            return
        existing_skill_versions = {
            (activation.skill_id, activation.content_hash) for activation in existing
        }
        for descriptor in self.registry.find_candidates(required_capability):
            if (descriptor.skill_id, descriptor.content_hash) in existing_skill_versions:
                continue
            activation = self._build_activation(
                request,
                descriptor,
                controls=controls,
                required_capability=required_capability,
            )
            self.activation_store.save(activation)
            return

    def _build_activation(
        self,
        request: ContextBuildRequest,
        descriptor: SkillDescriptor,
        *,
        controls: ExecutionControls,
        required_capability: str,
    ) -> SkillActivation:
        merge = merge_skill_controls(base=controls, descriptor=descriptor)
        denied_tools = denied_required_tools(merge)
        status: SkillActivationStatus = "active"
        denied_requirements: tuple[str, ...] = ()
        if descriptor.trust_level == "untrusted":
            status = "blocked"
            denied_requirements = ("untrusted_skill",)
        elif denied_tools:
            status = "blocked"
            denied_requirements = tuple(f"tool:{tool}" for tool in denied_tools)
        return SkillActivation(
            session_id=request.session_id,
            task_id=request.task_id,
            agent_run_id=request.agent_run_id,
            skill_id=descriptor.skill_id,
            content_hash=descriptor.content_hash,
            activated_by="task_capability_match",
            activation_reason=f"required_capability:{required_capability}",
            trigger_ref=f"task:{request.task_id}",
            scope="task_run",
            status=status,
            budget_chars=self.budget.max_active_skill_body_chars,
            loaded_sections=("SKILL.md",) if status == "active" else (),
            loaded_resource_refs=(),
            denied_requirements=denied_requirements,
            created_at=utcnow(),
            updated_at=utcnow(),
        )

    def _segment_for_activation(
        self,
        activation: SkillActivation,
        descriptor: SkillDescriptor,
    ) -> SkillContextSegment:
        body = _load_skill_instruction_body(descriptor)
        body_budget = min(activation.budget_chars, self.budget.max_active_skill_body_chars)
        excerpt, truncated = _truncate(body, body_budget)
        summary_budget = self.budget.max_active_skill_summary_chars
        summary, summary_truncated = _truncate(
            f"{descriptor.description} Activation: {activation.activation_reason}",
            summary_budget,
        )
        text_for_estimate = "\n".join(part for part in (summary, excerpt) if part)
        return SkillContextSegment(
            activation_id=activation.activation_id,
            skill_id=descriptor.skill_id,
            name=descriptor.name,
            description=descriptor.description,
            source_ref=descriptor.source_ref,
            content_hash=descriptor.content_hash,
            activation_reason=activation.activation_reason,
            rendered_summary=summary,
            rendered_instruction_excerpt=excerpt or None,
            loaded_resource_refs=activation.loaded_resource_refs,
            char_estimate=len(text_for_estimate),
            token_estimate=estimate_tokens(text_for_estimate),
            truncated=truncated or summary_truncated,
            truncation_reason="skill_context_budget" if truncated or summary_truncated else None,
        )


def merge_guidance(base: ExecutionGuidance, extra: ExecutionGuidance) -> ExecutionGuidance:
    return ExecutionGuidance(
        project_rules=_ordered_union(base.project_rules, extra.project_rules),
        active_skills=_ordered_skill_summaries(base.active_skills, extra.active_skills),
        output_requirements=_ordered_union(base.output_requirements, extra.output_requirements),
    )


def _summary_from_segment(segment: SkillContextSegment) -> SkillSummary:
    return SkillSummary(
        name=segment.name,
        description=segment.rendered_summary,
        source_ref=segment.source_ref,
        activation_id=segment.activation_id,
        content_hash=segment.content_hash,
        instruction_excerpt=segment.rendered_instruction_excerpt,
        resource_refs=segment.loaded_resource_refs,
        truncated=segment.truncated,
    )


def _load_skill_instruction_body(descriptor: SkillDescriptor) -> str:
    if descriptor.instruction_body:
        return _strip_frontmatter(descriptor.instruction_body).strip()
    if descriptor.skill_file_path:
        path = Path(descriptor.skill_file_path)
        if path.exists() and path.is_file():
            return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()
    if descriptor.output_contract:
        return descriptor.output_contract.strip()
    return descriptor.description.strip()


def _strip_frontmatter(raw: str) -> str:
    if not raw.startswith("---\n"):
        return raw
    end = raw.find("\n---", 4)
    if end == -1:
        return raw
    return raw[end + 4 :].lstrip("\n")


def _truncate(text: str, budget: int) -> tuple[str, bool]:
    if budget <= 0:
        return "", bool(text)
    if len(text) <= budget:
        return text, False
    return text[: max(0, budget - 24)].rstrip() + "\n[truncated by skill budget]", True


def _ordered_union(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for item in (*left, *right):
        if item not in values:
            values.append(item)
    return tuple(values)


def _ordered_skill_summaries(
    left: tuple[SkillSummary, ...],
    right: tuple[SkillSummary, ...],
) -> tuple[SkillSummary, ...]:
    values: list[SkillSummary] = []
    seen: set[tuple[str, str | None]] = set()
    for item in (*left, *right):
        key = (item.name, item.source_ref)
        if key not in seen:
            values.append(item)
            seen.add(key)
    return tuple(values)
