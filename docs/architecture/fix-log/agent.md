# Agent Architecture Fact Calibration Log

> Source document: `docs/architecture/agent.md`
> Preserved original: `docs/architecture/archive/original/agent.original.md`
> Calibrated document version: v1.5 · 2026-07-10
> Calibration scope: verify current Agent architecture claims against code and
> related architecture / decision / feature documents.

---

## 1. Workflow Gate Report

- User request summary: calibrate one architecture document at a time by checking
  related docs and code facts, preserving the old document, and writing a
  per-document fix log.
- Detected workflow phase: P5 Frontend / Backend Architecture fact maintenance,
  with P8 integration and P9 verification evidence.
- Task type: architecture documentation correction and evidence log.
- Required upstream artifacts: existing architecture doc, current implementation,
  related ADR / plan docs, targeted tests.
- Found artifacts:
  - `docs/architecture/agent.md`
  - `docs/architecture/overview.md`
  - `docs/decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md`
  - `docs/plans/feature/local-macos-wechat-send-mvp-technical-design.zh-CN.md`
  - Agent / TaskBus / Execution Plane / Collaborator / LLM resolver code under
    `src/taskweavn/`
- Missing or weak artifacts:
  - No single canonical public Agent protocol document exists yet.
  - No current Agent Manager / dynamic Agent assignment implementation exists.
  - Some older architecture wording mixed current fixed-route execution with
    future routed AgentPool concepts.
- Implementation allowed now: yes, for documentation-only calibration.
- Prework required before implementation: preserve original document, verify code
  and related docs, write fix log before treating the calibrated document as
  updated fact.
- Proposed execution scope: narrow revision of `agent.md`; no production code
  changes.
- Acceptance criteria:
  - Old document remains available for comparison.
  - Current facts distinguish fixed-route Default Agent execution, Runtime Input
    Router, local Execution Plane, and future Agent Manager work.
  - Claims about task creation, collaborator agent metadata, capability catalogs,
    LLM profile resolution, and ThoughtStore are grounded in code facts.
  - `git diff --check` and targeted tests pass.
- Risks and assumptions:
  - This log calibrates `agent.md` only. Other architecture documents may still
    contain stale claims until processed separately.
  - Some target abstractions remain valuable, but they are explicitly marked as
    future / not current Product 1.1 fact.

## 2. Evidence Inspected

### Implementation Evidence

- `src/taskweavn/server/main_page_agent.py`
  - `build_agent_loop_resident_default_agent(...)` constructs the resident
    Default Agent boundary.
  - `_SessionAgentLoopRunner.run(...)` creates a task-scoped `AgentLoop`.
  - Current tool registration includes workspace file/search/edit tools,
    `RunCommandTool`, optional web search/fetch tools, optional computer use,
    `AskUserTool`, and optional `RequestConfirmationTool`.
- `src/taskweavn/task/execution.py`
  - `FixedRouteExecutionDispatcher` responds to dispatch triggers and runs
    executor ticks.
  - `FixedRouteTaskExecutor` claims pending work from TaskBus by
    `required_capability` and invokes the resident Default Agent.
  - `AgentLoopResidentDefaultAgent.run(task)` maps AgentLoop outcomes to
    `TaskRunResult`.
  - The dispatcher does not keep a long-lived `AgentLoop` instance across tasks.
- `src/taskweavn/execution_plane/embedded_service.py`
  - `EmbeddedTaskApiService` accepts `TaskRequest`.
  - Ordinary task types are converted into TaskBus tasks.
  - Runtime handlers can process specific task types.
- `src/taskweavn/execution_plane/wechat_send_runtime.py`
  - `WeChatSendRuntimeHandler` is a concrete local runtime handler for WeChat
    send tasks.
  - It is a controlled local task runtime, not a public Agent Manager.
- `src/taskweavn/task/collaborator.py`
  - `CollaboratorAgentTemplate` is session-scoped metadata for the built-in
    Collaborator.
  - Collaborator writes are mediated by services and commands, not workspace /
    shell tools.
- `src/taskweavn/task/authoring.py`
  - `CapabilityCatalog` and `StaticCapabilityCatalog` support task authoring
    capability lookup / validation.
- `src/taskweavn/task/publisher_input.py`
  - `AgentCapabilityCatalog` and `StaticAgentCapabilityCatalog` support publish
    input validation.
- `src/taskweavn/llm/agent_config.py`
  - `AgentLlmRole` defines backend role names such as `runtime_input_router`,
    `execution_agent`, `collaborator`, `read_only_inquiry`, `audit_agent`, and
    `summary_agent`.
- `src/taskweavn/llm/agent_resolver.py`
  - `SettingsBackedAgentLlmResolver` resolves role-aware backend LLM clients.
  - LLM role/profile resolution does not create runtime Agent instances.

### Test Evidence

- `tests/test_fixed_route_task_executor.py`
- `tests/test_agent_llm_config.py`
- `tests/test_agent_llm_resolver.py`
- `tests/test_runtime_input_router.py`
- `tests/test_execution_plane_service.py`
- `tests/test_wechat_send_runtime.py`
- `tests/test_collaborator_api_adapter.py`
- `tests/test_task_publisher_input.py`
- `tests/test_task_authoring.py`

### Related Documentation Evidence

- `docs/architecture/overview.md`
  - Current system overview already treats local Execution Plane / Task API as a
    Product 1.1 foundation, while keeping remote / distributed execution as
    future work.
- `docs/decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md`
  - Confirms Product 1.0 fixed-route execution and TaskBus-centered future
    assignment direction.
- `docs/plans/feature/local-macos-wechat-send-mvp-technical-design.zh-CN.md`
  - Confirms the local macOS WeChat Send MVP and marks remote execution
    environment as out of scope for that feature.

## 3. Verified Current Facts

1. Current task execution path remains fixed-route:
   `FixedRouteExecutionDispatcher -> FixedRouteTaskExecutor ->
   AgentLoopResidentDefaultAgent -> task-scoped AgentLoop`.
2. The resident Default Agent is a stable runtime boundary / identity, but the
   actual `AgentLoop` run is task-scoped.
3. Current Product 1.1 has Runtime Input Router capabilities, but that router is
   for user input / contract revision / read-only inquiry / handoff decisions.
   It is not the TaskBus Routing Agent assignment policy described as a future
   dynamic routing abstraction.
4. Current Product 1.1 has a local Execution Plane / Task API foundation.
   `EmbeddedTaskApiService` can accept `TaskRequest`, map ordinary task types to
   TaskBus, and delegate special task types to local runtime handlers.
5. `EmbeddedTaskRuntimeHandler` is a service/runtime handler extension point,
   not a public Agent Manager and not dynamic Agent assignment.
6. `WeChatSendRuntimeHandler` is the concrete evidence for a special local
   runtime handler path.
7. No generic `CreateTaskTool` exists in current code. Task creation / revision
   is mediated by Collaborator Authoring Service, Authoring Command Service,
   Contract Revision Commands, and TaskPublisher.
8. `CollaboratorAgentTemplate` exists, but it is metadata for the built-in
   Collaborator. It does not expose workspace or shell tools and does not make a
   general Agent registry real.
9. `StaticCapabilityCatalog` and `StaticAgentCapabilityCatalog` are validation
   / lookup helpers, not a dynamic AgentPool.
10. `AgentLlmRole` and `SettingsBackedAgentLlmResolver` implement backend-only
    role-aware LLM selection. They do not instantiate runtime Agents.
11. ThoughtStore protocol / SQLite / Null implementations exist, but the current
    sidecar Default Agent path does not use ThoughtStore as a user-visible
    long-term memory or fact authority.

## 4. Corrections Applied

- Updated document header to v1.5 · 2026-07-10.
- Added a 2026-07-10 fact calibration note for local Execution Plane / Task API
  and runtime handler facts.
- Clarified that current Product 1.1 keeps fixed Default Agent route while
  adding Runtime Input Router and local Execution Plane foundations.
- Separated Runtime Input Router from the future Routing Agent assignment model.
- Replaced current `CreateTaskTool` claims with command-backed authoring /
  publishing boundaries.
- Marked public Agent protocol, Agent Manager, AgentPool, dynamic assignment,
  user custom Agent, and ThoughtStore experience injection as future / target
  abstractions rather than current Product 1.1 facts.
- Added current implementation notes for:
  - `CollaboratorAgentTemplate`
  - capability catalogs
  - role-aware Agent LLM resolver
  - task-scoped AgentLoop run
  - fixed-route dispatcher / executor
  - local Execution Plane and runtime handlers
  - current Default Agent tool families
  - ThoughtStore non-authority status in the sidecar Default Agent path

## 5. Follow-up Calibration Targets

- `docs/architecture/task.md`
  - Re-check task model claims against TaskBus, authoring commands, Task API,
    WeChat send task type, and revision flows.
- `docs/architecture/bus.md`
  - Re-check TaskBus state authority, fixed-route execution, ASK/resume,
    dispatch trigger semantics, and assignment roadmap.
- `docs/architecture/taskbus-service-multi-execution-env.md`
  - Re-check remote / multi-environment claims against the now-local Execution
    Plane foundation.
- `docs/architecture/collaborator-agent-task-authoring.md`
  - Re-check collaborator metadata and authoring command boundaries.
