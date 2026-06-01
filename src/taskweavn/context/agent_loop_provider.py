"""AgentLoop integration adapter for Context Manager builds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from taskweavn.context.models import (
    ContextBuildRequest,
    ContextBuildResult,
    ContextModel,
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


@runtime_checkable
class ContextBuilder(Protocol):
    def build(self, request: ContextBuildRequest) -> ContextBuildResult: ...


@runtime_checkable
class AgentLoopContextProvider(Protocol):
    def build_for_llm_call(self, request: AgentLoopContextRequest) -> RenderedLlmInput: ...


@dataclass(frozen=True)
class SessionAgentLoopContextProvider:
    """Build final AgentLoop LLM messages from SessionContextManager output."""

    context_builder: ContextBuilder
    max_prior_messages: int = 200

    def build_for_llm_call(self, request: AgentLoopContextRequest) -> RenderedLlmInput:
        prior_messages = self._prior_messages(request.loop_messages)
        result = self.context_builder.build(
            ContextBuildRequest(
                session_id=request.session_id,
                task_id=request.task_id,
                agent_id=request.agent_id,
                agent_run_id=request.agent_run_id,
                purpose="execution_step",
                writer=True,
                turn_index=request.turn_index,
                prior_messages=prior_messages,
            )
        )
        return result.rendered

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
