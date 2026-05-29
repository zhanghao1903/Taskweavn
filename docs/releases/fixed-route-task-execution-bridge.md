# Checkpoint: Fixed-Route Task Execution Bridge

> Status: checkpoint / gap still open
> Date: 2026-05-29
> Work Stream: Product 1.0 fixed-route execution / P8 backend integration
> Related Plan: [Fixed-Route Task Execution Bridge](../plans/feature/fixed-route-task-execution-bridge.md)
> Technical Design: [Fixed-Route Task Execution Bridge 技术设计](../plans/feature/fixed-route-task-execution-bridge-technical-design.zh-CN.md)
> Decisions: [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)

---

## 1. Summary

This checkpoint proves the Product 1.0 fixed-route execution path through the
backend runtime boundary:

```text
Published TaskBus Task
  -> FixedRouteTaskExecutor
  -> resident Default Agent
  -> TaskBus complete / fail
  -> Main Page snapshot projection
```

The work intentionally avoids Product 1.1 routing concepts. It does not add a
Router, Agent Manager, assignment fields, assigned-only claim, or Main Page
reassignment UI.

This is not a completed release for the full execution gap. Background dispatch,
HTTP control routes, durable result payload storage, and broader product smoke
remain follow-up work.

---

## 2. Checkpoint Scope

### 2.1 Execution Bridge

- Added a fixed-route executor over the existing TaskBus lifecycle.
- Uses existing TaskBus authority:
  - `claim_next`;
  - `complete`;
  - `fail`.
- Handles no-op idle state when no eligible Task exists.
- Handles missing Default Agent as runtime health failure, not routing failure.

### 2.2 Resident Default Agent

- Added the resident Default Agent protocol.
- Added fake Default Agent coverage for deterministic tests.
- Added `AgentLoopResidentDefaultAgent` and `AgentLoopRunner` boundary.
- Maps successful AgentLoop completion to stable `result_ref`.
- Maps unfinished/error outcomes to TaskBus-compatible `error_ref`.

### 2.3 Sidecar Assembly

- `build_main_page_sidecar_app(...)` can assemble an AgentLoop-backed resident
  Default Agent by default.
- Tests can inject a fake Default Agent or disable the Default Agent for health
  behavior coverage.
- Task-scoped AgentLoop runner factory uses session workspace and session event
  stream context.
- The initial production tool set remains conservative: read file, write file,
  list directory, and run command.

### 2.4 Main Page Projection Closure

- Main Page transport `TaskNodeCardView` now carries canonical `execution`
  separately from legacy display `status`.
- Backend `pending` is still displayable as `status=queued`, while the
  canonical execution fact is preserved as `execution=pending`.
- TaskBus `result_ref` and `error_ref` now flow through:

```text
TaskDomain
  -> TaskCardView
  -> TaskNodeCardView
  -> MainPageSnapshot JSON resultRef/errorRef
```

- `resultRef` and `errorRef` are diagnostic/backend references, not final
  production user copy.

---

## 3. Validation

Checkpoint validation included:

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

Covered behavior:

- pending Task can be claimed and completed by the fixed-route executor;
- Default Agent task error maps to failed TaskBus state;
- no eligible Task is a deterministic no-op;
- missing Default Agent is runtime health error and does not claim a Task;
- AgentLoop-backed Default Agent can run through the sidecar tick seam;
- Main Page snapshot exposes done/result and failed/error projection facts.

---

## 4. Follow-ups Before Gap Closure

- Add a background dispatcher or explicit HTTP control route for triggering
  fixed-route execution outside test-only/direct tick calls.
- Decide whether publish `startImmediately` should trigger execution in-process
  or only enqueue work for a dispatcher.
- Add durable result summary payload storage; current checkpoint stores stable
  refs only.
- Decide whether CodeAction/Docker-backed tools are safe to include in the
  resident Default Agent startup path.
- Run a normal browser/Electron smoke for publish -> execute -> snapshot
  visibility once the frontend control path is ready.
- Keep routing, assignment, Agent Manager, and custom Agent protocol work in
  Product 1.1+ unless product scope changes.
