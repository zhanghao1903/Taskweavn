# ADR-0011: Routing Agent Assignment And Cooperative Interruption

> Status: accepted
> Date: 2026-05-22
> Related: [Task](../architecture/task.md), [TaskBus](../architecture/bus.md), [Agent](../architecture/agent.md), [UI / Backend Communication](../architecture/ui-backend-communication.md), [Workflow Session Task UX Model](../product/workflow-session-task-ux-model.md), [Gap Registry](../gaps/)

---

## Context

TaskBus now owns the minimal published Task lifecycle:

```text
pending -> running -> done / failed
```

The next Product 1.0 gap is assignment: deciding which Agent should execute a
pending Task. A simple matcher inside TaskBus would be easy to implement, but
it would freeze routing strategy too early.

Routing may need to consider:

- required capability;
- required or preferred Agent;
- tool permissions;
- user or workflow policy;
- cost and latency;
- task risk;
- current Agent availability;
- historical success rate;
- custom strategies written by advanced users.

The system also needs user interruption. A user can request stop while a Task is
pending, running, or waiting inside an Agent/runtime. TaskBus can record this
intent, but only the executing Agent/runtime knows where a safe interruption
point exists.

---

## Decision

Route Tasks through a **Routing Agent** instead of hardcoding routing strategy
inside TaskBus.

The responsibility split is:

```text
Routing Agent = assignment strategy
TaskBus = assignment and lifecycle state authority
Execution Agent = task execution and safe-point behavior
```

Routing Agent may use hard rules, LLM reasoning, fallback strategies, or
advanced user configuration. It cannot directly mutate Task state. It submits
an assignment command:

```text
AssignmentCommand(
  session_id,
  task_id,
  assigned_agent_id,
  assigned_by,
  rationale
)
```

TaskBus validates and records assignment on `TaskDomain`. Assignment is a Task
execution fact, not only an external hint.

Execution Agent can only claim a Task assigned to itself. Task handoff is a
Routing Agent responsibility, not an Execution Agent responsibility.

Pending Tasks may be reassigned before claim. Running, done, and failed Tasks
cannot be reassigned.

Interruption is cooperative by default:

```text
User/system requests stop
  -> TaskBus records interrupt intent
  -> Agent/runtime observes intent
  -> Agent stops at a safe point
  -> Agent reports terminal outcome
```

TaskBus does not hard-kill running actions. Hard cancellation is a
runtime/tool-specific best-effort capability.

---

## Consequences

Positive:

- Routing strategy becomes pluggable without weakening TaskBus consistency.
- Product 1.0 can ship with a conservative default Routing Agent.
- Advanced users can later replace or configure Routing Agent behavior.
- TaskBus remains a small state authority instead of an LLM scheduler.
- Assignment facts are replayable and auditable.
- User stop requests are honest: UI can show "stopping" until Agent/runtime
  acknowledges a safe point.

Trade-offs:

- Assignment requires an additional command path and event.
- A default Routing Agent is now required for real execution.
- UI may need a routing notice surface for unassigned Tasks.
- Some running actions may not stop immediately, because safe points are owned
  by Agent/runtime.

Rejected alternatives:

- **TaskBus internal matcher:** too rigid and likely to grow into a hidden
  scheduler.
- **Execution Agent self-handoff:** makes routing implicit and hard to audit.
- **Immediate UI-driven running-state mutation on stop:** can diverge from real
  runtime side effects.
- **New `blocked` / `paused` / `cancelled` execution states in Product 1.0:**
  premature; use `pending` plus routing notice or `failed` with cancellation
  reason until product evidence requires more states.
