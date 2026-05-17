# Plato UI API Contract

> Status: MVP contract draft
>
> Last Updated: 2026-05-17
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

F5 的目标是把 Plato 前端原型需要的后端边界写清楚。

第一版前端已经具备：

- Main Page 工作台骨架；
- 9 个 Figma baseline 状态；
- TaskNode 选中；
- Detail Panel 动态切换；
- Context Input 作用域变化；
- Confirmation 操作；
- Result / File Change Summary 切换。

下一步 F6 要把这些能力接入真实后端。为了避免 UI 直接依赖内部对象，必须先定义稳定 API 合约：

```text
Backend domain / stores / bus
  -> UI Gateway
  -> Query / Command / Event contract
  -> Frontend adapter
  -> Plato UI ViewModel
```

本文定义的是语义稳定层，不要求第一版立刻实现完整 HTTP server。

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
  emittedMessageIds: MessageId[];
  publishedTaskIds: string[];
};
```

```ts
type RefreshHint = {
  waitForEvents: boolean;
  suggestedQueries: string[];
  affectedTaskRefs: TaskRef[];
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
    | "backend_busy"
    | "resync_required"
    | "internal_error";
  message: string;
  retryable: boolean;
  details: Record<string, unknown>;
};
```

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

Snapshot 不包含：

- `selectedTaskNodeId`
- `detailMode`
- `inputDraft`
- `expandedNodeIds`

这些由前端本地 store 管理。

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

### 7.5 TaskTreeView

```ts
type TaskTreeView = {
  id: TaskTreeId;
  sessionId: SessionId;
  title: string;
  status: "draft" | "published" | "running" | "completed" | "failed";
  nodes: TaskNodeCardView[];
  version: number;
};
```

第一版 `nodes` 返回 flat preorder。前端通过 `parentId` 还原树形和缩进。

### 7.6 TaskNodeCardView

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
  taskRef?: TaskRef;
  parentId: TaskNodeId | null;
  title: string;
  summary: string;
  status: TaskNodeStatus;
  depth: number;
  orderIndex: number;
  badges: TaskNodeBadges;
  permissions: TaskNodePermissions;
  version: number;
};
```

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

### 7.7 TaskNodeDetailView

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

### 7.8 SessionMessageView

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

### 7.9 ConfirmationActionView

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
| `POST` | `/api/v1/sessions/{sessionId}/tasks/{taskNodeId}/retry` | `RetryTaskPayload` | failed Task 创建 retry/follow-up。 |

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
};
```

规则：

- `draft` / `queued` 可修改；
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
  taskTreeId: TaskTreeId;
  startImmediately: boolean;
};
```

发布后 UI 应看到：

- TaskTree status 从 `draft` 进入 `published` 或 `running`；
- TaskNode status 进入 `queued` / `running`；
- Session Message Stream 追加发布消息。

### 9.8 ResolveConfirmationPayload

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

- Main Page 不直接 import fixture shape；
- API 类型与本文一致。

### F6.2 Snapshot query

产出：

- `GET /api/v1/sessions/{sessionId}/snapshot` 客户端调用；
- loading / error / ready 三态；
- 本地 fixture fallback 可保留为 dev mode。

退出标准：

- Main Page 可从 mock server 或真实 Gateway 装载 snapshot。

### F6.3 Command wiring

产出：

- Session input；
- Task input；
- resolve confirmation；
- publish TaskTree。

退出标准：

- 用户操作不再只改本地 state；
- CommandResponse 被转成 pending / rejected / refresh。

### F6.4 SSE event stream

产出：

- subscribe session events；
- event cursor；
- reconnect；
- `session.resync_required` fallback。

退出标准：

- message appended / confirmation resolved / task status changed 能实时反映。

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
6. SSE event retention 时间和 cursor 过期策略由哪个后端组件负责？

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
