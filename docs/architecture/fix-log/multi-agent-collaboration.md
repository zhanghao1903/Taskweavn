# Multi-Agent Collaboration Architecture Fact Calibration Log

> Source document: `docs/architecture/multi-agent-collaboration.md`
> Preserved original:
> `docs/architecture/multi-agent-collaboration.original.md`
> Calibration date: 2026-07-10
> Scope: current multi-Agent-related runtime, authoring, routing, interaction,
> Execution Plane, UI, and accepted future assignment direction.

## 1. Workflow Gate Report

- User request summary: calibrate each architecture document against related
  documentation, code, and tests; preserve the original; create a per-document
  fact log; replace the active document with a fact-based version.
- Detected workflow phase: P5 architecture fact maintenance, with P7/P8 code
  evidence and P9 test evidence.
- Task type: documentation-only architecture correction.
- Required upstream artifacts:
  - existing Chinese multi-Agent architecture document;
  - current TaskBus and execution implementation;
  - current Collaborator, Runtime Input Router, Inquiry, interaction, and
    Execution Plane implementations;
  - accepted routing ADRs;
  - frontend contract and targeted tests.
- Found artifacts: all required code, ADR, neighboring architecture, UI
  contract, and test sources were present.
- Missing or weak artifacts:
  - no implemented public Agent protocol;
  - no Agent Manager or dynamic assignment implementation;
  - no current agent-to-agent delegation protocol;
  - the existing document was primarily a target concept and did not provide a
    current implementation evidence map.
- Implementation allowed now: yes, for a narrow documentation-only correction.
- Prework required: identify which names denote real execution Agents versus
  service roles or metadata, and separate current code from accepted future
  direction.
- Execution scope: preserve the old file, rewrite the Chinese document, and add
  this fix log. No production code or API contract changes.
- Acceptance criteria:
  - preserved original matches the repository version before calibration;
  - current fixed-route execution is described from assembly through TaskBus;
  - Collaborator, Router, Inquiry, LLM roles, ExecutionEnv, and Orchestrator are
    classified by their actual runtime authority;
  - absent graph/runtime/assignment/UI features are not presented as current;
  - ADR-0011/0012 are marked as accepted future direction;
  - targeted tests and `git diff --check` pass.
- Risks and assumptions:
  - names containing “Agent” can look like runtime instances even when they are
    profile labels or metadata;
  - DTO fields for leases and future statuses can be mistaken for implemented
    services;
  - accepted ADR text can be mistaken for shipped behavior;
  - the English counterpart is a separate calibration target and is not changed
    by this log.

## 2. Original Preservation

- Original path: `docs/architecture/multi-agent-collaboration.md`
- Preserved path:
  `docs/architecture/multi-agent-collaboration.original.md`
- Original Git blob:
  `46b6bf5afe84b93c92998b8a5c3aec18b68ac2b9`
- The pre-calibration working-tree hash matched the `HEAD` blob.
- The original had 512 lines and identified itself as a historical architecture
  concept reference, but most body sections still described target concepts in
  present tense.

## 3. Evidence Inspected

### 3.1 Execution And TaskBus

- `src/taskweavn/task/execution.py`
  - `DEFAULT_FIXED_ROUTE_AGENT_ID` is `default_agent`.
  - `FixedRouteTaskExecutor` explicitly states that the current bridge has no
    Router, Agent Manager, assignment field, or reassignment UI.
  - It selects an eligible pending Task, calls `claim_next()` with the Task's
    `required_capability`, invokes one resident Default Agent, and commits
    complete/fail/wait outcomes.
  - `FixedRouteExecutionDispatcher` has one worker, coalesces Session triggers,
    and does not retain AgentLoop instances between Tasks.
  - `AgentLoopResidentDefaultAgent` uses a task-scoped runner factory and maps
    `LoopResult` to `TaskRunResult`.
- `src/taskweavn/task/models.py`
  - `TaskDomain` has `required_capability`, optional `dispatch_constraints`, and
    `claimed_by`; it has no assignment fields.
  - `TaskDispatchConstraints` is documented as future dispatch intent that does
    not change current claim semantics.
- `src/taskweavn/task/bus.py`
  - TaskBus owns Published Task lifecycle transitions.
  - In-memory claim filters by Session, pending status, exact capability, and
    parent readiness, then writes `running`, `claimed_by`, and `started_at`.
- `src/taskweavn/task/sqlite_bus.py`
  - SQLite claim applies the same capability/readiness rules.
  - Synchronization is an instance-local `RLock`, not a distributed lease.
- `src/taskweavn/server/main_page.py`
  - Workspace runtime assembly creates the Default Agent, fixed-route
    dispatcher, local env registry, and embedded Execution Plane service.
- `src/taskweavn/server/main_page_agent.py`
  - Builds the resident adapter and task-scoped `_SessionAgentLoopRunner`.
  - Main Page uses explicit ASK/confirmation tools and does not assemble an
    `AutonomyGate` for all ordinary actions.

### 3.2 Collaborator, Router, And Inquiry

- `src/taskweavn/task/collaborator.py`
  - `CollaboratorAgentTemplate` is metadata for the built-in authoring role.
  - The default template has no LLM-visible tool pools.
  - `DefaultCollaboratorAuthoringService` submits proposals through
    `AuthoringCommandService`.
- `src/taskweavn/task/collaborator_loop.py`
  - Allowed profile tools are bounded read/search/ask/finish operations.
  - Workspace writes and shell/command execution are forbidden.
- `src/taskweavn/task/collaborator_profile_runner.py`
  - Implements the bounded workspace-informed authoring loop.
- `src/taskweavn/server/runtime_input_router.py`
  - Routes user input to inquiry, contract commands, ASK/confirmation, selected
    Task controls, or execution handoff.
  - It does not observe or assign an execution Agent pool.
- `src/taskweavn/server/runtime_input_llm_router.py`
  - Optional LLM planning produces a route proposal; deterministic handlers
    still own state-changing commands.
- `src/taskweavn/server/read_only_inquiry.py`
- `src/taskweavn/server/read_only_inquiry_answer_provider.py`
  - Inquiry is bounded and read-only; separate LLM identity does not make it a
    TaskBus execution worker.
- `src/taskweavn/llm/agent_config.py`
  - Six Agent LLM roles configure model profiles only.

### 3.3 Interaction And Orchestration

- `src/taskweavn/interaction/message.py`
  - Current message types are informational, actionable, and response.
  - `agent_id` is a string label, not a validated Agent registry reference.
- `src/taskweavn/interaction/sqlite_message_stream.py`
  - Persists the user-facing Session message stream.
- `src/taskweavn/interaction/bus.py`
  - `InProcessMessageBus` is the only implementation.
  - Subscriptions deliver future publishes; durable history is read separately.
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/interaction/gate.py`
  - Autonomy behavior and gate primitives exist, but that does not establish
    graph-node autonomy configuration in Main Page.
- `src/taskweavn/orchestration/protocol.py`
  - Only an `Orchestrator` Protocol and `NullOrchestrator` exist.
  - Repository search found no caller outside module exports.

### 3.4 Execution Plane

- `src/taskweavn/execution_plane/models.py`
  - Service DTOs include future-looking env, lease, and status vocabulary.
- `src/taskweavn/execution_plane/env_registry.py`
  - Current registry is in-memory and selects a compatible local env.
- `src/taskweavn/execution_plane/embedded_service.py`
  - Validates idempotency and local capability compatibility.
  - Maps ordinary requests into TaskBus and supports selected local runtime
    handlers.
- `src/taskweavn/server/computer_use_runtime.py`
  - Sidecar assembly advertises local execution capabilities and optional
    computer-use support.
- `src/taskweavn/server/ui_http_execution_plane.py`
  - Provides local Task API routes; no remote worker registration/heartbeat/
    lease endpoint exists.

### 3.5 UI Contract

- `frontend/src/shared/api/types.ts`
  - `TaskNodeCardView` exposes task status, readiness, execution, confirmation,
    result/error, interruption, badges, permissions, and actions.
  - It has no assignment, `claimed_by`, Agent identity, or Agent health field.
- `frontend/src/pages/main-page/TaskNodeCard.tsx`
- `frontend/src/pages/main-page/MainPageDetailPanel.tsx`
  - Current task actions are status-centric, including stop and retry.
  - No assignment or reassignment control exists.
- Repository search found no current Agent graph editor, orchestration draft,
  constraint profile, or multi-Agent node/edge UI implementation.

### 3.6 Decisions And Neighboring Architecture

- `docs/decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md`
  - Accepts Routing Agent assignment and cooperative interruption as future
    direction; explicitly preserves fixed-route Product 1.0 scope.
- `docs/decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md`
  - Accepts a future TaskBus-centered Router/Agent Manager convergence model;
    its scope note says the model is not a Product 1.0 implementation
    requirement.
- `docs/architecture/overview.md`
- `docs/architecture/agent.md`
- `docs/architecture/task.md`
- `docs/architecture/bus.md`
- `docs/architecture/interaction-layer.md`
- `docs/architecture/collaborator-agent-task-authoring.md`
- `docs/architecture/taskbus-service-multi-execution-env.md`
- `docs/architecture/tool-capability-layer.md`
  - These calibrated documents establish the neighboring current boundaries.

## 4. Verified Current Facts

1. The only general Published Task execution route is the fixed Default Agent
   path.
2. The resident adapter is stable across dispatches, but the AgentLoop runner is
   task-scoped.
3. Dispatcher execution is serialized through one worker per assembled
   workspace runtime and duplicate Session triggers are coalesced.
4. TaskBus itself does not enforce a global one-running-Task-per-Session lock.
5. Claim matching uses exact `required_capability` plus parent readiness.
6. Current claim ignores `TaskDispatchConstraints` agent preference fields.
7. `claimed_by` is written after claim; it is not pre-claim assignment.
8. No Task assignment fields, command, index, state, or assigned-only claim API
   exist.
9. No Agent Manager, generic AgentPool, dynamic runtime registry, or worker
   lifecycle controller exists.
10. Collaborator is a real authoring service, but it is not a Published Task
    execution worker.
11. Collaborator mutations are command-backed and workspace context access is
    read/search only.
12. Runtime Input Router handles user input routing, not Task-to-Agent routing.
13. Read-only Inquiry is a bounded answer service, not a workspace-writing Agent.
14. Agent LLM roles select model profiles and do not create Agent instances.
15. `Orchestrator` is an unused placeholder with no concrete implementation.
16. MessageStream is a user interaction/projection surface, not an Agent mailbox
    protocol.
17. Explicit ASK and confirmation can place a Task in `waiting_for_user`; current
    execution is not universally non-blocking.
18. Main Page does not apply `AutonomyGate` to every normal tool action.
19. Current capability catalogs validate authoring/publish input; they are not a
    dynamic execution Agent catalog.
20. Default Agent tools are assembled as concrete tools, not selected from the
    old document's global ToolRegistry abstraction.
21. Execution Plane performs local env compatibility checks and provides a
    service-shaped Task API.
22. ExecutionEnv and TaskLease DTO vocabulary does not imply remote worker,
    lease, or heartbeat services are implemented.
23. Ordinary Execution Plane requests still use TaskBus and fixed-route
    execution.
24. Selected local runtime handlers are task-type extensions, not public Agents.
25. Main Page UI has no Agent graph, assignment, reassignment, pool, health, or
    parallel branch surface.
26. There is no current agent-to-agent delegation, handoff, result aggregation,
    or child-run protocol.
27. There is no current multi-writer workspace conflict/merge protocol.
28. ADR-0011/0012 describe accepted future dynamic routing, not shipped behavior.

## 5. Corrections Applied

| Original claim or framing | Correction |
|---|---|
| Planner, Executor, and Auditor form a current execution layer | Replaced with the actual fixed Default Agent route and classified other role names separately. |
| Message flow replaces interruption | Recorded that explicit ASK/confirmation transitions Task to `waiting_for_user` and ends the current run. |
| MessageStream coordinates all Agents | Restricted MessageStream to user-facing messages, responses, and projection; documented missing agent-to-agent protocol. |
| Every Agent operation passes an AutonomyGate | Limited this to the optional generic/CLI path and stated Main Page assembly behavior. |
| Highest autonomy makes all actionable messages non-blocking | Removed as a current guarantee. |
| Orchestration Designer generates Agent collaboration graphs | Marked Designer, drafts, node/edge models, and graph runtime as unimplemented. |
| ConstraintProfile guarantees generated graph validity | Marked the model and validator as absent from current code. |
| Global ToolRegistry assigns compatible tools to Agent nodes | Replaced with concrete Default Agent tool assembly and static authoring catalogs. |
| Preset layers and graph UI are current | Recorded that no such frontend contract or controls exist. |
| Current v1 runs a guarded Planner/Executor/Auditor topology | Removed; the current route has one general execution Agent. |
| Agent names imply runtime instances | Added a role map distinguishing services, metadata, LLM profiles, handlers, and TaskBus workers. |
| ExecutionEnv models imply a multi-environment worker system | Separated local compatibility registry facts from future remote lease/heartbeat work. |
| Accepted dynamic routing architecture is current | Moved ADR-0011/0012 content into an explicitly future section. |

## 6. Targeted Test Evidence

The calibration selected these suites because they exercise the described
boundaries:

- `tests/test_fixed_route_task_executor.py`
  - fixed claim/run/result flow, task-scoped runner factory, dispatcher drain,
    duplicate trigger coalescing, waiting and failure behavior.
- `tests/test_task_bus_lifecycle.py`
  - in-memory lifecycle, parent readiness, ASK/confirmation wait/resume, retry,
    and cooperative interruption.
- `tests/test_sqlite_task_bus.py`
  - SQLite persistence and matching lifecycle semantics.
- `tests/test_collaborator_authoring_service.py`
  - proposal-to-command flow and bounded workspace read/search behavior.
- `tests/test_collaborator_authoring_loop_contract.py`
  - allowed authoring profile tools and status-specific results.
- `tests/test_runtime_input_router.py`
  - inquiry, guidance, ASK/confirmation, selected Task controls, and execution
    handoff routing.
- `tests/test_execution_plane_service.py`
  - local task publish, idempotency, env compatibility, TaskBus result mapping,
    and SQLite store recovery.
- `tests/test_main_page_sidecar_app.py`
  - real sidecar assembly, fixed-route dispatch, Default Agent, ASK,
    confirmation, interruption recovery, and local Task API integration.

## 7. Validation Record

Validation completed on 2026-07-10:

- Original preservation:
  - `git hash-object docs/architecture/multi-agent-collaboration.original.md`
    returned `46b6bf5afe84b93c92998b8a5c3aec18b68ac2b9`.
  - `git rev-parse HEAD:docs/architecture/multi-agent-collaboration.md`
    returned the same blob id.
- Targeted backend tests:
  - `uv run pytest -q tests/test_fixed_route_task_executor.py
    tests/test_task_bus_lifecycle.py tests/test_sqlite_task_bus.py
    tests/test_collaborator_authoring_service.py
    tests/test_collaborator_authoring_loop_contract.py
    tests/test_runtime_input_router.py tests/test_execution_plane_service.py
    tests/test_main_page_sidecar_app.py`
  - Result: `162 passed in 17.11s`.
- Document checks:
  - relative architecture and ADR targets referenced by the calibrated document
    exist;
  - no source or frontend files were changed for this calibration;
  - `git diff --check` passed for the three document artifacts.

## 8. Remaining Follow-Up

- Calibrate `multi-agent-collaboration_en.md` independently rather than assuming
  it is a line-for-line translation.
- Keep dynamic routing language aligned with future code only when assignment
  model/store/commands, Router loop, Agent Manager loop, UI projection, and
  tests land together.
- Revisit this document if `Orchestrator` gains a concrete caller or if the
  Execution Plane gains remote worker claim/lease/heartbeat services.
