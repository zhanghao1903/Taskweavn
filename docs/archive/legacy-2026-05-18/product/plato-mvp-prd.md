# 柏拉图 Plato MVP PRD

> Status: MVP product requirements baseline
>
> Scope: 第一版柏拉图产品定义。本文回答“第一版做什么、为什么做、做到什么程度算成功”。它不是 UX Flow 规格、Figma 画面说明、前端组件文档或 API 合约。

## 1. 产品一句话

柏拉图是一个 Task-first 的智能工作台。

用户用自然语言表达目标，柏拉图将目标转化为可理解、可编辑、可确认、可执行、可追踪的 TaskTree，并在执行过程中持续展示状态、确认点、结果和审计入口。

```text
Natural language goal
  -> Project
  -> Workflow
  -> Session
  -> Session Workspace
  -> Draft TaskTree
  -> Review / confirm / edit
  -> Publish Tasks
  -> Execute
  -> Result / File Change Summary / Audit
```

## 2. MVP 目标

第一版不追求完整能力，而是证明核心产品心智成立：

```text
普通用户可以不用理解 Agent、Tool、Bus、Provider，
也能凭直觉完成“表达目标 -> 看懂任务 -> 确认动作 -> 查看结果”的路径。
```

MVP 的核心价值：

1. 用户能把模糊目标交给系统。
2. 系统能把目标展示为结构化 TaskTree。
3. 用户能在执行前理解和调整 TaskNode。
4. 系统执行时，用户能看到状态和确认请求。
5. 执行完成后，用户能找到结果、文件变更和审计入口。

## 3. 目标用户

### 3.1 第一优先级用户

非深度技术用户，但愿意让 AI 帮自己完成稍复杂任务的人。

他们可能是：

- 想搭建个人网站的普通用户。
- 想整理资料、生成计划、完成轻量项目的人。
- 能理解“任务”和“确认”，但不想理解 Agent、Tool、命令行的人。

他们需要：

- 系统先说明计划，而不是直接乱动。
- 每个关键动作有确认和上下文。
- 结果清楚，修改清楚。
- 不懂技术也能知道下一步该做什么。

### 3.2 第二优先级用户

轻技术用户或创作者。

他们可能愿意：

- 编辑 TaskTree。
- 指定某些 TaskNode 的负责人或能力。
- 查看文件修改摘要。
- 进入审计视图确认系统做了什么。

### 3.3 暂不优先服务

- 需要复杂企业权限的团队。
- 需要完整多 Agent 编排画布的高级用户。
- 需要完整 DevOps / CI 集成的开发团队。
- 需要全量审计、合规和日志查询的企业管理员。

这些用户以后可以支持，但不是 MVP 的优先目标。

## 4. 用户问题

现有 AI 产品常见问题：

1. 聊天流太长，用户难以知道系统到底理解了什么。
2. 系统直接执行，用户缺少执行前控制感。
3. 任务、结果、文件修改、确认动作散落在对话里。
4. 用户不知道系统什么时候需要自己介入。
5. 完成后只有总结，缺少可验收的结构。
6. 审计和调试信息要么不可见，要么过于技术化。

柏拉图 MVP 要解决的是控制感和可理解性，不是一次性解决所有自动化能力。

## 5. 产品原则

MVP 必须遵守以下原则：

1. Task-first，不是 Chat-first。
2. Workflow 是 Session 的用户语义模式。
3. Project 是用户组织工作的容器，不等同于执行用 workspace。
4. Session Workspace 是默认文件执行边界，避免多个 Session 默认并发修改同一工作区。
5. 重要工作先 Draft，再执行。
6. TaskNode 是最小交互锚点。
7. Main Page 是控制面。
8. Audit Page 是信任面。
9. Agent routing 是高级能力，默认不抢占普通用户心智。
10. UI 优先展示用户能行动的信息。
11. 内部系统对象只在提升控制或信任时暴露。

## 6. MVP 范围

### 6.1 必须包含

| 能力 | 说明 |
|---|---|
| Project 上下文 | 用户知道自己正在处理哪个项目或空间。 |
| Workflow 入口 | 用户知道自己正在用哪种工作模式。 |
| Session 创建与状态 | 用户知道当前协作过程在哪里。 |
| Session Workspace 提示 | 用户知道当前执行发生在隔离工作区中，而不是直接污染其他 Session。 |
| 自然语言输入 | 用户通过普通语言表达目标或补充信息。 |
| Draft TaskTree 展示 | 系统将目标转成可见任务结构。 |
| TaskNode 基础交互 | 用户能选中任务、查看详情、补充说明。 |
| 发布入口 | 用户能将 Draft TaskTree 发布为可执行 Tasks。 |
| 执行状态展示 | 用户能看到 TaskNode queued/running/waiting/done/failed。 |
| 用户确认动作 | 高影响动作以 TaskNode 上下文展示确认选项。 |
| Session Message Stream | 展示会话级过程消息。 |
| Task-scoped message projection | 选中 TaskNode 后能看到相关消息。 |
| Result 初版展示 | 用户能看到任务结果或总结。 |
| File Change Summary 初版展示 | 用户能看到文件修改摘要。 |
| Audit 入口 | 用户能进入或预期进入审计视图。 |

### 6.2 暂不包含

| 暂不做 | 原因 |
|---|---|
| 完整多 Agent 编排画布 | 容易把普通用户入口做重，先用 TaskNode routing 留余地。 |
| 完整 Audit Page | MVP 只需要信任入口和摘要，完整审计后续做。 |
| 完整配置中心 | 配置会影响体验，但不是第一版主路径。 |
| Agent Marketplace | 先验证 Task-first 主路径。 |
| 复杂 workflow engine | 暂不做循环、条件分支、补偿逻辑。 |
| 全量日志查询 | 属于审计/运维线，不进入 Main Page MVP。 |
| 复杂权限系统 | 单用户和本地优先假设足够支撑第一版。 |
| 完整移动端适配 | 第一版优先桌面工作台体验。 |

## 7. 核心用户路径

### 7.1 路径 A：从自然语言生成任务计划

```text
用户打开 Plato
  -> 选择或默认进入一个 Workflow
  -> 输入自然语言目标
  -> 系统进入 Understanding / Planning
  -> 生成 Draft TaskTree
  -> 用户看到 TaskTree 和 Session 消息
```

验收点：

- 用户知道系统没有直接执行。
- 用户能看懂 TaskTree 是系统对目标的理解。
- 用户能判断任务拆解是否大体合理。

### 7.2 路径 B：选中 TaskNode 并补充信息

```text
用户选中一个 Draft TaskNode
  -> 看到 TaskNode detail
  -> 输入补充说明
  -> 系统更新该 TaskNode 或追加相关消息
  -> 用户看到更新后的任务状态
```

验收点：

- 用户知道输入框当前作用于哪个 TaskNode。
- 用户能理解这是对任务的补充，不是新开一个全局聊天。

### 7.3 路径 C：发布并执行任务

```text
用户确认 Draft TaskTree 可执行
  -> 点击发布或运行
  -> TaskTree 进入 Published / Executing
  -> TaskNode 状态开始变化
  -> 用户看到执行过程消息
```

验收点：

- 用户知道哪些任务未开始、进行中、完成或失败。
- 用户能理解发布后任务进入执行系统。

### 7.4 路径 D：完成确认动作

```text
系统在某个 TaskNode 下请求确认
  -> 用户看到确认原因、影响范围、选项
  -> 用户选择确认 / 修改 / 跳过
  -> 系统继续或改变任务状态
```

验收点：

- 确认请求不是无上下文弹窗。
- 用户知道确认动作影响哪个 TaskNode。
- 用户知道不确认会发生什么。

### 7.5 路径 E：查看结果和文件变更

```text
TaskNode 完成
  -> 用户看到 Result
  -> 用户看到 File Change Summary
  -> 用户可进入 Audit 入口查看过程证据
```

验收点：

- 用户能找到结果。
- 用户能找到文件改动摘要。
- 用户知道哪里可以进一步追溯。

## 8. 主要页面范围

### 8.1 Main Page

MVP 的主要页面是 Main Page。

Main Page 是用户控制面，负责展示：

- 当前 Project。
- 当前 Workflow。
- 当前 Session。
- 当前 Session Workspace 的隔离边界提示。
- 自然语言输入。
- TaskTree / WorkTree。
- 选中 TaskNode detail。
- Session Message Stream。
- Task-scoped messages。
- Confirmation Card。
- Result Card。
- File Change Summary。
- Audit entry point。

Main Page 不负责展示：

- 全量日志。
- 原始 EventStream。
- 原始 Tool call 参数。
- Provider retry 细节。
- 完整风险模型细节。

### 8.2 Audit Page

MVP 只需要 Audit 入口和少量摘要，不要求完整页面。

入口应让用户理解：

```text
如果我不放心，可以在这里查看系统为什么这么做。
```

完整 Audit Page 后续作为独立信任面建设。

## 9. 核心对象

### 9.1 Project

用户眼中的项目或空间容器。

Project 用来帮助用户组织不同工作，但它不是第一版默认的文件写入边界。MVP 中，Project 可以理解为：

```text
一组相关 Workflow / Session 的集合。
```

Project 可以关联多个 Session。每个 Session 默认拥有自己的执行 workspace，完成后再通过显式动作沉淀、导出或合并结果。

### 9.2 Workflow

用户眼里的工作模式。

MVP 至少需要一个默认 Workflow：

```text
Task Planning & Execution
```

它支持：

- 自然语言目标输入。
- Draft TaskTree 生成。
- 用户审阅和补充。
- 发布执行。
- 查看结果。

后续可以拆出：

- Task Planning only。
- Project Execution。
- Research。
- Bug Fix。
- Result Packaging。

### 9.3 Session

一次 Workflow 运行实例。

MVP 用户可见状态：

```text
New
Understanding
Planning
Reviewing
Executing
Waiting for User
Completed
Failed
Paused
```

Session 默认拥有自己的执行 workspace。这个取舍用于降低并发修改、权限控制和回滚复杂度。跨 Session 合并或共享结果应通过显式动作完成，而不是默认共享同一个文件工作区。

### 9.4 Session Workspace

一次 Session 独占的文件执行边界。

用户不需要频繁操作 Session Workspace，但 UI 应在必要位置表达：

```text
当前修改发生在本次会话的隔离工作区中。
```

MVP 只需要展示轻量提示，不需要完整 workspace 管理页面。

### 9.5 TaskTree

系统对用户目标的结构化理解。

MVP 用户可见状态：

```text
Draft
Ready to Publish
Published
Executing
Completed
Partially Completed
```

### 9.6 TaskNode

最小交互锚点。

MVP 用户可见状态：

```text
Proposed
Needs Clarification
Ready
Queued
Running
Waiting for Confirmation
Done
Failed
Skipped
Cancelled
```

TaskNode 必须能承载：

- 标题和说明。
- 状态。
- 层级关系。
- 相关消息。
- 确认动作。
- 结果。
- 文件变更摘要。
- 可选 Agent / Capability 信息。

### 9.7 Message

MVP 使用一个 Session Message Stream，通过 `task_id` 聚合 Task-scoped view。

用户不需要理解 MessageBus。用户只需要理解：

```text
会话里有消息。
选中任务后，可以看到和这个任务有关的消息。
```

### 9.8 Result

Result 是用户验收的主要对象之一。

MVP 支持：

- 文本结果。
- 结构化摘要。
- Result Card。
- 和 TaskNode 关联。

### 9.9 File Change Summary

MVP 支持初版文件变更摘要。

要求：

- 子 TaskNode 展示直接变化。
- 父 TaskNode 可展示子节点聚合变化。
- Session 可展示全局摘要。

## 10. 功能需求

### 10.1 P0

| 编号 | 需求 |
|---|---|
| P0-1 | 用户可以创建或进入一个 Session。 |
| P0-2 | 用户可以在默认 Workflow 中输入自然语言目标。 |
| P0-3 | 系统可以展示 Draft TaskTree。 |
| P0-4 | 用户可以选中 TaskNode 查看详情。 |
| P0-5 | 用户可以对选中的 TaskNode 输入补充说明。 |
| P0-6 | 用户可以发布 Draft TaskTree。 |
| P0-7 | TaskNode 状态可以展示执行进度。 |
| P0-8 | 用户可以看到需要确认的 TaskNode。 |
| P0-9 | 用户可以提交确认选择。 |
| P0-10 | 用户可以查看 Result 和 File Change Summary。 |
| P0-11 | 用户可以看到 Audit 入口。 |

### 10.2 P1

| 编号 | 需求 |
|---|---|
| P1-1 | 支持多个 Workflow 模板的入口展示。 |
| P1-2 | 支持 TaskNode agent/capability routing 的只读展示。 |
| P1-3 | 支持失败 TaskNode 的 retry / skip 操作入口。 |
| P1-4 | 支持 Result Card 的多种展示类型。 |
| P1-5 | 支持更完整的 File Change Summary 聚合。 |
| P1-6 | 支持 Audit 摘要展开。 |

### 10.3 P2

| 编号 | 需求 |
|---|---|
| P2-1 | 自定义 Workflow。 |
| P2-2 | 自定义 Agent。 |
| P2-3 | 复杂 Task dependency / DAG 展示。 |
| P2-4 | 完整 Audit Page。 |
| P2-5 | 配置中心和高级自动化策略。 |

## 11. 非功能需求

### 11.1 可理解性

用户必须能在不阅读教程的情况下理解：

- 当前处于哪个 Workflow / Session。
- TaskTree 是什么。
- 哪个 TaskNode 需要操作。
- 输入框当前作用于哪里。
- 系统是否已经开始执行。

### 11.2 可控性

系统执行重要动作前应尽量让用户看到：

- 将要做什么。
- 影响哪个 TaskNode。
- 可能影响哪些文件或结果。
- 用户有哪些选项。

### 11.3 可追溯性

MVP 不需要完整审计页面，但必须保留：

- Audit entry point。
- 用户确认记录的可追溯入口。
- Result 和 File Change Summary 的来源关系。

### 11.4 性能体验

MVP 可以先使用 Mock 数据验证 UI，但真实联调时应避免：

- 长时间无反馈。
- 状态跳变不可解释。
- TaskTree 更新导致用户失去位置。

## 12. 成功标准

第一版成功标准不是“界面很美”，而是“用户能走通”。

### 12.1 用户测试标准

给用户一个任务，例如：

```text
帮我规划一个个人网站项目。
```

用户应能独立完成：

1. 输入目标。
2. 看懂系统生成的 TaskTree。
3. 选中一个 TaskNode。
4. 对 TaskNode 补充说明。
5. 找到发布 / 执行入口。
6. 找到需要确认的任务。
7. 完成确认动作。
8. 找到结果和文件变更摘要。
9. 说出 Audit 入口大概是做什么的。

### 12.2 产品判断标准

如果用户能说出下面这句话，产品心智基本成立：

```text
我说出目标，柏拉图帮我拆成任务。
我可以先看和改，再让它执行。
执行时我能看到哪里需要我确认，完成后我能看到结果和改动。
```

## 13. 风险与取舍

| 风险 | 说明 | MVP 取舍 |
|---|---|---|
| UI 过复杂 | TaskTree、Message、Result、Audit 同时出现会压迫用户。 | 先围绕主路径组织信息，高级信息折叠。 |
| 像任务管理器 | 如果缺少自然语言和执行过程，会变成普通 Task App。 | 保留 Workflow、自然语言、执行状态和确认动作。 |
| 像聊天工具 | 如果 TaskTree 不突出，会退化为 Chat UI。 | TaskTree 必须是主对象。 |
| 审计太重 | 主页面展示太多内部信息会吓退用户。 | Main Page 只放入口和摘要。 |
| 后端接口过早固化 | UI 还没验证前定义接口容易返工。 | 先用 fixtures / stories 验证前端交互，再定 API 合约。 |
| Figma 过度追求美观 | 视觉好看但对象关系不清楚。 | 评审优先看路径和对象心智。 |

## 14. PRD 之后的下一步

本 PRD 的直接下游是 UX Flow Spec：

```text
docs/product/plato-main-page-ux-flow.md
```

UX Flow Spec 应把本文转成可生成 Figma 的交互输入，重点回答：

- Main Page 有哪些关键状态。
- 用户从空状态到结果完成怎么走。
- TaskNode 在不同状态下怎么显示和交互。
- 输入框在 session-level 和 task-scoped 下如何变化。
- 确认动作如何出现。
- Result / File Change Summary / Audit entry 如何进入视野。
