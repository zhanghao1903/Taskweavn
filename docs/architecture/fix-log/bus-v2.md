# TaskBus v2 Architecture Fact Calibration Fix Log

> Target document: `docs/architecture/bus-v2.md`
> Original preserved as: `docs/architecture/bus-v2.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue one-document-at-a-time architecture fact calibration.
- Detected phase: P5 architecture maintenance, verified against P8/P9 code and tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: current TaskBus facts, Execution Plane facts, ADR-0012, ADR-0020, related tests.
- Found artifacts: current `bus.md`, `taskbus-service-multi-execution-env.md`, TaskBus implementations, fixed-route executor, Execution Plane DTO/service/store, runtime docs, tests.
- Missing or weak artifacts: previous `bus-v2.md` was useful future design but mixed old v1 assumptions, EventStream-source wording, and unimplemented v2 APIs.
- Implementation allowed now: yes, docs-only.
- Prework required: verify that v2 scheduler/IOScope/lease APIs are not implemented before editing.
- Scope: preserve original, revise `bus-v2.md`, add this fix-log.
- Acceptance criteria: current runtime facts and future proposals are separated; no unimplemented v2 API is described as current.
- Risks and assumptions: older review/plan docs may still praise or reference v2 concepts, but code remains authoritative for current facts.

## Maintainability Gate

- Requested change: architecture hygiene for `bus-v2.md`.
- Trigger: architecture fact calibration.
- Size signal: target document was 719 lines, below the 800-line threshold.
- Risk level: low for docs-only slice.
- Refactor required first: no.
- Allowed change type: docs-only boundary correction.
- Validation commands: `git diff --check` plus targeted TaskBus / Execution Plane tests.

## Evidence Inspected

### Code

- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`
- `src/taskweavn/task/models.py`
- `src/taskweavn/task/execution.py`
- `src/taskweavn/execution_plane/models.py`
- `src/taskweavn/execution_plane/embedded_service.py`
- `src/taskweavn/execution_plane/env_registry.py`
- `src/taskweavn/execution_plane/store.py`
- `src/taskweavn/server/computer_use_runtime.py`
- `src/taskweavn/server/ui_http_execution_plane.py`

### Tests

- `tests/test_task_bus_lifecycle.py`
- `tests/test_sqlite_task_bus.py`
- `tests/test_fixed_route_task_executor.py`
- `tests/test_execution_plane_models.py`
- `tests/test_execution_plane_service.py`
- `tests/test_execution_plane_http_transport.py`
- `tests/test_task_commands.py`

### Related Docs

- `docs/architecture/bus.md`
- `docs/architecture/taskbus-service-multi-execution-env.md`
- `docs/architecture/task.md`
- `docs/architecture/agent.md`
- `docs/architecture/review.md`
- `docs/decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md`
- `docs/decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md`
- `docs/plans/observability.md`
- `docs/plans/configuration.md`

## Verified Facts

1. Current TaskBus Protocol has no `TaskBusV2`, scheduler, `assign`, `claim_assigned`, `sweep_stale_pending_tasks`, `acquire_io`, `release_io`, `running_tasks`, `concurrency_level`, or `force_decide`.

2. Current `TaskDomain` has no `IOScope`, declared read/write scope, scheduler priority, assigned agent fields, lease fields, or `max_concurrent` fields.

3. Current `TaskDispatchConstraints` is an optional dispatch-hint model for future assignment work and does not change TaskBus claim semantics.

4. Current `InMemoryTaskBus` and `SqliteTaskBus` enforce pending status, capability match, and parent done at claim time.

5. Current TaskBus does not enforce a global "one running task" lock. The fixed-route product path serializes execution per Session through `FixedRouteExecutionDispatcher`.

6. Current `FixedRouteTaskExecutor` selects the first eligible pending Task and uses `claim_next`; it does not use LLM scheduling.

7. Runtime Input Router is implemented for user-input/contract routing, not execution Task scheduling.

8. Current Execution Plane DTOs include `TaskLease`, `claimed`, and `lease_expired`, but no lease store, claim endpoint, renewal flow, expiry handling, or remote worker protocol is implemented.

9. Current `ExecutionEnvRegistry` is in-memory and local. It checks online status, required capability, and allowed tool subset.

10. Current sidecar can expose a local HTTP shell over `TaskApiService`, but no execution-env register/heartbeat/claim endpoints exist.

11. Current EventStream is runtime/audit/evidence read-side. TaskBus lifecycle truth is stored in TaskBus implementations, not rebuilt from EventStream.

12. No production code defines `IOScope` or an IO guard. File-change evidence and EventStream projections describe observed changes after execution; they do not reserve future IO.

13. ADR-0012 accepts future TaskBus-centered assignment convergence, but explicitly avoids leases/locks for the first assignment implementation. That implementation is not current code.

14. ADR-0020 accepts Execution Plane service direction, but current implementation is embedded/local foundation.

## Corrections Applied

1. Reframed `bus-v2.md` as future design reference, not current runtime architecture.

2. Added a current baseline section for TaskBus API, storage, fixed-route scheduling, and embedded Execution Plane.

3. Removed old wording that described v1 as simply FIFO + strict TaskBus-level serial lock; corrected to current fixed-route serial product path plus no TaskBus global running lock.

4. Marked LLM scheduler, `IOScope`, IO guard, `max_concurrent`, assignment API, leases, and EventStream scheduler rationale as future-only.

5. Corrected EventStream boundary: future scheduler/IO events may support audit, but TaskBus lifecycle source of truth remains TaskBus store.

6. Added safer intermediate route: IO declaration and telemetry before concurrency.

7. Added ExecutionEnv/lease section aligned with current DTO-only and local registry facts.

8. Added risk controls and an implementation order that keeps current lifecycle authority intact.

## Follow-up Candidates

- `docs/architecture/tool-capability-layer.md`: likely needs alignment with current `CapabilityPolicy`, tool pool, computer-use runtime, and lack of IO scope guard.
- `docs/architecture/workspace-communication-protocol.md`: should be checked for workspace/IO/concurrency assumptions.
- `docs/plans/observability.md`: still describes EventStream trace events for v2 as plan language and may need a status note if treated as current.
- `docs/plans/configuration.md`: superseded but still has `max_concurrent_tasks` future references.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_task_bus_lifecycle.py tests/test_sqlite_task_bus.py tests/test_fixed_route_task_executor.py tests/test_execution_plane_models.py tests/test_execution_plane_service.py tests/test_execution_plane_http_transport.py tests/test_task_commands.py tests/test_task_stop_recovery.py tests/test_task_api_publisher.py` passed: 132 tests.
