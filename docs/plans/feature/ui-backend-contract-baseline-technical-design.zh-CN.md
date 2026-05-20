# UI/backend Contract Baseline：中文详细技术方案

> Status: in_progress
> Type: 后端主线 / UI contract technical design
> Last Updated: 2026-05-20
> Parent Plan: [UI/backend Contract Baseline](ui-backend-contract-baseline.md)
> Related Architecture: [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md), [Authoring Domain](../../architecture/authoring-domain.md), [Interaction Layer](../../architecture/interaction-layer.md)
> Related Product: [Plato UI API Contract](../../product/plato-ui-api-contract.md)

---

## 1. 设计结论

第一阶段不做 HTTP server，也不接真实前端。先把后端的 UI contract 层独立出来：

```text
server-core domain/projection/services
  -> taskweavn.server.ui_contract
  -> stable JSON contract
  -> future sidecar HTTP/SSE transport
  -> Plato frontend adapter
```

这个 contract 层必须做到：

1. 分离 snapshot/query/command/event/error 五类对象；
2. 后端 Python 模型内部可以用 snake_case，但 JSON 输出必须是 frontend-compatible camelCase；
3. 不暴露裸 `TaskDomain`、`DraftTaskNode`、`AgentMessage`、SQLite row；
4. command accepted 不等于最终事实；
5. event 是 thin patch hint，不携带完整 ViewModel；
6. contract model 可被纯后端测试硬化，不依赖 FastAPI/Starlette/Electron；
7. 后续 sidecar transport 只能包住这层，不重新定义业务语义。

---

## 2. 当前基线

### 2.1 前端已有

`frontend/src/shared/api/types.ts` 已有：

- `ApiError`
- `QueryResponse<T>`
- `CommandRequest<TPayload>`
- `CommandResult`
- `RefreshHint`
- `CommandResponse`
- `MainPageSnapshot`
- `UiEvent`

`frontend/src/shared/api/platoApi.ts` 已有 documented endpoints 的 client adapter。

这说明前端 contract 形状已经基本成型，但它现在是 TypeScript 单边定义。

### 2.2 后端已有

后端已有 server-core 事实和投影：

- `taskweavn.task.models.TaskRef`
- `taskweavn.task.views.TaskTreeView`
- `taskweavn.task.views.TaskCardView`
- `taskweavn.task.views.TaskDetailView`
- `taskweavn.task.projection.DefaultTaskProjectionService`
- `taskweavn.task.commands.CommandResult`
- `taskweavn.task.commands.DefaultTaskCommandService`
- `taskweavn.task.collaborator_api.DefaultCollaboratorApiAdapter`
- `taskweavn.interaction.MessageStream`

但这些不是 UI transport contract。它们服务后端投影和命令语义，字段命名、聚合粒度和 UI `MainPageSnapshot` 不完全一致。

### 2.3 后端缺口

缺少：

- backend Pydantic `MainPageSnapshot`;
- backend Pydantic `QueryResponse` / `CommandResponse` / `ApiError` / `UiEvent`;
- backend contract JSON alias rule；
- UI Query Gateway；
- UI Command Gateway；
- UI Event projection；
- backend-to-frontend fixture parity tests。

---

## 3. 模块结构

推荐新增：

```text
src/taskweavn/server/ui_contract/
  __init__.py
  base.py
  errors.py
  envelopes.py
  view_models.py
  snapshots.py
  commands.py
  refs.py
  events.py
  gateways.py
  mapping.py
```

### 3.1 文件职责

| File | Responsibility |
|---|---|
| `base.py` | frozen/forbid-extra/camelCase base model, datetime serialization helpers. |
| `errors.py` | `ApiError`, `ApiErrorCode`, error factory helpers. |
| `envelopes.py` | `QueryResponse[T]`, `CommandRequest[T]`, `CommandResponse`, `RefreshHint`. |
| `refs.py` | `ObjectRef`, `AffectedObjectRef`, `AffectedScope`，用于非 Task 对象引用和 UI refresh invalidation。 |
| `view_models.py` | transport-facing `ProjectSummary`, `SessionSummary`, `TaskTreeView`, `TaskNodeCardView`, messages, confirmations, file/result/audit views. |
| `snapshots.py` | `MainPageSnapshot` and snapshot-specific helpers. |
| `commands.py` | command payload models: append session/task input, generate task tree, update node, publish, resolve confirmation. |
| `events.py` | `UiEvent`, `UiEventType`, cursor type, event constructors. |
| `gateways.py` | `UiQueryGateway` and `UiCommandGateway` Protocols. |
| `mapping.py` | server-core projection -> UI contract conversion functions. |

第一轮实现可以把文件合并得更少，但 public API 应该按这些职责导出。

### 3.2 与 `taskweavn.task.views` 的边界

`taskweavn.task.views` 保留为 server-core projection/read model，不废弃，也不改成 transport-facing UI contract。

原因：

- 它已经被 `DefaultTaskProjectionService` 和 `TaskInteractionTimelineService` 使用；
- 它包含后端 read-side 需要但前端 contract 不一定需要的字段，例如 `primary_actions`、`progress`、`latest_message`、`readonly_reason`、`from_subtree`；
- 直接把它暴露给 UI 会让 frontend contract 被后端投影细节牵引；
- 直接删除它会让 Query Gateway 变厚，需要重复拼装 TaskStore / DraftStore / MessageStream / FileChangeStore 逻辑。

边界规则：

```text
TaskDomain / DraftTaskNode / MessageStream / FileChangeStore / SummaryStore
  -> taskweavn.task.views                 # server-core read/projection model
  -> taskweavn.server.ui_contract.mapping # pure mapping boundary
  -> taskweavn.server.ui_contract         # transport-facing JSON contract
  -> frontend/src/shared/api/types.ts
```

因此 `mapping.py` 是唯一的 projection -> contract 转换层。Query Gateway 应组合 `TaskProjectionService` 和 mapping functions，不应重新实现字段映射。

---

## 4. Base Model 设计

### 4.1 Frozen contract model

所有 contract models 继承：

```python
class UiContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )
```

规则：

- Python 构造允许 snake_case；
- JSON 输出使用 camelCase；
- unknown fields 直接拒绝；
- model frozen，避免 gateway 中途改写；
- 时间字段序列化为 ISO 8601 string。

### 4.2 CamelCase rule

内部字段：

```python
request_id
generated_at
task_node_ids
affected_task_refs
```

JSON 输出：

```json
{
  "requestId": "...",
  "generatedAt": "...",
  "taskNodeIds": [],
  "affectedTaskRefs": []
}
```

测试必须断言 JSON key，不只断言 Python attribute。

---

## 5. Error Contract

### 5.1 Canonical error codes

第一版后端采用：

```python
ApiErrorCode = Literal[
    "bad_request",
    "not_found",
    "version_conflict",
    "command_rejected",
    "permission_denied",
    "backend_busy",
    "resync_required",
    "internal_error",
]
```

说明：

- `permission_denied` 来自 architecture error model，前后端 contract 需要保持同步；
- 不用 Python exception class 名直接作为 code；
- `internal_error` 给未知异常兜底；
- `resync_required` 同时可作为 query/command error 和 event type 的语义。

### 5.2 ApiError

```python
class ApiError(UiContractModel):
    code: ApiErrorCode
    message: str
    retryable: bool = False
    details: dict[str, object] = Field(default_factory=dict)
```

规则：

- 用户能理解的错误写 `message`；
- 调试细节写 `details`；
- 不把 traceback 放入 `message`；
- internal exceptions 进入日志，不进入普通 UI payload。

### 5.3 Error factory

建议提供：

```python
bad_request(message, **details) -> ApiError
not_found(message, **details) -> ApiError
command_rejected(message, **details) -> ApiError
internal_error(message="Internal error") -> ApiError
```

Gateway 可以统一使用这些 helper。

---

## 6. Envelope Contract

### 6.1 QueryResponse

```python
class QueryResponse[T](UiContractModel):
    request_id: str
    ok: bool
    data: T | None
    error: ApiError | None = None
    cursor: str | None = None
    generated_at: datetime
```

Invariant:

- `ok=True` 时 `data is not None` 且 `error is None`；
- `ok=False` 时 `data is None` 且 `error is not None`；
- `cursor` 是 opaque string，UI 只能保存和回传，不解析。

### 6.2 CommandRequest

```python
class CommandRequest[T](UiContractModel):
    command_id: str
    session_id: str
    idempotency_key: str | None = None
    expected_version: int | None = None
    payload: T
```

规则：

- UI 生成 `command_id`；
- 写入型命令推荐带 `idempotency_key`；
- 编辑型命令推荐带 `expected_version`；
- payload 是 command-specific typed model。

### 6.3 CommandResult 与对象引用

`CommandResult` 是 command 的稳定 ACK surface，不是 Authoring Domain 的 mutation protocol。Authoring Domain 与系统状态交互应通过 `AuthoringCommand` / `AuthoringCommandService` 完成；`CommandResult` 只告诉 UI：命令是否被接受、哪些对象可追踪、哪些视图需要刷新。

第一版不要使用自由 `metadata: dict[str, object]` 承载关键语义。改用强类型引用：

```python
ObjectRefKind = Literal[
    "raw_task",
    "raw_task_ask",
    "draft_task",
    "draft_tree",
    "draft_subtree",
    "published_task",
    "message",
    "command",
]

AffectedObjectImpact = Literal[
    "changed",
    "created",
    "deleted",
    "may_need_update",
    "needs_review",
    "invalidated",
    "replaced",
    "superseded",
]

class ObjectRef(UiContractModel):
    kind: ObjectRefKind
    id: str

class AffectedObjectRef(UiContractModel):
    ref: ObjectRef
    impact: AffectedObjectImpact
    reason: str | None = None

class CommandResult(UiContractModel):
    command_id: str
    status: Literal["accepted", "rejected"]
    message: str
    affected_task_refs: tuple[TaskRef, ...] = ()
    object_refs: tuple[ObjectRef, ...] = ()
    affected_objects: tuple[AffectedObjectRef, ...] = ()
    emitted_message_ids: tuple[str, ...] = ()
    published_task_ids: tuple[str, ...] = ()
    debug_refs: dict[str, str] = Field(default_factory=dict)
```

规则：

- `affected_task_refs` 只承载真实 draft/published Task，不承载 RawTask；
- RawTask / RawTaskAsk / draft tree / draft subtree 用 `ObjectRef`；
- `affected_objects` 表达 command 对对象的影响，例如 `draft_subtree + replaced`、`raw_task_ask + superseded`；
- `debug_refs` 只放可追踪 id，例如 `sourceMessageId`、`authoringBatchId`，不放复杂业务数据；
- 如果 UI 需要完整对象内容，必须按 `RefreshHint` 重查 snapshot/detail，而不是解析 `CommandResult`。

### 6.4 RefreshHint

```python
AffectedScopeKind = Literal[
    "session",
    "task_tree",
    "task_subtree",
    "task_detail",
    "messages",
    "confirmations",
]

class AffectedScope(UiContractModel):
    kind: AffectedScopeKind
    task_ref: TaskRef | None = None
    reason: str | None = None

class RefreshHint(UiContractModel):
    wait_for_events: bool = True
    suggested_queries: tuple[str, ...] = ()
    affected_task_refs: tuple[TaskRef, ...] = ()
    affected_scopes: tuple[AffectedScope, ...] = ()
```

`suggested_queries` 第一版使用稳定字符串：

```text
session.snapshot
session.messages
task.tree
task.detail
task.file_changes
session.result
```

后续可以升级成 enum。

`affected_scopes` 是更粗粒度、更 UI 友好的 invalidation 描述。例如父节点被重写时：

```python
RefreshHint(
    suggested_queries=("task.tree", "task.detail"),
    affected_task_refs=(TaskRef.draft("parent-1"),),
    affected_scopes=(
        AffectedScope(kind="task_subtree", task_ref=TaskRef.draft("parent-1")),
    ),
)
```

### 6.5 CommandResponse

```python
class CommandResponse(UiContractModel):
    request_id: str
    ok: bool
    result: CommandResult | None
    error: ApiError | None
    refresh: RefreshHint
```

Invariant:

- accepted command: `ok=True`, `result.status="accepted"`;
- rejected command: 可以是 `ok=False + ApiError(code="command_rejected")`；
- transport parse error: `ok=False + bad_request`；
- backend exception: `ok=False + internal_error`；
- 无论成功失败都给 `refresh`，失败默认不等待事件。

---

## 7. ViewModel Contract

这一层对齐 frontend `types.ts`，采用 camelCase JSON。

### 7.1 IDs

Python 不需要为每个 ID 建复杂类型；第一版使用 `str` + `Field(min_length=1)`。

保留语义别名：

```python
ProjectId = str
WorkflowId = str
SessionId = str
TaskTreeId = str
TaskNodeId = str
MessageId = str
ConfirmationId = str
ResultId = str
EventCursor = str
```

### 7.2 TaskRef

可以复用 `taskweavn.task.models.TaskRef`，但 contract JSON 必须稳定：

```json
{"kind": "draft", "id": "draft-1"}
```

如果复用 domain model，测试必须确认它的 JSON shape 和 UI contract 一致。

### 7.3 MainPageSnapshot

```python
class MainPageSnapshot(UiContractModel):
    project: ProjectSummary
    workflows: tuple[WorkflowSummary, ...]
    workflow: WorkflowSummary
    sessions: tuple[SessionSummary, ...]
    session: SessionSummary
    task_tree: TaskTreeView | None = None
    messages: tuple[SessionMessageView, ...] = ()
    pending_confirmations: tuple[ConfirmationActionView, ...] = ()
    result: ResultCardView | None = None
    file_change_summary: FileChangeSummaryView | None = None
    audit_links: tuple[AuditLinkView, ...] = ()
    cursor: str | None = None
    generated_at: datetime
```

JSON keys must match:

```text
taskTree
pendingConfirmations
fileChangeSummary
auditLinks
generatedAt
```

### 7.4 TaskNodeCardView

Contract shape follows frontend:

```python
class TaskNodeCardView(UiContractModel):
    id: str
    task_ref: TaskRef | None = None
    parent_id: str | None = None
    title: str
    summary: str
    status: TaskNodeStatus
    depth: int
    order_index: int
    badges: TaskNodeBadges
    permissions: TaskNodePermissions
    version: int
```

Mapping from server-core:

| Server-core projection | UI contract |
|---|---|
| `TaskCardView.task_ref.id` | `id` |
| `TaskCardView.task_ref` | `task_ref` |
| `TaskCardView.parent_ref.id` | `parent_id` |
| `TaskCardView.title` | `title` |
| `TaskCardView.intent_preview` | `summary` |
| `TaskCardView.status` | mapped `status` |
| `TaskCardView.depth` | `depth` |
| `TaskCardView.order_index` | `order_index` |
| `TaskCardView.badges` | badge subset |
| `TaskCardView.permissions` | permission subset |

Status mapping:

| Backend status | UI status |
|---|---|
| `draft` | `draft` |
| `pending` | `queued` |
| `running` | `running` |
| `done` | `done` |
| `failed` | `failed` |
| `cancelled` | `cancelled` |

`waiting_user` is derived from pending confirmation, not directly from current `TaskDomain.status`.

### 7.5 Message and Confirmation

Contract message:

```python
class SessionMessageView(UiContractModel):
    id: str
    session_id: str
    task_node_id: str | None = None
    task_ref: TaskRef | None = None
    kind: MessageKind
    title: str
    body: str
    created_at: datetime
    related_confirmation_id: str | None = None
    related_command_id: str | None = None
```

Mapping:

- `AgentMessage.message_id -> id`
- `AgentMessage.task_id -> task_node_id`
- `AgentMessage.message_type == actionable -> kind=actionable`
- `AgentMessage.message_type == response -> kind=response`
- `AgentMessage.context["title"]` if present else short generated title
- `AgentMessage.content -> body`

Confirmation:

- first version can use actionable message id as `ConfirmationActionView.id`;
- response messages keep `parent_message_id`;
- resolved history must remain queryable through message/timeline later.

---

## 8. Command Payloads

### 8.1 Payload models

```python
class AppendSessionInputPayload(UiContractModel):
    content: str
    mode: Literal["global_guidance", "generate_task_tree"]

class GenerateTaskTreePayload(UiContractModel):
    prompt: str | None = None
    raw_task_id: str | None = None
    context: dict[str, object] = Field(default_factory=dict)

class UpdateTaskNodePayload(UiContractModel):
    title: str | None = None
    summary: str | None = None
    full_intent: str | None = None
    constraints: tuple[str, ...] | None = None
    update_mode: Literal["node_fields", "replace_children", "replace_subtree"] = "node_fields"
    preserve_root_id: bool = True

class AppendTaskInputPayload(UiContractModel):
    content: str
    mode: Literal["guidance", "revision_request", "clarification_answer"]

class PublishTaskTreePayload(UiContractModel):
    task_tree_id: str
    start_immediately: bool = True

class ResolveConfirmationPayload(UiContractModel):
    value: str
    note: str | None = None
```

### 8.2 `generateTaskTree(prompt)` 与 RawTask flow

这里是当前最需要小心的地方。

前端产品语义希望：

```text
用户输入自然语言
  -> 生成 Task Tree
```

后端 authoring domain 实际是：

```text
user message
  -> RawTask
  -> feasibility / ask
  -> ready RawTask
  -> DraftTaskTree
```

因此第一版 Command Gateway 应采用这个规则：

1. `appendSessionInput(mode="generate_task_tree")` 是 UI 默认入口；
2. Gateway 调用 Collaborator authoring flow 创建 RawTask；
3. 如果 RawTask `ready_to_plan`，Gateway 继续触发 TaskTree generation；
4. 如果 RawTask `awaiting_user`，Gateway 返回 accepted，并通过 snapshot/message/confirmation 展示 ask；
5. 如果 RawTask `rejected`，Gateway 返回 rejected 或 accepted-with-message，具体由产品错误可见性决定；
6. `generateTaskTree(rawTaskId=...)` 是显式 regenerate/continue 入口。

`generateTaskTree(prompt)` 不作为 Main Page 主工作流入口。独立 endpoint 可以保留给未来特定工作流，例如结构化导入、测试工具、外部自动化、或“已有 RawTask 显式继续生成”的高级入口。主工作流必须优先把用户自然语言落到 Session Message / RawTask authoring flow 中。

实现注意：

- 当前 `DefaultCollaboratorApiAdapter.append_session_message` 返回的 `CommandResult` 不暴露 `raw_task_id`。
- Gateway 不应该通过“最新 RawTask”这类不稳定推断补齐 id。
- 推荐方案是扩展 command ACK surface：
  - 用 `object_refs` 承载 `raw_task_id`、`raw_task_ask_id`、`draft_tree_id` 等非 Task 引用；
  - 用 `affected_objects` 表达创建、替换、失效、需要复核等影响；
  - 用 `debug_refs` 承载 `sourceMessageId`、`authoringBatchId` 等调试追踪 id。
- 不采用自由 `metadata` 承载关键业务语义；metadata 容易变成隐式协议，前后端也难以测试。

这样可以减少重复查询和不稳定推断。

### 8.3 父节点修改与子树重建

如果用户修改父节点语义，子节点很可能也要跟着变化。对于浅层 Task Tree，LLM 更擅长基于父节点意图重建整棵子树，而不是精确 patch 每个后代节点。

因此 Authoring Domain 的命令语义应预留：

```text
update_node(fields-only)
replace_children(parent_ref, new_children)
replace_subtree(root_ref, new_subtree)
```

规则：

- `replace_subtree` 默认保留 root task id，重建 descendants；
- 被替换的旧子节点在 `affected_objects` 中标记为 `superseded` 或 `replaced`；
- `RefreshHint.affected_scopes` 至少包含 `task_subtree(root_ref)`；
- 已解决的确认动作、用户补充信息、澄清回答等交互事实不应丢弃，应进入 AuthoringContext，供 LLM 重建时读取；
- 未解决的确认动作不能静默消失：要么迁移到新子树，要么标记 superseded 并产生新的确认动作；
- 第一版审计可以弱于正式 Task 执行，但必须可追溯：保留 command id、source message id、authoring batch id 和 affected object refs。

这让 UI 不需要理解精细 patch，只需要按 scope 刷新对应 Task Tree/subtree/detail。

---

## 9. Gateway Protocols

### 9.1 Query Gateway

```python
class UiQueryGateway(Protocol):
    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]: ...
```

Future extension:

```python
def list_session_messages(...)
def get_task_tree(...)
def get_task_detail(...)
def list_pending_confirmations(...)
def get_file_changes(...)
def get_result(...)
```

### 9.2 Query Gateway dependencies

```python
class DefaultUiQueryGateway:
    def __init__(
        self,
        *,
        session_reader: SessionReader,
        task_projection: TaskProjectionService,
        project_provider: ProjectProvider | None = None,
        workflow_provider: WorkflowProvider | None = None,
        audit_link_provider: AuditLinkProvider | None = None,
    ) -> None: ...
```

第一版 Project/Workflow 可以用 static providers：

```text
default project: local
default workflow: task_authoring
```

不要因为 Project/Workflow 还没完整产品化而阻塞 snapshot contract。

第一版实现边界：

- `SessionReader` 只要求 `get(session_id)` 和 `list()`，可由 `SessionManager` 或测试 stub 提供；
- `TaskProjectionService.list_task_tree()` 是 Task snapshot 的主输入；
- messages 和 pending confirmations 第一版从 projected task cards 收集，后续可扩展为完整 Session Message Stream query；
- Project/Workflow 使用静态 provider，避免提前产品化导航系统；
- Gateway 捕获异常并返回 `QueryResponse(ok=False, ApiError(code="internal_error"))`，不向 UI 泄露 traceback。

### 9.3 Command Gateway

```python
class UiCommandGateway(Protocol):
    def append_session_input(
        self,
        request: CommandRequest[AppendSessionInputPayload],
    ) -> CommandResponse: ...

    def generate_task_tree(
        self,
        request: CommandRequest[GenerateTaskTreePayload],
    ) -> CommandResponse: ...

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[AppendTaskInputPayload],
    ) -> CommandResponse: ...

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[UpdateTaskNodePayload],
    ) -> CommandResponse: ...

    def publish_task_tree(
        self,
        request: CommandRequest[PublishTaskTreePayload],
    ) -> CommandResponse: ...

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[ResolveConfirmationPayload],
    ) -> CommandResponse: ...
```

Dependencies:

- `CollaboratorApiAdapter`
- `TaskCommandService`
- required `TaskRefResolver`

第一版实现边界：

- `appendSessionInput(mode="generate_task_tree")` 走 `CollaboratorApiAdapter.append_session_message`，保持 Main Page 主工作流进入 RawTask authoring；
- `generateTaskTree(rawTaskId=...)` 走 `CollaboratorApiAdapter.generate_task_tree`，只作为高级/特定工作流入口；
- `appendTaskInput` 根据 `TaskRefResolver` 结果路由：draft Task 走 Collaborator refine，published Task 走 `TaskCommandService.append_task_message`；
- `updateTaskNode` 走 `TaskCommandService.update_task_node`，并把 `update_mode` 转成 `TaskNodePatch.children_ops` 里的保留语义；
- `publishTaskTree` 第一版走 `CollaboratorApiAdapter.publish_task_tree`；
- `resolveConfirmation` 走 `TaskCommandService.resolve_confirmation`；
- backend `CommandResult` 必须包装成 UI `CommandResponse`，并补充 `ObjectRef` / `AffectedObjectRef` / `RefreshHint`；
- rejected command 返回 `ok=False + ApiError(code="command_rejected")`，unexpected exception 返回 `internal_error`。

### 9.4 TaskRefResolver

Frontend routes currently use `taskNodeId` for convenience. Backend needs `TaskRef`.

Add a small resolver boundary:

```python
class TaskRefResolver(Protocol):
    def resolve(self, session_id: str, task_node_id: str) -> TaskRef: ...
```

First version:

- if id exists as draft node -> `TaskRef.draft(id)`;
- else if id exists as published task -> `TaskRef.published(id)`;
- else not_found.

This avoids making every command guess draft/published state.

---

## 10. Event Contract

### 10.1 UiEvent

```python
UiEventType = Literal[
    "session.status_changed",
    "session.resync_required",
    "task.tree.changed",
    "task.node.changed",
    "message.appended",
    "confirmation.created",
    "confirmation.resolved",
    "result.updated",
    "file_changes.updated",
    "audit.summary_updated",
    "command.completed",
    "command.failed",
]

class UiEvent(UiContractModel):
    event_id: str
    session_id: str
    event_type: UiEventType
    cursor: str
    task_node_ids: tuple[str, ...] = ()
    task_refs: tuple[TaskRef, ...] = ()
    message_ids: tuple[str, ...] = ()
    command_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
```

### 10.2 Event cursor

第一版 cursor 是 opaque string。

第一版不实现 durable `UiEventStore`。contract 只定义 cursor 字段和 `resync_required` fallback；SSE replay、cursor retention、过期策略放到未来 sidecar/SSE plan 中处理。

可实现为：

```text
ui:<monotonic-sequence>
```

或：

```text
<created_at_iso>#<event_id>
```

但 UI 不允许解析 cursor。

### 10.3 Event constructors

建议先提供纯函数：

```python
session_status_changed(session_id: str, *, cursor: str, ...) -> UiEvent
resync_required(session_id: str, *, cursor: str, reason: str) -> UiEvent
task_tree_changed(session_id: str, *, cursor: str, task_refs: tuple[TaskRef, ...], ...) -> UiEvent
task_node_changed(session_id: str, *, cursor: str, task_refs: tuple[TaskRef, ...], ...) -> UiEvent
message_appended(message: AgentMessage, cursor: str) -> UiEvent
confirmation_created(message: AgentMessage, cursor: str) -> UiEvent
confirmation_resolved(response: AgentMessage, cursor: str) -> UiEvent
result_updated(session_id: str, *, cursor: str, ...) -> UiEvent
file_changes_updated(session_id: str, *, cursor: str, ...) -> UiEvent
audit_summary_updated(session_id: str, *, cursor: str, ...) -> UiEvent
command_completed(session_id: str, *, cursor: str, command_id: str, ...) -> UiEvent
command_failed(session_id: str, *, cursor: str, command_id: str, ...) -> UiEvent
```

Event projection 不应该读取 UI state。第一版 constructors 只负责生成 thin patch hint，不负责 SSE framing、durable replay 或 cursor retention。

---

## 11. Mapping Rules

### 11.1 Task tree mapping

Backend:

```python
taskweavn.task.views.TaskTreeView(
    session_id=...,
    nodes=(TaskCardView(...),),
    generated_at=...,
)
```

Contract:

```python
TaskTreeView(
    id=<tree id or synthetic session tree id>,
    session_id=...,
    title=...,
    status=...,
    nodes=(TaskNodeCardView(...),),
    version=...
)
```

Because backend projection currently does not expose tree id/title/status/version in the same shape as frontend:

- draft tree should use real `DraftTaskTree.draft_tree_id` when available;
- if unavailable, use `session:{session_id}:task-tree` synthetic id;
- `TaskTreeView.id` is a UI projection/cache/debug id, not a user-facing label and not a domain primary key;
- normal product UI should not display this id; debug/audit views may expose it as technical detail;
- command payloads that require a real draft tree id must be resolved by Gateway instead of blindly trusting a synthetic projection id;
- title can default to `"Task Tree"`;
- version can default to max node version or `1`;
- status derives from nodes:
  - any running -> `running`;
  - all done and non-empty -> `completed`;
  - any failed -> `failed`;
  - any published/queued -> `published`;
  - otherwise -> `draft`.

### 11.2 Session status mapping

Contract `SessionSummary.status` is product-facing:

```text
new, understanding, draft_ready, running, waiting_user, completed, failed
```

Mapping priority:

1. pending confirmation exists -> `waiting_user`;
2. draft tree exists and not published -> `draft_ready`;
3. any task running -> `running`;
4. all published tasks done -> `completed`;
5. any failed root / unrecoverable session error -> `failed`;
6. raw task assessing / collaborator processing -> `understanding`;
7. default -> `new`.

This is not identical to `core.Session.status`; it is a UI projection.

### 11.3 Message mapping

Task-scoped messages remain physically stored in the single Session Message Stream.

```text
AgentMessage
  -> SessionMessageView
  -> optional ConfirmationActionView
```

Rules:

- `task_id is None` -> `taskNodeId=null`;
- `message_type=actionable` -> `kind=actionable` and may create `ConfirmationActionView`;
- `message_type=response` -> `kind=response`;
- `agent_id=user` informational -> user-visible response/guidance message;
- system/internal-only messages can be filtered later by context flag.

---

## 12. Test Design

### 12.1 Backend unit tests

New tests:

```text
tests/test_ui_contract_models.py
tests/test_ui_contract_mapping.py
tests/test_ui_query_gateway.py
tests/test_ui_command_gateway.py
tests/test_ui_event_projection.py
```

First implementation may start with only models and mapping tests.

### 12.2 Required cases

Model tests:

- unknown fields rejected;
- frozen models cannot mutate;
- camelCase serialization;
- QueryResponse success/error invariants;
- CommandResponse accepted/rejected invariants;
- ApiError code enum rejects unknown code;
- UiEvent type enum rejects unknown type.

Mapping tests:

- draft TaskCard -> contract TaskNodeCard;
- published pending Task -> UI `queued`;
- pending actionable message -> confirmation view;
- parent file summary keeps recursive flag;
- no raw backend object appears in JSON.

Gateway tests:

- empty session snapshot;
- draft tree snapshot;
- pending confirmation snapshot;
- command rejected maps to `command_rejected`;
- unexpected exception maps to `internal_error`;
- generated response has refresh hints.

### 12.3 Contract fixture

Optional but recommended:

```text
tests/fixtures/ui_contract/main_page_snapshot.min.json
```

Generate from Python contract and consume in frontend test later.

This is the cheapest way to catch Python/TypeScript field drift without introducing schema codegen.

---

## 13. Implementation Order

Recommended first PR:

1. add `taskweavn.server.ui_contract.base`;
2. add `errors.py`, `envelopes.py`, `view_models.py`, `snapshots.py`, `events.py`;
3. export package;
4. add model tests;
5. keep frontend `ApiError` type aligned with backend `permission_denied`;
6. no gateway yet.

Second PR:

1. add mapping functions;
2. add snapshot fragment mapping tests;
3. add `TaskRefResolver`;
4. add minimal `DefaultUiQueryGateway.get_session_snapshot`.

Third PR:

1. add `DefaultUiCommandGateway`;
2. wrap Collaborator and Task command services;
3. decide and implement RawTask id handoff;
4. add command tests.

Fourth PR:

1. add event constructors;
2. add event tests;
3. prepare sidecar API shell plan.

---

## 14. Documentation Updates When Implemented

When implementation lands:

- update [UI/backend Contract Baseline Plan](ui-backend-contract-baseline.md);
- update [Gap Registry](../../gaps/README.md);
- update [Plato UI API Contract](../../product/plato-ui-api-contract.md) if fields changed;
- update [UI And Backend Communication](../../architecture/ui-backend-communication.md) only if boundary decisions changed;
- add release record under `docs/releases/`.

---

## 15. Open Decisions

These do not block Slice 1 contract models. Current state:

- no blocking open decision remains for Slice 1;
- Slice 2/3 can proceed with the resolved boundary rules below;
- sidecar/SSE plan must still design durable event retention.

Resolved:

- `CommandResult` 不使用自由 `metadata` 表达关键语义，改用 `ObjectRef`、`AffectedObjectRef`、`AffectedScope` 和 `debugRefs`；
- `permission_denied` 已同步到 frontend `ApiError` union；
- 父节点语义变化支持 `replace_subtree` / `replace_children` 风格，UI 通过 `affected_scopes` 重查。
- `TaskTreeView.id` 第一版允许 synthetic id，但它是 UI projection/cache/debug id，不是用户可见标签，也不是 domain primary key；
- Event cursor 第一版不实现 durable store，只保留 opaque cursor + `resync_required`；durable replay/retention 放入 sidecar/SSE plan；
- Main Page 主工作流统一走 `appendSessionInput(mode="generate_task_tree")`；`generateTaskTree(rawTaskId=...)` / 独立 endpoint 保留给未来特定工作流或高级入口。

建议：

- Slice 2/3 按上述规则实现 Gateway；
- sidecar API shell 前补一份 SSE durable cursor/event retention 计划。
