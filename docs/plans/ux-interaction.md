# Plan: UX 交互设计

> 多 Agent 协作架构 · UX & HITL 设计计划 · v0 · 2026-05-10

---

## 1. 背景

架构层提了 `AutonomyBehavior` / `interrupt_allowed` / `ConstraintProfile`，但**用户实际怎么和系统打交道**几乎没写。这份 plan 的目标是把 UX 从"提到了"推进到"可实现"。

参考评审：[architecture/review.md](../architecture/review.md) 第 2.2 节（HITL / UX 列为 🟠 中等优先空白）。

---

## 2. 目标

- 让用户**始终掌握**多 Agent 系统的运行节奏，无论它们是串行还是并发
- 让"自主度"从配置项变成**用户可感知、可即时调节**的旋钮
- 让"打断"和"确认"的语义清晰、可预测、不丢失上下文

**非目标：** 设计具体 UI 像素布局；这份 plan 只定义**交互模型**，UI 由产品/设计层落地。

---

## 3. 待解决的问题清单

| # | 问题 | 难点 |
|---|------|-----|
| 1 | 用户怎么从消息流中区分"对话内容 / Agent 进度 / 待确认动作"？ | 视觉与语义双层信息密度 |
| 2 | 多个并发任务都需要确认时，UX 如何避免轰炸？ | 合并策略 + 优先级 |
| 3 | 用户打断时，正在 running 的任务怎么处置？ | 中断语义（cancel vs pause vs ignore） |
| 4 | 用户长时间不回应一个确认请求，系统怎么办？ | 超时降级 + 默认动作 |
| 5 | 用户怎么"事后追看"已完成的任务详情？ | 历史可导航性 |
| 6 | 自主度从"风险确认"切到"全自动"，已 pending 的确认请求怎么处理？ | 配置变更的中间态 |
| 7 | Agent 主动发起"我建议你做 X"的提议时，UX 表达？ | 区别于用户主动请求 |

---

## 4. 核心交互模型：消息流 + 操作卡片

```
┌──────────────────────────────────────────────────┐
│  Session Stream                                  │
│                                                  │
│  [User] 帮我审计 src/auth.py                       │
│                                                  │
│  [System] 拆分为 3 个子任务：                       │
│    ├─ T1 审计 auth.py 安全漏洞                     │
│    ├─ T2 审计 auth.py 输入校验                     │
│    └─ T3 综合报告                                 │
│                                                  │
│  [Agent: AuditAgent] 正在分析 ... (T1 running)    │
│                                                  │
│  ┌────────────────────────────────────────┐      │
│  │ ⚠️  发现高危漏洞 · 需要确认是否自动修复     │      │
│  │   - SQL 注入风险（line 42）              │      │
│  │   - [允许修复] [仅记录] [跳过]            │      │
│  │   action_id=A-7  expires_in=10min        │      │
│  └────────────────────────────────────────┘      │
│                                                  │
│  [User] 允许修复                                   │
│                                                  │
└──────────────────────────────────────────────────┘
```

**两种基本元素：**

1. **消息（Message）** —— 不可变，append-only，是对话内容
2. **操作卡片（ActionCard）** —— 可变，有生命周期（pending / resolved / expired），是需要用户决定的事件

操作卡片在消息流中**占位**——它在出现时是 pending，被用户操作后变成 resolved 状态的"快照"，不消失，但视觉上收起。

---

## 5. AutonomyBehavior 的两个维度

把"自主度"从一个标量拆成两个独立维度：

```
                   ┌───────────────────────┐
                   │   wait（等待维度）       │
                   │                       │
                   │  block:    必等用户回应  │
                   │  notify:   通知但不等   │
                   │  silent:   不通知       │
                   └───────────────────────┘

                   ┌───────────────────────┐
                   │  trigger（触发维度）    │
                   │                       │
                   │  always:   总是确认     │
                   │  risky:    仅高风险确认  │
                   │  destructive: 仅破坏性  │
                   │  never:    从不确认     │
                   └───────────────────────┘
```

**预设组合**（让用户不必两个旋钮都拧）：

| Preset | trigger | wait | 适用场景 |
|--------|---------|------|---------|
| `careful` | always | block | 学习阶段、敏感工作 |
| `balanced` | risky | block | 默认 |
| `auto-with-receipt` | risky | notify | 信任但要回执 |
| `auto-silent` | destructive | notify | 长期任务、自动化流水 |
| `yolo` | never | silent | 内部测试 |

---

## 6. AutonomyGate 决策模式

每次需要决定"是否需要用户介入"时，走 AutonomyGate：

```python
class AutonomyGate:
    def evaluate(
        self,
        action: PendingAction,
        config: AutonomyBehavior,
    ) -> GateDecision:
        risk = self._classify_risk(action)
        if not self._matches_trigger(risk, config.trigger):
            return GateDecision.AUTO_PROCEED
        if config.wait == "block":
            return GateDecision.WAIT_USER(timeout=...)
        if config.wait == "notify":
            return GateDecision.NOTIFY_AND_PROCEED
        return GateDecision.SILENT_PROCEED
```

**风险分级：**

```
destructive  ─ 文件删除、不可逆 IO、外部 API 写入
risky        ─ 文件修改、网络访问、Shell 命令
benign       ─ 只读文件、查询、自身推理
```

风险分级由工具元数据声明（在 [configuration.md](configuration.md) 中定义）。

---

## 7. 打断语义

用户可以在任何时刻发消息，**不阻塞 Agent 当前动作**——但消息会改变之后的执行：

```
打断的三种语义（由用户当前消息内容推断或显式指定）：

1. 增量信息（默认）
   "顺便把 db.py 也看一下"
   → 注入到当前 running 任务的上下文，下一次 LLM 推理可见
   → 不取消任何任务

2. 转向
   "停一下，先看 web.py"
   → 当前 running 任务转入 paused
   → 新任务插队
   → 旧任务可在新任务完成后恢复

3. 取消
   "算了不用看了"
   → 当前 running 任务转入 cancelled
   → 所有 pending 子任务批量 cancelled
   → 已完成的产物保留
```

**关键设计：意图推断不强制。** 用户每条消息附带 UI 上的"模式选择"（默认 = 增量信息），用户可显式切换。LLM 也可以推断模式但需用户确认。

---

## 8. 多任务并发的确认 UX（v2 场景）

bus-v2 引入并发后，可能多个任务**同时**需要用户确认：

### 8.1 合并策略

```
窗口 = 3 秒：3 秒内到达的多个 ActionCard 合并显示
合并规则：
  - 相同 capability 的任务合并为一组
  - 不同 capability 但相同 risk_level 合并为一组
  - 单个 destructive 不合并（永远独立卡片）
```

### 8.2 批量决策

```
┌────────────────────────────────────────────┐
│ ⚠️  3 个任务需要确认                         │
│                                            │
│  □ T1: 修改 auth.py（risky）                │
│  □ T2: 修改 db.py（risky）                  │
│  □ T3: 创建测试 test_auth.py（risky）        │
│                                            │
│  [全部允许] [全部拒绝] [展开逐个决定]          │
└────────────────────────────────────────────┘
```

### 8.3 排队上限

```
同时存在的 pending ActionCard 上限 = 5
超过上限 → 调度器暂停派发新需要确认的任务
        → 队列继续积累但不向 UI 推送
        → 直到用户处理掉 ≥1 个为止
```

防止"通知海啸"压垮用户。

---

## 9. 超时与默认动作

ActionCard 必须声明 `timeout` 和 `on_timeout`：

```python
@dataclass(frozen=True)
class ActionCard:
    action_id: str
    risk: RiskLevel
    options: list[ActionOption]
    timeout: timedelta              # 例：10 min
    on_timeout: TimeoutBehavior     # cancel | proceed_with_default | escalate

class TimeoutBehavior:
    pass

class CancelOnTimeout(TimeoutBehavior):
    """超时即取消任务，显示在历史中。"""

class ProceedWithDefault(TimeoutBehavior):
    default_option_id: str
    """超时按预设选项执行，写明 rationale。"""

class EscalateOnTimeout(TimeoutBehavior):
    notify_channel: str  # 邮件/IM 推送
    """超时升级通知（适合长会话/自动化）。"""
```

**超时不是"放弃用户"**，而是"在用户授权的范围内继续"。预设由 SessionConfig 决定。

---

## 10. Agent 发起的提议

Agent 可以主动建议（来自任务执行中的发现）：

```
┌────────────────────────────────────────────┐
│ 💡 AuditAgent 发现潜在改进                   │
│                                            │
│  src/utils.py 中有 3 处重复代码                │
│  建议：派生重构任务交给 RefactorAgent          │
│                                            │
│  [发起任务] [仅记录] [忽略]                    │
└────────────────────────────────────────────┘
```

视觉上**用 💡 区别于 ⚠️**（提议 vs 风险确认）。

提议和确认在数据上都是 ActionCard，但渲染样式不同。

---

## 11. 历史可导航性

Session 结束后或长会话中部，用户需要回看：

```
导航维度：
  按时间        → 消息流默认视图
  按任务        → 点击任意任务节点 → 显示该任务的完整子树
  按文件        → 点击文件名 → 显示所有触及它的任务
  按 ActionCard → 单独视图查看所有历史决策
```

底层全部从 EventStream 重建——这要求 EventStream 设计支持高效查询，对应 [observability.md](observability.md) 的工作。

---

## 12. 配置变更的中间态

用户从 `careful` 切到 `auto-silent`：

```
切换瞬间：
  - 已 pending 的 ActionCard 状态保持 pending（不自动消失）
  - 用户必须显式处理（或选择"按新策略一键放行"）
  - 切换后产生的新事件按新策略走
```

**显式处理已 pending 的请求**——避免"配置一变，未决的事自动放行"导致用户失去控制感。

---

## 13. 待回答的开放问题

| 问题 | 决策需要的输入 |
|------|------------|
| ActionCard 的渲染是否要支持富文本（代码 diff、表格）？ | 产品需求 + 渲染开销 |
| 移动端是否第一公民？ | 用户画像 |
| 离线（用户离开设备）的回执如何处理？ | 推送/邮件集成范围 |
| 多用户协作（v3）下 ActionCard 给谁？ | 见 session §7.4 |
| ActionCard 的 SLA（从生成到 UI 显示的延迟）？ | 性能预算 |

---

## 14. 实施里程碑

```
M1 — 静态消息流 + 单卡片
  ─ ActionCard 基础渲染
  ─ AutonomyGate 三档（careful / balanced / yolo）
  ─ 同步 block 等待

M2 — 打断语义 + 超时
  ─ 三种打断模式（增量 / 转向 / 取消）
  ─ Timeout + 默认动作
  ─ 历史按任务导航

M3 — 并发 UX（依赖 bus-v2）
  ─ ActionCard 合并 + 批量决策
  ─ 通知排队上限
  ─ Agent 主动提议 UI

M4 — 跨设备 / 跨 Session
  ─ 离线推送 / 邮件回执
  ─ 多设备状态同步
```

---

## 15. 验收标准

| 验收点 | 衡量方式 |
|------|---------|
| 用户能区分"消息 / 进度 / 待确认" | 用户测试：盲读三类内容的识别准确率 ≥ 90% |
| 自主度切换可感知 | 切换后下一次 ActionCard 行为符合预期，无"幽灵确认" |
| 打断不丢上下文 | 增量信息打断后，下一条 LLM 输出包含新信息引用 |
| 超时不卡死系统 | 任意 ActionCard 在 timeout 后系统进入终态，不阻塞其他任务 |
| 并发卡片无轰炸 | 5 个并发任务同时确认时，UI 上 ≤ 3 个独立卡片 |

---

## 16. 与其他 plan 的关系

- [walkthrough.md](walkthrough.md) — 端到端 trace 必须演示 UX 交互全流程
- [observability.md](observability.md) — ActionCard 历史依赖 EventStream 查询能力
- [configuration.md](configuration.md) — AutonomyBehavior 是 SessionConfig 的核心字段
- [cost-quota.md](cost-quota.md) — 成本超限是一种新的 ActionCard 类型
