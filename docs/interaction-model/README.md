# UI Interaction Model

> Status: active fact registry
>
> Last Updated: 2026-05-21
>
> Scope: Plato / TaskWeavn UI 的页面交互事实。本文档族记录“用户动作 -> UI 变化 -> 后端调用”，不替代 PRD、视觉稿、后端 API contract 或实现计划。

## 1. 目标

`docs/interaction-model/` 是 UI 行为的事实登记册。

每一个正式 Page 都必须有自己的交互模型文档。页面文档按组件划分，列出该组件允许的所有交互：

```text
User action / trigger
  -> UI state change
  -> Backend API call / external call
  -> Event or refresh behavior
```

如果一个交互没有登记在这里，默认不应进入产品实现。页面变更、API 变更、组件交互变更，都需要同步维护这里的事实。

## 2. 和其他文档的关系

| 文档 | 责任 |
|---|---|
| [Product Docs](../product/) | 定义用户目标、页面意图、UX flow、PRD 和体验原则。 |
| [UI API Contract](../product/plato-ui-api-contract.md) | 定义前后端 Query / Command / Event 合约。 |
| [Architecture](../architecture/) | 定义系统对象、协议、生命周期和边界。 |
| [Plans](../plans/) | 定义某一阶段如何实现。 |
| Interaction Model | 定义页面上允许发生的交互事实，以及这些交互触发哪些调用。 |

Interaction Model 是更靠近实现的 UX 事实层：它不讨论“为什么要这么设计”，只记录“页面能怎么动”。

## 3. 当前页面清单

| Page | Document | Status | Notes |
|---|---|---|---|
| Main Page | [main-page.md](main-page.md) | active baseline | Plato 1.0 主控制面。 |

未来新增 Audit Page、Settings Page、Workflow Page 等页面时，必须先新增对应交互模型文档，再实现页面交互。

## 4. 外部调用清单

所有离开前端本地组件状态的调用，集中登记在：

- [external-calls.md](external-calls.md)

页面文档中可以简写 API 名称，但必须链接或引用 `external-calls.md` 中的条目。

这里的“外部调用”包括：

- HTTP Query；
- HTTP Command；
- SSE / EventSource；
- 浏览器导航；
- 打开本地文件、外部链接或未来桌面能力；
- 任何未来直接调用第三方服务的前端能力。

默认原则：Plato 前端不直接调用 LLM provider、数据库或文件系统。它通过 UI Gateway / sidecar API 与系统通信。

## 5. 页面文档格式

每个页面文档至少包含：

1. Page scope
2. Source of truth
3. Component inventory
4. Interaction tables by component
5. Background event behavior
6. Disabled / not allowed interactions
7. Maintenance checklist

推荐表格列：

| Column | Meaning |
|---|---|
| ID | 稳定交互编号，例如 `MP-INPUT-001`。 |
| Status | `current` / `target` / `planned` / `disabled`。 |
| User action / trigger | 用户动作或系统触发条件。 |
| Availability | 什么时候允许该交互。 |
| UI change | 前端必须发生的状态变化。 |
| Backend / external call | 触发的 API、SSE、导航或无调用。 |
| Event / refresh | 后续由哪些事件或 query 刷新事实。 |
| Notes | 约束、来源或风险。 |

## 6. 状态定义

| Status | Meaning |
|---|---|
| `current` | 当前代码已经应该支持，或正在作为基线事实维护。 |
| `target` | 当前计划阶段要实现，页面设计已经允许。 |
| `planned` | 已进入产品/架构方向，但不属于当前实现阶段。 |
| `disabled` | 页面可以展示入口，但交互不可执行，必须无后端写入。 |

状态只描述 UI 实现成熟度，不改变产品方向。一个 `planned` 交互实现后，需要改成 `current` 或 `target`。

## 7. 维护规则

1. 新增页面前，新增页面交互模型文档。
2. 新增按钮、菜单、卡片操作、快捷入口前，先登记交互。
3. 新增 API 调用前，先登记到 [external-calls.md](external-calls.md)。
4. 后端 API contract 改名或变更语义后，同步更新页面文档中的调用。
5. 页面实现不能长期依赖本地 synthetic state 覆盖后端事实；需要在文档中说明 refetch / event 收敛方式。
6. 已完成 TaskNode 的默认交互是只读；任何复写、重试、撤销都必须有明确交互条目和 API。
7. Prototype / debug 交互必须标注为 `disabled` 或 `dev-only`，不能混入用户正式路径。

