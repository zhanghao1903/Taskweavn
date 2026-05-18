# UI 页面项目实施模板

> Status: template
> Last Updated: 2026-05-17
> Scope: 指导一个新的 UI 页面如何从产品定义走到设计、代码、联调和用户测试。
> Reference: [Plato MVP 实施计划](../../product/plato-mvp-implementation-plan.md)

---

## 1. 使用方式

每当需要创建或重做一个重要页面时，先复制本文档结构，生成页面自己的项目实施计划：

```text
docs/plans/ui/<page-name>-project-implementation-plan.md
```

页面计划不是 PRD，也不是 UX 规格。它负责定义完整工作流、阶段边界、交付件、验收标准和推荐任务拆分。

推荐顺序：

```text
产品 PRD
  -> UX 交互规格
  -> Figma 设计稿 / 原型
  -> 设计评审与微调
  -> UI 组件代码
  -> Mock 数据联调
  -> 后端 API 合约
  -> 真后端通信
  -> 用户测试
  -> 迭代修正
```

---

## 2. 页面计划头部模板

```markdown
# Plato <Page Name> 项目实施计划

> Status: planned
> Last Updated: YYYY-MM-DD
> Scope: 推进 <Page Name>，从产品 PRD 到用户测试的完整交付链路。
> Reference: [Plato MVP 实施计划](../../product/plato-mvp-implementation-plan.md)
```

---

## 3. 页面计划必须回答的问题

每个页面计划至少回答：

1. 这个页面的产品定位是什么？
2. 用户为什么会进入这个页面？
3. 这个页面帮用户完成什么任务？
4. 它和其他页面的边界是什么？
5. 第一版包含什么？
6. 第一版明确不包含什么？
7. 当前已有产品、UX、架构、代码基础是什么？
8. 最大缺口是什么？
9. 每个阶段的交付件是什么？
10. 每个阶段的退出标准是什么？

---

## 4. 推荐文档产物

| 阶段 | 推荐产物 | 建议路径 |
|---|---|---|
| 页面计划 | 项目实施计划 | `docs/plans/ui/<page-name>-project-implementation-plan.md` |
| 产品 PRD | 页面 PRD | `docs/product/plato-<page-name>-prd.md` |
| UX 规格 | 页面 UX flow/spec | `docs/product/plato-<page-name>-ux-flow.md` |
| Figma | 设计稿 / 原型 | Figma file |
| 设计评审 | 评审记录 | `docs/plans/ui/<page-name>-design-review-notes.md` |
| UI 组件 | 前端代码 | `frontend/` 或对应页面目录 |
| Mock 联调 | mock scenarios / fixtures | `frontend/src/api/mock/<page-name>/` |
| API 合约 | transport-ready API contract | `docs/plans/ui/<page-name>-api-contract.md` |
| 用户测试 | user case / walkthrough | `docs/user_cases/UC-XXX-<page-name>-flow.md` |

---

## 5. 标准阶段

### Phase 0: 项目重基线

目标：确认当前文档、代码、视觉资产和产品边界的真实状态。

交付件：

- 页面项目实施计划。
- 当前状态清单。
- 本轮包含 / 不包含清单。
- 相关事实源或依赖映射。

退出标准：

- 团队确认本轮只推进该页面。
- 页面和相邻页面的边界清楚。
- 后续每个阶段有明确产物。

### Phase 1: 产品 PRD

目标：定义页面第一版要解决的用户问题和产品边界。

交付件：

- `docs/product/plato-<page-name>-prd.md`

必须覆盖：

- 产品一句话定义。
- 目标用户。
- 使用时机。
- 主路径和次路径。
- 页面信息架构边界。
- MVP 包含和不包含。
- 用户可执行动作。
- 成功指标。
- 风险与取舍。

退出标准：

- 用户问题清楚。
- 页面边界清楚。
- PRD 可以直接进入 UX 规格阶段。

### Phase 2: UX 交互规格

目标：把 PRD 转成可用于 Figma 生成和设计评审的交互规格。

交付件：

- `docs/product/plato-<page-name>-ux-flow.md`

必须覆盖：

- 入口和退出路径。
- 关键用户路径。
- 页面主要对象和状态。
- 空状态、加载态、成功态、失败态、部分数据态。
- 用户动作、系统反馈、禁止动作。
- 和相邻页面的跳转与上下文保持。
- 必要的错误恢复路径。

退出标准：

- Figma 设计可以直接按规格展开。
- 每个关键状态都有用户目标、系统反馈、可用动作。
- 规格不依赖用户理解后端内部名词。

### Phase 3: Figma 设计稿 / 原型

目标：生成可评审的视觉与交互原型。

交付件：

- Figma v0.1。
- 关键状态 frame。
- 简单点击原型。

最低要求：

- 覆盖主路径关键状态。
- 覆盖至少一个失败或空状态。
- 覆盖相邻页面入口 / 返回。
- 符合 Plato 视觉方向和页面信息密度。

退出标准：

- 用户一眼能理解页面主要对象。
- 页面主路径可点击演示。
- 信息层级和行动入口清楚。

### Phase 4: 设计评审与微调

目标：在写代码前解决体验断点、信息层级和产品边界问题。

交付件：

- `docs/plans/ui/<page-name>-design-review-notes.md`
- Figma v0.2。

评审重点：

- 用户是否知道自己在哪里。
- 用户是否知道下一步可以做什么。
- 页面是否展示了正确层级的信息。
- 相邻页面边界是否清楚。
- 关键状态是否足够完整。
- 是否出现内部概念泄漏。

退出标准：

- P0/P1 交互问题有处理结论。
- Figma 已更新。
- UI 组件实现可以开始。

### Phase 5: UI 组件代码

目标：把设计稿落成可运行的前端 shell。

交付件：

- 页面 route。
- 页面 shell。
- 核心组件。
- typed API hooks。
- 基础样式和响应式行为。

实现原则：

- 组件依赖 typed API / hooks，不直接依赖 fixture。
- 页面 local state 只保存 UI 状态，不伪造后端事实。
- 组件围绕产品对象拆分，不围绕临时布局拆分。
- 与设计稿保持信息层级一致。

退出标准：

- 页面可本地启动。
- 核心布局在桌面和窄屏不重叠。
- 主路径组件可渲染。
- 页面可以切换到 mock data。

### Phase 6: Mock 数据联调

目标：用 mock scenarios 验证体验成立，再倒推 API 合约。

交付件：

- typed mock API。
- mock fixtures。
- mock scenario switcher 或测试入口。

最低 mock scenarios：

- 空状态。
- 正常成功路径。
- 处理中状态。
- 需要用户处理状态。
- 失败 / 可恢复状态。
- 部分数据或延迟数据状态。

退出标准：

- 不接真实后端也能完成页面 walkthrough。
- mock scenario 覆盖核心状态。
- 组件状态来自 API client，不来自页面内硬编码。

### Phase 7: 后端 API 合约

目标：把 mock API 收敛为真实后端可实现、前端可稳定依赖的合约。

交付件：

- `docs/plans/ui/<page-name>-api-contract.md`
- TypeScript contract 或 schema。
- 后端 ViewModel 对应关系。

必须覆盖：

- Query。
- Command。
- Event / subscription。
- ViewModel。
- 错误形态。
- 刷新和 invalidation 策略。

退出标准：

- Mock API 和真实 API 使用同一套 contract。
- 后端返回 ViewModel，不返回裸 domain model 或数据库 row。
- 命令 accepted 后的刷新策略清楚。
- 事件只作为 invalidation / patch hint，不作为唯一事实源。

### Phase 8: 真后端通信

目标：把前端从 mock API 切到真实后端。

交付件：

- 真实 API client。
- 后端 adapter。
- 联调记录。
- mock / real mode 切换策略。

建议顺序：

1. 只读查询。
2. 低风险命令。
3. 高风险或状态迁移命令。
4. 事件订阅。
5. 错误恢复。

退出标准：

- UI 可以用真实后端完成主路径。
- 页面刷新后能恢复状态。
- 用户动作有持久化事实。
- mock mode 仍可用于设计和测试。

### Phase 9: 用户测试

目标：验证目标用户是否能凭直觉使用页面。

交付件：

- `docs/user_cases/UC-XXX-<page-name>-flow.md`
- 测试记录、问题清单、下一轮修订建议。

测试应覆盖：

- 用户进入页面。
- 用户完成页面主任务。
- 用户处理一个非理想状态。
- 用户离开页面或返回相邻页面。

退出标准：

- 至少完成一轮真实或半真实 walkthrough。
- 记录 P0/P1 体验问题。
- 形成下一轮修订清单。

---

## 6. 标准里程碑

| Milestone | 阶段范围 | 主要产物 | 可继续条件 |
|---|---|---|---|
| M0 | Phase 0 | 实施计划 | 范围确认 |
| M1 | Phase 1-2 | PRD + UX Flow | 可以做 Figma |
| M2 | Phase 3-4 | Figma v0.2 + review notes | 可以写 UI |
| M3 | Phase 5-6 | Mock UI 可运行 | 可以收敛 API |
| M4 | Phase 7-8 | API 合约 + 真实后端通信 | 可以用户测试 |
| M5 | Phase 9 | 用户测试记录 + 修订清单 | 可以进入迭代 |

---

## 7. 推荐任务编号

页面任务建议使用页面缩写作为前缀：

```text
<PX>-001 写 <Page Name> PRD
<PX>-002 写 <Page Name> UX Flow
<PX>-003 生成 Figma v0.1
<PX>-004 设计评审与 v0.2 微调
<PX>-005 搭建页面 shell
<PX>-006 实现核心组件
<PX>-007 建立 typed mock API
<PX>-008 Mock 联调主路径
<PX>-009 收敛 API 合约
<PX>-010 实现后端 adapter
<PX>-011 接入真实后端通信
<PX>-012 第一轮用户测试
```

---

## 8. 阶段门 Checklist

进入 Figma 前：

- PRD 已写。
- UX Flow 已写。
- 页面范围和非目标明确。
- 相邻页面边界明确。

进入 UI 代码前：

- Figma v0.2 已通过设计评审。
- P0/P1 交互问题有结论。
- 核心组件边界明确。
- mock scenarios 已列出。

进入 API 合约前：

- Mock UI 主路径已走通。
- 前端知道真实需要哪些 ViewModel。
- 命令和查询边界清楚。
- 错误和 partial data 状态已被 UI 覆盖。

进入真后端联调前：

- API contract 已收敛。
- mock API 和真实 API 使用同一 contract。
- 后端 adapter 责任清楚。
- 刷新和订阅策略清楚。

进入用户测试前：

- 页面可用真实或半真实数据走通主路径。
- 关键失败态和空状态可见。
- 测试任务和观察指标已写。

---

## 9. 常见风险

| 风险 | 表现 | 处理 |
|---|---|---|
| 从 PRD 直接写代码 | 页面复制工程假设，后续返工 | 必须先经过 UX 和 Figma |
| 从后端模型直接生成页面 | 用户看到内部对象，不知道怎么使用 | API 返回 ViewModel，PRD 以用户目标为中心 |
| 过早定死 API | UI 体验未验证，合约很快返工 | Mock UI 走通后再收敛 API |
| Mock 数据太薄 | 只覆盖 happy path，真实联调暴露大量状态缺口 | Phase 6 必须覆盖失败、部分数据、等待用户 |
| 设计评审只看视觉 | 交互断点没有处理 | 评审必须按用户路径和状态机走查 |
| 页面边界不清 | 一个页面承担太多职责 | Phase 0 和 PRD 明确相邻页面职责 |
| 内部术语泄漏 | 用户被 domain/event/provider/schema 术语困住 | UX 文案优先使用用户心智模型 |

---

## 10. 页面计划骨架

复制下面骨架创建新页面计划：

```markdown
# Plato <Page Name> 项目实施计划

> Status: planned
> Last Updated: YYYY-MM-DD
> Scope: 推进 <Page Name>，从产品 PRD 到用户测试的完整交付链路。
> Reference: [Plato MVP 实施计划](../../product/plato-mvp-implementation-plan.md)

## 1. 目标

## 2. 范围

### 2.1 本轮包含

### 2.2 本轮不包含

## 3. 当前基线

### 3.1 已有产品与 UX 基础

### 3.2 已有后端 / 前端基础

### 3.3 关键缺口

## 4. 实施原则

## 5. 阶段计划

### Phase 0: 项目重基线

### Phase 1: 产品 PRD

### Phase 2: UX 交互规格

### Phase 3: Figma 设计稿 / 原型

### Phase 4: 设计评审与微调

### Phase 5: UI 组件代码

### Phase 6: Mock 数据联调

### Phase 7: 后端 API 合约

### Phase 8: 真后端通信

### Phase 9: 用户测试

## 6. 里程碑

## 7. 推荐任务拆分

## 8. 风险与处理

## 9. 第一轮执行建议
```
