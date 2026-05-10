# TaskBus Architecture Design

> Core abstraction of the multi-agent collaboration architecture · v1.0 · 2026-05-08

---

## 1. Definition

**TaskBus is the coordination layer for all Tasks inside a Session.**

It is simultaneously:

- a producer-consumer queue;
- a scheduler;
- the authority for Task state transitions;
- the collaboration hub between users and Agents;
- the audit boundary for task-level events.

In v1, TaskBus is intentionally simple:

```
FIFO queue + capability matching + serial execution
```

---

## 2. Core Abstraction

### 2.1 Producer-Consumer Pipeline

Users and Agents publish Tasks. Agent instances consume Tasks. The bus sits between them and prevents direct coupling.

```
User / Agent -> publish(Task) -> TaskBus -> AgentInstance -> result
```

### 2.2 Serial Execution

At most one Task is `running` in a Session in v1. This is the enforcement point for the single Workspace constraint.

### 2.3 Capability Matcher

The bus matches `task.required_capability` with registered AgentTemplates. It does not inspect natural-language intent deeply in v1.

### 2.4 State Authority

All Task state transitions must go through TaskBus APIs. This centralizes validation and event emission.

---

## 3. Core Attributes

| Attribute | Meaning |
|-----------|---------|
| `session_id` | owning Session |
| `queue` | pending Task IDs in FIFO order |
| `running_task` | current running Task ID, or `None` |
| `task_store` | materialized Task state |
| `agent_registry` | available AgentTemplates |
| `event_stream` | append-only event sink |
| `closed` | whether new Tasks are rejected |

---

## 4. Design Principles

### 4.1 Serial Beats Concurrent in v1

Serial execution removes locks, orphan detection, heartbeats, concurrent write conflicts, and many scheduling edge cases.

### 4.2 FIFO Beats Priority

Priority queues are powerful but introduce surprising behavior. FIFO is predictable, explainable, and enough for early product feedback.

### 4.3 No Work Stealing or Affinity

V1 avoids advanced scheduler behavior. There are no long-lived workers to steal from, and Agent instances are stateless.

### 4.4 The Bus Enforces the State Machine

Task state transitions are legal only if the bus accepts them:

```
pending -> running
running -> done
running -> failed
```

### 4.5 Bus as Audit Log Front Door

Every publish, claim, completion, and failure emits an EventStream event. The bus is not only a runtime component; it is also the entry point into observability.

---

## 5. Core API

```python
class TaskBus:
    def publish(self, task: Task) -> TaskId: ...
    def claim_next(self) -> Task | None: ...
    def complete(self, task_id: TaskId, result: TaskResult) -> None: ...
    def fail(self, task_id: TaskId, error: str) -> None: ...
    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]: ...
```

`claim_next` is deliberately capability-aware through the Agent registry. The caller should not bypass the bus to mutate Task state.

---

## 6. Scheduling Algorithm

V1 scheduling is intentionally small:

1. If `running_task` exists, do nothing.
2. Scan pending tasks in FIFO order.
3. Skip tasks whose parent is not `done`.
4. Find the first task with a matching AgentTemplate.
5. Mark it `running`, emit events, instantiate AgentInstance.
6. When the Agent completes, mark `done` or `failed`.

The algorithm is boring by design. Boring schedulers are easier to debug.

---

## 7. Relationships With Other Components

| Component | Relationship |
|-----------|--------------|
| Session | owns one TaskBus |
| Task | created, claimed, and completed through the bus |
| Agent | instantiated by bus decisions |
| EventStream | receives all lifecycle events |
| Workspace | protected by the serial running constraint |
| Configuration | controls bus behavior such as max concurrency in future versions |

---

## 8. Comparison With OS Schedulers

TaskBus resembles an OS scheduler, but with a much simpler goal:

| OS Scheduler | TaskBus v1 |
|--------------|------------|
| preemptive | cooperative |
| many runnable threads | one running task |
| priorities and fairness | FIFO |
| CPU affinity | none |
| microsecond decisions | human-scale LLM task decisions |

The v1 bus intentionally does not optimize throughput. It optimizes explainability.

---

## 9. Lifecycle

### 9.1 Creation

Created with the Session, empty queue, no running task, and a reference to EventStream and Agent registry.

### 9.2 Active

Accepts new Tasks, schedules pending work, and records events.

### 9.3 Paused

Pause is not a core v1 state. If needed, it can be represented at Session level by rejecting new claims while still accepting events.

### 9.4 Closed

Rejects new Tasks, waits for or fails the running Task, flushes state, and stops scheduling.

---

## 10. Future Development

### 10.1 v1.x: Better Capability Matching

Introduce namespaces, fallback capabilities, and template ranking while keeping serial execution.

### 10.2 v2.x: Bounded Concurrency

Allow multiple concurrent LLM calls when their declared `IOScope`s do not conflict.

### 10.3 v2.x: Pause and Resume

Support long-running tasks that wait for user input without blocking the whole Session.

### 10.4 v2.x: Cross-Session References

Allow read-only references to completed Task results from previous Sessions.

### 10.5 v3.x: DAG Support

Only introduce full DAG scheduling if task trees plus artifact references are not enough.

### 10.6 v3.x: Streaming Tasks

Support producer-consumer style Tasks that emit incremental outputs.

---

## 11. Decision Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| Queue | FIFO | predictable and easy to inspect |
| Concurrency | serial | protects the single Workspace |
| Matching | capability string | simple and deterministic |
| State authority | TaskBus | one place for invariants |
| Auditing | EventStream on every transition | replay and debugging |

---

## 12. Summary

TaskBus v1 is deliberately small. It does not try to be a smart scheduler. It gives the architecture a clean center: all collaboration passes through Tasks, and all Task state changes pass through one bus.
