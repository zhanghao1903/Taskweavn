# Task Architecture Fact Calibration Log

> Source document: `docs/architecture/task.md`
> Preserved original: `docs/architecture/archive/original/task.original.md`
> Calibrated document version: v1.6 · 2026-07-10
> Calibration scope: verify current Task architecture claims against Task domain
> models, TaskBus implementations, publisher/authoring boundaries, Execution
> Plane models, related architecture docs, and targeted tests.

---

## 1. Workflow Gate Report

- User request summary: continue one-document-at-a-time architecture fact
  calibration with original preservation and per-document fix logs.
- Detected workflow phase: P5 architecture fact maintenance, with P8
  integration and P9 verification evidence.
- Task type: documentation fact correction and evidence log.
- Required upstream artifacts: current task architecture doc, Task domain /
  TaskBus / publisher / authoring / Execution Plane implementation, related
  architecture and feature docs, targeted tests.
- Found artifacts:
  - `docs/architecture/task.md`
  - `docs/architecture/agent.md`
  - `docs/architecture/overview.md`
  - `docs/architecture/contract-revision-and-execution-loops.md`
  - `docs/plans/feature/execution-plane-service-task-api.md`
  - Task domain, TaskBus, publisher, Plan, Execution Plane, and projection code
    under `src/taskweavn/`
- Missing or weak artifacts:
  - Dynamic assignment / Agent Manager remains a future model, not current
    execution code.
  - Completion-time `task_after` pipeline orchestration is modeled but not
    implemented in the current publish-time loader.
  - Some broader TaskBus/EventStream statements are still likely stale in
    `bus.md` and should be handled in that document's own pass.
- Implementation allowed now: yes, documentation-only calibration.
- Prework required before implementation: preserve original document, verify
  implementation and test evidence, add this fix log.
- Proposed execution scope: narrow revision of `task.md`; no production code
  changes.
- Acceptance criteria:
  - Old document remains available for comparison.
  - Current TaskDomain fields and lifecycle transitions match code.
  - Current publish, API, Execution Plane, PlanTaskNode sync, ASK/confirmation,
    retry, interrupt, and pipeline facts are separated from future roadmap.
  - `git diff --check` and targeted tests pass.
- Risks and assumptions:
  - This log calibrates `task.md` only. Other architecture docs can still
    contradict it until processed separately.
  - Future abstractions remain documented only when explicitly labeled as
    later dynamic routing / workflow / orchestration work.

## 2. Evidence Inspected

### Implementation Evidence

- `src/taskweavn/task/models.py`
  - `TaskDomain` is the current published execution fact.
  - Current status values are `pending`, `running`, `waiting_for_user`, `done`,
    and `failed`.
  - Current fields include `task_id`, `session_id`, `parent_id`, `root_id`,
    `order_index`, `intent`, `summary`, `instructions`, `acceptance_criteria`,
    `required_capability`, `dispatch_constraints`, `result_ref`, `error_ref`,
    `claimed_by`, ASK/confirmation wait linkage, interrupt intent fields, and
    timestamps.
  - There are no current `assigned_agent_id`, `assigned_by`, `assigned_at`, or
    `assignment_rationale` fields.
- `src/taskweavn/task/bus.py`
  - `TaskBus` owns published Task lifecycle transitions.
  - `InMemoryTaskBus.claim_next(...)` claims only `pending` tasks matching
    `required_capability`, records `claimed_by`, and requires parent `done`.
  - `resume_after_user(...)` and `resume_after_confirmation(...)` both return
    the Task to `pending`, clear wait linkage, clear `claimed_by`, and clear
    `started_at`.
  - `retry(...)` moves a failed Task back to `pending` on the same identity,
    clears refs/linkage/interrupt state, and can append retry instruction to
    `intent`.
- `src/taskweavn/task/sqlite_bus.py`
  - `SqliteTaskBus` persists Task lifecycle facts in a `tasks` table with a
    status column and full `TaskDomain` JSON payload.
  - It implements the same lifecycle surface as `InMemoryTaskBus`.
- `src/taskweavn/task/publisher.py`
  - `DefaultTaskPublisher` normalizes task trees into `TaskDomain` objects and
    writes them through TaskBus.
  - Idempotent publish can replay existing tasks without duplicating TaskBus
    rows.
  - `dispatch_constraints` stores publish metadata, source info,
    `preferred_agent_id`, and `required_capabilities`.
- `src/taskweavn/task/api_publisher.py`
  - `DefaultApiTaskPublisher` is the transport-neutral API publish adapter.
  - It enforces session permission, idempotency policy, capability / agent
    allowlists, and optional rate limiting before calling the publish service.
- `src/taskweavn/task/pipeline.py`
  - `DefaultPipelineTaskLoader` expands publish-time `task_before` and
    `task_begin` specs into ordinary normalized root tasks.
  - `task_after` is modeled but not loaded during publish-time expansion.
- `src/taskweavn/task/plan_models.py`
  - `Plan` and `PlanTaskNode` are durable Product 1.1 contract facts.
  - `PlanTaskNode` may hold `published_ref`, `result_ref`, `error_ref`,
    `file_summary_ref`, and `audit_ref`.
- `src/taskweavn/task/plan_lifecycle.py`
  - `PlanTaskNodeLifecycleSync` best-effort syncs TaskBus status/result/error
    facts back into durable PlanTaskNode rows.
- `src/taskweavn/task/execution.py`
  - `FixedRouteTaskExecutor` selects eligible pending work, claims through
    TaskBus, runs the resident Default Agent, and commits done/failed/waiting
    outcomes through TaskBus.
  - `FixedRouteExecutionDispatcher` coalesces triggers and does not hold
    AgentLoop state between tasks.
- `src/taskweavn/execution_plane/models.py`
  - `TaskRequest` / `TaskExecution` are service-level Execution Plane models.
  - `TaskExecutionStatus` includes service-level statuses beyond TaskDomain,
    but TaskDomain still has the five-status lifecycle above.
- `src/taskweavn/execution_plane/embedded_service.py`
  - `EmbeddedTaskApiService.publish_task(...)` maps ordinary `TaskRequest`
    values to TaskBus tasks and persists Execution Plane idempotency/execution
    records.
  - Special task types can be handled by `EmbeddedTaskRuntimeHandler`.
- `src/taskweavn/task/result_summary.py`
  - Result/error refs resolve to durable user-readable summaries outside the
    TaskDomain payload.
- `src/taskweavn/task/timeline.py` and `src/taskweavn/task/projection.py`
  - Timeline and UI projections stitch Task facts with draft, message,
    confirmation, EventStream, file-change, and result summary facts.
  - They are read-side composition layers, not Task lifecycle authorities.

### Test Evidence

- `tests/test_task_bus_lifecycle.py`
  - In-memory TaskBus lifecycle, ASK/confirmation wait/resume, retry, skip, and
    interrupt semantics.
- `tests/test_sqlite_task_bus.py`
  - SQLite TaskBus persistence, parent eligibility, wait/resume, retry,
    interrupt recovery, and reopen behavior.
- `tests/test_task_publisher.py`
  - DefaultTaskPublisher normalization, publish, idempotency, draft-tree
    publish, and retry semantics.
- `tests/test_task_api_publisher.py`
  - API publish permissions, idempotency, capability/agent validation, and
    SQLite replay.
- `tests/test_execution_plane_service.py`
  - Embedded Execution Plane Task API publish/idempotency/result behavior.
- `tests/test_task_pipeline.py`
  - Publish-time pipeline before/begin expansion and `task_after` non-loading.
- `tests/test_plan_lifecycle.py`
  - PlanTaskNode lifecycle sync from TaskBus facts.
- `tests/test_fixed_route_task_executor.py`
  - Fixed-route Task execution, parent dependency behavior, waiting outcome,
    result/error refs, and dispatcher semantics.

### Related Documentation Evidence

- `docs/architecture/overview.md`
  - Current Product 1.1 overview treats local Execution Plane / Task API as a
    foundation and keeps dynamic distributed execution as future work.
- `docs/architecture/agent.md`
  - Current Agent calibration identifies fixed-route Default Agent execution,
    no generic `CreateTaskTool`, and Execution Plane runtime handlers.
- `docs/architecture/contract-revision-and-execution-loops.md`
  - Product-state mutations must go through command-backed Contract Revision
    boundaries; execution works through TaskBus.
- `docs/plans/feature/execution-plane-service-task-api.md`
  - Defines `TaskRequest` / `TaskExecution` service-level boundary and the
    embedded first slice.
- `docs/plans/feature/task-publishers-schedule-api.md`
  - Documents TaskPublisher, API/scheduler publish, persistent publish
    metadata, and publish-time pipeline expansion.

## 3. Verified Current Facts

1. Current `TaskDomain` is the published execution fact used by TaskBus and
   Agents.
2. Current TaskDomain has five lifecycle states:
   `pending`, `running`, `waiting_for_user`, `done`, `failed`.
3. Current TaskDomain does not include current assignment fields such as
   `assigned_agent_id`, `assigned_by`, `assigned_at`, or
   `assignment_rationale`.
4. Current dynamic assignment / assigned-only claim is a future TaskBus
   direction, not current local execution behavior.
5. Current `claim_next(...)` matches `required_capability`, records
   `claimed_by`, and only claims eligible `pending` tasks.
6. Child tasks are eligible only after their parent is `done`; current
   `complete(...)` does not inspect child terminal status.
7. `waiting_for_user` covers durable ASK and confirmation waits.
8. `resume_after_user(...)` and `resume_after_confirmation(...)` return the
   task to `pending`, not directly to `running`.
9. Skip and cancel are represented as `failed` with `skipped:` or `cancelled:`
   error refs.
10. Running interrupt records cooperative intent while keeping status
    `running`; sidecar recovery can convert stale interrupted running tasks to
    cancelled failure.
11. Retry is a narrow in-place transition from `failed` to `pending` on the
    same Task identity. It clears current refs/linkage/interrupt state.
12. Current Task lifecycle facts are persisted by TaskBus store. EventStream is
    a related read-side evidence source, not the sole Task lifecycle source of
    truth.
13. Result and error refs point to result summary / external result / Execution
    Plane stores for user-readable payloads.
14. Current publish paths include DefaultTaskPublisher, API publisher, Plan
    publisher, scheduler/pipeline adapters, and EmbeddedTaskApiService.
15. There is no generic current Agent-side `CreateTaskTool` that directly
    writes TaskBus.
16. Execution Plane `TaskRequest` can map to ordinary TaskBus tasks; special
    task types can be handled by local runtime handlers.
17. Publish-time pipeline expansion only loads `task_before` and `task_begin`;
    `task_after` remains completion-time orchestration follow-up.

## 4. Corrections Applied

- Updated document header to v1.6 · 2026-07-10.
- Added a 2026-07-10 fact calibration note for TaskDomain fields,
  ASK/confirmation resume semantics, and Execution Plane mapping.
- Added `Plan` / `PlanTaskNode` and `TaskRequest` / `TaskExecution` to the task
  taxonomy.
- Corrected the TaskDomain field sketch and property table to match current
  code.
- Replaced assignment-field current claims with `dispatch_constraints` and
  future dynamic routing notes.
- Replaced `CreateTaskTool` current claims with command-backed publisher / API /
  Execution Plane boundaries.
- Corrected state transitions so `waiting_for_user` resumes to `pending` and
  requires a later claim to run again.
- Corrected parent/child semantics: current TaskBus uses parent-done claim
  eligibility, not parent waiting for all children at complete time.
- Corrected retry semantics: same identity returns to `pending` and current
  refs/linkage are cleared.
- Corrected persistence claims: TaskBus store is current lifecycle authority;
  EventStream and other stores are read-side evidence sources.
- Corrected pipeline taxonomy to reflect publish-time before/begin expansion
  and `task_after` follow-up status.
- Updated component relationship diagram and design decision summary.

## 5. Follow-up Calibration Targets

- `docs/architecture/bus.md`
  - Re-check EventStream-as-truth statements, stale pending sweep, assignment
    roadmap, ASK/confirmation resume-to-pending semantics, and SQLite TaskBus
    persistence.
- `docs/architecture/taskbus-service-multi-execution-env.md`
  - Re-check distributed / multi-env claims against the local Execution Plane
    foundation and runtime handler seam.
- `docs/architecture/authoring-domain.md`
  - Re-check Plan / DraftTaskTree / TaskPublisher and Runtime Input Router
    command-backed boundaries.
- `docs/architecture/collaborator-agent-task-authoring.md`
  - Re-check Collaborator service, command boundaries, TaskPublisher, and no
    direct TaskBus writes.
