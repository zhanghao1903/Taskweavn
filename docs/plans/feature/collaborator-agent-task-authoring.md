# Feature Plan: Collaborator Agent 与 Task Authoring 工具

> Status: planned  
> Type: 新特性支持  
> Last Updated: 2026-05-10  
> Owner/Session: planning session  
> Target Implementation Session: independent feature session  
> Related Docs: `docs/architecture/agent.md`, `docs/architecture/task.md`, `docs/architecture/bus.md`, `docs/plans/task-first-ui-interaction.md`

---

## 1. 背景

TaskWeavn 的 UI 设计已经明确：用户交互对象不是文件或聊天消息，而是 `Task`。

但从系统能力看，还缺一个关键角色：**协作者 Agent**。它不是执行业务任务的 Agent，而是系统启动时默认创建的用户协作伙伴，用来把用户的自然语言变成可编辑、可确认、可发布的 Task Tree List。

用户最常见的路径应该是：

```text
自然语言目标
  → Collaborator Agent 拆成 Task Tree List 草案
  → 用户选择 Task Node 修改 / 补充 / 选择选项
  → Collaborator Agent 更新 Task Node 或子树
  → 用户确认
  → 发布 Task 到 TaskBus
```

这件事很重要，因为它把 Task-first UI 从“展示层设计”变成“系统可以真实生成和维护 Task 的能力”。

---

## 2. 定位

Collaborator Agent 是系统内置 Agent Template，符合 Agent 基本抽象，但生命周期和职责有特殊性。

### 2.1 它仍然是 Agent

它应该符合当前 Agent 设计：

- 有 `AgentTemplate`
- 有 `capability`
- 有工具集
- 有 LLM 配置
- 有 system prompt
- 可记录日志、事件和消息

### 2.2 它是系统组成部分

和普通执行 Agent 不同：

- Session 开始时默认可用。
- 它服务于用户与 Task Tree 的协作，不直接改 Workspace 文件。
- 它的主要产物是 `DraftTaskTree` / `TaskNodePatch` / `PublishTaskCommand`。
- 它不通过 TaskBus 被动领取普通任务；它响应用户输入和 UI command。
- 它可以在未来作为一个特殊 capability：`collaborate` / `task_authoring`。

### 2.3 它不破坏 Agent 无状态原则

Collaborator Agent 不应在实例内积累长期状态。它需要的上下文来自：

- Session 当前 Task Tree 草案
- Session Message Stream
- 用户选中的 Task Node
- Task Node 的约束和历史消息
- 已确认 / 未确认状态

每次调用可以被视为：

```text
CollaboratorAgent(input, session_view) -> draft tree / patch / publish proposal
```

---

## 3. 目标

1. 定义 Collaborator Agent 的系统职责和生命周期。
2. 定义自然语言生成 Task Tree List 的流程。
3. 定义选中 Task Node 后，用户选择选项或输入自然语言时如何更新 Task Node。
4. 定义用户确认无误后，如何发布 Task 到 TaskBus。
5. 定义完成这些能力需要的新 Tool 对象。
6. 明确 draft task 与 published task 的边界，避免用户未确认时任务已经进入执行总线。

---

## 4. 非目标

- 不实现完整 UI。
- 不实现多用户协同编辑。
- 不实现 DAG Task 拓扑；当前仍是 Tree List。
- 不实现复杂自动规划评估器；第一版依赖 LLM + 校验规则。
- 不让 Collaborator Agent 直接执行业务工具，例如写文件、运行命令。
- 不把 draft task 直接写入 TaskBus；发布必须经过用户确认。

---

## 5. 核心工作流

### 5.1 工作流 A：自然语言生成 Task Tree List

```text
User global input
  → Session Message Stream append user message
  → Collaborator Agent receives session context
  → GenerateDraftTaskTreeTool creates draft root tasks
  → UI displays Task Tree List in draft state
```

要求：

- 输出是一个或多个 root Task Tree。
- 每个 Task Node 至少有：
  - title
  - intent
  - required_capability
  - parent-child 关系
  - draft status
  - rationale / explanation
- 生成结果必须是草案，不自动发布。
- UI 必须能展示“待用户确认”状态。

### 5.2 工作流 B：选中 Task Node 后更新节点

用户可以：

- 选择某个 Collaborator 给出的选项
- 输入自然语言补充
- 修改 intent / constraints
- 要求拆分子任务
- 要求合并、删除、改顺序

流程：

```text
User selects Task Node
  → User sends option or natural language note
  → Session Message Stream append task-scoped message
  → Collaborator Agent receives selected task + tree context
  → UpdateDraftTaskNodeTool applies patch
  → UI refreshes Task Node / subtree
```

要求：

- Task-scoped 输入不触发全局 Task Tree 重建。
- Collaborator 只能更新 draft / pending 但未发布执行的节点。
- 如果节点已经 running / done，应给出 follow-up proposal，而不是原地修改。

### 5.3 工作流 C：用户确认后发布 Task

```text
User confirms draft tree
  → ValidateDraftTaskTreeTool checks tree correctness
  → PublishDraftTasksTool converts draft tasks to TaskBus tasks
  → TaskBus.publish(root tasks)
  → UI status: draft → pending
```

要求：

- 发布前必须校验：
  - 无环
  - parent_id 合法
  - required_capability 可被系统识别
  - status 允许发布
  - 每个 root task 有明确 intent
- 发布必须产生 Session Message / Event 记录。
- 发布后 Task 进入 TaskBus，由执行 Agent 领取。

---

## 6. 数据模型需求

### 6.1 DraftTaskNode

第一版字段可以简略：

```python
class DraftTaskNode(BaseModel):
    id: str
    parent_id: str | None
    title: str
    intent: str
    required_capability: str
    constraints: list[str] = []
    status: Literal["draft", "cancelled"] = "draft"
    rationale: str | None = None
    children: list[DraftTaskNode] = []
```

### 6.2 DraftTaskTree

```python
class DraftTaskTree(BaseModel):
    session_id: str
    root_nodes: list[DraftTaskNode]
    created_by: Literal["collaborator_agent", "user"]
    version: int
```

### 6.3 TaskNodePatch

```python
class TaskNodePatch(BaseModel):
    title: str | None = None
    intent: str | None = None
    required_capability: str | None = None
    constraints_add: list[str] = []
    constraints_remove: list[str] = []
    status: str | None = None
    children_ops: list[TaskTreeEditOp] = []
```

### 6.4 PublishResult

```python
class PublishResult(BaseModel):
    published_task_ids: list[str]
    root_task_ids: list[str]
    rejected_nodes: list[RejectedDraftTaskNode] = []
```

---

## 7. 新 Tool 对象计划

Collaborator Agent 需要一组专门的 Task Authoring Tools。这些 Tool 不直接写 Workspace 文件，而是操作 Draft Task Store、Message Stream 和 TaskBus。

### 7.1 GenerateDraftTaskTreeTool

用途：

- 将用户自然语言目标转换成 `DraftTaskTree`。

输入：

- `session_id`
- `prompt`
- `context`
- 可选 workspace summary

输出：

- `DraftTaskTree`

验收：

- 能生成多个 root tree。
- 每个节点有 `intent` 和 `required_capability`。
- 输出默认是 draft，不进入 TaskBus。

### 7.2 UpdateDraftTaskNodeTool

用途：

- 根据用户选项或自然语言补充更新某个 Draft Task Node。

输入：

- `session_id`
- `task_node_id`
- `instruction`
- `patch`

输出：

- 更新后的 `DraftTaskNode`
- 可选 affected subtree summary

验收：

- 只能修改 draft 节点。
- 支持添加约束、修改 intent、拆分/新增子任务。
- 更新后 version 增加。

### 7.3 ProposeTaskNodeOptionsTool

用途：

- 为某个 Task Node 生成可选操作，例如拆分、合并、跳过、改能力、补充约束。

输入：

- `session_id`
- `task_node_id`
- `context`

输出：

- option list

验收：

- 每个 option 可被用户选择。
- option 选择后能映射为 `TaskNodePatch` 或更明确的 edit command。

### 7.4 ValidateDraftTaskTreeTool

用途：

- 发布前校验 Draft Task Tree。

输入：

- `session_id`
- `draft_tree_id`

输出：

- validation result

验收：

- 检查 parent-child 合法性。
- 检查 required capability 是否存在。
- 检查 root task intent 是否为空。
- 检查是否存在 cancelled / invalid node。

### 7.5 PublishDraftTasksTool

用途：

- 将用户确认后的 Draft Task Tree 发布到 TaskBus。

输入：

- `session_id`
- `draft_tree_id`
- `root_node_ids`

输出：

- `PublishResult`

验收：

- 调用 TaskBus.publish。
- draft status 转成 `pending`。
- 写入 Session Message Stream 和 EventStream。
- 发布失败时不产生半发布状态，或有明确事务语义。

### 7.6 ReadDraftTaskTreeTool

用途：

- 让 Collaborator Agent 读取当前 Session 的 draft tree / selected node context。

输入：

- `session_id`
- 可选 `task_node_id`

输出：

- tree 或 node detail

验收：

- 支持 selected node + ancestor + children 视图。
- 支持 version 字段，避免覆盖旧版本。

### 7.7 AppendTaskAuthoringMessageTool

用途：

- 将协作者的解释、问题、建议写入 Session Message Stream，并关联 Task Node。

输入：

- `session_id`
- `task_node_id?`
- `message_type`
- `content`
- `options?`

输出：

- message id

验收：

- 全局模式消息不带 task_node_id。
- Task-scoped 模式消息必须关联 task_node_id。
- 消息进入唯一 Session Message Stream。

---

## 8. Collaborator Agent Template

建议内置模板：

```python
AgentTemplate(
    id="system.collaborator",
    capability="task_authoring",
    display_name="Collaborator",
    description="帮助用户把自然语言目标拆解、修改并发布为 Task Tree",
    tools=[
        GenerateDraftTaskTreeTool,
        ReadDraftTaskTreeTool,
        UpdateDraftTaskNodeTool,
        ProposeTaskNodeOptionsTool,
        ValidateDraftTaskTreeTool,
        PublishDraftTasksTool,
        AppendTaskAuthoringMessageTool,
    ],
    default_autonomy="manual_or_collaborative",
)
```

### 8.1 System Prompt 要求

Collaborator Agent 的 prompt 应强调：

- 只负责生成和维护 Task，不直接执行代码修改。
- Task 必须是树，不是 DAG。
- Task intent 应清晰、可执行、可验证。
- `required_capability` 必须来自已注册 capability。
- 未经用户确认不得发布 Task。
- 用户选中 Task Node 时，只处理该 Task 的局部上下文。
- 已运行或已完成 Task 不原地修改，只提出 follow-up Task。

---

## 9. Session 生命周期集成

### 9.1 Session Start

Session 创建时：

```text
SessionManager.create
  → register system Collaborator Agent Template
  → initialize DraftTaskStore
  → append system message: collaborator ready
```

### 9.2 Global Input

```text
appendSessionMessage(global user input)
  → invoke Collaborator Agent
  → GenerateDraftTaskTreeTool
  → append assistant message with draft summary
  → UI subscribe event refresh
```

### 9.3 Task-scoped Input

```text
appendTaskMessage(task node input)
  → invoke Collaborator Agent with selected node context
  → UpdateDraftTaskNodeTool / ProposeTaskNodeOptionsTool
  → append assistant message
  → UI refresh selected node
```

### 9.4 Publish

```text
user confirms
  → ValidateDraftTaskTreeTool
  → PublishDraftTasksTool
  → TaskBus.publish
  → execution Agent lifecycle starts
```

---

## 10. 与 UI API 的关系

当前 `docs/plans/ui/ui-api-interfaces.md` 中已有接口：

- `generateTaskTree`
- `updateTaskNode`
- `appendTaskMessage`
- `acceptTaskTree`
- `startTaskExecution`

Collaborator Agent 是这些接口背后的系统执行者：

| UI/API | Collaborator / Tool |
|---|---|
| `generateTaskTree` | `GenerateDraftTaskTreeTool` |
| `updateTaskNode` | `UpdateDraftTaskNodeTool` |
| `appendTaskMessage` | `AppendTaskAuthoringMessageTool` + Collaborator reasoning |
| `acceptTaskTree` | `ValidateDraftTaskTreeTool` + mark draft accepted |
| `startTaskExecution` | `PublishDraftTasksTool` + TaskBus publish |

后续可能需要把 UI API 文档中的 `acceptTaskTree` 和 `startTaskExecution` 明确区分：

- `acceptTaskTree`：用户确认草案正确，但还不一定开始执行。
- `publishTaskTree` / `startTaskExecution`：真正进入 TaskBus。

---

## 11. 存储需求

需要新增 Draft Task Store，避免 draft task 与已发布 Task 混在 TaskBus 中。

### 11.1 DraftTaskStore Protocol

```python
class DraftTaskStore(Protocol):
    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree: ...
    def get_tree(self, session_id: str, tree_id: str) -> DraftTaskTree: ...
    def list_trees(self, session_id: str) -> list[DraftTaskTree]: ...
    def update_node(self, session_id: str, node_id: str, patch: TaskNodePatch, version: int) -> DraftTaskNode: ...
    def mark_accepted(self, session_id: str, tree_id: str) -> DraftTaskTree: ...
    def mark_published(self, session_id: str, tree_id: str, task_ids: list[str]) -> DraftTaskTree: ...
```

### 11.2 版本控制

每次修改 draft tree：

- version + 1
- 写入事件或 message
- UI 更新时带 version，避免覆盖并发修改

第一版可以单用户串行，但接口要预留 version。

---

## 12. 消息与事件需求

### 12.1 MessageStream

Collaborator 需要写入：

- global planning response
- task-scoped clarification response
- option list
- validation failure explanation
- publish success/failure summary

每条消息应能关联：

- `session_id`
- `task_node_id?`
- `draft_tree_id?`
- `message_type`
- `created_by=collaborator_agent`

### 12.2 EventStream

建议新增事件类型：

- `draft_task_tree.created`
- `draft_task_tree.updated`
- `draft_task_node.updated`
- `draft_task_tree.accepted`
- `draft_task_tree.published`
- `draft_task_tree.validation_failed`

这些事件用于审计和 UI 回放；真正执行任务的 publish / claim / complete 仍属于 TaskBus 事件。

---

## 13. 执行切片

### Slice 1: Draft Task Models and Store

产出：

- `DraftTaskNode`
- `DraftTaskTree`
- `TaskNodePatch`
- `DraftTaskStore` Protocol
- SQLite 或内存实现

验收：

- 能创建 tree list。
- 能读取 selected node。
- 能更新节点并递增 version。
- 能区分 draft / accepted / published 状态。

### Slice 2: Task Authoring Tools

产出：

- `GenerateDraftTaskTreeTool`
- `ReadDraftTaskTreeTool`
- `UpdateDraftTaskNodeTool`
- `ProposeTaskNodeOptionsTool`
- `ValidateDraftTaskTreeTool`
- `AppendTaskAuthoringMessageTool`

验收：

- 每个 Tool 有 Action / Observation 类型。
- Tool 不直接写 Workspace。
- Tool 写入 DraftTaskStore / MessageStream。
- 非法更新返回结构化错误。

### Slice 3: PublishDraftTasksTool and TaskBus Integration

产出：

- `PublishDraftTasksTool`
- draft node 到 published Task 的转换
- TaskBus publish 集成
- publish transaction / rollback 语义

验收：

- 用户未确认时不会进入 TaskBus。
- 发布后 Task status 是 `pending`。
- 发布产生 MessageStream 和 EventStream 记录。
- 校验失败不会半发布。

### Slice 4: Collaborator Agent Template

产出：

- 系统内置 Collaborator Agent Template
- system prompt
- tool list
- capability=`task_authoring`
- Session start 注册逻辑

验收：

- Session 创建后 Collaborator 可用。
- Collaborator 不具备文件写入和 shell 执行工具。
- Collaborator 的输出只影响 draft task / message / publish command。

### Slice 5: API / CLI / UI Adapter

产出：

- `generateTaskTree`
- `updateTaskNode`
- `appendTaskMessage`
- `acceptTaskTree`
- `publishTaskTree` 或 `startTaskExecution`

验收：

- UI API 能调用 Collaborator 工作流。
- Task-scoped input 不触发全局 tree 重建。
- 用户确认后才发布。

### Slice 6: Tests and Docs

产出：

- 单元测试
- 集成测试
- 更新 UI API 文档和架构文档引用

验收：

- 自然语言生成 tree 的离线测试可 mock LLM。
- Task Node update 测试覆盖自然语言补充和 option 选择。
- publish 测试覆盖成功、校验失败、重复发布。

---

## 14. 测试计划

### 14.1 单元测试

- `test_draft_task_models.py`
- `test_draft_task_store.py`
- `test_task_authoring_tools.py`
- `test_collaborator_agent_template.py`
- `test_publish_draft_tasks.py`

### 14.2 集成场景

| 场景 | 期望 |
|---|---|
| 用户输入自然语言 | 生成 DraftTaskTree，未进入 TaskBus |
| 用户选择 Task Node 输入补充 | 只更新该 Task Node 或子树 |
| 用户选择 Collaborator option | option 转成 patch 并更新节点 |
| 用户确认发布 | Draft tasks 转成 pending tasks 并 publish 到 TaskBus |
| 校验失败 | 返回 validation error，不发布任何任务 |
| 已发布节点再次修改 | 被拒绝，提示创建 follow-up |
| Collaborator 无业务工具 | 无法写文件、无法执行 shell |

---

## 15. 风险与决策点

| 风险 | 处理 |
|---|---|
| Collaborator Agent 打破“Agent 无状态”原则 | 将状态放入 DraftTaskStore / MessageStream，每次调用重建上下文 |
| draft task 与 published task 混淆 | 明确 DraftTaskStore 与 TaskBus 分离 |
| 用户以为确认即执行 | 区分 accept / publish / start execution 的 UI 文案 |
| LLM 生成无效 tree | 发布前强校验，invalid draft 可展示但不可发布 |
| required_capability 幻觉 | Collaborator 只能从注册 capability 列表中选择 |
| Tool 过多导致复杂 | 第一版先实现 generate/read/update/validate/publish，option tool 可后置 |
| Task-scoped input 改坏全局计划 | selected node context + version 校验，默认只影响选中节点或子树 |

---

## 16. 完成标准

该 feature 完成时，应满足：

- Session 开始时系统有一个内置 Collaborator Agent Template。
- 用户自然语言输入能生成 Draft Task Tree List。
- 用户选中 Task Node 后，能通过选项或自然语言更新该 node / subtree。
- Draft task 在用户确认前不会进入 TaskBus。
- 用户确认后，Draft Task Tree 可校验并发布到 TaskBus。
- 所需 Task Authoring Tools 有明确 Action/Observation 类型和测试。
- MessageStream / EventStream 能记录 draft create/update/publish 过程。
- UI API 文档与实现 plan 对齐。

---

## 17. 状态

- Status: planned
- Created: 2026-05-10
- Next Step: 在独立实现会话中创建 feature 分支，先完成 Slice 1 Draft Task Models and Store，再实现 Task Authoring Tools。
