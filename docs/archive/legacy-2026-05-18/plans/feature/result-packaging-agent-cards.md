# Feature Plan: Result Packaging Agent 与卡片化结果展示

> Status: planned
> Type: 新特性支持 / UI 体验增强
> Last Updated: 2026-05-11
> Owner/Session: planning session
> Target Implementation Session: independent feature session
> Related Docs: [Task-first UI Plan](../task-first-ui-interaction.md), [UI API Interfaces](../ui/ui-api-interfaces.md), [Task Publisher Plan](task-publishers-schedule-api.md), [Pipeline Task Loading](pipeline-task-loading.md)

---

## 1. 背景

有一类任务不是“改文件”或“执行命令”，而是信息型回答，例如：

```text
用户：我想买一辆车
系统：搜索 / 汇总 / 比较 / 给出建议
```

传统 LLM 产品通常把结果展示成文字，最多附带文件。如果用户没有明确要求表格、图、卡片，系统就默认只输出文本。

TaskWeavn 的 UI 目标不同：用户的核心交互对象是 Task，而 Task 的结果也应该可以变成更清晰的 UI 对象。对于信息流回答，尤其是比较、推荐、清单、步骤、候选项、风险提示等结果，卡片化展示能让重点更清楚，视觉体验也更好。

LLM 本身擅长把结果结构化；如果 UI 提供稳定的展示方式，就可以引入一个专门的 **Result Packaging Agent**，把普通答案包装成 `ResultCardSet`。

---

## 2. 核心问题

包装结果本身应该是一个 Task，走 TaskBus。但触发这个 Task 有两种候选方式：

1. 协作者 Agent 判断是否需要发布包装 Task。
2. 每次任务结束后，系统自动判断是否需要发布包装 Task。

本计划采用第二种作为默认机制：

> 任务完成后，由 ResultPresentationPolicy 自动判断是否发布 Result Packaging Task。Collaborator Agent 可以提供 presentation hint，但不独占判断权。

原因：

- 包装需求来自“结果形态”，而不只来自“用户意图草案”。
- 搜索 / 分析 / 问答类任务可能在执行后才知道结果是否适合卡片化。
- 把判断放在任务结束后更稳定，减少 Collaborator 对所有任务类型的隐式责任。
- 包装 Task 仍走总线，符合 TaskWeavn 的任务系统边界。

---

## 3. 目标

1. 定义 `ResultArtifact` / `ResultCardSet` 等结果展示模型。
2. 定义 Result Packaging Agent 的职责：
   - 输入普通回答、引用、上下文、Task 信息；
   - 输出 UI 可渲染的卡片集合；
   - 保留原始文本结果。
3. 定义 ResultPresentationPolicy：
   - 判断某个完成结果是否值得卡片化；
   - 生成或跳过包装 Task；
   - 支持用户 / Collaborator / Pipeline hint。
4. 让包装任务成为普通 Task：
   - 通过 TaskPublisher 发布；
   - 进入 TaskBus；
   - 由具备 `result_packaging` capability 的 Agent 执行。
5. 为 UI 提供第一版卡片渲染接口。

---

## 4. 非目标

- 不做商业推荐流、广告推送或主动营销。
- 不在第一版实现复杂图表、可视化编辑器或自定义卡片 DSL。
- 不替代原始文本回答；卡片是增强展示，不是唯一答案。
- 不让 Result Packaging Agent 决定事实正确性；它只负责结构化和展示包装。
- 不在第一版支持所有卡片类型，只做最常见的信息型结果。

---

## 5. 设计原则

- **Result is still user-owned**：用户问的问题必须被直接回答，卡片不能变成系统自嗨。
- **Packaging is a Task**：包装由普通 Task 执行，方便审计、重试、跳过和替换 Agent。
- **Decision is lightweight**：是否包装的判断应便宜、可配置，不应每次都引入重型 LLM 调用。
- **Raw answer preserved**：原始文字答案必须保留，卡片失败不能导致最终回答丢失。
- **Cards are projections, not truth**：事实来源仍是原始结果、引用、消息和 Task 结果；卡片是 UI 投影。
- **No dark pattern**：不做推流、不做商业排序、不暗示系统在替用户做购买决策。

---

## 6. 核心概念

### 6.1 ResultArtifact

任务完成后可产生一个结果对象。第一版可以比较轻：

```python
class ResultArtifact(BaseModel):
    result_id: str
    session_id: str
    task_id: str | None
    source_message_id: str | None
    raw_text: str
    citations: list[CitationRef] = []
    structured_data: dict[str, Any] = {}
    created_at: datetime
```

说明：

- `raw_text` 是兜底展示。
- `structured_data` 可以来自原任务，也可以由包装 Agent 生成。
- 如果没有 `task_id`，表示这是 session-level 信息回答。

### 6.2 ResultCardSet

UI 渲染入口：

```python
class ResultCardSet(BaseModel):
    card_set_id: str
    result_id: str
    session_id: str
    task_id: str | None
    title: str
    summary: str
    cards: list[ResultCard]
    display_mode: Literal["inline", "panel", "task_detail"] = "inline"
    fallback_text: str
```

### 6.3 ResultCard

第一版建议支持：

```python
CardType = Literal[
    "summary",
    "option",
    "comparison",
    "checklist",
    "steps",
    "risk",
    "citation",
    "metric",
]

class ResultCard(BaseModel):
    card_id: str
    type: CardType
    title: str
    body: str
    highlights: list[str] = []
    actions: list[ResultCardAction] = []
    data: dict[str, Any] = {}
```

单个接口的数据细节可以后续细化。第一版重点是统一卡片集合、卡片类型、fallback、关联关系。

### 6.4 ResultPresentationDecision

```python
class ResultPresentationDecision(BaseModel):
    should_package: bool
    reason: str
    preferred_card_types: list[CardType] = []
    confidence: float
    source: Literal["policy", "collaborator_hint", "user_request", "pipeline"]
```

---

## 7. 触发策略

### 7.1 默认：任务结束后自动判断

流程：

```text
Task completed
  -> ResultPresentationPolicy.evaluate(task_result, messages, task metadata)
  -> if should_package:
       TaskPublisher.publish(ResultPackagingTask)
     else:
       keep raw text only
```

适合自动包装的结果：

- 有多个候选项，需要比较；
- 有推荐 / 取舍 / 风险；
- 有步骤清单；
- 有数据点 / 指标；
- 有引用来源；
- 有用户后续可操作选项；
- 文本较长，且可以被分块提炼。

不适合自动包装的结果：

- 一句话直接回答；
- 纯闲聊；
- 需要完整叙事语气的解释；
- 用户明确要求“只要文字”；
- 结构化会造成误导或过度简化。

### 7.2 Collaborator Agent 的角色

Collaborator Agent 可以在 Task 草案中设置 presentation hint：

```python
class TaskPresentationHint(BaseModel):
    prefer_result_cards: bool = False
    preferred_card_types: list[CardType] = []
    reason: str | None = None
```

但它不应该成为唯一判断者。

原因：

- Collaborator 看到的是任务意图，不一定看到执行结果。
- 执行结果可能比预期更简单或更复杂。
- 用户也可能在执行中改变要求。

### 7.3 用户显式请求

用户可以说：

- “给我卡片形式”
- “做成对比卡”
- “只要文字，不要卡片”

这类指令应优先于默认策略。

---

## 8. Result Packaging Task

包装任务是普通 Task。

建议 capability：

```text
result_packaging
```

任务输入：

```python
class ResultPackagingRequest(BaseModel):
    session_id: str
    task_id: str | None
    source_result_id: str
    raw_text: str
    citations: list[CitationRef] = []
    preferred_card_types: list[CardType] = []
    display_context: Literal["session_stream", "task_detail", "result_panel"]
```

任务输出：

```python
class ResultPackagingResult(BaseModel):
    card_set: ResultCardSet
    warnings: list[str] = []
```

执行约束：

- 不改写事实。
- 不新增未经来源支持的推荐。
- 如果结构化失败，返回 `fallback_text`。
- 卡片应能关联回原始结果和引用。

---

## 9. UI 行为

### 9.1 Session Message Stream

在 session-level 信息回答中：

```text
Assistant raw answer
ResultCardSet inline preview
```

用户可以展开卡片，查看原文和引用。

### 9.2 Task Detail

选中 Task Node 时：

- 显示该 Task 的原始结果；
- 显示 `ResultCardSet`；
- 如果 Task 有子节点，父节点可以展示子节点结果卡片摘要。

### 9.3 卡片操作

第一版卡片 action 只做轻量行为：

- open_source：查看来源；
- copy：复制内容；
- pin：固定到 Task summary；
- ask_followup：以该卡片作为上下文继续提问。

复杂动作例如“直接购买 / 下单 / 提交外部表单”不在第一版范围内。

---

## 10. 与 Pipeline / Publisher 的关系

Result Packaging 可以作为 `task_after` pipeline 的默认候选步骤，但不应该强制每个任务都执行。

推荐结构：

```text
Task after completed
  -> ResultPresentationPolicy
  -> maybe publish ResultPackagingTask
  -> TaskBus
  -> ResultPackagingAgent
  -> ResultCardSet persisted / emitted
```

这里有两个边界：

- Policy 负责“要不要包装”；
- Packaging Task 负责“怎么包装”。

这个设计比“Collaborator 负责判断一切”更可维护，也比“每次都包装”更克制。

---

## 11. 持久化与可重放

第一版需要记录：

- 原始结果消息；
- presentation decision；
- packaging task；
- card set artifact；
- 用户对卡片的后续操作或追问。

这样后端可以重现：

```text
用户问了什么
原始回答是什么
为什么系统决定生成卡片
卡片由哪个 Agent 生成
用户基于哪张卡片继续交互
```

---

## 12. 执行切片

### Slice 1: Result Schema

- `ResultArtifact`
- `ResultCardSet`
- `ResultCard`
- `ResultPresentationDecision`
- 最小序列化测试

### Slice 2: Presentation Policy

- 规则型策略：
  - 结果长度；
  - 候选项数量；
  - 结构化信号；
  - user/collaborator hint；
  - “只要文字”禁用。
- 第一版可以不调用 LLM。

### Slice 3: Result Packaging Agent

- Agent template / capability: `result_packaging`
- 接收 `ResultPackagingRequest`
- 输出 `ResultCardSet`
- 保留 fallback text

### Slice 4: TaskPublisher / Pipeline Integration

- 任务结束后触发 policy；
- policy 通过 TaskPublisher 发布 packaging task；
- packaging task 走 TaskBus；
- 不适合包装时跳过并记录 reason。

### Slice 5: UI API Projection

- Session stream 返回 card set reference；
- Task detail 返回 associated card sets；
- card action API 第一版支持 `open_source` / `copy` / `ask_followup`。

### Slice 6: UI Rendering

- inline card preview；
- task detail card panel；
- fallback raw text；
- empty / failed packaging state。

---

## 13. 验收标准

1. 短文本回答不会被强行包装。
2. 有多个候选项的回答会生成 `ResultPackagingTask`。
3. 包装任务通过 TaskBus 执行，而不是直接绕过总线。
4. 包装失败时，原始文本仍可展示。
5. 用户显式要求“只要文字”时，不生成卡片。
6. 用户显式要求“做成对比卡”时，policy 优先尊重。
7. UI 可以展示 `ResultCardSet`，并能回到原始文本和引用。
8. 结果卡片、包装任务、用户后续追问可被重放。

---

## 14. 风险

| Risk | Mitigation |
|---|---|
| 卡片化让回答看起来像商业推荐 | 明确禁止广告/推流语义；保留来源、原文和用户控制 |
| 过度包装导致 UI 嘈杂 | policy 默认克制；短答不包装；用户可关闭 |
| LLM 结构化产生幻觉 | card set 必须关联原文和引用；包装 Agent 不新增事实 |
| 包装任务导致任务数量膨胀 | policy 先判断；可配置阈值；可批量包装 |
| UI card schema 过早复杂化 | 第一版只支持少量 card type |

---

## 15. Open Questions

1. `ResultArtifact` 应该归属于 MessageStream，还是单独 artifact store？
2. `ResultPresentationPolicy` 是否需要 LLM 参与，还是第一版规则足够？
3. CardSet 是否应该允许用户手动编辑？
4. 父 Task 的结果卡片是否自动汇总子 Task 卡片？
5. 是否需要 session-level “关闭卡片化结果”的用户设置？

---

## 16. Status

- Status: planned
- Next Step: 在独立实现会话中先做 Slice 1 + Slice 2，验证 policy 不会过度包装。
