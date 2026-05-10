# Session Architecture Design

> Core abstraction of the multi-agent collaboration architecture · v1.0 · 2026-05-08

---

## 1. Definition

**Session is the complete interaction context for a user and the largest resource boundary in the system.**

A Session contains:

- one Workspace;
- one TaskBus instance;
- the Agent pool / template registry;
- access to ThoughtStore;
- an EventStream shard;
- one or more task trees.

```
Session = an isolated work environment + all Tasks inside that environment
```

---

## 2. Core Abstraction

### 2.1 Session Is a Resource Boundary

Every Task, Agent instance, tool call, and file operation happens inside a Session. Cross-session access is intentionally restricted.

```
Session A                         Session B
Workspace A                       Workspace B
TaskBus A                         TaskBus B
Tasks A                           Tasks B
Agent instances A                 Agent instances B
```

An Agent in Session A cannot see Session B's Workspace or TaskBus unless a future cross-session reference mechanism explicitly allows it.

### 2.2 One Session Owns One Workspace

This is one of the strongest constraints:

```
Rejected: Session -> TaskWorkspace -> AgentWorkspace
Chosen:   Session -> one Workspace shared by all Tasks
```

The architecture avoids fork / merge / conflict resolution by combining a single Workspace with serial task execution.

### 2.3 Session Contains Task Trees

Each user request creates a root Task. A Session may contain multiple root tasks over time, but they share the same Workspace and EventStream.

```
Session
  ├── Root Task 1
  │     └── Subtask
  └── Root Task 2
        └── Subtask
```

---

## 3. Core Attributes

| Attribute | Type | Meaning |
|-----------|------|---------|
| `id` | `SessionId` | globally unique ID |
| `workspace` | `Workspace` | the only workspace for this session |
| `bus` | `TaskBus` | task coordination layer |
| `agent_pool` | `AgentPool` | Agent template registry and instance factory |
| `thought_store` | `ThoughtStore` | long-term memory access |
| `event_stream` | `EventStream` | append-only event log |
| `root_tasks` | `list[TaskId]` | root tasks in this session |
| `created_at` | `datetime` | creation time |
| `closed_at` | `datetime \| None` | close time |
| `status` | `SessionStatus` | `creating`, `active`, `closed`, `abandoned` |
| `user_id` | `UserId` | owner |
| `config` | `SessionConfig` | autonomy, constraints, presets, limits |

---

## 4. Design Principles

### 4.1 Session Is a Process, Not Just a Conversation

Session should be understood as a process-like container:

| OS Process | Session |
|------------|---------|
| isolated memory | isolated Workspace |
| multiple threads | multiple Agent instances |
| process-local files | Session-local artifacts |
| process shutdown | Session cleanup |

This makes Session a heavyweight object. A user should have a small number of active Sessions, not one Session per message.

### 4.2 Single Workspace Is the Simplicity Anchor

The single Workspace choice removes:

- task-level fork and merge;
- cross-workspace synchronization;
- ambiguity about the source of truth;
- many classes of concurrent write conflict.

The cost is lower parallel write capability, which is acceptable in v1 because the system is intentionally serial.

### 4.3 Session Config Is the User Control Boundary

Autonomy, constraints, and presets are attached to the Session:

```python
@dataclass
class SessionConfig:
    autonomy_behavior: AutonomyBehavior
    constraint_profile: ConstraintProfile
    preset: OrchestrationPreset | None
    interrupt_allowed: bool
```

Agent instances inherit Session configuration at creation time. This gives users one coherent control surface.

### 4.4 Session Is the Root of EventStream

Events are partitioned by `session_id`. This makes audit and replay naturally scoped:

```
by session_id -> full history
by task_id    -> task lifecycle
by agent_run  -> one Agent execution
```

---

## 5. Lifecycle

```
creating -> active -> closed
                  \-> abandoned
```

### 5.1 Creating

Session creation initializes:

1. `SessionId`;
2. Workspace;
3. TaskBus;
4. AgentPool / AgentTemplate registry;
5. ThoughtStore connection;
6. EventStream shard;
7. SessionConfig.

### 5.2 Active

The Session accepts user messages and Agent-created Tasks. During active operation:

- Workspace is read and written;
- EventStream appends events;
- ThoughtStore may be queried or updated;
- Agent instances are created and destroyed per Task.

### 5.3 Closed

Normal close means:

1. stop accepting new Tasks;
2. let the current running Task reach a terminal state, or fail it explicitly;
3. destroy Agent instances;
4. flush EventStream and ThoughtStore;
5. persist or discard Workspace based on user choice.

Closed Sessions are not resumed in v1. A follow-up continues in a new Session.

### 5.4 Abandoned

`abandoned` represents abnormal termination, timeout, or host crash. Recovery is a future feature; v1 should preserve enough EventStream data for inspection.

### 5.5 Persistence Model

The durable truth is EventStream. Session tables are indexes and materialized views for fast queries.

---

## 6. Relationships With Other Components

| Component | Relationship |
|-----------|--------------|
| Task | belongs to exactly one Session |
| TaskBus | created per Session |
| Agent | instantiated inside one Session |
| Workspace | owned by one Session |
| EventStream | partitioned by Session |
| ThoughtStore | shared service, accessed through Session scope |

---

## 7. Future Development

### 7.1 v1.x: Session Resume

Load persisted events, reconstruct task state, mark interrupted running tasks as failed, and let the user retry through new Tasks.

### 7.2 v2.x: Sub-Session

Introduce isolated sub-sessions for heavier parallel work. A sub-session has its own Workspace and may merge results back into the parent.

### 7.3 v2.x: Session Templates

Provide preconfigured Session profiles such as code audit, research report, or document editing.

### 7.4 v3.x: Multi-User Sessions

Allow multiple users to observe or participate in one Session with role-based task publishing and Workspace permissions.

### 7.5 v3.x: Cross-Session References

Allow read-only references to historical Task results without copying entire workspaces or task trees.

---

## 8. Decision Summary

| Decision | Choice | Reason |
|----------|--------|--------|
| Resource boundary | Session | gives clear isolation |
| Workspace model | one Workspace per Session | removes fork/merge complexity |
| Config location | SessionConfig | creates one user-facing control surface |
| Event scope | per Session | simplifies replay and audit |
| Recovery | deferred | keeps v1 lifecycle simple |
