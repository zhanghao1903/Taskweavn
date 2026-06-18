"""Context Manager source for Contract Revision guidance facts."""

from __future__ import annotations

from dataclasses import dataclass

from taskweavn.context.models import ContextBuildRequest, ExecutionGuidance
from taskweavn.context.sources import ExecutionGuidanceSource
from taskweavn.contract_revision.guidance_store import GuidanceFactStore


@dataclass(frozen=True)
class ContractGuidanceContextSource:
    """Load typed guidance facts as bounded execution guidance."""

    guidance_store: GuidanceFactStore
    max_guidance_items: int = 20

    def collect(self, request: ContextBuildRequest) -> ExecutionGuidance:
        facts = self.guidance_store.list_for_scope(
            session_id=request.session_id,
            task_node_id=request.task_id,
            limit=self.max_guidance_items,
        )
        project_rules: list[str] = []
        output_requirements: list[str] = []
        for fact in facts:
            entry = f"[{fact.scope_kind}/{fact.guidance_kind}] {fact.guidance_text}"
            if fact.guidance_kind in {"constraint", "instruction", "correction"}:
                project_rules.append(entry)
            else:
                output_requirements.append(entry)
        return ExecutionGuidance(
            project_rules=tuple(project_rules),
            output_requirements=tuple(output_requirements),
        )


@dataclass(frozen=True)
class MergedGuidanceContextSource:
    """Merge multiple ExecutionGuidance sources deterministically."""

    sources: tuple[ExecutionGuidanceSource, ...]

    def collect(self, request: ContextBuildRequest) -> ExecutionGuidance:
        merged = ExecutionGuidance()
        for source in self.sources:
            extra = source.collect(request)
            merged = ExecutionGuidance(
                project_rules=_ordered_union(
                    merged.project_rules,
                    extra.project_rules,
                ),
                active_skills=(*merged.active_skills, *extra.active_skills),
                output_requirements=_ordered_union(
                    merged.output_requirements,
                    extra.output_requirements,
                ),
            )
        return merged


def _ordered_union(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    values: list[str] = []
    for item in (*left, *right):
        if item in seen:
            continue
        seen.add(item)
        values.append(item)
    return tuple(values)


__all__ = ["ContractGuidanceContextSource", "MergedGuidanceContextSource"]
