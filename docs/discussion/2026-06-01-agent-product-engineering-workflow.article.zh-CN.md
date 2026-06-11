# 做 Agent 产品，不要先写页面：状态模型、工作流和可恢复性更重要

> 发布草稿
> 来源：`2026-06-01-ai-assisted-project-failure-memo.md`
> 主题：Agent 产品工程化、前端架构、状态模型、DFX、AI 协作工作流
> 适合读者：前端架构师、AI 应用工程师、技术 PM、Agent 产品开发者

---

## 开场

很多 Agent 产品一开始都会从一个页面开始：左边是任务或会话，中间是工作区，右边是详情，底部是输入框。用户输入目标，Agent 开始执行，页面显示进度。

这看起来像一个前端问题。但我在一个月的 AI 辅助开发里得到的结论是：Agent 产品最早不能从页面开始，至少不能只从页面开始。

更合理的顺序是：

```text
任务语义
-> 状态模型
-> 交互生命周期
-> API / ViewModel contract
-> reducer / event model
-> mock 或 sidecar runtime
-> 页面实现
```

如果跳过前面的模型，直接做 UI，早期会显得很快，后期会被状态复杂度反噬。

这篇文章总结的是一个实际项目里的工程教训。

---

## 1. Agent 产品的 UI 不是静态信息展示

普通管理后台里，一个页面常见状态是 loading、empty、error、success。Agent 产品不是这样。

Agent 产品的页面要同时表达多个维度：

- 用户目标是否已经被理解？
- RawTask 是否已创建？
- DraftTaskTree 是否已生成？
- TaskTree 是否已发布？
- 某个 Task 是否 ready？
- Task 是否 pending、running、done、failed？
- 是否等待用户确认？
- 是否等待用户补充信息？
- 用户是否有权限执行当前动作？
- 当前 snapshot 是否过期？
- 结果摘要是否存在？
- 文件变更证据是否可读？
- 审计结论是 passed、warning、failed 还是 inconclusive？

这些维度不能压缩成一个 `status`。

如果前端只拿到一个扁平状态，很容易出现下面的问题：

- `failed` 同时表示执行失败、权限失败、查询失败、证据加载失败。
- `done` 无法说明结果是否已生成、文件摘要是否存在、审计是否通过。
- `waiting` 无法区分等待用户确认、等待用户补充信息、等待后端队列。
- `readonly` 无法区分用户权限限制、Audit 页面只读、snapshot stale。

结果就是 UI 变得含糊，代码也开始到处写 if。

所以第一条经验是：

> Agent 产品必须把状态拆成独立维度，而不是用一个全局 status 驱动所有 UI。

---

## 2. 页面实现前，先定义 canonical status model

在这个项目里，后来稳定下来的状态模型至少包括这些维度：

1. planning state：系统是否正在理解和规划。
2. task readiness：任务节点是否可执行。
3. execution status：任务执行生命周期。
4. confirmation status：确认动作生命周期。
5. permission/action availability：用户或系统动作是否可用。
6. audit verdict：审计结论。

每个维度都要定义：

- allowed values
- 语义
- 后端 owner field
- 前端 owner field
- UI label 和 tone
- transient / terminal 分类
- unknown / error handling

这个模型不是“文档洁癖”。它直接决定前端能不能写干净。

例如，任务执行失败时，UI 需要知道：

- planning 是否已经结束？
- TaskTree 是否已经发布？
- 当前 Task 是否 terminal failed？
- 有没有 error_ref？
- error_ref 能否读取到 summary？
- 用户能否 retry？
- retry 是 task-level 还是 session-level？
- Audit 入口是否仍然可用？

如果这些信息不在 contract 里，前端只能猜。猜出来的 UI 通常不可维护。

---

## 3. Figma 不能替代状态模型

这个项目在 Figma 上投入过重。我们做了 token、component skeleton、screen states、prototype flows、dev handoff，甚至多轮治理和 hygiene pass。

问题是，Figma 可以表达“一个状态长什么样”，但它不能自然保证“状态体系是否完备”。尤其在 AI 操作 Figma 时，常见问题是：

- 组件看起来存在，但语义不足。
- 页面状态很多，但彼此差异不清晰。
- metadata 很完整，但画面不可读。
- 设计系统很规范，但实现路径仍然不明确。
- 老静态稿反而比新规范稿更像产品。

最后证明，对早期 Agent 产品更有价值的是：

- 静态视觉 baseline
- screen state spec
- frontend architecture plan
- API contract
- mock/runtime adapter

Figma 应该服务于这些文档，而不是替代它们。

经验是：

> Agent 产品的 Figma 可以作为视觉基准和讨论材料，但不要在状态模型稳定前把它作为实现源。

---

## 4. API contract 要描述状态，而不是只描述数据

很多 API 合约容易写成字段列表。但 Agent 产品的 API 合约必须描述状态变化和 UI 后果。

例如发布任务树不是简单返回 `ok: true`。它至少要回答：

- command 是否被 accepted？
- command 是否最终 done / failed / rejected？
- 失败是否 retryable？
- affected scopes 是什么？
- 前端应该 refresh 哪些 query？
- result_ref / error_ref 是否可读取？
- snapshot cursor 是否过期？
- 是否需要 resync？

这个项目曾经出现过一个典型问题：UI snapshot 里有一个 `taskTree.id`，看起来像 draft tree id；发布时前端把它当成真实 draft_tree_id 传给后端；后端找不到对应 DraftTaskTree，发布失败。

表面看是 bug，深层原因是 contract 没说清楚 identity：

- 哪些 id 是真实领域对象 id？
- 哪些 id 是 projection/synthetic view id？
- command 应该显式传 draft_tree_id，还是默认解析 active draft tree？
- identity mismatch 时应该返回什么结构化错误？

后来修复方向不是让前端“猜对 id”，而是把 RawTask、DraftTaskTree、AuthoringState 持久化，并让 gateway 能从 session 解析 active draft tree，必要时返回结构化 identity error。

经验是：

> API contract 不只是字段定义，它必须明确 identity、状态转换、错误语义和 UI 刷新策略。

---

## 5. DFX 是 Agent 产品的主路径，不是后期优化

DFX 可以拆成四件事：

- Durability：草稿、任务、结果不能丢。
- Feedback：用户知道系统正在做什么。
- Recoverability：失败或重启后能恢复。
- Explainability：用户知道为什么这样做。

在普通应用里，持久化和恢复可能被当成工程质量。但在 Agent 产品里，它们是用户信任的基础。

这个项目里，RawTask / DraftTaskTree 最初没有持久化。结果是系统重启后，用户未发布的任务草稿会丢。这个问题直接破坏主路径，因为用户会觉得“我刚才和系统协作出的计划不见了”。

后来补上的关键能力包括：

- SqliteRawTaskStore
- SqliteDraftTaskTreeStore
- SqliteAuthoringStateStore
- restart recovery
- single active draft tree
- publish idempotency
- result/error summary store
- message stream bridge
- file change summary projection

这些能力没有让产品显得更“智能”，但让产品变得可信。

经验是：

> Agent 产品的 1.0 不是“能调用 LLM”就够了，而是要保证用户工作不会因为重启、失败、刷新而消失。

---

## 6. TaskBus 的价值应收敛为生命周期事实，而不是早期智能编排

项目初期，我高估了 TaskBus 和多 Agent 编排的价值。

理论上，TaskBus 可以支持多个 Agent claim 任务、并行执行、能力路由、依赖协调。这个方向有吸引力，但 Product 1.0 阶段真正暴露的问题是更基础的：

- 单个任务能否可靠发布？
- 未 claim 的任务能否启动？
- running 任务重启后如何恢复？
- failed 任务如何 retry？
- 用户能否看到结果和错误？
- 任务之间是否应该默认线性执行？

所以 TaskBus 的定位需要收敛。

更稳的 1.0 定位是：

> TaskBus 是任务生命周期事实来源，记录 pending、claimed、running、done、failed，而不是一开始承担复杂多 Agent 智能调度。

多 Agent 并行要等上下文治理成熟之后再扩展。因为多 Agent 最大的问题不是并发本身，而是上下文隔离、证据归属、冲突处理和用户理解成本。

---

## 7. AI 协作需要 workflow gate

AI coding 最大的问题之一是：它很会执行局部任务，但不天然知道产品交付顺序。

用户说“继续下一步”，AI 很可能直接继续。但下一步是否应该做，取决于上游 artifact 是否存在：

- PRD 是否清晰？
- UX flow 是否定义？
- screen states 是否完整？
- component spec 是否存在？
- frontend architecture 是否稳定？
- API contract 是否存在？
- mock data 是否可运行？
- backend integration 是否准备好？

如果这些检查靠人临时想起，很容易漏。

后来项目把 workflow gate 写进 agent instructions。每个任务开始前必须输出：

- 当前 workflow phase
- task type
- required upstream artifacts
- found artifacts
- missing/weak artifacts
- implementation allowed or blocked
- execution scope
- acceptance criteria
- risks and assumptions

这并不复杂，但很有效。它把 AI 从“立刻执行者”约束成“产品流程协作者”。

经验是：

> AI 辅助工程的核心治理手段不是更长的 prompt，而是可重复执行的 workflow gate。

---

## 8. 更合理的早期交付顺序

如果重新做一次，我会把 Agent 产品早期交付顺序改成这样：

```text
1. 产品主路径
2. Task / Session / Message 的用户语义
3. canonical status model
4. screen state spec
5. API / ViewModel contract
6. event / reducer contract
7. minimal visual baseline
8. mock runtime or sidecar runtime
9. vertical slice UI
10. restart recovery / result exposure / error recovery
11. audit and advanced evidence
12. richer design system and prototype
```

注意，Figma 和组件系统没有消失，但它们的位置后移了。

因为在 Agent 产品里，最先需要验证的是“系统行为是否可理解”，不是“组件是否规范”。

---

## 9. 可以直接复用的检查清单

如果你也在做 Agent 产品，可以在写页面前问这些问题：

1. 用户输入会落到哪个领域对象上？
2. 未执行 Task 对用户意味着什么？
3. 执行中 Task 对用户意味着什么？
4. 完成后 Task 展示的是结果、证据，还是摘要？
5. 如果缺少信息，系统如何 ASK 用户？
6. 如果用户刷新或重启，草稿是否还在？
7. 如果 command accepted 但最终 failed，UI 怎么表达？
8. 如果 snapshot stale，UI 是报错还是保留旧内容并提示 resync？
9. 如果用户没有权限，哪些动作 disabled，哪些内容 hidden？
10. result_ref / error_ref 指向什么对象，前端如何读取？
11. message stream 展示 Agent 原话，还是展示产品化摘要？
12. 文件变化是证据，还是 Agent 的自然语言描述？

如果这些问题没有答案，页面做得越快，返工越大。

---

## 结尾

AI 让工程实现速度变快，但 Agent 产品的困难不在于“能不能写出代码”。真正困难的是让用户理解系统正在做什么、为什么这样做、什么时候需要自己介入，以及失败后如何恢复。

所以，做 Agent 产品的工程顺序应该更保守：

- 不要先迷恋多 Agent。
- 不要先生产化 Figma。
- 不要先写复杂页面。
- 不要把所有状态塞进一个 status。
- 不要把可恢复性留到最后。

先定义语义，先定义状态，先定义 contract，先跑通一条闭环。

AI 可以帮你很快实现一切，但它不会自动替你判断什么应该先实现。这个判断，仍然是产品和工程负责人最核心的工作。
