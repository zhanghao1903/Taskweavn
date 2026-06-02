# Feature Plan: Context Manager 1.0

> Status: done / accepted for Product 1.0 fixed-route execution context governance
> Type: Product 1.0 execution context governance
> Last Updated: 2026-06-01
> Architecture: [Context Manager](../../architecture/context-manager.md), [Architecture Overview](../../architecture/overview.md)
> Related Plans: [Fixed-route Task Execution Bridge](fixed-route-task-execution-bridge.md), [Linear Authoring And Minimal Retry Recovery](linear-authoring-retry-recovery.md), [Result And Evidence Exposure Surface](result-exposure-surface.md)
> Release: [Context Manager 1.0](../../releases/context-manager-1-0.md)
> Related References: [Codex context governance research](../../reference/codex-context-governance-engineering.md), [Task context architecture](../../reference/Task%20context%20architecture.md), [Agent skills research](../../reference/agent-skills.md)

---

## 1. Problem

Product 1.0 now has a fixed execution route:

```text
PublishedTask
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Resident Default Agent
  -> AgentLoop
  -> TaskBus complete / fail
```

The execution path works, but the LLM input is still assembled inside
`AgentLoop` from local `messages` state:

- the original task intent is passed as a plain user message;
- tool observations are appended directly to the loop message list;
- task, event, workspace, file, approval, and interrupt facts do not pass
  through one explicit context boundary;
- there is no durable context snapshot or trace that explains what the LLM saw
  for a task run.

This creates an architecture gap. Taskweavn execution is stateful, while the
LLM API is stateless. Product 1.0 needs a minimal Context Manager that assembles
deterministic task execution facts into the LLM input for the Default Agent.

The goal is not to build advanced memory or retrieval. The goal is to introduce
the right boundary now, while keeping the implementation small enough for the
1.0 closed loop.

---

## 2. Product 1.0 Decision

Context Manager 1.0 is a deterministic fact assembler.

It must:

- be Session-scoped;
- serve the fixed-route Default Agent path first;
- keep one active writer execution lane per Session;
- build a structured `TaskExecutionContextV0`;
- render a bounded LLM input for execution calls;
- record snapshots and traces for recovery and debugging;
- preserve extension points for skills, MCP, multimodal context, retrieval,
  compression, and custom policies in Product 1.1+.

It must not:

- introduce Router, Agent Manager, custom Agent protocol, or assignment fields;
- introduce vector search, LLM ranking, long-term memory, or complex
  compression;
- crawl or snapshot the entire workspace;
- allow file contents or tool results to become system-level instructions;
- support parallel writer Agents in one Session.

---

## 3. Current Implementation Anchors

The implementation should attach to existing code instead of inventing a second
execution path.

| Existing Surface | Current Role | Context Manager Use |
|---|---|---|
| `TaskDomain` | Published task identity and lifecycle fact. | Required task identity source. |
| `TaskBus.get/list_for_session` | Task lifecycle authority. | Pull task status, parent, result, failure, and dependency facts. |
| `SqliteEventStream.iter_for_task` | Task-scoped action/observation replay. | Pull bounded recent events and tool observations. |
| `FileContentObservation` | File read result from `read_file`. | Candidate source for selected file snippets. |
| `AgentLoopResidentDefaultAgent` | Adapter between claimed `TaskDomain` and `AgentLoopRunner`. | First integration seam for rendered task input. |
| `AgentLoop._run_inner` | Owns current `messages` list and `llm.chat` calls. | Needs a second seam before full closure so every LLM call can be governed. |
| `WorkspaceLayout.session_meta_dir` | Per-session metadata root. | Recommended home for `context.sqlite`. |
| `TaskExecutionSummaryStore` | Durable user-readable result/error summaries. | Context snapshot refs may later appear in audit/result surfaces. |

---

## 4. Goals

1. Add a `taskweavn.context` package with validated v0 context models.
2. Add `SessionContextManager` as the single assembly boundary for execution
   LLM input.
3. Pull facts from TaskBus, EventStream, current loop state, workspace/file
   references, and runtime controls through small source adapters.
4. Represent read file content as bounded `selected_file_snippets`, not as a
   full file map.
5. Use deterministic selection policy with explicit budgets and stable
   ordering.
6. Render the context into the current OpenAI-compatible `messages` shape used
   by `LLMClient.chat`.
7. Persist context snapshots and traces under the Session metadata directory.
8. Integrate with the fixed-route Default Agent path without changing TaskBus
   lifecycle semantics.
9. Add focused unit and integration tests that prove deterministic assembly,
   bounded rendering, and Default Agent integration.

---

## 5. Non-goals

- No Product 1.1 skill loading engine.
- No MCP context expansion.
- No multimodal input packing.
- No semantic retrieval or vector index.
- No LLM-based candidate ranking.
- No provider-specific prompt-cache directive or advanced cache policy engine
  in the baseline implementation. Product 1.0 cache-aware append-only rendering
  hardening is tracked separately in
  [Context Manager Cache-Aware Rendering](context-manager-cache-aware-rendering.md).
- No cross-session memory.
- No custom context policy UI.
- No public Agent Manager.
- No dynamic routing.
- No concurrent writer Agents.

---

## 6. Implementation Slices

### C1. Context Models, Store, And Renderer

Current status: implemented as the first foundation slice.

Deliver:

- `src/taskweavn/context/models.py`
- `src/taskweavn/context/renderer.py`
- `src/taskweavn/context/store.py`
- `src/taskweavn/context/sqlite_store.py`
- `src/taskweavn/context/__init__.py`
- a `WorkspaceLayout.session_context_db(session_id)` helper or equivalent
  sidecar composition path;
- deterministic JSON serialization for `TaskExecutionContextV0`,
  `ContextSnapshot`, and `ContextTrace`.

Acceptance:

- models validate required task identity and controls;
- `FileSnippet` is bounded and cannot act as instruction by default;
- renderer produces stable message output for identical input;
- SQLite store can save and retrieve snapshots/traces by
  `session_id`, `task_id`, and `agent_run_id`.

### C2. Source Adapters And Deterministic Policy

Current status: implemented for Product 1.0. TaskBus, EventStream, workspace
evidence, controls, guidance, deterministic trimming, and candidate selection
are in place. Loop-local state is carried through the AgentLoop per-call
provider request instead of a separate public source class.

Deliver:

- `TaskContextSource`;
- `EventStreamContextSource`;
- `LoopStateContextSource`;
- `WorkspaceEvidenceContextSource`;
- `ControlContextSource`;
- `DeterministicContextPolicy`.

Acceptance:

- task identity always includes the original target from `TaskDomain.intent`;
- current task status and claim identity are always present;
- recent events/tool results are bounded by count and approximate token budget;
- file snippets are selected only from explicit evidence such as
  `FileContentObservation` or an explicit workspace ref;
- raw large outputs are referenced by `raw_ref` instead of blindly inlined;
- selection is deterministic and testable without an LLM.

### C3. Default Agent Pre-run Integration

Current status: implemented. The sidecar-built fixed-route Default Agent now
builds and stores execution-start context before calling the existing
`AgentLoopRunner.run(...)` contract.

Deliver:

- inject `SessionContextManager` into the fixed-route Default Agent assembly;
- build a context before `AgentLoopRunner.run(...)`;
- pass rendered task input to the existing runner contract;
- save a snapshot/trace for the execution start.

Acceptance:

- published tasks executed by the fixed-route bridge enter the AgentLoop through
  the Context Manager renderer;
- existing TaskBus `claim_next`, `complete`, `fail`, and projection behavior
  remains unchanged;
- existing tests for fixed-route execution still pass;
- context build failure produces a clear task failure summary instead of
  silently falling back to an ungoverned prompt.

This slice is useful, but it does not close the whole Context Manager gap by
itself because subsequent AgentLoop turns still append tool results internally.

### C4. AgentLoop Per-call Context Seam

Current status: implemented for the fixed-route Default Agent path.

Deliver:

- introduce an optional `AgentLoopContextProvider` or equivalent seam inside
  `AgentLoop`;
- before each `llm.chat(...)`, call the provider with:
  - task id;
  - run id;
  - step index;
  - current loop message state;
  - pending approval/deferred action state;
  - latest tool observations;
- let Context Manager render the final message list for that call;
- keep the old behavior as an explicit fallback only when no provider is wired.

Acceptance:

- every Default Agent LLM call in Product 1.0 goes through Context Manager when
  the sidecar is assembled normally;
- tool observations remain available to the next turn, but through structured
  context facts instead of uncontrolled message growth;
- deferred approval resolution and audit messages remain visible to the LLM at
  safe points;
- each LLM call has a context snapshot id or trace id available for logs/tests.

### C5. Product 1.0 Closure Tests And Docs

Current status: implemented and accepted for the Product 1.0 fixed-route
Default Agent path. Focused unit/integration tests cover models, renderer,
source adapters, policy, store, Default Agent pre-run integration, and
AgentLoop per-call provider behavior. Release/gap closure is recorded in the
Product 1.0 control plane.

Deliver:

- unit tests for models, renderer, source adapters, policy, and store;
- integration tests for fixed-route execution with a fake runner/context
  manager;
- AgentLoop tests proving provider path is used before `llm.chat`;
- docs update for release/gap status when implementation is complete.

Acceptance:

- deterministic fixture context renders byte-stable output;
- large `FileContentObservation` payloads are bounded as snippets;
- repeated tool results do not cause unbounded context growth;
- context snapshots can be queried by task id after execution;
- Product 1.1 features remain absent from the 1.0 implementation.

---

## 7. Acceptance Criteria For The Full Gap

The Product 1.0 Context Manager gap is closed only when:

1. Default Agent execution calls are assembled through `SessionContextManager`.
2. `TaskExecutionContextV0` always includes task identity, execution state,
   controls, recent bounded facts, and selected file snippets when applicable.
3. File contents are selected evidence, not a global file map.
4. Context building is pull-time and deterministic.
5. Snapshots and traces are persisted for task runs.
6. Existing fixed-route TaskBus lifecycle behavior is unchanged.
7. Main Page projections continue to derive from TaskBus, MessageStream,
   result summaries, and file summaries, not from Context Manager internals.
8. No Router, Agent Manager, skill engine, MCP integration, multimodal packing,
   vector retrieval, or parallel writer Agent behavior is introduced.

## 8. Implementation Closure

Accepted Product 1.0 implementation:

- `src/taskweavn/context/` provides v0 models, deterministic policy, renderer,
  source adapters, in-memory store, SQLite store, session manager, and
  AgentLoop provider.
- `WorkspaceLayout.session_context_db(session_id)` provides the session-scoped
  `context.sqlite` storage path.
- `AgentLoopResidentDefaultAgent` builds execution-start context before the
  runner is invoked and fails clearly when context build fails.
- Sidecar Default Agent assembly wires `SessionContextManager`,
  `SqliteContextStore`, `SqliteEventStream`, and `SessionAgentLoopContextProvider`.
- `AgentLoop` calls the context provider before each `llm.chat(...)` when the
  provider is present, using rendered messages and context metadata for the
  actual LLM input.
- Product 1.1 expansion points remain out of scope: Router, Agent Manager,
  skill engine, MCP, multimodal packing, semantic retrieval, and parallel writer
  Agents.

Validation evidence:

- `git diff --check` passed.
- Targeted Ruff over changed source and focused tests passed.
- Targeted mypy over `src/taskweavn/context`, `core/loop.py`, `task/execution.py`,
  `server/main_page.py`, and `tests/test_context_manager.py` passed.
- Focused pytest for context manager, fixed-route executor, sidecar app, and
  loop behavior passed: 75 tests.
- Full pytest was run and exposed three unrelated pre-existing failures:
  two CLI validation tests fail because `LLM_API_KEY` validation happens before
  the expected unknown-setting validation, and one UI fixture canonical JSON
  drift test fails outside the Context Manager path.

---

## 9. Risks And Controls

| Risk | Control |
|---|---|
| AgentLoop currently owns `messages`. | Split implementation into pre-run integration and per-call seam. Do not mark the gap closed after pre-run integration only. |
| Context Manager could become a second source of truth. | Store snapshots/traces as derived artifacts only. Rebuild from TaskBus/EventStream/Workspace where possible. |
| File content can become unbounded. | Use `selected_file_snippets` with char/token limits, hashes, and raw refs. |
| Tool observations may contain prompt injection. | Render observations and file snippets under data/evidence sections with `can_act_as_instruction=False`. |
| SQLite snapshot payloads may contain sensitive local file content. | Keep storage local, include hashes/refs, and add redaction policy as a follow-up if diagnostic export expands. |
| Per-call context seam may be too broad for one PR. | Keep C3 and C4 separately testable. C4 is required for architectural closure. |

---

## 10. Recommended Execution Order

1. C1 models/store/renderer — done.
2. C2 sources/policy — done for Product 1.0.
3. C3 fixed-route Default Agent pre-run integration — done.
4. C4 AgentLoop per-call context seam — done.
5. C5 closure tests, release record, and docs status update — done.

This implementation gives the project the required Product 1.0 boundary:
Context Manager owns the actual LLM input for the fixed-route Default Agent
execution calls while remaining small enough to extend in Product 1.1+.
