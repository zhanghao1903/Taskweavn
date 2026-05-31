# TaskWeavn Architecture Overview

> Status: active architecture overview
> Last Updated: 2026-05-31
> Version: v1.2
> Related Decisions: [ADR-0008](../decisions/ADR-0008-authoring-domain-execution-boundary.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)

This document is the current high-level architecture map. It summarizes the
active system boundaries and points to the detailed architecture documents that
own each contract.

TaskWeavn keeps the runtime deliberately small for Product 1.0 while preserving
clear extension points for later routing, skills, MCP, multimodal context, and
custom Agent governance.

---

## 1. Current Architecture Shape

TaskWeavn is a task-first local assistant system with two major domains:

```text
Authoring Domain
  turns fuzzy user intent into publishable work

Execution Domain
  executes confirmed PublishedTasks and projects results back to the UI
```

The current Product 1.0 path is:

```text
User message
  -> RawTask
  -> FeasibilityReport / RawTaskAsk
  -> DraftTaskTree
  -> user review / edit / confirmation
  -> TaskPublisher
  -> PublishedTask
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Resident Default Agent task-run
  -> TaskBus complete / fail
  -> Main Page / Audit projections
```

The runtime is tree-capable, but the Product 1.0 user experience is line-first:
one active flow, one default execution route, explicit user checkpoints, and no
default multi-Agent orchestration surface.

---

## 2. Core Objects

| Object | Responsibility | Canonical Docs |
|---|---|---|
| `Project` | Long-lived product container for user work. It is a UI/product organization layer, not the default file write boundary. | [UI/backend communication](ui-backend-communication.md) |
| `Workflow` | Product-level grouping under a Project. It can organize related Sessions and future reusable flows. | [Workflow Session Task UX Model](../product/workflow-session-task-ux-model.md) |
| `Session` | Runtime boundary for one interaction context and its Session Workspace. | [Session](session.md) |
| `Session Workspace` | File and process boundary for execution. Product 1.0 keeps one active Session workspace and avoids implicit cross-session writes. | [Session](session.md), [Workspace Communication Protocol](workspace-communication-protocol.md) |
| `RawTask` | Durable authoring object created from task-like user intent before execution is valid. | [Authoring Domain](authoring-domain.md) |
| `DraftTaskTree` | Editable authoring plan. It is not executable until published. | [Authoring Domain](authoring-domain.md), [Task/UI separation](task-domain-ui-model-separation.md) |
| `PublishedTask` | Execution-domain unit of work. It is the only Task object that enters TaskBus. | [Task](task.md) |
| `TaskBus` | PublishedTask lifecycle authority. Product 1.0 uses fixed-route claim/complete/fail; Product 1.1+ may add assignment convergence. | [TaskBus](bus.md) |
| `Execution Agent` | Task executor. Product 1.0 uses a fixed Default Agent route; later versions may use routed Agent templates and instances. | [Agent](agent.md) |
| `Context Manager` | Assembles execution context for stateless LLM calls from task, event, workspace, tool, skill, and permission facts. | [Context Manager](context-manager.md) |
| `MessageStream` | User-visible conversation, confirmation, and execution messages. | [Interaction Layer](interaction-layer.md), [UI/backend communication](ui-backend-communication.md) |
| `EventStream` | Append-only runtime fact ledger for replay, audit, and projections. | [Reference](reference.md), [TaskBus](bus.md) |

---

## 3. Authoring Domain

Authoring Domain exists so TaskBus does not absorb non-executable states such as
clarification, feasibility assessment, draft editing, or publish readiness.

```text
UserMessage
  -> RawTask
  -> FeasibilityReport / RawTaskAsk
  -> DraftTaskTree
  -> TaskPublisher
  -> PublishedTask
```

The stable rule is:

```text
Authoring objects do not enter Execution TaskBus.
Only PublishedTasks enter TaskBus.
```

Authoring state changes use [Authoring Command Protocol](authoring-command-protocol.md):

```text
LLM produces proposals.
AuthoringCommandService validates and persists commands.
Stores and messages are mutated only by command handlers.
```

This keeps exploratory authoring recoverable without making ordinary LLM tools
the source of truth for RawTask, DraftTaskTree, publish mapping, or authoring
messages.

---

## 4. Execution Domain

Execution Domain starts after a DraftTaskTree is published.

```text
TaskPublisher
  -> PublishedTask
  -> TaskBus
  -> executor / Agent runtime
  -> TaskResult or TaskFailure
```

TaskBus owns PublishedTask lifecycle facts:

```text
pending -> running -> done / failed
```

Product 1.0 uses the accepted fixed-route bridge:

```text
Published TaskBus Task
  -> FixedRouteTaskExecutor
  -> Resident Default Agent
  -> TaskBus complete / fail
```

This Product 1.0 path intentionally does not include:

- Router runtime;
- Routing Agent policy;
- Agent Manager;
- assignment fields;
- assigned-only claim;
- Main Page reassignment controls.

Routing Agent assignment and TaskBus-centered convergence remain accepted
architecture direction for Product 1.1+ when multiple execution Agents, custom
routing, or assignment visibility become real product needs.

---

## 5. Communication Boundaries

TaskWeavn distinguishes three mutation worlds.

| Mutation Target | Boundary | Notes |
|---|---|---|
| TaskWeavn authoring state | Authoring Commands | RawTask, DraftTaskTree, clarification asks, authoring messages, publish requests. |
| PublishedTask lifecycle | TaskBus commands | publish, claim, complete, fail, retry/skip semantics, interrupt intent. |
| User workspace state | Workspace Communication Protocol | files, commands, artifacts, project processes, future external providers. |

This boundary is central:

```text
Commands change TaskWeavn state.
Workspace Requests change user workspace state.
Tools are adapters, not the long-term top-level boundary.
```

The [Workspace Communication Protocol](workspace-communication-protocol.md) is
currently an architecture target, not a complete Product 1.0 implementation. It
defines the direction for turning current Tool classes into protocol adapters
behind a `WorkspaceGateway`.

---

## 6. UI And Projection Boundary

The UI consumes projections, not raw domain objects.

```text
Backend facts
  TaskDomain / DraftTaskNode / Message / Event / FileChange / ResultSummary
        |
        v
Projection services
        |
        v
UI ViewModels
        |
        v
Main Page / Audit Page
```

The communication pattern is Query / Command / Event:

| Type | Direction | Meaning |
|---|---|---|
| Query | UI -> backend | Read current ViewModel. |
| Command | UI -> backend | Submit user intent. Accepted does not mean final state. |
| Event | backend -> UI | Notify that backend facts changed. |

Main Page is the Product 1.0 control plane. It projects task state, execution
result/error summaries, file changes, messages, and confirmations. Audit Page is
the trust plane and owns deeper evidence, diagnostics, and review trails.

---

## 7. Agent Model

Agent architecture distinguishes:

```text
Agent Template
  stable capability, tools, LLM config, prompt, policy

Agent Instance
  runtime execution of one Task
```

The long-term model treats Execution Agents as stateless task executors. State
continues through TaskBus, EventStream, MessageStream, Workspace, result stores,
and Context Manager, not through hidden Agent object memory.

Product 1.0 uses a fixed Default Agent route:

```text
FixedRouteTaskExecutor
  -> ResidentDefaultAgent protocol
  -> task-scoped AgentLoop runner
```

The word "resident" means a stable runtime boundary and system identity. It
does not mean Product 1.0 introduces a long-lived AgentLoop instance, public
Agent Manager, or custom Agent protocol.

The default architecture has one active writer execution lane per Session. More
than one Agent may appear as serialized delegation, tool-like specialization, or
future isolated sub-session work, but multiple Agents do not concurrently write
the same Session Workspace or advance the same task context.

Product 1.1+ will define Agent Protocol and special Agent protocols before
custom Agents, Routing Agents, skills-driven Agents, or MCP-backed Agents become
user-extensible product features.

---

## 8. Context Governance

LLM calls are stateless, but Taskweavn execution is stateful. Context Manager is
the execution-time bridge:

```text
TaskBus / EventLog / Workspace / Tool Results / Skills / Permissions
        |
        v
Context Manager
        |
        v
TaskExecutionContext
        |
        v
LLM API input
```

Product 1.0 context governance is deterministic fact assembly:

- original task target;
- current execution state;
- recent bounded events;
- recent bounded tool summaries;
- workspace references;
- permission, approval, and interrupt facts;
- active project rules or skill summaries when already configured.

It does not yet implement semantic retrieval, long-term memory, complex
compression, multimodal packing, MCP expansion, or custom context policies.

---

## 9. Product 1.0 Constraints

Product 1.0 is intentionally constrained:

| Constraint | Current Meaning |
|---|---|
| Line-first UX | The product emphasizes current step, acceptance, and next decision over full tree orchestration. |
| One active Session workspace | File writes happen within a Session Workspace; cross-session merge/export is explicit future work. |
| One active writer execution lane | A Session has one context owner for workspace-writing execution; parallel Agents must be read-only, independently sharded, or workspace-isolated. |
| Fixed execution route | PublishedTasks execute through the default Agent bridge, not dynamic routing. |
| Simple Task status | `pending`, `running`, `done`, `failed`; cancellation and skip are represented through failure reason semantics when needed. |
| Deterministic context assembly | Context Manager starts as a simple fact assembler, not a semantic retrieval platform. |
| Projection over raw objects | UI reads ViewModels and snapshots, not TaskBus rows or store internals. |

These are release constraints, not permanent architecture limits.

---

## 10. Deferred Extension Paths

| Area | Deferred Until | Direction |
|---|---|---|
| Routing Agent assignment | Product 1.1+ | Router runtime with optional Routing Agent policy submits assignment commands; TaskBus validates. |
| Agent Manager | Product 1.1+ | Creates runtime Agent instances after assignment when dynamic Agents exist. |
| Parallel multi-Agent execution | Later, data-driven | Requires context ownership, read/write isolation, merge semantics, and replayable conflict handling. |
| Skills | Product 1.1+ research | Reusable capabilities and workflow context integrated through CapabilityCatalog, Authoring, Context Manager, and Agent Protocol. |
| MCP | Product 1.1+ research | External tools/data sources behind confirmation, capability, audit, and workspace boundaries. |
| File and multimodal context | Product 1.1+ research | Files and multimodal inputs become first-class Task context and evidence. |
| Result packaging cards | Product 1.1 | Rich card packaging on top of durable result summaries. |
| Completion-time task_after pipeline | Product 1.1 | Post-completion automation after the primary 1.0 loop is stable. |
| TaskBus v2 concurrency | Later, data-driven | Requires workspace isolation and conflict model before relaxing serial execution. |

---

## 11. Current Read Order

For new architecture or implementation work, read:

1. [README](README.md)
2. [Reference](reference.md)
3. [Task](task.md)
4. [Authoring Domain](authoring-domain.md)
5. [Authoring Command Protocol](authoring-command-protocol.md)
6. [Task Domain And UI ViewModel Separation](task-domain-ui-model-separation.md)
7. [UI And Backend Communication](ui-backend-communication.md)
8. [TaskBus](bus.md)
9. [Agent](agent.md)
10. [Tool Capability Layer](tool-capability-layer.md)
11. [Workspace Communication Protocol](workspace-communication-protocol.md)
12. [Context Manager](context-manager.md)

Feature-specific plans and ADRs should then be read for implementation scope.
