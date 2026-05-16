# UI API 接口归档

> Status: aligned with Phase 3C Slice 9
> Last Updated: 2026-05-16
> 作用：归档 Task-first UI 各分述共同引用的接口需求。第一版定义接口边界、返回 ViewModel、命令语义和实时事件；字段细节以后随实现继续收紧。
> Transport: 具体 UI/后端通信契约见 [UI And Backend Communication](../../architecture/ui-backend-communication.md)。

---

## 1. 范围

本文档是 Task-first UI 的公共接口归档。所有 UI 分述文件只声明“依赖哪些接口”和“为什么依赖”，不在各自文档里重复定义接口结构。

当前版本已对齐 Phase 3C 的 Task domain/UI ViewModel 分层实现：

- 后端 Task 领域事实：`TaskDomain`
- draft authoring 事实：`DraftTaskNode` / `DraftTaskTree`
- UI 投影视图：`TaskTreeView` / `TaskCardView` / `TaskDetailView`
- 命令结果：`CommandResult`
- 可回放时间线：`TaskInteractionTimeline`

本文档刻意不规定 REST path、RPC 方法名、WebSocket 格式或前端框架。它定义的是稳定语义。

---

## 2. 核心约定

- **API 返回 ViewModel，不直接返回裸后端 Task。**
- **TaskRef 是 UI/API 边界上的 Task 引用。** `TaskRef(kind="draft"|"published", id=...)` 能同时表达草稿节点和已发布 Task。
- **消息只有一条 Session Message Stream。** Task Message View 是按 TaskRef/TaskId 过滤出的视图，不是第二套存储。
- **命令与查询分离。** 查询返回视图模型；命令表达用户意图并返回 `CommandResult`。
- **确认动作必须可回放。** `resolveConfirmation` 写回消息流，timeline 能看到 created/resolved。
- **父 Task 文件汇总是递归聚合。** 子节点仍然拥有 direct file changes；父节点只显示 roll-up。
- **UI local state 不进入后端事实源。** selected、expanded、focused、draft input、optimistic patch 属于前端 store。

---

## 3. 基础类型

| 类型 | 说明 |
|---|---|
| `SessionId` | 会话 ID |
| `TaskRef` | UI/API 边界引用：`kind=draft/published` + `id` |
| `TaskId` | 已发布 Task ID，只用于 published task 内部或调试语义 |
| `DraftTaskId` | draft task ID，只用于 draft store 内部或调试语义 |
| `MessageId` | Session Message ID |
| `ConfirmationId` | 确认动作 ID，第一版等于 actionable message id |
| `FileChangeId` | 文件变更记录 ID |
| `CommandId` | 命令追踪 ID |
| `Cursor` | 实时事件或分页查询游标 |

### 3.1 TaskRef

```python
class TaskRef(BaseModel):
    kind: Literal["draft", "published"]
    id: str
```

使用规则：

- UI 卡片、详情、命令、timeline 都应优先使用 `TaskRef`。
- Store 层可以继续使用 plain `task_id` / `draft_task_id`。
- API 不应该用一个裸字符串让前端猜它是 draft 还是 published。

### 3.2 状态类型

| 类型 | 值 |
|---|---|
| `TaskViewStatus` | `draft` / `pending` / `running` / `done` / `failed` / `cancelled` |
| `TaskDomain.status` | `pending` / `running` / `done` / `failed` |
| `DraftTaskNode.status` | `draft` / `accepted` / `published` / `cancelled` |

说明：

- `cancelled` 是 UI/draft/pending 操作语义；当前 published Task domain 仍保持极简 4 状态。
- `done` / `failed` 是执行终态；原地修改应禁止。

---

## 4. ViewModel 归档

字段细节以后可以扩展，但接口返回的模型名应尽量稳定。

| 模型 | 最低数据能力 | 当前代码位置 |
|---|---|---|
| `SessionOverview` | Session 标识、名称、整体状态、root Task 摘要、未处理确认数量 | 待实现 |
| `TaskTreeView` | 一个 Session 下的 Task card preorder 列表 | `taskweavn.task.views` |
| `TaskCardView` | 卡片展示数据：TaskRef、父子关系、标题、状态、badge、权限、主操作 | `taskweavn.task.views` |
| `TaskDetailView` | Card + 完整 intent、约束、消息、确认、文件、结果摘要 | `taskweavn.task.views` |
| `TaskCardBadges` | pending confirmations、unread、direct/subtree file count、child progress | `taskweavn.task.views` |
| `TaskCardPermissions` | can_edit / can_append_guidance / can_resolve_confirmation / can_publish / can_cancel / can_retry | `taskweavn.task.views` |
| `TaskCardAction` | UI 可渲染主操作，例如 edit、publish、confirm、retry | `taskweavn.task.views` |
| `SessionMessageView` | 消息 ID、Session、可选 TaskRef、类型、摘要、时间、关联动作 | `taskweavn.task.views` |
| `ConfirmationActionView` | 所属 TaskRef、prompt、options、default、risk summary、状态 | `taskweavn.task.views` |
| `TaskFileChangeSummary` | owner TaskRef、path、change type、summary、是否子树汇总、记录时间 | `taskweavn.task.views` |
| `TaskSummaryView` | 结果摘要、失败原因、后续建议、产物引用、更新时间 | `taskweavn.task.views` |
| `TaskInteractionTimeline` | 某 TaskRef 的可回放交互时间线 | `taskweavn.task.timeline` |
| `TaskInteractionEntry` | draft/message/confirmation/event/file/summary 统一时间线条目 | `taskweavn.task.timeline` |
| `TaskInteractionSnapshot` | `TaskDetailView` + `TaskInteractionTimeline` | `taskweavn.task.timeline` |

### 4.1 TaskTreeView

第一版推荐返回 flat preorder，而不是 nested children：

```python
class TaskTreeView(BaseModel):
    session_id: str
    nodes: tuple[TaskCardView, ...]
    generated_at: datetime
```

理由：

- 更容易 diff、分页和测试；
- UI 可根据 `depth` / `parent_ref` 还原树形展示；
- 避免大树局部更新时替换整棵嵌套树。

### 4.2 TaskCardView

```python
class TaskCardView(BaseModel):
    task_ref: TaskRef
    parent_ref: TaskRef | None
    root_ref: TaskRef
    title: str
    intent_preview: str
    status: TaskViewStatus
    depth: int
    order_index: int
    badges: TaskCardBadges
    permissions: TaskCardPermissions
    primary_actions: tuple[TaskCardAction, ...]
    confirmation: ConfirmationActionView | None
    latest_message: SessionMessageView | None
    file_summary: TaskFileChangeSummary | None
    progress: TaskProgressView | None
```

### 4.3 TaskDetailView

```python
class TaskDetailView(BaseModel):
    card: TaskCardView
    full_intent: str
    constraints: tuple[str, ...]
    messages: tuple[SessionMessageView, ...]
    confirmations: tuple[ConfirmationActionView, ...]
    file_changes: tuple[TaskFileChangeSummary, ...]
    result_summary: TaskSummaryView | None
    timeline_cursor: str | None
```

### 4.4 CommandResult

命令统一返回：

```python
class CommandResult(BaseModel):
    command_id: str
    status: Literal["accepted", "rejected"]
    message: str
    affected_task_refs: tuple[TaskRef, ...]
    emitted_message_ids: tuple[str, ...]
    published_task_ids: tuple[str, ...]
```

UI 不应仅依赖本地 optimistic state。命令 accepted 后，应等待订阅事件或重新查询 ViewModel。

---

## 5. 查询接口

| 接口 | 返回 | 最低能力 |
|---|---|---|
| `getSessionOverview(session_id)` | `SessionOverview` | Session 基本信息、root Task 摘要、当前运行状态、未处理确认数量 |
| `listTaskTrees(session_id, filters)` | `TaskTreeView` | 返回 draft/published Task cards 的 preorder 视图 |
| `getTaskCard(session_id, task_ref)` | `TaskCardView` | 返回单个卡片投影 |
| `getTaskDetail(session_id, task_ref, message_limit)` | `TaskDetailView` | 返回卡片详情、消息、确认、文件、摘要 |
| `getTaskTimeline(session_id, task_ref, filters)` | `TaskInteractionTimeline` | 返回可回放交互时间线 |
| `getTaskSnapshot(session_id, task_ref)` | `TaskInteractionSnapshot` | 一次性返回 detail + timeline |
| `listSessionMessages(session_id, filters)` | `list[SessionMessageView]` | 返回唯一 Session Message Stream 的 UI 视图 |
| `listTaskMessages(session_id, task_ref, scope)` | `list[SessionMessageView]` | `listSessionMessages` 的 Task 过滤便捷视图 |
| `listPendingConfirmations(session_id, filters)` | `list[ConfirmationActionView]` | 返回待用户处理的确认动作，可按 TaskRef 过滤 |
| `getTaskFileChanges(session_id, task_ref, recursive)` | `list[TaskFileChangeSummary]` | `recursive=true` 时父节点包含所有子孙 Task 汇总 |
| `getTaskSummary(session_id, task_ref)` | `TaskSummaryView | None` | 返回结果摘要、失败原因、后续建议 |

### 5.1 Query Protocol 对应关系

当前 server-core 已有或计划中的协议：

| API 语义 | 对应协议 |
|---|---|
| `listTaskTrees` / `getTaskCard` / `getTaskDetail` | `TaskProjectionService` |
| `getTaskTimeline` / `getTaskSnapshot` | `TaskInteractionTimelineService` |
| `listSessionMessages` / `listTaskMessages` | `MessageStream` + ViewModel adapter |
| `getTaskFileChanges` | `FileChangeStore` |
| `getTaskSummary` | `TaskSummaryStore` |

### 5.2 查询约定

- Task Tree 默认排序：topological preorder，然后 `order_index`，然后创建时间/稳定 id。
- 消息和 timeline 默认按时间升序。
- 消息类列表必须支持 cursor。
- Task Tree 查询必须返回足够父子关系数据，前端不应靠 title 或数组位置推断结构。
- `listTaskMessages` 不是新存储，只是 Session Message Stream 的 Task 过滤视图。
- 父 Task 查看文件时用 `recursive=true`；子 Task 直接归属不变。

---

## 6. 命令接口

| 接口 | 返回 | 最低能力 |
|---|---|---|
| `generateTaskTree(session_id, prompt, context)` | `CommandResult` + `TaskTreeView` refresh | 从自然语言生成 Draft Task Tree；由 Collaborator Agent 计划实现 |
| `updateTaskNode(session_id, task_ref, patch, expected_version?)` | `CommandResult` | 修改 draft Task 或 pending published Task |
| `appendTaskMessage(session_id, task_ref, content, mode)` | `CommandResult` | 给某个 Task 追加用户补充信息 |
| `appendSessionMessage(session_id, content, mode)` | `CommandResult` | 给整个 Session 追加全局用户输入 |
| `resolveConfirmation(session_id, confirmation_id, value, note?)` | `CommandResult` | 处理确认动作，写回消息流 |
| `publishTaskTree(session_id, draft_tree_id)` | `CommandResult` | 发布 draft tree，后续接 TaskPublisher / TaskBus |
| `startTaskExecution(session_id, task_ref)` | `CommandResult` | 从某个 Task 或 root Task 开始执行；后续接 TaskPublisher/TaskBus |
| `cancelTask(session_id, task_ref, reason)` | `CommandResult` | 取消 draft 或未开始 Task；运行中取消后续细化 |
| `retryTask(session_id, task_ref, instruction?)` | `CommandResult` | 基于 failed Task 创建 retry/fix Task |

### 6.1 Command Protocol 对应关系

当前 server-core 已有：

| API 语义 | 对应协议/服务 |
|---|---|
| `updateTaskNode` | `TaskCommandService.update_task_node` |
| `appendSessionMessage` | `CollaboratorApiAdapter.append_session_message` |
| `generateTaskTree` | `CollaboratorApiAdapter.generate_task_tree` |
| `appendTaskMessage` | `CollaboratorApiAdapter.append_task_message` for draft authoring; `TaskCommandService.append_task_message` for published Task guidance |
| `answerRawTaskAsk` | `CollaboratorApiAdapter.answer_raw_task_ask` |
| `resolveConfirmation` | `TaskCommandService.resolve_confirmation` |
| `publishTaskTree` | `CollaboratorApiAdapter.publish_task_tree` + `AuthoringCommandService` + `TaskPublisher` |
| `retryTask` | `TaskCommandService.retry_task` + `TaskPublisher` |

后续需要补充：

- `startTaskExecution`：TaskPublisher / TaskBus 集成后实现；
- `cancelTask`：draft/pending 取消规则需要和 TaskPublisher/TaskBus 对齐。

说明：

- `CollaboratorApiAdapter` 是当前 server-core 对 UI/API 的薄适配层。它返回稳定的 `CommandResult`，不会把 Collaborator LLM 的原始 proposal schema 暴露给 UI。
- `appendTaskMessage` 在 draft Task 上走 Collaborator authoring；published Task 的执行期指导仍走普通 `TaskCommandService`。

### 6.2 命令约定

- 命令接口不直接返回裸 `TaskDomain`。
- 命令 accepted 不代表 UI 本地状态自动可信；UI 应通过订阅事件或重新查询刷新。
- `updateTaskNode` 只能修改 `draft` / `pending` Task。
- `running` Task 的用户补充走 `appendTaskMessage`。
- `done` Task 只读；需要修改时创建 follow-up 或 retry Task。
- `failed` Task 原地只读；可通过 `retryTask` 创建新任务。
- `resolveConfirmation` 必须写入 Session Message Stream，并保留 resolved history。
- `TaskEditMode=task_scoped` 时，用户输入不触发全局 Task Tree 重新生成。

---

## 7. 实时事件接口

UI 需要订阅 Session 级事件流：

```text
subscribeSessionEvents(session_id, cursor?)
```

事件 envelope 第一版：

```python
class SessionEventEnvelope(BaseModel):
    event_id: str
    session_id: str
    task_ref: TaskRef | None
    type: str
    created_at: datetime
    payload: dict[str, object]
    cursor: str
```

最低事件类型：

| 事件 | 用途 |
|---|---|
| `draft_tree.created` | 新 draft tree 出现，刷新 Task Tree |
| `draft_task.updated` | draft node 被 patch，刷新卡片/子树 |
| `task.published` | draft 转 published，连接 draft/published refs |
| `task.created` | 新 published Task 出现 |
| `task.updated` | intent / constraints / dispatch metadata 变化 |
| `task.status_changed` | 更新节点状态、权限、progress |
| `message.appended` | 更新 Session Stream 和 Task Message View |
| `confirmation.created` | 新增待确认动作 |
| `confirmation.resolved` | 确认动作完成 |
| `file_change.recorded` | 更新 Task 文件变更摘要 |
| `task.summary_updated` | 更新 Task Summary |

第一版可以由查询刷新驱动；事件订阅是 UI 增量更新和实时体验的下一层。

---

## 8. 子文档接口依赖矩阵

| 子文档 | 主要接口 |
|---|---|
| `information-architecture.md` | `getSessionOverview`、`listTaskTrees`、`listSessionMessages`、`listPendingConfirmations`、`subscribeSessionEvents` |
| `task-generation-flow.md` | `generateTaskTree`、`publishTaskTree`、`updateTaskNode`、`listTaskTrees`、`startTaskExecution` |
| `task-tree-view.md` | `listTaskTrees`、`getTaskCard`、`getTaskDetail`、`listPendingConfirmations`、`getTaskFileChanges`、`subscribeSessionEvents` |
| `task-node-detail.md` | `getTaskDetail`、`getTaskTimeline`、`updateTaskNode`、`appendTaskMessage`、`listTaskMessages`、`listPendingConfirmations`、`getTaskFileChanges`、`getTaskSummary`、`retryTask` |
| `task-message-view.md` | `listTaskMessages`、`listSessionMessages`、`appendTaskMessage`、`resolveConfirmation`、`subscribeSessionEvents` |
| `session-message-stream.md` | `listSessionMessages`、`appendSessionMessage`、`subscribeSessionEvents` |
| `confirmation-actions.md` | `listPendingConfirmations`、`resolveConfirmation`、`listTaskMessages`、`listSessionMessages`、`subscribeSessionEvents` |
| `task-editing-rules.md` | `updateTaskNode`、`appendTaskMessage`、`cancelTask`、`retryTask`、`getTaskDetail` |
| `file-change-summary.md` | `getTaskFileChanges`、`getTaskDetail`、`subscribeSessionEvents` |
| `task-scoped-chat-flow.md` | `appendTaskMessage`、`listTaskMessages`、`getTaskDetail`、`updateTaskNode` |

---

## 9. 关键跨文档约定

- API 返回 ViewModel；裸 `TaskDomain` 只用于内部调度、调试或开发者视图。
- `TaskRef` 是 UI/API 层的默认引用。
- `listTaskMessages` 不代表第二套存储，只是 `listSessionMessages(..., task_ref=...)` 的语义别名。
- `getTaskFileChanges(..., recursive=true)` 用于父节点汇总；`recursive=false` 用于直接归属。
- `TaskInteractionTimeline` 是回放用户交互的首选接口；不要让前端自己拼所有事实源。
- `resolveConfirmation` 必须把结果写回 Session Message Stream，并保留 resolved history。
- `TaskEditMode=task_scoped` 时，用户输入不应触发全局 Task Tree 重新生成。

---

## 10. 第一版非目标

- 不决定 HTTP path、RPC method name 或前后端框架。
- 不定义完整数据库 schema。
- 不定义所有 payload 字段和错误码。
- 不定义权限系统和多用户协作。
- 不定义 DAG Task 拓扑。
- 不定义完整 diff viewer。
