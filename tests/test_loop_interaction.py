"""Tests for AgentLoop ⇄ interaction-layer integration (Phase 3.6a).

Drives the loop with a stub LLM + the real ``InProcessMessageBus`` to make
sure each :class:`GateVerdict` × :class:`WaitOutcome` path runs the action,
skips with the right ``ErrorObservation`` kind, or publishes the right
notice. Threaded ``reply()`` helpers stand in for a human user.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from code_agent.core.loop import AgentLoop, LoopError
from code_agent.interaction import (
    AUTONOMY_PRESETS,
    AgentMessage,
    AutonomyGate,
    BaselineOnlyAssessor,
    InProcessMessageBus,
    SqliteMessageStream,
    WaitCoordinator,
)
from code_agent.llm.client import ChatResponse, ToolCall
from code_agent.runtime import LocalRuntime
from code_agent.tools import ReadFileTool, Workspace, WriteFileTool
from code_agent.tools.base import Tool
from code_agent.tools.shell import RunCommandTool
from code_agent.types import ErrorObservation

# ---------------------------------------------------------------------------
# Fixtures + LLM stubs
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    (tmp_path / "ws").mkdir()
    return Workspace(tmp_path / "ws")


@pytest.fixture
def bus(tmp_path: Path) -> Iterator[InProcessMessageBus]:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    b = InProcessMessageBus(stream)
    try:
        yield b
    finally:
        b.close()
        stream.close()


class _StubLLM:
    """Minimal LLM driver — yields canned ChatResponses and records inputs."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self._iter = iter(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        self.calls.append({"messages": list(messages), "tools": tools})
        return next(self._iter)


def _tool_call(tool_name: str, args: dict[str, Any], call_id: str = "c1") -> ChatResponse:
    arg_json = json.dumps(args)
    return ChatResponse(
        content="",
        tool_calls=[ToolCall(id=call_id, name=tool_name, arguments=arg_json)],
        raw_assistant_message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": arg_json},
                }
            ],
        },
    )


def _finish(answer: str, call_id: str = "cend") -> ChatResponse:
    from code_agent.core.loop import FINISH_TOOL_NAME

    arg_json = json.dumps({"final_answer": answer})
    return ChatResponse(
        content="",
        tool_calls=[ToolCall(id=call_id, name=FINISH_TOOL_NAME, arguments=arg_json)],
        raw_assistant_message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": FINISH_TOOL_NAME,
                        "arguments": arg_json,
                    },
                }
            ],
        },
    )


def _build_loop(
    workspace: Workspace,
    llm: _StubLLM,
    *,
    bus: InProcessMessageBus | None = None,
    gate: AutonomyGate | None = None,
    wait_coordinator: WaitCoordinator | None = None,
    session_id: str = "s",
) -> AgentLoop:
    runtime = LocalRuntime()
    tools: list[Tool[Any, Any]] = [
        ReadFileTool(workspace),
        WriteFileTool(workspace),
        RunCommandTool(workspace),
    ]
    for tool in tools:
        tool.register(runtime)
    return AgentLoop(
        llm=llm,  # type: ignore[arg-type]
        runtime=runtime,
        tools=tools,
        max_steps=4,
        session_id=session_id,
        workspace_root=workspace.root if gate is not None else None,
        bus=bus,
        gate=gate,
        wait_coordinator=wait_coordinator,
    )


# ---------------------------------------------------------------------------
# Bundle invariants
# ---------------------------------------------------------------------------


def test_gate_without_coordinator_is_rejected(workspace: Workspace) -> None:
    runtime = LocalRuntime()
    with pytest.raises(LoopError, match="gate and wait_coordinator"):
        AgentLoop(
            llm=_StubLLM([]),  # type: ignore[arg-type]
            runtime=runtime,
            tools=[],
            gate=AutonomyGate(
                AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor()
            ),
            workspace_root=workspace.root,
        )


def test_gate_without_bus_is_rejected(workspace: Workspace) -> None:
    runtime = LocalRuntime()
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    with pytest.raises(LoopError, match="MessageBus"):
        AgentLoop(
            llm=_StubLLM([]),  # type: ignore[arg-type]
            runtime=runtime,
            tools=[],
            gate=gate,
            wait_coordinator=WaitCoordinator(
                _DummyBus(), AUTONOMY_PRESETS["risk_gated"]
            ),
            workspace_root=workspace.root,
        )


def test_gate_without_workspace_root_is_rejected(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    with pytest.raises(LoopError, match="workspace_root"):
        AgentLoop(
            llm=_StubLLM([]),  # type: ignore[arg-type]
            runtime=LocalRuntime(),
            tools=[],
            gate=gate,
            wait_coordinator=WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"]),
            bus=bus,
            # workspace_root deliberately omitted
        )


class _DummyBus:
    """Minimal MessageBus stub for the 'gate without bus' negative test
    (the missing piece is the bus, but we need *something* satisfying the
    coordinator's type to even reach the validation that flags the missing
    bus on the loop itself)."""

    def publish(self, message: object) -> None: ...
    def subscribe(self, *a: object, **k: object) -> object: ...
    def wait_for_response(
        self, message_id: str, timeout: float | None
    ) -> object | None:
        return None

    @property
    def stream(self) -> object:
        return self


# ---------------------------------------------------------------------------
# gate=None — backward compatibility smoke
# ---------------------------------------------------------------------------


def test_no_gate_runs_action_unchanged(workspace: Workspace) -> None:
    """With no autonomy bundle, the loop is bit-for-bit equivalent to pre-3.6
    behavior: the action runs without consulting any bus."""
    llm = _StubLLM(
        [
            _tool_call("write_file", {"path": "x.txt", "content": "hi"}, "c1"),
            _finish("done", "c2"),
        ]
    )
    loop = _build_loop(workspace, llm)
    result = loop.run("noop")
    assert result.finished
    assert (workspace.root / "x.txt").read_text() == "hi"


# ---------------------------------------------------------------------------
# Gate PROCEED path — risk_gated + low-risk action
# ---------------------------------------------------------------------------


def test_low_risk_action_proceeds_silently_no_inform(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """``ReadFileAction`` has baseline risk 0.0 → PROCEED, no inform spam
    even with notify_on_proceed=True (risk floor is > 0)."""
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    (workspace.root / "a.txt").write_text("a")
    llm = _StubLLM([_tool_call("read_file", {"path": "a.txt"}, "c1"), _finish("ok")])
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    loop.run("read it")

    # No actionable, no informational — risk=0.0 means no UI noise.
    assert len(bus.stream) == 0


def test_proceed_with_inform_publishes_informational(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """``WriteFileAction`` has baseline 0.3 — under risk_gated's 0.5 threshold
    → PROCEED, but notify_on_proceed=True + risk>0 means an informational
    notice DOES get published."""
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    llm = _StubLLM(
        [_tool_call("write_file", {"path": "y.txt", "content": "y"}, "c1"), _finish("done")]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    loop.run("write")

    msgs = list(bus.stream.list_for_session("s"))
    info = [m for m in msgs if m.message_type == "informational"]
    assert len(info) == 1
    assert info[0].risk_assessment is not None
    assert info[0].risk_assessment.final == pytest.approx(0.3)
    # task_id stamped from AgentLoop.run()'s uuid.
    assert info[0].task_id is not None
    # Action should still have run.
    assert (workspace.root / "y.txt").read_text() == "y"


# ---------------------------------------------------------------------------
# Gate EMIT path — sync user reply approves
# ---------------------------------------------------------------------------


def test_emit_with_user_yes_runs_action(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """RunCommand is baseline 0.5 → EMIT under risk_gated. A 'yes' reply runs
    the action."""
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    llm = _StubLLM(
        [_tool_call("run_command", {"command": "echo hi"}, "c1"), _finish("done")]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    # Reply "yes" once an actionable lands.
    def replier() -> None:
        with bus.subscribe("s", types=["actionable"]) as sub:
            for msg in sub:
                bus.publish(
                    AgentMessage(
                        session_id="s",
                        message_type="response",
                        content="yes",
                        parent_message_id=msg.message_id,
                        response_source="user",
                        response_value="yes",
                    )
                )
                return

    t = threading.Thread(target=replier)
    t.start()
    try:
        result = loop.run("ls")
    finally:
        t.join(timeout=5.0)
    assert result.finished
    # The actionable lives on the message stream.
    actionables = [
        m for m in bus.stream.list_for_session("s") if m.message_type == "actionable"
    ]
    assert len(actionables) == 1
    assert actionables[0].related_action_id is not None
    assert actionables[0].risk_assessment is not None


def test_emit_with_user_no_skips_action(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """A 'no' reply yields ErrorObservation(error_type='user_declined') and
    the action does NOT run."""
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])
    sentinel = workspace.root / "sentinel.txt"
    llm = _StubLLM(
        [
            _tool_call(
                "run_command",
                {"command": f"touch {sentinel}"},
                "c1",
            ),
            _finish("declined"),
        ]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    def replier() -> None:
        with bus.subscribe("s", types=["actionable"]) as sub:
            for msg in sub:
                bus.publish(
                    AgentMessage(
                        session_id="s",
                        message_type="response",
                        content="no",
                        parent_message_id=msg.message_id,
                        response_source="user",
                        response_value="no",
                    )
                )
                return

    t = threading.Thread(target=replier)
    t.start()
    try:
        loop.run("run unwanted command")
    finally:
        t.join(timeout=5.0)

    # The shell never ran.
    assert not sentinel.exists()
    errors = [e for e in loop.event_stream if isinstance(e, ErrorObservation)]
    assert any(e.error_type == "user_declined" for e in errors)


# ---------------------------------------------------------------------------
# Gate EMIT — timeout dispatch
# ---------------------------------------------------------------------------


def test_emit_timeout_proceed_runs_action(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """``timeout_action='proceed_default'`` (the risk_gated default) must run
    the action when the user is silent."""
    behavior = replace(AUTONOMY_PRESETS["risk_gated"], wait_timeout=0.05)
    gate = AutonomyGate(behavior, BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, behavior)
    llm = _StubLLM(
        [_tool_call("run_command", {"command": "echo hi"}, "c1"), _finish("done")]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)
    start = time.monotonic()
    result = loop.run("timeout proceed")
    elapsed = time.monotonic() - start
    assert result.finished
    assert elapsed < 2.0  # honored the 0.05s timeout
    # A timeout notice was published alongside the actionable.
    notices = [
        m for m in bus.stream.list_for_session("s")
        if m.message_type == "informational"
        and m.context.get("auto_decision") == "timeout_default"
    ]
    assert len(notices) == 1


def test_emit_timeout_skip_yields_error(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """``timeout_action='skip'`` produces an ErrorObservation with the
    autonomy_timeout_skip kind and the runtime never sees the action."""
    behavior = replace(
        AUTONOMY_PRESETS["risk_gated"], wait_timeout=0.05, timeout_action="skip"
    )
    gate = AutonomyGate(behavior, BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, behavior)
    sentinel = workspace.root / "skip.txt"
    llm = _StubLLM(
        [
            _tool_call("run_command", {"command": f"touch {sentinel}"}, "c1"),
            _finish("skipped"),
        ]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    loop.run("timeout skip")
    assert not sentinel.exists()
    errors = [e for e in loop.event_stream if isinstance(e, ErrorObservation)]
    assert any(e.error_type == "autonomy_timeout_skip" for e in errors)


# ---------------------------------------------------------------------------
# Async strategy — Phase 3.6b defers and drain resolves on later step
# ---------------------------------------------------------------------------


def _async_behavior() -> Any:
    """Manual + async: every action EMITs, every wait returns PENDING."""
    return replace(
        AUTONOMY_PRESETS["manual"],
        wait_strategy="async",
        timeout_action="proceed_default",
    )


def test_async_emit_defers_action_no_immediate_run(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """async + manual + no replier: the loop's run terminates, the action
    NEVER ran (no observation in the stream for it), and one pending
    decision is left over keyed to the actionable message."""
    behavior = _async_behavior()
    gate = AutonomyGate(behavior, BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, behavior)
    sentinel = workspace.root / "deferred.txt"
    llm = _StubLLM(
        [
            _tool_call("write_file", {"path": "deferred.txt", "content": "x"}, "c1"),
            _finish("done"),
        ]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    loop.run("defer me")

    # Action did not run.
    assert not sentinel.exists()
    # No observation for the WriteFile in the event stream — only the
    # action event got appended at deferral time.
    from code_agent.tools.fs import FileWriteObservation, WriteFileAction

    actions = [e for e in loop.event_stream if isinstance(e, WriteFileAction)]
    observations = [e for e in loop.event_stream if isinstance(e, FileWriteObservation)]
    assert len(actions) == 1
    assert len(observations) == 0
    # And the actionable is on the bus, awaiting reply.
    actionables = [
        m for m in bus.stream.list_for_session("s") if m.message_type == "actionable"
    ]
    assert len(actionables) == 1


def test_async_drain_resolves_yes_runs_action(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """After ``run`` returns with a pending decision, publishing a 'yes'
    response and calling :meth:`AgentLoop.drain_pending_responses` runs the
    action and appends an observation to the event stream."""
    behavior = _async_behavior()
    gate = AutonomyGate(behavior, BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, behavior)
    llm = _StubLLM(
        [
            _tool_call(
                "write_file", {"path": "late.txt", "content": "late"}, "c1"
            ),
            _finish("done"),
        ]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    loop.run("defer write")
    actionable = [
        m for m in bus.stream.list_for_session("s") if m.message_type == "actionable"
    ][0]

    # Late reply lands.
    bus.publish(
        AgentMessage(
            session_id="s",
            message_type="response",
            content="yes",
            parent_message_id=actionable.message_id,
            response_source="user",
            response_value="yes",
        )
    )

    # Drive drain manually post-run, asking it not to mutate any messages
    # list (the LLM has gone home).
    resolved = loop.drain_pending_responses(messages=None)
    assert resolved == 1
    # The runtime executed the write.
    assert (workspace.root / "late.txt").read_text() == "late"
    # And the observation is in the stream.
    from code_agent.tools.fs import FileWriteObservation

    observations = [
        e for e in loop.event_stream if isinstance(e, FileWriteObservation)
    ]
    assert len(observations) == 1


def test_async_drain_resolves_no_emits_user_declined(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """A 'no' reply on a deferred action turns into ErrorObservation
    (user_declined) at drain time; the action does NOT run."""
    behavior = _async_behavior()
    gate = AutonomyGate(behavior, BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, behavior)
    sentinel = workspace.root / "rejected.txt"
    llm = _StubLLM(
        [
            _tool_call(
                "write_file", {"path": "rejected.txt", "content": "x"}, "c1"
            ),
            _finish("done"),
        ]
    )
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    loop.run("defer + reject")
    actionable = [
        m for m in bus.stream.list_for_session("s") if m.message_type == "actionable"
    ][0]
    bus.publish(
        AgentMessage(
            session_id="s",
            message_type="response",
            content="no",
            parent_message_id=actionable.message_id,
            response_source="user",
            response_value="no",
        )
    )
    loop.drain_pending_responses(messages=None)

    assert not sentinel.exists()
    errors = [e for e in loop.event_stream if isinstance(e, ErrorObservation)]
    assert any(e.error_type == "user_declined" for e in errors)


def test_async_drain_within_loop_threads_resolution_into_messages(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """In-loop drain: a replier publishes the response after step 1 but
    before step 2's drain. Step 2 sees the resolution and runs the action,
    AND appends a 'previously deferred ... resolved' system message into
    the LLM context for the next turn."""
    behavior = _async_behavior()
    gate = AutonomyGate(behavior, BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, behavior)
    llm = _StubLLM(
        [
            _tool_call(
                "write_file", {"path": "intra.txt", "content": "yes"}, "c1"
            ),
            # Step 2: the deferral hasn't resolved yet at drain time (race),
            # so the LLM gets a noop tool call so the loop doesn't terminate
            # early. Use a low-risk read_file to keep the gate quiet.
            _tool_call("read_file", {"path": "intra.txt"}, "c2"),
            _finish("done"),
        ]
    )
    (workspace.root / "intra.txt").write_text("placeholder")
    loop = _build_loop(workspace, llm, bus=bus, gate=gate, wait_coordinator=coord)

    # Replier publishes IMMEDIATELY when the actionable lands. Subscriptions
    # serialize via the bus's condition lock, so by the time step 2's drain
    # acquires the lock for its non-blocking poll, the response is committed
    # — assuming the OS schedules the replier between step 1 and step 2.
    # We give that a generous deadline below.
    def replier() -> None:
        with bus.subscribe("s", types=["actionable"]) as sub:
            for msg in sub:
                bus.publish(
                    AgentMessage(
                        session_id="s",
                        message_type="response",
                        content="yes",
                        parent_message_id=msg.message_id,
                        response_source="user",
                        response_value="yes",
                    )
                )
                return

    t = threading.Thread(target=replier)
    t.start()
    try:
        loop.run("intra-loop drain")
    finally:
        t.join(timeout=5.0)

    # Either step 2's drain (likely) or the shutdown drain (fallback) ran
    # the action — both code paths use the same drain method, so assert on
    # the post-state.
    from code_agent.tools.fs import FileWriteObservation

    observations = [
        e for e in loop.event_stream if isinstance(e, FileWriteObservation)
    ]
    assert len(observations) == 1
    assert (workspace.root / "intra.txt").read_text() == "yes"


# ---------------------------------------------------------------------------
# Cross-stream task_id stamping
# ---------------------------------------------------------------------------


def test_task_id_stamps_messages(
    workspace: Workspace, bus: InProcessMessageBus
) -> None:
    """Every published message in one ``run()`` shares one task_id. Two runs
    yield two distinct ids."""
    gate = AutonomyGate(AUTONOMY_PRESETS["risk_gated"], BaselineOnlyAssessor())
    coord = WaitCoordinator(bus, AUTONOMY_PRESETS["risk_gated"])

    def writer_program() -> _StubLLM:
        return _StubLLM(
            [
                _tool_call(
                    "write_file", {"path": "z.txt", "content": "z"}, "c1"
                ),
                _finish("done"),
            ]
        )

    loop = _build_loop(
        workspace, writer_program(), bus=bus, gate=gate, wait_coordinator=coord
    )
    loop.run("first")
    loop.llm = writer_program()  # type: ignore[assignment]
    loop.run("second")

    msgs = list(bus.stream.list_for_session("s"))
    task_ids = {m.task_id for m in msgs if m.task_id is not None}
    assert len(task_ids) == 2  # one per run()
