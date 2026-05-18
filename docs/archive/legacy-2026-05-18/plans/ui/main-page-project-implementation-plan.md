# Plato Main Page 项目实施计划

> Status: planned
> Last Updated: 2026-05-17
> Scope: 重新推进 Plato / TaskWeavn Main Page，从产品 PRD 到用户测试的完整交付链路。
> Reference: [Plato MVP 实施计划](../../product/plato-mvp-implementation-plan.md)

---

## 1. 目标

本计划用于把 Main Page 从已有产品方向推进为可评审、可运行、可联调、可测试的第一版产品体验。

目标不是一次性完成所有 Agent 应用能力，而是走通一条可信的 Main Page 主路径：

```text
用户选择或进入 Workflow
  -> 创建 Session
  -> 用自然语言表达目标
  -> 系统生成 Draft TaskTree
  -> 用户查看、选择、补充或修改 TaskNode
  -> 用户发布 TaskTree
  -> TaskNode 进入执行
  -> 用户完成必要确认
  -> 用户查看执行过程、结果和文件变更
  -> 用户看到 Audit 入口，但不在 Main Page 展开完整审计
```

Main Page 的产品定位是 Control Plane。它要让用户知道当前工作在哪里、系统理解了什么任务、哪些任务需要操作、什么已经完成、结果在哪里，以及下一步能做什么。

---

## 2. 范围

### 2.1 本轮包含

- Main Page 产品 PRD。
- Main Page UX 交互规格。
- Figma 设计稿 / 可点击原型。
- 设计评审与微调记录。
- 前端 UI 组件代码。
- Mock 数据和 mock scenario 联调。
- 后端 API 合约收敛。
- UI 到真实后端通信。
- 第一轮用户测试。

### 2.2 本轮不包含

- 完整 Audit Page。
- 完整多 Agent 编排画布。
- Agent Marketplace。
- 配置中心。
- 复杂 Workflow Engine。
- 全量日志查询、回放和调试控制台。
- 权限系统和团队协作。
- 复杂 diff viewer。

Audit 在本轮只作为 Main Page 的信任入口出现：用户能看到某个 Task 或 Session 存在可追溯记录，但不会在 Main Page 中展开完整审计证据。

---

## 3. 当前基线

### 3.1 已有产品与 UX 基础

- [Core Product Principles](../../product/core-product-principles.md)：定义 Task-first、Workflow-first、Main Page 是 Control Plane、Audit Page 是 Trust Plane。
- [Workflow, Session, And Task UX Model](../../product/workflow-session-task-ux-model.md)：定义 Workflow、Session、RawTask、TaskTree、TaskNode、Message、Result、File Change Summary、Audit Record 的用户心智模型。
- [Plato MVP 实施计划](../../product/plato-mvp-implementation-plan.md)：定义 PRD 到用户测试的推荐顺序。
- [Task-first UI 交互设计总述](../task-first-ui-interaction.md)：定义 TaskTree、TaskNode Detail、Task-scoped message、确认动作等交互原则。
- [UI Information Architecture](information-architecture.md)：定义 Header、Task Tree、Task Detail、Session Stream、Input Area 的区域关系。
- [Frontend Framework Technical Design](frontend-framework-design.md)：定义 Vite + React + TypeScript、typed mock API、组件切片和前端目录建议。
- [UI API 接口归档](ui-api-interfaces.md)：定义已有 ViewModel、查询、命令和实时事件语义。

### 3.2 已有后端基础

- `TaskProjectionService` 已能投影 `TaskTreeView`、`TaskCardView`、`TaskDetailView`。
- `TaskInteractionTimelineService` 已能提供 Task 相关时间线。
- `CollaboratorApiAdapter` 已覆盖 draft task tree generation、task message、publish 等 authoring 边界。
- `MessageStream`、`ConfirmationActionView`、`TaskFileChangeSummary`、`TaskSummaryView` 已有 UI-facing 模型基础。

### 3.3 关键缺口

- 缺少独立的 Main Page PRD。
- 缺少可直接驱动 Figma 的 Main Page UX 交互规格。
- 缺少最新版 Figma 设计稿和评审记录。
- 缺少实际前端应用目录和组件代码。
- 缺少 typed mock scenarios。
- UI API 仍偏语义归档，尚未收敛到 transport-ready 合约。
- 缺少真实 UI 与后端 API 通信层。
- 缺少围绕 Main Page 的用户测试记录。

---

## 4. 实施原则

1. 先产品边界，再设计画面，再写组件代码。
2. Main Page 只呈现行动和进度，不暴露底层系统细节。
3. Task 是第一交互对象，chat 只是输入方式之一。
4. Draft TaskTree 在执行前必须可见、可选中、可修改或可发布。
5. 确认动作必须绑定 TaskNode，不作为普通消息淹没在 stream 中。
6. Result 和 File Change Summary 必须在完成态 TaskNode 上清楚可见。
7. Mock UI 先走通体验，再倒推和收紧 API 合约。
8. API 返回 ViewModel，不把后端 domain model 直接暴露给前端。
9. 前端依赖 typed API client，不在组件里直接拼 mock fixture 或 fetch。
10. 用户测试优先验证用户是否理解 TaskTree、输入作用域、确认动作和结果位置。

---

## 5. 阶段计划

### Phase 0: 项目重基线

目标：确认当前文档、代码和视觉资产的真实状态，避免后续重复设计。

产出：

- 本实施计划。
- Main Page 现状清单。
- 本轮不做事项清单。

验收标准：

- 团队确认本轮只推进 Main Page。
- Audit Page 只保留入口边界。
- 后续每个阶段有明确文档或代码产物。

建议状态：当前阶段。

### Phase 1: 产品 PRD

目标：定义 Main Page 第一版到底要解决什么用户问题。

建议产出：

```text
docs/product/plato-main-page-prd.md
```

必须覆盖：

- 产品一句话定义。
- 目标用户。
- 主路径和次路径。
- Main Page 信息架构边界。
- MVP 包含和不包含。
- 用户可执行动作。
- 状态、结果、确认、文件变更、Audit 入口的展示原则。
- 成功指标。

验收标准：

- 普通用户主路径清楚。
- Main Page 和 Audit Page 边界清楚。
- PRD 可以直接进入 UX 规格阶段。

### Phase 2: UX 交互规格

目标：把 PRD 转成可用于 Figma 生成和设计评审的交互规格。

建议产出：

```text
docs/product/plato-main-page-ux-flow.md
```

必须覆盖：

- 空状态。
- Workflow / Session 进入状态。
- 用户输入自然语言目标。
- Understanding / Planning 状态。
- Draft TaskTree 生成后状态。
- TaskNode 选中、未选中、编辑、补充说明。
- Publish TaskTree。
- Running / Waiting / Done / Failed TaskNode。
- Confirmation 出现与处理。
- Result 和 File Change Summary 展示。
- Global input 和 task-scoped input 的切换规则。
- Audit 入口出现时机。

验收标准：

- UX 规格不依赖工程内部名词才能理解。
- 每个关键状态都有用户目标、系统反馈、可用动作、禁止动作。
- Figma 设计可以直接按规格展开。

### Phase 3: Figma 设计稿 / 原型

目标：产出可评审的 Main Page 第一版设计稿和关键状态原型。

建议产出：

- Figma Main Page v0.1。
- 关键状态 frame。
- 简单点击原型。

最低 frame：

1. 空 Session。
2. 用户输入目标后，系统理解中。
3. Draft TaskTree 已生成。
4. 选中 TaskNode 的详情态。
5. TaskNode 正在编辑或补充约束。
6. TaskTree ready to publish。
7. 执行中。
8. 等待确认。
9. 完成态，展示 Result。
10. File Change Summary 展示。
11. Failed TaskNode recovery。
12. Audit 入口可见但不展开。

验收标准：

- 用户一眼能看到 Session、TaskTree、选中 Task、待确认事项。
- 输入框作用域清楚。
- Confirmation 不被普通消息淹没。
- 完成态 Task 能找到结果和文件变更。
- 视觉符合 Plato 的冷静、清晰、可控、可信方向。

### Phase 4: 设计评审与微调

目标：在写代码前解决体验断点和信息层级问题。

建议产出：

```text
docs/plans/ui/main-page-design-review-notes.md
```

评审重点：

- 用户是否知道当前在哪个 Workflow / Session。
- 用户是否理解 TaskTree 是系统对目标的结构化理解。
- 用户是否知道当前输入会影响全局还是选中 Task。
- 用户是否能找到需要确认的任务。
- 用户是否理解任务何时只是 draft、何时开始执行。
- 用户是否能找到 Result 和 File Change Summary。
- Audit 入口是否建立信任，但不干扰主流程。

验收标准：

- 所有 P0/P1 交互问题有处理结论。
- Figma 更新到 v0.2。
- UI 组件实现可以开始。

### Phase 5: UI 组件代码

目标：把设计稿落成可运行的前端 shell。

建议产出：

```text
frontend/
```

建议技术栈沿用 [Frontend Framework Technical Design](frontend-framework-design.md)：

- Vite + React + TypeScript。
- TanStack Query。
- TanStack Router。
- Tailwind CSS + CSS variables。
- Radix Primitives。
- lucide-react。
- typed mock API。

核心组件：

- `AppShell`
- `SessionHeader`
- `WorkflowSwitcher`
- `TaskTreePanel`
- `TaskNodeItem`
- `TaskDetailPanel`
- `TaskMessageView`
- `SessionStreamPanel`
- `ConfirmationCard`
- `ResultCard`
- `FileChangeSummary`
- `AuditEntryPoint`
- `ComposerBar`

验收标准：

- 页面可本地启动。
- 核心布局在桌面和窄屏不重叠。
- 能选中 TaskNode 并同步更新详情和 task-scoped messages。
- 组件只依赖 typed API/hooks，不直接依赖 fixture。

### Phase 6: Mock 数据联调

目标：用 mock scenarios 走通第一版用户体验。

建议产出：

```text
frontend/src/api/mock/
frontend/src/test/fixtures/
```

最低 mock scenarios：

1. Empty Session。
2. Understanding / Planning。
3. Draft TaskTree generated。
4. Selected Task editing。
5. Ready to publish。
6. Running with progress messages。
7. Waiting for confirmation。
8. Confirmation resolved。
9. Completed with result。
10. Completed with file changes。
11. Failed with retry affordance。

验收标准：

- 不接真实后端也能完成完整演示路径。
- mock scenario 能驱动用户测试彩排。
- 组件状态来自 API client，不来自页面内硬编码。

### Phase 7: 后端 API 合约

目标：把 mock API 收敛为真实后端可实现的契约。

建议产出：

```text
docs/plans/ui/main-page-api-contract.md
```

或在 [UI API 接口归档](ui-api-interfaces.md) 中新增 Main Page transport-ready 章节。

必须收敛：

- Query：
  - `getSessionOverview`
  - `listTaskTrees`
  - `getTaskDetail`
  - `getTaskTimeline`
  - `listSessionMessages`
  - `listTaskMessages`
  - `listPendingConfirmations`
  - `getTaskFileChanges`
  - `getTaskSummary`
- Command：
  - `appendSessionMessage`
  - `generateTaskTree`
  - `updateTaskNode`
  - `appendTaskMessage`
  - `publishTaskTree`
  - `startTaskExecution`
  - `resolveConfirmation`
  - `cancelTask`
  - `retryTask`
- Event：
  - `session.status.changed`
  - `task.tree.changed`
  - `task.card.changed`
  - `task.detail.changed`
  - `message.created`
  - `confirmation.created`
  - `confirmation.resolved`
  - `file.change.recorded`
  - `summary.updated`

验收标准：

- Mock API 和真实 API 使用同一套 TypeScript contracts。
- 后端返回 ViewModel，不返回裸 domain 或 SQLite row。
- 命令 accepted 后的刷新策略清楚。
- 事件只作为 invalidation / patch hint，不作为唯一事实源。

### Phase 8: 真后端通信

目标：把前端从 mock API 切到真实后端。

建议顺序：

1. Session overview 查询。
2. TaskTree 查询。
3. TaskDetail 查询。
4. Session messages 查询。
5. Task messages 查询。
6. Pending confirmations 查询。
7. File changes / summary 查询。
8. Append session message。
9. Generate task tree。
10. Update task node。
11. Publish task tree。
12. Resolve confirmation。
13. Start execution。
14. Event subscription。

验收标准：

- UI 可以用真实后端完成主路径。
- 用户输入、TaskTree 生成、TaskNode 修改、发布、确认处理都有持久化事实。
- UI 可以通过查询刷新恢复状态。
- mock mode 仍可保留用于设计和测试。

### Phase 9: 用户测试

目标：验证 Main Page 的基本心智模型是否成立。

建议产出：

```text
docs/user_cases/UC-006-main-page-mvp-flow.md
docs/user_cases/terminal_outputs/UC-006-main-page-mvp-flow.txt
```

测试任务：

1. 创建一个新 Session 并输入目标。
2. 理解系统生成的 Draft TaskTree。
3. 选中一个 TaskNode 并补充要求。
4. 判断什么时候只是 draft，什么时候会开始执行。
5. 发布 TaskTree。
6. 处理一个确认动作。
7. 找到任务结果。
8. 找到文件变更摘要。
9. 找到 Audit 入口并说出它的意义。

观察指标：

- 用户是否知道下一步该做什么。
- 用户是否理解 TaskTree。
- 用户是否理解输入框作用域。
- 用户是否能定位待确认 Task。
- 用户是否误以为 draft 已经执行。
- 用户是否能找到结果和文件变更。
- 用户是否信任系统的过程可追溯。

验收标准：

- 至少完成一轮真实或半真实用户 walkthrough。
- 记录 P0/P1 体验问题。
- 形成下一轮修订清单。

---

## 6. 里程碑

| Milestone | 阶段范围 | 主要产物 | 可继续条件 |
|---|---|---|---|
| M0 | Phase 0 | 实施计划 | 范围确认 |
| M1 | Phase 1-2 | PRD + UX Flow | 可以做 Figma |
| M2 | Phase 3-4 | Figma v0.2 + review notes | 可以写 UI |
| M3 | Phase 5-6 | Mock UI 可运行 | 可以收敛 API |
| M4 | Phase 7-8 | API 合约 + 真实后端通信 | 可以用户测试 |
| M5 | Phase 9 | 用户测试记录 + 修订清单 | 可以进入迭代 |

---

## 7. 推荐任务拆分

| ID | 任务 | 产出 | 依赖 |
|---|---|---|---|
| MP-001 | 写 Main Page PRD | `docs/product/plato-main-page-prd.md` | 本计划 |
| MP-002 | 写 Main Page UX Flow | `docs/product/plato-main-page-ux-flow.md` | MP-001 |
| MP-003 | 生成 Figma v0.1 | Figma 文件 | MP-002 |
| MP-004 | 设计评审与 v0.2 微调 | review notes + Figma v0.2 | MP-003 |
| MP-005 | 搭建 frontend shell | `frontend/` | MP-004 |
| MP-006 | 实现核心组件 | Main Page mock UI | MP-005 |
| MP-007 | 建立 typed mock API | mock scenarios | MP-005 |
| MP-008 | Mock 联调主路径 | 可演示 mock flow | MP-006, MP-007 |
| MP-009 | 收敛 Main Page API 合约 | API contract doc | MP-008 |
| MP-010 | 实现后端 API adapter | server API boundary | MP-009 |
| MP-011 | 接入真实后端通信 | UI real mode | MP-010 |
| MP-012 | 第一轮用户测试 | UC-006 + findings | MP-011 |

---

## 8. 风险与处理

| 风险 | 表现 | 处理 |
|---|---|---|
| 过早写代码 | UI 复制旧假设，后续返工 | Phase 1-4 必须先通过 |
| Main Page 变成 chat UI | TaskTree 和 Task 状态不突出 | 每轮评审用 Task-first checklist |
| 过早展开审计 | 主流程被底层日志淹没 | 本轮 Audit 只做入口和摘要 |
| API 合约太早定死 | Mock 体验还没验证就锁死后端 | Mock UI 走通后再收敛 transport-ready 合约 |
| 后端 domain 泄漏到前端 | UI 被内部模型绑死 | API 只返回 ViewModel |
| 确认动作被淹没 | 用户错过关键决策 | Confirmation 独立区域和 Task badge 双重呈现 |
| 输入作用域模糊 | 用户不知道是在改全局还是改 Task | Composer 必须明确 global / task-scoped mode |
| 结果位置不清楚 | 用户完成后不知道看哪里 | Done TaskNode 必须展示 Result 和 File Change Summary |

---

## 9. 第一轮执行建议

下一步从 MP-001 开始，不直接进入 Figma 或代码。

建议第一轮工作顺序：

```text
MP-001 Main Page PRD
  -> MP-002 Main Page UX Flow
  -> MP-003 Figma v0.1
  -> MP-004 设计评审
```

只有当 PRD 和 UX Flow 明确以后，再进入 UI 组件代码和 mock 联调。这样可以避免把当前后端已有模型直接翻译成页面，而是让页面服务 Plato 的用户心智模型。
