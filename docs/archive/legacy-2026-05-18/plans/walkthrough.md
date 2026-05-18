# Plan: 端到端 Walkthrough

> 多 Agent 协作架构 · 端到端示例文档计划 · v0 · 2026-05-10

---

## 1. 背景

评审里把"没有端到端 trace"列为**最严重的直观性问题**。读者必须靠脑补串联组件，没有一个具体例子作为思考锚点。

参考评审：[architecture/review.md](../architecture/review.md) 第 3.2.1 节（缺少端到端 trace ⭐ 最严重的问题）。

---

## 2. 目标

写一份完整的"用户输入一句话 → 系统跑完整个流程"的可读 trace，让读者：

- **看到组件如何协作**（不只是组件各自定义）
- **看到数据如何流动**（task / result / event 在哪生在哪死）
- **看到决策如何发生**（autonomy gate / scheduler decision / IO conflict）
- **看到失败如何处理**（至少一个失败分支）
- **看到 UI 如何呈现**（消息流 + ActionCard 怎么走）

**非目标：**
- 不是 API 文档（API 在各组件文档里）
- 不是用户指南（用户视角在 [user-guide.md](user-guide.md)）
- 不要写得像 reference manual——读起来像故事

---

## 3. 待回答的开放问题

| # | 问题 | 倾向答案 |
|---|------|---------|
| 1 | 选什么场景作为主例？ | 代码审计 + 修复（典型、覆盖面广） |
| 2 | 写多少个场景？ | 1 主 + 2 短 |
| 3 | 详细到什么粒度？ | 事件级，每个组件至少出场一次 |
| 4 | 是否包含 LLM prompt 实例？ | 关键节点放精简片段 |
| 5 | 写中文还是双语？ | 中文（与其他文档一致），关键术语保留英文 |
| 6 | 文档形式？ | 故事化叙述 + 图 + 事件流表格 |

---

## 4. 主例：代码审计 + 修复（详细版）

### 4.1 场景设定

```
用户：「审计 src/auth.py 的安全性，发现高危问题就修，给我一个总结报告」

预期参与组件：
  - Session（资源容器）
  - Root Task（用户请求 → 初始任务）
  - 子任务：审计、修复、综合
  - Agents：AuditAgent / FixerAgent / SummaryAgent
  - TaskBus（v2，含 IOScope）
  - AutonomyGate（修复需用户确认）
  - EventStream（全流程记录）
  - CostAggregator（成本归集）
```

### 4.2 走完整流程

要展示的关键时刻（按时间顺序）：

```
T+0:00.000   Session 创建
T+0:00.150   Root Task 派发
T+0:00.180   Orchestrator 拆分为 3 个子任务
T+0:00.250   AuditAgent 开始
T+0:08.500   AuditAgent 发现高危问题 → 派生 FixerTask
T+0:09.100   AutonomyGate 阻塞 → ActionCard 推送
T+0:25.000   用户确认「允许修复」
T+0:25.200   FixerAgent 开始 → 申请 IO Lease
T+0:32.700   FixerAgent 完成
T+0:33.000   SummaryAgent 开始（依赖前两者）
T+0:40.000   SummaryAgent 返回
T+0:40.500   Root Task 完成 → 用户看到报告
```

### 4.3 每个时刻要展示的内容

每个时刻给出：

1. **发生了什么**（叙述）
2. **核心数据结构当时的样子**（task tree、bus 状态）
3. **对应的 Event**（写入 EventStream 的事件）
4. **如果适用，UI 看到什么**

例：

> **T+0:08.500 — AuditAgent 发现高危问题**
>
> AuditAgent 第 4 次 LLM 推理产出："line 42 存在 SQL 注入漏洞，建议参数化查询"。Agent 调用 `CreateTaskTool` 派生子任务：
>
> ```python
> task = Task(
>     id="T-fix-1",
>     parent_id="T-audit",
>     intent="修复 src/auth.py:42 的 SQL 注入：改为参数化查询",
>     required_capability="fix",
>     created_by="agent-run-audit-1",
> )
> bus.publish(task)
> ```
>
> 此刻 TaskBus 状态：
> ```
> running:  [T-audit (running)]
> pending:  [T-summary (waiting for T-audit, T-fix-1), T-fix-1 (just published)]
> ```
>
> EventStream 写入：
> ```
> [E-37] TaskPublished(task_id=T-fix-1, parent=T-audit, capability=fix)
> [E-38] LLMCallCompleted(task=T-audit, tokens=2.3k→0.4k, cached=1.8k)
> ```

### 4.4 失败分支

主例中至少展示一次失败：

```
分支 A：AutonomyGate 超时
  用户 10 分钟未回应 → ActionCard 进入 expired 状态
  按 SessionConfig.on_timeout 策略，T-fix-1 进入 cancelled
  T-summary 等待者收到事件，决定继续（仅含 audit 报告，不含 fix 状态）

分支 B：工具调用失败（备选）
  FixerAgent 写文件被 Workspace 拒绝（权限）
  Agent 重试一次，仍失败 → 返回 fail
  T-fix-1: failed
  父任务 T-audit 决定：将失败信息纳入 summary，不阻塞整体
```

主文档展示分支 A（更典型）；分支 B 放在附录"如果换一种失败"。

---

## 5. 短例 1：单个对话回合

```
场景："列出当前目录下的 Python 文件"

参与：仅一个 Task，无子任务，无 ActionCard。

意义：展示"最简单情况下系统也是任务驱动的"——
     不是只有复杂场景才走 TaskBus。
```

10-20 行叙述足够，重点是和主例对比"复杂度可伸缩"。

---

## 6. 短例 2：用户中途打断

```
场景：审计任务跑到一半，用户说「停一下，先帮我看 db.py」

参与：
  - 中断语义（转向）
  - 任务进入 paused
  - 新任务插队
  - 完成后旧任务恢复
```

展示 [ux-interaction.md §7] 的打断语义如何在事件层落地。

---

## 7. 章节结构建议

```
walkthrough.md
├─ 0. 阅读说明（受众 / 前置概念 / 推荐阅读顺序）
├─ 1. 主例：代码审计 + 修复
│   ├─ 1.1 场景与角色
│   ├─ 1.2 时间线总览（一张大图）
│   ├─ 1.3 详细叙述（每个关键时刻一节）
│   ├─ 1.4 任务树最终样态
│   ├─ 1.5 EventStream 完整列表
│   └─ 1.6 成本归因表
├─ 2. 短例 1：单回合对话
├─ 3. 短例 2：用户打断
├─ 4. 失败分支汇编
├─ 5. 数据流回路总图
└─ 6. 与各组件文档的交叉索引
```

---

## 8. 关键图示

### 8.1 时间线总览图

```
User    ┃■━━━━━━━━━━━━━━━━━━━━━━━━━━━━━■
Session ┃ ■━━━━━━━━━━━━━━━━━━━━━━━━━━━■
T-root  ┃   ■━━━━━━━━━━━━━━━━━━━━━━━━■
T-audit ┃     ■━━━━━━━■                ▼
T-fix   ┃              ⏸━━━ user ━━━■━■
T-sum   ┃                              ■━━■
        ┃───────────────────────────────────→ time
                       ↑
                   ActionCard
```

### 8.2 数据流回路图

```
   User Message
       ↓
   Session.handle_request → publish Root Task
       ↓
   TaskBus.claim → AgentInstance.run → publish Subtasks
       ↑                                     ↓
       │                                     │
       └─── result 回流 ←── TaskBus.complete ─┘
       ↓
   Root.result → Session → User
```

### 8.3 状态机切片

某个时刻的：
- TaskBus 队列状态
- 各 Agent 实例状态
- 已发出但未 resolve 的 ActionCard
- 当前累计成本

---

## 9. 写作规范

| 项 | 要求 |
|---|------|
| 时长 | 主例 ≈ 1500-2500 字；短例 ≈ 200-400 字 |
| 代码片段 | 关键节点放最精简伪代码，不要完整签名 |
| 字段名 | 与组件文档一致，不引入新名词 |
| 图比例 | 时间线图 1 张、数据流图 1 张、状态机切片 ≥ 2 张 |
| 引用 | 每出现一个新概念都链到对应组件文档 |
| 阅读时长 | 总计可在 15 分钟内读完 |

---

## 10. 待回答的开放问题

| 问题 | 决策需要的输入 |
|------|------------|
| 是否做交互版（点击事件可展开）？ | 工作量预算 |
| 是否提供可执行的 demo 代码？ | 引擎是否已实现 |
| 是否双语（中英）？ | 受众范围 |
| 是否随版本更新（每次架构变更同步）？ | 维护成本 |

---

## 11. 实施里程碑

```
M1 — 主例骨架
  ─ 时间线总览图
  ─ 关键时刻的叙述（占位 + 大纲）
  ─ 任务树最终态

M2 — 主例完整
  ─ 每个时刻补全：叙述 + 数据 + 事件
  ─ 失败分支 A 完整
  ─ 成本归因表

M3 — 短例
  ─ 短例 1（单回合）
  ─ 短例 2（用户打断）
  ─ 失败分支 B（附录）

M4 — 总图与索引
  ─ 数据流回路总图
  ─ 与各组件文档的交叉索引
  ─ 阅读时长打磨到 15 分钟内

M5 — 演进维护
  ─ 与组件文档版本同步检查清单
  ─ 每次架构改动后回归校验
```

---

## 12. 验收标准

| 验收点 | 衡量方式 |
|------|---------|
| 没读过任何组件文档的人能理解主例 70% | 用户测试 |
| 读过主例后能流畅阅读组件文档 | 用户访谈："walkthrough 帮你理解组件了吗" |
| 主例覆盖所有核心组件 | 检查清单：Session/Task/Bus/Agent/EventStream/AutonomyGate/CostAggregator 均出场 |
| 失败分支真实可信 | 工程师评审："这种失败模式确实可能发生" |
| 与组件文档无冲突 | 自动化检查：术语一致性 |

---

## 13. 与其他 plan 的关系

- [user-guide.md](user-guide.md) — Walkthrough 是 user-guide 的关键参考
- [observability.md](observability.md) — 主例的 EventStream 列表演示查询能力
- [ux-interaction.md](ux-interaction.md) — 主例展示 ActionCard 完整流程
- [cost-quota.md](cost-quota.md) — 主例附"成本归因表"
- [configuration.md](configuration.md) — 主例选用一个具体 OrchestrationPreset

---

## 14. 文档之外的想法

如果时间允许，walkthrough 可以做成**可交互的网页**：

```
特性：
  - 时间线可拖动，看任意时刻的快照
  - 任务节点可点击展开，看 Agent 的内部 LLM 调用
  - ActionCard 可以"扮演用户"做不同选择，看分支
  - 切换 OrchestrationPreset，重跑，对比差异
```

这等同于一个**架构沙箱**——但属于 v2 范围，不在 v1 落地清单。
