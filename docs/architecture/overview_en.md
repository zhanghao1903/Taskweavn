# Multi-Agent Collaboration Architecture Overview

> Version v1.0 · 2026-05-08 · codeAgent Phase 4

---

## 1. Overview

This architecture proposes a **TaskBus-driven** collaboration model for multi-agent systems. It is built around four first-class concepts:

```
Session  - one user interaction context with one workspace
Task     - the smallest unit of work, organized as a tree
Agent    - a stateless function-like executor: capability + tools
TaskBus  - the task coordination layer: FIFO scheduling + capability matching
```

The whole design should fit on one page. The core position is **a simple engine with a flexible user experience**: strong constraints at the architecture layer, progressive openness at the product layer.

---

## 2. Core Abstractions

### 2.1 Task-Driven Collaboration

Most multi-agent frameworks start with agents and then assign work to them. This architecture reverses the center of gravity: **Task is the primary object**.

```
Agents are instantiated when a Task needs them.
Agents do not communicate directly with each other.
Collaboration happens by publishing and completing Tasks.
The right to publish Tasks is a capability exposed as CreateTaskTool.
```

Any Agent with `CreateTaskTool` may publish a subtask and ask other Agents to collaborate. Users and Agents are symmetric before the TaskBus: both can be Task producers.

### 2.2 Tree-Shaped Task Relationships

Tasks form a tree through `parent_id`. A parent task creates subtasks, waits for their results, and synthesizes the outcome:

```
        Root Task (user request)
          ├── Subtask 1
          ├── Subtask 2
          └── Subtask 3
```

Fan-out and fan-in are handled by the parent task as the synchronization point. This provides parallel decomposition and synthesis without a full DAG scheduler.

### 2.3 Stateless Agents

An Agent is treated like a disposable function object:

```
Task arrives -> instantiate Agent(capability=X) -> execute -> destroy
N tasks requiring the same capability = N independent Agent instances
```

Cross-task experience is not stored in the Agent instance. It is explicitly stored and retrieved through `ThoughtStore`.

### 2.4 Serial TaskBus

The v1 TaskBus is intentionally small: a FIFO queue plus capability matching, with serial execution:

```
publish(task)              publish a task into the bus
claim_next(capability)     claim the next matching task
complete(id, result)       complete a task and notify waiters
```

There is no work stealing, no affinity scheduling, and no priority queue. The goal is an implementation small enough to reason about.

---

## 3. Five Strong Constraints

| # | Constraint | Complexity Removed |
|---|------------|--------------------|
| 1 | One Session has one Workspace | git-like fork / merge / conflict handling |
| 2 | Tasks execute serially | locks, CAS, heartbeats, orphan-task recovery |
| 3 | Agents are stateless between tasks | Agent lifecycle management and cache-affinity scheduling |
| 4 | Task states are only `pending/running/done/failed` | intermediate states such as `waiting`, `blocked`, `assigned` |
| 5 | Task dependency is a single `parent_id` | DAG topological sorting, cycle detection, readiness subscriptions |

---

## 4. Why Strong Constraints Exist

### 4.1 Simple Engine, Flexible Product

The constraints belong to the engine, not to the user's perceived experience. Users can still get flexible UI orchestration, conversation-driven graph generation, and autonomy configuration. Internally, the engine remains predictable.

```
Product layer       progressive openness
----------------------------------------
Architecture layer  strong constraints
```

These two directions do not conflict. User flexibility becomes safer when it sits on top of a predictable engine.

### 4.2 Simplicity Enables Relaxation

Strong constraints are not permanent limitations. Each constraint has a planned relaxation path:

| Constraint | Relaxation Trigger | Later Shape |
|------------|-------------------|-------------|
| Single Workspace | real parallel-write need appears | sub-session isolation |
| Serial execution | LLM latency is no longer the bottleneck | bounded task concurrency |
| Stateless Agents | cache cost becomes dominant | warm Agent pools |
| Single `parent_id` | real DAG use cases appear | `artifact_refs` or full DAG |

A simple engine can be relaxed. An overly flexible engine usually needs to be rewritten.

### 4.3 Constraints Are Explainability

Four task states are easier to debug than eight. A tree is easier to explain than a DAG. Agent systems are already hard to inspect; the architecture should not add avoidable cognitive load.

---

## 5. Known Drawbacks

| Drawback | Impact | Mitigation |
|----------|--------|------------|
| Serial execution reduces throughput | total task time can increase | LLM calls dominate wall-clock time in v1 |
| Stateless Agents reduce cache reuse | token cost can increase | stable system prompt + tool schemas still cache well |
| Tree dependency limits expression | lateral dependency is awkward | introduce `artifact_refs` as a non-breaking extension |
| Single Workspace blocks parallel writes | write-heavy tasks must serialize | consistent with v1 serial execution |

These are delayed decisions, not permanent refusals. Every relaxation should be justified by real usage data.

---

## 6. Comparison With the OS Thread Model

### 6.1 Concept Mapping

| OS / Runtime Concept | This Architecture |
|----------------------|-------------------|
| Process | Session |
| Thread | Agent instance |
| Job / work item | Task |
| Work queue | TaskBus |
| Shared memory | Workspace |
| Thread-local storage | Agent working memory |
| Persistent files | ThoughtStore |
| Thread pool | Agent pool |
| fork / join | parent task creating and waiting for subtasks |

### 6.2 Similarities

Both systems separate work from execution resources. A Task is the unit of work; an Agent instance is the execution carrier. A parent task can fork subtasks and join their results, similar to thread-based fork/join programming.

Both systems also deal with shared resources. Threads share process memory; Agents share the Session Workspace. The difference is that v1 avoids most concurrency hazards through serial execution.

### 6.3 Key Differences

**Lifecycle.** Threads are usually reused; Agent instances are disposable. Reuse improves cache efficiency, but stateless Agents make scheduling and replay dramatically simpler.

**Sharing.** Thread systems are "shared by default, isolated by discipline." This architecture is "isolated by default, shared only through Task results and Workspace access."

**Communication.** Threads can communicate through many mechanisms. Agents communicate only through Tasks and task results. This is less expressive but much easier to observe.

**Scheduling.** OS schedulers are preemptive and complex. The v1 TaskBus is cooperative and simple because LLM workloads run at human-scale latency, not CPU-scale latency.

**Failure.** A thread crash can destabilize a process. A Task failure is naturally scoped to that Task, and the parent task can decide whether to retry, ignore, or report.

---

## 7. Future Development Path

### 7.1 Short Term: v1.x

- Add stronger capability matching without changing the task tree model.
- Improve EventStream queries and replay.
- Add user-visible walkthroughs and debugging views.
- Introduce cost and quota controls.

### 7.2 Mid Term: v2.x

- Add bounded concurrency based on `IOScope`.
- Use LLM scheduling with explicit rationale and deterministic fallback.
- Add `artifact_refs` for read-only cross-tree data references.
- Support pausing and resuming long-running sessions.

### 7.3 Long Term: v3.x

- Consider full DAG scheduling only if tree + references proves insufficient.
- Support streaming tasks and long-running agent pipelines.
- Introduce cross-session collaboration and multi-user sessions.

---

## 8. Design Philosophy

This architecture prefers **strong internal constraints and gradual external flexibility**. It does not try to build the most expressive multi-agent engine first. It tries to build a small engine whose behavior can be explained, tested, replayed, and relaxed one constraint at a time.

The bet is simple: in early agent systems, debuggability is more valuable than theoretical expressiveness.

---

## Appendix: Component Documents

- `task.md`: Task abstraction and lifecycle
- `session.md`: Session and workspace boundary
- `agent.md`: stateless Agent model
- `bus.md`: v1 TaskBus
- `bus-v2.md`: LLM scheduling and bounded concurrency
- `review.md`: architecture review and roadmap mapping
