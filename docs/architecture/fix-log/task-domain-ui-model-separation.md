# Fix Log: task-domain-ui-model-separation.md

> Architecture document:
> [../task-domain-ui-model-separation.md](../task-domain-ui-model-separation.md)
>
> Original:
> [../task-domain-ui-model-separation.original.md](../task-domain-ui-model-separation.original.md)
>
> Calibration date: 2026-07-10

## Workflow Gate Report

1. User request summary: fact-check and update one architecture document at a
   time, preserving the old document and recording factual evidence in a
   per-document fix log.
2. Detected workflow phase: P5 Frontend/Backend Architecture maintenance, with
   P8/P9 implementation and tests used as verification sources.
3. Task type: documentation-only architecture fact calibration.
4. Required upstream artifacts: target architecture document, current task
   domain models, Plan/TaskNode migration docs, UI contract models, projection
   code, command gateway code, Runtime Input and Activity implementation, and
   relevant tests.
5. Found artifacts: all required artifacts were found in repository docs, code,
   and tests.
6. Missing or weak artifacts: the old architecture document was stale because
   it mixed early server-core design with Product 1.1 implementation facts.
7. Whether implementation is allowed now: yes, because this is a docs-only
   calibration grounded in existing artifacts.
8. Prework required before implementation: preserve the original file and
   inspect related docs/code/tests before rewriting.
9. Proposed execution scope: rewrite only
   `docs/architecture/task-domain-ui-model-separation.md` and add this fix log.
10. Acceptance criteria: original preserved, current architecture doc generated,
    facts and stale claims listed, and targeted validation commands run.
11. Risks and assumptions: no production behavior changes were made; status
    model details remain transitional and must be stated as such.

## Sources Inspected

Architecture and product docs:

- `docs/architecture/task-domain-ui-model-separation.md`
- `docs/plans/feature/plan-tasknode-contract-migration.md`
- `docs/product/canonical-status-model.md`
- `docs/product/plato-1-1-open-work.md`

Backend domain and projection code:

- `src/taskweavn/task/models.py`
- `src/taskweavn/task/plan_models.py`
- `src/taskweavn/task/views.py`
- `src/taskweavn/task/projection.py`
- `src/taskweavn/task/plan_publisher.py`
- `src/taskweavn/task/plan_lifecycle.py`
- `src/taskweavn/server/ui_contract/view_models.py`
- `src/taskweavn/server/ui_contract/snapshots.py`
- `src/taskweavn/server/ui_contract/plan_projection.py`
- `src/taskweavn/server/ui_contract/plan_read_helpers.py`
- `src/taskweavn/server/ui_contract/query_snapshot_helpers.py`
- `src/taskweavn/server/ui_contract/gateways.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/ui_contract/command_plan_helpers.py`
- `src/taskweavn/server/ui_contract/runtime_input.py`
- `src/taskweavn/server/ui_contract/session_activity_projection.py`

Frontend code:

- `frontend/src/shared/api/types.ts`
- `frontend/src/pages/main-page/mainPageUiTypes.ts`
- `frontend/src/pages/main-page/mainPageViewModel.ts`
- `frontend/src/pages/main-page/mainPageRuntimeInput.ts`
- `frontend/src/pages/main-page/mainPageSelectors.ts`
- `frontend/src/pages/main-page/mainPageActivityProjection.ts`
- `frontend/src/pages/main-page/runtime/adapter.ts`

Tests:

- `tests/test_task_views.py`
- `tests/test_task_projection.py`
- `tests/test_plan_view_contract.py`
- `tests/test_plan_store.py`
- `tests/test_plan_publisher.py`
- `tests/test_plan_lifecycle.py`
- `tests/test_ui_query_gateway.py`
- `tests/test_ui_command_gateway.py`
- `tests/test_session_activity_projection.py`
- `tests/test_runtime_input_router.py`
- `tests/test_contract_revision_commands.py`

## Verified Facts

### Domain facts

1. `src/taskweavn/task/models.py` states that `TaskDomain` is the published
   execution fact used by TaskBus and agents, while `DraftTaskNode` and
   `DraftTaskTree` represent authoring facts before publish.
2. `TaskDomain` currently stores execution statuses `pending`, `running`,
   `waiting_for_user`, `done`, and `failed`.
3. `TaskDomain` also stores result/error refs, ASK/confirmation wait linkage,
   interrupt request metadata, and dispatch constraints.
4. `DraftTaskNode` stores draft identity, session/tree identity, task content,
   constraints, status, version, and timestamps.
5. `DraftTaskStatus` values are `draft`, `accepted`, `published`, and
   `cancelled`.
6. `src/taskweavn/task/plan_models.py` defines durable Product 1.1 `Plan` and
   `PlanTaskNode` storage-facing models.
7. `PlanStatus` includes `draft`, `reviewing`, `approved`, `published`,
   `running`, `finalizing`, `awaiting_acceptance`, `accepted`,
   `follow_up_needed`, `failed`, `cancelled`, and `archived`.
8. `PlanTaskNode` stores `readiness`, `execution`, draft/published refs, result
   refs, error refs, file summary refs, and audit refs.
9. `PlanTaskNodeReadiness` values are `draft`, `reviewing`, `approved`,
   `published`, `cancelled`, and `unknown`.
10. `PlanTaskNodeExecutionStatus` values are `not_started`, `pending`,
    `running`, `waiting_for_user`, `done`, `failed`, `cancelled`, and
    `unknown`.

### Projection facts

11. `src/taskweavn/task/views.py` explicitly says server-core task views are not
    backend task facts and not transport-facing UI contracts.
12. `DefaultTaskProjectionService` is read-only and combines task, draft,
    message, confirmation, file, summary, and permission facts into server-core
    task views.
13. `DefaultTaskProjectionService.list_plan_tree` exists and projects the
    Product 1.1 plan surface as a flat TaskNode list, hiding legacy hierarchy
    complexity from the first Product 1.1 plan surface.
14. `src/taskweavn/server/ui_contract/view_models.py` is the transport-facing
    ViewModel module consumed by Plato frontend.
15. Backend transport `TaskNodeCardView` currently includes `status` and
    `execution`, but not a Python `readiness` field.
16. Frontend `frontend/src/shared/api/types.ts` reserves optional
    `TaskNodeCardView.readiness`, `readonlyReason`, and `availableActions`
    fields, so the status split is only partially migrated.
17. `DefaultPlanProjectionService.project_stored_plan` projects durable Plan
    and TaskNode rows into `PlanView`.
18. `DefaultPlanProjectionService.project_legacy_task_tree` projects old
    `TaskTreeView` data into a synthetic `PlanView`.
19. Legacy `PlanView.task_nodes` are flattened, while
    `PlanView.task_tree_projection` preserves the compatibility tree shape.
20. Stored-plan projection maps `Plan.status` to `PlanUiStatus` and
    `PlanTaskNode.execution` to both compatibility task status and execution
    fields.
21. Intentional stop failures with `error_ref` prefixes `cancelled:` or
    `skipped:` are projected as cancelled instead of failed/retryable.
22. `ExecutionRollupView` is derived from projected task-node execution.

### Snapshot and read-path facts

23. `MainPageSnapshot` carries `active_plan`, `archived_plans`, compatibility
    `task_tree`, planning, messages, pending confirmations, pending asks,
    active ask, result, file-change summary, audit links, cursor, and generated
    time.
24. `MainPageSnapshot` has a compatibility validator that populates
    `active_plan` from legacy `task_tree` when `active_plan` is missing.
25. `get_session_snapshot_query` loads the legacy source tree, maps it to the
    UI contract, then asks `active_plan_read_context` whether to prefer stored
    Plan data or legacy fallback.
26. `active_stored_plan` prefers active authoring state's `active_plan_id`,
    then `PlanStore.get_active_plan`, then archived legacy plan lookup.
27. If the active stored plan is archived, active legacy fallback is suppressed.
28. Archived plan views are projected separately and can appear in snapshot
    messages as archived-plan messages.
29. Result and file-change reads prefer stored PlanTaskNode identity when
    stored nodes exist, then fall back to legacy tree reads only when allowed.
30. Audit selected-task read helpers normalize legacy task ids back to
    PlanTaskNode ids where possible.

### Command and Runtime Input facts

31. `DefaultUiCommandGateway` is implemented and wraps server-core command
    services.
32. The command gateway handles append session input, generate task tree, update
    task node, append task input, publish, archive, retry, stop, confirmation
    resolution, ASK answers, authoring ASK answers, and authoring-state repair.
33. `publish_task_tree` first tries to publish an active durable Plan through
    `DefaultPlanPublisher`; if no durable plan is available it falls back to
    legacy DraftTaskTree publish.
34. `archive_plan` supports durable plans and legacy synthetic plan ids.
35. `RuntimeInputRouteRequest` carries session id, content, mode, selected
    session/plan/task scope, inquiry refs, and client state for active ASK or
    confirmation.
36. Runtime Input decisions can dispatch to read-only inquiry, guidance,
    ASK/confirmation resolution, existing commands, execution handoff,
    clarification, or unsupported routes.
37. Runtime Input route results can include Activity, command response, and
    read-only inquiry result.

### Activity, frontend, and product docs facts

38. `DefaultSessionActivityProjectionService` projects user-readable Activity
    from safe UI facts: messages, active/archived plans, task nodes, ASKs,
    confirmations, result, and file-change summary.
39. Activity items include scope, side effect, related refs, source kind, source
    id, and disclosure level.
40. `frontend/src/pages/main-page/mainPageViewModel.ts` derives local Main Page
    detail, input, workspace, task workspace, top bar, pending command, and
    audit-entry view models from `MainPageSnapshot` plus local controller state.
41. `frontend/src/pages/main-page/mainPageRuntimeInput.ts` builds runtime input
    route requests from selected session/plan/task scope and active ASK or
    confirmation client state.
42. `docs/plans/feature/plan-tasknode-contract-migration.md` says the
    Plan/TaskNode migration foundation is accepted and that legacy DraftTaskTree
    compatibility remains.
43. That same plan says the Main Page query projection prefers stored Plan data
    when available while keeping legacy TaskTree compatibility.
44. `docs/product/canonical-status-model.md` identifies status flattening as a
    migration issue: planning, readiness, execution, confirmation, permission,
    and audit verdict must not be treated as one field.
45. `docs/product/plato-1-1-open-work.md` says Plan/TaskNode foundation,
    Session Activity, Runtime Input Router, and Contract Revision command
    substrate are implemented or accepted Product 1.1 baselines.

## Stale Or Corrected Claims

1. The old document treated `TaskDomain`, `DraftTaskNode`, and
   `DraftToPublishedMapping` as the main domain split. The new document adds
   durable `Plan` and `PlanTaskNode` as Product 1.1 source-of-truth facts.
2. The old document described concrete API command handlers and persistence as
   follow-up work. Current code has `DefaultUiCommandGateway`, `PlanStore`,
   `DefaultPlanPublisher`, and `PlanTaskNodeLifecycleSync`.
3. The old document centered a conceptual `TaskViewData` / `TaskUIState`
   division. Current code uses server-core task views, transport UI contract
   view models, and frontend Main Page view models instead.
4. The old document did not clearly distinguish server-core task views from the
   frontend transport contract. Current `task.views` explicitly says it is not
   the transport-facing UI contract.
5. The old document over-focused on a TaskTree projection. Current Product 1.1
   read path is plan-aware and returns `active_plan`, `archived_plans`, and
   compatibility `task_tree`.
6. The old document implied hierarchy as a central task-tree concept. Product
   1.1 current Plan/TaskNode contract is flat; legacy hierarchy is preserved
   only in compatibility projections.
7. The old document did not reflect archived plan history and suppression of
   active legacy fallback when a stored plan is archived.
8. The old document did not reflect Runtime Input Router, Contract Revision
   command skills, durable Activity, read-only inquiry, and diagnostic linkage
   now present in Product 1.1.
9. The old document's status model needed correction: current implementation
   still has compatibility `TaskNodeStatus`, while canonical separation of
   readiness/execution/confirmation/permission/audit remains partially migrated.
10. The old document did not capture that richer server-core permission/action
    data is not fully exposed through current transport `TaskNodePermissions`.

## New Document Decisions

1. Keep the document focused on current architecture rather than the historical
   implementation plan.
2. Use `Plan` and `PlanTaskNode` as the primary Product 1.1 identity in the
   architecture narrative.
3. Keep `DraftTaskTree` and `TaskTreeView` as compatibility surfaces, not the
   future source of truth.
4. State the status-model transition explicitly to avoid false completion
   claims.
5. Describe Activity as a projection from safe UI facts, not as raw domain
   storage.
6. Describe frontend state as local rendering/interaction state only.

## Validation Log

Validation commands run after this rewrite:

```bash
git diff --check
uv run pytest tests/test_task_views.py tests/test_task_projection.py tests/test_plan_view_contract.py tests/test_plan_store.py tests/test_plan_publisher.py tests/test_plan_lifecycle.py tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_session_activity_projection.py tests/test_runtime_input_router.py tests/test_contract_revision_commands.py
npm --prefix frontend run test -- src/pages/main-page/mainPageViewModel.test.ts src/pages/main-page/mainPageRuntimeInput.test.ts src/pages/main-page/mainPageSelectors.test.ts src/pages/main-page/mainPageActivityProjection.test.ts src/pages/main-page/MainPageWorkbench.test.tsx src/pages/main-page/ActivityOverlay.test.tsx src/shared/api/backendContractFixtures.test.ts
```

Results:

- `git diff --check`: passed.
- Backend pytest: 169 passed.
- Frontend Vitest: 7 files passed, 95 tests passed.
