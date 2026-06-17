# Execution Plane Service And Task API Plan

> Status: in progress / foundation implementation in review
>
> Last Updated: 2026-06-18
>
> Gap: Product 1.1 needs Execution Plane to serve both Plato and external applications through a stable Task API.
>
> ADR: [ADR-0020 Execution Plane As Service / Task API Boundary](../../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)
>
> Technical Design: [Execution Plane Service And Task API Technical Design](execution-plane-service-task-api-technical-design.zh-CN.md)
>
> Architecture:
> [TaskBus service and multi-execution-env memo](../../architecture/taskbus-service-multi-execution-env.md),
> [Task domain](../../architecture/task.md),
> [TaskBus v2](../../architecture/bus-v2.md),
> [Agent architecture](../../architecture/agent.md),
> [Tool capability layer](../../architecture/tool-capability-layer.md),
> [Workspace communication protocol](../../architecture/workspace-communication-protocol.md),
> [Context manager](../../architecture/context-manager.md),
> [UI/backend communication](../../architecture/ui-backend-communication.md)

---

## 1. Problem / Gap

Plato's execution substrate is becoming valuable outside the Plato UI:

- Task publication and lifecycle tracking;
- TaskBus execution authority;
- AgentLoop execution;
- tool and capability governance;
- event, result, evidence, and audit traces;
- execution environment routing and recovery.

Current implementation is still product-internal. Plato Session / Plan /
TaskNode semantics are close to the runtime path, and external applications do
not have a stable way to publish tasks, observe execution, query results, or
attach evidence.

This blocks Product 1.1 scenarios such as:

- ecommerce operations systems publishing outreach or reconciliation tasks;
- a CRM creating a task that must run on a specific desktop environment;
- another application using Plato's AgentLoop and tool runtime without adopting
  Plato's Main Page or Session UX.

The product needs a service-capable Execution Plane without disrupting Product
1.0 closure.

## 2. Product Decision

Execution Plane becomes a reusable runtime boundary.

Plato remains the first client. External apps become later clients.

```text
Plato Product / Control Plane
  -> Task API client
  -> Execution Plane

External Apps
  -> Task API client
  -> Execution Plane
```

The first implementation should be logical, not physical:

- keep embedded/in-process mode for Plato;
- design contracts as service-compatible;
- avoid remote deployment and auth complexity until the local boundary is
  stable.

## 3. Goals

1. Define a service-level `TaskRequest` / `TaskExecution` contract independent
   of Plato Session internals.
2. Add an in-process Task API boundary that Plato can call.
3. Preserve current Product 1.0 fixed-route execution behavior while routing it
   through the new boundary.
4. Define idempotency, requester, capability, permission, result, evidence, and
   callback fields before external API work.
5. Prepare ExecutionEnv registry, claim, lease, and heartbeat semantics.
6. Keep Audit Plane read-side and independent from task execution.
7. Reserve vertical workflow packages, such as ecommerce operations, outside
   Execution Plane core.

## 4. Non-Goals

- No immediate repo split.
- No immediate remote service deployment.
- No unrestricted public task execution endpoint.
- No cloud auth or multi-tenant SaaS auth in the first slice.
- No WeChat-first automation MVP.
- No default multi-Agent parallel execution.
- No Product 1.0 UI rewrite.
- No replacement of Plato Session / Plan / TaskNode UX.
- No business-specific ecommerce objects inside Execution Plane core.
- No Audit Plane blocking execution by default.

## 5. Source-Of-Truth Hierarchy

| Layer | Source |
|---|---|
| Durable architecture decision | ADR-0020 |
| Exploratory distributed execution context | `taskbus-service-multi-execution-env.md` |
| Current task lifecycle facts | `task.md`, existing TaskBus implementation |
| Agent lifecycle direction | `agent.md` |
| Tool/capability policy | `tool-capability-layer.md`, `workspace-communication-protocol.md` |
| Context behavior | `context-manager.md` |
| UI/product projection | `ui-backend-communication.md`, Product 1.0 Main Page implementation |

This plan must not override Product 1.0 closure requirements. It should create
an implementation path that gradually routes existing behavior through a better
boundary.

## 6. Target System Shape

```text
Task API Boundary
  - publish task
  - query task execution
  - cancel / retry
  - stream/query task events
  - query result / error / evidence

Execution Runtime
  - maps TaskRequest to TaskBus task
  - manages idempotency
  - runs AgentLoop through execution env/tool policy
  - emits TaskEvents
  - persists TaskResult / TaskError / EvidenceRef

Execution Env Registry
  - environment identity
  - capabilities
  - tool pool
  - status / heartbeat
  - claim / lease later
```

## 7. Canonical Objects

The Execution Plane should converge on these service-level concepts:

| Object | Meaning |
|---|---|
| `TaskRequest` | Incoming publish request from Plato or external app. |
| `TaskExecution` | Canonical execution lifecycle object. |
| `TaskEvent` | Append-only execution event emitted by runtime/env. |
| `TaskResult` | Durable success output and optional structured payload. |
| `TaskError` | Durable failure output with retryability and recovery hint. |
| `EvidenceRef` | Safe reference to screenshots, files, observations, diffs, or tool outputs. |
| `ExecutionEnv` | Machine/runtime/browser profile capable of executing work. |
| `CapabilityPolicy` | Required capability, allowed tools, denied tools, confirmation policy. |
| `Requester` | Caller identity and trust scope. |
| `ExternalRef` | Caller-owned object identity, such as CRM record or Plato TaskNode. |
| `CallbackPolicy` | Webhook/SSE/callback subscription contract. |

Plato maps:

```text
Session / Plan / TaskNode
  -> TaskRequest
  -> TaskExecution
  -> TaskEvent / TaskResult / EvidenceRef
  -> Main Page / Audit projections
```

## 8. Slice Plan

Implementation status as of 2026-06-18:

- EP0 model / DTO foundation is implemented in `src/taskweavn/execution_plane/`.
- EP1 embedded `TaskApiService` foundation is implemented over current TaskBus.
- EP3 local sidecar route shell is implemented as a thin adapter over the
  service boundary.
- Local default `ExecutionEnv` registry foundation is included.
- Result, error, event, and evidence query surfaces have focused tests.
- Full Plato Main Page runtime replacement, external app auth, callbacks,
  remote worker claim/lease/heartbeat, and vertical workflow packages remain
  later slices.

### EP0: Contract And DTO Closure

Goal: define models without changing runtime behavior.

Deliverables:

- service-level model definitions;
- serializer examples;
- error taxonomy;
- TaskRequest validation rules;
- focused tests for shape and unknown-field rejection.

Acceptance:

- Plato and external clients can be represented without Session-specific
  fields in the core DTOs.
- `TaskRequest` requires idempotency, requester, task type, intent,
  capability/policy, and evidence expectations.

### EP1: In-Process Task API Boundary

Goal: introduce a service-like interface that Plato can call without HTTP.

Deliverables:

- `TaskApiService` protocol;
- `EmbeddedTaskApiService` adapter over current TaskBus/runtime;
- publish/query/cancel/retry method shells;
- event/result/evidence query method shells;
- compatibility mapping from Plato TaskNode to TaskRequest.

Acceptance:

- existing fixed-route execution path can call the boundary in tests;
- no external HTTP route required;
- no visible UI behavior change.

### EP2: Plato Runtime Wiring Through Boundary

Goal: make Plato a Task API client internally.

Deliverables:

- Main/Product publish path maps TaskNode to TaskRequest;
- idempotency and external refs preserve Session/Plan/TaskNode return context;
- result/error/file/evidence projections remain stable;
- existing Product 1.0 user path smoke still passes.

Acceptance:

- Product 1.0 Main Page behavior is unchanged;
- published TaskNode execution goes through Task API boundary;
- rollback path exists through old adapter during migration.

### EP3: Local Service Shell

Goal: expose the same boundary over local sidecar API.

Candidate endpoints:

```http
POST /api/v1/tasks
GET /api/v1/tasks/{taskId}
POST /api/v1/tasks/{taskId}/cancel
POST /api/v1/tasks/{taskId}/retry
GET /api/v1/tasks/{taskId}/events
GET /api/v1/tasks/{taskId}/result
GET /api/v1/tasks/{taskId}/evidence
```

Acceptance:

- local sidecar can publish and query a task through service DTOs;
- endpoint remains local-only;
- auth is not public internet auth yet;
- diagnostics redact sensitive payloads.

### EP4: ExecutionEnv Registry Foundation

Goal: model execution environments before distributed claim/lease.

Deliverables:

- `ExecutionEnv` model;
- local default env registration;
- capability/tool pool projection;
- health/status state;
- diagnostics-safe summary.

Acceptance:

- current local runtime appears as one registered execution env;
- task publish can resolve a compatible env in-process;
- no remote worker required.

### EP5: Claim / Lease / Heartbeat Protocol

Goal: prepare distributed execution correctness.

Deliverables:

- claim/lease state model;
- heartbeat API contract;
- lease expiry recovery policy;
- duplicate claim rejection;
- retry/reclaim behavior after restart or env loss.

Acceptance:

- one task cannot be double-claimed;
- lease expiry has explicit state and recovery;
- Product 1.0 local execution can still use a fast-path lease.

### EP6: External Task API Preview

Goal: allow non-Plato callers to publish typed tasks in a controlled local/dev
mode.

Deliverables:

- external requester model;
- external refs;
- callback policy placeholder;
- strict capability/tool policy validation;
- local/dev auth or trusted-token boundary;
- example payloads.

Acceptance:

- external client can submit a typed task without Plato Session fields;
- unsafe free-text-only task publish is rejected;
- callback/webhook execution may remain stubbed.

### EP7: First Vertical Proof

Goal: validate service value with a low-risk vertical workflow.

Recommended first proof:

```text
Email/browser-based ecommerce outreach draft task
```

Not recommended as first proof:

```text
WeChat desktop automation
```

Acceptance:

- external app publishes a typed outreach task;
- local env claims it;
- Agent drafts communication;
- human confirmation is required before outbound send or simulated send;
- result and evidence are queryable;
- business hook emits a communication event.

## 9. API / Contract Direction

First `POST /tasks` request shape should include:

```json
{
  "idempotencyKey": "client:task:123",
  "requester": {
    "kind": "plato",
    "id": "workspace:local"
  },
  "externalRef": {
    "system": "plato",
    "kind": "task_node",
    "id": "task-node-id"
  },
  "taskType": "plato.default_execution",
  "intent": "Implement the selected task.",
  "input": {},
  "requiredCapability": "execute",
  "policy": {
    "allowedTools": ["file_read", "file_write", "shell"],
    "requiresHumanConfirmation": false
  },
  "evidence": {
    "required": ["result_summary"],
    "optional": ["file_change_summary", "tool_observation"]
  }
}
```

The DTO must support external systems without adding Plato-only fields:

```json
{
  "idempotencyKey": "crm:outreach:inf_123:2026-06-18",
  "requester": {
    "kind": "external_app",
    "id": "ops-crm"
  },
  "externalRef": {
    "system": "ops-crm",
    "kind": "influencer",
    "id": "inf_123"
  },
  "taskType": "ecommerce.outreach.email_draft",
  "intent": "Draft a sample collaboration email for this creator.",
  "requiredCapability": "outreach.email_draft",
  "policy": {
    "allowedTools": ["browser_read", "email_draft"],
    "requiresHumanConfirmation": true
  }
}
```

## 10. Storage Direction

First implementation can wrap current stores.

New persistent records likely needed:

- task request idempotency records;
- task execution service records;
- requester/external ref metadata;
- execution env registry;
- env heartbeat history or latest heartbeat;
- service-level evidence refs;
- callback delivery state later.

Do not duplicate existing TaskBus task state blindly. The first design should
decide which service fields are wrappers around TaskBus and which are
service-owned.

## 11. Frontend / Product Impact

Product 1.0 Main Page should not change in the first slices.

Later UI impacts:

- task detail can show execution env/capability;
- Activity/Audit can show task came from Plato or external API;
- Settings/Diagnostics can show local execution env health;
- external task monitor could become a future product surface.

## 12. Backend Work

Backend work is the main scope:

- service DTOs;
- embedded Task API adapter;
- TaskBus mapping;
- idempotency;
- env registry;
- claim/lease;
- sidecar endpoints;
- result/evidence query;
- contract and integration tests.

## 13. Tests And Validation

Required test categories:

- DTO validation and JSON examples;
- Plato TaskNode -> TaskRequest mapping;
- idempotent publish;
- duplicate publish returns same task execution;
- unknown/unsafe task request rejection;
- capability mismatch rejection;
- embedded service publish/query path;
- result/error/evidence query;
- env registry compatibility matching;
- claim/lease duplicate rejection later;
- local sidecar endpoint smoke when EP3 starts.

## 14. Acceptance Criteria

The plan is complete when:

1. Plato can publish through the Execution Plane boundary.
2. External TaskRequest can be represented without Plato Session fields.
3. Task execution, events, result, and evidence have service-level identities.
4. Permission/capability policy is explicit.
5. Idempotent publish is guaranteed.
6. The first local service shell can publish/query tasks.
7. ExecutionEnv registry supports the current local default env.
8. Audit remains read-side and does not block execution.

## 15. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Product 1.0 closure gets delayed by platform work | Start with in-process boundary; no UI change in EP0-EP2. |
| Task API is too permissive | Reject missing requester/capability/policy/idempotency. |
| Plato Session leaks into service DTOs | Keep Session fields in `externalRef`/metadata, not core identity. |
| Distributed execution complexity arrives too early | Defer remote workers until Env registry and local lease semantics pass. |
| Ecommerce logic pollutes core | Keep vertical task schemas and hooks outside Execution Plane core. |

## 16. Open Questions

1. Should `taskType` be free-form namespaced string or registered schema id?
2. What is the first auth model for local external callers?
3. Which fields are service-owned vs TaskBus-owned?
4. Should external callbacks use webhook, SSE, or polling first?
5. What minimum evidence is mandatory for computer-use tasks?
6. How should external apps receive ASK/confirmation events?
7. Should ExecutionEnv be workspace-scoped, tenant-scoped, or both?

## 17. Completion Updates

No implementation has started under this plan.
