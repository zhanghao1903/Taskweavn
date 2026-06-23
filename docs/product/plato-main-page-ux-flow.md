# 柏拉图 Plato Main Page UX Flow Spec

> Status: UX flow baseline
>
> Last Updated: 2026-06-19
>
> Scope: Main Page 第一版交互流程、关键画面状态、对象状态变化和 Figma 输入。本文不是最终视觉稿、组件 API 或后端接口文档。

## 0. 2026-06-19 Session-First Direction Update

Main Page 的产品核心从“Plan 页面”收敛为“Session 工作台”。

```text
Session = 核心工作单元与连续对话时间线
Conversation = 用户感知层
Plan = Session 内的一段结构化工作
Direct Task = Session 内的一段轻量执行工作
TaskNode = 可执行工作锚点
```

Plan 完成后不自动归档。完成的 Plan 仍作为当前 active work 展示，直到用户点击：

```text
Archive plan
```

归档后，Plan 从 active work 区域移入 Session history；Conversation 不清空，用户仍可向前滚动查看之前 Plan 的内容。历史 Plan 的主入口应位于 Session 级 `Plans` / `History`，并可通过 Conversation 中的 `Plan archived` 边界项进入。

## 1. 目标

Main Page 是柏拉图的用户控制面。

它要让用户在不理解内部系统概念的情况下完成主路径：

```text
输入目标
  -> 看到对话响应和必要的 Plan / Direct Task
  -> 看到 Draft TaskTree（当请求需要 Plan）
  -> 选中 TaskNode
  -> 补充或确认
  -> 发布执行
  -> 看到执行状态
  -> 完成确认动作
  -> 查看 Result / File Change Summary
  -> 需要时进入 Audit
```

第一版 UX Flow 的目标不是覆盖所有页面，而是让 Figma 可以生成一组连贯的核心状态画面。

## 2. UX 原则

1. Session Conversation 是用户感知主线，不能被 Plan 切断。
2. TaskTree / Plan & Progress 是结构化控制面，不能替代 Session。
3. TaskNode 是最小交互锚点。
4. 用户输入框必须显示当前作用域。
5. 确认动作必须挂在具体 TaskNode 上。
6. Result 和 File Change Summary 必须容易找到。
7. Audit 入口可见但不打扰主流程。
8. Main Page 展示用户下一步要做什么，不展示完整内部细节。
9. 完成的 Plan 由用户手动归档，归档不清空 Conversation。

## 3. Main Page 信息模型

Main Page 需要同时承载五类信息。这里有一个关键取舍：

```text
Project
  -> Workflow
      -> Session
          -> Session Workspace
          -> TaskTree / TaskNode
```

`Project` 是用户眼中的项目容器；`Workflow` 是工作模式；`Session` 是一次具体工作；`Session Workspace` 才是 Agent 实际读写文件的隔离边界。

第一版不要把用户眼中的 Project 和执行用 Workspace 混在一起。这样做不是因为概念上更漂亮，而是为了避免多个 Session 默认并发修改同一个文件工作区，也避免过早引入复杂权限控制。

| 信息 | 用户问题 | UX 表达 |
|---|---|---|
| Project / Workflow / Session | 我在哪个项目、模式和会话里？ | 顶部 Project、当前 Workflow、当前 Session 状态 |
| TaskTree | 系统打算怎么做？ | 主 TaskTree / WorkTree 视图 |
| Detail Panel | 当前焦点对象是什么？我能做什么？ | 动态 Context Inspector |
| Message Stream | 系统过程发生了什么？ | Session 消息流 + Task scoped projection |
| Result / File Change / Audit | 产出了什么，改了什么，能否追溯？ | 结果卡、文件变更摘要、审计入口 |
| Routing / Assignment | 谁负责这个 TaskNode？为什么？ | 轻量 Agent/capability 标记，必要时进入 Audit |

### 3.1 Detail Panel 动态语义

Detail Panel 不是固定的 Task 详情页，而是当前焦点对象的 `Context Inspector`。

| 页面阶段 | Detail Panel 展示 |
|---|---|
| 会话开始前 | Workflow 信息、适用场景、输入方式、交付物、默认策略 |
| 理解和规划中 | Session 目标、系统正在做什么、可补充信息 |
| Draft TaskTree 阶段 | TaskTree 审阅说明、发布前检查、选中任务后的 TaskNode Detail |
| 执行中 | 当前 Session Workspace、执行状态、选中 TaskNode 的过程信息 |
| 需要确认 | 挂在具体 TaskNode 上的确认卡、影响范围、用户选项 |
| 完成后 | Summary、Result、File Change Summary、Audit 入口 |

这意味着右侧面板的标题、内容和操作会随用户焦点变化。用户不用理解内部对象类型，但必须知道“当前面板正在解释哪个对象”。

## 4. 推荐画面集合

第一版 Figma 至少生成以下 9 个画面状态。

| 编号 | 画面 | 用途 |
|---|---|---|
| S1 | Empty / New Session | 用户首次进入，看到 Workflow 和输入入口。 |
| S2 | Understanding | 用户提交目标后，系统正在理解和规划。 |
| S3 | Draft TaskTree Ready | Draft TaskTree 已生成，等待用户审阅。 |
| S4 | TaskNode Selected | 用户选中一个任务，查看详情和相关消息。 |
| S5 | TaskNode Editing | 用户对选中任务补充说明或修改。 |
| S6 | Published / Running | TaskTree 已发布，TaskNode 进入执行状态。 |
| S7 | Waiting For Confirmation | 某个 TaskNode 需要用户确认。 |
| S8 | Completed With Result | 任务完成，展示结果卡。 |
| S9 | File Change Summary + Audit Entry | 展示文件变更摘要和审计入口。 |

## 5. 全局页面骨架

> 这是结构说明，不是最终布局规定。

Main Page 建议采用稳定工作台结构：

```text
+--------------------------------------------------------------+
| Top Bar: Plato / Project / Workflow / Session / Status        |
+----------------------+----------------------+----------------+
| Workflow + Sessions  | Main Work Area       | Detail Panel   |
|                      | TaskTree / Messages  | Context info   |
|                      | Session Workspace   | Result / Files |
+----------------------+----------------------+----------------+
| Context-aware input: session-level or task-scoped             |
+--------------------------------------------------------------+
```

布局重点：

- 左侧/主区域必须能清楚展示 TaskTree。
- 详情区只服务当前选中对象。
- 输入框的作用域必须明确。
- Message Stream 不应抢走 TaskTree 的主视觉地位。
- 左侧导航必须表达 `Workflow -> Sessions` 的层级，而不是把两者做成并列列表。
- Session Workspace 只作为执行边界提示出现，不应成为用户主要操作对象。

### 5.1 左侧导航层级

推荐左侧导航顺序：

```text
Workflow
  任务规划与执行
  调研与结果卡
  Bug 修复
  结果验收

Sessions in this workflow
  个人网站项目规划
  产品介绍页
  博客迁移
```

原因：

- Workflow 是工作模式，决定输入方式、默认策略和交付件。
- Session 是 Workflow 下的一次工作，不应在 UX 上压过 Workflow。
- 用户可以先理解“我要用哪种工作方式”，再理解“我要进入哪一次工作”。
- 执行用 workspace 默认挂在 Session 下，并且与其他 Session 隔离。

## 6. 状态 S1：Empty / New Session

### 6.1 用户看到

- 产品名 `柏拉图 / Plato`。
- 当前默认 Workflow，例如 `Task Planning & Execution`。
- 一个清晰的自然语言输入入口。
- 简短提示：用户可以描述目标。
- 空的 TaskTree 区域或欢迎状态。
- Audit 入口可以存在，但弱化。

### 6.2 用户能做

- 输入目标。
- 切换 Workflow（MVP 可只展示入口，不一定完整实现）。
- 进入已有 Session（如果存在）。

### 6.3 输入框提示

```text
描述你想完成的事，例如：帮我规划一个个人网站项目
```

### 6.4 状态转移

```text
用户提交目标
  -> S2 Understanding
```

### 6.5 设计注意

不要做成营销首页。
这是工作台空状态，不是 landing page。

## 7. 状态 S2：Understanding

### 7.1 用户看到

- Session 状态：`Understanding` 或 `正在理解目标`。
- 用户刚输入的目标。
- 系统正在生成 TaskTree 的轻量反馈。
- TaskTree 区域可显示骨架屏或规划中状态。
- Message Stream 中出现系统过程消息。

### 7.2 用户能做

- 等待。
- 取消。
- 追加说明（可选，MVP 可以弱化）。

### 7.3 文案示例

```text
正在把你的目标整理成可执行的任务结构。
```

### 7.4 状态转移

```text
TaskTree 生成成功 -> S3 Draft TaskTree Ready
需要澄清 -> S4/S5 的任务补充模式或 clarification message
失败 -> Error state（MVP 可简化）
```

### 7.5 设计注意

等待状态必须解释系统正在做什么，不能只有“AI 正在思考”。

## 8. 状态 S3：Draft TaskTree Ready

### 8.1 用户看到

- Session 状态：`Reviewing`。
- TaskTree 状态：`Draft`。
- 多个 TaskNode，带层级、标题、状态。
- 明显但不刺眼的主操作：`发布任务` / `开始执行`。
- Session Message Stream 中说明系统生成了任务计划。

### 8.2 用户能做

- 选中 TaskNode。
- 对 TaskTree 进行初步审阅。
- 发布 TaskTree。
- 继续输入全局补充。

### 8.3 TaskNode 初始显示

每个 TaskNode 至少展示：

- 标题。
- 简短意图。
- 状态：`Proposed` / `Ready`。
- 是否有子任务。
- 可选 capability / agent hint。

### 8.4 状态转移

```text
选中 TaskNode -> S4 TaskNode Selected
发布 TaskTree -> S6 Published / Running
输入全局补充 -> S2/S3 更新态
```

### 8.5 设计注意

用户必须能感知：现在还没有正式执行。
Draft 和 Published 必须视觉上有区别。

## 9. 状态 S4：TaskNode Selected

### 9.1 用户看到

- 被选中的 TaskNode 高亮。
- Detail Panel 展示：
  - 标题。
  - 任务意图。
  - 状态。
  - 父子关系。
  - 相关消息。
  - 预期结果。
  - 可选 agent/capability。
- 输入框变为 Task-scoped。

### 9.2 用户能做

- 对该 TaskNode 补充说明。
- 请求拆分或修改。
- 查看相关消息。
- 如果任务已完成，查看结果和文件变更。

### 9.3 输入框提示

```text
正在补充当前任务：{TaskNode title}
```

### 9.4 状态转移

```text
输入补充 -> S5 TaskNode Editing
取消选择 -> S3 Draft TaskTree Ready
发布 TaskTree -> S6 Published / Running
```

### 9.5 设计注意

输入作用域必须非常清楚。
这是防止误操作的关键。

## 10. 状态 S5：TaskNode Editing

### 10.1 用户看到

- 当前 TaskNode 仍然选中。
- 用户刚输入的补充信息。
- 系统正在更新该 TaskNode 或追加任务相关消息。
- TaskNode 可能出现 `Needs Clarification`、`Ready`、`Updated` 等反馈。

### 10.2 用户能做

- 接受更新。
- 继续补充。
- 回到 TaskTree 审阅。

### 10.3 文案示例

```text
已将这条补充加入当前任务。
```

或：

```text
这个补充会改变任务范围，建议确认后再发布。
```

### 10.4 状态转移

```text
更新完成 -> S4 TaskNode Selected
继续补充 -> S5
发布 -> S6
```

### 10.5 设计注意

不要让用户感觉这是新开了一轮全局聊天。
所有反馈都应保持和当前 TaskNode 的关联。

## 11. 状态 S6：Published / Running

### 11.1 用户看到

- TaskTree 状态：`Published` / `Executing`。
- TaskNode 状态开始变化：
  - `Queued`
  - `Running`
  - `Waiting for Confirmation`
  - `Done`
  - `Failed`
- Session Message Stream 显示执行过程。
- 发布按钮消失或变成运行状态。

### 11.2 用户能做

- 查看运行状态。
- 选中正在执行的 TaskNode。
- 对 Running TaskNode 追加指导（MVP 可只展示入口）。
- 暂停或停止（MVP 可不做完整行为）。

### 11.3 状态转移

```text
需要确认 -> S7 Waiting For Confirmation
任务完成 -> S8 Completed With Result
任务失败 -> Failed state（MVP 可在 S6 内表达）
```

### 11.4 设计注意

Published 后，用户应感知“系统已经开始行动”。
Draft 的自由编辑能力应收敛，避免用户误以为仍可任意修改结构。

## 12. 状态 S7：Waiting For Confirmation

### 12.1 用户看到

- TaskNode 状态：`Waiting for Confirmation`。
- Confirmation Card 挂在该 TaskNode detail 或相关 message 上。
- 确认原因。
- 影响范围。
- 选项。
- 推荐操作或默认值（如果有）。

### 12.2 Confirmation Card 必须包含

- 标题：需要确认什么。
- 关联 TaskNode。
- 系统将要做什么。
- 可能影响什么。
- 用户选项。
- 取消 / 修改入口。

### 12.3 选项示例

```text
确认执行
先预览
修改任务
跳过此任务
```

### 12.4 状态转移

```text
确认执行 -> S6 Running
修改任务 -> S5 TaskNode Editing
跳过 -> S6 / TaskNode Skipped
失败 -> Failed state
```

### 12.5 设计注意

确认不能是无上下文弹窗。
确认必须让用户知道“这会影响哪个任务”。

## 13. 状态 S8：Completed With Result

### 13.1 用户看到

- TaskNode 状态：`Done`。
- Result Card。
- 简短总结。
- 可能的后续动作：
  - 查看文件变更。
  - 继续追问。
  - 创建 follow-up Task。
  - 查看审计。

### 13.2 Result Card 内容

MVP Result Card 至少包含：

- 结果标题。
- 结果摘要。
- 关联 TaskNode。
- 生成时间或完成状态。
- 后续操作入口。

### 13.3 状态转移

```text
查看文件变更 -> S9
继续追问 -> S4/S5 task-scoped follow-up
查看审计 -> Audit entry
```

### 13.4 设计注意

结果不应该只出现在消息流末尾。
它应该成为 TaskNode detail 中可被找到的稳定对象。

## 14. 状态 S9：File Change Summary + Audit Entry

### 14.1 用户看到

- 当前 TaskNode 的文件变更摘要。
- 如果是父 TaskNode，展示子任务聚合变更。
- Session 级别可以展示全局变更摘要入口。
- Audit entry point。

### 14.2 File Change Summary 内容

MVP 至少展示：

- 文件路径。
- 变化类型：created / modified / deleted。
- 简短说明。
- 关联 TaskNode。

### 14.3 Audit Entry 内容

Audit 入口文案应简单：

```text
查看这个任务的执行记录
```

或：

```text
查看系统为什么这样做
```

### 14.4 状态转移

```text
点击文件 -> 文件预览或后续实现
点击 Audit -> Audit Page / Audit Drawer（MVP 可只做入口）
返回 TaskTree -> S8/S6
```

### 14.5 设计注意

File Change Summary 是验收入口，不是开发者日志。
Audit 是信任入口，不是主流程负担。

## 15. 输入框上下文规则

同一个输入框在不同上下文下有不同语义。

| 上下文 | 输入语义 | UI 必须提示 |
|---|---|---|
| 未选择 TaskNode | Session-level 目标或全局补充 | “描述你的目标或补充当前会话” |
| 选中 Draft TaskNode | 修改、补充、拆分当前任务 | “正在补充当前任务：...” |
| 选中 Running TaskNode | 追加指导或提供信息 | “给正在执行的任务补充信息” |
| 选中 Waiting TaskNode | 回答系统请求或补充确认依据 | “回复此确认请求” |
| 选中 Done TaskNode | 追问结果或创建 follow-up | “基于此结果继续提问” |

规则：

- 输入框必须显示当前作用域。
- 切换 TaskNode 时，输入框提示要变化。
- 用户应能清除选择，回到 Session-level 输入。
- 对高影响修改，应提示用户确认。

## 16. TaskNode 状态显示规则

| 状态 | 用户含义 | 推荐显示 |
|---|---|---|
| Proposed | 系统建议的任务 | 弱状态标签 |
| Needs Clarification | 需要补充信息 | 明显提示 |
| Ready | 可发布 | 正向状态 |
| Queued | 等待执行 | 中性状态 |
| Running | 正在执行 | 进行中状态 |
| Waiting for Confirmation | 需要用户确认 | 强提示 |
| Done | 已完成 | 完成状态 |
| Failed | 失败 | 错误状态 |
| Skipped | 已跳过 | 弱化状态 |
| Cancelled | 已取消 | 弱化状态 |

状态颜色必须配合文字或图标，不能只依靠颜色。

## 17. Message 展示规则

Main Page 中的消息分两种视图：

1. Session Message Stream：会话级过程。
2. Task-scoped Message Projection：当前 TaskNode 相关消息。

MVP 消息类型：

| 类型 | 用途 |
|---|---|
| informational | 系统说明、过程更新 |
| actionable | 需要用户操作的消息 |
| response | 用户回答或确认 |
| result | 结果摘要 |
| audit_summary | 审计摘要入口 |

设计规则：

- actionable message 必须有清晰操作。
- result message 应能沉淀为 Result Card。
- audit_summary 不应压过主流程。
- Task-scoped view 应说明消息来自同一 Session。

## 18. Figma 生成输入摘要

给 Figma 的设计输入可以概括为：

```text
Design a desktop-first Main Page for Plato, a Session-first intelligent
workbench with Task-first execution control.
The page should show Workflow, Session, Draft TaskTree, TaskNode details,
Session messages, Task-scoped messages, confirmation cards, result cards,
file change summaries, and a lightweight audit entry.

The visual style is Modern Classical Workbench: calm, structured, legible,
rational, trustworthy, with restrained blue/gold/cream/gray colors,
fine borders, stable grids, and low-noise panels.

Generate states:
1. Empty new session.
2. Understanding user goal.
3. Draft TaskTree ready.
4. TaskNode selected.
5. TaskNode editing.
6. Published and running.
7. Waiting for confirmation.
8. Completed with result.
9. File change summary with audit entry.
```

## 19. UX Flow 验收标准

这份 Flow 生成的原型必须能回答：

1. 用户是否知道当前 Workflow 和 Session？
2. 用户是否能看到 TaskTree？
3. 用户是否能选中 TaskNode？
4. 用户是否知道输入框作用于哪里？
5. 用户是否知道系统是否已经执行？
6. 用户是否能找到需要确认的动作？
7. 用户是否能找到 Result？
8. 用户是否能找到 File Change Summary？
9. 用户是否知道 Audit 入口是做什么的？

如果这些问题无法从画面中自然得到答案，Figma 原型需要重做。

## 20. 下一步

本 UX Flow Spec 的直接下游是 Figma / UX 原型。

建议下一步：

```text
已使用本文和设计哲学文档生成 Figma UI baseline 1.0
  -> 评审 9 个关键状态
  -> 持续修订 UX Flow 或视觉稿
  -> 以前端技术设计与工程重建为下一步
```
