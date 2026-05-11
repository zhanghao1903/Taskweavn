# Message Interaction API For UI

> Status: planned
> Last Updated: 2026-05-11
> Scope: Session/Task message interaction components
> Related: [UI API archive](ui-api-interfaces.md), [Session Message Stream](session-message-stream.md), [Task Message View](task-message-view.md), [Task-scoped Chat Flow](task-scoped-chat-flow.md)

---

## 1. 背景

前端第一阶段不应该把完整 TaskBus、Task Tree 编辑和多 Agent 交互一次性接入。要让界面先“活起来”，最小闭环是：

1. 进入一个 Session；
2. 拉取消息；
3. 用户发送消息；
4. Agent / 系统追加消息；
5. UI 收到增量事件；
6. 用户对 actionable message 做确认回复；
7. 回复结果回到同一条消息流。

因此第一批前后端对接重点是 **Session 支持 + Message 支持**。

---

## 2. UI 组件范围

| Component | UI 位置 | 第一版职责 |
|---|---|---|
| `TaskMessagePanel` | 中间主工作区 / 选中 Task 下方 | 展示当前交互上下文的消息流；支持 actionable message；展示 response history。 |
| `MessageComposer` | 底部输入区 | 发送 global 或 task_scoped 用户消息；显示当前输入作用域。 |

### 2.1 Global timeline 首版隐藏

当前 shell 中的 `Global timeline / Session Stream` 右侧区域先隐藏。

原因：

- 首版需要先保证消息交互闭环，而不是同时维护两个消息视图。
- 全局消息流仍是后端事实源，但 UI 第一版只展示“当前交互流”。
- 当用户未选中 Task 时，`TaskMessagePanel` 展示 Session-level messages。
- 当用户选中 Task 时，`TaskMessagePanel` 展示 Task-scoped messages。

后续可以重新引入 Global timeline，作为高级回放/筛选视图。

---

## 3. 后端事实模型映射

后端当前 `AgentMessage.message_type` 只有三类：

```text
informational | actionable | response
```

UI 不应该把它改造成另一套事实类型。建议前端消息模型拆成：

```ts
type BackendMessageType = "informational" | "actionable" | "response"
type MessageAuthorRole = "user" | "agent" | "system"
```

语义：

| Backend message_type | UI 展示 |
|---|---|
| `informational` | 普通消息、进度消息、系统提示 |
| `actionable` | Confirmation card / 需要用户操作的消息 |
| `response` | 用户回复、超时默认回复、自动决策结果 |

`ConfirmationActionView` 第一版不需要独立后端实体。它可以由 `actionable AgentMessage` 投影得到。

---

## 4. Message ViewModel

### 4.1 SessionMessageItem

前端组件使用的最小视图模型：

```ts
type SessionMessageItem = {
  messageId: string
  sessionId: string
  taskId: string | null
  agentId: string
  parentMessageId: string | null
  messageType: "informational" | "actionable" | "response"
  authorRole: "user" | "agent" | "system"
  content: string
  createdAt: string

  actionOptions: string[]
  requiresResponse: boolean
  timeoutSeconds: number | null
  risk: MessageRiskView | null
  relatedActionId: string | null

  responseSource:
    | "user"
    | "timeout_default"
    | "timeout_confident"
    | "timeout_skip"
    | "auto_proceed"
    | null
  responseValue: string | null

  ui: {
    isPendingActionable: boolean
    isResolvedActionable: boolean
    canRespond: boolean
  }
}
```

说明：

- `messageType` 来自后端事实字段。
- `authorRole` 是 UI 展示字段，可由 `agent_id` 和 message context 推导，也可由 API 直接返回。
- `ui.*` 是后端或 API projection 层给前端的便利字段，避免前端重复做 parent/response join。

### 4.2 MessageRiskView

```ts
type MessageRiskView = {
  final: number
  label: "low" | "medium" | "high"
  rationale: string[]
}
```

第一版可以只返回 `label` 和 `rationale` 摘要，后续再补完整 `RiskAssessment`。

---

## 5. 查询接口

### 5.1 当前交互流

前端组件优先使用一个统一查询：

```ts
getInteractionMessages(request: {
  sessionId: string
  taskId?: string | null
  scope?: "session" | "task_direct" | "task_subtree"
  cursor?: string | null
  limit?: number
}): Promise<InteractionMessagePage>
```

返回：

```ts
type InteractionMessagePage = {
  items: SessionMessageItem[]
  nextCursor: string | null
  hasMore: boolean
}
```

语义：

| 参数 | 含义 |
|---|---|
| `scope=session` | 展示 Session-level 当前交互流。 |
| `scope=task_direct` | 只展示当前 Task 直接关联消息。 |
| `scope=task_subtree` | 展示当前 Task 及子树消息，后续扩展。 |

第一版 UI 规则：

- 未选中 Task：`scope=session`。
- 选中 Task：`scope=task_direct`。
- Global timeline 不显示，但此接口仍可返回 session 视图。

### 5.2 Pending actionable

组件也可以独立查询待处理 actionable：

```ts
listPendingActionables(request: {
  sessionId: string
  taskId?: string | null
}): Promise<SessionMessageItem[]>
```

用途：

- Header badge；
- Task card badge；
- 当前消息面板顶部提示；
- 防止 pending actionable 淹没在普通消息里。

---

## 6. 命令接口

### 6.1 发送用户消息

```ts
appendUserMessage(request: {
  sessionId: string
  taskId?: string | null
  content: string
  mode: "global" | "task_scoped"
  clientMessageId?: string
}): Promise<MessageCommandResult>
```

返回：

```ts
type MessageCommandResult = {
  accepted: boolean
  messageId: string
  createdAt: string
  cursor: string
}
```

约束：

- `mode=global` 时 `taskId` 可以为空。
- `mode=task_scoped` 时 `taskId` 必须存在。
- 服务端落库为 `AgentMessage(message_type="informational", agent_id="user")`，或等价投影。
- 成功后必须产生 `message.appended` 事件。

### 6.2 回复 actionable message

```ts
respondToActionable(request: {
  sessionId: string
  messageId: string
  value: string
  note?: string
  clientMessageId?: string
}): Promise<MessageCommandResult>
```

约束：

- `messageId` 必须指向 `message_type="actionable"` 的消息。
- 服务端创建 `message_type="response"` 的消息。
- `parent_message_id` 指向 actionable message。
- `response_source="user"`。
- `response_value=value`。
- 成功后必须产生：
  - `message.appended`
  - 可选 `confirmation.resolved`

### 6.3 重发/失败处理

第一版不做复杂离线队列，但 command 需要可表达失败：

```ts
type MessageCommandError = {
  code:
    | "session_not_found"
    | "task_not_found"
    | "actionable_not_found"
    | "actionable_already_resolved"
    | "validation_error"
    | "internal_error"
  message: string
}
```

UI 行为：

- 发送中显示 pending state；
- 失败时保留输入内容；
- actionable 已被他处 resolved 时，刷新消息流并提示用户。

---

## 7. 实时事件接口

消息交互需要 session 级订阅：

```ts
subscribeInteractionEvents(request: {
  sessionId: string
  cursor?: string | null
}): InteractionEventSubscription
```

事件 envelope：

```ts
type InteractionEvent = {
  eventId: string
  sessionId: string
  taskId?: string | null
  type:
    | "message.appended"
    | "message.updated"
    | "message.response_recorded"
    | "actionable.resolved"
  cursor: string
  createdAt: string
  payload: unknown
}
```

前端收到事件后：

- `message.appended`：追加到当前 message query 或 invalidate query；
- `actionable.resolved`：刷新 pending actionables；
- `message.updated`：用于未来编辑/补充摘要；
- reconnect 时用 cursor 补漏。

第一版如果后端没有实时接口，可以先用轮询：

```text
GET getInteractionMessages(cursor=lastCursor)
```

但 API contract 仍保留 subscribe 语义，避免未来再改组件边界。

---

## 8. 组件状态机

### 8.1 TaskMessagePanel

```text
idle
  -> loading
  -> ready
  -> appending_message
  -> resolving_actionable
  -> ready
  -> error
```

关键状态：

| 状态 | UI 行为 |
|---|---|
| `loading` | 面板内 skeleton 或 loading row |
| `ready` | 展示消息列表 |
| `appending_message` | 用户刚发送的消息可 optimistic 显示 |
| `resolving_actionable` | 被点击的 action option 禁用 |
| `error` | 显示 retry / refresh |

### 8.2 MessageComposer

```text
empty
  -> editing
  -> submitting
  -> empty
  -> failed
```

规则：

- `global` 模式 placeholder 说明“影响整个 Session”。
- `task_scoped` 模式 placeholder 说明“只补充当前 Task”。
- 没有选中 Task 时，不能进入 `task_scoped`。
- 提交失败后保留输入内容。

---

## 9. UI 对接优先级

建议前后端对接分三步：

1. **HTTP Snapshot**
   - `getInteractionMessages`
   - `appendUserMessage`
   - `respondToActionable`
   - 手动刷新或 query invalidation
2. **Pending Actionable**
   - `listPendingActionables`
   - Task card / Header badge
   - actionable resolved 状态
3. **Realtime**
   - `subscribeInteractionEvents`
   - cursor resume
   - replace polling

---

## 10. 验收标准

- Global timeline 首版隐藏，但用户仍能看到当前交互消息流。
- 未选中 Task 时，消息面板展示 Session-level interaction messages。
- 选中 Task 时，消息面板展示 Task-scoped messages。
- 用户发送 global message 后，消息进入同一条 stream。
- 用户发送 task_scoped message 后，消息带 `taskId`。
- actionable message 展示为确认卡。
- 用户点击选项后，产生 response message，并且 actionable 变为 resolved。
- 页面刷新后，历史消息和 response history 仍可回放。

