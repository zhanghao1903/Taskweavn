# TaskBus 架构设计

> Published Task lifecycle authority · v1.6 · 2026-07-10
>
> 2026-07-10 fact calibration: 当前 TaskBus 是 PublishedTask 生命周期权威，
> 不是 EventStream 的物化视图，也不是 Router / Agent Manager。当前实现包括
> `InMemoryTaskBus` 和 `SqliteTaskBus`，API 为 `publish`、`claim_next`、
> `complete`、`fail`、`wait_for_user`、`wait_for_confirmation`、
> `resume_after_user`、`resume_after_confirmation`、`skip`、`retry`、
> `request_interrupt`、`recover_interrupted_running_tasks` 和查询方法。
>
> 当前 Product 1.1 本地闭环通过 fixed-route Default Agent / embedded
> Execution Plane 推进 TaskBus 生命周期。dynamic assignment、assigned-only
> claim、Agent Manager、remote worker lease、stale pending sweep 和
> TaskBus-sourced EventStream replay 都不是当前事实。

---

## 1. 定义

**TaskBus 是已发布执行任务的生命周期权威。**

TaskBus 接收的对象是执行域的 `TaskDomain` / PublishedTask。它负责发布、
领取、完成、失败、等待用户、等待确认、恢复、跳过、重试和协作式中断这些
生命周期事实。

TaskBus 不处理 Authoring Domain 对象：

```text
RawTask
DraftTaskTree
RawTaskAsk
CollaboratorProposal
PlanTaskNode
```

这些对象由 Authoring / Plan / Publisher 边界管理。只有经过发布边界转换后
形成的执行 Task 才进入 TaskBus。

```text
TaskBus = PublishedTask lifecycle state authority
```

当前 TaskBus 也不是这些组件：

| 不是 | 当前边界 |
|------|----------|
| Router | 不选择 Agent，不执行 LLM routing，不读取用户输入意图 |
| Agent Manager | 不创建 Agent 实例，不维护 worker pool，不做 remote lease |
| EventStream | 不从 EventStream 重建 Task 生命周期，也不把每个 TaskBus transition 写入 EventStream |
| Workspace lock manager | 不直接操作文件系统；工作区串行写入由当前 fixed-route 执行路径约束 |

---

## 2. 当前执行拓扑

### 2.1 当前 Product 1.1 路径

普通 PublishedTask 的当前路径是固定路由：

```text
TaskPublisher / PlanPublisher / API Publisher
  -> TaskBus.publish
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor.claim_next
  -> Resident Default Agent task-scoped run
  -> TaskBus.complete / fail / wait_for_user / wait_for_confirmation
```

本地 Execution Plane 已经存在，但它当前是 service facade，不是分布式调度器：

```text
TaskRequest
  -> EmbeddedTaskApiService
  -> ExecutionEnv compatibility check
  -> TaskBus.publish
  -> fixed-route dispatcher or runtime handler
```

普通 task type 会映射为 TaskBus Task。特定 task type 可以由本地
`EmbeddedTaskRuntimeHandler` 处理，例如 WeChat send runtime。此类 runtime
handler 可以使用 TaskBus 的 publish / wait / resume / claim / complete / fail
能力，但它仍然不是 public Agent Manager，也不是 dynamic assignment。

### 2.2 用户输入路径在 TaskBus 之前

用户自然语言输入不会直接进入 TaskBus：

```text
UserMessage
  -> Runtime Input Router / Contract Revision / Authoring
  -> Draft or Plan artifact
  -> publish command
  -> TaskBus
```

Runtime Input Router 处理用户输入和 Contract Revision。它不执行 TaskBus
调度，也不把 pending Task 分配给 Agent。

### 2.3 后续 dynamic routing 路径

后续 dynamic routing 可以增加 Router 和 Agent Manager：

```text
TaskPublisher
  -> TaskBus.publish
  -> Router observes pending Task + Agent descriptors
  -> TaskBus.assign                 # future
  -> Agent Manager / Execution Agent # future
  -> TaskBus.claim_assigned          # future
  -> TaskBus.complete / fail
```

该路径是已接受方向，但当前代码没有 `assign`、`claim_assigned`、
`assignment_index`、assigned-only claim 或 stale pending sweep。

---

## 3. 当前数据模型和存储

### 3.1 TaskBus API 表面

当前 `TaskBus` Protocol 的生命周期方法是：

```python
class TaskBus(Protocol):
    def publish(self, task: TaskDomain) -> TaskDomain: ...

    def claim_next(
        self,
        session_id: str,
        *,
        capability: str,
        agent_id: str,
    ) -> TaskDomain | None: ...

    def complete(
        self,
        session_id: str,
        task_id: str,
        *,
        result_ref: str | None = None,
    ) -> TaskDomain: ...

    def fail(self, session_id: str, task_id: str, *, error_ref: str) -> TaskDomain: ...

    def wait_for_user(self, session_id: str, task_id: str, *, ask_id: str) -> TaskDomain: ...

    def wait_for_confirmation(
        self,
        session_id: str,
        task_id: str,
        *,
        confirmation_id: str,
    ) -> TaskDomain: ...

    def resume_after_user(
        self,
        session_id: str,
        task_id: str,
        *,
        ask_id: str,
    ) -> TaskDomain: ...

    def resume_after_confirmation(
        self,
        session_id: str,
        task_id: str,
        *,
        confirmation_id: str,
    ) -> TaskDomain: ...

    def skip(self, session_id: str, task_id: str, *, reason: str) -> TaskDomain: ...

    def retry(
        self,
        session_id: str,
        task_id: str,
        *,
        instruction: str | None = None,
    ) -> TaskDomain: ...

    def request_interrupt(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
        requested_by: TaskInterruptRequestedBy = "user",
        request_id: str | None = None,
    ) -> TaskDomain: ...

    def recover_interrupted_running_tasks(self, session_id: str) -> list[TaskDomain]: ...

    def get(self, session_id: str, task_id: str) -> TaskDomain | None: ...
    def list_for_session(self, session_id: str) -> list[TaskDomain]: ...
    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]: ...
```

### 3.2 当前存储实现

| 实现 | 当前事实 |
|------|----------|
| `InMemoryTaskBus` | 使用 `_tasks: dict[(session_id, task_id), TaskDomain]` 和 `_children` 映射；主要用于测试和内存场景 |
| `SqliteTaskBus` | 使用 workspace-level SQLite `tasks` 表，`session_id` 隔离行；持久化 `status` 列和完整 `TaskDomain` JSON `payload` |
| `TaskBus` Protocol | 生命周期命令和查询边界；不承诺 EventStream、assignment 或 global scheduler lock |

当前主应用装配为：

```python
task_bus = SqliteTaskBus(layout.workspace_tasks_db)
```

这意味着 TaskBus store 是 workspace-level，Task 行通过 `session_id` 隔离。它
不是 `TaskBus(session_id, event_stream)` 形式的 session-private EventStream
materialized view。

### 3.3 TaskDomain 中与 TaskBus 相关的事实

| 字段 | 当前用途 |
|------|----------|
| `session_id` / `task_id` | TaskBus 查询和唯一性作用域 |
| `parent_id` / `root_id` | parent done 后 child 才能被 claim |
| `status` | `pending` / `running` / `waiting_for_user` / `done` / `failed` |
| `required_capability` | `claim_next` 的能力匹配条件 |
| `dispatch_constraints` | 发布时附带的执行提示或 metadata；不是 assignment |
| `claimed_by` / `started_at` | claim 成功后的执行事实 |
| `waiting_for_ask_id` | ASK blocking point |
| `waiting_for_confirmation_id` | confirmation blocking point |
| `result_ref` / `error_ref` | 终态结果或错误引用 |
| interrupt fields | 协作式停止意图和恢复记录 |

当前没有 `assigned_agent_id`、`assigned_by`、`assigned_at` 或
`assignment_index` 这样的 TaskBus assignment 事实。

---

## 4. 当前状态机

TaskBus 的当前状态集合是：

```text
pending
running
waiting_for_user
done
failed
```

### 4.1 发布和 claim

```text
publish(task)
  requires task.status == pending
  persists TaskDomain

claim_next(session_id, capability, agent_id)
  requires capability and agent_id are non-empty
  selects first pending task in session
  requires task.required_capability == capability
  requires parent is absent or parent.status == done
  updates status -> running
  sets claimed_by and started_at
```

Selection order is deterministic: `created_at`, then `order_index`, then
`task_id`.

### 4.2 Completion and failure

```text
complete
  running -> done
  records result_ref and completed_at

fail
  running/waiting_for_user -> failed
  records error_ref and completed_at
  clears waiting links
```

`complete` does not currently wait for children to finish. Parent-child
readiness is enforced at claim time: a child is claimable only after its parent
is `done`.

### 4.3 ASK and confirmation blocking points

```text
wait_for_user
  running -> waiting_for_user
  records waiting_for_ask_id

wait_for_confirmation
  running -> waiting_for_user
  records waiting_for_confirmation_id

resume_after_user / resume_after_confirmation
  waiting_for_user -> pending
  requires matching active ask_id or confirmation_id
  clears waiting link, claimed_by, started_at, result_ref, error_ref, completed_at
```

重要事实：resume 后回到 `pending`，不是直接回到 `running`。这让 resumed Task
重新通过 `claim_next` 领取，可能由不同 `agent_id` 执行。

### 4.4 Skip, retry, interrupt

```text
skip
  pending/running -> failed
  error_ref = "skipped: ..."

retry
  failed -> pending
  preserves same task_id and queue position
  clears result/error/wait/claim/interrupt lifecycle fields
  may append retry instruction to intent

request_interrupt
  pending -> failed("cancelled: ...")
  running -> remains running, records interrupt_requested intent

recover_interrupted_running_tasks
  running + interrupt_requested -> failed("cancelled: ...; safe_point=sidecar_recovery")
```

TaskBus records stop intent, but it does not kill a process, cancel an LLM
request, undo file writes, or interrupt an external application directly.

---

## 5. 串行执行边界

### 5.1 当前 product path 是串行的

当前 fixed-route dispatcher 对同一个 Session 做 coalesced dispatch：

```text
request_dispatch(session_id)
  -> pending session queue
  -> _running_session_ids prevents duplicate concurrent drain for that session
  -> _drain_session calls FixedRouteTaskExecutor.tick repeatedly
  -> next tick only after prior tick returns completed
```

这给当前本地产品路径提供了单 Session 执行 lane。

### 5.2 TaskBus API 本身不是全局 scheduler lock

当前 TaskBus 没有 `running_task` 字段，也不会因为同一 Session 已经有
`running` Task 就拒绝另一个 eligible pending root Task 的 `claim_next`。

它实际验证的是：

```text
status == pending
required_capability matches
parent is absent or parent.status == done
```

因此，"当前系统一般串行执行" 是 fixed-route dispatcher / executor 路径的
产品约束，不是 TaskBus 存储层的全局互斥语义。后续如果要让 TaskBus 自身承担
多 worker lease、heartbeat 或 max concurrency enforcement，需要单独设计。

### 5.3 为什么仍然偏向串行

在单工作区、本地工具和 LLM 主导执行中，串行路径降低了文件写冲突、调试难度
和恢复复杂度。并发应在具备 workspace isolation、conflict model、lease 和
timeout 之后再引入。

---

## 6. Event、audit 和 projection 边界

当前 TaskBus 生命周期真相在 TaskBus store 中：

```text
InMemoryTaskBus / SqliteTaskBus
  -> current PublishedTask lifecycle facts
```

EventStream 仍然是 runtime action / observation / file evidence / replay 的
重要审计层，但它不是当前 TaskBus 生命周期的 source of truth。

当前相关读侧和审计侧包括：

| 组件 | 当前作用 |
|------|----------|
| `TaskPublishAuditSink` | 记录 publish preview/published/rejected 等 service-level audit facts；明确还不是 EventStream event |
| `TaskExecutionSummaryStore` | 保存执行结果或错误摘要，供 `result_ref` / `error_ref` 读取 |
| `MessageStream` | 向用户投影执行完成、失败、等待等消息 |
| `EventStreamFileChangeStore` | 从 session EventStream 投影工具产生的文件变更事实 |
| `TaskInteractionTimelineService` | 把 draft、message、confirmation、event、file、summary 等读侧事实拼成 timeline |
| `PlanTaskNodeLifecycleSync` | best-effort 将 TaskBus 生命周期同步回 PlanTaskNode execution |
| `ExecutionPlaneStore` | 记录 Task API execution、idempotency、events、evidence、result/error |

因此当前不能写成：

```text
EventStream -> replay -> TaskBus current state
```

更准确的关系是：

```text
TaskBus store owns PublishedTask lifecycle
EventStream / MessageStream / ResultSummary / PublishAudit / ExecutionPlaneStore
  provide audit, evidence, user-facing projection, and integration facts
```

---

## 7. 与其他组件的关系

| 组件 | 当前关系 |
|------|----------|
| Session | TaskBus rows are scoped by `session_id`; main app uses a workspace-level SQLite TaskBus |
| Authoring Domain | Raw/Draft/Ask/Proposal 不进入 TaskBus；publish boundary 负责转换 |
| TaskPublisher / PlanPublisher | 负责把 validated draft/plan nodes 发布为 TaskBus Tasks |
| EmbeddedTaskApiService | 普通 TaskRequest 映射到 TaskBus Task；保留 Execution Plane idempotency and evidence |
| FixedRouteExecutionDispatcher | 当前本地自动执行入口，按 Session coalesce 并串行 drain |
| FixedRouteTaskExecutor | 从 TaskBus claim eligible Task，运行 Default Agent，提交 terminal/waiting lifecycle |
| Resident Default Agent | task-scoped AgentLoop runner，不持有 TaskBus 状态 |
| ASK / confirmation tools | 运行中 Task 调用后进入 `waiting_for_user`，用户答复持久化后 resume 到 `pending` |
| WeChat send runtime | local controlled runtime handler，使用 TaskBus 等待确认和领取目标 Task，但有自己的 boundary store/evidence |
| Router / Routing Agent | 当前不调度 TaskBus；future dynamic routing 才提交 assignment |
| EventStream | runtime evidence source and replay/audit layer，不是当前 TaskBus lifecycle store |
| Workspace | TaskBus 不直接写 Workspace；串行执行路径降低写冲突 |

---

## 8. Dynamic routing foundation

本节是 future design，不是当前实现事实。

后续 dynamic routing 可以引入：

```python
class TaskBus:
    def assign(self, task_id: str, agent_id: str, *, assigned_by: str) -> TaskDomain: ...
    def claim_assigned(self, task_id: str, agent_id: str) -> TaskDomain | None: ...
```

需要同时补齐：

| 能力 | 需要的新事实 |
|------|--------------|
| assignment | `assigned_agent_id`、`assigned_by`、`assigned_at`、assignment rationale/audit |
| assigned-only claim | TaskBus 验证 caller agent 与 assignment 匹配 |
| Agent Manager | worker/agent descriptor registry、health、lifecycle |
| remote worker | lease、heartbeat、timeout、retry/recovery |
| stale pending sweep | 明确定义 timeout、失败原因、audit record 和用户可见行为 |
| concurrency | workspace isolation、max concurrency、conflict handling |

在这些事实落地前，文档应避免把 Router assignment、stale pending sweep 或
`claim_assigned` 写成当前 Product 1.1 行为。

---

## 9. 与 OS 调度器的对比

```text
                    OS scheduler                  Current TaskBus path
---------------------------------------------------------------------------
调度单位             thread / process              PublishedTask
执行粒度             微秒到毫秒                     秒到分钟
调度策略             抢占式 + priority + affinity   fixed-route capability claim
并发度               多核并行                       product path serial per Session
负载均衡             work stealing                  当前不需要
就绪判定             资源 + signal                  parent.done + capability match
状态机复杂度         多状态                         5 个 lifecycle status
失败处理             signal / supervisor            failed terminal state; no auto parent propagation
持久化               kernel/process state            TaskBus store plus read-side audit/evidence stores
```

TaskBus 优化的是本地执行正确性、可恢复性和可投影性，不是吞吐量最大化。

---

## 10. 生命周期

### 10.1 创建

当前主应用创建 workspace-level SQLite TaskBus：

```python
task_bus = SqliteTaskBus(layout.workspace_tasks_db)
```

测试和局部服务可使用 `InMemoryTaskBus`。每个 Task 的 `session_id` 负责隔离
不同 Session 的生命周期事实。

### 10.2 活跃期

活跃期内的主要循环是：

```text
1. publisher/API/runtime publishes pending Tasks
2. fixed-route dispatcher requests execution for a Session
3. FixedRouteTaskExecutor claims next eligible pending Task
4. Resident Default Agent or runtime handler executes
5. TaskBus records done / failed / waiting_for_user
6. ASK/confirmation answer resumes waiting Task to pending
7. retry / skip / interrupt command mutates lifecycle through TaskBus
8. PlanTaskNodeLifecycleSync and UI projections observe committed facts
```

### 10.3 暂停和关闭

当前没有 `bus.pause()` / `bus.resume()` API。

`SqliteTaskBus.close()` 只关闭 SQLite connection。`FixedRouteExecutionDispatcher`
有 `stop()` / `close()` 用于停止 worker thread。当前没有已经实现的
"Session 关闭时拒绝 publish、等待 running、取消所有 pending、flush
EventStream" 的 TaskBus 生命周期流程。

这些能力如果需要，应作为 session/runtime lifecycle 设计单独落地。

---

## 11. 未来发展点

### 11.1 能力匹配增强

当前 TaskBus 使用单值 `required_capability` 匹配。只有当单值表达力被实证不足
时，才应引入多能力或能力表达式：

```python
required_capabilities: tuple[str, ...]
capability_match: Literal["all", "any"]
```

复杂评分、成本估计、历史成功率和 LLM 判断应留在 Router policy 中，不放入
TaskBus lifecycle API。

### 11.2 Dynamic assignment

Router / Routing Agent 可以成为可插拔 policy，TaskBus 只验证 assignment
command 合法性。该能力要和 Agent descriptor、audit、claim validation 一起
设计，不能只添加一个字段。

### 11.3 Remote execution env and lease

ExecutionEnv registry 当前用于本地 compatibility check。要支持真正多执行环境，
还需要：

- remote worker identity
- lease and renew
- heartbeat
- task timeout policy
- idempotent result callback
- evidence upload and authorization

### 11.4 Concurrency

并发不应只通过 `max_concurrent > 1` 开关打开。需要先具备：

- workspace isolation or fork/sub-session model
- conflict detection and merge policy
- per-worker lease and recovery
- UI projection for concurrent running Tasks
- tests for cancellation and partial failure

### 11.5 DAG dependencies

当前只支持单 parent readiness。如果需要多依赖，应引入显式 DAG 模型：

```python
depends_on: tuple[str, ...]
```

同时需要环检测、拓扑排序、就绪事件或可接受的扫描策略。

---

## 12. 设计决策小结

| 决策 | 当前选择 | 不作为当前事实的替代方案 | 理由 |
|------|----------|--------------------------|------|
| 状态权威 | TaskBus store | EventStream replay as TaskBus truth | 当前实现由 InMemory/SQLite TaskBus 持有生命周期 |
| 执行路径 | fixed-route Default Agent / local runtime handler | dynamic Agent assignment | 当前代码没有 assignment API 或 Agent Manager |
| Claim 规则 | capability + parent done + pending | assigned-only claim | 当前 `claim_next` 不读取 assignment |
| 串行性 | fixed-route dispatcher per Session serial drain | TaskBus global `running_task` lock | 当前 TaskBus 无 global running guard |
| ASK/confirmation resume | waiting -> pending | waiting -> running | 当前实现清除 claim/start 并重新 claim |
| 中断 | cooperative intent in TaskBus | TaskBus hard kill | 安全点属于 Agent/runtime/tool |
| Publish audit | dedicated audit sink | EventStream TaskBus events | 当前 publish audit 明确不是 EventStream event |
| Pending timeout | no current stale pending sweep | automatic timeout failure | 当前仅有 interrupted running recovery |
| Parent/child | child claim waits for parent done | complete waits for children | 当前 complete 只要求自身 running |

---

## 13. 总结

TaskBus 的当前职责很窄：保存和验证 PublishedTask 生命周期事实。它把执行状态从
Agent、Authoring、UI、Execution Plane 和 audit/read-side stores 中分离出来，
让这些组件通过明确边界协作。

后续 dynamic routing、remote worker、并发和 DAG 都应建立在这个事实之上：

```text
先保持 TaskBus lifecycle truth 清楚，
再把 routing / worker / concurrency / audit 扩展逐步接上。
```
