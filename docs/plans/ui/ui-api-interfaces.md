# UI API 接口归档

> Status: planned
> Last Updated: 2026-05-11
> 作用：归档 Task-first UI 各分述共同引用的接口需求。第一版只定义接口边界和最低数据能力，字段细节后续补充。

---

## 1. 范围

本文档是 Task-first UI 的公共接口归档。所有 UI 分述文件只声明“依赖哪些接口”和“为什么依赖”，不在各自文档里重复定义接口结构。

第一版目标是框架优先：

- 明确 UI 需要哪些查询接口、命令接口和实时事件。
- 明确同一个接口被哪些 UI 区域复用。
- 明确 Task、Message、Confirmation、File Change 的最小视图模型。
- 暂不决定具体传输方式，可以是 REST、RPC、本地 IPC、WebSocket 或内嵌前端 store。
- 暂不展开完整字段 schema，只保留后续实现必须预留的数据能力。

---

## 2. 设计原则

- **单一事实源**：消息只有一条 Session Message Stream；Task Message View 是按 Task 过滤出的视图。
- **Task-first**：UI 的主要读取、编辑、确认、文件汇总都围绕 `TaskNode`。
- **只读历史**：已完成 Task 和已 resolved 的 Confirmation 不能被原地修改。
- **视图聚合不改归属**：父 Task 的文件变更汇总是递归聚合，直接归属仍属于产生变更的子 Task。
- **命令与查询分离**：查询接口返回视图模型，命令接口表达用户意图并产生事件。
- **Session 级订阅**：实时更新以 Session 为订阅边界，Task 视图通过过滤同一事件源更新。
- **接口名稳定优先**：第一版字段可以粗，但接口边界要尽量稳定，便于后续分会话实现。

---

## 3. 基础类型

| 类型 | 说明 |
|---|---|
| `SessionId` | 会话 ID |
| `TaskId` | Task Node ID |
| `MessageId` | Session Message ID |
| `ConfirmationId` | 确认动作 ID |
| `FileChangeId` | 文件变更记录 ID |
| `TaskStatus` | `draft` / `pending` / `running` / `done` / `failed` / `cancelled` |
| `TaskEditMode` | `global` / `task_scoped` |
| `BackendMessageType` | `informational` / `actionable` / `response` |
| `MessageAuthorRole` | `user` / `agent` / `system` |
| `MessageDisplayKind` | UI projection：普通消息 / 确认卡 / 回复结果 / 系统提示 |
| `TaskMessageScope` | `direct` / `subtree` |
| `Cursor` | 实时事件或分页查询游标 |

状态说明：

- `draft` 表示 Task Tree 还处于用户确认前的计划草案。
- `pending` 表示 Task 已进入可执行计划，但尚未开始。
- `running` 表示 Task 正在执行。
- `done` / `failed` 是执行终态。
- `cancelled` 表示用户取消了未开始任务；运行中取消的语义后续单独设计。

---

## 4. 视图模型草案

字段细节后续补充。当前只定义每个模型必须能承载的信息类别。

| 模型 | 最低数据能力 |
|---|---|
| `SessionOverview` | Session 标识、名称、整体状态、当前选中/运行 Task、root Task 摘要、未处理确认数量 |
| `TaskNodeSummary` | Task 标识、父子关系、标题/intent 摘要、状态、badge、排序信息 |
| `TaskNodeDetail` | Summary + 完整 intent、约束、权限、确认摘要、文件摘要、结果摘要 |
| `SessionMessageView` | 消息 ID、Session、可选 Task、后端消息类型、作者角色、内容摘要、时间、关联确认/文件/动作 |
| `ConfirmationActionView` | Confirmation ID、所属 Task、说明、风险/原因、选项、默认行为、状态 |
| `TaskFileChangeSummary` | direct owner task、path、change type、summary、是否来自子树汇总 |
| `TaskSummaryView` | 结果摘要、失败原因、后续建议、产物引用 |

---

## 5. 查询接口

| 接口 | 最低能力 |
|---|---|
| `getSessionOverview(session_id)` | 返回 Session 基本信息、root Task 列表摘要、当前运行状态 |
| `listTaskTrees(session_id)` | 返回一个 Session 下的 root Task Tree 列表 |
| `getTaskNode(session_id, task_id)` | 返回单个 Task Node 的详情、父子关系和状态 |
| `listSessionMessages(session_id, filters)` | 返回唯一 Session Message Stream，可按时间、类型、Task、确认状态过滤 |
| `listTaskMessages(session_id, task_id, scope)` | `listSessionMessages` 的 Task 过滤便捷视图；`scope=direct/subtree` |
| `getInteractionMessages(session_id, task_id?, scope?, cursor?)` | 当前消息交互组件使用的统一消息查询；未选 Task 时返回 session 交互流，选中 Task 时返回 task 交互流 |
| `listPendingConfirmations(session_id, filters)` | 返回待用户处理的确认动作，可按 Task 过滤 |
| `listPendingActionables(session_id, task_id?)` | 返回待用户处理的 actionable messages；第一版可替代独立 confirmation 查询 |
| `getTaskFileChanges(session_id, task_id, recursive)` | 返回 Task 文件变更；`recursive=true` 时包含所有子孙 Task |
| `getTaskSummary(session_id, task_id)` | 返回 Task 结果摘要、失败原因、后续建议 |

### 5.1 查询约定

- 列表查询默认按时间升序或拓扑顺序返回，具体排序必须在接口文档中显式声明。
- 消息类列表必须支持 cursor，以便 Session Message Stream 可以增量加载。
- Task Tree 查询必须返回足够的父子关系数据，前端不应靠 title 或顺序推断结构。
- `listTaskMessages` 不是新存储，只是 `listSessionMessages` 的 Task 过滤视图。
- `getInteractionMessages` 是 UI 便捷接口；它不代表第二套存储，只是为当前消息组件统一 session/task 两种作用域。
- 父 Task 查看文件时，使用 `getTaskFileChanges(..., recursive=true)`；子 Task 直接归属不变。

---

## 6. 命令接口

| 接口 | 最低能力 |
|---|---|
| `generateTaskTree(session_id, prompt, context)` | 从自然语言生成 Task Tree List 草案 |
| `acceptTaskTree(session_id, root_task_ids)` | 将 Task Tree 草案转入可执行计划 |
| `updateTaskNode(session_id, task_id, patch)` | 修改未开始 Task 的 intent、约束、状态或结构 |
| `appendTaskMessage(session_id, task_id, content, mode)` | 给某个 Task 追加用户补充信息 |
| `appendSessionMessage(session_id, content, mode)` | 给整个 Session 追加全局用户输入 |
| `appendUserMessage(session_id, task_id?, content, mode)` | 当前 MessageComposer 使用的统一发送接口；`global` 不要求 task_id，`task_scoped` 必须有 task_id |
| `resolveConfirmation(session_id, confirmation_id, value, note)` | 处理确认动作，写回消息流 |
| `respondToActionable(session_id, message_id, value, note?)` | 直接回复 actionable message；创建 response message 并写回同一条消息流 |
| `startTaskExecution(session_id, task_id)` | 从某个 Task 或 root Task 开始执行 |
| `cancelTask(session_id, task_id, reason)` | 取消未开始 Task；运行中取消语义后续细化 |
| `retryTask(session_id, task_id, instruction)` | 基于 failed Task 创建 retry/fix Task |

### 6.1 命令约定

- 命令接口应返回被影响的对象摘要，或返回可用于订阅事件追踪的 command id。
- 命令成功后必须产生可订阅事件，前端以事件刷新 UI，而不是只信任本地 optimistic state。
- `updateTaskNode` 只能修改 `draft` / `pending` Task；`running` Task 的用户补充走 `appendTaskMessage`。
- `resolveConfirmation` 必须写入 Session Message Stream，并保留 resolved history。
- 第一版确认动作可以不建独立后端对象，直接由 `message_type=actionable` 的 `AgentMessage` 投影为 confirmation card；用户选择选项后通过 `respondToActionable` 写入 `message_type=response`。
- `TaskEditMode=task_scoped` 时，用户输入不应触发全局 Task Tree 重新生成。

---

## 7. 实时事件接口

UI 需要订阅 Session 级事件流：

```text
subscribeSessionEvents(session_id, cursor?)
```

最低事件类型：

| 事件 | 用途 |
|---|---|
| `task.created` | 新 Task 出现，更新 Task Tree |
| `task.updated` | intent / constraints / structure 变化 |
| `task.status_changed` | 更新节点状态和 badge |
| `message.appended` | 更新 Session Stream 和 Task Message View |
| `message.response_recorded` | actionable message 得到 response |
| `actionable.resolved` | actionable message 不再等待用户 |
| `confirmation.created` | 新增待确认动作 |
| `confirmation.resolved` | 确认动作完成 |
| `file_change.recorded` | 更新 Task 文件变更摘要 |
| `task.summary_updated` | 更新 Task Summary |

事件 envelope 第一版只要求具备：

- `event_id`
- `session_id`
- `task_id?`
- `type`
- `created_at`
- `payload`
- `cursor`

---

## 8. 子文档接口依赖矩阵

| 子文档 | 主要接口 |
|---|---|
| `information-architecture.md` | `getSessionOverview`、`listTaskTrees`、`listSessionMessages`、`listPendingConfirmations`、`subscribeSessionEvents` |
| `task-generation-flow.md` | `generateTaskTree`、`acceptTaskTree`、`updateTaskNode`、`listTaskTrees`、`startTaskExecution` |
| `task-tree-view.md` | `listTaskTrees`、`getTaskNode`、`listPendingConfirmations`、`getTaskFileChanges`、`subscribeSessionEvents` |
| `task-node-detail.md` | `getTaskNode`、`updateTaskNode`、`appendTaskMessage`、`listTaskMessages`、`listPendingConfirmations`、`getTaskFileChanges`、`getTaskSummary`、`retryTask` |
| `task-message-view.md` | `listTaskMessages`、`listSessionMessages`、`appendTaskMessage`、`resolveConfirmation`、`subscribeSessionEvents` |
| `session-message-stream.md` | `listSessionMessages`、`appendSessionMessage`、`subscribeSessionEvents` |
| `message-interaction-api.md` | `getInteractionMessages`、`appendUserMessage`、`respondToActionable`、`listPendingActionables`、`subscribeInteractionEvents` |
| `confirmation-actions.md` | `listPendingConfirmations`、`resolveConfirmation`、`listTaskMessages`、`listSessionMessages`、`subscribeSessionEvents` |
| `task-editing-rules.md` | `updateTaskNode`、`appendTaskMessage`、`cancelTask`、`retryTask`、`getTaskNode` |
| `file-change-summary.md` | `getTaskFileChanges`、`subscribeSessionEvents` |
| `task-scoped-chat-flow.md` | `appendTaskMessage`、`listTaskMessages`、`getTaskNode`、`updateTaskNode` |

---

## 9. 关键跨文档约定

- `listTaskMessages` 不代表第二套存储，只是 `listSessionMessages(..., task_id=...)` 的语义别名。
- Global timeline 第一版隐藏；当前可见消息组件使用 `getInteractionMessages`，但底层仍然来自唯一 Session Message Stream。
- `getTaskFileChanges(..., recursive=true)` 用于父节点汇总；`recursive=false` 用于直接归属。
- `updateTaskNode` 只能修改未开始 Task；运行中 Task 使用 `appendTaskMessage` 补充信息。
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
