# Plato Frontend Technical Design

> Status: living frontend implementation design
>
> Design reference: Figma UI baseline 1.0 is now historical/reference input.
> New canonical Figma work must follow `docs/design/figma-governance.md`.
>
> Figma file: <https://www.figma.com/design/wHFPOBaxeImyhJer7BnMaq>
>
> Scope: Plato 前端 1.0 的技术选型、架构方案、实施切片和边界约束。本文不替代 PRD、UX Flow、Figma 文件或后端 API 合约。

## 1. 背景

当前 Figma 文件 `wHFPOBaxeImyhJer7BnMaq` 是 Plato UI 1.0 的历史起点和
参考文件。新的 canonical Figma 工作必须进入
`Plato Product Design System and Prototype`，并遵守
`docs/design/figma-governance.md`。

本文最初用于指导前端从 Figma baseline 1.0 重新起步。当前事实已经推进：

- `frontend/` 已经重建为 React + TypeScript + Vite 产品前端基线；
- Main Page 已实现 Figma 9 个 baseline 状态、TaskNode 选择、Detail Panel 切换、ContextInput 作用域、Confirmation、Result / File Change Summary；
- `shared/api` 已包含 UI contract TypeScript 类型、HTTP client、SSE client 和后端 fixture parity 测试；
- runtime 可通过 `VITE_PLATO_API_MODE=http`、`VITE_PLATO_API_BASE_URL`、`VITE_PLATO_SESSION_ID` 切换到真实 sidecar；
- 但 Main Page 页面状态仍主要由 fixture/state catalog 兼容层驱动，尚未完全迁移到真实 backend snapshot / command / event 收敛模型。

因此，后续工作不再是“销毁旧前端重新开始”，而是沿着当前产品前端基线继续收敛：

```text
Figma UI baseline 1.0 reference
  -> governed canonical Figma file
  -> frontend technical design
  -> frontend scaffold
  -> design tokens
  -> component system
  -> static states
  -> interactive prototype
  -> API contract
  -> backend integration
```

早期重启的目的不是追求更“高级”的技术栈，而是在成本最低的时候把长期前端架构定稳。现在要避免的反而是让 fixture prototype 继续冒充真实运行时。

## 2. 前端目标

Plato 前端 1.0 要服务普通用户，不是服务内部系统调试。

核心目标：

1. 让用户理解 `Project -> Workflow -> Session -> Session Workspace -> TaskTree` 的层级。
2. 让 TaskTree 成为主对象，而不是让聊天流主导页面。
3. 让 Detail Panel 成为动态 `Context Inspector`。
4. 让用户清楚当前输入作用域：Session-level 或 Task-scoped。
5. 让确认动作挂在具体 TaskNode 上。
6. 让 Result / File Change Summary / Audit entry 可发现。
7. 为后续真实消息流、任务总线、审计和配置能力留下结构空间。

## 3. 技术选型结论

当前第一版采用：

```text
React + TypeScript + Vite
  + CSS variables / CSS Modules
  + Radix primitives
  + Lucide icons
  + React local state for current Main Page prototype
  + TanStack Query for server state
  + REST snapshot + SSE event stream
  + Vitest / Testing Library
```

`zustand` 仍在依赖中，但当前 Main Page 尚未建立集中 client store。若后续把 snapshot、pending command、event invalidation 和 UI selection 分层，Zustand 或 reducer 都可以作为下一步局部状态容器。

### 3.1 为什么不是 Next.js

Next.js 很强，但 Plato 1.0 的主要复杂度不在 SSR、SEO 或内容路由，而在：

- 桌面工作台布局。
- 长生命周期 Session 状态。
- 实时消息流。
- TaskTree 交互。
- 本地或私有后端联调。

第一版使用 Vite 更直接，开发速度快，架构负担低。后续如果需要 Web SaaS、权限系统、服务端渲染或营销站，再引入 Next.js 也不晚。

### 3.2 为什么不是直接桌面端

Plato 未来可能需要桌面形态，但第一版不应先被桌面壳绑定。

当前路径：

```text
Web app first
  -> local backend integration
  -> optional desktop shell
```

桌面壳可以后续用 Tauri 或 Electron 承载同一套前端。现在先把 UI 对象、状态和 API 合约做对。

### 3.3 为什么不用现成 Admin UI

Plato 不是普通后台管理系统。它的核心对象是 TaskTree、TaskNode、Message Projection 和 Context Inspector。

现成 Admin UI 会很快，但容易把产品带向：

- 表格中心。
- 配置中心。
- 管理员视角。
- 内部对象泄漏。

第一版可以使用 Radix 这类无样式可访问性原语，但不要让视觉和交互心智被现成后台模板接管。

## 4. 设计到代码的原则

### 4.1 Figma 是视觉和布局源头，不是代码结构源头

Figma 里的 Frame 和 Layer 不应一比一变成 React 组件。

前端组件应围绕产品对象拆分：

```text
Project
Workflow
Session
TaskTree
TaskNode
Message
Result
FileChangeSummary
AuditEntry
ContextInput
DetailPanel
```

Figma 负责回答：

- 看起来是什么。
- 信息层级是什么。
- 关键状态如何表达。
- 视觉 tokens 如何约束。

代码负责回答：

- 状态如何流动。
- 数据如何归一。
- 组件如何复用。
- API 如何接入。

### 4.2 UI View Model 独立于后端 DTO

不要让后端 Task 数据结构直接驱动页面。

前端应有独立的 UI View Model：

```text
Backend DTO
  -> normalizer / adapter
  -> UI View Model
  -> components
```

原因：

- 后端 Task 偏执行和存储。
- 前端 Task Card 需要选中态、临时编辑态、确认态、可见状态、聚合摘要。
- 用户交互信息不一定都属于 Task 主数据。
- 后端可能支持强类型 TaskTree，而 UI 还要支持 rawTask authoring。

## 5. 推荐目录结构

当前结构大体采用下面方向：

```text
frontend/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  src/
    app/
      App.tsx
      routes.tsx
      providers.tsx
    shared/
      api/
      components/
      icons/
      styles/
      utils/
    entities/
      project/
      workflow/
      session/
      task/
      message/
      result/
      file-change/
      audit/
    features/
      create-session/
      author-task-tree/
      publish-task-tree/
      confirm-action/
      edit-task-node/
      inspect-result/
    pages/
      main-page/
    stories/
    tests/
```

当前代码还没有建立 `features/` 与 stories 目录；`pages/main-page` 暂时承载了较多 command wiring、event handling 和 fixture compatibility 逻辑。后续真实后端联调时，应逐步把这些动作拆出页面组件。

拆分原则：

- `entities/` 放稳定产品对象。
- `features/` 放用户动作。
- `pages/` 放页面组合。
- `shared/` 放无业务语义的基础能力。
- 不要按 Figma 画面状态建立一堆页面组件。

## 6. Main Page 组件边界

第一版 Main Page 可以拆为：

| 组件 | 职责 |
|---|---|
| `MainPage` | 页面组合、数据装载、当前选择态协调。 |
| `TopBar` | Product / Project / Workflow / Session / Status。 |
| `WorkflowSessionSidebar` | Workflow 列表和当前 Workflow 下的 Sessions。 |
| `TaskTreeWorkspace` | TaskTree 主工作区。 |
| `TaskTreeView` | TaskTree 展示和层级渲染。 |
| `TaskNodeCard` | TaskNode 卡片、状态、选中态。 |
| `SessionMessageStream` | 会话级消息流。 |
| `TaskMessageProjection` | 选中 TaskNode 后的消息投影。 |
| `DetailPanel` | 动态 Context Inspector 容器。 |
| `WorkflowInspector` | 会话开始前的 Workflow 信息。 |
| `SessionInspector` | Session 目标、状态、执行边界。 |
| `TaskNodeInspector` | 选中 TaskNode 的详情和补充入口。 |
| `ConfirmationInspector` | 需要确认时的操作区。 |
| `ResultInspector` | 完成后的结果展示。 |
| `FileChangeInspector` | 文件变更摘要和聚合。 |
| `ContextInput` | 根据当前作用域展示输入语义。 |

Detail Panel 必须通过 `mode` 或 derived context 切换内容：

```text
workflow
session
task_node
confirmation
result
file_changes
audit_summary
```

## 7. 状态管理方案

Plato 前端状态分三类。

### 7.1 Server State

来自后端，可缓存、可失效、可重新拉取：

- Project 列表。
- Workflow 列表。
- Session snapshot。
- TaskTree snapshot。
- Message history。
- Result。
- File Change Summary。
- Audit summary。

当前代码已经使用 TanStack Query 装载 `MainPageSnapshot`。需要修正的一点是：query key 仍包含 fixture `stateId`，HTTP adapter 只是忽略这个 stateId 并拉取固定 session snapshot。真实运行态应转向 `["main-page-snapshot", sessionId]` 或等价 key。

### 7.2 Realtime State

来自消息流或事件流：

- Session Message append。
- TaskNode status update。
- Actionable confirmation request。
- Result ready。
- File change update。

当前第一版使用：

```text
REST snapshot
  + SSE event stream
```

SSE 足够覆盖单向系统事件。若后续需要更复杂的双向低延迟通信，再升级 WebSocket。

当前前端低层 client 已监听所有 canonical `UiEventType` 命名事件。但 Main Page 页面只消费 `message.appended` 和 `session.resync_required` 两类事件；其他事件还没有驱动 UI 刷新。后续应把事件当作 invalidation / refetch hint，而不是假设 event payload 携带完整 ViewModel。

### 7.3 Local UI State

只属于前端：

- 当前选中的 Workflow。
- 当前选中的 Session。
- 当前选中的 TaskNode。
- Detail Panel mode。
- 输入框 draft。
- 临时展开/折叠状态。
- 当前 review stage 或 debug scenario。

当前实现使用 React local state。第一版可以继续这样做，但要把状态分层保持清楚：selection / detail mode / input draft 可以留在本地；snapshot、messages、confirmations、task tree 应来自 Query + event invalidation。

## 8. API 方向

前端不要直接依赖内部 EventStream / MessageBus / Tool / Agent 对象。

当前 API 已经收敛到 `/api/v1/sessions/{sessionId}/...` 为主的 Main Page sidecar contract：

```text
GET    /api/v1/sessions/{sessionId}/snapshot
POST   /api/v1/sessions/{sessionId}/input
POST   /api/v1/sessions/{sessionId}/task-tree/generate
PATCH  /api/v1/sessions/{sessionId}/tasks/{taskNodeId}
POST   /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input
POST   /api/v1/sessions/{sessionId}/task-tree/publish
POST   /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond
GET    /api/v1/sessions/{sessionId}/events
```

`/snapshot` 用于初始装载和恢复页面。

`/events` 用于实时追加：

- message added
- task status changed
- confirmation requested
- result updated
- file change updated
- session status changed

具体字段以 `plato-ui-api-contract.md` 和后端 `taskweavn.server.ui_contract` 为准。

## 9. Figma 1.0 对应实现策略

Figma 9 个状态不应直接做成 9 个页面。

推荐做法：

1. 每个 Figma 状态先建立一个 Story。
2. Story 使用同一套组件，不复制组件。
3. Story 数据来自 `fixtures/`。
4. Main Page 运行时根据真实 state 组合出对应 UI。

这样可以同时满足：

- 对照 Figma 做视觉 QA。
- 保证组件复用。
- 避免 9 套状态页面分叉。

建议 Story 命名：

```text
MainPage.Empty
MainPage.Understanding
MainPage.DraftReady
MainPage.TaskSelected
MainPage.TaskEditing
MainPage.Running
MainPage.WaitingConfirmation
MainPage.CompletedResult
MainPage.FileChanges
```

## 10. 测试策略

### 10.1 单元测试

覆盖：

- UI View Model adapter。
- TaskNode 文件变更聚合。
- Detail Panel mode 推导。
- Message task projection。
- Confirmation option mapping。

### 10.2 组件测试

覆盖：

- TaskNodeCard 状态显示。
- ContextInput 作用域文案。
- ConfirmationInspector 操作选项。
- ResultInspector / FileChangeInspector 内容。

### 10.3 E2E / Visual

使用 Playwright 覆盖主路径：

```text
打开 Main Page
  -> 输入目标
  -> 看到 Draft TaskTree
  -> 选中 TaskNode
  -> 补充任务
  -> 发布
  -> 等待确认
  -> 确认执行
  -> 查看 Result
  -> 查看 File Change Summary
```

同时对 Figma 9 个状态做截图回归。

## 11. 实施切片与当前事实

### Slice F1：前端工程重建

产出：

- `frontend/` 全新工程。
- React + TypeScript + Vite。
- lint / typecheck / test 基线。
- design token 文件。
- 空 Main Page shell。

退出标准：

- `npm run build` 通过。
- `npm run test` 通过。
- 页面能启动。

当前状态：已完成。

### Slice F2：Design Tokens

产出：

- 颜色、字体、间距、圆角、阴影 token。
- Figma 1.0 色彩映射。
- 基础 Button / Badge / Panel / Text primitives。

退出标准：

- 基础组件可在 Story 中查看。
- token 不散落在业务组件里。

当前状态：代码中已完成 primitives 和 token baseline；Storybook/Ladle 尚未建立。

### Slice F3：Main Page Static States

产出：

- Main Page shell。
- Sidebar / TopBar / TaskTree / Message / Detail / Input。
- 9 个 Figma 状态 Story。

退出标准：

- 9 个状态与 Figma 1.0 在结构上对应。
- 无明显文字溢出和重叠。

当前状态：已完成为 fixture/state catalog 驱动的页面状态，不是独立 stories。

### Slice F4：Interactive Prototype

产出：

- 选中 TaskNode。
- Detail Panel 动态切换。
- ContextInput 作用域变化。
- Confirmation 操作。
- Result / File Change 切换。

退出标准：

- 用户可以走通 PRD 主路径。

当前状态：局部完成。页面支持选择 TaskNode、confirmation、本地输入回显、result/file changes 切换；但命令结果仍以 local synthetic message 为主，并未完全由后端事实驱动。

### Slice F5：UI API Contract

产出：

- `docs/product/plato-ui-api-contract.md`。
- Snapshot DTO。
- Event DTO。
- Command DTO。
- UI View Model adapter 规则。

退出标准：

- 前后端知道各自边界。
- UI 不依赖后端内部对象。

当前状态：已完成 contract baseline，并有后端生成 JSON fixture 被前端测试消费。

### Slice F6：Backend Integration

产出：

- Session snapshot 拉取。
- SSE / event stream 接入。
- User input / task input / confirmation response。

退出标准：

- 最小真实 Session 可在 UI 中运行。

当前状态：部分完成。HTTP client、HTTP adapter、runtime env、SSE named event compatibility、local sidecar backend assembly 已存在；Main Page runtime 仍主要是 fixture-compatible 页面模型，尚未完整使用 `CommandResponse.refresh`、`affectedScopes` 和 canonical `UiEvent` 来驱动 refetch / invalidation。

## 12. 风险与取舍

| 风险 | 说明 | 对策 |
|---|---|---|
| 过早接后端 | API 未稳定会拖慢 UI 验证。 | 先 Story + fixtures，再 API contract。 |
| 组件按 Figma Layer 拆 | 会导致代码结构脆弱。 | 按产品对象拆组件。 |
| 后端 DTO 直出 UI | Task Card 和交互态会被后端结构绑死。 | 建 UI View Model adapter。 |
| 状态管理过重 | 过早引入复杂状态机会拖慢开发。 | 先 Zustand / reducer，必要时再局部状态机。 |
| 视觉走样 | Figma 和代码容易分叉。 | 9 个状态 Story + screenshot QA。 |
| 消息流淹没 TaskTree | 产品退化为 Chat UI。 | 布局和组件优先保护 TaskTree 主视觉。 |

## 13. 当前决策

1. Figma `wHFPOBaxeImyhJer7BnMaq` 是 UI 1.0 历史起点；新的
   canonical Figma 工作进入 `Plato Product Design System and Prototype`。
2. 当前 `frontend/` 已经是产品前端基线，不再视为 throwaway demo。
3. fixture/state catalog 仍作为 dev/demo/visual regression 输入保留，但不能继续作为真实运行态的核心状态机。
4. API 合约已经制定，并有前后端 fixture parity 测试。
5. 真实后端联调的下一步是让 Main Page runtime 从 snapshot + command response + event invalidation 收敛，而不是继续扩大本地 optimistic patch。
6. `StatePicker` 应保留为开发/演示工具，真实 HTTP mode 默认不应把它暴露给普通用户。
