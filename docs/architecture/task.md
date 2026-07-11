# Task 架构设计

> 多 Agent 协作架构的核心抽象 · v1.6 · 2026-07-10
>
> 2026-06-19 review note: 当前实现中 Task 的执行文件读写边界是 selected workspace root；Session 隔离的是 TaskBus、message、ASK、context、event、audit 等运行事实，不是自动 fork 的 per-session file workspace。
>
> 2026-05-31 scope note: Product 1.0 通过 fixed-route Default Agent bridge 关闭执行闭环。Assignment fields、Router / Routing Agent policy、Agent Manager 和 assigned-only claim 是已接受的 Product 1.1+ 架构方向，不是 Product 1.0 实现要求。
>
> 2026-06-19 fact note: Product 1.0 TaskBus 已实现 `waiting_for_user` 作为 durable execution ASK 的 cooperative blocking point。手动 retry 在同一 Task identity 上把 failed Task 退回 `pending`，skip/cancel 仍通过 `failed` + reason 前缀表达。
>
> 2026-06-24 Product 1.1 alignment: 当前 Product 1.1 在 Task 之上增加 Runtime Input Router、durable Conversation / Activity、read-only inquiry、workspace inspection refs、token usage projection 和 command-backed guidance/ASK/confirmation；TaskBus 仍是执行状态权威，dynamic execution assignment / Agent Manager 仍未成为当前执行路径。
>
> 2026-07-10 fact calibration: 当前 `TaskDomain` 是 TaskBus 的 published execution fact，由 `SqliteTaskBus` / `InMemoryTaskBus` 持久化和变更。当前字段包括 `task_id`、`session_id`、`root_id`、`dispatch_constraints`、`claimed_by`、ASK/confirmation wait linkage 和 interrupt intent；没有当前可执行的 `assigned_agent_id` / `assigned_by` / `assigned_at` 字段。ASK 或 confirmation resume 后 Task 回到 `pending`，再由 dispatcher 重新 claim。Execution Plane `TaskRequest` 可以映射为普通 TaskBus Task；特殊 task type 可由 runtime handler 接管。

---

## 1. 定义

**PublishedTask 是工作的最小执行单位，是 Execution Domain 的一等公民。**

TaskWeavn 现在区分 Authoring Domain 和 Execution Domain。用户的自然语言输入不会直接变成可执行 Task，而是先进入 Authoring Domain：

```text
UserMessage
  -> RawTask
  -> FeasibilityReport / RawTaskAsk
  -> DraftTaskTree
  -> Plan / PlanTaskNode
  -> user confirmation
  -> PublishedTask
```

本文中的 `Task` 默认指 **PublishedTask / Execution Task**：已经被确认、校验，并允许进入 TaskBus 的执行任务。

任何需要执行闭环完成的事情最终都被表达为 PublishedTask，或被表达为
Execution Plane `TaskRequest` 后映射成 PublishedTask / special runtime
execution。审计、验证、综合、结果包装等执行工作也应通过发布边界进入执行域。
当前没有通用 Agent-side `CreateTaskTool` 直接写 TaskBus。**整个执行系统的运转就是
PublishedTask / TaskExecution 的生产、流转、消费。**

```
PublishedTask ≡ 一个明确的意图 + 完成它所需的能力声明 + 完成后的结果
```

---

## 1.1 Task Taxonomy

| Object | Domain | Executable | Enters TaskBus | Purpose |
|---|---|---:|---:|---|
| `RawTask` | Authoring | No | No | Capture user intent before feasibility and planning are complete. |
| `DraftTaskNode` / `DraftTaskTree` | Authoring | No | No | Editable user-facing plan. |
| `Plan` / `PlanTaskNode` | Contract / Product State | No | No | Durable Product 1.1 contract facts; `PlanTaskNode` may hold a `published_ref` to a TaskBus task. |
| `PublishedTask` | Execution | Yes | Yes | Unit claimed and executed by Agents. |
| `TaskRequest` / `TaskExecution` | Execution Plane | Yes | Indirect | Service-level Task API objects. Ordinary task types map to TaskBus; special task types may use local runtime handlers. |
| `PipelineTaskSpec` / generated Task | Execution Publish | Yes | Yes | Publish-time `task_before` / `task_begin` specs expand into ordinary TaskBus tasks; `task_after` is modeled but remains completion-time orchestration follow-up. |
| `ResultPackagingTask` | Execution | Yes | Yes | Future packaging work for richer result cards; Product 1.0 uses durable result summaries instead. |

This distinction prevents the execution Task state machine from absorbing authoring states such as `awaiting_user`, `ready_to_plan`, or `ready_to_publish`.

---

## 2. 核心抽象

### 2.1 Task 不是函数调用，是工作描述

Task 描述"要做什么"，不描述"怎么做"。**怎么做**由 TaskBus 调度到匹配能力的 Agent 实例后决定。

```
Task        ─ "审计这段代码的安全性"     ← intent
              required_capability="audit"  ← who can do it
              ↓
TaskBus     ─ 当前 claim_next 按 required_capability 领取
              ↓
Default Agent task-run / future Execution Agent
            ─ 执行，产出 result_ref / error_ref
```

这种解耦让 Task 可以被序列化、持久化、转发、replay——它是数据，不是控制流。

### 2.2 Task 是树的节点

任务通过 `parent_id` 形成单根树：

```
        Root Task (用户请求)
          ├── Subtask 1
          │     └── Subtask 1.1
          ├── Subtask 2
          └── Subtask 3
```

**树而非图**是核心约束。当前 TaskBus 只实现 parent-done eligibility：child task
只有在 parent `done` 后才可被 claim。文档中的 fan-out / fan-in、父任务等待子任务
后再综合，是后续 workflow / routing 层目标，不是当前 TaskBus `complete(...)`
语义。

### 2.3 Task 核心字段

```python
class TaskDomain(BaseModel):
    # identity / tree
    task_id: str
    session_id: str
    parent_id: str | None
    root_id: str
    order_index: int

    # contract payload
    intent: str
    summary: str | None
    instructions: str | None
    acceptance_criteria: tuple[str, ...]
    required_capability: str
    dispatch_constraints: TaskDispatchConstraints | None

    # lifecycle
    status: TaskStatus  # pending/running/waiting_for_user/done/failed
    result_ref: str | None
    error_ref: str | None
    claimed_by: str | None
    waiting_for_ask_id: str | None
    waiting_for_confirmation_id: str | None
    interrupt_requested: bool
```

`intent` / `summary` / `instructions` / `acceptance_criteria` 给执行 loop；
`required_capability` 给当前 `claim_next` 路径；`dispatch_constraints` 记录
publish-time hints 和 source metadata；`result_ref` / `error_ref` 指向 durable
result summary、external result、error 或 Execution Plane result/error record。

Current note: fixed-route bridge 使用既有 TaskBus `claim_next` 路径和稳定 Default
Agent identity。`assigned_agent_id` 及相关 assignment facts 在本文中保留为已接受的
later dynamic routing model，不是当前 Product 1.1 execution path 的 fields。

---

## 3. 核心属性

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `task_id` | `str` | TaskBus 内的 Task identity |
| `session_id` | `str` | 所属 Session |
| `parent_id` | `str \| None` | 父任务，None 表示根任务 |
| `root_id` | `str` | 所属根任务；root task 要求 `root_id == task_id` |
| `order_index` | `int` | 同级排序 hint |
| `intent` | `str` | 任务意图，自然语言 |
| `summary` | `str \| None` | 用户/执行可读摘要 |
| `instructions` | `str \| None` | 执行指令 |
| `acceptance_criteria` | `tuple[str, ...]` | 验收标准 |
| `required_capability` | `str` | 当前 `claim_next` 使用的 capability 匹配键 |
| `dispatch_constraints` | `TaskDispatchConstraints \| None` | publish-time hints、source metadata、future assignment hints |
| `status` | `TaskStatus` | `pending` / `running` / `waiting_for_user` / `done` / `failed` |
| `result_ref` | `str \| None` | `done` 后的结果引用 |
| `error_ref` | `str \| None` | `failed` 后的错误引用 |
| `claimed_by` | `str \| None` | 当前 fixed-route executor / Agent identity |
| `waiting_for_ask_id` | `str \| None` | durable ASK linkage |
| `waiting_for_confirmation_id` | `str \| None` | durable confirmation linkage |
| `waiting_for_user_since` | `datetime \| None` | 进入用户等待态的时间 |
| `interrupt_requested` | `bool` | 是否存在 cooperative interrupt intent |
| `interrupt_request_id` | `str \| None` | interrupt request identity |
| `interrupt_reason` | `str \| None` | interrupt reason |
| `interrupt_requested_by` | `"user" \| "system" \| None` | interrupt requester |
| `interrupt_requested_at` | `datetime \| None` | interrupt request time |
| `created_at` | `datetime` | 创建时间 |
| `created_by` | `str` | publish boundary actor |
| `started_at` | `datetime \| None` | 进入 running 的时间 |
| `completed_at` | `datetime \| None` | 进入终态的时间 |

Product 1.0 fixed-route execution 不要求 `assigned_*` 字段。它们是
later dynamic routing 和 assignment projection 的扩展方向，不是当前
`TaskDomain` 字段。

**TaskDomain 是 frozen Pydantic model，状态变更通过新建对象并写回 TaskStore
完成。** 当前 SQLite TaskBus 持久化 `tasks` table + JSON payload；EventStream、
MessageStream、publish audit、result summary、file-change 和 audit stores 是相关读侧/
证据来源，不是当前 Task lifecycle 的唯一 source of truth。

---

## 4. 设计理念

### 4.1 Task 是数据，不是行为

Task 的所有信息都可以序列化为 JSON 持久化。这意味着：
- 任务可以跨进程转发
- 任务可以被 replay 用于调试
- 任务 lifecycle 可以由 TaskBus store 直接查询
- 审计、timeline、file-change、publish 和 result stores 可以围绕 Task identity 聚合证据

### 4.2 单根树形约束

```
为什么不用 DAG？

DAG 解锁的能力（leaf-to-leaf 横向依赖）在 LLM 驱动的任务分解里
出现频率极低。LLM 自顶向下分解任务，自然形成树。

代价：
  树调度器 ≈ 几十行代码
  DAG 调度器 ≈ 几百行 + 拓扑排序 + 环检测 + 就绪事件订阅 + 死锁处理

收益：90% 场景的简洁性远超 10% 场景的表达力损失。
```

剩下 10% 的场景通过 `artifact_refs`（未来扩展）以非破坏性方式补足。

### 4.3 状态机极简化

当前实现保持极简状态机，但为了 durable execution ASK 增加一个阻塞态：

```
pending  ─→  running  ─→  done
                   │
                   ├→ waiting_for_user ─→ pending ─→ running
                   │              └────→ failed
                   └→ failed
```

砍掉的中间态：
- ❌ `waiting`（等待依赖）→ pending 时由总线判断 parent 是否完成
- ❌ `assigned`（已分配未开始）→ 与 running 合并
- ❌ `blocked`（创建子任务后等待）→ 当前 child eligibility 由 parent done 控制；复杂 fan-out / fan-in 留给 workflow 层
- ❌ `cancelled` → 通过 failed + error reason 表达

`waiting_for_user` 不是通用阻塞/暂停状态。它只表示 running Task 已经创建 durable
ASK 或 confirmation，并且 TaskBus 暂停执行直到 answer / confirmation response /
defer / cancel 命令完成。当前 resume 会把 Task 退回 `pending`，再由 dispatcher
重新 claim。

### 4.4 任务发布权 = 命令 / Publisher 边界

当前实现没有通用 `CreateTaskTool`。能发布执行任务的边界包括：

- `DefaultTaskPublisher`：把 normalized task tree 写入 TaskBus；
- `DefaultApiTaskPublisher`：传输无关 API adapter，带 session/capability/agent
  allowlist、rate limit 和 idempotency policy；
- `PlanPublisher` / plan publish flow：把 durable Plan / PlanTaskNode 转成
  PublishedTask；
- scheduler / pipeline publish adapters；
- `EmbeddedTaskApiService`：把 service-level `TaskRequest` 映射为 TaskBus Task
  或交给 special runtime handler；
- Authoring / Contract Revision commands：负责创建、修订、确认和发布产品状态。

后续如果把“创建/修订任务”暴露成 Agent tool，也必须是 command-backed adapter，
不能让 Agent tool 直接改 TaskBus、PlanStore 或 DraftTaskStore。

### 4.5 Assignment 是后续动态路由事实

Task 路由不应该长期硬编码在 TaskBus 内。路由策略会涉及 capability、工具权限、成本、用户偏好、历史成功率、当前负载、特殊 Agent 能力，以及未来高级用户自定义策略。这个空间很难一次性做完整，所以 later dynamic routing 把执行任务分配策略交给 **Router / Routing Agent policy**：

```text
pending Task
  -> Router / Routing Agent policy decides responsibility
  -> AssignmentCommand
  -> TaskBus validates and records assignment
  -> Agent Manager creates instance and claims task
```

Router 可以很简单，例如完全硬路由；也可以使用 LLM Routing Agent 和补全/fallback 策略。高级用户未来可以接入自定义 Router policy。无论 Routing Agent 多灵活，它都不能直接修改 Task 状态，只能提交 assignment proposal / command。

Product 1.0 / 当前 Product 1.1 本地执行闭环不产品化这条 routing path。它使用：

```text
pending PublishedTask
  -> FixedRouteTaskExecutor
  -> Default Agent task-run
  -> TaskBus complete / fail / wait_for_user
```

TaskBus 仍然是状态权威：

- 只允许 `pending` Task 被 `claim_next` 领取；
- `running` / `waiting_for_user` / `done` / `failed` Task 不会被 `claim_next` 领取；
- claim 时必须匹配 `required_capability`，并记录 `claimed_by`；
- 当前没有 stale pending sweep 实现；无 eligible task 时 executor 返回 idle / health
  result，Task 保持 `pending`。

`dispatch_constraints` 目前记录 publish-time hints、source metadata、
`preferred_agent_id` 和 `required_capabilities`，但 current TaskBus claim 不执行
assigned-only validation。真正 assignment command、assigned-only claim 和 stale
pending sweep 属于 `bus.md` 中的 later dynamic routing foundation。

---

## 5. 任务状态机

```
            ┌─────────┐
            │ pending │  任务已发布到总线，等待被领取
            └────┬────┘
                 │ Agent 领取
                 ↓
            ┌─────────┐
            │ running │  正在被某个 Agent 实例执行
            └──┬──┬───┘
               │  │ 创建 blocking ASK
               │  ↓
               │  ┌──────────────────┐
               │  │ waiting_for_user │
               │  └──────┬─────┬─────┘
               │         │     │ defer/cancel/fail
               │         ↓     ↓
               │      pending failed
               │         │
               │         └── claim_next
           ┌───┴──────────────┐
           ↓                  ↓
       ┌──────┐           ┌────────┐
       │ done │           │ failed │
       └──────┘           └────────┘
        终态               终态
```

**关键状态转换规则：**

```
pending → running   当前 Product 1.1：FixedRouteTaskExecutor 通过 claim_next 领取任务
                    later dynamic routing：已分配的 Agent 通过 claim_assigned 领取任务
                    parent 必须是 done（否则任务停留在 pending）
                    当前 claimant 必须匹配 required_capability；
                    later dynamic routing claimant 才需要匹配 assigned_agent_id

running → waiting_for_user
                    Execution Agent 创建 blocking ASK 或 confirmation；
                    AskStore / confirmation store 先持久化用户等待事实，
                    TaskBus 记录 waiting_for_ask_id 或 waiting_for_confirmation_id

waiting_for_user → pending
                    ASK answer 或 confirmation response 成功持久化后，
                    TaskBus resume_after_user(...) / resume_after_confirmation(...)
                    清除 wait linkage、claimed_by、started_at；Execution dispatcher
                    再次 claim 后进入 running

waiting_for_user → failed
                    ASK defer/cancel 或执行策略决定不能继续

running → done      Agent 返回 result，无异常
                    当前 TaskBus complete 只要求当前 Task 是 running；
                    child eligibility 由 parent done 控制

running → failed    Agent 返回 error / 抛异常 / 显式标记失败
                    终态；Product 1.0 手动 retry 可在同一 Task identity
                    上回到 pending
```

终态 result/error 证据应通过 result summary、messages、publish audit、
PlanTaskNode sync、EventStream/file/audit stores 等读侧事实保留。当前手动 retry
是窄例外：同一 Task identity 可以从 `failed` 回到 `pending`，实现会清除当前
`result_ref` / `error_ref` / `claimed_by` / wait linkage / interrupt linkage，并可把
retry instruction append 到 `intent`。语义性修改仍应通过 Plan/TaskNode 修订或新
publish 表达。

---

## 6. 生命周期

### 6.1 创建

执行任务由用户、Collaborator、Plan publish、pipeline、scheduler、API 或
Execution Plane 通过发布边界创建，必须指定 `intent` 和 `required_capability`：

```
用户输入（根任务）：
  UserMessage -> RawTask -> DraftTaskTree -> Plan -> TaskPublisher.publish(...)

服务/API 发布：
  TaskRequest / ApiPublishRequest
    -> validation + idempotency + capability policy
    -> TaskDomain / TaskExecution
    -> TaskBus.publish(task) 或 runtime handler

后续 Agent 派生任务：
  Agent tool-like request
    -> command-backed authoring / publish boundary
    -> TaskBus.publish(task)
```

PublishedTask 创建即进入 `pending` 状态，进入总线队列。RawTask 和 DraftTaskTree 不进入这里。

### 6.2 等待与领取

任务在总线上等待，直到：
- `parent_id is None` 或 `parent.status == done`
- Current fixed-route path：Default Agent bridge 用 matching capability 调用 `claim_next`
- Later dynamic routing path：Router 已写入 `assigned_agent_id`，Agent Manager 为对应 Execution Agent 申请领取该 Task

匹配成功后，`status: pending → running`。

如果短期没有可用 Agent，Task 保持 `pending`。当前 fixed-route executor 返回
`idle` / `health_error` / `claim_not_available` 等 tick result，不会自动把 stale
pending Task sweep 成 failed。routing notice、assignment failure 和 stale pending
sweep 属于 later dynamic routing work。

### 6.3 执行

Agent 实例执行任务：
- 读取 Workspace
- 调用 LLM 推理
- 调用工具（当前 Default Agent 不包含通用 `CreateTaskTool`）
- 写入 Workspace
- 返回 result

执行期间任务保持 `running`。当前 TaskBus 不在 `complete(...)` 时检查子任务终态；
它通过 claim eligibility 保证 child 只有在 parent `done` 后才会被领取。更复杂的
fan-out / fan-in 编排属于后续 authoring / routing / workflow 层设计。

如果执行 Agent 需要用户补充缺失信息，它创建 durable ASK 并调用
TaskBus `wait_for_user(...)`。该 Task 暂时进入 `waiting_for_user`；ASK
answer 写入 AskStore 后，TaskBus `resume_after_user(...)` 将 Task 回到
`pending`，由 dispatcher 重新 claim 后继续推进。confirmation 使用
`wait_for_confirmation(...)` / `resume_after_confirmation(...)`，同样复用
`waiting_for_user` 状态。

### 6.4 完成

```
Agent 返回 result（成功）→ status: running → done
Agent 返回 error 或自身抛异常 → status: running → failed
Execution Plane / result summary store 可把 result_ref / error_ref 解析成用户可读结果
```

完成时间 `completed_at` 写入，`result_ref`（或 `error_ref`）写入当前 Task
payload。

### 6.5 中断与安全点

用户可以请求停止 Task，但中断是否能立即生效不是 TaskBus 能单方面保证的。中断是 **cooperative interruption**：

```text
User requests stop
  -> TaskBus records interrupt intent
  -> Agent/runtime observes interrupt_requested
  -> Agent stops at a safe point
  -> Agent acknowledges and reports failed/cancelled outcome
```

TaskBus 负责记录控制意图和验证最终状态转换。Agent/runtime 负责定义安全点，因为只有执行者知道当前动作是否能安全停止。常见安全点包括：

- before / after each tool call；
- before / after file write；
- after shell command exits；
- after a search / summarization batch；
- while waiting for user confirmation。

1.0 不引入完整 `paused` / `cancelled` PublishedTask 状态。短期规则：

- `pending` Task 收到 cancel request 可以立即终止为 `failed`，error reason 以 `cancelled:` 或 `skipped:` 开头；
- `running` Task 收到 cancel request 先保持 `running`，投影为 "stopping"；
- Agent 在安全点确认停止后，TaskBus 接受 `fail(..., error_ref="cancelled: ...")`；
- hard cancel 属于 runtime/tool 的 best-effort 能力，不由 TaskBus 直接执行。

### 6.6 持久化与归档

当前 Task lifecycle 持久化在 TaskBus store 中。SQLite 实现使用 `tasks` table
保存状态列和完整 `TaskDomain` JSON payload；in-memory 实现用于 focused tests。
结果和错误的用户可读内容通过 `TaskExecutionSummaryStore`、Execution Plane result /
error store、messages、file-change projection、audit records 和 EventStream 共同形成
读侧证据。

```
活跃任务  ──  TaskBus store (`pending` / `running` / `waiting_for_user`)
终态任务  ──  TaskBus store (`done` / `failed`) + result/error refs
读侧证据  ──  result summaries + messages + EventStream + file/audit/publish stores
```

---

## 7. 与其他组件的关系

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   User      ──输入──> RawTask / DraftTaskTree       │
│                            │                        │
│                            ↓ publish boundary       │
│   Plan / API / Scheduler / Execution Plane          │
│                 ───────>   PublishedTask            │
│                            │                        │
│                            ↓ publish                │
│                         TaskBus                     │
│                            │                        │
│                            ↓ claim                  │
│                   Default Agent task-run            │
│                            │                        │
│                            ↓ read/write             │
│                        Workspace                    │
│                            │                        │
│                            ↓ evidence               │
│          result summaries / EventStream / audit     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

- **与 Session：** 每个 Task 隶属于一个 Session，使用 Session 的 Workspace
- **与 FixedRouteTaskExecutor：** 当前 Product 1.1 中，固定执行桥从 TaskBus 领取 eligible pending Task，并交给 Default Agent task-run 执行
- **与 Router：** later dynamic routing 中，Router 为 pending Task 提交 assignment command，不直接改状态；Routing Agent 是可插拔 policy。当前 Runtime Input Router 只处理用户输入和 contract revision，不调度 execution Task。
- **与 Agent Manager / Execution Agent：** later dynamic routing 中，Agent Manager 创建实例并领取被分配的 Task，Execution Agent 执行
- **与 Bus：** Task 是 Bus 的载荷；Bus 是当前 published Task lifecycle 状态权威
- **与 Execution Plane：** `TaskRequest` 可以映射成 TaskBus Task；specific task type 可以由 runtime handler 接管本地流程
- **与 Plan / TaskNode：** PlanTaskNode 可通过 `published_ref` 指向 PublishedTask；`PlanTaskNodeLifecycleSync` best-effort 同步 execution/result/error refs
- **与 ThoughtStore：** ThoughtStore 不是当前 Task lifecycle authority；后续经验复用需显式注入和审计

---

## 8. 未来发展点

### 8.1 v1.x：非破坏性扩展

**`artifact_refs` 字段**

```python
@dataclass(frozen=True)
class Task:
    # ...existing fields
    artifact_refs: list[TaskId] = field(default_factory=list)
```

- 调度器忽略此字段（不影响调度逻辑）
- Agent 在执行时通过此字段读取其他任务的产物
- 表达"我需要任务 X 的输出，但 X 不是我的 parent"
- 解决 90% 的"伪 DAG 需求"，零破坏性

### 8.2 v2.x：状态扩展

**`cancelled` 状态**

当用户主动取消会话或父任务时，未开始的子任务进入 `cancelled` 而非 `failed`，便于区分意图。

**`paused` 状态**

需要长时间等待外部输入（如人工审核）时的中间态。仅在确实出现此场景时引入。

### 8.3 v3.x：DAG 化（仅在数据支持下）

**真正的多依赖**

```python
@dataclass(frozen=True)
class Task:
    parent_id: TaskId | None              # 仍保留，表示创建关系
    depends_on: list[TaskId]              # 新增，表示调度依赖
```

调度器升级为拓扑排序 + 环检测。**只有当 `artifact_refs` 模式无法表达的需求被实证后才引入。**

### 8.4 v3.x：流式任务

**长生命周期任务（producer 风格）**

```python
class StreamingTask(Task):
    yields: AsyncIterator[Artifact]  # 持续产出而非单次返回
```

仅在生产者-消费者用例（如实时监控、流式数据处理）成为核心需求时引入。这会引发对"无状态 Agent"约束的根本挑战，需要慎重评估。

---

## 9. 设计决策小结

| 决策 | 选择 | 替代方案 | 选择理由 |
|------|------|---------|---------|
| 任务关系 | 单根树 | DAG | LLM 分解天然成树，DAG 复杂度收益不成比例 |
| 状态数 | 5 个（含 `waiting_for_user`） | 8+ 个 | durable ASK/confirmation 需要一个阻塞态，其余中间态保持压缩 |
| 依赖表达 | 单值 parent_id | 多值 depends_on | 可演进为 artifact_refs，渐进引入 |
| 不变性 | frozen model + store writeback | mutable in-place object | 状态转换显式，可测试、可持久化 |
| 协作权 | command-backed publisher / API / Execution Plane 边界 | Agent 直接写 TaskBus | Product state mutation 必须可验证、可审计 |
| 失败处理 | 终态 + 窄 retry 回到同一 Task identity | 新任务替代所有重试 | 保留用户可追踪 identity，同时要求历史证据留在读侧 stores |
