# TaskWeavn

> [中文版](README_zh.md)

TaskWeavn is a task agent with **strongly-typed Action / Observation**, an **EventStream-driven ReAct loop**, and a **pluggable Runtime** — built on top of the OpenHands SDK for LLM adaptation. Roadmap covers four phases: ReAct foundation → CodeAction audit → RAG memory → multi-agent orchestration.

## Status

**Phase 2 complete** — CodeAction schema, sandboxed executor, AuditAgent, and SqliteThoughtStore are all in place.

| Phase | Scope | State |
| ----- | ----- | ----- |
| 1 | Action/Observation types, EventStream, Runtime, ReAct loop | ✅ done |
| 2 | `CodeAction` (sandboxed exec) + AuditAgent + SqliteThoughtStore | ✅ done |
| 3 | RAG memory + SQLite EventStream + budget controller | planned |
| 4 | Multi-agent orchestration (planner / executor / auditor) | planned |

## Project Highlights

### Message Stream over Blocking Interrupt

Traditional human-in-the-loop systems pause execution and force the user to respond before the agent continues. TaskWeavn replaces this with a **message stream model**: agents post messages to a shared stream; users respond when they want to, or not at all. What happens when no response arrives is controlled by a per-agent **autonomy level** — not hardwired into the system.

At full autonomy the stream becomes a read-only execution log. At minimum autonomy every decision waits for user confirmation. The tradeoff between task quality and interruption frequency is a user setting, not an architectural constraint.

### Constraint-driven LLM Orchestration

Users describe what they want in natural language. An **Orchestration Designer** meta-agent translates that intent into a valid agent graph within a **ConstraintProfile** — so the output is legal by construction, not validated after the fact. The constraint profile is itself versioned and progressively relaxed as success-rate data accumulates, keeping the early experience simple and reliable while expanding capability over time.

Constraints are first-class citizens with documented rationale: each rule records what failure mode it guards against, so loosening a constraint is a data-backed engineering decision rather than a guess.

> Full design: [docs/multi_agent_collaboration_architecture.md](docs/multi_agent_collaboration_architecture.md) · [docs/multi_agent_collaboration_architecture_en.md](docs/multi_agent_collaboration_architecture_en.md)

## Why this design

- **Action / Observation symmetry.** Every event flowing through the agent is one of the two — Pydantic v2 frozen models with a `kind` discriminator so they round-trip through JSON without losing their type. A single `EventStream` is the source of truth for *what happened*; consumers (loop, audit, replay, persistence) read the same Protocol regardless of storage.
- **Tool = Action class + executor.** A `Tool[ActionT, ObservationT]` exposes its schema to the LLM and registers itself with the Runtime. Adding a tool is one file; the loop never has to know about it.
- **Runtime is swappable.** `LocalRuntime` (in-process) today, sandboxed / Docker tomorrow (Phase 2.2). Same `execute(action) -> observation` contract, no consumer changes.
- **Never-raise contract.** The Runtime catches every executor exception and returns an `ErrorObservation`. The loop feeds it back to the LLM as a tool message — errors become recoverable signals instead of crashes.
- **LLM layer leans on `litellm`.** `LLMClient.chat()` goes straight through `litellm.completion`, so our Pydantic Actions become OpenAI-format tool schemas without subclassing openhands' `Action` / `Observation` hierarchy.

## Quick start

Requires Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).

```bash
uv sync                                  # install deps + dev tools
export LLM_API_KEY=sk-ant-...            # any litellm-supported provider key
export LLM_MODEL=anthropic/claude-sonnet-4-5-20250929  # optional override

uv run taskweavn run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

The agent writes every Action and Observation to an in-memory `EventStream` and stops on one of: explicit `agent_finish` tool call, an LLM turn with no `tool_calls`, or `--max-steps` reached.

## Programmatic usage

```python
from taskweavn.core.loop import AgentLoop
from taskweavn.llm.client import LLMClient
from taskweavn.runtime.local import LocalRuntime
from taskweavn.tools.fs import ReadFileTool, WriteFileTool, ListDirTool
from taskweavn.tools.shell import RunCommandTool
from taskweavn.tools.workspace import Workspace

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
src/taskweavn/
├── types/          # BaseEvent / BaseAction / BaseObservation + registry
├── core/           # EventStream, ReAct AgentLoop
├── memory/         # ThoughtStore (side channel, opt-in)
├── llm/            # LLMClient (openhands-sdk + litellm), tool-schema helpers
├── runtime/        # Runtime Protocol + LocalRuntime
├── tools/          # Workspace, Tool base, ReadFile/WriteFile/ListDir/RunCommand
├── orchestration/  # Multi-agent Protocol (Phase 4 placeholder)
└── cli/            # Typer entry point (`taskweavn`)
```

## Documentation

| Document | Chinese | English |
| -------- | ------- | ------- |
| Project Plan | [agent_project_plan.md](docs/agent_project_plan.md) | [agent_project_plan_en.md](docs/agent_project_plan_en.md) |
| Multi-Agent Architecture | [multi_agent_collaboration_architecture.md](docs/multi_agent_collaboration_architecture.md) | [multi_agent_collaboration_architecture_en.md](docs/multi_agent_collaboration_architecture_en.md) |

## Development

```bash
uv run pytest          # run test suite
uv run ruff check .    # lint
uv run mypy src tests  # strict type-check
```

All three gates are required green before commits land.

## License

MIT
