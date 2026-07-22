# Fix Log: interaction-layer.md

> Architecture document:
> [../interaction-layer.md](../interaction-layer.md)
>
> Original:
> [interaction-layer.original.md](../archive/original/interaction-layer.original.md)
>
> Calibration date: 2026-07-10

## Workflow Gate Report

1. User request summary: calibrate architecture documents one at a time against
   current code and related documents, preserve each original, and record facts
   in a per-document fix log.
2. Detected workflow phase: P0/P5/P10 repository intake, execution architecture
   calibration, and iterative documentation maintenance, with P9 tests used as
   verification evidence.
3. Task type: documentation-only architecture fact calibration.
4. Required upstream artifacts: interaction models and stores, Task lifecycle,
   AgentLoop and runtime assembly, Main Page query/command/runtime-input paths,
   frontend interaction surfaces, accepted plans/releases, and tests.
5. Found artifacts: all required code paths, accepted implementation records,
   and targeted tests were present.
6. Missing or weak artifacts: the old document mixed an implemented historical
   baseline with Phase 3 plans, future bus implementations, obsolete slice
   sequencing, and behavior that current sidecar assembly does not provide.
7. Whether implementation is allowed now: yes. Current code provides direct
   evidence for a docs-only rewrite.
8. Prework required before implementation: preserve the original and inspect
   every relevant authority, write path, read projection, assembly path, and
   failure boundary.
9. Proposed execution scope: replace only
   `docs/architecture/interaction-layer.md`, preserve its original, and add this
   fix log. No production code changes.
10. Acceptance criteria: original matches the HEAD blob; ASK, confirmation,
    MessageBus, autonomy, Task status, UI and recovery facts are traceable;
    unsupported behavior is explicit; targeted checks pass.
11. Risks and assumptions: comments and draft designs can be stale. Only active
    call sites, models, storage schemas, accepted implementation records, and
    tests are treated as current facts.

## Original Preservation

- `interaction-layer.original.md` was copied before rewriting the current
  document.
- Original file SHA-1: `2c076a3bb88e242e46b848df6646290dac4c7390`.
- Original Git blob id: `65c5ffb0316d28b611cb0a9cc053d12ebaafcb17`.
- The copied original has the same Git blob id as
  `HEAD:docs/architecture/interaction-layer.md`.

## Sources Inspected

Architecture, product decisions, plans, releases, and UX:

- `docs/architecture/interaction-layer.md`
- `docs/architecture/task.md`
- `docs/architecture/session.md`
- `docs/architecture/context-manager.md`
- `docs/architecture/task-domain-ui-model-separation.md`
- `docs/architecture/ui-backend-communication.md`
- `docs/plans/feature/ask-domain-unification-batch-answer.md`
- `docs/plans/feature/ask-confirmation-frontend-integration.md`
- `docs/releases/message-ask-confirmation-backend.md`
- `docs/engineering/ask-lifecycle-contract.md`
- `docs/interaction-model/ask-user-interaction.md`
- `docs/ux/ask-ui-spec.md`

Interaction models, stores, and policies:

- `src/taskweavn/interaction/message.py`
- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/bus.py`
- `src/taskweavn/interaction/ask.py`
- `src/taskweavn/interaction/sqlite_ask_store.py`
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/interaction/gate.py`
- `src/taskweavn/interaction/risk.py`
- `src/taskweavn/interaction/wait.py`

Tool, Task, AgentLoop, and assembly code:

- `src/taskweavn/tools/ask.py`
- `src/taskweavn/tools/confirmation.py`
- `src/taskweavn/types/ask.py`
- `src/taskweavn/types/confirmation.py`
- `src/taskweavn/task/ask_service.py`
- `src/taskweavn/task/commands.py`
- `src/taskweavn/task/models.py`
- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`
- `src/taskweavn/core/loop.py`
- `src/taskweavn/core/session_status.py`
- `src/taskweavn/core/workspace_layout.py`
- `src/taskweavn/context/sources.py`
- `src/taskweavn/cli/main.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_agent.py`
- `src/taskweavn/server/ask_recovery.py`

UI backend and frontend:

- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/server/ui_http_commands.py`
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/runtime_input_activity.py`
- `src/taskweavn/server/ui_contract/gateway_protocols.py`
- `src/taskweavn/server/ui_contract/command_gateway.py`
- `src/taskweavn/server/ui_contract/query_snapshot_helpers.py`
- `src/taskweavn/server/ui_contract/session_activity_projection.py`
- `src/taskweavn/server/ui_contract/events.py`
- `src/taskweavn/task/projection.py`
- `frontend/src/shared/api/types.ts`
- `frontend/src/pages/main-page/interaction/AuthoringAskWorkArea.tsx`
- `frontend/src/pages/main-page/interaction/ExecutionAskDetailPanel.tsx`
- `frontend/src/pages/main-page/interaction/ConfirmationDetailPanel.tsx`
- `frontend/src/shared/components/choice/ChoiceGroup.tsx`

Tests selected for verification:

- `tests/test_agent_message.py`
- `tests/test_sqlite_message_stream.py`
- `tests/test_message_bus.py`
- `tests/test_wait_coordinator.py`
- `tests/test_interaction_autonomy.py`
- `tests/test_interaction_risk.py`
- `tests/test_interaction_risk_llm.py`
- `tests/test_autonomy_gate.py`
- `tests/test_ask_store.py`
- `tests/test_task_ask_service.py`
- `tests/test_ask_projection.py`
- `tests/test_loop_interaction.py`
- `tests/test_task_commands.py`
- `tests/test_task_bus_lifecycle.py`
- `tests/test_ask_recovery.py`
- `tests/test_ui_query_gateway.py`
- `tests/test_ui_command_gateway.py`
- `tests/test_runtime_input_router.py`
- `tests/test_session_activity_projection.py`
- `tests/test_main_page_sidecar_app.py`
- `frontend/src/pages/main-page/interaction/AuthoringAskWorkArea.test.tsx`
- `frontend/src/pages/main-page/interaction/ExecutionAskDetailPanel.test.tsx`
- `frontend/src/pages/main-page/interaction/ConfirmationDetailPanel.test.tsx`
- `frontend/src/pages/main-page/useMainPageController.test.tsx`
- `frontend/src/pages/main-page/mainPageViewModel.test.ts`
- `frontend/src/pages/main-page/ActivityOverlay.test.tsx`
- `frontend/src/pages/main-page/mainPageRuntimeInput.test.ts`

## Verified Facts

### Domain and authority boundaries

1. Current user interaction is not represented by one unified object or state
   machine.
2. Authoring ASK is owned by RawTask/authoring stores and does not pause
   TaskBus execution.
3. Execution ASK is owned by AskStore and uses TaskBus waiting linkage.
4. Execution ASK is explicitly documented in code as neither a normal
   MessageStream row nor a confirmation.
5. Confirmation has no separate store; a pending actionable AgentMessage is
   the request and a response AgentMessage is the answer.
6. Published Task records either an active execution ASK id or active
   confirmation id while waiting.
7. Optional autonomy gating also uses actionable/response AgentMessage rows but
   does not use the Published Task waiting linkage.
8. Accepted ASK unification work preserves separate authoring and execution
   authorities while sharing UI vocabulary.

### AgentMessage and MessageStream

9. AgentMessage is frozen, forbids extra fields, and has informational,
   actionable, and response message types.
10. It carries session identity, optional task identity, agent identity, parent
    relationship, body/context, actionable fields, response fields, and time.
11. The model only has a risk-assessment coercion validator; it does not enforce
    complete message-type-specific invariants.
12. Action options are UI hints rather than a model-level response enum.
13. MessageStream exposes direct, session, task, agent, pending, response, and
    thread queries.
14. List queries use created time plus insertion id for deterministic ordering.
15. `pending_actionable` anti-joins response rows and does not check
    `requires_response`.
16. SQLite validates unique message id, response parent existence, and
    actionable parent type.
17. SQLite does not validate parent/response session or task equality.
18. SQLite has no unique constraint limiting one response per actionable.
19. `response_for` treats the earliest response as canonical and leaves later
    response rows in history.
20. Task projection maps all pending actionable messages for a Task to
    confirmation views.

### MessageBus

21. InProcessMessageBus is the only MessageBus implementation in the repository.
22. It serializes publish and waits with one threading.Condition.
23. Publish persists before fan-out and notify.
24. Response waits re-query SQLite and support infinite, timed, and zero-timeout
    operation.
25. A closed bus returns no response when no persisted response exists and
    wakes waiters/subscriptions.
26. Subscriptions only deliver future publishes; replay uses MessageStream.
27. Subscription deques are unbounded.
28. The supported writer path is MessageBus, but `_insert` remains callable and
    single-writer ownership is not an enforced language boundary.
29. Cross-process SqliteMessageBus and RedisMessageBus are not implemented.

### Execution ASK

30. AskRequest supports pending, answered, deferred, cancelled, and expired
    states.
31. Blocking ASK requires task_id.
32. ASK supports free-text, single-choice, multi-choice, and boolean answer
    policies.
33. One AskRequest can contain subquestions while one AskAnswer closes the ASK.
34. Attachments are fixed unsupported and non-empty answer attachments fail
    validation.
35. AskUserTool first creates a durable AskRequest and then calls
    TaskBus.wait_for_user.
36. TaskBus only lets a running Task enter waiting_for_user.
37. AgentLoop recognizes a successful AskUserObservation as blocking and ends
    the current run with stop_reason waiting_for_user.
38. ASK create and Task wait are separate database writes with no cross-store
    transaction.
39. AskStore validates target identity, pending state, option ids, answer type,
    option count, and free-text policy.
40. SqliteAskStore atomically persists ASK state, its single answer row, and
    optional ASK command idempotency within its own database.
41. ASK command idempotency is scoped by session id plus idempotency key.
42. DefaultTaskAskCommandService writes AskStore before Task lifecycle changes.
43. A first accepted answer resumes a matching waiting Task to pending.
44. Accepted defer/cancel fails a matching waiting Task.
45. Replayed ASK commands do not repeat Task lifecycle mutation.
46. ASK Store and TaskBus mutation are not one transaction; accepted ASK state
    remains when resume/fail cannot complete.
47. HTTP ASK answer requests execution dispatch with reason ask_answer_resume
    after command acceptance.
48. Dispatch failure does not roll back the ASK answer.
49. AskContextSource supplies pending/answered ASK facts to a subsequent Main
    Page AgentLoop context.
50. Snapshot recovery can repair answered blocking ASK Task state and request
    dispatch without failing the snapshot read.

### Confirmation

51. RequestConfirmationTool publishes an actionable message before moving the
    running Task to waiting_for_user.
52. A successful RequestConfirmationObservation stops the current AgentLoop run
    as waiting_for_user.
53. Default confirmation options are confirm and reject; approve_session can be
    added.
54. approve_session is recorded but does not bypass later confirmations.
55. Confirmation message publish and Task wait are separate writes without a
    cross-store transaction.
56. resolve_confirmation validates existence, session, actionable type,
    unresolved state, and non-empty value.
57. It does not validate response value against action options.
58. It does not treat reject as a Task failure or skip; any non-empty value can
    resume the matching Task.
59. The response message is published before Task resume is attempted.
60. Task resume returns the waiting Task to pending.
61. The direct confirmation HTTP route does not invoke the execution dispatch
    helper used by ASK answer.
62. Main Page Context Manager has no MessageStream/confirmation response source;
    confirmation response_value is not directly injected into the next run.
63. There is no confirmation counterpart to DefaultAskRecoveryService.
64. Different concurrent command ids can pass the unresolved pre-check before
    separate response inserts because parent uniqueness is absent.

### Main Page and optional autonomy

65. Main Page registers explicit ask_user and request_confirmation tools when
    their dependencies and task id are present.
66. Main Page constructs AgentLoop without gate, WaitCoordinator, or AgentLoop
    bus fields.
67. Generic CLI autonomy is opt-in through `--autonomy` and is off by default.
68. CLI autonomy constructs SqliteMessageStream, InProcessMessageBus,
    RiskAssessor, AutonomyGate, WaitCoordinator, and an stdin responder thread.
69. CLI message storage defaults to log-dir/messages.sqlite unless explicitly
    set, not automatically to workspace `.plato/messages.sqlite`.
70. AutonomyGate is pure and returns PROCEED or EMIT; it does not publish or
    block itself.
71. Risk scores are bounded and dynamic risk cannot undercut baseline risk.
72. Baseline-only, LLM, and composite assessors are implemented.
73. LLM risk assessor failures fall back to baseline.
74. No confidence provider is passed by the CLI assembly, so on_uncertainty
    defaults to confidence 1.0 and proceeds.
75. `proceed_confident` currently selects the first option just like
    `proceed_default`.
76. WaitCoordinator timeout self-decisions publish only an optional
    informational notice, not a response row.
77. Such timeout actionables therefore remain pending in MessageStream.
78. Async autonomy pending actions live in AgentLoop memory, are polled on later
    steps, and are discarded from memory when the run ends unresolved.
79. AgentLoop treats a fixed token set as rejection; any other response proceeds.

### Task, Session, UI, and events

80. TaskDomain requires exactly one ASK or confirmation linkage while
    waiting_for_user and none outside that state.
81. ASK/confirmation resume returns a Task to pending, after which a dispatcher
    must claim it.
82. The core derive_session_status helper checks archived, pending actionable,
    last finish observation, then active.
83. Production code does not call that core helper; its direct call sites are
    tests.
84. Main Page uses a separate richer status derivation that includes active ASK,
    authoring ASK, confirmations, TaskTree, stored Session state, and messages.
85. Task, core Session, and UI use waiting_for_user, awaiting_user, and
    waiting_user respectively.
86. Snapshot exposes messages, pending confirmations, planning/pending/active
    ASK, Task status, and other projected state.
87. Dedicated ASK list/detail and answer/defer/cancel routes exist.
88. Runtime Input Router prioritizes active execution ASK, then active
    confirmation, before its other routing categories.
89. Frontend contains AuthoringAskWorkArea, ExecutionAskDetailPanel,
    ConfirmationDetailPanel, and ChoiceGroup implementations.
90. Frontend commands keep local pending/error state and converge through
    snapshot/refetch rather than treating command acceptance as final truth.
91. Session Activity is a projection assembled from message, ASK, confirmation,
    Plan, Task, result, file, and Runtime Input facts; it is not Audit.
92. Backend UiEventType declares ASK event types and helper constructors.
93. No production source calls those ASK event helpers.
94. Frontend UiEventType does not contain ASK event types.
95. ASK live convergence therefore currently relies on commands and
    snapshot/refetch, not a complete ASK event stream.

## Stale or Corrected Claims

1. The old document presented a single Phase 3 interaction architecture as the
   current layer. Current Main Page behavior separates authoring ASK, execution
   ASK, confirmation, and optional autonomy gating.
2. The old principle that MessageBus is not a control-flow primitive was too
   absolute. CLI autonomy uses `wait_for_response` as a blocking/non-blocking
   action gate, while Main Page uses TaskBus lifecycle instead.
3. The old document said every action passes AutonomyGate as if universal.
   Main Page AgentLoop does not wire a gate.
4. The old cross-process SqliteMessageBus and RedisMessageBus discussion was a
   future design, not implemented code.
5. The old failure table implied restart reconstructs and resumes pending gate
   waits. CLI async pending action state is memory-only and no such gate recovery
   is wired.
6. The old failure table implied a UNIQUE constraint decides response races.
   Only message_id is unique; parent_message_id is not.
7. The old write rule described MessageBus as impossible to bypass. `_insert`
   is private by convention but callable.
8. The old pending semantics did not state that `requires_response` is ignored.
9. The old message model discussion did not state that message-type-specific
   invariants are mostly unenforced at model construction.
10. The old timeout story could imply an automatic response is persisted.
    Current timeout paths write an informational notice only.
11. The old `proceed_confident` wording implied confidence-based behavior. It
    currently selects the first option.
12. The old collaborative preset wording implied uncertainty gating works by
    default. CLI assembly supplies no ConfidenceProvider.
13. The old session status section described the core derivation as the live UI
    rule. Main Page production uses a different helper.
14. The old phase slice table included obsolete plans such as polling bus,
    prompt-toolkit commands, RAG, and session resume behavior as architecture
    trajectory. They are not current interaction facts.
15. The old document did not cover durable execution ASK, AskStore answer
    validation, TaskBus ASK linkage, or ASK recovery.
16. The old document did not cover explicit request_confirmation tooling and
    confirmation Task linkage.
17. The old document did not distinguish authoring ASK from execution ASK.
18. The old document did not state the cross-store non-atomic boundaries around
    ASK/confirmation creation and resolution.
19. The old document did not state that confirmation values are not option
    validated and reject still resumes the Task.
20. The old document did not state that confirmation response values are not a
    current Context Manager source.
21. The old document did not state that direct confirmation response lacks the
    ASK answer path's dispatch trigger.
22. The old document did not cover Runtime Input routing, Activity projection,
    current frontend panels, or ASK event-contract gaps.
23. Historical status, phase sequencing, open questions, and future acceptance
    criteria were removed from the current fact document and preserved only in
    the original copy.

## New Document Decisions

1. Organize the architecture around authority boundaries and actual runtime
   assembly instead of historical implementation phases.
2. Keep authoring ASK, execution ASK, confirmation, and autonomy gate distinct.
3. Document MessageStream constraints from the real SQLite schema and queries.
4. Treat single-writer ownership as an API convention, not an enforced process
   boundary.
5. Describe Main Page explicit-tool control flow separately from CLI autonomy.
6. State cross-store ordering and compensation behavior at every ASK and
   confirmation transition.
7. Separate durable facts from in-process waits, subscriptions, and pending
   action memory.
8. Record status vocabulary differences across Task, core Session, and UI.
9. Treat command response plus snapshot/refetch as the current ASK convergence
   mechanism until event production and frontend event types close the gap.
10. Put unsupported or incomplete semantics in a dedicated current-limits list
    rather than leaving them as implicit assumptions.

## Validation Log

Validation commands selected for this rewrite:

```bash
git diff --check
uv run pytest tests/test_agent_message.py tests/test_sqlite_message_stream.py tests/test_message_bus.py tests/test_wait_coordinator.py tests/test_interaction_autonomy.py tests/test_interaction_risk.py tests/test_interaction_risk_llm.py tests/test_autonomy_gate.py tests/test_ask_store.py tests/test_task_ask_service.py tests/test_ask_projection.py tests/test_loop_interaction.py tests/test_task_commands.py tests/test_task_bus_lifecycle.py tests/test_ask_recovery.py tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py tests/test_runtime_input_router.py tests/test_session_activity_projection.py tests/test_main_page_sidecar_app.py
# Run from frontend/.
npm test -- src/pages/main-page/interaction/AuthoringAskWorkArea.test.tsx src/pages/main-page/interaction/ExecutionAskDetailPanel.test.tsx src/pages/main-page/interaction/ConfirmationDetailPanel.test.tsx src/pages/main-page/useMainPageController.test.tsx src/pages/main-page/mainPageViewModel.test.ts src/pages/main-page/ActivityOverlay.test.tsx src/pages/main-page/mainPageRuntimeInput.test.ts
```

Results:

- `git diff --check`: passed.
- Backend pytest: 336 passed.
- Frontend Vitest: 7 test files passed, 80 tests passed.
