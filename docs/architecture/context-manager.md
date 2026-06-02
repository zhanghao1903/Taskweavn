# Context Manager Architecture

> Status: accepted architecture baseline for Product 1.0 execution context governance
> Last Updated: 2026-06-02

Context Manager is the execution-time context governance layer for Taskweavn.
It bridges the stateful workspace and task runtime to the stateless LLM API
used by an Execution Agent.

Product 1.0 intentionally implements only a simple deterministic baseline:
Context Manager collects known facts from existing runtime sources, builds a
structured execution context, renders the LLM input, and records enough trace
data for recovery and debugging. It does not implement complex retrieval,
memory, ranking, multimodal packing, or agent-specific policy optimization.

The accepted Product 1.0 implementation lives under `src/taskweavn/context/`
and is wired into the sidecar-built fixed-route Default Agent path, including
the AgentLoop per-call `llm.chat(...)` seam.

The Product 1.0 hardening path now uses cache-aware append-only rendering:
the first call establishes a stable start context, later calls preserve the
existing AgentLoop transcript, and Context Manager appends bounded delta or
checkpoint messages when policy requires new context facts. See
[ADR-0013](../decisions/ADR-0013-cache-aware-append-only-context-rendering.md)
and the
[cache-aware rendering plan](../plans/feature/context-manager-cache-aware-rendering.md).

---

## 1. Problem Statement

Taskweavn's execution world is stateful:

- PublishedTasks have lifecycle, assignment, results, and parent-child
  relationships.
- Session Workspace contains files, documents, code, and generated artifacts.
- Tool calls produce observations, errors, command output, and file changes.
- Users can interrupt, clarify, approve, deny, or redirect work.
- Skills, project rules, tool permissions, and autonomy settings constrain
  execution.

The LLM API is stateless. Each call only receives a finite input payload and
does not inherently remember task state, workspace facts, previous tool
results, or user constraints unless the runtime provides them again.

Context governance solves this mismatch:

```text
stateful Task / Workspace / Event / Tool / User world
  -> Context Manager
  -> finite stateless LLM API input
```

The consumer of this layer is the Execution Agent. Context Manager should
therefore be designed around what the Execution Agent needs to continue the
current task, not around a generic memory or retrieval abstraction.

---

## 2. Responsibility Boundary

Context Manager is the only component responsible for assembling the input sent
to the LLM API for Execution Agent calls.

It is responsible for:

- collecting execution-relevant facts from approved context sources;
- building a structured `TaskExecutionContext`;
- applying deterministic Product 1.0 context limits;
- rendering `TaskExecutionContext` into an LLM API input payload;
- recording context snapshots and traces for recovery, audit, and debugging.

It is not responsible for:

- owning Task lifecycle state;
- changing PublishedTask status;
- executing tools;
- deciding task assignment or routing;
- storing canonical workspace files;
- acting as a long-term memory system;
- making product or permission decisions outside existing runtime controls.

Facts remain owned by their domains:

| Source | Owns |
|---|---|
| TaskBus / TaskDomain | PublishedTask state, claim, result, and failure facts |
| EventStream / EventLog | Ordered runtime facts and audit events |
| Session Workspace | Files, code, documents, generated artifacts |
| Tool runtime / ToolResultStore | Tool calls, observations, command output, raw results |
| Permission / Autonomy runtime | Allowed tools, pending approval, interrupt intent |
| Skill registry | Future available and activated skill descriptions |

Context Manager reads these sources and produces a derived execution view. It
does not become the source of truth for those facts.

---

## 3. Architecture Pipeline

```text
TaskBus / EventLog / Workspace / Tool Results / Permissions
        |
        v
Context Sources
        |
        v
Context Manager
        |
        v
TaskExecutionContext
        |
        v
LLM Input Renderer
        |
        v
Execution Agent LLM API Call
```

The important architectural split is:

```text
TaskExecutionContext != prompt text
```

`TaskExecutionContext` is a structured intermediate representation. Prompt or
LLM API input is only one rendering of that representation. This keeps later
changes possible: different Execution Agent templates, reviewer agents,
recovery agents, or evaluator agents can render the same context differently
without changing fact collection.

---

## 4. Product 1.0 Scope

Product 1.0 context governance is deliberately small.

### 4.1 Product 1.0 Goals

- Give the default Execution Agent enough facts to execute a PublishedTask.
- Preserve the original task target and current execution state.
- Include recent events and recent tool observations without unbounded history.
- Include permission, approval, and interrupt facts in every execution context.
- Store enough context trace to debug why an LLM call saw a specific input.
- Keep the architecture replaceable when richer context policies are added.
- Keep one active writer execution lane per Session by default.

### 4.2 Product 1.0 Non-Goals

Product 1.0 does not implement:

- semantic retrieval or vector search;
- LLM-based context ranking;
- long-term memory;
- sophisticated compression;
- multimodal packing;
- user-custom context policies;
- per-Agent advanced context strategies;
- parallel multi-Agent context ownership;
- automatic skill discovery beyond activated or configured skill facts;
- MCP-specific context expansion;
- provider-specific prompt-cache directives or advanced cache policy engines;
- cross-session context reuse.

These capabilities belong to Product 1.1+ or later architecture extensions.

### 4.3 Execution Lane Constraint

Product 1.0 and Product 1.1 default to a single active execution lane per
Session. Multiple Agents may exist as concepts, templates, or serialized
delegation steps, but they do not concurrently advance the same Session
Workspace or task context.

The constraint is:

```text
one Session
  -> one SessionContextManager
  -> one active writer execution lane
  -> one authoritative TaskExecutionContext build per LLM call
```

The goal is to keep task state, workspace writes, context ownership, and audit
replay convergent. Parallel multi-Agent execution is not a default architecture
mode because it creates competing local context views, write conflicts, merge
requirements, and difficult-to-replay failure paths.

Parallel Agent work is allowed only when one of these isolation conditions is
true:

| Parallel Shape | Requirement |
|---|---|
| Read-only reviewer | Agent may inspect facts but cannot mutate Task state or Session Workspace. |
| Independent shard | Inputs and outputs are independent and can be reduced explicitly. |
| Isolated workspace | Agent runs in a sub-session or separate workspace with explicit merge/export. |
| Tool-like specialist | Specialist returns a bounded structured result to the active lane and does not own ongoing context. |

Context Manager should represent this through build purpose and writer intent:

```python
ContextBuildRequest(
    task_id=task_id,
    agent_run_id=agent_run_id,
    purpose="execution_step",
    writer=True,
)
```

Read-only or isolated future builds can use:

```python
ContextBuildRequest(
    task_id=task_id,
    agent_run_id=agent_run_id,
    purpose="read_only_review",
    writer=False,
)
```

Product 1.0 only needs the writer execution path.

---

## 5. TaskExecutionContext v0

`TaskExecutionContext v0` is the minimal structured contract between Context
Manager and the Execution Agent. The Product 1.0 implementation uses immutable
Pydantic models in `src/taskweavn/context/models.py`; the snippets below show
the contract shape.

```python
class TaskExecutionContextV0(ContextModel):
    task: TaskContextIdentity
    execution: ExecutionContextState
    facts: ExecutionFacts
    controls: ExecutionControls
    guidance: ExecutionGuidance
    trace: ContextTraceRef | None = None
```

### 5.1 Task Identity

```python
class TaskContextIdentity(ContextModel):
    task_id: str
    session_id: str
    parent_task_id: str | None
    root_task_id: str
    original_target: str
    interpreted_goal: str | None
    success_criteria: tuple[str, ...]
    non_goals: tuple[str, ...]
    required_capability: str | None
```

Rules:

- `original_target` must not be replaced by a summary.
- `interpreted_goal` may be generated by planning or authoring, but it is not
  more authoritative than the original target.
- `success_criteria` should be explicit when available, but Product 1.0 may
  leave it empty.

### 5.2 Execution State

```python
class ExecutionContextState(ContextModel):
    status: str
    claimed_by: str | None
    current_step: CurrentStepContext | None
    latest_user_instruction: str | None
    interruption: InterruptionContext | None
```

```python
class CurrentStepContext(ContextModel):
    step_id: str | None
    objective: str
    expected_output: str | None
```

```python
class InterruptionContext(ContextModel):
    requested: bool
    reason: str | None
    requested_at: str | None
```

Rules:

- The current step should be explicit when the runtime has one.
- If no plan step exists in Product 1.0, Context Manager can derive a single
  current step from the PublishedTask intent.
- Interrupt intent is context, not a direct task state mutation. The Execution
  Agent must see it at a safe point.

### 5.3 Execution Facts

```python
class ExecutionFacts(ContextModel):
    recent_events: tuple[EventSummary, ...]
    recent_tool_results: tuple[ToolResultSummary, ...]
    workspace_refs: tuple[WorkspaceRef, ...]
    selected_file_snippets: tuple[FileSnippet, ...]
    changed_artifacts: tuple[str, ...]
```

Product 1.0 facts are bounded and deterministic:

- keep only the latest configured number of events;
- keep only summarized tool results in the default LLM input;
- include raw tool result references when available;
- include workspace references, not whole workspace snapshots;
- include selected file snippets only when they are explicit task evidence.

`selected_file_snippets` is not a workspace file map. It is the bounded set of
file excerpts selected into one context build.

```python
class FileSnippet(ContextModel):
    snippet_id: str
    workspace_id: str | None
    path: str
    source: str
    content: str
    start_line: int | None
    end_line: int | None
    file_hash: str | None
    content_hash: str
    raw_ref: str | None
    reason: str
    token_estimate: int
    observed_at: str | None
    stale: bool
    can_act_as_instruction: bool = False
```

Rules:

- Workspace remains the source of truth for file contents.
- `FileContentObservation` and explicit workspace refs are evidence sources.
- Context Manager may select snippets from read-file observations or explicit
  refs, but it does not crawl the whole workspace in Product 1.0.
- File snippets are rendered as workspace evidence, not instructions.
- Large file reads should be represented by bounded snippets plus `raw_ref`.

### 5.4 Controls

```python
class ExecutionControls(ContextModel):
    allowed_tools: tuple[str, ...]
    denied_tools: tuple[str, ...]
    requires_approval: tuple[str, ...]
    pending_approval: ApprovalSummary | None
    file_scopes: tuple[str, ...]
```

Rules:

- Permission facts must be present in every Execution Agent context.
- If a tool or file scope requires approval, the renderer must not hide that
  fact inside a long history summary.
- Product 1.0 does not require hard cancellation. Cooperative interruption is
  represented through execution state and safe-point checks.

### 5.5 Guidance

```python
class ExecutionGuidance(ContextModel):
    project_rules: tuple[str, ...]
    active_skills: tuple[SkillSummary, ...]
    output_requirements: tuple[str, ...]
```

Rules:

- Product 1.0 may include only configured or explicitly activated skill
  summaries.
- Full skill bodies, skill references, and skill scripts are loaded by the
  normal skill/runtime mechanism when needed. Context Manager should reference
  them, not inline all possible skill material.

---

## 6. Context Candidates and Selection

Even Product 1.0 should preserve the candidate-selection shape so richer
policies can be added later.

```python
class ContextCandidate(ContextModel):
    candidate_id: str
    source_type: str
    source_ref: str
    summary: str
    raw_ref: str | None
    priority: int
    token_estimate: int
    can_act_as_instruction: bool
```

Product 1.0 selection policy:

1. Always include task identity.
2. Always include current execution state.
3. Always include permission, approval, and interrupt facts.
4. Include bounded recent events.
5. Include bounded recent tool result summaries.
6. Include explicit workspace references already connected to the task.
7. Exclude raw large outputs by default; provide `raw_ref` instead.

No LLM ranking is used in Product 1.0. Selection is deterministic.

---

## 7. Rendering To LLM Input

Context Manager should render structured context into an LLM API input payload,
not into an uncontrolled free-form prompt.

The renderer should produce:

- stable execution instructions;
- task identity and original target;
- current step and latest user instruction;
- controls and permission facts;
- recent event/tool summaries;
- workspace references;
- output expectations;
- references to raw artifacts or tool results.

The renderer should avoid:

- hiding active controls inside compressed prose;
- presenting summaries as higher authority than user or system instructions;
- sending unbounded command output;
- sending unrelated workspace files;
- allowing project file text to act as system instruction.

---

## 8. Storage, Recovery, and Trace

Product 1.0 should record context construction artifacts even if the context
policy is simple.

```python
class ContextSnapshot(ContextModel):
    snapshot_id: str
    session_id: str
    task_id: str
    agent_id: str
    agent_run_id: str
    purpose: ContextBuildPurpose
    turn_index: int
    context_version: str
    renderer_version: str
    task_execution_context: TaskExecutionContextV0
    rendered_input_hash: str
    created_at: str
```

```python
class ContextTrace(ContextModel):
    trace_id: str
    snapshot_id: str
    session_id: str
    task_id: str
    candidates_seen: tuple[str, ...]
    candidates_selected: tuple[str, ...]
    candidates_excluded: tuple[ContextExclusion, ...]
    policy_version: str
    renderer_version: str
```

This trace answers:

- What did the Execution Agent see?
- What facts were available but excluded?
- Which policy and renderer produced the input?
- Which raw refs can recover omitted tool results?

Recovery should rebuild context from canonical facts when possible. Snapshots
are debugging and replay artifacts, not the primary source of truth.

## 8.1 Lifecycle

Context Manager is Session-scoped, not Agent-scoped.

```text
Session starts
  -> create SessionContextManager

Execution Agent turn
  -> SessionContextManager.build(...)
  -> ContextBuildResult / rendered LLM input

Task ends
  -> Agent run ends
  -> SessionContextManager remains available

Session closes
  -> flush context snapshots, traces, and indexes
```

Execution Agent runs are consumers of context, not owners of context. This lets
later tasks, recovery flows, audit views, and serialized specialist steps reuse
the same Session-level context governance without giving each Agent its own
competing memory of the task world.

EventStream and tool stores may push events to lightweight indexes, but final
LLM input is always produced by a pull-time `build(...)` call:

```text
EventStream.append(event)
  -> optional ContextIndexer.observe(event)

SessionContextManager.build(...)
  -> pull canonical facts and indexes
  -> select context
  -> render LLM input
  -> save snapshot / trace
```

Do not let EventStream callbacks directly mutate final TaskExecutionContext or
rendered prompt state.

---

## 9. Extension Points

Product 1.0 should keep these interfaces narrow:

```python
class ContextSource(Protocol):
    def collect(self, request: ContextBuildRequest) -> tuple[ContextCandidate, ...]:
        ...
```

```python
class ContextPolicy(Protocol):
    def select(
        self,
        candidates: tuple[ContextCandidate, ...],
        budget: ContextBudget,
    ) -> SelectedContext:
        ...
```

```python
class ContextRenderer(Protocol):
    def render(self, context: TaskExecutionContextV0) -> LlmInput:
        ...
```

```python
class ContextStore(Protocol):
    def save_snapshot(self, snapshot: ContextSnapshot) -> None:
        ...

    def save_trace(self, trace: ContextTrace) -> None:
        ...
```

Future extensions can add:

- `SkillContextSource`;
- `McpContextSource`;
- `MultimodalContextSource`;
- `MemoryContextSource`;
- `RetrievalContextSource`;
- `CompressionPolicy`;
- `AgentSpecificContextPolicy`;
- `ContextAuditor`;
- `ContextReplayService`.

These should plug into Context Manager without changing TaskBus or Execution
Agent lifecycle ownership.

---

## 10. Relationship To Existing Architecture

### TaskBus

TaskBus remains the PublishedTask lifecycle authority. Context Manager reads
Task facts and may include task status, assignment, result, and failure facts in
context. It does not call `claim`, `complete`, `fail`, or retry operations.

### Execution Agent

Execution Agent consumes rendered context and tools. It may request additional
information through allowed tools, but the next LLM call still goes through
Context Manager.

### EventStream

EventStream is the ordered fact ledger. Context Manager derives recent events,
tool history views, progress summaries, and recovery inputs from it.

### Skills

Skills are progressively loaded workflow context. Context Manager records which
skills are active or relevant, but Product 1.0 does not turn skills into a full
context policy system.

### Workspace

Workspace owns files and artifacts. Context Manager includes workspace refs and
selected snippets only when they are task-relevant and within Product 1.0
budget limits.

---

## 11. Acceptance Criteria For Product 1.0

Product 1.0 Context Manager is acceptable when:

1. Every fixed-route Default Agent LLM call is assembled through Context
   Manager.
2. `original_target` is always present in `TaskExecutionContext`.
3. Permission, approval, and interrupt facts are always represented.
4. Recent event and tool result inclusion is deterministic and bounded.
5. Large raw tool outputs are summarized or referenced, not blindly inlined.
6. Context snapshots and traces can explain a rendered LLM input.
7. Context can be rebuilt from TaskBus/EventLog/Workspace facts after
   interruption or process restart.
8. Product 1.0 implementation does not require semantic retrieval, long-term
   memory, complex compression, MCP expansion, or multimodal packing.
9. Future context sources and policies can be added without changing TaskBus
   ownership or Execution Agent lifecycle ownership.
10. The default Session context policy permits only one active writer execution
    lane; parallel Agent context builds must be read-only or isolated.

---

## 12. Product 1.1+ Follow-ups

- Which event types should become mandatory context candidates?
- How should Context Manager expose context trace to Audit Page in Product 1.1?
- Should diagnostic bundles include full context snapshots, hashes only, or
  redacted rendered inputs?
- Should trace records include richer candidate-level exclusion details beyond
  the current policy/renderer/snapshot linkage?
- What are the explicit contracts for future Skill, MCP, multimodal, retrieval,
  and compression context sources?
