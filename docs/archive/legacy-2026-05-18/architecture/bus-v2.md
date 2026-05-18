# TaskBus v2 架构设计

> 多 Agent 协作架构 · TaskBus 增强版本 · v2.0 · 2026-05-09

---

## 0. 这是什么

本文是 [bus.md](bus.md) 的**演进版本**，不替代它。v1 的 TaskBus 用**最少的复杂度**换来了协作正确性，是足够好的起点；v2 在 v1 的骨架上**增加智能与并发**两个维度，让 TaskBus 从"传送带"升级为"智能调度中枢"。

**v2 的三个核心升级：**

1. **LLM 驱动的调度器** —— 把"FIFO + 字符串能力匹配"升级为"LLM 决策的智能调度"
2. **并发任务执行** —— 放开严格串行约束，让多个任务并发运行 LLM
3. **基于读写域的冲突解决** —— 取代单工作区串行约束，按任务声明的读写域并发

> 本文不修改 v1 的五个核心文档。v1 是简洁的基础引擎，v2 是激活更高维能力的扩展层。
> 实际系统可以选择仅落地 v1，或在 v1 跑通后渐进引入 v2 的某些能力。

---

## 1. 定义升级

```
v1：TaskBus ≡ FIFO 队列 + 能力匹配 + 串行执行 + 状态权威
v2：TaskBus ≡ LLM 调度器 + 并发执行池 + 读写域冲突解决 + 状态权威
```

v2 保留 v1 的三个核心责任（状态权威、事件溯源、协作枢纽），但把**调度策略**和**执行模型**从硬编码升级为可推理、可并发。

```
       ┌─────────────────────────────────────────┐
       │            TaskBus v2                   │
       │                                         │
       │   ┌──────────────────┐                  │
       │   │ Scheduler (LLM)  │ ← 决策下一个动作  │
       │   └────────┬─────────┘                  │
       │            │                            │
       │   ┌────────┴─────────┐                  │
       │   │ Concurrency Pool │ ← N 个任务并发   │
       │   │   T_a   T_b  T_c │   运行 LLM       │
       │   └────────┬─────────┘                  │
       │            │                            │
       │   ┌────────┴─────────┐                  │
       │   │ Conflict Guard   │ ← 读写域校验     │
       │   └──────────────────┘                  │
       │                                         │
       └─────────────────────────────────────────┘
```

---

## 2. 与 v1 的差异速览

| 维度 | v1 | v2 |
|-----|----|----|
| 调度策略 | FIFO + 字符串能力匹配 | LLM 推理 + 多维度评估 |
| 执行模型 | 严格串行（`max_concurrent=1`） | 受限并发（按读写域兼容性） |
| 工作区访问 | 默认 Workspace 全量串行 | 任务声明读写域，互不冲突即可并发 |
| 任务排序 | 创建时间 FIFO | 调度器综合 priority / dependency / cost |
| 失败处理 | 终态 + 不传播 | 终态 + 调度器可主动重试或重派 |
| Agent 选择 | 任意匹配 capability 的实例 | 调度器可选择"最合适"的实例 |
| 复杂度 | 几十行代码 | 几百行 + 调度器 prompt |
| 适用场景 | 引擎冷启动、确定性优先 | 大规模任务、性能敏感、跨域协作 |

**v1 → v2 不是替换，是路径。** 可以在 v1 跑稳后**逐项**引入 v2 能力，不是一次性升级。

---

## 3. LLM 驱动的调度器

### 3.1 为什么用 LLM 做调度

经典调度器（FIFO / 优先级 / 公平）的核心局限：

```
经典调度器只看：
  - 任务到达顺序
  - 静态优先级
  - 资源可用性

经典调度器看不到：
  - 任务的语义关联（"这两个 audit 任务覆盖同一模块，可以合并"）
  - 任务的紧急程度（"用户下一句话很可能问 X，应优先做 X"）
  - Agent 实例的"擅长"程度（"这个实例刚处理过类似上下文"）
  - 全局优化（"先做 T3 能让 T1/T2 的耗时缩短"）
```

LLM 调度器把"调度"从**机械分派**升级为**带语义理解的决策**：

```
经典调度器的输入：(queue, capability_filter) → next_task
LLM 调度器的输入： (queue, agent_pool, history, workspace_state, user_intent)
                  → SchedulingDecision
```

### 3.2 LLM 调度器的输入

```python
@dataclass(frozen=True)
class SchedulingContext:
    pending_tasks: list[Task]                     # 排队中的任务
    running_tasks: list[Task]                     # 正在执行的任务
    available_agents: list[AgentInstance]         # 可用 Agent 实例
    workspace_snapshot: WorkspaceFingerprint      # 工作区状态摘要
    recent_events: list[Event]                    # 最近 N 个事件
    user_active_intent: str | None                # 用户当前会话主线
    constraint_profile: ConstraintProfile         # 用户配置的策略偏好
```

调度器拿到的不是单纯的"下一个任务"问题，而是**全局视角**。

### 3.3 LLM 调度器的输出

```python
@dataclass(frozen=True)
class SchedulingDecision:
    # 主决策
    actions: list[ScheduleAction]
    # 解释（用于审计、用户可见性）
    rationale: str
    # 期望下次重新评估的时机
    revisit_at: datetime | TaskId | None

class ScheduleAction:
    pass

@dataclass(frozen=True)
class DispatchAction(ScheduleAction):
    task_id: TaskId
    agent_id: AgentInstanceId
    expected_cost: Cost                # token / time 估算

@dataclass(frozen=True)
class HoldAction(ScheduleAction):
    task_id: TaskId
    reason: str                        # "等待 T3 完成以避免读写域冲突"

@dataclass(frozen=True)
class MergeProposalAction(ScheduleAction):
    """提议合并语义重叠的任务，给父任务确认。"""
    task_ids: list[TaskId]
    merged_intent: str

@dataclass(frozen=True)
class ReprioritizeAction(ScheduleAction):
    task_id: TaskId
    new_position: int
```

调度器**不只能"选一个任务"**——还可以建议合并、重排序、暂缓。这些建议都是**可审计、可解释**的。

### 3.4 调度器的执行循环

```
                  ┌────────────────────────────┐
                  │   Trigger: 状态变化事件       │
                  │   (publish / complete /     │
                  │    fail / agent_idle)       │
                  └──────────────┬─────────────┘
                                 │
                                 ↓
                  ┌────────────────────────────┐
                  │   收集 SchedulingContext    │
                  └──────────────┬─────────────┘
                                 │
                                 ↓
                  ┌────────────────────────────┐
                  │   Scheduler.decide(ctx)    │  ← LLM 调用
                  └──────────────┬─────────────┘
                                 │
                                 ↓
                  ┌────────────────────────────┐
                  │   apply(decision)          │
                  │   - DispatchAction → bus   │
                  │   - HoldAction → 留在队列   │
                  │   - MergeProposal → 父任务  │
                  └────────────────────────────┘
```

**注意：调度器不是每个任务调用一次 LLM**。它的触发是事件驱动 + 节流的：
- `publish/complete/fail/agent_idle` 触发重新评估
- 短时间内多次触发会被合并（防抖动）
- 极简场景下（队列长度 ≤ 1，无并发候选），跳过 LLM 直接走 v1 的 FIFO 路径

### 3.5 成本控制

LLM 调度本身有 token 成本，必须控制：

```
1. 分级：小队列走 FIFO，大队列才调用 LLM
       len(pending) < 阈值 → fast_path（v1 行为）
       len(pending) ≥ 阈值 → llm_path

2. 缓存：调度器的 prompt 高度结构化
       system + tools 部分稳定 → prompt cache 命中率高

3. 模型分层：调度用小模型（haiku 类），执行用大模型
       调度决策不需要深度推理，更需要快速反应

4. 限流：每秒最多一次调度调用
       多个事件在窗口内合并为一次调度
```

**不是所有调度都需要 LLM。** 在 v1 的简单路径之上，把 LLM 当作"队列变复杂时才请来的咨询师"。

### 3.6 可降级性

LLM 调度器**必须可降级**到 v1 行为：

```python
class TaskBusV2:
    def claim_next(self, capability: str) -> Task | None:
        if self.scheduler.is_available() and self._should_use_llm():
            return self._llm_schedule(capability)
        return self._fifo_schedule(capability)  # v1 行为
```

降级触发条件：
- 调度器超时 / 错误
- LLM API 不可用
- 用户配置 `scheduler="fifo"`
- 队列规模过小不值得 LLM 调用

**v1 路径永远是兜底。** v2 的智能是增量价值，不是必须依赖。

---

## 4. 并发执行模型

### 4.1 重新评估串行约束

v1 选择串行的核心理由是"单工作区，并发会写冲突"。但用户指出：

```
LLM 任务的"耗时"集中在 LLM API 调用（百毫秒~分钟）
LLM 任务的"写"集中在工具调用阶段（毫秒级 IO）

      ┌── LLM 推理 ──┐ ┌─ 工具调用 ─┐ ┌── LLM 推理 ──┐
      │   ~10 秒    │ │  ~ 50ms  │ │   ~10 秒    │
      └─────────────┘ └──────────┘ └─────────────┘
            ↑              ↑
       并发收益巨大     冲突风险只在这里
```

**真正会冲突的是工具调用阶段（IO），但它在任务总耗时里占比 < 5%。**

如果让多个任务的 **LLM 推理阶段**并发运行，仅在**工具调用阶段**串行化（或按读写域并发），收益是数倍的总时长缩短。

### 4.2 并发模型的核心想法

```
任务 = 多次 (LLM 推理 + 工具调用) 的循环

并发策略：
  阶段 1（LLM 推理）：完全并发，N 个任务同时调用 LLM API
  阶段 2（工具调用）：按读写域校验
                     - 读写域不重叠 → 并发执行
                     - 读写域冲突   → 加入小锁队列串行执行
```

```
T1: ┌─LLM─┐ ┌─Tool─┐ ┌─LLM─┐ ┌─Tool─┐
T2: ┌─LLM─┐         ┌─LLM─┐ ┌─Tool─┐
T3:        ┌─LLM─┐         ┌─LLM─┐  ┌─Tool─┐

时间 ────────────────────────────────────→
       并发LLM   读写检查  并发LLM     串行化（如有冲突）
```

### 4.3 读写域声明

每个任务在工具调用前**声明**它将触及的读写域：

```python
@dataclass(frozen=True)
class IOScope:
    reads: frozenset[Path]   # 即将读取的路径
    writes: frozenset[Path]  # 即将写入的路径

# 由 Agent 在每次工具调用前提交
bus.acquire_io(task_id, IOScope(reads=..., writes=...))
# 执行工具
bus.release_io(task_id)
```

冲突判定：

```
任务 A 的 IOScope vs 任务 B 的 IOScope：

  A.writes ∩ B.writes ≠ ∅          → 写写冲突，必须串行
  A.writes ∩ B.reads  ≠ ∅          → 写读冲突，必须串行
  A.reads  ∩ B.reads  =  *         → 读读不冲突，可并发
```

不冲突 → 并发执行；冲突 → 后到的等前者 release。

### 4.4 IOScope 怎么来

三种获取方式，按精度递增、获取成本递增：

```
1. 任务级粗粒度声明（最简单）
   Task.declared_scope: IOScope
   任务发布时由发布者提供，覆盖整个任务生命周期。

2. 工具调用前细粒度声明（中等）
   Agent 在每次 tool_call 前调用 bus.acquire_io(...)
   精度高，但需要 Agent 配合。

3. 工具自我声明（最强）
   每个工具 schema 标注它的 IO 模式（读/写/路径模板）
   ToolRegistry 静态推导出工具调用的 IOScope
```

**v2 起步时只用 1 + 3**：粗粒度任务声明 + 工具静态声明。这两者都是声明式的，不需要 Agent 在运行时关心调度细节。

### 4.5 冲突解决策略

```
策略 A：拒绝式
  发现冲突 → 后来者直接进入 pending，等前者释放
  优点：简单
  缺点：可能 starvation

策略 B：让步式
  调度器在调度阶段就避免可能冲突的任务并发
  优点：fairness
  缺点：可能过度保守（保守预测冲突，错过并发机会）

策略 C：乐观执行 + 回滚（不推荐）
  让任务先跑，事后比对，冲突就回滚
  优点：理论吞吐量最高
  缺点：LLM 任务回滚成本极高（已消耗 token），不划算
```

**v2 选择 A + B 的组合**：调度器尽量避免冲突，运行时碰到了就拒绝（拒绝者排队）。

### 4.6 并发度上限

并发不是越多越好：

```
受限维度：
  1. LLM API rate limit（典型瓶颈）
  2. Workspace IO 带宽（极少瓶颈）
  3. 内存中 Agent 实例数量
  4. 用户感知（同时跑太多任务会让用户失去掌控感）

实践默认：max_concurrent = 4
  理由：典型 LLM API 的 rate limit 允许，
       用户也能从 UI 上跟得上。
```

并发度可由 SessionConfig 配置，从 1（v1 行为）到 N。

---

## 5. 重新评估 Agent 亲和性与缓存

### 5.1 Prompt Cache 的真实模型

prompt cache 命中要求**完全相同的前缀**：

```
[system_prompt][tool_definitions][user_msg_1][assistant_msg_1][...]

cache 边界：cache 只能从前缀的某个位置切——前缀完全相同才命中。
            一旦中间有任何差异，后续都不命中。
```

哪些部分稳定（高命中率）？

```
✓ system_prompt        ─ Agent 模板级稳定
✓ tool_definitions     ─ Agent 模板级稳定
✗ workspace_snapshot   ─ 任务级动态
✗ task_intent          ─ 任务级动态
✗ tool_call_history    ─ 任务级动态
```

### 5.2 重新审视"无状态" 与缓存的关系

v1 文档提到"无状态 Agent 的 cache 命中差"。但仔细分析：

```
单个 Agent 实例的生命周期：
  实例化 → [LLM调用 1] → [工具] → [LLM调用 2] → ... → 销毁

  LLM 调用 2/3/.../N 都能命中 LLM 调用 1 的 system + tools 缓存
  ──实例内部缓存自然命中率高──

跨实例：
  实例 A 销毁后，实例 B 用同一 AgentTemplate
  system + tools 完全相同 → API 侧 prompt cache 仍然命中
  （cache 是 API 提供商侧的，不依赖客户端实例）
```

**关键洞见：缓存命中靠 prefix 相同，不靠实例延续。**

只要：
- 同一 AgentTemplate 的 system + tools 是确定的
- API 提供商侧有跨请求的 prompt cache（OpenAI / Anthropic 都有）

**实例的销毁不会丢失 cache 命中机会。** 真正会破坏命中的是：
- workspace_snapshot 内容变化（任务级，无法避免）
- 历史消息差异（任务级，无法避免）

这些差异**与"实例是否复用"无关**。

### 5.3 结论：Agent 池预热 ≠ 状态保留

```
v1 担心：无状态 → cache 命中差 → 成本高
v2 重新评估：cache 命中由 prompt prefix 决定，与实例生命周期解耦

→ 不需要为了 cache 命中放弃"无状态"约束
→ "Agent 池预热"如果有，目的是减少**实例化开销**，不是为了 cache
→ 甚至 Agent 池预热的价值都不大（实例化是 ms 级，LLM 调用是 s 级）
```

**结论：v1 的"无状态 Agent"约束不需要松绑。** 这是好消息——一个原本以为是代价的设计，重新分析后发现并没有显著代价。

### 5.4 真正影响 cache 命中的因素

排在前面的优化点：

```
1. 让 system_prompt 在所有 AgentTemplate 间共享公共前缀
   通用框架性 prompt 在前，模板特化 prompt 在后
   → 跨模板也能命中前段缓存

2. 让 tool_definitions 排序稳定
   工具集相同时不同顺序也会破坏缓存
   → ToolRegistry 输出固定顺序

3. 让 workspace_snapshot 的注入方式可控
   workspace 大块内容放在用户消息后部
   → 减少对前段缓存的污染
```

这些优化都**不需要修改 Bus 设计**——属于 Agent 模板和 prompt 工程层。

---

## 6. v2 核心 API

```python
class TaskBusV2:
    # —— v1 兼容部分 ——
    def publish(self, task: Task) -> TaskId: ...
    def get(self, task_id: TaskId) -> Task: ...
    def children_of(self, task_id: TaskId) -> list[Task]: ...

    # —— claim 行为升级 ——
    def claim_next(self, capability: str) -> Task | None:
        """
        v2: 走调度器决策
        - 满足 IOScope 兼容性
        - 受 max_concurrent 限制
        可降级到 v1 FIFO 行为。
        """

    # —— 新增：IO 域获取 / 释放 ——
    def acquire_io(self, task_id: TaskId, scope: IOScope) -> IoLease:
        """获取读写域。冲突则阻塞或返回 LeaseDenied。"""

    def release_io(self, lease: IoLease) -> None:
        """释放读写域。"""

    # —— 新增：调度器接口 ——
    @property
    def scheduler(self) -> Scheduler: ...

    def force_decide(self) -> SchedulingDecision:
        """显式触发一次调度决策（运维/调试用）。"""

    # —— 新增：并发观察 ——
    def running_tasks(self) -> list[Task]: ...
    def concurrency_level(self) -> int: ...

    # —— 完成 / 失败仍然集中 ——
    def complete(self, task_id: TaskId, result: TaskResult) -> None: ...
    def fail(self, task_id: TaskId, error: str) -> None: ...
```

API 增量主要在两块：**IO 域** 和 **调度器观察**。状态权威、事件溯源等核心责任不变。

---

## 7. 调度算法（v2 简化伪代码）

```python
async def schedule_loop(bus: TaskBusV2):
    while bus.is_active():
        await bus.wait_for_event()  # publish/complete/fail/io_release...

        # 防抖
        await asyncio.sleep(DEBOUNCE_MS / 1000)
        bus.drain_events()

        ctx = bus.collect_context()

        # 分级路径
        if ctx.is_simple():
            decision = fifo_decide(ctx)        # v1 行为
        else:
            decision = await llm_scheduler.decide(ctx)  # v2 行为

        for action in decision.actions:
            apply_action(bus, action)
```

```python
def apply_action(bus, action):
    match action:
        case DispatchAction(task_id, agent_id, _):
            if bus.concurrency_level() >= bus.max_concurrent:
                return  # 等下一轮
            scope = bus.task_scope(task_id)
            if bus.has_conflict(scope):
                return  # 留在 pending
            bus._dispatch(task_id, agent_id)

        case HoldAction(task_id, reason):
            bus._mark_held(task_id, reason)

        case MergeProposalAction(ids, merged):
            bus._propose_merge_to_parent(ids, merged)

        case ReprioritizeAction(task_id, pos):
            bus._reorder(task_id, pos)
```

这部分代码量比 v1 增加了 **3-5x**，但仍可控（数百行级）。

---

## 8. 与其他组件的关系

v2 的关系图比 v1 多两条边：

```
                  ┌────────────────────────────┐
                  │  TaskBus v2                │
                  │                            │
                  │  ┌──────────┐              │
                  │  │ Scheduler│ ←── LLM API  │ ← 新增
                  │  │  (LLM)   │              │
                  │  └──────────┘              │
                  │                            │
                  │  ┌──────────┐              │
                  │  │ IO Guard │ ←── ToolRegistry IOScope 元数据
                  │  └──────────┘              │ ← 新增
                  │                            │
                  │  ┌──────────┐              │
                  │  │  Queue   │ ←── publish (User/Agent)
                  │  │  Index   │ → claim/complete (Agent)
                  │  └──────────┘              │
                  │                            │
                  └──────────┬─────────────────┘
                             │ emit
                             ↓
                       EventStream
```

新关系：
- **与 LLM API（间接）**：调度器是 LLM 客户端，调度本身消耗 token
- **与 ToolRegistry**：IO Guard 读取工具的 IOScope 元数据做静态冲突分析

**与 v1 的相同关系都保留**：与 Session、Agent、EventStream、Workspace 的关系不变。

---

## 9. 设计哲学

### 9.1 v1 是骨架，v2 是肌肉

```
v1：保证"做对"
  - 状态永远一致
  - 任务永不丢失
  - 失败永不传染
  - 简单到容易审计

v2：保证"做好"
  - 全局视角的调度
  - 并发释放的吞吐
  - 语义层面的合并/重排
  - 用户意图的对齐
```

v2 不能违背 v1 的承诺：状态权威、事件溯源、失败隔离仍然是底线。

### 9.2 智能是可降级的

调度器的智能必须**永远可关闭**：

```
配置：scheduler.mode = "off" | "llm" | "auto"
  off  → v1 行为（FIFO）
  llm  → 全部走 LLM
  auto → 队列简单走 FIFO，复杂走 LLM
```

这保证：
- 调试时可关闭智能层观察底层
- LLM API 故障时系统不停摆
- 用户偏好"可预测"时可以选择简单路径

### 9.3 并发不是必然

```
max_concurrent = 1 → 退化为 v1 串行
max_concurrent = N → v2 并发
```

并发也是配置项，不是默认强制。**简单优先级原则**：用户没有明确的吞吐量需求时，串行路径仍然是默认值。

### 9.4 调度可解释

LLM 调度的最大风险是"决策不可解释"。v2 强制每个 SchedulingDecision 携带 `rationale`：

```
SchedulingDecision(
    actions=[Dispatch(T3, agent_5)],
    rationale="T3 的读写域与 T1 不冲突，且 T3 是用户当前问题的关键路径"
)
```

`rationale` 写入 EventStream，用户/审计者随时可追溯。这是把"LLM 调度"从黑箱变成**可审计组件**的关键。

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|-----|------|------|
| LLM 调度延迟 | 调度本身耗时增加 | 分级 + 防抖 + 小模型 |
| LLM 调度成本 | token 持续消耗 | 简单路径走 FIFO，prompt 高度结构化以最大化 cache |
| LLM 决策不稳定 | 同状态可能给出不同决策 | 决策审计 + rationale + 可降级 |
| 并发引入的死锁 | 任务互等读写域释放 | 静态冲突预测 + 死锁检测 + 拒绝式排队 |
| IOScope 声明不准 | 漏声明 → 真冲突；过声明 → 错失并发 | 工具静态声明优先；逐步增加 Agent 显式 acquire_io |
| 复杂度上升 | 调试难度增加 | EventStream 完整记录调度决策与 IO 决议 |

每条风险都有显式缓解路径。**没有缓解方案的风险不引入。**

---

## 11. 渐进引入路线

不必一次性引入 v2 全部能力。建议路线：

```
阶段 0：v1 落地稳定运行
        基线指标：单 Session 平均任务延迟、错误率

阶段 1：引入 IOScope（无并发）
        Task / Tool 声明读写域，但 max_concurrent=1
        验证 IOScope 声明的准确性，零行为改变

阶段 2：开启有限并发（max_concurrent=2~4）
        仍用 FIFO 调度，但允许并发
        验证并发收益与冲突频率

阶段 3：引入 LLM 调度器（可降级）
        默认 auto 模式，简单走 FIFO
        在大队列、复杂依赖场景观察 LLM 决策质量

阶段 4：调度器精细化
        加入 MergeProposal、Reprioritize 等高级动作
        基于阶段 3 的真实使用数据调整 prompt
```

每一步都**可独立产出价值，可独立回滚**。这才是好的演进设计。

---

## 12. 设计决策小结

| 决策 | v2 选择 | v1 对比 | 选择理由 |
|------|--------|---------|---------|
| 调度器 | LLM + FIFO 双轨 | 仅 FIFO | 队列复杂时 LLM 提供语义级决策 |
| 并发模型 | 受限并发（按 IOScope） | 严格串行 | LLM 推理是耗时主体，并发收益巨大 |
| 冲突解决 | 静态预测 + 拒绝排队 | 不需要（串行） | 冲突域可被静态分析，无需运行时回滚 |
| 缓存策略 | 不绑定实例亲和 | 同 v1 | cache 命中由 prompt prefix 决定，与实例无关 |
| 调度可降级 | 强制可降级到 FIFO | N/A | 智能层故障不影响系统正确性 |
| 决策可解释 | 强制 rationale 写 EventStream | N/A | 把 LLM 调度变成可审计组件 |
| 并发度 | 默认 4，可配置 | 默认 1 | 平衡 API 限速与用户掌控感 |
| IOScope 来源 | 工具静态 + 任务声明 | N/A | 声明式优先，避免运行时冗余协调 |

---

## 13. 总结

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   v1 解决了"对不对"，v2 解决"好不好"                       │
│                                                          │
│   智能调度可降级，并发模型可关闭                          │
│                                                          │
│   IOScope 让冲突可预测，LLM 让调度有语义                  │
│                                                          │
│   每一步都可独立落地，每一步都可独立回滚                   │
│                                                          │
│   v1 是地基，v2 是楼层——不是替代，是叠加                 │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

如果说 v1 的口号是 *"做最少的事，做对所有事"*，那 v2 的口号是 *"在做对的基础上，让 LLM 的推理也能调度本身"*——**让架构的智能层和执行层共享同一种能力**。
