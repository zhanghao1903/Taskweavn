# TaskWeavn 核心架构参考

> Status: fact-calibrated current implementation reference
> Last Updated: 2026-07-10
> Original preserved as:
> `docs/architecture/reference.original.md`
> Verification record:
> [fix-log/reference.md](fix-log/reference.md)
> Related:
> [Overview](overview.md),
> [Agent](agent.md),
> [Task](task.md),
> [TaskBus](bus.md),
> [Interaction Layer](interaction-layer.md),
> [Context Manager](context-manager.md),
> [LLM Reliability](llm-provider-reliability.md),
> [Logging](configurable-logging-system.md)

## 1. 范围与阅读规则

本文面向需要修改 TaskWeavn Python 后端的贡献者，提供当前底层 substrate、对象
生命周期和产品装配的快速参考。

本文不是整个仓库的自动生成 API 索引，也不声称列出所有 Protocol、模型或存储。
当前代码已经远超早期 `types -> runtime -> core -> CLI` 范围，包含 Task authoring、
Context Manager、Runtime Input Router、UI contract、Execution Plane、skills、usage、
runtime config、workspace inspection 和 observability 等独立域。

阅读时必须区分三类事实：

1. **substrate 能力存在**：类或 Protocol 已实现；
2. **某个入口已装配**：Main Page sidecar 或 CLI 实际使用该能力；
3. **产品闭环成立**：store、command、service、projection、UI 和 tests 已贯通。

一个类存在不等于 Main Page 已装配。典型例子：

- `AutonomyGate`、`CodeActionTool`、`AuditAgent` 和 configurable ThoughtStore 在通用
  CLI 路径可用；
- Main Page Default Agent 不装配这四项，而使用显式 ASK/confirmation、直接
  filesystem/shell tools、Context Manager 和 cooperative interruption；
- `Orchestrator` 存在 Protocol，但没有真实实现或调用路径。

## 2. 当前代码结构

### 2.1 产品执行主路径

```text
React Main Page
  -> local sidecar HTTP / SSE
  -> Runtime Input Router or explicit command/query
  -> Authoring / Contract Revision / Interaction / Task controls
  -> Plan / TaskNode publish
  -> TaskBus
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor
  -> resident Default Agent adapter
  -> task-scoped AgentLoop
  -> concrete tools + Context Manager + LLM
  -> EventStream / TaskBus / MessageStream / result summaries / usage
```

普通 Execution Plane TaskRequest 也会映射到 TaskBus，再进入同一 fixed-route 路径；
特定 task type 可以交给 local runtime handler。

### 2.2 包级职责

| 包 | 当前职责 |
|---|---|
| `taskweavn.types` | typed Action / Observation 基类、注册表和通用事件类型 |
| `taskweavn.runtime` | Action 到 Observation 的执行协议和进程内 dispatch |
| `taskweavn.tools` | concrete Tool、workspace path policy、file/shell/web/computer-use/interaction adapters |
| `taskweavn.core` | AgentLoop、EventStream、Session、WorkspaceLayout、loop profile seam |
| `taskweavn.llm` | provider-neutral request/response、provider facade、retry、role-aware resolver |
| `taskweavn.memory` | optional ThoughtStore side channel |
| `taskweavn.audit` | optional CodeAction LLM audit substrate |
| `taskweavn.interaction` | MessageStream、ASK、autonomy/risk primitives、in-process bus |
| `taskweavn.context` | Session context collection、policy、render、checkpoint/delta persistence |
| `taskweavn.task` | authoring、Plan/TaskNode、publish、Published Task lifecycle、projection、fixed execution |
| `taskweavn.contract_revision` | typed guidance/task revision commands and durable activity |
| `taskweavn.execution_plane` | service-level local Task API、env compatibility、selected runtime handlers |
| `taskweavn.workspace_inspection` | bounded read/search/precision-file evidence |
| `taskweavn.skills` | skill registry、policy、activation facts、context injection |
| `taskweavn.runtime_config` | schema registry、resolved values、mutation ledger、same-process config bus |
| `taskweavn.usage` | successful ChatResponse token-usage ledger |
| `taskweavn.observability` | structured process-local logging and legacy channel bridge |
| `taskweavn.server` | Main Page composition root、UI gateways、HTTP/SSE、recovery、diagnostics |
| `taskweavn.cli` | standalone Typer entry point and optional substrate assembly |

### 2.3 依赖关系不是全局层级铁律

当前仓库使用 Protocol 隔离许多边界，但没有“所有跨层依赖必须先写 Protocol”或
“箭头永远向下”的全局规则。例如 `core.loop` 直接组合 LLM、tools、audit、memory、
observability 和 runtime；`server` 组合 Task、Context、Interaction、Execution Plane
与 UI contracts。

应以包的 authority、command/query 边界和 composition root 为依据，不应从旧的
单向分层图推断当前依赖合法性。

## 3. Typed Action / Observation Substrate

模块：`taskweavn.types`

### 3.1 基类

| 类型 | 当前字段/性质 |
|---|---|
| `BaseEvent` | Pydantic frozen model；`extra="forbid"`；`event_id`、UTC `timestamp`、ClassVar `kind` |
| `BaseAction` | 增加 `source`；ClassVar `baseline_risk`；定义子类时校验 `[0,1]` |
| `BaseObservation` | 增加可选 `action_id` 和 `success`；`action_id` 并非所有 Observation 都必填 |

`to_dict()` / `to_json()` 会把 ClassVar `kind` 写入 payload。`kind` 是反序列化
discriminator，不是独立事件 family。

### 3.2 自动注册

`BaseAction.__init_subclass__` 和 `BaseObservation.__init_subclass__` 默认把 concrete
子类注册到：

- `ActionRegistry`；
- `ObservationRegistry`。

规则：

- 默认 key 是类名，也可以在类定义时指定 `kind=`；
- abstract/intermediate class 可传 `register=False`；
- 同一个 kind 注册到不同 class 会抛 `ValueError`；
- SQLite replay 前必须 import 定义 concrete event 的模块，否则 registry 无法找回
  class；
- registry 只覆盖 Action/Observation family，不是所有 domain event 的全局 schema
  registry。

### 3.3 当前事件家族

通用类型包括：

- `AgentFinishAction` / `AgentFinishObservation`；
- `AgentErrorObservation` / `ErrorObservation`；
- `CodeAction` / `CodeExecutionObservation`；
- `AskUserAction` / `AskUserObservation`；
- `RequestConfirmationAction` / `RequestConfirmationObservation`；
- `ComputerUseAction` / `ComputerUseObservation`。

file、precision-file、shell、web search/fetch 的 Action/Observation 定义在各自 Tool
模块中，import 时同样注册。TaskBus、UI events、runtime config changes 和 token usage
不是 `BaseEvent` 子类；它们有各自 model/store。

### 3.4 标识限制

`event_id` 默认是 `uuid4().hex`，但 SQLite EventStream schema 当前没有
`UNIQUE(event_id)` 约束。文档可以称其为应用生成标识，不能把数据库级全局唯一性写成
已强制不变量。

## 4. Runtime、Tool 与 Workspace

### 4.1 Runtime Protocol

```python
@runtime_checkable
class Runtime(Protocol):
    def execute(self, action: BaseAction) -> BaseObservation: ...
```

Protocol 文档要求实现把失败转换为 Observation 而不是抛异常。当前
`LocalRuntime.execute()` 实际执行该约束：

- 按 Action 的**精确 class**查找 executor；
- 未注册时返回 `ErrorObservation(error_type="no_executor")`；
- executor 抛异常时返回 `ErrorObservation(error_type="execution_error")`；
- 重复注册同一 Action class 会静默覆盖；
- invoke/result 通过 structured tool logger 记录。

该 total-function 保证属于 Runtime execution boundary，不自动覆盖 Tool startup、
EventStream append、ThoughtStore write 或其他 AgentLoop 依赖。

### 4.2 Tool 抽象

```python
class Tool[ActionT: BaseAction, ObservationT: BaseObservation](ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    action_type: ClassVar[type[BaseAction]]
    observation_type: ClassVar[type[BaseObservation]]

    def execute(self, action: ActionT) -> ObservationT: ...
    def startup(self) -> None: ...
    def shutdown(self) -> None: ...
    def register(self, runtime: LocalRuntime) -> None: ...
```

`Tool.execute()` 可以抛异常；LocalRuntime 负责归一化。`startup()` / `shutdown()` 是
每次 `AgentLoop.run()` 的 hooks。

当前生命周期细节：

1. AgentLoop 按 tools 顺序调用全部 `startup()`；
2. startup exception 不会转换为 LoopResult，会离开 `run()`；
3. `finally` 会对 tools 列表中的**每个** Tool 尝试 `shutdown()`，包括 startup 尚未
   执行或已失败的 Tool；
4. 每个 shutdown exception 被 suppress；
5. 因此要求 shutdown 幂等并容忍未完成 startup，但不能把它描述成严格的一一成功
   配对。

### 4.3 Workspace path policy

`Workspace(root)` 要求 root 已存在且是目录。`resolve(path)`：

- 解析相对/绝对路径；
- 拒绝逃出 root 的路径；
- 拒绝 `.plato`、legacy `.taskweavn` 和 `.code-agent` metadata tree。

这是 normal filesystem Tool 的 path policy，不是 OS sandbox。`RunCommandTool` 以
workspace 为 cwd，但 Workspace 对象本身不能阻止任意子进程访问系统其他位置。

### 4.4 Main Page 与 CLI Tool 集不同

Main Page Default Agent 基础工具：

```text
read_file
read_file_range
search_workspace
replace_file_range
append_file
write_file
list_dir
run_command
```

按配置可增加：

- `web_search`；
- `web_fetch`；
- `computer_use`；
- Published Task 绑定的 `ask_user`；
- Published Task 绑定的 `request_confirmation`。

Standalone CLI 还固定装配 `CodeActionTool` (`run_code`)，并可选 audit、thoughts 和
autonomy bundle。Main Page 不装配 `CodeActionTool`。

### 4.5 Sandbox substrate

`CodeActionTool` 持有 `SandboxExecutor`：

- startup 创建 Docker container；
- workspace bind mount 到 `/workspace`；
- 默认 network mode 是 `none`；
- 同一个 run 内复用 container，但每次 `docker exec` 使用新的 Python interpreter；
- file state 可持续，Python globals 不持续；
- side-effect snapshot 跳过受保护 metadata，并区分 declared/undeclared changes；
- shutdown best-effort 删除 container。

这是 CLI substrate，不是当前 Main Page 普通 filesystem/shell Tool 的安全边界。

## 5. AgentLoop

模块：`taskweavn.core.loop`

### 5.1 当前构造面

```python
@dataclass
class AgentLoop:
    llm: LLMClient
    runtime: Runtime
    tools: list[Tool[Any, Any]]
    event_stream: EventStream = InMemoryEventStream()
    thought_store: ThoughtStore = NullThoughtStore()
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_steps: int = 20
    auditor: AuditAgent | None = None

    session_id: str = "default"
    workspace_root: Path | None = None
    bus: MessageBus | None = None
    gate: AutonomyGate | None = None
    wait_coordinator: WaitCoordinator | None = None
    context_provider: AgentLoopContextProvider | None = None
    interrupt_checker: TaskInterruptChecker | None = None
```

### 5.2 装配校验

`__post_init__` 当前验证：

- Tool name 不能重复；
- `agent_finish` 是 loop 保留 Tool name；
- `gate` 与 `wait_coordinator` 必须同时存在或同时缺失；
- gate 存在时必须有 `bus` 和 `workspace_root`。

Context provider、interrupt checker、auditor 和 thought store 没有 bundle-level
cross-validation。

### 5.3 Run identity

```python
run(task: str, *, task_id: str | None = None) -> LoopResult
```

- 未传 `task_id` 时创建一个 uuid hex；
- Main Page 传入 Published `TaskDomain.task_id`；
- 每次调用还创建
  `agent_loop:<task_id>:<uuid>` 形式的 internal `agent_run_id`；
- EventStream concrete extension和 AgentMessage 只记录 `task_id`；
- `agent_run_id` 进入 Context/LLM metadata 和 usage path，但不是当前 EventStream row
  的字段。

同一个 Published Task 在 ASK/confirmation resume、retry 或其他 rerun 后可以产生多次
AgentLoop run。因此按 `task_id` 联结 events/messages 得到的是 Task-level timeline，
不一定是精确一次 run。不能再把 `task_id` 定义成“一次 AgentLoop.run 的唯一 id”。

### 5.4 主循环

每个 step 的当前顺序是：

1. 在 `step_start` 检查 cooperative interruption；
2. drain 当前 run 内的 async autonomy pending decisions；
3. 再次检查 interruption；
4. 通过 Context Provider 准备 LLM messages/metadata；
5. context error 生成 `AgentErrorObservation` 并停止；
6. LLM 前检查 interruption；
7. 记录 LLM input，调用 `llm.chat()`，记录 output；
8. LLM error/timeout 生成 `AgentErrorObservation` 并停止；
9. 有 response content 时写 ThoughtStore；
10. 无 tool calls 时成功结束；
11. `agent_finish` 生成 finish Action/Observation 并成功结束；
12. 普通 tool call 解析为 Action；解析失败写 `ErrorObservation` 后继续；
13. Tool 前检查 interruption；
14. 可选 AutonomyGate 返回 proceed/skip/defer；
15. proceed 时 append Action、Runtime.execute、append Observation；
16. 可选 AuditAgent 只处理 CodeAction/CodeExecutionObservation；
17. 成功的 ASK/confirmation waiting Observation 以 `waiting_for_user` 停止；
18. Tool 后再次检查 interruption；
19. step 用完后返回 `max_steps`。

### 5.5 LoopResult

```python
@dataclass(frozen=True)
class LoopResult:
    final_answer: str
    steps: int
    finished: bool
    stop_reason: str
```

当前源码产生这些 stop reason：

| stop reason | `finished` | 含义 |
|---|---:|---|
| `no_tool_calls` | true | LLM 直接完成 |
| `agent_finish` | true | LLM 调用保留 finish tool |
| `max_steps` | false | step limit |
| `waiting_for_user` | false | ASK/confirmation 已把 Task 置为 waiting |
| `context_error` | false | Context Provider 失败 |
| `llm_error` | false | provider/LLM 调用失败 |
| `llm_timeout` | false | timeout-shaped LLM failure |
| `interrupted` | false | cooperative stop 在 safe point 生效 |
| `interrupt_check_error` | false | interruption source 本身失败 |

`stop_reason` 是普通字符串，不是 Literal-validated closed enum。

### 5.6 异常边界

AgentLoop 会把 context、LLM 和 interruption-check failures 转成 LoopResult；
LocalRuntime 会把 Tool execute failure 转成 ErrorObservation。但 `run()` 不是全局
“永不抛”函数。以下依赖失败仍可能抛出：

- Tool startup；
- EventStream append；
- ThoughtStore write；
- 部分 MessageBus publish/wait 路径；
- audit 之外的内部实现错误。

Main Page 的 `FixedRouteTaskExecutor` 在更外层捕获 resident Agent exception，并把
Task 失败事实提交给 TaskBus。该外层补偿不能改写 AgentLoop 自身的契约。

### 5.7 Context 和 interruption

Main Page 为 AgentLoop 装配 `SessionAgentLoopContextProvider`：

- 每次 LLM call 前从 Task、Event、ASK、guidance、control 和 context store 构建输入；
- 支持 persisted messages、delta/checkpoint 和 stable prefix metadata；
- 生成 snapshot/trace/render hashes；
- 把 `agent_run_id`、turn index、tools 和 pending decision count 传入 context request。

Main Page 还装配 TaskBus-backed `TaskInterruptChecker`。它在 LLM/tool 边界的 cooperative
safe points 读取 stop intent；不会 hard-kill 已经运行的 provider call 或 command。

### 5.8 Loop profile seam

`core.loop_profile` 定义 `AgentLoopProfile`、`AgentLoopProfileResult` 和
`LoopTerminalAction`。该 Protocol 描述 profile-neutral prompt/terminal mapping seam，
当前 Collaborator authoring 有自己的 profile/runner。

它不是 `AgentLoop` dataclass 的 `profile` 字段，也不是通用多 Agent runtime。

## 6. EventStream

### 6.1 Protocol

```python
@runtime_checkable
class EventStream(Protocol):
    def append(self, event: BaseEvent) -> None: ...
    def __iter__(self) -> Iterator[BaseEvent]: ...
    def __len__(self) -> int: ...
    def replay(self, *, since=None, kinds=None) -> Iterator[BaseEvent]: ...
```

这是 typed Action/Observation append/replay boundary。它不是 Published Task lifecycle、
UI event replay、authoring audit 或 MessageStream 的统一 store。

### 6.2 In-memory implementation

`InMemoryEventStream`：

- list + `Lock`；
- append 后发 structured action/observation log；
- iteration 在 lock 下复制 snapshot；
- replay 使用 `timestamp > since` 和 kind filter。

### 6.3 SQLite implementation

`SqliteEventStream`：

- 每个 Session 一个 `events.sqlite`；
- 每行保存 `event_id`、`kind`、family、timestamp、JSON payload 和可选 `task_id`；
- WAL + autocommit；
- append 由 instance-local `Lock` 串行；
- family 只接受 `BaseAction` / `BaseObservation`；
- 通过 registry 反序列化；
- 支持 `iter_for_task(task_id)` concrete extension；
- 支持 context manager 和幂等 close。

`EventStream.append()` Protocol 没有 `task_id` kwarg。AgentLoop 当前先尝试
`append(event, task_id=...)`，捕获 `TypeError` 后退回 `append(event)`。这是 compatibility
adapter，不是推荐所有 Protocol 扩展都使用异常探测。

## 7. ThoughtStore

### 7.1 当前实现

`ThoughtStore` Protocol：

- `write(record)`；
- `iter_for_event(event_id)`；
- `__len__()`。

实现：

- `NullThoughtStore`：默认 no-op；
- `SqliteThoughtStore`：SQLite persistence，可按 phase allow-list 过滤。

`ThoughtConfig` 从 `THOUGHTS_*` env/CLI 解析 enabled/backend/db/path/phases，
`build_store()` 总是返回一个 store。

### 7.2 装配与关联限制

Standalone CLI 可选装配 SQLite ThoughtStore。Main Page Default Agent 没有传入
ThoughtStore，使用 AgentLoop 默认 `NullThoughtStore`。

当前 AgentLoop 在每个有 content 的 LLM response 上写：

```python
ThoughtRecord(event_id=f"step-{step}", phase="reason", ...)
```

这个 `event_id` 是 step label，不是已经 append 的 `BaseEvent.event_id`，并且可在不同
run 中重复。因此旧文档所称“ThoughtRecord 总能通过 event_id 关联回 EventStream”不
是当前 AgentLoop 保证。

## 8. Audit Substrate

模块：`taskweavn.audit.agent`

### 8.1 CodeAction AuditAgent

`AuditAgent` 接受 `CodeAction + CodeExecutionObservation`，调用 LLM 解析
`AuditVerdict`，返回 `AuditObservation`。内部 LLM/JSON/schema failure 转成
`verdict="inconclusive"`，不会从 `audit()` 抛出。

`AuditConfig` 默认 disabled，可读取 `AUDIT_ENABLED`、`AUDIT_MODEL`、
`AUDIT_API_KEY`。Standalone CLI 可显式装配 auditor。

### 8.2 当前装配边界

- AgentLoop 只在 auditor 存在且 Action/Observation 类型精确匹配时调用 audit；
- Main Page Default Agent 不传 `auditor`，所以此 CodeAction audit path 不在当前 Main
  Page execution lane；
- Main Page 也不装配 `CodeActionTool`；
- Audit Page 还投影 EventStream、logs、runtime config、Task/ASK/confirmation 等更广
  evidence，不能与这个单一 `AuditAgent` 类等同；
- role-aware LLM config 中有 `audit_agent` role name，但 Main Page 当前只为 execution、
  collaborator、read-only inquiry 和 runtime router 创建 clients。

## 9. LLM Boundary

### 9.1 Facade 与 provider

`LLMClient.chat()` 构造 `ChatRequest` 并调用 `LLMProvider.chat()`。当前 provider
implementations 包括 LiteLLM、DeepSeek 和 OpenRouter。Provider contract 包含：

- normalized ChatRequest/ChatResponse；
- optional thinking/provider routing；
- usage、reasoning、provider request metadata；
- retry policy and records。

直接 `LLMClient(...)` 未传 provider 时使用 LiteLLM provider；`LLMClient.from_env()`
通过配置 loader 解析 provider，默认 model 是 `deepseek-v4-pro`。

`complete()` 和 `count_tokens()` 仍走 lazy OpenHands compatibility client，不经过当前
provider-backed `chat()` 的全部 retry/usage/routing path。

### 9.2 Main Page wrappers

未注入共享 LLM 时，Main Page 按 role 构造：

```text
UsageRecordingLLM
  -> AgentConfiguredLLM
  -> LazyLLMClient
  -> LLMClient
  -> provider
```

当前实际装配四个 role client：

- `execution_agent`；
- `collaborator`；
- `read_only_inquiry`；
- `runtime_input_router`。

注入 `dependencies.llm` / `llm_factory` 时，四个角色共享同一个
`UsageRecordingLLM` wrapper，绕过 role resolver/provider profile selection。

Provider 参数、retry、thinking、routing、usage 和敏感日志限制详见
[LLM Reliability](llm-provider-reliability.md)。

## 10. Interaction Boundary

当前交互不是一个统一机制，而是四条相关路径：

1. Authoring ASK；
2. Published Task execution ASK；
3. confirmation via actionable/response AgentMessage；
4. standalone CLI 可选 AutonomyGate/WaitCoordinator。

### 10.1 Message model

`AgentMessage.message_type`：

```text
informational, actionable, response
```

主要字段包括 message/session/task/agent/parent identity、content/context、options、
requires_response、timeout/risk/action linkage、response source/value 和 created_at。

`agent_id` 是开放字符串。当前会出现 `agent`、`user`、`system`、`router`、
`runtime_input_router`、`read_only_inquiry`、`collaborator` 等标签；它不是固定三值 enum，
也不是 Agent registry foreign key。

### 10.2 Message storage and bus

- `SqliteMessageStream` 是 workspace-level durable store，按 `session_id` 过滤；
- `InProcessMessageBus` 是当前唯一 MessageBus implementation；
- bus subscription 只接收订阅后 publish 的消息；
- 历史读取必须单独查询 stream；
- 没有 atomic cursor-based “snapshot + attach” API，因此不能声称简单 replay-then-attach
  自动消除所有 gap/duplicate race；
- bus、Condition 和 live subscription 不跨进程恢复。

### 10.3 Main Page 与 CLI

Main Page 不装配 AutonomyGate。它通过 `AskUserTool` / `RequestConfirmationTool` 显式
创建 durable interaction，并把 Task 置为 `waiting_for_user`。

CLI 只有在传入 `--autonomy` 时才装配：

```text
SqliteMessageStream
  + InProcessMessageBus
  + RiskAssessor
  + AutonomyGate
  + WaitCoordinator
  + stdin responder thread
```

`pending_actionable`、multiple response、timeout self-decision、ASK/confirmation
cross-store 原子性等限制详见 [Interaction Layer](interaction-layer.md)。

## 11. WorkspaceLayout 与 Session

### 11.1 当前 layout

```text
<workspace root>/
├─ .plato/
│  ├─ workspace.sqlite
│  ├─ messages.sqlite
│  ├─ tasks.sqlite
│  ├─ authoring.sqlite
│  ├─ asks.sqlite
│  ├─ ui_commands.sqlite
│  ├─ ui_events.sqlite
│  ├─ results.sqlite
│  ├─ inspection.sqlite
│  ├─ usage.sqlite
│  ├─ contract_revision.sqlite
│  ├─ runtime_config.sqlite
│  ├─ execution_plane.sqlite
│  └─ sessions/
│     └─ <session_id>/
│        ├─ events.sqlite
│        ├─ thoughts.sqlite       # path exists; store is optional
│        ├─ context.sqlite
│        ├─ plan.md               # legacy/path helper; may be absent
│        └─ logs/
├─ shared/
└─ user project files...
```

不是所有 DB 都由 `WorkspaceLayout` 本身创建；它只提供 path math 和目录 bootstrap，
consumer 打开 store 时建 schema。

关键事实：

- `session_project_dir(session_id)` 当前忽略 session id 并返回 workspace root；
- 不存在旧稿的 `sessions/<id>/<id>/` 独立 project root；
- 多个 Session 可以操作同一 workspace files；事实 store 通过 workspace/session id
  隔离；
- `.plato/sessions/<id>` 只保存 Session metadata；
- `bootstrap()` 可把 legacy `.taskweavn` 目录迁移到 `.plato`，并迁移 legacy
  `.code-agent/logs`；
- `bootstrap_session()` 幂等创建 Session metadata/log path。

### 11.2 Session model and manager

`Session` 是 frozen dataclass：

```text
id, name, workspace_root, created_at, last_active_at, status
```

`new_session_id()` 当前生成 8 位 uuid hex。stored status 是：

```text
active, awaiting_user, finished, archived
```

`SessionManager` 使用 workspace `workspace.sqlite`，WAL + autocommit，支持：

```text
create, get, require, list, touch, rename, delete, mark_status, close
```

delete 会移除 registry row，并把 Session metadata directory 移到
`.plato/deleted-sessions/`；不会删除 workspace project root。

### 11.3 Status 有两套派生边界

`core.derive_session_status()` 按 archived override、pending actionable、last
AgentFinishObservation、active 的顺序返回 core SessionStatus。当前直接调用点在测试中。

Main Page snapshot 使用自己的 UI status projection，输入包括 active execution ASK、
authoring ASK、confirmations、Task tree、planning 和 messages，输出：

```text
new, understanding, draft_ready, running, waiting_user, completed, failed
```

不能把 core helper 规则当作 Main Page 当前状态算法。

## 12. 上层产品域参考

底层 substrate 只解释 Action/Observation/AgentLoop，不拥有完整产品事实。当前权威
分工：

| 事实/能力 | 当前 authority | 详细文档 |
|---|---|---|
| RawTask、Plan、TaskNode、draft authoring | authoring stores + AuthoringCommandService | [Authoring Domain](authoring-domain.md) |
| command envelope、idempotency、effects | authoring command protocol | [Authoring Command Protocol](authoring-command-protocol.md) |
| Published Task lifecycle | TaskBus | [TaskBus](bus.md) |
| fixed-route execution | dispatcher/executor + Default Agent | [Agent](agent.md) |
| Task/Plan UI projection | projection services + UI contract | [Task Domain/UI](task-domain-ui-model-separation.md) |
| LLM context input | Session Context Manager | [Context Manager](context-manager.md) |
| ASK/confirmation/messages | AskStore、MessageStream、TaskBus links | [Interaction Layer](interaction-layer.md) |
| Main Page query/command/SSE | server UI contract/gateways | [UI/Backend](ui-backend-communication.md) |
| Runtime Input Router/Contract Revision | deterministic router + commands | [Contract Revision](contract-revision-and-execution-loops.md) |
| service-level local Task API | EmbeddedTaskApiService + Execution Plane store | [Execution Plane](taskbus-service-multi-execution-env.md) |
| tool/capability/skill boundaries | concrete tools、catalogs、skill stores | [Tool Capability](tool-capability-layer.md) |
| workspace evidence | workspace inspection stores/providers | [Workspace Protocol](workspace-communication-protocol.md) |
| logging | LoggingManager and separate trace/frontend paths | [Logging](configurable-logging-system.md) |

## 13. Protocol 参考

### 13.1 Core substrate protocols（非穷举）

| Protocol | 模块 | 关键方法/字段 | 当前 concrete path |
|---|---|---|---|
| `Runtime` | `runtime.base` | `execute(action)` | `LocalRuntime` |
| `EventStream` | `core.event_stream` | append/iterate/len/replay | in-memory / SQLite |
| `ThoughtStore` | `memory.thought_store` | write/iter_for_event/len | null / SQLite |
| `LLMProvider` | `llm.contracts` | chat/complete/count_tokens | LiteLLM / DeepSeek / OpenRouter providers |
| `MessageStream` | `interaction.message` | durable message queries | SQLite |
| `MessageBus` | `interaction.bus` | publish/subscribe/wait/stream | in-process |
| `Subscription` | `interaction.bus` | iterator/close/context manager | private in-process implementation |
| `RiskAssessor` | `interaction.risk` | assess | baseline / LLM / composite |
| `ConfidenceProvider` | `interaction.gate` | get(action) | no production concrete provider |
| `TaskInterruptChecker` | `core.loop` | interrupt_for_task | Main Page TaskBus adapter |
| `AgentLoopProfile` | `core.loop_profile` | prompt/terminal/rejection mapping | profile-specific implementations |
| `Orchestrator` | `orchestration.protocol` | submit/shutdown | only `NullOrchestrator` |

### 13.2 Domain protocols

当前 repository 还有大量 runtime-checkable domain protocols，包括但不限于：

- TaskBus、Task/Plan/Draft stores、publisher、command、projection；
- ContextStore、ContextBuilder、AgentLoopContextProvider；
- UiQueryGateway、UiCommandGateway 和 projection providers；
- TaskApiService、ExecutionPlaneStore、ExecutionEnvRegistry；
- RuntimeConfig stores/bus/mutation service；
- SkillActivationStore；
- usage/logging/web/computer-use adapters。

因此，不再维护一个手写的“所有 Protocol 总表”。需要完整列表时应从源码或 generated
API inventory 获取，避免静态文档再次把局部列表误称为全量。

### 13.3 Protocol 使用原则

- Protocol 只承诺声明的 surface；concrete extension 不能被 Protocol-typed caller
  假定存在；
- `@runtime_checkable` 只做结构存在检查，不验证参数/返回值语义；
- 不是每个跨模块调用都必须引入 Protocol；只有存在替换、测试 seam 或 authority
  boundary 时才值得抽象；
- concrete implementation 的额外 kwarg 需要显式 adapter，不应默认依赖 catch-all
  `TypeError`。

## 14. 标识与事实权威

| 标识 | 当前语义 | 注意事项 |
|---|---|---|
| `event_id` | 一个 typed Action/Observation id | Event SQLite schema 未设 UNIQUE |
| `action_id` | Observation 指向 Action | 可为 None，loop-level error 常无 Action |
| `kind` | typed event class discriminator | 依赖 registry import |
| `message_id` | 一个 AgentMessage id | response 用 parent_message_id 关联 actionable |
| `ask_id` | 一个 durable execution/authoring ASK id | ASK 与 confirmation 不是同一 store |
| `session_id` | workspace 内 Session identity | core 默认生成 8 位 hex；API caller 也可携带已有 id |
| `task_id` | Published Task id或 standalone run correlation | Main Page 可跨多个 AgentLoop run 复用 |
| `agent_run_id` | 一个 AgentLoop invocation metadata id | 当前不是 EventStream row column |
| `plan_id` / `task_node_id` | authoring/Plan contract identity | 不等于 Published Task id；有 lineage mapping |
| `workspace_id` | UI/usage/multi-workspace routing identity | 与 filesystem root mapping 由 server registry 管理 |
| `execution_id` | Execution Plane service execution identity | 映射到 TaskBus task id，不是 Agent instance id |

ID 只用于关联；它不决定事实 authority。Task status 看 TaskBus，message response 看
MessageStream，ASK status 看 AskStore，context snapshot 看 ContextStore，usage 看 usage
ledger。

## 15. 资源、并发与恢复

### 15.1 SQLite resources

EventStream、MessageStream、ThoughtStore、SessionManager 以及多数 domain SQLite store
提供 close/context manager 或由 workspace runtime 统一关闭。它们通常使用 WAL、
autocommit 和 process-local locks。

这些锁不构成跨进程 transaction coordinator。Task、ASK、message、context、usage、
UI event 分属不同 SQLite stores，多 store command 通常不是原子事务。

### 15.2 AgentLoop and tools

- AgentLoop synchronous、single-threaded；
- provider call、Tool execution 和 sync wait 都占用当前 run；
- async Autonomy pending queue 只存在当前 run 内存；
- run 结束时 unresolved queue 丢失，durable actionable 仍在 MessageStream；
- Tool shutdown best-effort；
- cooperative interruption 只在明确 safe points 生效。

### 15.3 Product dispatcher

FixedRouteExecutionDispatcher：

- 一个 background worker；
- per-Session duplicate trigger coalescing；
- 按 queue 依次 drain Sessions；
- 不保留跨 Task AgentLoop；
- startup/retry/publish/ASK-answer/manual 等 trigger 请求执行；
- 不提供 distributed lease、heartbeat 或 hard cancellation。

### 15.4 Recovery

当前有针对部分跨-store/进程中断场景的 recovery：

- execution ASK snapshot recovery；
- interrupted running Task startup recovery；
- durable Task/authoring/message/context/UI event stores；
- Execution Plane idempotent request records。

不存在通用 event-sourced 全系统 replay、confirmation 专用补偿器、Agent run checkpoint
restore 或 remote worker recovery。

## 16. Observability

当前 backend logging 是 process-local `LoggingManager` + category-bound
`ObjectLogger`，并保留 early channel logger compatibility bridge。它支持 structured
rules、context、sinks、profiles、archives、redaction 和 same-process control。

必须区分：

- structured manager；
- legacy channel API；
- separate `main_page_trace` helper；
- frontend TypeScript logger；
- diagnostics bundle secondary sanitizer。

日志不是 Task、EventStream、MessageStream、Audit、runtime config 或 usage 的事实权威。
文件扩展、payload mode 和 redaction 限制详见专门的
[Logging architecture](configurable-logging-system.md)。

## 17. 当前非事实与常见误读

| 旧断言/误读 | 当前事实 |
|---|---|
| 全仓库遵守一个向下依赖层级 | 没有该全局铁律；server 是跨域 composition root |
| 文档中的 9 项是所有 runtime-checkable Protocol | 远非全量；Task/Context/UI/Execution Plane 等已有大量 Protocol |
| workspace metadata 位于 `.taskweavn` | canonical metadata root 是 `.plato`，可迁移 legacy `.taskweavn` |
| 每个 Session 有独立嵌套 project root | `session_project_dir()` 当前返回共享 workspace root |
| `task_id` 唯一标识一次 AgentLoop run | Main Page 可复用 domain Task id；单次 run 有 internal `agent_run_id` |
| EventStream + MessageStream 可重建全部产品状态 | 它们只覆盖 execution events/messages；Task、ASK、authoring、context 等有独立 stores |
| AgentMessage.agent_id 只有 agent/user/system | 当前是开放字符串，多个服务角色会写入 |
| ThoughtRecord.event_id 总指向 BaseEvent | 当前 AgentLoop 写 `step-N` label |
| Tool startup/shutdown 永远成功配对 | startup 可抛；finally 对全部 Tool best-effort shutdown |
| AgentLoop.run 永不抛 | 只归一化部分依赖错误；startup/store/bus 等仍可抛 |
| AuditAgent 审计 Main Page 每次代码操作 | Main Page 不装配 CodeActionTool/AuditAgent |
| Main Page 所有 Action 经过 AutonomyGate | Main Page gate 未装配；使用显式 ASK/confirmation |
| replay 后 attach 自动无 gap/duplicate | 当前没有 atomic snapshot/cursor subscription contract |
| Orchestrator 是多 Agent runtime | 只有 Null placeholder，无调用路径 |
| SQLite instance locks 提供分布式安全 | 仅 process-local synchronization |

## 18. 代码与测试索引

Core substrate source：

- `src/taskweavn/types/`
- `src/taskweavn/runtime/`
- `src/taskweavn/tools/`
- `src/taskweavn/core/`
- `src/taskweavn/llm/`
- `src/taskweavn/memory/`
- `src/taskweavn/audit/`
- `src/taskweavn/interaction/`
- `src/taskweavn/observability/`

Product assembly source：

- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_agent.py`
- `src/taskweavn/server/ui_contract/`
- `src/taskweavn/task/`
- `src/taskweavn/context/`
- `src/taskweavn/contract_revision/`
- `src/taskweavn/execution_plane/`
- `src/taskweavn/runtime_config/`
- `src/taskweavn/workspace_inspection/`
- `src/taskweavn/skills/`
- `src/taskweavn/usage/`

核心验证测试：

- `tests/test_types.py`
- `tests/test_runtime.py`
- `tests/test_tools_fs.py`
- `tests/test_tools_shell.py`
- `tests/test_workspace.py`
- `tests/test_event_stream.py`
- `tests/test_sqlite_event_stream.py`
- `tests/test_thought_store.py`
- `tests/test_thought_config.py`
- `tests/test_sqlite_thought_store.py`
- `tests/test_audit.py`
- `tests/test_loop.py`
- `tests/test_loop_interaction.py`
- `tests/test_loop_profile_contract.py`
- `tests/test_agent_message.py`
- `tests/test_message_bus.py`
- `tests/test_sqlite_message_stream.py`
- `tests/test_wait_coordinator.py`
- `tests/test_workspace_layout.py`
- `tests/test_session_manager.py`
- `tests/test_session_status.py`
- `tests/test_main_page_sidecar_app.py`

维护本文时，不应手工声称“全量”。先确认当前 source surface，再更新对应事实、入口装配
差异和验证记录。
