# Task 架构设计

> 多 Agent 协作架构的核心抽象 · v1.4 · 2026-05-31
>
> 2026-06-19 review note: 当前实现中 Task 的执行文件读写边界是 selected workspace root；Session 隔离的是 TaskBus、message、ASK、context、event、audit 等运行事实，不是自动 fork 的 per-session file workspace。
>
> 2026-05-31 scope note: Product 1.0 通过 fixed-route Default Agent bridge 关闭执行闭环。Assignment fields、Router / Routing Agent policy、Agent Manager 和 assigned-only claim 是已接受的 Product 1.1+ 架构方向，不是 Product 1.0 实现要求。
>
> 2026-06-19 fact note: Product 1.0 TaskBus 已实现 `waiting_for_user` 作为 durable execution ASK 的 cooperative blocking point。手动 retry 在同一 Task identity 上把 failed Task 退回 `pending`，skip/cancel 仍通过 `failed` + reason 前缀表达。

---

## 1. 定义

**PublishedTask 是工作的最小执行单位，是 Execution Domain 的一等公民。**

TaskWeavn 现在区分 Authoring Domain 和 Execution Domain。用户的自然语言输入不会直接变成可执行 Task，而是先进入 Authoring Domain：

```text
UserMessage
  -> RawTask
  -> FeasibilityReport / RawTaskAsk
  -> DraftTaskTree
  -> Plan / PlanTaskNode projection
  -> user confirmation
  -> PublishedTask
```

本文中的 `Task` 默认指 **PublishedTask / Execution Task**：已经被确认、校验，并允许进入 TaskBus 的执行任务。

任何需要被 Agent 完成的事情最终都被表达为 PublishedTask。Agent 派生的子工作、审计、验证、综合、结果包装等执行工作也都是 PublishedTask。**整个执行系统的运转就是 PublishedTask 的生产、流转、消费。**

```
PublishedTask ≡ 一个明确的意图 + 完成它所需的能力声明 + 完成后的结果
```

---

## 1.1 Task Taxonomy

| Object | Domain | Executable | Enters TaskBus | Purpose |
|---|---|---:|---:|---|
| `RawTask` | Authoring | No | No | Capture user intent before feasibility and planning are complete. |
| `DraftTaskNode` / `DraftTaskTree` | Authoring | No | No | Editable user-facing plan. |
| `PublishedTask` | Execution | Yes | Yes | Unit claimed and executed by Agents. |
| `PipelineTask` | Execution | Yes | Yes | Auto-loaded before/begin Task in current scope; completion-time `task_after` pipeline is deferred to Product 1.1. |
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
TaskBus     ─ 匹配能力为 audit 的 Agent
              ↓
Agent 实例   ─ 执行，产出 result
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

**树而非图**是核心约束。Fan-out / fan-in 由父任务作为同步点：父任务创建多个子任务并行执行，等待全部完成后再综合。

### 2.3 Task 三要素

```python
@dataclass(frozen=True)
class Task:
    # 身份
    id: TaskId
    parent_id: TaskId | None

    # 意图
    intent: str                       # 自然语言描述
    required_capability: str          # 单值，决定调度

    # 状态与产出
    status: TaskStatus                # pending/running/waiting_for_user/done/failed
    assigned_agent_id: AgentId | None # 路由结果
    result: TaskResult | None         # 完成后填充
```

`intent` 给 Agent（人类可读），`required_capability` 给 Router 和执行 Agent（机器可读），`assigned_agent_id` 记录路由结果，`result` 给后续任务（结构化或自由文本）。

Product 1.0 note: fixed-route bridge 使用既有 TaskBus `claim_next` 路径和稳定 Default Agent identity。`assigned_agent_id` 及相关 assignment facts 在本文中保留为已接受的 Product 1.1+ routing model，不是 Product 1.0 required fields。

---

## 3. 核心属性

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `id` | `TaskId` | 全局唯一，UUID 或递增 |
| `parent_id` | `TaskId \| None` | 父任务，None 表示根任务 |
| `intent` | `str` | 任务意图，自然语言 |
| `required_capability` | `str` | 必须有此 capability 的 Agent 才能领取 |
| `status` | `TaskStatus` | `pending` / `running` / `waiting_for_user` / `done` / `failed` |
| `assigned_agent_id` | `AgentId \| None` | 当前被 Router 分配的执行 Agent。未分配时为 None |
| `assigned_by` | `AgentId \| SystemId \| None` | 提交 assignment command 的 Router、Routing Agent policy 或系统策略 |
| `assigned_at` | `datetime \| None` | 最近一次成功分配时间 |
| `assignment_rationale` | `str \| None` | 用户可读或审计可读的分配原因摘要 |
| `result` | `TaskResult \| None` | 任务完成后的产物 |
| `created_at` | `datetime` | 创建时间 |
| `created_by` | `AgentId \| UserId` | 任务创建者 |
| `started_at` | `datetime \| None` | 进入 running 的时间 |
| `completed_at` | `datetime \| None` | 进入终态的时间 |
| `error` | `str \| None` | failed 状态时的失败原因 |

Product 1.0 fixed-route execution 不要求 `assigned_*` 字段。它们是
Product 1.1+ 动态路由和 assignment projection 的 TaskDomain 扩展方向。

**所有属性 frozen，状态变更通过新建 Task 对象完成。** 这与 EventStream 的不可变事件模型一致。

---

## 4. 设计理念

### 4.1 Task 是数据，不是行为

Task 的所有信息都可以序列化为 JSON 持久化。这意味着：
- 任务可以跨进程转发
- 任务可以被 replay 用于调试
- 任务历史就是系统的完整审计日志
- Task ↔ Event 同构，可以共用持久化层

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
                   ├→ waiting_for_user ─→ running
                   │              └────→ failed
                   └→ failed
```

砍掉的中间态：
- ❌ `waiting`（等待依赖）→ pending 时由总线判断 parent 是否完成
- ❌ `assigned`（已分配未开始）→ 与 running 合并
- ❌ `blocked`（创建子任务后等待）→ 父任务继续 running，LLM 调用嵌套
- ❌ `cancelled` → 通过 failed + error reason 表达

`waiting_for_user` 不是通用阻塞/暂停状态。它只表示 running Task 已经创建 durable ASK，并且 TaskBus 暂停执行直到 ASK answer / defer / cancel 命令完成。

### 4.4 任务发布权 = 协作能力

是否能发布任务取决于 Agent 是否挂载了 `CreateTaskTool`：

```
普通 Agent     ─ 工具集 = [read_file, write_file]
                  无法发布任务，是协作的"叶子节点"

协作 Agent     ─ 工具集 = [read_file, write_file, create_task]
                  可以发布子任务，触发其他 Agent 协作

Orchestrator  ─ 工具集 = [create_task, claim_result]
                  专门做编排，自己不直接执行业务工具
```

**协作能力被工具化**，与其他能力同等管理，不需要在 Agent 类型上特殊分类。

### 4.5 Assignment 是 Task 执行事实

Task 路由不应该硬编码在 TaskBus 内。路由策略会涉及 capability、工具权限、成本、用户偏好、历史成功率、当前负载、特殊 Agent 能力，以及未来高级用户自定义策略。这个空间很难一次性做完整，所以 Product 1.1+ 把路由策略交给 **Router**，其中可以包含可插拔的 **Routing Agent policy**：

```text
pending Task
  -> Router / Routing Agent policy decides responsibility
  -> AssignmentCommand
  -> TaskBus validates and records assignment
  -> Agent Manager creates instance and claims task
```

Router 可以很简单，例如完全硬路由；也可以使用 LLM Routing Agent 和补全/fallback 策略。高级用户未来可以接入自定义 Router policy。无论 Routing Agent 多灵活，它都不能直接修改 Task 状态，只能提交 assignment proposal / command。

Product 1.0 不产品化这条 routing path。它使用：

```text
pending PublishedTask
  -> FixedRouteTaskExecutor
  -> Default Agent task-run
  -> TaskBus complete / fail / wait_for_user
```

TaskBus 仍然是状态权威：

- 只允许 `pending` Task 被分配或重新分配；
- `running` / `done` / `failed` Task 不允许重新分配；
- claim 时必须匹配 `assigned_agent_id`；
- 短期路由失败不会引入新状态，Task 保持 `pending`；如果 pending 长期未被推进，TaskBus sweep 会退化为 `failed(dispatch_timeout)`。

重新 assignment 在 Task 未被领取前是允许的。新的 assignment 会覆盖 TaskDomain 上的 assignment 字段，但历史原因和 previous assignment 应通过 EventStream / Audit 记录。

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
               │         │     │ answer/defer/cancel
               │         ↓     ↓
               │      running failed
           ┌───┴──────────────┐
           ↓                  ↓
       ┌──────┐           ┌────────┐
       │ done │           │ failed │
       └──────┘           └────────┘
        终态               终态
```

**关键状态转换规则：**

```
pending → running   Product 1.0：FixedRouteTaskExecutor 通过 claim_next 领取任务
                    Product 1.1+：已分配的 Agent 通过 claim_assigned 领取任务
                    parent 必须是 done（否则任务停留在 pending）
                    Product 1.1+ claimant 必须匹配 assigned_agent_id

running → waiting_for_user
                    Execution Agent 创建 blocking ASK；AskStore 先持久化 ASK，
                    TaskBus 记录 waiting_for_ask_id

waiting_for_user → running
                    ASK answer 成功持久化后，TaskBus resume_after_user(...)
                    清除 waiting_for_ask_id，Execution dispatcher 继续推进

waiting_for_user → failed
                    ASK defer/cancel 或执行策略决定不能继续

running → done      Agent 返回 result，无异常
                    若任务有未完成的子任务，等子任务全部 done 才 done

running → failed    Agent 抛异常 / 子任务 failed / 显式标记失败
                    终态；Product 1.0 手动 retry 可在同一 Task identity
                    上回到 pending，同时保留旧失败证据
```

终态 result/error 证据不可覆盖。Product 1.0 的手动 retry 是窄例外：同一
Task identity 可以从 `failed` 回到 `pending`，但旧 failure、message、audit
和 result/error references 必须保留为历史证据。语义性修改仍通过新建或修订
Task 表达。

---

## 6. 生命周期

### 6.1 创建

执行任务由用户、Collaborator、pipeline、scheduler、API 或 Agent 通过发布边界创建，必须指定 `intent` 和 `required_capability`：

```
用户输入（根任务）：
  UserMessage -> RawTask -> DraftTaskTree -> Plan -> TaskPublisher.publish(...)

Agent 创建（子任务）：
  CreateTaskTool 在工具调用层包装：
  Tool input → Task object → bus.publish(task)
```

PublishedTask 创建即进入 `pending` 状态，进入总线队列。RawTask 和 DraftTaskTree 不进入这里。

### 6.2 等待与领取

任务在总线上等待，直到：
- `parent_id is None` 或 `parent.status == done`
- Product 1.0 fixed-route path：Default Agent bridge 用 matching capability 调用 `claim_next`
- Product 1.1+ dynamic routing path：Router 已写入 `assigned_agent_id`，Agent Manager 为对应 Execution Agent 申请领取该 Task

匹配成功后，`status: pending → running`。

如果短期没有可用 Agent，Task 保持 `pending`。系统可以写入 routing notice 或用户消息，例如 "No available Agent can handle capability X"，但应做节流，避免频繁打扰用户。若 Task 长期未被 assign / claim，TaskBus sweep 会将其退化为 `failed(dispatch_timeout)`。

### 6.3 执行

Agent 实例执行任务：
- 读取 Workspace
- 调用 LLM 推理
- 调用工具（可能包括 CreateTaskTool 派生子任务）
- 写入 Workspace
- 返回 result

执行期间任务保持 `running`。如果创建了子任务，**任务依然 running**，等所有子任务终态后才转入终态。

如果执行 Agent 需要用户补充缺失信息，它创建 durable ASK 并调用
TaskBus `wait_for_user(...)`。该 Task 暂时进入 `waiting_for_user`；ASK
answer 写入 AskStore 后，TaskBus `resume_after_user(...)` 将 Task 回到
`running`，由 dispatcher 继续推进。

### 6.4 完成

```
所有子任务 done + Agent 返回 result（成功）→ status: running → done
任何子任务 failed 且未被父任务捕获 → 父任务 status: running → failed
Agent 自身抛异常 → status: running → failed
```

完成时间 `completed_at` 写入，result（或 error）写入。

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

任务终态后**永久存档**到 EventStream，作为审计和 replay 的依据。Workspace 里的产物保留到 Session 结束。

```
活跃任务  ──  内存 + TaskBus 队列
终态任务  ──  EventStream（append-only）+ 可选缓存
```

---

## 7. 与其他组件的关系

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   User      ──输入──> RawTask / DraftTaskTree       │
│                            │                        │
│                            ↓ publish boundary       │
│   Agent     ──创建──>     PublishedTask             │
│                            │                        │
│                            ↓ publish                │
│                         TaskBus                     │
│                            │                        │
│                            ↓ claim                  │
│                          Agent                      │
│                            │                        │
│                            ↓ read/write             │
│                        Workspace                    │
│                            │                        │
│                            ↓ persist                │
│                       EventStream                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

- **与 Session：** 每个 Task 隶属于一个 Session，使用 Session 的 Workspace
- **与 FixedRouteTaskExecutor：** Product 1.0 中，固定执行桥从 TaskBus 领取 eligible pending Task，并交给 Default Agent task-run 执行
- **与 Router：** Product 1.1+ 中，Router 为 pending Task 提交 assignment command，不直接改状态；Routing Agent 是可插拔 policy
- **与 Agent Manager / Execution Agent：** Product 1.1+ 中，Agent Manager 创建实例并领取被分配的 Task，Execution Agent 执行
- **与 Bus：** Task 是 Bus 的载荷，Bus 是 Task 的传递媒介
- **与 ThoughtStore：** Task 执行过程中的推理可选写入 ThoughtStore，供后续任务检索

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
| 状态数 | 4 个 | 8+ 个 | 中间态可压缩到 running，少状态少 bug |
| 依赖表达 | 单值 parent_id | 多值 depends_on | 可演进为 artifact_refs，渐进引入 |
| 不变性 | frozen | mutable | 与 EventStream 一致，可 replay |
| 协作权 | 工具化（CreateTaskTool） | Agent 类型分类 | 与其他能力同构管理 |
| 失败处理 | 终态 + 重试 = 新任务 | 状态回退 | 任务历史完整，调试友好 |
