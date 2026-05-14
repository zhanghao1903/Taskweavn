# Feature Plan: Collaborator Agent 与 Authoring Command Protocol

> Status: in progress
> Type: 新特性支持
> Last Updated: 2026-05-14
> Owner/Session: planning session
> Target Implementation Session: independent feature session
> Technical Design: `docs/architecture/collaborator-agent-task-authoring.md`
> Related Docs: `docs/architecture/authoring-domain.md`, `docs/architecture/authoring-command-protocol.md`, `docs/architecture/tool-capability-layer.md`, `docs/architecture/workspace-communication-protocol.md`, `docs/architecture/agent.md`, `docs/architecture/task.md`, `docs/architecture/bus.md`, `docs/architecture/task-domain-ui-model-separation.md`, `docs/plans/task-first-ui-interaction.md`
> User Needs: `UN-105`, `UN-101`, `UN-102`, `UN-103`

---

## 1. 背景

TaskWeavn 的 UI 设计已经明确：用户交互对象不是文件或聊天消息，而是 `Task`。

但从系统能力看，还缺一个关键角色：**协作者 Agent**。它不是执行业务任务的 Agent，而是系统启动时默认创建的用户协作伙伴，用来把用户的自然语言变成可编辑、可确认、可发布的 Task Tree List。

用户最常见的路径现在拆成两个阶段。

第一阶段是 intent authoring：

```text
自然语言目标
  → RawTask
  → feasibility / clarification / enrichment
  → ready_to_plan
```

第二阶段是 task tree authoring：

```text
RawTask
  → Collaborator Agent 拆成 Task Tree List 草案
  → 用户选择 Task Node 修改 / 补充 / 选择选项
  → Collaborator Agent 更新 Task Node 或子树
  → 用户确认
  → 发布 Task 到 TaskBus
```

这件事很重要，因为它把 Task-first UI 从“展示层设计”变成“系统可以真实生成和维护 Task 的能力”。

### 1.1 当前基线

2026-05-14 之后，本计划不再从零定义 Draft Task 模型。上一阶段已经落地：

- `TaskRef`
- `TaskDomain`
- `DraftTaskNode`
- `DraftTaskTree`
- `DraftToPublishedMapping`
- `TaskStore`
- `DraftTaskStore`
- `TaskProjectionService`
- `TaskCommandService`
- `TaskInteractionTimelineService`

因此本阶段重点调整为：

```text
CollaboratorAuthoringService
  + AuthoringContextBuilder
  + DraftTaskTreeValidator
  + AuthoringCommandService
  + Authoring command handlers
  + Collaborator Agent Template
```

领域边界见 [Authoring Domain Architecture](../../architecture/authoring-domain.md)，协作者技术方案见 [Collaborator Agent And Task Authoring](../../architecture/collaborator-agent-task-authoring.md)。
Authoring Command 边界见 [Authoring Command Protocol](../../architecture/authoring-command-protocol.md)。
工具与能力边界见 [Tool Capability Layer](../../architecture/tool-capability-layer.md)。
系统与 workspace 的长期通信边界见 [Workspace Communication Protocol](../../architecture/workspace-communication-protocol.md)。

### 1.2 用户需求归因

本计划对应的用户需求链路：

| User Need | 本计划承担的部分 |
|---|---|
| [UN-105](../../user_model/needs/UN-105-system-evaluability-and-capability-disclosure.md) | RawTask feasibility、澄清问题、能力边界提示，帮助用户在执行前判断任务是否适合系统。 |
| [UN-101](../../user_model/needs/UN-101-photo-curation-batch-screening.md) | 把批量筛图目标转成可编辑 Task Tree，并保留人工复核节点。 |
| [UN-102](../../user_model/needs/UN-102-courseware-html-generation.md) | 把教学目标、受众、时长、风格约束转成可持续修改的课件任务树。 |
| [UN-103](../../user_model/needs/UN-103-car-purchase-decision-support.md) | 对高风险信息整理任务先做约束收集、可行性判断与风险提示，不强行进入执行。 |

---

## 2. 定位

Collaborator Agent 是系统内置 Agent Template，符合 Agent 基本抽象，但生命周期和职责有特殊性。

### 2.1 它仍然是 Agent

它应该符合当前 Agent 设计：

- 有 `AgentTemplate`
- 有 `capability`
- 有 Authoring Command Protocol 与受控能力描述
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

### 2.4 它不挂载全量工具池

Collaborator 需要知道系统能做什么，但不应该挂载所有能改变 workspace 的工具。

第一版原则：

- Collaborator 不默认挂载 `authoring.system` / `publishing.system` 作为 LLM-visible tool pool。
- RawTask / DraftTaskTree / publish mapping 等系统状态修改走 `AuthoringCommandService`。
- Collaborator 通过只读 `CapabilityCatalog` 理解 execution capabilities。
- 普通执行 Agent 不提交 authoring commands。
- Task Node 写 `required_capability`，不直接绑定 `tool_id`。
- capability 到 `WorkspaceRequest` / Tool adapter / Agent Template 的绑定留给 publish/preflight/execution 阶段。

这样可以保留 RawTask 工作流的连贯性，同时避免协作者面对全量工具池导致规划质量下降。

---

## 3. 目标

1. 定义 Collaborator Agent 的系统职责和生命周期。
2. 定义自然语言生成 Task Tree List 的流程。
3. 定义选中 Task Node 后，用户选择选项或输入自然语言时如何更新 Task Node。
4. 定义用户确认无误后，如何发布 Task 到 TaskBus。
5. 定义完成这些能力需要的 Authoring Commands、command handlers 与服务边界。
6. 明确 draft task 与 published task 的边界，避免用户未确认时任务已经进入执行总线。
7. 定义 RawTask / FeasibilityReport / RawTaskAsk，避免系统在信息不足时强行生成 Task Tree。

---

## 4. 非目标

- 不实现完整 UI。
- 不实现多用户协同编辑。
- 不实现 DAG Task 拓扑；当前仍是 Tree List。
- 不实现复杂自动规划评估器；第一版依赖 LLM + 校验规则。
- 不让 Collaborator Agent 直接执行业务工具，例如写文件、运行命令。
- 不把 draft task 直接写入 TaskBus；发布必须经过用户确认。
- 不把 RawTask 写入 Execution TaskBus；RawTask 属于 Authoring Domain。

---

## 5. 核心工作流

### 5.1 工作流 A：自然语言生成 RawTask

```text
User global input
  → Session Message Stream append user message
  → Collaborator produces RawTask authoring proposal
  → AuthoringCommandService submits MutateRawTaskCommand
  → command handler records feasibility / missing inputs
  → if needs clarification: command handler creates RawTaskAsk + actionable message
  → if ready: RawTask status = ready_to_plan
```

要求：

- 用户输入后先形成 RawTask，不直接强行生成完整 Task Tree。
- RawTask 可以表达 `ready` / `needs_clarification` / `partially_feasible` / `not_supported` / `unsafe` 等状态。
- ASK 动作挂载在 RawTask 上，用户回答后 patch RawTask。
- RawTask 不进入 Execution TaskBus。
- UI 可以展示 RawTask Card，说明当前目标为什么还不能规划或执行。

### 5.2 工作流 B：RawTask 生成 Task Tree List

```text
RawTask ready_to_plan
  → Collaborator Agent receives session context
  → Collaborator proposes DraftTaskTree
  → AuthoringCommandService submits MutateDraftTaskTreeCommand
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

### 5.3 工作流 C：选中 Task Node 后更新节点

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
  → AuthoringCommandService submits MutateDraftTaskTreeCommand patch
  → UI refreshes Task Node / subtree
```

要求：

- Task-scoped 输入不触发全局 Task Tree 重建。
- Collaborator 只能更新 draft / pending 但未发布执行的节点。
- 如果节点已经 running / done，应给出 follow-up proposal，而不是原地修改。

### 5.4 工作流 D：用户确认后发布 Task

```text
User confirms draft tree
  → DraftTaskTreeValidator checks tree correctness
  → AuthoringCommandService submits PublishDraftTaskTreeCommand
  → TaskPublisher converts draft tasks to TaskBus tasks
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

### 6.5 RawTask

RawTask 是自然语言输入到 Task Tree 之间的过渡对象。它属于 Authoring Domain，不进入 Execution TaskBus。

```python
class RawTask(BaseModel):
    id: str
    session_id: str
    source_message_id: str
    user_input: str
    status: Literal[
        "created",
        "assessing",
        "awaiting_user",
        "ready_to_plan",
        "converted",
        "rejected",
        "cancelled",
    ]
    intent_summary: str | None = None
    feasibility: FeasibilityReport | None = None
    missing_inputs: list[Question] = []
    constraints: list[str] = []
    assumptions: list[str] = []
```

### 6.6 FeasibilityReport

FeasibilityReport 不回答简单 yes/no，而回答做到什么程度、缺什么、风险在哪、下一步应该做什么。

```python
class FeasibilityReport(BaseModel):
    status: Literal[
        "ready",
        "needs_clarification",
        "needs_user_permission",
        "partially_feasible",
        "not_supported",
        "unsafe",
    ]
    confidence: float
    reasons: list[str] = []
    missing_inputs: list[Question] = []
    required_capabilities: list[str] = []
    required_permissions: list[str] = []
    suggested_next_action: Literal[
        "generate_task_tree",
        "ask_user",
        "offer_alternatives",
        "decline",
    ]
```

### 6.7 RawTaskAsk / RawTaskAnswer

```python
class RawTaskAsk(BaseModel):
    raw_task_id: str
    question: str
    options: list[AnswerOption] = []
    required: bool
    reason: str
```

```python
class RawTaskAnswer(BaseModel):
    raw_task_id: str
    ask_id: str
    value: str
    source_message_id: str
```

---

## 7. Authoring Command 与 Handler 计划

Collaborator Agent 需要一组专门的 Authoring Commands。这些 commands 不直接写 Workspace 文件，而是通过 command handlers 操作 `RawTaskStore`、`DraftTaskStore`、`MessageStream` 和 `TaskPublisher`。

### 7.1 MutateRawTaskCommand: create

用途：

- 将用户自然语言输入转换为 RawTask。

输入：

- `session_id`
- `source_message_id`
- `user_input`

输出：

- `RawTask`

验收：

- 每条全局用户输入可以生成一个 RawTask。
- RawTask 初始状态为 `created` 或 `assessing`。
- RawTask 不进入 Execution TaskBus。

### 7.2 MutateRawTaskCommand: record_feasibility

用途：

- 对 RawTask 做结构化可行性判断。

输入：

- `raw_task_id`
- session context
- capability catalog
- policy / permission context

输出：

- `FeasibilityReport`

验收：

- 能输出 `ready` / `needs_clarification` / `needs_user_permission` / `partially_feasible` / `not_supported` / `unsafe`。
- 不能完成时必须给出原因和建议下一步。
- `needs_clarification` 必须产生可问用户的 missing inputs。

### 7.3 MutateRawTaskCommand: add_clarification_ask

用途：

- 针对 RawTask 发布澄清问题。

输入：

- `raw_task_id`
- `question`
- `options`
- `required`
- `reason`

输出：

- `RawTaskAsk`
- associated MessageStream actionable

验收：

- ASK 必须带 `raw_task_id`。
- 用户回答后能形成 `RawTaskAnswer` 并 patch RawTask。
- ASK 不直接创建 DraftTaskTree。

### 7.4 MutateDraftTaskTreeCommand: create_tree

用途：

- 将 ready_to_plan 的 RawTask 转换成 `DraftTaskTree`。

输入：

- `session_id`
- `raw_task_id`
- `context`
- 可选 workspace summary

输出：

- `DraftTaskTree`

验收：

- 能生成多个 root tree。
- 每个节点有 `intent` 和 `required_capability`。
- `required_capability` 必须来自 `CapabilityCatalog`，不能从 LLM 自由编造。
- 输出默认是 draft，不进入 TaskBus。

### 7.5 MutateDraftTaskTreeCommand: patch_node

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

### 7.6 Proposal Type: TaskNodeOptionSet

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

### 7.7 DraftTaskTreeValidator

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

### 7.8 PublishDraftTaskTreeCommand

用途：

- 将用户确认后的 Draft Task Tree 发布到 TaskBus。

输入：

- `session_id`
- `draft_tree_id`
- `root_node_ids`

输出：

- `PublishResult`

验收：

- 通过 `TaskPublisher` 调用 TaskBus.publish。
- draft status 转成 `pending`。
- 写入 Session Message Stream 和 EventStream。
- 发布失败时不产生半发布状态，或有明确事务语义。

### 7.9 AuthoringContextBuilder

用途：

- 让 Collaborator Agent 读取当前 Session 的 RawTask、draft tree、selected node context 和相关消息。

输入：

- `session_id`
- 可选 `task_node_id`

输出：

- tree 或 node detail

验收：

- 支持 selected node + ancestor + children 视图。
- 支持 version 字段，避免覆盖旧版本。

### 7.10 Message Command Side Effects

用途：

- 由 command handler 将协作者的解释、问题、建议写入 Session Message Stream，并关联 RawTask 或 Task Node。

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
    command_protocol="authoring.v1",
    capability_catalog="execution.capabilities.readonly",
    default_autonomy="manual_or_collaborative",
)
```

注意：

- `command_protocol` 表示协作者提交系统状态变更时使用的强类型协议，不代表把系统工具全部暴露给 LLM。
- 第一版优先由 `CollaboratorAuthoringService` 调用 `AuthoringCommandService`，LLM 只输出结构化 proposal。
- Collaborator 不挂载 `workspace.basic`，因此不能直接写文件或运行命令。

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
  → Collaborator emits authoring proposal
  → AuthoringCommandService submits MutateRawTaskCommand
  → if needs clarification: command handler writes RawTaskAsk + actionable message
  → if ready_to_plan: AuthoringCommandService submits MutateDraftTaskTreeCommand
  → append assistant message with RawTask / draft summary
  → UI subscribe event refresh
```

### 9.3 Task-scoped Input

```text
appendTaskMessage(task node input)
  → invoke Collaborator Agent with selected node context
  → Collaborator emits patch / option proposal
  → AuthoringCommandService submits MutateDraftTaskTreeCommand
  → append assistant message
  → UI refresh selected node
```

### 9.4 Publish

```text
user confirms
  → DraftTaskTreeValidator
  → AuthoringCommandService submits PublishDraftTaskTreeCommand
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

| UI/API | Collaborator / Command Boundary |
|---|---|
| `generateTaskTree` | `MutateRawTaskCommand` + maybe `MutateDraftTaskTreeCommand` |
| `updateTaskNode` | `MutateDraftTaskTreeCommand` |
| `appendTaskMessage` | Message append + Collaborator reasoning + command side effects |
| `acceptTaskTree` | `DraftTaskTreeValidator` + `MutateDraftTaskTreeCommand` marks accepted |
| `startTaskExecution` | `PublishDraftTaskTreeCommand` + TaskPublisher + TaskBus publish |

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

第一版不强制新增 typed EventStream 事件。优先依赖 MessageStream、RawTaskStore/DraftTaskStore version history、command result trace 来重放 authoring 过程。

如果后续需要更强审计，可以新增事件类型：

- `draft_task_tree.created`
- `draft_task_tree.updated`
- `draft_task_node.updated`
- `draft_task_tree.accepted`
- `draft_task_tree.published`
- `draft_task_tree.validation_failed`

这些事件用于审计和 UI 回放；真正执行任务的 publish / claim / complete 仍属于 TaskBus 事件。

---

## 13. 执行切片

### 13.1 重审后的切片原则

这次重审后，切片按稳定性从内向外推进：

```text
Draft contracts
  → RawTask facts
  → Authoring Command contracts
  → Authoring stores
  → Command service / handlers
  → Context builder
  → Collaborator LLM proposal mapping
  → Publish boundary
  → API adapter
```

原因是：协作者 prompt 和 proposal parsing 会高频试错，不能先进入基础层。基础层应该先稳定 RawTask / DraftTaskTree / AuthoringCommand / Store / Handler 这几个强约束对象。

### Slice 1: Draft Authoring Contracts And Validator

状态：已完成第一版，保留。

产出：

- `AuthoringContext`
- `DraftTaskNodeProposal`
- `DraftTaskTreeProposal`
- `DraftTaskPatchProposal`
- `DraftTaskValidationIssue`
- `DraftTaskTreeValidation`
- `TaskNodeOption`
- `TaskNodeOptionSet`
- `CapabilityCatalog`
- `StaticCapabilityCatalog`
- `DraftTaskTreeValidator`

验收：

- 能校验 capability、tree 结构、publishable status、max depth / max nodes。
- capability catalog 可先是静态实现。
- 不需要真实 LLM。
- 不改 TaskBus。

### Slice 2: RawTask Contracts And Feasibility

产出：

- `RawTask`
- `RawTaskStatus`
- `RawTaskAsk`
- `RawTaskAnswer`
- `FeasibilityReport`
- `FeasibilityStatus`
- RawTask status transition rules
- RawTask validation helpers
- deterministic fallback feasibility assessor/helper

验收：

- 用户输入可以形成 RawTask。
- RawTask 可以表达 ready / needs_clarification / partially_feasible / not_supported / unsafe。
- ASK 必须关联 RawTask。
- RawTask 可以记录用户 answer 并推进 version。
- RawTask 不进入 Execution TaskBus。
- 不引入 LLM、store、command handler。

### Slice 3: Authoring Command Protocol Contracts

产出：

- `ActorRef`
- `AuthoringCommandBatch`
- `MutateRawTaskCommand`
- `RawTaskOperation`
- `MutateDraftTaskTreeCommand`
- `DraftTaskTreeOperation`
- `PublishDraftTaskTreeCommand`
- `AuthoringCommandResult`
- `AuthoringCommandError`
- `AuthoringMessageEffect`
- idempotency / expected_version 字段

验收：

- command 是纯数据合约，不执行写入。
- batch 默认 `all_or_nothing`。
- command result 能表达 accepted/rejected、errors、warnings、affected refs、message effects。
- 不引入 store、handler、LLM。

### Slice 4: In-Memory Authoring Stores

产出：

- `RawTaskStore` protocol
- `DraftTaskStore` protocol alignment 或扩展
- `InMemoryRawTaskStore`
- `InMemoryDraftTaskStore`
- create/read/update/mark_published
- version check
- tree traversal helper
- draft-to-published mapping persistence

验收：

- 能创建 tree list。
- 能读取 selected node。
- 能更新节点并递增 version。
- stale version 被拒绝。
- 能区分 draft / accepted / published 状态。
- RawTask / DraftTaskTree store 均可独立测试。

### Slice 5: Authoring Command Service And Handlers

产出：

- `AuthoringCommandService`
- `DefaultAuthoringCommandService`
- `MutateRawTaskHandler`
- `MutateDraftTaskTreeHandler`
- `ValidateDraftTaskTreeHandler`
- `PublishDraftTaskTreeHandler` skeleton
- message effect application
- structured command errors/warnings
- `all_or_nothing` 语义

验收：

- command handler 不直接写 Workspace。
- command handler 写入 RawTaskStore / DraftTaskStore / MessageStream。
- 非法更新返回结构化错误。
- 同一 idempotency key 不重复应用副作用。
- handler tests 不需要 LLM。

### Slice 6: Authoring Context Builder And Capability Catalog v1

产出：

- `AuthoringContextBuilder`
- session-mode context
- task-mode selected node context
- RawTask + DraftTaskTree + recent messages 聚合
- descriptor-based `CapabilityCatalog` v1 或从当前 static catalog 的 adapter；字段需兼容未来 `WorkspaceCapabilityDescriptor`

验收：

- context builder 只读，不产生状态变化。
- 能为 RawTask generation、DraftTaskTree generation、selected-node refinement 生成不同 context。
- capability descriptor 至少预留 risk/cost/reliability/preconditions，并能从未来 WorkspaceManifest 派生。

### Slice 7: Collaborator Authoring Service

产出：

- `CollaboratorAuthoringService`
- `DefaultCollaboratorAuthoringService`
- structured LLM proposal parsing
- proposal-to-command-batch mapping
- prompt templates

验收：

- mock LLM 能生成 draft tree。
- mock LLM 能把 selected node instruction 转成 patch。
- mock LLM 能提出 RawTask feasibility / clarification proposal。
- task-scoped input 不触发全局 tree 重建。
- 所有 durable 输出通过 `AuthoringCommandService` 写入 RawTaskStore / DraftTaskStore / MessageStream。

### Slice 8: Publish Boundary

产出：

- `PublishDraftTaskTreeCommand` handler 完成
- draft node 到 published Task 的转换
- `TaskPublisher` boundary 集成
- publish transaction / rollback 语义

验收：

- 用户未确认时不会进入 TaskBus。
- 发布后 Task status 是 `pending`。
- 发布产生 MessageStream 和 EventStream 或等价 trace 记录。
- 校验失败不会半发布。
- duplicate publish 被拒绝或幂等返回。
- 第一版不直接实现 TaskBus v2；具体 TaskBus-backed publisher 归后续 TaskPublisher 计划。

### Slice 9: Collaborator Agent Template And API Adapter

产出：

- 系统内置 Collaborator Agent Template
- system prompt
- `command_protocol="authoring.v1"`
- capability=`task_authoring`
- Session start 注册逻辑
- `appendSessionMessage` / `answerRawTaskAsk` / `generateTaskTree` / `appendTaskMessage` / `publishTaskTree` adapter

验收：

- Session 创建后 Collaborator 可用。
- Collaborator 不具备文件写入和 shell 执行工具。
- Collaborator 的输出只影响 RawTask / draft task / message / publish command。
- API adapter 不暴露 LLM proposal 原始结构给 UI。

### Slice 10: Tests, Docs, And Release Candidate

产出：

- 单元测试
- 集成测试
- 更新 UI API 文档和架构文档引用
- release record
- roadmap / project roadmap 状态更新

验收：

- 自然语言生成 tree 的离线测试可 mock LLM。
- Task Node update 测试覆盖自然语言补充和 option 选择。
- RawTask clarification 测试覆盖 ask/answer/reassess。
- publish 测试覆盖成功、校验失败、重复发布。

---

## 14. 测试计划

### 14.1 单元测试

- `test_draft_task_models.py`
- `test_raw_task_models.py`
- `test_raw_task_feasibility.py`
- `test_draft_task_store.py`
- `test_authoring_commands.py`
- `test_authoring_command_service.py`
- `test_authoring_context_builder.py`
- `test_collaborator_agent_template.py`
- `test_publish_draft_tasks.py`

### 14.2 集成场景

| 场景 | 期望 |
|---|---|
| 用户输入自然语言且信息不足 | 生成 RawTask + RawTaskAsk，未生成 DraftTaskTree，未进入 TaskBus |
| 用户补充 RawTask 缺失信息 | RawTask 更新为 ready_to_plan 后生成 DraftTaskTree |
| 用户输入自然语言且信息充分 | 生成 RawTask，再生成 DraftTaskTree，未进入 TaskBus |
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
| Tool 过多导致复杂 | 第一版优先实现 object-scoped authoring commands；workspace 执行能力后续走 Workspace Communication Protocol，Tool 只是 adapter |
| Task-scoped input 改坏全局计划 | selected node context + version 校验，默认只影响选中节点或子树 |

---

## 16. 完成标准

该 feature 完成时，应满足：

- Session 开始时系统有一个内置 Collaborator Agent Template。
- 用户自然语言输入先生成 RawTask，并能在信息不足时进入澄清流程。
- RawTask 的 FeasibilityReport 能表达 ready / needs_clarification / partially_feasible / not_supported / unsafe。
- ready_to_plan 的 RawTask 能生成 Draft Task Tree List。
- 用户选中 Task Node 后，能通过选项或自然语言更新该 node / subtree。
- RawTask / DraftTaskTree 在用户确认前不会进入 Execution TaskBus。
- Draft task 在用户确认前不会进入 TaskBus。
- 用户确认后，Draft Task Tree 可校验并发布到 TaskBus。
- 所需 Authoring Commands、command handlers 和结果类型有明确接口与测试。
- MessageStream / store history / optional EventStream 能记录 draft create/update/publish 过程。
- UI API 文档与实现 plan 对齐。

---

## 17. 状态

- Status: in progress
- Created: 2026-05-10
- Started: 2026-05-14
- Current Branch: `codex/collaborator-agent-task-authoring`
- Technical Design: [Collaborator Agent And Task Authoring](../../architecture/collaborator-agent-task-authoring.md)
- Completed in first implementation pass:
  - Slice 1 Draft Authoring Contracts And Validator.
  - Slice 2 RawTask Contracts And Feasibility.
  - Slice 3 Authoring Command Protocol Contracts.
  - Slice 4 In-Memory Authoring Stores.
  - Slice 5 Authoring Command Service And Handlers.
  - Slice 6 Authoring Context Builder And Capability Catalog v1.
  - Added `taskweavn.task.authoring` with:
    - `ActorRef`
    - `AuthoringCommandBatch`
    - `MutateRawTaskCommand`
    - `RawTaskOperation`
    - `MutateDraftTaskTreeCommand`
    - `DraftTaskTreeOperation`
    - `PublishDraftTaskTreeCommand`
    - `PublishOptions`
    - `AuthoringMessageEffect`
    - `AuthoringCommandError`
    - `AuthoringCommandWarning`
    - `RawTask`
    - `RawTaskStatus`
    - `RawTaskAsk`
    - `RawTaskAnswer`
    - `RawTaskAnswerOption`
    - `FeasibilityReport`
    - `FeasibilityStatus`
    - `FeasibilityNextAction`
    - `AuthoringContext`
    - `CapabilityDescriptor`
    - `DraftTaskNodeProposal`
    - `DraftTaskTreeProposal`
    - `DraftTaskPatchProposal`
    - `TaskNodeOption`
    - `TaskNodeOptionSet`
    - `DraftTaskValidationIssue`
    - `DraftTaskTreeValidation`
    - `AuthoringCommandResult`
    - `CapabilityCatalog`
    - `StaticCapabilityCatalog`
    - `DraftTaskTreeValidator`
  - `CapabilityCatalog` is now descriptor-based while retaining deterministic `contains()` checks for validation.
  - `AuthoringContext` now carries RawTask fields:
    - `raw_task_id`
    - `feasibility_status`
    - `unresolved_asks`
    - `raw_tasks`
  - Added `taskweavn.task.stores` authoring store contracts and implementations:
    - `RawTaskStore`
    - `InMemoryRawTaskStore`
    - `InMemoryDraftTaskStore`
    - `TaskStoreError`
    - `VersionConflictError`
  - `DraftTaskStore` now includes traversal and lifecycle methods:
    - `list_nodes`
    - `list_children`
    - `add_node`
    - `mark_accepted`
  - Added `taskweavn.task.authoring_service` with:
    - `AuthoringCommandService`
    - `DefaultAuthoringCommandService`
    - deterministic RawTask and DraftTaskTree command handlers
    - delayed message-effect publication through `MessageBus`
    - batch idempotency cache
    - in-memory rollback support for `all_or_nothing` batches
    - explicit `PublishDraftTaskTreeCommand` skeleton deferred to Slice 8
  - Added `taskweavn.task.authoring_context` with:
    - `AuthoringContextBuilder`
    - `DefaultAuthoringContextBuilder`
    - session-mode RawTask/DraftTaskTree/recent-message aggregation
    - task-mode selected-node/ancestor/children/recent-message aggregation
    - capability descriptor filtering for raw intent and selected node refinement
  - Validator now covers capability lookup, root structure, duplicate node ids, duplicate sibling order, publishable status, blank content, max depth, and max node count.
  - Added tests for AuthoringContextBuilder session/task modes, selected-node reconstruction, capability filtering, read-only behavior, AuthoringCommandService command application, idempotency, RawTask clarification mutation, nested DraftTaskTree creation, message effects, all-or-nothing rollback, best-effort partial success, publish skeleton behavior, in-memory RawTask/DraftTask stores, version conflicts, traversal, accepted/published state transitions, lineage mapping, AuthoringCommand batch invariants, command target validation, message effect validation, result validation, RawTask lifecycle, feasibility defaults/validation, ask/answer linkage, authoring context, proposal schemas, option schemas, validation results, capability catalog, validator errors/warnings, and frozen model behavior.
- Verified:
  - `uv run pytest tests/test_task_authoring.py` — 29 passed, 1 warning
  - `uv run pytest tests/test_in_memory_authoring_stores.py tests/test_task_store_protocols.py tests/test_task_commands.py tests/test_task_projection.py tests/test_task_timeline.py` — 40 passed, 1 warning
  - `uv run pytest tests/test_authoring_command_service.py tests/test_in_memory_authoring_stores.py tests/test_task_authoring.py` — 51 passed, 1 warning
  - `uv run pytest tests/test_authoring_context_builder.py tests/test_task_authoring.py` — 37 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_authoring.py`
  - `uv run ruff check src/taskweavn/task tests/test_in_memory_authoring_stores.py tests/test_task_store_protocols.py tests/test_task_commands.py tests/test_task_projection.py tests/test_task_timeline.py`
  - `uv run ruff check src/taskweavn/task tests/test_authoring_command_service.py tests/test_in_memory_authoring_stores.py tests/test_task_authoring.py`
  - `uv run ruff check src/taskweavn/task tests/test_authoring_context_builder.py tests/test_task_authoring.py`
  - `uv run mypy src/taskweavn/task tests/test_task_authoring.py`
  - `uv run mypy src/taskweavn/task tests/test_in_memory_authoring_stores.py tests/test_task_store_protocols.py tests/test_task_commands.py tests/test_task_projection.py tests/test_task_timeline.py`
  - `uv run mypy src/taskweavn/task tests/test_authoring_command_service.py tests/test_in_memory_authoring_stores.py tests/test_task_authoring.py`
  - `uv run mypy src/taskweavn/task tests/test_authoring_context_builder.py tests/test_task_authoring.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest` — 554 passed, 1 warning
  - `git diff --check`
- Discussion promoted: [RawTask、可行性判断与 Authoring Domain](../../discussion/2026-05-14-raw-task-authoring-domain.md)
- Revised Next Step: Slice 7 Collaborator Proposal Mapping Service。
