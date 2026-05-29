# Feature Plan: Fixed-Route Task Execution Bridge

> Status: in_progress
> Last Updated: 2026-05-29
> Gap: [Fixed-route task execution bridge](../../gaps/README.md)
> Architecture: [Task](../../architecture/task.md), [TaskBus](../../architecture/bus.md), [Agent](../../architecture/agent.md)
> Decisions: [ADR-0010](../../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md), [ADR-0011](../../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)
> Product: [Plato MVP PRD](../../product/plato-mvp-prd.md), [Line-first Authoring Policy](../../product/plato-1-0-line-first-authoring-policy.md), [Main Page UX Flow](../../product/plato-main-page-ux-flow.md)
> Technical Design: [中文详细技术方案](fixed-route-task-execution-bridge-technical-design.zh-CN.md)
> Release Record: [Checkpoint: Fixed-Route Task Execution Bridge](../../releases/fixed-route-task-execution-bridge.md)

---

## 1. Problem / Gap

Implementation has started with the Slice 1-3 service boundary:

- `FixedRouteTaskExecutor`
- `ResidentDefaultAgent` protocol
- `AgentLoopRunner` protocol and `AgentLoopResidentDefaultAgent` adapter
- task-scoped AgentLoop runner factory support for session-specific workspace
  and event context
- one-tick execution over existing TaskBus `claim_next -> complete / fail`
- focused unit tests using a fake resident Default Agent
- `MainPageSidecarApp.run_fixed_route_tick(...)` runtime assembly seam
- sidecar smoke tests covering publish -> tick -> projected `done`
- `LoopResult.finished` maps to a stable `agent_loop:{session_id}:{task_id}:{stop_reason}`
  result ref
- unfinished loop results map to `agent_loop_failed:{stop_reason}` failure refs
- `build_agent_loop_resident_default_agent(...)` assembles a session-scoped
  AgentLoop with LocalRuntime, file/shell tools, and SqliteEventStream

Background loop / HTTP control route, durable result summary storage, broader
Main Page projection polish, CodeAction/Docker-backed tool inclusion, and
user-facing runtime smoke remain follow-up work.

Product 1.0 needs a complete execution loop, not a flexible routing system.
ADR-0010 sets the default as single-task, single-agent, fixed-route flow.

TaskBus already supports:

```text
pending -> running -> done / failed
```

The missing 1.0 gap is a thin runtime bridge that takes a published pending
Task, runs it through the default execution path, and reports status back to
TaskBus so Main Page can project progress, result, and failure.

The bridge should not introduce Product 1.1 routing concepts as 1.0 blockers:

- no Router runtime;
- no Routing Agent policy;
- no Agent descriptor registry;
- no Agent Manager;
- no `assigned_agent_id` Task field;
- no assigned-only claim;
- no Main Page manual reassignment or assignment display.

---

## 2. Goals

Deliver the smallest execution bridge required for the 1.0 closed loop:

1. Pick the next eligible pending Task from TaskBus using the existing
   lifecycle API.
2. Claim it with the resident Default Agent identity.
3. Execute it through the resident Default Agent.
4. Report success through `TaskBus.complete`.
5. Report startup or execution failure through `TaskBus.fail`.
6. Preserve the existing Task status model and Main Page projection path.
7. Avoid routing, assignment, and Agent protocol expansion in 1.0.

---

## 3. Non-goals

- Do not implement dynamic routing strategy.
- Do not implement Router / Routing Agent policy.
- Do not add assignment fields to `TaskDomain`.
- Do not add `assign` or `claim_assigned` as 1.0 blockers.
- Do not implement Agent registry, custom Agent protocol, skills integration,
  MCP integration, or multimodal execution.
- Do not implement Agent Manager or dynamic Agent instance creation.
- Do not implement stale pending sweep / dispatch timeout in this work package.
- Do not implement running timeout, hard cancellation, or cooperative
  interruption enforcement.
- Do not add Main Page assignment or reassignment UX.

---

## 4. Design Direction

### 4.1 Fixed route over routing

For Product 1.0, the execution route is fixed:

```text
TaskBus pending Task
  -> FixedRouteTaskExecutor
  -> resident Default Agent
  -> TaskBus complete / fail
```

The Default Agent is a resident universal Agent started with the app/runtime.
Its identity can be a stable system value such as `default_agent` or
`universal_agent`. It is used as `claimed_by`; it is not a public Agent
template, a routed assignment, or an Agent Manager-created instance.

If the resident Default Agent is not available, that is an application/runtime
health problem. It should be surfaced during startup or runtime diagnostics, not
modeled as routing failure.

### 4.2 Preserve TaskBus lifecycle authority

The bridge does not mutate Task objects directly. It calls existing TaskBus
commands:

```text
claim_next(session_id, capability=task.required_capability, agent_id=default_agent_id)
complete(session_id, task_id, result_ref=...)
fail(session_id, task_id, error_ref=...)
```

If claim returns no Task, the bridge does nothing.

### 4.3 Keep Main Page simple

Main Page 1.0 should show pending, running, done, failed, result summary where
available, and file/audit surfaces as separate 1.0 trust work. It should not
show routing state, assigned Agent, or reassignment controls.

---

## 5. Implementation Slices

### Slice 1 — Execution bridge service

Output:

- `FixedRouteTaskExecutor` or equivalent runtime service;
- configurable but fixed `default_agent_id`;
- one-tick / drain method for executing eligible Tasks.

Acceptance:

- bridge claims one eligible pending Task;
- bridge leaves TaskBus unchanged when no eligible Task exists;
- bridge does not add routing or assignment fields.

### Slice 2 — Resident Default Agent adapter

Output:

- minimal protocol for submitting a claimed Task to the resident Default Agent;
- fake resident Default Agent for tests;
- adapter around the current AgentLoop-compatible execution implementation.

Acceptance:

- resident Default Agent success maps to `TaskBus.complete`;
- resident Default Agent task failure or exception maps to `TaskBus.fail`;
- missing Default Agent is treated as app/runtime health failure, not Agent
  Manager startup failure.

Current status:

- `AgentLoopRunner` captures the small `run(task: str) -> LoopResult` contract
  needed by the resident Default Agent.
- `AgentLoopResidentDefaultAgent` maps a `TaskDomain.intent` into
  `AgentLoopRunner.run(...)`.
- `LoopResult.finished=True` becomes a stable TaskBus `result_ref`.
- `LoopResult.finished=False` becomes a TaskBus-compatible failure ref.
- Production construction of the AgentLoop instance is handled by Slice 3.
  Durable result payload storage remains outside this slice.

### Slice 3 — Sidecar AgentLoop assembly

Output:

- production sidecar can construct a resident Default Agent backed by
  AgentLoop;
- AgentLoop construction is task-scoped so each run gets the correct session
  workspace and event stream;
- tests can still inject a fake Default Agent or disable the default agent to
  cover runtime health behavior.

Acceptance:

- `build_main_page_sidecar_app(...)` wires an AgentLoop-backed default agent by
  default;
- explicit `run_fixed_route_tick(session_id)` can publish `pending -> done`
  through the real AgentLoop adapter without requiring a background loop;
- no Router, Agent Manager, assignment field, or UI reassignment behavior is
  introduced.

Current status:

- `build_agent_loop_resident_default_agent(...)` builds an
  `AgentLoopResidentDefaultAgent` with a per-Task runner factory.
- Each run uses `WorkspaceLayout.session_project_dir(session_id)` as the tool
  workspace and `WorkspaceLayout.session_events_db(session_id)` as the
  EventStream.
- First sidecar tool set is intentionally conservative: read file, write file,
  list directory, run command.
- `CodeActionTool` is deferred because it starts a Docker-backed sandbox during
  tool startup and needs a separate runtime readiness decision.

### Slice 4 — Main Page projection closure

Output:

- confirm existing projection shows `pending`, `running`, `done`, `failed`;
- expose canonical execution status separately from legacy display `status`, so
  backend `pending` remains available as `execution=pending` even if display
  status is `queued`;
- preserve execution `result_ref` / `error_ref` from TaskBus through task
  projection and Main Page UI contract snapshot as `resultRef` / `errorRef`;
- keep these refs as diagnostic/backend references, not production display copy.

Acceptance:

- Main Page can observe Task status progressing through backend facts;
- Main Page snapshot exposes canonical `execution` values for
  `pending/running/done/failed`;
- completed Task snapshots expose `resultRef`;
- failed Task snapshots expose `errorRef`;
- no assignment-specific UI is added.

Current status:

- Transport `TaskNodeCardView` carries canonical `execution` separately from
  legacy display `status`.
- `TaskCardView` and transport `TaskNodeCardView` carry optional result/error
  refs.
- UI contract mapping preserves `resultRef` for `done` tasks and `errorRef` for
  `failed` tasks.
- Sidecar smoke tests cover publish -> tick -> snapshot for both done/result
  and failed/error paths.

### Slice 5 — Tests and docs

Output:

- focused bridge tests;
- projection regression tests if touched;
- release record after implementation.

Acceptance:

- fixed-route success and failure paths are deterministic;
- existing TaskBus lifecycle tests still pass.

Current status:

- Checkpoint release record created.
- Focused bridge/projection/UI contract validation is recorded in the release
  checkpoint.
- The gap remains open until execution can be triggered through a production
  runtime path and result payload behavior is decided.

---

## 6. Testing Strategy

Focused tests:

- bridge claims and completes a pending Task;
- bridge claims and fails on resident Default Agent task error;
- bridge does nothing when no Task is eligible;
- bridge reports runtime health failure if the resident Default Agent is
  unavailable;
- parent dependency behavior remains owned by TaskBus `claim_next`.

Regression tests:

- existing TaskBus lifecycle tests;
- Task projection tests touched by result/failure display.

Checkpoint validation:

- `uv run pytest tests/test_task_projection.py tests/test_ui_contract_mapping.py tests/test_main_page_sidecar_app.py tests/test_ui_contract_models.py`
  - 41 passed, 1 warning
- `uv run mypy src/taskweavn/task/projection.py src/taskweavn/task/views.py src/taskweavn/server/ui_contract/view_models.py src/taskweavn/server/ui_contract/mapping.py src/taskweavn/server/ui_contract/__init__.py tests/test_task_projection.py tests/test_ui_contract_mapping.py tests/test_main_page_sidecar_app.py tests/test_ui_contract_models.py`
  - passed
- `uv run ruff check src/taskweavn/task/projection.py src/taskweavn/task/views.py src/taskweavn/server/ui_contract/view_models.py src/taskweavn/server/ui_contract/mapping.py src/taskweavn/server/ui_contract/__init__.py tests/test_task_projection.py tests/test_ui_contract_mapping.py tests/test_main_page_sidecar_app.py tests/test_ui_contract_models.py`
  - passed
- `npm run build --prefix frontend`
  - passed
- `git diff --check`
  - passed

---

## 7. Follow-ups

Deferred to Product 1.1+:

- minimal Agent assignment semantics;
- Router runtime;
- Routing Agent policy;
- Agent Manager;
- Agent registry / descriptor model;
- public Agent protocol and special Agent protocols;
- stale pending sweep as routing degradation;
- manual reassignment.
