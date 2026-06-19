# 架构评审与自评

> 多 Agent 协作架构 v1.0 + bus-v2 · 第三方视角自评 · 2026-05-09

---

## 0. 评审目标

本文从外部读者视角，对 `docs/architecture/` 下的架构文档（overview / task / session / agent / bus / bus-v2）做**新颖性 / 完整性 / 直观性**三维评价。目的不是自我证明，而是**显性化短板**，作为后续工作的路线图。

> 评审结论也是 [`docs/plans/`](../plans/) 目录的输入——每个空白都对应一份 plan。

---

## 1. 新颖性：7 / 10

### 1.1 真正"独立思想"的设计

| 设计 | 为什么是亮点 |
|------|------------|
| **CreateTaskTool 把"协作能力"工具化** | 多数框架把 Orchestrator/Worker 做成 Agent 类型分层。本架构把"是否能派任务"降维成普通工具能力，让控制流能力和业务能力同构管理，整个 Agent 体系少一层概念。 |
| **强约束 + 显式松绑路径** | 不是新方法论，但**罕见地把"约束何时该松"写成一等公民**。多数架构文档只讲"现在为什么这样"，本架构讲"现在为什么 + 未来怎么改 + 改的触发条件"。这是工程文档的成熟形态。 |
| **bus-v2 的 IOScope 洞见** | "LLM 推理占总耗时 95%，工具 IO < 5%" 这个观察推翻了 v1 的串行约束基础，但保留了 v1 的所有正确性承诺。是少数读完会拍桌子的设计跳跃。 |
| **LLM 调度 + 强制 rationale 审计** | 用 LLM 做调度有人提过（Manus、AutoGen），但**强制写决策理由到 EventStream**这一笔把黑箱变成可审计组件，是工程化贡献。 |

### 1.2 不算新（诚实说）

- 单根树 vs DAG（Claude Code、CrewAI 都这样）
- 极简任务状态机（当前实现为 `pending` / `running` /
  `waiting_for_user` / `done` / `failed`）
- 无状态 Agent（LangGraph 类似）
- EventStream / append-only（event sourcing 老技术）
- 进程/线程类比（解释装置很好，但映射本身不新）

---

## 2. 完整性：6 / 10

### 2.1 覆盖到位

每个组件都有独立文档，结构统一（定义 / 抽象 / 理念 / 生命周期 / 未来），设计决策都有 rationale 和替代方案，演进路径清晰。**这部分是合格的架构文档。**

### 2.2 明显空白

| 维度 | 空白 | 严重程度 | 对应 plan |
|------|------|---------|---------|
| **错误处理** | "failed 终态、重试=新建任务"过于简化。重试策略、部分失败、调度器自身故障 | 🔴 高 | （待加入路线图） |
| **安全与权限** | 完全没讨论。哪些 Agent 能用哪些工具？Workspace 读写权限？沙箱边界？ | 🔴 高 | （待加入路线图） |
| **可观测性** | EventStream 提了，但 trace、指标、调试工具的设计完全缺失 | 🟠 中 | [observability.md](../plans/observability.md) |
| **HITL / UX** | autonomy 在 SessionConfig 一笔带过，但用户打断、延迟回应、多任务并发确认的 UX 没设计 | 🟠 中 | [ux-interaction.md](../plans/ux-interaction.md) |
| **成本与配额** | LLM token 预算、任务成本上限、成本超限处理 | 🟠 中 | [cost-quota.md](../plans/cost-quota.md) |
| **存储具体形态** | ThoughtStore 是 KV / 文档库 / 向量库？EventStream 后端？一笔带过 | 🟡 低 | （在 observability + configuration 中部分覆盖） |
| **配置系统** | ConstraintProfile / OrchestrationPreset 反复提及，但具体形式没设计 | 🟡 低 | [configuration.md](../plans/configuration.md) |
| **死锁/活锁** | bus-v2 谈了死锁，但 v1 也可能"任务因 capability 未注册永远 pending" | 🟡 低 | （观察性 plan 内补充） |
| **测试策略** | 这种架构怎么测？事件 replay？随机扰动？ | 🟡 低 | （后续单独 plan） |

**核心架构决策（错误处理 + 安全 + 可观测性）的缺失会让审稿人怀疑设计是否经得起生产推敲。** 哲学层面的成熟度，超过了工程层面的密度。

---

## 3. 直观性：7 / 10

### 3.1 做得好

- **进程/线程对照表**（overview §6）是教学级好材料，从未见过 Agent 系统的人也能秒懂
- **每个文档末尾的决策小结表**把"为什么这样选"集中呈现，复习成本低
- **分层叙述**：overview → 组件 → v2 演进，符合"全景→局部→演进"的阅读节奏
- **ASCII 图都在关键决策点**，不是装饰

### 3.2 直观性的硬伤

1. **没有端到端 trace ⭐ 最严重的问题**
   一个完整的"用户说一句话 → 系统怎么走完一遍"的例子完全缺失。读者只能靠脑补串联各组件。
   → 对应 [walkthrough.md](../plans/walkthrough.md)

2. **术语过载没有全景图**
   SessionConfig / ConstraintProfile / OrchestrationPreset / AutonomyBehavior / AgentTemplate / AgentInstance / TaskResult / ScheduleAction / IOScope ... 名词高达 20+，缺一张"术语关系全景图"。
   → 对应 [user-guide.md](../plans/user-guide.md) 中的术语章节

3. **数据回流不清晰**
   Task 的 `result` 怎么从子任务回到父任务、从父任务回到用户？这个**回路**散落各处，没有一张图明确画出来。
   → 对应 [walkthrough.md](../plans/walkthrough.md)

4. **概念具体感不足**
   - Workspace 到底是文件系统？带版本的对象？
   - ThoughtStore 是 KV、文档库、向量库还是多模混合？
   一笔带过让读者没有"我能动手实现它"的具体感。

5. **bus v1 → v2 复杂度跳跃过陡**
   v1 是"几十行代码"的 FIFO，v2 突然 LLM 调度 + IOScope + 冲突解决 + 降级 + 渐进路线，复杂度阶跃太大。
   → 后续可补"最小可用 v2"中间态文档。

6. **缺反例对照**
   只有"为什么这样做"，没有"如果不这样会怎样"。补几个反例（"如果用 DAG 会怎样"、"如果不用 Bus 会怎样"），决策选择会更立体。

---

## 4. 综合评分

| 维度 | 分数 | 权重 |
|------|------|------|
| 新颖性 | 7.0 | 0.4 |
| 完整性 | 6.0 | 0.3 |
| 直观性 | 7.0 | 0.3 |
| **综合** | **6.7 → 7.3** | 亮点权重略加成 |

**定性结论：**

> 这是一份"**架构思考成熟度高于实现细节密度**"的文档。哲学层（约束、演进、心智模型）写得超过 80% 同类项目；工程层（错误处理、安全、可观测性）有明显空白。
>
> 亮点在 `CreateTaskTool 工具化`、`强约束+松绑路径`、`bus-v2 的 IOScope 洞见` 三处真正"独立思想"。
>
> 最大改进项是**端到端 trace 示例**和**术语全景图**——这两个动作能把直观性从 7 拉到 9。
>
> 属于"值得开源、能吸引人讨论、但离生产架构还差一个工程深度迭代"的水平。

---

## 5. 后续路线图

按本评审显性化的空白，建立 [`docs/plans/`](../plans/) 目录，每个空白对应一份独立 plan：

| Plan | 优先级 | 解决的空白 |
|------|-------|----------|
| [walkthrough.md](../plans/walkthrough.md) | P0 | 端到端 trace、数据回流不清晰 |
| [ux-interaction.md](../plans/ux-interaction.md) | P0 | HITL 细节、autonomy 实操语义 |
| [observability.md](../plans/observability.md) | P0 | trace、指标、调试工具、死锁检测 |
| [cost-quota.md](../plans/cost-quota.md) | P1 | token 预算、成本归因、超限处理 |
| [configuration.md](../plans/configuration.md) | P1 | ConstraintProfile / OrchestrationPreset 落地形式 |
| [user-guide.md](../plans/user-guide.md) | P1 | 术语全景图、上手路径 |

未列入 v1 plan 的（但应纳入未来工作）：
- 错误处理与重试策略
- 安全与权限模型
- 测试策略（含事件 replay、随机扰动）
- bus v1.5（IOScope-only，无 LLM 调度）作为 v2 中间态
- 反例对照文档（"如果不这样会怎样"）

---

## 6. 自评态度

写下评分不是为了打高分，而是为了**让接下来的工作有依据**。每一项扣分都对应一份 plan，每一份 plan 都对应一次具体的迭代。

> "好的架构文档不只是描述当前设计，更指明下一步该往哪里改。"

这份评审本身也是这样使用的——它不是终点，是工作的起点。
