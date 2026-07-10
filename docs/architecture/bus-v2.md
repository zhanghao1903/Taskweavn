# TaskBus v2 Architecture Memo

> Status: future design reference / not current runtime
> Last Updated: 2026-07-10
> Scope: future scheduling, concurrency, IO-scope, and multi-env evolution
> Related: [bus](bus.md), [task](task.md),
> [Execution Plane service memo](taskbus-service-multi-execution-env.md),
> [agent](agent.md), [tool capability layer](tool-capability-layer.md),
> [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md),
> [ADR-0020](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)
>
> 2026-07-10 fact calibration: This document is not an implementation status
> report. The current codebase has no `TaskBusV2`, LLM execution scheduler,
> `IOScope`, `acquire_io`, `release_io`, `max_concurrent` TaskBus enforcement,
> TaskBus assignment API, worker lease protocol, or EventStream-backed TaskBus
> replay. Current local execution is TaskBus + fixed-route dispatcher /
> embedded runtime handlers. `TaskLease` and `lease_expired` exist only as
> Execution Plane DTO/future-service shapes.

---

## 1. Purpose

`bus-v2.md` is a future design reference for moving beyond the current local
fixed-route execution path. It does not replace [bus.md](bus.md), which is the
current TaskBus fact document.

The original v2 thesis remains useful:

```text
Future TaskBus / Execution Plane evolution
  -> smarter scheduling
  -> bounded concurrency
  -> explicit workspace/tool conflict model
  -> service-compatible execution environments
  -> auditable scheduling decisions
```

But the current baseline must be stated accurately before any v2 planning:

```text
Current Product 1.1 local execution
  -> TaskBus.publish / claim_next / complete / fail / wait / resume
  -> FixedRouteExecutionDispatcher serializes the local product path per Session
  -> TaskBus itself has no global running_task lock
  -> Execution Plane is embedded/local, not remote multi-env
  -> EventStream is read-side/audit/evidence, not TaskBus lifecycle truth
```

---

## 2. Current Baseline Facts

### 2.1 TaskBus current API

Current TaskBus owns PublishedTask lifecycle through:

```text
publish
claim_next
complete
fail
wait_for_user
wait_for_confirmation
resume_after_user
resume_after_confirmation
skip
retry
request_interrupt
recover_interrupted_running_tasks
get / list_for_session / list_children
```

Current TaskBus does **not** expose:

```text
assign
claim_assigned
sweep_stale_pending_tasks
acquire_io
release_io
running_tasks
concurrency_level
force_decide
TaskBusV2 scheduler hooks
```

### 2.2 Current storage

Current implementations are:

- `InMemoryTaskBus`, with `_tasks` and `_children` maps;
- `SqliteTaskBus`, with a workspace-level `tasks` table and full `TaskDomain`
  JSON payload.

Current main app assembly creates:

```python
task_bus = SqliteTaskBus(layout.workspace_tasks_db)
```

Task rows are scoped by `session_id`. There is no `TaskBus(session_id,
event_stream)` lifecycle materialized view.

### 2.3 Current scheduling path

The current fixed-route executor:

1. lists TaskBus tasks for a session;
2. finds the first pending root or child whose parent is done;
3. calls `claim_next(session_id, capability, agent_id)`;
4. runs the resident Default Agent task-scoped run;
5. reports `complete`, `fail`, or waiting lifecycle back to TaskBus.

`FixedRouteExecutionDispatcher` coalesces dispatch requests and prevents a
duplicate concurrent drain for the same session. That is the current product
serial lane.

TaskBus itself does not reject a second eligible root task merely because
another task is already `running`. It validates pending status, capability, and
parent readiness.

### 2.4 Current Execution Plane

Execution Plane foundation exists, but only as local embedded infrastructure:

- service DTOs: `TaskRequest`, `TaskExecution`, `TaskEvent`, `TaskResult`,
  `TaskError`, `EvidenceRef`, `ExecutionEnv`, `CapabilityPolicy`, `TaskLease`;
- `EmbeddedTaskApiService` over current TaskBus;
- `SqliteExecutionPlaneStore`;
- local HTTP shell over `TaskApiService`;
- in-memory local `ExecutionEnvRegistry`;
- optional local WeChat send runtime handler.

There is no remote execution-env registration API, worker claim loop, lease
store, heartbeat protocol, callback delivery, or multi-env scheduler.

---

## 3. What v2 Is Not

TaskBus v2 should not be treated as any of these current facts:

| Not current | Correct status |
|-------------|----------------|
| LLM scheduler for execution Tasks | Future design only. Runtime Input Router is user-input/contract routing, not Task execution scheduling. |
| `IOScope` / IO guard | No current model or TaskBus API. Existing tool/file evidence is projection/audit, not concurrency control. |
| `max_concurrent` TaskBus enforcement | No current TaskBus setting or enforcement. |
| Agent assignment / `claim_assigned` | Future dynamic routing foundation. |
| Distributed lease / heartbeat | DTO shape only; no lease protocol. |
| EventStream as TaskBus source of truth | False currently; TaskBus store owns lifecycle. |
| Scheduler rationale written to EventStream | Future observability direction only. |
| Multi-env service | Future service mode; current env registry is local in-memory. |

---

## 4. v2 Design Goals

A future v2 should solve problems that the current local fixed-route path does
not try to solve:

1. choose work using more context than `created_at` and capability;
2. run safe independent work concurrently;
3. avoid workspace/file/tool conflicts before they happen;
4. route work to explicit execution environments;
5. make scheduling decisions auditable;
6. degrade to the current deterministic path when scheduler intelligence fails;
7. preserve TaskBus lifecycle authority.

The goal is not "LLM everywhere". The goal is to add intelligence only where the
queue, dependency, env, or conflict shape has become too complex for the
current fixed-route path.

---

## 5. Future Scheduling Layer

### 5.1 Scheduler inputs

A future scheduler may consume:

```python
@dataclass(frozen=True)
class SchedulingContext:
    pending_tasks: tuple[TaskDomain, ...]
    running_tasks: tuple[TaskDomain, ...]
    execution_envs: tuple[ExecutionEnv, ...]
    recent_lifecycle_events: tuple[object, ...]
    workspace_conflict_summary: object | None
    user_active_intent: str | None
    policy: object
```

This is a future shape. No current code builds or consumes this object.

### 5.2 Scheduler outputs

Future scheduler decisions should be command-like and auditable:

```python
@dataclass(frozen=True)
class SchedulingDecision:
    actions: tuple[ScheduleAction, ...]
    rationale: str
    fallback_safe: bool

@dataclass(frozen=True)
class DispatchAction(ScheduleAction):
    task_id: str
    env_id: str
    expected_cost_ref: str | None = None

@dataclass(frozen=True)
class HoldAction(ScheduleAction):
    task_id: str
    reason: str
```

Do not let the scheduler directly mutate TaskBus rows. It should submit commands
to the lifecycle authority, and those commands must be validated by TaskBus or
Execution Plane service boundaries.

### 5.3 Degradation rule

The current path must remain the fallback:

```text
if scheduler unavailable or disabled:
  use fixed-route capability/parent readiness path
```

The fallback is not optional. v2 scheduling is an optimization layer, not a new
source of lifecycle truth.

---

## 6. Future Concurrency Model

### 6.1 Why concurrency is not current

The older memo argued that most latency sits in LLM calls while file IO is
short. That may be true in some workflows, but the current implementation does
not yet have the safety machinery required to exploit it.

Before concurrency can be enabled, the system needs:

- workspace isolation or a precise conflict model;
- tool-level read/write declarations;
- result/evidence causality for concurrent runs;
- cancellation and retry semantics under partial progress;
- UI projection for multiple running tasks;
- tests for conflict, deadlock, and recovery.

### 6.2 IOScope as future model

`IOScope` remains a useful future concept:

```python
@dataclass(frozen=True)
class IOScope:
    reads: frozenset[str]
    writes: frozenset[str]
```

Conflict rule:

```text
A.writes intersects B.writes -> conflict
A.writes intersects B.reads  -> conflict
A.reads intersects B.reads   -> safe
```

This is not implemented today. Current file-change and EventStream projections
describe what happened; they do not reserve future IO or prevent conflicts.

### 6.3 Safer intermediate stage

Before LLM scheduling or multi-worker execution, a lower-risk v1.5 could be:

```text
Task/tool IO declaration only
max_concurrent remains 1
no behavior change
collect conflict telemetry
```

That would validate whether declared scopes are accurate before using them to
allow concurrent writes.

---

## 7. Future ExecutionEnv And Lease Layer

Execution Plane DTOs already include service-facing concepts:

- `ExecutionEnv`;
- `TaskExecution.env_id`;
- `TaskExecution.lease_id`;
- `TaskLease`;
- statuses such as `claimed` and `lease_expired`.

These are not runtime protocols yet. To make them real, a future slice must add:

1. durable env registry;
2. authenticated env registration;
3. claim endpoint;
4. lease issuance and renewal;
5. heartbeat and draining/offline behavior;
6. lease expiry recovery;
7. idempotent result/evidence submission against a lease;
8. diagnostics and user-visible projection.

Only after that should v2 talk about multi-env concurrency as implemented
behavior.

---

## 8. Event And Audit Boundary

Future v2 decisions should be auditable. That does not mean EventStream is the
TaskBus lifecycle source of truth.

Current boundary:

```text
TaskBus store
  -> lifecycle truth

EventStream / MessageStream / ExecutionPlaneStore / result summaries / audit projections
  -> read-side evidence and user/audit views
```

Future v2 may add scheduling and IO-conflict events, for example:

```text
SchedulingDecisionRecorded
DispatchHeld
IoLeaseRequested
IoLeaseDenied
IoLeaseReleased
```

Those events should explain decisions and support audit. They should not create
a second lifecycle authority.

---

## 9. Relationship To ADRs

### 9.1 ADR-0012

ADR-0012 accepted a TaskBus-centered convergence model for future assignment.
It explicitly avoids locks, leases, task versions, and distributed-router
coordination for the first assignment implementation.

Fact calibration:

- accepted direction: Router / Agent Manager can observe TaskBus and submit
  commands;
- current implementation: no Router assignment, no Agent Manager, no
  `assign`, no `claim_assigned`, no stale pending sweep.

### 9.2 ADR-0020

ADR-0020 accepts the Execution Plane as a service-capable boundary. It also
describes claim/lease/heartbeat as service-mode responsibilities.

Fact calibration:

- accepted direction: embedded now, service later;
- current implementation: embedded `TaskApiService`, local HTTP shell,
  local in-memory env registry, no distributed worker protocol.

---

## 10. Risk Controls Before Implementation

Do not implement broad v2 behavior until these controls exist:

| Control | Why it matters |
|---------|----------------|
| Deterministic fallback | Scheduler failure must not block execution. |
| Durable TaskBus lifecycle tests | v2 must preserve existing publish/claim/wait/resume/retry/interrupt behavior. |
| Conflict model tests | Concurrency without conflict tests will corrupt workspaces. |
| Env lease tests | Remote workers need duplicate claim and expiry coverage. |
| Redacted evidence policy | Concurrent tool/runtime evidence may contain sensitive payloads. |
| UI multi-running projection | Users need to understand concurrent work and stop/confirm per task. |
| Observability | Scheduler and IO decisions need traceable rationale. |

---

## 11. Recommended Evolution Path

A safer route is:

1. keep current TaskBus/fixed-route behavior stable;
2. document and test current Execution Plane embedded service;
3. add read-only IO declaration metadata without concurrency;
4. project IO/conflict telemetry for real runs;
5. introduce durable ExecutionEnv registry;
6. implement lease/heartbeat for one local worker path;
7. add bounded concurrency for read-only or isolated tasks;
8. add scheduler decision records with deterministic fallback;
9. evaluate LLM scheduling only after deterministic scheduling and conflict
   data show real need.

This order keeps each slice testable and reversible.

---

## 12. Decision Summary

| Decision | Current fact | Future v2 direction |
|----------|--------------|---------------------|
| Lifecycle authority | TaskBus store | Keep TaskBus/service command validation authoritative |
| Scheduler | Fixed-route executor selects eligible pending Task | Add deterministic then optional LLM scheduler |
| Concurrency | Product path serial per Session; TaskBus has no global lock | Add bounded concurrency only after conflict model |
| IO conflicts | Observed after tool execution through evidence/projections | Add declared IO scopes and guard |
| Assignment | Not implemented | Router/Agent Manager commands after product need |
| Lease | DTO only | Durable claim/renew/expire protocol |
| EventStream | Audit/evidence/read-side source | Add scheduling/IO decision events without making it lifecycle truth |
| ExecutionEnv | In-memory local compatibility check | Durable env registry and remote workers later |

---

## 13. Summary

TaskBus v2 is still a useful design direction, but it is not current runtime
fact. The current system has a small TaskBus lifecycle authority, a fixed-route
local execution path, and an embedded Execution Plane foundation.

Future v2 work should proceed only as evidence-backed slices:

```text
declare and observe conflicts first,
make env/lease semantics durable second,
enable bounded concurrency third,
add LLM scheduling last.
```

That preserves the current system's strongest property: one clear lifecycle
authority with testable transitions.
