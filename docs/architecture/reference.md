# TaskWeavn — 核心架构参考

> 版本 v1.0 · 2026-05-08
>
> 关联文档：
> - [项目计划](../project/roadmap.md)
> - [多 Agent 协作架构](multi-agent-collaboration.md)
> - [Interaction Layer 技术设计](interaction-layer.md)
>
> 本文档面向**贡献者**：当你在某一层工作时，需要快速搞清楚"周围有哪些抽象、它们之间如何契约、对象的生命周期是怎样的"。
>
> 不重复设计动机（见上方关联文档）；只列**当前代码里有什么**、**Protocol 长什么样**、**对象什么时候被创建/释放**。
> 范围：截至 Phase 3.6a。

---

## 目录

1. [分层与依赖](#1-分层与依赖)
2. [Types — 类型化事件骨架](#2-types--类型化事件骨架)
3. [Tools / Runtime — 执行层](#3-tools--runtime--执行层)
4. [LLM — 模型客户端](#4-llm--模型客户端)
5. [Memory / EventStream — 持久层](#5-memory--eventstream--持久层)
6. [Audit — 审计层](#6-audit--审计层)
7. [Interaction — 交互层](#7-interaction--交互层)
8. [Workspace / Session — 工作区与会话](#8-workspace--session--工作区与会话)
9. [Orchestration — 多 Agent 占位](#9-orchestration--多-agent-占位)
10. [Core — AgentLoop 编排](#10-core--agentloop-编排)
11. [Protocol 总表](#11-protocol-总表)
12. [标识与命名空间](#12-标识与命名空间)
13. [生命周期](#13-生命周期)
14. [双流架构（events ⊕ messages）](#14-双流架构events--messages)
15. [横切设计模式](#15-横切设计模式)

---

## 1. 分层与依赖

```
                    ┌──────────────────────────────────────────┐
                    │              CLI (typer)                 │
                    └────────────────────┬─────────────────────┘
                                         │
                    ┌────────────────────▼─────────────────────┐
                    │              Core                        │
                    │   AgentLoop · Session · WorkspaceLayout  │
                    └─┬──────┬──────────┬──────────┬────────┬──┘
                      │      │          │          │        │
       ┌──────────────▼┐ ┌───▼────┐ ┌───▼─────┐ ┌──▼───┐ ┌──▼──────────┐
       │  Interaction  │ │ Audit  │ │ Memory  │ │ LLM  │ │ Orchestration│
       │ gate · bus ·  │ │AuditAg │ │Thought  │ │Client│ │Orchestrator  │
       │ wait · risk · │ │Verdict │ │Store    │ │      │ │ (Phase 4)    │
       │ message       │ │        │ │         │ │      │ │              │
       └─┬─────────────┘ └────────┘ └────────┬┘ └──────┘ └──────────────┘
         │                                   │
       ┌─▼─────────────────────────┐  ┌──────▼─────────────┐
       │   EventStream + Tools     │  │   Runtime          │
       │   tool · workspace · fs   │  │   LocalRuntime     │
       └─┬─────────────────────────┘  └─┬──────────────────┘
         │                              │
       ┌─▼──────────────────────────────▼───┐
       │   Types — BaseEvent/Action/Obs     │
       │   ActionRegistry / ObsRegistry     │
       └────────────────────────────────────┘
```

**依赖方向铁律**：箭头永远向下。
- `types` 不依赖任何业务层。
- `runtime` 只依赖 `types`。
- `interaction` / `audit` / `memory` / `llm` 只依赖 `types` + `runtime`（如有）。
- `core` 把上面所有层粘合成一次 `AgentLoop.run()`。
- `cli` 只负责把命令行参数装配成 `core` 对象。

层与层之间通过 **Protocol** 解耦——所有跨层依赖都先写 Protocol，再给一个具体实现。

---

## 2. Types — 类型化事件骨架

模块：`taskweavn.types`

### 2.1 BaseEvent / BaseAction / BaseObservation

| 类型              | 定位                                    | 关键字段                                        |
| ----------------- | --------------------------------------- | ----------------------------------------------- |
| `BaseEvent`       | 一切上 EventStream 的对象               | `event_id`, `timestamp`, ClassVar `kind`        |
| `BaseAction`      | 想发生的事（agent / user / system）     | `source`, ClassVar `baseline_risk` ∈ [0, 1]     |
| `BaseObservation` | Action 执行后的结果                     | `action_id`（指回触发它的 Action）, `success`   |

**契约**
- 都是 Pydantic v2 frozen 模型，`extra="forbid"`，`validate_assignment=True`。
- 子类用 `__init_subclass__` 自动注册到 `ActionRegistry` / `ObservationRegistry`，注册键就是 `kind`（默认类名，可显式指定）。如果某层只是抽象中间类，传 `register=False` 跳过。
- `baseline_risk` 是**类常量**，子类必须保证 0 ≤ x ≤ 1，否则定义时就报错。
- 序列化通过 `to_dict()`（dict）/ `to_json()`（字符串），其中 `kind` 是判别字段；反序列化走 registry 的 `deserialize()`。

### 2.2 已有具体类型

- `taskweavn.types.common` — `AgentFinishAction`、`AgentFinishObservation`、`ErrorObservation`
- `taskweavn.types.code_action` — `CodeAction`、`CodeExecutionObservation`、`FileChange`、`TrackingConfig`
- `taskweavn.tools.fs` — `ReadFileAction/WriteFileAction/ListDirAction` + 对应 Observation
- `taskweavn.tools.shell` — `RunCommandAction` + Observation
- `taskweavn.audit.agent` — `AuditObservation`（包了 LLM 输出 `AuditVerdict`）

### 2.3 Registry

`_Registry[E]` 是一个泛型 dict，按 `kind` 字符串 → 类。两个全局实例：
- `ActionRegistry`
- `ObservationRegistry`

**用途**：SqliteEventStream 把行 JSON 反序列化成原类时只能拿到字符串 `kind`，需要 registry 找回 Python 类。**任何会被持久化的 Action/Observation 必须在导入路径上自动注册**——所以 `taskweavn.tools` 模块得在程序入口被 import 一次。

---

## 3. Tools / Runtime — 执行层

### 3.1 Runtime Protocol

模块：`taskweavn.runtime.base`

```python
@runtime_checkable
class Runtime(Protocol):
    def execute(self, action: BaseAction) -> BaseObservation: ...
```

**契约**
- **永远不能 raise**——所有失败包成 `ErrorObservation`。这是整个 loop 不写 try/except 的前提。
- 接受任意 `BaseAction`，返回任意 `BaseObservation`。具体路由由实现负责。

### 3.2 LocalRuntime

模块：`taskweavn.runtime.local`

进程内 Runtime，按 `type[BaseAction]` → `Executor` 字典分发。

| 方法                                 | 说明                                                       |
| ------------------------------------ | ---------------------------------------------------------- |
| `register(action_type, executor)`    | 把 action 类绑定到一个 `Callable[[Action], Observation]`。 |
| `execute(action)`                    | 找到 executor 调用，捕获所有异常 → `ErrorObservation`。     |

**关键决策**：重复 `register` 同一个 `action_type` 会**静默替换**——简化工具组合，代价是失去重复检测。

`tool` 频道的 logger 在 `invoke` 和 `result` 两个时刻打 JSON，便于事后审计。

### 3.3 Tool 抽象基类

模块：`taskweavn.tools.base`

```python
class Tool[ActionT: BaseAction, ObservationT: BaseObservation](ABC):
    name: ClassVar[str]
    description: ClassVar[str]          # → LLM tool schema 的 description
    action_type: ClassVar[type[BaseAction]]
    observation_type: ClassVar[type[BaseObservation]]

    @abstractmethod
    def execute(self, action: ActionT) -> ObservationT: ...

    def startup(self) -> None: ...      # 可重写：分配 per-task 资源
    def shutdown(self) -> None: ...     # 可重写：释放
    def register(self, runtime: LocalRuntime) -> None: ...
```

**Tool 把四件事打包**：Action 类型、Observation 类型、LLM 看到的 schema 信息、execute 函数。

**生命周期**（详见 §13）：`AgentLoop.run()` 进入时调用每个 tool 的 `startup()`，`finally` 块里调用 `shutdown()`。execute 期间任何异常由 Runtime 捕获，不会污染 startup/shutdown 配对。

### 3.4 Workspace（沙盒根）

模块：`taskweavn.tools.workspace`

`Workspace(root)` 是所有文件系统工具的路径解析器：
- `resolve(path)` 把传入路径（相对/绝对）解析到 `root` 之下；
- 越界时抛 `PathOutsideWorkspaceError`。

这是**纵深防御**，不是真正的安全边界（Phase 2.2 的 sandbox runtime 才是）。

---

## 4. LLM — 模型客户端

模块：`taskweavn.llm.client`

| 对象                                       | 作用                                                       |
| ------------------------------------------ | ---------------------------------------------------------- |
| `LLMClient(model, api_key)`                | 单一 LLM 入口，复用 openhands-sdk 的 LLM + litellm。       |
| `LLMClient.chat(messages, tools)`          | OpenAI-style 同步调用，返回 `ChatResponse`，loop 用这个。 |
| `LLMClient.complete(messages, tools)`      | 走 openhands-sdk，audit / RAG 用。                         |
| `LLMClient.from_env(default_model)`        | 从 `LLM_MODEL` / `LLM_API_KEY` 构造。                      |
| `ChatResponse`                             | `content: str`、`tool_calls: list[ToolCall]`、`raw_assistant_message: dict`（直接回灌进 messages）。 |
| `ToolCall`                                 | `id`、`name`、`arguments`（原始 JSON 字符串）。            |
| `tool_schema_from_action(name, desc, T)`   | 从 Pydantic Action 类生成 OpenAI tool schema，剥掉 `event_id` / `timestamp` / `source`。 |
| `parse_tool_arguments(raw)`                | 容错解析 tool_call 的 `arguments` JSON。                  |

**`chat()` 是 stateless 的**——会话历史由 `AgentLoop` 自己维护并每轮全量传入。`llm` 频道 logger 记 `request` / `response` / `request_failed`。

---

## 5. Memory / EventStream — 持久层

### 5.1 EventStream Protocol

模块：`taskweavn.core.event_stream`

```python
@runtime_checkable
class EventStream(Protocol):
    def append(self, event: BaseEvent) -> None: ...
    def __iter__(self) -> Iterator[BaseEvent]: ...
    def __len__(self) -> int: ...
    def replay(self, *, since=None, kinds=None) -> Iterator[BaseEvent]: ...
```

**契约**
- 仅追加（append-only）——没有 update/delete 接口，事件就是历史。
- 迭代必须返回快照，不能在外部迭代时被并发 append 撞到。
- `replay(since=, kinds=)` 是带过滤的有序回放。

### 5.2 InMemoryEventStream

`list` + `Lock`。append 之后顺手通过 `action` / `observation` 频道 logger 打一行。

### 5.3 SqliteEventStream

模块：`taskweavn.core.sqlite_event_stream`

| 关键点               | 说明                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------- |
| 持久化粒度           | 每个 event 一行，`payload` 存 `to_dict()` JSON。                                        |
| 反序列化             | 按 `family`（`"action"` / `"observation"`）路由到 `ActionRegistry` / `ObsRegistry`。   |
| 模式演进             | Phase 3.3 加了 `task_id` 列；旧库通过 `_migrate_task_id_column()` 在打开时自动 ALTER。 |
| 索引                 | `idx_events_kind`、`idx_events_timestamp`、`idx_events_task_created(task_id, ts, id)`。 |
| 并发                 | autocommit + WAL，单连接 + 内部 `Lock` 串行化 append。                                  |
| **协议外扩展**       | `append(event, *, task_id=None)` 比 Protocol 多一个 kwarg，AgentLoop 用 try/except TypeError 适配。 |
| **协议外扩展**       | `iter_for_task(task_id)`：按 `task_id` 重放本次 run 的所有 event。                      |

### 5.4 ThoughtStore Protocol

模块：`taskweavn.memory.thought_store`

```python
@runtime_checkable
class ThoughtStore(Protocol):
    def write(self, record: ThoughtRecord) -> None: ...
    def iter_for_event(self, event_id: str) -> Iterator[ThoughtRecord]: ...
    def __len__(self) -> int: ...
```

`ThoughtRecord` 是 Pydantic frozen 模型：`event_id`、`phase`、`content`、`timestamp`、`metadata`。
**为什么不放 EventStream**：thought 体量大、并非每个消费者都关心。单独存，靠 `event_id` 关联回 EventStream 即可。

具体实现：
- `NullThoughtStore` — 默认，丢弃所有写入；让消费者无脑 `self.thought_store.write(...)` 就行。
- `SqliteThoughtStore`（`memory/sqlite_thought_store.py`）— 落盘版，按 `ThoughtConfig` 控制 phases 过滤。

`ThoughtConfig`（`memory/config.py`）—— 从 env / CLI 装配 `enabled` / `backend` / `db_path` / `phases`。`build_store(cfg)` 返回 `ThoughtStore` 实例，loop 永远拿到一个非 None 对象。

---

## 6. Audit — 审计层

模块：`taskweavn.audit.agent`

| 对象                                       | 角色                                                                  |
| ------------------------------------------ | --------------------------------------------------------------------- |
| `AuditConfig(enabled, model, api_key)`     | 装配旋钮，`from_env()` 读 `AUDIT_*` env。                             |
| `AuditAgent(llm, system_prompt)`           | 同步审计器；`from_config(cfg, fallback_llm=)` 是工厂。                |
| `AuditVerdict`（Pydantic）                 | LLM 返回的 JSON 结构：`verdict`、`rationale`、`concerns`、`intent_met`、`scope_respected`。 |
| `AuditObservation`（BaseObservation）      | 把 verdict 包装成 EventStream 事件，`action_id` 指回被审 Action。     |
| `render_audit_system_message(audit)`       | 将 verdict 渲染成 `role=system` 文本，回灌进 LLM messages。           |

**铁律**
- 同步执行，跟在每次 `CodeAction` 后面跑（其他 Action 不审）。
- **绝不会让 loop 崩**——任何异常 / JSON 解析失败 → `verdict="inconclusive"`。
- 默认关闭。
- 模型可独立配置（`AUDIT_MODEL` / `AUDIT_API_KEY`），可以挂在更便宜的小模型上。

---

## 7. Interaction — 交互层

模块：`taskweavn.interaction`（Phase 3 主战场）

> 设计动机和决策细节见 [interaction-layer.md](interaction-layer.md)，本节只列对象表 + Protocol。

### 7.1 Risk

```python
@runtime_checkable
class RiskAssessor(Protocol):
    def assess(self, action: BaseAction, context: AssessmentContext) -> RiskAssessment: ...
```

| 对象                            | 关键字段 / 不变量                                                    |
| ------------------------------- | -------------------------------------------------------------------- |
| `AssessmentContext`             | `workspace_root: Path`、`session_id: str`。                          |
| `RiskAssessment`                | `baseline ∈ [0,1]`、`dynamic ≥ baseline`、`final = max(...)`、`rationale: tuple[str,...]`、`assessor: str`。 |
| `BaselineOnlyAssessor`          | 直接读 `action.baseline_risk`，不做动态评估。                        |
| 链式组合（未来）                | `dynamic ≥ baseline` 是单调不变量，多 assessor max 链仍然单调。      |

### 7.2 Autonomy 行为契约

模块：`taskweavn.interaction.autonomy`

```python
@dataclass(frozen=True)
class AutonomyBehavior:
    trigger: Literal["never", "on_risk", "on_uncertainty", "always"]
    risk_threshold: float                     # on_risk 时用
    confidence_threshold: float               # on_uncertainty 时用
    wait_strategy: Literal["sync", "async"]
    wait_timeout: float | None
    timeout_action: Literal["wait", "proceed_default", "proceed_confident", "skip"]
    notify_on_proceed: bool
```

5 个预设：`full_auto` / `risk_gated`（默认）/ `careful` / `collaborative` / `manual`。
通过 `AUTONOMY_PRESETS["risk_gated"]` 取，用 `dataclasses.replace(...)` 微调。

### 7.3 AutonomyGate

模块：`taskweavn.interaction.gate`

```python
class AutonomyGate:
    def __init__(self, behavior, assessor, confidence_provider=None) -> None
    def check(self, action, context) -> GateDecision
```

| 输出 | 含义 |
| ---- | ---- |
| `GateVerdict.PROCEED` | 直接执行；`inform_user` 决定是否发 informational 通知。 |
| `GateVerdict.EMIT`    | 发 actionable，等待用户回应。                          |

`ConfidenceProvider`（Protocol，3.7+ 才有具体实现）—— `get(action) -> float ∈ [0,1]`，缺省 `1.0`（完全自信，所以 `on_uncertainty` 永远 PROCEED）。

### 7.4 AgentMessage + MessageStream

模块：`taskweavn.interaction.message`

```python
class AgentMessage(BaseModel, frozen=True, extra="forbid"):
    message_id: str
    session_id: str
    task_id: str | None
    agent_id: str = "agent"          # "agent" / "user" / "system"
    parent_message_id: str | None     # response 指向 actionable
    message_type: Literal["informational", "actionable", "response"]
    content: str
    context: dict[str, Any]
    action_options: list[str]         # actionable 专用
    requires_response: bool
    timeout_seconds: float | None     # per-message 覆盖
    risk_assessment: RiskAssessment | None
    related_action_id: str | None     # 指向触发它的 BaseAction.event_id
    response_source: ResponseSource | None
    response_value: str | None
    created_at: datetime
```

`ResponseSource` ∈ `{user, timeout_default, timeout_confident, timeout_skip, auto_proceed}`。

```python
@runtime_checkable
class MessageStream(Protocol):
    def get(self, message_id) -> AgentMessage | None
    def list_for_session(self, sid, *, types=, since=, limit=) -> Iterator[AgentMessage]
    def list_for_task(self, task_id, ...) -> Iterator[AgentMessage]
    def list_for_agent(self, agent_id, ...) -> Iterator[AgentMessage]
    def pending_actionable(self, sid, *, task_id=None) -> list[AgentMessage]
    def response_for(self, message_id) -> AgentMessage | None
    def thread(self, message_id) -> list[AgentMessage]
    def __len__(self) -> int
```

`SqliteMessageStream` 是默认实现，工作区级单库（`<workspace>/.taskweavn/messages.sqlite`），用 `session_id` 列做行级隔离。

`pending_actionable` 用 `NOT EXISTS` 反 join 找"已发但未应答"的 actionable。

### 7.5 MessageBus + Subscription

模块：`taskweavn.interaction.bus`

```python
@runtime_checkable
class MessageBus(Protocol):
    def publish(self, message: AgentMessage) -> None
    def subscribe(self, session_id, *, types=None) -> Subscription
    def wait_for_response(self, message_id, timeout) -> AgentMessage | None
    @property
    def stream(self) -> MessageStream

@runtime_checkable
class Subscription(Protocol):
    def __iter__(self) -> Iterator[AgentMessage]
    def __next__(self) -> AgentMessage
    def close(self) -> None
    # 也是 context manager
```

**InProcessMessageBus 实现要点**
- 一个 `threading.Condition` 串起 publish / wait_for_response / subscription 三类等待者。
- `publish` 在锁内 INSERT → 派发给匹配的订阅 → `notify_all`。
- `wait_for_response` 用谓词重检 + `cond.wait(timeout=)`；timeout 到期返回 `None`，bus 关闭也返回 `None`。
- Subscription 只看**订阅之后**发布的消息；要看历史 → 配合 `stream.list_for_session()` 走 replay-then-attach。
- 关闭传递性：`bus.close()` → 标记所有 sub 关闭、所有等待者醒并返回 `None`。

### 7.6 WaitCoordinator

模块：`taskweavn.interaction.wait`

把"actionable 已发布"翻译成"loop 下一步该干什么"。

```python
class WaitOutcome(Enum):
    GOT_RESPONSE = "got_response"
    TIMED_OUT_PROCEED = "timed_out_proceed"
    TIMED_OUT_SKIP = "timed_out_skip"
    PENDING = "pending"          # async 专用

@dataclass(frozen=True)
class WaitResult:
    outcome: WaitOutcome
    response_value: str | None
    response_source: ResponseSource | None
    response: AgentMessage | None
    notice: AgentMessage | None  # 若发了 timeout 自决策通知
```

`handle_actionable(message)` 的逻辑：
- `wait_strategy="async"` → 立刻返回 `PENDING`。
- `sync` → `bus.wait_for_response(...)`，按 `timeout_action` 分支：
  - `wait` —— 永久等（再次 `wait_for_response(timeout=None)`，bus 关闭 → SKIP）。
  - `proceed_default` —— 第一个 option 当合成应答。
  - `proceed_confident` —— Phase 3 退化到 default（待 ConfidenceProvider 接入）。
  - `skip` —— 跳过这个 action。
- 当 `notify_on_proceed=True`，自决策时发一条 `informational` 通知（`auto_decision` 字段写明分支）。

---

## 8. Workspace / Session — 工作区与会话

### 8.1 WorkspaceLayout

模块：`taskweavn.core.workspace_layout`

**纯路径数学**——不开任何文件，不连任何库。

```
<workspace_root>/
├─ .taskweavn/
│   ├─ workspace.sqlite           # session 注册表
│   └─ messages.sqlite            # 工作区级消息（按 session_id 隔离）
├─ shared/                         # 跨 session 协作（Phase 3.5+）
└─ sessions/
    └─ <session_id>/
        ├─ .session/               # session 私有元数据
        │   ├─ events.sqlite
        │   ├─ thoughts.sqlite
        │   ├─ plan.md
        │   └─ logs/
        └─ <session_id>/           # agent 工具实际操作的项目根
```

两层 `<session_id>/` 嵌套：外层放元数据，内层是 tool 真正解析路径的 root，从而 `.session/` 永远不会被 LLM 看见。

`bootstrap()` / `bootstrap_session(id)` 都是幂等的。

### 8.2 Session

模块：`taskweavn.core.session`

```python
@dataclass(frozen=True)
class Session:
    id: str                   # 8 位 hex
    name: str
    workspace_root: Path
    created_at: datetime
    last_active_at: datetime
    status: Literal["active", "awaiting_user", "finished", "archived"]
```

**纯被动数据**——所有路径属性都是 `WorkspaceLayout` 的派生 view（`events_db_path`、`messages_db_path`、`logs_dir` 等）。变更走 `SessionManager`。

### 8.3 SessionManager

模块：`taskweavn.core.session_manager`

CRUD over `workspace.sqlite/sessions`：`create / get / require / list / touch / mark_status`。

WAL + autocommit。`__enter__` / `__exit__` 关连接，幂等。

---

## 9. Orchestration — 多 Agent 占位

模块：`taskweavn.orchestration.protocol`

```python
@runtime_checkable
class Orchestrator(Protocol):
    def submit(self, action: BaseAction) -> BaseObservation
    def shutdown(self) -> None

class NullOrchestrator: ...   # submit 抛 NotImplementedError
```

**故意只有壳**：Phase 1 把多 agent 边界**形状**冻结下来，单 agent 核心日后无需重构。Phase 4 (E4) 才填实现。

---

## 10. Core — AgentLoop 编排

模块：`taskweavn.core.loop`

```python
@dataclass
class AgentLoop:
    # —— 必备 ——
    llm: LLMClient
    runtime: Runtime
    tools: list[Tool]
    event_stream: EventStream = InMemoryEventStream()
    thought_store: ThoughtStore = NullThoughtStore()
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_steps: int = 20
    auditor: AuditAgent | None = None

    # —— 交互层（Phase 3.6，可选）——
    session_id: str = "default"
    workspace_root: Path | None = None
    bus: MessageBus | None = None
    gate: AutonomyGate | None = None
    wait_coordinator: WaitCoordinator | None = None
```

### 10.1 装配不变量（`__post_init__`）

- 工具名不能重复，且 `agent_finish` 是保留名。
- 交互层包要么**全有要么全无**：`gate ⇔ wait_coordinator`；
- 有 `gate` ⇒ 必须有 `bus`；
- 有 `gate` ⇒ 必须有 `workspace_root`（assessor 需要）。

### 10.2 LoopResult

```python
@dataclass(frozen=True)
class LoopResult:
    final_answer: str
    steps: int
    finished: bool                  # True 当且仅当 stop_reason ∈ {agent_finish, no_tool_calls}
    stop_reason: Literal["agent_finish", "no_tool_calls", "max_steps"]
```

### 10.3 单步骤主循环（伪代码）

```
for step in 1..max_steps:
    response = llm.chat(messages, tools=schemas)
    record thought (if content)
    append response to messages

    if not response.tool_calls:
        return no_tool_calls

    for tool_call in response.tool_calls:
        if tool_call.name == agent_finish:
            emit AgentFinishAction + AgentFinishObservation
            return agent_finish

        action = build_action(tool_call)        # parse arguments
        if isinstance(action, ErrorObservation):
            emit error; continue

        gate_skip = consult_gate(action)        # ← Phase 3.6 注入点
        if gate_skip is not None:
            emit action + skip_observation; continue

        emit action
        observation = runtime.execute(action)
        emit observation
        feed observation back to messages
        maybe_audit(action, observation, messages)

return max_steps
```

### 10.4 `_consult_gate` 路径

```
gate is None              → None（保持 3.6 之前的行为）
verdict=PROCEED + inform  → publish informational; None
verdict=PROCEED           → None
verdict=EMIT
  ├─ build actionable + bus.publish
  ├─ wait_coordinator.handle_actionable
  ├─ GOT_RESPONSE non-rejection → None
  ├─ GOT_RESPONSE rejection ("no"/"deny"/...) → ErrorObservation("user_declined")
  ├─ TIMED_OUT_PROCEED          → None
  ├─ TIMED_OUT_SKIP             → ErrorObservation("autonomy_timeout_skip")
  └─ PENDING                    → ErrorObservation("autonomy_pending")  *3.6b 才会真 drain*
```

拒绝词集（大小写不敏感）：`{"no","n","deny","reject","skip","cancel","abort"}`。

### 10.5 `_append_event`：task_id 鸭子类型适配

```python
try:
    self.event_stream.append(event, task_id=self._current_task_id)
except TypeError:
    self.event_stream.append(event)
```

EventStream Protocol 只有 `append(event)`。`SqliteEventStream` 多出一个 kwarg；用 try/except 让两者同时工作，而不必在 Protocol 里强加。

---

## 11. Protocol 总表

下表列出**所有 `runtime_checkable` Protocol**——任何跨层契约的入口。

| Protocol             | 模块                                  | 关键方法                                                   | 默认实现                       |
| -------------------- | ------------------------------------- | ---------------------------------------------------------- | ------------------------------ |
| `Runtime`            | `runtime.base`                        | `execute(action) → observation`                            | `LocalRuntime`                 |
| `EventStream`        | `core.event_stream`                   | `append`、`__iter__`、`__len__`、`replay`                  | `InMemoryEventStream` / `SqliteEventStream` |
| `ThoughtStore`       | `memory.thought_store`                | `write`、`iter_for_event`、`__len__`                       | `NullThoughtStore` / `SqliteThoughtStore`    |
| `MessageStream`      | `interaction.message`                 | `get`、`list_for_session/task/agent`、`pending_actionable`、`response_for`、`thread`、`__len__` | `SqliteMessageStream`          |
| `MessageBus`         | `interaction.bus`                     | `publish`、`subscribe`、`wait_for_response`、`stream`      | `InProcessMessageBus`          |
| `Subscription`       | `interaction.bus`                     | `__iter__`、`__next__`、`close` (+ ctx mgr)                | `_InProcessSubscription`       |
| `RiskAssessor`       | `interaction.risk`                    | `assess(action, context) → RiskAssessment`                 | `BaselineOnlyAssessor`         |
| `ConfidenceProvider` | `interaction.gate`                    | `get(action) → float ∈ [0,1]`                              | （无；Phase 3.7+）             |
| `Orchestrator`       | `orchestration.protocol`              | `submit`、`shutdown`                                       | `NullOrchestrator`             |

**约定**
- 每个 Protocol 都 `@runtime_checkable`，以便测试用 `isinstance` 做形状校验。
- 具体实现可以**多出**额外方法或 kwarg（例如 `SqliteEventStream.append` 多 `task_id`、`SqliteEventStream.iter_for_task`）；调用方根据是否有访问权决定是否使用，对 Protocol 类型的 caller 保持源码兼容。

---

## 12. 标识与命名空间

整个系统有**七种**ID，各管一摊。

| ID                  | 作用域                  | 由谁生成                         | 谁会读                              |
| ------------------- | ----------------------- | -------------------------------- | ----------------------------------- |
| `event_id`          | 单个 BaseEvent          | `BaseEvent` default factory（uuid4 hex） | EventStream、ThoughtStore、关联 Observation |
| `action_id`         | Observation 指向 Action | `BaseObservation` 字段，由 emitter 填 | EventStream consumer，audit         |
| `kind`              | Action / Observation 类 | `__init_subclass__` 注册时       | EventStream 反序列化                |
| `message_id`        | 单个 AgentMessage       | `AgentMessage` default factory   | MessageStream、`parent_message_id`、UI |
| `parent_message_id` | response → actionable   | 应答消息发布者                   | `pending_actionable`、`thread`       |
| `session_id`        | 一次会话                | `SessionManager.create()` 或 CLI 透传 | EventStream、MessageStream、AgentLoop |
| `task_id`           | 一次 `AgentLoop.run()`  | `AgentLoop.run()` 入口（uuid4 hex） | EventStream、MessageStream（task 列） |

**规则**
- `event_id` 跨流唯一；`message_id` 跨流唯一。两者命名空间互不干涉。
- `session_id` 是工作区级别的；同一工作区下 `messages.sqlite` 用它做行级隔离。
- `task_id` 是 session 内的；用于把"一次 run 的 events + messages"重新拼起来（见 §14）。
- `agent_id`（AgentMessage 字段）目前固定 `"agent"` / `"user"` / `"system"`；Phase 4 才填具体 agent 实例 id。

---

## 13. 生命周期

### 13.1 `AgentLoop.run(task)`

```
入口：
  1. mint task_id = uuid4()
  2. for tool in tools: tool.startup()        ← 顺序、串行
执行：
  3. _run_inner(task)                          ← 主循环（§10.3）
退出（finally）：
  4. for tool in tools: tool.shutdown()        ← 即使 startup 失败也跑
  5. self._current_task_id = None
```

**关键性质**
- 单线程、同步。所有阻塞（LLM 调用、`bus.wait_for_response`）都串行发生。
- `task_id` 在整个 run 内一致，泄漏到 `_append_event` 和发出去的 AgentMessage。
- tool startup/shutdown **永远成对**——shutdown 在 `contextlib.suppress(Exception)` 包里跑，不会掩盖主结果。
- LoopResult 总是会返回，绝不抛；除非内部代码 bug。

### 13.2 Tool 生命周期

```
register(runtime)                              ← 装配阶段，一次性
  └→ runtime._executors[ActionT] = self.execute

每次 AgentLoop.run():
   startup()                                   ← per-task 资源（如 docker 容器）
   …多次 execute(action)…
   shutdown()                                  ← 必须幂等、容忍 startup 失败
```

无状态 tool（fs、shell）`startup`/`shutdown` 是 no-op。有状态 tool（`CodeActionTool`）在 startup 里准备容器，shutdown 里销毁。

### 13.3 EventStream / MessageStream 资源

| 实现                  | open                              | close                              |
| --------------------- | --------------------------------- | ---------------------------------- |
| `InMemoryEventStream` | 构造时（`list` + `Lock`）         | 无（GC）                           |
| `SqliteEventStream`   | 构造时连接 + WAL + schema migrate | `close()` / `__exit__`             |
| `SqliteMessageStream` | 同上                              | 同上                               |

**约定**：所有 SQLite-backed 资源都实现了 `__enter__` / `__exit__`，CLI 装配代码用 `with` 管控生命周期。

### 13.4 MessageBus / Subscription

```
bus = InProcessMessageBus(stream)               ← 与 stream 寿命解耦
sub = bus.subscribe(session_id, types=[...])    ← 注册到 bus._subs
with sub:
    for msg in sub:                              ← __next__ 阻塞在 cond
        ...
# 退出 with → sub.close() → 从 bus._subs 中摘除并 cond.notify_all()

bus.close()                                      ← 标记 closed
                                                 → 所有等待者 / 订阅者醒
                                                 → wait_for_response 返回 None
                                                 → __next__ 抛 StopIteration
```

bus 关闭后 `publish` 会抛 `MessageStreamError`；`subscribe` 同样。

### 13.5 Session 生命周期

```
SessionManager.create(name)
  └→ status = "active"
       │
       ├─ AgentLoop.run() 中暂停等用户 → mark_status("awaiting_user")
       ├─ AgentFinishAction → mark_status("finished")
       └─ 用户手动归档（Phase 3.x）  → mark_status("archived")
```

`touch(session_id)` 把 `last_active_at` 推到 now，CLI list 命令按时序排序。

> 注：session.status 的"派生 vs 显式存储"在 Phase 3.7 还在讨论；目前是 `SessionManager.mark_status` 显式驱动。

---

## 14. 双流架构（events ⊕ messages）

```
                                ┌──────────────────────────┐
        Action / Observation ──→│ EventStream              │  per-session events.sqlite
                                │  (审计骨架)              │
                                └──────────────────────────┘
                                        ▲                ▲
                                  task_id 标记      event_id 关联
                                        │                │
                                ┌───────┴─────────┐  ┌───┴─────────────────┐
                                │ AgentLoop.run() │  │ AgentMessage         │  workspace 级 messages.sqlite
                                └─────────────────┘  │  (用户面)            │
                                                     └──────────────────────┘
                                                           ▲
                                                  task_id / session_id
```

**两条流，各管一摊**
- **EventStream** = 审计 / 复盘 / replay；Action+Observation 全量；session 级单库。
- **MessageStream** = 产品面、与用户/其他 agent 的对话；informational/actionable/response；工作区级单库（按 `session_id` 隔离）。

**为什么不合一**
- 两者节奏不同：events 一秒可能上百条，messages 一分钟一两条。
- 受众不同：events 给系统看，messages 给人看。
- 隔离便于演进：消息表加字段不影响事件表索引。

**怎么 join 一次 run**
```sql
-- 重建一次 AgentLoop.run() 的全貌
SELECT * FROM events   WHERE task_id = ? ORDER BY timestamp, id;   -- session events.sqlite
SELECT * FROM messages WHERE task_id = ? ORDER BY created_at, id;  -- workspace messages.sqlite
```
`SqliteEventStream.iter_for_task(task_id)` + `SqliteMessageStream.list_for_task(task_id)` 是这条 join 的程序入口。

---

## 15. 横切设计模式

### 15.1 Protocol + 具体实现 + kwarg 扩展

最常见的扩展方式：在具体实现上**加** kwarg（如 `task_id`），但**不动 Protocol**。AgentLoop 用 try/except TypeError 适配。

适用场景：新字段对老 Protocol 实现是可选的、不需要它就不应被强制实现。

### 15.2 Frozen 数据类 + `dataclasses.replace`

`AutonomyBehavior`、`RiskAssessment`、`Session`、`WorkspaceLayout` 都是 frozen dataclass。要"基于预设微调"——`replace(AUTONOMY_PRESETS["risk_gated"], wait_timeout=10.0)`，绝不原地改。

Pydantic 模型同理：`model_config = ConfigDict(frozen=True, extra="forbid")` 是默认。

### 15.3 "Total functions" / 永不抛

- `Runtime.execute` 永不抛——失败 → `ErrorObservation`。
- `AuditAgent.audit` 永不抛——失败 → `verdict="inconclusive"`。
- `AgentLoop.run` 永不抛——失败要么 LoopResult，要么是真 bug。

这个约定让上层不需要散落的 try/except，控制流变成**结果分支**而不是**异常分支**，更易测试。

### 15.4 Channel logger

`taskweavn.observability.setup.get_channel_logger(name)` 给每个频道（`tool` / `action` / `observation` / `audit` / `llm` 等）一个独立 logger，写到 `<log-dir>/<channel>.jsonl`。每个 EventStream / Runtime / LLMClient 在关键时刻都调一次，便于事后离线分析。

### 15.5 风险单调

> `dynamic ≥ baseline`，组合 assessor 用 `max` 链——单调不变量永远成立。

这个性质让"加一个新 assessor"是**纯加法**，不必担心降低别人已经标的风险。

### 15.6 Replay-then-attach（订阅一致性）

Subscription 不重放历史。订阅前的消息靠 `MessageStream.list_for_*()` 获取，订阅之后才看 live 流。这种"先快照后增量"是常见的 pub/sub 一致性模式，避免订阅者错过/重复消息。

### 15.7 Bundle 不变量

交互层在 AgentLoop 上一组**全有或全无**字段：`gate ⇔ wait_coordinator`，`gate ⇒ bus`，`gate ⇒ workspace_root`。`__post_init__` 做体检，避免半装配状态在运行时出错。

---

## 附：模块速查

| 模块路径                             | 主要导出                                                                        |
| ------------------------------------ | ------------------------------------------------------------------------------- |
| `taskweavn.types`                   | `BaseEvent/Action/Observation`, `ActionRegistry/ObservationRegistry`, `ErrorObservation`, `AgentFinishAction/Observation`, `CodeAction/CodeExecutionObservation`, `FileChange`, `TrackingConfig` |
| `taskweavn.runtime`                 | `Runtime`, `LocalRuntime`                                                       |
| `taskweavn.tools`                   | `Tool`, `Workspace`, `ReadFileTool/WriteFileTool/ListDirTool`, `RunCommandTool`, `CodeActionTool` |
| `taskweavn.llm`                     | `LLMClient`, `ChatResponse`, `ToolCall`, `tool_schema_from_action`              |
| `taskweavn.memory`                  | `ThoughtStore`, `ThoughtRecord`, `NullThoughtStore`, `SqliteThoughtStore`, `ThoughtConfig`, `build_store` |
| `taskweavn.audit`                   | `AuditAgent`, `AuditConfig`, `AuditObservation`, `AuditVerdict`, `render_audit_system_message` |
| `taskweavn.interaction`             | 见 §7（risk / autonomy / gate / message / bus / wait 全集）                     |
| `taskweavn.orchestration`           | `Orchestrator`, `NullOrchestrator`                                              |
| `taskweavn.core`                    | `AgentLoop`, `LoopResult`, `LoopError`, `EventStream`, `InMemoryEventStream`, `SqliteEventStream`, `Session`, `SessionManager`, `WorkspaceLayout` |
| `taskweavn.cli.main`                | `app`（Typer）, `run`, `version`                                                |
| `taskweavn.observability`           | `configure_logging`, `get_channel_logger`                                       |

---

> 文档维护：**任何新 Protocol、任何对生命周期的修改，必须在这里同步更新。**
> 设计动机的争论可以放在对应阶段的 design 文档；本文是事实清单。
