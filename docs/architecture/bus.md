# TaskBus 架构设计

> 多 Agent 协作架构的核心抽象 · v1.1 · 2026-05-14

---

## 1. 定义

**TaskBus 是已发布执行任务的中央传递媒介，是 Session 内 PublishedTask 流转的唯一通道。**

TaskBus 不是一个被动的队列，而是**调度器 + 状态权威 + 协作枢纽**的三位一体。任何已发布执行任务的发布、领取、完成、失败都必须经过 TaskBus，它是执行任务状态的**唯一真理来源（Single Source of Truth）**。

TaskBus 不处理 Authoring Domain 对象：

```text
RawTask
DraftTaskTree
RawTaskAsk
CollaboratorProposal
```

这些对象由 Authoring Domain 管理，经过用户确认和 `TaskPublisher` 转换后才产生 PublishedTask。

```
TaskBus ≡ FIFO 队列 + 能力匹配 + 串行执行 + 状态权威
```

---

## 2. 核心抽象

### 2.1 TaskBus 是生产-消费管道

执行任务的发布者和消费者（Agent 实例）通过 TaskBus 解耦，互不直接通信：

```
┌───────────────┐ publish(PublishedTask) ┌─────────┐ claim_next(cap) ┌──────────┐
│ TaskPublisher │ ─────────────────────→ │ TaskBus │ ←────────────── │ Consumer │
│ or Agent Tool │                         │  FIFO   │ complete/fail   │  Agent   │
└───────────────┘ ←────── result ──────── │  Queue  │ ──────────────→ │          │
                                          └─────────┘                 └──────────┘
```

发布者不知道哪个 Agent 会执行，消费者不知道任务从哪里来——**调度的中介性是架构松耦合的核心**。

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
2. 调度极简：无锁、无 CAS、无心跳、无超时
3. 可观测性极佳：任意时刻系统状态明确
4. LLM 不是 CPU：LLM 调用本身就是百毫秒~秒级，串行损失有限
```

### 2.3 TaskBus 是能力匹配器

任务声明 `required_capability`，Agent 实例声明能力，TaskBus 在两者之间撮合：

```
Task                 Agent Instance Pool
─────                ────────────────────
T1: cap="audit"     ┌─ instance A: cap="audit"
T2: cap="fix"       ├─ instance B: cap="fix"
T3: cap="audit"     └─ instance C: cap="review"

TaskBus.claim_next(capability="audit")
   → 返回 T1（FIFO 中第一个能力匹配的任务）
```

匹配是**单值字符串匹配**，不是复杂的能力推理或评分排序——简单到一行 hash 查询。

### 2.4 TaskBus 是任务状态权威

任务状态变迁**必须**经过 TaskBus 的 API：

```python
bus.publish(task)        # pending
bus.claim_next(cap)      # pending → running
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
| `queue` | `Deque[Task]` | FIFO 队列，pending 任务等待区 |
| `running_task` | `TaskId \| None` | 当前唯一执行中任务（约束 2 体现） |
| `tasks_index` | `dict[TaskId, Task]` | 全部任务的索引（含终态），便于查询 |
| `children_index` | `dict[TaskId, list[TaskId]]` | 父→子映射，用于 fan-in 判断 |
| `event_stream` | `EventStream` | 状态变迁的事件落盘 |
| `capability_filter` | `Callable` | 能力匹配函数（默认字符串相等） |

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

### 4.2 FIFO 优于优先级

```
不引入优先级队列的理由：

1. LLM 任务粒度大，FIFO 公平性已经足够
2. 优先级带来 starvation 风险（低优先任务可能永远不被执行）
3. 用户感知层有更好的优先级表达：人主动取消低价值任务
4. FIFO 实现 = 一行 deque.append + popleft
```

如果未来需要"加急"，更好的方案是用户层 UI（取消旧任务、提升任务到队首），而不是引擎层加优先级。

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
    def claim_next(self, capability: str) -> Task | None:
        if self.running_task is not None:
            return None  # 串行约束的实现
        task = self._find_next_matching(capability)
        if task and self._parent_done(task):
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

每次 publish / claim / complete / fail 都产生一个不可变事件写入 EventStream：

```
TaskBus 事件序列          ↔        系统行为完整记录
─────────────────────────────────────────────────
TaskPublished(t1, cap=audit)     ↔  发布
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
    # 发布任务
    def publish(self, task: Task) -> TaskId:
        """任务进入 pending 队列。"""

    # 领取任务（Agent 实例调用）
    def claim_next(self, capability: str) -> Task | None:
        """
        返回下一个匹配能力且 parent 已完成的任务，
        若当前已有 running 任务则返回 None。
        """

    # 完成任务
    def complete(self, task_id: TaskId, result: TaskResult) -> None:
        """
        标记任务完成。若任务有未完成子任务，
        实际状态保持 running，等待子任务结束后再转入 done。
        """

    # 失败任务
    def fail(self, task_id: TaskId, error: str) -> None:
        """标记任务失败。终态，不可恢复。"""

    # 查询
    def get(self, task_id: TaskId) -> Task: ...
    def children_of(self, task_id: TaskId) -> list[Task]: ...
    def pending_tasks(self) -> list[Task]: ...

    # 等待（用于父任务等待子任务）
    async def wait_for_children(self, task_id: TaskId) -> list[Task]:
        """阻塞至所有子任务进入终态。"""
```

API 表面**极小**——这是简洁性的直接体现。

---

## 6. 调度算法

```python
def claim_next(self, capability: str) -> Task | None:
    # 串行约束
    if self.running_task is not None:
        return None

    # FIFO 扫描，找第一个匹配的 ready 任务
    for task in self.queue:
        if task.required_capability != capability:
            continue
        if task.parent_id is not None:
            parent = self.tasks_index[task.parent_id]
            if parent.status != TaskStatus.done:
                continue  # parent 未完成，跳过
        # 匹配成功
        self.queue.remove(task)
        running_task = task.with_status(TaskStatus.running)
        self.running_task = running_task.id
        self.tasks_index[running_task.id] = running_task
        self._emit(TaskClaimed(task_id=task.id, ...))
        return running_task

    return None
```

**就这么多。** 几十行代码就能覆盖整个调度核心。

---

## 7. 与其他组件的关系

```
                ┌────────────────────────────┐
                │                            │
   User ──┐     │  ┌──────────┐              │
          ├───→ │  │ TaskBus  │ ←─── publish │
   Agent ─┘     │  │          │              │
                │  │  - queue │              │
                │  │  - index │ ←─ claim/    │
                │  │  - state │     complete │ ── Agent 实例
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
- **与 Agent：** Agent 实例通过 `claim_next` 拉取任务，通过 `complete/fail` 报告结果
- **与 EventStream：** 每次状态变迁都向 EventStream 发射事件，EventStream 是真相，TaskBus 是物化视图
- **与 Workspace：** TaskBus 不直接操作 Workspace，但通过"串行执行"保证 Workspace 访问无冲突

---

## 8. 与 OS 调度器的对比

```
                    OS 调度器                    TaskBus
─────────────────────────────────────────────────────────────────
调度单位             线程 / 进程                  Task
执行粒度             微秒~毫秒                    百毫秒~分钟
调度策略             抢占式 + 优先级 + 亲和性     FIFO + 能力匹配
并发度               多核并行                    严格串行
负载均衡             work stealing               不需要
就绪判定             资源 + 信号                 parent.done == True
状态机复杂度         多种（运行/就绪/阻塞/...）   4 种
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
  Loop 2: Agent 实例 claim_next
  Loop 3: Agent 完成或失败 → bus.complete / bus.fail
  Loop 4: 父任务 wait_for_children 解除阻塞
```

期间 `running_task` 至多有一个，`queue` 长度可变。

### 9.3 暂停

未来的"暂停"语义（v2.x）：

```
bus.pause()
  - 已 running 的任务执行完毕后正常进入终态
  - 新的 claim_next 返回 None
  - publish 仍然接受（任务进入 pending 但不被领取）

bus.resume()
  - 恢复 claim_next 的正常行为
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

**能力评分（拒绝引入）**

不引入能力评分排序。"评分"会引入隐式优先级，违背 FIFO 公平性。如果用户需要选择特定 Agent，应该通过约束 profile 在用户层显式选择，不在调度层。

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
    def claim_next(self, capability: str) -> Task | None:
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
| 调度策略 | FIFO | 优先级 / 亲和性 | LLM 粒度大，FIFO 公平性足够 |
| 并发度 | 严格串行 | 多 worker 并发 | 单工作区 + 调度极简 |
| 能力匹配 | 单值字符串 | 多值 / 评分 | 简单到一行查询，足够覆盖典型场景 |
| 状态权威 | 集中在 TaskBus | 分散在各 Agent | 状态合法性、事件发射在一处实现 |
| 失败传播 | 不自动传播 | 父任务自动失败 | 父任务可决定重试或捕获，灵活性更高 |
| 持久化 | 通过 EventStream | TaskBus 自管 | TaskBus 是物化视图，EventStream 是真相 |
| Work stealing | 不引入 | 多 worker 抢任务 | 串行架构下无意义 |
| 心跳与超时 | 不引入 | 检测孤儿任务 | 串行 + 同步执行，无孤儿任务可能 |

---

## 12. 总结

**TaskBus 是执行架构的"心脏"**——所有已发布执行任务的流转、状态变迁、协作触发都汇聚于此。它的设计哲学是：

```
  做最少的事 ─ FIFO + 能力匹配 + 状态机
  做对所有事 ─ 串行 + 集中 + 事件溯源
  为未来留路 ─ 单 worker 可扩为多 worker，单值依赖可扩为 DAG
```

简洁的 TaskBus 是整个执行架构能保持简洁的支点。Authoring Domain 承担用户意图、澄清、草案和可行性判断，正是为了让这颗心脏不要背上不属于它的生命周期。
