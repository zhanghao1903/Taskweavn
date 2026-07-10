# 多 Agent 协作架构设计

> 版本 v1.1 · 2026-06-24
>
> Status: historical architecture concept reference
>
> Product 1.1 alignment: 本文保留多 Agent 协作的早期理念来源。当前 Product 1.1 已落地的是 Runtime Input Router、task-scoped Default Agent execution、Agent LLM resolver、read-only inquiry 和 command-backed contract revision；完整 Agent Manager、dynamic assignment、custom Agent protocol 仍是后续扩展。当前事实以 [overview.md](overview.md)、[agent.md](agent.md)、[task.md](task.md) 和 [bus.md](bus.md) 为准。

---

## 目录

1. [设计核心理念](#1-设计核心理念)
2. [消息流模型：用户协作的基础](#2-消息流模型用户协作的基础)
3. [自主度系统](#3-自主度系统)
4. [对话式编排设计](#4-对话式编排设计)
5. [约束驱动的 UI 编排](#5-约束驱动的-ui-编排)
6. [核心数据结构](#6-核心数据结构)
7. [系统整体架构](#7-系统整体架构)
8. [渐进式约束演进路线](#8-渐进式约束演进路线)
9. [关键设计权衡](#9-关键设计权衡)

---

## 1. 设计核心理念

### 1.1 两个核心原则

本架构围绕两个核心理念展开，它们共同决定了多 agent 与用户协作的方式：

**原则一：消息流替代打断（Stream over Interrupt）**

传统 human-in-the-loop 系统依赖"暂停-等待-恢复"的阻塞式打断模型，系统主导节奏，用户被迫响应。本架构将其替换为**消息流模型**：agent 向消息流发送请求，用户可以回应，也可以不回应，agent 的等待行为由自主度配置决定。用户始终是主动方，不被系统打断。

**原则二：约束驱动的用户编排（Constraint-driven Orchestration）**

不强迫用户理解图结构，而是让 LLM 作为编排设计者，在约束边界内生成合法的 agent 协作图。用户通过自然语言描述意图，通过 UI 进行局部微调。约束本身是可版本化、可演进的，随着系统成熟度提升逐步松绑。

### 1.2 核心转变

```
旧模型                          新模型
──────────────────────────────────────────────────────
interrupt → pause → resume      消息流 + 响应等待策略
用户填写编排配置                  对话描述意图 → LLM 生成草稿
约束是事后校验                    约束是生成时上下文
自由度是默认，限制是补丁           约束是默认，松绑需要数据依据
```

---

## 2. 消息流模型：用户协作的基础

### 2.1 模型概述

Agent 执行过程中产生的所有与用户相关的通信，统一流向一条**消息流（Message Stream）**。用户可以实时观看、随时介入，但从不被强制阻塞。

```
┌─ Agent 执行层 ──────────────────────────────────────┐
│  Planner → Executor → Auditor → ...                 │
│      ↓          ↓         ↓                         │
└──────────────────────────────────────────────────────┘
              ↓  ↓  ↓
┌─ Message Stream ────────────────────────────────────┐
│  [INFO]  Planner: 已生成执行计划，共 5 步             │
│  [ASK]   Executor: 即将删除文件 config.py，确认？    │
│  [INFO]  Executor: 已修改 auth.py (第 42 行)         │
│  [WARN]  Auditor: 发现潜在安全漏洞，建议人工复查      │
└──────────────────────────────────────────────────────┘
              ↑
         用户随时可回复，也可不回复
```

### 2.2 消息的两种类型

| 类型 | 含义 | Agent 行为 |
|------|------|----------|
| **Informational** | 告知用户 agent 做了什么 | 发送后继续执行，不等待 |
| **Actionable** | 请求用户输入或确认 | 根据自主度配置决定等待策略 |

### 2.3 消息结构

```python
@dataclass
class AgentMessage:
    id: str
    agent_id: str
    message_type: Literal["informational", "actionable"]
    content: str
    context: dict               # 相关代码片段、文件路径等
    action_options: list[str]   # 仅 actionable 类型，提供给用户的选项
    requires_response: bool
    created_at: datetime
    timeout_seconds: float | None
```

### 2.4 "完全不打断"状态

当用户将自主度设为最高时，所有 Actionable 消息都配置了超时自动 proceed，消息流退化为**只读执行日志**。用户随时可以查看，但没有任何消息阻塞 agent 执行。

```
自主度 = 1.0  →  消息流 = 执行日志  →  用户完全不被打断
自主度 = 0.0  →  消息流 = 协作频道  →  每个关键决策用户都参与
```

这是用户的主动选择，系统只负责如实呈现任务质量与自主度的关系。

---

## 3. 自主度系统

### 3.1 自主度的真实含义

自主度不是一个魔法数字，而是对"agent 遇到不确定时如何行动"的精确描述。核心是两个维度：

- **触发维度**：什么情况下 agent 认为需要用户介入
- **等待维度**：发出请求后，等多久、等不到时怎么办

### 3.2 AutonomyBehavior 配置

```python
@dataclass
class AutonomyBehavior:
    # 触发维度：何时向消息流发送 Actionable 消息
    trigger: Literal[
        "never",            # 从不，所有消息都是 Informational
        "on_risk",          # 仅高风险操作（文件删除、执行命令等）
        "on_uncertainty",   # LLM 置信度低于阈值时
        "always",           # 每个关键操作都请求确认
    ]
    confidence_threshold: float  # 0.0~1.0，仅 on_uncertainty 生效

    # 等待维度：Actionable 消息发出后的等待策略
    wait_timeout: float | None   # 秒，None = 无限等待
    timeout_action: Literal[
        "wait",              # 继续等待（低自主度默认）
        "proceed_default",   # 超时后用最保守选择继续
        "proceed_confident", # 超时后用 LLM 最高置信选择继续
        "skip",              # 跳过该动作
    ]
    notify_on_proceed: bool      # 超时自行决定后是否告知用户
```

### 3.3 预设自主度档位

| 档位 | trigger | wait_timeout | timeout_action | 适合场景 |
|------|---------|--------------|----------------|---------|
| **全自主** | never | — | — | 批处理、可回滚任务 |
| **风险确认** | on_risk | 300s | proceed_default | 日常使用默认 |
| **协作模式** | on_uncertainty | None | wait | 复杂、高影响任务 |
| **全确认** | always | None | wait | 学习、审计场景 |

### 3.4 AutonomyGate：决策入口

每个 agent 在执行操作前经过 AutonomyGate，统一判断是否需要发送消息：

```python
class AutonomyGate:
    def check(
        self,
        action: CodeAction,
        confidence: float,
        behavior: AutonomyBehavior,
    ) -> GateDecision:
        if behavior.trigger == "never":
            return GateDecision.PROCEED
        if action.is_high_risk and behavior.trigger in ("on_risk", "always"):
            return GateDecision.SEND_ACTIONABLE
        if confidence < behavior.confidence_threshold:
            return GateDecision.SEND_ACTIONABLE
        return GateDecision.PROCEED
```

### 3.5 质量与自主度的 Tradeoff

系统应在 UI 中明确呈现这一权衡，而不是隐藏它：

```
自主度高  ████████░░
  ✓ 执行不被打断，速度快
  ✓ 用户认知负担低
  ✗ 歧义场景 agent 自行猜测
  ✗ 错误可能在用户不知情时累积

自主度低  ██░░░░░░░░
  ✓ 关键决策用户全程参与
  ✓ 错误率低，可控性强
  ✗ 需要用户持续关注消息流
  ✗ 任务速度依赖用户响应时间
```

选择权完全在用户，系统不做道德评判。

---

## 4. 对话式编排设计

### 4.1 LLM 作为编排设计者

用户不需要理解图结构。用户描述意图，**Orchestration Designer**（一个 meta-agent）在约束边界内生成合法的 agent 协作图，用户只需选择和微调。

```
用户自然语言意图
       ↓
Orchestration Designer (meta-agent)
  输入：用户意图 + ConstraintProfile + ToolRegistry
  输出：OrchestrationDraft（合法图结构 + 节点配置）
       ↓
UI 渲染图结构
       ↓
用户局部微调（选择题，不是填空题）
```

**关键原则：约束不是事后校验，而是生成时的上下文。** LLM 在约束边界内生成，输出天然合法，不会出现"UI 允许但后端拒绝"的不一致。

### 4.2 生成的三个阶段

**阶段一：意图解析**

```
用户: "我想要一个能审计代码安全漏洞并自动修复的系统"

解析输出:
  核心能力: [代码读取, 漏洞分析, 修复执行, 验证回环]
  风险识别: 修复执行 = 高风险，需要用户确认
  约束映射: 需要 auditor 节点，需要修复前 interrupt
```

**阶段二：约束内图生成**

LLM 接收 ConstraintProfile 作为 prompt 上下文，在合法拓扑范围内生成图结构，无需后端 validator 二次校验。

**阶段三：能力分配**

每个 agent 节点从 ToolRegistry 中**选择**工具子集，不能生成或引入 Registry 之外的工具。工具集是系统的安全底线。

### 4.3 OrchestrationDraft 结构

```python
@dataclass
class OrchestrationDraft:
    nodes: list[AgentNodeDraft]
    edges: list[EdgeDraft]
    rationale: str                    # LLM 解释设计理由，展示给用户

@dataclass
class AgentNodeDraft:
    id: str
    agent_type: AgentType
    display_name: str
    description: str                  # 此节点在本编排中的职责
    tool_set: list[ToolRef]           # 从 ToolRegistry 选出的子集
    autonomy_behavior: AutonomyBehavior
    suggested_alternatives: list[AgentType]  # 用户可替换的备选类型
```

`suggested_alternatives` 让节点替换成为**选择题**，用户不需要知道有哪些 agent 类型。

### 4.4 对话即 Diff，不是全量重生成

用户对草稿的反馈触发局部修改，而不是重新生成整张图：

```
用户: "让 executor 更自主一点"

DraftPatch:
  target_node: "executor"
  changes:
    autonomy_behavior.trigger: "on_uncertainty" → "on_risk"
    autonomy_behavior.confidence_threshold: 0.7 → 0.4
  reason: "降低打断频率，遇到不确定时优先尝试而非询问"
```

UI 高亮变更节点，用户看到的是 diff，不需要每次重新理解整张图。

### 4.5 ToolRegistry：封闭的工具集

```python
class ToolRegistry:
    tools: dict[ToolId, ToolSpec]
    compatible_tools: dict[AgentType, list[ToolId]]  # 预定义兼容关系

    def suggest_for(
        self,
        agent_type: AgentType,
        intent_keywords: list[str],
    ) -> list[ToolSpec]:
        # 从 compatible_tools 按相关性排序返回
        # LLM 从此列表选择，不能引入列表外工具
```

---

## 5. 约束驱动的 UI 编排

### 5.1 分层配置模型

```
Layer 3: 自定义 DAG（高级用户）
  用户在约束范围内自由连接 agent 节点，调整任意参数

Layer 2: Preset + 参数调节（中级用户）
  选择最佳实践模板，通过旋钮调整关键参数

Layer 1: Preset 直选（普通用户）
  Auto-pilot / Co-pilot / Manual / Audit-Focus
```

三层最终 normalize 到同一个 `OrchestrationConfig`，系统内部无差别处理。

### 5.2 ConstraintProfile：约束是一等公民

```python
@dataclass
class ConstraintProfile:
    version: str

    # 节点维度：用户能放哪些 agent
    allowed_agent_types: set[AgentType]

    # 连接维度：允许哪些边
    allowed_edges: list[EdgeRule]         # (src_type, dst_type, condition)
    forbidden_patterns: list[Pattern]     # 如：禁止 executor→executor 直连

    # 组合维度：整体约束
    required_nodes: set[AgentType]        # 如：auditor 永远必须存在
    max_parallel_branches: int

    # 元信息：每条约束的存在理由
    rationale: dict[str, str]             # constraint_key → 失败模式描述
```

`rationale` 不是注释，是**松绑决策的输入**：知道移除某条约束是在赌什么失败模式。

### 5.3 约束在 UI 中的体现

约束不是报错墙，而是**自然的边界感**：

- 节点 palette 只显示 `allowed_agent_types`，被禁止的节点根本不存在，不是灰掉
- 连接线拖拽时实时校验 `allowed_edges`，非法连接在拖拽过程中弹开，不是提交时报错
- 参数面板只渲染当前约束层级开放的配置项，其他参数用系统默认值静默填充

### 5.4 内置最佳实践 Preset

| Preset | 拓扑 | 自主度默认 | 适合场景 |
|--------|------|-----------|---------|
| **Auto-pilot** | sequential | 高（on_risk） | 批量处理，不需要陪跑 |
| **Co-pilot** | hierarchical | 中（on_uncertainty） | 日常开发辅助 |
| **Manual** | sequential | 低（always） | 学习、敏感操作 |
| **Audit-Focus** | DAG + 回流 | 中 | 代码审计 + 自动修复 |

Preset 是**只读模板**，用户选择 Preset 实际上 fork 出一个 snapshot，修改发生在 fork 上，随时可以 diff 或 reset。

---

## 6. 核心数据结构

### 6.1 完整配置层级

```
OrchestrationConfig
├── preset: OrchestrationPreset | None
├── constraint_profile: ConstraintProfile
├── nodes: list[AgentNodeConfig]
│   ├── id, agent_type, display_name
│   ├── tool_set: list[ToolRef]
│   └── autonomy_behavior: AutonomyBehavior
│       ├── trigger
│       ├── confidence_threshold
│       ├── wait_timeout
│       ├── timeout_action
│       └── notify_on_proceed
└── edges: list[EdgeConfig]
    ├── src, dst
    └── condition: EdgeCondition | None
```

### 6.2 消息流结构

```
MessageStream
└── messages: list[AgentMessage]
    ├── id, agent_id, created_at
    ├── message_type: "informational" | "actionable"
    ├── content, context
    ├── action_options: list[str]
    ├── requires_response: bool
    └── response: UserResponse | AutoResponse | None
        ├── source: "user" | "timeout_default" | "timeout_confident"
        ├── value: str
        └── responded_at: datetime
```

---

## 7. 系统整体架构

```
┌─ 用户层 ──────────────────────────────────────────────────────┐
│                                                               │
│  ┌─ 编排设计（一次性）─────────┐   ┌─ 任务执行（实时）──────┐  │
│  │ 对话描述意图                │   │ 消息流面板             │  │
│  │ 查看/调整 OrchestrationDraft│   │ [INFO] agent 动作日志  │  │
│  │ 配置自主度旋钮              │   │ [ASK]  确认请求        │  │
│  └─────────────────────────────┘   │ [WARN] 异常通知        │  │
│                                    └────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
         ↑ Draft                              ↑↓ Messages
┌─ 编排层 ──────────────────────────────────────────────────────┐
│                                                               │
│  OrchestrationDesigner          MessageStream                 │
│  (meta-agent)                   + AutonomyGate               │
│    ├── 意图解析                                               │
│    ├── 约束内图生成                                           │
│    └── 工具集匹配               ConstraintValidator           │
│                                 (加载时静态分析)              │
└───────────────────────────────────────────────────────────────┘
         ↑ ConstraintProfile              ↑ OrchestrationConfig
┌─ 执行层 ──────────────────────────────────────────────────────┐
│                                                               │
│  Agent Graph Runtime                                          │
│    ├── Planner Agent                                          │
│    ├── Executor Agent  ──→ AutonomyGate ──→ MessageStream     │
│    ├── Auditor Agent                                          │
│    └── [用户自定义节点]                                       │
│                                                               │
│  ToolRegistry (封闭工具集)                                    │
└───────────────────────────────────────────────────────────────┘
```

---

## 8. 渐进式约束演进路线

约束不是永久限制，而是有数据依据的阶段性护栏。

### 松绑决策框架

```
松绑一条约束需要同时满足：

1. 成功率数据    当前约束下 N 次执行，成功率 > threshold
2. 失败归因      当前失败案例中，该约束不是根因
3. 用户收益估算  松绑后可解锁的 use case 数量与重要性
4. 降级路径      失败率上升时，如何快速回收该自由度

指标：约束价值密度 = Δ失败率 / Δ可表达 use case 数
     优先松绑价值密度低的约束（限制多、收益少）
```

### 三阶段演进

**v1：高护栏（当前）**
- 允许节点：Planner / Executor / Auditor（三种固定）
- 允许连接：两条固定边 + 可选回流边
- 并行分支：禁止
- 暴露参数：仅 autonomy_behavior + tool 开关
- 目标：成功率 > 90%，用户 0 学习成本

**v2：松绑拓扑**
- 开放并行分支（max = 2）
- 开放自定义节点名称
- LLM 可生成 DAG 而不只是 sequential
- 依据：v1 成功率数据 + 失败归因不指向拓扑问题

**v3：松绑工具**
- 开放自定义工具接入（用户提供 Tool spec）
- 开放 ToolRegistry 动态扩展
- 依据：用户反馈中最高频"希望有但没有"的工具类型

---

## 9. 关键设计权衡

### 9.1 灵活性 vs 成功率

早期约束严格牺牲灵活性，换取高成功率。这是**主动选择**，不是技术限制。随着数据积累，有依据地松绑，不做功能堆砌。

### 9.2 用户控制 vs 系统复杂度

把打断控制权交给用户，意味着系统需要处理"用户不回应"的各种超时情形。`AutonomyBehavior.timeout_action` 的四种策略覆盖了主要场景，复杂度可控。

### 9.3 LLM 生成 vs 用户手动

对话式生成的最大风险是 LLM 误解意图。缓解策略：
- Draft 生成后展示 `rationale`，用户可以验证意图是否被正确理解
- 迭代用 Patch 而非全量重生成，每次变更范围小、可审查
- 最终编排在 UI 中完全可见，用户随时可以直接调整

### 9.4 消息流 vs 传统打断

消息流模型的代价是：用户需要主动关注流，而不是被动被提醒。缓解策略：
- 支持通知推送（Actionable 消息可触发系统通知）
- 消息流支持过滤（用户可只看 Actionable，隐藏 Informational）
- 流内消息提供快捷操作，降低响应成本

---

## 附录：本文涉及的核心类型速查

| 类型 | 职责 |
|------|------|
| `AutonomyBehavior` | 定义 agent 自主度：触发条件 + 等待策略 |
| `AutonomyGate` | 每次操作前的自主度决策入口 |
| `AgentMessage` | 消息流中的单条消息，Informational 或 Actionable |
| `MessageStream` | 全局消息流，agent 与用户协作的唯一通道 |
| `ConstraintProfile` | 当前版本的编排约束集合，含 rationale |
| `OrchestrationDesigner` | meta-agent，将用户意图转化为合法 OrchestrationDraft |
| `OrchestrationDraft` | LLM 生成的编排草稿，含图结构 + 节点配置 + rationale |
| `DraftPatch` | 用户反馈触发的局部修改，对话迭代的最小单元 |
| `ToolRegistry` | 封闭工具集，LLM 只能选择不能创造 |
| `OrchestrationPreset` | 内置最佳实践模板，用户 fork 后修改 |
