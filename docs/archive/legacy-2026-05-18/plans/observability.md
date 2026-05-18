# Plan: 可观测性

> 多 Agent 协作架构 · Trace / Metrics / Debug 设计计划 · v0 · 2026-05-10

---

## 1. 背景

EventStream 在架构里被反复提及，但**怎么用、怎么查、怎么和现代可观测体系对接**几乎没说。多 Agent 系统的调试已经够难了：任务嵌套、并发、LLM 不确定性、调度决策不可见——没有可观测体系，**调试成本会成为开发瓶颈**。

参考评审：[architecture/review.md](../architecture/review.md) 第 2.2 节（可观测性列为 🟠 中等优先空白）。

---

## 2. 目标

- **Trace**：任意任务可追溯完整生命周期（含父子链、Agent 实例、LLM 调用、工具调用）
- **Metrics**：核心指标实时可查（吞吐量、延迟、成本、命中率、错误率）
- **Debug**：可 replay、可 step、可 inspect 任意时刻的系统状态
- **集成**：与 OpenTelemetry / Prometheus / 类似生态对接

**非目标：**
- 不做完整的 APM 系统（依托现成生态）
- 不做日志聚合（用现成方案）

---

## 3. 待解决的问题清单

| # | 问题 | 难点 |
|---|------|-----|
| 1 | EventStream 怎么高效查询（按 task / agent / time）？ | 索引设计 |
| 2 | LLM 调用的 trace 跨进程怎么连起来？ | trace_id 传播 |
| 3 | replay 时如何处理 LLM 的非确定性？ | record/replay 模式 |
| 4 | 长会话（数千事件）下的 UI 性能？ | 分页 + 流式 |
| 5 | 调度器决策（含 rationale）怎么呈现？ | 时间轴 + 决策树 |
| 6 | 死锁 / 活锁怎么自动检测？ | 状态机不变量 |
| 7 | 隐私敏感数据（用户输入 / Workspace 内容）怎么脱敏？ | 字段级控制 |

---

## 4. 三大支柱

### 4.1 Trace（追踪）

完整记录"一次任务从生到死"的过程：

```
TaskTrace:
  task_id, parent_id, session_id
  events: [
    TaskPublished(...)
    TaskClaimed(agent_run_id, claimed_at)
    LLMCallStarted(model, prompt_hash, ...)
    LLMCallCompleted(usage, finish_reason)
    ToolCallStarted(tool_name, args_hash)
    ToolCallCompleted(result_hash, duration_ms)
    SubtaskPublished(subtask_id)
    SubtaskCompleted(subtask_id)
    TaskCompleted(result_hash)
  ]
```

**所有事件都是 EventStream 的一等公民**，trace 是事件的视图。

### 4.2 Metrics（指标）

核心指标分类：

```
Throughput
  ─ tasks_per_minute (by capability)
  ─ tasks_per_session

Latency
  ─ task_duration_p50/p95/p99 (by capability)
  ─ time_in_pending (排队等待时间)
  ─ time_in_running

Cost
  ─ tokens_per_task (by capability)
  ─ usd_per_session
  ─ scheduler_token_ratio (v2)

Reliability
  ─ task_failure_rate (by capability + by error_kind)
  ─ tool_call_failure_rate
  ─ scheduler_fallback_rate (v2)

Cache
  ─ prompt_cache_hit_ratio
  ─ tokens_saved_by_cache

Concurrency (v2)
  ─ avg_concurrent_tasks
  ─ io_conflict_rate
```

按 task / capability / model / session 多维度切片。

### 4.3 Debug（调试）

- **Replay**：从 EventStream 重建任意时刻的系统状态
- **Step**：单步执行模式（每个事件后暂停）
- **Inspect**：查看任意 Task / Agent / Scheduler 的当前状态

---

## 5. EventStream 数据模型

### 5.1 Event 基类

```python
class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: EventId                  # ULID，可排序
    event_type: str                    # 类型 tag
    occurred_at: datetime              # 发生时刻

    # 关联标识
    session_id: SessionId
    task_id: TaskId | None
    agent_run_id: AgentRunId | None
    trace_id: TraceId                  # OTel trace 联动

    # 数据
    payload: dict[str, Any]            # 类型相关字段

    # 因果
    causality_id: EventId | None       # 触发本事件的上游事件
```

### 5.2 事件类型枚举

```
SessionEvents       SessionCreated, SessionClosed, ConfigChanged
TaskEvents          TaskPublished, TaskClaimed, TaskCompleted, TaskFailed
AgentEvents         AgentInstantiated, AgentDestroyed
LLMEvents           LLMCallStarted, LLMCallCompleted, LLMCallFailed
ToolEvents          ToolCallStarted, ToolCallCompleted, ToolCallFailed
SchedulerEvents     SchedulingDecisionMade (v2), DispatchAttempted, DispatchHeld
IOEvents            IoLeaseAcquired, IoLeaseReleased, IoConflictDetected
CostEvents          CostRecorded, BudgetWarned, BudgetExceeded
UserEvents          UserMessageReceived, UserActionResolved
```

每个事件有强类型 payload schema，不允许自由 dict。

---

## 6. 索引与查询

### 6.1 必备索引

```
session_id                     ─ 取一次会话的所有事件
(task_id, occurred_at)         ─ 任务的事件链
(capability, occurred_at)      ─ 同类任务的对比
(event_type, occurred_at)      ─ 按类型筛选
trace_id                       ─ OTel 关联
```

### 6.2 查询 API

```python
class EventStream:
    def by_session(self, session_id, time_range=None, types=None) -> Iterator[Event]: ...
    def by_task(self, task_id, include_descendants=False) -> Iterator[Event]: ...
    def by_trace(self, trace_id) -> Iterator[Event]: ...
    def aggregate(self, session_id, group_by=...) -> dict: ...
    def stream(self, session_id) -> AsyncIterator[Event]:
        """实时订阅未来事件。"""
```

### 6.3 存储后端

```
开发期：SQLite（单文件，易调试）
生产期：PostgreSQL + JSONB payload + GIN 索引
未来：  独立 event store（如 EventStoreDB）
```

抽象层 `EventStreamBackend` 屏蔽差异。

---

## 7. Trace 视图：调度器决策树

bus-v2 的 LLM 调度决策最难调试。专门设计调度树视图：

```
SchedulingDecision @ 12:34:56
├─ Context:
│   ├─ pending: [T3, T4, T5]
│   ├─ running: [T1, T2]
│   └─ available_agents: [A1, A2, A3]
├─ LLM Call:
│   ├─ model: claude-haiku
│   ├─ tokens: 1.2k → 0.3k
│   └─ duration: 320ms
├─ Decision:
│   ├─ Dispatch(T3, A1) — "覆盖用户当前问题主线"
│   ├─ Hold(T4) — "读写域与 T1 冲突"
│   └─ MergeProposal([T5, T2]) — "语义重叠"
└─ Applied:
    ├─ T3 → running ✓
    ├─ T4 → held
    └─ MergeProposal → 父任务确认
```

**rationale 必须显式存储**——这是把 LLM 调度从黑箱变成可审计组件的关键。

---

## 8. OpenTelemetry 集成

### 8.1 trace_id 传播

```
User Request
  └─ Session.handle_request → trace_id 创建
       └─ Task.publish → trace_id 注入到 Task
            └─ Agent.run → trace_id 注入到 LLM API call header
                 └─ LLM Provider 返回 → 子 span 闭合
            └─ Tool.call → trace_id 注入工具内部
                 └─ Tool 内部 IO → 子 span
       └─ subtask.publish → 继承 trace_id，新 span
```

### 8.2 Span 命名约定

```
session.{session_id}.handle
task.{task_id}.lifecycle
task.{task_id}.llm_call.{n}
task.{task_id}.tool_call.{n}.{tool_name}
scheduler.decide
```

### 8.3 兼容现有 OTel SDK

EventStream 的事件**镜像**为 OTel events / spans。两者同步存在：
- EventStream → 系统内部状态权威
- OTel → 与外部 APM 工具集成

不强制依赖 OTel——可关闭 OTel exporter 仍能工作。

---

## 9. Replay 模式

### 9.1 Record 模式

```
recording_session = Session.start(record=True)
# 所有 LLM 调用的 (prompt, response) 被记录到 RecordingStore
# 所有工具调用的 (args, result) 被记录
```

### 9.2 Replay 模式

```
replayed = Session.replay(recording_id)
# LLM 调用不真实发生，从 RecordingStore 返回历史 response
# 工具调用同理（除非显式标记 "replay-side-effect"）
# 用于 debug / regression test
```

### 9.3 Hybrid 模式

```
session = Session.replay(recording_id, divergence_at=event_id)
# 在指定事件前 replay
# 之后切换到 live 模式
# 用于探索"如果当时换个决策会怎样"
```

### 9.4 LLM 不确定性的处理

```
策略：record 时存 (prompt_hash, response, model, temperature)
       replay 时若 prompt_hash 一致 → 返回历史 response
       不一致 → 报告 divergence，由调试者决定是否继续
```

---

## 10. 自动检测：死锁 / 活锁 / 异常

### 10.1 不变量

```
inv1: 串行模式下 |running_tasks| ≤ 1
inv2: pending 任务的 parent 不能是 pending
inv3: 任务深度 ≤ max_task_depth
inv4: agent_run_id 在终态后不再产生事件
inv5: 时间戳单调（per session）
```

每条不变量都有独立检查器，违反时立即写 `InvariantViolatedEvent` 并通知。

### 10.2 启发式

```
heuristic1: 任务在 pending 超过 N 分钟 → 可能 capability 没注册
heuristic2: 任务深度持续增长 → 可能任务爆炸
heuristic3: scheduler_token_ratio > 0.2 → 调度器太贵
heuristic4: 同一工具在同一任务中连续失败 N 次 → 可能死循环
```

启发式触发警告，不直接终止——避免误杀。

---

## 11. UI / CLI 入口

### 11.1 CLI

```
codeagent inspect session <id>          # 概览
codeagent inspect task <id>             # 任务详情 + 事件链
codeagent trace <task_id>               # ASCII 时间线
codeagent metrics --session <id>        # 指标快照
codeagent replay <recording_id>         # 启动 replay
codeagent watch                         # 实时事件流
```

### 11.2 Web UI

```
最小可用版：
  - 时间线视图（事件流）
  - 任务树视图（嵌套展开）
  - 调度决策视图（rationale 高亮）
  - 指标面板（4-6 个核心 chart）
  - Replay 控制面板
```

UI 也只是 EventStream 的查询 + OTel 视图的组合，不持有独立状态。

---

## 12. 隐私与脱敏

### 12.1 字段级标注

```python
class EventPayload(BaseModel):
    user_message: str = Field(sensitivity="user_content")
    workspace_snippet: str = Field(sensitivity="workspace")
    llm_prompt_hash: str = Field(sensitivity="public")
```

### 12.2 多档脱敏策略

```
public        ─ 完全保留
internal      ─ 内部审计可见，外部 export 时哈希化
user_content  ─ 仅本人可见，导出需用户授权
workspace     ─ 同上 + 路径脱敏
secret        ─ 永远只存 hash，原文不记录（如 API key）
```

EventStream 的 export / 跨进程传输都走脱敏过滤。

---

## 13. 待回答的开放问题

| 问题 | 决策需要的输入 |
|------|------------|
| 事件保留期？ | 隐私 + 存储成本 + 调试需求 |
| 是否压缩历史事件（hot vs cold）？ | 查询频率分布 |
| Metrics 的预聚合粒度？ | 查询模式 |
| Replay 的 LLM 调用是否产生新成本？ | 调试预算 |
| 与现有日志系统（zap/loguru）的关系？ | 现有依赖 |

---

## 14. 实施里程碑

```
M1 — 事件骨架
  ─ Event 基类 + 类型枚举
  ─ EventStream 接口 + SQLite 后端
  ─ 5 大类核心事件实现

M2 — 查询层
  ─ 索引建立
  ─ by_session / by_task / aggregate API
  ─ 实时订阅 stream API

M3 — Trace 视图
  ─ 任务树 trace 渲染
  ─ 调度决策树渲染
  ─ CLI inspect / trace 命令

M4 — Metrics
  ─ 核心指标定义 + 聚合
  ─ 实时指标 API
  ─ Prometheus exporter（可选）

M5 — Replay
  ─ Recording 模式
  ─ Replay 模式
  ─ Hybrid + divergence 检测

M6 — 不变量与启发式
  ─ 5 条核心不变量
  ─ 4 条启发式 + 警告通道
  ─ Auto-pause on violation

M7 — OTel 集成
  ─ trace_id 传播
  ─ Span 镜像
  ─ Exporter 配置

M8 — 隐私
  ─ 字段级 sensitivity
  ─ Export 脱敏
  ─ 用户授权流程
```

---

## 15. 验收标准

| 验收点 | 衡量方式 |
|------|---------|
| 任意任务可完整 trace | 给任意 task_id 能在 1s 内拿到完整事件链 |
| 调度决策可解释 | 每个 SchedulingDecision 有 rationale 字段非空 |
| Replay 可重现历史 | 录制后 replay 在相同输入下产生 ≥ 95% 一致输出 |
| 不变量违反必报 | 单元测试人为构造违反场景，100% 触发警报 |
| Metrics 实时性 | 指标查询延迟 < 100ms |
| OTel 联通 | 在 Jaeger / Tempo 中能看到完整 trace |

---

## 16. 与其他 plan 的关系

- [walkthrough.md](walkthrough.md) — 端到端示例必须展示完整 trace
- [cost-quota.md](cost-quota.md) — Cost 是核心指标
- [configuration.md](configuration.md) — ConfigChangedEvent 是事件类型之一
- [ux-interaction.md](ux-interaction.md) — UI 历史导航依赖查询能力
- [user-guide.md](user-guide.md) — 用户调试入口在 user-guide 中说明
