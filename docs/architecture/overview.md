# TaskWeavn Architecture Overview

> Status: active architecture overview
> Last Updated: 2026-07-10
> Version: v1.5
> Related Decisions: [ADR-0008](../decisions/ADR-0008-authoring-domain-execution-boundary.md), [ADR-0010](../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md), [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md), [ADR-0020](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)

This document is the current high-level architecture map for Plato / TaskWeavn.
It describes the implemented Product 1.1 local runtime, the additive Execution
Plane / Task API foundation, and the Product 1.0 fixed-route execution baseline
that still anchors local task execution.

TaskWeavn remains a Session-scoped local assistant system. The important Product
1.1 change is that ordinary Main Page input now enters a Runtime Input Router
before it can mutate product state or create workspace-changing execution work.
The later Product 1.1 platform change is that a service-compatible local Task
API now exists, but it is still backed by the embedded TaskBus path rather than a
remote multi-environment service.

---

## 1. Current Architecture Shape

The current architecture has a stable execution foundation plus a Product 1.1
runtime-input overlay and an additive Execution Plane service boundary:

```text
Stable execution foundation
  Authoring Domain -> PublishedTask -> TaskBus -> fixed Default Agent execution

Execution Plane foundation
  Local Task API / EmbeddedTaskApiService -> TaskBus -> fixed-route dispatcher

Product 1.1 runtime-input overlay
  Main Page input -> Runtime Input Router
    -> resolve active ASK / confirmation
    -> answer read-only inquiry
    -> record guidance / contract facts
    -> create execution work
```

The stable split between authoring and execution still holds:

```text
Authoring Domain
  turns fuzzy user intent into publishable work

Execution Domain
  executes confirmed PublishedTasks and projects results back to the UI
```

Product 1.1 adds the stricter loop boundary described in
[Contract Revision And Execution Loops](contract-revision-and-execution-loops.md):

```text
Contract Revision Loop
  routes user input, answers read-only questions, and revises Session / Plan /
  TaskNode contract facts

Contract Execution Loop
  executes published PublishedTasks and may change the user workspace
```

The boundary rule is:

```text
User language does not directly write the workspace.
Router decisions may change product contract state.
Only execution tasks may change workspace files or processes.
```

The current end-to-end shape is:

```text
Main Page / Electron renderer
  -> Runtime Input Route API
  -> Runtime Input Router
      -> Read-Only Inquiry Context
      -> Contract Revision Commands
      -> Authoring / Plan / TaskNode commands
      -> Execution handoff
  -> durable MessageStream Activity / Conversation records
  -> UI projections

Local Task API path
  -> TaskRequest
  -> EmbeddedTaskApiService
  -> TaskBus
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor
  -> Resident Default Agent task run or optional runtime handler

Execution handoff
  -> RawTask / DraftTaskTree or PlanTaskNode work
  -> TaskPublisher
  -> PublishedTask
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Resident Default Agent task run
  -> TaskBus complete / fail / waiting_for_user
  -> Main Page / Activity / Audit / diagnostics projections
```

TaskBus remains authoritative for executable work. Runtime Input Router is not
an execution-agent assignment system; it is the contract-facing input boundary.
The local Execution Plane Task API is a service-compatible facade over that same
execution authority. Remote worker claim/lease/heartbeat, external app auth, and
multi-environment dispatch remain later work.

---

## 2. Core Objects

| Object | Responsibility | Canonical Docs |
|---|---|---|
| `Project` | Long-lived product container for user work. It is a UI/product organization layer, not the default file write boundary. | [UI/backend communication](ui-backend-communication.md) |
| `Workflow` | Product-level grouping under a Project. It can organize related Sessions and future reusable flows. | [Workflow Session Task UX Model](../product/workflow-session-task-ux-model.md) |
| `Session` | Runtime boundary for one interaction context, continuous conversation, active work, execution facts, projections, and audit evidence. | [Session](session.md) |
| `Workspace root` | File and process boundary for execution. The selected workspace root is the Agent cwd; product facts live under `.plato` stores and are isolated by `workspace_id` / `session_id`. | [Session](session.md), [Workspace Communication Protocol](workspace-communication-protocol.md) |
| `RawTask` | Durable authoring object created from task-like user intent before execution is valid. | [Authoring Domain](authoring-domain.md) |
| `DraftTaskTree` | Editable authoring plan. It is not executable until published. | [Authoring Domain](authoring-domain.md), [Task/UI separation](task-domain-ui-model-separation.md) |
| `Plan` / `PlanTaskNode` | Durable Session-level active-work projection created from DraftTaskTree and synchronized from PublishedTask execution. | [Task/UI separation](task-domain-ui-model-separation.md), [Plan cycle semantics](../product/plato-plan-cycle-semantics.md) |
| `PublishedTask` | Execution-domain unit of work. It is the only Task object that enters TaskBus. | [Task](task.md) |
| `TaskBus` | PublishedTask lifecycle authority: publish, claim, complete, fail, wait/resume for user, retry/skip, and cooperative interrupt. | [TaskBus](bus.md) |
| `TaskRequest` / `TaskExecution` | Execution Plane service-level task publish/query contract. Local Product 1.1 exposes `/api/v1/tasks` and workspace-prefixed task routes through `EmbeddedTaskApiService`; remote service extraction remains later. | [ADR-0020](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md), [Execution Plane plan](../plans/feature/execution-plane-service-task-api.md) |
| `ExecutionEnv` | Local capability/tool-pool advertisement used by `EmbeddedTaskApiService` for compatibility checks. Registry and model foundation exist; distributed env registration, claim, lease, and heartbeat are not current Product 1.1 runtime behavior. | [TaskBus service memo](taskbus-service-multi-execution-env.md), [Execution Plane plan](../plans/feature/execution-plane-service-task-api.md) |
| `RuntimeInputRouteRequest` / `RuntimeInputRouteResult` | Main Page input contract. It carries user content, current selection, client state, Router decision, outcome, optional command response, optional inquiry result, and Activity projection. | [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md), [API contract](../engineering/runtime-input-router-api-contract.md) |
| `ReadOnlyInquiryRequest` / `ReadOnlyInquiryResult` | No-mutation question-answering contract over Session, Plan, Task, Activity, Audit, diagnostics, file, and diff evidence refs. | [Read-Only Inquiry Context](../plans/feature/read-only-inquiry-context.md) |
| `ContractCommandRequest` / `ContractCommandResult` | Product-state mutation boundary for guidance, ASK/confirmation resolution, and execution-task creation. | [Contract Revision And Execution Loops](contract-revision-and-execution-loops.md), [Contract Revision Command Skills](../plans/feature/contract-revision-command-skills.md) |
| `Execution Agent` | Task executor. Product 1.1 still uses a fixed Default Agent execution lane. | [Agent](agent.md) |
| `Agent LLM Resolver` | Backend-only role-aware LLM configuration for runtime router, execution agent, collaborator, read-only inquiry, audit, and summary roles. | [Agent LLM Config And Router LLM](../plans/feature/agent-llm-config-and-router-llm.md) |
| `Context Manager` | Assembles cache-aware execution context for stateless LLM calls from task, event, workspace, tool, permission, guidance, and ASK facts. | [Context Manager](context-manager.md) |
| `AskStore` | Durable execution ASK state. AskStore owns pending/answered/deferred/cancelled state; TaskBus resumes only after answer persistence. | [UI/backend communication](ui-backend-communication.md) |
| `MessageStream` | User-visible Session conversation, Router traces, ASK history, confirmations, execution messages, and durable Activity replay. | [Interaction Layer](interaction-layer.md), [Session Content Model](../product/plato-session-content-model.md) |
| `EventStream` / `UiEventStore` | Append-only runtime and UI fact ledgers for replay, sidecar SSE, audit, and projections. | [Reference](reference.md), [TaskBus](bus.md) |
| `WorkspaceInspectionGateway` | Read-only file/diff/evidence inspection boundary for UI, Audit, Read-Only Inquiry, and diagnostics. | [Workspace Inspection Milestone](../plans/feature/product-1-1-workspace-inspection-milestone.md) |
| `SettingsConfig` | Global/local sidecar settings for LLM, logging, diagnostics, web search, and web fetch readiness. | [UI/backend communication](ui-backend-communication.md) |
| `TokenUsageStore` | Workspace-scoped LLM usage ledger and summary source for analytics and diagnostics. | [Product 1.1 Open Work](../product/plato-1-1-open-work.md) |
| `Electron Sidecar` | Local desktop shell that shows startup UI, starts the Python sidecar, forwards runtime config, and packages release assets. | [Public Exposure Plan](../product/public-exposure/plato-public-exposure-plan.md), [Product 1.1 release evidence](../releases/product-1-1-runtime-input-router-release-evidence.md) |

---

## 3. Runtime Input And Contract Revision

Runtime Input Router is the Product 1.1 front door for Main Page input. It is a
safe classifier and dispatcher, not a workspace tool runner. The current router
has deterministic routes plus an optional LLM route planner. The planner can
propose only whitelisted dispatch targets and every proposal is validated before
any command-backed side effect.

```text
RuntimeInputRouteRequest
  -> active ASK / confirmation resolution
  -> deterministic stop / retry command
  -> LLM or deterministic route planning
  -> dispatch target
```

The current dispatch targets are:

| Dispatch target | Side effect | Boundary |
|---|---|---|
| `read_only_inquiry` | `no_effect` | Answer from bounded Session / workspace inspection evidence. |
| `record_guidance` | `context_effect` | Persist guidance as contract facts. |
| `resolve_ask` | `resume_effect` | Persist an ASK answer and resume the blocked task when allowed. |
| `resolve_confirmation` | `authorization_effect` | Persist confirmation choice and trigger the authorized command. |
| `execution_handoff` | `state_effect` | Create executable contract work without directly touching workspace files. |
| `clarification` / `unsupported` | `no_effect` | Ask for more information or reject unsafe input. |

These routes are dependency-gated. If the contract revision service,
interaction handler, task-node handler, read-only inquiry service, or execution
trigger gateway required for a route is not configured, the router returns an
unsupported or rejected outcome and does not mutate workspace files.

Router outcomes are durable. The Activity publisher writes:

- the user input;
- a user-visible Router interpretation;
- a question card when the Router asks for more information;
- the final read-only answer or command outcome.

Frontend rendering uses a protocol in `conversation_render` so Conversation can
display plain text, router traces, and structured question cards without
hardcoding backend internals.

Contract Revision Commands own product-state mutation. LLM output can propose a
route, but command handlers validate and persist changes. The Router cannot
invent arbitrary backend commands or workspace edits.

Current negative boundary: natural-language "publish plan" is not a deterministic
Router route. Existing publish remains an explicit command path over Authoring /
Plan / TaskPublisher boundaries.

---

## 4. Read-Only Inquiry Context

Read-Only Inquiry answers questions without mutating product or workspace state.
It is used for questions such as:

- "Is this plan finished?"
- "What changed in this file?"
- "Why is this task waiting?"
- "What does this Audit evidence show?"
- "What does this diagnostic mean?"

The service builds a bounded evidence set from:

- Session / Plan / Task snapshots;
- Activity and MessageStream records;
- Audit records and evidence;
- result summaries;
- workspace file and diff inspection;
- diagnostic support descriptors.

An optional guarded LLM answer provider may rewrite the baseline answer into a
more natural response, but it must cite known evidence refs and cannot request
tools, commands, file edits, TaskBus work, or hidden context.

Read-Only Inquiry is intentionally separate from execution. It can inspect and
answer; it cannot create or modify workspace files.

---

## 5. Authoring Domain

Authoring Domain exists so TaskBus does not absorb non-executable states such as
clarification, feasibility assessment, draft editing, or publish readiness.

```text
RawTask
  -> FeasibilityReport / RawTaskAsk
  -> DraftTaskTree
  -> Plan / PlanTaskNode projection
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

Product 1.1 Runtime Input can create execution work through Contract Revision,
but the publish boundary remains TaskPublisher -> PublishedTask -> TaskBus.

---

## 6. Execution Domain

Execution Domain starts after a DraftTaskTree or PlanTaskNode is published into
PublishedTasks, or after a service-level TaskRequest is accepted by the local
embedded Task API.

```text
TaskPublisher
  -> PublishedTask
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Resident Default Agent
  -> TaskResult or TaskFailure
```

The additive Task API path maps service-level requests into the same local
execution substrate:

```text
TaskRequest
  -> EmbeddedTaskApiService
  -> TaskExecution + ExecutionPlaneStore event
  -> TaskBus PublishedTask
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor / Resident Default Agent
```

TaskBus owns PublishedTask lifecycle facts:

```text
pending -> running -> done
                |
                -> waiting_for_user -> running / failed
                -> failed
```

Skip and cooperative cancel/stop are represented through TaskBus failure or
interrupt semantics with user-visible reasons. The UI may project richer labels
such as stopping or cancelled, but TaskBus remains the lifecycle authority.

Product 1.1 still uses the fixed-route execution bridge:

```text
Published TaskBus Task
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor
  -> Resident Default Agent
  -> TaskBus complete / fail / wait_for_user
```

This current path does not yet include dynamic Agent assignment, public Agent
Manager controls, assigned-only TaskBus claim semantics, remote worker claim /
lease / heartbeat, or public external-app auth.

---

## 7. Communication Boundaries

TaskWeavn distinguishes product-state mutation from workspace mutation.

| Mutation Target | Boundary | Notes |
|---|---|---|
| Authoring state | Authoring Commands | RawTask, DraftTaskTree, authoring asks, authoring messages, publish requests. |
| Contract revision state | Contract Revision Commands | guidance, ASK / confirmation resolution, execution-task creation, TaskNode contract edits. |
| Execution ASK state | AskStore commands | create, answer, defer, cancel, expire; answer persistence precedes TaskBus resume. |
| PublishedTask lifecycle | TaskBus commands | publish, claim, complete, fail, wait_for_user/resume_after_user, retry/skip, interrupt. |
| Service-level task execution | Execution Plane Task API | local `/api/v1/tasks` publish/query/cancel/retry/events/result/error/evidence shell over `TaskApiService`; local-only and embedded in Product 1.1. |
| User workspace state | Workspace tools / Workspace Communication Protocol | file reads/writes, commands, artifacts, project processes, future external providers. |
| External web state | Web retrieval providers | `web_search` and `web_fetch` read public external sources only; returned content is evidence, not instructions. |
| Diagnostics / settings | Sidecar settings and diagnostics gateways | local configuration, readiness, diagnostic bundle export, usage summaries. |

This boundary is central:

```text
Commands change TaskWeavn state.
Execution tools change user workspace state.
Web retrieval tools read public external state.
Tools are adapters, not the top-level product boundary.
Execution Plane API accepts execution work but the current embedded service still
delegates executable lifecycle authority to TaskBus.
```

The [Workspace Communication Protocol](workspace-communication-protocol.md) is
still the direction for turning current Tool classes into protocol adapters
behind a `WorkspaceGateway`.

---

## 8. UI, Projection, And Trust Boundary

The UI consumes projections, not raw domain objects.

```text
Backend facts
  TaskDomain / PlanTaskNode / Message / Event / FileChange / ResultSummary /
  RuntimeInput / Usage / Diagnostic / Inspection facts
        |
        v
Projection services
        |
        v
UI ViewModels
        |
        v
Main Page / Conversation / Activity / Audit / Settings / Inspection / Usage
```

The communication pattern is Query / Command / Event:

| Type | Direction | Meaning |
|---|---|---|
| Query | UI -> backend | Read current ViewModel or evidence. |
| Command | UI -> backend | Submit user intent. Accepted does not mean final state. |
| Event | backend -> UI | Notify that backend facts changed. |

Main Page is the control and conversation surface. It projects Session
conversation, active Plan / Task state, Router traces, execution result/error
summaries, pending ASK and confirmation controls, file changes, Activity, token
usage entry points, and Audit entry points.

Audit Page is the trust plane for deeper evidence, diagnostics, and review
trails. Workspace Inspection is a read-only evidence surface for files and diffs.
Diagnostics export packages runtime, Router, usage, logs, and evidence summaries
for support.

---

## 9. Agent, LLM, And Tool Model

Agent architecture distinguishes:

```text
Agent Template
  stable capability, tools, LLM config, prompt, policy

Agent Instance
  runtime execution of one Task
```

The long-term model treats Execution Agents as stateless task executors. State
continues through TaskBus, EventStream, MessageStream, Workspace, result stores,
Context Manager, and usage ledgers, not through hidden Agent object memory.

Product 1.1 uses role-aware backend LLM resolution:

```text
Settings-backed Agent LLM Resolver
  -> runtime_input_router
  -> execution_agent
  -> collaborator
  -> read_only_inquiry
  -> audit_agent / summary_agent extension roles
```

The resolver is backend-only for now. The Settings UI exposes global LLM and web
retrieval configuration, but not per-Agent role bindings.

The default execution Agent currently has these tool families when configured:

- workspace file tools, including precision file range tools;
- workspace search and shell command tools;
- `ask_user` for execution ASK;
- `web_search` for current public facts;
- `web_fetch` for bounded extraction of public URLs.

Web retrieval is not semantic memory. It is external evidence retrieval with
provider policy, URL policy, truncation, and prompt guidance that treats external
content as untrusted evidence.

The default architecture still has one active writer execution lane per Session.
Multiple Agents may appear later as serialized delegation, tool-like
specialization, or isolated sub-session work, but multiple Agents do not
concurrently write the same workspace root for the same Session.

---

## 10. Context Governance

LLM calls are stateless, but Taskweavn execution is stateful. Context Manager is
the execution-time bridge:

```text
TaskBus / EventLog / Workspace / Tool Results / Permissions / Guidance / ASK
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

Current context governance is deterministic fact assembly with cache-aware
append-only rendering:

- original task target;
- current execution state;
- recent bounded events;
- recent bounded tool summaries;
- workspace references;
- permission, approval, ASK, confirmation, and interrupt facts;
- active project rules and explicit guidance;
- web retrieval guidance when web tools are enabled.

`SessionContextManager` builds execution context, persists snapshots/traces, and
provides rendered messages before each Default Agent `llm.chat(...)` call. The
first call establishes a stable start context; later calls preserve the
AgentLoop transcript and append bounded delta/checkpoint messages when policy
requires new context facts.

It does not yet implement semantic retrieval, general long-term memory, complex
compression, multimodal packing, MCP expansion, or custom context policies.

---

## 11. Local App, Settings, And Release Runtime

Product 1.1 is delivered as a local Electron app backed by a Python sidecar.

```text
Electron main process
  -> shows workspace entry / startup shell
  -> starts Python sidecar
  -> waits for sidecar health
  -> injects renderer runtime config
  -> loads React Main Page
```

Settings are stored through the sidecar and can use a global settings root. The
current settings contract covers:

- LLM provider/model/API key readiness;
- logging profile and diagnostics readiness;
- web search and web fetch provider/API key readiness;
- diagnostic bundle export availability.

Token usage analytics records provider-reported LLM usage by workspace, session,
plan, task, and request purpose. The UI exposes summaries; diagnostics export
redacted usage summaries.

The sidecar also wires a local Execution Plane foundation: `SqliteExecutionPlaneStore`
is stored under the workspace `.plato` metadata directory, `EmbeddedTaskApiService`
is injected into the HTTP transport, and optional runtime handlers such as local
WeChat send are registered only when the relevant computer-use capability and
backend are enabled.

Packaging and smoke scripts live in the frontend package because Electron is
the product shell. Production packaging excludes obvious test and smoke-only
code from public DMG assets, while smoke packages can opt in to test fixtures.

---

## 12. Product 1.1 Current Constraints

| Constraint | Current Meaning |
|---|---|
| Router-first Main Page input | Main Page input should route through Runtime Input Router when the backend supports it; legacy append-session input remains compatibility fallback. |
| No direct workspace writes from user chat | Read-only inquiry and contract revision can answer or mutate product state; workspace changes require execution handoff and task execution. |
| Workspace-root execution with Session fact isolation | Agent file writes happen in the selected workspace root. Session facts, events, context, asks, usage, and projections are isolated by `.plato` storage and IDs. |
| One active writer execution lane | A Session has one context owner for workspace-writing execution; parallel Agents must be read-only, independently sharded, or workspace-isolated. |
| Fixed execution route | PublishedTasks execute through the default Agent bridge, not dynamic Agent assignment. |
| Embedded Execution Plane only | Service-level Task API routes exist locally and are backed by TaskBus; remote workers, external auth, callbacks, and distributed leases are deferred. |
| Evidence-first trust plane | Audit, Activity, Workspace Inspection, diagnostics, and usage summaries are first-class support and review surfaces. |
| Role-aware LLM resolution is backend-only | Agent LLM roles are configurable in backend settings, but per-role UI is not exposed yet. |
| Web retrieval is bounded evidence | `web_search` and `web_fetch` are optional, settings-gated, public-source-only execution tools. |
| Projection over raw objects | UI reads ViewModels and snapshots, not TaskBus rows or store internals. |

These are release constraints, not permanent architecture limits.

---

## 13. Deferred Extension Paths

| Area | Deferred Until | Direction |
|---|---|---|
| Routing Agent assignment | Later Product 1.1+ / Product 1.2 | Router or Routing Agent policy submits assignment commands; TaskBus validates. |
| Agent Manager | After dynamic assignment has product need | Creates runtime Agent instances after assignment when dynamic Agents exist. |
| Parallel multi-Agent execution | Later, data-driven | Requires context ownership, read/write isolation, merge semantics, and replayable conflict handling. |
| User-extensible skills | Later Product 1.1+ research | Reusable capabilities and workflow context integrated through CapabilityCatalog, Authoring, Context Manager, and Agent Protocol. |
| MCP | Later Product 1.1+ research | External tools/data sources behind confirmation, capability, audit, and workspace boundaries. |
| Semantic retrieval / long-term memory | Later, after deterministic context is stable | Retrieval and memory become explicit context sources with evidence, policies, and cache boundaries. |
| Multimodal context | Later Product 1.1+ research | Images and other media become first-class Task context and evidence. |
| TaskBus v2 concurrency | Later, data-driven | Requires workspace isolation and conflict model before relaxing serial execution. |
| Remote Execution Plane service | Later Product 1.1+ / Product 1.2 | External app auth, callback policy enforcement, worker registration, claim / lease / heartbeat, and multi-env recovery. |

---

## 14. Current Read Order

For new architecture or implementation work, read:

1. [README](README.md)
2. [Reference](reference.md)
3. [Task](task.md)
4. [Authoring Domain](authoring-domain.md)
5. [Authoring Command Protocol](authoring-command-protocol.md)
6. [Task Domain And UI ViewModel Separation](task-domain-ui-model-separation.md)
7. [UI And Backend Communication](ui-backend-communication.md)
8. [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md)
9. [Runtime Input Router Technical Design](../plans/feature/runtime-input-router-contract-technical-design.md)
10. [Read-Only Inquiry Context](../plans/feature/read-only-inquiry-context.md)
11. [Read-Only Inquiry Technical Design](../plans/feature/read-only-inquiry-context-technical-design.md)
12. [Agent LLM Config And Router LLM](../plans/feature/agent-llm-config-and-router-llm.md)
13. [Contract Revision And Execution Loops](contract-revision-and-execution-loops.md)
14. [TaskBus](bus.md)
15. [ADR-0020: Execution Plane As Service / Task API Boundary](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)
16. [Execution Plane Service And Task API Plan](../plans/feature/execution-plane-service-task-api.md)
17. [Agent](agent.md)
18. [Tool Capability Layer](tool-capability-layer.md)
19. [Workspace Communication Protocol](workspace-communication-protocol.md)
20. [Context Manager](context-manager.md)
21. [Product 1.1 Open Work](../product/plato-1-1-open-work.md)
22. [Product 1.1 Runtime Input Router Release Evidence](../releases/product-1-1-runtime-input-router-release-evidence.md)

Feature-specific plans and ADRs should then be read for implementation scope.
