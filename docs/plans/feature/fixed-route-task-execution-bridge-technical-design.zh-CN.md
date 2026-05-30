# Fixed-Route Task Execution Bridge 技术设计

> Status: in_progress
> Last Updated: 2026-05-29
> Feature Plan: [Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md)
> Gap: [Fixed-route task execution bridge](../../gaps/README.md)
> Decisions: [ADR-0010](../../decisions/ADR-0010-line-first-authoring-experience-for-1-0.md), [ADR-0011](../../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)

---

## 1. 背景

当前实现已进入 Slice 1-3 的服务边界：

- `FixedRouteTaskExecutor`；
- `ResidentDefaultAgent` protocol；
- `AgentLoopRunner` protocol 与 `AgentLoopResidentDefaultAgent` adapter；
- 支持 task-scoped AgentLoop runner factory，用于按 Session 构造 workspace
  和 EventStream 上下文；
- 基于现有 TaskBus `claim_next -> complete / fail` 的单次 tick；
- 使用 fake Default Agent adapter 的 focused unit tests。
- `MainPageSidecarApp.run_fixed_route_tick(...)` runtime assembly seam；
- 覆盖 publish -> tick -> projected `done` 的 sidecar smoke tests。
- `LoopResult.finished=True` 映射为稳定的
  `agent_loop:{session_id}:{task_id}:{stop_reason}` result ref；
- `LoopResult.finished=False` 映射为 `agent_loop_failed:{stop_reason}` failure ref。
- `build_agent_loop_resident_default_agent(...)` 在 sidecar 装配层构造
  session-scoped AgentLoop，使用 LocalRuntime、文件/命令工具和 SqliteEventStream。

production runtime trigger / background dispatch、durable result summary
storage、更完整的 Main Page projection polish、CodeAction/Docker-backed tool
纳入和最终 gap closure 尚未完成；当前已有 checkpoint release record。

ADR-0010 明确 1.0 默认是 line-first：

```text
single-task / single-agent / fixed-route flow
```

因此 1.0 当前不需要复杂路由策略，也不需要 Router / Routing Agent policy /
Agent Manager / Agent registry / assignment 字段。1.0 需要的是把 Published Task 从 TaskBus
真正推进到执行：

```text
pending -> running -> done / failed
```

现有基础：

- `TaskBus.claim_next(session_id, capability, agent_id)`；
- `TaskBus.complete(session_id, task_id, result_ref=...)`；
- `TaskBus.fail(session_id, task_id, error_ref=...)`；
- `TaskDomain.claimed_by`；
- SQLite / in-memory TaskBus lifecycle 测试。

本方案的目标是利用这些已有能力，补一个固定路线执行桥，而不是提前实现 Product 1.1 的 assignment 体系。

---

## 2. 设计原则

### 2.1 固定路线优先

1.0 执行路线固定：

```text
TaskBus pending Task
  -> FixedRouteTaskExecutor
  -> Default Agent task-run
  -> TaskBus complete / fail
```

Default Agent 在 1.0 中是稳定的系统执行身份和 runtime boundary，而不是一个必须
跨 Task 保活的 AgentLoop 实例。每次 claim 到 Task 后按需创建本次 Agent run，
Task done/failed 后结束。1.0 不通过 Agent Manager 动态创建实例。

### 2.2 不引入 assignment domain

本工作包不新增：

- `assigned_agent_id`;
- `assigned_by`;
- `assigned_at`;
- `assignment_rationale`;
- `assign(...)`;
- `claim_assigned(...)`;
- Router tick;
- Agent Manager tick。

这些能力保留在 [Minimal Agent Assignment Semantics](minimal-agent-assignment-semantics.md)，作为 Product 1.1+ routing foundation。

### 2.3 TaskBus 仍是生命周期权威

执行桥只能调用 TaskBus API 推进状态：

```text
claim_next -> complete / fail
```

不直接修改 Task 对象，不写 UI projection，不绕过 TaskBus。

---

## 3. 核心对象

### 3.1 FixedRouteTaskExecutor

建议接口：

```python
@dataclass(frozen=True)
class FixedRouteTaskExecutorConfig:
    session_id: str
    default_agent_id: str = "default_agent"


class FixedRouteTaskExecutor:
    def __init__(
        self,
        *,
        task_bus: TaskBus,
        default_agent: ResidentDefaultAgent | None,
        config: FixedRouteTaskExecutorConfig,
    ) -> None: ...

    def tick(self) -> TaskExecutionTickResult: ...
```

`tick()` 第一版只处理一个 Task，符合 1.0 单任务/单 Agent 约束。

当前实现中 `default_agent` 允许为 `None`。这不是 routing failure，而是
runtime health path：`tick()` 返回 `TaskExecutionTickResult(status="health_error",
error_ref="default_agent_unavailable")`，并且不会 claim Task。

### 3.2 ResidentDefaultAgent

最小协议：

```python
class ResidentDefaultAgent(Protocol):
    def run(self, task: TaskDomain) -> TaskRunResult: ...


@dataclass(frozen=True)
class TaskRunResult:
    result_ref: str | None = None
    error_ref: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_ref is None
```

约束：

- `ok=True` 时调用 `TaskBus.complete`；
- `ok=False` 时调用 `TaskBus.fail`；
- Default Agent 执行 Task 时抛异常，捕获并转成 `TaskBus.fail`；
- Default Agent 未启动不是单个 Task 的 routing failure，而是 app/runtime health failure，应在启动或诊断层暴露。

当前 Slice 2 已补充 `AgentLoopResidentDefaultAgent`：

```python
class AgentLoopRunner(Protocol):
    def run(self, task: str) -> LoopResult: ...


@dataclass(frozen=True)
class AgentLoopResidentDefaultAgent:
    loop: AgentLoopRunner | None = None
    result_ref_prefix: str = "agent_loop"
    loop_factory: AgentLoopRunnerFactory | None = None

    def run(self, task: TaskDomain) -> TaskRunResult: ...
```

映射规则：

- `loop` 与 `loop_factory` 必须二选一；两者同时为空或同时设置都会在
  `__post_init__` 抛 `ValueError`；
- `TaskDomain.intent` 是传入 `AgentLoopRunner.run(...)` 的输入；
- `LoopResult.finished=True` 映射为 `TaskRunResult(result_ref=...)`；
- `LoopResult.finished=False` 映射为
  `TaskRunResult(error_ref="agent_loop_failed: {stop_reason}")`；
- `loop` 适合 focused tests 和固定 fake loop；
- `loop_factory` 适合 sidecar runtime，按 `TaskDomain.session_id` 创建
  session-scoped AgentLoop；
- 当前 `result_ref` 只保存可追踪引用：
  `agent_loop:{session_id}:{task_id}:{stop_reason}`，不保存 `final_answer`
  payload；durable result summary store 是后续 slice；
- 生产环境的 durable result payload 持久化仍由后续 slice 处理。

### 3.3 Sidecar AgentLoop assembly

当前 Slice 3 已补 `build_agent_loop_resident_default_agent(...)`：

```python
def build_agent_loop_resident_default_agent(
    *,
    layout: WorkspaceLayout,
    llm: Any,
    max_steps: int = 20,
) -> AgentLoopResidentDefaultAgent: ...
```

装配规则：

- `MainPageSidecarConfig` 当前新增：
  - `enable_default_agent: bool = True`;
  - `default_agent_max_steps: int = 20`;
- `MainPageSidecarDependencies.default_agent` 优先级最高：测试或未来 packaging
  可以显式注入 fake / production-specific Default Agent；
- 当 `dependencies.default_agent is None` 且
  `config.enable_default_agent is True` 时，`build_main_page_sidecar_app(...)`
  默认启用 AgentLoop-backed Default Agent；
- 测试或诊断可以通过 `MainPageSidecarConfig(enable_default_agent=False)`
  保留 missing Default Agent 的 runtime health path；
- 每次 `run_fixed_route_tick(session_id)` 被显式调用时，adapter 为被 claim
  的 Task 创建一个新的 AgentLoop runner；
- runner 使用 `layout.session_project_dir(session_id)` 作为模型可见 workspace；
- runner 使用 `layout.session_events_db(session_id)` 作为 EventStream；
- runner 使用 `LocalRuntime` 并在 run 前注册工具；
- 第一版工具集仅包含 `ReadFileTool`、`WriteFileTool`、`ListDirTool`、
  `RunCommandTool`。

暂缓项：

- 不自动后台轮询；
- 不新增 HTTP control route；
- 不自动响应 publish 的 `startImmediately`；
- 不引入 Router / Agent Manager / assignment；
- 不默认启用 `CodeActionTool`，因为它在 startup 阶段会启动 Docker-backed
  sandbox，需要单独的 runtime readiness 策略。

---

## 4. Tick 流程

```python
def tick(self) -> TaskExecutionTickResult:
    if default_agent is None:
        return TaskExecutionTickResult(
            status="health_error",
            skipped_reason="default_agent_unavailable",
            error_ref="default_agent_unavailable",
        )

    task = select_next_pending_task_for_fixed_route(...)
    if task is None:
        return TaskExecutionTickResult(
            status="idle",
            skipped_reason="no_eligible_task",
        )

    claimed = task_bus.claim_next(
        task.session_id,
        capability=task.required_capability,
        agent_id=default_agent_id,
    )
    if claimed is None:
        return TaskExecutionTickResult(
            status="claim_not_available",
            skipped_reason="claim_not_available",
        )

    try:
        result = default_agent.run(claimed)
    except Exception as exc:
        failed = task_bus.fail(
            claimed.session_id,
            claimed.task_id,
            error_ref=f"agent_execution_failed: {type(exc).__name__}",
        )
        return TaskExecutionTickResult(claimed_task_id=claimed.task_id, failed_task_id=failed.task_id)

    if result.ok:
        completed = task_bus.complete(claimed.session_id, claimed.task_id, result_ref=result.result_ref)
        return TaskExecutionTickResult(claimed_task_id=claimed.task_id, completed_task_id=completed.task_id)

    failed = task_bus.fail(
        claimed.session_id,
        claimed.task_id,
        error_ref=result.error_ref or "agent_execution_failed",
    )
    return TaskExecutionTickResult(claimed_task_id=claimed.task_id, failed_task_id=failed.task_id)
```

`claim_next` 当前需要 capability。推荐先从 pending Task 中按当前 line-first 规则选择下一项，再用其 `required_capability` 调用 `claim_next`。这避免把 capability 配置变成另一个隐式路由策略。

---

## 5. 错误处理

| Failure | TaskBus result |
|---|---|
| no eligible Task | `TaskExecutionTickResult(status="idle")`; no-op |
| claim not available | `TaskExecutionTickResult(status="claim_not_available")`; no-op |
| Default Agent unavailable | `TaskExecutionTickResult(status="health_error")`; no Task claim |
| Default Agent execution exception | `failed`, `error_ref=agent_execution_failed: ...` |
| Default Agent returns error | `failed`, agent-provided `error_ref` |
| AgentLoop returns `finished=False` | `failed`, `error_ref=agent_loop_failed: {stop_reason}` |

不实现：

- dispatch timeout；
- assignment timeout；
- claim timeout；
- running timeout；
- hard cancel。

---

## 6. Main Page Projection

本工作包不新增 assignment UI。

Main Page 只需要现有状态投影和执行引用：

| Task fact | UI meaning |
|---|---|
| `pending` | `execution=pending`; legacy display `status=queued` |
| `running` | Running |
| `done` | Done / result available |
| `failed` | Failed / retry available where supported |
| `result_ref` | Transport snapshot `resultRef`; present for completed published Tasks when the execution bridge records a result reference. |
| `error_ref` | Transport snapshot `errorRef`; present for failed published Tasks as a diagnostic/reference string. |

Projection closure rule:

- `TaskDomain.result_ref/error_ref` 是 TaskBus lifecycle fact；
- `TaskCardView.result_ref/error_ref` 是 task projection owner field；
- `TaskNodeCardView.execution` 是 canonical execution status，必须稳定表达
  `pending/running/done/failed`；
- `TaskNodeCardView.status` 保持 legacy display status，允许把 backend
  `pending` 显示为 `queued`；
- `TaskNodeCardView.resultRef/errorRef` 是 Main Page transport owner field；
- UI 可以用这些字段决定是否存在可追踪结果/错误引用，但不应把 ref 本身当作
  面向用户的最终文案；
- 失败详情展示和 durable result summary payload 存储属于后续 slice，不在本次
  fixed-route bridge closure 内完成。

---

## 7. 测试方案

- pending Task 成功执行后 `done`；
- Default Agent 返回 error 后 `failed`；
- Default Agent 抛异常后 `failed`；
- 无 pending Task 时 no-op；
- Default Agent 未启动时不 claim Task，并产生 runtime health error；
- parent 未完成的子 Task 不被 claim；
- `claimed_by` 使用固定 Default Agent id。
- `AgentLoopResidentDefaultAgent(loop_factory=...)` 会按 Task 创建 runner；
- sidecar 默认 AgentLoop-backed Default Agent 可以通过显式 tick 推进
  `pending -> done`，并写入 session events sqlite；
- `enable_default_agent=False` 保留 missing Default Agent health path。

---

## 8. Production runtime trigger / background dispatch 设计

### 8.1 要解决的问题

当前 `MainPageSidecarApp.run_fixed_route_tick(session_id)` 是显式测试/诊断
seam。它证明 TaskBus -> Default Agent -> TaskBus lifecycle 能工作，但还不是
生产触发路径。

Product 1.0 需要的是：

```text
用户发布 TaskTree
  -> HTTP command 快速返回 accepted/rejected
  -> sidecar 后台触发 fixed-route execution
  -> UI 通过 snapshot / conservative refetch 观察 pending/running/done/failed
```

不能把 AgentLoop 执行放在 publish HTTP request 内同步完成。原因：

- AgentLoop 可能较慢，阻塞 HTTP request 会让 UI 命令生命周期不可控；
- 用户需要先看到 publish accepted / queued 状态；
- sidecar shutdown、浏览器取消请求、重复提交都不应该破坏 TaskBus lifecycle；
- 后续 SSE 或事件源可以增强感知，但最终事实仍应来自 snapshot query。

### 8.2 设计决策

第一版采用 sidecar 进程内 background dispatcher：

```text
PlatoUiHttpTransport / command gateway
  -> ExecutionTriggerGateway.request_dispatch(session_id, reason, command_id)
  -> FixedRouteExecutionDispatcher background worker
  -> FixedRouteTaskExecutor.tick()
  -> TaskBus lifecycle facts
```

约束：

- `FixedRouteTaskExecutor.tick()` 保持同步、纯粹、可单测；
- dispatcher 只负责调度和重复触发合并，不直接改 Task；
- dispatcher 与 sidecar 同生命周期，由 `MainPageSidecarApp.close()` 停止；
- Product 1.0 使用单 worker，避免并行 Task-run Agent 语义提前复杂化；
- 每个 Session 的重复 trigger 在 pending/running dispatch 时合并；
- 不引入 Router、Agent Manager、assignment 字段、assigned-only claim 或 Main Page
  reassignment UI。

### 8.3 Agent lifecycle != Context lifecycle

Slice 6 明确区分 Agent 生命周期和上下文生命周期：

- Agent 生命周期是 Task-run 级别：有 eligible pending Task 时启动，claim 一个
  Task，创建本次 AgentLoop runner，Task done/failed 后结束；
- 每个 Task 仍然是一次独立 Agent 执行。Task 之间通过 TaskBus lifecycle、
  MessageStream、EventStream、result/error refs 等 durable facts 串联，不通过
  长生命周期 Agent 内存串联；
- 上下文连续性是 Session 级责任。Product 1.0 当前依赖已有 session-scoped
  facts，足以支撑小型串行任务；
- Slice 6 不新增 `SessionContextStore`、上下文摘要器或上下文预算治理；
- 更系统的上下文治理、session summary、task-local context pruning 和跨任务
  context assembly 仍在调研中，放入 Product 1.1 计划。

因此第一版 dispatcher 不应缓存或保活 AgentLoop。可以保留 sidecar-owned
dispatcher 和 stable Default Agent identity，但 AgentLoop/runtime/tools 仍按
Task run 按需创建和释放。

### 8.4 核心接口

建议新增轻量 runtime boundary：

```python
DispatchTriggerReason = Literal[
    "publish_start_immediately",
    "manual_control_route",
    "startup_recovery",
]


@dataclass(frozen=True)
class ExecutionDispatchRequestResult:
    session_id: str
    status: Literal[
        "queued",
        "already_pending",
        "already_running",
        "disabled",
        "health_error",
    ]
    reason: DispatchTriggerReason
    request_id: str | None = None
    message: str = ""


class ExecutionTriggerGateway(Protocol):
    def request_dispatch(
        self,
        session_id: str,
        *,
        reason: DispatchTriggerReason,
        request_id: str | None = None,
    ) -> ExecutionDispatchRequestResult: ...
```

`FixedRouteExecutionDispatcher` 建议持有：

- `task_bus`;
- `default_agent`;
- `default_agent_id`;
- `max_ticks_per_trigger`;
- `enabled`;
- `pending_session_ids`;
- `running_session_ids`;
- background worker thread / condition。

worker 对每个 session 执行 bounded drain：

```python
for _ in range(max_ticks_per_trigger):
    result = executor.tick()
    record result for diagnostics
    if result.status in {"idle", "health_error", "claim_not_available"}:
        break
```

说明：

- bounded drain 可以让线性 TaskTree 自动推进多个已解锁节点；
- `max_ticks_per_trigger` 防止一个 trigger 长时间占住 worker；
- 如果 Task 执行产生用户确认或等待状态，当前 fixed-route tick 应自然进入
  `idle` / no eligible task，而不是忙等；
- 失败 Task 进入 terminal `failed`，不在 dispatcher 内自动 retry。

### 8.5 Trigger sources

核心规则：trigger 的语义是“请求 dispatcher 检查这个 Session 是否有 eligible
pending work 并尽力推进”，而不是“只有 publish 才能启动 Agent”。

第一版触发源：

1. Publish command with `startImmediately=true`
   - `POST /api/v1/sessions/{sessionId}/task-tree/publish`;
   - publish 成功后 request dispatch；
   - command response 仍表示 publish accepted，不等待执行完成；
   - response refresh 继续建议 `session.snapshot` / `task.tree`。

2. Explicit control route
   - `POST /api/v1/sessions/{sessionId}/execution/dispatch`;
   - 用于恢复、测试、开发工具按钮或未来 UI retry；
   - 返回 dispatch request result，不返回 Task 执行结果；
   - 不接受 task id，不做 assignment，不绕过 TaskBus eligibility。

3. Optional startup recovery
   - 第一版默认不自动扫描所有 Sessions；
   - 可以保留 config 开关，如 `dispatch_pending_on_startup=False`；
   - 原因是 running-task crash recovery 还没有策略，启动扫描只适合 pending
     Tasks，不适合安全处理旧 running Tasks。

后续也可以由 confirmation resolved、post-publish edit、用户显式 retry 等事件触发
同一个 dispatch boundary，但这些不是 Slice 6 的首批实现范围。

### 8.6 HTTP/API contract

新增 route 候选：

```text
POST /api/v1/sessions/{sessionId}/execution/dispatch
```

请求：

```json
{
  "commandId": "dispatch-session-...",
  "sessionId": "session-1",
  "idempotencyKey": "optional-client-key",
  "payload": {
    "reason": "manual_control_route"
  }
}
```

响应：

```json
{
  "requestId": "dispatch-session-...",
  "ok": true,
  "result": {
    "commandId": "dispatch-session-...",
    "status": "accepted",
    "message": "execution dispatch queued",
    "debugRefs": {
      "dispatchStatus": "queued"
    }
  },
  "refresh": {
    "waitForEvents": true,
    "suggestedQueries": ["session.snapshot", "task.tree"]
  }
}
```

错误/不可用语义：

- dispatcher disabled -> `ok=false`, `error.code=command_rejected` 或
  `internal_error` 取决于配置是否预期；
- invalid session -> `not_found`;
- default agent unavailable -> command 可被拒绝，或 accepted 但
  `debugRefs.dispatchStatus=health_error`。第一版建议拒绝显式 control route，
  但 publish hook 可只记录 health diagnostic，避免 publish 成功被 execution
  health 问题回滚。

### 8.7 Publish `startImmediately` 语义

`PublishTaskTreePayload.start_immediately` 已存在。Slice 6 应正式定义：

- `true`：publish 成功后 enqueue session dispatch；
- `false`：只发布 TaskTree，不触发 execution；
- publish command response 不承诺执行完成，只承诺 dispatch request accepted
  或已记录为 diagnostic；
- 重复 publish command 通过现有 UI command idempotency 处理；
- 重复 dispatch trigger 由 dispatcher coalescing 处理。

这避免前端多次点击造成多个并行 AgentLoop。

### 8.8 State visibility

UI 不需要新的 assignment 状态。可观察事实仍是：

- `execution=pending`;
- `execution=running`;
- `execution=done`, `resultRef`;
- `execution=failed`, `errorRef`;
- command refresh / conservative refetch。

当前 `ResyncOnlyEventSource` 可以继续工作。SSE 真实事件源是增强项，不是 Slice 6
前置依赖。

### 8.9 Shutdown and lifecycle

`MainPageSidecarApp.close()` 必须：

1. stop dispatcher;
2. wait bounded timeout for worker exit;
3. then close HTTP server/message bus/task bus/stores。

如果 worker 正在执行 AgentLoop：

- 第一版不强杀；
- stop 请求只阻止后续 queued dispatch；
- 当前运行中的 Task 由 AgentLoop 正常返回后 complete/fail；
- hard cancellation 和 cooperative interruption 属于后续 Product 1.0/1.1
  单独策略。

### 8.10 Running crash recovery

当前 TaskBus 没有 running timeout/reclaim 语义。若 sidecar 进程在 Task running
时崩溃，重启后可能留下 `running` Task。

第一版 Slice 6 不自动改写旧 running Task，因为这会引入新的生命周期决策。
需要后续单独策略：

- running older than threshold -> fail with `error_ref=execution_interrupted`;
- 或 running older than threshold -> reset to pending if action is idempotent;
- 或显示 recover action，让用户决定 retry/mark failed。

在该策略落地前，startup recovery 只应考虑 pending Tasks，且默认关闭。

### 8.11 测试计划

Unit tests:

- dispatcher queues one session and completes a pending Task；
- dispatcher drains multiple linearly-unlocked Tasks up to `max_ticks_per_trigger`；
- duplicate dispatch while pending/running returns `already_pending` /
  `already_running`；
- dispatcher trigger is not publish-specific: explicit route can advance any
  eligible pending Task in the Session；
- dispatcher disabled returns `disabled` and does not claim；
- missing Default Agent returns/records `health_error`；
- each claimed Task gets an isolated Agent run; dispatcher does not reuse a
  live AgentLoop across Tasks；
- stop prevents new queued work and closes worker。

Sidecar integration tests:

- publish with `startImmediately=true` schedules dispatch and eventually snapshot
  shows `execution=done` + `resultRef`；
- publish with `startImmediately=false` leaves snapshot at `execution=pending`；
- explicit `/execution/dispatch` route queues dispatch；
- repeated dispatch route calls do not create parallel execution；
- dispatcher failure path snapshots `execution=failed` + `errorRef`。

Docs/tests closure:

- fixed-route checkpoint is updated after Slice 6 implementation;
- production trigger/background dispatch is implemented;
- keep gap `in_progress` until durable result payload behavior and user-facing
  smoke pass。

---

## 9. 与后续 Routing Foundation 的关系

```text
1.0:
  stable Default Agent identity
  FixedRouteTaskExecutor -> claim_next

1.1+:
  Router -> assign
  Agent Manager -> claim_assigned
```

迁移条件：

- 多执行 Agent 变成真实需求；
- 用户需要自定义路由；
- Main Page 需要展示 assignment / waiting-for-agent；
- skills/MCP/多模态执行带来能力选择复杂度。
