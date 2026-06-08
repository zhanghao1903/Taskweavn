# Feature Plan: Pipeline Task 自动装载与指定 Agent 调度

> Status: planned  
> Type: 新特性支持  
> Last Updated: 2026-05-10  
> Owner/Session: planning session  
> Target Implementation Session: independent feature session  
> Related Docs: `docs/architecture/task.md`, `docs/architecture/bus.md`, `docs/architecture/agent.md`, `docs/plans/configuration.md`, `docs/plans/feature/collaborator-agent-task-authoring.md`

---

## 1. 背景

当前 Task 主要由用户输入、Collaborator Agent、或执行中的 Agent 创建。用户想要一种更稳定的“流水线任务”能力：在发布任务时，系统自动装载一组预定义任务，例如：

- 发布前先跑检查 / 环境分析 / 计划审计
- 正式开始时先跑初始化 / 上下文整理
- 主任务结束后自动跑总结 / 测试 / 文件变更汇总 / 用户报告

这些任务不应该成为特殊对象，也不应该绕过 TaskBus。它们本质上仍然是普通 Task，只是在特定生命周期点由系统按配置自动 publish。

本计划目标是定义 Pipeline Task 的配置、上下文、装载时机、Agent 指定能力，以及与 TaskBus 的关系。

---

## 2. 目标

1. 支持用户在发布任务时配置三类流水线任务清单：
   - `task_before`
   - `task_begin`
   - `task_after`
2. 三类任务都转换为普通 Task，并走正常 TaskBus。
3. 支持配置文件声明 pipeline tasks。
4. 支持每个 pipeline task 指定 capability 或特定 Agent Template。
5. 支持不同阶段使用不同上下文：
   - `task_before` / `task_begin`：使用用户输入 + 生成的 Task Trees 作为上下文
   - `task_after`：使用会话内容作为上下文，且允许用户配置上下文范围
6. 保持 TaskBus 仍是状态权威；Pipeline Loader 只负责自动发布，不负责执行。

---

## 3. 非目标

- 不引入新的 PipelineTask 运行时对象。
- 不绕过 TaskBus 执行任务。
- 不实现并发流水线调度。
- 不把 pipeline 做成外部 CI/CD 系统。
- 不在第一版中支持复杂 DAG；仍然基于 Task Tree List。
- 不在第一版中实现 UI 可视化编辑器，只设计配置和 API。

---

## 4. 核心概念

### 4.1 PipelineTaskSpec

Pipeline 配置项不是运行时任务，而是生成 Task 的模板：

```python
class PipelineTaskSpec(BaseModel):
    id: str
    title: str
    intent_template: str
    required_capability: str
    agent_ref: str | None = None
    context_policy: PipelineContextPolicy
    enabled: bool = True
    order: int = 0
```

运行时：

```text
PipelineTaskSpec + Context → Task(intent, required_capability, dispatch_constraints)
```

### 4.2 PipelineStage

```python
PipelineStage = Literal["task_before", "task_begin", "task_after"]
```

语义：

| Stage | 装载时机 | 上下文 |
|---|---|---|
| `task_before` | 用户确认发布前，或发布流程的 preflight 阶段 | 用户输入 + Draft/Generated Task Trees |
| `task_begin` | 主任务正式进入 TaskBus 前，作为准备任务发布 | 用户输入 + Generated/Accepted Task Trees |
| `task_after` | 主任务树完成后 | 会话内容 + Task 结果 + 文件变更 + 可配置范围 |

### 4.3 PipelineConfig

```python
class PipelineConfig(BaseModel):
    version: Literal["1"] = "1"
    enabled: bool = True
    task_before: list[PipelineTaskSpec] = []
    task_begin: list[PipelineTaskSpec] = []
    task_after: list[PipelineTaskSpec] = []
```

---

## 5. 三类任务语义

### 5.1 Task Before

`task_before` 用于发布前检查和补强。它的上下文包含：

- 用户原始输入
- Collaborator 生成的 Draft Task Trees
- 用户对 Task Tree 的编辑和补充
- 当前 workspace summary（可选）

典型任务：

- 检查 Task Tree 是否过粗或过细
- 检查 required_capability 是否合理
- 生成风险提示
- 让用户确认关键约束

注意：

- 它发生在真正发布主任务前。
- 如果 `task_before` 发现问题，可以产生用户确认动作或建议修改 draft tree。
- 第一版可以允许 `task_before` 作为“发布流程中的普通任务”，但它的结果必须在主任务 publish 前被处理。

### 5.2 Task Begin

`task_begin` 用于主任务开始前的准备动作。它的上下文包含：

- 用户原始输入
- 已接受的 Task Tree
- root task 列表
- 配置文件信息

典型任务：

- 初始化 workspace 状态检查
- 读取项目结构摘要
- 生成本轮执行约束摘要
- 预计算任务上下文

注意：

- 它已经属于发布后的执行流水线。
- 它仍是普通 Task，进入 TaskBus。
- 如果 begin task 失败，主任务是否继续由配置决定。

### 5.3 Task After

`task_after` 用于任务完成后的总结、验证和归档。它的上下文来自会话内容，并允许用户自由配置范围。

可选上下文范围：

```python
class AfterTaskContextPolicy(BaseModel):
    include_user_messages: bool = True
    include_agent_messages: bool = True
    include_task_results: bool = True
    include_file_changes: bool = True
    include_confirmations: bool = True
    include_logs_summary: bool = False
    include_failed_tasks: bool = True
    task_scope: Literal["root_tree", "session", "selected_tasks"] = "root_tree"
    max_messages: int | None = 200
```

典型任务：

- 总结完成内容
- 汇总文件变更
- 运行验证 / 测试计划
- 生成用户交付报告
- 生成后续建议

注意：

- `task_after` 不应直接读取无限制全量会话，必须受 context policy 控制。
- 用户可以选择更多上下文，但默认应该保守，避免 token 爆炸。

---

## 6. “指定特定 Agent”能力

当前 Agent 架构主要按 `required_capability` 匹配。用户提出“每个任务可以指定 Agent”，这应该成为系统能力，但不能破坏 TaskBus 的简单性。

建议新增调度约束：

```python
class TaskDispatchConstraints(BaseModel):
    required_capability: str
    preferred_agent_template_id: str | None = None
    required_agent_template_id: str | None = None
```

语义：

| 字段 | 含义 |
|---|---|
| `required_capability` | 仍是主匹配键 |
| `preferred_agent_template_id` | 优先使用指定 Agent Template，不可用时可退回同 capability |
| `required_agent_template_id` | 必须使用指定 Agent Template，不可用则任务不可领取 |

约束：

- `required_agent_template_id` 对应的 AgentTemplate 必须具备该 capability。
- 指定 Agent Template 不代表指定 Agent Instance；Instance 仍然一次性创建，用完销毁。
- TaskBus 可以继续用 capability FIFO，但 claim 时需要检查 dispatch constraints。

第一版建议：

- 先实现 `required_agent_template_id`。
- `preferred_agent_template_id` 可以后置，避免 fallback 语义复杂。

---

## 7. 配置文件设计

建议支持项目级文件：

```text
.plato/pipeline.yaml
```

示例：

```yaml
version: "1"
enabled: true

task_before:
  - id: review-task-tree
    title: Review generated task tree
    intent_template: |
      Review the generated task tree for ambiguity, missing steps, and risky assumptions.
      User request:
      {{ user_input }}

      Draft task tree:
      {{ task_tree }}
    required_capability: audit
    agent: system.audit
    context:
      include_user_input: true
      include_task_tree: true

task_begin:
  - id: summarize-workspace
    title: Summarize workspace before execution
    intent_template: |
      Summarize the current workspace structure before executing the accepted task tree.
    required_capability: summarize
    agent: system.summarizer
    context:
      include_user_input: true
      include_task_tree: true
      include_workspace_summary: true

task_after:
  - id: final-session-summary
    title: Final session summary
    intent_template: |
      Summarize what changed in this session, list important files, and provide follow-up suggestions.
    required_capability: summarize
    agent: system.summarizer
    context:
      task_scope: root_tree
      include_user_messages: true
      include_agent_messages: true
      include_task_results: true
      include_file_changes: true
      max_messages: 200
```

### 7.1 配置合并

遵循配置系统计划：

```text
builtin defaults
  → user config
  → project config
  → session override
  → task publish override
```

Session 可以临时关闭 pipeline：

```yaml
pipeline:
  enabled: false
```

也可以只关闭某一阶段：

```yaml
pipeline:
  task_after: []
```

---

## 8. Pipeline Loader

Pipeline Loader 是发布流程中的装载器，不是执行器。

```python
class PipelineTaskLoader:
    def load_before_tasks(self, context: PublishContext) -> list[Task]: ...
    def load_begin_tasks(self, context: PublishContext) -> list[Task]: ...
    def load_after_tasks(self, context: SessionCompletionContext) -> list[Task]: ...
```

职责：

- 读取有效 PipelineConfig。
- 根据 stage 构造上下文。
- 渲染 `intent_template`。
- 校验 capability 和 agent_ref。
- 创建普通 Task。
- 调用 TaskBus.publish。

不负责：

- 执行 Task。
- 绕过 TaskBus 改状态。
- 直接调用 Agent。

---

## 9. 发布流程集成

### 9.1 推荐流程

```text
User confirms draft task tree
  → load task_before
  → publish before tasks to TaskBus
  → before tasks complete
  → if before result allows publish:
       load task_begin
       publish begin tasks
       publish accepted root tasks
  → main task tree complete
  → load task_after
  → publish after tasks
```

### 9.2 简化第一版

为了降低实现复杂度，第一版可以采用：

```text
publish accepted tree
  → enqueue task_begin before root tasks
  → enqueue root tasks
  → after root tree done, enqueue task_after
```

`task_before` 可以先作为可选 preflight：用户点击发布时先运行，完成后再让用户确认是否继续发布主任务。

这点需要实现会话决策。计划层要求是：无论哪种实现，所有 pipeline-generated tasks 都必须进入 TaskBus。

---

## 10. 上下文构造策略

### 10.1 Before / Begin Context

```python
class PublishContext(BaseModel):
    session_id: str
    user_input: str
    draft_task_tree: DraftTaskTree | None
    accepted_task_tree: DraftTaskTree | None
    task_tree_summary: str
    workspace_summary: str | None = None
```

### 10.2 After Context

```python
class SessionCompletionContext(BaseModel):
    session_id: str
    root_task_ids: list[str]
    messages: list[SessionMessageView]
    task_results: list[TaskSummaryView]
    file_changes: list[TaskFileChangeSummary]
    confirmations: list[ConfirmationActionView]
    logs_summary: str | None = None
```

### 10.3 上下文自由度

用户可以配置 after task 的上下文范围，但需要系统保护：

- `max_messages` 默认限制。
- 大字段只用 summary。
- 可配置是否包含 confirmation history。
- 可配置 task scope：当前 root tree / 全 session / selected tasks。
- 默认不包含完整日志，只包含 logs summary。

---

## 11. 任务关系建模

Pipeline task 仍是普通 Task，但需要保留来源元数据：

```python
class TaskMetadata(BaseModel):
    source: Literal["user", "agent", "pipeline"]
    pipeline_stage: PipelineStage | None = None
    pipeline_spec_id: str | None = None
    generated_from_task_tree_id: str | None = None
```

这些 metadata 用于：

- UI 标记“系统自动装载的任务”
- 日志和审计
- replay
- 用户排查 pipeline 行为

但 metadata 不应影响 TaskBus 状态机。

---

## 12. UI / 用户体验

第一版 UI 可以简单：

- 发布确认界面展示将自动装载的 pipeline tasks。
- 用户可以临时启用/禁用某个 pipeline task。
- Task Tree 中 pipeline tasks 使用 badge 标记，例如 `pipeline:before`。
- After tasks 完成后显示在 Session Summary 区域。

用户应该能理解：

```text
这些不是特殊任务，只是系统根据 pipeline 配置自动加入的普通任务。
```

---

## 13. 事件与日志需求

建议新增事件：

- `pipeline.config_loaded`
- `pipeline.task_loaded`
- `pipeline.task_skipped`
- `pipeline.stage_started`
- `pipeline.stage_completed`
- `pipeline.context_built`

每个事件至少包含：

- `session_id`
- `stage`
- `pipeline_spec_id`
- `task_id?`
- `reason?`

日志 category 可使用：

- `task`
- `bus`
- `config`
- 未来可选 `pipeline`

---

## 14. 执行切片

### Slice 1: Pipeline Config Models

产出：

- `PipelineConfig`
- `PipelineTaskSpec`
- `PipelineContextPolicy`
- `AfterTaskContextPolicy`
- schema validation

验收：

- YAML 可解析。
- 非法 stage / capability / duplicate id 有错误。
- 默认配置为空且安全。

### Slice 2: Agent Dispatch Constraints

产出：

- `TaskDispatchConstraints`
- Task metadata 或 dispatch 字段扩展计划
- AgentTemplate id 校验
- TaskBus claim 约束设计

验收：

- 指定 `required_agent_template_id` 的任务只能被该模板领取。
- 指定 Agent Template 必须满足 required capability。
- 不指定 Agent 时保持现有 capability 匹配。

### Slice 3: Pipeline Context Builder

产出：

- `PublishContext`
- `SessionCompletionContext`
- context policy 渲染
- summary / truncation 规则

验收：

- before/begin context 包含用户输入和 Task Tree。
- after context 可按 policy 包含会话消息、结果、文件、确认历史。
- max_messages 生效。

### Slice 4: PipelineTaskLoader

产出：

- `PipelineTaskLoader`
- stage task rendering
- TaskBus publish 集成
- pipeline metadata

验收：

- loader 创建普通 Task。
- loader 不直接执行 Agent。
- task_before/task_begin/task_after 均能 publish 到 TaskBus。

### Slice 5: Publish Flow Integration

产出：

- publish accepted tree 时自动加载 begin tasks
- root tree done 后自动加载 after tasks
- task_before preflight 流程

验收：

- 用户发布时能看到自动装载任务。
- 关闭 pipeline 后不装载。
- stage 失败策略有明确行为。

### Slice 6: UI/API and Docs

产出：

- 配置文件文档
- UI API 增加 pipeline preview
- pipeline task badge
- 示例 pipeline.yaml

验收：

- 用户能输入配置文件指定任务。
- 用户能指定每个任务的 Agent Template。
- UI 能展示 pipeline tasks 来源。

---

## 15. 测试计划

| 场景 | 期望 |
|---|---|
| 空 pipeline config | 不装载任何额外任务 |
| task_begin config | 发布时生成 begin task，并进入 TaskBus |
| task_after config | 主任务完成后生成 after task |
| task_before preflight | 主任务发布前先生成 before task |
| 指定 Agent Template | 任务只能被指定模板领取 |
| capability 不存在 | 配置校验失败 |
| Agent Template capability 不匹配 | 配置校验失败 |
| after max_messages | 构造上下文时截断消息 |
| pipeline disabled | 不装载任何 pipeline task |
| metadata replay | pipeline task 可追溯来源 stage/spec |

---

## 16. 风险与决策点

| 风险 | 处理 |
|---|---|
| Pipeline 被误解成特殊执行系统 | 明确 Pipeline Loader 只 publish 普通 Task，执行仍走 TaskBus |
| before task 与主任务发布时序复杂 | 第一版可将 before 作为 preflight，并要求用户二次确认 |
| after context 太大 | policy + summary + max_messages 控制 |
| 指定 Agent 破坏 capability 抽象 | 以 dispatch constraint 表达，Agent 仍是 Template，不指定 Instance |
| 失败策略复杂 | 第一版先支持 fail_stop / continue 两种 |
| 配置过复杂 | 提供简单示例和内置默认 pipeline |

---

## 17. 完成标准

该 feature 完成时，应满足：

- 用户可以通过配置文件声明 `task_before` / `task_begin` / `task_after`。
- Pipeline tasks 自动转换为普通 Task 并发布到 TaskBus。
- `task_before` / `task_begin` 使用用户输入和 Task Tree 上下文。
- `task_after` 使用可配置范围的会话上下文。
- 用户可以为 pipeline task 指定 capability 和特定 Agent Template。
- 指定 Agent 是系统级调度能力，不是绕过 TaskBus 的特殊调用。
- Pipeline task 有 metadata 和事件可用于 UI 展示、日志和 replay。

---

## 18. 状态

- Status: planned
- Created: 2026-05-10
- Next Step: 在独立实现会话中先完成 Slice 1 Pipeline Config Models，再设计 TaskDispatchConstraints。
