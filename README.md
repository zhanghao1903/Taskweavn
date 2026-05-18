# TaskWeavn

> User-facing product name: Plato
> Chinese: [README_zh.md](README_zh.md)
> Canonical docs entry: [docs/README.md](docs/README.md)

TaskWeavn is the local task-agent system behind Plato. Its core idea is simple:
turn natural-language intent into task-centered plans, let users inspect and
guide those tasks, then execute them with visible messages, confirmations,
file changes, audit evidence, and diagnostics.

Plato is not designed as a wrapped CLI chat. The product model is:

```text
User intent
  -> RawTask and feasibility assessment
  -> Collaborator drafts Task Tree List
  -> user edits/confirms Task nodes
  -> TaskPublisher publishes Tasks
  -> TaskBus dispatches execution
  -> UI observes topology, messages, confirmations, files, audit, and results
```

## Current Status

The project has moved beyond the original single-turn ReAct agent. Current
work is focused on Plato 1.0 productization: making the server-core foundations
usable as a local desktop product.

| Area | State | Notes |
|---|---:|---|
| Phase 1 core agent | done | Typed Action/Observation, EventStream, Runtime, ReAct loop, CLI. |
| Phase 2 sandbox/audit/memory | done | CodeAction, Docker sandbox, AuditAgent, SQLite ThoughtStore. |
| Phase 3.1-3.8 Interaction Layer | done | Sessions, workspaces, risk/autonomy, messages, bus, wait, loop integration, LLM risk, derived session status. |
| LLM provider reliability | done | Provider abstraction, retry, DeepSeek thinking, OpenRouter routing. |
| Configurable logging | done | Structured JSONL logs, session archives, profiles, runtime control. |
| Task authoring foundation | done | RawTask, feasibility, DraftTaskTree, Collaborator authoring commands. |
| Task publishing foundation | partial / server-core done | TaskPublisher, SQLite TaskBus publish surface, SQLite publish control plane, API publish transport. Execution lifecycle remains. |
| Plato frontend baseline | done / integration pending | `frontend/src` has Main Page scaffold, state catalog, typed mock/API adapter, shared API types, UI primitives. |
| Plato 1.0 productization | active | UI/backend contracts, sidecar API, real backend integration, settings, audit, diagnostics, packaging. |

For the living roadmap, read [docs/roadmap.md](docs/roadmap.md) and
[docs/project/roadmap.md](docs/project/roadmap.md).

## Product And Architecture Highlights

### Task-First UX

Task is the primary user-facing object. Chat is input, clarification, and
explanation; it is not the main state model. Users should be able to select a
TaskNode, see its status, add guidance, answer confirmations, inspect related
messages, and review file changes.

### Strongly Typed Agent Core

Actions and Observations are frozen Pydantic models with a `kind`
discriminator. Tools expose Action schemas to the LLM, and Runtime implementations
return Observations. Runtime errors become `ErrorObservation` values instead of
crashing the loop.

### Interaction Layer

TaskWeavn uses one session message stream with task-scoped projections. The
interaction layer includes:

- `AgentMessage` and `SqliteMessageStream`;
- `InProcessMessageBus`;
- quantified risk and autonomy presets;
- `AutonomyGate` and `WaitCoordinator`;
- sync wait and async deferred response paths.

### Task Authoring And Publishing

The authoring domain is separate from execution:

- RawTask and DraftTaskTree support exploratory planning before execution.
- Collaborator authoring tools refine task trees with user input.
- TaskPublisher publishes approved task trees into TaskBus.
- API, scheduler, pipeline, and custom tree publishers route through the same
  publish boundary.

### Plato 1.0 Direction

Plato 1.0 targets a local single-user desktop assistant. The current P0 path is:

1. UI/backend contract baseline.
2. Local sidecar API shell.
3. Main Page real backend integration.
4. Settings and first run.
5. Task execution lifecycle.
6. Message and confirmation integration.
7. File Change Summary.
8. Audit / Trust page.
9. Product error handling.
10. Diagnostic bundle.
11. Packaging and distribution.

## Quick Start: CLI Agent

Requires Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).

```bash
uv sync

export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-...
export LLM_MODEL=deepseek-chat

uv run taskweavn run \
  --task "write a hello.py that prints hi, then run it" \
  --workspace ./workspace \
  --max-steps 10
```

With the interaction layer enabled:

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

Configuration planning lives in
[Settings and First Run](docs/capabilities/settings-and-first-run/) and
[Configuration Control Plane](docs/capabilities/configuration-control-plane/).
The older CLI configuration guide is archived at
[docs/archive/legacy-2026-05-18/root/configuration.md](docs/archive/legacy-2026-05-18/root/configuration.md).

## Quick Start: Frontend Baseline

The Plato frontend baseline lives under `frontend/`.

```bash
cd frontend
npm install
npm run dev
```

Useful frontend checks:

```bash
npm test
npm run lint
npm run build
```

The current frontend is a Main Page baseline with typed mock scenarios and an
HTTP adapter contract. Real backend sidecar integration is still a Plato 1.0
gap, tracked from [docs/contracts/ui-backend/](docs/contracts/ui-backend/) and
[docs/capabilities/main-page-real-backend/](docs/capabilities/main-page-real-backend/).

## Project Layout

```text
src/taskweavn/
  audit/          AuditAgent and audit observations
  cli/            Typer CLI entry point
  core/           AgentLoop, EventStream, sessions, workspace layout
  interaction/    Risk, autonomy, messages, bus, gate, wait coordination
  llm/            LLM client and provider implementations
  memory/         ThoughtStore side channel
  observability/  Structured logging and session archives
  orchestration/  Multi-agent placeholders and protocol boundaries
  runtime/        Runtime protocol and LocalRuntime
  server/         Framework-neutral server/transport adapters
  task/           Task domain, authoring, publishing, pipeline, stores
  tools/          Workspace, Tool base, fs/shell/code-action tools
  types/          BaseEvent, BaseAction, BaseObservation, registries

frontend/
  src/            Plato Main Page baseline, API types, UI primitives

docs/
  README.md       Canonical docs entry
```

## Documentation

Start with [docs/README.md](docs/README.md). The main active docs are:

| Need | Entry |
|---|---|
| Product version | [Plato 1.0 Overview](docs/product/versions/1.0/overview.md) |
| Current gaps | [Plato 1.0 Gap Analysis](docs/product/versions/1.0/gap-analysis.md) |
| Capability map | [docs/capabilities/index.md](docs/capabilities/index.md) |
| Current architecture | [docs/architecture/current.md](docs/architecture/current.md) |
| UI/backend contracts | [docs/contracts/ui-backend/](docs/contracts/ui-backend/) |
| Roadmap | [docs/roadmap.md](docs/roadmap.md) |
| Operational project plan | [docs/project/roadmap.md](docs/project/roadmap.md) |
| Docs workflow | [docs/project/docs-operating-model.md](docs/project/docs-operating-model.md) |
| Release records | [docs/releases/](docs/releases/) |

Historical docs are kept under `docs/archive/legacy-2026-05-18/` and are no
longer the active workflow entry points.

## Development Checks

Backend:

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Target quality gate: tests, lint, type checks, and relevant product docs all
updated together when a capability changes.

## License

MIT
