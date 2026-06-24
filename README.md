# TaskWeavn

> User-facing product name: Plato
> Chinese: [README_zh.md](README_zh.md)
> Documentation hub: [docs/README.md](docs/README.md)

TaskWeavn is the local task-agent runtime behind Plato. It turns user intent
into task-centered work: author a task tree, let the user review and refine it,
publish confirmed tasks, execute them through a visible runtime, and project
messages, confirmations, file changes, results, and audit evidence back to the
Main Page.

The current product direction is task-first rather than chat-first:

```text
User intent
  -> RawTask and feasibility assessment
  -> Collaborator drafts a Task Tree List
  -> user edits / confirms Task nodes
  -> TaskPublisher publishes tasks
  -> TaskBus manages execution lifecycle
  -> FixedRouteTaskExecutor runs the resident Default Agent
  -> Main Page projects state, messages, results, and file changes
```

## Current Status

TaskWeavn has moved beyond the early single ReAct-loop prototype. The active
Product 1.1 beta path is a local Plato experience with a Main Page frontend, a
local Python sidecar, durable authoring/execution stores, Router-first runtime
input, workspace evidence, restart-safe replay checks, and a deterministic,
cache-aware Context Manager for LLM input assembly.

| Area | State | Notes |
|---|---:|---|
| Agent core | Done | Strongly typed Action/Observation, EventStream, Runtime, ReAct loop, CLI. |
| Interaction substrate | Done | Session/workspace persistence, MessageStream, MessageBus, risk/autonomy, wait coordination, derived session status. |
| Reliability and observability | Done / follow-up hardening | LLM provider abstraction, retry, DeepSeek thinking, OpenRouter routing, structured JSONL session logs. |
| Authoring domain | Done | RawTask, feasibility, DraftTaskTree, Authoring Commands, Collaborator authoring, publish boundary. |
| Publishing and TaskBus | Done | TaskPublisher, SQLite TaskBus, publish idempotency, claim/running/complete/fail/skip/retry lifecycle. |
| Runtime input | Product 1.1 beta | One Main Page input routes questions, guidance, ASK / confirmation answers, Plan / TaskNode edits, and execution handoff through the Runtime Input Router. |
| Conversation / Activity | Product 1.1 beta | User input, Router interpretation, answers, command outcomes, task updates, and Plan archive events are durable and replayable. |
| Workspace evidence | Product 1.1 beta | Git/diff/file-viewer foundation, precision file tools, result/file projections, Audit links, and diagnostics-safe descriptors. |
| Main Page integration | Done baseline | Frontend runtime adapter, local sidecar HTTP/SSE shell, command/query/event contracts, result/error/file projections. |
| Context Manager | Accepted / cache-aware hardened | Deterministic and append-only cache-aware context assembly before `llm.chat(...)`. |
| Electron beta release | P0 accepted / P1 hardening | Configured Electron, packaged app, mounted `1.1-beta` installer, repo-mode sidecar replay, and launcher-packaged sidecar replay smoke pass. |
| Product 1.1+ platform work | Planned | Public skill marketplace, custom Agent protocol, broad MCP, multimodal context, signed distribution, and remote execution remain later work. |

Start with [docs/roadmap.md](docs/roadmap.md),
[docs/project/roadmap.md](docs/project/roadmap.md), and
[docs/gaps/README.md](docs/gaps/README.md) for the current planning state.
For Product 1.1 beta publishing, start with
[Product 1.1 Beta External Release Notes](docs/releases/product-1-1-beta-external-release-notes.md)
and the internal
[Product 1.1 Runtime Input Router Release Evidence](docs/releases/product-1-1-runtime-input-router-release-evidence.md).

## Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv)
- Node.js and npm for the Plato frontend
- An LLM provider key for authoring/execution flows

Common LLM environment:

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat
```

You can also use the OpenAI-compatible provider path through the environment
documented in [docs/configuration.md](docs/configuration.md).

## Install

From the repository root:

```bash
uv sync
npm install --prefix frontend
```

`uv sync` installs the Python package and development dependencies from
`pyproject.toml`. The frontend install is separate because Plato's Main Page is
a Vite/React package under `frontend/`.

## Start Plato Locally

The normal local product command starts both the Python sidecar and the Vite
frontend:

```bash
uv run taskweavn plato-dev --workspace ./plato-workspace
```

Default URLs:

```text
Frontend: http://127.0.0.1:5173
Sidecar:  http://127.0.0.1:52789
Health:   http://127.0.0.1:52789/api/v1/health
```

Useful options:

```bash
uv run taskweavn plato-dev \
  --workspace ./plato-workspace \
  --sidecar-port 52789 \
  --frontend-port 5173
```

Use `--model <model-id>` to override the model for Collaborator authoring. If
`--model` is omitted, TaskWeavn reads the provider/model from environment
variables.

### Sidecar Only

Run the backend sidecar without starting the frontend:

```bash
uv run taskweavn plato-sidecar --workspace ./plato-workspace
```

Then start the frontend in HTTP mode:

```bash
VITE_PLATO_API_MODE=http \
VITE_PLATO_API_BASE_URL=http://127.0.0.1:52789 \
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

### Mock Frontend Only

For UI work that does not need a backend:

```bash
npm run dev --prefix frontend
```

Without `VITE_PLATO_API_MODE=http`, the frontend uses typed mock scenarios.

## Run The CLI Agent

The lower-level CLI loop is still available for direct workspace tasks:

```bash
uv run taskweavn run \
  --task "write a hello.py that prints hi, then run it" \
  --workspace ./workspace \
  --max-steps 10
```

With the interaction layer:

```bash
uv run taskweavn run \
  --task "inspect this project and propose a small safe improvement" \
  --workspace ./workspace \
  --autonomy risk_gated \
  --risk-assessor baseline \
  --messages-db ./logs/messages.sqlite
```

Available autonomy presets:

```text
full_auto, risk_gated, careful, collaborative, manual
```

Available risk assessors:

```text
baseline, llm, composite
```

## Logs

CLI and sidecar flows write structured session artifacts when logging is
enabled. The default CLI log directory is `./logs`.

Useful commands:

```bash
uv run taskweavn logging profiles
uv run taskweavn logging manifest --log-dir ./logs --session-id <session-id>
uv run taskweavn logging render ./logs/sessions/<session-id>/llm.jsonl --limit 50
```

Session archives use this shape:

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

## Development Checks

Backend:

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Frontend:

```bash
npm test --prefix frontend
npm run build --prefix frontend
```

Targeted examples:

```bash
uv run pytest tests/test_main_page_sidecar_app.py tests/test_ui_http_transport.py
npm test --prefix frontend -- useMainPageController platoApi httpMainPageAdapter
```

## Project Layout

```text
src/taskweavn/
  audit/          AuditAgent and audit observations
  cli/            Typer entry point: taskweavn
  context/        Context Manager models, stores, source adapters, renderer
  core/           AgentLoop, EventStream, sessions, workspace layout
  interaction/    Risk, autonomy, messages, bus, gate, wait coordination
  llm/            LLM client and provider implementations
  memory/         ThoughtStore side-channel persistence
  observability/  Structured logging and session archives
  runtime/        Runtime protocol and LocalRuntime
  server/         Plato sidecar, UI HTTP transport, contract gateways
  task/           Task domain, authoring, publishing, TaskBus, projection
  tools/          Workspace, Tool base, fs/shell/code-action tools
  types/          BaseEvent, BaseAction, BaseObservation, registries

frontend/
  src/            Plato Main Page, runtime adapters, API types, UI primitives

docs/
  README.md       Canonical documentation entry
```

## Documentation Map

| Need | Start with |
|---|---|
| Current direction | [docs/roadmap.md](docs/roadmap.md) |
| Current execution queue | [docs/project/roadmap.md](docs/project/roadmap.md) |
| Known gaps | [docs/gaps/README.md](docs/gaps/README.md) |
| Architecture facts | [docs/architecture/README.md](docs/architecture/README.md) |
| Product intent | [docs/product/README.md](docs/product/README.md) |
| UI/API contract | [docs/product/plato-ui-api-contract.md](docs/product/plato-ui-api-contract.md) |
| Implementation plans | [docs/plans/README.md](docs/plans/README.md) |
| Durable decisions | [docs/decisions/README.md](docs/decisions/README.md) |
| Completed work | [docs/releases/README.md](docs/releases/README.md) |

## License

MIT
