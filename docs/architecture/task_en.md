# Task Architecture Design

> Core abstraction of the multi-agent collaboration architecture · v1.0 · 2026-05-08

---

## 1. Definition

**Task is the smallest unit of work and a first-class object in this architecture.**

Anything that should be completed by an Agent is represented as a Task: a user request, an Agent-created subtask, an audit, a validation step, or a synthesis step.

```
Task = a clear intent + the required capability + the result after completion
```

The whole system is the production, routing, execution, and completion of Tasks.

---

## 2. Core Abstraction

### 2.1 A Task Is a Work Description, Not a Function Call

A Task describes **what** needs to be done. It does not prescribe **how** to do it. The TaskBus routes it to an Agent instance with a matching capability; the Agent decides how to execute it.

```
Task       "audit this code for security issues"
           required_capability = "audit"
             ↓
TaskBus    finds an AgentTemplate with capability "audit"
             ↓
Agent      executes and returns a result
```

Because a Task is data, it can be serialized, persisted, replayed, and audited.

### 2.2 A Task Is a Tree Node

Tasks form a single-root tree through `parent_id`:

```
        Root Task
          ├── Subtask 1
          │     └── Subtask 1.1
          ├── Subtask 2
          └── Subtask 3
```

The tree constraint is intentional. A parent task acts as the synchronization point for fan-out and fan-in: it creates subtasks, waits for them, and synthesizes their results.

### 2.3 Three Essential Fields

```python
@dataclass(frozen=True)
class Task:
    id: TaskId
    parent_id: TaskId | None

    intent: str
    required_capability: str

    status: TaskStatus
    result: TaskResult | None
```

`intent` is human-readable and Agent-facing. `required_capability` is machine-readable and scheduler-facing. `result` is the output consumed by the parent task or later tasks.

---

## 3. Core Attributes

| Attribute | Type | Meaning |
|-----------|------|---------|
| `id` | `TaskId` | globally unique ID |
| `parent_id` | `TaskId \| None` | parent task; `None` means root |
| `intent` | `str` | natural-language task intent |
| `required_capability` | `str` | capability required for execution |
| `status` | `TaskStatus` | `pending`, `running`, `done`, `failed` |
| `result` | `TaskResult \| None` | final output |
| `created_at` | `datetime` | creation time |
| `created_by` | `AgentId \| UserId` | creator |
| `started_at` | `datetime \| None` | when execution started |
| `completed_at` | `datetime \| None` | when terminal state was reached |
| `error` | `str \| None` | failure reason |

The model should be frozen. State transitions create new task versions or append events instead of mutating history in place.

---

## 4. Design Principles

### 4.1 Task Is Data, Not Behavior

Task objects should round-trip through JSON. This enables persistence, replay, debugging, and audit. A Task is closer to an event-sourced command than to an in-memory function call.

### 4.2 Single-Root Tree Constraint

Full DAG scheduling is intentionally deferred. In LLM-driven decomposition, most work is naturally top-down: user goal → subtasks → synthesis. The tree model covers the majority of cases with far less machinery.

The cost difference matters:

```
Tree scheduler: small queue + parent checks
DAG scheduler: topological sort + cycle detection + readiness events + deadlock handling
```

The missing cases can later be addressed with `artifact_refs`, a read-only data dependency that does not change the execution tree.

### 4.3 Minimal State Machine

Only four states exist:

```
pending -> running -> done
                 \-> failed
```

Removed states:

- `waiting`: represented by `pending` until the parent is done.
- `assigned`: merged into `running`.
- `blocked`: the parent remains `running` while waiting for subtasks.
- `cancelled`: represented by `failed` with a clear reason.

### 4.4 Task Publishing Is a Collaboration Capability

An Agent can publish subtasks only if it has `CreateTaskTool`.

```
Leaf Agent:        tools = [read_file, write_file]
Collaborative Agent: tools = [read_file, write_file, create_task]
Orchestrator Agent:  tools = [create_task, claim_result]
```

This makes collaboration an explicit capability rather than a special Agent class.

---

## 5. State Machine

```
pending  - published, waiting to be claimed
running  - being executed by one Agent instance
done     - terminal success
failed   - terminal failure
```

Transition rules:

| Transition | Rule |
|------------|------|
| `pending -> running` | parent is done and a matching Agent claims it |
| `running -> done` | Agent returns a valid result and all subtasks are done |
| `running -> failed` | Agent error, subtask failure, or explicit failure |

Terminal tasks are immutable. A retry is represented as a new Task, not a mutation of the old Task.

---

## 6. Lifecycle

### 6.1 Creation

Tasks are created by users or Agents. Root tasks have `parent_id=None`; subtasks carry the parent task ID. Creation immediately appends a `TaskCreated` event and puts the task into `pending`.

### 6.2 Waiting and Claiming

A pending task can be claimed when:

- it has no parent, or its parent is `done`;
- an AgentTemplate exists with the required capability;
- the TaskBus allows a new running task under the current execution policy.

### 6.3 Execution

The Agent instance reads the Workspace, calls the LLM, invokes tools, optionally creates subtasks, and returns a result. If subtasks are created, the parent task keeps responsibility for synthesis.

### 6.4 Completion

Completion writes the result, emits a `TaskCompleted` event, and notifies the parent task if one exists.

### 6.5 Persistence and Archive

Task history is preserved through EventStream. The current Task table can be treated as a materialized view over events.

---

## 7. Relationships With Other Components

| Component | Relationship |
|-----------|--------------|
| Session | owns the task tree and workspace boundary |
| TaskBus | publishes, claims, and transitions Tasks |
| Agent | executes exactly one Task per instance |
| EventStream | records every Task lifecycle event |
| ThoughtStore | stores reusable knowledge produced by completed Tasks |

---

## 8. Future Development

### 8.1 v1.x: Non-Breaking Extensions

- Add task labels and tags.
- Add estimated cost and duration.
- Add structured result schemas per capability.

### 8.2 v2.x: State Extensions

Add `paused` or `needs_user` only if UX and HITL flows prove that `running` is too coarse.

### 8.3 v3.x: DAG Support

Move beyond the tree only when real usage shows that `artifact_refs` cannot express the needed data dependencies.

### 8.4 v3.x: Streaming Tasks

Introduce Tasks that produce incremental outputs and remain active for long periods.

---

## 9. Decision Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| Unit of work | Task | decouples work from Agent instances |
| Dependency model | tree via `parent_id` | simple, observable, enough for v1 |
| State machine | 4 states | easy to debug and replay |
| Retry model | new Task | keeps history immutable |
| Collaboration | `CreateTaskTool` | makes orchestration a capability |
