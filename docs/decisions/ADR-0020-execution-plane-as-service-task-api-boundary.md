# ADR-0020: Execution Plane As Service / Task API Boundary

> Status: accepted direction
> Date: 2026-06-18
> Related:
> [TaskBus service and multi-execution-env memo](../architecture/taskbus-service-multi-execution-env.md),
> [Task domain](../architecture/task.md),
> [TaskBus v2](../architecture/bus-v2.md),
> [Agent architecture](../architecture/agent.md),
> [Tool capability layer](../architecture/tool-capability-layer.md),
> [Workspace communication protocol](../architecture/workspace-communication-protocol.md),
> [Context manager](../architecture/context-manager.md),
> [UI/backend communication](../architecture/ui-backend-communication.md)

---

## Context

Plato started as a task-first Agent product. As the system evolved, several
capabilities became clearly reusable outside the Plato UI:

- Task publication and lifecycle tracking;
- TaskBus execution authority;
- AgentLoop execution;
- tool and capability governance;
- event, result, evidence, and audit traces;
- execution environment routing and recovery.

Emerging vertical scenarios, especially ecommerce operations, show that the
valuable platform layer is not a specific UI screen. The valuable layer is a
general execution substrate that can accept work from different applications,
route it to capable execution environments, run Agents with tools, and return
structured results and evidence.

Examples:

- Plato publishes tasks from a Session / Plan / TaskNode.
- An ecommerce CRM publishes a task to contact an influencer.
- An internal operations system publishes a task to reconcile sales feedback
  with product iteration notes.
- A workflow tool publishes a task that requires a specific desktop
  environment with browser, email, or computer-use capability.

If Execution remains only a Plato internal module, these scenarios will either
duplicate runtime infrastructure or force unrelated business semantics into
Plato's product model.

At the same time, directly turning the Execution Agent into a vertical business
brain would pollute the execution boundary. Execution Agents should execute
bounded tasks. Business meaning belongs in workflow packages, task schemas,
hooks, and external applications.

---

## Decision

Treat the Execution Plane as a service-capable runtime boundary.

Plato is one client of this boundary, not the sole owner of it.

The Execution Plane must be able to run in two deployment modes:

1. **Embedded / in-process mode** for the current Plato product path.
2. **Service mode** for external applications that publish tasks through a
   Task API.

The boundary is logical first. Physical service extraction is a later step.

```text
Plato Product / Control Plane
  -> Task API client
  -> Execution Plane

External Business Apps
  -> Task API client
  -> Execution Plane

Execution Plane
  -> Task intake
  -> queue / claim / lease
  -> Agent runtime
  -> tool runtime
  -> event stream
  -> result and evidence stores
```

### 1. Plane Boundaries

#### Product / Control Plane

The Product / Control Plane owns user-facing product semantics:

- Workspace and Session UX;
- RawTask and DraftTaskTree authoring;
- Plan / TaskNode presentation;
- ASK, confirmation, guidance, and user interaction;
- route state and UI projection;
- mapping a Plato TaskNode into an execution request.

It does not own low-level task execution mechanics once a task is published for
execution.

#### Execution Plane

The Execution Plane owns execution mechanics:

- Task API intake;
- idempotent task creation;
- task lifecycle state for execution;
- execution environment registration;
- capability and permission matching;
- claim / lease / heartbeat;
- Agent runtime instantiation;
- tool runtime and tool policy application;
- event emission;
- result and error summaries;
- evidence references;
- retry, cancellation, and recovery semantics.

The Execution Plane must not depend on Plato Session semantics. It may accept
Plato-derived metadata, but its core contracts must be usable by external
applications.

#### Audit Plane

The Audit Plane is a read-side trust layer:

- consumes task events, evidence refs, file summaries, and result summaries;
- builds user-readable audit records;
- explains what happened and why;
- supports traceability and review.

Audit should not block the normal execution path unless a later policy feature
explicitly introduces pre-execution compliance gates.

### 2. Canonical Execution Plane Objects

The Execution Plane should converge on the following service-level objects:

```text
TaskRequest
TaskExecution
TaskEvent
TaskResult
TaskError
EvidenceRef
ExecutionEnv
CapabilityPolicy
Requester
ExternalRef
CallbackPolicy
```

Plato objects map into these objects:

```text
Plato Session / Plan / TaskNode
  -> TaskRequest
  -> TaskExecution
  -> TaskEvent / TaskResult / EvidenceRef
  -> Plato projection
```

External systems should not need to know about Plato Session, DraftTaskTree, or
MainPageSnapshot.

### 3. Task API Boundary

The Task API is the stable publish/query/control boundary for execution.

Minimum candidate API surface:

```text
POST /tasks
GET /tasks/{task_id}
POST /tasks/{task_id}/cancel
POST /tasks/{task_id}/retry
GET /tasks/{task_id}/events
GET /tasks/{task_id}/result
GET /tasks/{task_id}/evidence
```

Distributed execution later adds environment APIs:

```text
POST /execution-envs/register
POST /execution-envs/{env_id}/heartbeat
POST /execution-envs/{env_id}/claim
POST /execution-envs/{env_id}/tasks/{task_id}/events
POST /execution-envs/{env_id}/tasks/{task_id}/result
```

The first implementation does not need to expose all endpoints over HTTP. The
contract should still be designed as if the boundary can become HTTP or RPC.

### 4. Task Request Requirements

Task publication must not mean "run arbitrary free text with every tool".

Every accepted task request must carry enough boundary information to enforce
policy and support recovery:

```text
idempotency_key
requester identity
external_ref, when applicable
task_type
intent
input payload
required capability
allowed / denied tools
workspace or environment boundary
permission policy
human confirmation policy
timeout / budget
expected result contract
evidence requirements
callback / subscription policy
```

Plato can derive many of these from Session, TaskNode, user settings, and
workspace configuration. External applications must provide them explicitly or
through registered defaults.

### 5. Execution Environment Model

An execution environment is a machine, sandbox, browser profile, or local
runtime that can execute tasks with a concrete tool pool.

It is not equivalent to an Agent.

```text
ExecutionEnv
  - env_id
  - display_name
  - status
  - capabilities
  - tool_pool
  - permission_profile
  - workspace_roots
  - active_task_id
  - heartbeat
  - runtime version
```

An Agent is instantiated for a task inside an environment. The Agent may be
short-lived while session/workspace context persists outside the Agent
lifecycle.

### 6. Capability And Permission Matching

Execution dispatch must be capability-first:

```text
TaskRequest.required_capability
  -> candidate ExecutionEnv
  -> env tool pool
  -> permission merge
  -> Agent template / skill context
  -> execution
```

Tool availability must be environment-scoped. The system must not assume every
Agent has every tool.

High-risk tools such as computer use, desktop automation, outbound messaging,
and credentialed browser sessions require explicit policy and evidence.

### 7. Evidence And Result Contract

Execution must produce durable outputs beyond final prose:

- result summary;
- structured result payload, when task type defines one;
- error summary and retryability;
- evidence refs;
- tool observations;
- business events emitted by hooks;
- audit-ready trace metadata.

The result contract is part of the Task API. A task may complete with a human
readable summary, but external clients need stable queryable objects.

### 8. Vertical Workflow Packages

Vertical workflows should live outside the Execution Plane core.

Examples:

- ecommerce influencer outreach;
- customer feedback triage;
- product iteration issue detection;
- campaign cost reconciliation;
- supplier follow-up.

Each package defines:

- task types;
- schemas;
- required capabilities;
- result contracts;
- evidence requirements;
- hook behavior;
- knowledge update rules;
- human review rules.

This prevents vertical business logic from leaking into TaskBus, AgentLoop, or
tool runtime code.

---

## Consequences

### Positive

- Plato can continue as the first product client without blocking service
  evolution.
- External applications can publish tasks without adopting Plato's Session UI.
- Ecommerce and other vertical scenarios can reuse AgentLoop, TaskBus, tools,
  events, results, and evidence.
- Execution environments can eventually run on separate machines.
- Audit can remain a read-side consumer rather than an execution dependency.
- Tool policy and capability matching become explicit instead of implicit.

### Trade-offs

- API and identity boundaries become more important earlier.
- TaskRequest must be stricter than a raw natural-language string.
- Service mode requires idempotency, leases, heartbeats, and recovery semantics.
- The codebase needs to resist leaking Plato UI concepts into execution
  contracts.
- Vertical workflow packages require their own schemas and acceptance criteria.

### Risks

| Risk | Mitigation |
|---|---|
| Execution Plane becomes too abstract before Product 1.0 closes | Keep service extraction logical first; do not block 1.0 UI/runtime closure. |
| External Task API becomes unsafe "run anything" endpoint | Require requester, capability, permission, workspace, budget, and evidence policy. |
| Plato Session semantics leak into external API | Keep TaskRequest and TaskExecution independent of Session/DraftTaskTree/MainPageSnapshot. |
| Vertical ecommerce logic pollutes core runtime | Put vertical task schemas, hooks, and knowledge rules in packages outside Execution core. |
| Distributed workers duplicate or stale-execute tasks | Use idempotency, claim, lease, heartbeat, and structured recovery states. |
| Audit accidentally blocks execution | Keep Audit Plane read-side unless an explicit compliance gate is added later. |

---

## Implementation Direction

This ADR does not require immediate service extraction.

Recommended phases:

1. **In-process boundary**
   - Define service-like interfaces around task intake, execution request,
     event sink, result store, evidence store, and execution environment.
   - Plato calls these interfaces directly.

2. **Local service shell**
   - Add an HTTP/RPC-shaped adapter while still running locally.
   - Preserve existing Product 1.0 behavior.

3. **Execution environment registry**
   - Register envs with capabilities and tool pools.
   - Add heartbeat and health state.

4. **Claim / lease protocol**
   - Allow compatible environments to claim work.
   - Prevent duplicate execution.
   - Support recovery after restart or lease expiry.

5. **External Task API**
   - Allow non-Plato clients to publish tasks.
   - Enforce requester identity, idempotency, permissions, and result contracts.

6. **First vertical proof**
   - Prefer an email/browser-based ecommerce operations workflow before
     high-risk WeChat/computer-use automation.

---

## Non-Goals

This ADR does not decide to:

- split the repository immediately;
- deploy a remote service immediately;
- replace Plato's current local execution path immediately;
- make computer use the default execution mode;
- expose unrestricted task execution to external callers;
- merge Product / Execution / Audit Plane responsibilities;
- build a full ecommerce platform inside Plato Core;
- implement dynamic multi-Agent scheduling for Product 1.0.

---

## Open Questions

1. What is the first accepted external task type for service validation?
2. Which authentication model should the first Task API use?
3. How should external callbacks be retried and signed?
4. What result schema should the first vertical workflow require?
5. Which evidence types are mandatory for desktop/computer-use execution?
6. How much of the current TaskBus state model should be reused directly vs
   wrapped in service DTOs?
7. Should execution environments be tenant-scoped, workspace-scoped, or both?

---

## Decision Test

Future implementation should satisfy these tests before claiming this ADR is
implemented:

1. Plato can publish a task through the same execution boundary external apps
   would use.
2. An external app can publish a typed task without knowing Plato Session
   internals.
3. Task execution state, events, result, and evidence can be queried through
   service-level identifiers.
4. Capability and tool permission policy are explicit in the task or inherited
   from a registered policy.
5. A task cannot be double-executed after retry, restart, or duplicate publish.
6. Audit can consume execution events without being required for the task to
   run.
