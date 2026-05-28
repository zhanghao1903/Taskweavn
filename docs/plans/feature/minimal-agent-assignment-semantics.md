# Feature Plan: Minimal Agent Assignment Semantics

> Status: deferred
> Last Updated: 2026-05-28
> Gap: [Routing Agent assignment productization](../../gaps/README.md)
> Architecture: [Task](../../architecture/task.md), [TaskBus](../../architecture/bus.md), [Agent](../../architecture/agent.md)
> Decisions: [ADR-0011](../../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)
> Product: [Plato MVP PRD](../../product/plato-mvp-prd.md), [Main Page UX Flow](../../product/plato-main-page-ux-flow.md)
> Technical Design: [中文详细技术方案](minimal-agent-assignment-semantics-technical-design.zh-CN.md)
> Release Record: TBD

---

## 1. Problem / Gap

TaskBus now supports the basic execution lifecycle:

```text
pending -> running -> done / failed
```

It also records `claimed_by` when an Agent claims a Task. What is missing is the
minimal assignment layer between Published Tasks and execution:

```text
Published pending Task
  -> Router assigns an Agent identity
  -> Agent Manager creates an Agent instance and claims
  -> Agent instance executes and completes / fails
```

Without this layer, an Execution Agent can effectively pick work by capability
through `claim_next`, which bypasses the agreed routing model:

- Router should be the place where assignment facts are produced.
- TaskBus should validate assignment and claim facts.
- Agent Manager should own instance creation, not TaskBus or Router.
- Main Page should see assignment projection state from backend facts.
- Pending Tasks should not hang forever if Router or Agent Manager stops
  advancing them.

This plan records the Product 1.1+ routing foundation direction. It is no
longer a Product 1.0 implementation work package.

Product 1.0 follows ADR-0010 line-first defaults and should implement the
smaller [Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md)
instead.

---

## 2. Goals

Deliver the minimal semantics needed when Product 1.1+ introduces real routing:

1. Add assignment facts to Published Tasks without adding a new `assigned`
   status.
2. Add TaskBus commands for `assign`, assigned-only claim, stale pending sweep,
   and retry cleanup semantics.
3. Introduce a minimal Router service that observes pending unassigned Tasks and
   assigns Agent identities.
4. Introduce a minimal Agent Manager service that observes pending assigned
   Tasks, creates Agent instances, and claims execution.
5. Keep the first routing implementation single-instance: one Router loop and one Agent Manager loop
   per TaskBus instance.
6. Make stale pending Tasks degrade through TaskBus sweep into a normal failure
   path.
7. Project assignment facts to Main Page read models without exposing manual
   reassignment.
8. Cover in-memory and SQLite TaskBus behavior with deterministic tests.

---

## 3. Non-goals

- Do not implement the public Agent protocol.
- Do not implement special Agent protocols beyond the minimal interfaces needed
  by Router and Agent Manager.
- Do not implement skills integration, MCP integration, or multimodal support.
- Do not implement multi-router, multi-Agent-Manager, distributed workers,
  leases, locks, task versions, or compare-and-swap.
- Do not add a Task status named `assigned`.
- Do not implement Main Page manual reassignment.
- Do not implement running execution timeout, hard cancellation, or cooperative
  interruption behavior.
- Do not replace existing TaskPublisher retry behavior unless a future implementation
  explicitly chooses to add in-place retry later.

---

## 4. Design Direction

### 4.1 TaskBus-centered convergence

TaskBus remains the Published Task lifecycle authority. Router and Agent Manager
are convergence loops:

```text
Router tick:
  read pending unassigned Tasks
  choose assigned_agent_id
  call TaskBus.assign(...)

Agent Manager tick:
  read pending assigned Tasks
  create Agent instance
  call TaskBus.claim_assigned(...)
  start execution

TaskBus sweep:
  read stale pending Tasks
  fail(dispatch_timeout)
```

Router and Agent Manager do not take ownership of Task lifecycle after seeing a
Task. They only submit commands back to TaskBus.

### 4.2 Assignment is a fact, not a status

Use:

```text
pending + assigned_agent_id is not None
```

to mean "assigned and waiting for Agent Manager claim." Do not add an
`assigned` status.

### 4.3 Router contains policy, not all policy is Agent

Router is the runtime boundary. It may use a Routing Agent policy, but fixed
control behavior can stay in Router code:

```text
Router = deterministic runtime + optional Routing Agent policy
```

Examples of deterministic Router behavior:

- no-Agent fallback;
- assignment command construction;
- routing failure logging;
- choosing whether to skip a candidate Task for this tick;
- respecting required Agent constraints.

### 4.4 Agent Manager owns instance creation

TaskBus does not create Agent instances. Router does not create Agent instances.
Agent Manager resolves the assigned Agent identity, performs any minimal
preflight, creates the runtime instance, and only then claims the Task.

If startup fails, Agent Manager reports a normal Task failure through TaskBus.

### 4.5 Sweep replaces callback-dependent health

TaskBus should not rely on Router / Agent Manager callbacks to keep pending
Tasks healthy. It exposes a deterministic sweep:

```text
sweep_stale_pending_tasks(now) -> failed dispatch_timeout Tasks
```

The sweep uses one dispatch timeout for the first routing implementation. It does not distinguish
assignment timeout from claim timeout; logs and audit records carry details when
available.

---

## 5. Implementation Slices

### Slice 1 — Task assignment fields and TaskBus commands

Output:

- `TaskDomain` assignment fields:
  - `assigned_agent_id`;
  - `assigned_by`;
  - `assigned_at`;
  - `assignment_rationale`;
- TaskBus `assign`;
- TaskBus assigned-only claim path;
- retry cleanup helper or documented retry behavior;
- in-memory tests.

Acceptance:

- pending Task can be assigned;
- non-pending Task cannot be assigned;
- assigned Task can only be claimed by the assigned Agent;
- unassigned Task is not claimed by assigned-only claim;
- `pending + assigned_agent_id` does not create a new status.

### Slice 2 — SQLite persistence and migration

Output:

- SQLite schema columns for assignment facts;
- persistent `assign` and assigned-only claim;
- stale pending sweep persisted as `failed`;
- migration/backward-compatible table creation behavior;
- SQLite tests.

Acceptance:

- assignment facts survive reload;
- claim validation works against persisted assignment;
- sweep updates stale pending Tasks to failed with `dispatch_timeout`;
- existing published Task tests continue to pass.

### Slice 3 — Minimal Router runtime

Output:

- `Router` / `TaskRouter` service;
- Agent descriptor source interface;
- deterministic default policy for Product 1.0;
- optional Routing Agent policy interface shape;
- routing tick tests.

Acceptance:

- Router assigns pending unassigned Tasks to compatible Agent identities;
- Router respects hard required Agent constraints when present;
- Router does not mutate Tasks directly;
- Router is single-instance by design and does not add locks or leases.

### Slice 4 — Minimal Agent Manager runtime

Output:

- `AgentManager` service;
- Agent template registry / descriptor lookup;
- Agent instance factory interface;
- claim-and-start flow;
- startup failure -> TaskBus fail;
- tests with fake Agent instances.

Acceptance:

- Agent Manager observes pending assigned Tasks;
- creates instance before claim or claims only when startup can proceed,
  depending on the final technical design;
- reports startup failure through TaskBus fail;
- does not choose assignment.

### Slice 5 — Projection and Main Page semantics

Output:

- Task projection exposes assigned Agent display fields or badges;
- Main Page can render:
  - waiting for routing;
  - waiting for agent;
  - running;
  - dispatch timed out;
- no manual reassignment action.

Acceptance:

- UI ViewModel does not expose raw internal Router state;
- failed `dispatch_timeout` is visible as a user-readable failure reason;
- Main Page actions remain unchanged except retry where already supported.

### Slice 6 — Docs and release closure

Output:

- architecture docs updated if implementation changes exact API names;
- Gap Registry status updated;
- release record added;
- roadmap updated only if sequencing changes.

Acceptance:

- implemented behavior is traceable to this plan and ADR-0012;
- non-goals remain documented follow-ups.

---

## 6. Testing Strategy

Focused tests:

- `test_task_bus_assignment.py`
- `test_sqlite_task_bus_assignment.py`
- `test_task_router.py`
- `test_agent_manager.py`
- projection tests for assignment display and dispatch timeout.

Regression tests:

- existing TaskBus lifecycle tests;
- TaskPublisher retry tests;
- Main Page projection / UI contract mapping tests touched by assignment fields.

No browser validation is required unless frontend UI rendering changes in this
work package.

---

## 7. Open Follow-ups

Related 1.0 work:

- [Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md).

Not for this deferred plan:

- public Product 1.1 Agent protocol;
- custom user-created Router policies;
- multi-router coordination;
- manual reassignment;
- cooperative interruption;
- running timeout / hard cancellation;
- Result Packaging Agent execution semantics.
