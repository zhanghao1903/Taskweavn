# Minimal Agent Assignment Semantics 技术设计

> Status: deferred
> Last Updated: 2026-05-28
> Feature Plan: [Minimal Agent Assignment Semantics](minimal-agent-assignment-semantics.md)
> Gap: [Routing Agent assignment productization](../../gaps/README.md)
> Decisions: [ADR-0011](../../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md), [ADR-0012](../../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)

---

## 1. 背景

当前 TaskBus 已经能表达最小执行生命周期：

```text
pending -> running -> done / failed
```

并且已有：

- `TaskDomain.claimed_by`;
- `TaskBus.claim_next(...)`;
- `TaskBus.complete(...)`;
- `TaskBus.fail(...)`;
- `TaskBus.skip(...)`;
- SQLite TaskBus 对应持久化实现。

但 `claim_next(capability, agent_id)` 仍然让 Execution Agent 可以按
capability 直接领取任务。后续版本需要把领取前的 assignment 变成明确事实：

```text
pending unassigned
  -> Router assign
  -> pending assigned
  -> Agent Manager create instance and claim
  -> running
```

这个设计必须遵守 ADR-0012，但不再作为 Product 1.0 实施范围：

- TaskBus 是 Published Task 生命周期事实权威；
- Router / Agent Manager 是首个 routing foundation 的单实例收敛循环；
- assignment 不是新状态；
- 不做复杂 callback handshake；
- 不做锁、lease、version/CAS；
- stale pending 由 TaskBus sweep 退化为普通 failed。

Product 1.0 按 ADR-0010 采用 line-first / fixed-route 默认，当前应实现
[Fixed-Route Task Execution Bridge](fixed-route-task-execution-bridge.md)，不实现本方案中的 assignment 字段、Router 或 Agent Manager。

---

## 2. 当前代码事实

### 2.1 TaskDomain

当前核心字段位于 `src/taskweavn/task/models.py`：

```python
TaskStatus = Literal["pending", "running", "done", "failed"]

class TaskDomain(BaseModel):
    task_id: str
    session_id: str
    root_id: str
    parent_id: str | None = None
    intent: str
    status: TaskStatus = "pending"
    dispatch_constraints: TaskDispatchConstraints | None = None
    claimed_by: str | None = None
    result_ref: str | None = None
    error_ref: str | None = None
    created_at: datetime = ...
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

需要新增 assignment 字段，但不新增 status。

### 2.2 TaskBus

当前 `TaskBus` interface 提供：

```python
claim_next(session_id, *, capability, agent_id) -> TaskDomain | None
complete(session_id, task_id, *, result_ref=None) -> TaskDomain
fail(session_id, task_id, *, error_ref) -> TaskDomain
skip(session_id, task_id, *, reason) -> TaskDomain
```

需要从“按 capability claim”推进到“先 assign，再 assigned-only claim”。

### 2.3 Retry

当前 Product 1.0 retry 已收敛为 in-place retry：同一个 failed published Task
回到 `pending`，不发布新的 retry root Task。

后续增加 assignment 字段时，retry 必须清理：

- assignment；
- `claimed_by`；
- `started_at`；
- `completed_at`；
- `result_ref`；
- `error_ref`。

---

## 3. 领域模型变更

### 3.1 TaskDomain assignment 字段

建议新增：

```python
assigned_agent_id: str | None = Field(default=None, min_length=1)
assigned_by: str | None = Field(default=None, min_length=1)
assigned_at: datetime | None = None
assignment_rationale: str | None = None
```

语义：

| Field | Meaning |
|---|---|
| `assigned_agent_id` | Router 选择的 Agent identity/template/capability object id，不是 runtime instance id。 |
| `assigned_by` | 产生 assignment 的 Router / system actor。 |
| `assigned_at` | 最近一次 assignment 成功时间。 |
| `assignment_rationale` | 可选的人类可读/审计可读理由。 |

约束：

- assignment 只允许写到 `pending` Task；
- assignment 可以在 `pending` 且未 claim 时覆盖；
- `running` / `done` / `failed` 不允许 assign；
- `assigned_agent_id` 不等于 `claimed_by`，前者是路由事实，后者是运行事实；
- `claimed_by` 可以使用同一个 Agent identity，也可以后续扩展为 runtime instance owner；1.0 先使用 Agent identity。

### 3.2 Dispatch timeout failure

不新增 `blocked` / `timed_out` 状态。TaskBus sweep 使用普通 fail：

```text
status = failed
error_ref = "dispatch_timeout"
completed_at = now
```

如果需要更详细的原因，可以采用稳定前缀：

```text
dispatch_timeout: pending task was not assigned or claimed before timeout
```

具体错误定位优先交给日志和 audit，不在 TaskDomain 增加细分状态。

---

## 4. TaskBus API 设计

### 4.1 Interface

建议扩展 `TaskBus`：

```python
class TaskBus(Protocol):
    def assign(
        self,
        session_id: str,
        task_id: str,
        *,
        agent_id: str,
        assigned_by: str,
        rationale: str | None = None,
    ) -> TaskDomain: ...

    def claim_assigned(
        self,
        session_id: str,
        task_id: str,
        *,
        agent_id: str,
    ) -> TaskDomain | None: ...

    def list_pending_unassigned(self, session_id: str) -> tuple[TaskDomain, ...]: ...

    def list_pending_assigned(self, session_id: str) -> tuple[TaskDomain, ...]: ...

    def sweep_stale_pending_tasks(
        self,
        session_id: str,
        *,
        now: datetime,
        stale_after: timedelta,
        error_ref: str = "dispatch_timeout",
    ) -> tuple[TaskDomain, ...]: ...
```

是否保留 `claim_next(...)`：

- 短期可以保留，避免破坏已有测试和调用点；
- 新 Router/Agent Manager 路径必须使用 `assign` + `claim_assigned`；
- 文档标记 `claim_next` 是 legacy direct-claim helper，后续可移除或仅用于测试。

### 4.2 assign

行为：

```text
input: session_id, task_id, agent_id, assigned_by, rationale?

validate:
  task exists in session
  task.status == pending
  agent_id not empty
  assigned_by not empty

update:
  assigned_agent_id = agent_id
  assigned_by = assigned_by
  assigned_at = now
  assignment_rationale = rationale

return updated TaskDomain
```

不在 TaskBus 内检查 Agent registry。TaskBus 校验状态和字段合法性；Agent 是否存在属于 Router/Agent Manager 的输入事实和日志责任。SQLite 层也不做外键到 Agent registry。

### 4.3 claim_assigned

行为：

```text
input: session_id, task_id, agent_id

return None when:
  another Task is already running in this TaskBus/session
  task does not exist
  task.status != pending
  task.assigned_agent_id is None
  task.assigned_agent_id != agent_id
  parent dependency is not done

update when accepted:
  status = running
  claimed_by = agent_id
  started_at = now
```

是否抛异常：

- 状态非法、找不到 Task 可以沿用现有 `TaskStoreError` 风格；
- “当前不能 claim” 可以返回 `None`，与 `claim_next` 风格一致。

### 4.4 list helpers

`list_pending_unassigned`：

```text
status == pending
assigned_agent_id is None
```

`list_pending_assigned`：

```text
status == pending
assigned_agent_id is not None
```

是否过滤 parent dependency：

- Router 可以看到所有 pending unassigned，但 assign 子任务不一定意味着可 claim；
- Agent Manager claim 时由 TaskBus 判断 parent dependency；
- 为了简单，list helper 不过滤 parent dependency。

### 4.5 sweep_stale_pending_tasks

行为：

```text
for each pending task in session:
  if now - created_or_assignment_reference_time >= stale_after:
      fail with error_ref
```

时间基准建议：

```text
reference_time = assigned_at or created_at
```

理由：

- unassigned pending 从 `created_at` 开始计时；
- assigned pending 从最近 assignment 开始计时，给 Agent Manager 一个启动窗口；
- 不区分 assignment_timeout / claim_timeout，但有公平的时间窗口。

更新：

```text
status = failed
error_ref = error_ref
completed_at = now
result_ref = None
```

不要清空 assignment 字段。失败后的 assignment 字段是诊断事实：它能说明 stale pending 是未分配还是已分配未 claim。

---

## 5. SQLite 设计

### 5.1 Schema

在 published task table 增加：

```sql
assigned_agent_id TEXT NULL,
assigned_by TEXT NULL,
assigned_at TEXT NULL,
assignment_rationale TEXT NULL
```

当前项目如果使用 `CREATE TABLE IF NOT EXISTS`，需要补充轻量 migration：

```text
PRAGMA table_info(tasks)
if column missing:
  ALTER TABLE tasks ADD COLUMN ...
```

不要引入新 migration framework。

### 5.2 assign 持久化

SQLite update 条件：

```sql
UPDATE tasks
SET assigned_agent_id = ?,
    assigned_by = ?,
    assigned_at = ?,
    assignment_rationale = ?
WHERE session_id = ?
  AND task_id = ?
  AND status = 'pending'
```

更新后 reload TaskDomain。若没有行变化，需要区分：

- task 不存在；
- task 非 pending。

可以沿用当前 `TaskStoreError` 文案风格。

### 5.3 claim_assigned 持久化

SQLite update 条件：

```sql
UPDATE tasks
SET status = 'running',
    claimed_by = ?,
    started_at = ?
WHERE session_id = ?
  AND task_id = ?
  AND status = 'pending'
  AND assigned_agent_id = ?
```

另外保持当前单 running 约束和 parent dependency 判断。由于 1.0 单实例，不需要 DB lock / lease / CAS。

### 5.4 sweep 持久化

建议在 Python 层列出候选，逐个 fail，保持逻辑与 in-memory 一致：

```python
for task in list_for_session(session_id):
    if task.status == "pending" and _is_stale(task, now, stale_after):
        _update_failed(task.task_id, error_ref=...)
```

SQLite 可以后续优化成批量 update；1.0 以可读和可测为先。

---

## 6. Router 设计

### 6.1 Agent descriptor

先定义最小 descriptor，不等同 Product 1.1 Agent protocol：

```python
@dataclass(frozen=True)
class AgentDescriptor:
    agent_id: str
    capability: str
    display_name: str | None = None
    enabled: bool = True
```

`agent_id` 指向 Agent identity / template，不是实例。

### 6.2 Descriptor source

```python
class AgentDescriptorSource(Protocol):
    def list_agents(self) -> tuple[AgentDescriptor, ...]: ...
```

第一版可以是 in-memory registry。后续 Product 1.1 Agent protocol 再补版本、schema、工具声明、健康检查等。

### 6.3 Routing policy

可选 policy interface：

```python
class RoutingPolicy(Protocol):
    def choose_agent(
        self,
        task: TaskDomain,
        agents: tuple[AgentDescriptor, ...],
    ) -> AgentDescriptor | None: ...
```

默认 policy：

```text
1. disabled agents are ignored
2. if task.dispatch_constraints.required_agent_id exists:
     choose exactly that agent if enabled
3. else if task.dispatch_constraints.preferred_agent_id exists and enabled:
     choose preferred
4. else choose first enabled agent whose capability matches required capability
5. else return None
```

具体字段名以现有 `TaskDispatchConstraints` 为准；如果现有约束字段不同，技术实现应适配已有模型，不新增重复概念。

### 6.4 Router tick

```python
class TaskRouter:
    def tick(self, session_id: str) -> RoutingTickResult:
        tasks = task_bus.list_pending_unassigned(session_id)
        agents = agent_source.list_agents()
        for task in tasks:
            agent = policy.choose_agent(task, agents)
            if agent is None:
                log no compatible agent
                continue
            task_bus.assign(
                session_id,
                task.task_id,
                agent_id=agent.agent_id,
                assigned_by=self.router_id,
                rationale=...
            )
```

Router 不调用 `fail`。路由长期不成功由 TaskBus sweep 收敛。

`RoutingTickResult` 用于测试和日志：

```python
@dataclass(frozen=True)
class RoutingTickResult:
    assigned_task_ids: tuple[str, ...]
    skipped_task_ids: tuple[str, ...]
    errors: tuple[str, ...]
```

---

## 7. Agent Manager 设计

### 7.1 Agent template registry

最小接口：

```python
class AgentTemplateRegistry(Protocol):
    def get(self, agent_id: str) -> AgentTemplate | None: ...
```

最小 `AgentTemplate`：

```python
@dataclass(frozen=True)
class AgentTemplate:
    agent_id: str
    capability: str
    display_name: str | None = None
```

### 7.2 Agent instance factory

```python
class AgentInstance(Protocol):
    def execute(self, task: TaskDomain) -> AgentExecutionResult: ...

class AgentInstanceFactory(Protocol):
    def create(self, template: AgentTemplate, task: TaskDomain) -> AgentInstance: ...
```

第一版可以同步执行。异步/后台线程属于后续 runtime orchestration。

### 7.3 Agent Manager tick

建议 claim 顺序：

```text
1. read pending assigned Tasks
2. resolve template
3. create instance/preflight
4. claim_assigned
5. execute
6. complete/fail
```

为什么先 create 再 claim：

- 避免 claim 成 running 后才发现 template 不存在或实例无法创建；
- 如果 create 失败，Task 仍是 pending assigned，可以直接 fail 为 startup failure。

如果 create 成功但 claim 返回 None，说明 TaskBus 当前不可执行，例如已有 running Task 或 parent dependency 未完成。此时不执行，等待下一轮 tick。

错误处理：

```text
template missing -> fail(agent_start_failed: template missing)
preflight/create failed -> fail(agent_start_failed: ...)
execute returns success -> complete(result_ref)
execute returns failure / raises -> fail(error_ref)
```

### 7.4 Tick result

```python
@dataclass(frozen=True)
class AgentManagerTickResult:
    claimed_task_ids: tuple[str, ...]
    completed_task_ids: tuple[str, ...]
    failed_task_ids: tuple[str, ...]
    skipped_task_ids: tuple[str, ...]
    errors: tuple[str, ...]
```

---

## 8. Projection / Main Page

### 8.1 TaskCard projection

建议扩展 projection 内部模型或 metadata：

```text
assigned_agent_id
assigned_agent_display_name
assignment_rationale
```

UI 状态映射：

| Domain facts | View label |
|---|---|
| `pending` + no assignment | Waiting for routing |
| `pending` + assignment | Waiting for agent |
| `running` | Running |
| `failed` + `error_ref` starts with `dispatch_timeout` | Dispatch timed out |
| `failed` + other error | Failed |

不暴露 Router internal status。

### 8.2 Main Page actions

Product 1.0 不增加 manual reassign。失败后仍走现有 retry action。

---

## 9. 日志与诊断

结构化日志建议：

| Component | Event | Payload |
|---|---|---|
| `task.router` | `assignment_selected` | task_id, agent_id, rationale |
| `task.router` | `no_compatible_agent` | task_id, capability/constraints |
| `task.agent_manager` | `instance_created` | task_id, agent_id |
| `task.agent_manager` | `agent_start_failed` | task_id, agent_id, reason |
| `task.bus` | `dispatch_timeout` | task_id, assigned_agent_id, reference_time |

这些日志用于弥补首个 routing foundation 不细分 assignment timeout / claim timeout 的选择。

---

## 10. 测试方案

### 10.1 In-memory TaskBus

覆盖：

- assign pending Task；
- reject assign running/done/failed；
- assigned Task 只能由 assigned Agent claim；
- unassigned Task 不能通过 `claim_assigned` claim；
- reassignment allowed while pending；
- sweep unassigned stale pending -> failed dispatch_timeout；
- sweep assigned stale pending -> failed dispatch_timeout；
- non-stale pending not changed。

### 10.2 SQLite TaskBus

覆盖：

- schema migration / table creation includes assignment columns；
- assignment persists after reload；
- claim_assigned validates assignment；
- sweep persists failure；
- existing claim/complete/fail/skip behavior remains compatible。

### 10.3 Router

覆盖：

- default policy assigns by capability；
- required Agent constraint is respected；
- preferred Agent is used when available；
- no compatible Agent leaves Task pending unassigned；
- Router only calls TaskBus commands。

### 10.4 Agent Manager

覆盖：

- assigned pending Task creates instance and claims；
- successful fake instance completes；
- failing fake instance fails；
- missing template fails with agent_start_failed；
- claim returning None prevents execution。

### 10.5 Projection

覆盖：

- waiting for routing；
- waiting for agent；
- dispatch timeout failure；
- no manual reassign action。

---

## 11. Implementation Order

1. Extend `TaskDomain` and serialization.
2. Add in-memory `assign`, `claim_assigned`, list helpers, and sweep.
3. Add SQLite columns and persistent behavior.
4. Add Router descriptors, default policy, and tick.
5. Add Agent Manager interfaces and tick.
6. Update projection / UI contract mapping if needed.
7. Update docs, gap status, and release record.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Existing tests expect direct `claim_next`. | Keep `claim_next` during transition; new execution path uses assignment. |
| Assignment fields duplicate dispatch constraints. | Keep constraints as requirements/preferences; assignment is the final routing fact. |
| Sweep failure reason is too coarse. | Rely on structured logs and audit; add finer failure taxonomy only if debugging pain appears. |
| Agent Manager synchronous execution blocks tick. | Accept for minimal implementation; async runtime can be a later execution orchestration plan. |
| Agent protocol work leaks into routing foundation. | Keep only descriptor/template interfaces needed for Router and Agent Manager. |

---

## 13. Deferred Decisions

- Public Agent protocol and special Agent protocols.
- User-created Agent template workflow.
- Routing Agent LLM prompt / policy shape.
- Multi-session or multi-workspace Agent Manager ownership.
- Multi-router coordination and distributed execution.
- Running timeout and interruption enforcement.
