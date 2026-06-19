# TaskBus 架构设计

> 多 Agent 协作架构的核心抽象 · v1.4 · 2026-05-31
>
> 2026-05-31 scope note: TaskBus 在所有版本中都是 PublishedTask 生命周期权威。Product 1.0 当前通过 fixed-route Default Agent bridge 使用 `claim_next -> complete / fail` 执行闭环。Router assignment、assigned-only claim、Agent Manager、stale pending sweep 和 assignment projection 是已接受的 Product 1.1+ routing foundation，不是 Product 1.0 阻塞项。
>
> 2026-06-19 fact note: Product 1.0 当前 TaskBus API 还包括 `wait_for_user` / `resume_after_user`（durable ASK 阻塞点）、`retry`、`skip`、`request_interrupt` 和 interrupted running recovery。动态 assignment 仍是 1.1+ 方向。

---

## 1. 定义

**TaskBus 是已发布执行任务的中央传递媒介，是 Session 内 PublishedTask 流转的唯一通道。**

TaskBus 不是一个被动的队列，而是 PublishedTask 的**状态权威 + 协作枢纽**。任何已发布执行任务的发布、领取、完成、失败都必须经过 TaskBus，它是执行任务状态的**唯一真理来源（Single Source of Truth）**。

在 Product 1.1+ 动态路由方向中，TaskBus 还会承担 assignment 执法和 stale pending 收敛职责；Product 1.0 固定路线闭环不依赖这些 routing 能力。

TaskBus 不处理 Authoring Domain 对象：

```text
RawTask
DraftTaskTree
RawTaskAsk
CollaboratorProposal
```

这些对象由 Authoring Domain 管理，经过用户确认和 `TaskPublisher` 转换后才产生 PublishedTask。

```text
TaskBus ≡ PublishedTask 状态权威 + 生命周期转换
```

当 Product 1.1+ 启用动态路由时，TaskBus 会在该状态权威之上增加 assignment validation 和 pending sweep。

---

## 2. 核心抽象

### 2.1 TaskBus 是生产-消费管道

执行任务的发布者、执行桥、Router、Agent Manager 和执行消费者通过 TaskBus 解耦，互不直接通信。Product 1.0 当前路径更简单：

```text
TaskPublisher / Agent Tool
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Resident Default Agent task-run
  -> TaskBus complete / fail / wait_for_user
```

Product 1.1+ 动态路由路径会增加 Router 和 Agent Manager：

```
┌───────────────┐ publish(PublishedTask) ┌─────────┐ assign(task, agent) ┌───────────────┐
│ TaskPublisher │ ─────────────────────→ │ TaskBus │ ←────────────────── │ Router        │
│ or Agent Tool │                         │         │                     │ + policy      │
└───────────────┘                         │         │                     └───────────────┘
                                          │         │ claim_assigned      ┌───────────────┐
                                          │         │ ←────────────────── │ Agent Manager │
                                          │         │                     └───────────────┘
                                          │         │ complete/fail       ┌───────────────┐
                                          │         │ ←────────────────── │ Agent Instance│
                                          └─────────┘                     └───────────────┘
```

发布者不知道哪个 Agent 会执行，Execution Agent 不决定任务交接，Router 不直接改 Task 状态。**路由决策和状态权威分离**是 1.1+ 动态路由的核心。1.0 则通过固定默认 Agent 路线先关闭执行闭环。

用户自然语言输入的路径在 TaskBus 之前：

```text
UserMessage -> RawTask -> DraftTaskTree -> TaskPublisher -> TaskBus
```

### 2.2 TaskBus 串行执行

这是本架构最强的约束之一：**任意时刻，TaskBus 内只有一个任务处于 running 状态**。

```
时间轴：
   t0 ─── claim T1 ─── T1 running ─── T1 done ───┐
                                                 ↓
   t1 ─────────────────────── claim T2 ─── T2 running ─── T2 done

NOT：
   t0 ─── T1 running ───────────────────┐
                                        │ 不允许
   t1 ─── T2 running ───────────────────┘
```

为什么串行？

```
1. 单工作区约束的必然结果：并行写会冲突
2. 调度极简：无锁、无 CAS、无心跳；Product 1.1+ routing pending 健康由确定性 sweep 收敛
3. 可观测性极佳：任意时刻系统状态明确
4. LLM 不是 CPU：LLM 调用本身就是百毫秒~秒级，串行损失有限
```

### 2.3 TaskBus 是 assignment 执法者

本节描述已接受的 Product 1.1+ routing foundation。Product 1.0 fixed-route execution 不需要 assignment fields 或 assigned-only claim。

任务路由由 Router 负责。Router 可以包含 Routing Agent policy，但不要求所有路由流程都由 LLM Agent 完成。TaskBus 不内置完整路由策略，不做 LLM 推理，也不替高级用户决定路由策略。TaskBus 只验证和记录 Router 提交的 assignment：

```
Router:
  inspect pending Tasks + available Agent descriptors
  decide T1 -> agent-a
  submit AssignmentCommand

TaskBus:
  validate T1 is pending
  record assigned_agent_id="agent-a"
  later allow only agent-a to claim T1
```

Router 可以使用硬路由、LLM Routing Agent、用户自定义策略或混合策略。TaskBus 不关心策略细节，只保证 assignment command 合法、可审计、可回放。

### 2.3.1 TaskBus 收敛 stale pending

本节同样属于 Product 1.1+ routing convergence。Product 1.0 fixed-route execution 不需要 stale pending sweep。

TaskBus 不依赖 Router / Agent Manager 的回调来保证 pending Task 永不悬挂。Product 1.1+ routing foundation 采用确定性扫描：

```text
sweep_stale_pending_tasks(now)
  pending too long -> failed(dispatch_timeout)
```

这不是 TaskBus 接管路由策略，而是 TaskBus 维护自身事实账本健康：一个已发布 Task 不能无限停留在 pending。Router / Agent Manager 的具体失败细节由日志和 Audit 记录辅助定位。

### 2.4 TaskBus 是任务状态权威

任务状态变迁**必须**经过 TaskBus 的 API：

Product 1.0 fixed-route path：

```python
bus.publish(task)              # pending
bus.claim_next(...)            # pending -> running
bus.wait_for_user(id, ask_id)  # running -> waiting_for_user
bus.resume_after_user(id, ask) # waiting_for_user -> running
bus.complete(id, result)       # running -> done
bus.fail(id, error)            # running/waiting_for_user -> failed
bus.retry(id)                  # failed -> pending
bus.skip(id, reason)           # pending/running -> failed("skipped: ...")
bus.request_interrupt(id, ...) # pending -> failed or running records intent
```

Product 1.1+ dynamic routing path 增加 assignment validation：

```python
bus.publish(task)        # pending
bus.assign(id, agent)    # pending, records assignment
bus.claim_assigned(id)   # pending → running
bus.complete(id, result) # running → done（如无未完成子任务）
bus.fail(id, error)      # running → failed
```

Agent 不能直接修改 Task 对象的状态。这种集中化让：
- 状态转换的合法性在一处校验
- EventStream 的写入在一处发生
- 父子任务联动的逻辑在一处实现

---

## 3. 核心属性

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `session_id` | `SessionId` | 所属 Session，绑定生命周期 |
| `queue` | `Deque[Task]` | pending 任务等待区 |
| `running_task` | `TaskId \| None` | 当前唯一执行中任务（约束 2 体现） |
| `tasks_index` | `dict[TaskId, Task]` | 全部任务的索引（含终态），便于查询 |
| `children_index` | `dict[TaskId, list[TaskId]]` | 父→子映射，用于 fan-in 判断 |
| `event_stream` | `EventStream` | 状态变迁的事件落盘 |
| `assignment_index` | `dict[TaskId, AgentId]` | 当前 pending/running Task 的 assignment 事实 |

Product 1.0 fixed-route execution 不要求 `assignment_index`。该字段是
Product 1.1+ 动态路由的物化索引。

---

## 4. 设计理念

### 4.1 串行优于并发

```
并发的诱惑：
  - 多任务并行能减少总耗时
  - 多核 CPU 利用率高
  - "现代系统就该并行"

并发的代价：
  - 锁、CAS、内存模型问题
  - 心跳、超时、孤儿任务清理
  - 工作区写冲突 → fork/merge/conflict
  - 调试难度指数级增长
  - LLM 任务里收益微薄（IO 不是瓶颈，LLM 本身才是）

结论：在 LLM 主导的系统里，串行是**正确性优于性能**的合理选择。
```

并发能力作为**可松绑的约束**保留在未来发展点中（见第 7 节）。

### 4.2 策略在 Router / Routing Agent policy，不在 TaskBus

TaskBus 不应该承载完整路由策略。原因：

1. 路由策略很难一次性做完整；
2. 高级用户可能希望自定义路由策略；
3. LLM routing、硬路由、成本路由、权限路由和 fallback 策略会并存；
4. TaskBus 的职责是保证状态一致性，不是做智能调度。

默认 Router 可以很保守，例如按 capability 做硬匹配和简单 fallback。需要 LLM 判断时，Router 内部可以调用 Routing Agent policy。未来可以替换成配置化或用户自定义 Router policy。

### 4.3 无 Work Stealing，无亲和性调度

```
Work stealing  ─ 多个工作线程从队列里抢任务
亲和性调度     ─ 把任务尽量给"上次执行过类似任务"的实例（提高 cache 命中）

两者都依赖：
  - 多个并发 worker
  - 有状态的 worker（亲和性）
  - 复杂调度策略

本架构主动放弃这两个能力：
  - 串行 → 单 worker 就够，没有 stealing 的必要
  - 无状态 Agent → 没有 cache 可亲和
```

Cache 命中的损失通过**prompt 分层缓存**（system prefix 稳定）在 LLM API 层弥补，不依赖调度。

### 4.4 总线是状态机的执法者

任务状态机的所有转换都在 TaskBus 内实现，Agent 只能通过 TaskBus API 间接触发：

```python
class TaskBus:
    def assign(self, task_id: TaskId, agent_id: AgentId, *, assigned_by: AgentId) -> Task:
        task = self.tasks_index[task_id]
        if task.status != pending:
            raise InvalidTransition("only pending tasks can be assigned")
        task = task.with_assignment(agent_id, assigned_by=assigned_by)
        self._emit(TaskAssigned(...))
        return task

    def claim_assigned(self, task_id: TaskId, agent_id: AgentId) -> Task | None:
        if self.running_task is not None:
            return None  # 串行约束的实现
        task = self.tasks_index[task_id]
        if task.assigned_agent_id == agent_id and self._parent_done(task):
            task = task.with_status(running)
            self.running_task = task.id
            self._emit(TaskClaimed(...))
            return task
        return None

    def complete(self, task_id: TaskId, result: TaskResult):
        task = self.tasks_index[task_id]
        if not self._all_children_done(task_id):
            return  # 等待子任务，状态保持 running
        task = task.with_status(done, result=result)
        self.running_task = None
        self._emit(TaskCompleted(...))
        self._wake_waiters(task)
```

**所有状态合法性、子任务联动、事件发射都集中在一处。** 这是 TaskBus 复杂度的来源，但也是协作正确性的保证。

### 4.5 总线即审计日志

每次 publish / assign / claim / complete / fail / wait_for_user / resume /
retry / skip / interrupt request 都应产生一个不可变事实，供 EventStream、
Audit 或 UI projection 追踪：

```
TaskBus 事件序列          ↔        系统行为完整记录
─────────────────────────────────────────────────
TaskPublished(t1, cap=audit)     ↔  发布
TaskAssigned(t1, agent=a1)       ↔  分配责任
TaskClaimed(t1, agent_run=...)   ↔  开始执行
TaskPublished(t2, parent=t1)     ↔  派生子任务
TaskClaimed(t2, agent_run=...)   ↔  子任务开始
TaskCompleted(t2, result=...)    ↔  子任务完成
TaskCompleted(t1, result=...)    ↔  父任务完成
```

任何时刻的系统状态都可以由 EventStream 重建。**TaskBus 在内存里的状态是 EventStream 的物化视图。**

---

## 5. 核心 API

```python
class TaskBus:
    def publish(self, task: TaskDomain) -> TaskDomain: ...

    def claim_next(
        self,
        session_id: str,
        *,
        capability: str,
        agent_id: str,
    ) -> TaskDomain | None: ...

    def complete(self, session_id: str, task_id: str, *, result_ref: str | None = None) -> TaskDomain: ...

    def fail(self, session_id: str, task_id: str, *, error_ref: str) -> TaskDomain: ...

    def wait_for_user(self, session_id: str, task_id: str, *, ask_id: str) -> TaskDomain: ...

    def resume_after_user(self, session_id: str, task_id: str, *, ask_id: str) -> TaskDomain: ...

    def skip(self, session_id: str, task_id: str, *, reason: str) -> TaskDomain: ...

    def retry(self, session_id: str, task_id: str, *, instruction: str | None = None) -> TaskDomain: ...

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

Product 1.0 的 API 表面仍然保持小而集中：TaskBus 负责 PublishedTask
状态转换、ASK blocking point、retry/skip、interrupt intent 和 recovery。
Router / Routing Agent policy 的复杂策略不进入 TaskBus API；动态
assignment API 是 Product 1.1+ 扩展。

---

## 6. Assignment And Claim Algorithm

```python
def assign(self, task_id: TaskId, agent_id: AgentId, *, assigned_by: AgentId) -> Task:
    task = self.tasks_index[task_id]
    if task.status != TaskStatus.pending:
        raise InvalidTransition("only pending tasks can be assigned")

    assigned = task.with_assignment(
        assigned_agent_id=agent_id,
        assigned_by=assigned_by,
        assigned_at=now(),
    )
    self.tasks_index[task_id] = assigned
    self._emit(TaskAssigned(task_id=task_id, agent_id=agent_id, assigned_by=assigned_by))
    return assigned


def claim_assigned(self, task_id: TaskId, agent_id: AgentId) -> Task | None:
    # 串行约束
    if self.running_task is not None:
        return None

    task = self.tasks_index[task_id]
    if task.status != TaskStatus.pending:
        return None
    if task.assigned_agent_id != agent_id:
        return None
    if task.parent_id is not None:
        parent = self.tasks_index[task.parent_id]
        if parent.status != TaskStatus.done:
            return None

    running_task = task.with_status(TaskStatus.running)
    self.running_task = running_task.id
    self.tasks_index[running_task.id] = running_task
    self._emit(TaskClaimed(task_id=task.id, agent_id=agent_id))
    return running_task
```

TaskBus 不扫描 Agent pool，也不选择 Agent。选择发生在 Router / Routing Agent policy；TaskBus 只验证状态、assignment、parent readiness 和串行约束。

---

## 6.1 Cooperative Interruption

TaskBus 接受停止请求，但不承诺立即停止 running Task。原因是安全点属于 Agent/runtime 能力：

```text
User requests stop
  -> TaskBus records interrupt_requested
  -> Execution Agent observes it
  -> Agent stops at a safe point
  -> Agent reports fail/cancelled outcome
```

规则：

- `pending` Task 可以立即终止为 `failed`，error reason 使用 `cancelled:` 或 `skipped:` 前缀；
- `running` Task 记录 interruption intent，UI 可投影为 "stopping"；
- Execution Agent 在安全点调用 `fail(task_id, "cancelled: ...")` 或完成当前不可中断动作后再收尾；
- hard cancellation 属于 runtime/tool best-effort，不由 TaskBus 直接 kill 进程或撤销外部动作。

这保证用户可以表达控制意图，同时不让 TaskBus 假装知道文件写入、shell 命令、外部 API 或 LLM 请求何时可以安全中断。

---

## 7. 与其他组件的关系

Product 1.0 relationship:

```text
TaskPublisher / Agent Tool
  -> TaskBus
  -> FixedRouteTaskExecutor
  -> Resident Default Agent
  -> TaskBus complete / fail / wait_for_user
```

Product 1.1+ dynamic routing relationship:

```
                ┌────────────────────────────┐
                │                            │
   User ──┐     │  ┌──────────┐              │
          ├───→ │  │ TaskBus  │ ←─── publish │
   Agent ─┘     │  │          │              │
                │  │  - queue │ ←─ assign    │ ── Router / policy
                │  │  - index │ ←─ claim/    │
                │  │  - state │     complete │ ── Execution Agent
                │  └──────────┘              │
                │       │                    │
                │       │ emit               │
                │       ↓                    │
                │  EventStream               │
                │       │                    │
                │       │ snapshot           │
                │       ↓                    │
                │   持久化存储                │
                └────────────────────────────┘
```

- **与 Session：** 每个 Session 独占一个 TaskBus 实例，绑定生命周期
- **与 Task：** TaskBus 是 PublishedTask 的容器和状态权威
- **与 Authoring Domain：** TaskBus 不接收 RawTask / DraftTaskTree；`TaskPublisher` 是两域边界
- **与 FixedRouteTaskExecutor：** Product 1.0 中固定执行桥通过 `claim_next` 推进 eligible pending Task
- **与 Router：** Product 1.1+ 中 Router 观察 pending tasks 和 Agent registry，提交 assignment command；Routing Agent 是 Router 内部可插拔 policy
- **与 Agent Manager / Execution Agent：** Product 1.1+ 中 Agent Manager 创建实例并通过 `claim_assigned` 领取被分配给自己的任务；Execution Agent 通过 `complete/fail` 报告结果
- **与 EventStream：** 每次状态变迁都向 EventStream 发射事件，EventStream 是真相，TaskBus 是物化视图
- **与 Workspace：** TaskBus 不直接操作 Workspace，但通过"串行执行"保证 Workspace 访问无冲突

---

## 8. 与 OS 调度器的对比

```
                    OS 调度器                    TaskBus
─────────────────────────────────────────────────────────────────
调度单位             线程 / 进程                  Task
执行粒度             微秒~毫秒                    百毫秒~分钟
调度策略             抢占式 + 优先级 + 亲和性     Router policy + assignment validation
并发度               多核并行                    严格串行
负载均衡             work stealing               不需要
就绪判定             资源 + 信号                 parent.done == True
状态机复杂度         多种（运行/就绪/阻塞/...）   5 种（含 ASK blocking point）
失败处理             信号 + supervisor           Task failed 不传播
```

OS 调度器是**复杂换吞吐量**，TaskBus 是**简洁换正确性**。两者优化目标完全不同——OS 任务粒度小，调度复杂度被任务数量摊薄；LLM 任务粒度大，调度复杂度的 ROI 极低。

---

## 9. 生命周期

### 9.1 创建

TaskBus 与 Session 同生：

```
Session 创建时：
  bus = TaskBus(session_id=session.id, event_stream=session.event_stream)
  session.bus = bus
```

无独立的"启动"步骤——创建即可用。

### 9.2 活跃期

TaskBus 在 Session active 期间持续接受任务：

```
持续循环：
  Loop 1: 用户/Agent publish 任务
  Loop 2: Product 1.0 fixed-route executor claim_next
  Loop 3: Agent 完成、失败或创建 ASK → bus.complete / bus.fail / bus.wait_for_user
  Loop 4: ASK answer/defer/cancel → bus.resume_after_user 或 bus.fail
  Loop 5: retry/skip/interrupt command 通过 TaskBus 改变生命周期事实

Product 1.1+ 动态路由会在 Loop 2 前增加 Router assign pending tasks 和
Agent Manager claim_assigned。
```

期间 `running_task` 至多有一个，`queue` 长度可变。

### 9.3 暂停

未来的"暂停"语义（v2.x）：

```
bus.pause()
  - 已 running 的任务执行完毕后正常进入终态
  - 新的 claim_assigned 返回 None
  - publish 仍然接受（任务进入 pending 但不被领取）

bus.resume()
  - 恢复 claim_assigned 的正常行为
```

v1.x 不实现，因为没有典型用例。

### 9.4 关闭

Session 关闭时：

```
1. 拒绝新的 publish
2. 等待 running_task 进入终态
3. 把仍在 pending 的任务标记为 cancelled（或 abandoned）
4. flush EventStream
5. 释放索引内存
```

关闭后 TaskBus 不可用，与 Session 一同销毁。

---

## 10. 未来发展点

### 10.1 v1.x：能力匹配增强

**多能力匹配**

```python
@dataclass
class Task:
    required_capabilities: list[str]  # 改为多值
    capability_match: Literal["all", "any"] = "any"
```

让任务可以表达"需要 audit 或 review 任一能力的 Agent"。**当且仅当**单值匹配的表达力被实证不足时引入。

**能力评分（放到 Router / Routing Agent policy）**

TaskBus 不引入能力评分排序。如果需要评分、成本估计、历史成功率或 LLM 判断，应由 Router / Routing Agent policy 产生 assignment rationale，并通过 assignment command 落入 TaskBus。

### 10.2 v2.x：并发执行

**有限并发**

```python
class TaskBus:
    max_concurrent: int = 1  # 默认 1，可配置
```

放宽串行约束，允许 N 个任务并发。**前提是 Workspace 隔离机制（sub-session 或 fork）已经就绪。**

```
v1：串行 + 单工作区
v2：可配置并发 + sub-session 工作区
```

引入并发后需要新增：
- 锁机制（或乐观并发）
- 心跳与超时
- Worker 健康检查

这是真正的复杂度跃迁，必须有数据驱动（吞吐量瓶颈被实证）才做。

### 10.3 v2.x：任务暂停与恢复

**断点机制**

```python
bus.pause()
bus.resume()
```

支持长时间运行的会话被暂停（如用户离开），恢复时从同一状态继续。这要求 TaskBus 状态完整可序列化——目前已经满足，只需暴露 API。

### 10.4 v2.x：跨 Session 任务引用

**只读引用**

```python
new_session.bus.import_artifact(
    task_id=old_task_id,
    from_session=old_session_id,
)
# 在 new_session 内可以创建依赖此 artifact 的新任务
# 不复制整个任务树，仅引用最终 result
```

让历史会话的产物在新会话中可被引用，避免在一个 Session 内堆积所有内容。

### 10.5 v3.x：DAG 化

**真正的多依赖调度**

如果 `artifact_refs` 模式被实证不够，需要真正的 DAG：

```python
@dataclass
class Task:
    parent_id: TaskId | None
    depends_on: list[TaskId]  # 新增

class TaskBus:
    def claim_assigned(self, task_id: TaskId, agent_id: AgentId) -> Task | None:
        # 升级为：所有 depends_on 都 done 才 ready
        ...
```

需要的新基础设施：
- 拓扑排序
- 环检测
- 就绪事件订阅（避免 O(N²) 扫描）
- 死锁检测

**只有在 v1.x 的 `artifact_refs` + 单 parent 模式被实证无法表达需求时才引入。**

### 10.6 v3.x：流式任务

**长生命周期任务**

```python
class StreamingTaskBus(TaskBus):
    def publish_stream(self, task: StreamingTask) -> AsyncIterator[Artifact]:
        ...
```

支持生产者-消费者管道（实时监控、流式数据处理）。这会**根本性挑战"无状态 Agent"**约束，引入需要重新评估整个架构基础。

---

## 11. 设计决策小结

| 决策 | 选择 | 替代方案 | 选择理由 |
|------|------|---------|---------|
| 路由策略 | Router / Routing Agent policy | TaskBus 内置 matcher | 策略可插拔，支持硬路由、LLM 路由和高级用户自定义 |
| 并发度 | 严格串行 | 多 worker 并发 | 单工作区 + 调度极简 |
| Assignment 权威 | TaskBus 验证并记录 | Router / Routing Agent 直接改状态 | 保持状态一致性和可审计性 |
| 状态权威 | 集中在 TaskBus | 分散在各 Agent | 状态合法性、事件发射在一处实现 |
| 中断 | Cooperative interruption | TaskBus 强杀运行中动作 | 安全点属于 Agent/runtime 能力 |
| 失败传播 | 不自动传播 | 父任务自动失败 | 父任务可决定重试或捕获，灵活性更高 |
| 持久化 | 通过 EventStream | TaskBus 自管 | TaskBus 是物化视图，EventStream 是真相 |
| Work stealing | 不引入 | 多 worker 抢任务 | 串行架构下无意义 |
| 心跳与超时 | 不引入 per-task timer；pending 用 sweep 收敛 | 检测孤儿任务 | 串行 + 同步执行下避免复杂 timer，pending 不无限悬挂 |

---

## 12. 总结

**TaskBus 是执行架构的"心脏"**——所有已发布执行任务的流转、状态变迁、协作触发都汇聚于此。它的设计哲学是：

```
  做最少的事 ─ assignment 验证 + 状态机
  做对所有事 ─ 串行 + 集中 + 事件溯源
  为未来留路 ─ Router policy 可替换，单 worker 可扩为多 worker，单值依赖可扩为 DAG
```

简洁的 TaskBus 是整个执行架构能保持简洁的支点。Authoring Domain 承担用户意图、澄清、草案和可行性判断，正是为了让这颗心脏不要背上不属于它的生命周期。
