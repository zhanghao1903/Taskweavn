# Feature Plan: Task 领域模型与 UI ViewModel 分层

> Status: done / accepted
> Type: 新特性支持 / 架构规划
> Last Updated: 2026-05-14
> Owner/Session: planning session
> Target Implementation Session: independent feature session
> Related Docs: `docs/architecture/task.md`, `docs/architecture/task-domain-ui-model-separation.md`, `docs/plans/task-first-ui-interaction.md`, `docs/plans/ui/ui-api-interfaces.md`, `docs/plans/feature/collaborator-agent-task-authoring.md`

---

## 1. 背景

Task 是 TaskWeavn 的核心对象。当前架构里的 `Task` 更偏后端系统设计：它服务于 TaskBus 调度、Agent 执行、状态机和审计。

但 Task-first UI 对 Task 有更多交互需求：

- Task 要展示成卡片，里面有状态、摘要、可选项、确认动作、badge。
- 用户需要在卡片内追加补充信息和指导意见。
- Task 卡片需要有临时 UI 状态，例如 selected、expanded、unread、editing、pending local input。
- 后端 Task 有些字段不应直接展示，例如内部调度信息、错误细节、原始 payload。
- 前端展示需要聚合 MessageStream、Confirmation、File Change、Summary，而这些不全是后端 Task 自身字段。

因此需要尽早规划：**后端 Task 领域实体和前端 Task UI 对象是否应该分开**。

本计划的结论是：应该分开。

---

## 2. 目标

1. 明确 `Task` 领域模型与 `TaskCardView` / `TaskNodeViewModel` 的边界。
2. 定义 UI 需要的 Task 卡片能力：
   - 可选项 / 确认动作
   - 用户补充信息入口
   - 状态、badge、摘要、文件变更、消息聚合
3. 定义哪些信息属于后端事实，哪些属于 UI 临时状态。
4. 设计 projection / adapter 层，把后端 Task + 消息 + 文件 + 确认动作投影成 UI ViewModel。
5. 为 Collaborator Agent、Task Authoring Tools、UI API 提供一致的数据模型方向。

---

## 3. 非目标

- 不在本计划中实现前端组件。
- 不改变 TaskBus 的极简状态机。
- 不把所有 UI 状态持久化到后端。
- 不在第一版中设计完整 diff viewer。
- 不引入 DAG Task 拓扑，当前仍是 Tree List。
- 不决定最终 API 传输协议。

---

## 4. 核心决策

### 4.1 后端 Task 是领域实体

后端 `Task` 应继续保持小而稳定：

```python
Task:
  id
  parent_id
  intent
  required_capability
  status
  result
  created_at
  created_by
  started_at
  completed_at
  error
```

它回答的是：

- 这个工作是什么？
- 谁能执行它？
- 当前处于哪个调度状态？
- 执行结果是什么？

它不应该直接回答：

- 卡片是否展开？
- 是否被用户选中？
- 是否有未读 UI 消息？
- 卡片里按钮怎么排？
- 是否正在编辑输入框？

### 4.2 前端使用 Task UI ViewModel

UI 应使用独立对象，例如：

- `TaskNodeViewModel`
- `TaskCardView`
- `TaskDetailView`

它回答的是：

- 这个 Task 如何展示？
- 用户现在能点什么？
- 这个卡片有哪些确认动作？
- 这个 Task 相关消息、文件、摘要如何聚合？
- 当前 UI 是否选中、展开、正在编辑？

### 4.3 中间使用 Projection 层

UI ViewModel 不应由前端自己拼所有数据，也不应污染后端 Task。

需要一个投影层：

```text
Task
  + MessageStream
  + ConfirmationAction
  + FileChangeSummary
  + TaskSummary
  + UI local state
  → TaskCardView
```

这个 projection 可以在后端 API 层、前端 store 层，或两者组合实现。第一版先定义接口，不绑定实现位置。

---

## 5. 三类对象边界

### 5.1 TaskDomain

系统事实源，服务调度和执行。

| 字段类型 | 示例 |
|---|---|
| identity | `id`, `parent_id` |
| execution intent | `intent`, `required_capability` |
| state machine | `pending`, `running`, `done`, `failed` |
| execution result | `result`, `error`, timestamps |
| audit | `created_by`, `created_at` |

### 5.2 TaskViewData

后端或 API 聚合出来的展示数据，来自多个事实源，但不是临时 UI 状态。

| 字段类型 | 示例 |
|---|---|
| display text | `title`, `subtitle`, `intent_preview` |
| badges | `has_pending_confirmation`, `unread_count`, `file_change_count` |
| actions | `available_actions`, `confirmation_options` |
| aggregates | `message_summary`, `file_summary`, `children_progress` |
| permissions | `can_edit`, `can_append_message`, `can_publish`, `can_retry` |

### 5.3 TaskUIState

只属于当前前端会话或 UI store，不应该进入 TaskBus。

| 字段类型 | 示例 |
|---|---|
| visual state | `selected`, `expanded`, `focused`, `hovered` |
| local editing | `editing_title`, `draft_note`, `pending_patch` |
| client-side cache | `last_seen_message_id`, `optimistic_update_id` |
| layout | `tree_depth`, `visible_index`, `collapsed_children_count` |

---

## 6. Task Card ViewModel 草案

第一版建议：

```python
class TaskCardView(BaseModel):
    task_id: str
    parent_id: str | None
    title: str
    intent_preview: str
    status: Literal["draft", "pending", "running", "done", "failed", "cancelled"]
    depth: int
    order_index: int

    badges: TaskCardBadges
    permissions: TaskCardPermissions
    primary_actions: list[TaskCardAction]
    confirmation: ConfirmationActionView | None = None
    latest_message: SessionMessageView | None = None
    file_summary: TaskFileChangeSummary | None = None
    progress: TaskProgressView | None = None
```

### 6.1 TaskCardBadges

```python
class TaskCardBadges(BaseModel):
    pending_confirmation_count: int = 0
    unread_message_count: int = 0
    file_change_count: int = 0
    child_count: int = 0
    failed_child_count: int = 0
    risk_level: str | None = None
```

### 6.2 TaskCardPermissions

```python
class TaskCardPermissions(BaseModel):
    can_edit: bool
    can_append_guidance: bool
    can_resolve_confirmation: bool
    can_publish: bool
    can_cancel: bool
    can_retry: bool
```

### 6.3 TaskCardAction

```python
class TaskCardAction(BaseModel):
    action_id: str
    label: str
    kind: Literal["confirm", "edit", "append_guidance", "publish", "cancel", "retry", "open_detail"]
    disabled: bool = False
    reason: str | None = None
```

---

## 7. 卡片内确认动作

Task 卡片内的“可选项”不应该存进后端 Task 本体，而应来自 Confirmation / Actionable Message。

推荐模型：

```python
class ConfirmationActionView(BaseModel):
    confirmation_id: str
    task_id: str
    prompt: str
    options: list[ConfirmationOptionView]
    default_option_id: str | None
    risk_summary: str | None
    status: Literal["pending", "resolved", "expired"]
```

```python
class ConfirmationOptionView(BaseModel):
    option_id: str
    label: str
    description: str | None = None
    value: str
    is_default: bool = False
```

来源：

- AutonomyGate / WaitCoordinator 产生确认动作
- Collaborator Agent 产生 Task authoring options
- MessageStream 记录 pending / resolved 状态

投影规则：

- 卡片最多展示一个主确认动作，其余进入 detail。
- resolved confirmation 进入历史，不再作为主按钮。
- 确认结果必须写回 Session Message Stream。

---

## 8. 卡片内用户补充信息

用户在 Task 卡片内输入的补充信息，不应直接修改后端 Task 字段。

它应该进入 Task-scoped Message：

```python
class TaskGuidanceInput(BaseModel):
    session_id: str
    task_id: str
    content: str
    mode: Literal["guidance", "constraint", "clarification", "correction"]
```

处理路径：

```text
User types guidance in Task Card
  → appendTaskMessage(session_id, task_id, content, mode)
  → MessageStream append
  → Collaborator Agent or running Agent sees it in next context
  → optional TaskNodePatch / confirmation / follow-up task
```

状态约束：

| Task 状态 | 补充信息行为 |
|---|---|
| `draft` | 可转成 TaskNodePatch，更新 draft node |
| `pending` | 可转成 TaskNodePatch，更新未执行计划 |
| `running` | 追加为 guidance，不直接覆盖 Task；影响后续推理 |
| `done` | 不追加到原 Task；建议创建 follow-up |
| `failed` | 建议创建 retry/fix Task |

---

## 9. 后端 Task 不应显示全部字段

后端字段需要经过显示策略：

| 后端字段 | UI 展示策略 |
|---|---|
| `id` | 可隐藏，调试模式展示 |
| `parent_id` | 用于拓扑，不直接显示 |
| `intent` | 摘要展示，详情可展开 |
| `required_capability` | 普通用户可隐藏，高级/调试模式展示 |
| `status` | 显示为友好状态和颜色 |
| `result` | 显示 summary，不显示原始结构 |
| `error` | 显示用户可理解摘要；原始 stack 进入日志/调试 |
| timestamps | 卡片可隐藏，详情展示 |
| `created_by` | 可显示为 user / collaborator / agent |

这避免 UI 被后端实现细节污染。

---

## 10. Projection API 需求

### 10.1 TaskProjectionService

```python
class TaskProjectionService:
    def get_task_card(self, session_id: str, task_id: str) -> TaskCardView: ...
    def list_task_cards(self, session_id: str, root_id: str | None = None) -> list[TaskCardView]: ...
    def get_task_detail(self, session_id: str, task_id: str) -> TaskDetailView: ...
    def project_tree(self, session_id: str) -> TaskTreeView: ...
```

### 10.2 Projection 输入源

| 输入源 | 用途 |
|---|---|
| Task Store / TaskBus materialized view | Task 基础信息和状态 |
| DraftTaskStore | draft task 信息 |
| MessageStream | latest message、unread、guidance、confirmation history |
| Confirmation Store / actionable messages | pending confirmation |
| FileChange Store | 文件变更 badge 和 summary |
| Task Summary Store | 完成/失败摘要 |
| UI State Store | selected/expanded/local draft |

注意：UI State Store 只提供当前展示状态，不属于后端事实源。后端重现 Task 交互历史时不依赖它。

### 10.3 Projection 输出约束

- 不泄漏后端内部字段。
- 不把 UI local state 写回 Task Domain。
- 投影结果可缓存，但必须能通过事件增量更新。
- 卡片列表必须支持 Tree List 顺序和 depth。

---

## 11. Task Interaction Replay

把 UI ViewModel 从后端 Task 中拆出来，不代表后端丢失用户与 Task 的交互历史。相反，后端必须能根据 `task_id` / `draft_task_id` / `session_id` 重现完整 Task 交互时间线。

### 11.1 重现目标

后端应能重现：

```text
Task T3
  ├─ 初始 intent
  ├─ draft 阶段创建与修改历史
  ├─ 用户补充信息和指导意见
  ├─ Collaborator Agent 建议
  ├─ 确认动作
  ├─ 用户选择或自然语言确认
  ├─ 发布事件
  ├─ 执行状态变化
  ├─ 文件变更摘要
  └─ 最终结果 / 失败原因
```

这些历史不应该全部塞入 `Task` 本体，而是由多个事实源按时间聚合。

### 11.2 TaskInteractionTimeline

建议新增后端查询模型：

```python
class TaskInteractionTimeline(BaseModel):
    session_id: str
    task_id: str | None = None
    draft_task_id: str | None = None
    domain_task: TaskDomain | None = None
    draft_task: DraftTaskNode | None = None
    entries: list[TaskInteractionEntry]
```

```python
class TaskInteractionEntry(BaseModel):
    entry_id: str
    occurred_at: datetime
    source: Literal["draft", "message", "confirmation", "event", "file", "summary"]
    kind: str
    actor: str | None
    summary: str
    payload_ref: str | None = None
```

第一版 `payload_ref` 可以只是原始 message/event id，避免 timeline 复制大 payload。

### 11.3 Timeline 输入源

| 输入源 | 重现内容 |
|---|---|
| `DraftTaskStore` | draft 创建、patch、版本变化、accept/publish |
| `MessageStream` | 用户补充、协作者回复、Task-scoped 消息、确认结果 |
| `ConfirmationAction` / actionable message | pending/resolved confirmation、选项、默认行为 |
| `EventStream` | Task 创建、发布、状态变化、Action/Observation、执行结果 |
| `FileChange Store` | 文件变更及摘要 |
| `Task Summary Store` | 任务总结、失败摘要、后续建议 |

### 11.4 TaskInteractionSnapshot

除时间线外，后端还可以提供快照：

```python
class TaskInteractionSnapshot(BaseModel):
    task_card: TaskCardView
    task_detail: TaskDetailView
    timeline: TaskInteractionTimeline
```

用途：

- UI 打开 Task Detail 时一次性加载完整上下文。
- 调试和用户测试时复盘某个 Task 的全部交互。
- 后续 RAG / summarization 可以用 timeline 作为输入。

### 11.5 约束

- 所有用户补充信息必须进入 `MessageStream`，不能只留在前端输入框。
- 所有确认动作必须有 pending/resolved 历史。
- 所有 draft 修改必须记录版本和来源。
- 发布时要保留 draft node id 到 published task id 的映射。
- UI local state 不参与 replay；它只影响当前视觉状态。

---

## 12. UI Local State Store

前端需要自己的临时状态：

```typescript
type TaskUiState = {
  selectedTaskId?: string
  expandedTaskIds: Set<string>
  focusedTaskId?: string
  draftInputs: Record<TaskId, string>
  optimisticPatches: Record<TaskId, TaskNodePatch>
  lastSeenMessageIds: Record<TaskId, MessageId>
}
```

这些数据：

- 可以在前端内存中。
- 可以持久化到浏览器 local storage。
- 不应进入 TaskBus。
- 不应影响 EventStream replay 的系统状态。

后续如果需要跨设备恢复 UI 状态，可以单独设计 `UserPreferenceStore`，不要混入 Task。

---

## 13. 与 Draft Task 的关系

Collaborator Agent 计划中定义了 `DraftTaskNode`。它和本计划的关系：

| 对象 | 作用 |
|---|---|
| `DraftTaskNode` | 未发布任务的后端草案数据 |
| `Task` | 已发布任务的后端领域数据 |
| `TaskCardView` | UI 展示数据，可投影 draft 或 published task |
| `TaskUIState` | 前端临时交互状态 |

同一个 Task 卡片可以来自：

- DraftTaskNode：状态 `draft`
- Task：状态 `pending/running/done/failed`

UI 不应该关心底层来自哪个 store；projection 层统一输出 `TaskCardView`。

发布时需要持久化映射关系：

```text
draft_task_id -> published_task_id
```

这样 `TaskInteractionTimeline` 可以把 draft 阶段和 published 阶段串起来。

---

## 14. 与现有 UI API 的关系

当前 `docs/plans/ui/ui-api-interfaces.md` 已经有：

- `TaskNodeSummary`
- `TaskNodeDetail`
- `ConfirmationActionView`
- `TaskFileChangeSummary`
- `TaskSummaryView`

本计划建议把这些模型升级成更清晰的层次：

| 现有名称 | 建议演进 |
|---|---|
| `TaskNodeSummary` | `TaskCardView` 或 `TaskNodeSummaryView` |
| `TaskNodeDetail` | `TaskDetailView` |
| `ConfirmationActionView` | 保留，作为卡片内确认区域来源 |
| `TaskFileChangeSummary` | 保留，作为卡片 badge/detail 来源 |
| `TaskSummaryView` | 保留，作为完成态展示来源 |

后续需要更新 UI API 文档，使它明确：

- API 返回 UI ViewModel，不直接返回后端 Task。
- 领域 Task 通过 domain API 或调试 API 查看。
- 卡片操作通过 command API 转成 message / patch / confirmation resolution。
- 后端需要提供 Task interaction timeline / snapshot，用于重现用户与 Task 的全部交互。

---

## 15. 执行切片

### Slice 1: Model Boundary Design

产出：

- `TaskDomain` / `DraftTaskNode` / `TaskCardView` / `TaskUIState` 边界文档
- 更新 UI API 文档中的视图模型名称和说明

验收：

- 文档明确哪些字段属于 domain，哪些属于 view，哪些属于 local UI。
- 不再把 Task 卡片字段塞进后端 Task。
- 文档明确后端仍必须能通过事实流重现完整 Task 交互历史。

### Slice 2: ViewModel Schemas

产出：

- `TaskCardView`
- `TaskCardBadges`
- `TaskCardPermissions`
- `TaskCardAction`
- `TaskDetailView`
- `TaskProgressView`

验收：

- 可以表达 Task 卡片、确认动作、用户补充入口、badge 和权限。
- 可以同时投影 draft task 和 published task。

### Slice 3: Projection Service

产出：

- `TaskProjectionService`
- `get_task_card`
- `list_task_cards`
- `get_task_detail`
- `project_tree`

验收：

- 能从 Task + Message + Confirmation + FileSummary 聚合出卡片。
- 父节点文件汇总仍遵守 recursive aggregation，不改变子节点直接归属。
- projection 不修改 domain 数据。

### Slice 4: Command Mapping

产出：

- 卡片按钮到命令的映射：
  - confirm option → `resolveConfirmation`
  - append guidance → `appendTaskMessage`
  - edit draft/pending → `updateTaskNode`
  - publish → `publishTaskTree`
  - retry → `retryTask`

验收：

- 卡片操作不直接 mutate 后端 Task。
- running/done/failed 的操作遵守状态权限。

### Slice 5: Task Interaction Timeline

产出：

- `TaskInteractionTimeline`
- `TaskInteractionEntry`
- `TaskInteractionSnapshot`
- draft task id 到 published task id 映射查询

验收：

- 能按 `TaskRef` 聚合用户补充、确认动作、事件、文件摘要和总结。
- 能串联 draft 阶段和 published 阶段。
- timeline 按时间排序。
- timeline 不依赖 UI local state。

### Slice 6: UI API Doc Alignment

产出：

- 更新 `docs/plans/ui/ui-api-interfaces.md`
- 明确 API 返回 `TaskTreeView` / `TaskCardView` / `TaskDetailView`
- 明确命令返回 `CommandResult`
- 明确 timeline/snapshot 查询接口
- 明确 `TaskRef` 是 UI/API 边界默认引用

验收：

- UI API 文档不再暗示返回裸后端 Task。
- `listTaskMessages` 明确是 Session Message Stream 的过滤视图。
- UI local state 明确不进入后端事实源。

### Slice 7: Tests and Docs

产出：

- projection 单元测试
- timeline/replay 单元测试
- command mapping 测试
- UI API 文档更新

验收：

- draft task card 投影测试
- running task guidance 投影测试
- pending confirmation 卡片测试
- TaskInteractionTimeline 重现用户补充和确认动作测试
- done task 只读测试

---

## 16. 测试计划

本分支不适合作为完整用户测试分支。它交付的是后端 Task 领域边界、ViewModel、projection、command mapping 和 replay timeline；真实用户用例需要等 Task-first UI 原型完成后，才能验证“自然语言输入 -> Task Tree 展示 -> 选择 Task Node -> 补充/确认 -> 发布/执行 -> 查看文件和总结”的完整体验。

因此本分支的验收以 contract / projection / replay 测试为主：

| 场景 | 期望 |
|---|---|
| DraftTaskNode 投影 | 生成可编辑 TaskCardView，包含 publish/edit action |
| pending Task 投影 | 可编辑或可取消，取决于权限 |
| running Task 投影 | 可 append guidance，可处理 confirmation，不可直接改 intent |
| done Task 投影 | 只读，显示 summary 和 file changes |
| pending confirmation | 卡片显示主确认动作和 options |
| task guidance input | 生成 appendTaskMessage command |
| task guidance replay | 后端 timeline 能看到用户补充信息 |
| confirmation replay | 后端 timeline 能看到确认动作、选项和用户选择 |
| draft to published replay | timeline 能串联 draft_task_id 和 published task_id |
| UI selected/expanded | 只影响 TaskUIState，不影响后端 Task |
| 后端 error 字段 | UI 显示摘要，不泄漏原始调试细节 |

后续 UI 完善后，需要补充至少一个端到端 user case：

```text
User intent
  -> Collaborator Agent generates Draft Task Tree
  -> UI renders Task cards
  -> User selects one Task Node
  -> User appends guidance or resolves a confirmation
  -> Task Tree is published
  -> Execution updates messages, file summary, and TaskInteractionTimeline
  -> User opens completed Task detail and reviews immutable history
```

---

## 17. 风险与决策点

| 风险 | 处理 |
|---|---|
| 模型分层过多 | 第一版只落 `TaskCardView` 和 `TaskDetailView` 两个主 ViewModel |
| 前端重复后端逻辑 | 复杂聚合放到 projection service，前端只持有 local UI state |
| 后端 Task 被 UI 需求污染 | 明确禁止 selected/expanded/editing 等字段进入 Task Domain |
| 用户补充信息语义不清 | 统一走 Task-scoped Message，再由 Collaborator 或 Agent 解释 |
| 可选项来源混乱 | 统一来自 ConfirmationActionView / actionable message |
| draft 和 published task 混淆 | projection 输出统一卡片，底层 store 保持分离 |
| 拆分 UI ViewModel 后丢失交互历史 | 所有交互事实进入 MessageStream / Confirmation / EventStream / Draft history，并提供 TaskInteractionTimeline |

---

## 18. 完成标准

该 plan 完成时，应满足：

- 明确后端 `Task` 与 UI `TaskCardView` 是不同实体。
- Task 卡片能表达可选项、确认动作、用户补充信息入口和状态权限。
- UI 临时状态有独立 `TaskUIState`，不污染 TaskBus / EventStream。
- 有 projection 层把 Task + Message + Confirmation + FileChange 聚合成 UI ViewModel。
- 后端能通过 TaskInteractionTimeline 重现该 Task 的用户补充、确认动作、选择结果、draft 修改和发布事件。
- DraftTaskNode 和 published Task 都能投影成统一 TaskCardView。
- draft_task_id 到 published_task_id 的映射可查询。
- UI API 文档更新为“返回 ViewModel，而不是直接返回后端 Task”。

---

## 19. 状态

- Status: done / accepted
- Created: 2026-05-10
- Started: 2026-05-13
- Accepted: 2026-05-14
- Technical Design: [Task Domain And UI ViewModel Separation](../../architecture/task-domain-ui-model-separation.md)
- Current Branch: `codex/task-domain-ui-model-design`
- Completed in first implementation pass:
  - Slice 1 Model Boundary And Protocols.
  - Added `taskweavn.task` package with:
    - `TaskRef`
    - `TaskDomain`
    - `TaskDispatchConstraints`
    - `TaskNodePatch`
    - `DraftTaskNode`
    - `DraftTaskTree`
    - `DraftToPublishedMapping`
    - `TaskStore` Protocol
    - `DraftTaskStore` Protocol
  - Added tests for model validation, immutability, draft tree root constraints, lineage mapping, and Protocol conformance.
- Completed in second implementation pass:
  - Slice 2 ViewModel Schemas.
  - Added Task-first UI projection models:
    - `TaskTreeView`
    - `TaskCardView`
    - `TaskDetailView`
    - `TaskCardBadges`
    - `TaskCardPermissions`
    - `TaskCardAction`
    - `TaskProgressView`
    - `ConfirmationActionView`
    - `ConfirmationOptionView`
    - `SessionMessageView`
    - `TaskFileChangeSummary`
    - `TaskSummaryView`
  - Added tests for card validation, confirmation default options, duplicate tree refs, detail grouping, progress counts, and frozen ViewModels.
- Completed in third implementation pass:
  - Slice 3 Projection Service.
  - Added `DefaultTaskProjectionService` plus protocols:
    - `TaskProjectionService`
    - `FileChangeStore`
    - `TaskSummaryStore`
  - Projection now supports:
    - deterministic topological preorder for published Task trees;
    - draft tree projection into editable Task cards;
    - status-based permission/action resolution;
    - latest task message and pending confirmation projection from MessageStream;
    - direct/subtree file change summary aggregation through `FileChangeStore`;
    - result summary aggregation through `TaskSummaryStore`;
    - Task detail assembly for messages, confirmations, file changes, constraints, and result summary.
  - Added tests for preorder projection, draft cards, permissions by status, message/confirmation/file/summary aggregation, missing-task errors, and Protocol conformance.
- Completed in fourth implementation pass:
  - Slice 4 Command Mapping.
  - Added `DefaultTaskCommandService` plus command boundary protocols:
    - `TaskCommandService`
    - `PublishedTaskEditor`
    - `TaskPublisher`
  - Added command result models:
    - `CommandResult`
    - `TaskPublishResult`
  - Command mapping now supports:
    - draft Task patching through `DraftTaskStore`;
    - pending published Task patching through an injected `PublishedTaskEditor`;
    - task-scoped user guidance messages through `MessageBus`;
    - confirmation resolution by publishing a response message;
    - draft tree publication through an injected `TaskPublisher`;
    - failed Task retry through the same publisher boundary.
  - Added tests for status-based rejection, draft/published edit boundaries, message publishing, confirmation response publishing, draft Task confirmation refs, publish/retry boundaries, and Protocol conformance.
- Completed in fifth implementation pass:
  - Slice 5 Interaction Timeline.
  - Added `DefaultTaskInteractionTimelineService` plus timeline protocols/models:
    - `TaskInteractionTimelineService`
    - `DraftPublicationStore`
    - `TaskInteractionEntry`
    - `TaskInteractionTimeline`
    - `TaskInteractionSnapshot`
  - Timeline now supports:
    - draft creation/update/publish entries;
    - task-scoped message entries;
    - actionable/response messages as confirmation created/resolved entries;
    - EventStream task entries through `iter_for_task` when available;
    - file change entries;
    - result summary entries;
    - published Task timelines stitched back to draft history through draft-to-published mappings;
    - snapshot assembly from Task detail projection + timeline.
  - Added `recorded_at` to `TaskFileChangeSummary` and `updated_at` to `TaskSummaryView` so file/summary facts can participate in deterministic replay ordering.
  - Added tests for draft timelines, published timelines with draft stitching, event/file/summary ordering, timeline limit, snapshot assembly, and Protocol conformance.
- Completed in sixth implementation pass:
  - Slice 6 UI API Doc Alignment.
  - Rewrote `docs/plans/ui/ui-api-interfaces.md` to align with the implemented Phase 3C server-core contracts.
  - UI API docs now state that:
    - query APIs return ViewModels instead of raw backend `TaskDomain`;
    - `TaskRef(kind, id)` is the default UI/API Task reference;
    - `TaskTreeView`, `TaskCardView`, `TaskDetailView`, `CommandResult`, `TaskInteractionTimeline`, and `TaskInteractionSnapshot` are first-class API shapes;
    - `listTaskMessages` remains a filtered view over the single Session Message Stream;
    - Task file rollups preserve direct child ownership;
    - UI local state does not enter TaskBus, EventStream, MessageStream, or timeline replay.
- Completed in seventh implementation pass:
  - Slice 7 Tests and Docs.
  - Reconciled the implementation with architecture and UI API docs.
  - Added a release record for the Task Domain/UI ViewModel Separation feature.
  - Updated roadmap/project roadmap to mark Phase 3C's first package as ready for acceptance.
  - After merge/acceptance, follow-up docs mark this package as done and Collaborator Agent as the active Phase 3C package.
  - Tightened `TaskInteractionTimeline` cursor semantics so pagination resumes after the returned entry in chronological order instead of comparing UUID strings.
  - Added a cursor-resume timeline regression test.
- Verified:
  - `uv run pytest tests/test_task_models.py tests/test_task_store_protocols.py tests/test_task_views.py tests/test_task_projection.py tests/test_task_commands.py tests/test_task_timeline.py`
  - `uv run ruff check src/taskweavn/task tests/test_task_models.py tests/test_task_store_protocols.py tests/test_task_views.py tests/test_task_projection.py tests/test_task_commands.py tests/test_task_timeline.py`
  - `uv run mypy src/taskweavn/task tests/test_task_models.py tests/test_task_store_protocols.py tests/test_task_views.py tests/test_task_projection.py tests/test_task_commands.py tests/test_task_timeline.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest` — 494 passed, 1 warning
  - `git diff --check`
- Latest verification:
  - `uv run pytest` in `docs/user_cases/workspace/user-test-cli` — 24 passed
  - `uv run pytest tests/test_task_timeline.py` — 5 passed, 1 warning
  - `uv run ruff check src/taskweavn/task tests/test_task_timeline.py`
  - `uv run mypy src/taskweavn/task tests/test_task_timeline.py`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest` — 495 passed, 1 warning
  - `git diff --check`
- User-case acceptance note:
  - 本阶段不做新的端到端 user case 验收；当前工作是 server-core Task/ViewModel contract。
  - 已回归旧的 UC-005 生成项目测试，确认之前的用户测试产物没有因本分支破坏。
  - UC-001-UC-004 仍保留为手工/LLM 用户测试用例，等待 Task-first UI 或后续需要时再运行。
- Next Step: 已进入 Collaborator Agent / Task authoring tools 阶段。
