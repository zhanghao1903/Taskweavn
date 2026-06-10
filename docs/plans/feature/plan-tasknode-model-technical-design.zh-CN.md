# Plan / TaskNode 模型升级：中文详细技术方案

> Status: draft technical design
> Type: product model / authoring domain / execution domain / UI contract migration
> Last Updated: 2026-06-09
> Product Baseline:
> [Plato Task Semantics](../../product/plato-task-semantics.md),
> [Plato Plan Cycle Semantics](../../product/plato-plan-cycle-semantics.md),
> [Plato Session Content Model](../../product/plato-session-content-model.md)
> Related:
> [Authoring Domain](../../architecture/authoring-domain.md),
> [Authoring Command Protocol](../../architecture/authoring-command-protocol.md),
> [Plato UI API Contract](../../product/plato-ui-api-contract.md),
> [UI ViewModel Contract](../../frontend/ui-viewmodel-contract.md),
> [RawTask / DraftTaskTree Persistence](raw-task-draft-tree-persistence-technical-design.zh-CN.md)

---

## 0. 摘要

本方案把当前 `RawTask -> DraftTaskTree -> PublishedTask` 流程升级为：

```text
Session
  -> Plan
      -> TaskNode list
      -> Plan finalization
      -> Outcome review
```

关键修订：

1. `Plan` 成为 Session 内的一级工作对象。
2. Collaborator 产出 `Plan`，不是松散的 `TaskTree List`。
3. Product 1.1 第一版只实现两级结构：`Plan -> TaskNode[]`。
4. 第一版不引入父子 TaskNode、不引入 `children_policy`。
5. 第一版不引入 `execution_role` 枚举。TaskNode 要做什么，交给执行 Agent 在 Task contract、上下文和验收标准内自由裁量。
6. Plan finalization 是 Plan 级流程，不通过父节点执行角色来表达。
7. 旧数据中的 `DraftTaskTree` / `TaskTreeView` 兼容投影为 Plan。

本文档保留 `TaskNode` 作为领域/contract 名称。Product 1.1 第一版中的 `TaskNode` 是 Plan 下的扁平任务项；UI 可以简称为 `Task`，但第一版不支持父子 TaskNode。

---

## 1. 背景与问题

当前系统已经具备：

- `RawTask` / `RawTaskAsk` / `DraftTaskTree` 的 authoring 持久化；
- `DraftTaskTree` 发布到 Execution Domain 的路径；
- Main Page 对 `TaskTreeView` / `TaskNodeCardView` 的投影；
- dirty authoring state 防护；
- TaskBus 执行、ASK、retry、audit 等中下层能力。

当前真正需要解决的问题不是 “如何完整表达任意任务树”，而是：

1. `DraftTaskTree` 是技术对象，不足以表达一次完整工作计划的生命周期。
2. Collaborator 产出 TaskTree List 后，Session 不知道这一轮工作完成后如何继续。
3. UI 上用户看到的是 Plan 与进度，而内部最高对象还是 TaskTree。
4. Plan 完成后缺少 Plan 级 summary、验收、下一轮 Plan 的上下文边界。
5. 旧数据和新语义之间需要兼容。

因此本方案优先新增 `Plan`，暂不扩大 Task 层级模型。

---

## 2. 设计目标

### 2.1 目标

- 定义 Plan 数据模型和生命周期。
- 定义第一版 `TaskNode` 数据模型。
- 定义 LLM / Collaborator 的 Plan 输出 contract。
- 定义 UI 中 Plan / TaskNode 的状态与选中模型。
- 定义旧 `DraftTaskTree` / `TaskTreeView` 数据兼容策略。
- 定义后续如果需要父子任务时的预留点，但不在第一版实现。

### 2.2 非目标

第一版不实现：

- 父子 TaskNode；
- `node_type: composite | atomic`；
- `execution_role` 系统枚举；
- `children_policy`；
- 复杂 DAG 调度；
- 多 active Plan 并发；
- 完整 Agent 编排 UI；
- 历史 Plan 高级比较视图。

---

## 3. 设计原则

### 3.1 Plan 是工作循环边界

```text
Session = 长期协作容器
Plan = 一轮组织化工作
TaskNode = Plan 内的一条可执行工作线
```

一个 Session 可以有多个 Plan，但同一时刻只有一个 active Plan。

### 3.2 先控制复杂度

父子节点、复合节点、节点级 summary/validation/integration 都有潜在价值，但它们会显著增加：

- LLM 输出 schema 复杂度；
- UI 树形交互复杂度；
- TaskBus 调度复杂度；
- Context Manager 上下文选择复杂度；
- Audit 和 file rollup 归因复杂度；
- 用户理解成本。

Product 1.1 第一版先用 `Plan -> TaskNode[]` 跑通完整工作循环。只有当真实用户场景证明 TaskNode 不够用时，再引入层级。

### 3.3 TaskNode 只定义工作契约，不定义执行角色

系统不应该用过细的 `execution_role` 枚举硬编码 Task 要做什么。

TaskNode 提供：

- title；
- intent；
- summary；
- instructions；
- constraints；
- acceptance criteria；
- required capability；
- dependency hints。

执行 Agent 根据这些信息和上下文自行判断需要执行、总结、验证、写文档还是修改 workspace。

### 3.4 Plan finalization 是 Plan 级流程

如果一轮 Plan 结束后需要总结、验收、file rollup、context compression，这些是 Plan 级 finalization job。

不要在第一版把它们建模成隐藏父节点或特殊 TaskNode 类型。

### 3.5 LLM 输出只是 proposal

LLM 产出的 Plan JSON 必须经过代码侧 validation、normalization、projection 才能进入持久化和 UI。

---

## 4. 概念模型

### 4.1 对象关系

```text
Session
  id
  active_plan_id?
  plans[]

Plan
  id
  session_id
  source_raw_task_id?
  task_nodes[]
  status
  summary
  context_policy
  finalization
  outcome

TaskNode
  id
  plan_id
  task_index
  order_index
  title
  intent
  summary
  instructions
  constraints
  acceptance_criteria
  required_capability?
  depends_on[]
  status dimensions
  draft/published lineage
```

### 4.2 RawTask 与 Plan

```text
UserMessage
  -> RawTask
  -> Feasibility / ASK
  -> Plan proposal
  -> Plan review
  -> Publish / execution
```

RawTask 仍然是探索对象。Plan 是 RawTask 被整理后的结构化工作对象。

### 4.3 Plan 与 DraftTaskTree

短期兼容策略：

- `DraftTaskTree` 继续作为 legacy authoring 持久化结构存在；
- Gateway 可以把 legacy `DraftTaskTree` 投影为 synthetic `PlanView`；
- UI 不再把 `TaskTree` 作为一级产品语言；
- 新实现逐步从 `DraftTaskTree` 迁移到 `Plan + TaskNode`。

---

## 5. Plan 数据模型

### 5.1 Python 领域模型草案

```python
class Plan(BaseModel):
    id: str
    session_id: str
    source_raw_task_id: str | None = None
    source_draft_tree_id: str | None = None

    title: str
    objective: str
    summary: str
    status: PlanStatus
    version: int

    task_node_ids: tuple[str, ...]
    context_policy: PlanContextPolicy = PlanContextPolicy()
    finalization: PlanFinalizationState = PlanFinalizationState()
    outcome: PlanOutcome | None = None

    created_by: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
```

### 5.2 PlanStatus

```python
PlanStatus = Literal[
    "draft",
    "reviewing",
    "approved",
    "published",
    "running",
    "finalizing",
    "awaiting_acceptance",
    "accepted",
    "follow_up_needed",
    "failed",
    "cancelled",
    "archived",
]
```

| Status | Meaning | UI label |
|---|---|---|
| `draft` | Plan proposal exists, still editable. | Draft |
| `reviewing` | User is reviewing or revising before publish. | Review |
| `approved` | User accepted the Plan, not yet published. | Approved |
| `published` | Plan crossed into execution domain. | Published |
| `running` | At least one TaskNode is pending, running, waiting, or retrying. | Running |
| `finalizing` | TaskNodes terminal; Plan summary/rollup/context preparation is running. | Finalizing |
| `awaiting_acceptance` | Outcome is ready for user review. | Review outcome |
| `accepted` | User accepted the outcome. | Accepted |
| `follow_up_needed` | Outcome points to a follow-up Plan. | Follow-up |
| `failed` | Plan cannot reach intended outcome. | Failed |
| `cancelled` | User/system cancelled this Plan. | Cancelled |
| `archived` | Historical, not active. | Archived |

### 5.3 PlanContextPolicy

```python
class PlanContextPolicy(BaseModel):
    include_prior_plan_summaries: bool = True
    include_session_guidance: bool = True
    include_completed_task_summaries: bool = True
    include_file_change_rollup: bool = True
    max_prior_plan_summaries: int = 3
    context_budget_hint: int | None = None
```

第一版可以只持久化 compact JSON，不需要暴露完整 UI。

### 5.4 PlanFinalizationState

```python
class PlanFinalizationState(BaseModel):
    status: Literal[
        "not_started",
        "pending",
        "running",
        "skipped",
        "done",
        "failed",
    ] = "not_started"
    required: bool = True
    result_summary_id: str | None = None
    file_rollup_id: str | None = None
    context_summary_id: str | None = None
    warnings: tuple[str, ...] = ()
```

注意：Plan finalization 不建模为父 TaskNode。它是 Plan lifecycle 的一部分。

### 5.5 PlanOutcome

```python
class PlanOutcome(BaseModel):
    status: Literal[
        "succeeded",
        "succeeded_with_warnings",
        "partially_completed",
        "failed",
        "cancelled",
    ]
    summary: str
    completed_task_count: int
    failed_task_count: int
    skipped_task_count: int
    file_change_summary_id: str | None = None
    audit_summary_id: str | None = None
    suggested_next_actions: tuple[SuggestedNextAction, ...] = ()
    created_at: datetime
```

---

## 6. TaskNode 数据模型

### 6.1 Python 领域模型草案

```python
class TaskNode(BaseModel):
    id: str
    plan_id: str
    session_id: str

    task_index: str
    order_index: int
    title: str
    intent: str
    summary: str
    instructions: str = ""

    required_capability: str | None = None
    depends_on: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()

    readiness: TaskNodeReadiness
    execution: TaskNodeExecutionStatus
    confirmation: ConfirmationStatus | None = None

    draft_ref: DraftTaskRef | None = None
    published_ref: PublishedTaskRef | None = None
    result_ref: str | None = None
    file_summary_ref: str | None = None
    audit_ref: str | None = None

    version: int
    created_at: datetime
    updated_at: datetime
```

### 6.2 不包含 node_type / execution_role

第一版不在 TaskNode 上增加：

```python
node_type
execution_role
children_policy
completion_policy
```

原因：

- 第一版没有父子结构，`node_type` 没有实际分支价值；
- `execution_role` 会把 Agent 的自主判断提前固化为系统枚举；
- `children_policy` 暂无对象可作用；
- `completion_policy` 对扁平 TaskNode 可以由 execution status 和 TaskBus outcome 推导。

### 6.3 task_index

`task_index` 是给用户定位 TaskNode 的 UI index，不是 primary key。

要求：

- 在同一个 Plan 内唯一；
- 对用户稳定；
- 不要求全局唯一；
- 第一版只使用扁平数字：`1`, `2`, `3`。

UI 展示：

```text
Task 1
Task 2
Task 3
```

旧数据没有 `task_index` 时按当前投影顺序生成。

### 6.4 depends_on

`depends_on` 只表达 TaskNode 之间的最小依赖，不表达父子。

第一版建议：

- 默认线性依赖；
- 如果 LLM 明确指出可并行，先记录为 hint，不一定执行并行；
- TaskBus 仍可按现有能力进行顺序执行。

---

## 7. LLM Plan 输出 Contract

### 7.1 设计原则

Collaborator 输出 Plan proposal，不直接写数据库。

```text
LLM Plan JSON
  -> parse
  -> schema validation
  -> normalization
  -> authoring command
  -> Plan / TaskNode facts
```

LLM 输出不得包含：

- 数据库 id；
- published task id；
- local file path 绝对路径，除非来自明确 workspace evidence；
- tool execution result；
- audit verdict；
- 用户不可见内部状态。

### 7.2 最小 JSON shape

```json
{
  "schema_version": "plato.plan.proposal.v1",
  "title": "Personal website project plan",
  "objective": "Build a simple personal website from the user's goal.",
  "summary": "A 5-task plan covering technical setup, content pages, contact area, blog structure, and deployment.",
  "assumptions": [
    "The user wants a lightweight static website unless stated otherwise."
  ],
  "constraints": [
    "Avoid paid infrastructure unless the user confirms."
  ],
  "tasks": [
    {
      "client_task_id": "task-1",
      "task_index": "1",
      "title": "Choose technology stack and deployment approach",
      "intent": "Decide the technical stack and deployment path before building pages.",
      "summary": "Select a simple stack and hosting approach.",
      "instructions": "Review the user's goal and recommend a stack and deployment path. Record the decision in a user-readable summary.",
      "required_capability": "workspace.basic",
      "depends_on": [],
      "constraints": [],
      "acceptance_criteria": [
        "A stack recommendation is recorded.",
        "Deployment approach is documented."
      ]
    }
  ],
  "finalization": {
    "required": true,
    "summary_required": true,
    "file_rollup_required": true,
    "context_summary_required": true
  }
}
```

### 7.3 Validation rules

必须校验：

1. `schema_version` 支持。
2. `tasks` 非空。
3. `client_task_id` 在 proposal 内唯一。
4. `task_index` 在 Plan 内唯一。
5. 第一版不接受 `parent_client_task_id`。
6. 第一版不接受 `children`。
7. 第一版不接受 `node_type`、`execution_role`、`children_policy`。
8. `depends_on` 必须引用已有 `client_task_id`。
9. `depends_on` 不形成 cycle。
10. title / summary / instructions 长度满足 UI 投影限制。
11. `required_capability` 如果存在，必须是注册能力或可映射能力。

### 7.4 Normalization rules

推荐 normalization：

- trim 文本；
- 填补缺失 `summary`；
- 填补缺失 `instructions`；
- 生成缺失 `task_index`；
- 新 `PlanProposal` 中如果出现 `parent_client_task_id` / `children` /
  `node_type` / `execution_role` / `children_policy`，直接拒绝并要求重新生成扁平 Plan；
- 旧 `DraftTaskTreeProposal` / 旧 session 中已有的 children 作为 legacy
  compatibility input，按 preorder flatten 成扁平 TaskNode list。

---

## 8. UI Plan / TaskNode 状态

### 8.1 MainPageSnapshot 扩展方向

当前 Main Page 使用 `taskTree: TaskTreeView | null`。迁移目标：

```ts
type MainPageSnapshot = {
  // existing fields...
  planning: PlanningView;
  activePlan: PlanView | null;

  /**
   * Deprecated compatibility field.
   * During migration, equals activePlan.taskTreeProjection.
   */
  taskTree: TaskTreeView | null;
};
```

第一阶段可以不移除 `taskTree`，只新增 `activePlan`。

### 8.2 PlanView

```ts
type PlanView = {
  id: string;
  sessionId: string;
  title: string;
  summary: string;
  objective: string;
  status: PlanUiStatus;
  taskCount: number;
  taskNodeIds: string[];
  executionRollup: ExecutionRollupView;
  finalization: PlanFinalizationView;
  outcome: PlanOutcomeView | null;
  permissions: PlanPermissions;
  version: number;
};
```

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
```

### 8.3 Selection

Main Page 需要支持选中整个 Plan，而不只是选中 TaskNode。

```ts
type MainPageSelection =
  | { kind: "session" }
  | { kind: "plan"; planId: string }
  | { kind: "task_node"; planId: string; taskNodeId: string };
```

| Selection | Input scope | User meaning |
|---|---|---|
| `session` | session | Start or guide the session. |
| `plan` | plan | Refine the whole plan or ask plan-level question. |
| `task_node` | task | Guide selected TaskNode. |

### 8.4 TaskNodeCardView

```ts
type TaskNodeCardView = {
  id: string;
  planId: string;
  taskRef?: TaskRef | null;

  taskIndex: string;
  title: string;
  summary: string;
  orderIndex: number;

  readiness: TaskNodeReadiness;
  execution: ExecutionStatus;
  confirmation: ConfirmationStatus | null;

  badges: TaskNodeBadges;
  permissions: TaskNodePermissions;
  readonlyReason?: string | null;
  version: number;
};
```

`TaskNodeCardView` 在 Product 1.1 第一版语义上表示一个扁平 TaskNode 卡片，不表示树节点卡片。

### 8.5 UI 状态表

| Plan state | TaskNode state | Main Page work area | Detail Panel | Input target |
|---|---|---|---|---|
| no active plan | none | Empty session prompt | Session explanation | session |
| `draft` / `reviewing` | draft nodes | Plan review | Plan or TaskNode detail | plan / task |
| `published` / `running` | pending/running/done | Plan & Progress | selected TaskNode or plan progress | task if allowed |
| `finalizing` | terminal nodes | Plan finalization progress | Plan outcome building | usually disabled/read-only |
| `ready_for_review` | terminal nodes | Outcome review | Plan outcome / file rollup / audit | plan question or follow-up |
| `accepted` | terminal nodes | Accepted outcome history | Plan summary | read-only question / follow-up |
| `failed` | failed nodes | Recovery surface | failure detail | retry / revise plan |

### 8.6 Plan Overview 行

Plan Overview 不应显示内部名称 `Task Tree`。

显示优先级：

1. `PlanView.summary`
2. `PlanOutcome.summary`
3. generated fallback: `N-task plan covering A, B, and X more`
4. final fallback: `Task plan`

---

## 9. 后端持久化策略

### 9.1 最小 schema 扩展

第一阶段可以在 `authoring.sqlite` 增加 Plan 表，但保留旧 DraftTaskTree 表。

```sql
CREATE TABLE IF NOT EXISTS plans (
    session_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    source_raw_task_id TEXT,
    source_draft_tree_id TEXT,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    context_policy_json TEXT NOT NULL,
    finalization_json TEXT NOT NULL,
    outcome_json TEXT,
    version INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    PRIMARY KEY (session_id, plan_id)
);

CREATE INDEX IF NOT EXISTS idx_plans_session_updated
    ON plans(session_id, updated_at, plan_id);
```

### 9.2 TaskNode table

推荐新增 `plan_task_nodes`，避免继续加重 legacy `draft_task_nodes`。

```sql
CREATE TABLE IF NOT EXISTS plan_task_nodes (
    session_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    task_node_id TEXT NOT NULL,
    task_index TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    intent TEXT NOT NULL,
    summary TEXT NOT NULL,
    instructions TEXT NOT NULL,
    required_capability TEXT,
    depends_on_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    acceptance_criteria_json TEXT NOT NULL,
    readiness TEXT NOT NULL,
    execution TEXT NOT NULL,
    draft_ref_json TEXT,
    published_ref_json TEXT,
    result_ref TEXT,
    file_summary_ref TEXT,
    audit_ref TEXT,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, task_node_id),
    UNIQUE (session_id, plan_id, task_index)
);

CREATE INDEX IF NOT EXISTS idx_plan_task_nodes_order
    ON plan_task_nodes(session_id, plan_id, order_index, task_node_id);
```

### 9.3 Active Plan state

`authoring_active_sessions` 应增加或派生：

```sql
ALTER TABLE authoring_active_sessions ADD COLUMN active_plan_id TEXT;
```

兼容规则：

- 如果 `active_plan_id` 存在，以 Plan 为准；
- 如果不存在但 `active_draft_tree_id` 存在，Gateway 生成 synthetic Plan projection；
- 如果二者都没有，按 RawTask authoring state 投影。

---

## 10. 命令与服务边界

### 10.1 MutatePlanCommand

新增或扩展 Authoring Command：

```python
class MutatePlanCommand(BaseModel):
    command_id: str
    session_id: str
    plan_id: str | None = None
    actor: ActorRef
    causation_message_id: str | None = None
    expected_version: int | None = None
    idempotency_key: str | None = None
    operations: tuple[PlanOperation, ...]
```

```python
class PlanOperation(BaseModel):
    op: Literal[
        "create_plan",
        "update_plan_summary",
        "patch_task_node",
        "add_task_node",
        "remove_task_node",
        "reorder_task_nodes",
        "set_plan_status",
        "record_finalization",
        "record_outcome",
    ]
    payload: dict[str, object]
```

### 10.2 PublishPlanCommand

长期目标是发布 Plan，而不是发布 DraftTaskTree。

```python
class PublishPlanCommand(BaseModel):
    command_id: str
    session_id: str
    plan_id: str
    actor: ActorRef
    expected_version: int | None = None
    idempotency_key: str
    publish_options: PublishOptions = PublishOptions()
```

兼容期：

- `PublishDraftTaskTreeCommand` 继续可用；
- Gateway 接收到旧 publish command 时解析 active Plan / active DraftTaskTree；
- 如果 Plan 存在，优先走 `PublishPlanCommand`；
- 如果只有 DraftTaskTree，走 legacy path 并生成 synthetic Plan lineage。

### 10.3 PlanFinalizationService

```python
class PlanFinalizationService(Protocol):
    def should_finalize(self, plan: Plan, nodes: Sequence[TaskNode]) -> bool: ...
    def enqueue_finalization(self, session_id: str, plan_id: str) -> None: ...
    def record_outcome(self, session_id: str, plan_id: str, outcome: PlanOutcome) -> None: ...
```

第一版可以先不做异步 worker，只在 gateway/projection 中标记 `finalization.status = "not_started"` 或 `skipped`。

---

## 11. Runtime / TaskBus 执行策略

### 11.1 发布规则

第一版发布规则很简单：

```text
for each TaskNode in Plan.task_nodes ordered by order_index:
    publish one PublishedTask
```

TaskNode 的 `title`、`intent`、`summary`、`instructions`、`constraints`、`acceptance_criteria` 进入 execution context。

### 11.2 Agent 自由裁量

系统不通过 `execution_role` 控制 Task 做总结、验证、集成还是修改文件。

Agent 根据：

- TaskNode intent；
- instructions；
- acceptance criteria；
- Context Manager 提供的上下文；
- 可用 workspace capability；
- runtime policy / audit / confirmation gate；

自行决定执行步骤。

### 11.3 Plan finalization

当 Plan 内所有 required TaskNode 到达 terminal state：

```text
all TaskNodes terminal
  -> Plan finalization
  -> Outcome review
```

Plan finalization 可以由专门服务、Collaborator、reviewer Agent 或 Context Manager 支持，但第一版不把它建模为隐藏 TaskNode。

---

## 12. 旧数据兼容策略

### 12.1 兼容场景

必须支持：

1. 只有 RawTask，没有 DraftTaskTree。
2. RawTask + DraftTaskTree。
3. DraftTaskTree 已发布。
4. PublishedTask 存在，但没有 Plan。
5. dirty authoring state：RawTaskAsk pending + TaskTree exists。
6. 旧 TaskNode 没有 `task_index`。
7. 旧 LLM output 带有 children。

### 12.2 Projection compatibility

Gateway 规则：

```text
if Plan exists:
    project PlanView
elif DraftTaskTree exists:
    project synthetic PlanView from DraftTaskTree
elif PublishedTask tree exists:
    project synthetic PlanView from published task nodeage
else:
    project no active Plan
```

Synthetic Plan fields：

| Plan field | Legacy source |
|---|---|
| `plan_id` | `plan:{draft_tree_id}` or `plan:legacy:{session_id}` |
| `source_draft_tree_id` | legacy `draft_tree_id` |
| `title` | DraftTaskTree title or `Task plan` |
| `summary` | existing TaskTreeView.summary or generated fallback |
| `status` | mapped from TaskTreeView status / planning state |
| `task_node_ids` | flattened legacy nodes |

### 12.3 Legacy tree flattening

旧 DraftTaskTree 如果包含父子结构，第一版投影为扁平 TaskNode list。

推荐规则：

1. preorder flatten；
2. 如果父节点只有分组意义，不发布父节点；
3. 如果父节点有明确可执行 intent，可作为普通 TaskNode 保留；
4. child 的 inherited context 合并进 `instructions` 或 `constraints`；
5. UI 不显示树形缩进。

这条规则保护当前产品的线性工作流，避免用户同时理解 Plan、父节点、子节点三层对象。

### 12.4 Dirty authoring state

已有规则继续有效：

- Task/Plan domain active 时，pending RawTaskAsk 不显示为可操作控件。
- pending RawTaskAsk 可作为 history/audit evidence。
- late answer 不得隐式生成新 Plan。
- repair command 可以把 stale RawTaskAsk 标记为 superseded。

新增规则：

- 如果 Plan exists，Plan 优先于 DraftTaskTree 和 RawTask。
- 如果 DraftTaskTree exists 但 Plan missing，允许 synthetic Plan。
- 如果 RawTask converted 但 Plan/DraftTaskTree missing，显示 recoverable diagnostic。

### 12.5 数据迁移策略

#### Phase M0: Projection-only

- 不迁移数据库。
- Gateway 从 legacy DraftTaskTree 生成 PlanView。
- 前端可开始使用 `activePlan`。
- `taskTree` 保留兼容。

#### Phase M1: Dual-write new Plan

- 新 Collaborator proposal 写入 Plan + TaskNode。
- 同时保留 legacy DraftTaskTree 投影或 lineage。
- Publish path 同时支持 Plan 和 DraftTaskTree。

#### Phase M2: Backfill existing active data

- 对 active DraftTaskTree 生成 persistent Plan。
- 保留 source linkage。
- 不删除旧表。

#### Phase M3: Legacy read-only

- DraftTaskTree 只作为 lineage/history。
- 新 UI/API 只读 Plan。

---

## 13. 实施切片建议

### P11.1 Docs / Contract alignment

- 本文档。
- 更新 UI API Contract 的 `PlanView` / `TaskNodeCardView` 草案。
- 更新 ViewModel Contract 的 `activePlan` 草案。

### P11.2 Backend projection-only PlanView

- 不改持久化。
- `DraftTaskTree -> synthetic PlanView`。
- Flatten legacy tree。
- Main Page 继续可显示 Plan Overview / TaskNode list。

### P11.3 LLM Plan Proposal schema

- 定义 `PlanProposal` / `PlanTaskNodeProposal` Pydantic 模型。
- Collaborator 输出改为 Plan proposal。
- 新 Plan proposal 拒绝 children；legacy DraftTaskTree input 兼容 flatten。
- proposal validation / normalization 单元测试。

### P11.4 Plan store and TaskNode store

- 新增 SQLite tables。
- Store protocol + implementation。
- Reopen / migration / version conflict tests。

### P11.5 Authoring command integration

- `MutatePlanCommand`。
- `create_plan`、`patch_task_node`、`set_plan_status`。
- 保持 batch/idempotency。

### P11.6 PublishPlanCommand

- Plan -> PublishedTask mapping。
- Legacy PublishDraftTaskTree 兼容。
- 顺序执行为默认策略。

### P11.7 Plan finalization and outcome review

- Plan finalization service。
- PlanOutcome projection。
- Main Page Outcome Review 状态。

### P11.8 Future hierarchy research gate

只有在用户场景证明扁平 TaskNode 不够用后，才重新评估：

- parent/child TaskNode；
- node_type；
- children_policy；
- parent summary task；
- tree UI；
- subtree file rollup。

---

## 14. 测试策略

### 14.1 Contract tests

- PlanProposal JSON happy path。
- duplicate task_index。
- invalid depends_on。
- cycle in depends_on。
- new PlanProposal children output rejected。
- legacy DraftTaskTree children input flattened for PlanView。
- legacy DraftTaskTree maps to PlanView。
- PlanView and TaskTreeView compatibility。

### 14.2 Store tests

- create/get/list Plan。
- create Plan with TaskNode list。
- reopen persistence。
- version conflict。
- task_index uniqueness。
- old authoring.sqlite without plans table migrates safely。

### 14.3 Publish tests

- each TaskNode publishes one PublishedTask。
- order_index is preserved。
- legacy publish command still works。
- dependencies are preserved when present。

### 14.4 UI tests

- no Plan => session input。
- Plan selected => plan input。
- TaskNode selected => task input。
- Plan Overview shows `PlanView.summary`。
- task_index visible and stable。
- legacy tree displays as flat TaskNode list。

### 14.5 Compatibility tests

- dirty authoring state still hidden from active controls。
- late RawTaskAsk answer rejected or routed to explicit guidance command。
- existing sessions without Plan still load。
- existing published sessions still show Plan & Progress。

---

## 15. Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Plan duplicates DraftTaskTree too early. | Model confusion and extra persistence burden. | Start projection-only, then dual-write. |
| Flat TaskNode cannot express enough structure. | Some complex plans lose hierarchy. | Preserve instructions/constraints and defer hierarchy behind a research gate. |
| LLM emits tree output anyway. | New Plan proposal rejected; legacy DraftTaskTree compatibility input flattened. | Validator handles children as unsupported v1 feature and projection keeps old sessions readable. |
| Old sessions look different. | Product trust issue. | Synthetic Plan projection and compatibility tests. |
| Plan finalization becomes hidden work. | User does not understand post-task delay. | Show `finalizing` state and user-readable progress. |

---

## 16. Open Questions

1. Plan 是否需要独立 Audit summary，还是先复用 session/task audit rollup？
2. Plan finalization 第一版是 deterministic projection，还是调用 Collaborator/reviewer Agent？
3. Plan history 在 Main Page 何时可见？Product 1.1 是否只显示 active Plan？
4. 旧 DraftTaskTree 是否需要后台 backfill，还是长期 projection-only 足够？
5. 如果 LLM 持续输出 children，是否需要在 prompt / repair UI 上提示用户重新生成更扁平的 Plan？

---

## 17. 第一版验收标准

第一版技术实现完成后，应满足：

1. 新 Collaborator 产出 Plan proposal。
2. Plan proposal 能被验证、规范化，并生成 PlanView。
3. Plan 内使用扁平 TaskNode list。
4. TaskNode 显式携带稳定 `task_index`。
5. 不实现 `node_type`、`execution_role`、`children_policy` 或父子 TaskNode。
6. 旧 DraftTaskTree session 仍能正常显示为 Plan。
7. UI 能选中 session / plan / task_node。
8. Plan Overview 展示用户可理解的 plan summary。
9. dirty authoring state 不重新污染 active controls。
10. 旧 publish flow 不被破坏。
