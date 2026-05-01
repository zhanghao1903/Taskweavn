# codeAgent

A code agent with **strongly-typed Action / Observation**, an **EventStream-driven
ReAct loop**, and a **pluggable Runtime** — built on top of the OpenHands SDK
for LLM adaptation. Roadmap covers four phases: ReAct foundation → CodeAction
audit → RAG memory → multi-agent orchestration.

## Status

**Phase 1 complete** — ReAct loop runs end-to-end with file/shell tools.
Future phases live in [`docs/agent_project_plan.md`](docs/agent_project_plan.md).

| Phase | Scope                                                       | State        |
| ----- | ----------------------------------------------------------- | ------------ |
| 1     | Action/Observation types, EventStream, Runtime, ReAct loop  | ✅ done       |
| 2     | `CodeAction` (sandboxed exec) + AuditAgent                  | next         |
| 3     | RAG memory + SQLite EventStream + budget controller         | planned      |
| 4     | Multi-agent orchestration (planner / executor / auditor)    | planned      |

## Why this design

- **Action / Observation symmetry.** Every event flowing through the agent is
  one of the two — Pydantic v2 frozen models with a `kind` discriminator so
  they round-trip through JSON without losing their type. A single
  `EventStream` is the source of truth for *what happened*; consumers (loop,
  audit, replay, persistence) read the same Protocol regardless of storage.
- **Tool = Action class + executor.** A `Tool[ActionT, ObservationT]` exposes
  its schema to the LLM and registers itself with the Runtime. Adding a tool
  is one file; the loop never has to know about it.
- **Runtime is swappable.** `LocalRuntime` (in-process) today, sandboxed /
  Docker tomorrow (Phase 2.2). Same `execute(action) -> observation` contract,
  no consumer changes.
- **Never-raise contract.** The Runtime catches every executor exception and
  returns an `ErrorObservation`. The loop feeds it back to the LLM as a tool
  message — errors become recoverable signals instead of crashes.
- **LLM layer leans on `litellm`.** `LLMClient.chat()` goes straight through
  `litellm.completion`, so our Pydantic Actions become OpenAI-format tool
  schemas without subclassing openhands' `Action` / `Observation` hierarchy.
  `LLMClient.complete()` still wraps openhands-sdk `LLM` for one-shot use
  later (audit, RAG).

## Quick start

Requires Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).

```bash
uv sync                                  # install deps + dev tools
export LLM_API_KEY=sk-ant-...            # any litellm-supported provider key
export LLM_MODEL=anthropic/claude-sonnet-4-5-20250929  # optional override

uv run code-agent run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

The agent writes every Action and Observation to an in-memory `EventStream`
and stops on one of: explicit `agent_finish` tool call, an LLM turn with no
`tool_calls`, or `--max-steps` reached. The CLI prints `stop_reason`,
`steps`, and the final answer.

## Programmatic usage

```python
from code_agent.core.loop import AgentLoop
from code_agent.llm.client import LLMClient
from code_agent.runtime.local import LocalRuntime
from code_agent.tools.fs import ReadFileTool, WriteFileTool, ListDirTool
from code_agent.tools.shell import RunCommandTool
from code_agent.tools.workspace import Workspace

ws = Workspace("./workspace")
runtime = LocalRuntime()
tools = [ReadFileTool(ws), WriteFileTool(ws), ListDirTool(ws), RunCommandTool(ws)]
for t in tools:
    t.register(runtime)

loop = AgentLoop(llm=LLMClient.from_env(), runtime=runtime, tools=tools)
result = loop.run("create README.md describing this folder")
print(result.final_answer)
```

## Project layout

```
src/code_agent/
├── types/          # BaseEvent / BaseAction / BaseObservation + registry
├── core/           # EventStream, ReAct AgentLoop
├── memory/         # ThoughtStore (side channel, opt-in)
├── llm/            # LLMClient (openhands-sdk + litellm), tool-schema helpers
├── runtime/        # Runtime Protocol + LocalRuntime
├── tools/          # Workspace, Tool base, ReadFile/WriteFile/ListDir/RunCommand
├── orchestration/  # Multi-agent Protocol (Phase 4 placeholder)
└── cli/            # Typer entry point (`code-agent`)
```

## Development

```bash
uv run pytest          # 70 tests, ~3s
uv run ruff check .    # lint
uv run mypy src tests  # strict type-check
```

All three gates are required green before commits land.

## License

MIT
