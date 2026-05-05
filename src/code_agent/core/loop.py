"""ReAct main loop.

The loop is a small state machine that bridges the LLM, the Runtime and the
EventStream:

    user task ─▶ messages ─▶ LLMClient.chat ─▶ tool_calls
                                                 │
                                                 ▼
                                  parse → BaseAction → Runtime.execute
                                                 │
                                                 ▼
                              BaseObservation ─▶ EventStream ─▶ tool message
                                                 │
                                                 ▼  (next turn)
                                              messages

Termination conditions:
    1. The LLM returns no tool_calls (it answered directly).
    2. The LLM emits an :class:`AgentFinishAction`.
    3. ``max_steps`` reached.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from code_agent.audit import AuditAgent, render_audit_system_message
from code_agent.core.event_stream import EventStream, InMemoryEventStream
from code_agent.llm.client import (
    LLMClient,
    ToolCall,
    parse_tool_arguments,
    tool_schema_from_action,
)
from code_agent.memory.thought_store import (
    NullThoughtStore,
    ThoughtRecord,
    ThoughtStore,
)
from code_agent.runtime.base import Runtime
from code_agent.tools.base import Tool
from code_agent.types.base import BaseAction, BaseObservation
from code_agent.types.code_action import CodeAction, CodeExecutionObservation
from code_agent.types.common import (
    AgentFinishAction,
    AgentFinishObservation,
    ErrorObservation,
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a code agent operating inside a sandboxed workspace.\n"
    "Decompose the task, then call the provided tools to make progress.\n"
    "When the task is complete, call the `agent_finish` tool with a short summary.\n"
    "Prefer small, verifiable steps over large speculative ones."
)

FINISH_TOOL_NAME = "agent_finish"


class LoopError(RuntimeError):
    """Raised on misconfiguration (e.g. duplicate tool names)."""


@dataclass(frozen=True)
class LoopResult:
    """What the loop returns when it stops."""

    final_answer: str
    steps: int
    finished: bool  # True iff terminated via AgentFinishAction or empty tool_calls
    stop_reason: str  # "agent_finish" | "no_tool_calls" | "max_steps"


@dataclass
class AgentLoop:
    """ReAct controller.

    Wire it up with concrete Tools, a Runtime, an LLMClient, and (optionally) a
    ThoughtStore. The EventStream is the only required write target — it is the
    source of truth for everything that happened.
    """

    llm: LLMClient
    runtime: Runtime
    tools: list[Tool[Any, Any]]
    event_stream: EventStream = field(default_factory=InMemoryEventStream)
    thought_store: ThoughtStore = field(default_factory=NullThoughtStore)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_steps: int = 20
    auditor: AuditAgent | None = None

    def __post_init__(self) -> None:
        names = [t.name for t in self.tools]
        if len(set(names)) != len(names):
            raise LoopError(f"duplicate tool names in loop: {names}")
        if FINISH_TOOL_NAME in names:
            raise LoopError(
                f"tool name {FINISH_TOOL_NAME!r} is reserved for the loop's finish action."
            )
        self._tools_by_name: dict[str, Tool[Any, Any]] = {t.name: t for t in self.tools}
        self._tool_schemas: list[dict[str, Any]] = [
            tool_schema_from_action(
                name=t.name,
                description=t.description,
                action_type=t.action_type,
            )
            for t in self.tools
        ]
        self._tool_schemas.append(
            tool_schema_from_action(
                name=FINISH_TOOL_NAME,
                description=(
                    "Signal that the task is complete. Provide a short final_answer "
                    "summarizing what was done."
                ),
                action_type=AgentFinishAction,
            )
        )

    def run(self, task: str) -> LoopResult:
        """Execute the loop on a single user task. Synchronous, single-threaded.

        Stateful tools allocate per-task resources via :meth:`Tool.startup`;
        teardown happens in ``finally`` so a partially-started tool still gets
        a chance to clean up.
        """
        try:
            for tool in self.tools:
                tool.startup()
            return self._run_inner(task)
        finally:
            for tool in self.tools:
                # Teardown must not mask the loop result.
                with contextlib.suppress(Exception):
                    tool.shutdown()

    def _run_inner(self, task: str) -> LoopResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]

        for step in range(1, self.max_steps + 1):
            response = self.llm.chat(messages=messages, tools=self._tool_schemas)

            if response.content:
                self.thought_store.write(
                    ThoughtRecord(
                        event_id=f"step-{step}",
                        phase="reason",
                        content=response.content,
                    )
                )

            messages.append(response.raw_assistant_message)

            if not response.tool_calls:
                return LoopResult(
                    final_answer=response.content,
                    steps=step,
                    finished=True,
                    stop_reason="no_tool_calls",
                )

            for tool_call in response.tool_calls:
                if tool_call.name == FINISH_TOOL_NAME:
                    finish_action, finish_obs = self._handle_finish(tool_call)
                    self.event_stream.append(finish_action)
                    self.event_stream.append(finish_obs)
                    messages.append(self._tool_message(tool_call.id, finish_obs))
                    return LoopResult(
                        final_answer=finish_obs.final_answer,
                        steps=step,
                        finished=True,
                        stop_reason="agent_finish",
                    )

                action_or_error = self._build_action(tool_call)
                if isinstance(action_or_error, ErrorObservation):
                    self.event_stream.append(action_or_error)
                    messages.append(self._tool_message(tool_call.id, action_or_error))
                    continue

                action = action_or_error
                self.event_stream.append(action)
                observation = self.runtime.execute(action)
                self.event_stream.append(observation)
                messages.append(self._tool_message(tool_call.id, observation))
                self._maybe_audit(action, observation, messages)

        return LoopResult(
            final_answer="",
            steps=self.max_steps,
            finished=False,
            stop_reason="max_steps",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _handle_finish(
        self, tool_call: ToolCall
    ) -> tuple[AgentFinishAction, AgentFinishObservation]:
        try:
            kwargs = parse_tool_arguments(tool_call.arguments)
            action = AgentFinishAction(**kwargs)
        except (ValueError, ValidationError) as exc:
            action = AgentFinishAction(
                final_answer=f"(failed to parse finish arguments: {exc})"
            )
        observation = AgentFinishObservation(
            action_id=action.event_id,
            final_answer=action.final_answer,
        )
        return action, observation

    def _build_action(self, tool_call: ToolCall) -> BaseAction | ErrorObservation:
        tool = self._tools_by_name.get(tool_call.name)
        if tool is None:
            return ErrorObservation(
                error_type="unknown_tool",
                message=f"No tool registered with name {tool_call.name!r}.",
            )
        try:
            kwargs = parse_tool_arguments(tool_call.arguments)
            action = tool.action_type(**kwargs)
        except (ValueError, ValidationError) as exc:
            return ErrorObservation(
                error_type="invalid_arguments",
                message=f"Could not build {tool.action_type.__name__}: {exc}",
            )
        return action

    @staticmethod
    def _tool_message(tool_call_id: str, observation: BaseObservation) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": observation.to_json(),
        }

    def _maybe_audit(
        self,
        action: BaseAction,
        observation: BaseObservation,
        messages: list[dict[str, Any]],
    ) -> None:
        """Run the auditor on a CodeAction result and append a system message.

        No-op when:
          * no auditor is configured (off by default), or
          * the action is not a CodeAction (we only audit code execution).

        The auditor itself is total — it returns an inconclusive verdict on
        any internal failure rather than raising — so this method does not
        need extra exception handling.
        """
        if self.auditor is None:
            return
        if not isinstance(action, CodeAction) or not isinstance(
            observation, CodeExecutionObservation
        ):
            return
        audit = self.auditor.audit(action, observation)
        self.event_stream.append(audit)
        messages.append(
            {"role": "system", "content": render_audit_system_message(audit)}
        )
