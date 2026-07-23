# Fact Calibration Log: overview.md

> Calibrated document: [../overview.md](../overview.md)
> Preserved original: [overview.original.md](../archive/original/overview.original.md)
> Calibration date: 2026-07-10
> Scope: first document in the architecture fact-calibration pass.

## Workflow Gate

- User request: fact-check architecture docs one document at a time, preserve old docs, add per-document fix logs, and revise based on code and document facts.
- Detected phase: P5 Frontend/Backend Architecture plus P8/P9 runtime and release-readiness evidence.
- Task type: architecture documentation fact calibration.
- Required upstream artifacts: active architecture docs, engineering contracts, ADRs, release evidence, implementation code, and focused tests.
- Found artifacts: current architecture docs, Product 1.1 open-work and release records, ADR-0020, Runtime Input Router and Execution Plane code/tests.
- Missing/weak artifacts: `docs/engineering/runtime-input-router-api-contract.md` still contains a deferred-capability section that is older than current Runtime Input Router code and Product 1.1 release/open-work facts.
- Implementation allowed now: yes, documentation-only, narrow scope.
- Prework required: preserve the original overview before editing and record evidence in this log.
- Execution scope: revise `overview.md` only, preserve `overview.original.md`, and add this fix log.
- Acceptance criteria: every updated architecture statement is tied to code or current docs; future/distributed Execution Plane claims stay clearly deferred.
- Risks/assumptions: some adjacent architecture docs still use older phrasing and need separate calibration passes.

## Maintainability Gate

- Requested change: architecture hygiene / documentation repair.
- Files/modules inspected: `docs/architecture/overview.md`, Runtime Input Router, Contract Revision, Execution Plane, fixed-route execution, Agent LLM, Context Manager, sidecar assembly, and targeted tests.
- Trigger: architecture hygiene and fact document correction.
- Current risk level: medium because the overview is a canonical read-order document.
- Responsibility count: documentation cross-cuts runtime input, execution, sidecar, LLM, context, and release evidence.
- Size/complexity signals: `overview.md` is about 500 lines; no production code edited.
- Coupling signals: references many subsystem boundaries.
- Tests covering the area: targeted backend tests listed below cover the facts used.
- Refactor required first: no.
- Allowed change type: boundary_redesign_plan / documentation fact correction.
- Proposed slice: calibrate only `overview.md`.
- Validation commands: `git diff --check` plus targeted tests if time permits.
- Risks and assumptions: old docs may remain inconsistent until their own fix-log passes.

## Evidence Inspected

### Active docs and decisions

- `docs/architecture/overview.md`
- `docs/architecture/README.md`
- `docs/architecture/taskbus-service-multi-execution-env.md`
- `docs/decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md`
- `docs/plans/feature/execution-plane-service-task-api.md`
- `docs/releases/product-1-1-runtime-input-router-release-evidence.md`
- `docs/releases/local-computer-use-tool-foundation.md`
- `docs/product/plato-1-1-open-work.md`
- `docs/engineering/runtime-input-router-api-contract.md`
- `docs/engineering/workspace-entry-contract.md`
- `docs/releases/context-manager-cache-aware-rendering.md`
- `docs/plans/feature/agent-llm-config-and-router-llm.md`

### Code and tests

- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/runtime_input_llm_router.py`
- `src/taskweavn/server/runtime_input_activity.py`
- `src/taskweavn/contract_revision/service.py`
- `src/taskweavn/task/execution.py`
- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/publisher.py`
- `src/taskweavn/execution_plane/models.py`
- `src/taskweavn/execution_plane/service.py`
- `src/taskweavn/execution_plane/embedded_service.py`
- `src/taskweavn/execution_plane/store.py`
- `src/taskweavn/server/ui_http_execution_plane.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/computer_use_runtime.py`
- `src/taskweavn/llm/agent_config.py`
- `src/taskweavn/llm/agent_resolver.py`
- `src/taskweavn/context/manager.py`
- `src/taskweavn/context/renderer.py`
- `src/taskweavn/context/agent_loop_provider.py`
- `tests/test_runtime_input_router.py`
- `tests/test_runtime_input_llm_router.py`
- `tests/test_execution_plane_service.py`
- `tests/test_execution_plane_http_transport.py`
- `tests/test_fixed_route_task_executor.py`
- `tests/test_agent_llm_resolver.py`
- `tests/test_context_manager.py`

## Verified Facts

1. Runtime Input Router is implemented as deterministic routes plus optional LLM route planning.
   Evidence: `DefaultRuntimeInputRouter.route()` handles active ASK, active confirmation, stop/retry, questions, guidance mode, change mode/workspace-change markers, and unsupported fallback. `LLMRuntimeInputRoutePlanner` returns validated proposals only.

2. Router LLM does not execute tools or mutate files directly.
   Evidence: `runtime_input_llm_router.py` sends no tools, restricts dispatch targets, rejects low-confidence mutation, and validates side effects. Tests reject low-confidence mutation and read-only refs on mutating dispatch.

3. Guidance recording is current code when `ContractRevisionCommandService` is configured.
   Evidence: `_record_guidance()` creates a `ContractCommandRequest(command_kind="record_guidance")`; `ContractRevisionCommandService._record_guidance()` persists a `GuidanceFact`; tests assert guidance facts and durable activity.

4. Execution handoff through Runtime Input is current code when the contract revision service and task-node handler are configured.
   Evidence: `_create_execution_task()` dispatches `command_kind="create_execution_task"`; tests assert `mode="change"` creates a `task_created` activity through the task-node command handler.

5. Runtime Input routes are dependency-gated.
   Evidence: router branches return unsupported/rejected outcomes when read-only inquiry, contract revision service, interaction handlers, or task-node handlers are unavailable; tests cover unavailable read-only inquiry and unsupported workspace-changing routes without a contract service.

6. Natural-language `publish plan` is not a deterministic Router route.
   Evidence: `tests/test_runtime_input_router.py::test_router_defers_publish_and_workspace_changing_requests` asserts `publish plan` produces `unsupported`.

7. The local Execution Plane Task API exists as a service-compatible boundary.
   Evidence: `TaskApiService` protocol defines publish/get/cancel/retry/events/result/evidence methods; `ui_http_routes.py` matches `/api/v1/tasks` routes; `ui_http_execution_plane.py` delegates those routes to `TaskApiService`; HTTP tests cover publish/get/events/result and workspace-prefixed publish.

8. The current Execution Plane implementation is embedded/local, not a remote distributed service.
   Evidence: `EmbeddedTaskApiService` is backed by `TaskBus`, `ExecutionPlaneStore`, and local `ExecutionEnvRegistry`; ADR-0020 and the Execution Plane plan call remote/service extraction later; HTTP route returns 503 when no service is configured.

9. Main Page sidecar assembly wires the embedded Execution Plane.
   Evidence: `main_page.py` creates `SqliteExecutionPlaneStore(layout.meta_dir / "execution_plane.sqlite")`, builds runtime handlers, creates `EmbeddedTaskApiService`, and injects it into `PlatoUiHttpTransport`.

10. Optional computer-use / WeChat runtime handlers are capability-gated.
    Evidence: `computer_use_runtime.py` returns no Execution Plane runtime handlers unless computer-use settings are enabled and a backend is configured; release evidence says real desktop automation and distributed execution remain out of scope for that release.

11. Fixed-route execution remains the current local execution path.
    Evidence: `FixedRouteExecutionDispatcher` queues sidecar dispatch and instantiates `FixedRouteTaskExecutor`; `FixedRouteTaskExecutor` claims from TaskBus and runs a resident Default Agent; tests cover claim/complete/fail/wait and dispatcher behavior.

12. Execution Plane service-level DTOs and stores are implemented.
    Evidence: `execution_plane/models.py` defines `TaskRequest`, `TaskExecution`, `TaskEvent`, `TaskResult`, `TaskError`, `EvidenceRef`, `ExecutionEnv`, and `TaskLease`; `store.py` provides in-memory and SQLite execution stores; tests cover idempotent publish and SQLite persistence.

13. Distributed ExecutionEnv registration, remote worker claim, lease, heartbeat, callback enforcement, and external app auth are not current runtime facts.
    Evidence: they appear in ADR-0020 and the multi-execution-env memo as direction; current `EmbeddedTaskApiService` uses a local in-memory env registry and TaskBus-backed publish/query flow.

14. Agent LLM roles are backend-only and current.
    Evidence: `AgentLlmRole` includes `runtime_input_router`, `execution_agent`, `collaborator`, `read_only_inquiry`, `audit_agent`, and `summary_agent`; resolver tests prove role-profile binding. The technical design explicitly excludes Settings UI exposure.

15. Context Manager cache-aware rendering remains current.
    Evidence: `SessionContextManager`, `DeterministicContextRenderer`, and `SessionAgentLoopContextProvider` implement start, delta, checkpoint, and transcript reuse modes; release evidence and tests cover deterministic, cache-aware rendering.

## Changes Made To overview.md

1. Updated metadata from v1.4 / 2026-06-23 to v1.5 / 2026-07-10 and added ADR-0020 to related decisions.
2. Added the additive local Execution Plane / Task API foundation to the architecture shape.
3. Added `TaskRequest` / `TaskExecution` and `ExecutionEnv` to Core Objects with local-versus-deferred boundaries.
4. Clarified that Runtime Input Router has deterministic routes plus an optional validated LLM planner.
5. Clarified dependency-gated Runtime Input behavior and the negative boundary for natural-language `publish plan`.
6. Added the local Task API path through `EmbeddedTaskApiService`, `TaskBus`, `FixedRouteExecutionDispatcher`, and `FixedRouteTaskExecutor`.
7. Added Execution Plane Task API to Communication Boundaries while preserving TaskBus as executable lifecycle authority.
8. Added sidecar wiring facts for `SqliteExecutionPlaneStore`, `EmbeddedTaskApiService`, and optional runtime handlers.
9. Added "Embedded Execution Plane only" to current constraints.
10. Added remote Execution Plane service to deferred extension paths.
11. Updated the read order to include ADR-0020 and the Execution Plane service plan.

## Follow-Up Calibration Targets

- `docs/engineering/runtime-input-router-api-contract.md`: deferred-capability section is older than current Runtime Input Router code and should be revised in its own pass.
- `docs/architecture/agent.md`, `docs/architecture/task.md`, and `docs/architecture/bus.md`: still contain older fixed-route wording that should be checked against the Execution Plane foundation and current dispatcher/executor code.
- `docs/architecture/taskbus-service-multi-execution-env.md`: already calls itself exploratory, but should be checked after the Execution Plane plan/API docs are calibrated.

## PR #182 Review Follow-Up (2026-07-11)

- Replaced the nonexistent `TaskFailure` result branch in the fixed-route flow
  with the implemented `TaskRunResult` boundary.
- Made the next transition explicit: `FixedRouteTaskExecutor` maps the run
  result to `TaskBus.complete(...)` / `TaskBus.fail(...)`, or preserves the
  interaction-committed `waiting_for_user` state already stored on `TaskDomain`.
- Execution Plane `TaskResult` / `TaskError` remain separate service DTOs and are
  not presented as the direct return type of the resident Default Agent.
