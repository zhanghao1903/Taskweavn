# Release: Context Manager 1.0

> Status: done / accepted for Product 1.0 fixed-route execution context governance
> Date: 2026-05-31
> Work Stream: Product 1.0 execution context governance / P8-P9 closure
> Related Plan: [Context Manager 1.0](../plans/feature/context-manager-1-0.md)
> Technical Design: [Context Manager 1.0 详细技术方案](../plans/feature/context-manager-1-0-technical-design.zh-CN.md)
> Architecture: [Context Manager](../architecture/context-manager.md), [Architecture Overview](../architecture/overview.md)
> Decisions: [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md)

---

## 1. Summary

This release closes the Product 1.0 Context Manager baseline for the fixed-route
Default Agent execution path.

The accepted runtime path is:

```text
Published TaskBus Task
  -> FixedRouteTaskExecutor
  -> resident Default Agent
  -> SessionContextManager
  -> AgentLoop per-call context provider
  -> llm.chat(...)
```

Context Manager 1.0 is intentionally small. It builds deterministic execution
facts, renders bounded OpenAI-compatible chat messages, persists context
snapshots and traces, and keeps TaskBus as the lifecycle authority. It does not
add Router, Agent Manager, skill engine, MCP expansion, multimodal packing,
semantic retrieval, or parallel writer Agent behavior.

---

## 2. Release Scope

### 2.1 Context Package

Added `src/taskweavn/context/` with:

- v0 Pydantic models for build requests, budgets, task identity, execution
  state, facts, controls, guidance, snapshots, traces, and rendered LLM input;
- deterministic context policy and bounded trimming for recent events, tool
  results, and selected file snippets;
- renderer that produces stable chat messages and rendered input hashes;
- in-memory and SQLite context stores;
- source adapters for TaskBus, EventStream, workspace evidence, controls, and
  guidance;
- `SessionContextManager` orchestration;
- AgentLoop context provider adapter.

### 2.2 Session Storage

Added a `WorkspaceLayout.session_context_db(session_id)` helper so session
metadata owns `context.sqlite` under the session metadata directory.

Snapshots and traces are derived debug/recovery artifacts. They do not become
canonical Task, EventStream, or workspace truth.

### 2.3 Fixed-route Default Agent Integration

`AgentLoopResidentDefaultAgent` now accepts an execution context builder. Before
the runner starts, it builds execution-start context for the claimed Task and
uses the rendered task input.

Context build failure produces a clear task failure result with
`context_build_failed`, rather than silently falling back to an ungoverned
prompt.

### 2.4 Sidecar Assembly

The Main Page sidecar assembly wires the fixed-route Default Agent to:

- `SqliteEventStream`;
- `SqliteContextStore`;
- `SessionContextManager`;
- `SessionAgentLoopContextProvider`.

This keeps the normal Product 1.0 sidecar path governed while preserving test
injection seams.

### 2.5 AgentLoop Per-call Context Seam

`AgentLoop` now has an optional context provider. When present, each
`llm.chat(...)` call uses provider-rendered messages and attaches context
metadata:

- `context_snapshot_id`;
- `context_trace_id`;
- `context_renderer_version`.

Existing no-provider behavior remains available for tests and non-sidecar
callers, but the Product 1.0 sidecar-built Default Agent path uses Context
Manager for each LLM call.

### 2.6 Bounded File Evidence

Read file content enters context through bounded `selected_file_snippets`, not a
workspace file map. File snippets are rendered as workspace evidence, not
instructions, and large content can be bounded with raw references.

---

## 3. Validation

Release validation included:

- `git diff --check`
  - passed
- `uv run ruff check src tests/test_context_manager.py tests/test_fixed_route_task_executor.py tests/test_main_page_sidecar_app.py tests/test_loop.py tests/test_loop_interaction.py`
  - passed
- `uv run mypy src/taskweavn/context src/taskweavn/core/loop.py src/taskweavn/task/execution.py src/taskweavn/server/main_page.py tests/test_context_manager.py`
  - passed
- `uv run pytest tests/test_context_manager.py tests/test_fixed_route_task_executor.py tests/test_main_page_sidecar_app.py tests/test_loop.py tests/test_loop_interaction.py`
  - 75 passed, 1 warning

Full-suite validation was also run:

- `uv run pytest`
  - 878 passed, 3 failed, 1 warning

The three full-suite failures are tracked as unrelated to Context Manager:

- `tests/test_cli.py::test_autonomy_unknown_preset_rejected` fails because
  missing `LLM_API_KEY` validation happens before the expected unknown autonomy
  preset validation.
- `tests/test_cli.py::test_risk_assessor_unknown_via_cli` fails for the same
  validation-order reason.
- `tests/test_ui_contract_fixtures.py::test_main_page_snapshot_fixture_is_canonical_contract_json`
  fails because the canonical UI contract fixture JSON has drifted outside the
  Context Manager path.

Covered behavior:

- deterministic renderer output and rendered input hashes;
- SQLite snapshot and trace persistence/query by task/run;
- EventStream file read observations become bounded file snippets;
- deterministic policy trims event, tool result, and file snippet facts;
- sidecar-built fixed-route Default Agent builds execution-start context;
- context build failure becomes an explicit Task failure path;
- AgentLoop invokes the context provider before `llm.chat(...)`;
- tool observations from prior turns are available through provider-rendered
  context on later LLM calls.

---

## 4. Follow-ups After Acceptance

- Expose context snapshot/trace references through Audit or diagnostics when
  the Audit evidence surface is ready.
- Add redaction/export rules before context snapshots are included in any
  user-shareable diagnostic bundle.
- Populate richer candidate-level trace exclusions if Context Manager debugging
  needs more than snapshot/renderer/policy ids.
- Add skill, MCP, multimodal, retrieval, compression, and custom context policy
  sources in Product 1.1+ only after their contracts are defined.
- Keep Router, Agent Manager, assignment, and parallel writer Agent work out of
  Product 1.0 unless the product scope changes.
