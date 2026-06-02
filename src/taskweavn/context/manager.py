"""Session-scoped Context Manager orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from taskweavn.context.models import (
    ContextBuildRequest,
    ContextBuildResult,
    ContextSnapshot,
    ContextTrace,
    ContextTraceRef,
    ExecutionFacts,
    TaskContextIdentity,
    TaskExecutionContextV0,
    new_context_id,
)
from taskweavn.context.policy import DeterministicContextPolicy
from taskweavn.context.renderer import DeterministicContextRenderer
from taskweavn.context.sources import (
    ControlContextSource,
    EventStreamContextSource,
    GuidanceContextSource,
    TaskContextSource,
    WorkspaceEvidenceContextSource,
    merge_facts,
)
from taskweavn.context.store import ContextStore, InMemoryContextStore


@dataclass
class SessionContextManager:
    """Build, render, and persist execution context for one Session."""

    task_source: TaskContextSource
    event_source: EventStreamContextSource | None = None
    workspace_source: WorkspaceEvidenceContextSource = field(
        default_factory=WorkspaceEvidenceContextSource
    )
    control_source: ControlContextSource = field(default_factory=ControlContextSource)
    guidance_source: GuidanceContextSource = field(default_factory=GuidanceContextSource)
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
        facts = merge_facts(event_facts, workspace_facts)
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
            controls=self.control_source.collect(request),
            guidance=self.guidance_source.collect(request),
            trace=trace_ref,
        )
        rendered = self.renderer.render(
            context,
            snapshot_id=snapshot_id,
            trace_id=trace_id,
            prior_messages=request.prior_messages,
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
