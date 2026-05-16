# Feature Plan: Task Publisher 抽象、定时发布与接口发布

> Status: done / server-core release candidate
> Type: 新特性支持
> Last Updated: 2026-05-16
> Owner/Session: planning session
> Target Implementation Session: independent feature session
> Related Docs: `docs/architecture/task.md`, `docs/architecture/bus.md`, `docs/plans/feature/pipeline-task-loading.md`, `docs/plans/feature/collaborator-agent-task-authoring.md`

---

## 1. 背景

TaskBus 是 TaskWeavn 的任务状态权威。任何 Task 最终都应该通过 TaskBus 发布、领取、完成和失败。

随着系统扩展，Task 的发布者会越来越多：

- 用户在 UI 中确认 Task Tree
- Collaborator Agent 生成并发布任务
- Pipeline Loader 自动装载 before / begin / after tasks
- 定时任务按时间触发发布
- 外部接口请求发布任务
- 用户直接输入自己定制化的 Task Tree

这些发布者形态不同，但不应该各自绕过总线，也不应该各自发明一套发布协议。需要抽象一个统一的 **Task Publisher** 层：负责校验、归一化、审计、预览和调用 TaskBus.publish。

---

## 2. 目标

1. 定义统一 Task Publisher 抽象。
2. 支持定时任务发布 Task。
3. 支持 API / 接口发布 Task。
4. 支持用户输入自定义 Task Tree 并发布。
5. 所有发布方式最终都转换为普通 Task，并走正常 TaskBus。
6. 发布过程必须有审计、校验、幂等和权限控制。
7. 明确 TaskBus 的边界：TaskBus 是状态权威，Publisher 是任务来源适配层。

---

## 3. 非目标

- 不把定时任务做成独立执行系统。
- 不让 API 直接修改 TaskBus 内部状态。
- 不在第一版中支持复杂 DAG；用户自定义 Task Tree 仍必须是 Tree List。
- 不实现完整多租户权限系统，但接口必须预留认证和授权边界。
- 不实现分布式调度器；第一版可以是单进程 scheduler。
- 不支持并发执行语义变更；TaskBus 串行约束保持不变。

---

## 4. 核心原则

- **All roads lead to TaskBus**：所有发布方式最终都调用 TaskBus 的发布接口。
- **Publisher is adapter, not executor**：Publisher 只创建和发布 Task，不执行 Task。
- **Normalize before publish**：外部输入必须先转成内部 Task Tree，再校验，再发布。
- **Preview before dangerous publish**：用户自定义 Task Tree 和 API 发布可以先 preview，确认后 publish。
- **Idempotency is required**：API 和 scheduler 必须支持幂等键，避免重复发布。
- **Publisher metadata is preserved**：每个 Task 都应能追溯由哪个 publisher 创建。
- **Custom Task Tree is first-class**：用户可以不经过 LLM，直接提交自定义 Task Tree。

---

## 5. TaskPublisher 抽象

### 5.1 Publisher 类型

```python
PublisherKind = Literal[
    "user",
    "collaborator",
    "pipeline",
    "scheduler",
    "api",
    "custom_tree",
    "agent",
]
```

### 5.2 TaskPublisher Protocol

```python
class TaskPublisher(Protocol):
    kind: PublisherKind

    def preview(self, request: PublishRequest) -> PublishPreview:
        ...

    def publish(self, request: PublishRequest) -> PublishResult:
        ...
```

注意：

- `preview` 不写 TaskBus。
- `publish` 必须走统一校验和 TaskBus。
- 不同 publisher 可以有自己的 request adapter，但进入核心发布层前必须归一化为 `NormalizedTaskTree`。
- 当前实现为了兼容已存在的 draft publish command，也保留 `publish_draft_tree(...)` / `retry_task(...)` compatibility hooks；后续可以在 TaskBus 完整生命周期稳定后再决定是否拆成更小协议。

### 5.3 PublishRequest

```python
class PublishRequest(BaseModel):
    session_id: str
    publisher: PublisherRef
    source: PublishSource
    task_tree: TaskTreeInput | None = None
    natural_language_input: str | None = None
    options: PublishOptions = PublishOptions()
    idempotency_key: str | None = None
```

### 5.4 PublisherRef

```python
class PublisherRef(BaseModel):
    kind: PublisherKind
    actor_id: str | None = None
    name: str | None = None
```

示例：

- `kind=user, actor_id=user-1`
- `kind=api, actor_id=api-key-abc`
- `kind=scheduler, name=nightly-summary`
- `kind=pipeline, name=task_after.final-summary`

### 5.5 PublishResult

```python
class PublishResult(BaseModel):
    request_id: str
    session_id: str
    published_task_ids: list[str]
    root_task_ids: list[str]
    skipped: bool = False
    reason: str | None = None
    idempotency_key: str | None = None
```

---

## 6. NormalizedTaskTree

所有入口最终归一化成：

```python
class NormalizedTaskTree(BaseModel):
    root_nodes: list[NormalizedTaskNode]
    source: PublisherRef
    source_ref: str | None = None
    metadata: dict[str, Any] = {}
```

```python
class NormalizedTaskNode(BaseModel):
    id: str
    parent_id: str | None = None
    title: str
    intent: str
    required_capability: str
    agent_ref: str | None = None
    children: list[NormalizedTaskNode] = []
    metadata: dict[str, Any] = {}
```

校验：

- Tree List，不允许 DAG。
- 每个节点必须有 intent。
- 每个节点必须有 required_capability。
- parent-child 关系合法。
- capability 必须已注册或可被配置识别。
- agent_ref 如果存在，必须满足 capability。

---

## 7. 自定义 Task Tree 发布

用户可以不经过 Collaborator Agent，直接提交自定义 Task Tree。

支持格式：

- YAML
- JSON
- UI builder 输出

示例：

```yaml
version: "1"
tasks:
  - id: inspect
    title: Inspect project
    intent: Inspect current project structure and identify the frontend entry point.
    required_capability: summarize
    agent: system.summarizer
    children:
      - id: inspect-tests
        title: Inspect tests
        intent: Identify current test framework and important commands.
        required_capability: summarize
```

流程：

```text
User uploads / writes Task Tree
  → parse
  → normalize
  → validate
  → preview
  → user confirm
  → publish to TaskBus
```

要求：

- preview 展示将发布哪些任务。
- 用户可以选择保存为模板。
- 发布后每个 Task 保留 `source=custom_tree` metadata。

---

## 8. 定时任务发布

### 8.1 ScheduleConfig

```python
class ScheduledPublishConfig(BaseModel):
    id: str
    enabled: bool = True
    schedule: ScheduleExpression
    session_selector: SessionSelector
    task_tree: TaskTreeInput
    idempotency_policy: IdempotencyPolicy
    timezone: str = "Asia/Shanghai"
```

### 8.2 ScheduleExpression

第一版建议支持：

- interval：每 N 分钟 / 小时
- daily time：每天某个时间
- cron：可后置，或者只作为配置预留

```python
class ScheduleExpression(BaseModel):
    type: Literal["interval", "daily", "cron"]
    every_seconds: int | None = None
    time_of_day: str | None = None
    cron: str | None = None
```

### 8.3 Scheduler 行为

```text
Scheduler tick
  → find due schedules
  → build PublishRequest(kind=scheduler)
  → use idempotency key
  → preview/validate internally
  → publish to TaskBus
```

要求：

- 定时器不是执行器，只是 publisher。
- 到期任务仍然走 TaskBus。
- 同一个 schedule tick 必须幂等。
- 记录 last_run_at / next_run_at / last_result。
- 支持禁用 schedule。

### 8.4 定时任务典型用例

- 每天自动生成项目状态总结 Task。
- 每小时检查当前 Session 是否有未完成任务。
- 每次工作日开始发布 workspace health check。
- 在长会话中定时生成 conversation summary。

---

## 9. API / 接口发布

### 9.1 Publish API

传输协议可以后置，第一版先定义语义：

```text
POST /sessions/{session_id}/tasks:publish
```

请求：

```json
{
  "publisher": {
    "kind": "api",
    "actor_id": "api-key-abc"
  },
  "idempotency_key": "external-job-123",
  "task_tree": {
    "tasks": [
      {
        "id": "summarize",
        "title": "Summarize current session",
        "intent": "Summarize current session progress and outstanding risks.",
        "required_capability": "summarize",
        "agent": "system.summarizer"
      }
    ]
  },
  "options": {
    "dry_run": false,
    "require_confirmation": false
  }
}
```

响应：

```json
{
  "request_id": "pub_123",
  "published_task_ids": ["task_1"],
  "root_task_ids": ["task_1"],
  "skipped": false
}
```

### 9.2 Dry Run / Preview

```text
POST /sessions/{session_id}/tasks:preview
```

用途：

- 校验 task tree。
- 返回 normalized tree。
- 返回 capability / agent 校验结果。
- 不写 TaskBus。

### 9.3 API 安全

第一版要求接口预留：

- API key / token 身份。
- session 权限校验。
- allowed capabilities 白名单。
- allowed agent templates 白名单。
- rate limit。
- idempotency key。

不要求第一版完成完整认证系统，但数据模型和接口不能把它封死。

---

## 10. 发布选项

```python
class PublishOptions(BaseModel):
    dry_run: bool = False
    require_confirmation: bool = True
    allow_pipeline: bool = True
    source_label: str | None = None
    failure_policy: Literal["fail_all", "publish_valid"] = "fail_all"
```

实现命名说明：Authoring Domain 已经有 `PublishOptions`，因此执行发布层第一版代码命名为 `TaskPublishOptions`，语义对应本节。

语义：

- `dry_run=true`：只 preview，不 publish。
- `require_confirmation=true`：需要用户或系统 confirmation 后发布。
- `allow_pipeline=true`：发布时可触发 pipeline task loading。
- `failure_policy=fail_all`：任何节点无效则全部不发布。
- `failure_policy=publish_valid`：只发布有效节点，需谨慎，第一版可不实现。

---

## 11. 幂等与重复发布控制

API 和 scheduler 必须支持幂等。

```python
class PublishIdempotencyRecord(BaseModel):
    session_id: str
    publisher_kind: PublisherKind
    idempotency_key: str
    request_hash: str
    publish_result: PublishResult
    created_at: datetime
```

规则：

- 同一 `session_id + publisher_kind + idempotency_key` 重复提交：
  - request_hash 相同：返回之前的 PublishResult。
  - request_hash 不同：返回冲突错误。
- scheduler 每次 tick 生成稳定 idempotency key。
- 用户 UI 手动发布可以不强制 idempotency key，但内部仍应生成 request_id。

---

## 12. 与 Pipeline 的关系

Pipeline Task Loading 是一种自动装载机制，Task Publisher 是更通用的入口抽象。

| 能力 | 作用 |
|---|---|
| Pipeline Loader | 在发布生命周期点自动生成 before/begin/after tasks |
| Scheduler Publisher | 按时间生成 PublishRequest |
| API Publisher | 接收外部请求生成 PublishRequest |
| Custom Tree Publisher | 用户直接提交 Task Tree |
| TaskBus | 接收普通 Task 并管理状态 |

关系：

```text
Scheduler/API/CustomTree/User/Collaborator
  → TaskPublisher
  → normalize + validate + preview
  → optional Pipeline Loader
  → TaskBus.publish
```

Pipeline Loader 可以被 PublishOptions 控制是否参与。

---

## 13. 事件与审计

建议新增事件：

- `task_publish.previewed`
- `task_publish.validated`
- `task_publish.rejected`
- `task_publish.published`
- `task_publish.idempotent_replayed`
- `schedule.created`
- `schedule.updated`
- `schedule.disabled`
- `schedule.triggered`
- `api_publish.received`

每个 publish 事件至少包含：

- `request_id`
- `session_id`
- `publisher_kind`
- `actor_id?`
- `idempotency_key?`
- `root_task_ids?`
- `rejection_reason?`

---

## 14. 配置文件需求

可以支持项目级定时发布配置：

```text
.taskweavn/schedules.yaml
```

示例：

```yaml
version: "1"
schedules:
  - id: daily-session-summary
    enabled: true
    timezone: Asia/Shanghai
    schedule:
      type: daily
      time_of_day: "18:00"
    session_selector:
      mode: current
    idempotency:
      key_template: "daily-summary:{{ date }}"
    task_tree:
      tasks:
        - id: summary
          title: Daily session summary
          intent: Summarize today's session progress, unresolved tasks, and risks.
          required_capability: summarize
          agent: system.summarizer
```

API 发布也可以支持配置 allowlist：

```yaml
api_publish:
  enabled: true
  allowed_capabilities: [summarize, audit, execute]
  allowed_agent_templates: [system.summarizer, system.audit]
  require_idempotency_key: true
```

---

## 15. 执行切片

### Slice 1: Task Publisher Contracts

产出：

- `TaskPublisher` Protocol
- `PublishRequest`
- `PublishPreview`
- `PublishResult`
- `PublisherRef`
- `NormalizedTaskTree`
- `NormalizedTaskNode`

验收：

- 用户、API、scheduler、custom tree 都能表达为 PublishRequest。
- preview 不写 TaskBus。
- publish 只通过统一服务写 TaskBus。

### Slice 2: Task Tree Parser and Validator

产出：

- YAML / JSON task tree parser
- normalize logic
- tree validation
- capability / agent_ref validation

验收：

- 自定义 Task Tree 可解析。
- DAG / cycle / missing intent / missing capability 被拒绝。
- agent_ref 与 capability 不匹配会失败。

### Slice 3: Publish Service and Idempotency

产出：

- `TaskPublishService`
- idempotency store
- publish metadata
- EventStream / MessageStream audit hooks

验收：

- API 重复提交同 key 同 payload 返回相同结果。
- 同 key 不同 payload 返回冲突。
- publish 后 Task metadata 可追溯 publisher。

### Slice 4: Scheduler Publisher

产出：

- `ScheduledPublishConfig`
- scheduler loop / tick
- last_run_at / next_run_at store
- schedule enable / disable

验收：

- due schedule 会产生 PublishRequest。
- scheduler 触发发布走 TaskBus。
- 重复 tick 不重复发布。

### Slice 5: API Publisher

产出：

- publish endpoint 语义实现
- preview endpoint 语义实现
- API publish allowlist
- rate limit / auth hook 预留

验收：

- API 能发布 Task Tree。
- API dry run 不发布。
- 未授权 capability 被拒绝。

### Slice 6: Pipeline Integration

产出：

- `PublishOptions.allow_pipeline`
- publisher 与 pipeline loader 集成
- pipeline task metadata 与 publisher metadata 兼容

验收：

- API 发布可选择触发 pipeline。
- scheduler 发布可选择不触发 pipeline。
- pipeline-generated task 仍可追溯原始 publisher request。

### Slice 7: Docs and Tests

产出：

- 用户自定义 Task Tree 文档
- schedules.yaml 示例
- API publish 示例
- 测试覆盖 publisher contracts、scheduler、API、idempotency

验收：

- 另一个实现会话能按文档完成 feature。

---

## 16. 测试计划

| 场景 | 期望 |
|---|---|
| custom tree preview | 返回 normalized tree，不写 TaskBus |
| custom tree publish | 转成普通 Task 并发布 |
| invalid tree | 缺 intent / cycle / invalid capability 被拒绝 |
| API dry run | 只 preview，不发布 |
| API idempotency replay | 同 key 同 payload 返回旧结果 |
| API idempotency conflict | 同 key 不同 payload 返回冲突 |
| scheduler due tick | 触发一次 publish |
| scheduler duplicate tick | 不重复发布 |
| schedule disabled | 不触发 publish |
| allow_pipeline=false | 不装载 pipeline tasks |
| publisher metadata | published Task 可追溯 publisher_kind / request_id |

---

## 17. 风险与决策点

| 风险 | 处理 |
|---|---|
| 发布入口太多导致 TaskBus 边界混乱 | 所有入口统一走 TaskPublishService，再调用 TaskBus.publish |
| API 被滥用 | 预留 auth、capability allowlist、rate limit、idempotency |
| 定时任务重复发布 | scheduler 必须使用稳定 idempotency key |
| 用户自定义 Task Tree 不合法 | preview + validate 必须先行 |
| 自定义 Task Tree 绕过 Collaborator 安全检查 | publish service 统一做 capability / agent / policy 校验 |
| pipeline 与 publisher 互相嵌套复杂 | `allow_pipeline` 显式控制，metadata 保留来源链 |
| cron 复杂度过高 | 第一版优先 interval / daily，cron 可后置 |

---

## 18. 完成标准

该 feature 完成时，应满足：

- 有统一 TaskPublisher / TaskPublishService 抽象。
- 定时任务可以按配置发布普通 Task 到 TaskBus。
- API 可以 preview 和 publish Task Tree。
- 用户可以输入自定义 Task Tree，经校验后发布。
- 所有发布方式都支持 publisher metadata 和审计事件。
- API 与 scheduler 支持幂等，避免重复发布。
- 发布时仍可与 Pipeline Loader 集成，但不破坏 TaskBus 边界。
- TaskBus 仍是唯一任务状态权威。

---

## 19. 状态

- Status: done / server-core release candidate
- Created: 2026-05-11
- Started: 2026-05-15
- Current Branch: `codex/collaborator-agent-task-authoring`
- Completed:
  - Slice 1 Task Publisher Contracts and minimal TaskBus-backed publish boundary.
  - Added `taskweavn.task.bus`:
    - `TaskBus`
    - `InMemoryTaskBus`
  - Added `taskweavn.task.publisher`:
    - `PublisherKind`
    - `PublisherRef`
    - `PublishSource`
    - `TaskPublishOptions`
    - `NormalizedTaskNode`
    - `NormalizedTaskTree`
    - `PublishRequest`
    - `PublishPreview`
    - `PublishResult`
    - `TaskPublishResult`
    - `TaskPublisher`
    - `DefaultTaskPublisher`
  - `DefaultTaskPublisher.preview(...)` validates normalized trees without writing TaskBus.
  - `DefaultTaskPublisher.publish(...)` converts normalized tree nodes into pending `TaskDomain` records and writes through `TaskBus.publish(...)`.
  - `DefaultTaskPublisher.publish_draft_tree(...)` bridges accepted DraftTaskTree publication to TaskBus-backed PublishedTasks and returns draft-to-published mappings for AuthoringCommandService.
  - `DefaultTaskPublisher.retry_task(...)` creates a retry root task for failed published tasks.
  - Slice 2 Task Tree Parser and Validator.
  - Added `taskweavn.task.publisher_input`:
    - `TaskTreeInputFormat`
    - `TaskTreeInputError`
    - `AgentCapabilityCatalog`
    - `StaticAgentCapabilityCatalog`
    - `AgentCapabilityBinding`
    - `TaskTreeInputValidator`
    - `TaskTreeValidation`
    - `TaskTreeValidationIssue`
    - `parse_task_tree_input(...)`
    - `normalize_task_tree_input(...)`
  - Custom Task Tree input supports JSON and YAML.
  - Parser supports nested `children` trees and flat `parent_id` trees.
  - Validator checks registered capability availability and optional `agent_ref` capability compatibility.
  - Slice 3 Publish Service and Idempotency.
  - Added `taskweavn.task.publisher_service`:
    - `TaskPublishService`
    - `PublishIdempotencyStore`
    - `InMemoryPublishIdempotencyStore`
    - `PublishIdempotencyRecord`
    - `PublishIdempotencyConflictError`
    - `TaskPublishAuditSink`
    - `InMemoryTaskPublishAuditSink`
    - `PublishAuditEvent`
  - `TaskPublishService.publish(...)` supports same-key/same-payload idempotent replay.
  - Same idempotency key with a different payload returns a skipped conflict result without writing TaskBus.
  - `DefaultTaskPublisher` now records publish request metadata on each published Task's dispatch constraints.
  - Publish audit hooks are defined as a thin sink boundary, ready to adapt into EventStream / MessageStream later.
  - Slice 4 Scheduler Publisher.
  - Added `taskweavn.task.scheduler`:
    - `ScheduledPublishConfig`
    - `ScheduleExpression`
    - `SessionSelector`
    - `IdempotencyPolicy`
    - `ScheduledPublishState`
    - `ScheduledPublishTickResult`
    - `ScheduledPublishStore`
    - `InMemoryScheduledPublishStore`
    - `SchedulerPublisher`
  - Scheduler tick evaluates due configs and builds scheduler `PublishRequest` objects.
  - Interval and daily schedules are executable in the first implementation.
  - Cron is accepted as reserved configuration shape but returns `unsupported schedule type` until a cron evaluator is introduced.
  - Scheduler state records `last_run_at`, `next_run_at`, and `last_result`.
  - Schedule enable / disable is supported through the store.
  - Scheduler idempotency keys are stable per schedule tick by default and may be customized with `key_template`.
  - Slice 5 API Publisher.
  - Added `taskweavn.task.api_publisher`:
    - `ApiAuthContext`
    - `ApiPublishPolicy`
    - `ApiPublishRequest`
    - `ApiRateLimiter`
    - `ApiRateLimitDecision`
    - `AllowAllApiRateLimiter`
    - `ApiTaskPublisher`
    - `DefaultApiTaskPublisher`
  - API preview returns `PublishPreview` without writing TaskBus.
  - API publish returns `PublishResult` and writes through `TaskPublishService`.
  - API publish requires idempotency keys by default, with policy override.
  - API layer validates session access, capability allowlists, agent allowlists, catalog capability, and agent capability compatibility.
  - Rate limiting is represented as a transport-neutral hook.
  - Slice 6 Pipeline Integration.
  - Added `taskweavn.task.pipeline`:
    - `PipelineStage`
    - `PipelineContextPolicy`
    - `PipelineTaskSpec`
    - `PipelineConfig`
    - `PipelineTaskLoader`
    - `DefaultPipelineTaskLoader`
  - `TaskPublishService` can optionally use a `PipelineTaskLoader` before preview/publish.
  - Publish-time pipeline expansion turns `task_before` and `task_begin` specs into ordinary `NormalizedTaskNode` roots.
  - `task_after` is modeled but not loaded during publish-time expansion; it belongs to completion-time orchestration.
  - `TaskPublishOptions.allow_pipeline=false` disables expansion for a request.
  - Pipeline-generated Tasks retain metadata for `pipeline_stage`, `pipeline_spec_id`, original request id, and original publisher kind.
  - Slice 7 Docs and Tests.
  - Added [Task Publisher 使用说明](../../project/task-publishers.md) with custom Task Tree, scheduler, API, and pipeline examples.
  - Added [release record](../../releases/task-publishers-schedule-api.md).
  - Updated release index and project docs index.
- Verified:
  - `uv run pytest tests/test_task_publisher.py tests/test_task_commands.py tests/test_authoring_command_service.py tests/test_collaborator_api_adapter.py` — 49 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_publisher.py tests/test_task_commands.py tests/test_authoring_command_service.py tests/test_collaborator_api_adapter.py`
  - `uv run mypy src/taskweavn/task tests/test_task_publisher.py tests/test_task_commands.py tests/test_authoring_command_service.py tests/test_collaborator_api_adapter.py`
  - `uv run pytest tests/test_task_publisher_input.py tests/test_task_publisher.py` — 34 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_publisher_input.py tests/test_task_publisher.py`
  - `uv run mypy src/taskweavn/task tests/test_task_publisher_input.py tests/test_task_publisher.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests` — 135 source files
  - `uv run pytest` — 606 passed, 1 warning
  - `git diff --check`
  - `uv run pytest tests/test_task_publish_service.py tests/test_task_publisher.py tests/test_task_publisher_input.py` — 43 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_publish_service.py tests/test_task_publisher.py tests/test_task_publisher_input.py`
  - `uv run mypy src/taskweavn/task tests/test_task_publish_service.py tests/test_task_publisher.py tests/test_task_publisher_input.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests` — 137 source files
  - `uv run pytest` — 615 passed, 1 warning
  - `git diff --check`
  - `uv run pytest tests/test_task_scheduler_publisher.py tests/test_task_publish_service.py` — 21 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_scheduler_publisher.py tests/test_task_publish_service.py`
  - `uv run mypy src/taskweavn/task tests/test_task_scheduler_publisher.py tests/test_task_publish_service.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests` — 139 source files
  - `uv run pytest` — 627 passed, 1 warning
  - `git diff --check`
  - `uv run pytest tests/test_task_api_publisher.py tests/test_task_publish_service.py` — 22 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_api_publisher.py tests/test_task_publish_service.py`
  - `uv run mypy src/taskweavn/task tests/test_task_api_publisher.py tests/test_task_publish_service.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests` — 141 source files
  - `uv run pytest` — 640 passed, 1 warning
  - `git diff --check`
  - `uv run pytest tests/test_task_pipeline.py tests/test_task_publish_service.py` — 17 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_pipeline.py tests/test_task_publish_service.py`
  - `uv run mypy src/taskweavn/task tests/test_task_pipeline.py tests/test_task_publish_service.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests` — 143 source files
  - `uv run pytest` — 648 passed, 1 warning
  - `git diff --check`
- Next Step: Continue persistent TaskBus / publish stores or completion-time `task_after` orchestration as follow-up work。
