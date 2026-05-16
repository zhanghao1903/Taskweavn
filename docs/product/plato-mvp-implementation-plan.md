# 柏拉图 Plato MVP 实施计划

> Status: UX implementation plan baseline
>
> Scope: 从产品定义到第一版可运行 UI 的实施路径。本文关注工作流、产出物、阶段边界和验收标准，不替代具体 PRD、UX Flow、Figma 文件或 API 合约。

## 1. 目标

第一版目标不是把柏拉图做得尽善尽美，而是让产品动起来。

MVP 应该证明一件事：

```text
普通用户可以用自然语言启动一个 Workflow，
看到系统生成的 TaskTree，
理解每个 TaskNode 的状态，
完成必要确认，
看到执行过程和结果，
并在需要时进入审计入口建立信任。
```

如果用户不用理解 Agent、Tool、MessageBus、EventStream、Provider，也能走完这条路径，MVP 就是成功的。

## 2. 总体工作流

推荐实施顺序：

```text
MVP PRD
  -> UX Flow Spec
  -> Figma / UX 原型
  -> 设计评审与微调
  -> 前端组件代码
  -> Mock 数据联调
  -> API 合约
  -> 后端通信
  -> 用户测试
  -> 迭代修正
```

不要从 PRD 直接跳到代码，也不要从 PRD 直接要求 Figma 生成完整 UI。

PRD 解决“做什么”。
UX Flow Spec 解决“用户怎么走”。
Figma 解决“用户看到什么”。
前端 Mock 解决“体验是否成立”。
API 合约和后端通信解决“真实数据如何进入体验”。

## 3. 阶段一：MVP PRD

### 3.1 目标

定义第一版产品交付边界。

### 3.2 产出

建议文档：

```text
docs/product/plato-mvp-prd.md
```

内容应包括：

- 产品一句话定义。
- 目标用户。
- MVP 核心用户路径。
- 第一版包含哪些对象。
- 第一版不包含哪些能力。
- 主要页面范围。
- 成功标准。
- 风险与取舍。

### 3.3 MVP 应包含

- Workflow 入口。
- Session 创建与状态。
- 自然语言输入。
- Draft TaskTree 展示。
- TaskNode 基本状态。
- TaskNode 选中后的详情。
- 用户确认动作。
- Session Message Stream。
- Task-scoped message projection。
- Result / File Change Summary 的初版展示。
- Audit Page 入口。

### 3.4 MVP 暂不包含

- 完整多 Agent 编排画布。
- 完整审计页面。
- 完整配置中心。
- 完整 Agent Marketplace。
- 复杂 workflow engine。
- 全量日志查询和回放。
- 复杂权限系统。
- 高级自动化策略配置。

### 3.5 退出标准

- 产品边界清楚。
- 主路径清楚。
- 非目标能力清楚。
- UX Flow 可以基于 PRD 继续展开。

## 4. 阶段二：UX Flow Spec

### 4.1 目标

把 PRD 转换成可用于设计生成和评审的交互规格。

### 4.2 产出

建议文档：

```text
docs/product/plato-main-page-ux-flow.md
```

内容应包括：

- Main Page 的用户目标。
- 关键用户路径。
- 主要对象的状态变化。
- 用户输入在不同上下文中的语义。
- TaskNode 选中 / 未选中时的交互差异。
- 确认动作如何出现、如何完成。
- Result 和 File Change Summary 如何进入用户视野。
- Audit 入口何时出现。

### 4.3 必须覆盖的核心流程

```text
空状态
  -> 用户输入自然语言
  -> 系统生成 Draft TaskTree
  -> 用户选中 TaskNode
  -> 用户补充或修改 TaskNode
  -> 用户发布 TaskTree
  -> TaskNode 进入执行状态
  -> 系统请求确认
  -> 用户确认
  -> 任务完成
  -> 用户查看 Result 和 File Change Summary
```

### 4.4 退出标准

- Figma 插件可以根据文档生成第一版 UX 画面。
- 页面不需要依赖工程实现细节才能理解。
- 用户主路径没有明显断点。

## 5. 阶段三：Figma / UX 原型

### 5.1 目标

生成第一版可评审的视觉与交互原型。

### 5.2 推荐画面

第一版只做关键状态，不追求全量页面。

建议至少生成：

1. Main Page 空状态。
2. 用户输入目标后的理解中状态。
3. Draft TaskTree 生成后。
4. 选中 TaskNode 的详情态。
5. TaskNode 等待用户确认。
6. TaskNode 执行中。
7. TaskNode 完成，展示 Result。
8. File Change Summary 展示。
9. Audit 入口可见但不展开。

### 5.3 评审重点

优先评审：

- 用户是否知道自己在哪个 Workflow / Session。
- 用户是否一眼能看到 TaskTree。
- 用户是否知道哪个 TaskNode 需要操作。
- 用户是否理解输入框当前作用域。
- 确认动作是否有上下文。
- Result 和文件变更是否容易找到。
- Audit 是否作为信任入口存在，而不是干扰主流程。

暂不优先评审：

- 图标是否最终定稿。
- 颜色是否完全精确。
- 微动效是否完整。
- 所有边缘状态是否覆盖。

## 6. 阶段四：前端组件代码

### 6.1 目标

把 Figma 初稿转成可运行的前端骨架。

### 6.2 实施原则

先做 Mock 数据版本，不急着接后端。

原因：

- 可以快速验证产品体验。
- 避免 API 未稳定导致 UI 返工。
- 可以让用户测试提前发生。
- 可以倒推后端 API 的真实需求。

### 6.3 推荐组件边界

组件应围绕产品对象拆分：

- `WorkflowSwitcher`
- `SessionHeader`
- `TaskTreeView`
- `TaskNodeItem`
- `TaskNodeDetail`
- `SessionMessageStream`
- `TaskScopedMessageView`
- `ConfirmationCard`
- `ResultCard`
- `FileChangeSummary`
- `AuditEntryPoint`

组件命名可以之后根据前端框架调整，但边界应尽量保持对象导向，而不是布局导向。

### 6.4 退出标准

- 使用 Mock 数据可以走通主路径。
- 页面状态可以手动切换或通过 mock scenario 切换。
- TaskTree、TaskNode、Message、Result 之间的关系清楚。
- 用户测试可以开始。

## 7. 阶段五：API 合约

### 7.1 目标

在 UI 体验基本成立后，定义前后端通信合约。

### 7.2 产出

建议文档：

```text
docs/product/plato-ui-api-contract.md
```

或者在已有 UI API 文档中新增 Plato MVP 章节。

### 7.3 API 对象

第一版 API 合约应围绕这些对象：

- Workflow
- Session
- RawTask
- DraftTaskTree
- TaskNode
- TaskMessage
- Confirmation
- Result
- FileChangeSummary
- AuditLink

### 7.4 原则

- API 返回 UI 需要的 ViewModel，不强迫 UI 拼后端内部对象。
- 后端保留 Domain Model，前端使用 Projection / ViewModel。
- Task-scoped message 可以从 Session message stream 通过 `task_id` 聚合。
- Audit 数据只暴露入口和摘要，完整审计后续再做。

## 8. 阶段六：后端通信

### 8.1 目标

把 Mock UI 接到真实后端能力。

### 8.2 推荐顺序

1. Session 创建 / 查询。
2. Workflow 列表 / 选择。
3. RawTask 创建。
4. Draft TaskTree 生成 / 查询。
5. TaskNode 更新。
6. Publish TaskTree。
7. Message stream 查询。
8. Confirmation 提交。
9. Result / FileChangeSummary 查询。

先接只读和低风险写入，再接发布和执行。

### 8.3 退出标准

- UI 不再依赖 Mock 数据完成主路径。
- 后端能保存关键用户操作。
- 用户确认动作可以回写。
- TaskTree 发布可以进入真实 TaskBus。
- 结果和文件变更至少有初版真实数据或可替代数据。

## 9. 阶段七：用户测试

### 9.1 目标

验证普通用户是否能凭直觉使用第一版。

### 9.2 测试任务

第一轮只测三类场景：

1. 创建一个计划：用户输入目标，查看系统生成的 TaskTree。
2. 调整一个任务：用户选中 TaskNode，补充说明或修改任务。
3. 完成一次确认：用户看到确认请求，理解影响范围并选择操作。

可选第四类：

4. 查看结果：用户找到 Result 和 File Change Summary。

### 9.3 观察指标

- 用户是否知道下一步该点哪里。
- 用户是否理解输入框作用范围。
- 用户是否能说出 TaskTree 是什么。
- 用户是否能找到需要确认的任务。
- 用户是否误以为系统已经开始执行。
- 用户是否能找到结果。
- 用户是否能理解 Audit 入口的意义。

## 10. 推荐任务拆分

建议后续按以下顺序创建具体任务：

| Step | 任务 | 产出 |
|---|---|---|
| P1 | 写 Plato MVP PRD | `plato-mvp-prd.md` |
| P2 | 写 Main Page UX Flow Spec | `plato-main-page-ux-flow.md` |
| P3 | 用 Figma 插件生成第一版 UX 文件 | Figma 初稿 |
| P4 | 评审并修订 UX 文件 | Figma v0.2 / review notes |
| P5 | 生成前端 Mock UI | 可运行页面 |
| P6 | 定义 Plato UI API Contract | API 合约文档 |
| P7 | 接入真实后端通信 | 可运行 MVP |
| P8 | 做第一轮用户测试 | 用户测试记录 |

## 11. 当前决策

当前采用以下实施策略：

```text
先产品定义
再交互规格
再 Figma 原型
再 Mock UI
再 API 合约
再真实后端
最后用户测试和迭代
```

这是为了减少返工。

第一版可以粗糙，但对象关系不能混乱。Plato 的核心不是漂亮截图，而是用户能理解并控制系统如何把意图变成 Task，再把 Task 变成结果。
