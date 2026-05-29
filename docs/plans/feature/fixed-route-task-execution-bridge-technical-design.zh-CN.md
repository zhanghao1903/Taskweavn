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
- 使用 fake resident Default Agent 的 focused unit tests。
- `MainPageSidecarApp.run_fixed_route_tick(...)` runtime assembly seam；
- 覆盖 publish -> tick -> projected `done` 的 sidecar smoke tests。
- `LoopResult.finished=True` 映射为稳定的
  `agent_loop:{session_id}:{task_id}:{stop_reason}` result ref；
- `LoopResult.finished=False` 映射为 `agent_loop_failed:{stop_reason}` failure ref。
- `build_agent_loop_resident_default_agent(...)` 在 sidecar 装配层构造
  session-scoped AgentLoop，使用 LocalRuntime、文件/命令工具和 SqliteEventStream。

后台循环 / HTTP control route、durable result summary storage、更完整的
Main Page projection polish、CodeAction/Docker-backed tool 纳入和 release
record 尚未完成。

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
  -> resident Default Agent
  -> TaskBus complete / fail
```

Default Agent 是应用/runtime 启动时常驻的万能执行 Agent。它可以先由当前 AgentLoop 或执行能力封装而成，但 1.0 不通过 Agent Manager 动态创建实例。

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
| resident Default Agent unavailable | `TaskExecutionTickResult(status="health_error")`; no Task claim |
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

## 8. 与后续 Routing Foundation 的关系

```text
1.0:
  resident Default Agent
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
