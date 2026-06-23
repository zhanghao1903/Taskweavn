# UI And Backend Communication

> Status: active architecture boundary
> Last Updated: 2026-06-24
> Related: [Plato Frontend Technical Design](../product/plato-frontend-technical-design.md), [Figma UI Baseline](../product/plato-figma-ui-baseline.md), [UI API Interfaces](../plans/ui/ui-api-interfaces.md), [Task Domain/UI Model Separation](task-domain-ui-model-separation.md), [Authoring Domain](authoring-domain.md), [TaskBus](bus.md)
>
> Product 1.1 alignment: This boundary now includes Router-first Main Page input, durable Conversation / Activity replay, read-only inquiry, command-backed ASK/confirmation/guidance/execution handoff, workspace inspection routes, token usage projection, Audit/Diagnostics linkage, and local sidecar settings-backed runtime.

---

## 1. Purpose

TaskWeavn 的 UI 不是传统聊天窗口，也不是文件浏览器。当前产品入口是
Session；Task 仍是执行状态权威，Plan / Direct Task 是 Session 内的 active
work 投影：

- 用户输入自然语言。
- Runtime Input Router 将输入解释为 read-only answer、ASK/confirmation
  resolution、guidance、Direct Task、Plan-required work、stop/retry 等命令。
- 系统将 task-like 输入转成 RawTask / DraftTaskTree / Plan / PublishedTask。
- UI 展示 Session conversation、active Plan / TaskNode、ASK、确认动作、
  Activity、文件变更、结果摘要和 Audit 入口。
- 用户可以在 Session 级对话，也可以选中 Task 后进行 task-scoped 输入。

这意味着 UI 与后端之间需要一套稳定通信契约，而不是临时暴露内部 service 或 SQLite 结构。

本文定义 UI 和后端的通信边界：

- 查询如何拿 ViewModel；
- 命令如何提交用户意图；
- 实时事件如何推送；
- UI 如何处理命令 accepted 与最终状态之间的延迟；
- 后端 transport 层如何包住现有 server-core service。

本文不规定具体前端框架，也不要求第一版必须实现完整 HTTP server。它定义的是长期接口方向。

当前前端实现路线已经重新锚定到 Figma UI baseline 1.0。本文只定义 UI/backend 通信边界；具体前端技术栈、目录结构、状态库和 Story 实施切片见 [Plato Frontend Technical Design](../product/plato-frontend-technical-design.md)。

---

## 2. Design Principles

### 2.1 Query / Command / Event 三分

UI 通信分成三类：

| 类型 | 方向 | 语义 |
|---|---|---|
| Query | UI -> Backend | 获取当前投影视图或 snapshot，例如 MainPageSnapshot / TaskDetailView。 |
| Command | UI -> Backend | 提交用户意图，例如 runtime input、生成 Task Tree、更新 Task Node、ASK/确认动作。 |
| Event | Backend -> UI | 通知事实变化，例如消息追加、Task 状态变化、ASK/确认创建或解决。 |

不要把三者混成一个接口。查询不改变状态；命令不承诺直接返回完整最新视图；事件只通知变化，不替代查询。

### 2.2 API 返回 ViewModel，不返回裸领域对象

UI 不应该直接消费：

- `TaskDomain`
- `DraftTaskNode`
- `RawTask`
- SQLite row
- MessageStream 原始存储结构

UI 应消费稳定投影：

- `MainPageSnapshot`
- `TaskTreeView`
- `TaskCardView`
- `TaskDetailView`
- `PlanView`
- `SessionMessageView`
- `SessionActivityItemView`
- `AskRequestView`
- `AskListResult`
- `ConfirmationActionView`
- `TaskInteractionTimeline`
- `CommandResult`

领域对象可以演化，UI ViewModel 应尽量稳定。

### 2.3 Session 是通信主边界

第一版所有 UI 通信都以 `session_id` 为主边界。

Task 是 Session 内的投影视角，而不是独立连接边界：

```text
Session
  ├── Conversation / Session Message Stream
  ├── Active Plan / Task Tree View
  ├── Task Detail View
  ├── Task-scoped Message View
  ├── Pending ASK / Active ASK
  ├── Pending Confirmations
  ├── Activity
  └── File / Result / Audit Projections
```

Task Message View 不是第二条物理消息流。它仍然来自唯一 Session Message Stream，只是按 `TaskRef` / `task_id` 聚合过滤。

### 2.3.1 Project, Session, And Workspace Root

产品 UI 会展示：

```text
Project
  -> Workflow
      -> Session
          -> active work / conversation / task projections
```

后端通信的事实边界仍以 Session 为主，但文件写入边界是当前打开的
workspace root，而不是一个自动 fork 的 per-session workspace。

- `Project` 是用户组织工作的容器，可用于导航、归档和跨 Session 结果沉淀。
- `Session` 是对话、active work、TaskBus 状态、ASK、Activity、Audit 和 context
  trace 的隔离边界。
- 当前实现让 Agent 在 selected workspace root 中读写文件。`.plato` 下的
  stores 和 `session_id` 隔离 session metadata；用户文件默认共享。
- UI 不应展示 `Session workspace: isolated` 这类暗示文件 fork 的提示。
- 跨 Session 文件冲突、显式 fork、导出、沉淀到 Project baseline 都属于后续
  command / workflow 设计，不是 Product 1.0 默认通信事实。

### 2.4 Command accepted 不等于最终状态

命令返回 `accepted` 只表示后端接收并开始处理，不能表示 UI 本地状态已经是真实状态。

推荐流程：

```text
UI submits command
  -> backend returns CommandResult(status="accepted")
  -> backend emits events as facts change
  -> UI patches affected views or re-queries ViewModel
```

这可以避免 UI 依赖脆弱的 optimistic truth。

### 2.5 第一版优先 HTTP + SSE

第一版建议：

- Query / Command：HTTP JSON 或同构 RPC over HTTP；
- Event：SSE；
- WebSocket：保留为后续升级。

原因：

- HTTP 查询/命令容易测试、缓存、重放和调试；
- SSE 足够覆盖后端到 UI 的 session event stream；
- WebSocket 双向协议复杂度更高，第一版没有必要为了“看起来实时”提前引入。

如果以后需要高频双向协作、多人同时编辑、浏览器端 agent worker，再升级到 WebSocket。

---

## 3. Layering

推荐后端 transport 分层：

```text
Browser UI
  |
  | HTTP Query / HTTP Command / SSE Events
  v
Transport Adapter
  |
  v
UI Application Gateway
  |
  +--> Query Services
  |      - TaskProjectionService
  |      - TaskInteractionTimelineService
  |      - MessageView adapter
  |
  +--> Command Services
  |      - CollaboratorApiAdapter
  |      - TaskCommandService
  |      - TaskPublishService
  |
  +--> Event Publisher
         - MessageStream
         - TaskBus events
         - Authoring events
         - File/Summary update events
```

### 3.1 Transport Adapter

Transport Adapter 负责协议细节：

- HTTP path / method；
- JSON encode/decode；
- auth/session headers；
- request id；
- error response；
- SSE framing；
- disconnect/reconnect。

它不应该直接操作 `TaskDomain`、`DraftTaskStore`、`TaskBus`。

### 3.2 UI Application Gateway

UI Application Gateway 是真正的 UI 后端边界。

它负责：

- 将 HTTP/RPC 请求映射到 server-core service；
- 统一返回 ViewModel；
- 统一生成 `CommandResult`；
- 统一处理版本、cursor、idempotency；
- 隐藏内部 store 和 service 组合。

第一版可以是一个薄对象，不一定要拆成复杂模块。

---

## 4. Query Contract

查询接口返回当前投影视图。

### 4.1 Query Envelope

第一版可以直接使用普通 HTTP query/body。长期建议所有查询至少具备：

```python
class QueryRequest(BaseModel):
    request_id: str
    session_id: str
    cursor: str | None = None
    limit: int | None = None
    filters: dict[str, object] = {}
```

响应：

```python
class QueryResponse[T](BaseModel):
    request_id: str
    ok: bool
    data: T | None
    error: ApiError | None = None
    cursor: str | None = None
    generated_at: datetime
```

字段细节后续可以收紧；重要的是 response envelope 要稳定。

### 4.2 Required Queries

| API 语义 | 返回 | 来源 |
|---|---|---|
| `getSessionSnapshot(session_id)` | `MainPageSnapshot` | SessionManager + MessageStream + PlanStore + TaskStore + AskStore projection |
| `getSessionOverview(session_id)` | `SessionOverview` | SessionManager + MessageStream + TaskStore projection |
| `listTaskTrees(session_id, filters)` | `TaskTreeView` | TaskProjectionService / PlanProjectionService |
| `getTaskCard(session_id, task_ref)` | `TaskCardView` | TaskProjectionService |
| `getTaskDetail(session_id, task_ref, message_limit)` | `TaskDetailView` | TaskProjectionService + MessageView adapter |
| `getTaskTimeline(session_id, task_ref, filters)` | `TaskInteractionTimeline` | TaskInteractionTimelineService |
| `getTaskSnapshot(session_id, task_ref)` | `TaskInteractionSnapshot` | Detail + timeline |
| `listSessionMessages(session_id, filters)` | `list[SessionMessageView]` | MessageStream adapter |
| `listSessionActivity(session_id, filters)` | `list[SessionActivityItemView]` | Session activity projection |
| `listTaskMessages(session_id, task_ref, scope)` | `list[SessionMessageView]` | MessageStream filtered view |
| `listAsks(session_id, filters)` | `AskListResult` | AskStore projection |
| `getAsk(session_id, ask_id)` | `AskRequestView` | AskStore projection |
| `listPendingConfirmations(session_id, filters)` | `list[ConfirmationActionView]` | MessageStream pending actionable query |
| `getTaskFileChanges(session_id, task_ref, recursive)` | `list[TaskFileChangeSummary]` | FileChangeStore projection |
| `getTaskSummary(session_id, task_ref)` | `TaskSummaryView | None` | TaskSummaryStore projection |

### 4.3 Query Consistency

查询返回的是某个时间点的投影，不保证和正在传输的 event 完全同步。

因此每个响应应携带：

- `generated_at`
- 可选 `cursor`
- 可选 `version` 或 `revision`

UI 可以用它判断：

- 是否需要重新拉取；
- SSE 重连后从哪个 cursor 继续；
- 本地视图是否被较新的事件覆盖。

---

## 5. Command Contract

命令接口表达用户意图。

### 5.1 Command Envelope

```python
class CommandRequest(BaseModel):
    command_id: str
    session_id: str
    idempotency_key: str | None = None
    expected_version: int | None = None
    payload: dict[str, object]
```

统一返回现有 `CommandResult` 语义：

```python
class ObjectRef(BaseModel):
    kind: Literal[
        "raw_task",
        "raw_task_ask",
        "plan",
        "draft_task",
        "draft_tree",
        "draft_subtree",
        "published_task",
        "message",
        "command",
    ]
    id: str

class AffectedObjectRef(BaseModel):
    ref: ObjectRef
    impact: Literal[
        "changed",
        "created",
        "deleted",
        "may_need_update",
        "needs_review",
        "invalidated",
        "replaced",
        "superseded",
    ]
    reason: str | None = None

class CommandResult(BaseModel):
    command_id: str
    status: Literal["accepted", "rejected"]
    message: str
    affected_task_refs: tuple[TaskRef, ...]
    object_refs: tuple[ObjectRef, ...]
    affected_objects: tuple[AffectedObjectRef, ...]
    emitted_message_ids: tuple[str, ...]
    published_task_ids: tuple[str, ...]
    debug_refs: dict[str, str]
```

`affected_task_refs` 只表达真实 draft/published Task。RawTask、RawTaskAsk、draft tree、draft subtree 等 authoring-only/system objects 通过 `ObjectRef` / `AffectedObjectRef` 表达，避免把 RawTask 伪装成 Task，也避免自由 metadata 变成隐式协议。

扩展建议：

```python
class CommandResponse(BaseModel):
    request_id: str
    result: CommandResult
    refresh: RefreshHint
```

`RefreshHint` 告诉 UI accepted 后应该等事件还是主动重查：

```python
class AffectedScope(BaseModel):
    kind: Literal[
        "session",
        "task_tree",
        "task_subtree",
        "task_detail",
        "messages",
        "confirmations",
    ]
    task_ref: TaskRef | None = None
    reason: str | None = None

class RefreshHint(BaseModel):
    wait_for_events: bool = True
    suggested_queries: tuple[str, ...] = ()
    affected_task_refs: tuple[TaskRef, ...] = ()
    affected_scopes: tuple[AffectedScope, ...] = ()
```

`affected_scopes` 是 UI invalidation 的粗粒度边界。父节点语义变化导致子树重建时，command response 应返回 `AffectedScope(kind="task_subtree", task_ref=parent_ref)`，UI 重查 subtree/detail，而不是依赖局部 optimistic patch。

### 5.2 Required Commands

| API 语义 | 作用 | 后端边界 |
|---|---|---|
| `appendSessionMessage` | 全局自然语言输入 | `CollaboratorApiAdapter.append_session_message` |
| `routeRuntimeInput` | 主输入入口：ASK/confirmation/read-only/guidance/Direct Task/Plan-required/stop/retry 分类 | `RuntimeInputRouter` + query/command gateways |
| `generateTaskTree` | 从 ready RawTask 或特定工作流生成 draft Task Tree | `CollaboratorApiAdapter.generate_task_tree` |
| `appendTaskMessage` | 选中 Task 后补充信息 | draft: Collaborator authoring; published: TaskCommandService |
| `updateTaskNode` | 修改 draft/pending Task | TaskCommandService / AuthoringCommandService |
| `answerRawTaskAsk` | 回答可行性/澄清问题 | CollaboratorApiAdapter |
| `answerAuthoringAskBatch` | 批量回答 authoring ASK | CollaboratorApiAdapter + AuthoringCommandService |
| `answerAsk` | 回答 execution ASK | AskStore first, then TaskBus resume_after_user + optional dispatch |
| `deferAsk` | 暂缓 execution ASK | AskStore first, then TaskBus fail policy |
| `cancelAsk` | 取消 execution ASK | AskStore first, then TaskBus fail policy |
| `resolveConfirmation` | 处理确认动作 | TaskCommandService + MessageStream |
| `publishTaskTree` | 发布 draft tree 到 TaskBus | CollaboratorApiAdapter + TaskPublisher |
| `assignTask` | Routing Agent 分配 pending Task 给 Execution Agent | Routing Agent + TaskBus assignment command |
| `requestTaskInterrupt` | 用户或系统请求停止 Task | TaskCommandService + TaskBus interrupt intent |
| `cancelTask` | 取消 draft/pending Task | draft: AuthoringCommandService; pending: TaskBus terminal update |
| `retryTask` | failed Task 原地回到 pending | TaskCommandService + TaskBus lifecycle retry |
| `dispatchExecution` | 推进 fixed-route execution loop | FixedRouteTaskExecutor / dispatcher |
| `startTaskExecution` | 领取已分配 Task 并进入 running | TaskBus claim_assigned + Execution Agent runtime |

### 5.3 Command Rules

- 命令必须有 `command_id`。
- 会产生写入的命令应支持 `idempotency_key`。
- 修改已有对象的命令应支持 `expected_version`。
- rejected 命令也应该产生可调试的错误信息，但不一定进入用户消息流。
- `updateTaskNode` 需要保留 `update_mode` 语义：`node_fields` 只改当前节点，`replace_children` / `replace_subtree` 允许后端重建受影响的子节点并通过 `AffectedScope` 通知 UI 重查。
- Main Page 自然语言主入口走 `appendSessionMessage` / `appendSessionInput(mode="generate_task_tree")`，不直接调用 `generateTaskTree(prompt)`；独立 generate endpoint 保留给未来特定工作流、高级入口或 ready RawTask continue。
- accepted 命令如果创建消息、确认、Task，应返回相关 id，方便 UI 关联 loading 状态。
- 命令处理不应要求 UI 了解内部 store 顺序。

---

## 6. Event Contract

事件是 UI 实时性的核心。

### 6.1 Event Transport

第一版推荐 SSE：

```text
GET /sessions/{session_id}/events?cursor=...
Accept: text/event-stream
```

SSE event frame：

```text
id: <cursor>
event: task.node.changed
data: {"session_id":"...","task_ref":{...},"reason":"status_changed"}
```

SSE 断线后，UI 使用最后一个 event id 作为 cursor 重连。

Product 1.0 sidecar 已有 session-scoped `UiEventStore`。后端应 replay
retained events after cursor when possible；如果无法 replay cursor 之后的
事件，必须返回/发送 `session.resync_required`，让 UI 重新查询 snapshot。

### 6.2 Event Envelope

```python
class UiEvent(BaseModel):
    event_id: str
    session_id: str
    event_type: str
    cursor: str
    task_refs: tuple[TaskRef, ...] = ()
    message_ids: tuple[str, ...] = ()
    command_id: str | None = None
    payload: dict[str, object] = {}
    created_at: datetime
```

`payload` 第一版可以保持轻量，只放 patch hint，不放完整 ViewModel。

原因：

- 完整 ViewModel 可能很大；
- 投影逻辑集中在 Query；
- event 只负责告诉 UI “什么变了，该刷新哪里”。

### 6.3 Required Event Types

| Event Type | 触发 | UI 建议动作 |
|---|---|---|
| `session.status_changed` | session 派生状态变化 | 刷新 SessionOverview / Session header |
| `session.resync_required` | cursor 过期或无法 replay | 重新查询 `MainPageSnapshot` |
| `task.tree.changed` | Task 拓扑变化、新增/删除/发布 | 刷新 TaskTreeView |
| `task.node.changed` | 单个 Task 状态、badge、权限、intent 或约束变化 | 刷新 TaskNodeCard / Task detail |
| `message.appended` | Session Message Stream 新消息 | 追加或重查 messages |
| `confirmation.created` | 新确认动作 | 显示确认 UI，更新 pending count |
| `confirmation.resolved` | 确认完成 | 刷新对应消息和 Task card |
| `file_changes.updated` | 文件变更摘要更新 | 刷新 Task 文件区域 |
| `result.updated` | 结果卡片或任务结果摘要更新 | 刷新 result cards / Task summary |
| `audit.summary_updated` | 审计摘要更新 | 刷新 Audit / trust projection |
| `command.completed` | 长命令完成 | 清理 UI pending state |
| `command.failed` | 长命令失败 | 显示错误并建议重查 |

### 6.4 Replay-Then-Attach

UI 初始化时不要只订阅事件。

推荐流程：

```text
1. Query getSessionOverview
2. Query listTaskTrees
3. Query listSessionMessages(limit=N)
4. Start SSE from returned cursor
5. On event, patch or re-query affected ViewModel
```

SSE 重连：

```text
1. Browser reconnects with last cursor
2. Backend replays retained events after cursor if available
3. If cursor expired, backend sends resync_required
4. UI re-runs snapshot queries
```

### 6.5 Cursor Expiry

如果 event cursor 已过期，后端返回：

```python
UiEvent(
    event_type="session.resync_required",
    payload={"reason": "cursor_expired"},
)
```

UI 应重新 query snapshot，不要尝试本地修复。

---

## 7. UI State Machine

### 7.1 Session Load Lifecycle

```text
idle
  -> loading_snapshot
  -> connecting_events
  -> ready
  -> reconnecting
  -> ready
  -> resyncing
  -> ready
```

### 7.2 Command Lifecycle

```text
draft input
  -> submitting command
  -> accepted
  -> waiting for event/query refresh
  -> reflected in ViewModel
```

Rejected path：

```text
submitting command
  -> rejected
  -> show error / keep local draft
```

### 7.3 Task Selection Lifecycle

```text
no selection
  -> select TaskRef
  -> query TaskDetailView
  -> subscribe via session events
  -> event affects selected Task
  -> refresh detail/card/timeline
```

Task selection remains local UI state. Backend does not need to persist selected/expanded/focused state.

---

## 8. Error Model

### 8.1 API Error

```python
class ApiError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, object] = {}
```

Recommended codes:

| Code | Meaning |
|---|---|
| `bad_request` | 请求结构错误 |
| `not_found` | Session / Task / Message 不存在 |
| `version_conflict` | `expected_version` 不匹配 |
| `command_rejected` | 命令语义被拒绝 |
| `permission_denied` | 权限不足 |
| `backend_busy` | 后端忙，可重试 |
| `internal_error` | 未预期错误 |
| `resync_required` | UI 状态需要重查 |

### 8.2 Error Visibility

不是所有错误都应该进入 Session Message Stream。

| 错误类型 | 用户可见消息流 | UI toast/form error | 日志 |
|---|---:|---:|---:|
| 表单校验错误 | No | Yes | Optional |
| version conflict | No | Yes | Yes |
| command rejected due to state | Optional | Yes | Yes |
| LLM/agent 失败 | Yes, if affects task | Yes | Yes |
| internal transport error | No | Yes | Yes |

---

## 9. Idempotency And Versions

### 9.1 Idempotency

以下命令应支持 idempotency：

- publish Task Tree；
- API publish custom tree；
- scheduler publish；
- retry Task；
- potentially expensive collaborator generation。

UI 可以为一次用户点击生成稳定 idempotency key，避免刷新/重试造成重复 Task。

### 9.2 Version Checks

以下命令应带 `expected_version`：

- update draft Task node；
- append structured guidance to draft Task；
- mark draft tree accepted/published；
- update pending published Task。

如果版本冲突，后端返回 `version_conflict`，UI 重查 Task detail 并提示用户重新确认。

---

## 10. Mapping To Existing Server-Core

| Communication Need | Existing / Planned Backend |
|---|---|
| Main Page snapshot | `DefaultUiQueryGateway.get_session_snapshot`, PlanStore, TaskStore, AskStore, MessageStream adapters |
| Query Task cards/details | `TaskProjectionService`, `PlanProjectionService`, `TaskStore`, `DraftTaskStore`, Message adapter |
| Query timeline | `TaskInteractionTimelineService` |
| Generate/edit draft tree | `CollaboratorApiAdapter`, `AuthoringCommandService` |
| Publish draft/custom tree | `TaskPublisher`, `TaskPublishService`, `TaskBus` |
| Scheduled/API publish | `SchedulerPublisher`, `DefaultApiTaskPublisher` |
| Message stream, ASK, and confirmations | `MessageStream`, `AskStore`, `TaskAskCommandService`, `InProcessMessageBus`, `WaitCoordinator` |
| Assignment and execution status | Product 1.0 fixed-route dispatch + TaskBus claim/complete/fail/wait/retry/interrupt lifecycle; Product 1.1+ Routing Agent assignment commands |
| Interruption | TaskBus interrupt intent + Agent/runtime cooperative safe points |
| Runtime input | `RuntimeInputRouter`, read-only inquiry, command gateway |
| HTTP/SSE transport | `ui_http.py`, `ui_http_routes.py`, `UiEventStore` |
| Logs/diagnostics | Configurable logging and archives |

The UI transport wraps these services; it should not create a second business
layer.

---

## 11. Current Implemented Baseline

The Product 1.0 sidecar baseline now includes:

- Gateway protocol and envelope models under `src/taskweavn/server/ui_contract/`.
- Main Page snapshot query with Session, active Plan, Task tree, messages,
  Activity, pending ASK, confirmations, results, file summaries, and audit
  links.
- HTTP route matching under `/api/v1/sessions/{session_id}/...`.
- Session-scoped `UiEventStore` and SSE replay where retained events are
  available.
- Runtime input routing for ASK/confirmation/read-only/guidance/Direct Task
  handoff/stop/retry.
- Execution ASK query and command endpoints.
- Task retry and cooperative stop commands.
- Snapshot-time recovery hooks for stale stopping and answered-but-not-continued
  ASK cases.

Current concrete route families include:

```text
GET  /api/v1/sessions/{session_id}/snapshot
GET  /api/v1/sessions/{session_id}/activity
POST /api/v1/sessions/{session_id}/runtime-input/route
POST /api/v1/sessions/{session_id}/input
POST /api/v1/sessions/{session_id}/task-tree/generate
POST /api/v1/sessions/{session_id}/task-tree/publish
POST /api/v1/sessions/{session_id}/authoring/raw-tasks/{raw_task_id}/asks/answers
GET  /api/v1/sessions/{session_id}/asks
GET  /api/v1/sessions/{session_id}/asks/{ask_id}
POST /api/v1/sessions/{session_id}/asks/{ask_id}/answer
POST /api/v1/sessions/{session_id}/asks/{ask_id}/defer
POST /api/v1/sessions/{session_id}/asks/{ask_id}/cancel
POST /api/v1/sessions/{session_id}/tasks/{task_id}/retry
POST /api/v1/sessions/{session_id}/tasks/{task_id}/stop
GET  /api/v1/sessions/{session_id}/events
```

The important invariant is preserving Query / Command / Event semantics. Route
paths can evolve only through the UI API contract, tests, and compatibility
notes.

---

## 12. Open Questions

1. 是否需要为 `ObjectRef` 增加 stable URI 格式，还是保持 `{kind, id}`？
2. UI 是否需要 local-first cache；如果需要，cursor/version 设计要更严格。
3. 多用户/多浏览器同时连接同一个 Session 时，是否需要 user identity 和 presence？
4. WebSocket 何时升级：多人协作、浏览器端 agent worker，还是高频日志流？
5. 任务执行日志是否走同一 SSE channel，还是单独 debug/log channel？
6. Plan archive command、Session history query、archived Plan detail projection 的 API 是否单独成组？

---

## 13. Non-Goals For First Version

- 不实现完整多人协作 presence。
- 不要求浏览器直接连接 TaskBus。
- 不把所有 EventStream 事件原样暴露给 UI。
- 不让 UI 直接读 SQLite。
- 不把 Task selection / expanded / focused 等本地 UI 状态写入后端。
- 不在第一版强行实现 WebSocket。

---

## 14. Summary

UI 与后端通信的核心不是“选 REST 还是 WebSocket”，而是把状态变化边界稳定下来：

```text
Query returns ViewModel.
Command submits intent.
Event announces facts changed.
UI refreshes through projection.
```

只要这条边界稳定，后续无论是 FastAPI、SSE、WebSocket，还是桌面本地 UI，都可以复用同一套 server-core 语义。
