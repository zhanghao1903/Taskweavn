# TaskBus Architecture Fact Calibration Fix Log

> Target document: `docs/architecture/bus.md`
> Original preserved as: `docs/architecture/bus.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: fact-calibrate architecture documents one by one; current target is TaskBus architecture.
- Detected phase: P5 architecture maintenance, verified against P8/P9 implementation and tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: existing architecture docs, TaskBus code, execution bridge code, Execution Plane code, publisher/audit code, related tests.
- Found artifacts: TaskBus protocol and implementations, fixed-route executor/dispatcher, embedded Execution Plane, WeChat runtime handler, plan lifecycle sync, timeline and EventStream projections, TaskBus tests.
- Missing or weak artifacts: previous `bus.md` mixed current facts with future dynamic routing design.
- Implementation allowed now: yes, docs-only calibration.
- Prework required: verify current implementation facts before revising doc.
- Scope: preserve original, revise `bus.md`, add this fix-log.
- Acceptance criteria: every current-behavior claim is traceable to code/tests; future claims are explicitly labeled future.
- Risks and assumptions: current Product 1.1 remains fixed-route/local embedded execution; dynamic assignment and remote worker leases remain future unless code later changes.

## Maintainability Gate

- Requested change: architecture hygiene for `docs/architecture/bus.md`.
- Trigger: maintenance / architecture fact calibration.
- Size signal: `bus.md` was 677 lines, below the 800-line production-behavior review threshold.
- Risk level: low for docs-only slice.
- Refactor required first: no.
- Allowed change type: docs-only boundary correction.
- Validation commands: `git diff --check` plus targeted TaskBus/Execution Plane tests.

## Evidence Inspected

### Code

- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`
- `src/taskweavn/task/execution.py`
- `src/taskweavn/task/publisher_service.py`
- `src/taskweavn/task/sqlite_publish.py`
- `src/taskweavn/task/plan_lifecycle.py`
- `src/taskweavn/task/timeline.py`
- `src/taskweavn/task/event_file_changes.py`
- `src/taskweavn/execution_plane/embedded_service.py`
- `src/taskweavn/execution_plane/wechat_send_runtime.py`
- `src/taskweavn/server/main_page.py`

### Tests

- `tests/test_task_bus_lifecycle.py`
- `tests/test_sqlite_task_bus.py`
- `tests/test_fixed_route_task_executor.py`
- `tests/test_execution_plane_service.py`
- `tests/test_wechat_send_runtime.py`
- `tests/test_sqlite_publish_stores.py`

### Related Architecture Docs

- `docs/architecture/overview.md`
- `docs/architecture/agent.md`
- `docs/architecture/task.md`
- `docs/architecture/session.md`
- `docs/architecture/reference.md`
- `docs/plans/feature/execution-plane-service-task-api.md`

## Verified Facts

1. Current `TaskBus` Protocol includes `publish`, `claim_next`, `complete`, `fail`, `wait_for_user`, `wait_for_confirmation`, `resume_after_user`, `resume_after_confirmation`, `skip`, `retry`, `request_interrupt`, `recover_interrupted_running_tasks`, `get`, `list_for_session`, and `list_children`.

2. Current TaskBus has no `assign`, `claim_assigned`, `assignment_index`, `assigned_agent_id`, `running_task`, stale pending sweep, worker lease, or heartbeat API.

3. `InMemoryTaskBus` stores lifecycle state in `_tasks: dict[(session_id, task_id), TaskDomain]` and parent/child lookup in `_children`.

4. `SqliteTaskBus` stores Task lifecycle state in a workspace-level SQLite `tasks` table with `session_id`, `task_id`, `parent_id`, `root_id`, `status`, `order_index`, `created_at`, and full `payload` JSON. The main app constructs it as `SqliteTaskBus(layout.workspace_tasks_db)`.

5. `claim_next` selects pending Tasks by `session_id`, matching `required_capability`, parent readiness, and deterministic order. It sets `status="running"`, `claimed_by`, and `started_at`.

6. TaskBus itself does not enforce a global "only one running task" invariant. The current product path is serial because `FixedRouteExecutionDispatcher` coalesces per-session execution and `FixedRouteTaskExecutor.tick()` runs one claimed Task at a time.

7. Parent-child readiness is claim-time logic: a child becomes eligible only after its parent is `done`. `complete` does not wait for children and does not implement fan-in.

8. `wait_for_user` and `wait_for_confirmation` both require a running Task and transition it to `waiting_for_user`, with exactly one active ASK or confirmation linkage.

9. `resume_after_user` and `resume_after_confirmation` transition `waiting_for_user` back to `pending`, clear wait links, clear `claimed_by`, clear `started_at`, and require a later `claim_next`. They do not resume directly to `running`.

10. `skip` marks pending/running Tasks as failed with an `error_ref` beginning with `skipped:`.

11. `retry` moves only failed Tasks back to pending on the same Task identity, clears lifecycle result/error/wait/claim/interrupt fields, and can append a retry instruction to `intent`.

12. `request_interrupt` immediately fails pending Tasks as `cancelled: ...`, but running Tasks remain running with interrupt intent recorded. `recover_interrupted_running_tasks` converts interrupted running Tasks to failed with a sidecar recovery safe point.

13. `EmbeddedTaskApiService` maps ordinary `TaskRequest` objects to TaskBus Tasks, preserves Execution Plane idempotency, and exposes execution events/evidence through its own store.

14. `WeChatSendRuntimeHandler` is a local embedded runtime handler. It can publish/resume/claim TaskBus Tasks for the WeChat send flow, but it is not a general Agent Manager or dynamic assignment implementation.

15. `TaskPublishAuditSink` and `PublishAuditEvent` are explicitly service-level publish audit hooks and are intentionally not EventStream events yet.

16. `TaskInteractionTimelineService` treats EventStream as one read-side source among draft, message, confirmation, file, and summary sources. It does not rebuild TaskBus lifecycle state from EventStream.

17. `EventStreamFileChangeStore` is a read-only projection over session EventStream facts for file changes, not the TaskBus lifecycle store.

18. `PlanTaskNodeLifecycleSync` best-effort synchronizes TaskBus lifecycle facts back into durable PlanTaskNode rows.

## Corrections Applied

1. Replaced "TaskBus is EventStream materialized view" with "TaskBus store owns PublishedTask lifecycle; EventStream is runtime/audit/evidence read-side."

2. Replaced "TaskBus has exactly one running task" with "current fixed-route product path is serial per Session, but TaskBus API has no global `running_task` guard."

3. Removed current-fact language for Router assignment, `claim_assigned`, assignment indexes, and stale pending sweep; moved those into future dynamic routing foundation.

4. Corrected Product 1.1 path from `TaskPublisher / Agent Tool -> TaskBus` to publisher/API/runtime boundaries feeding TaskBus and fixed-route dispatcher/executor.

5. Added current local Execution Plane facts: `EmbeddedTaskApiService` maps ordinary TaskRequests to TaskBus and special task types may use embedded runtime handlers.

6. Added `wait_for_confirmation` and `resume_after_confirmation` to the current API surface.

7. Corrected resume semantics from `waiting_for_user -> running` to `waiting_for_user -> pending`.

8. Corrected parent/child semantics: child readiness is enforced during claim; `complete` does not wait for all children.

9. Corrected lifecycle construction: the app uses workspace-level `SqliteTaskBus(layout.workspace_tasks_db)` with `session_id` row isolation, not `TaskBus(session_id, event_stream)`.

10. Corrected shutdown semantics: current `SqliteTaskBus.close()` only closes the SQLite connection; there is no implemented session-close pending cancellation flow in TaskBus.

11. Updated decision summary to separate current facts from future dynamic routing, remote worker, concurrency, and stale pending timeout work.

## Follow-up Candidates

- `docs/architecture/taskbus-service-multi-execution-env.md`: likely needs alignment with embedded-only Execution Plane and no current remote lease.
- `docs/architecture/bus-v2.md`: should be checked after this doc because it likely assumes assignment/lease/concurrency details.
- `docs/architecture/authoring-domain.md`: may still mention `PublishedTask` and TaskBus in older terms.
- `docs/architecture/contract-revision-and-execution-loops.md`: should be checked for Runtime Input Router vs TaskBus execution boundary.
- `docs/architecture/ui-backend-communication.md`: should be checked for ASK/confirmation resume and TaskBus state projection semantics.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_task_bus_lifecycle.py tests/test_sqlite_task_bus.py tests/test_fixed_route_task_executor.py tests/test_task_stop_recovery.py tests/test_execution_plane_service.py tests/test_wechat_send_runtime.py tests/test_task_publisher.py tests/test_task_publish_service.py tests/test_task_api_publisher.py tests/test_task_pipeline.py tests/test_task_projection.py tests/test_task_timeline.py tests/test_plan_lifecycle.py tests/test_task_event_file_changes.py tests/test_task_commands.py` passed: 196 tests.
