# Contract Revision And Execution Loops Fact Calibration Fix Log

> Target document:
> `docs/architecture/contract-revision-and-execution-loops.md`
> Original preserved as:
> `docs/architecture/contract-revision-and-execution-loops.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue architecture fact calibration one document at a time.
- Detected phase: P5 architecture maintenance, verified against P8/P9 code and
  tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: target architecture doc, Runtime Input Router,
  Contract Revision command service, guidance/idempotency/activity stores,
  read-only inquiry, Plan/TaskNode command handlers, Plan lifecycle sync, UI
  HTTP/frontend route wiring, Product 1.1 evidence, and tests.
- Found artifacts: runtime input models/router, contract revision models and
  service, read-only inquiry service, Runtime Input Activity publisher,
  diagnostic summary collector, guidance/idempotency SQLite stores, Plan
  lifecycle sync, HTTP/frontend route references, and direct tests.
- Missing or weak artifacts: previous document mixed current P0 implementation
  with broader future plan-editing and outcome-review direction; one program
  doc readiness matrix still says some command work is planned even though
  release evidence and implementation show P0 command paths are implemented.
- Implementation allowed now: yes, docs-only.
- Prework required: verify code, tests, and Product 1.1 evidence before
  editing.
- Scope: preserve original, rewrite
  `contract-revision-and-execution-loops.md`, and add this fix-log.
- Acceptance criteria: active document reflects current runtime input,
  contract revision, read-only inquiry, execution handoff, activity, audit, and
  diagnostic facts; future work remains explicit.
- Risks and assumptions: no production code edits; broader Electron smoke is
  not rerun for this docs-only slice.

## Maintainability Gate

- Requested change: architecture hygiene for
  `contract-revision-and-execution-loops.md`.
- Trigger: architecture fact calibration.
- Size signal: original document was 295 lines, below the 800-line threshold.
- Current risk level: low for docs-only change.
- Responsibility count: broad architecture doc crossing runtime input,
  contract revision, execution handoff, Activity, Audit, diagnostics, and Plan
  lifecycle.
- Coupling signals: medium conceptual coupling, no production code edits.
- Refactor required first: no.
- Allowed change type: narrow docs correction.
- Proposed slice: one architecture document only.
- Acceptance criteria: original preserved; fix-log lists evidence; active doc
  separates current implementation from future direction.
- Validation commands: `git diff --check` plus targeted runtime input,
  contract revision, read-only inquiry, Plan lifecycle, UI HTTP/query, and
  diagnostics tests.
- Risks and assumptions: unrelated dirty files remain untouched.

## Evidence Inspected

### Code

- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/ui_contract/runtime_input.py`
- `src/taskweavn/server/ui_http_runtime_input.py`
- `src/taskweavn/server/read_only_inquiry.py`
- `src/taskweavn/server/runtime_input_llm_router.py`
- `src/taskweavn/server/runtime_input_activity.py`
- `src/taskweavn/diagnostics/runtime_input.py`
- `src/taskweavn/contract_revision/models.py`
- `src/taskweavn/contract_revision/service.py`
- `src/taskweavn/contract_revision/tasknode_commands.py`
- `src/taskweavn/contract_revision/interaction_commands.py`
- `src/taskweavn/contract_revision/guidance_store.py`
- `src/taskweavn/contract_revision/idempotency_store.py`
- `src/taskweavn/contract_revision/activity.py`
- `src/taskweavn/task/plan_lifecycle.py`
- `src/taskweavn/task/plan_commands.py`
- Frontend route references under `frontend/src/pages/main-page/` and
  `frontend/src/shared/api/platoApi.ts`.

### Tests

- `tests/test_runtime_input_router.py`
- `tests/test_runtime_input_llm_router.py`
- `tests/test_contract_revision_commands.py`
- `tests/test_read_only_inquiry.py`
- `tests/test_read_only_inquiry_answer_provider.py`
- `tests/test_read_only_inquiry_sidecar_acceptance.py`
- `tests/test_main_page_sidecar_config.py`
- `tests/test_plan_lifecycle.py`
- `tests/test_plan_commands.py`
- `tests/test_ui_http_transport.py`
- `tests/test_ui_query_gateway.py`
- `tests/test_session_activity_projection.py`
- `tests/test_diagnostic_bundle_export.py`

### Related Docs

- `docs/product/plato-runtime-input-model.md`
- `docs/product/plato-1-1-p0-release-evidence-2026-06-20.md`
- `docs/product/plato-1-1-open-work.md`
- `docs/plans/feature/runtime-input-and-contract-revision-program.md`
- `docs/plans/feature/plan-tasknode-contract-migration.md`

## Verified Facts

1. `RuntimeInputRouteRequest`, `RuntimeInputRouteDecision`,
   `RuntimeInputOutcome`, and `RuntimeInputRouteResult` are implemented in
   `server.ui_contract.runtime_input`.

2. Runtime input modes are `auto`, `ask`, `guide`, and `change`.

3. Runtime input dispatch targets include read-only inquiry, guidance,
   ASK/confirmation resolution, existing commands, execution handoff,
   clarification, and unsupported.

4. `DefaultRuntimeInputRouter` checks active ASK before confirmation and before
   ordinary classification.

5. Active confirmation input must be a clear yes/no response; ambiguous input
   returns a no-effect clarification.

6. Stop and retry route to existing UI command gateway task commands and
   require selected task scope.

7. Optional `RuntimeInputRoutePlanner` is constrained to read-only inquiry,
   guidance, execution handoff, clarification, and unsupported dispatches.

8. Planner validation rejects low-confidence mutation and read-only refs on
   mutating dispatch.

9. `DefaultReadOnlyInquiryService` answers from Main Page snapshot and
   explicit safe refs; it does not mutate product or workspace state.

10. `ContractRevisionCommandService` implements command kinds:
    `record_guidance`, `resolve_ask`, `resolve_confirmation`,
    `patch_task_node`, `create_task_node`, `delete_task_node`, and
    `create_execution_task`.

11. Contract Revision command idempotency compares request hash and returns
    `idempotency_conflict` on changed payload reuse.

12. Guidance facts are persisted by in-memory and SQLite stores and can be
    consumed as execution context rules.

13. `patch_task_node` delegates to `UiCommandGateway.update_task_node`.

14. `create_task_node` appends a draft PlanTaskNode to an editable Plan.

15. `delete_task_node` tombstones an unexecuted node and rejects nodes with
    published or execution evidence.

16. `create_execution_task` appends an approved PlanTaskNode to an editable
    active Plan or creates an approved Plan when none exists.

17. `resolve_ask` and `resolve_confirmation` delegate to UI command gateway
    paths through interaction handlers when configured.

18. Runtime Input Activity can persist user input, Router trace, clarification
    question cards, and route outcome Activity through MessageStream.

19. Contract Revision Activity can persist accepted/noop command activity
    through MessageStream.

20. Audit projection can represent Runtime Input Router messages as Audit
    records and details.

21. Diagnostic bundle export can include
    `router/runtime-input.summary.json`.

22. Runtime input diagnostic summary is built from safe MessageStream context
    and excludes model input data, LLM provider data, raw logs, and raw SQL
    rows.

23. The HTTP route `/api/v1/sessions/{sessionId}/runtime-input/route` is
    implemented and validates request/session identity.

24. Frontend Main Page code has `routeRuntimeInput` adapter/controller paths.

25. PlanTaskNode lifecycle sync maps TaskBus status back to durable
    PlanTaskNode execution and rolls Plan status to `running`,
    `awaiting_acceptance`, or `failed`.

26. Plan archive command is implemented separately through
    `DefaultPlanLifecycleCommandService`.

27. Product 1.1 P0 release evidence marks the runtime input route matrix as
    implemented for P0 while keeping some beta-depth evidence as follow-up.

## Corrections Applied

1. Reframed the document from mostly baseline/product direction to current
   Product 1.1 P0 implementation facts.

2. Added exact current runtime input modes, intents, dispatch targets, and
   router ordering.

3. Added current read-only inquiry implementation and no-mutation behavior.

4. Added implemented Contract Revision command kinds and their current
   handlers.

5. Clarified Contract Revision idempotency hash-conflict semantics.

6. Added current guidance fact persistence and execution context bridge.

7. Added PlanTaskNode create/delete/execution handoff behavior, including
   tombstone semantics and execution-evidence rejection.

8. Clarified ASK and confirmation routed paths and fallbacks.

9. Added current Activity, Audit, and diagnostic evidence facts.

10. Marked broader natural-language plan editing, outcome review, and follow-up
    Plan cycles as follow-up work rather than fully general current behavior.

## Follow-up Candidates

- `docs/architecture/task-domain-ui-model-separation.md`: should be calibrated
  against current PlanView/TaskNode projection and Runtime Input refs.
- `docs/architecture/ui-backend-communication.md`: should be calibrated
  against `/runtime-input/route`, UI command idempotency, and route result
  shapes.
- `docs/plans/feature/runtime-input-and-contract-revision-program.md`: outside
  the architecture directory, but its readiness matrix now lags current
  implementation and release evidence.
- Runtime Input behavior/test follow-up: sidecar read-only inquiry acceptance
  tests currently expect explicit `mode="ask"` to answer read-only even when an
  active ASK exists, while `DefaultRuntimeInputRouter` currently prioritizes
  active ASK before ordinary mode routing.

## Validation

- `git diff --check` passed.
- Initial targeted run including
  `tests/test_read_only_inquiry_sidecar_acceptance.py` collected 174 tests:
  172 passed and 2 failed.
- Failing sidecar acceptance tests:
  - `tests/test_read_only_inquiry_sidecar_acceptance.py::test_read_only_inquiry_sidecar_acceptance_no_mutation`
  - `tests/test_read_only_inquiry_sidecar_acceptance.py::test_read_only_inquiry_sidecar_acceptance_opt_in_llm_no_mutation`
- Failure reason observed: both tests expected runtime input outcome
  `answered`, but current Router returned `dispatched` because active ASK
  routing takes precedence before read-only `mode="ask"` routing.
- Follow-up targeted run excluding those two sidecar acceptance tests passed:
  `uv run pytest tests/test_runtime_input_router.py tests/test_runtime_input_llm_router.py tests/test_contract_revision_commands.py tests/test_read_only_inquiry.py tests/test_read_only_inquiry_answer_provider.py tests/test_main_page_sidecar_config.py tests/test_plan_lifecycle.py tests/test_plan_commands.py tests/test_ui_http_transport.py tests/test_ui_query_gateway.py tests/test_session_activity_projection.py tests/test_diagnostic_bundle_export.py`
  passed: 172 tests.
