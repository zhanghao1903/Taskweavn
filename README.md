# TaskWeavn

> [中文版](README_zh.md)

TaskWeavn is a task agent with **strongly-typed Action / Observation**, an
**EventStream-driven ReAct loop**, a **pluggable Runtime**, and an
**interaction layer for user collaboration**. It is built on top of the
OpenHands SDK for LLM adaptation.

The project is currently in Phase 3: turning the single-turn ReAct foundation
into a persistent, session-aware agent that can ask the user for input without
collapsing the execution model into blocking interrupts.

## Status

**Phase 3 in progress** — persistent workspaces/sessions, SQLite event/message
streams, autonomy presets, user-facing message bus, loop integration, and
LLM-backed risk assessment are in place. The next active work is tightening
derived session status and the user-facing session surface.

| Phase | Scope | State |
| ----- | ----- | ----- |
| 1 | Action/Observation types, EventStream, Runtime, ReAct loop | ✅ done |
| 2 | `CodeAction` (sandboxed exec) + AuditAgent + SqliteThoughtStore | ✅ done |
| 3 | Persistent sessions, MessageStream, autonomy gate, user interaction, risk assessment | 🚧 in progress |
| 4 | Multi-agent orchestration (planner / executor / auditor) | planned |

## Project Highlights

### Message Stream over Blocking Interrupts

Traditional human-in-the-loop systems pause execution and force the user to
respond before the agent continues. TaskWeavn replaces this with a **message
stream model**: agents post messages to a shared stream; users respond when
they want to, or not at all. What happens when no response arrives is
controlled by an **autonomy preset** instead of being hardwired into the loop.

At full autonomy the stream becomes a read-only execution log. At minimum
autonomy every risky decision waits for user confirmation. The tradeoff between
task quality and interruption frequency is a user setting, not an architectural
constraint.

### Quantified Risk and Autonomy

Every `BaseAction` has a class-level `baseline_risk`. Runtime assessors can
raise risk dynamically, but never lower the floor. The autonomy gate combines:

- the action's static baseline;
- optional LLM-backed dynamic risk assessment;
- the configured autonomy preset;
- sync vs async wait behavior.

That produces one of three outcomes: proceed silently, inform the user, or
publish an actionable message and wait/defer according to the preset.

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
export LLM_PROVIDER=litellm              # litellm | deepseek | openrouter
export LLM_API_KEY=sk-ant-...            # provider API key
export LLM_MODEL=anthropic/claude-sonnet-4-5-20250929  # optional override

uv run taskweavn run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

The agent writes every Action and Observation to an in-memory `EventStream` and stops on one of: explicit `agent_finish` tool call, an LLM turn with no `tool_calls`, or `--max-steps` reached.

For DeepSeek:

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat
```

Do not pass `--model` when switching provider through environment variables;
the CLI only reads `LLM_PROVIDER` through `LLMClient.from_env()` when
`--model` is unset. See [Configuration Guide](docs/configuration.md) for all
provider, audit, thought-store, autonomy, and logging options.

To turn on the Phase 3 interaction layer:

```bash
uv run taskweavn run \
    --task "inspect this project and propose a small safe improvement" \
    --workspace ./workspace \
    --autonomy risk_gated \
    --risk-assessor baseline \
    --messages-db ./logs/messages.sqlite
```

Available autonomy presets are `full_auto`, `risk_gated`, `careful`,
`collaborative`, and `manual`. Available risk assessors are `baseline`, `llm`,
and `composite`.

## Recommended Local Test Commands

### Basic task with DeepSeek

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
    --task "write a hello.py that prints hi, then run it" \
    --workspace ./workspace \
    --max-steps 10
```

### With autonomy gate enabled

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
    --task "inspect this project and propose a small safe improvement" \
    --workspace ./workspace \
    --autonomy risk_gated \
    --risk-assessor baseline \
    --messages-db ./logs/messages.sqlite
```

### Log output location

When `--log-dir` is set (default `./logs`), CLI runs write a session archive:

```text
<log-dir>/
  global/config.jsonl
  sessions/<session-id>/
    manifest.json
    action.jsonl
    observation.jsonl
    tool.jsonl
    llm.jsonl
    bus.jsonl
    gate.jsonl
    wait.jsonl
    audit.jsonl
```

Useful logging switches:

```bash
uv run taskweavn run \
    --task "inspect this project and summarize provider config" \
    --workspace ./workspace \
    --session-id debug-llm-run \
    --logging-profile debug-llm \
    --log-dir ./logs
```

Available profiles include `normal`, `quiet`, `debug-llm`, `debug-tools`,
`debug-bus`, and `full-debug`. `manifest.json` is the stable entry point for
UI, testers, and archive scripts. Read `files` for concrete category JSONL
paths; future task/agent-scoped sinks are advertised through manifest
`templates` without changing the default session/category layout. The legacy
`configure_logging()` API still supports flat files such as `tool.log`, but
`taskweavn run` uses session archives.

Inspect logs without mutating a running agent:

```bash
uv run taskweavn logging profiles
uv run taskweavn logging manifest --log-dir ./logs --session-id debug-llm-run
uv run taskweavn logging render ./logs/sessions/debug-llm-run/llm.jsonl --limit 50
```

Additionally, `--messages-db` (default `<log-dir>/messages.sqlite`) stores the
interaction-layer message stream as SQLite, and `--thoughts-db` (default
`<log-dir>/thoughts.sqlite`) stores LLM reasoning when thought persistence is
enabled via `--thoughts`.

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

With the interaction layer enabled programmatically, wire the bundle together:

```python
from taskweavn.interaction import (
    AutonomyGate,
    BaselineOnlyAssessor,
    InProcessMessageBus,
    SqliteMessageStream,
    WaitCoordinator,
    get_preset,
)

behavior = get_preset("risk_gated")
stream = SqliteMessageStream("./workspace/.code-agent/messages.sqlite")
bus = InProcessMessageBus(stream)
gate = AutonomyGate(behavior, BaselineOnlyAssessor())

loop = AgentLoop(
    llm=LLMClient.from_env(),
    runtime=runtime,
    tools=tools,
    workspace_root=ws.root,
    session_id="demo-session",
    bus=bus,
    gate=gate,
    wait_coordinator=WaitCoordinator(bus, behavior),
)
```

## Project layout

```
src/taskweavn/
├── types/          # BaseEvent / BaseAction / BaseObservation + registry
├── core/           # EventStream, SQLite EventStream, sessions, AgentLoop
├── interaction/    # Risk, autonomy, AgentMessage, MessageStream, MessageBus
├── memory/         # ThoughtStore (side channel, opt-in)
├── llm/            # LLMClient (openhands-sdk + litellm), tool schema helpers
├── runtime/        # Runtime Protocol + LocalRuntime
├── tools/          # Workspace, Tool base, fs/shell/code-action tools
├── audit/          # AuditAgent for CodeAction review
├── observability/  # Logging setup
├── orchestration/  # Multi-agent Protocol (Phase 4 placeholder)
└── cli/            # Typer entry point (`taskweavn`)
```

## Documentation

| Document | Chinese | English |
| -------- | ------- | ------- |
| Configuration Guide | [configuration.md](docs/configuration.md) | - |
| Architecture Reference | [architecture.md](docs/architecture.md) | - |
| Interaction Layer Design | [interaction_layer_design.md](docs/interaction_layer_design.md) | - |
| Project Plan | [agent_project_plan.md](docs/agent_project_plan.md) | [agent_project_plan_en.md](docs/agent_project_plan_en.md) |
| Multi-Agent Architecture | [multi_agent_collaboration_architecture.md](docs/multi_agent_collaboration_architecture.md) | [multi_agent_collaboration_architecture_en.md](docs/multi_agent_collaboration_architecture_en.md) |
| User Test Cases | [docs/user_cases](docs/user_cases) | - |

## Development

```bash
uv run pytest          # run test suite
uv run ruff check .    # lint
uv run mypy src tests  # strict type-check
```

The intended quality gate is: tests, Ruff, and mypy all green. Current PR
review follow-up: `uv run mypy src` passes, while `uv run mypy src tests` is
tracked separately in [issue #7](https://github.com/zhanghao1903/codeAgent/issues/7).

## License

MIT
