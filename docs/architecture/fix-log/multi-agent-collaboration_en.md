# Multi-Agent Collaboration English Architecture Fact Calibration Log

> Source document: `docs/architecture/multi-agent-collaboration_en.md`
> Preserved original:
> `docs/architecture/archive/original/multi-agent-collaboration_en.original.md`
> Calibration date: 2026-07-10
> Scope: independent calibration of the English multi-Agent architecture
> document against current source, tests, UI contracts, and accepted ADRs.

## 1. Workflow Gate Report

- User request summary: calibrate each architecture document independently,
  preserve its original, replace it with a current fact document, and create a
  per-document fix log.
- Detected workflow phase: P5 architecture fact maintenance, supported by P7/P8
  implementation evidence and P9 test evidence.
- Task type: documentation-only architecture correction.
- Required upstream artifacts:
  - the complete English source document;
  - current execution, TaskBus, authoring, routing, inquiry, interaction, and
    Execution Plane code;
  - current frontend contracts;
  - accepted routing ADRs and neighboring calibrated architecture;
  - targeted tests.
- Found artifacts: all required source, decision, architecture, UI contract, and
  test evidence was present.
- Missing or weak artifacts:
  - no public Agent protocol, Agent Manager, or dynamic assignment runtime;
  - no current Agent graph, delegation protocol, or graph authoring UI;
  - the old English body asserted target concepts as current despite its
    “historical architecture concept” header.
- Implementation allowed now: yes, for documentation-only calibration.
- Prework required: inspect the English document independently because its
  section ordering and several assertions differ from the Chinese source.
- Execution scope: preserve the English original, rewrite the English current
  baseline, and add this English-specific log. No code changes.
- Acceptance criteria:
  - preserved original matches the pre-calibration `HEAD` blob;
  - every implemented/non-implemented distinction has source or ADR evidence;
  - English-specific stale claims are corrected explicitly;
  - accepted future routing is not presented as current;
  - targeted tests and document checks pass.
- Risks and assumptions:
  - the old header's warning did not prevent present-tense body claims from being
    read as shipped architecture;
  - code-level autonomy primitives could be confused with a product-level Agent
    graph editor;
  - future-looking Execution Plane DTOs could be confused with a remote worker
    service;
  - this file is not treated as a mechanical translation of the Chinese
    counterpart.

## 2. Original Preservation

- Original Git blob:
  `c7c260077cf03f04c1b99901e2a1fa432b2bbb82`.
- Preserved path:
  `docs/architecture/archive/original/multi-agent-collaboration_en.original.md`.
- The pre-calibration working-tree hash matched the `HEAD` blob.
- The original contained 510 lines.
- It was related to, but not line-for-line identical with, the Chinese original:
  it changed section order and contained distinct English statements that
  required separate review.

## 3. English-Specific Stale Claims Found

1. The message section described only informational and actionable types, while
   current `AgentMessage` also has `response`.
2. The example `AgentMessage` used `id` rather than the current `message_id` and
   omitted response-parent and response-value fields.
3. It said users are never forced to block, while explicit ASK/confirmation can
   transition Task to `waiting_for_user`.
4. It modeled autonomy as a numeric `0.0` to `1.0` spectrum, which is not the
   current product contract.
5. It omitted current `risk_threshold` and `wait_strategy` fields from
   `AutonomyBehavior`.
6. It said every Agent action passes through AutonomyGate; Main Page assembly
   does not do this.
7. It claimed constraints make LLM output valid without a backend validator;
   current authoring, command, and publish boundaries still validate input.
8. It presented OrchestrationDesigner, OrchestrationDraft, DraftPatch,
   ConstraintProfile, OrchestrationConfig, graph nodes/edges, and ToolRegistry as
   concrete architecture, but repository search found no current models.
9. It described a live graph UI, node palette, drag validation, autonomy sliders,
   and orchestration presets that do not exist in frontend contracts.
10. It marked a Planner/Executor/Auditor “v1 high guardrails” topology as
    current; the current general execution route has one Default Agent.
11. It described MessageStream as the global and sole collaboration channel,
    ignoring TaskBus, authoring stores/commands, AskStore, Context Manager, and
    evidence stores.
12. It proposed push notifications and stream filters as mitigations without an
    implemented product surface.

## 4. Implementation Evidence

### 4.1 Fixed-Route Execution

- `src/taskweavn/task/execution.py`
  - Defines one `default_agent` fixed route.
  - `FixedRouteTaskExecutor` states that no Router, Agent Manager, assignment
    field, or reassignment UI is used.
  - `FixedRouteExecutionDispatcher` has one worker, coalesces Session triggers,
    and does not retain AgentLoop instances between Tasks.
  - `AgentLoopResidentDefaultAgent` creates/uses a task-scoped runner.
- `src/taskweavn/server/main_page.py`
  - Assembles the Default Agent, fixed-route dispatcher, local env registry, and
    embedded Execution Plane.
- `src/taskweavn/server/main_page_agent.py`
  - Assembles concrete tools, Context Manager, and task-scoped AgentLoop runner.
  - Does not assemble a Main Page AutonomyGate.

### 4.2 Task And Claim

- `src/taskweavn/task/models.py`
  - Task has capability, dispatch hints, and post-claim `claimed_by`, but no
    assignment fields.
- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`
  - Claim uses Session, pending status, exact capability, parent readiness, and
    deterministic ordering.
  - No Agent registry or assigned-only check is involved.

### 4.3 Specialized Roles

- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/task/collaborator_loop.py`
- `src/taskweavn/task/collaborator_profile_runner.py`
  - Collaborator is command-backed authoring with bounded workspace read/search,
    not a TaskBus worker.
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/runtime_input_llm_router.py`
  - Runtime Input Router classifies Main Page input and delegates to validated
    handlers; it does not assign Execution Agents.
- `src/taskweavn/server/read_only_inquiry.py`
- `src/taskweavn/server/read_only_inquiry_answer_provider.py`
  - Inquiry is bounded and read-only.
- `src/taskweavn/llm/agent_config.py`
  - Six Agent role names configure LLM profiles only.

### 4.4 Interaction And Placeholder Orchestration

- `src/taskweavn/interaction/message.py`
  - Defines informational, actionable, and response messages.
- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/bus.py`
  - Provide durable user-facing messages and in-process live delivery, not an
    Agent mailbox protocol.
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/interaction/gate.py`
  - Provide code-level autonomy primitives with narrower assembly than the old
    product-wide claim.
- `src/taskweavn/orchestration/protocol.py`
  - Contains only the placeholder Protocol and `NullOrchestrator`.
  - Search found no product/test caller beyond module exports.

### 4.5 Execution Plane And UI

- `src/taskweavn/execution_plane/models.py`
- `src/taskweavn/execution_plane/env_registry.py`
- `src/taskweavn/execution_plane/embedded_service.py`
  - Provide a local service-shaped Task API and in-memory env compatibility
    registry; no remote worker lease/heartbeat control plane exists.
- `frontend/src/shared/api/types.ts`
  - `TaskNodeCardView` has no assignment or Agent-health fields.
- `frontend/src/pages/main-page/TaskNodeCard.tsx`
- `frontend/src/pages/main-page/MainPageDetailPanel.tsx`
  - Current task controls include stop/retry, not assignment/reassignment.
- Searches across `src/taskweavn`, `tests`, and `frontend/src` found no current
  OrchestrationDraft, ConstraintProfile, OrchestrationConfig, Agent graph
  runtime, or corresponding editor.

## 5. Decision And Architecture Evidence

- `docs/decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md`
  - Accepts future Routing Agent assignment and cooperative interruption while
    retaining fixed-route current scope.
- `docs/decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md`
  - Accepts future TaskBus-centered Router/Agent Manager convergence and marks it
    outside the Product 1.0 implementation requirement.
- Current neighboring fact baselines:
  - `docs/architecture/overview.md`
  - `docs/architecture/agent.md`
  - `docs/architecture/task.md`
  - `docs/architecture/bus.md`
  - `docs/architecture/interaction-layer.md`
  - `docs/architecture/tool-capability-layer.md`
  - `docs/architecture/collaborator-agent-task-authoring.md`
  - `docs/architecture/taskbus-service-multi-execution-env.md`

## 6. Verified Facts

1. One fixed Default Agent is the current general Published Task executor.
2. Its stable adapter creates a task-scoped execution runner/AgentLoop.
3. The dispatcher uses one worker per assembled workspace runtime and coalesces
   duplicate Session triggers.
4. TaskBus itself has no global one-running-Task-per-Session guard.
5. Claim matches exact capability and parent readiness.
6. Current claim ignores Agent preference fields in dispatch constraints.
7. `claimed_by` is a post-claim fact, not pre-claim assignment.
8. No assignment model/store/command/index or assigned-only claim exists.
9. No Agent Manager, AgentPool, or generic runtime Agent registry exists.
10. Collaborator is an implemented authoring actor, not an execution worker.
11. Collaborator writes through commands and has only bounded workspace
    read/search context tools.
12. Runtime Input Router is an input/contract router, not the future Task
    assignment Router.
13. Read-only Inquiry cannot execute workspace-changing Tasks.
14. Agent LLM roles configure clients rather than instantiate Agents.
15. `Orchestrator` is an unused placeholder.
16. MessageStream has three message types and is user-facing rather than an
    Agent-to-Agent protocol.
17. ASK and confirmation can block a Task.
18. Main Page does not gate every normal tool action with AutonomyGate.
19. Capability catalogs validate authoring/publish input rather than provide a
    live Agent pool.
20. Concrete tools are assembled directly for Default Agent; the original
    ToolRegistry abstraction is absent.
21. Execution Plane env selection is local compatibility checking.
22. Future-looking lease/env DTO fields do not establish a remote worker
    service.
23. Main Page has no graph, assignment, reassignment, worker-health, or parallel
    branch UI.
24. No agent-to-agent handoff or result aggregation protocol exists.
25. No parallel workspace-writer conflict/merge protocol exists.
26. ADR-0011/0012 remain future dynamic-routing direction.

## 7. Corrections Applied

- Replaced the target Planner/Executor/Auditor graph with the actual fixed-route
  execution topology.
- Added a role map distinguishing runtime Agent, service role, metadata, LLM
  profile, runtime handler, and placeholder protocol.
- Corrected MessageStream from two message types to three and documented its
  user-facing authority.
- Replaced “stream over interrupt” as a universal fact with the actual
  ASK/confirmation waiting lifecycle.
- Restricted AutonomyGate claims to the code paths that actually assemble it.
- Removed the numeric-autonomy product model and non-existent graph-node
  autonomy UI.
- Marked OrchestrationDesigner, graph models, ConstraintProfile, graph presets,
  DraftPatch, and ToolRegistry as non-facts.
- Rejected the old claim that prompt constraints remove the need for backend
  validation.
- Replaced graph tool assignment with current concrete Default Agent tool
  assembly and static validation catalogs.
- Added current TaskBus claim rules and the distinction between `claimed_by` and
  assignment.
- Added local Execution Plane facts without promoting DTO vocabulary to remote
  worker behavior.
- Added current UI/API boundaries and absent assignment/reassignment surfaces.
- Moved ADR-0011/0012 routing content into an explicitly future section.
- Added minimum implementation prerequisites before dynamic multi-Agent claims
  can become current facts.

## 8. Targeted Test Evidence

- `tests/test_fixed_route_task_executor.py`
- `tests/test_task_bus_lifecycle.py`
- `tests/test_sqlite_task_bus.py`
- `tests/test_collaborator_authoring_service.py`
- `tests/test_collaborator_authoring_loop_contract.py`
- `tests/test_runtime_input_router.py`
- `tests/test_execution_plane_service.py`
- `tests/test_main_page_sidecar_app.py`

Together these suites cover fixed-route claim/run/drain, TaskBus lifecycle and
persistence, Collaborator proposal/command behavior, Runtime Input routes,
embedded Execution Plane behavior, and real sidecar assembly.

## 9. Validation Record

Validation completed on 2026-07-10:

- Original preservation:
  - `git hash-object docs/architecture/archive/original/multi-agent-collaboration_en.original.md`
    returned `c7c260077cf03f04c1b99901e2a1fa432b2bbb82`.
  - `git rev-parse HEAD:docs/architecture/multi-agent-collaboration_en.md`
    returned the same blob id.
- Targeted backend tests:
  - `uv run pytest -q tests/test_fixed_route_task_executor.py
    tests/test_task_bus_lifecycle.py tests/test_sqlite_task_bus.py
    tests/test_collaborator_authoring_service.py
    tests/test_collaborator_authoring_loop_contract.py
    tests/test_runtime_input_router.py tests/test_execution_plane_service.py
    tests/test_main_page_sidecar_app.py`
  - Result: `162 passed in 17.22s`.
- Document checks:
  - all relative architecture and ADR targets referenced by the calibrated
    document exist;
  - stale target language is retained only where the fix log identifies it as
    an original error or where the current document labels it a non-fact;
  - no source or frontend file was changed;
  - `git diff --check` passed for the English document artifacts.

## 10. Follow-Up Boundary

- Do not reintroduce the old orchestration graph as current architecture until
  model, command, store, runtime, UI, and test evidence all exist.
- Revisit the placeholder status only when `Orchestrator` has a concrete
  implementation and product caller.
- Revisit ExecutionEnv wording only when remote registration, claim, lease,
  heartbeat, and stale recovery are implemented together.
