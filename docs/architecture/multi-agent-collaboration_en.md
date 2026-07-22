# Multi-Agent Collaboration Architecture: Current Facts And Extension Boundary

> Status: fact-calibrated current architecture baseline
> Last Updated: 2026-07-10
> Chinese counterpart:
> [multi-agent-collaboration.md](multi-agent-collaboration.md)
> Original preserved as:
> `docs/architecture/archive/original/multi-agent-collaboration_en.original.md`
> Related:
> [Overview](overview.md),
> [Agent](agent.md),
> [Task](task.md),
> [TaskBus](bus.md),
> [Interaction Layer](interaction-layer.md),
> [Collaborator Authoring](collaborator-agent-task-authoring.md),
> [Execution Plane](taskbus-service-multi-execution-env.md),
> [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md),
> [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)

## 1. Purpose And Current Conclusion

This document records what the repository currently implements around
multi-Agent collaboration. Accepted future design is kept separate from current
runtime fact.

Plato / TaskWeavn does **not** currently implement a multi-Agent graph runtime.
The general Published Task execution path is fixed-route:

```text
Published Task
  -> TaskBus
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor
  -> resident Default Agent boundary
  -> task-scoped AgentLoop
  -> TaskBus complete / fail / wait
```

The repository also contains components whose names include Agent, Router, or
Execution Environment. They do not collectively form a dynamic multi-Agent
scheduler:

- Collaborator performs command-backed task authoring and never claims a
  Published Task.
- Runtime Input Router classifies and dispatches Main Page input; it does not
  assign Execution Agents.
- Read-only Inquiry answers bounded questions and cannot mutate the workspace.
- Agent LLM roles select model profiles and do not create runtime Agent
  instances.
- ExecutionEnv registry performs local compatibility checks and does not manage
  remote workers.
- `Orchestrator` is an unused placeholder Protocol with only a
  `NullOrchestrator` implementation.

This document therefore distinguishes:

1. currently implemented specialized service roles;
2. the one fixed-route general execution Agent;
3. the future Router + Agent Manager + multiple Execution Agent architecture.

## 2. Current Role Map

| Name | Current implementation | Claims TaskBus work | Actual boundary |
|---|---|---:|---|
| Default Agent | `AgentLoopResidentDefaultAgent` | Yes | Stable `default_agent` identity; task-scoped runner / AgentLoop per Task |
| Collaborator | Authoring service, profile runner, and command adapter | No | Proposes RawTask / Plan / DraftTaskTree changes and submits authoring commands |
| Runtime Input Router | Deterministic router plus optional LLM route planner | No | Routes user input to inquiry, contract commands, interaction resolution, Task controls, or execution handoff |
| Read-only Inquiry | Inquiry service and answer provider | No | Answers from explicitly allowed product, diagnostic, and read-only workspace context |
| Agent LLM roles | Six `AgentLlmRole` values | No | Resolve provider/model configuration only |
| Local runtime handler | `EmbeddedTaskRuntimeHandler` implementations | No | Handle selected local task types through a controlled service seam |
| `Orchestrator` | Protocol and `NullOrchestrator` | No | Placeholder; not assembled or called by the product runtime |

### 2.1 Default Agent

Main Page sidecar assembly builds one resident Default Agent adapter for a
workspace runtime. The adapter is a stable entry point, but it does not retain
the same AgentLoop between Tasks:

```text
AgentLoopResidentDefaultAgent.run(task)
  -> loop_factory(task)
  -> task-scoped _SessionAgentLoopRunner
  -> AgentLoop.run(rendered context, task_id)
  -> TaskRunResult
```

TaskBus, Context Manager, AskStore, MessageStream, Event/Audit stores, and
result summaries own durable facts. Cross-task private Agent memory is not a
system authority.

### 2.2 Collaborator

`CollaboratorAgentTemplate` is real, but it is metadata for the built-in
authoring role:

- template id: `system.collaborator`;
- capability: `task_authoring`;
- command protocol: `authoring.v1`;
- default LLM-visible tool pools: empty;
- registry scope: Collaborator metadata per Session, not a general AgentPool.

The authoring service asks an LLM for a structured proposal and submits the
proposal through `AuthoringCommandService`. Workspace-informed authoring can
use bounded read/search operations. The profile explicitly forbids
`write_file`, `run_command`, `shell`, and `execute_code`.

Its collaboration with execution is a durable contract transition:

```text
user input
  -> Collaborator proposal
  -> AuthoringCommandService
  -> RawTask / Plan / DraftTaskTree facts
  -> explicit publish
  -> Published Task in TaskBus
```

There is no private Collaborator-to-Default-Agent handoff message.

### 2.3 Runtime Input Router And Inquiry

Runtime Input Router may use an LLM route planner, but deterministic handlers
still validate and submit state-changing commands. It routes Main Page input;
it does not observe Agent availability or write Task assignment.

Read-only Inquiry may have a separate LLM profile. It has no TaskBus claim
authority and no workspace mutation tools. Message or log labels such as
`runtime_input_router` and `read_only_inquiry` are not entries in a runtime
Agent registry.

## 3. Current Runtime Topology

### 3.1 Input And Authoring

```text
Main Page input
  -> Runtime Input Router
     -> read-only inquiry
     -> guidance / contract revision
     -> answer active ASK
     -> resolve active confirmation
     -> stop / retry selected Task
     -> execution handoff command
     -> clarification / unsupported outcome

Authoring
  -> Collaborator profile
  -> bounded workspace read/search when required
  -> structured proposal
  -> AuthoringCommandService
  -> Plan / TaskNode or legacy DraftTaskTree projection
  -> explicit publish
```

### 3.2 General Published Task Execution

```text
publish or resume trigger
  -> FixedRouteExecutionDispatcher.request_dispatch(session_id)
  -> one dispatcher worker dequeues a Session
  -> FixedRouteTaskExecutor selects one eligible pending Task
  -> TaskBus.claim_next(
       session_id,
       capability=task.required_capability,
       agent_id="default_agent",
     )
  -> resident Default Agent runs the Task
  -> TaskBus.complete / fail / wait_for_user / wait_for_confirmation
```

The dispatcher coalesces duplicate triggers per Session. One worker drains
queued Sessions, and one trigger runs up to a configured tick limit. It
continues to the next tick only when the previous tick completed. It neither
keeps AgentLoop instances alive between Tasks nor executes a graph of child
Agents.

### 3.3 Embedded Execution Plane

`EmbeddedTaskApiService` provides a local service-shaped Task API:

```text
TaskRequest
  -> idempotency validation
  -> local ExecutionEnv compatibility check
  -> ordinary task: publish TaskDomain to TaskBus
  -> selected task type: optional local EmbeddedTaskRuntimeHandler
```

Ordinary task types still use fixed-route Default Agent execution. Selected
runtime handlers, including the controlled local WeChat send path, are
task-type extensions rather than public Agents or an Agent Manager.

## 4. Assignment And Claim Facts

### 4.1 Current Task Model

`TaskDomain` currently contains:

- single-string `required_capability`;
- optional `dispatch_constraints` for future dispatch intent and metadata;
- `claimed_by`, written after claim;
- status values `pending`, `running`, `waiting_for_user`, `done`, and `failed`.

It does not contain:

- `assigned_agent_id`;
- `assigned_by` or `assigned_at`;
- assignment rationale or version;
- an `assigned` status;
- implemented `AssignmentCommand` or `claim_assigned()` operations.

`TaskDispatchConstraints` can carry `required_agent_id`, `preferred_agent_id`,
and `required_capabilities`, but current `claim_next()` does not inspect those
fields.

### 4.2 Exact Claim Rules

Both in-memory and SQLite TaskBus implementations require:

1. matching Session;
2. `pending` status;
3. exact `required_capability` match;
4. a root Task, or a parent whose status is `done`;
5. candidate order by `created_at`, `order_index`, then `task_id`.

A successful claim writes `running`, the caller-provided `claimed_by`, and
`started_at`. TaskBus does not consult an Agent registry, Agent health, tool
inventory, cost, load, or historical success.

### 4.3 Where Serial Execution Comes From

The Main Page product path is normally serial because the assembled
fixed-route dispatcher uses one worker. TaskBus itself does not enforce one
running Task per Session. Another caller can invoke `claim_next()` again and
claim another eligible pending root.

SQLite claim is protected by the current `SqliteTaskBus` instance's process
local `RLock`. There is no distributed compare-and-swap, worker lease, fencing
token, or stale ownership recovery protocol.

## 5. Current Collaboration Surfaces

### 5.1 Durable Facts, Not Shared Agent Memory

| Collaboration subject | Authority |
|---|---|
| Unpublished intent and task structure | RawTask / Plan / TaskNode / DraftTask stores |
| Published Task lifecycle | TaskBus |
| Execution ASK | AskStore plus TaskBus waiting linkage |
| Confirmation | MessageStream response plus TaskBus waiting linkage |
| User-visible messages | SQLite MessageStream |
| Execution evidence | EventStream, result/error summaries, audit projections |
| Next run context | Session Context Manager |
| Service-level execution request | Execution Plane store plus TaskBus |

No role advances these facts by mutating another Agent object's private state.

### 5.2 MessageStream Is Not An Agent Mailbox

Current `AgentMessage.message_type` has **three** values:

- `informational`;
- `actionable`;
- `response`.

Messages carry Session identity, optional Task identity, an `agent_id` string,
an optional response parent, body/context, action options, response fields, and
a timestamp. `SqliteMessageStream` persists history. `InProcessMessageBus` is
the only bus implementation, and live subscriptions deliver messages published
after subscription starts.

The stream supports user conversation, ASK/confirmation, and UI projection. It
does not define:

- Agent mailbox addressing;
- Agent-to-Agent request/response schemas;
- delegation ids, handoff tokens, or child-run correlation;
- multi-Agent result aggregation;
- delivery acknowledgement, retry, or backpressure between Agents.

### 5.3 ASK And Confirmation Can Block A Task

Main Page's explicit `ask_user` and `request_confirmation` tools can transition
a running Task to `waiting_for_user` and end the current task-scoped run. A
valid answer returns the Task to `pending`; a later dispatcher trigger claims
it again.

This is a real pause/wait/resume lifecycle. The old “never interrupted” claim is
not a current guarantee.

### 5.4 Autonomy Primitives Have A Narrower Boundary

`AutonomyBehavior`, five code-level presets, `AutonomyGate`, and
`WaitCoordinator` exist. The generic CLI can opt into that path. Main Page
Default Agent assembly does not route every normal tool action through an
AutonomyGate; it uses explicit ASK and confirmation tools instead.

The existence of these primitives does not establish:

- a numeric autonomy slider;
- per-Agent graph-node autonomy configuration;
- a Main Page autonomy preset selector;
- confidence-based `proceed_confident` behavior for an Agent graph;
- universal non-blocking action semantics.

## 6. Agent Lifecycle And State Ownership

### 6.1 Current Lifecycle

```text
workspace runtime assembly
  -> build resident Default Agent adapter
  -> dispatcher receives trigger
  -> adapter creates task-scoped runner
  -> Context Manager renders execution input
  -> AgentLoop executes tools / asks / confirmations
  -> adapter maps LoopResult to TaskRunResult
  -> executor commits TaskBus lifecycle
  -> run-local stack is released
```

`claimed_by="default_agent"` is a Task execution fact, not a foreign key into
a general instance registry.

### 6.2 Missing Lifecycle Components

Current code has no general:

- Agent Manager;
- Agent template/instance registry;
- warm Agent pool or process pool;
- spawn, health, drain, or terminate lifecycle;
- capacity, cost, or load scheduler;
- child Agent ownership tree;
- runtime validation chain joining Agent version, permission profile, and Task
  assignment.

The Collaborator metadata registry and ExecutionEnv registry do not provide
these capabilities.

### 6.3 Placeholder Orchestrator

`src/taskweavn/orchestration/protocol.py` defines this shape:

```python
class Orchestrator(Protocol):
    def submit(self, action: BaseAction) -> BaseObservation: ...
    def shutdown(self) -> None: ...
```

Only `NullOrchestrator` exists, and its `submit()` raises
`NotImplementedError`. Repository search found no product or test caller beyond
module exports. It is not a current planner/executor orchestration layer.

## 7. Capabilities, Tools, And Execution Environments

### 7.1 Capability Catalogs

The default Main Page authoring catalog currently contains:

```text
general, writing, coding, testing, research
```

`StaticCapabilityCatalog` and `StaticAgentCapabilityCatalog` support authoring
and publish validation. They are not a dynamic Agent descriptor registry.

The sidecar directly constructs concrete Default Agent tools and mounts them in
`LocalRuntime`. Current code has no global `ToolRegistry.tools`,
`compatible_tools`, or Agent graph tool-set compiler of the form described by
the original document.

### 7.2 Local ExecutionEnv Compatibility

`InMemoryExecutionEnvRegistry` implements `upsert`, `get`, `list`, and
`find_compatible`. An environment is compatible when:

- it is `online`;
- its capabilities include the request's `required_capability`;
- non-empty requested `allowed_tools` are a subset of its tool pool.

Sidecar assembly creates the local `local-default` environment. Service DTOs
already include `last_heartbeat_at`, `active_execution_id`, `TaskLease`,
`claimed`, and `lease_expired` vocabulary, but the current service has no
remote environment registration, claim, lease issue/renew/revoke/expire, or
heartbeat endpoint.

## 8. UI And API Surface

Main Page currently displays Plan/Task structure, execution status, ASK,
confirmation, messages, activity, results/errors, audit evidence, and stop/retry
actions.

`TaskNodeCardView` has no assignment, assigned Agent, `claimed_by`, or Agent
health field. The frontend has no:

- Agent graph editor;
- Agent node palette or edge configuration;
- AgentPool / worker list;
- Task assignment or reassignment controls;
- per-node autonomy slider;
- parallel branch monitor;
- multi-Agent handoff timeline.

Local Execution Plane HTTP routes publish/query/cancel/retry Tasks and read
events/results/errors/evidence. They do not expose an Agent Manager or remote
worker control plane.

## 9. Concurrency, Isolation, And Recovery

### 9.1 Current Guarantees

- execution tools are scoped to the selected workspace root;
- Task, ASK, message, context, event, and authoring facts are isolated by
  workspace/Session identifiers and stores;
- the fixed-route dispatcher coalesces duplicate triggers for a Session;
- a child Task cannot be claimed until its parent is `done`;
- retry preserves Task identity while clearing current claim, wait, result,
  error, and interruption runtime facts;
- running interruption is cooperative and checked at runtime safe points;
- startup recovery can converge stale running Tasks that already carry an
  interruption request.

### 9.2 Guarantees That Do Not Yet Exist

- locking, branch isolation, or merge protocol for multiple workspace writers;
- distributed exactly-once execution;
- Agent lease, heartbeat, and stale worker reclaim;
- parallel child result merge and conflict resolution;
- general restoration of run-local LLM transcript after an Agent crash;
- atomic transactions spanning Task, message, ASK, and context stores.

Parallel multi-Agent workspace writes require an explicit ownership, isolation,
merge, and replay contract before increasing worker count.

## 10. Accepted Future Dynamic Routing Direction

ADR-0011 and ADR-0012 accept a TaskBus-centered convergence model:

```text
pending unassigned Task
  -> Router observes Task + Agent descriptors
  -> Routing Agent policy proposes AssignmentCommand
  -> TaskBus validates and stores assignment fact
  -> Agent Manager observes pending assigned Task
  -> Agent Manager creates/selects runtime instance
  -> assigned Agent claims Task
  -> Agent run reports complete / fail / wait
```

The accepted direction says:

- Router owns assignment strategy, not Task lifecycle;
- TaskBus remains the Published Task lifecycle and assignment-fact authority;
- Agent Manager creates/selects runtime instances without becoming another Task
  store;
- assignment refers to Agent identity/template/capability, not a temporary run;
- the first design does not add a separate `assigned` status;
- retry clears assignment and current-attempt runtime facts;
- an initial implementation may use one Router loop and one Agent Manager loop
  per TaskBus;
- assigned-only claim, stale-pending sweep, audit, and UI projection must land
  with assignment;
- the first assignment UI should project state without manual reassignment.

This is accepted design, not shipped behavior. Current source has no production
`AssignmentCommand`, `assigned_agent_id`, `claim_assigned`, or Agent Manager.

## 11. Minimum Preconditions For Dynamic Multi-Agent Execution

1. Add auditable assignment facts and idempotent commands to TaskBus
   model/store boundaries.
2. Define stable relations between Agent descriptor, template identity, runtime
   instance, and run id.
3. Implement the Router observation/command loop with deterministic fallback.
4. Implement Agent Manager health/lifecycle convergence and assigned-only claim
   validation.
5. Validate capability, tools, permissions, workspace scope, and Agent identity
   together.
6. Add lease, heartbeat, fencing, and stale recovery for remote or concurrent
   execution.
7. Define serial, isolated-branch, or merge behavior for workspace writers.
8. Define delegation, result, failure, cancellation, and audit schemas between
   Agents.
9. Extend UI contracts to project assignment and health before adding manual
   reassignment.
10. Add cross-process race, duplicate delivery, worker crash, and recovery
    tests.

## 12. Current Non-Facts

| Original concept or target | Current status |
|---|---|
| Running Planner -> Executor -> Auditor graph | Not implemented |
| LLM Orchestration Designer producing a valid Agent DAG | Not implemented |
| `OrchestrationDraft`, `ConstraintProfile`, `OrchestrationConfig` | No current source models |
| Auto-pilot / Co-pilot / Manual / Audit-Focus orchestration presets | Not implemented; distinct from CLI autonomy presets |
| No backend validation is needed because constraints are in the prompt | Not a current invariant; existing command/publish paths validate input |
| Every Agent action passes through Main Page AutonomyGate | False |
| Maximum autonomy makes every actionable non-blocking | False; explicit ASK/confirmation can wait |
| MessageStream is the sole Agent/user collaboration channel | False; it is one user-facing surface among domain stores and commands |
| ToolRegistry dynamically assigns tools to Agent node types | Not implemented |
| Dynamic Agent assignment or reassignment | Not implemented |
| Generic child Agent spawn, handoff, and result aggregation | Not implemented |
| Parallel Agents write one workspace with conflict handling | Not implemented |
| Remote multi-ExecutionEnv worker pool | Not implemented |
| `Orchestrator` participates in runtime execution | False; placeholder only |
| “v1 high guardrails” Planner/Executor/Auditor topology is current | False |

## 13. Evidence Index

Execution and TaskBus:

- `src/taskweavn/task/execution.py`
- `src/taskweavn/task/models.py`
- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_agent.py`

Specialized roles:

- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/task/collaborator_loop.py`
- `src/taskweavn/task/collaborator_profile_runner.py`
- `src/taskweavn/task/collaborator_workspace_context.py`
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/runtime_input_llm_router.py`
- `src/taskweavn/server/read_only_inquiry.py`
- `src/taskweavn/server/read_only_inquiry_answer_provider.py`
- `src/taskweavn/llm/agent_config.py`

Interaction and extension boundaries:

- `src/taskweavn/interaction/message.py`
- `src/taskweavn/interaction/bus.py`
- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/interaction/gate.py`
- `src/taskweavn/orchestration/protocol.py`
- `src/taskweavn/execution_plane/models.py`
- `src/taskweavn/execution_plane/env_registry.py`
- `src/taskweavn/execution_plane/embedded_service.py`

UI contracts:

- `src/taskweavn/task/views.py`
- `src/taskweavn/server/ui_contract/view_models.py`
- `frontend/src/shared/api/types.ts`
- `frontend/src/pages/main-page/TaskNodeCard.tsx`
- `frontend/src/pages/main-page/MainPageDetailPanel.tsx`

Targeted tests:

- `tests/test_fixed_route_task_executor.py`
- `tests/test_task_bus_lifecycle.py`
- `tests/test_sqlite_task_bus.py`
- `tests/test_collaborator_authoring_service.py`
- `tests/test_collaborator_authoring_loop_contract.py`
- `tests/test_runtime_input_router.py`
- `tests/test_execution_plane_service.py`
- `tests/test_main_page_sidecar_app.py`

## 14. Calibration Rule

Before promoting a future multi-Agent statement to current fact, verify:

1. whether the named thing is a role/profile/metadata record or a Task-claiming
   runtime Agent;
2. whether model, store, command, service, assembly, UI, and tests form a
   complete path;
3. which authority owns assignment, claim, run, and result facts;
4. whether parallel execution has workspace isolation, lease, and recovery;
5. whether accepted ADR direction has actually landed in production source.

Future design becomes current architecture only when that evidence chain exists.
