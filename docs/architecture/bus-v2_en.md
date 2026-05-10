# TaskBus v2 Architecture Design

> Extension proposal · LLM scheduling + bounded concurrency · 2026-05-09

---

## 0. What This Is

`bus.md` defines the v1 TaskBus: FIFO, serial execution, capability matching. This document describes a v2 direction that keeps the same core abstractions but gives the bus more intelligence.

The key insight is that **LLM calls are the main latency bottleneck**, not workspace I/O. Therefore, v2 should explore parallel LLM execution while keeping tool-side conflicts controlled.

---

## 1. Definition Upgrade

TaskBus v2 is no longer just a FIFO queue. It becomes:

```
TaskBus v2 =
  Task state authority
  + LLM-assisted scheduler
  + bounded concurrency controller
  + IOScope conflict gate
  + audit trail for scheduling rationale
```

It still remains a Session-scoped component and still owns Task state transitions.

---

## 2. Difference From v1

| Dimension | v1 | v2 |
|-----------|----|----|
| Scheduling | FIFO + capability match | LLM-assisted scheduling with fallback |
| Concurrency | one running task | bounded concurrent LLM execution |
| Conflict control | avoided by serial execution | controlled through `IOScope` |
| Explanation | implicit | every scheduling decision has rationale |
| Fallback | not needed | can fall back to v1 behavior |

v2 should be a superset, not a replacement. Setting `max_concurrent=1` and disabling LLM scheduling should recover v1 behavior.

---

## 3. LLM-Driven Scheduler

### 3.1 Why Use an LLM for Scheduling

Task routing often requires semantic judgment:

- Which pending task best advances the user's current goal?
- Should a validation task run before a risky write?
- Should similar tasks be grouped?
- Should the bus wait for more context instead of dispatching immediately?

Rules can encode simple matching, but an LLM can reason over intent, history, and risk.

### 3.2 Scheduler Input

The scheduler receives a structured snapshot:

```python
@dataclass
class SchedulingContext:
    pending_tasks: list[TaskSummary]
    running_tasks: list[TaskSummary]
    agent_templates: list[AgentTemplateSummary]
    recent_events: list[EventSummary]
    workspace_summary: WorkspaceSummary
    session_config: SessionConfig
    budget_state: BudgetState
```

The input is bounded and summarized. The scheduler should not receive the whole workspace or full transcript by default.

### 3.3 Scheduler Output

```python
@dataclass
class SchedulingDecision:
    action: Literal["dispatch", "hold", "reprioritize", "merge_proposal"]
    task_id: TaskId | None
    agent_template_id: str | None
    rationale: str
    confidence: float
```

Every decision must include `rationale`. This rationale is written to EventStream.

### 3.4 Scheduler Loop

1. Build SchedulingContext.
2. If the situation is simple, use deterministic v1 scheduling.
3. If ambiguity or risk exists, ask the LLM scheduler.
4. Validate the decision structurally.
5. Apply it or fall back to v1.
6. Emit `SchedulingDecisionEvent`.

### 3.5 Cost Control

The scheduler itself consumes tokens. It should not run for every trivial step. Triggers:

- multiple eligible tasks;
- risk-sensitive task;
- budget pressure;
- user changed autonomy settings;
- repeated failures.

### 3.6 Degradability

LLM scheduling must be optional. If it fails, times out, or exceeds budget, TaskBus should fall back to deterministic v1 scheduling.

---

## 4. Concurrency Model

### 4.1 Re-evaluating the Serial Constraint

V1 serial execution was chosen for simplicity. The important new observation is:

```
LLM reasoning often dominates wall-clock time.
Tool I/O and workspace writes are usually a small fraction.
```

Therefore, parallel LLM calls can significantly reduce total time even if tool writes remain controlled.

### 4.2 Core Idea

Separate execution into two domains:

```
LLM reasoning domain: can run concurrently
Tool / workspace I/O domain: protected by IOScope checks
```

This allows concurrency where it matters while preserving correctness where conflicts actually occur.

### 4.3 IOScope

`IOScope` describes what a task or tool may read and write:

```python
@dataclass(frozen=True)
class IOScope:
    reads: set[PathPattern]
    writes: set[PathPattern]
    external_effects: set[str]
```

Two running tasks conflict if their write scopes overlap or if one writes what the other reads in a way the policy forbids.

### 4.4 Where IOScope Comes From

Preferred sources:

1. static tool declarations;
2. task-level declarations;
3. Agent runtime `acquire_io` calls before side-effecting tools;
4. conservative fallback: unknown write scope conflicts with everything.

### 4.5 Conflict Strategy

Use two layers:

- **Predictive scheduling:** the scheduler tries not to run conflicting tasks together.
- **Runtime gate:** tool execution must acquire IOScope; if denied, the task waits or fails according to policy.

### 4.6 Concurrency Limit

Default should be conservative:

```yaml
taskbus:
  max_concurrent: 4
  llm_scheduler: auto
  io_conflict_policy: wait
```

`max_concurrent=1` returns to v1.

---

## 5. Re-evaluating Agent Affinity and Cache

### 5.1 Real Prompt Cache Model

Prompt cache hit depends on **identical prefix**, not on keeping the same Agent object alive.

Stable cacheable parts:

- system prompt;
- developer instructions;
- tool schemas;
- template-level user prompt prefix.

Unstable parts:

- workspace-specific context;
- recent tool results;
- task-specific intent;
- dynamic summaries.

### 5.2 Stateless Agents Are Not a Cache Disaster

If multiple AgentInstances come from the same AgentTemplate, their stable prefixes can still match. Destroying an Agent instance does not necessarily destroy prompt cache opportunity at the API layer.

### 5.3 Warm Pool Is Not State Retention

The system may preload templates or keep model clients warm without preserving task memory. This improves latency while keeping Agents stateless.

### 5.4 What Actually Hurts Cache Hit Rate

Workspace-specific context and changing tool results are more likely to break prefix equality than Agent instance churn.

Conclusion: v2 does **not** need to abandon stateless Agents.

---

## 6. Core API

```python
class TaskBusV2(TaskBus):
    def schedule(self) -> list[SchedulingDecision]: ...
    def acquire_io(self, task_id: TaskId, scope: IOScope) -> IOLease: ...
    def release_io(self, lease: IOLease) -> None: ...
    def set_concurrency(self, max_concurrent: int) -> None: ...
```

The existing v1 API remains valid.

---

## 7. Simplified Scheduling Pseudocode

```python
def tick():
    refresh_completed_tasks()

    while running_count < max_concurrent:
        candidates = eligible_pending_tasks()
        if not candidates:
            return

        if should_use_llm_scheduler(candidates):
            decision = llm_scheduler.decide(context())
        else:
            decision = fifo_decision(candidates)

        if not validate(decision):
            decision = fifo_decision(candidates)

        if conflicts_with_running(decision.task_id):
            hold(decision.task_id)
            return

        dispatch(decision.task_id, decision.agent_template_id)
```

---

## 8. Relationships With Other Components

| Component | v2 Relationship |
|-----------|-----------------|
| Task | may include estimated IOScope and scheduling metadata |
| Agent | remains stateless; requests IO leases before side effects |
| Session | owns max concurrency and scheduler configuration |
| EventStream | records scheduler input summary and rationale |
| Cost system | budgets scheduler calls and concurrent LLM usage |
| Observability | exposes scheduling traces and IO wait graphs |

---

## 9. Design Philosophy

### 9.1 v1 Is Skeleton, v2 Is Muscle

V1 proves the minimal model. V2 adds power only where user experience needs it.

### 9.2 Intelligence Must Be Degradable

LLM scheduling is useful only if the system still works when it fails.

### 9.3 Concurrency Is a Tool, Not an Identity

The architecture should support bounded concurrency without becoming a fully concurrent system everywhere.

### 9.4 Scheduling Must Be Explainable

The scheduler is allowed to be smart, but not silent. Every non-trivial decision needs a rationale.

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LLM scheduler makes bad choices | fallback to v1, validate output, log rationale |
| IOScope declarations are wrong | conservative defaults, runtime checks |
| concurrency creates hidden conflicts | IO leases and EventStream tracing |
| scheduler cost grows | trigger-based invocation and budget integration |
| debugging becomes harder | visual scheduling trace |

---

## 11. Gradual Adoption Path

1. Stabilize v1.
2. Add IOScope declarations but keep `max_concurrent=1`.
3. Enable bounded concurrency with FIFO scheduling.
4. Add LLM scheduler in `auto` mode for ambiguous cases.
5. Expose scheduler rationale in UI and trace tools.

Each step should be independently useful and independently reversible.

---

## 12. Decision Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| Smart scheduling | LLM-assisted | semantic task routing matters |
| Safety | deterministic fallback | avoid black-box dependency |
| Concurrency | bounded | reduce wall-clock time without uncontrolled writes |
| Conflict model | IOScope | explicit read/write boundaries |
| Agent state | still stateless | cache does not require instance affinity |

---

## 13. Summary

TaskBus v2 keeps the core elegance of the v1 architecture but challenges one assumption: serial execution may be too conservative once real usage shows that LLM latency dominates. The proposed answer is not full concurrency; it is bounded LLM parallelism plus explicit IO conflict control, with LLM scheduling as an optional, auditable layer.
