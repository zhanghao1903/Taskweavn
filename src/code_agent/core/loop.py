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

Phase 3.6 adds an optional autonomy seam between ``_build_action`` and
``Runtime.execute``: when an :class:`AutonomyGate` is wired in, every action
is gated against the user's :class:`AutonomyBehavior`. The gate may PROCEED
(run as before, optionally posting an informational message) or EMIT (publish
an ``actionable`` and hand off to the :class:`WaitCoordinator` for a reply).
The gate is OFF by default — existing tests keep their current shape.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

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
from code_agent.types.base import BaseAction, BaseEvent, BaseObservation
from code_agent.types.code_action import CodeAction, CodeExecutionObservation
from code_agent.types.common import (
    AgentFinishAction,
    AgentFinishObservation,
    ErrorObservation,
)

if TYPE_CHECKING:  # pragma: no cover
    from code_agent.interaction import (
        AgentMessage,
        AutonomyGate,
        GateDecision,
        MessageBus,
        WaitCoordinator,
    )

DEFAULT_SYSTEM_PROMPT = (
    "You are a code agent operating inside a sandboxed workspace.\n"
    "Decompose the task, then call the provided tools to make progress.\n"
    "When the task is complete, call the `agent_finish` tool with a short summary.\n"
    "Prefer small, verifiable steps over large speculative ones."
)

FINISH_TOOL_NAME = "agent_finish"

# Reply values that count as "user said no". Compared case-insensitively
# after trim. Empty / None never rejects (a blank reply is "ack, proceed").
_REJECTION_TOKENS: frozenset[str] = frozenset(
    {"no", "n", "deny", "reject", "skip", "cancel", "abort"}
)


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

    The interaction-layer fields (``bus``, ``gate``, ``wait_coordinator``,
    ``session_id``, ``workspace_root``) are optional. Wire them as a coherent
    bundle: gate ⇔ wait_coordinator (both or neither); when ``gate`` is set,
    ``workspace_root`` must be too so the gate can build its
    :class:`AssessmentContext`. ``bus`` is required when the gate is wired
    (the loop publishes both informational notices and actionables onto it).
    """

    llm: LLMClient
    runtime: Runtime
    tools: list[Tool[Any, Any]]
    event_stream: EventStream = field(default_factory=InMemoryEventStream)
    thought_store: ThoughtStore = field(default_factory=NullThoughtStore)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_steps: int = 20
    auditor: AuditAgent | None = None

    # ── Interaction layer (Phase 3.6) ─────────────────────────────────
    session_id: str = "default"
    """Tag for cross-stream joins (events ⊕ messages). Single-process Phase 3
    runs can leave this at 'default'; multi-session orchestration in 4.x will
    fill in real ids."""

    workspace_root: Path | None = None
    """Required when ``gate`` is set so the assessor sees the root path. Left
    optional for the gate-less default-behavior path used by all pre-3.6
    tests."""

    bus: MessageBus | None = None
    gate: AutonomyGate | None = None
    wait_coordinator: WaitCoordinator | None = None

    def __post_init__(self) -> None:
        names = [t.name for t in self.tools]
        if len(set(names)) != len(names):
            raise LoopError(f"duplicate tool names in loop: {names}")
        if FINISH_TOOL_NAME in names:
            raise LoopError(
                f"tool name {FINISH_TOOL_NAME!r} is reserved for the loop's finish action."
            )
        # Interaction-layer bundle invariants. We don't try to be helpful by
        # half-wiring anything — either the user opted in to autonomy gating
        # (all three pieces present) or they didn't (none of them).
        gate_set = self.gate is not None
        coord_set = self.wait_coordinator is not None
        if gate_set != coord_set:
            raise LoopError(
                "gate and wait_coordinator must be supplied together; got "
                f"gate={'set' if gate_set else 'None'}, "
                f"wait_coordinator={'set' if coord_set else 'None'}"
            )
        if gate_set and self.bus is None:
            raise LoopError(
                "AgentLoop with a gate also requires a MessageBus to publish "
                "actionables / informational notices on."
            )
        if gate_set and self.workspace_root is None:
            raise LoopError(
                "AgentLoop with a gate requires workspace_root for the "
                "RiskAssessor's AssessmentContext."
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
        # Set on every ``run()`` call so cross-stream joins (events ⊕ messages)
        # can pin every event/message of one run to a shared key.
        self._current_task_id: str | None = None

    def run(self, task: str) -> LoopResult:
        """Execute the loop on a single user task. Synchronous, single-threaded.

        Stateful tools allocate per-task resources via :meth:`Tool.startup`;
        teardown happens in ``finally`` so a partially-started tool still gets
        a chance to clean up.

        A fresh ``task_id`` (uuid4) is minted for every call. It propagates to
        the EventStream (when the impl accepts the kwarg) and to every
        AgentMessage the loop publishes, so an ops UI can reconstruct exactly
        the events/messages produced by *this* invocation.
        """
        self._current_task_id = uuid4().hex
        try:
            for tool in self.tools:
                tool.startup()
            return self._run_inner(task)
        finally:
            for tool in self.tools:
                # Teardown must not mask the loop result.
                with contextlib.suppress(Exception):
                    tool.shutdown()
            self._current_task_id = None

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
                    self._append_event(finish_action)
                    self._append_event(finish_obs)
                    messages.append(self._tool_message(tool_call.id, finish_obs))
                    return LoopResult(
                        final_answer=finish_obs.final_answer,
                        steps=step,
                        finished=True,
                        stop_reason="agent_finish",
                    )

                action_or_error = self._build_action(tool_call)
                if isinstance(action_or_error, ErrorObservation):
                    self._append_event(action_or_error)
                    messages.append(self._tool_message(tool_call.id, action_or_error))
                    continue

                action = action_or_error

                # Autonomy gate (Phase 3.6). When the loop has no gate wired in
                # this short-circuits to None and the action runs as before.
                gate_skip = self._consult_gate(action)
                if gate_skip is not None:
                    self._append_event(action)
                    self._append_event(gate_skip)
                    messages.append(self._tool_message(tool_call.id, gate_skip))
                    continue

                self._append_event(action)
                observation = self.runtime.execute(action)
                self._append_event(observation)
                messages.append(self._tool_message(tool_call.id, observation))
                self._maybe_audit(action, observation, messages)

        return LoopResult(
            final_answer="",
            steps=self.max_steps,
            finished=False,
            stop_reason="max_steps",
        )

    # ------------------------------------------------------------------
    # Autonomy gate dispatch
    # ------------------------------------------------------------------

    def _consult_gate(self, action: BaseAction) -> ErrorObservation | None:
        """Return ``None`` to proceed; an :class:`ErrorObservation` to skip.

        Three outcomes:

        * Gate not wired → always proceed.
        * Gate says PROCEED → optionally publish an informational notice, then
          proceed. The action runs.
        * Gate says EMIT → publish an actionable, hand to the
          :class:`WaitCoordinator`. Whether the action proceeds depends on the
          :class:`WaitOutcome`:

          * ``GOT_RESPONSE`` + non-rejection → proceed.
          * ``GOT_RESPONSE`` + rejection ("no" / "deny" / …) → skip.
          * ``TIMED_OUT_PROCEED`` → proceed (the synthesized default IS the
            response).
          * ``TIMED_OUT_SKIP`` → skip.
          * ``PENDING`` (async) → skip for Phase 3.6a; the
            ``drain_pending_responses`` path in 3.6b will surface async replies
            in a later iteration.

        Skips return an ErrorObservation with a stable ``error_type`` so logs /
        UIs can distinguish "user declined" from "timeout fired".
        """
        if self.gate is None:
            return None

        # Local imports so the interaction layer stays a soft dependency: a
        # consumer that never wires a gate doesn't pull risk / message code.
        from code_agent.interaction import (
            AssessmentContext,
            GateVerdict,
            WaitOutcome,
        )

        assert self.workspace_root is not None  # __post_init__ enforces this
        assert self.bus is not None
        assert self.wait_coordinator is not None

        context = AssessmentContext(
            workspace_root=self.workspace_root,
            session_id=self.session_id,
        )
        decision = self.gate.check(action, context)

        if decision.verdict == GateVerdict.PROCEED:
            if decision.inform_user:
                self._publish_inform(action, decision)
            return None

        # EMIT — synthesize an actionable, publish, wait.
        actionable = self._build_actionable_message(action, decision)
        self.bus.publish(actionable)
        result = self.wait_coordinator.handle_actionable(actionable)

        if result.outcome == WaitOutcome.GOT_RESPONSE:
            if _is_rejection(result.response_value):
                return ErrorObservation(
                    error_type="user_declined",
                    message=(
                        f"user declined to run {type(action).__name__}: "
                        f"reply={result.response_value!r}"
                    ),
                )
            return None

        if result.outcome == WaitOutcome.TIMED_OUT_PROCEED:
            # The coordinator already published a notice when notify_on_proceed
            # is on; treat the synthesized default as approval.
            return None

        if result.outcome == WaitOutcome.TIMED_OUT_SKIP:
            return ErrorObservation(
                error_type="autonomy_timeout_skip",
                message=(
                    f"autonomy timeout fired with action=skip; "
                    f"{type(action).__name__} not executed"
                ),
            )

        # PENDING (async). Phase 3.6a does not implement the drain loop yet;
        # surface as an error so the action does not run speculatively.
        return ErrorObservation(
            error_type="autonomy_pending",
            message=(
                "async autonomy strategy returned PENDING; awaiting "
                "drain_pending_responses (Phase 3.6b)"
            ),
        )

    def _build_actionable_message(
        self,
        action: BaseAction,
        decision: GateDecision,
    ) -> AgentMessage:
        from code_agent.interaction import AgentMessage as _AgentMessage

        return _AgentMessage(
            session_id=self.session_id,
            task_id=self._current_task_id,
            agent_id="agent",
            message_type="actionable",
            content=(
                f"OK to run {type(action).__name__}? "
                f"(risk {decision.risk_assessment.final:.2f}; {decision.reason})"
            ),
            context={
                "action_kind": action.kind,
                "action_event_id": action.event_id,
            },
            action_options=["yes", "no"],
            requires_response=True,
            risk_assessment=decision.risk_assessment,
            related_action_id=action.event_id,
        )

    def _publish_inform(
        self,
        action: BaseAction,
        decision: GateDecision,
    ) -> None:
        """Post a non-blocking 'fyi, just doing X' notice. Only called when
        the gate's PROCEED branch flagged ``inform_user``.
        """
        from code_agent.interaction import AgentMessage as _AgentMessage

        assert self.bus is not None
        info = _AgentMessage(
            session_id=self.session_id,
            task_id=self._current_task_id,
            agent_id="agent",
            message_type="informational",
            content=(
                f"Running {type(action).__name__} "
                f"(risk={decision.risk_assessment.final:.2f}; {decision.reason})"
            ),
            context={
                "action_kind": action.kind,
                "action_event_id": action.event_id,
            },
            risk_assessment=decision.risk_assessment,
            related_action_id=action.event_id,
        )
        self.bus.publish(info)

    # ------------------------------------------------------------------
    # EventStream helper (task_id duck-typing)
    # ------------------------------------------------------------------

    def _append_event(self, event: BaseEvent) -> None:
        """Append ``event`` and stamp it with the current task id, if the
        underlying stream supports the kwarg.

        :class:`EventStream` (Protocol) declares only ``append(event)``;
        :class:`SqliteEventStream` extends with ``*, task_id=None``. Probing
        with ``try/except TypeError`` keeps both shapes working without forcing
        the Protocol to grow a kwarg every consumer must accept.
        """
        if self._current_task_id is None:
            self.event_stream.append(event)
            return
        try:
            self.event_stream.append(event, task_id=self._current_task_id)  # type: ignore[call-arg]
        except TypeError:
            self.event_stream.append(event)

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
        self._append_event(audit)
        messages.append(
            {"role": "system", "content": render_audit_system_message(audit)}
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _is_rejection(value: str | None) -> bool:
    """Did the user say 'no' to the actionable?

    Empty / whitespace-only / None → not a rejection (a blank reply is treated
    as 'I read it, proceed' — the user can always pick the 'no' option
    explicitly). Match is case-insensitive against a small token set; anything
    else is a free-form 'do whatever' reply that the loop honours by running
    the action.
    """
    if value is None:
        return False
    stripped = value.strip().lower()
    if not stripped:
        return False
    return stripped in _REJECTION_TOKENS
