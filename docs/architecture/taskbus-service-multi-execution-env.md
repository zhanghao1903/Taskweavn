# Execution Plane Service And Multi-Execution-Env Architecture Memo

> Status: fact-calibrated architecture memo
> Last Updated: 2026-07-10
> Scope: current local embedded Execution Plane facts plus future multi-env service direction
> Related: [overview](overview.md), [task](task.md), [bus](bus.md), [agent](agent.md),
> [bus-v2](bus-v2.md), [tool capability layer](tool-capability-layer.md),
> [workspace communication protocol](workspace-communication-protocol.md),
> [context manager](context-manager.md), [ui/backend communication](ui-backend-communication.md),
> [ADR-0020](../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)
>
> 2026-07-10 fact calibration: The Execution Plane now has service-level DTOs,
> an embedded in-process `TaskApiService`, a local HTTP shell, an in-memory
> `ExecutionEnvRegistry`, durable `SqliteExecutionPlaneStore`, and a local
> WeChat send runtime handler. It does **not** yet have remote ExecutionEnv
> registration APIs, distributed claim/lease/heartbeat, webhook delivery,
> service auth for external callers, generic hook runtime, email outreach MVP,
> or a separated TaskBus service.

---

## 1. Core Thesis

Plato's platform direction is to make work executable, traceable, and
data-producing across tools that do not share a clean API surface.

The intended long-term capability remains:

```text
Execution Plane / Task API
  + TaskBus-backed lifecycle authority
  + service-level task contracts
  + execution environments with explicit capabilities
  + tool-scoped evidence and result records
  + business hooks outside the execution core
```

Current implementation is a local foundation, not a distributed service:

```text
TaskRequest
  -> EmbeddedTaskApiService
  -> local ExecutionEnv compatibility check
  -> TaskBus publish / lifecycle
  -> fixed-route dispatcher or local runtime handler
  -> ExecutionPlaneStore result/error/evidence/events
```

This memo should therefore be read in two layers:

1. **Current fact:** service-compatible contracts and embedded local runtime.
2. **Future direction:** remote/multi-env service, leases, hooks, callbacks, and
   vertical workflow packages.

---

## 2. Current Implemented Facts

### 2.1 Service-level models exist

`src/taskweavn/execution_plane/models.py` defines:

| Model | Current status |
|-------|----------------|
| `TaskRequest` | Implemented service-level publish request. Requires idempotency, requester, namespaced `task_type`, intent, and `CapabilityPolicy`. |
| `TaskExecution` | Implemented service-level execution record with `execution_id`, `task_id`, status, requester, optional `env_id`, result/error refs, evidence refs, and `session_id`. |
| `TaskEvent` / `TaskEventPage` | Implemented event DTO and paged response shape. Current embedded service appends acceptance, cancel, retry, and runtime-specific events. |
| `TaskResult` | Implemented durable result DTO with structured payload and evidence refs. |
| `TaskError` | Implemented durable error DTO with retryability and recovery hint. |
| `EvidenceRef` / `EvidencePage` | Implemented evidence reference DTO and query response. |
| `ExecutionEnv` | Implemented local-compatible env descriptor with capability/tool matching. |
| `CapabilityPolicy` | Implemented required capability, allowed/denied tools, human confirmation flag, budgets, workspace scope, and risk level. |
| `CallbackPolicy` | Modeled and validated, but no callback/webhook delivery is implemented. |
| `TaskLease` | Modeled, but no lease service/store/renewal flow is implemented. |

The current request shape uses nested `policy.requiredCapability`; it is not the
older memo's top-level `requiredCapability` field.

### 2.2 TaskApiService exists

`TaskApiService` currently exposes:

```python
publish_task(request)
get_task(execution_id)
cancel_task(execution_id, command)
retry_task(execution_id, command)
list_events(execution_id, query)
get_result(result_ref)
get_error(error_ref)
list_evidence(execution_id)
```

`EmbeddedTaskApiService` implements this protocol in-process over the current
TaskBus. It is service-compatible but not a separate network service.

### 2.3 Embedded publish path

For ordinary task types, `EmbeddedTaskApiService.publish_task()` currently:

1. validates any matching runtime handler before side effects;
2. scopes the idempotency key by requester;
3. rejects idempotency reuse with a different request hash;
4. resolves a compatible local `ExecutionEnv`;
5. maps `TaskRequest` to `TaskDomain`;
6. publishes the Task through TaskBus;
7. persists `TaskExecution` and idempotency record in `ExecutionPlaneStore`;
8. appends a `task.accepted` event;
9. returns a `TaskExecution` with `status="pending"`.

Execution progress is still driven by TaskBus and the fixed-route dispatcher for
ordinary tasks.

### 2.4 ExecutionPlaneStore exists

`InMemoryExecutionPlaneStore` and `SqliteExecutionPlaneStore` store:

| Store record | SQLite table |
|--------------|--------------|
| idempotency records | `execution_idempotency` |
| execution payloads | `execution_tasks` |
| task events | `execution_events` |
| results | `execution_results` |
| errors | `execution_errors` |
| evidence refs | `execution_evidence` |

The main sidecar creates:

```python
execution_plane_store = SqliteExecutionPlaneStore(
    layout.meta_dir / "execution_plane.sqlite"
)
```

This store is separate from `SqliteTaskBus`. TaskBus remains the lifecycle
authority for PublishedTask facts; ExecutionPlaneStore owns service-level
idempotency, execution records, events, result/error payloads, and evidence
refs.

### 2.5 Local ExecutionEnv registry exists

The current registry is `InMemoryExecutionEnvRegistry`, not a remote registry
service. It supports:

```python
upsert(env)
get(env_id)
list()
find_compatible(policy)
```

Compatibility means:

```text
env.status == "online"
policy.required_capability in env.capabilities
policy.allowed_tools is empty or subset of env.tool_pool
```

The default env is `local-default`. In sidecar assembly, `build_execution_env_registry()`
creates one local env. When computer-use is enabled, it adds `computer_use` and
the WeChat send capability with tool pool entries `computer_use` and
`wechat_desktop`.

### 2.6 Local HTTP shell exists

The sidecar has a thin HTTP shell over `TaskApiService`:

```text
POST /api/v1/tasks
GET  /api/v1/tasks/{executionId}
POST /api/v1/tasks/{executionId}/cancel
POST /api/v1/tasks/{executionId}/retry
GET  /api/v1/tasks/{executionId}/events
GET  /api/v1/tasks/{executionId}/result
GET  /api/v1/tasks/{executionId}/error
GET  /api/v1/tasks/{executionId}/evidence
```

There is also a workspace-prefixed publish route that injects workspace metadata:

```text
POST /api/v1/workspaces/{workspaceId}/tasks
```

These routes are local sidecar routes. They are not yet public internet APIs and
do not implement the future execution-env registration, claim, heartbeat, or
callback endpoints.

### 2.7 Runtime handlers exist for selected local task types

`EmbeddedTaskRuntimeHandler` is a local seam:

```python
validate_request(request)
publish_or_resume(request, execution)
```

The current concrete runtime handler is local WeChat send:

```text
communication.wechat.send_message
  -> validate high-risk confirmation policy
  -> readiness / open / contact resolution / draft evidence
  -> TaskBus wait_for_confirmation
  -> idempotent replay after user response
  -> send-after-confirmation service
  -> TaskResult / TaskError / EvidenceRef
```

This is a controlled local runtime flow, not a general Agent Manager or remote
ExecutionEnv implementation.

---

## 3. Current Non-Facts

The following concepts are architectural direction or DTO placeholders, not
current shipped runtime behavior:

| Concept | Current fact |
|---------|--------------|
| Remote ExecutionEnv service | No register/heartbeat/claim endpoint exists. |
| Distributed claim / lease / renewal | `TaskLease` model exists, but there is no lease store or protocol. |
| Task status `claimed` / `lease_expired` | DTO statuses exist, but embedded service maps TaskBus statuses: `pending`, `running`, `waiting_for_user`, `done`, `failed`. |
| Service-owned scheduler | Ordinary tasks still use TaskBus + fixed-route dispatcher. |
| TaskBus as external service | Current app embeds `SqliteTaskBus`; no separate TaskBus service process. |
| External auth / multi-tenant SaaS boundary | Sidecar auth exists for local UI routes, but no external app auth model is implemented for Task API. |
| Webhook callback delivery | `CallbackPolicy` exists; delivery state and dispatch do not. |
| Generic business hook runtime | Not implemented. |
| Email outreach MVP | Recommended direction only; no email vertical package is implemented. |
| CRM / ERP object store | Not implemented in Execution Plane core. |
| Global tool pool per env | Current local env exposes static capabilities/tool_pool; no remote tool inventory protocol. |

---

## 4. Control Plane Boundary

The long-term control plane should own:

1. task publish APIs;
2. service-level idempotency;
3. execution records and query surfaces;
4. execution environment registry;
5. distributed claim, lease, heartbeat, and recovery;
6. result, error, event, and evidence references;
7. callback / hook dispatch;
8. policy enforcement around requester, capability, tools, risk, and workspace.

Current Product 1.1 only implements items 1-4 partially and item 6 for local
embedded flows. Items 5, 7, and full external policy/auth are future work.

The control plane must not absorb vertical business logic. Vertical packages may
define task schemas, result contracts, hooks, and business object mappings, but
those should remain outside TaskBus and Execution Plane core.

---

## 5. Execution Environment Boundary

An execution environment is a machine, sandbox, browser profile, or local
runtime with concrete tools and permissions. It is not the same thing as an
Agent.

Current `ExecutionEnv` fields are:

```text
env_id
display_name
status
capabilities
tool_pool
permission_profile_id
workspace_scope
active_execution_id
last_heartbeat_at
runtime_version
```

Current behavior:

- in-memory only;
- one local default env in sidecar assembly;
- compatibility check at publish time;
- no durable env table;
- no env heartbeat API;
- no remote claim loop;
- no lease renew/revoke/expire behavior.

Future service mode should add durable environment records, authenticated
registration, heartbeat, claim/lease, tool inventory, workspace scoping, and
diagnostics-safe health summaries.

---

## 6. Task Publish API

Current accepted request shape:

```json
{
  "idempotencyKey": "crm:outreach:inf-123",
  "requester": {
    "kind": "external_app",
    "id": "ops-crm"
  },
  "externalRef": {
    "system": "ops-crm",
    "kind": "influencer",
    "id": "inf-123"
  },
  "taskType": "ecommerce.outreach.email_draft",
  "intent": "Draft a sample collaboration email.",
  "input": {
    "creatorName": "Test Creator"
  },
  "policy": {
    "requiredCapability": "outreach.email_draft",
    "allowedTools": ["browser_read", "email_draft"],
    "requiresHumanConfirmation": true,
    "riskLevel": "medium"
  },
  "evidence": {
    "required": ["result_summary"],
    "optional": ["tool_observation"]
  },
  "callback": {
    "mode": "none"
  },
  "metadata": {}
}
```

Current validation includes:

- unknown fields rejected by Pydantic model config;
- `taskType` must be namespaced;
- `external_app` cannot publish `plato.*` task types;
- allowed and denied tools must not overlap;
- webhook callback mode requires a URL;
- non-webhook callback modes cannot carry `signingKeyRef`.

Important current limitation: a valid DTO does not mean the task can execute.
The embedded service also requires a compatible local env. If no local env
supports `policy.requiredCapability` and `allowedTools`, publish fails with
`capability_not_available`.

---

## 7. Claim, Lease, And Recovery

Distributed execution needs a stronger lifecycle than the current local embedded
path. Future service mode should include:

```text
pending
claimed
running
waiting_for_user
done
failed
cancelled
lease_expired
```

Current state:

- `TaskExecutionStatus` includes these future statuses.
- `TaskLease` model validates `claimed_at`, `expires_at`, and `renewed_at`.
- `ExecutionPlaneErrorCode` includes `lease_conflict`.
- No service method currently issues, renews, expires, revokes, or persists a
  lease.
- Current WeChat runtime may raise `lease_conflict` if it cannot claim its
  target TaskBus Task, but this is not a distributed lease protocol.

Future required mechanics:

1. env asks for compatible work;
2. service grants a lease with expiry;
3. env renews lease by heartbeat;
4. env reports progress/evidence/result against the lease;
5. lease expiry has explicit recovery semantics;
6. duplicate claim/result submission is rejected or deduplicated.

Until these mechanics exist, documents should not describe claim/lease/heartbeat
as current platform behavior.

---

## 8. Tool Capability Boundary

Current capability matching is simple:

```text
TaskRequest.policy.required_capability
  -> InMemoryExecutionEnvRegistry.find_compatible
  -> ExecutionEnv.supports(policy)
  -> TaskBus Task required_capability
```

Current local computer-use assembly:

```text
computer-use disabled
  -> local-default capabilities: execute, testing
  -> no WeChat runtime handler

computer-use macos enabled
  -> local-default capabilities include computer_use and communication.wechat_desktop_send
  -> tool_pool includes computer_use and wechat_desktop
  -> WeChatSendRuntimeHandler registered
```

Future service mode should make env-scoped tools durable, queryable, and
permission-aware. It should not assume every Agent or env has every tool.

---

## 9. Evidence And Audit

Current Execution Plane evidence is represented by `EvidenceRef` and stored in
ExecutionPlaneStore. Evidence refs can point at tool observations, screenshots,
text extracts, diffs, audit records, result summaries, or error summaries, but
storage of raw artifacts is not generalized in this layer.

Current evidence-producing paths:

- ordinary execution can expose result summaries from `TaskExecutionSummaryStore`;
- service code can record result/error/evidence through `EmbeddedTaskApiService`;
- WeChat send runtime records readiness, contact resolution, draft, send
  observation, result, and error evidence refs;
- Task timeline and audit pages can also read EventStream, MessageStream,
  TaskBus projections, result summaries, and file-change projections.

Current non-facts:

- no generic evidence upload API;
- no redaction pipeline for screenshots as part of Execution Plane core;
- no business event store;
- no durable `BusinessEvent` model in Execution Plane.

---

## 10. Hooks And Knowledge Maintenance

Business-specific hooks should stay outside TaskBus and Execution Plane core.

Future model:

```text
TaskExecution event
  -> hook matcher
  -> business hook
  -> knowledge update task or direct external write
  -> audit/evidence record
```

Current state:

- no generic hook runtime exists;
- no CRM/ecommerce knowledge store exists in Execution Plane;
- no automatic business object updates are triggered by TaskExecution events.

This is intentional. Execution Plane should first stabilize task intake,
lifecycle, results, evidence, and env policy before accepting vertical business
state mutation.

---

## 11. Local WeChat Runtime Position

The old memo recommended not starting with WeChat. Since then, a controlled local
macOS WeChat send MVP has landed as an opt-in runtime path.

Current facts:

- the path is local macOS only;
- it requires explicit computer-use backend configuration;
- it requires `requiresHumanConfirmation=true`;
- it drafts before send and waits for confirmation;
- it uses a durable `SqliteWeChatSendBoundaryStore` for idempotency,
  fingerprint, status, confirmation, observation, result, and error refs;
- terminal replay returns the same execution/result and does not send again;
- unknown/send-attempted boundaries require manual review and block automatic
  retry.

This does not change the service roadmap:

- it is not remote ExecutionEnv;
- it is not generic outbound communication automation;
- it is not the first recommended external vertical package;
- it does not implement screenshots/redaction, CRM writeback, or production
  abuse policy.

---

## 12. Recommended Future Service Direction

The future service-oriented track should be ordered as:

1. keep embedded Task API and local HTTP shell stable;
2. make ExecutionEnv registry durable and observable;
3. define authenticated local/external requester policy;
4. implement claim / lease / heartbeat over service records;
5. add result/evidence upload APIs with redaction and permission policy;
6. add callback delivery state before webhook execution;
7. add a low-risk vertical proof such as email/browser-based outreach draft;
8. add business hook runtime outside Execution Plane core;
9. only then evaluate remote desktop / LAN / multi-env workers.

Implementation should not start on remote workers until API contract, lease
recovery, env auth, and evidence retention semantics are explicit.

---

## 13. Key Risks

| Risk | Current mitigation / required future work |
|------|-------------------------------------------|
| DTOs imply behavior not implemented | Keep docs explicit: `TaskLease`, callback, and lease statuses are not runtime features yet. |
| Distributed execution creates duplicate or stale work | Future lease/heartbeat/recovery protocol; current local path relies on TaskBus/idempotency and runtime-specific boundaries. |
| External task publish is too permissive | Current models reject unknown fields and require requester/idempotency/policy; future auth and task type registry still needed. |
| Computer use is unstable or risky | Current WeChat path is opt-in, high-risk confirmation-gated, evidence-producing, and local only. |
| Knowledge base pollution | No generic knowledge hook exists yet; future hooks must require evidence refs, confidence, and review status. |
| Service platform absorbs vertical business logic | Keep business schemas, hooks, and object mappings outside Execution Plane core. |

---

## 14. Non-Goals For Current Product 1.1

Current Product 1.1 does not include:

- separated TaskBus service process;
- remote ExecutionEnv registration;
- lease/heartbeat worker protocol;
- multi-env scheduler;
- public SaaS Task API;
- webhook callback delivery;
- generic business hook runtime;
- email outreach vertical MVP;
- CRM/ERP object ownership;
- unreviewed high-risk outbound communication;
- fully autonomous WeChat outreach.

---

## 15. Summary

The Execution Plane direction is now partly real: Plato has a service-compatible
Task API boundary, DTOs, local HTTP shell, embedded service over TaskBus, local
env compatibility checks, durable execution store, and one opt-in local runtime
handler for WeChat send.

The multi-env service story is still future work. The next architecture and
implementation decisions should treat leases, heartbeats, callbacks, external
auth, hook runtime, and vertical workflows as explicit new slices rather than
implied current behavior.
