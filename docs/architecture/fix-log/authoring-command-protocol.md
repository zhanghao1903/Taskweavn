# Authoring Command Protocol Fact Calibration Fix Log

> Target document: `docs/architecture/authoring-command-protocol.md`
> Original preserved as:
> `docs/architecture/archive/original/authoring-command-protocol.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue architecture fact calibration one document at a time.
- Detected phase: P5 architecture maintenance, verified against P8/P9 code and
  tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: target architecture doc, calibrated Authoring
  Domain doc, authoring command models/service, idempotency stores,
  Collaborator API adapter, UI command gateway, Plan publisher, related plans,
  and tests.
- Found artifacts: command models, command service, authoring idempotency
  stores, SQLite authoring schema, Collaborator adapter, UI command gateway,
  UI HTTP command idempotency, Plan publisher, and direct tests.
- Missing or weak artifacts: previous document mixed recommendations with
  current implementation and did not capture durable Plan publish, declared but
  unimplemented draft operations, or idempotency-layer differences.
- Implementation allowed now: yes, docs-only.
- Prework required: verify code and tests before editing.
- Scope: preserve original, rewrite `authoring-command-protocol.md`, and add
  this fix-log.
- Acceptance criteria: active document reflects current command models,
  service behavior, idempotency semantics, Plan publish split, validation, and
  future work.
- Risks and assumptions: adjacent Runtime Input Router and Contract Revision
  docs may still need calibration in later slices.

## Maintainability Gate

- Requested change: architecture hygiene for
  `authoring-command-protocol.md`.
- Trigger: architecture fact calibration.
- Size signal: original document was 402 lines, below the 800-line threshold.
- Current risk level: low for docs-only change.
- Responsibility count: broad command-boundary document spanning authoring,
  publish, idempotency, gateway, and Plan migration behavior.
- Coupling signals: medium conceptual coupling, no production code edits.
- Refactor required first: no.
- Allowed change type: narrow docs correction.
- Proposed slice: one architecture document only.
- Acceptance criteria: original preserved; fix-log lists evidence; active doc
  marks future items as future and current facts as current.
- Validation commands: `git diff --check` plus targeted authoring, Plan,
  publish, collaborator adapter, UI command gateway, UI HTTP, and idempotency
  tests.
- Risks and assumptions: unrelated dirty files remain untouched.

## Evidence Inspected

### Code

- `src/taskweavn/task/authoring.py`
- `src/taskweavn/task/authoring_service.py`
- `src/taskweavn/task/authoring_idempotency.py`
- `src/taskweavn/task/sqlite_authoring.py`
- `src/taskweavn/task/collaborator_api.py`
- `src/taskweavn/task/plan_publisher.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/ui_command_idempotency.py`
- `src/taskweavn/server/runtime_input_router.py`

### Tests

- `tests/test_task_authoring.py`
- `tests/test_authoring_command_service.py`
- `tests/test_sqlite_authoring_stores.py`
- `tests/test_collaborator_api_adapter.py`
- `tests/test_collaborator_authoring_service.py`
- `tests/test_ui_command_gateway.py`
- `tests/test_ui_command_idempotency.py`
- `tests/test_ui_http_transport.py`
- `tests/test_plan_publisher.py`
- `tests/test_plan_store.py`
- `tests/test_plan_commands.py`

### Related Docs And Plans

- `docs/architecture/authoring-domain.md`
- `docs/plans/feature/raw-task-draft-tree-persistence.md`
- `docs/plans/feature/ask-domain-unification-batch-answer.md`
- `docs/plans/feature/plan-tasknode-contract-migration.md`

## Verified Facts

1. `MutateRawTaskCommand`, `MutateDraftTaskTreeCommand`,
   `PublishDraftTaskTreeCommand`, `AuthoringCommandBatch`,
   `AuthoringCommandResult`, and `AuthoringMessageEffect` are implemented in
   `taskweavn.task.authoring`.

2. `AuthoringCommand` currently unions RawTask mutation, DraftTaskTree
   mutation, and legacy DraftTaskTree publish commands.

3. `PublishPlanCommand` is implemented separately in
   `taskweavn.task.plan_publisher` and is not submitted through
   `AuthoringCommandBatch`.

4. `DefaultAuthoringCommandService` implements deterministic handlers for
   authoring commands.

5. RawTask operations currently handled are `create`,
   `set_intent_summary`, `record_feasibility`, `add_clarification_ask`,
   `apply_answer`, `update_constraints`, `update_assumptions`, and
   `set_status`.

6. DraftTaskTree operations currently handled are `create_tree`, `patch_node`,
   `add_node`, `attach_options`, `mark_accepted`, and `mark_ready`.

7. `mark_ready` currently returns a `mark_ready_noop` warning.

8. `remove_node` and `reorder_siblings` are declared operation kinds but are
   not handled by `DefaultAuthoringCommandService`.

9. `create_tree` can create a durable Plan from the draft tree when a
   `PlanStore` is configured.

10. Active authoring state records active RawTask/DraftTaskTree/Plan identity
    when command service dependencies are configured.

11. `PublishDraftTaskTreeCommand` requires a non-empty idempotency key.

12. Legacy draft publish requires accepted nodes and rejects empty trees,
    already-published nodes, cancelled nodes, and partial root publish.

13. Legacy draft publish optionally runs `DraftTaskTreeValidator`, calls
    `TaskPublisher.publish_draft_tree`, validates mappings, and marks draft
    nodes published.

14. `DefaultPlanPublisher` publishes durable Plans through
    `TaskPublisher.publish`, writes published refs back to PlanTaskNodes, and
    marks the Plan published.

15. UI command gateway prefers active durable Plan publish and falls back to
    legacy draft publish only when no active durable Plan path is available.

16. If active Plan publish rejects, UI command gateway does not fall back to
    legacy draft publish.

17. Authoring command idempotency replays the first result for
    `(session_id, idempotency_key)`.

18. `AuthoringCommandIdempotencyRecord` stores a request hash, but
    `DefaultAuthoringCommandService` does not compare the new request hash
    before replaying an existing record.

19. SQLite authoring command idempotency records persist in
    `authoring_command_idempotency_records`.

20. HTTP UI command response idempotency is a separate layer and returns
    `idempotency_conflict` when the same key is reused with a different
    request hash.

21. UI command gateway derives child idempotency keys for compound generation
    and authoring ask batch flows.

22. `AuthoringCommandBatch` validates session and actor equality and rejects
    best-effort publish batches.

23. Current all-or-nothing rollback snapshots RawTaskStore and DraftTaskStore
    only; it is not a full transaction across PlanStore and active state.

24. Message effects are converted to `AgentMessage` only after command
    application and only when a `MessageBus` is configured.

25. The default service maps unsupported declared draft operations to
    structured command errors through exception handling.

26. UI command gateway rejects stale authoring ask answers and can generate a
    task tree after all RawTask asks are answered.

27. Runtime Input Router delegates mutations to command services/gateways and
    is not the authoring store authority.

28. Typed authoring EventStream events are not currently implemented as a
    dedicated event stream.

## Corrections Applied

1. Reframed the document from proposed command design to current implemented
   protocol.

2. Added the durable Plan publish command boundary and clarified that it is
   separate from `AuthoringCommandBatch`.

3. Corrected DraftTaskTree operation status: `remove_node` and
   `reorder_siblings` are declared but not implemented; `mark_ready` is a
   no-op warning.

4. Clarified current RawTask and DraftTaskTree operation behavior.

5. Split idempotency into authoring command result idempotency and HTTP UI
   command response idempotency.

6. Corrected authoring idempotency semantics: first result replay, no
   request-hash conflict at the authoring service layer.

7. Added current transaction-boundary limits for all-or-nothing batches.

8. Clarified that separate actor authorization policy is not currently
   implemented in `DefaultAuthoringCommandService`.

9. Clarified Collaborator API adapter behavior, including legacy publish
   accept-then-publish flow.

10. Clarified UI command gateway behavior for RawTask readiness, stale
    authoring asks, repair, Plan publish preference, and legacy fallback.

11. Marked typed authoring EventStream events and Plan/TaskNode contract
    revision commands as future work.

## Follow-up Candidates

- `docs/architecture/contract-revision-and-execution-loops.md`: should be
  calibrated against Runtime Input Router and missing Plan/TaskNode revision
  command facts.
- `docs/architecture/task-domain-ui-model-separation.md`: should be checked
  against current PlanView, TaskNodeCardView, and legacy TaskTree projection.
- `docs/architecture/ui-backend-communication.md`: should be checked against
  UI command response idempotency and current HTTP command routes.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_task_authoring.py tests/test_authoring_command_service.py tests/test_in_memory_authoring_stores.py tests/test_sqlite_authoring_stores.py tests/test_collaborator_api_adapter.py tests/test_collaborator_authoring_service.py tests/test_ui_command_gateway.py tests/test_ui_command_idempotency.py tests/test_ui_http_transport.py tests/test_plan_publisher.py tests/test_plan_store.py tests/test_plan_commands.py`
  passed: 215 tests.
