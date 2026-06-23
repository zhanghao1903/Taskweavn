"""AgentLoop integration adapter for Context Manager builds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from taskweavn.context.models import (
    ContextBudget,
    ContextBuildRequest,
    ContextBuildResult,
    ContextModel,
    ContextRenderMode,
    InterruptionContext,
    RenderedLlmInput,
)


class AgentLoopContextRequest(ContextModel):
    session_id: str
    task_id: str
    agent_id: str = "default_agent"
    agent_run_id: str
    turn_index: int
    loop_messages: tuple[dict[str, Any], ...] = ()
    tool_names: tuple[str, ...] = ()
    pending_decision_count: int = 0


class AgentLoopContextCallResult(ContextModel):
    llm_messages: tuple[dict[str, Any], ...]
    persisted_messages: tuple[dict[str, Any], ...]
    rendered: RenderedLlmInput
    appended_context_messages: tuple[dict[str, Any], ...] = ()
    render_mode: ContextRenderMode
    stable_prefix_hash: str | None = None
    delta_reason: str | None = None
    checkpoint_reason: str | None = None


class CacheAwareRunState(ContextModel):
    agent_run_id: str
    start_context_initialized: bool = False
    stable_prefix_hash: str | None = None
    last_checkpoint_step: int = 0
    appended_context_message_count: int = 0
    last_delta_hash: str | None = None
    last_pending_decision_count: int = 0
    last_interruption_signature: str | None = None


class ContextRenderTrigger(ContextModel):
    render_mode: Literal["delta_context", "checkpoint_context"]
    reason: str


class ContextTriggerEvaluator(Protocol):
    def __call__(
        self,
        request: AgentLoopContextRequest,
        state: CacheAwareRunState,
        /,
    ) -> ContextRenderTrigger | None: ...


@runtime_checkable
class ContextBuilder(Protocol):
    def build(self, request: ContextBuildRequest) -> ContextBuildResult: ...


@runtime_checkable
class AgentLoopContextProvider(Protocol):
    def build_for_llm_call(self, request: AgentLoopContextRequest) -> RenderedLlmInput: ...


@runtime_checkable
class CacheAwareAgentLoopContextProvider(AgentLoopContextProvider, Protocol):
    def prepare_llm_call(
        self,
        request: AgentLoopContextRequest,
    ) -> AgentLoopContextCallResult: ...


@dataclass(frozen=True)
class SessionAgentLoopContextProvider:
    """Build final AgentLoop LLM messages from SessionContextManager output."""

    context_builder: ContextBuilder
    max_prior_messages: int = 200
    checkpoint_interval_steps: int = 5
    default_budget: ContextBudget = field(default_factory=ContextBudget)
    additional_trigger_evaluators: tuple[ContextTriggerEvaluator, ...] = ()
    _run_states: dict[str, CacheAwareRunState] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def build_for_llm_call(self, request: AgentLoopContextRequest) -> RenderedLlmInput:
        prior_messages = self._prior_messages(request.loop_messages)
        result = self.context_builder.build(
            ContextBuildRequest(
                session_id=request.session_id,
                task_id=request.task_id,
                agent_id=request.agent_id,
                agent_run_id=request.agent_run_id,
                purpose="execution_step",
                render_mode="full_context",
                writer=True,
                turn_index=request.turn_index,
                budget=self.default_budget,
                prior_messages=prior_messages,
            )
        )
        return result.rendered

    def prepare_llm_call(
        self,
        request: AgentLoopContextRequest,
    ) -> AgentLoopContextCallResult:
        state = self._run_states.get(request.agent_run_id)
        if state is None or not state.start_context_initialized:
            return self._prepare_start_context(request)
        trigger = self._next_trigger(request, state)
        if trigger is not None:
            return self._prepare_triggered_context(request, state, trigger)
        return self._prepare_reuse_transcript(request, state)

    def _prepare_start_context(
        self,
        request: AgentLoopContextRequest,
    ) -> AgentLoopContextCallResult:
        result = self.context_builder.build(
            ContextBuildRequest(
                session_id=request.session_id,
                task_id=request.task_id,
                agent_id=request.agent_id,
                agent_run_id=request.agent_run_id,
                purpose="execution_step",
                render_mode="start_context",
                writer=True,
                turn_index=request.turn_index,
                budget=self.default_budget,
                prior_messages=(),
            )
        )
        rendered = result.rendered
        state = CacheAwareRunState(
            agent_run_id=request.agent_run_id,
            start_context_initialized=True,
            stable_prefix_hash=rendered.stable_prefix_hash,
            last_checkpoint_step=0,
            last_pending_decision_count=request.pending_decision_count,
            last_interruption_signature=_interruption_signature(
                result.context.execution.interruption
            ),
        )
        self._run_states[request.agent_run_id] = state
        return AgentLoopContextCallResult(
            llm_messages=rendered.messages,
            persisted_messages=rendered.messages,
            rendered=rendered,
            render_mode=rendered.render_mode,
            stable_prefix_hash=rendered.stable_prefix_hash,
        )

    def _prepare_reuse_transcript(
        self,
        request: AgentLoopContextRequest,
        state: CacheAwareRunState,
    ) -> AgentLoopContextCallResult:
        result = self.context_builder.build(
            ContextBuildRequest(
                session_id=request.session_id,
                task_id=request.task_id,
                agent_id=request.agent_id,
                agent_run_id=request.agent_run_id,
                purpose="execution_step",
                render_mode="delta_context",
                writer=True,
                turn_index=request.turn_index,
                budget=self.default_budget,
                prior_messages=request.loop_messages,
            )
        )
        rendered = result.rendered
        interruption_signature = _interruption_signature(
            result.context.execution.interruption
        )
        if (
            interruption_signature is not None
            and interruption_signature != state.last_interruption_signature
        ):
            return self._prepare_triggered_context(
                request,
                state,
                ContextRenderTrigger(
                    render_mode="delta_context",
                    reason="interrupt_requested",
                ),
            )
        self._run_states[request.agent_run_id] = state.model_copy(
            update={
                "last_pending_decision_count": request.pending_decision_count,
                "last_interruption_signature": interruption_signature,
            }
        )
        return AgentLoopContextCallResult(
            llm_messages=rendered.messages,
            persisted_messages=rendered.messages,
            rendered=rendered,
            render_mode=rendered.render_mode,
            stable_prefix_hash=rendered.stable_prefix_hash or state.stable_prefix_hash,
        )

    def _prepare_triggered_context(
        self,
        request: AgentLoopContextRequest,
        state: CacheAwareRunState,
        trigger: ContextRenderTrigger,
    ) -> AgentLoopContextCallResult:
        result = self.context_builder.build(
            ContextBuildRequest(
                session_id=request.session_id,
                task_id=request.task_id,
                agent_id=request.agent_id,
                agent_run_id=request.agent_run_id,
                purpose="execution_step",
                render_mode=trigger.render_mode,
                render_reason=trigger.reason,
                writer=True,
                turn_index=request.turn_index,
                budget=self.default_budget,
                prior_messages=request.loop_messages,
            )
        )
        rendered = result.rendered
        interruption_signature = _interruption_signature(
            result.context.execution.interruption
        )
        appended_context_messages = _appended_context_messages(
            before=request.loop_messages,
            after=rendered.messages,
        )
        updated_state = state.model_copy(
            update={
                "last_checkpoint_step": (
                    request.turn_index
                    if trigger.render_mode == "checkpoint_context"
                    else state.last_checkpoint_step
                ),
                "appended_context_message_count": (
                    state.appended_context_message_count + len(appended_context_messages)
                ),
                "last_delta_hash": (
                    rendered.rendered_input_hash
                    if trigger.render_mode == "delta_context"
                    else state.last_delta_hash
                ),
                "last_pending_decision_count": request.pending_decision_count,
                "last_interruption_signature": interruption_signature,
            }
        )
        self._run_states[request.agent_run_id] = updated_state
        return AgentLoopContextCallResult(
            llm_messages=rendered.messages,
            persisted_messages=rendered.messages,
            rendered=rendered,
            appended_context_messages=appended_context_messages,
            render_mode=rendered.render_mode,
            stable_prefix_hash=rendered.stable_prefix_hash or state.stable_prefix_hash,
            delta_reason=(trigger.reason if trigger.render_mode == "delta_context" else None),
            checkpoint_reason=(
                trigger.reason if trigger.render_mode == "checkpoint_context" else None
            ),
        )

    def _next_trigger(
        self,
        request: AgentLoopContextRequest,
        state: CacheAwareRunState,
    ) -> ContextRenderTrigger | None:
        checkpoint_trigger = self._interval_checkpoint_trigger(request, state)
        if checkpoint_trigger is not None:
            return checkpoint_trigger
        for evaluator in self.additional_trigger_evaluators:
            trigger = evaluator(request, state)
            if trigger is not None:
                return trigger
        return None

    def _interval_checkpoint_trigger(
        self,
        request: AgentLoopContextRequest,
        state: CacheAwareRunState,
    ) -> ContextRenderTrigger | None:
        if self.checkpoint_interval_steps <= 0:
            return None
        if request.turn_index - state.last_checkpoint_step < self.checkpoint_interval_steps:
            return None
        return ContextRenderTrigger(
            render_mode="checkpoint_context",
            reason=f"interval:{self.checkpoint_interval_steps}",
        )

    def _prior_messages(
        self,
        loop_messages: tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        # The first two loop messages are the loop-local system prompt and
        # initial task. Context Manager replaces them with the current
        # rendered context; subsequent assistant/tool/system messages preserve
        # the OpenAI tool-call protocol and late approval/audit observations.
        prior = loop_messages[2:]
        if len(prior) <= self.max_prior_messages:
            return prior
        return prior[-self.max_prior_messages :]


def _appended_context_messages(
    *,
    before: tuple[dict[str, Any], ...],
    after: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    if len(after) <= len(before):
        return ()
    if after[: len(before)] != before:
        return ()
    return after[len(before) :]


def _interruption_signature(interruption: InterruptionContext | None) -> str | None:
    if interruption is None or not interruption.requested:
        return None
    if interruption.request_id is not None:
        return f"request_id:{interruption.request_id}"
    requested_at = (
        interruption.requested_at.isoformat()
        if interruption.requested_at is not None
        else "unknown_time"
    )
    return "|".join(
        (
            f"requested_by:{interruption.requested_by or 'unknown'}",
            f"reason:{interruption.reason or 'none'}",
            f"requested_at:{requested_at}",
        )
    )
