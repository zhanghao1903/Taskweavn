# Plan: 用户指南

> 多 Agent 协作架构 · 用户文档计划 · v0 · 2026-05-10

---

## 1. 背景

架构文档是给**架构师 / 实现者**看的；user-guide 是给**实际使用者**看的。这两种受众的诉求差异巨大：

```
架构文档读者         user-guide 读者
──────────────────────────────────────────
关心"为什么这样"      关心"我该怎么做"
能接受抽象            需要具体步骤
读起来像论文          读起来像手册
                    
20+ 个新名词           需要术语全景图
```

参考评审：[architecture/review.md](../architecture/review.md) 第 3.2.2 节（术语过载没有全景图）。

---

## 2. 目标

- **能上手**：30 分钟内完成第一次成功的多 Agent 任务
- **能进阶**：1 小时内学会自定义 Agent / 配置自主度 / 调试问题
- **能查阅**：常见问题快速定位答案（FAQ + 索引）
- **降低术语门槛**：用一张全景图覆盖所有核心名词

**非目标：**
- 不替代 API reference（自动生成的部分另立）
- 不写营销文案
- 不写贡献指南（contributing 单独）

---

## 3. 受众与分层

```
Tier 1：使用者（80%）
  ─ 只想用现成 Preset，少量配置
  ─ 关心"我能让它做什么"
  ─ 需要：快速上手、典型场景、配置速查

Tier 2：调优者（15%）
  ─ 调整自主度、约束、成本
  ─ 关心"我能让它怎么做"
  ─ 需要：配置详解、调试指南、性能调优

Tier 3：扩展者（5%）
  ─ 自定义 Agent、写新工具、改调度
  ─ 关心"我能改变它的行为"
  ─ 需要：扩展点、SPI、最佳实践

文档分层匹配三个 Tier。
```

---

## 4. 章节结构

```
user-guide.md
├─ 0. 速览（30 秒读完）
├─ 1. 30 分钟上手
│   ├─ 1.1 安装
│   ├─ 1.2 第一个 Session
│   ├─ 1.3 看到第一个结果
│   └─ 1.4 你刚才发生了什么（最简化版 walkthrough）
├─ 2. 核心概念
│   ├─ 2.1 术语全景图
│   ├─ 2.2 Session：你的工作环境
│   ├─ 2.3 Task：系统的工作单元
│   ├─ 2.4 Agent：实际干活的"工人"
│   └─ 2.5 自主度：你和系统的协作模式
├─ 3. 典型场景
│   ├─ 3.1 代码审计 + 修复
│   ├─ 3.2 长文档总结
│   ├─ 3.3 数据探索
│   └─ 3.4 …
├─ 4. 配置与定制（Tier 2）
│   ├─ 4.1 Autonomy 配置
│   ├─ 4.2 Budget 与成本控制
│   ├─ 4.3 ConstraintProfile
│   ├─ 4.4 OrchestrationPreset
│   └─ 4.5 配置文件结构
├─ 5. 调试与问题排查（Tier 2）
│   ├─ 5.1 任务卡住怎么办
│   ├─ 5.2 看 trace
│   ├─ 5.3 看成本
│   └─ 5.4 常见错误
├─ 6. 扩展（Tier 3）
│   ├─ 6.1 写一个自定义 Agent
│   ├─ 6.2 注册一个新工具
│   ├─ 6.3 自定义 OrchestrationPreset
│   └─ 6.4 何时该改调度策略
├─ 7. FAQ
└─ 8. 索引（按术语 / 按场景）
```

---

## 5. 术语全景图（核心装置）

放在 `2.1`，是整本指南的导航中心。

### 5.1 一张图

```
                      ┌────────────┐
                      │   User     │
                      └──────┬─────┘
                             │ creates
                             ↓
   ┌────────────────────────────────────────────────────┐
   │                  Session                           │
   │   持有：Workspace · TaskBus · AgentPool · ...        │
   │   配置：SessionConfig                                │
   │           ├─ AutonomyBehavior (trigger + wait)       │
   │           ├─ ConstraintProfile                      │
   │           ├─ OrchestrationPreset                    │
   │           └─ Budget                                 │
   └──────┬─────────────────────────────────────────────┘
          │
          ↓ root task
   ┌────────────┐    publish    ┌────────────┐
   │   Task     │ ─────────────→│  TaskBus   │
   │  - intent  │               │  调度+状态  │
   │  - cap     │ ←──── claim ──┤            │
   │  - status  │               └────────────┘
   │  - result  │                      ↑
   └─────┬──────┘                      │
         │                             │
         │                  ┌──────────┴──────────┐
         │                  │  AgentInstance      │
         │                  │  (来自 AgentTemplate)│
         │                  │  capability + tools │
         │                  └─────────┬───────────┘
         │                            │ uses
         │                            ↓
         └─────── reads/writes ──→  Workspace
                                     │
                                     │ all events to
                                     ↓
                              EventStream
                            (用于 trace / replay / metrics)
```

### 5.2 术语速查表

| 术语 | 一句话定义 | 详见 |
|------|----------|------|
| Session | 一次完整交互的资源容器 | §2.2 |
| Task | 工作的最小单位，树形组织 | §2.3 |
| TaskBus | 任务的传递媒介与调度中枢 | §2.3 |
| Agent | 完成任务的"工人"，按需实例化 | §2.4 |
| AgentTemplate | Agent 的"图纸" | §6.1 |
| AgentInstance | Agent 的运行实例 | §6.1 |
| Session Workspace | 单个 Session 的隔离工作目录 | §2.2 |
| Capability | Agent 能做的事的类别（如 audit / fix） | §2.4 |
| AutonomyBehavior | "什么时候打扰你 + 是否等你回应"的双维度 | §2.5 |
| ConstraintProfile | 任务可以做什么、不能做什么的约束集 | §4.3 |
| OrchestrationPreset | 一组预设：Autonomy + Constraint + Agents | §4.4 |
| Budget | 单次会话的成本上限 | §4.2 |
| Quota | 跨会话的周期性总量限制 | §4.2 |
| ActionCard | UI 上需要你点击决定的卡片 | §2.5 |
| EventStream | 系统所有事件的不可变日志 | §5.2 |
| ThoughtStore | Agent 的长期记忆 | （高级） |
| trace_id | 一次请求的全链路 ID | §5.2 |

**保持每条 ≤ 1 行**——这张表的价值是密度。

---

## 6. 30 分钟上手（最关键章节）

### 6.1 设计原则

```
只引入最少的概念：Session / Task / Result
不出现：AutonomyBehavior、ConstraintProfile、Capability
不出现：自定义 Agent、调度策略
能跑通就行，理解延后到第 2 章
```

### 6.2 内容草案

```bash
# 安装
pip install codeagent

# 第一次跑
codeagent run "审计 src/auth.py"

# 输出：
# ✓ Session 已创建
# ✓ 任务已派发
# 🔍 AuditAgent 正在分析…
# 
# === 报告 ===
# - line 42: 潜在 SQL 注入
# - line 78: 输入未校验长度
# === 完成 (耗时 12s, 花费 $0.04) ===
```

然后用 100-200 字解释"刚才系统做了什么"——铺垫核心概念，但**不展开**：

> 系统创建了一个 Session（你的工作环境）。你的请求被表达为一个 Task（任务），一个 AuditAgent 被实例化来执行。它读取了文件、做了几次思考、得到结论。整个过程被记录到日志里，你可以随时回看。

让用户**先看到效果，再理解原理**。

---

## 7. 配置示例的呈现方式

每个配置项都用三种形式呈现：

```yaml
# 1. 最简
autonomy:
  preset: balanced

# 2. 中等定制
autonomy:
  preset: balanced
  override:
    wait: notify        # 不阻塞，发通知

# 3. 完全自定义
autonomy:
  trigger: risky
  wait: block
  per_capability:
    fix: { trigger: destructive }    # fix 任务更宽松
```

**先简后繁**——避免用户一上来就要理解所有字段。

---

## 8. FAQ 内容方向

至少覆盖：

```
- Q: 任务卡住不动怎么办？
  A: 看 §5.1 调试 → 大概率是 ActionCard 在等你。

- Q: 怎么省钱？
  A: 看 §4.2 Budget 配置 + §4.4 选小模型 Preset。

- Q: Session 关了再开还能继续吗？
  A: 现在不能（v1 限制），见架构 [session.md] §7.1 future。

- Q: 我能让它跑得更快吗？
  A: 看 §4.4 切到并发 Preset（v2 可用）。

- Q: 我能让它做 X 但不做 Y 吗？
  A: ConstraintProfile，看 §4.3。

- Q: 它做了我不想要的事，能撤销吗？
  A: 工具层面看任务的 IO 记录；业务层面用 git。

- Q: 怎么排查"它为什么这么做"？
  A: §5.2 trace；尤其是调度决策的 rationale。
```

按问题频率排序，不按主题分类——FAQ 是按"问"组织而不是按"答"。

---

## 9. 调试章节的关键示例

### 9.1 任务卡住

```
诊断步骤：
1. codeagent inspect session <id>     # 看哪个任务在 running
2. 如果是 pending → 看 §5.4 capability 未注册
3. 如果是 running 但久无新事件 → LLM API 慢或超时
4. 如果有 ActionCard pending → UI 上响应它
```

每一步给具体命令、预期输出、下一步。

### 9.2 trace 阅读

用 walkthrough 主例的 EventStream 切片做教学样本，标注：

```
[E-37] TaskPublished(...)        ← 任务诞生
[E-38] LLMCallCompleted(...)     ← 看 tokens 字段诊断成本
[E-42] SchedulingDecisionMade    ← 看 rationale 理解为什么这样调度
```

让用户学会**自己读 trace**，而不是只能问开发者。

---

## 10. 扩展章节（Tier 3）

### 10.1 写一个自定义 Agent

```python
from codeagent import AgentTemplate

my_agent = AgentTemplate(
    name="DocLinter",
    capability="lint_docs",
    tools=[read_file, write_file],
    system_prompt="""
    你是文档校对员。检查 markdown 文件的：
    - 死链
    - 拼写错误
    - 标题层级
    """,
)

# 注册到当前项目
register_template(my_agent, scope="project")
```

3-5 个完整可跑的扩展示例，覆盖：
- 新 capability 的 Agent
- 新工具的注册
- 自定义 OrchestrationPreset
- 自定义 PriceTable

### 10.2 何时不要扩展

```
不要写自定义 Agent 如果：
  - 已有 capability 能完成（用现成的）
  - 你的需求是"换 prompt 措辞"（用 Preset 的 system_prompt_override）
  - 你的需求是"暂时实验性"（用 Session 级临时覆盖）
```

设计 anti-pattern 比示例更重要——避免社区写出过多重复 Agent。

---

## 11. 写作风格规范

| 维度 | 要求 |
|------|------|
| 人称 | 第二人称"你"，不用"用户" |
| 句长 | 平均 ≤ 25 字 |
| 代码 | 每段示例 ≤ 15 行 |
| 章节长度 | 单章 ≤ 1000 字 |
| 图 | 每章至少 1 张图（不算概念图） |
| 链接 | 引用术语首次出现时链到术语表 |
| 命令 | 真实可跑，不写伪命令 |

---

## 12. 待回答的开放问题

| 问题 | 决策需要的输入 |
|------|------------|
| 是否提供视频教程？ | 团队产能 |
| 是否英文版同步发布？ | 用户分布 |
| 是否提供 playground（在线试跑）？ | 基础设施成本 |
| FAQ 是否社区驱动（GitHub Discussions）？ | 维护意愿 |
| 是否区分 CLI 用户和 Library 用户？ | 实际使用比例 |

---

## 13. 实施里程碑

```
M1 — 骨架与术语
  ─ 全文档目录
  ─ 术语全景图（§2.1）
  ─ 术语速查表

M2 — 30 分钟上手
  ─ 安装 + 跑通示例
  ─ "你刚才发生了什么"解读
  ─ 用户测试（5 人）目标：100% 在 30 分钟内跑通

M3 — 核心概念章节
  ─ §2 全部完成
  ─ 与架构文档交叉链接

M4 — 典型场景
  ─ 5 个典型场景的端到端示例
  ─ 与 walkthrough 主例呼应

M5 — 配置详解（Tier 2）
  ─ §4 全部完成
  ─ 三档 by-example 风格

M6 — 调试章节（Tier 2）
  ─ §5 全部完成
  ─ 与 observability plan 衔接

M7 — 扩展（Tier 3）
  ─ §6 全部完成
  ─ 5 个完整扩展示例

M8 — FAQ + 索引
  ─ 至少 30 条 FAQ
  ─ 完整索引
  ─ 全文校对

M9 — 维护流程
  ─ 与架构文档版本同步检查清单
  ─ 用户反馈 → FAQ 流程
```

---

## 14. 验收标准

| 验收点 | 衡量方式 |
|------|---------|
| 新人 30 分钟跑通 | 用户测试，N=5，全部通过 |
| 术语全景图覆盖率 100% | 检查清单：所有架构文档术语出现 |
| 调试场景可解决 | 用户测试：给 5 个常见问题，能否在指南内找到答案 |
| 扩展示例可跑 | 自动化 CI：运行所有代码片段 |
| FAQ 命中率 | 6 个月后用户提问中已被覆盖比例 ≥ 60% |
| 阅读体验 | NPS 调研：≥ 40 |

---

## 15. 与其他 plan 的关系

- [walkthrough.md](walkthrough.md) — 是 user-guide 第 1.4 节"你刚才发生了什么"和 §3 典型场景的素材源
- [observability.md](observability.md) — §5 调试章节直接调用 observability 工具
- [configuration.md](configuration.md) — §4 配置章节是 configuration 系统的"用户视图"
- [ux-interaction.md](ux-interaction.md) — §2.5 自主度章节解释 ActionCard 模型
- [cost-quota.md](cost-quota.md) — §4.2 是 cost-quota 的用户面

**user-guide 不重新设计任何东西**——它把所有 plan 的设计成果"翻译"成用户可读的语言。
