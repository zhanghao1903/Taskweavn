# Plan: Observability

## 1. Background

Multi-agent systems are hard to debug because decisions are distributed across LLM calls, tool calls, task routing, user choices, and workspace changes. This architecture already has EventStream; the next step is to make it queryable and useful.

## 2. Goals

- Make every important state transition observable.
- Provide trace views for Session, Task, Agent run, and scheduler decision.
- Support replay for debugging and regression tests.
- Expose metrics for cost, latency, failures, and queue behavior.
- Integrate with OpenTelemetry where practical.

## 3. Problems to Solve

| Problem | Need |
|---------|------|
| A task gets stuck | inspect queue, parent, capability, running state |
| LLM scheduler makes surprising decisions | view rationale and context summary |
| Cost spikes | trace cost to Task and Agent run |
| Tool output differs between runs | replay and recording |
| User asks "why did it do that?" | decision trail |

## 4. Three Pillars

### 4.1 Trace

Trace answers: what happened, in what order, and why?

### 4.2 Metrics

Metrics answer: how often, how long, how expensive, how many failures?

### 4.3 Debug

Debug tools answer: can I replay this and inspect the exact state?

## 5. EventStream Data Model

### 5.1 Event Base

```python
class Event(BaseModel):
    id: EventId
    session_id: SessionId
    task_id: TaskId | None
    agent_run_id: AgentRunId | None
    timestamp: datetime
    kind: str
    payload: dict
```

### 5.2 Event Types

Core event kinds:

- `SessionStarted`
- `TaskCreated`
- `TaskDispatched`
- `AgentRunStarted`
- `LLMCallStarted`
- `LLMCallFinished`
- `ToolCallStarted`
- `ToolCallFinished`
- `SchedulingDecision`
- `UserDecisionRequested`
- `UserDecisionResolved`
- `CostRecorded`
- `ConfigChanged`
- `TaskCompleted`
- `TaskFailed`

## 6. Indexes and Queries

### 6.1 Required Indexes

- `session_id`
- `task_id`
- `agent_run_id`
- `kind`
- `timestamp`
- `trace_id`

### 6.2 Query API

```python
class EventQuery:
    session_id: SessionId | None
    task_id: TaskId | None
    agent_run_id: AgentRunId | None
    kind: list[str] | None
    since: datetime | None
    until: datetime | None
```

### 6.3 Storage Backend

SQLite is enough for v1. Later versions can export to OpenTelemetry or analytical stores.

## 7. Trace View

The UI should show:

- task tree;
- current state per task;
- Agent run timeline;
- tool calls;
- scheduler decisions;
- user decisions;
- cost rollup.

## 8. OpenTelemetry Integration

### 8.1 trace_id Propagation

Each Session has a root trace. Tasks, Agent runs, LLM calls, and tool calls become spans.

### 8.2 Span Names

Examples:

- `session.run`
- `task.execute`
- `agent.run`
- `llm.call`
- `tool.call`
- `taskbus.schedule`

### 8.3 Compatibility

OTel export is optional. EventStream remains the primary local source of truth.

## 9. Replay Mode

### 9.1 Record Mode

Store LLM prompts/responses and tool call inputs/outputs.

### 9.2 Replay Mode

Return recorded responses instead of calling external services.

### 9.3 Hybrid Mode

Replay up to a selected event, then switch to live execution.

### 9.4 Handling LLM Nondeterminism

Replay should not pretend the model is deterministic. It should record enough to reproduce one observed path.

## 10. Automatic Detection

### 10.1 Invariants

- only one running task in v1;
- every running task has an Agent run;
- terminal tasks do not change result;
- every tool call has a matching finish or failure event.

### 10.2 Heuristics

- task pending too long;
- repeated failure pattern;
- budget spike;
- scheduler keeps holding all tasks.

## 11. UI / CLI Entry Points

### 11.1 CLI

```bash
agent trace SESSION_ID
agent events --task TASK_ID
agent replay SESSION_ID --until EVENT_ID
```

### 11.2 Web UI

Start with a Session timeline and task tree. Add deeper trace panes later.

## 12. Privacy and Redaction

### 12.1 Field-Level Marking

Events should mark sensitive fields.

### 12.2 Redaction Levels

- none;
- secrets only;
- user content hidden;
- metadata only.

## 13. Open Questions

- How much prompt content should be stored by default?
- Should replay be enabled in production?
- What is the default retention period?

## 14. Milestones

| Milestone | Output |
|-----------|--------|
| M1 | event schema |
| M2 | SQLite indexes and query API |
| M3 | CLI trace |
| M4 | replay recording |
| M5 | web trace view |

## 15. Acceptance Criteria

- Every Task can be traced from creation to terminal state.
- Scheduler decisions are inspectable.
- A recorded run can be replayed.
- Cost and latency can be attributed to Task and Agent run.

## 16. Related Plans

- `walkthrough.md`: provides sample trace.
- `cost-quota.md`: emits cost events.
- `ux-interaction.md`: emits user decision events.
- `configuration.md`: emits config change events.
