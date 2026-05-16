# Task Publisher 使用说明

> Status: server-core release candidate
> Last Updated: 2026-05-16
> Related Plan: [Task Publisher 抽象、定时发布与接口发布](../plans/feature/task-publishers-schedule-api.md)
> Related Release: [Task Publishers, Schedule, API, And Pipeline Expansion](../releases/task-publishers-schedule-api.md)

---

## 1. 目的

TaskPublisher 是 TaskWeavn 中所有执行 Task 进入 TaskBus 的统一发布边界。

它解决的问题是：用户、Collaborator、scheduler、API、自定义 Task Tree、pipeline loader 都可以生成任务，但它们不能各自直接写 TaskBus。所有入口都应该先归一化、校验、preview、幂等处理，再发布为普通 `TaskDomain`。

```text
custom tree / API / scheduler / collaborator / pipeline
  -> Normalize
  -> Validate / Preview
  -> TaskPublishService
  -> DefaultTaskPublisher
  -> TaskBus.publish(TaskDomain)
```

第一版是 server-core 能力，不绑定 HTTP 框架，也不实现分布式调度器。

---

## 2. 自定义 Task Tree

自定义 Task Tree 支持 JSON 和 YAML。入口是：

- `parse_task_tree_input(...)`
- `normalize_task_tree_input(...)`
- `TaskTreeInputValidator`

YAML 示例：

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
        capability: testing
        agent: system.tester
```

也支持 flat `parent_id` 形式：

```yaml
tasks:
  - id: root
    title: Root
    intent: Do root work.
    capability: general
  - id: child
    parent_id: root
    title: Child
    intent: Do child work.
    capability: testing
```

校验范围：

- 必须是 Tree List，不支持 DAG。
- 必须有 `intent`。
- 必须有 `required_capability` 或 `capability`。
- flat 输入不能同时使用 `children`。
- capability 可以通过 `CapabilityCatalog` 校验。
- `agent_ref` 可以通过 `AgentCapabilityCatalog` 校验。

---

## 3. 发布服务

核心服务是 `TaskPublishService`。

```python
service = TaskPublishService(
    publisher=DefaultTaskPublisher(task_bus=task_bus),
    idempotency_store=InMemoryPublishIdempotencyStore(),
    audit_sink=InMemoryTaskPublishAuditSink(),
)
```

行为：

- `preview(request)` 返回 `PublishPreview`，不写 TaskBus。
- `publish(request)` 返回 `PublishResult`，通过 `DefaultTaskPublisher` 写 TaskBus。
- 有 `idempotency_key` 时，同 key 同 payload 返回第一次结果。
- 同 key 不同 payload 返回 skipped conflict，不写 TaskBus。
- publish audit 通过 `TaskPublishAuditSink` hook 发出，后续可接 EventStream、MessageStream 或 observability。

发布后的 `TaskDomain.dispatch_constraints.metadata` 会保留：

- `publish_request_id`
- `publish_idempotency_key`
- `publisher_kind`
- `publisher_actor_id`
- `source_type`
- `source_id`
- `source_ref`
- `source_node_id`

---

## 4. Scheduler Publisher

Scheduler 只是 publisher 上游适配器，不执行任务。

```python
config = ScheduledPublishConfig(
    id="daily-summary",
    schedule=ScheduleExpression(type="daily", time_of_day="18:00"),
    session_selector=SessionSelector(mode="fixed", session_id="s1"),
    task_tree={
        "tasks": [
            {
                "id": "summary",
                "title": "Daily summary",
                "intent": "Summarize today's session progress and risks.",
                "capability": "summarize",
            }
        ]
    },
)
```

`SchedulerPublisher.tick(...)` 会：

1. 找出 due schedule。
2. 构造 `PublisherRef(kind="scheduler")`。
3. 生成稳定 idempotency key。
4. 调用 `TaskPublishService.publish(...)`。
5. 更新 `ScheduledPublishState.last_run_at / next_run_at / last_result`。

第一版支持：

- `interval`
- `daily`
- enable / disable
- current/fixed session selector
- 自定义 idempotency key template

第一版保留但不执行：

- `cron`

---

## 5. API Publisher

API Publisher 是传输协议无关的语义适配层，入口是 `DefaultApiTaskPublisher`。

它不依赖 FastAPI、Typer、HTTP 或 RPC。未来 HTTP endpoint 可以很薄地包装它。

```python
adapter = DefaultApiTaskPublisher(
    publish_service=service,
    policy=ApiPublishPolicy(
        require_idempotency_key=True,
        allowed_capabilities=("summarize", "testing"),
        allowed_agent_refs=("system.summarizer", "system.tester"),
    ),
    capability_catalog=capability_catalog,
    agent_catalog=agent_catalog,
)
```

请求形状：

```python
request = ApiPublishRequest(
    session_id="s1",
    source_id="external-job-123",
    idempotency_key="external-job-123",
    task_tree={
        "tasks": [
            {
                "id": "summarize",
                "title": "Summarize current session",
                "intent": "Summarize progress and outstanding risks.",
                "capability": "summarize",
                "agent": "system.summarizer",
            }
        ]
    },
)
```

安全边界：

- `ApiAuthContext.allowed_session_ids`
- `ApiAuthContext.allowed_capabilities`
- `ApiAuthContext.allowed_agent_refs`
- `ApiPublishPolicy.allowed_capabilities`
- `ApiPublishPolicy.allowed_agent_refs`
- `ApiRateLimiter` hook

默认要求 API publish 带 `idempotency_key`。可以通过 policy 关闭，但生产入口不建议关闭。

---

## 6. Pipeline Expansion

Pipeline Loader 在 publish-time 只负责自动装载普通 Task，不负责执行任务。

```python
pipeline = PipelineConfig(
    task_before=(
        PipelineTaskSpec(
            id="review",
            title="Review Task Tree",
            intent_template="Review request {request_id} with roots {root_ids}.",
            required_capability="audit",
            agent_ref="system.audit",
        ),
    ),
    task_begin=(
        PipelineTaskSpec(
            id="prepare",
            title="Prepare Context",
            intent_template="Prepare session {session_id} before {task_count} tasks.",
            required_capability="summarize",
            agent_ref="system.summarizer",
        ),
    ),
)
```

接入：

```python
service = TaskPublishService(
    publisher=DefaultTaskPublisher(task_bus=task_bus),
    pipeline_loader=DefaultPipelineTaskLoader(pipeline),
)
```

第一版语义：

- `task_before` 和 `task_begin` 在 publish-time 扩展为 root Tasks。
- 它们和主任务一样写入 TaskBus。
- `task_after` 已建模，但不在 publish-time 装载，后续由 completion-time orchestration 触发。
- `TaskPublishOptions.allow_pipeline=false` 可关闭本次发布的 pipeline expansion。

Pipeline task metadata 会保留：

- `source = "pipeline"`
- `pipeline_stage`
- `pipeline_spec_id`
- `pipeline_order`
- `pipeline_source_request_id`
- `pipeline_source_publisher_kind`
- `pipeline_source_id`

---

## 7. 当前边界

已完成：

- TaskPublisher / TaskBus-backed publish。
- JSON/YAML custom Task Tree parser。
- Capability / agent validation。
- Publish service with idempotency。
- Scheduler publisher。
- Transport-neutral API publisher。
- Publish-time pipeline expansion。

未完成：

- 持久化 TaskBus / publisher stores。
- HTTP/RPC server transport。
- cron evaluator。
- completion-time `task_after` orchestration。
- 分布式 scheduler。
- 用户界面中的 preview/confirm 体验。

