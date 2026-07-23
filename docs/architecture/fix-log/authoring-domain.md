# Authoring Domain Fact Calibration Fix Log

> Target document: `docs/architecture/authoring-domain.md`
> Original preserved as: `docs/architecture/archive/original/authoring-domain.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue architecture fact calibration one document at a time.
- Detected phase: P5 architecture maintenance, verified against P8/P9 code and
  tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: target architecture doc, Authoring Command
  Protocol, Collaborator authoring implementation, RawTask/DraftTaskTree
  persistence plan, ASK domain unification plan, Plan/TaskNode migration plan,
  stores, command gateway, query gateway, Plan publisher, and tests.
- Found artifacts: RawTask and command models, DraftTaskTree models,
  Plan/TaskNode models, authoring stores, SQLite authoring and Plan stores,
  command service, UI command/query gateway, Runtime Input Router models, and
  direct tests.
- Missing or weak artifacts: previous document mixed current implementation
  with future lifecycle/status ideas and did not reflect durable Plan/TaskNode
  migration as a current fact.
- Implementation allowed now: yes, docs-only.
- Prework required: verify code and tests before editing.
- Scope: preserve original, rewrite `authoring-domain.md`, and add this
  fix-log.
- Acceptance criteria: active document reflects current RawTask, ASK,
  DraftTaskTree, Plan, active state, command, publish, and projection facts.
- Risks and assumptions: adjacent docs may still be stale and are handled in
  later slices.

## Maintainability Gate

- Requested change: architecture hygiene for `authoring-domain.md`.
- Trigger: architecture fact calibration.
- Size signal: original document was 563 lines, below the 800-line threshold.
- Current risk level: low for docs-only change.
- Responsibility count: broad architecture doc crossing authoring, publish,
  Plan migration, projection, ASK, and runtime input boundaries.
- Coupling signals: medium conceptual coupling, no production code edits.
- Refactor required first: no.
- Allowed change type: narrow docs correction.
- Proposed slice: one architecture document only.
- Acceptance criteria: original preserved; fix-log lists evidence; active doc
  marks future items as future.
- Validation commands: `git diff --check` plus targeted authoring, Plan,
  publish, command gateway, query gateway, and ASK tests.
- Risks and assumptions: unrelated dirty files remain untouched.

## Evidence Inspected

### Code

- `src/taskweavn/task/authoring.py`
- `src/taskweavn/task/models.py`
- `src/taskweavn/task/stores.py`
- `src/taskweavn/task/authoring_service.py`
- `src/taskweavn/task/authoring_idempotency.py`
- `src/taskweavn/task/sqlite_authoring.py`
- `src/taskweavn/task/plan_models.py`
- `src/taskweavn/task/plan_stores.py`
- `src/taskweavn/task/sqlite_plan_store.py`
- `src/taskweavn/task/plan_from_draft.py`
- `src/taskweavn/task/plan_publisher.py`
- `src/taskweavn/task/plan_commands.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/ui_contract/query_snapshot_helpers.py`
- `src/taskweavn/server/ui_contract/ask_projection.py`
- `src/taskweavn/server/ui_contract/plan_projection.py`
- `src/taskweavn/server/ui_contract/plan_read_helpers.py`
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/ui_contract/runtime_input.py`

### Tests

- `tests/test_task_authoring.py`
- `tests/test_authoring_command_service.py`
- `tests/test_in_memory_authoring_stores.py`
- `tests/test_sqlite_authoring_stores.py`
- `tests/test_plan_store.py`
- `tests/test_plan_publisher.py`
- `tests/test_plan_commands.py`
- `tests/test_plan_lifecycle.py`
- `tests/test_plan_view_contract.py`
- `tests/test_task_publisher.py`
- `tests/test_task_publish_service.py`
- `tests/test_task_publisher_input.py`
- `tests/test_ask_projection.py`
- `tests/test_ask_recovery.py`
- `tests/test_ui_command_gateway.py`
- `tests/test_ui_query_gateway.py`
- `tests/test_collaborator_api_adapter.py`
- `tests/test_collaborator_authoring_service.py`

### Related Docs And Plans

- `docs/plans/feature/raw-task-draft-tree-persistence.md`
- `docs/plans/feature/ask-domain-unification-batch-answer.md`
- `docs/plans/feature/plan-tasknode-contract-migration.md`
- `docs/architecture/authoring-command-protocol.md`
- `docs/architecture/collaborator-agent-task-authoring.md`

## Verified Facts

1. `RawTask`, `RawTaskAsk`, `RawTaskAnswer`,
   `RawTaskAnswerOption`, and `FeasibilityReport` are implemented in
   `taskweavn.task.authoring`.

2. `RawTaskAsk` does not currently persist a `status` field or
   `superseded_by_draft_tree_id`.

3. `RawTask.status` values are `created`, `assessing`, `awaiting_user`,
   `ready_to_plan`, `converted`, `rejected`, and `cancelled`.

4. `FeasibilityReport.status` values are `ready`, `needs_clarification`,
   `needs_user_permission`, `partially_feasible`, `not_supported`, and `unsafe`.

5. `TaskDomain` is the execution Task fact. `TaskBus` owns execution statuses
   such as `pending`, `running`, `waiting_for_user`, `done`, and `failed`.

6. `DraftTaskTree` and `DraftTaskNode` are implemented as legacy-compatible
   authoring facts.

7. Current `DraftTaskNode.status` values are `draft`, `accepted`, `published`,
   and `cancelled`. Current code does not define persisted DraftTaskTree
   statuses `validating` or `ready_to_publish`.

8. Product 1.1 durable `Plan` and `PlanTaskNode` models are implemented.

9. `PlanStore`, `PlanTaskNodeStore`, and `SqlitePlanStore` are implemented with
   additive Plan tables in the authoring database.

10. `build_plan_from_draft_tree` creates durable Plan/TaskNode rows from
    legacy draft facts and preserves source RawTask/DraftTaskTree lineage.

11. `DefaultAuthoringCommandService` creates a durable Plan during
    `create_tree` when a `PlanStore` is configured.

12. `ActiveAuthoringState` includes `active_plan_id` and supports
    `none`, `raw_task`, `draft_tree`, `published`, and `cancelled` states.

13. `SqliteAuthoringStateStore` persists active RawTask/DraftTaskTree/Plan
    identity and supports migration of `active_plan_id`.

14. Planning projection marks authoring asks as `superseded` when a task tree
    exists. This is a projection status, not a RawTaskAsk field.

15. UI command gateway rejects stale authoring ask answers when authoring state
    has moved to draft tree, published, cancelled, or a published tree exists.

16. UI command gateway can repair dirty authoring state by cancelling an active
    raw authoring flow after a TaskTree exists.

17. Authoring ASK and execution ASK use separate backend authorities:
    `RawTask.asks`/`answers` versus `AskStore`/`AskRequest`.

18. `DefaultPlanPublisher` maps durable Plan/TaskNode rows to existing
    `TaskPublisher` requests and writes published refs back to PlanTaskNodes.

19. UI publish prefers active durable Plan publish and falls back to legacy
    DraftTaskTree publish when no active durable Plan path is available.

20. Typed authoring EventStream events such as `RawTaskCreated` or
    `RawTaskAskSuperseded` are not currently implemented.

21. Runtime Input Router sits in front of authoring and routes to command
    services, read-only inquiry, confirmation/ASK handling, or execution
    handoff. It is not the Authoring Domain store authority.

## Corrections Applied

1. Added current Product 1.1 Plan/TaskNode facts as part of Authoring Domain.

2. Corrected RawTaskAsk lifecycle: supersession is projection/gateway behavior,
   not a persisted RawTaskAsk status field.

3. Corrected DraftTaskTree lifecycle: current persisted statuses live on
   DraftTaskNode and do not include `validating` or `ready_to_publish`.

4. Replaced "first implementation can be in-memory" wording with the current
   fact that SQLite authoring and Plan stores are implemented and sidecar-wired.

5. Added current active authoring state facts, including `active_plan_id`.

6. Clarified Plan publish preference and legacy DraftTaskTree fallback.

7. Clarified ASK split between authoring ASK and execution ASK.

8. Marked typed authoring EventStream events as future rather than current.

9. Clarified Runtime Input Router as a front-door router, not authoring storage
   authority.

## Follow-up Candidates

- `docs/architecture/authoring-command-protocol.md`: should be calibrated next
  because it likely contains stale operation and idempotency details.
- `docs/architecture/contract-revision-and-execution-loops.md`: should be
  checked against Runtime Input Router and Contract Revision command facts.
- `docs/architecture/task-domain-ui-model-separation.md`: should be checked
  against current PlanView and TaskNodeCardView projection behavior.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_task_authoring.py tests/test_authoring_command_service.py tests/test_in_memory_authoring_stores.py tests/test_sqlite_authoring_stores.py tests/test_plan_store.py tests/test_plan_publisher.py tests/test_plan_commands.py tests/test_plan_lifecycle.py tests/test_plan_view_contract.py tests/test_task_publisher.py tests/test_task_publish_service.py tests/test_task_publisher_input.py tests/test_ask_projection.py tests/test_ask_recovery.py tests/test_ui_command_gateway.py tests/test_ui_query_gateway.py tests/test_collaborator_api_adapter.py tests/test_collaborator_authoring_service.py`
  passed: 273 tests.

## PR #182 Review Follow-Up (2026-07-11)

- Removed `TaskClaim` and `TaskFailure` from the current Execution Domain object
  list because neither model exists in current `src/`, frontend, or tests.
- Replaced them with the implemented TaskBus/runtime facts `TaskDomain` and
  `TaskRunResult`, plus the implemented Execution Plane DTOs `TaskExecution`,
  `TaskResult`, and `TaskError`.
- This is a documentation-only fact correction; no runtime contract changed.
