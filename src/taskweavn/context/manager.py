"""Session-scoped Context Manager orchestration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from taskweavn.context.models import (
    ContextBuildRequest,
    ContextBuildResult,
    ContextSkillPermissionOutcome,
    ContextSkillTrace,
    ContextSnapshot,
    ContextTrace,
    ContextTraceRef,
    ExecutionFacts,
    RenderedLlmInput,
    TaskContextIdentity,
    TaskExecutionContextV0,
    new_context_id,
)
from taskweavn.context.policy import DeterministicContextPolicy
from taskweavn.context.renderer import DeterministicContextRenderer
from taskweavn.context.sources import (
    AskContextSource,
    ControlContextSource,
    EventStreamContextSource,
    ExecutionGuidanceSource,
    GuidanceContextSource,
    TaskContextSource,
    WorkspaceEvidenceContextSource,
    merge_facts,
)
from taskweavn.context.store import ContextStore, InMemoryContextStore
from taskweavn.skills.context_source import SkillContextSource, merge_guidance
from taskweavn.skills.models import SkillContextSegment


@dataclass
class SessionContextManager:
    """Build, render, and persist execution context for one Session."""

    task_source: TaskContextSource
    event_source: EventStreamContextSource | None = None
    ask_source: AskContextSource | None = None
    workspace_source: WorkspaceEvidenceContextSource = field(
        default_factory=WorkspaceEvidenceContextSource
    )
    control_source: ControlContextSource = field(default_factory=ControlContextSource)
    guidance_source: ExecutionGuidanceSource = field(default_factory=GuidanceContextSource)
    skill_source: SkillContextSource | None = None
    policy: DeterministicContextPolicy = field(default_factory=DeterministicContextPolicy)
    renderer: DeterministicContextRenderer = field(default_factory=DeterministicContextRenderer)
    store: ContextStore = field(default_factory=InMemoryContextStore)

    def build(self, request: ContextBuildRequest) -> ContextBuildResult:
        task = self.task_source.load_task(request)
        event_facts = ExecutionFacts()
        if self.event_source is not None:
            collected = self.event_source.collect(request)
            event_facts = ExecutionFacts(
                recent_events=self.policy.trim_events(collected.events, request.budget),
                recent_tool_results=self.policy.trim_tool_results(
                    collected.tool_results,
                    request.budget,
                ),
                selected_file_snippets=self.policy.trim_file_snippets(
                    collected.file_snippets,
                    request.budget,
                ),
            )
        workspace_facts = self.workspace_source.collect(request)
        ask_facts = (
            ExecutionFacts()
            if self.ask_source is None
            else self.ask_source.collect(request)
        )
        facts = merge_facts(event_facts, workspace_facts, ask_facts)
        controls = self.control_source.collect(request)
        guidance = self.guidance_source.collect(request)
        skill_segments: tuple[SkillContextSegment, ...] = ()
        skill_permission_outcomes: tuple[ContextSkillPermissionOutcome, ...] = ()
        skill_segment_hashes: tuple[str, ...] = ()
        if self.skill_source is not None:
            skill_result = self.skill_source.collect(
                request,
                controls=controls,
                required_capability=task.required_capability,
            )
            skill_segments = skill_result.segments
            skill_segment_hashes = tuple(_skill_segment_hash(segment) for segment in skill_segments)
            guidance = merge_guidance(guidance, skill_result.guidance)
            if skill_result.permission_merge is not None:
                controls = skill_result.permission_merge.controls
                skill_permission_outcomes = tuple(
                    ContextSkillPermissionOutcome(
                        kind=outcome.kind,
                        skill_id=outcome.skill_id,
                        tool=outcome.tool,
                        reason=outcome.reason,
                    )
                    for outcome in skill_result.permission_merge.outcomes
                )
        snapshot_id = new_context_id("ctx")
        trace_id = new_context_id("trace")
        trace_ref = ContextTraceRef(snapshot_id=snapshot_id, trace_id=trace_id)
        context = TaskExecutionContextV0(
            task=TaskContextIdentity(
                task_id=task.task_id,
                session_id=task.session_id,
                parent_task_id=task.parent_id,
                root_task_id=task.root_id,
                original_target=task.intent,
                interpreted_goal=None,
                required_capability=task.required_capability,
            ),
            execution=self.task_source.execution_state(task, request),
            facts=facts,
            controls=controls,
            guidance=guidance,
            trace=trace_ref,
        )
        rendered = self._render_context(
            context,
            request=request,
            snapshot_id=snapshot_id,
            trace_id=trace_id,
        )
        trace = ContextTrace(
            trace_id=trace_id,
            snapshot_id=snapshot_id,
            session_id=request.session_id,
            task_id=request.task_id,
            candidates_seen=(),
            candidates_selected=(),
            candidates_excluded=(),
            policy_version=self.policy.version,
            renderer_version=self.renderer.version,
            render_mode=rendered.render_mode,
            stable_prefix_hash=rendered.stable_prefix_hash,
            context_segment_hashes=tuple(segment.content_hash for segment in rendered.segments),
            appended_context_message_count=_appended_context_message_count(
                request.prior_messages,
                rendered.messages,
            ),
            delta_reason=(
                request.render_reason if rendered.render_mode == "delta_context" else None
            ),
            checkpoint_reason=(
                request.render_reason if rendered.render_mode == "checkpoint_context" else None
            ),
            active_skill_ids=tuple(segment.skill_id for segment in skill_segments),
            active_skill_hashes=tuple(segment.content_hash for segment in skill_segments),
            skill_activation_ids=tuple(segment.activation_id for segment in skill_segments),
            skill_context_segment_hashes=skill_segment_hashes,
            skill_permission_outcomes=skill_permission_outcomes,
            skill_traces=tuple(
                ContextSkillTrace(
                    activation_id=segment.activation_id,
                    skill_id=segment.skill_id,
                    name=segment.name,
                    source_ref=segment.source_ref,
                    content_hash=segment.content_hash,
                    activation_reason=segment.activation_reason,
                    segment_hash=segment_hash,
                    truncated=segment.truncated,
                    truncation_reason=segment.truncation_reason,
                )
                for segment, segment_hash in zip(skill_segments, skill_segment_hashes, strict=True)
            ),
            skill_truncation_count=sum(1 for segment in skill_segments if segment.truncated),
        )
        snapshot = ContextSnapshot(
            snapshot_id=snapshot_id,
            session_id=request.session_id,
            task_id=request.task_id,
            agent_id=request.agent_id,
            agent_run_id=request.agent_run_id,
            purpose=request.purpose,
            turn_index=request.turn_index,
            renderer_version=self.renderer.version,
            rendered_input_hash=rendered.rendered_input_hash,
            render_mode=rendered.render_mode,
            stable_prefix_hash=rendered.stable_prefix_hash,
            context_segment_hashes=tuple(segment.content_hash for segment in rendered.segments),
            task_execution_context=context,
        )
        self.store.save_snapshot(snapshot)
        self.store.save_trace(trace)
        return ContextBuildResult(
            request=request,
            context=context,
            rendered=rendered,
            snapshot=snapshot,
            trace=trace,
        )

    def _render_context(
        self,
        context: TaskExecutionContextV0,
        *,
        request: ContextBuildRequest,
        snapshot_id: str,
        trace_id: str,
    ) -> RenderedLlmInput:
        if request.render_mode == "start_context":
            return self.renderer.render_start_context(
                context,
                snapshot_id=snapshot_id,
                trace_id=trace_id,
                prior_messages=request.prior_messages,
            )
        if request.render_mode == "delta_context":
            if request.render_reason:
                return self.renderer.render_delta_context(
                    context,
                    snapshot_id=snapshot_id,
                    trace_id=trace_id,
                    reason=request.render_reason,
                    prior_messages=request.prior_messages,
                )
            return self.renderer.render_reused_transcript(
                context,
                snapshot_id=snapshot_id,
                trace_id=trace_id,
                prior_messages=request.prior_messages,
            )
        if request.render_mode == "checkpoint_context":
            return self.renderer.render_checkpoint_context(
                context,
                snapshot_id=snapshot_id,
                trace_id=trace_id,
                reason=request.render_reason or "checkpoint",
                prior_messages=request.prior_messages,
            )
        return self.renderer.render(
            context,
            snapshot_id=snapshot_id,
            trace_id=trace_id,
            prior_messages=request.prior_messages,
        )


def _appended_context_message_count(
    prior_messages: tuple[dict[str, Any], ...],
    rendered_messages: tuple[dict[str, Any], ...],
) -> int:
    if len(rendered_messages) <= len(prior_messages):
        return 0
    if rendered_messages[: len(prior_messages)] != prior_messages:
        return 0
    return len(rendered_messages) - len(prior_messages)


def _skill_segment_hash(segment: SkillContextSegment) -> str:
    payload = segment.model_dump_json()
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
