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

Phase 3.6b extends the EMIT path: when the autonomy strategy is ``async``,
the coordinator returns ``PENDING`` and the loop **defers** instead of
erroring. The deferred action is queued in ``_pending_decisions`` and the
LLM gets a synthetic placeholder tool result that says "queued, will resolve
out-of-band". On every subsequent step (and the final shutdown drain in
``run()``) :meth:`AgentLoop.drain_pending_responses` non-blocking-polls the
bus for replies; resolved actions execute and surface as a system message
spliced into the LLM's context, so the agent can reason about the late
result on the next turn.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import ValidationError

from taskweavn.audit import AuditAgent, render_audit_system_message
from taskweavn.core.event_stream import EventStream, InMemoryEventStream
from taskweavn.llm.client import (
    LLMClient,
    ToolCall,
    parse_tool_arguments,
    tool_schema_from_action,
)
from taskweavn.memory.thought_store import (
    NullThoughtStore,
    ThoughtRecord,
    ThoughtStore,
)
from taskweavn.observability import LogContext, use_log_context
from taskweavn.prompts import AGENT_LOOP_SYSTEM_PROMPT
from taskweavn.runtime.base import Runtime
from taskweavn.tools.base import Tool
from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation
from taskweavn.types.code_action import CodeAction, CodeExecutionObservation
from taskweavn.types.common import (
    AgentErrorObservation,
    AgentFinishAction,
    AgentFinishObservation,
    ErrorObservation,
)

if TYPE_CHECKING:  # pragma: no cover
    from taskweavn.context.agent_loop_provider import AgentLoopContextProvider
    from taskweavn.interaction import (
        AgentMessage,
        AutonomyGate,
        GateDecision,
        MessageBus,
        WaitCoordinator,
    )

DEFAULT_SYSTEM_PROMPT = AGENT_LOOP_SYSTEM_PROMPT

FINISH_TOOL_NAME = "agent_finish"

# Reply values that count as "user said no". Compared case-insensitively
# after trim. Empty / None never rejects (a blank reply is "ack, proceed").
_REJECTION_TOKENS: frozenset[str] = frozenset(
    {"no", "n", "deny", "reject", "skip", "cancel", "abort"}
)


class LoopError(RuntimeError):
    """Raised on misconfiguration (e.g. duplicate tool names)."""


@dataclass(frozen=True)
class _GateDispatch:
    """What :meth:`AgentLoop._consult_gate` decided.

    Three terminal kinds; the loop's inner-tool-call loop branches on
    ``kind``. ``skip_observation`` is set iff ``kind=="skip"``;
    ``deferred_actionable_id`` is set iff ``kind=="defer"``.
    """

    kind: Literal["proceed", "skip", "defer"]
    skip_observation: ErrorObservation | None = None
    deferred_actionable_id: str | None = None
    deferred_action: BaseAction | None = None


@dataclass
class _PendingDecision:
    """One un-resolved async deferral waiting for a user reply.

    ``actionable_message_id`` keys ``MessageBus.wait_for_response``;
    ``action`` is the original :class:`BaseAction` that will run when the
    reply lands and is not a rejection. The action's :attr:`event_id` is
    already on the event stream (appended at deferral time), so on
    resolution we only need to append the resulting observation.
    """

    actionable_message_id: str
    action: BaseAction


@dataclass(frozen=True)
class LoopResult:
    """What the loop returns when it stops."""

    final_answer: str
    steps: int
    finished: bool  # True iff terminated via AgentFinishAction or empty tool_calls
    stop_reason: str  # "agent_finish" | "no_tool_calls" | "max_steps" | "llm_error"


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
    context_provider: AgentLoopContextProvider | None = None

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
        # Phase 3.6b: actions that were gated as EMIT under wait_strategy=
        # "async" sit here until ``drain_pending_responses`` finds their
        # replies on the bus. Drained on every step entry and once at
        # shutdown. A run that ends with leftover pending entries simply
        # discards them — the actionables are still on the message stream
        # for an operator to inspect.
        self._pending_decisions: list[_PendingDecision] = []
        self._current_agent_run_id: str | None = None

    def run(self, task: str, *, task_id: str | None = None) -> LoopResult:
        """Execute the loop on a single user task. Synchronous, single-threaded.

        Stateful tools allocate per-task resources via :meth:`Tool.startup`;
        teardown happens in ``finally`` so a partially-started tool still gets
        a chance to clean up.

        A fresh ``task_id`` (uuid4) is minted for every call unless the caller
        supplies a domain task id. It propagates to the EventStream (when the
        impl accepts the kwarg) and to every AgentMessage the loop publishes,
        so an ops UI can reconstruct exactly the events/messages produced by
        *this* invocation.
        """
        self._current_task_id = task_id or uuid4().hex
        self._current_agent_run_id = f"agent_loop:{self._current_task_id}:{uuid4().hex}"
        # A fresh queue per ``run()`` — leftovers from a previous task have
        # no business resolving against this one.
        self._pending_decisions = []
        try:
            with use_log_context(
                LogContext(
                    session_id=self.session_id,
                    task_id=self._current_task_id,
                    workspace_root=(
                        str(self.workspace_root) if self.workspace_root is not None else None
                    ),
                )
            ):
                for tool in self.tools:
                    tool.startup()
                return self._run_inner(task)
        finally:
            with use_log_context(
                LogContext(
                    session_id=self.session_id,
                    task_id=self._current_task_id,
                    workspace_root=(
                        str(self.workspace_root) if self.workspace_root is not None else None
                    ),
                )
            ):
                # Best-effort shutdown drain: any reply that arrived while the
                # loop was finishing should still produce an observation in the
                # event stream so the audit trail is consistent. The LLM is
                # done — we don't append to ``messages`` here.
                with contextlib.suppress(Exception):
                    self.drain_pending_responses(messages=None)
                for tool in self.tools:
                    # Teardown must not mask the loop result.
                    with contextlib.suppress(Exception):
                        tool.shutdown()
            self._current_task_id = None
            self._current_agent_run_id = None

    def _run_inner(self, task: str) -> LoopResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]

        for step in range(1, self.max_steps + 1):
            # Resolve any prior async deferrals before asking the LLM again
            # so the resolved observation is in context when it reasons.
            # Cheap (a non-blocking SQL poll per pending entry) and a no-op
            # when the queue is empty.
            self.drain_pending_responses(messages)

            try:
                messages_for_call, metadata = self._prepare_llm_call(messages, step)
            except Exception as exc:  # noqa: BLE001 — loop contract: return LoopResult.
                obs = self._handle_context_error(exc, step)
                self._append_event(obs)
                self._publish_loop_error(obs)
                return LoopResult(
                    final_answer="",
                    steps=step,
                    finished=False,
                    stop_reason="context_error",
                )

            try:
                if metadata:
                    response = self.llm.chat(
                        messages=messages_for_call,
                        tools=self._tool_schemas,
                        metadata=metadata,
                    )
                else:
                    response = self.llm.chat(messages=messages_for_call, tools=self._tool_schemas)
            except Exception as exc:  # noqa: BLE001 — loop contract: return LoopResult.
                obs = self._handle_llm_error(exc, step)
                self._append_event(obs)
                self._publish_loop_error(obs)
                return LoopResult(
                    final_answer="",
                    steps=step,
                    finished=False,
                    stop_reason="llm_error",
                )

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
                # the dispatch is always ``proceed`` and the action runs as
                # before. Otherwise we branch on dispatch.kind:
                #   proceed → run normally (3.6a baseline).
                #   skip    → emit ErrorObservation, action does not run.
                #   defer   → enqueue pending decision; placeholder tool
                #             message keeps the LLM moving; drain runs the
                #             action on a future step.
                dispatch = self._consult_gate(action)
                if dispatch.kind == "skip":
                    assert dispatch.skip_observation is not None
                    self._append_event(action)
                    self._append_event(dispatch.skip_observation)
                    messages.append(self._tool_message(tool_call.id, dispatch.skip_observation))
                    continue
                if dispatch.kind == "defer":
                    assert dispatch.deferred_actionable_id is not None
                    self._append_event(action)
                    self._pending_decisions.append(
                        _PendingDecision(
                            actionable_message_id=dispatch.deferred_actionable_id,
                            action=action,
                        )
                    )
                    # Synthetic placeholder so the OpenAI tool-call protocol
                    # stays well-formed (every tool_call needs a tool reply).
                    # Not appended to the event stream — drain emits the
                    # real observation when the response lands.
                    placeholder = ErrorObservation(
                        error_type="autonomy_deferred",
                        message=(
                            f"queued {type(action).__name__} for user "
                            f"confirmation (message_id="
                            f"{dispatch.deferred_actionable_id}); the result "
                            "will resolve out-of-band on a later step"
                        ),
                    )
                    messages.append(self._tool_message(tool_call.id, placeholder))
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

    def _consult_gate(self, action: BaseAction) -> _GateDispatch:
        """Resolve the autonomy contract for ``action`` into a dispatch tag.

        Five outcomes collapse into three kinds:

        * Gate not wired → ``proceed``.
        * Gate says PROCEED → optionally publish an informational notice,
          then ``proceed``.
        * Gate says EMIT → publish an actionable and ask the
          :class:`WaitCoordinator`:

          * ``GOT_RESPONSE`` + non-rejection → ``proceed``.
          * ``GOT_RESPONSE`` + rejection ("no" / "deny" / …) → ``skip`` with
            ``error_type="user_declined"``.
          * ``TIMED_OUT_PROCEED`` → ``proceed`` (the synthesized default IS
            the response; the coordinator already published a notice when
            ``notify_on_proceed`` is on).
          * ``TIMED_OUT_SKIP`` → ``skip`` with
            ``error_type="autonomy_timeout_skip"``.
          * ``PENDING`` (``async`` strategy) → ``defer``; the action is
            queued in ``_pending_decisions`` and resolved by
            :meth:`drain_pending_responses` on a later step or at shutdown.
        """
        if self.gate is None:
            return _GateDispatch(kind="proceed")

        # Local imports so the interaction layer stays a soft dependency: a
        # consumer that never wires a gate doesn't pull risk / message code.
        from taskweavn.interaction import (
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
            return _GateDispatch(kind="proceed")

        # EMIT — synthesize an actionable, publish, wait.
        actionable = self._build_actionable_message(action, decision)
        self.bus.publish(actionable)
        result = self.wait_coordinator.handle_actionable(actionable)

        if result.outcome == WaitOutcome.GOT_RESPONSE:
            if _is_rejection(result.response_value):
                return _GateDispatch(
                    kind="skip",
                    skip_observation=ErrorObservation(
                        error_type="user_declined",
                        message=(
                            f"user declined to run {type(action).__name__}: "
                            f"reply={result.response_value!r}"
                        ),
                    ),
                )
            return _GateDispatch(kind="proceed")

        if result.outcome == WaitOutcome.TIMED_OUT_PROCEED:
            return _GateDispatch(kind="proceed")

        if result.outcome == WaitOutcome.TIMED_OUT_SKIP:
            return _GateDispatch(
                kind="skip",
                skip_observation=ErrorObservation(
                    error_type="autonomy_timeout_skip",
                    message=(
                        f"autonomy timeout fired with action=skip; "
                        f"{type(action).__name__} not executed"
                    ),
                ),
            )

        # PENDING — async strategy. Defer; drain_pending_responses owns it.
        return _GateDispatch(
            kind="defer",
            deferred_actionable_id=actionable.message_id,
            deferred_action=action,
        )

    # ------------------------------------------------------------------
    # Async deferral drain (Phase 3.6b)
    # ------------------------------------------------------------------

    def drain_pending_responses(
        self,
        messages: list[dict[str, Any]] | None,
    ) -> int:
        """Resolve any deferred async actionables whose replies have landed.

        For each entry in ``_pending_decisions`` we non-blocking-poll the bus
        (``timeout=0``) for a response. If one is present:

        * Rejection ("no"/"deny"/…) → emit
          ``ErrorObservation(error_type="user_declined")``; the action does
          NOT run.
        * Anything else → run the action through the runtime exactly as the
          synchronous EMIT path would.

        The resulting :class:`BaseObservation` is appended to the event
        stream. When ``messages`` is provided, a system message is spliced
        into the LLM context summarizing the resolution so the agent can
        reason about the late result on its next turn. ``messages=None`` is
        the shutdown-drain mode used by ``run()``'s finally clause — the
        observation lands in the event stream but no LLM context update
        happens because there is no next turn.

        Returns the number of decisions that resolved this call. Cheap:
        a single SQL ``response_for`` query per pending entry, plus a
        :meth:`Runtime.execute` for each non-rejection.
        """
        if not self._pending_decisions or self.bus is None:
            return 0

        resolved = 0
        still_pending: list[_PendingDecision] = []
        for pending in self._pending_decisions:
            response = self.bus.wait_for_response(pending.actionable_message_id, timeout=0)
            if response is None:
                still_pending.append(pending)
                continue

            obs: BaseObservation
            if _is_rejection(response.response_value):
                obs = ErrorObservation(
                    error_type="user_declined",
                    message=(
                        f"user declined queued "
                        f"{type(pending.action).__name__}: "
                        f"reply={response.response_value!r}"
                    ),
                )
            else:
                # The runtime is itself total — any internal failure surfaces
                # as an ErrorObservation rather than an exception, so we
                # don't need a try/except here.
                obs = self.runtime.execute(pending.action)

            self._append_event(obs)
            if messages is not None:
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"Previously deferred "
                            f"{type(pending.action).__name__} "
                            f"(action_id={pending.action.event_id}) has "
                            f"resolved: {obs.to_json()}"
                        ),
                    }
                )
                self._maybe_audit(pending.action, obs, messages)
            resolved += 1

        self._pending_decisions = still_pending
        return resolved

    def _build_actionable_message(
        self,
        action: BaseAction,
        decision: GateDecision,
    ) -> AgentMessage:
        from taskweavn.interaction import AgentMessage as _AgentMessage

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
        from taskweavn.interaction import AgentMessage as _AgentMessage

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

    def _prepare_llm_call(
        self,
        messages: list[dict[str, Any]],
        step: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.context_provider is None:
            return messages, {}
        if self._current_task_id is None or self._current_agent_run_id is None:
            raise LoopError("context provider requires an active AgentLoop.run")

        from taskweavn.context.agent_loop_provider import AgentLoopContextRequest

        rendered = self.context_provider.build_for_llm_call(
            AgentLoopContextRequest(
                session_id=self.session_id,
                task_id=self._current_task_id,
                agent_id="default_agent",
                agent_run_id=self._current_agent_run_id,
                turn_index=step,
                loop_messages=tuple(dict(message) for message in messages),
                tool_names=tuple(tool.name for tool in self.tools) + (FINISH_TOOL_NAME,),
                pending_decision_count=len(self._pending_decisions),
            )
        )
        metadata = {
            "context_snapshot_id": rendered.snapshot_id,
            "context_trace_id": rendered.trace_id,
            "context_renderer_version": rendered.renderer_version,
        }
        return [dict(message) for message in rendered.messages], metadata

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
            action = AgentFinishAction(final_answer=f"(failed to parse finish arguments: {exc})")
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

    def _handle_llm_error(self, exc: Exception, step: int) -> AgentErrorObservation:
        """Convert a pre-Action LLM failure into an EventStream observation.

        The Runtime can only produce :class:`ErrorObservation` after an Action
        exists. Provider failures happen earlier, while asking the model for
        the next tool call, so they need their own loop-level event.
        """
        model_name = getattr(self.llm, "model", None)
        if model_name is not None and not isinstance(model_name, str):
            model_name = repr(model_name)
        return AgentErrorObservation(
            error_type="llm_error",
            message=f"{type(exc).__name__}: {exc}",
            phase="llm_chat",
            step=step,
            model_name=model_name,
            task_id=self._current_task_id,
        )

    def _handle_context_error(self, exc: Exception, step: int) -> AgentErrorObservation:
        return AgentErrorObservation(
            error_type="context_build_error",
            message=f"{type(exc).__name__}: {exc}",
            phase="context_build",
            step=step,
            model_name=None,
            task_id=self._current_task_id,
        )

    def _publish_loop_error(self, observation: AgentErrorObservation) -> None:
        """Optionally mirror a loop-level failure to MessageStream."""
        if self.bus is None:
            return
        from taskweavn.interaction import AgentMessage as _AgentMessage

        noun = "LLM request" if observation.error_type == "llm_error" else "Context build"
        message = _AgentMessage(
            session_id=self.session_id,
            task_id=self._current_task_id,
            agent_id="system",
            message_type="informational",
            content=f"{noun} failed during {observation.phase}: {observation.message}",
            context={
                "error_type": observation.error_type,
                "phase": observation.phase,
                "step": observation.step,
                "model_name": observation.model_name,
                "event_id": observation.event_id,
            },
        )
        # Mirroring to MessageStream is UX-only. The EventStream observation
        # above is the durable audit fact, so a message-store failure must not
        # re-crash the loop while handling the original LLM failure.
        with contextlib.suppress(Exception):
            self.bus.publish(message)

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
        messages.append({"role": "system", "content": render_audit_system_message(audit)})


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
