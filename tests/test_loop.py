"""Tests for the ReAct AgentLoop (1.5)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from taskweavn.context import (
    AgentLoopContextCallResult,
    AgentLoopContextRequest,
    InMemoryContextStore,
    RenderedLlmInput,
    SessionAgentLoopContextProvider,
    SessionContextManager,
    TaskContextSource,
)
from taskweavn.core import SqliteEventStream
from taskweavn.core.loop import (
    FINISH_TOOL_NAME,
    AgentLoop,
    LoopError,
    LoopInterruptIntent,
)
from taskweavn.interaction import InMemoryAskStore
from taskweavn.llm.client import ChatResponse, ToolCall
from taskweavn.observability import configure_session_logging
from taskweavn.runtime import LocalRuntime
from taskweavn.task import InMemoryTaskBus, TaskDomain
from taskweavn.tools import (
    AskUserTool,
    ReadFileTool,
    Workspace,
    WriteFileTool,
)
from taskweavn.types import (
    AgentErrorObservation,
    AgentFinishAction,
    AgentFinishObservation,
    BaseAction,
    BaseObservation,
    ErrorObservation,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


class StubLLM:
    """Returns canned ChatResponses in order."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self._iter: Iterator[ChatResponse] = iter(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append({"messages": list(messages), "tools": tools, "metadata": metadata})
        try:
            return next(self._iter)
        except StopIteration as exc:  # pragma: no cover — test misconfig signal
            raise AssertionError("StubLLM ran out of canned responses") from exc


class FailingLLM:
    model = "test/failing-model"

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append({"messages": list(messages), "tools": tools, "metadata": metadata})
        raise self.exc


class SequenceInterruptChecker:
    def __init__(self, *, interrupt_on_call: int) -> None:
        self.interrupt_on_call = interrupt_on_call
        self.calls: list[str] = []

    def interrupt_for_task(self, task_id: str) -> LoopInterruptIntent | None:
        self.calls.append(task_id)
        if len(self.calls) != self.interrupt_on_call:
            return None
        return LoopInterruptIntent(
            task_id=task_id,
            request_id="stop-1",
            reason="user requested stop",
            requested_by="user",
        )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _finish_response(answer: str, call_id: str = "c1") -> ChatResponse:
    args = json.dumps({"final_answer": answer})
    tc = ToolCall(id=call_id, name=FINISH_TOOL_NAME, arguments=args)
    return ChatResponse(
        content="",
        tool_calls=[tc],
        raw_assistant_message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": FINISH_TOOL_NAME, "arguments": args},
                }
            ],
        },
    )


def _tool_call_response(
    tool_name: str, arguments: dict[str, Any], call_id: str = "c1", thought: str = ""
) -> ChatResponse:
    args = json.dumps(arguments)
    tc = ToolCall(id=call_id, name=tool_name, arguments=args)
    return ChatResponse(
        content=thought,
        tool_calls=[tc],
        raw_assistant_message={
            "role": "assistant",
            "content": thought,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": args},
                }
            ],
        },
    )


def _build_loop(
    workspace: Workspace,
    llm: StubLLM,
    *,
    max_steps: int = 5,
) -> AgentLoop:
    from taskweavn.tools.base import Tool

    runtime = LocalRuntime()
    tools: list[Tool[Any, Any]] = [
        ReadFileTool(workspace),
        WriteFileTool(workspace),
    ]
    for tool in tools:
        tool.register(runtime)
    return AgentLoop(
        llm=llm,  # type: ignore[arg-type]
        runtime=runtime,
        tools=tools,
        max_steps=max_steps,
    )


def test_loop_stops_when_ask_user_blocks_current_task() -> None:
    task = TaskDomain(
        task_id="task-1",
        session_id="session-1",
        root_id="task-1",
        intent="Choose a deployment target.",
        required_capability="general",
        created_by="tester",
    )
    task_bus = InMemoryTaskBus([task])
    claimed = task_bus.claim_next(
        "session-1",
        capability="general",
        agent_id="default_agent",
    )
    assert claimed is not None
    ask_store = InMemoryAskStore()
    runtime = LocalRuntime()
    tool = AskUserTool(
        ask_store=ask_store,
        task_bus=task_bus,
        session_id="session-1",
        task_id="task-1",
    )
    tool.register(runtime)
    llm = StubLLM(
        [
            _tool_call_response(
                "ask_user",
                {
                    "question": "Which deployment target should be used?",
                    "reason": "Deployment target is a user-owned decision.",
                    "suggested_options": ["Vercel", "Netlify"],
                },
                call_id="ask-call-1",
            )
        ]
    )
    loop = AgentLoop(
        llm=llm,  # type: ignore[arg-type]
        runtime=runtime,
        tools=[tool],
        session_id="session-1",
    )

    result = loop.run("Choose deployment target.", task_id="task-1")

    waiting_task = task_bus.get("session-1", "task-1")
    asks = ask_store.list_for_session("session-1", statuses=("pending",), task_id="task-1")
    assert result.finished is False
    assert result.stop_reason == "waiting_for_user"
    assert waiting_task is not None
    assert waiting_task.status == "waiting_for_user"
    assert len(asks) == 1
    assert waiting_task.waiting_for_ask_id == asks[0].ask_id
    assert asks[0].suggested_options[0].label == "Vercel"


def test_loop_persists_batched_ask_user_questions() -> None:
    task = TaskDomain(
        task_id="task-1",
        session_id="session-1",
        root_id="task-1",
        intent="Clarify portfolio requirements.",
        required_capability="general",
        created_by="tester",
    )
    task_bus = InMemoryTaskBus([task])
    assert (
        task_bus.claim_next(
            "session-1",
            capability="general",
            agent_id="default_agent",
        )
        is not None
    )
    ask_store = InMemoryAskStore()
    runtime = LocalRuntime()
    tool = AskUserTool(
        ask_store=ask_store,
        task_bus=task_bus,
        session_id="session-1",
        task_id="task-1",
    )
    tool.register(runtime)
    llm = StubLLM(
        [
            _tool_call_response(
                "ask_user",
                {
                    "question": "Portfolio planning details",
                    "reason": "The portfolio task needs user-owned details.",
                    "questions": [
                        {
                            "question_id": "role",
                            "question": "What is your professional role?",
                        },
                        {
                            "question_id": "goal",
                            "question": "What is the main goal?",
                            "input_hint": "Find work, attract clients, build a brand...",
                        },
                    ],
                },
                call_id="ask-call-1",
            )
        ]
    )
    loop = AgentLoop(
        llm=llm,  # type: ignore[arg-type]
        runtime=runtime,
        tools=[tool],
        session_id="session-1",
    )

    result = loop.run("Clarify portfolio requirements.", task_id="task-1")

    asks = ask_store.list_for_session("session-1", statuses=("pending",), task_id="task-1")
    assert result.stop_reason == "waiting_for_user"
    assert len(asks) == 1
    assert [question.question_id for question in asks[0].questions] == [
        "role",
        "goal",
    ]
    assert asks[0].questions[1].input_hint == (
        "Find work, attract clients, build a brand..."
    )


def test_agent_loop_logs_execution_agent_llm_input_and_output(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="session-1")
    llm = StubLLM([_finish_response("done")])
    loop = AgentLoop(
        llm=llm,  # type: ignore[arg-type]
        runtime=LocalRuntime(),
        tools=[],
        session_id="session-1",
        max_steps=1,
    )

    result = loop.run("Finish the task.", task_id="task-1")

    assert result.finished
    meta_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "llm.jsonl"
    )
    io_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "llm_io.jsonl"
    )
    meta_agent_rows = [
        row for row in meta_rows if row["event"] in {"agent_input", "agent_output"}
    ]
    io_agent_rows = [
        row for row in io_rows if row["event"] in {"agent_input", "agent_output"}
    ]
    assert [row["event"] for row in meta_agent_rows] == [
        "agent_input",
        "agent_output",
    ]
    assert [row["event"] for row in io_agent_rows] == [
        "agent_input",
        "agent_output",
    ]
    input_row, output_row = meta_agent_rows
    input_io_row, output_io_row = io_agent_rows

    assert input_row["context"] == {
        "session_id": "session-1",
        "task_id": "task-1",
        "agent_id": "default_agent",
    }
    assert input_row["data"]["agent_kind"] == "execution_agent"
    assert input_row["data"]["request_purpose"] == "execution.agent_loop.step"
    assert "messages" not in input_row["data"]
    assert input_io_row["data"]["input"]["messages"][1] == {
        "role": "user",
        "content": "Finish the task.",
    }
    assert input_row["data"]["metadata"]["session_id"] == "session-1"
    assert input_row["data"]["metadata"]["task_id"] == "task-1"
    assert (
        input_io_row["data"]["input"]["tools"][0]["function"]["name"]
        == FINISH_TOOL_NAME
    )

    assert output_row["context"] == input_row["context"]
    assert output_row["data"]["agent_kind"] == "execution_agent"
    assert output_row["data"]["request_purpose"] == "execution.agent_loop.step"
    assert output_row["data"]["tool_calls"][0]["name"] == FINISH_TOOL_NAME
    assert "raw_assistant_message" not in output_row["data"]
    assert (
        output_io_row["data"]["output"]["raw_assistant_message"]["role"]
        == "assistant"
    )


class PersistingContextProvider:
    def __init__(self) -> None:
        self.requests: list[AgentLoopContextRequest] = []

    def prepare_llm_call(
        self,
        request: AgentLoopContextRequest,
    ) -> AgentLoopContextCallResult:
        self.requests.append(request)
        if len(self.requests) == 1:
            messages = (
                {"role": "system", "content": "managed system"},
                {"role": "user", "content": "# Task Start Context\nmanaged task"},
            )
            rendered = RenderedLlmInput(
                renderer_version="test.renderer",
                system_content="managed system",
                user_content="# Task Start Context\nmanaged task",
                messages=messages,
                rendered_input_hash="sha256:first",
                snapshot_id="ctx-1",
                trace_id="trace-1",
                render_mode="start_context",
                stable_prefix_hash="sha256:stable",
            )
            return AgentLoopContextCallResult(
                llm_messages=messages,
                persisted_messages=messages,
                rendered=rendered,
                render_mode="start_context",
                stable_prefix_hash="sha256:stable",
            )

        rendered = RenderedLlmInput(
            renderer_version="test.renderer",
            system_content="reuse",
            user_content="reuse",
            messages=request.loop_messages,
            rendered_input_hash="sha256:second",
            snapshot_id="ctx-2",
            trace_id="trace-2",
            render_mode="delta_context",
            stable_prefix_hash="sha256:stable",
        )
        return AgentLoopContextCallResult(
            llm_messages=request.loop_messages,
            persisted_messages=request.loop_messages,
            rendered=rendered,
            render_mode="delta_context",
            stable_prefix_hash="sha256:stable",
        )

    def build_for_llm_call(self, request: AgentLoopContextRequest) -> RenderedLlmInput:
        raise AssertionError("AgentLoop should prefer prepare_llm_call")


def test_loop_terminates_on_agent_finish(workspace: Workspace) -> None:
    llm = StubLLM([_finish_response("all done")])
    loop = _build_loop(workspace, llm)
    result = loop.run("noop task")

    assert result.finished is True
    assert result.stop_reason == "agent_finish"
    assert result.final_answer == "all done"
    assert result.steps == 1

    events = list(loop.event_stream)
    assert len(events) == 2
    assert isinstance(events[0], AgentFinishAction)
    assert isinstance(events[1], AgentFinishObservation)


def test_loop_terminates_on_no_tool_calls(workspace: Workspace) -> None:
    llm = StubLLM(
        [
            ChatResponse(
                content="I have nothing to do.",
                tool_calls=[],
                raw_assistant_message={
                    "role": "assistant",
                    "content": "I have nothing to do.",
                },
            )
        ]
    )
    loop = _build_loop(workspace, llm)
    result = loop.run("nothing to do")

    assert result.finished is True
    assert result.stop_reason == "no_tool_calls"
    assert result.final_answer == "I have nothing to do."
    assert list(loop.event_stream) == []


def test_loop_records_llm_chat_failure_as_event(workspace: Workspace) -> None:
    llm = FailingLLM(RuntimeError("provider 500"))
    loop = _build_loop(workspace, llm)  # type: ignore[arg-type]

    result = loop.run("trigger provider failure")

    assert result.finished is False
    assert result.stop_reason == "llm_error"
    assert result.steps == 1

    events = list(loop.event_stream)
    assert len(events) == 1
    assert isinstance(events[0], AgentErrorObservation)
    assert events[0].error_type == "llm_error"
    assert events[0].phase == "llm_chat"
    assert events[0].step == 1
    assert events[0].model_name == "test/failing-model"
    assert "provider 500" in events[0].message


def test_loop_records_llm_timeout_as_distinct_stop_reason(workspace: Workspace) -> None:
    llm = FailingLLM(TimeoutError("provider timed out"))
    loop = _build_loop(workspace, llm)  # type: ignore[arg-type]

    result = loop.run("trigger provider timeout")

    assert result.finished is False
    assert result.stop_reason == "llm_timeout"
    assert result.steps == 1
    assert "provider timed out" in result.final_answer

    events = list(loop.event_stream)
    assert len(events) == 1
    assert isinstance(events[0], AgentErrorObservation)
    assert events[0].error_type == "llm_timeout"
    assert events[0].phase == "llm_chat"
    assert events[0].step == 1


def test_loop_maps_llm_timeout_to_interrupted_when_stop_requested(
    workspace: Workspace,
) -> None:
    llm = FailingLLM(TimeoutError("provider timed out"))
    loop = _build_loop(workspace, llm)  # type: ignore[arg-type]
    loop.interrupt_checker = SequenceInterruptChecker(interrupt_on_call=4)

    result = loop.run("trigger provider timeout", task_id="task-1")

    assert result.finished is False
    assert result.stop_reason == "interrupted"
    assert result.final_answer == (
        "cancelled: user requested stop; safe_point=llm_timeout"
    )
    events = list(loop.event_stream)
    assert len(events) == 1
    assert isinstance(events[0], AgentErrorObservation)
    assert events[0].error_type == "interrupted"
    assert events[0].phase == "llm_timeout"


def test_loop_stops_before_llm_call_when_interrupt_requested(workspace: Workspace) -> None:
    llm = StubLLM([_finish_response("should not run")])
    loop = _build_loop(workspace, llm)
    loop.interrupt_checker = SequenceInterruptChecker(interrupt_on_call=1)

    result = loop.run("write hello.txt", task_id="task-1")

    assert result.finished is False
    assert result.stop_reason == "interrupted"
    assert result.final_answer.startswith("cancelled: user requested stop")
    assert llm.calls == []
    events = list(loop.event_stream)
    assert len(events) == 1
    assert isinstance(events[0], AgentErrorObservation)
    assert events[0].error_type == "interrupted"
    assert events[0].phase == "step_start"


def test_loop_stops_before_tool_dispatch_when_interrupt_requested(
    workspace: Workspace,
) -> None:
    llm = StubLLM(
        [
            _tool_call_response(
                "write_file",
                {"path": "hello.txt", "content": "hi"},
                call_id="c1",
            )
        ]
    )
    loop = _build_loop(workspace, llm)
    loop.interrupt_checker = SequenceInterruptChecker(interrupt_on_call=4)

    result = loop.run("write hello.txt", task_id="task-1")

    assert result.finished is False
    assert result.stop_reason == "interrupted"
    assert not (workspace.root / "hello.txt").exists()
    events = list(loop.event_stream)
    assert len(events) == 1
    assert isinstance(events[0], AgentErrorObservation)
    assert events[0].error_type == "interrupted"
    assert events[0].phase == "after_llm_response"


def test_loop_executes_tool_then_finishes(workspace: Workspace) -> None:
    llm = StubLLM(
        [
            _tool_call_response(
                "write_file",
                {"path": "hello.txt", "content": "hi"},
                call_id="c1",
                thought="I will write the file.",
            ),
            _finish_response("wrote hello.txt", call_id="c2"),
        ]
    )
    loop = _build_loop(workspace, llm)
    result = loop.run("write hello.txt")

    assert result.finished is True
    assert result.stop_reason == "agent_finish"
    assert (workspace.root / "hello.txt").read_text() == "hi"

    events = list(loop.event_stream)
    kinds = [type(e).__name__ for e in events]
    assert kinds[0] == "WriteFileAction"
    assert kinds[1] == "FileWriteObservation"
    assert kinds[2] == "AgentFinishAction"
    assert kinds[3] == "AgentFinishObservation"

    # Second LLM call should include the tool message from the first step.
    second_call_messages = llm.calls[1]["messages"]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "c1"
    assert "bytes_written" in tool_msgs[0]["content"]


def test_loop_persists_context_provider_messages_before_next_llm_call(
    workspace: Workspace,
) -> None:
    llm = StubLLM(
        [
            _tool_call_response(
                "write_file",
                {"path": "hello.txt", "content": "hi"},
                call_id="c1",
            ),
            _finish_response("wrote hello.txt", call_id="c2"),
        ]
    )
    provider = PersistingContextProvider()
    loop = _build_loop(workspace, llm)
    loop.context_provider = provider

    result = loop.run("write hello.txt", task_id="task-1")

    assert result.finished is True
    assert provider.requests[0].loop_messages[0]["content"] == loop.system_prompt
    assert provider.requests[1].loop_messages[0]["content"] == "managed system"
    assert provider.requests[1].loop_messages[1]["content"].startswith("# Task Start Context")
    assert any(message.get("role") == "tool" for message in provider.requests[1].loop_messages)
    assert llm.calls[0]["messages"][0]["content"] == "managed system"
    assert llm.calls[1]["messages"][0]["content"] == "managed system"
    assert llm.calls[0]["metadata"]["context_render_mode"] == "start_context"
    assert llm.calls[1]["metadata"]["context_render_mode"] == "delta_context"
    assert llm.calls[1]["metadata"]["context_stable_prefix_hash"] == "sha256:stable"


def test_loop_observes_checkpoint_interval_and_stable_prefix(
    workspace: Workspace,
) -> None:
    llm = StubLLM(
        [
            _tool_call_response(
                "write_file",
                {"path": "one.txt", "content": "one"},
                call_id="c1",
            ),
            _tool_call_response(
                "write_file",
                {"path": "two.txt", "content": "two"},
                call_id="c2",
            ),
            _finish_response("done", call_id="c3"),
        ]
    )
    task_bus = InMemoryTaskBus()
    task_bus.publish(
        TaskDomain(
            task_id="task-cache-observation",
            session_id="default",
            root_id="task-cache-observation",
            intent="Observe cache-aware checkpoint behavior",
            required_capability="general",
            created_by="tester",
        )
    )
    store = InMemoryContextStore()
    manager = SessionContextManager(
        task_source=TaskContextSource(task_bus),
        store=store,
    )
    provider = SessionAgentLoopContextProvider(manager, checkpoint_interval_steps=2)
    loop = _build_loop(workspace, llm, max_steps=3)
    loop.context_provider = provider

    result = loop.run("observe cache-aware behavior", task_id="task-cache-observation")

    assert result.finished is True
    assert result.steps == 3
    assert [call["metadata"]["context_render_mode"] for call in llm.calls] == [
        "start_context",
        "checkpoint_context",
        "delta_context",
    ]
    assert [call["metadata"]["context_appended_message_count"] for call in llm.calls] == [
        0,
        1,
        0,
    ]
    assert llm.calls[1]["metadata"]["context_checkpoint_reason"] == "interval:2"
    assert (
        llm.calls[0]["metadata"]["context_stable_prefix_hash"]
        == llm.calls[1]["metadata"]["context_stable_prefix_hash"]
        == llm.calls[2]["metadata"]["context_stable_prefix_hash"]
    )

    first_messages = llm.calls[0]["messages"]
    second_messages = llm.calls[1]["messages"]
    third_messages = llm.calls[2]["messages"]
    assert second_messages[: len(first_messages)] == first_messages
    assert third_messages[: len(second_messages)] == second_messages
    assert second_messages[-1]["role"] == "system"
    assert "# Context Checkpoint" in second_messages[-1]["content"]
    assert "Reason: interval:2" in second_messages[-1]["content"]

    snapshots = store.list_snapshots_for_task(
        "default",
        "task-cache-observation",
    )
    assert [snapshot.render_mode for snapshot in snapshots] == [
        "start_context",
        "checkpoint_context",
        "delta_context",
    ]


def test_loop_tags_sqlite_events_with_supplied_task_id(
    workspace: Workspace,
    tmp_path: Path,
) -> None:
    from taskweavn.tools.base import Tool

    llm = StubLLM(
        [
            _tool_call_response(
                "write_file",
                {"path": "hello.txt", "content": "hi"},
                call_id="c1",
            ),
            _finish_response("wrote hello.txt", call_id="c2"),
        ]
    )
    runtime = LocalRuntime()
    tools: list[Tool[Any, Any]] = [
        ReadFileTool(workspace),
        WriteFileTool(workspace),
    ]
    for tool in tools:
        tool.register(runtime)

    with SqliteEventStream(tmp_path / "events.sqlite") as event_stream:
        loop = AgentLoop(
            llm=llm,  # type: ignore[arg-type]
            runtime=runtime,
            tools=tools,
            event_stream=event_stream,
        )

        loop.run("write hello.txt", task_id="published-task-1")

        task_events = list(event_stream.iter_for_task("published-task-1"))

    assert [type(event).__name__ for event in task_events] == [
        "WriteFileAction",
        "FileWriteObservation",
        "AgentFinishAction",
        "AgentFinishObservation",
    ]


def test_loop_unknown_tool_yields_error_observation(workspace: Workspace) -> None:
    llm = StubLLM(
        [
            _tool_call_response("does_not_exist", {}, call_id="c1"),
            _finish_response("gave up", call_id="c2"),
        ]
    )
    loop = _build_loop(workspace, llm)
    result = loop.run("call a missing tool")

    assert result.finished is True
    error_events = [e for e in loop.event_stream if isinstance(e, ErrorObservation)]
    assert len(error_events) == 1
    assert error_events[0].error_type == "unknown_tool"


def test_loop_invalid_arguments_yield_error_observation(
    workspace: Workspace,
) -> None:
    # write_file requires `path` and `content` — pass nothing.
    llm = StubLLM(
        [
            _tool_call_response("write_file", {}, call_id="c1"),
            _finish_response("done", call_id="c2"),
        ]
    )
    loop = _build_loop(workspace, llm)
    result = loop.run("missing args")

    assert result.finished is True
    error_events = [e for e in loop.event_stream if isinstance(e, ErrorObservation)]
    assert len(error_events) == 1
    assert error_events[0].error_type == "invalid_arguments"


def test_loop_respects_max_steps(workspace: Workspace) -> None:
    # Three identical write calls but max_steps=2 — should stop without finishing.
    response = _tool_call_response("write_file", {"path": "a.txt", "content": "a"}, call_id="c")
    llm = StubLLM([response, response, response])
    loop = _build_loop(workspace, llm, max_steps=2)
    result = loop.run("loop forever")

    assert result.finished is False
    assert result.stop_reason == "max_steps"
    assert result.steps == 2
    assert len(llm.calls) == 2


def test_loop_rejects_duplicate_tool_names(workspace: Workspace) -> None:
    runtime = LocalRuntime()
    tool = ReadFileTool(workspace)
    with pytest.raises(LoopError):
        AgentLoop(
            llm=StubLLM([]),  # type: ignore[arg-type]
            runtime=runtime,
            tools=[tool, tool],
        )


def test_loop_rejects_finish_tool_name_collision(workspace: Workspace) -> None:
    class _ShadowAction(BaseAction, kind="shadow_finish_action"):
        pass

    class _ShadowObs(BaseObservation, kind="shadow_finish_obs"):
        pass

    from typing import ClassVar

    from taskweavn.tools.base import Tool

    class ShadowFinishTool(Tool[_ShadowAction, _ShadowObs]):
        name: ClassVar[str] = FINISH_TOOL_NAME
        description: ClassVar[str] = "shadow"
        action_type: ClassVar[type[BaseAction]] = _ShadowAction
        observation_type: ClassVar[type[BaseObservation]] = _ShadowObs

        def execute(self, action: _ShadowAction) -> _ShadowObs:
            return _ShadowObs(action_id=action.event_id)

    with pytest.raises(LoopError):
        AgentLoop(
            llm=StubLLM([]),  # type: ignore[arg-type]
            runtime=LocalRuntime(),
            tools=[ShadowFinishTool()],
        )


def test_loop_runs_auditor_when_configured(workspace: Workspace) -> None:
    """When an auditor is wired in, every CodeAction execution produces an
    AuditObservation on the EventStream and a system message in the next turn."""
    from typing import ClassVar

    from taskweavn.audit import AuditAgent, AuditObservation
    from taskweavn.tools.base import Tool
    from taskweavn.types import (
        BaseAction as _BA,
    )
    from taskweavn.types import (
        BaseObservation as _BO,
    )
    from taskweavn.types.code_action import (
        CodeAction,
        CodeExecutionObservation,
    )

    class _StubCodeTool(Tool[CodeAction, CodeExecutionObservation]):
        name: ClassVar[str] = "run_code"
        description: ClassVar[str] = "stub"
        action_type: ClassVar[type[_BA]] = CodeAction
        observation_type: ClassVar[type[_BO]] = CodeExecutionObservation

        def execute(self, action: CodeAction) -> CodeExecutionObservation:
            return CodeExecutionObservation(
                action_id=action.event_id,
                intent=action.intent,
                exit_code=0,
                stdout="ok",
                stderr="",
                duration_ms=1.0,
            )

    # Auditor LLM always returns a pass verdict.
    audit_llm = StubLLM(
        [
            ChatResponse(
                content=json.dumps(
                    {
                        "verdict": "pass",
                        "rationale": "snippet matched its intent",
                        "concerns": [],
                        "intent_met": True,
                        "scope_respected": True,
                    }
                ),
                tool_calls=[],
                raw_assistant_message={"role": "assistant", "content": "x"},
            )
        ]
    )
    auditor = AuditAgent(llm=audit_llm)  # type: ignore[arg-type]

    main_llm = StubLLM(
        [
            _tool_call_response(
                "run_code",
                {
                    "intent": "noop",
                    "code": "x = 1",
                    "tracking": {"files": [], "variables": []},
                },
                call_id="c1",
            ),
            _finish_response("done", call_id="c2"),
        ]
    )

    runtime = LocalRuntime()
    tool = _StubCodeTool()
    tool.register(runtime)
    loop = AgentLoop(
        llm=main_llm,  # type: ignore[arg-type]
        runtime=runtime,
        tools=[tool],
        auditor=auditor,
    )
    loop.run("audit me")

    audits = [e for e in loop.event_stream if isinstance(e, AuditObservation)]
    assert len(audits) == 1
    assert audits[0].verdict == "pass"

    # Second main-LLM call should now have a system-role audit message in its history.
    second_messages = main_llm.calls[1]["messages"]
    audit_systems = [
        m
        for m in second_messages
        if m.get("role") == "system" and "[audit]" in m.get("content", "")
    ]
    assert len(audit_systems) == 1
    assert "verdict=pass" in audit_systems[0]["content"]


def test_loop_skips_auditor_for_non_code_actions(workspace: Workspace) -> None:
    """A WriteFileAction must NOT be audited — only CodeActions get audited."""
    from taskweavn.audit import AuditAgent, AuditObservation

    audit_llm = StubLLM([])  # would raise StopIteration if called
    auditor = AuditAgent(llm=audit_llm)  # type: ignore[arg-type]

    main_llm = StubLLM(
        [
            _tool_call_response(
                "write_file",
                {"path": "x.txt", "content": "y"},
                call_id="c1",
            ),
            _finish_response("done", call_id="c2"),
        ]
    )
    loop = _build_loop(workspace, main_llm)
    loop.auditor = auditor
    loop.run("write only")

    audits = [e for e in loop.event_stream if isinstance(e, AuditObservation)]
    assert audits == []
    assert audit_llm.calls == []  # auditor was never invoked


def test_loop_continues_when_auditor_returns_inconclusive(
    workspace: Workspace,
) -> None:
    """An inconclusive verdict must still be appended and the loop must keep going."""
    from typing import ClassVar

    from taskweavn.audit import AuditAgent, AuditObservation
    from taskweavn.tools.base import Tool
    from taskweavn.types import (
        BaseAction as _BA,
    )
    from taskweavn.types import (
        BaseObservation as _BO,
    )
    from taskweavn.types.code_action import (
        CodeAction,
        CodeExecutionObservation,
    )

    class _StubCodeTool(Tool[CodeAction, CodeExecutionObservation]):
        name: ClassVar[str] = "run_code"
        description: ClassVar[str] = "stub"
        action_type: ClassVar[type[_BA]] = CodeAction
        observation_type: ClassVar[type[_BO]] = CodeExecutionObservation

        def execute(self, action: CodeAction) -> CodeExecutionObservation:
            return CodeExecutionObservation(
                action_id=action.event_id,
                intent=action.intent,
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=1.0,
            )

    # Auditor LLM raises — agent must still record an inconclusive verdict.
    class _RaisingLLM:
        def chat(
            self,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]] | None = None,
        ) -> ChatResponse:
            raise RuntimeError("audit api 500")

    auditor = AuditAgent(llm=_RaisingLLM())  # type: ignore[arg-type]

    main_llm = StubLLM(
        [
            _tool_call_response(
                "run_code",
                {
                    "intent": "noop",
                    "code": "x = 1",
                    "tracking": {"files": [], "variables": []},
                },
                call_id="c1",
            ),
            _finish_response("done", call_id="c2"),
        ]
    )
    runtime = LocalRuntime()
    tool = _StubCodeTool()
    tool.register(runtime)
    loop = AgentLoop(
        llm=main_llm,  # type: ignore[arg-type]
        runtime=runtime,
        tools=[tool],
        auditor=auditor,
    )
    result = loop.run("inconclusive path")

    assert result.finished is True
    audits = [e for e in loop.event_stream if isinstance(e, AuditObservation)]
    assert len(audits) == 1
    assert audits[0].verdict == "inconclusive"


def test_loop_passes_tool_schemas_to_llm(workspace: Workspace) -> None:
    llm = StubLLM([_finish_response("done")])
    loop = _build_loop(workspace, llm)
    loop.run("trigger")

    tools_arg = llm.calls[0]["tools"]
    assert tools_arg is not None
    names = {t["function"]["name"] for t in tools_arg}
    assert "read_file" in names
    assert "write_file" in names
    assert FINISH_TOOL_NAME in names
    # event_id / timestamp / source must be hidden from the model.
    write_schema = next(t for t in tools_arg if t["function"]["name"] == "write_file")
    properties = write_schema["function"]["parameters"]["properties"]
    assert "event_id" not in properties
    assert "timestamp" not in properties
    assert "source" not in properties
    assert "path" in properties
    assert "content" in properties
