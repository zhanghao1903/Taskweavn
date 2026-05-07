# Interaction Layer 技术设计

> 版本 v1.1 · 2026-05-08
>
> 关联文档：[多 Agent 协作架构设计](multi_agent_collaboration_architecture.md)
>
> 本文档落实 Phase 3 的实现接口。架构理念见上方关联文档；本文档只解决"具体怎么做"。

---

## 目录

1. [背景与范围](#1-背景与范围)
2. [设计原则](#2-设计原则)
3. [关键决策一览](#3-关键决策一览)
4. [核心数据结构](#4-核心数据结构)
5. [核心组件](#5-核心组件)
6. [控制流](#6-控制流)
7. [持久化、并发、失败模式](#7-持久化并发失败模式)
8. [与已有架构的衔接](#8-与已有架构的衔接)
9. [Phase 3 切片重排](#9-phase-3-切片重排)
10. [待定问题](#10-待定问题)
11. [附录 A — 类型速查](#附录-a--类型速查)
12. [附录 B — 风险基线参考表](#附录-b--风险基线参考表)

---

## 1. 背景与范围

### 1.1 问题陈述

现有的单轮 `AgentLoop.run(task) -> LoopResult` 不支持：

- 长程对话（任务跨数十轮、跨进程）
- 用户在执行中介入（中途追加要求、纠偏、回应确认）
- agent 之间协同（Phase 4 的多 agent 编排）

直接的"暂停 / 等待用户输入 / 恢复"模型存在两个问题：

1. **打断不可配置** — 高自主度任务希望"我自己干，别问我"，低自主度希望"每一步都让我看一眼"，硬编码的 ask/finish 二元控制流支撑不了
2. **多 agent 时退化** — 多个 agent 同时想问用户，"暂停整个 loop"语义模糊

### 1.2 本文档的范围

定义"agent 与用户、agent 与 agent 之间结构化通信"的实现层接口，覆盖：

- 消息流（MessageStream）的事件类型与持久化
- 自主度行为（AutonomyBehavior）的配置与生效路径
- 自主度门禁（AutonomyGate）的决策模型
- 风险评估（RiskAssessor）的量化与可扩展性
- 消息总线（MessageBus）的发布/订阅与等待语义

不在本文档范围（推到对应阶段或后续设计）：

- AgentInstance 抽象与多 agent 编排（Phase 4）
- ConstraintProfile 与 OrchestrationDesigner（Phase 4）
- ToolRegistry 形式化（Phase 4 起点）
- Plan / RAG / Summarization（Phase 3 后段，本文档不展开）

---

## 2. 设计原则

| 原则 | 含义 | 落地体现 |
|---|---|---|
| **消息流替代打断** | agent 永远不"暂停整个流程"；它发消息，等待行为由 autonomy 决定 | `AutonomyBehavior` 决定阻塞/非阻塞，`MessageBus` 不是控制流原语 |
| **风险量化而非二元** | 不存在"危险/不危险"的开关，只有 0.0–1.0 的连续值 | `RiskScore: float`，用户阈值，最佳实践默认 |
| **静态下限 + 动态上调** | Action 类自带 `baseline_risk`，runtime 评估器只能让风险更高，不能更低 | `final_risk = max(baseline_risk, dynamic_risk)` |
| **接口先于实现** | 每个组件先定义 Protocol，单进程实现是默认，跨进程实现可替换 | `MessageBus` Protocol、`RiskAssessor` Protocol |
| **存储分流** | MessageStream 是用户产品体验，EventStream 是工程审计；分别建表 | 独立的 `messages.sqlite` |
| **现有抽象不污染** | Phase 1/2 的 Action / Observation / EventStream 一行不改 | AgentMessage 是新家族 |

---

## 3. 关键决策一览

| 决策 | 选定 | 理由 |
|---|---|---|
| **AgentInstance 抽象** | Phase 4 才引入 | Phase 3 单 agent 场景下，所有消息的 `agent_id` 都填 `"agent"`；不提前预埋复杂度 |
| **风险判定** | runtime 实例级，类级提供下限 | 同一个 `RunCommand` 跑 `ls` 和 `rm -rf /` 风险不同，不能在类上一刀切 |
| **风险量化** | float ∈ [0.0, 1.0]，用户配阈值，内置默认值 | 连续量便于策略演进；二元 flag 一旦定下来很难松绑 |
| **MessageStream 存储** | 独立 SQLite，跟 EventStream 分表 | 用户消费的是消息流（产品层），EventStream 是审计层；混表会绑死两者演进节奏 |
| **消息总线** | 真正的 pub/sub（不是轮询） | 用户回复要立刻唤醒等待中的 agent；轮询 latency 不可接受 |
| **等待语义** | 双模式：sync wait / async ack | 低自主度等用户授权 = 阻塞；高自主度发完即继续，响应回流到下一次迭代 |
| **`Session.status.awaiting_user`** | 保留枚举值，改为派生量 | 列表 UI 显示 "等用户"，但不影响 loop 控制流 |

---

## 4. 核心数据结构

### 4.1 风险模型

风险是连续值 `RiskScore: float ∈ [0.0, 1.0]`：

```
0.0  完全无副作用，纯读取
0.3  受限副作用（写 workspace 内文件、追加日志）
0.5  受限副作用 + 不可逆（删除 workspace 内文件）
0.7  跨边界副作用（沙箱外文件、网络请求）
0.9  系统级影响（修改全局配置、安装包、kill 进程）
1.0  灾难级（rm -rf /、修改系统服务、撤销不可能）
```

附录 B 给出每种 Action 的基线参考。

#### 4.1.1 三层风险

```python
@dataclass(frozen=True)
class RiskAssessment:
    baseline: float              # Action 类静态下限（编译期常量）
    dynamic: float               # 运行时评估器给出的提升（默认 = baseline）
    final: float                 # max(baseline, dynamic)，决策用这个
    rationale: list[str]         # 评估依据，可累加
    assessor: str                # 谁给的：'baseline' | 'llm' | 'audit' | <custom>
```

**不变量**：

- `final == max(baseline, dynamic)`
- `dynamic >= baseline` 总是成立 — 评估器只能让风险更高
- 多个评估器串行时，`final` 永不下降

#### 4.1.2 BaselineRisk 在 Action 上的表达

```python
class BaseAction(BaseEvent):
    # 已有字段...

    baseline_risk: ClassVar[float] = 0.0
    """Action 类的静态下限。子类覆盖。"""

class CodeAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.5  # 任意代码执行
    # ...

class WriteFileAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.3
    # ...

class ReadFileAction(BaseAction):
    baseline_risk: ClassVar[float] = 0.0
    # ...
```

#### 4.1.3 RiskAssessor Protocol

```python
@runtime_checkable
class RiskAssessor(Protocol):
    """评估单次 Action 实例的动态风险。

    返回的 RiskAssessment.dynamic 必须 >= action.baseline_risk。
    实现负责保证这一点（基类提供 helper）。
    """

    def assess(self, action: BaseAction, context: AssessmentContext) -> RiskAssessment: ...

@dataclass(frozen=True)
class AssessmentContext:
    """评估器看到的全部信息。"""
    workspace_root: Path
    session_id: str
    recent_observations: list[BaseObservation]   # 最近 N 条 obs，提供决策上下文
    recent_messages: list[AgentMessage]          # 最近 N 条 user/agent 消息
```

**默认实现**：

```python
class BaselineOnlyAssessor:
    """什么都不评估，只把 baseline 作为最终风险。"""

    def assess(self, action, context) -> RiskAssessment:
        return RiskAssessment(
            baseline=action.baseline_risk,
            dynamic=action.baseline_risk,
            final=action.baseline_risk,
            rationale=["baseline only"],
            assessor="baseline",
        )
```

**可选实现**（Phase 3.7 或之后）：

- `LLMRiskAssessor` — 用一个轻量 LLM 看 action 内容（特别是 CodeAction.code、RunCommand.command）输出风险
- `AuditRiskAssessor` — 复用 Phase 2.3 的 AuditAgent，对历史 verdict 加权
- `CompositeAssessor` — 多评估器串联，`final = max(...)`

### 4.2 AutonomyBehavior

完整字段（基于多 agent 协作文档 + 本文档新增的 wait_strategy）：

```python
@dataclass(frozen=True)
class AutonomyBehavior:
    # ── 触发维度 ──────────────────────────────────────
    trigger: Literal["never", "on_risk", "on_uncertainty", "always"] = "on_risk"
    risk_threshold: float = 0.5
    """trigger='on_risk' 时，final_risk >= 此阈值才发 actionable。"""

    confidence_threshold: float = 0.5
    """trigger='on_uncertainty' 时，LLM 置信度低于此值才发 actionable。"""

    # ── 等待维度 ──────────────────────────────────────
    wait_strategy: Literal["sync", "async"] = "sync"
    """sync：阻塞 agent 线程直到响应或超时；
       async：消息发出即继续，响应回流到下一次 ReAct 迭代。"""

    wait_timeout: float | None = 300.0
    """sync 模式下，等待响应的最长秒数。None = 无限等待。
       async 模式下被忽略。"""

    timeout_action: Literal[
        "wait", "proceed_default", "proceed_confident", "skip"
    ] = "proceed_default"
    """sync 模式下超时策略；async 模式下被忽略。"""

    notify_on_proceed: bool = True
    """timeout_action 自行决定后是否补一条 informational 消息告知用户。"""
```

#### 4.2.1 内置预设

| 预设 | trigger | risk_threshold | wait_strategy | timeout | timeout_action | 适合 |
|---|---|---|---|---|---|---|
| `full_auto` | never | — | async | — | — | 批处理、可回滚 |
| `risk_gated` | on_risk | 0.5 | sync | 300 | proceed_default | 日常默认 |
| `careful` | on_risk | 0.3 | sync | 600 | proceed_default | 重要任务 |
| `collaborative` | on_uncertainty | — | sync | None | wait | 复杂、高影响 |
| `manual` | always | — | sync | None | wait | 学习、审计 |

预设是 immutable 模板，用户 fork 出 snapshot 之后可改。

### 4.3 AgentMessage

```python
class AgentMessage(BaseModel):
    """MessageStream 上的一条消息。

    不是 BaseAction，也不是 BaseObservation —— 它是第三个事件家族。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(default_factory=_new_id)
    session_id: str
    task_id: str | None = None
    """同一次 AgentLoop.run() 内所有事件共享的 id；None 表示 session 级、非
    任务态消息（如 resume 时的系统提示）。Phase 3 由 AgentLoop 进入 run() 时
    生成，本 run 期间所有 message 与 event 都打上此值。"""

    agent_id: str = "agent"
    """发起者：Phase 3 永远是 'agent'，Phase 4 起填具体 agent instance id。
    用户回复（response 类型）此处填 'user'，其它人类操作员可填具名值。"""

    parent_message_id: str | None = None
    """如果本消息是对另一条 actionable 的回复，指向那条 message_id。"""

    message_type: Literal["informational", "actionable", "response"]

    content: str
    context: dict[str, Any] = Field(default_factory=dict)
    """结构化补充信息：相关文件路径、代码片段、风险评估等。"""

    # ── actionable 专属 ─────────────────────────────────
    action_options: list[str] = Field(default_factory=list)
    requires_response: bool = False
    timeout_seconds: float | None = None
    risk_assessment: RiskAssessment | None = None
    related_action_id: str | None = None
    """指向 EventStream 上的 BaseAction.event_id，把消息与底层动作钉在一起。"""

    # ── response 专属 ───────────────────────────────────
    response_source: Literal[
        "user", "timeout_default", "timeout_confident", "timeout_skip", "auto_proceed"
    ] | None = None
    response_value: str | None = None

    # ── 通用 ────────────────────────────────────────────
    created_at: datetime = Field(default_factory=_utcnow)
```

#### 4.3.1 三类消息的语义

```
informational
  agent → user
  agent 已完成或正在做某事，告知用户
  不需要响应；持久化用于审计/回放
  例："已修改 auth.py 第 42 行" / "正在分析 5 个候选方案"

actionable
  agent → user
  agent 需要授权、确认、或选择
  根据 autonomy_behavior 决定阻塞/非阻塞
  必有 risk_assessment（驱动 trigger 判定）

response
  user → agent  或  系统超时自动生成
  对 actionable 的回应
  parent_message_id 指向被回应的 actionable
  response_source 区分人工 vs 自动
```

### 4.4 MessageStream Protocol

```python
@runtime_checkable
class MessageStream(Protocol):
    """消息流的读接口。写走 MessageBus。

    所有 list_* 默认按 created_at ASC + 自增 id ASC 排序，保证：
      a) 时间序唯一确定
      b) created_at 同毫秒时仍稳定（id 是单调自增的次序键）
    """

    def get(self, message_id: str) -> AgentMessage | None: ...

    # ── 聚合查询 ────────────────────────────────────────────
    def list_for_session(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]: ...

    def list_for_task(
        self,
        task_id: str,
        *,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        """一次 AgentLoop.run() 内的全部消息，按时间序。

        跨 session 也可查（Phase 4 多 agent 协作场景；Phase 3 必然单 session）。
        """
        ...

    def list_for_agent(
        self,
        agent_id: str,
        *,
        session_id: str | None = None,
        types: Iterable[str] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> Iterator[AgentMessage]:
        """某个 agent 发出的消息。session_id 收紧到具体会话；不传则跨会话。"""
        ...

    # ── 关系查询 ────────────────────────────────────────────
    def pending_actionable(
        self, session_id: str, *, task_id: str | None = None
    ) -> list[AgentMessage]:
        """未收到 response 的 actionable 消息。task_id 可进一步收紧到本次 run。"""
        ...

    def response_for(self, message_id: str) -> AgentMessage | None:
        """快捷查询：某 actionable 的回应（user / 超时自动皆可）。"""
        ...

    def thread(self, message_id: str) -> list[AgentMessage]:
        """取一条 actionable 及其所有回复（含撤回），按时间序。"""
        ...
```

实现：`SqliteMessageStream`，独立 `messages.sqlite` 数据库（详见 §7）。

#### 4.4.1 支持的访问路径

下表把"用户/工程上想拿什么"映射到查询、再映射到承担它的索引。新增任何
查询前，先确认它能落到现有索引上 —— 这是 §7.1 索引集合的不变量。

| 想要 | 查询入口 | 承担索引 |
|---|---|---|
| 一个 session 的全部消息（时间序） | `list_for_session(sid)` | `idx_messages_session_created` |
| 一个 session 内某 task 的消息（时间序） | `list_for_session(sid, ...)` 或 `list_for_task(tid)` | `idx_messages_session_task_created` |
| 一个 task 的全部消息（跨 agent，Phase 4） | `list_for_task(tid)` | `idx_messages_task_created` |
| 一个 session 内某 agent 的消息 | `list_for_agent(aid, session_id=sid)` | `idx_messages_session_agent_created` |
| 某 agent 跨 session 的消息（Phase 4） | `list_for_agent(aid)` | `idx_messages_agent_created` |
| 某 session 的待响应 actionable | `pending_actionable(sid)` | `idx_messages_session_type_created` + `idx_messages_parent` |
| actionable 的回复线索 | `thread(mid)` | `idx_messages_parent` |
| 跨流时间线（events ⊕ messages） | 应用层归并，按 `task_id` + `created_at` 排序 | `idx_messages_task_created` + 事件表 task_id 索引 |

### 4.5 GateDecision

AutonomyGate 的输出：

```python
@dataclass(frozen=True)
class GateDecision:
    verdict: Literal["proceed", "emit_actionable", "skip"]
    """proceed: 直接执行 action，可能伴随 informational 通告
       emit_actionable: 发 actionable 消息，sync 模式下还要等待
       skip: 不执行该 action（autonomy 决定的）"""

    inform_user: bool = False
    """proceed 时是否发一条 informational 告知用户。"""

    suggested_message: str | None = None
    """emit_actionable 时建议的提问内容；None 时由 gate 模板填充。"""

    risk_assessment: RiskAssessment
    """决策依据，记录到日志和事件流。"""
```

---

## 5. 核心组件

### 5.1 AutonomyGate

每个 agent 在执行 Action 前唯一的"是否要打扰用户"决策点。

```python
class AutonomyGate:
    def __init__(
        self,
        behavior: AutonomyBehavior,
        assessor: RiskAssessor,
        confidence_provider: ConfidenceProvider | None = None,
    ): ...

    def check(
        self,
        action: BaseAction,
        context: AssessmentContext,
    ) -> GateDecision: ...
```

#### 决策逻辑

```
1. 评估风险：assessment = assessor.assess(action, context)
2. 按 trigger 分支：
   - never:
       proceed, inform_user = False
   - on_risk:
       if assessment.final >= behavior.risk_threshold:
           emit_actionable
       else:
           proceed, inform_user = behavior.notify_on_proceed and risk > 0
   - on_uncertainty:
       confidence = confidence_provider.get(action) if available else 1.0
       if confidence < behavior.confidence_threshold:
           emit_actionable
       else:
           proceed
   - always:
       emit_actionable
```

`ConfidenceProvider` 是可选钩子（Phase 3 暂不实现，留接口）：从 LLM 输出的 logprobs 或显式 confidence 字段抽取。

### 5.2 MessageBus

真正的 pub/sub，不是轮询。

```python
@runtime_checkable
class MessageBus(Protocol):
    def publish(self, message: AgentMessage) -> None:
        """持久化 + 通知所有订阅者。"""
        ...

    def subscribe(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
    ) -> Subscription:
        """返回一个可读 Subscription；调用方在 with 块内收消息。"""
        ...

    def wait_for_response(
        self,
        message_id: str,
        timeout: float | None,
    ) -> AgentMessage | None:
        """阻塞等待对某条 actionable 的 response；超时返回 None。"""
        ...

class Subscription(Protocol):
    def __iter__(self) -> Iterator[AgentMessage]: ...
    def close(self) -> None: ...
    def __enter__(self) -> Subscription: ...
    def __exit__(self, *exc) -> None: ...
```

#### 5.2.1 默认实现：`InProcessMessageBus`

单进程下的真正总线：

- 内部 `threading.Condition` 协调发布者和等待者
- `publish()` 先写 SQLite，再 `condition.notify_all()`
- `wait_for_response(message_id, timeout)` 走 `condition.wait_for(predicate, timeout)`，predicate 检查 SQLite 中是否已存在 `parent_message_id == message_id` 的 response 行
- `subscribe()` 给 CLI 实时 view 用，内部维护一个增量游标 + 线程安全的队列

**为什么 SQLite + Condition 而不是纯内存队列**：进程重启后，已发的消息能 replay；用户在 agent 思考期间打开 CLI 不丢消息；多进程实现可以平替（详见 §5.2.2）。

#### 5.2.2 跨进程预留

将来如果要"agent 是后台进程，CLI 是另一个进程"：

- `SqliteMessageBus`（poll 版本）：每 N ms 查 SQLite 看新行；implements MessageBus protocol，只是 `wait_for_response` 用轮询。简单但有 latency。
- `RedisMessageBus`：真正跨进程总线，pub/sub。

`InProcessMessageBus` 是 Phase 3 唯一实现，但 Protocol 让升级零成本。

### 5.3 等待协调器（Wait Coordinator）

把 sync/async 等待语义封进单一组件，Loop 不直接用 Bus.wait_for_response：

```python
class WaitCoordinator:
    """根据 AutonomyBehavior，将"已发 actionable"翻译成具体等待行为。"""

    def __init__(self, bus: MessageBus, behavior: AutonomyBehavior): ...

    def handle_actionable(
        self,
        message: AgentMessage,
    ) -> WaitOutcome:
        """
        sync 模式：阻塞至 response 或 timeout，触发 timeout_action。
        async 模式：立即返回 WaitOutcome.PENDING，调用方继续工作。
        """
        ...

class WaitOutcome(Enum):
    GOT_RESPONSE = "got_response"        # sync 模式拿到 response
    TIMED_OUT_PROCEED = "timed_out_proceed"
    TIMED_OUT_SKIP = "timed_out_skip"
    PENDING = "pending"                  # async 模式：丢给后续迭代处理
```

### 5.4 Async 响应回流

async 模式下，agent 不在原地等。响应到达后如何"找到"它？

```
Loop 每个 ReAct iter 开始时：
  1. drained = bus.drain_pending_responses(session_id, since=last_check)
  2. 每条 drained 转成一条 system message 注入 messages 列表
     例："[user-response to 'should we use Tailwind?'] Yes, use Tailwind"
  3. agent 在下一次 LLM 调用看到这些响应，自然把它们 fold 进推理
```

这跟 Phase 2.3 把 audit verdict 注成 system message 的模式一致 —— async 响应也是同一种"系统侧信道告诉模型一些事"。

---

## 6. 控制流

### 6.1 完整流程图

```
┌─ Loop iteration ─────────────────────────────────────────────┐
│                                                              │
│  1. drain_pending_responses → fold async responses           │
│  2. llm.chat(messages) → tool_calls                          │
│  3. for each tool_call:                                      │
│       action = build_action(tool_call)                       │
│                                                              │
│       ┌─ AutonomyGate.check(action) ─────────────────┐       │
│       │  decision.verdict ∈ {proceed, emit, skip}    │       │
│       └────────────────────┬─────────────────────────┘       │
│                            │                                 │
│        ┌───────────────────┼────────────────────┐            │
│        ▼                   ▼                    ▼            │
│     proceed            emit_actionable        skip           │
│        │                   │                    │            │
│        │              bus.publish(msg)          │            │
│        │                   │                    │            │
│        │              wait_coord.handle()       │            │
│        │              ┌────┴──────┐             │            │
│        │              │           │             │            │
│        │           sync         async           │            │
│        │              │           │             │            │
│        │       got/timeout    PENDING           │            │
│        │              │           │             │            │
│        ▼              ▼           ▼             ▼            │
│   runtime.execute  proceed/skip  next iter   next iter       │
│        │           per outcome                               │
│        ▼                                                     │
│   observation → EventStream                                  │
│   (optional informational message after)                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 阻塞模式时序（sync wait）

```
Agent thread                MessageBus               CLI thread
    │                           │                        │
    │ check gate                │                        │
    │                           │                        │
    │ publish(actionable msg)   │                        │
    │ ─────────────────────────▶│  ──── notify ────────▶ │
    │                           │                        │ render to user
    │ wait_for_response(id, T)  │                        │
    │                           │                        │ user types reply
    │                           │ ◀── publish(response) ─│
    │                           │                        │
    │ ◀──── (cond notified) ────│                        │
    │                           │                        │
    │ proceed with action       │                        │
    │ runtime.execute()         │                        │
    │ ...                       │                        │
```

### 6.3 非阻塞模式时序（async ack）

```
Agent thread                MessageBus               CLI thread
    │                           │                        │
    │ check gate                │                        │
    │                           │                        │
    │ publish(actionable msg)   │                        │
    │ ─────────────────────────▶│  ──── notify ────────▶ │
    │                           │                        │ render
    │ continue immediately      │                        │
    │                           │                        │
    │ next ReAct iter           │                        │ user replies later
    │ runtime.execute(...)      │ ◀── publish(response) ─│
    │ ...                       │                        │
    │                           │                        │
    │ next ReAct iter           │                        │
    │ drain_pending_responses() │                        │
    │ ◀──── 1 response ─────────│                        │
    │                           │                        │
    │ inject as system msg      │                        │
    │ llm.chat(... + sys msg)   │                        │
```

### 6.4 timeout 路径（sync 模式）

```
publish(actionable, timeout=300s)
  ↓
wait_for_response 阻塞 300 秒
  ↓
没回应 → timeout_action 决定：
  wait               → 继续等（实际上 wait_timeout=None 才合理，否则不应进这里）
  proceed_default    → 用最保守选项继续（"如何选最保守"由 action 类决定）
  proceed_confident  → 用 LLM 最高置信选项继续（需要 ConfidenceProvider）
  skip               → 跳过该 action，写一条 ErrorObservation
  ↓
若 notify_on_proceed=True，再发一条 informational 告知超时及选择
```

`proceed_default` 和 `proceed_confident` 的实现先用最简策略：

- `proceed_default` = 假定 `action_options[0]`（option list 第一个）
- `proceed_confident` = 跟 default 一样，等 ConfidenceProvider 落地后再分化

### 6.5 LoopResult 变化

```python
# 旧
@dataclass(frozen=True)
class LoopResult:
    final_answer: str
    steps: int
    finished: bool
    stop_reason: str  # "agent_finish" | "no_tool_calls" | "max_steps"

# 新
@dataclass(frozen=True)
class LoopResult:
    final_answer: str
    steps: int
    finished: bool
    stop_reason: str
    # 不再加 awaiting_user —— loop 在 sync wait 内部处理，不向调用方暴露
```

`Session.status.awaiting_user` 变成派生量：

```python
def derive_status(session_id: str, manager: SessionManager, stream: MessageStream) -> SessionStatus:
    stored = manager.require(session_id).status
    if stored == "finished":
        return "finished"
    if stream.pending_actionable(session_id):
        return "awaiting_user"
    return "active"
```

---

## 7. 持久化、并发、失败模式

### 7.1 messages.sqlite Schema

独立数据库，路径 `<workspace>/.code-agent/messages.sqlite`（workspace 级，不是
session 级 —— 跨 session 协作时多个 session 共享同一份消息流读取能力，但行级
带 `session_id` 隔离）。

#### 7.1.1 设计目标

消息表是用户产品体验的核心存储，相比 EventStream（审计层）有更高的读密集度。
要支持四个维度的聚合：

1. **session × 时间** — UI 主时间线："这个会话里发生过什么"
2. **session × task × 时间** — "本次 run 期间发生了什么"（resume / 调试 / 总结）
3. **task × 时间** — Phase 4 跨 agent 时，"这个任务里所有 agent 的对话"
4. **agent × 时间** — Phase 4 时审视某个 agent 的全部输出（含跨会话）

所有查询都带 ORDER BY，单调时序由 `(created_at, id)` 二元组保证（同毫秒打平时
按自增 id 决胜，不依赖 wall clock 精度）。

#### 7.1.2 表结构

```sql
CREATE TABLE IF NOT EXISTS messages (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,    -- 入库次序，时间打平时的 tiebreaker
    message_id            TEXT    NOT NULL UNIQUE,              -- 对外稳定 id（跨 session 全局唯一，见 Q7）
    session_id            TEXT    NOT NULL,
    task_id               TEXT,                                 -- 一次 run 的聚合 id；None 表示 session 级非任务态消息
    agent_id              TEXT    NOT NULL,                     -- 'agent' | 'user' | <具名>
    parent_message_id     TEXT,                                 -- response → actionable 的反向指针
    message_type          TEXT    NOT NULL CHECK(message_type IN ('informational','actionable','response')),
    content               TEXT    NOT NULL,
    context_json          TEXT    NOT NULL DEFAULT '{}',
    action_options_json   TEXT    NOT NULL DEFAULT '[]',
    requires_response     INTEGER NOT NULL DEFAULT 0,
    timeout_seconds       REAL,
    risk_json             TEXT,                                 -- RiskAssessment 序列化（仅 actionable）
    related_action_id     TEXT,                                 -- 指向 EventStream.event_id（仅 actionable）
    response_source       TEXT,                                 -- 仅 response：user/timeout_*/auto_proceed
    response_value        TEXT,                                 -- 仅 response
    created_at            TEXT    NOT NULL                      -- ISO-8601 UTC
);
```

#### 7.1.3 索引集

每条索引都对应 §4.4.1 表里的一条访问路径。命名规范 `idx_messages_<聚合维度...>_<排序键>`。

```sql
-- 主时间线（最常用）
CREATE INDEX idx_messages_session_created
    ON messages(session_id, created_at, id);

-- session 内 task 视图（resume / 单次 run 回放）
CREATE INDEX idx_messages_session_task_created
    ON messages(session_id, task_id, created_at, id);

-- 跨 session 的 task 视图（Phase 4 多 agent）
CREATE INDEX idx_messages_task_created
    ON messages(task_id, created_at, id);

-- session × agent 视图
CREATE INDEX idx_messages_session_agent_created
    ON messages(session_id, agent_id, created_at, id);

-- 跨 session 的 agent 视图（Phase 4）
CREATE INDEX idx_messages_agent_created
    ON messages(agent_id, created_at, id);

-- pending_actionable 加速：session × type，命中后再用 parent 索引反查
CREATE INDEX idx_messages_session_type_created
    ON messages(session_id, message_type, created_at, id);

-- thread / response_for / 撤回链路
CREATE INDEX idx_messages_parent
    ON messages(parent_message_id);

-- 通过 message_id 直接 get
-- 已由 UNIQUE 约束自带索引，无需重复
```

每个 list_* 查询的 ORDER BY 都形如 `ORDER BY created_at, id`，与索引最后两列
对齐 —— SQLite 直接走索引序，不做额外排序。

#### 7.1.4 写入规则

- INSERT 由 `MessageBus.publish()` 唯一持有；外部代码不能直绕 bus 写表
- `task_id` 在 INSERT 前必须由调用方确定（None 也合法）；不允许 INSERT 后回填
- response 类型 INSERT 时校验 `parent_message_id` 必须指向已存在的 actionable
- `(parent_message_id, message_type='response')` 不强制唯一 —— 允许撤回链路追加
  （首条 user response 决定 actionable 结果，后续视为追加事实）；首条由应用
  层通过 `MIN(created_at, id)` 取出，见 §7.3 `DuplicateResponseError`

#### 7.1.5 task_id 在 EventStream 上的镜像

跨流（events ⊕ messages）按 task 归并是核心场景（"本次 run 全貌"），因此
EventStream 也补一个 `task_id` 列：

```sql
ALTER TABLE events ADD COLUMN task_id TEXT;
CREATE INDEX idx_events_task_created ON events(task_id, timestamp, id);
CREATE INDEX idx_events_session_task_created ON events(session_id, task_id, timestamp, id);
```

这是对 3.1 schema 的小扩展，不破坏 §8.1 "EventStream 协议不变"的承诺 —— Protocol
方法签名一行不动，只是底层表多了一列与索引。AgentLoop.run() 进入时生成
`task_id`，注入到 append 时的事件 metadata。

PRAGMA：`journal_mode=WAL` + `synchronous=NORMAL`，跟 EventStream / ThoughtStore 一致。

### 7.2 并发模型

**Phase 3 假设**：单进程，多线程（agent 主循环 + CLI 输入 + 可能的后台计时器线程）。

- SQLite 用 `check_same_thread=False`，每个线程拿同一个连接（autocommit 模式下每条语句独立事务）
- `InProcessMessageBus` 用一把 `threading.Condition` 序列化所有发布与等待
- 写入 SQLite 时按 `session_id` 不分锁 —— SQLite 自己保证 INSERT 的原子性

**当未来要做多进程时**（不是 Phase 3 任务）：

- `SqliteMessageBus` 用 polling on `id` 列（auto-increment 给出全序）
- 或上 Redis / NATS

### 7.3 失败模式

| 失败 | 检测 | 恢复 |
|---|---|---|
| **Bus 进程崩溃** | 不适用（进程内，崩溃 = 整个 agent 崩溃） | session resume 时从 SQLite 重建 pending_actionable，loop 自动重新进入 wait |
| **用户回复重复** | `parent_message_id` 已有 response 时拒绝第二次 | 第二次 publish 抛 `DuplicateResponseError`；CLI 显示 "已回应，被忽略" |
| **超时与回复几乎同时** | 用 SQLite UNIQUE 约束 + 应用层 race 处理 | 先到的胜利；后到的写入失败时，应用层捕获并丢弃 |
| **agent 在 wait 中收到新 user message（非回复）** | bus.subscribe 捕获 informational 类型的 user-originated msg | 注入下一次 LLM context；不打断当前 wait |
| **session 重启后有未答 actionable** | resume 时检查 pending_actionable | 恢复 sync wait（等用户）；如果原本是 async，丢给 drain 处理 |

### 7.4 用户撤回

用户希望"刚才那条不算了"：

```
publish(message_type=response, parent_message_id=<actionable_id>,
        response_source=user, response_value="<RETRACT>")
```

agent 收到 `<RETRACT>` 时按"用户拒绝授权"处理（等同 timeout_action=skip）。先用约定字符串，等需要再做正式 retract 字段。

---

## 8. 与已有架构的衔接

### 8.1 EventStream Protocol 不变，schema 微调

- BaseAction / BaseObservation / EventStream Protocol / SqliteEventStream **接口** 一行不改
- 底层表新增 `task_id TEXT` 列与对应索引（见 §7.1.5）—— Protocol 方法签名不变，
  调用方无感知；老数据 `task_id` 为 NULL，依然可读
- `SqliteEventStream.append()` 新增可选关键字 `task_id: str | None = None`，
  旧调用方不传则保持 NULL
- AgentMessage 是新家族，自己的存储、自己的索引
- 关联：
  - actionable 消息的 `related_action_id` 指向 EventStream 上的 `action.event_id`，
    把"消息"钉到具体"动作"
  - 同一次 run 的 events 与 messages 共享 `task_id`，replay 工具能跨流按时间序归并

### 8.2 AgentLoop 改动

```python
@dataclass
class AgentLoop:
    # 已有
    llm: LLMClient
    runtime: Runtime
    tools: list[Tool[Any, Any]]
    event_stream: EventStream
    thought_store: ThoughtStore
    auditor: AuditAgent | None

    # 新增（都有合理默认）
    autonomy_behavior: AutonomyBehavior = field(default_factory=lambda: AutonomyBehavior())
    message_bus: MessageBus | None = None
    message_stream: MessageStream | None = None
    risk_assessor: RiskAssessor = field(default_factory=BaselineOnlyAssessor)
    session_id: str = "default"

    # 内部派生
    _gate: AutonomyGate = field(init=False)
    _wait_coord: WaitCoordinator | None = field(init=False)
```

行为：

- `message_bus is None` 时退化为 Phase 2 行为（gate 永远 proceed，无消息流）。便于回归测试和 CI。
- `message_bus` 非 None 时启用完整流程；session_id 必填且对齐 SessionManager。

**task_id 生命周期**：

```python
def run(self, instruction: str) -> LoopResult:
    task_id = _new_id()                       # 入口生成
    self._current_task_id = task_id           # 整段 run 共享
    self.event_stream.append(                 # 首事件即带 task_id
        TaskStartAction(instruction=instruction),
        task_id=task_id,
    )
    try:
        ...                                   # ReAct 循环；每次 append 与 publish 都带 task_id
    finally:
        self._current_task_id = None
```

- AgentLoop 内部的所有 `event_stream.append(...)` 与 `message_bus.publish(...)`
  都从 `self._current_task_id` 取值；调用点无需关心
- 一次 run 中如果触发自我递归（Phase 4 子任务派发），子任务用新的 task_id，
  在 `parent_task_id` 上挂当前 id（schema 留位 —— Phase 3 不开此字段）

### 8.3 Session 变化

```python
# session.py
class Session:
    # 新增 path 属性
    @property
    def messages_db_path(self) -> Path:
        # 注意：messages 是 workspace 级，不是 session 级
        return self.layout.workspace_messages_db
```

`WorkspaceLayout`：

```python
@property
def workspace_messages_db(self) -> Path:
    return self.meta_dir / "messages.sqlite"
```

### 8.4 CLI 改动（Phase 3 后段）

CLI 的具体 UI 不在本文档定，但关键约束：

- 必须支持非阻塞 stdin（用户输入 + agent 发消息要并发显示）
- pending actionable 必须可枚举（`/pending` 命令）
- 用户回复要能精准对到一条 actionable（默认回复"最新一条"，可显式 `/reply <id>`）

实现栈倾向：`prompt_toolkit` 的 `Application` 模式（split layout：上方消息流、下方输入条），但允许第一版用纯 stdlib 实现。

---

## 9. Phase 3 切片重排

旧切片（已废）：

```
3.2 AskUser 工具 + 可恢复 loop（awaiting_user 终止状态）   ← 废
3.3 CLI chat 交互式入口 + session list/show/resume        ← 重定义
```

新切片：

| # | 名称 | 内容 | 验收 |
|---|---|---|---|
| **3.1** ✅ | Session/Workspace/SqliteEventStream | 已完成 | — |
| **3.2** | Risk model + AutonomyBehavior | RiskScore / RiskAssessment / BaselineOnlyAssessor / AutonomyBehavior + 预设；BaseAction.baseline_risk；附录 B 标定 | 各 Action 类有合理 baseline；pytest 覆盖评估器接口 |
| **3.3** | AgentMessage + MessageStream + SqliteMessageStream | AgentMessage Pydantic 模型（含 task_id）；MessageStream Protocol（含 list_for_session/list_for_task/list_for_agent/pending_actionable/thread）；独立 messages.sqlite + 完整索引集（§7.1.3）；EventStream 加 task_id 列与索引（§7.1.5） | round-trip 持久化；四个聚合维度（session/task/agent/时间）查询正确；同毫秒消息按入库 id 决胜稳定；pending_actionable 在有 / 无 task_id 收紧下都对；跨流按 task_id 归并样例通过 |
| **3.4** | InProcessMessageBus（含 wait_for_response） | threading.Condition + SqliteMessageStream；publish/subscribe/wait_for_response；多线程压力测试 | 并发 publish/subscribe 无丢消息；wait_for_response 在 timeout / 响应到达 / spurious wake 下行为正确 |
| **3.5** | AutonomyGate + WaitCoordinator | gate.check 决策矩阵；WaitOutcome；timeout_action 四分支 | 单元测试覆盖 trigger × wait_strategy × timeout_action 笛卡尔积关键格 |
| **3.6** | AgentLoop 集成 + CLI 最小可用版 | loop 调 gate；async 模式 drain_pending_responses；CLI prompt_toolkit 双栏；`/pending`、`/reply` 命令 | 端到端：用户开 session → agent 想跑高风险代码 → CLI 弹确认 → 用户授权 → 继续 |
| **3.7** | LLMRiskAssessor + 复用 AuditAgent | 用一个轻量 LLM 评估 CodeAction.code 的风险；CompositeAssessor | 已有审计样本回归：风险评估与人工标注一致率 > 80% |
| **3.8** | session 派生 status + CLI session 子命令 | derive_status；`code-agent list/show/resume <id>` | UI 列表正确显示 awaiting_user；resume 自动回到正确 wait 状态 |
| **3.9** | PlanTool | workspace/.session/plan.md 读写工具；loop system message 注入 | LLM 维护 plan，进展可见；token 预算 < 500 |
| **3.10** | shared/ append-only 协作 | shared/ 子目录约束；Workspace 跨根支持；按 session-id 命名 from-子目录 | session A 写 shared/from-A/x.json；session B 读到；A 不能写 from-B |
| **3.11** | in-session RAG over EventStream | 索引 EventStream actions/observations/messages；BM25 / 向量；retrieve_relevant 工具 | 给定 query，召回准确率 > 70%（人工标注 20 例） |
| **3.12** | cross-session RAG（可选） | 跨 session retrieve；隐私边界（默认能搜还是默认不能） | 待 3.11 完成后评估收益 |
| **3.13** | Conversation summarization | 当 token 接近预算时压缩历史；保留关键决策与未答问题 | 长任务（50+ steps）token 不爆，关键事实不丢失 |

每片都对应一个 commit / 子分支，每片都自带测试与门禁。3.2–3.6 是核心交互层，必须连续做完才完整可用；3.7 之后可独立排期。

---

## 10. 待定问题

| # | 问题 | 倾向 |
|---|---|---|
| Q1 | `proceed_default` 的具体语义 —— 哪个是"最保守"？ | Action 类提供 `default_safe_choice() -> str` 方法，由具体 Action 决定；CodeAction 默认拒绝执行 |
| Q2 | `notify_on_proceed=False` 时，超时自决策的事实是否还要落 EventStream？ | 落，但不发 informational message；EventStream 是审计层，不可静默 |
| Q3 | actionable 消息的 timeout 是 message-level 还是 behavior-level？ | message 可覆盖 behavior，缺省取 behavior；同一 session 内不同 action 可能合理需要不同 timeout |
| Q4 | LLMRiskAssessor 用什么模型？跟 AuditAgent 共享一个还是独立？ | 独立配置（AUDIT_MODEL / RISK_MODEL），但允许指向同一个；评估比 audit 更频繁，建议更便宜的模型 |
| Q5 | 消息流的"清理"策略 —— 跑了 1 万条 informational 怎么办？ | 不清理；3.11 RAG 解决"老消息怎么找"；存储成本可接受 |
| Q6 | CLI 在 sync wait 期间能否接受新 user instruction（非回复）？ | 能。新 instruction 走 informational 类型从 user 发到 agent，下一次 LLM call 看到；不打断当前 wait |
| Q7 | 同一个 message_id 是否要求全局唯一（跨 session）？ | 是。便于跨 session 引用与日志 trace |
| Q8 | risk_threshold 和 confidence_threshold 是否需要独立的 telemetry，方便后续调优？ | 是，但不在 3.x 预算内；记 todo |

---

## 附录 A — 类型速查

| 类型 | 模块（计划）| 职责 |
|---|---|---|
| `RiskScore` | `code_agent.interaction.risk` | float ∈ [0,1] alias |
| `RiskAssessment` | `code_agent.interaction.risk` | baseline + dynamic + final + rationale |
| `RiskAssessor` (Protocol) | `code_agent.interaction.risk` | `assess(action, context) -> RiskAssessment` |
| `BaselineOnlyAssessor` | `code_agent.interaction.risk` | 默认实现 |
| `AssessmentContext` | `code_agent.interaction.risk` | 评估器输入 |
| `AutonomyBehavior` | `code_agent.interaction.autonomy` | 自主度配置 |
| `AutonomyGate` | `code_agent.interaction.autonomy` | 决策入口 |
| `GateDecision` | `code_agent.interaction.autonomy` | 决策结果 |
| `WaitCoordinator` | `code_agent.interaction.autonomy` | sync/async 等待协调 |
| `WaitOutcome` | `code_agent.interaction.autonomy` | 等待结果枚举 |
| `AgentMessage` | `code_agent.interaction.message` | 消息流单条事件（含 task_id） |
| `MessageStream` (Protocol) | `code_agent.interaction.message` | 读接口 — list_for_session / list_for_task / list_for_agent / pending_actionable / thread |
| `SqliteMessageStream` | `code_agent.interaction.message` | 默认读实现 |
| `MessageBus` (Protocol) | `code_agent.interaction.bus` | 写接口 + 等待原语 |
| `Subscription` (Protocol) | `code_agent.interaction.bus` | 增量订阅 |
| `InProcessMessageBus` | `code_agent.interaction.bus` | 默认实现 |
| `ConfidenceProvider` (Protocol) | `code_agent.interaction.autonomy` | 可选钩子，Phase 3 不实现 |

注：`code_agent.interaction.*` 是新顶级包；不污染现有 `core` / `memory` / `audit`。

---

## 附录 B — 风险基线参考表

```
0.0   ReadFileAction        纯读，无副作用
0.0   ListDirAction         同上
0.1   AgentFinishAction     仅控制流，不写不删
0.3   WriteFileAction       写 workspace 内，可覆盖
0.3   AskUserMessage        发消息（控制流，但消耗用户注意力）
0.4   PlanWriteAction       写 plan.md（meta，影响后续推理）
0.5   CodeAction            任意 Python 执行，受沙箱限制但可触达网络（如配置允许）
0.5   RunCommandAction      shell 执行，类似上
0.6   FileDeleteAction      删除 workspace 内文件，可逆性差
0.7   SharedWriteAction     写 workspace/shared/ 内（影响其他 session）
0.8   PackageInstallAction  改变运行环境（虽然在沙箱内）
0.9   NetworkRequestAction  对外发起请求（如 Phase 4 引入）
1.0   SystemModifyAction    修改沙箱外的系统配置（保留位，目前 Action 集合不允许）
```

baseline 是**类静态下限**；同样 `RunCommandAction("ls")` 和 `RunCommandAction("rm -rf /")` 类 baseline 都是 0.5，运行时由 LLMRiskAssessor 把后者抬到 0.95+。

用户阈值的最佳实践默认（对应预设）：

```
full_auto         risk_threshold = 1.01   （永不触发）
risk_gated        risk_threshold = 0.5    （写 / 执行级别开始问）
careful           risk_threshold = 0.3    （写文件就开始问）
collaborative     用 confidence，不用 risk threshold
manual            risk_threshold = 0.0    （什么都问）
```

用户在自己的 session 里可以覆盖任何值。

---

## 修订历史

| 版本 | 日期 | 作者 | 改动 |
|---|---|---|---|
| v1.0 | 2026-05-08 | claude + zhanghao | 初版；落地多 agent 协作架构文档的 Phase 3 实现层 |
| v1.1 | 2026-05-08 | claude + zhanghao | 消息表重设计：AgentMessage 新增 task_id；MessageStream Protocol 增加 list_for_task / list_for_agent / thread；§7.1 重写 schema、加 §7.1.1–7.1.5（设计目标、表结构、索引集、写入规则、EventStream task_id 镜像）；§4.4.1 列支持的访问路径与索引承担表；§8.1 与 §8.2 补 task_id 注入路径；3.3 切片验收点更新 |
