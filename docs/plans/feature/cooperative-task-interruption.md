# Feature Plan: Cooperative Task Interruption

> Status: planned
> Type: Product 1.0 minimal task control and execution safety
> Last Updated: 2026-06-02
> Decisions: [ADR-0011 Routing Agent Assignment And Cooperative Interruption](../../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md)
> Architecture: [Task](../../architecture/task.md), [TaskBus](../../architecture/bus.md), [Agent](../../architecture/agent.md), [Context Manager](../../architecture/context-manager.md), [UI / Backend Communication](../../architecture/ui-backend-communication.md)
> Related Plans: [Fixed-route Task Execution Bridge](fixed-route-task-execution-bridge.md), [Linear Authoring And Retry Recovery](linear-authoring-retry-recovery.md), [Context Manager Cache-Aware Rendering](context-manager-cache-aware-rendering.md)
> Technical Design: [Cooperative task interruption technical design](cooperative-task-interruption-technical-design.zh-CN.md)

---

## 1. Problem

Product 1.0 now has a fixed-route execution loop:

```text
PublishedTask
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Default Agent / AgentLoop
  -> TaskBus complete / fail
```

Users still need a truthful way to stop work that is pending or running.
TaskBus can record the stop intent, but it cannot safely kill an LLM request,
file write, shell command, or external API call. Only the executing
Agent/runtime knows the safe interruption points.

Without a minimal interruption contract:

- Main Page may show a cancel affordance that cannot be honored honestly;
- running Tasks can remain confusing when the user requests stop;
- retry/recovery cannot distinguish user-cancelled failure from ordinary
  runtime failure;
- Context Manager cannot reliably include interrupt facts in the next LLM
  input;
- Audit Page cannot explain the stop request and eventual Agent outcome.

---

## 2. Product 1.0 Decision

Product 1.0 uses cooperative interruption, not hard cancellation.

```text
User/system requests stop
  -> TaskBus records interrupt intent
  -> UI projects running Task as stopping
  -> Context Manager includes interrupt fact
  -> Agent/runtime observes intent at safe points
  -> Agent reports terminal outcome through TaskBus fail
```

PublishedTask domain status remains minimal:

```text
pending -> running -> done / failed
```

No Product 1.0 `paused` or `cancelled` PublishedTask status is added.
Cancellation is represented through:

- interrupt intent while a Task is still active;
- terminal `failed` outcome with an error reason prefixed by `cancelled:` or
  `skipped:`;
- UI projection labels and audit events.

---

## 3. Goals

1. Add a minimal TaskBus interrupt-intent contract.
2. Allow pending Tasks to stop immediately by transitioning to `failed` with a
   cancellation reason.
3. Allow running Tasks to remain `running` while projecting a `stopping`
   affordance until Agent/runtime acknowledgement.
4. Define Product 1.0 safe points for the fixed-route Default Agent path.
5. Ensure Context Manager can include interruption facts before the next LLM
   call and trigger cache-aware context deltas/checkpoints.
6. Preserve auditability: stop request, safe-point acknowledgement, and final
   outcome must be explainable.
7. Keep retry semantics compatible with in-place retry: a cancelled failed Task
   can later retry through the existing failed -> pending path when permitted.

---

## 4. Non-goals

- No hard kill of running LLM calls, shell commands, file writes, or external
  APIs.
- No new `paused` PublishedTask state.
- No new `cancelled` PublishedTask state.
- No pause/resume workflow.
- No complex recovery strategy for partially completed tools.
- No process tree management or OS-level signal handling.
- No multi-Agent handoff, Routing Agent behavior, or Agent Manager dependency.
- No global timeout scheduler.

---

## 5. Product 1.0 Scope

### In Scope

- TaskBus interrupt intent for active published Tasks.
- Pending Task immediate stop as terminal `failed`.
- Running Task cooperative stop request and UI `stopping` projection.
- Agent/runtime safe-point checks in the fixed-route Default Agent path.
- Context Manager `InterruptionContext` population.
- Audit/event evidence for request and terminal outcome.
- Focused unit/integration tests.

### Out Of Scope

- Hard cancellation.
- Background timeout sweep.
- Parallel Agent interruption coordination.
- External process cancellation guarantees.
- User-configurable interruption policy.
- Rich partial-result recovery.

---

## 6. Minimal Semantics

### 6.1 Interrupt Intent

Interrupt intent is a TaskBus control fact:

```text
task_id
session_id
requested_by: user | system
reason
requested_at
request_id
```

It is not itself a terminal state. It remains active until the Task reaches
`done` or `failed`.

### 6.2 Pending Task

If the Task is still `pending`, Product 1.0 can stop it immediately:

```text
pending + request stop
  -> failed
  -> error_ref = "cancelled: user requested stop before execution"
```

This avoids adding a `cancelled` status while still preserving user intent.

### 6.3 Running Task

If the Task is `running`, TaskBus records the interrupt intent but leaves the
domain status unchanged:

```text
running + request stop
  -> running with interrupt_requested=true
  -> UI projection: "Stopping..."
```

The executing Agent checks safe points and reports:

```text
fail(task_id, error_ref="cancelled: stopped at safe point before next tool call")
```

If the Agent finishes a non-interruptible action and completes successfully
before observing the intent, TaskBus may still accept `complete(...)`. Audit
must show that the stop request arrived but completion won the race.

### 6.4 Done / Failed Task

If the Task is already terminal, the stop request should be rejected as a
command error or treated as an idempotent no-op only if the command layer can
prove the same request was already recorded.

---

## 7. Safe Points

Product 1.0 safe points for the fixed-route Default Agent path:

- before each LLM call;
- after each LLM call returns and before tool dispatch;
- before each tool call;
- after each tool observation;
- before file write actions when the runtime can identify them;
- after shell command exit;
- while waiting for user confirmation or deferred action resolution;
- before starting the next Task from the fixed-route executor.

Safe points do not guarantee immediate stop. They guarantee the system has a
defined place to observe intent and stop before starting more work.

---

## 8. UI Projection

Product 1.0 should avoid adding a new canonical task status just for stopping.

The UI projection rule is:

```text
TaskDomain.status = running
interrupt_requested = true
  -> display label: "Stopping..."
  -> disable duplicate cancel
  -> keep detail/audit links available
```

Pending Tasks that stop immediately project as `failed` with cancellation copy
derived from the `cancelled:` reason.

Retry remains a separate permission. A cancelled failed Task can expose retry
if existing retry rules allow it.

---

## 9. Context Manager Interaction

Context Manager already has an `InterruptionContext` field. This feature makes
its source explicit.

When interrupt intent is active:

```python
InterruptionContext(
    requested=True,
    reason="user requested stop",
    requested_at=...
)
```

Cache-aware Context Manager rendering should treat interruption as a high-value
delta trigger:

```text
# Context Delta
Reason: interrupt_requested

- The user requested this Task to stop.
- Stop at the next safe point.
- Do not start new risky work unless needed to leave the workspace consistent.
```

The delta must be appended to the AgentLoop transcript, not inserted before the
stable prefix.

---

## 10. Implementation Slices

### C1. Docs And Contract

Current status: planned / this package.

Deliver:

- feature plan;
- technical design;
- feature index and gap registry links.

Acceptance:

- Product 1.0 scope is explicit;
- no hard cancel, no `paused`, no PublishedTask `cancelled` status;
- Context Manager and cache-aware rendering interaction is defined.

### C2. TaskBus Interrupt Intent

Deliver:

- TaskBus command to record interrupt intent;
- pending Task immediate terminal failure behavior;
- running Task interrupt-intent persistence;
- command error behavior for terminal Tasks;
- event/audit evidence for interrupt requests.

Acceptance:

- pending stop moves to `failed` with `cancelled:` reason;
- running stop keeps status `running` and records intent;
- repeated stop requests are deterministic;
- existing claim/complete/fail/retry behavior remains unchanged.

### C3. AgentLoop Safe-Point Checks

Deliver:

- interrupt checker dependency for AgentLoop or fixed-route executor;
- safe-point checks before LLM calls and tool dispatch;
- interrupted LoopResult or equivalent error observation;
- mapping from interrupted loop result to TaskBus `fail(...)`.

Acceptance:

- a running Task can stop before starting the next LLM/tool action;
- in-flight LLM/tool calls are not hard-killed;
- terminal failure reason uses `cancelled:` prefix;
- EventStream/Audit can explain where interruption was acknowledged.

### C4. Context Manager Source And Delta

Deliver:

- Task context source pulls active interrupt intent;
- `InterruptionContext` is populated for active running Tasks;
- cache-aware provider treats interrupt intent as a context delta/checkpoint
  trigger.

Acceptance:

- next governed LLM call sees the stop request;
- delta is appended to the transcript;
- stable prefix is not regenerated solely because stop was requested.

### C5. Main Page Command And Projection

Deliver:

- Main Page command path for stopping published pending/running Tasks;
- projection of running + interrupt intent as `Stopping...`;
- duplicate cancel disabled while stop is pending;
- failed cancellation copy from `cancelled:` reason.

Acceptance:

- UI does not promise immediate cancellation;
- pending stop updates immediately;
- running stop shows a visible stopping affordance until terminal outcome;
- retry remains governed by existing failed-task retry rules.

### C6. Tests And Docs Closure

Deliver:

- TaskBus tests;
- AgentLoop safe-point tests;
- Context Manager interruption source tests;
- projection/command tests;
- release/gap docs closure.

Acceptance:

- targeted backend tests pass;
- targeted frontend projection tests pass if UI is touched;
- `git diff --check` passes;
- gap registry status is updated after implementation acceptance.

---

## 11. Acceptance Criteria

This feature is accepted when:

1. Users can request stop for pending or running published Tasks.
2. Pending Tasks stop immediately as `failed` with a `cancelled:` reason.
3. Running Tasks record interrupt intent and project as `Stopping...`.
4. AgentLoop observes interrupt intent at Product 1.0 safe points.
5. Running Task acknowledgement reports terminal outcome through TaskBus.
6. Context Manager includes interruption facts in governed LLM input.
7. Audit evidence shows stop request, acknowledgement, and terminal outcome.
8. No hard cancel, `paused`, or PublishedTask `cancelled` status is introduced.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| UI implies immediate cancellation. | Use "Stopping..." copy and document cooperative behavior. |
| In-flight tool leaves partial side effects. | Do not hard-kill; stop only at safe points and preserve audit evidence. |
| TaskBus becomes responsible for runtime safety. | Keep TaskBus to intent and lifecycle authority only. |
| Context Manager cache optimization misses stop requests. | Treat interrupt intent as an explicit delta/checkpoint trigger. |
| Cancelled failure pollutes retry semantics. | Keep `cancelled:` reason visible and reuse existing retry permission rules. |

---

## 13. Later Expansion

Product 1.1+ may add:

- explicit cancellation status if product evidence requires it;
- hard-cancel best-effort support for selected runtime/tool classes;
- partial-result recovery;
- pause/resume;
- user-configurable interruption policy;
- multi-Agent interruption propagation;
- diagnostic views for stuck stopping Tasks.

