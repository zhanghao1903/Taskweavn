# Plato UI API Contract

> Status: MVP contract baseline
>
> Last Updated: 2026-06-06
>
> Scope: Plato Main Page 1.0 的前后端通信合约。本文服务 F6 Backend Integration，不替代后端领域模型、数据库 schema 或完整 transport 实现。
>
> Related:
> [Plato Frontend Technical Design](plato-frontend-technical-design.md),
> [Main Page UX Flow](plato-main-page-ux-flow.md),
> [UI And Backend Communication](../architecture/ui-backend-communication.md),
> [Task Domain/UI Model Separation](../architecture/task-domain-ui-model-separation.md),
> [legacy UI API archive](../plans/ui/ui-api-interfaces.md)

## 1. 目标

F5/F6 的目标是把 Plato 前端原型需要的后端边界写清楚，并让第一条本地 sidecar 联调路径成立。

第一版前端已经具备：

- Main Page 工作台骨架；
- 9 个 Figma baseline 状态；
- TaskNode 选中；
- Detail Panel 动态切换；
- Context Input 作用域变化；
- Confirmation 操作；
- Result / File Change Summary 切换。

当前事实是：

- 前端已有 `shared/api/types.ts`、`platoApi.ts`、HTTP adapter 和 runtime env switch；
- 后端已有 `taskweavn.server.ui_contract`、gateway、HTTP transport、SSE frame shell 和 Main Page sidecar assembly；
- 前端 Main Page 页面仍保留 fixture/state catalog 兼容层，尚未完全按 `CommandResponse.refresh` 和 `UiEvent` 做真实运行态收敛。

为了避免 UI 直接依赖内部对象，必须继续保持稳定 API 合约：

```text
Backend domain / stores / bus
  -> UI Gateway
  -> Query / Command / Event contract
  -> Frontend adapter
  -> Plato UI ViewModel
```

本文定义的是语义稳定层。当前已经有第一版 framework-neutral HTTP/SSE sidecar，但 durable SSE replay、多 session UI 创建流程和完整 execution lifecycle 仍不属于本文完成标准。

## 2. 非目标

第一版不解决：

- 多用户权限；
- 跨 Session 并发编辑；
- 完整 DAG task topology；
- 完整 audit 页面；
- 完整 diff viewer；
- WebSocket 双向协作；
- 前端离线编辑；
- 所有字段的最终精确定义。

这些能力需要架构预留，但不应阻塞 F6。

## 3. 设计原则

### 3.1 Session 是主通信边界

Main Page 的用户对象层级是：

```text
Project
  -> Workflow
      -> Session
          -> TaskTree / TaskNode
```

但第一版 API 写入边界以 `session_id` 为主。

原因：

- Session 是一次具体工作；
- Session Workspace 默认隔离文件写入；
- TaskTree、Message、Confirmation、Result、FileChange 都能从 Session 聚合；
- Project/Workflow 更偏导航和默认策略，不应承载执行写入。

### 3.2 API 返回 UI ViewModel

前端不直接消费：

- `TaskDomain`
- `DraftTaskNode`
- `RawTask`
- SQLite row
- MessageStream 原始 payload
- TaskBus 内部事件

API 返回面向 UI 的 ViewModel：

- `MainPageSnapshot`
- `WorkflowSummary`
- `SessionSummary`
- `TaskTreeView`
- `TaskNodeCardView`
- `SessionMessageView`
- `ConfirmationActionView`
- `ResultCardView`
- `FileChangeSummaryView`
- `AuditLinkView`

后端领域对象可以继续演化，UI ViewModel 尽量稳定。

### 3.3 Query / Command / Event 三分

| 类型 | 方向 | 语义 |
|---|---|---|
| Query | UI -> Backend | 获取当前投影视图，不改变状态。 |
| Command | UI -> Backend | 提交用户意图，不承诺直接返回完整最新视图。 |
| Event | Backend -> UI | 通知事实变化，提示 UI patch 或 re-query。 |

不要让一个接口同时承担查询、写入、实时同步三种职责。

### 3.4 Command accepted 不是最终事实

命令返回 `accepted` 只代表后端接收。

推荐流程：

```text
UI submit command
  -> CommandResponse(status="accepted")
  -> UI enters pending state
  -> backend emits events
  -> UI patches local projection or re-query
```

这能避免把 optimistic state 当成真实事实。

### 3.5 Task Message View 是 Session Message Stream 的投影

系统只有一条 Session Message Stream。

Task Message View 不是第二套物理消息流，而是：

```text
Session messages
  -> filter by task_ref / task_node_id
  -> task scoped projection
```

这样一个会话包含很多 Task 时，消息存储仍然统一，Task 视角由查询和投影产生。

### 3.6 UI Local State 不进入后端事实源

以下状态只属于前端：

- 当前选中的 TaskNode；
- Detail Panel 当前 mode；
- 输入框 draft；
- task card 展开/折叠；
- hover / focus；
- fixture state picker；
- optimistic pending indicator。

后端只保存可回放的用户意图和系统事实。

### 3.7 Snapshot 只暴露一个 Active Domain

Main Page snapshot 必须把 Session 投影成一个用户可操作的 active domain。

```text
Authoring active:
  taskTree = null
  planning.state in capturing_input / assessing / awaiting_user / ready_to_plan
  planning.asks may contain pending authoring asks

Task active:
  taskTree != null
  plan or TaskNode becomes the input/detail target
  planning.asks must not expose stale authoring asks as actionable controls
```

如果底层事实同时存在 `RawTaskAsk(status=pending)` 和 `TaskTreeView`，Gateway
不能把这个脏状态原样交给 UI。推荐投影规则：

1. `taskTree != null` 时，Task Domain 优先成为 active domain；
2. pending authoring asks 转为 `superseded`、隐藏为 active 控件，或作为
   read-only history/audit evidence 暴露；
3. 用户旧回答不能隐式生成新的 RawTask；
4. 如需复用旧回答，必须通过显式命令进入 plan guidance 或 draft revision。
5. 如果 session-level `active_authoring_state` 仍停留在 `raw_task`，但
   `TaskTreeView` 已存在，Gateway 应把该状态诊断为
   `dirty_authoring_state`。诊断不等于删除数据；RawTask/ASK 仍作为
   lineage/audit 事实保留。

前端只负责展示已归一化 ViewModel，不应在组件里自行判断 RawTask 与
TaskTree 谁优先。

## 4. Transport 方向

第一版推荐：

```text
Query / Command: HTTP JSON
Event: SSE
Base path: /api/v1
```

WebSocket 暂不作为 MVP 必需项。

原因：

- HTTP 容易调试、测试和重放；
- SSE 足够覆盖系统到 UI 的实时消息；
- Plato 当前不是多人同时编辑器，双向低延迟协议不是第一优先级。

## 5. 基础类型

### 5.1 ID 类型

```ts
type ProjectId = string;
type WorkflowId = string;
type SessionId = string;
type TaskTreeId = string;
type TaskNodeId = string;
type MessageId = string;
type ConfirmationId = string;
type ResultId = string;
type CommandId = string;
type EventCursor = string;
```

后续 published/draft 任务并存时，API 边界应逐步升级到 `TaskRef`：

```ts
type TaskRef = {
  kind: "draft" | "published";
  id: string;
};
```

MVP 前端原型目前使用 `TaskNodeId`。F6 可以先兼容 `taskNodeId`，但 Gateway 层应为 `TaskRef` 留扩展位。

### 5.2 时间与排序

- 所有时间使用 ISO 8601 字符串。
- Session Message 默认按 `createdAt ASC` 返回。
- TaskTree 默认按 UI preorder 返回。
- 同时间事件用稳定 id 或后端 cursor 做 tie-break。

## 6. Envelope

### 6.1 QueryResponse

```ts
type QueryResponse<T> = {
  requestId: string;
  ok: boolean;
  data: T | null;
  error: ApiError | null;
  cursor?: EventCursor | null;
  generatedAt: string;
};
```

### 6.2 CommandRequest

```ts
type CommandRequest<TPayload> = {
  commandId: CommandId;
  sessionId: SessionId;
  idempotencyKey?: string | null;
  expectedVersion?: number | null;
  payload: TPayload;
};
```

### 6.3 CommandResponse

```ts
type CommandResponse = {
  requestId: string;
  ok: boolean;
  result: CommandResult | null;
  error: ApiError | null;
  refresh: RefreshHint;
};
```

```ts
type CommandResult = {
  commandId: CommandId;
  status: "accepted" | "rejected";
  message: string;
  affectedTaskRefs: TaskRef[];
  objectRefs: ObjectRef[];
  affectedObjects: AffectedObjectRef[];
  emittedMessageIds: MessageId[];
  publishedTaskIds: string[];
  debugRefs: Record<string, string>;
};
```

```ts
type RefreshHint = {
  waitForEvents: boolean;
  suggestedQueries: string[];
  affectedTaskRefs: TaskRef[];
  affectedScopes: AffectedScope[];
};
```

```ts
type ObjectRef = {
  kind:
    | "raw_task"
    | "raw_task_ask"
    | "plan"
    | "draft_task"
    | "draft_tree"
    | "draft_subtree"
    | "published_task"
    | "message"
    | "command";
  id: string;
};

type AffectedObjectRef = {
  ref: ObjectRef;
  impact:
    | "changed"
    | "created"
    | "deleted"
    | "may_need_update"
    | "needs_review"
    | "invalidated"
    | "replaced"
    | "superseded";
  reason?: string | null;
};

type AffectedScope = {
  kind:
    | "session"
    | "task_tree"
    | "task_subtree"
    | "task_detail"
    | "messages"
    | "confirmations";
  taskRef?: TaskRef | null;
  reason?: string | null;
};
```

### 6.4 ApiError

```ts
type ApiError = {
  code:
    | "bad_request"
    | "not_found"
    | "version_conflict"
    | "command_rejected"
    | "permission_denied"
    | "backend_busy"
    | "resync_required"
    | "internal_error";
  message: string;
  retryable: boolean;
  details: Record<string, unknown>;
};
```

`code="command_rejected"` 可使用 `details.reason` 承载更细的领域拒绝原因。
其中 `stale_authoring_context` 表示用户正在回答的 authoring ASK 已经被当前
TaskTree / Task Domain supersede。前端收到后应刷新 snapshot，并提示用户改用
plan guidance 或显式修订计划。

### 4.x Dirty Authoring Session Repair

维护入口：

```http
POST /api/v1/sessions/{sessionId}/authoring/repair
```

请求：

```ts
type RepairAuthoringStatePayload = {
  reason: "dirty_authoring_state";
};
```

语义：

- 只在 `active_authoring_state == raw_task` 且当前 session 已有 TaskTree 时
  接受；
- 将 session active authoring state 关闭为 `cancelled`；
- 不删除 RawTask、RawTaskAsk、RawTaskAnswer 或 DraftTaskTree；
- 返回 `session.snapshot`、`session.messages`、`task.tree` refresh hint；
- 如果没有 dirty state，返回 `command_rejected`，不产生副作用。

## 7. Main Page ViewModel

### 7.1 MainPageSnapshot

`MainPageSnapshot` 是 Main Page 初始化和恢复的核心查询结果。

```ts
type MainPageSnapshot = {
  project: ProjectSummary;
  workflows: WorkflowSummary[];
  workflow: WorkflowSummary;
  sessions: SessionSummary[];
  session: SessionSummary;
  activePlan: PlanView | null;
  /**
   * Deprecated compatibility field.
   * During migration this equals activePlan.taskTreeProjection when a Plan is
   * available from legacy projection.
   */
  taskTree: TaskTreeView | null;
  messages: SessionMessageView[];
  pendingConfirmations: ConfirmationActionView[];
  result: ResultCardView | null;
  fileChangeSummary: FileChangeSummaryView | null;
  auditLinks: AuditLinkView[];
  cursor: EventCursor | null;
  generatedAt: string;
};
```

Product 1.1 新代码应优先读取 `activePlan`。`taskTree` 只保留给旧 Main Page
组件和旧命令路径兼容；它不是新的产品级工作对象。

Snapshot 不包含：

- `selectedTaskNodeId`
- `selectedTarget`
- `detailMode`
- `inputDraft`
- `expandedNodeIds`

这些由前端本地 store 管理。

`selectedTarget = "plan"` 表示用户正在选中整个 TaskTree/plan，而不是某个
TaskNode。它只影响 Main Page 的 detail/input 作用域，不写回后端。

### 7.2 ProjectSummary

```ts
type ProjectSummary = {
  id: ProjectId;
  name: string;
};
```

### 7.3 WorkflowSummary

```ts
type WorkflowSummary = {
  id: WorkflowId;
  name: string;
  description: string;
  inputHint?: string;
  deliveryKind?: "task_tree" | "execution_result" | "result_card" | "audit_review";
};
```

### 7.4 SessionSummary

```ts
type SessionStatus =
  | "new"
  | "understanding"
  | "draft_ready"
  | "running"
  | "waiting_user"
  | "completed"
  | "failed";

type SessionSummary = {
  id: SessionId;
  projectId: ProjectId;
  workflowId: WorkflowId;
  name: string;
  status: SessionStatus;
  createdAt: string;
  updatedAt: string;
  workspaceLabel?: string;
};
```

`workspaceLabel` 面向用户展示，例如 `Isolated session workspace`。不要把真实本地路径默认暴露给普通用户。

### 7.5 PlanView

```ts
type PlanUiStatus =
  | "draft"
  | "reviewing"
  | "ready_to_publish"
  | "published"
  | "running"
  | "finalizing"
  | "ready_for_review"
  | "accepted"
  | "follow_up_needed"
  | "failed"
  | "cancelled"
  | "unknown";

type PlanView = {
  id: PlanId;
  sessionId: SessionId;
  title: string;
  summary: string;
  objective: string;
  status: PlanUiStatus;
  taskCount: number;
  taskNodeIds: TaskNodeId[];
  taskNodes: TaskNodeCardView[];
  executionRollup: ExecutionRollupView;
  finalization: PlanFinalizationView;
  outcome: PlanOutcomeView | null;
  permissions: PlanPermissions;
  /**
   * Deprecated compatibility projection for legacy Main Page components.
   */
  taskTreeProjection?: TaskTreeView | null;
  sourceKind:
    | "plan_store"
    | "legacy_draft_tree"
    | "legacy_published_task_tree"
    | "synthetic";
  sourceRef?: ObjectRef | null;
  version: number;
};
```

`PlanView` 是 Product 1.1 的 canonical work contract。PTC-2 只要求它能
安全表达 active Plan；PTC-3 才负责完整 legacy DraftTaskTree / published
task projection-only migration。

### 7.6 TaskTreeView

```ts
type TaskTreeView = {
  id: TaskTreeId;
  sessionId: SessionId;
  title: string;
  summary?: string | null;
  status: "draft" | "published" | "running" | "completed" | "failed";
  nodes: TaskNodeCardView[];
  version: number;
};
```

`TaskTreeView` 是 deprecated compatibility projection。第一版 `nodes`
返回 legacy preorder。PTC-3 会把 legacy tree 作为 synthetic Plan 投影时
flatten 成 Product 1.1 的扁平 TaskNode list。

`summary` 是面向用户的计划概况，不是 TaskTree 的内部类型名。Main Page 的
`Plan overview` 行优先展示 `summary`；缺失时前端只能用 TaskNode 标题生成临时概况。
产品目标是在生成 Raw Task → TaskTree 时由 Collaborator/LLM 一并生成该字段，避免用户看到
`Task Tree` 这类系统内部命名。

`TaskTreeView.id` 是 UI projection/cache/debug id，不是普通用户可见字段。产品 UI 默认展示 `title`、状态和节点内容，不展示该 id。第一版允许 synthetic id；如果 command 需要真实 draft tree id，必须由 Gateway 解析，不能把 synthetic projection id 当成 domain primary key。

### 7.7 TaskNodeCardView

```ts
type TaskNodeStatus =
  | "draft"
  | "queued"
  | "running"
  | "waiting_user"
  | "done"
  | "failed"
  | "cancelled";

type TaskNodeCardView = {
  id: TaskNodeId;
  planId?: PlanId | null;
  taskRef?: TaskRef;
  parentId: TaskNodeId | null;
  taskIndex?: string | null;
  title: string;
  // Card-safe short summary. No concatenated Summary:/Instructions: markers.
  summary: string;
  // Detail-only structured content.
  intent?: string | null;
  instructions?: string | null;
  acceptanceCriteria: string[];
  status: TaskNodeStatus;
  depth: number;
  orderIndex: number;
  displayIndex: number;
  badges: TaskNodeBadges;
  permissions: TaskNodePermissions;
  version: number;
};
```

`planId` 和 `taskIndex` 是 Product 1.1 字段。兼容期里旧 `taskTree` 调用方
可以暂时缺省；`activePlan.taskNodes` 必须提供稳定的 `planId` 和用户可见
`taskIndex`。

`summary` 是列表卡片专用短摘要；`intent`、`instructions`、
`acceptanceCriteria` 是 Detail Panel 专用结构化字段。后端 projection
必须优先使用结构化字段；遇到旧数据中拼接的 `Summary:`、`Instructions:`、
`Acceptance criteria:` 文本时，可以在 projection 层拆分，但不应继续把
这些 marker 暴露到卡片。

```ts
type TaskNodeBadges = {
  pendingConfirmationCount: number;
  unreadMessageCount: number;
  directFileChangeCount: number;
  subtreeFileChangeCount: number;
};

type TaskNodePermissions = {
  canEdit: boolean;
  canAppendGuidance: boolean;
  canResolveConfirmation: boolean;
  canPublish: boolean;
  canCancel: boolean;
  canRetry: boolean;
};
```

MVP 可以先只返回 `id/title/summary/status/parentId`，但 Gateway 层应按上述目标组织。

### 7.8 TaskNodeDetailView

选中 TaskNode 后，Detail Panel 可按需查询 detail。

```ts
type TaskNodeDetailView = {
  node: TaskNodeCardView;
  fullIntent: string;
  constraints: string[];
  messages: SessionMessageView[];
  confirmations: ConfirmationActionView[];
  result: ResultCardView | null;
  fileChanges: FileChangeSummaryView | null;
  auditLinks: AuditLinkView[];
  timelineCursor?: EventCursor | null;
};
```

### 7.9 SessionMessageView

```ts
type MessageKind = "informational" | "actionable" | "response" | "error";

type SessionMessageView = {
  id: MessageId;
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  taskRef?: TaskRef | null;
  kind: MessageKind;
  title: string;
  body: string;
  createdAt: string;
  relatedConfirmationId?: ConfirmationId | null;
  relatedCommandId?: CommandId | null;
};
```

规则：

- `taskNodeId = null` 表示 Session-level 消息；
- 有 Task 归属的消息同时出现在 Session Stream 和 Task projection；
- actionable message 可以关联 `ConfirmationActionView`。

### 7.10 ConfirmationActionView

```ts
type ConfirmationActionView = {
  id: ConfirmationId;
  sessionId: SessionId;
  taskNodeId: TaskNodeId;
  taskRef?: TaskRef | null;
  title: string;
  body: string;
  options: ConfirmationOptionView[];
  defaultOptionValue?: string | null;
  status: "pending" | "resolved" | "expired";
  riskLabel?: string;
  createdAt: string;
  resolvedAt?: string | null;
};
```

```ts
type ConfirmationOptionView = {
  value: string;
  label: string;
  tone?: "primary" | "secondary" | "danger";
};
```

第一版可以把 `ConfirmationId` 视为 actionable message id，但 API 字段应保持独立。

### 7.10 ResultCardView

```ts
type ResultCardView = {
  id: ResultId;
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  title: string;
  summary: string;
  sections?: ResultSectionView[];
  updatedAt: string;
};
```

```ts
type ResultSectionView = {
  title: string;
  body: string;
  kind?: "text" | "list" | "metric" | "link";
};
```

Result Card 是用户视角的产物摘要，不是日志，也不是完整审计。

### 7.11 FileChangeSummaryView

```ts
type FileChangeSummaryView = {
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  recursive: boolean;
  changedFiles: FileChangeItemView[];
  summary: string;
  updatedAt: string;
};
```

```ts
type FileChangeItemView = {
  path: string;
  changeType: "created" | "modified" | "deleted" | "renamed";
  summary?: string;
  ownerTaskNodeId?: TaskNodeId | null;
};
```

父节点文件变更规则：

- 子节点仍然拥有自己的 direct file changes；
- 父节点展示 `recursive=true` 的子树汇总；
- UI 不应自己递归拼文件列表，后端 projection 负责汇总。

### 7.12 AuditLinkView

```ts
type AuditLinkView = {
  label: string;
  href: string;
  severity?: "info" | "warning" | "danger";
};
```

MVP Main Page 只暴露 Audit 入口和简要提示。完整审计页后续独立设计。

## 8. Query API

### 8.1 Required Queries

| Method | Path | Return | 用途 |
|---|---|---|---|
| `GET` | `/api/v1/projects` | `ProjectSummary[]` | 左上项目导航。 |
| `GET` | `/api/v1/projects/{projectId}/workflows` | `WorkflowSummary[]` | Workflow 列表。 |
| `GET` | `/api/v1/workflows/{workflowId}/sessions` | `SessionSummary[]` | 左侧 Session 列表。 |
| `GET` | `/api/v1/sessions/{sessionId}/snapshot` | `MainPageSnapshot` | Main Page 初始化和 resync。 |
| `GET` | `/api/v1/sessions/{sessionId}/messages` | `SessionMessageView[]` | Session Message Stream。 |
| `GET` | `/api/v1/sessions/{sessionId}/task-tree` | `TaskTreeView | null` | TaskTree 局部刷新。 |
| `GET` | `/api/v1/sessions/{sessionId}/tasks/{taskNodeId}` | `TaskNodeDetailView` | Detail Panel 选中任务。 |
| `GET` | `/api/v1/sessions/{sessionId}/confirmations/pending` | `ConfirmationActionView[]` | 待确认动作。 |
| `GET` | `/api/v1/sessions/{sessionId}/tasks/{taskNodeId}/file-changes?recursive=true` | `FileChangeSummaryView` | 文件变更摘要。 |
| `GET` | `/api/v1/sessions/{sessionId}/result` | `ResultCardView | null` | Session 结果卡。 |

### 8.2 Snapshot 装载流程

```text
1. UI knows current session id
2. GET /api/v1/sessions/{sessionId}/snapshot
3. Render Project / Workflow / Session / TaskTree / Messages / Detail default
4. Start SSE with snapshot.cursor
5. On event, patch or re-query affected view
```

如果 UI 没有当前 Session：

```text
1. GET /api/v1/projects
2. choose default project
3. GET /api/v1/projects/{projectId}/workflows
4. choose default workflow
5. create or select session
6. load snapshot
```

### 8.3 Task Message Projection

Task 消息查询可以是显式接口：

```text
GET /api/v1/sessions/{sessionId}/messages?taskNodeId=...
```

也可以由 `TaskNodeDetailView.messages` 返回。

两者语义相同：都来自唯一 Session Message Stream。

## 9. Command API

### 9.1 Required Commands

| Method | Path | Payload | 语义 |
|---|---|---|---|
| `POST` | `/api/v1/sessions` | `CreateSessionPayload` | 创建 Session。 |
| `POST` | `/api/v1/sessions/{sessionId}/input` | `AppendSessionInputPayload` | Session-level 自然语言输入。 |
| `POST` | `/api/v1/sessions/{sessionId}/task-tree/generate` | `GenerateTaskTreePayload` | 从自然语言生成 Draft TaskTree。 |
| `PATCH` | `/api/v1/sessions/{sessionId}/tasks/{taskNodeId}` | `UpdateTaskNodePayload` | 修改 draft/pending TaskNode。 |
| `POST` | `/api/v1/sessions/{sessionId}/tasks/{taskNodeId}/input` | `AppendTaskInputPayload` | Task-scoped 补充信息。 |
| `POST` | `/api/v1/sessions/{sessionId}/task-tree/publish` | `PublishTaskTreePayload` | 发布 TaskTree 到 TaskBus。 |
| `POST` | `/api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond` | `ResolveConfirmationPayload` | 处理确认动作。 |
| `POST` | `/api/v1/sessions/{sessionId}/tasks/{taskNodeId}/cancel` | `CancelTaskPayload` | 取消 draft 或未开始 Task。 |
| `POST` | `/api/v1/sessions/{sessionId}/tasks/{taskNodeId}/retry` | `RetryTaskPayload` | failed Task 原地回到 pending，并保留失败审计事实。 |

### 9.2 CreateSessionPayload

```ts
type CreateSessionPayload = {
  projectId: ProjectId;
  workflowId: WorkflowId;
  name?: string;
  initialInput?: string;
};
```

### 9.3 AppendSessionInputPayload

```ts
type AppendSessionInputPayload = {
  content: string;
  mode: "global_guidance" | "generate_task_tree";
};
```

用户未选中 TaskNode 时，底部输入框走该命令。

### 9.4 GenerateTaskTreePayload

```ts
type GenerateTaskTreePayload = {
  prompt: string;
  context?: Record<string, unknown>;
};
```

第一版由 Collaborator Agent 处理。命令 accepted 后，UI 等待 `task.tree.changed` 或重新查询 snapshot。

### 9.5 UpdateTaskNodePayload

```ts
type UpdateTaskNodePayload = {
  title?: string;
  summary?: string;
  fullIntent?: string;
  constraints?: string[];
  updateMode?: "node_fields" | "replace_children" | "replace_subtree";
  preserveRootId?: boolean;
};
```

规则：

- `draft` / `queued` 可修改；
- `updateMode="node_fields"` 只修改当前节点字段；
- `updateMode="replace_children"` / `"replace_subtree"` 表示父节点语义变化可能影响后代，后端可重建子节点或整棵子树；
- `replace_subtree` 默认保留当前 root node id，后代节点可以被替换；
- `running` 不原地修改，走 `appendTaskInput`；
- `done` 只读；
- `failed` 只读，可 retry。

### 9.6 AppendTaskInputPayload

```ts
type AppendTaskInputPayload = {
  content: string;
  mode: "guidance" | "revision_request" | "clarification_answer";
};
```

用户选中 TaskNode 时，底部输入框走该命令。

### 9.7 PublishTaskTreePayload

```ts
type PublishTaskTreePayload = {
  taskTreeId?: TaskTreeId;
  startImmediately: boolean;
};
```

`taskTreeId` 可缺省。Gateway 必须优先解析当前 Session 的 active
`draft_tree_id`：

- 缺省时发布 active draft tree；
- 如果传入真实 active `draft_tree_id`，发布该 active tree；
- 如果传入旧版 synthetic `TaskTreeView.id`，Gateway 应解析为 active
  draft tree，或返回结构化身份错误；
- 如果 Gateway 没有 active authoring state 可用，且收到 synthetic id，返回
  `bad_request`，错误详情包含
  `reason = "synthetic_task_tree_identity_unresolved"`；
- 如果传入非 active tree id，返回 `bad_request`，错误详情包含
  `reason = "invalid_task_tree_identity"`；
- 如果当前 Session 没有 active draft tree，返回 `bad_request`，错误详情包含
  `reason = "no_active_draft_tree"`。

前端不应把 `TaskTreeView.id` 当成可发布 domain primary key；发布路径应依赖
Gateway 的 active draft tree 解析，或在 contract 明确返回真实 draft tree id。

UI/API 层的 publish 动作语义是“用户接受当前草稿并发布”。因此 adapter 可以先把
DraftTaskTree 标记为 accepted，再调用底层 authoring publish boundary。底层
`PublishDraftTaskTreeCommand` 仍保持更严格的规则：未 accepted 的 tree 不能被直接发布。

发布后 UI 应看到：

- TaskTree status 从 `draft` 进入 `published` 或 `running`；
- TaskNode status 进入 `queued` / `running`；
- Session Message Stream 追加发布消息。

### 9.8 RetryTaskPayload

```ts
type RetryTaskPayload = {
  instruction?: string;
  startImmediately: boolean;
};
```

规则：

- 只允许 retry `failed` published Task；
- retry 是显式用户命令，不自动触发；
- 后端将同一个 published Task 从 `failed` 重置为 `pending`，不创建新的
  Task identity；
- retry 会清空当前 `error_ref` / `result_ref` / claim / started /
  completed 执行字段；历史失败保留在 MessageStream、result/error summary、
  Audit/日志等 append-only 事实中；
- 如果 payload 携带 `instruction`，后端应把它作为本次 retry 的用户指导写入
  task-scoped message，并可将其并入下一次执行输入；
- Main Page snapshot / TaskTree 控制面继续显示原 Task，只是状态从
  `failed` 回到 `queued` / `running`；
- 下游 Task 依赖仍以该 Task 本身为准：该 Task 到达 `done` 后，子任务才可继续推进；
- `startImmediately=true` 时，命令接受后请求 fixed-route execution dispatch；
- 不支持的 retry 返回结构化 `command_rejected`。

### 9.9 ResolveConfirmationPayload

```ts
type ResolveConfirmationPayload = {
  value: string;
  note?: string;
};
```

规则：

- 必须写回 Session Message Stream；
- 必须触发 `confirmation.resolved`；
- 如果影响 Task 状态，继续触发 `task.node.changed` 或 `task.tree.changed`。

## 10. Event API

### 10.1 SSE Endpoint

```text
GET /api/v1/sessions/{sessionId}/events?cursor=...
Accept: text/event-stream
```

### 10.2 UiEvent

```ts
type UiEvent = {
  eventId: string;
  sessionId: SessionId;
  eventType: UiEventType;
  cursor: EventCursor;
  taskNodeIds: TaskNodeId[];
  taskRefs?: TaskRef[];
  messageIds: MessageId[];
  commandId?: CommandId | null;
  payload: Record<string, unknown>;
  createdAt: string;
};
```

### 10.3 Required Event Types

```ts
type UiEventType =
  | "session.status_changed"
  | "session.resync_required"
  | "task.tree.changed"
  | "task.node.changed"
  | "message.appended"
  | "confirmation.created"
  | "confirmation.resolved"
  | "result.updated"
  | "file_changes.updated"
  | "audit.summary_updated"
  | "command.completed"
  | "command.failed";
```

### 10.4 Event Handling Rules

| Event | UI 行为 |
|---|---|
| `session.status_changed` | 刷新 top status 或 snapshot。 |
| `task.tree.changed` | 重新查询 TaskTreeView。 |
| `task.node.changed` | 刷新对应 TaskNode card；若被选中，刷新 detail。 |
| `message.appended` | 追加消息或重新查询 messages。 |
| `confirmation.created` | 展示确认入口，更新待确认数量。 |
| `confirmation.resolved` | 更新消息、确认卡和 TaskNode 状态。 |
| `result.updated` | 刷新 ResultCardView。 |
| `file_changes.updated` | 刷新 FileChangeSummaryView。 |
| `session.resync_required` | 重新查询 snapshot。 |

Event payload 第一版可以很薄，只给 `reason` 和 affected ids。完整数据通过 Query 获取。

当前后端 `message.appended` 事件尤其需要注意：它携带 `messageIds`、`taskRefs`、`message_type`、`agent_id` 等轻量字段，不承诺携带 `SessionMessageView.title/body`。前端不能把 `message.appended.payload` 当成完整消息卡片；可选策略是：

1. 如果事件足够完整，再做局部 append；
2. 否则根据 `messageIds` / `affectedScopes` 重新查询 snapshot 或 messages；
3. 任何完整 UI 文案以 `SessionMessageView` 查询结果为准。

## 11. Frontend Adapter Rules

前端应通过 adapter 把 API ViewModel 转换为 UI runtime model。

### 11.1 目标目录

```text
frontend/src/shared/api/
  client.ts
  platoApi.ts
  types.ts

frontend/src/entities/
  project/model.ts
  workflow/model.ts
  session/model.ts
  task/model.ts
  message/model.ts
  result/model.ts
  file-change/model.ts
  audit/model.ts
```

### 11.2 Adapter 职责

Adapter 可以做：

- 字段命名转换；
- 默认值补齐；
- status 到 badge tone 的轻量映射；
- API `TaskRef` 到当前 `TaskNodeId` 的兼容；
- command response 到 pending UI state 的映射。

Adapter 不应该做：

- 从 Message 自己推断 TaskTree；
- 从多个接口手动拼父节点文件汇总；
- 把后端内部错误吞掉；
- 把 selected/focused/expanded 写回后端。

### 11.3 Fixture 对齐

F4 现有 fixture 字段可以视为 API contract 的最小子集：

| 当前前端字段 | Contract 目标 |
|---|---|
| `ProjectSummary` | `ProjectSummary` |
| `WorkflowSummary` | `WorkflowSummary` |
| `SessionSummary` | `SessionSummary` |
| `TaskTree` | `TaskTreeView` |
| `TaskNode` | `TaskNodeCardView` |
| `SessionMessage` | `SessionMessageView` |
| `ResultCard` | `ResultCardView` |
| `FileChangeSummary` | `FileChangeSummaryView` |

F6 可以先用 adapter 兼容当前简化字段，再逐步扩展实体模型。

## 12. Error Visibility

| 错误类型 | Session Message | UI 局部错误 | 日志 |
|---|---:|---:|---:|
| 表单校验失败 | No | Yes | Optional |
| version conflict | No | Yes | Yes |
| command rejected | Optional | Yes | Yes |
| LLM / collaborator 失败 | Yes, if user-visible task impact | Yes | Yes |
| backend internal error | No | Yes | Yes |
| event cursor expired | No | Yes, then resync | Yes |

原则：

- 用户需要知道任务为何停住；
- 用户不需要看到所有 transport 或开发错误；
- 可追溯信息进入日志和 audit，不把 Main Page 变成调试控制台。

## 13. F6 Backend Integration 建议切片

### F6.1 API types and mock adapter

产出：

- `frontend/src/shared/api/types.ts`
- `frontend/src/shared/api/platoApi.ts`
- fixture adapter

退出标准：

- API client 不直接 import fixture shape；
- API 类型与本文一致。

当前状态：已完成 `shared/api/types.ts` / `platoApi.ts`，并有后端 JSON fixture parity 测试。Main Page 页面仍通过 `mockPlatoApi` 的 adapter/metadata 类型兼容旧 fixture 状态，这是后续 runtime 收敛要拆掉的部分。

### F6.2 Snapshot query

产出：

- `GET /api/v1/sessions/{sessionId}/snapshot` 客户端调用；
- loading / error / ready 三态；
- 本地 fixture fallback 可保留为 dev mode。

退出标准：

- Main Page 可从 mock server 或真实 Gateway 装载 snapshot。

当前状态：HTTP adapter 已可从 sidecar snapshot 装载数据，但 query key 和页面状态仍以 `stateId` 兼容层为主。真实运行态应转为 session-centric query key。

### F6.3 Command wiring

产出：

- Session input；
- Task input；
- resolve confirmation；
- publish TaskTree。

退出标准：

- 用户操作不再只改本地 state；
- CommandResponse 被转成 pending / rejected / refresh。

当前状态：部分完成。Session input、Task input、resolve confirmation 已通过 adapter 发命令；但命令 accepted 后仍主要写入 local synthetic message / local decision state，没有系统使用 `refresh.affectedScopes` 或 canonical events 来驱动查询失效。

### F6.4 SSE event stream

产出：

- subscribe session events；
- event cursor；
- reconnect；
- `session.resync_required` fallback。

退出标准：

- message appended / confirmation resolved / task status changed 能实时反映。

当前状态：低层 client 已监听 default `message` 和所有 canonical named events；Main Page 目前只消费 `message.appended` 与 `session.resync_required`，并且对 `message.appended` 的 payload 期待比后端当前 contract 更重。下一步需要把事件处理改为 invalidation/refetch-first。

### F6.5 Result and file change projection

产出：

- ResultCardView query；
- FileChangeSummaryView query；
- 父节点 recursive file summary。

退出标准：

- 完成态可以展示真实结果和文件修改摘要。

## 14. Open Questions

这些问题不阻塞 F6，但需要后续收紧：

1. `TaskRef` 何时替代裸 `TaskNodeId` 成为前端默认引用？
2. `RawTask` authoring 阶段是否需要独立 snapshot，还是先归入 Session snapshot？
3. `Workflow` 默认策略配置是否随 snapshot 返回，还是独立配置接口？
4. `ResultCardView.sections` 是否需要第一版支持结构化卡片渲染？
5. Audit 入口是否只暴露 href，还是返回 lightweight audit summary？
6. SSE event retention 时间和 cursor 过期策略由哪个后端组件负责？已决定不放入 contract baseline，转入 sidecar/SSE plan。

## 15. 第一版验收标准

F5 完成后，团队应能回答：

- Main Page 首屏需要哪一个 snapshot；
- 哪些用户操作是 command；
- 哪些后端变化通过 event 通知；
- Task 消息如何从 Session Message Stream 投影；
- Confirmation 如何回写消息流；
- Result 和 File Change Summary 如何查询；
- 前端哪些状态不属于后端事实源。

满足这些条件后，可以进入 F6 后端通信。
