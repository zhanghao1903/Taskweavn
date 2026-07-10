# Collaborator Agent And Task Authoring Fact Calibration Fix Log

> Target document: `docs/architecture/collaborator-agent-task-authoring.md`
> Original preserved as:
> `docs/architecture/collaborator-agent-task-authoring.original.md`
> Calibration date: 2026-07-10

## Workflow Gate

- User request: continue architecture fact calibration one document at a time.
- Detected phase: P5 architecture maintenance, verified against P8/P9 code and
  tests.
- Task type: docs-only architecture fact correction.
- Required upstream artifacts: target architecture doc, related authoring
  plans, Authoring Domain and Command Protocol docs, Collaborator authoring
  implementation, Plan migration implementation, workspace-informed authoring
  implementation, UI command gateway, and tests.
- Found artifacts: authoring contracts, command service, context builder,
  Collaborator service/API adapter/profile runner, workspace context source,
  authoring stores, Plan publisher/store wiring, sidecar assembly, command
  gateway, and related tests.
- Missing or weak artifacts: previous document mixed current facts with older
  implementation slices and future operations. It also treated some deferred
  surfaces as if they were the current public service API.
- Implementation allowed now: yes, docs-only.
- Prework required: verify current code and tests before editing.
- Scope: preserve original, rewrite current architecture document, and add this
  fix-log.
- Acceptance criteria: current implemented facts are explicit; partial and
  future items are clearly marked; no unsupported claims remain as current
  facts.
- Risks and assumptions: adjacent architecture docs may still be stale and will
  be calibrated in later slices.

## Maintainability Gate

- Requested change: architecture hygiene for
  `collaborator-agent-task-authoring.md`.
- Trigger: architecture fact calibration.
- Size signal: original document was 908 lines, above the 800-line review
  threshold.
- Current risk level: medium for documentation complexity, low for production
  behavior because this slice changes docs only.
- Responsibility count: broad architecture document covering Collaborator,
  Authoring Domain, command services, stores, UI command gateway, workspace
  context, and Plan migration.
- Coupling signals: high conceptual coupling across authoring, runtime input,
  Plan migration, workspace context, and publish boundaries.
- Refactor required first: no code refactor required for this docs-only slice.
- Allowed change type: narrow docs correction.
- Proposed slice: one architecture document only.
- Acceptance criteria: original preserved; fix-log lists evidence; active doc
  distinguishes implemented, partial, and future facts.
- Validation commands: `git diff --check` plus targeted authoring,
  collaborator, workspace-context, Plan/publish, and sidecar tests.
- Risks and assumptions: test failures outside the calibrated boundary should
  be recorded separately instead of hidden.

## Evidence Inspected

### Code

- `src/taskweavn/task/authoring.py`
- `src/taskweavn/task/authoring_service.py`
- `src/taskweavn/task/authoring_context.py`
- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/task/collaborator_api.py`
- `src/taskweavn/task/collaborator_loop.py`
- `src/taskweavn/task/collaborator_profile_runner.py`
- `src/taskweavn/task/collaborator_workspace_context.py`
- `src/taskweavn/task/authoring_evidence.py`
- `src/taskweavn/task/authoring_idempotency.py`
- `src/taskweavn/task/stores.py`
- `src/taskweavn/task/sqlite_authoring.py`
- `src/taskweavn/task/plan_from_draft.py`
- `src/taskweavn/task/plan_publisher.py`
- `src/taskweavn/task/publisher.py`
- `src/taskweavn/task/publisher_input.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`

### Tests

- `tests/test_task_authoring.py`
- `tests/test_authoring_command_service.py`
- `tests/test_authoring_context_builder.py`
- `tests/test_collaborator_authoring_service.py`
- `tests/test_collaborator_api_adapter.py`
- `tests/test_collaborator_authoring_loop_contract.py`
- `tests/test_collaborator_workspace_context.py`
- `tests/test_authoring_evidence_contract.py`
- `tests/test_in_memory_authoring_stores.py`
- `tests/test_sqlite_authoring_stores.py`
- `tests/test_collaborator_sidecar_acceptance.py`
- `tests/test_task_publisher.py`
- `tests/test_task_publish_service.py`
- `tests/test_task_publisher_input.py`

### Related Docs And Plans

- `docs/plans/feature/collaborator-agent-task-authoring.md`
- `docs/plans/feature/collaborator-workspace-informed-authoring.md`
- `docs/plans/feature/plan-tasknode-contract-migration.md`
- `docs/architecture/authoring-domain.md`
- `docs/architecture/authoring-command-protocol.md`
- `docs/architecture/tool-capability-layer.md`
- `docs/architecture/workspace-communication-protocol.md`

## Verified Facts

1. `CollaboratorAgentTemplate` is implemented with
   `template_id="system.collaborator"`, `capability="task_authoring"`,
   `command_protocol="authoring.v1"`, and empty `llm_visible_tool_pools`.

2. `DefaultCollaboratorAuthoringService` currently exposes
   `create_raw_task_from_message`, `generate_task_tree`, and
   `refine_task_node`.

3. `DefaultCollaboratorAuthoringService` maps LLM/profile results into
   `MutateRawTaskCommand` or `MutateDraftTaskTreeCommand` and submits them
   through `AuthoringCommandService`.

4. The current natural-language service protocol does not expose separate
   `assess_raw_task`, `answer_raw_task_ask`, `propose_task_options`,
   `validate_task_tree`, or direct publish methods.

5. `DefaultCollaboratorApiAdapter` is the stable UI/server adapter for session
   start, session message append, RawTask ask answers, task tree generation,
   draft task message append, and task tree publish.

6. `RawTask`, `RawTaskAsk`, `RawTaskAnswer`, `FeasibilityReport`,
   authoring commands, authoring results, `CapabilityDescriptor`,
   `AuthoringContext`, draft proposal models, Plan proposal models, option
   models, and `DraftTaskTreeValidator` are implemented.

7. `PlanProposal` is the current flat Product 1.1 LLM contract. It validates
   task ordering and dependencies and rejects hierarchy/role fields.

8. Legacy `DraftTaskTreeProposal` remains accepted for compatibility, but
   Collaborator mapping flattens nested draft proposals before command
   submission.

9. `DefaultAuthoringCommandService` implements RawTask create/update,
   feasibility recording, ask creation, answer application, constraint and
   assumption updates, DraftTaskTree create/patch/add/options/accept, and
   publish through `TaskPublisher`.

10. `mark_ready` is a current no-op warning. `remove_node` and
    `reorder_siblings` are declared operation names but are not implemented by
    the current command service.

11. In-memory and SQLite stores exist for RawTask and DraftTaskTree. SQLite
    stores also implement active authoring state and command idempotency.

12. The main sidecar runtime uses SQLite authoring stores by default when store
    dependencies are not injected.

13. Authoring command idempotency is implemented by session and idempotency key.
    Reuse returns the first cached result instead of duplicating side effects.

14. `DefaultAuthoringContextBuilder` is read-only and builds session or draft
    task context from RawTaskStore, DraftTaskStore, MessageStream, and
    CapabilityCatalog.

15. `CollaboratorAuthoringProfile` allows read/search workspace, ask, and
    finish authoring tools. The profile declares write/shell/command execution
    tools as forbidden.

16. `CollaboratorAuthoringProfileRunner` exposes context tools only when a
    workspace context source is configured and enforces a bounded context-step
    loop.

17. `CollaboratorAuthoringLoopResult` includes `waiting_for_context`, but the
    current default runner/service path does not expose a complete user-facing
    waiting-for-context flow.

18. `LocalCollaboratorWorkspaceContextSource` implements bounded workspace
    read/search with `workspace://current` labels, protected metadata checks,
    UTF-8 and size bounds, evidence refs, and absolute path redaction.

19. `AuthoringEvidenceRecord` requires safe workspace labels and records
    allowed, denied, and omitted decisions.

20. UI command gateway routes global input, task tree generation, authoring ask
    batch answers, draft task input, and publish through Collaborator or related
    command services.

21. UI publish prefers active durable Plan publishing through `PlanPublisher`
    and falls back to legacy DraftTaskTree publishing if no durable Plan path is
    available.

22. `DefaultAuthoringCommandService` can create durable Plans from draft output
    when a `PlanStore` is configured.

23. The current local default capability catalog is static:
    `general`, `writing`, `coding`, `testing`, and `research`.

## Corrections Applied

1. Reframed the document from an implementation-slice plan into a current fact
   baseline.

2. Replaced future-style `CollaboratorAuthoringService` method lists with the
   currently implemented natural-language service API and the separate
   Collaborator API adapter surface.

3. Added current Product 1.1 Plan proposal and durable Plan publish facts.

4. Corrected the old "SQLite deferred" implication: SQLite RawTask,
   DraftTaskTree, active authoring state, and idempotency stores are now
   implemented and wired by default in the sidecar runtime.

5. Corrected DraftTaskTree operation status: `mark_ready` is a no-op warning,
   while `remove_node` and `reorder_siblings` are declared but not handled.

6. Added workspace-informed authoring facts for read/search tools, evidence
   records, safe labels, protected metadata, and sidecar acceptance coverage.

7. Marked `waiting_for_context` as a model/tested shape rather than a complete
   current user-facing flow.

8. Clarified that Collaborator does not mount write/shell/execution tools by
   default and does not directly mutate workspace files.

9. Clarified that UI publish currently prefers active durable Plan publish and
   only falls back to legacy DraftTaskTree publish.

## Follow-up Candidates

- `docs/architecture/authoring-domain.md`: should be checked against current
  Plan/TaskNode migration and active state invariants.
- `docs/architecture/authoring-command-protocol.md`: should be checked for the
  partial operation set and current idempotency/store behavior.
- `docs/architecture/contract-revision-and-execution-loops.md`: should be
  checked for Runtime Input Router, read-only inquiry, and Plan/TaskNode
  command facts.
- `docs/architecture/README.md`: should be aligned after the individual
  architecture docs are calibrated.

## Validation

- `git diff --check` passed.
- `uv run pytest tests/test_task_authoring.py tests/test_authoring_command_service.py tests/test_authoring_context_builder.py tests/test_collaborator_authoring_service.py tests/test_collaborator_api_adapter.py tests/test_collaborator_authoring_loop_contract.py tests/test_collaborator_workspace_context.py tests/test_authoring_evidence_contract.py tests/test_in_memory_authoring_stores.py tests/test_sqlite_authoring_stores.py tests/test_collaborator_sidecar_acceptance.py tests/test_task_publisher.py tests/test_task_publish_service.py tests/test_task_publisher_input.py` passed: 193 tests.
