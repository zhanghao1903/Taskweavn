# 多 Agent 协作架构：现行事实与扩展边界

> Status: fact-calibrated current architecture baseline
> Last Updated: 2026-07-10
> Original preserved as:
> `docs/architecture/archive/original/multi-agent-collaboration.original.md`
> Related:
> [Overview](overview.md),
> [Agent](agent.md),
> [Task](task.md),
> [TaskBus](bus.md),
> [Interaction Layer](interaction-layer.md),
> [Collaborator Authoring](collaborator-agent-task-authoring.md),
> [Execution Plane](taskbus-service-multi-execution-env.md),
> [ADR-0011](../decisions/ADR-0011-routing-agent-assignment-and-cooperative-interruption.md),
> [ADR-0012](../decisions/ADR-0012-taskbus-centered-agent-assignment-convergence.md)

## 1. 文档目的与结论

本文只描述代码库当前已经成立的多 Agent 相关事实，并把已接受但尚未实现的
扩展方向单独列出。

当前 Plato / TaskWeavn **不是一个已经实现的多 Agent 图运行时**。现行执行闭环是：

```text
Published Task
  -> TaskBus
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor
  -> Resident Default Agent boundary
  -> task-scoped AgentLoop
  -> TaskBus complete / fail / wait
```

代码库同时存在若干名称中带有 Agent、Router 或 Execution Env 的边界，但它们不
共同构成动态多 Agent 调度系统：

- Collaborator 负责命令驱动的任务编写，不领取 Published Task；
- Runtime Input Router 负责用户输入分类和命令分发，不分配 Execution Agent；
- Read-only Inquiry 负责有界只读回答，不执行 workspace mutation；
- Agent LLM role 负责选择模型配置，不创建 Agent instance；
- ExecutionEnv registry 负责本地能力兼容检查，不管理远程 worker；
- `Orchestrator` 只有占位 Protocol 和 `NullOrchestrator`，没有真实调度实现或调用路径。

因此，本文使用“多 Agent”时必须区分：

1. **当前存在的多个专用服务角色**；
2. **当前唯一的固定路线执行 Agent**；
3. **未来 Router + Agent Manager + 多 Execution Agent 的目标架构**。

## 2. 当前角色地图

| 名称 | 当前实现 | 是否是 TaskBus 执行 Agent | 当前边界 |
|---|---|---:|---|
| Default Agent | `AgentLoopResidentDefaultAgent` | 是 | 固定 identity `default_agent`；每个 Task 创建 task-scoped runner / AgentLoop |
| Collaborator | `DefaultCollaboratorAuthoringService`、profile runner、authoring commands | 否 | 生成 RawTask / Plan / DraftTaskTree proposal，并通过命令服务持久化 |
| Runtime Input Router | `DefaultRuntimeInputRouter` + 可选 LLM route planner | 否 | 分类用户输入，分发 inquiry、guidance、ASK、confirmation、stop/retry 或 execution handoff |
| Read-only Inquiry | `DefaultReadOnlyInquiryService` + answer provider | 否 | 基于允许的产品事实、诊断和 workspace 只读上下文回答问题 |
| Agent LLM roles | 六个 `AgentLlmRole` 字符串 | 否 | 按角色解析 provider/model profile；不实例化 runtime Agent |
| Local runtime handler | `EmbeddedTaskRuntimeHandler` 实现 | 否 | 为特定 Task type 执行受控本地流程，不是通用 Agent protocol |
| `Orchestrator` | Protocol + `NullOrchestrator` | 否 | 未接入生产路径；`submit()` 在空实现中抛出 `NotImplementedError` |

### 2.1 Default Agent 是当前唯一通用执行者

Main Page sidecar 在 workspace runtime 装配时创建一个 resident Default Agent
adapter。这个 adapter 提供稳定执行入口，但不会在 Task 之间保留同一个
`AgentLoop`：

```text
AgentLoopResidentDefaultAgent.run(task)
  -> loop_factory(task)
  -> new task-scoped _SessionAgentLoopRunner
  -> AgentLoop.run(rendered context, task_id)
  -> TaskRunResult
```

TaskBus、Context Manager、AskStore、MessageStream、Event/Audit stores 保存系统
事实。Agent 对象的跨任务私有内存不是事实权威。

### 2.2 Collaborator 是 authoring actor，不是执行 worker

`CollaboratorAgentTemplate` 确实存在，但它是内置 Collaborator 的 metadata：

- template id 是 `system.collaborator`；
- capability 是 `task_authoring`；
- command protocol 是 `authoring.v1`；
- 默认 `llm_visible_tool_pools` 为空；
- registry 是 session-scoped 的 Collaborator metadata registry，不是通用 AgentPool。

真实变更由 `CollaboratorAuthoringService` 生成结构化 proposal，再提交给
`AuthoringCommandService`。Workspace-informed authoring 只暴露有界 read/search
工具；`write_file`、`run_command`、`shell` 和 `execute_code` 明确不在其允许工具中。

Collaborator 到执行层的“协作”发生在持久化 contract 上：

```text
user input
  -> Collaborator proposal
  -> AuthoringCommandService
  -> RawTask / Plan / DraftTaskTree facts
  -> explicit publish
  -> Published Task in TaskBus
```

这不是 Collaborator 向 Default Agent 发送私有消息，也不是运行时 handoff 协议。

### 2.3 Router 和 Inquiry 不是子 Agent 调度器

Runtime Input Router 可以使用 LLM planner，但最终命令仍由确定性服务验证和提交。
它操作的是 Main Page 输入 contract，不观察 Agent pool，也不写 assignment。

Read-only Inquiry 可以使用单独的 LLM profile，并读取显式允许的上下文。它没有
TaskBus claim、workspace 写工具或任务完成权限。两者的 `agent_id` 日志/消息标签
不能解释为已经注册了可调度 Agent instance。

## 3. 当前运行拓扑

### 3.1 Main Page 输入与 authoring

```text
Main Page input
  -> Runtime Input Router
     -> read-only inquiry
     -> record guidance / contract revision command
     -> answer active ASK
     -> resolve active confirmation
     -> stop / retry selected Task
     -> create execution Task contract
     -> clarification / unsupported outcome

Authoring path
  -> Collaborator authoring profile
  -> bounded workspace read/search when needed
  -> structured proposal
  -> AuthoringCommandService
  -> Plan / TaskNode or legacy DraftTaskTree projection
  -> explicit publish
```

### 3.2 普通 Published Task 执行

```text
publish or resume trigger
  -> FixedRouteExecutionDispatcher.request_dispatch(session_id)
  -> one dispatcher worker dequeues a Session
  -> FixedRouteTaskExecutor selects one eligible pending Task
  -> TaskBus.claim_next(
       session_id,
       capability=task.required_capability,
       agent_id="default_agent",
     )
  -> Resident Default Agent runs the Task
  -> TaskBus.complete / fail / wait_for_user / wait_for_confirmation
```

Dispatcher 会按 Session 合并重复 trigger，并在一个 worker thread 中依次 drain。
一次 trigger 最多执行配置的 tick 数；只有前一个 tick `completed` 才继续下一项。
它不保留跨 Task 的 AgentLoop，也不并行运行一组子 Agent。

### 3.3 Execution Plane 路径

`EmbeddedTaskApiService` 提供 service-shaped local Task API：

```text
TaskRequest
  -> idempotency validation
  -> local ExecutionEnv compatibility check
  -> ordinary task: publish TaskDomain to TaskBus
  -> selected task type: optional local EmbeddedTaskRuntimeHandler
```

普通 task type 最终仍进入固定 Default Agent 路线。特定 runtime handler（当前包括
受控的本地 WeChat send 路径）是 task-type extension seam，不是 Agent Manager。

## 4. Task 分配与 claim 的当前事实

### 4.1 TaskDomain 没有 assignment 状态

当前 `TaskDomain` 有：

- `required_capability`：单值字符串；
- `dispatch_constraints`：未来 dispatch intent / metadata；
- `claimed_by`：claim 成功后的执行事实；
- `status`：`pending`、`running`、`waiting_for_user`、`done`、`failed`。

当前没有：

- `assigned_agent_id`；
- `assigned_by` / `assigned_at`；
- assignment rationale / version；
- 单独的 `assigned` 状态；
- `claim_assigned()` 或 `AssignmentCommand` 实现。

`TaskDispatchConstraints.required_agent_id`、`preferred_agent_id` 和
`required_capabilities` 可以随发布结果保存，但当前 `claim_next()` 不读取这些字段。

### 4.2 `claim_next()` 的真实匹配条件

In-memory 和 SQLite TaskBus 都只检查：

1. Session 相同；
2. Task 是 `pending`；
3. `required_capability` 与调用参数精确相等；
4. root Task 可执行，或 parent Task 已经 `done`；
5. 候选按 `created_at`、`order_index`、`task_id` 排序。

claim 成功后写入 `running`、调用方传入的 `claimed_by` 和 `started_at`。
TaskBus 不检查 agent registry、agent health、tool inventory、成本或历史成功率。

### 4.3 当前串行性来自 dispatcher，不是完整调度协议

Main Page 产品路径使用一个 dispatcher worker，所以通常形成串行执行 lane。但
TaskBus Protocol 本身没有“同一 Session 只能有一个 running Task”的全局 guard；
其他调用方重复调用 `claim_next()` 时，可能领取另一个 eligible pending Task。

SQLite claim 使用当前 `SqliteTaskBus` 实例的进程内 `RLock`。代码没有分布式
compare-and-swap、lease、fencing token 或跨进程 worker ownership 协议。

## 5. 当前协作媒介

### 5.1 Durable contract，而不是 Agent 私有对话

当前角色之间通过各自权威存储产生的事实衔接：

| 协作内容 | 权威边界 |
|---|---|
| 未发布任务理解与草稿 | RawTask / Plan / TaskNode / DraftTask stores |
| Published Task 生命周期 | TaskBus |
| 用户 ASK | AskStore + TaskBus waiting linkage |
| confirmation | MessageStream response + TaskBus waiting linkage |
| 用户可见消息 | SQLite MessageStream |
| 执行证据 | EventStream、result/error summary、audit projection |
| 下一次执行上下文 | Session Context Manager |
| service-level execution request | Execution Plane store + TaskBus |

没有一个 Agent 可以通过修改另一个 Agent 的内存来推进这些事实。

### 5.2 MessageStream 是用户交互面，不是 agent-to-agent mailbox

`AgentMessage.message_type` 当前有三类：

- `informational`；
- `actionable`；
- `response`。

消息包含 `session_id`、可选 `task_id`、`agent_id`、可选
`parent_message_id`、内容、context、action options、response 字段和时间。SQLite
stream 持久化消息；`InProcessMessageBus` 是当前唯一 bus 实现，live subscription
只接收订阅之后发布的消息。

这些消息服务于用户会话、ASK/confirmation 和 UI projection。当前没有：

- Agent mailbox 地址协议；
- Agent-to-Agent request/response schema；
- delegation id、handoff token 或 child-run correlation；
- 多 Agent result aggregation protocol；
- Agent 间 backpressure、delivery acknowledgement 或 retry contract。

### 5.3 ASK 和 confirmation 会真实阻塞 Task

当前 Main Page 显式工具 `ask_user` 和 `request_confirmation` 可以把运行中的 Task
变为 `waiting_for_user`，结束当前 task-scoped run。回答后 Task 回到 `pending`，再由
dispatcher 重新 claim。这不是“消息永远不打断执行”的模型。

通用 CLI 路径可以选择装配 `AutonomyGate` 和 `WaitCoordinator`；Main Page Default
Agent 没有把所有普通工具动作统一接入该 gate。Autonomy presets 的存在也不等于
已经实现 per-Agent 图节点自主度配置或 Main Page 自主度编排 UI。

## 6. Agent 生命周期与状态所有权

### 6.1 当前执行生命周期

```text
workspace runtime assembly
  -> build resident Default Agent adapter
  -> dispatcher receives trigger
  -> adapter creates task-scoped runner
  -> Context Manager builds run input
  -> AgentLoop executes tools / asks / confirmations
  -> adapter maps LoopResult to TaskRunResult
  -> executor commits TaskBus lifecycle
  -> run-local stack is released
```

`claimed_by="default_agent"` 是 Task 执行记录，不是通用实例注册表中的外键。

### 6.2 当前不存在的生命周期管理

代码库没有通用：

- Agent Manager；
- Agent template/instance registry；
- Agent process pool 或 warm pool；
- spawn、health check、drain、terminate lifecycle；
- capacity / load / cost scheduler；
- child Agent ownership tree；
- Agent version、permission profile 与 Task assignment 的运行时校验链。

Collaborator 的 metadata registry 和 ExecutionEnv registry 都不能替代上述边界。

### 6.3 `Orchestrator` 仍是占位

`src/taskweavn/orchestration/protocol.py` 定义：

```python
class Orchestrator(Protocol):
    def submit(self, action: BaseAction) -> BaseObservation: ...
    def shutdown(self) -> None: ...
```

当前只有 `NullOrchestrator`，其 `submit()` 抛出 `NotImplementedError`。除模块导出外，
生产代码和测试没有调用点。因此不能把它写成已运行的 planner/executor 编排层。

## 7. Capability、工具与执行环境

### 7.1 Capability 是验证与 claim 键

Main Page 默认 authoring catalog 当前包含：

```text
general, writing, coding, testing, research
```

`StaticCapabilityCatalog` 和 `StaticAgentCapabilityCatalog` 用于 authoring / publish
validation。它们不是动态 Agent descriptor registry。

Default Agent 的具体工具由 sidecar assembly 直接构造并挂载到 `LocalRuntime`，不是
由图节点从全局 `ToolRegistry` 动态选择。当前代码没有旧文档描述的
`ToolRegistry.tools`、`compatible_tools` 或 Agent graph tool-set compiler。

### 7.2 ExecutionEnv 只做本地兼容选择

`InMemoryExecutionEnvRegistry` 支持 `upsert/get/list/find_compatible`。兼容条件是：

- env 状态是 `online`；
- env capabilities 包含 request 的 `required_capability`；
- 非空 `allowed_tools` 是 env tool pool 的子集。

sidecar 当前构造本地 `local-default` env。虽然 DTO 中已经有
`last_heartbeat_at`、`active_execution_id`、`TaskLease`、`claimed` 和
`lease_expired` 等字段/状态，但当前 service 没有 remote env registration、claim、
lease issue/renew/revoke/expire 或 heartbeat endpoint。

## 8. UI 与 API 的当前表面

Main Page 当前展示 Plan/Task tree、执行状态、ASK、confirmation、消息、结果、错误、
activity、audit 和 stop/retry 操作。

当前 `TaskNodeCardView` 不包含 assignment、assigned Agent、`claimed_by` 或 Agent
health 字段。前端没有：

- Agent graph editor；
- Agent palette 或 node/edge 配置；
- AgentPool / worker 列表；
- Task assignment / reassignment 控件；
- per-node autonomy slider；
- parallel branch monitor；
- multi-Agent handoff timeline。

Execution Plane HTTP routes 可以 publish/query/cancel/retry/list events/read
result/error/evidence，但这些是本地 sidecar API。它们没有暴露 Agent Manager 或
remote worker control plane。

## 9. 并发、隔离与恢复边界

### 9.1 当前保证

- workspace runtime 把执行工具限制在选定 workspace root；
- Task、ASK、message、context、event 和 authoring facts 通过 Session/workspace id
  隔离；
- fixed-route dispatcher 合并同一 Session 的重复 trigger；
- child Task 只有在 parent `done` 后才能 claim；
- retry 在同一 Task identity 上回到 `pending`，并清除当前 claim/wait/result/error/
  interruption runtime facts；
- running interruption 采用 cooperative safe-point 语义；
- startup recovery 可以收敛带 interruption intent 的 stale running Task。

### 9.2 当前没有的保证

- 多个 workspace writer Agent 的锁、branch 或 merge 协议；
- 同一 Task 的分布式 exactly-once execution；
- Agent lease、heartbeat 和 stale worker reclaim；
- 并行子任务 result merge / conflict resolution；
- Agent crash 后恢复 run-local LLM transcript 的通用协议；
- 跨 store 的 Task/message/ASK 原子事务。

任何真正的并行多 Agent 写入都必须先定义 workspace ownership、隔离、合并和可重放
冲突处理，不能仅通过增加 worker 数量实现。

## 10. 已接受但尚未实现的 dynamic routing 方向

ADR-0011 和 ADR-0012 接受的目标是 TaskBus-centered convergence：

```text
pending unassigned Task
  -> Router observes Task + Agent descriptors
  -> Routing Agent policy proposes AssignmentCommand
  -> TaskBus validates and stores assignment fact
  -> Agent Manager observes pending assigned Task
  -> Agent Manager creates/selects runtime instance
  -> assigned Agent claims Task
  -> Agent run reports complete / fail / wait
```

该方向的约束包括：

- Router 决定 assignment strategy，但不拥有 Task lifecycle；
- TaskBus 继续是 Published Task lifecycle 和 assignment fact authority；
- Agent Manager 创建/选择 runtime instance，但不成为第二个 Task store；
- assignment 指向 Agent identity/template/capability，不直接指向临时 run；
- 初始方案不增加单独 `assigned` status；
- retry 清除 assignment 和本次 runtime facts，再进入 routing；
- 初始 dynamic routing 可使用每个 TaskBus 一个 Router loop 和 Agent Manager loop；
- stale pending sweep、assigned-only claim 和 projection UI 需要与 assignment 一起落地；
- 第一版 UI 只投影 assignment，不提供手工 reassignment。

以上是已接受设计，不是当前代码事实。当前仓库搜索不到生产
`AssignmentCommand`、`assigned_agent_id`、`claim_assigned` 或 Agent Manager 实现。

## 11. 实现 dynamic multi-Agent 前的最低前置条件

1. 在 TaskBus command/model/store 中加入可审计 assignment facts 和幂等语义。
2. 定义 Agent descriptor、template identity、runtime instance 和 run id 的稳定关系。
3. 实现 Router observation/command loop，并明确 deterministic fallback。
4. 实现 Agent Manager health/lifecycle loop 和 assigned-only claim validation。
5. 定义 capability、tools、permissions、workspace scope 与 Agent identity 的联合校验。
6. 为本地并行或远程执行增加 lease、heartbeat、fencing 和 stale recovery。
7. 为同 workspace 写入定义串行、隔离 branch 或 merge contract。
8. 定义 Agent-to-Agent delegation、result、failure、cancellation 和 audit schema。
9. 扩展 UI contract 与 projection，先显示 assignment/health，再考虑 reassignment。
10. 增加跨进程并发、重复 delivery、worker crash 和恢复测试。

## 12. 当前非事实清单

| 旧概念或目标 | 当前状态 |
|---|---|
| Planner -> Executor -> Auditor graph 已运行 | 未实现 |
| LLM `OrchestrationDesigner` 生成合法 Agent DAG | 未实现 |
| `OrchestrationDraft` / `ConstraintProfile` / `OrchestrationConfig` | 代码中不存在 |
| Auto-pilot / Co-pilot / Manual / Audit-Focus 编排 preset | 未实现；不要与 CLI autonomy presets 混同 |
| 所有 Agent 动作都经过 Main Page `AutonomyGate` | 不成立 |
| 最高自主度时所有 actionable 都不会阻塞 | 不成立；显式 ASK/confirmation 可使 Task waiting |
| MessageStream 是 Agent 间通信总线 | 不成立；它是用户交互和投影边界 |
| ToolRegistry 按 Agent type 动态分配工具 | 未实现 |
| 动态 Agent assignment / reassignment | 未实现 |
| 通用 child Agent spawn / handoff / aggregation | 未实现 |
| 多 Agent 并行写同一 workspace | 未实现，也没有冲突合并协议 |
| remote multi-ExecutionEnv worker pool | 未实现 |
| `Orchestrator` 已接入运行路径 | 不成立；仅占位 Protocol |

## 13. 代码事实索引

执行与 TaskBus：

- `src/taskweavn/task/execution.py`
- `src/taskweavn/task/models.py`
- `src/taskweavn/task/bus.py`
- `src/taskweavn/task/sqlite_bus.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_agent.py`

专用角色：

- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/task/collaborator_loop.py`
- `src/taskweavn/task/collaborator_profile_runner.py`
- `src/taskweavn/task/collaborator_workspace_context.py`
- `src/taskweavn/server/runtime_input_router.py`
- `src/taskweavn/server/runtime_input_llm_router.py`
- `src/taskweavn/server/read_only_inquiry.py`
- `src/taskweavn/server/read_only_inquiry_answer_provider.py`
- `src/taskweavn/llm/agent_config.py`

交互与扩展边界：

- `src/taskweavn/interaction/message.py`
- `src/taskweavn/interaction/bus.py`
- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/autonomy.py`
- `src/taskweavn/interaction/gate.py`
- `src/taskweavn/orchestration/protocol.py`
- `src/taskweavn/execution_plane/models.py`
- `src/taskweavn/execution_plane/env_registry.py`
- `src/taskweavn/execution_plane/embedded_service.py`

UI contract：

- `src/taskweavn/task/views.py`
- `src/taskweavn/server/ui_contract/view_models.py`
- `frontend/src/shared/api/types.ts`
- `frontend/src/pages/main-page/TaskNodeCard.tsx`
- `frontend/src/pages/main-page/MainPageDetailPanel.tsx`

关键测试：

- `tests/test_fixed_route_task_executor.py`
- `tests/test_task_bus_lifecycle.py`
- `tests/test_sqlite_task_bus.py`
- `tests/test_collaborator_authoring_service.py`
- `tests/test_collaborator_authoring_loop_contract.py`
- `tests/test_runtime_input_router.py`
- `tests/test_execution_plane_service.py`
- `tests/test_main_page_sidecar_app.py`

## 14. 校准原则

后续修改本文时，应分别证明：

1. 名称是否只是 role/profile/metadata，还是可领取 Task 的 runtime Agent；
2. 设计是否已由 model、store、command、service、assembly、UI 和 tests 贯通；
3. assignment、claim、run 和 result 分别由哪个权威边界持有；
4. 并行执行是否已有 workspace isolation、lease 和 recovery；
5. ADR 的 accepted direction 是否已经进入生产代码。

只有完整证据链成立后，才能把 future multi-Agent 方向改写为 current fact。
