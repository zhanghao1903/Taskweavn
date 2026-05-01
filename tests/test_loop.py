"""Tests for the ReAct AgentLoop (1.5)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from code_agent.core.loop import FINISH_TOOL_NAME, AgentLoop, LoopError
from code_agent.llm.client import ChatResponse, ToolCall
from code_agent.runtime import LocalRuntime
from code_agent.tools import (
    ReadFileTool,
    Workspace,
    WriteFileTool,
)
from code_agent.types import (
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
    ) -> ChatResponse:
        self.calls.append({"messages": list(messages), "tools": tools})
        try:
            return next(self._iter)
        except StopIteration as exc:  # pragma: no cover — test misconfig signal
            raise AssertionError("StubLLM ran out of canned responses") from exc


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
    from code_agent.tools.base import Tool

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
    response = _tool_call_response(
        "write_file", {"path": "a.txt", "content": "a"}, call_id="c"
    )
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

    from code_agent.tools.base import Tool

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
    write_schema = next(
        t for t in tools_arg if t["function"]["name"] == "write_file"
    )
    properties = write_schema["function"]["parameters"]["properties"]
    assert "event_id" not in properties
    assert "timestamp" not in properties
    assert "source" not in properties
    assert "path" in properties
    assert "content" in properties
