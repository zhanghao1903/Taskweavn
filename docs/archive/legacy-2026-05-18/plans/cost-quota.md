# Plan: 成本与配额系统

> 多 Agent 协作架构 · 成本控制设计计划 · v0 · 2026-05-10

---

## 1. 背景

LLM 调用是真金白银。本架构的"任务驱动"模型让派生任务非常容易（一次工具调用就能 publish 一个新 task），如果没有成本控制：

```
风险场景：
  - Agent 派生子任务 → 子任务又派生子任务 → "任务爆炸"
  - 单个任务陷入"工具循环"反复消耗 token
  - 调度器（bus-v2）本身的 LLM 调用也在烧钱
  - 用户配置 yolo 模式后无意中跑了几小时长任务
```

参考评审：[architecture/review.md](../architecture/review.md) 第 2.2 节（成本与配额列为 🟠 中等优先空白）。

---

## 2. 目标

- **可见**：任意时刻知道任意 Session / Task / Agent 已花了多少
- **可控**：能在用户层、Session 层、Task 层设置预算上限
- **可归因**：每一笔 token 消耗能追溯到具体任务和 Agent 实例
- **可降级**：超限时不是简单 fail，而是按策略优雅降级

**非目标：**
- 不做计费系统（只做工程层度量）
- 不做实时定价对比（接什么模型由 configuration 层管）

---

## 3. 待解决的问题清单

| # | 问题 | 难点 |
|---|------|-----|
| 1 | token 怎么实时统计且不影响热路径性能？ | API 返回 usage 时间窗口、聚合粒度 |
| 2 | 成本超限时取消 vs 降级 vs 询问用户？ | 用户体验 vs 安全 |
| 3 | 调度器（bus-v2）自身 token 怎么归类？ | 它服务于多个任务，难单独归因 |
| 4 | 子任务的成本算父任务的吗？ | 树形归集语义 |
| 5 | 不同模型价格差异大，怎么统一度量？ | 抽象为 token 还是抽象为 USD？ |
| 6 | 缓存命中带来的折扣怎么体现？ | API 返回 cached_tokens vs uncached_tokens |
| 7 | 事前估算 vs 事后核算的差距？ | 估算用什么模型？误差容忍度？ |

---

## 4. 核心抽象

### 4.1 Cost 是显式数据

```python
@dataclass(frozen=True)
class Cost:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0      # 缓存命中部分
    model: str                         # 用于反查单价
    usd_estimate: Decimal              # 由 PriceTable 换算

    def __add__(self, other: "Cost") -> "Cost": ...

class PriceTable:
    """模型 → 单价的注册表，按 USD/1M tokens。"""
    def usd(self, model: str, input: int, output: int, cached: int) -> Decimal: ...
```

**两套度量并存：**
- **token** —— 与模型解耦，工程层的硬通货
- **USD 估算** —— 用户感知，预算设置维度

### 4.2 Budget 是显式约束

```python
@dataclass(frozen=True)
class Budget:
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_usd: Decimal | None = None
    on_exceed: ExceedBehavior = "ask_user"

ExceedBehavior = Literal["fail", "ask_user", "downgrade", "soft_warn"]
```

**层级：** Budget 可以挂在 User / Session / Task 任意层级，**取最严格者**：

```
有效预算 = min(user.budget, session.budget, task.budget)
```

---

## 5. 成本归因模型

```
   每次 LLM 调用产生 CostEvent，归属维度：
       agent_run_id  ─ 这次 Agent 实例化的运行
       task_id       ─ 当前任务（运行 Agent 时已知）
       session_id    ─ 通过 task → session
       user_id       ─ 通过 session → user
       caller_kind   ─ "agent" | "scheduler" | "system"
```

**调度器（bus-v2）的 token 怎么归？**

```
方案 A：归到当时被调度的 task（按比例分摊）
方案 B：归到 session 级"系统开销"
方案 C：归到一个虚拟 "scheduler_task"，便于审计

推荐 C：
  - 与业务任务清晰分离
  - 用户可以单独看"调度本身花了多少"
  - 反过来约束调度策略（调度比执行还贵就不合理）
```

### 5.1 父子归集

```
父任务的"总成本" = 自身成本 + Σ 子任务总成本

但单看任务时显示两个数：
  task.own_cost      ─ 该任务 Agent 实例自身消耗
  task.total_cost    ─ 含所有后代
```

UI 展示父任务时默认显示 total，可展开看 own + 各子任务分项。

---

## 6. 实时统计实现

### 6.1 数据流

```
LLM API 返回 → 解析 usage 字段 → 构造 CostEvent → 写 EventStream
                                              → 更新内存中的 CostAggregator
```

CostEvent 是不可变事件，进 EventStream；CostAggregator 是物化视图，便于查询。

### 6.2 CostAggregator 接口

```python
class CostAggregator:
    def cost_of_task(self, task_id: TaskId, include_descendants: bool = True) -> Cost: ...
    def cost_of_session(self, session_id: SessionId) -> Cost: ...
    def cost_of_user(self, user_id: UserId, time_range: TimeRange) -> Cost: ...
    def cost_by_model(self, session_id: SessionId) -> dict[str, Cost]: ...
    def cost_by_caller(self, session_id: SessionId) -> dict[str, Cost]: ...
```

查询走聚合视图，不需要每次都从 EventStream 扫描。

---

## 7. 预算检查时机

### 7.1 事前估算（pre-flight check）

任务派发前估算：

```
estimated_cost = estimator.estimate(task, agent_template)

if estimated_cost + current_session_cost > budget.max_usd:
    → 触发 on_exceed 策略
```

估算来源：
- 历史平均（同 capability 的任务历史成本）
- prompt 长度上界（system + tools + workspace_snapshot 的 token 数）
- 默认上限（无历史时按 capability 的 fallback 值）

**估算允许误差，不阻塞执行——只是用于提前预警。**

### 7.2 事中检查（mid-flight check）

每次 LLM 调用返回后：

```
session.cost += event.cost
if session.cost > budget.max_usd:
    → 任务进入 paused
    → 触发 on_exceed
```

事中检查比事前严格：超过即停。

### 7.3 事后核算

任务终态后写入 EventStream，作为审计记录。这部分不影响执行。

---

## 8. 超限策略

### 8.1 ExceedBehavior 详解

```
fail
  ─ 任务直接 failed，error="budget_exceeded"
  ─ 适合后台批量任务、不可交互场景

ask_user
  ─ 弹出 ActionCard：「预算已用 95%，是否继续？提升预算 / 取消任务 / 降级」
  ─ 适合交互式 Session（默认）

downgrade
  ─ 切换到更便宜的模型重试
  ─ 切换到精简 prompt（裁剪历史）
  ─ 仍然失败则 fail
  ─ 适合自动化但有质量底线的场景

soft_warn
  ─ 只记录、不阻塞
  ─ 适合内部测试、本地开发
```

`ask_user` 与 [ux-interaction.md](ux-interaction.md) 的 ActionCard 模型对接。

### 8.2 软上限 + 硬上限

```python
@dataclass(frozen=True)
class TieredBudget:
    soft_usd: Decimal      # 80% → 警告
    hard_usd: Decimal      # 100% → 触发 on_exceed
```

软上限提供"开车快到油站"的体感；硬上限是真停车。

---

## 9. 估算器设计

### 9.1 历史驱动

```python
class HistoricalEstimator:
    def estimate(self, task: Task, template: AgentTemplate) -> Cost:
        history = self.store.lookup(
            capability=task.required_capability,
            template_version=template.version,
            limit=100,
        )
        if len(history) >= MIN_SAMPLES:
            return Cost(
                input_tokens=percentile(history.inputs, 75),
                output_tokens=percentile(history.outputs, 75),
                ...
            )
        return self._fallback_estimate(task, template)
```

用 P75 而非平均，预算偏保守。

### 9.2 静态上界

无历史时退化到静态：

```
input_estimate = len(system) + len(tools) + len(snapshot) + len(intent) + 安全系数
output_estimate = task.required_capability 的默认上界
```

### 9.3 估算误差监控

```
EstimatorAccuracyMetric:
  observation = (estimated, actual)
  bucket by capability + template_version
  alert if MAPE > 30% (Mean Absolute Percentage Error)
```

误差大说明历史样本不足或任务异质性高，需要重新校准。

---

## 10. 缓存折扣处理

API 返回的 `cached_input_tokens` 单价远低于普通 input。PriceTable 必须区分：

```python
class PriceTable:
    def usd(
        self,
        model: str,
        input_tokens: int,
        cached_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        non_cached = input_tokens - cached_tokens
        return (
            non_cached * price[model].input
            + cached_tokens * price[model].cached_input
            + output_tokens * price[model].output
        ) / 1_000_000
```

UI 展示时单独标注：

```
本任务：23,400 tokens · $0.18
  ↳ 缓存命中：12,000 tokens（节省 $0.04）
```

让用户感知 cache 的价值——也间接督促 prompt 工程优化。

---

## 11. 配额系统

预算是单次 Session 的硬约束；配额是更高维度的"周期内总量限制"：

```python
@dataclass(frozen=True)
class Quota:
    user_id: UserId
    period: Period                  # daily / weekly / monthly
    max_usd: Decimal
    reset_at: datetime
```

```
配额检查：
  Session 创建前 → 检查用户当前周期累计是否超限
  超限 → Session 拒绝创建（或降级模式）
```

**配额由用户/管理员配置；预算由 Session/Task 配置。** 两者互不替代。

---

## 12. 调度器自身的成本

bus-v2 的 LLM 调度本身消耗 token，需要单独度量：

```
metrics:
  scheduler_tokens_per_decision   ─ 每次决策成本
  scheduler_tokens_per_session     ─ 累计调度开销
  scheduler_token_ratio            ─ 调度成本 / 业务任务成本

警戒阈值：
  scheduler_token_ratio > 0.1 → 调度器太贵，触发降级到 FIFO
```

这把成本控制本身变成了**调度策略的输入**。

---

## 13. 待回答的开放问题

| 问题 | 决策需要的输入 |
|------|------------|
| 是否支持多币种？ | 用户分布 |
| 历史成本数据的保留期？ | 隐私合规 + 估算精度 |
| 任务级预算的默认值是什么？ | 用户研究 |
| 团队/组织级配额（v3）？ | 多租户需求 |
| 缓存命中折扣的 PriceTable 由谁维护？ | 模型供应商关系 |

---

## 14. 实施里程碑

```
M1 — 度量基础
  ─ Cost / CostEvent / CostAggregator
  ─ EventStream 中的成本事件
  ─ 任务 / Session 级实时聚合

M2 — 预算与超限
  ─ Budget 数据模型
  ─ 事中检查 + on_exceed 四种策略
  ─ 软/硬上限

M3 — 估算器
  ─ 历史驱动估算
  ─ 估算误差监控
  ─ 事前 pre-flight check

M4 — 配额系统
  ─ Quota 数据模型
  ─ 周期重置
  ─ 跨 Session 累计

M5 — 调度器成本反馈
  ─ scheduler_token_ratio 监控
  ─ 触发降级策略
```

---

## 15. 验收标准

| 验收点 | 衡量方式 |
|------|---------|
| 任意任务的实时成本可查 | API `cost_of_task` 返回延迟 < 50ms |
| 预算超限策略生效 | hard 上限触发后任务不再消耗 token |
| 估算误差可控 | 主要 capability 的 MAPE ≤ 30% |
| 调度成本可见 | UI 单独显示"系统调度开销" |
| 缓存折扣体现 | 节省金额单独展示 |

---

## 16. 与其他 plan 的关系

- [observability.md](observability.md) — Cost 数据是核心指标之一
- [configuration.md](configuration.md) — Budget / Quota 是 SessionConfig / UserConfig 字段
- [ux-interaction.md](ux-interaction.md) — 超限询问走 ActionCard 渲染
- [walkthrough.md](walkthrough.md) — 端到端示例需展示一笔成本如何归因
