# ADR-0012: TaskBus-Centered Agent Assignment Convergence

> Status: accepted
> Date: 2026-05-23
> Related: [Task](../architecture/task.md), [TaskBus](../architecture/bus.md), [Agent](../architecture/agent.md), [ADR-0011](ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [Gap Registry](../gaps/)

---

## Context

ADR-0011 established that assignment strategy belongs outside TaskBus and that
Routing Agent submits assignment commands instead of directly changing Task
state.

The implementation still needs minimal assignment semantics for Product 1.0:

- what TaskBus owns after a Task is published;
- whether Router or Agent Manager owns Task lifecycle;
- whether assignment needs a new Task status;
- how to avoid callback-heavy lifecycle handshakes;
- how pending Tasks degrade if Router or Agent Manager stops making progress.

The project should avoid complex bidirectional callback protocols. Systems with
many cross-component callbacks, handshakes, confirmations, cancellations, and
compensation paths are hard to debug and test. Product 1.0 should prefer a
small number of authoritative facts and deterministic convergence loops.

---

## Decision

Use a **TaskBus-centered convergence model** for minimal Agent assignment.

TaskBus remains the authority for Published Task lifecycle facts. Router and
Agent Manager observe TaskBus and submit commands that advance Task facts; they
do not own Task lifecycle.

```text
TaskBus = Published Task lifecycle facts and command validation
Router = observes pending unassigned Tasks and submits assignment
Agent Manager = observes pending assigned Tasks, creates Agent instances, and claims
Agent Instance = executes the claimed Task and reports complete / fail
```

Do not introduce a separate `assigned` Task status for Product 1.0.

```text
pending + no assigned_agent_id = waiting for routing
pending + assigned_agent_id    = waiting for Agent Manager / claim
running                        = Agent instance has claimed execution
done / failed / skipped        = terminal or user-selected outcome
```

Assignment points to an Agent identity / template / capability object, not a
runtime Agent instance. Agent is the reusable capability shape; runtime
execution creates a short-lived instance.

Use a Router runtime that may contain a Routing Agent policy:

```text
Router = deterministic routing runtime + optional Routing Agent policy
```

Deterministic responsibilities such as fallback flow, logging, retry cleanup,
and routing error recording do not have to be implemented by an LLM-powered
Routing Agent. The Routing Agent is the pluggable policy component inside the
Router boundary.

Published Tasks must be assigned before an Execution Agent can claim them.

```text
pending Task
  -> Router assigns Agent identity
  -> Agent Manager creates instance
  -> Agent Manager claims Task
  -> Agent Instance executes
```

Retry clears assignment and current attempt runtime facts. It returns the Task
to pending so Router can choose again.

Clear on retry:

- assignment;
- `claimed_by`;
- runtime timestamps for the current attempt;
- current failure reason/details.

Keep historical events, logs, and attempt counters.

For Product 1.0, use a single Router loop and a single Agent Manager loop per
TaskBus instance. Do not add locks, leases, task versions, compare-and-swap, or
distributed-router coordination until the product needs them.

TaskBus provides a deterministic sweep for stale pending Tasks instead of
per-task timers or callback-dependent health. The sweep collapses stale pending
work into a normal failure path.

```text
TaskBus.sweep_stale_pending_tasks(now)
  pending too long -> fail(dispatch_timeout)
```

The sweep does not need to distinguish assignment timeout from claim timeout in
Product 1.0. It should provide a reason when available; otherwise diagnosis
belongs to logs and audit records.

Agent Manager startup failure is also reported through normal `fail` semantics:

- assigned Agent missing;
- Agent preflight failed;
- instance creation failed;
- startup health failed.

Do not implement running execution timeout or hard interruption as part of
minimal assignment semantics. Running cancellation remains a cooperative
Agent/runtime capability.

Main Page 1.0 only displays assignment projection state. It does not provide
manual reassignment.

---

## Consequences

Positive:

- Task lifecycle has one authoritative owner after publish.
- Router and Agent Manager become simple convergence loops instead of lifecycle
  co-owners.
- Product 1.0 avoids callback-heavy handshakes, per-task timers, locks, leases,
  and optimistic versioning.
- Tests can be deterministic: create TaskBus facts, call router tick, call Agent
  Manager tick, call TaskBus sweep, assert resulting facts.
- Retry naturally re-enters routing and can recover from a bad assignment.
- Main Page can project user-readable routing/execution states from Task facts.

Trade-offs:

- A stale pending Task may fail by sweep rather than receiving a precise
  component-specific failure reason.
- Single Router and Agent Manager loops are a 1.0 scaling constraint.
- Logs and audit records become important for distinguishing Router failure
  from Agent Manager failure.
- Manual reassignment is intentionally deferred.

Rejected alternatives:

- **Router or Agent Manager owns lifecycle after taking a Task from TaskBus:**
  creates multiple lifecycle authorities and makes Main Page, audit, retry, and
  failure recovery ambiguous.
- **Callback-driven lifecycle handshakes:** too many failure paths for Product
  1.0; harder to debug and test than convergence over TaskBus facts.
- **Per-task timeout timers:** adds runtime complexity and timer failure modes;
  deterministic sweep is simpler.
- **New `assigned` status:** premature. `pending + assigned_agent_id` is enough
  until product evidence shows that assignment is a user-facing bottleneck.
- **Assignment versions / leases / locks:** unnecessary while Product 1.0 uses
  one Router loop and one Agent Manager loop per TaskBus instance.
- **Running timeout in this work package:** belongs with cooperative
  interruption and Agent runtime safety points.
