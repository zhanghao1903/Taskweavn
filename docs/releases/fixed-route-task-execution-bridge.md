# Release: Fixed-Route Task Execution Bridge

> Status: done / accepted for Product 1.0 fixed-route execution
> Date: 2026-05-30
> Work Stream: Product 1.0 fixed-route execution / P8 backend integration
> Related Plan: [Fixed-Route Task Execution Bridge](../plans/feature/fixed-route-task-execution-bridge.md)
> Technical Design: [Fixed-Route Task Execution Bridge 技术设计](../plans/feature/fixed-route-task-execution-bridge-technical-design.zh-CN.md)
> Decisions: [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)

---

## 1. Summary

This release closes the Product 1.0 fixed-route execution bridge. The accepted
runtime path runs through the backend boundary:

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

Slice 6 adds background dispatch and an HTTP control route. P8.E1 adds durable
result/error summary storage. P8.E2 and P8.E3 add user-facing execution messages
and Main Page result/error projection. P8.E4 adds deterministic Main Page file
summary projection from observed file facts. Sidecar HTTP user-path smoke has
passed. Audit evidence closure, normal browser/Electron smoke, and richer runtime
recovery remain separate follow-up gaps rather than blockers for this bridge.

---

## 2. Release Scope

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

### 2.5 Runtime Trigger And Background Dispatch

- Added a sidecar-owned in-process fixed-route execution dispatcher.
- `publish.startImmediately=true` requests background execution after a
  successful publish; `startImmediately=false` leaves execution untriggered.
- Added explicit `POST /api/v1/sessions/{sessionId}/execution/dispatch` for
  manual/recovery dispatch.
- Duplicate dispatch triggers for one Session are coalesced while dispatch is
  pending or running.
- Sidecar shutdown stops queued dispatch and closes the worker before stores
  close.
- Agent lifecycle remains Task-run scoped; no long-lived AgentLoop or
  SessionContextStore is introduced.

### 2.6 Durable Result/Error Summary Store

- Added `TaskExecutionSummary` as the readable result/error payload addressed
  by TaskBus `result_ref` / `error_ref`.
- Added `SqliteTaskExecutionSummaryStore` backed by workspace
  `.taskweavn/results.sqlite`.
- AgentLoop success stores `LoopResult.final_answer` as a result summary.
- Successful executor paths without an agent-provided `result_ref` now create a
  default readable completion summary ref.
- AgentLoop unfinished and execution exception paths store error summaries.
- Sidecar `run_fixed_route_tick(...)` and background dispatcher share the same
  result summary store.

### 2.7 AgentLoop To MessageStream Bridge

- Fixed-route successful completion writes a task/session-correlated
  informational message into `MessageStream`.
- Fixed-route failure writes a task/session-correlated error-toned message into
  `MessageStream`.
- Message context carries execution status, result/error refs, execution title,
  and summary metadata when available.
- MessageStream write failure does not roll back the TaskBus lifecycle fact.

### 2.8 Main Page Result/Error Projection

- `TaskExecutionSummaryViewStore` adapts durable execution summaries into
  task projection `TaskSummaryView`.
- `DefaultUiQueryGateway` projects the latest terminal published Task with a
  readable summary into `MainPageSnapshot.result`.
- Failed Task summaries use the same result surface and include a
  `Failure reason` section.
- Snapshot message merging now preserves the richer raw session MessageStream
  projection when it duplicates a task-tree latest message, so execution
  messages retain their title and error kind.

### 2.9 Main Page File Change Summary Projection

- Fixed-route AgentLoop execution now supplies the published Task id to
  `AgentLoop.run(...)`, so session-scoped EventStream facts can be read by Task.
- `EventStreamFileChangeStore` projects deterministic file facts from
  `FileWriteObservation` and `CodeExecutionObservation` into
  `TaskFileChangeSummary`.
- Recursive child-task roll-up remains in `DefaultTaskProjectionService`, not
  the EventStream reader.
- `DefaultUiQueryGateway` maps file-change facts into
  `MainPageSnapshot.file_change_summary` when evidence exists.
- Agent final answers remain result summaries; file evidence is generated from
  observed facts only.

---

## 3. Validation

Release validation included:

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
- `uv run pytest tests/test_fixed_route_task_executor.py tests/test_ui_http_transport.py tests/test_main_page_sidecar_app.py`
  - 49 passed, 1 warning
- `uv run pytest tests/test_task_event_file_changes.py tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_main_page_sidecar_app.py tests/test_ui_query_gateway.py tests/test_ui_contract_mapping.py tests/test_task_projection.py tests/test_ui_contract_models.py tests/test_ui_http_transport.py tests/test_task_result_summary_store.py`
  - 115 passed, 1 warning
- Sidecar HTTP user-path smoke:
  - create session;
  - generate draft TaskTree;
  - publish with `startImmediately=true`;
  - background fixed-route AgentLoop writes `notes/smoke-result.md`;
  - snapshot shows `execution=done`, readable `result.summary`, and
    deterministic `fileChangeSummary`.
- `uv run mypy src/taskweavn/task/execution.py src/taskweavn/task/__init__.py src/taskweavn/server/ui_contract/commands.py src/taskweavn/server/ui_contract/__init__.py src/taskweavn/server/ui_http.py src/taskweavn/server/main_page.py tests/test_fixed_route_task_executor.py tests/test_ui_http_transport.py tests/test_main_page_sidecar_app.py`
  - passed
- `uv run mypy src/taskweavn/core/loop.py src/taskweavn/server/main_page.py src/taskweavn/server/ui_contract/gateways.py src/taskweavn/task/__init__.py src/taskweavn/task/event_file_changes.py src/taskweavn/task/execution.py src/taskweavn/task/projection.py tests/test_task_event_file_changes.py tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_ui_query_gateway.py tests/test_main_page_sidecar_app.py`
  - passed
- `uv run ruff check src/taskweavn/task/execution.py src/taskweavn/task/__init__.py src/taskweavn/server/ui_contract/commands.py src/taskweavn/server/ui_contract/__init__.py src/taskweavn/server/ui_http.py src/taskweavn/server/main_page.py tests/test_fixed_route_task_executor.py tests/test_ui_http_transport.py tests/test_main_page_sidecar_app.py`
  - passed
- `uv run ruff check src/taskweavn/core/loop.py src/taskweavn/server/main_page.py src/taskweavn/server/ui_contract/gateways.py src/taskweavn/task/__init__.py src/taskweavn/task/event_file_changes.py src/taskweavn/task/execution.py src/taskweavn/task/projection.py tests/test_task_event_file_changes.py tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_ui_query_gateway.py tests/test_main_page_sidecar_app.py`
  - passed

Covered behavior:

- pending Task can be claimed and completed by the fixed-route executor;
- Default Agent task error maps to failed TaskBus state;
- no eligible Task is a deterministic no-op;
- missing Default Agent is runtime health error and does not claim a Task;
- AgentLoop-backed Default Agent can run through the sidecar tick seam;
- Main Page snapshot exposes done/result and failed/error projection facts.
- publish `startImmediately=true` schedules background execution and snapshot
  eventually shows done/result;
- publish `startImmediately=false` does not schedule execution;
- explicit execution dispatch route returns structured accepted/rejected command
  responses.
- result/error summaries survive store reopen;
- AgentLoop result refs can be resolved through the SQLite summary store.
- fixed-route completion/failure messages are persisted and projected through
  the Main Page snapshot message stream.
- successful and failed terminal Tasks produce readable
  `MainPageSnapshot.result` payloads.
- AgentLoop events are tagged with the published Task id when fixed-route
  execution runs a Task.
- observed file write / code execution facts project into Task file summaries.
- Main Page snapshots expose deterministic `fileChangeSummary` without parsing
  Agent prose.
- sidecar HTTP user-path smoke validates generate -> publish -> background
  execution -> result/file summary snapshot.

---

## 4. Follow-ups After Acceptance

- Add Audit evidence records/links for file summary detail and hidden/partial
  evidence states.
- Decide whether CodeAction/Docker-backed tools are safe to include in the
  resident Default Agent startup path.
- Run a normal browser/Electron smoke for publish -> execute -> snapshot
  visibility as release QA. Sidecar HTTP smoke has passed; browser UI smoke is
  still tracked separately.
- Define richer interrupted-running recovery after the minimum fixed-route
  bridge.
- Keep routing, assignment, Agent Manager, and custom Agent protocol work in
  Product 1.1+ unless product scope changes.
