# Execution Plane Service And Task API Technical Design

> Status: in progress / foundation implementation in review
>
> Last Updated: 2026-06-18
>
> Feature Plan: [Execution Plane Service And Task API Plan](execution-plane-service-task-api.md)
>
> ADR: [ADR-0020 Execution Plane As Service / Task API Boundary](../../decisions/ADR-0020-execution-plane-as-service-task-api-boundary.md)
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

## 1. 目标

本技术方案把 ADR-0020 落成可执行的后端设计。

目标不是马上拆服务，而是先建立一个 service-compatible 的 Execution
Plane 边界：

```text
TaskRequest
  -> TaskApiService
  -> TaskExecution
  -> TaskBus / AgentLoop / ToolRuntime
  -> TaskEvent / TaskResult / TaskError / EvidenceRef
```

Plato 继续本地内嵌调用；未来外部应用可以通过同一套 Task API 发布任务。

## 2. 设计原则

1. **先逻辑边界，后物理服务。**
   第一阶段不要求远程部署、远程 worker、云 auth。

2. **Task API 不等于自由文本执行 API。**
   任务必须带 requester、idempotency、task type、capability、policy、
   evidence 要求。

3. **Execution Plane 不依赖 Plato Session。**
   Plato 的 Session/Plan/TaskNode 信息只能作为 `external_ref` 或 metadata。

4. **TaskBus 仍是当前执行状态权威。**
   Service boundary 第一阶段包装 TaskBus，不直接替代 TaskBus。

5. **Agent lifecycle != Context lifecycle。**
   Agent 可以按任务短生命周期创建和销毁；Session/Workspace/Task context
   由 Context Manager 和 stores 负责。

6. **Audit 是 read-side。**
   Execution 完成与否不依赖 Audit Page 或 Audit projection。

## 3. 非目标

- 不实现公网 API。
- 不实现多租户权限系统。
- 不实现远程 worker claim。
- 不实现 WeChat computer-use 垂直场景。
- 不重写 Main Page。
- 不重写 TaskBus。
- 不把 ecommerce domain model 放进 Execution Plane core。
- 不把所有 Product 1.1 plans 合并到这个任务。

## 4. 建议模块边界

新增后端包建议：

```text
src/taskweavn/execution_plane/
  __init__.py
  models.py
  errors.py
  service.py
  embedded_service.py
  idempotency.py
  mapper.py
  env_registry.py
  policy.py
  evidence.py
  result_store.py
  routes.py
```

测试目录建议：

```text
tests/unit/execution_plane/
  test_models.py
  test_task_request_validation.py
  test_idempotency.py
  test_policy.py
  test_plato_task_mapper.py
  test_env_registry.py

tests/integration/execution_plane/
  test_embedded_task_api_service.py
  test_plato_publish_through_execution_plane.py
  test_task_result_evidence_query.py
```

先不要把新逻辑塞进：

- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/ui_contract/gateways.py`

这些是已有 hotspot。HTTP route 只应薄薄转发到 service。

## 5. Model Design

模型建议使用 Pydantic，和现有 UI contract / context models 保持一致：

- `extra="forbid"`；
- JSON-safe；
- explicit literal；
- stable ids；
- timestamp UTC。

### 5.1 Literal Types

```python
TaskRequesterKind = Literal[
    "plato",
    "external_app",
    "system",
    "test",
]

TaskExecutionStatus = Literal[
    "accepted",
    "pending",
    "claimed",
    "running",
    "waiting_for_user",
    "done",
    "failed",
    "cancelled",
    "lease_expired",
    "rejected",
]

TaskEventKind = Literal[
    "task.accepted",
    "task.claimed",
    "task.started",
    "task.progress",
    "task.waiting_for_user",
    "task.result_ready",
    "task.failed",
    "task.cancelled",
    "task.lease_expired",
    "task.evidence_added",
]

EvidenceKind = Literal[
    "result_summary",
    "error_summary",
    "file_change_summary",
    "tool_observation",
    "screenshot",
    "text_extract",
    "diff",
    "audit_record",
]
```

### 5.2 Requester

```python
class TaskRequester(ExecutionPlaneModel):
    kind: TaskRequesterKind
    id: str
    display_name: str | None = None
    trust_scope: str | None = None
```

规则：

- `plato` requester 表示来自 Plato product/control plane；
- `external_app` requester 必须通过后续 local auth / token policy；
- `system` 仅用于内部维护任务；
- requester 不等于 human user，后续可增加 `actor_ref`。

### 5.3 ExternalRef

```python
class ExternalRef(ExecutionPlaneModel):
    system: str
    kind: str
    id: str
    url: str | None = None
```

Plato 映射示例：

```text
system = "plato"
kind = "task_node"
id = "<task_node_id>"
```

电商系统示例：

```text
system = "ops-crm"
kind = "influencer"
id = "inf_123"
```

### 5.4 CapabilityPolicy

```python
class CapabilityPolicy(ExecutionPlaneModel):
    required_capability: str
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    requires_human_confirmation: bool = False
    max_runtime_seconds: int | None = None
    max_llm_tokens: int | None = None
    workspace_scope: str | None = None
    risk_level: Literal["low", "medium", "high"] = "medium"
```

规则：

- `required_capability` 必填；
- `allowed_tools` 为空不代表全量工具，表示由 requester/default policy 决定；
- high-risk 工具必须经过 runtime policy 合并；
- skill 不能提升 policy 权限，只能请求或收窄。

### 5.5 EvidenceRequirement

```python
class EvidenceRequirement(ExecutionPlaneModel):
    required: tuple[EvidenceKind, ...] = ("result_summary",)
    optional: tuple[EvidenceKind, ...] = ()
    retention_policy: str | None = None
    redact_for_diagnostics: bool = True
```

第一阶段只强制 `result_summary`。computer-use、outbound communication、
credentialed browser 等后续任务类型应要求截图、tool observation 或
explicit human confirmation evidence。

### 5.6 CallbackPolicy

```python
class CallbackPolicy(ExecutionPlaneModel):
    mode: Literal["none", "poll", "sse", "webhook"] = "none"
    url: str | None = None
    signing_key_ref: str | None = None
    event_kinds: tuple[TaskEventKind, ...] = ()
```

Product 1.1 第一阶段：

- Plato 内部调用使用 `none` 或现有 UI event/SSE；
- external preview 可先只支持 `poll`；
- webhook 仅定义，不实现发送。

### 5.7 TaskRequest

```python
class TaskRequest(ExecutionPlaneModel):
    idempotency_key: str
    requester: TaskRequester
    external_ref: ExternalRef | None = None
    task_type: str
    intent: str
    input: dict[str, JsonValue] = {}
    policy: CapabilityPolicy
    evidence: EvidenceRequirement = EvidenceRequirement()
    callback: CallbackPolicy = CallbackPolicy()
    metadata: dict[str, JsonValue] = {}
```

验证规则：

1. `idempotency_key` 必填，且对 requester scoped。
2. `task_type` 必须是 namespaced string，例如：
   - `plato.default_execution`
   - `ecommerce.outreach.email_draft`
3. `intent` 必填但不能是唯一任务定义。
4. `policy.required_capability` 必填。
5. `metadata` 不得包含 raw secrets、absolute workspace root、full prompt。
6. external app 请求不得使用 Plato Session 字段作为必需 core 字段。

### 5.8 TaskExecution

```python
class TaskExecution(ExecutionPlaneModel):
    execution_id: str
    task_id: str
    request_id: str
    status: TaskExecutionStatus
    requester: TaskRequester
    external_ref: ExternalRef | None
    task_type: str
    required_capability: str
    env_id: str | None = None
    lease_id: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_ref: str | None = None
    error_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
```

第一阶段可以让 `task_id` 指向现有 TaskBus Task id，`execution_id` 是
service-level id。后续如 TaskBus model 和 service model 收敛，可减少重复。

### 5.9 TaskEvent

```python
class TaskEvent(ExecutionPlaneModel):
    event_id: str
    execution_id: str
    task_id: str
    kind: TaskEventKind
    occurred_at: datetime
    summary: str
    data: dict[str, JsonValue] = {}
    evidence_refs: tuple[str, ...] = ()
```

TaskEvent 是 service-level projection，不要求完全等同内部 EventStream
事件。它可以由内部事件映射而来。

## 6. Service Interface

### 6.1 Protocol

```python
class TaskApiService(Protocol):
    def publish_task(self, request: TaskRequest) -> TaskExecution: ...
    def get_task(self, execution_id: str) -> TaskExecution: ...
    def cancel_task(self, execution_id: str, command: CancelTaskCommand) -> TaskExecution: ...
    def retry_task(self, execution_id: str, command: RetryTaskCommand) -> TaskExecution: ...
    def list_events(self, execution_id: str, query: TaskEventQuery) -> TaskEventPage: ...
    def get_result(self, result_ref: str) -> TaskResult: ...
    def get_error(self, error_ref: str) -> TaskError: ...
    def list_evidence(self, execution_id: str) -> EvidencePage: ...
```

`TaskApiService` 是业务边界。HTTP route、Plato gateway、external adapter
都不应绕过它。

### 6.2 EmbeddedTaskApiService

第一阶段实现：

```text
EmbeddedTaskApiService
  -> TaskRequestValidator
  -> TaskRequestIdempotencyStore
  -> PlatoTaskMapper / ExternalTaskMapper
  -> TaskBus publish / query
  -> ResultStore / EvidenceStore
```

它可以复用当前 Product 1.0 stores，但需要通过 adapter 隔离字段。

## 7. Idempotency Design

幂等键必须由 caller 提供，后端按 requester scope 存储。

推荐 key：

```text
requester.kind + requester.id + idempotency_key
```

记录：

```python
class TaskRequestIdempotencyRecord:
    scoped_key: str
    request_hash: str
    execution_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    status: Literal["accepted", "completed", "conflict"]
```

规则：

1. 相同 scoped key + 相同 request hash：返回已有 `TaskExecution`。
2. 相同 scoped key + 不同 request hash：返回 conflict。
3. publish accepted 后，即使服务重启，也不能创建重复 execution。
4. retry 不使用新的 publish idempotency key；retry 是 command。

## 8. Mapping: Plato To TaskRequest

Plato 内部发布应显式转换：

```text
WorkspaceId
SessionId
PlanId
TaskNodeId
TaskNode title/summary/instructions
Execution controls / user settings
Context policy
  -> TaskRequest
```

建议：

```python
class PlatoTaskRequestMapper:
    def from_task_node(
        self,
        workspace_id: str,
        session_id: str,
        plan_id: str,
        task_node: PlanTaskNode,
        publish_command_id: str,
    ) -> TaskRequest: ...
```

映射规则：

- `requester.kind = "plato"`；
- `requester.id = f"workspace:{workspace_id}"`；
- `external_ref.system = "plato"`；
- `external_ref.kind = "task_node"`；
- `external_ref.id = task_node.id`；
- `task_type = "plato.default_execution"` 或更细分的 internal type；
- `idempotency_key` 使用 publish command id / task node version；
- `intent` 来自 TaskNode 用户可见目标；
- `input` 包含 instructions、acceptance criteria、context refs；
- `policy` 来自 user config + workspace policy + task capability；
- `metadata` 可包含 return context，但不得依赖它作为 service core identity。

## 9. ExecutionEnv Registry

### 9.1 Model

```python
class ExecutionEnv(ExecutionPlaneModel):
    env_id: str
    display_name: str
    status: Literal["online", "offline", "draining", "disabled"]
    capabilities: tuple[str, ...]
    tool_pool: tuple[str, ...]
    permission_profile_id: str | None
    workspace_scope: str | None = None
    active_execution_id: str | None = None
    last_heartbeat_at: datetime | None = None
    runtime_version: str | None = None
```

Product 1.1 first foundation:

- register one `local-default` env at startup;
- status is derived from local runtime health;
- capabilities initially include current default execution capability;
- tool pool comes from configured runtime tools.

### 9.2 Matching

```text
TaskRequest.policy.required_capability
  -> registry candidate envs
  -> tool policy merge
  -> selected env
```

第一阶段可 deterministic：

- local-only；
- one env；
- reject if capability mismatch。

后续再加入 score/routing。

## 10. Claim / Lease Protocol

第一阶段 local embedded execution 可以不暴露 remote claim，但数据模型应预留。

### 10.1 Lease Model

```python
class TaskLease(ExecutionPlaneModel):
    lease_id: str
    execution_id: str
    env_id: str
    status: Literal["active", "released", "expired", "revoked"]
    claimed_at: datetime
    expires_at: datetime
    renewed_at: datetime | None = None
```

### 10.2 Rules

1. `pending -> claimed` 必须原子化。
2. 同一 execution 同一时间只能有一个 active lease。
3. heartbeat 只允许 lease holder 更新。
4. lease expiry 不等于 failed；应进入 `lease_expired` 或 recoverable state。
5. retry/reclaim 必须产生新的 lease，不产生新的 publish request。

## 11. Result / Error / Evidence

### 11.1 TaskResult

```python
class TaskResult(ExecutionPlaneModel):
    result_ref: str
    execution_id: str
    summary: str
    structured_payload: dict[str, JsonValue] = {}
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime
```

### 11.2 TaskError

```python
class TaskError(ExecutionPlaneModel):
    error_ref: str
    execution_id: str
    code: str
    message: str
    retryable: bool
    recovery_hint: str | None = None
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime
```

### 11.3 EvidenceRef

```python
class EvidenceRef(ExecutionPlaneModel):
    evidence_id: str
    execution_id: str
    kind: EvidenceKind
    title: str
    summary: str
    uri: str | None = None
    object_ref: dict[str, JsonValue] = {}
    visibility: Literal["visible", "permission_limited", "hidden"] = "visible"
    created_at: datetime
```

规则：

- evidence ref 可见不等于 raw payload 可见；
- diagnostics export 必须走 redaction；
- Audit 使用 evidence ref，不直接读取 unsafe raw payload。

## 12. HTTP Route Shape

EP3 才实现 HTTP。route 层必须薄：

```text
HTTP parse/serialize
  -> TaskApiService
  -> response mapping
```

候选 routes：

```http
POST /api/v1/tasks
GET /api/v1/tasks/{executionId}
POST /api/v1/tasks/{executionId}/cancel
POST /api/v1/tasks/{executionId}/retry
GET /api/v1/tasks/{executionId}/events
GET /api/v1/tasks/{executionId}/result
GET /api/v1/tasks/{executionId}/evidence
```

Env routes later:

```http
POST /api/v1/execution-envs/register
POST /api/v1/execution-envs/{envId}/heartbeat
POST /api/v1/execution-envs/{envId}/claim
POST /api/v1/execution-envs/{envId}/tasks/{executionId}/events
POST /api/v1/execution-envs/{envId}/tasks/{executionId}/result
```

第一阶段 local-only，可以通过 sidecar origin/loopback policy 限制。

## 13. Error Taxonomy

Service errors:

| Code | Meaning | Retry |
|---|---|---:|
| `invalid_task_request` | Required field missing or malformed. | no |
| `idempotency_conflict` | Same key with different request payload. | no |
| `capability_not_available` | No env/tool policy can satisfy task. | maybe |
| `permission_denied` | Requester/policy cannot use requested capability/tool. | no |
| `task_not_found` | Unknown execution id. | no |
| `task_not_cancellable` | Current status cannot be cancelled. | no |
| `task_not_retryable` | Current result/error does not allow retry. | no |
| `lease_conflict` | Task already claimed by active lease. | maybe |
| `execution_failed` | Runtime failed after accept. | maybe |

Errors must map to product recovery labels later, but service code should stay
UI-independent.

## 14. Persistence Direction

SQLite tables likely needed:

```sql
execution_task_requests(
  scoped_idempotency_key text primary key,
  request_hash text not null,
  execution_id text not null,
  request_json text not null,
  created_at text not null,
  updated_at text not null
)

execution_tasks(
  execution_id text primary key,
  task_id text not null,
  request_id text not null,
  status text not null,
  requester_json text not null,
  external_ref_json text,
  task_type text not null,
  required_capability text not null,
  env_id text,
  lease_id text,
  result_ref text,
  error_ref text,
  created_at text not null,
  updated_at text not null,
  completed_at text
)

execution_envs(
  env_id text primary key,
  env_json text not null,
  status text not null,
  last_heartbeat_at text,
  updated_at text not null
)

execution_leases(
  lease_id text primary key,
  execution_id text not null,
  env_id text not null,
  status text not null,
  claimed_at text not null,
  expires_at text not null,
  renewed_at text
)
```

Result/evidence may initially reuse existing stores, but service-level refs
should be stable and queryable.

## 15. Migration Strategy

### Phase 1: Additive Models

- Add `execution_plane.models`.
- Add validation tests.
- No runtime behavior change.

### Phase 2: Embedded Service

- Implement `TaskApiService` protocol.
- Implement in-process adapter over current TaskBus/runtime.
- Add mapping tests from Plato TaskNode to TaskRequest.

### Phase 3: Plato Publish Path

- Route fixed-route publish through embedded service.
- Preserve existing UI projection.
- Keep compatibility fallback.

### Phase 4: Service Shell

- Add local sidecar routes.
- Keep local-only boundary.
- Add route tests and sidecar smoke.

### Phase 5: Env Registry / Lease

- Register local env.
- Add capability match tests.
- Add lease model but keep remote worker disabled.

### Phase 6: External Preview

- Add local trusted external task publish.
- Add example client or fixture.
- Do not add public auth yet.

## 16. Test Matrix

| Test | Slice |
|---|---|
| TaskRequest rejects missing idempotency key | EP0 |
| TaskRequest rejects missing capability | EP0 |
| External request contains no Session required field | EP0 |
| Same idempotency key/request returns same execution | EP1 |
| Same key/different payload returns conflict | EP1 |
| Plato TaskNode maps to TaskRequest with external ref | EP1 |
| Embedded publish creates/query execution | EP1 |
| Product fixed-route path still completes task | EP2 |
| Result and evidence refs query through service | EP2 |
| HTTP POST /tasks local route publishes task | EP3 |
| Local default env matches execute capability | EP4 |
| Capability mismatch rejects publish or dispatch | EP4 |
| Active lease rejects duplicate claim | EP5 |
| Lease expiry enters recoverable state | EP5 |
| External task publish works in trusted local mode | EP6 |

## 17. Acceptance Criteria

Technical design is implemented when:

1. `TaskRequest` / `TaskExecution` / `TaskEvent` / `TaskResult` /
   `TaskError` / `EvidenceRef` models exist and are tested.
2. Embedded Task API service can publish/query/cancel/retry through stable
   methods.
3. Plato's current publish path uses the boundary or has a tested compatibility
   adapter ready.
4. Idempotent publish is durable.
5. Result/error/evidence refs are service-queryable.
6. Local default ExecutionEnv is represented.
7. HTTP shell exists for local `POST /tasks` and query endpoints.
8. External preview task can be submitted without Plato Session fields.

## 18. Implementation Guardrails

- Do not edit Main Page UI in EP0-EP2.
- Do not put route parsing into service models.
- Do not put service DTOs into UI contract packages.
- Do not put ecommerce fields into core `TaskRequest`.
- Do not expose raw evidence payloads.
- Do not allow a skill or task request to grant broader tool permission than
  runtime policy allows.
- Do not remove current Product 1.0 fixed-route path until the compatibility
  path is tested.

## 19. Open Decisions Before EP3

1. Should local HTTP API use existing sidecar trust boundary only, or a local
   bearer token?
2. Should `task_id` be generated by TaskBus or Execution Plane?
3. Should `execution_id` be the public id and `task_id` stay internal?
4. Should result/evidence stores live under workspace DB or service DB?
5. How should ASK/confirmation events be delivered to external clients?
6. Should callback webhooks be implemented before remote workers?
7. How much audit metadata should be part of TaskEvent vs Audit projection?
