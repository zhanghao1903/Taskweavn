# Configurable Logging System Technical Design

> Status: implemented v1
> Last Updated: 2026-06-24
> Scope: server core execution line, local sidecar, Router/read-only inquiry, Agent LLM logs, diagnostics
> Related Plan: [Configurable logging feature plan](../plans/feature/configurable-logging-system.md)
> Related Architecture: [Architecture Reference](reference.md)

Product 1.1 alignment: logging now supports the local sidecar runtime, diagnostic
bundles, workspace inspection summaries, token usage analytics, Runtime Input
Router, and Agent LLM calls. LLM observability is split conceptually into
input/output logs for prompt/response payloads and metadata logs for provider,
usage, retry, routing, and diagnostics-safe summaries.

---

## 1. 背景

TaskWeavn 当前日志系统位于 `src/taskweavn/observability/setup.py`，能力很轻：

```text
taskweavn.tool        -> <log_dir>/tool.log
taskweavn.action      -> <log_dir>/action.log
taskweavn.observation -> <log_dir>/observation.log
taskweavn.llm         -> <log_dir>/llm.log
```

现有接口：

```python
configure_logging(log_dir, level=logging.INFO) -> dict[str, Path]
get_channel_logger(channel) -> logging.Logger
```

这足够支撑早期开发，但已经不够支撑接下来的服务端核心线：

- LLM provider 已经有 retry、provider、request_id、usage 等调试元数据；
- Session-scoped execution 架构会引入 Task、TaskBus、Agent、Publisher、ASK
  等对象；
- 用户测试需要按 Session / category 动态打开 DEBUG；
- 长会话需要稳定归档目录和 manifest；
- CLI 体验不能要求用户直接读巨大 JSON。

本设计定义下一阶段实现边界：**可配置、可继承、可热更新、可归档的结构化日志系统**。

---

## 2. 设计目标

1. 保留现有 `configure_logging()` / `get_channel_logger()` 兼容入口。
2. 增加新的 object-aware logger API，日志调用点声明 category、event、context、payload。
3. 支持全局配置与 Session 级覆盖。
4. 支持 category 级日志级别、payload 模式和 sink 路由。
5. 支持运行中热更新，不重复 handler、不丢失当前调用。
6. 支持 Session 日志归档目录与 `manifest.json`。
7. 默认落盘 JSONL，展示层提供 pretty renderer。
8. LLM / Tool / Action / Observation 第一批迁移；Bus / Task / Agent 接口先预留。

---

## 3. 非目标

- 不实现完整 OpenTelemetry / metrics / tracing；这些属于更大的 observability 计划。
- 不实现集中式日志服务，例如 Loki / ELK / Datadog。
- 不实现多进程并发写同一日志文件的强一致协议。
- 不在第一版实现 UI 日志面板。
- 不把日志变成事实源。EventStream / MessageStream 仍是系统状态事实源。
- 不在第一版完成所有对象的深度接入；第一版先完成系统骨架和高价值对象。

---

## 4. 核心决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | JSONL 是权威落盘格式，pretty 是展示格式 | JSONL 支持查询、过滤、UI 聚合；pretty 适合人读但不适合作为事实记录。 |
| D2 | 保留 stdlib logging 兼容桥，但新代码优先用 `ObjectLogger` | 现有调用点可渐进迁移，避免一次性重写所有日志。 |
| D3 | 第一版实现 global/session/category，object override 只做模型和匹配接口预留 | 控制实现规模，同时不堵 Task / Agent 后续扩展。 |
| D4 | `OFF` 是 TaskWeavn 自己的 level，不映射为 stdlib level | `OFF` 表示完全不构造 payload，不只是过滤输出。 |
| D5 | Lazy payload 是强制 API 能力 | DEBUG/full payload 可能包含大 prompt、响应、文件清单，未启用时不能构造。 |
| D6 | 热更新通过 immutable snapshot 原子替换 | emit 路径读快照，update 路径构造新快照再 swap，避免半更新状态。 |
| D7 | Session manifest 是归档入口 | UI、测试人员、归档脚本都应该从 manifest 找日志，而不是猜文件名。 |

---

## 5. 模块布局

当前 `src/taskweavn/observability/` 模块布局：

```text
src/taskweavn/observability/
  __init__.py
  setup.py          # 兼容入口：configure_logging / get_channel_logger
  context.py        # ambient LogContext propagation
  control.py        # same-process UI/server hot-update surface
  events.py         # stable category -> event-name taxonomy
  levels.py         # LogLevel / TRACE / OFF
  models.py         # Pydantic config/event/context models
  manager.py        # LoggingManager, snapshot, hot update, manifest helpers
  logger.py         # ObjectLogger public API
  sinks.py          # FileSink / ConsoleSink / NullSink
  formatting.py     # JSONL formatter + pretty renderer
  bridge.py         # stdlib logging -> LogEvent adapter
  redaction.py      # redaction hooks
```

第一版把 archive/manifest helpers 放在 `manager.py` 内，避免过早拆分一个很薄的 `archive.py`。公共边界保持如下：

- `models.py` 不依赖 manager；
- `logger.py` 只通过全局 manager 发事件；
- `setup.py` 只负责兼容和默认配置；
- `control.py` 是同进程 UI / server 调试接口；
- `events.py` 是事件命名约束入口；
- `bridge.py` 是旧 logger 到新系统的迁移层。

---

## 6. 类型设计

### 6.1 LogLevel

```python
LogLevel = Literal[
    "TRACE",
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "OFF",
]
```

规则：

- `TRACE` 自定义为 `5`，低于 stdlib `DEBUG=10`。
- `OFF` 不进入 stdlib level 比较，直接让 manager 返回 disabled。
- 解析时大小写不敏感，内部统一大写。

### 6.2 LogCategory

```python
LogCategory = Literal[
    "action",
    "observation",
    "llm",
    "task",
    "tool",
    "bus",
    "agent",
    "session",
    "runtime",
    "sandbox",
    "audit",
    "risk",
    "gate",
    "wait",
    "config",
]
```

第一版核心迁移 category：

- `action`
- `observation`
- `llm`
- `tool`
- `runtime`
- `config`

预留 category：

- `task`
- `bus`
- `agent`
- `session`
- `sandbox`
- `audit`
- `risk`
- `gate`
- `wait`

### 6.3 LogContext

```python
class LogContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    trace_id: str | None = None

    action_id: str | None = None
    observation_id: str | None = None
    message_id: str | None = None

    tool_name: str | None = None
    model: str | None = None
    provider: str | None = None
    provider_request_id: str | None = None

    workspace_root: str | None = None
```

设计约束：

- context 只放可索引、可过滤、可关联的字段；
- 大 payload 不进入 context；
- `workspace_root` 第一版可以只在 summary/debug 中出现，避免长期索引用户绝对路径。

### 6.4 LogEvent

```python
class LogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: datetime
    level: LogLevel
    category: LogCategory
    event: str
    message: str
    context: LogContext = LogContext()
    data: dict[str, Any] = Field(default_factory=dict)

    schema_version: Literal["1"] = "1"
```

JSONL envelope：

```json
{
  "ts": "2026-05-12T21:00:00+08:00",
  "level": "INFO",
  "category": "llm",
  "event": "request",
  "message": "LLM request",
  "context": {
    "session_id": "s1",
    "task_id": "t1",
    "model": "deepseek-chat",
    "provider": "deepseek"
  },
  "data": {
    "message_count": 6,
    "tool_count": 5
  },
  "schema_version": "1"
}
```

兼容旧测试和旧工具时，可以额外保留 `msg` 字段作为 `event` 的别名，但新代码读取 `event`。

### 6.5 Sink Config

```python
class RotationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_bytes: int | None = 10 * 1024 * 1024
    backup_count: int = 5


class LogSinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    type: Literal["file", "console", "null"]
    path_template: str | None = None
    format: Literal["jsonl", "pretty"] = "jsonl"
    rotation: RotationConfig | None = None
```

路径模板可用变量：

```text
{archive_root}
{category}
{session_id}
{task_id}
{agent_id}
{date}
```

### 6.6 Rule Config

```python
PayloadMode = Literal["summary", "full", "off"]


class LogRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: LogCategory
    level: LogLevel = "INFO"
    sinks: tuple[str, ...] = ("session_file",)
    payload_mode: PayloadMode = "summary"
    redact: bool = True
```

`payload_mode` 含义：

| Mode | 含义 |
|---|---|
| `summary` | 只写摘要、长度、hash、状态、耗时等轻量字段。 |
| `full` | 写完整 payload，用于 DEBUG/测试。 |
| `off` | 只保留 event/context，不写 data；或直接跳过 data 构造。 |

### 6.7 Scope And Override

```python
class LogScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    tool_name: str | None = None
    model: str | None = None
    provider: str | None = None


class LogOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: LogScope
    category: LogCategory
    level: LogLevel | None = None
    sinks: tuple[str, ...] | None = None
    payload_mode: PayloadMode | None = None
    expires_at: datetime | None = None
```

第一版实现：

- `scope.session_id`
- `category`
- `level`
- `payload_mode`

其他字段先进入 schema 和匹配接口，后续 Task/Agent 接入时启用。

### 6.8 Profile And Config

```python
class LoggingProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    patch: LoggingConfigPatch


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1"] = "1"
    enabled: bool = True
    default_level: LogLevel = "INFO"
    archive_root: str
    sinks: dict[str, LogSinkConfig]
    rules: dict[LogCategory, LogRule]
    profiles: dict[str, LoggingProfile] = Field(default_factory=dict)
    session_overrides: dict[str, LoggingConfigPatch] = Field(default_factory=dict)
    overrides: tuple[LogOverride, ...] = ()
```

`LoggingConfigPatch` 第一版可以只支持：

- `default_level`
- `rules`
- `overrides`

不需要做完整 JSON Patch。

---

## 7. Public API

### 7.1 新 API

```python
def get_object_logger(category: LogCategory) -> ObjectLogger: ...
def get_logging_manager() -> LoggingManager: ...
def configure_observability(config: LoggingConfig) -> LoggingManager: ...
```

`ObjectLogger`：

```python
class ObjectLogger:
    category: LogCategory

    def enabled(
        self,
        level: LogLevel,
        *,
        context: LogContext | None = None,
    ) -> bool: ...

    def log(
        self,
        level: LogLevel,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: Mapping[str, Any] | Callable[[], Mapping[str, Any]] | None = None,
    ) -> None: ...

    def trace(...): ...
    def debug(...): ...
    def info(...): ...
    def warning(...): ...
    def error(...): ...
    def critical(...): ...
```

示例：

```python
logger = get_object_logger("llm")
ctx = LogContext(session_id=session_id, task_id=task_id, model=model, provider=provider)

logger.info(
    "request",
    context=ctx,
    data={
        "message_count": len(messages),
        "tool_count": len(tools or []),
    },
)

logger.debug(
    "raw_response",
    context=ctx,
    data=lambda: {"response": raw_response},
)
```

要求：

- `debug` 未启用时，`lambda` 不执行；
- `payload_mode=off` 时，`data` 不执行；
- `payload_mode=summary` 时，调用点应传 summary data；
- `payload_mode=full` 的 raw data 可以通过 `debug` 或显式 helper 提供。

### 7.2 兼容 API

必须保留：

```python
configure_logging(log_dir: Path | str, *, level: str | int = logging.INFO) -> dict[str, Path]
get_channel_logger(channel: str) -> logging.Logger
```

兼容策略：

1. `configure_logging(log_dir, level)` 生成一份 legacy-style `LoggingConfig`：
   - `archive_root = log_dir`
   - sink path = `{archive_root}/{category}.log`
   - categories = 当前 `CHANNELS`
   - format = `jsonl`
2. `get_channel_logger(channel)` 仍返回 stdlib logger。
3. stdlib logger 安装 `StructuredBridgeHandler`，把 `LogRecord` 转为 `LogEvent`：
   - category = logger name suffix
   - event = `record.getMessage()`
   - message = `record.getMessage()`
   - data = `record.data` if exists
4. 旧 JSON 字段兼容：
   - 新 envelope 包含 `event`
   - 可保留 `msg` alias，降低现有测试迁移成本。

---

## 8. LoggingManager

### 8.1 职责

```python
class LoggingManager:
    def apply_config(self, config: LoggingConfig) -> None: ...
    def get_effective_rule(
        self,
        category: LogCategory,
        context: LogContext | None = None,
    ) -> EffectiveLogRule: ...
    def is_enabled(
        self,
        category: LogCategory,
        level: LogLevel,
        context: LogContext | None = None,
    ) -> bool: ...
    def emit(self, event: LogEvent) -> None: ...
    def apply_profile(self, session_id: str, profile_name: str) -> None: ...
    def update_session_config(self, session_id: str, patch: LoggingConfigPatch) -> None: ...
    def set_level(
        self,
        *,
        session_id: str | None,
        category: LogCategory,
        level: LogLevel,
        duration_seconds: float | None = None,
    ) -> None: ...
    def start_session(self, session_id: str, *, workspace_root: Path | None = None) -> None: ...
    def close_session(self, session_id: str) -> None: ...
```

### 8.2 Snapshot

热更新通过 immutable snapshot：

```python
@dataclass(frozen=True)
class LoggingSnapshot:
    config: LoggingConfig
    config_hash: str
    sinks: Mapping[str, LogSink]
    created_at: datetime
```

Manager 内部：

```python
class LoggingManager:
    _lock: RLock
    _snapshot: LoggingSnapshot
```

更新流程：

```text
1. validate new LoggingConfig
2. render sink configs into new sink instances
3. build new immutable LoggingSnapshot
4. acquire manager lock
5. old_snapshot = self._snapshot
6. self._snapshot = new_snapshot
7. release lock
8. close old sinks outside lock
9. emit config.updated using new snapshot
```

emit 流程：

```text
1. snapshot = manager.current_snapshot()
2. rule = resolve(snapshot.config, category, context)
3. if disabled -> return
4. build data lazily according to payload_mode
5. redact
6. construct LogEvent
7. dispatch to rule.sinks
```

### 8.3 Resolution Order

```text
temporary override, if not expired
  > object override
  > session rule
  > global category rule
  > default_level
```

第一版实际实现：

```text
session/category override
  > global category rule
  > default_level
```

object-level override 保持在数据模型和 resolver 函数签名中，后续开启。

### 8.4 Expiring Overrides

带 `duration_seconds` 的临时 override 不需要后台线程。第一版采用 opportunistic cleanup：

- 每次 `get_effective_rule()` 时过滤已过期 override；
- 每次 `set_level()` / `apply_profile()` 时顺手清理；
- 测试可通过注入 clock 控制时间。

---

## 9. Sink Design

```python
class LogSink(Protocol):
    name: str

    def emit(self, event: LogEvent) -> None: ...
    def close(self) -> None: ...
```

### 9.1 FileSink

职责：

- 渲染 path template；
- 创建 parent directory；
- 写 JSONL；
- 可选 size-based rotation；
- 每个 sink 内部自带 `Lock`，保证单进程多线程写一行日志不会交错。

文件路径按事件 context 动态渲染：

```text
{archive_root}/sessions/{session_id}/{category}.jsonl
{archive_root}/global/{category}.jsonl
```

缺失 `session_id` 时：

- 如果 path 需要 session_id，落到 `_unknown`；
- 或使用 global sink；
- 第一版推荐默认 `session_id="_unknown"`，并在 data 里标记 `missing_context=true`。

### 9.2 ConsoleSink

职责：

- pretty render；
- 默认写 stderr；
- 不作为权威存储。

### 9.3 NullSink

用于：

- 测试；
- `OFF` 或禁用配置；
- benchmark。

---

## 10. Archive And Manifest

默认目录：

```text
<workspace>/.taskweavn/logs/
  global/
    config.jsonl
  sessions/
    <session_id>/
      manifest.json
      session.jsonl
      action.jsonl
      observation.jsonl
      llm.jsonl
      tool.jsonl
      runtime.jsonl
      config.jsonl
      tasks/
      agents/
```

CLI legacy `--log-dir ./logs` 的目录可以继续写：

```text
./logs/action.log
./logs/observation.log
./logs/tool.log
./logs/llm.log
```

但新 session-aware 配置推荐写 `.taskweavn/logs/sessions/<session_id>/...`。

### 10.1 Manifest Schema

```python
class LogArchiveManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1"] = "1"
    session_id: str
    created_at: datetime
    closed_at: datetime | None = None
    config_hash: str
    active_config_path: str | None = None
    archive_root: str
    files: dict[str, str] = Field(default_factory=dict)
    templates: dict[str, str] = Field(default_factory=dict)
    rotation: dict[str, Any] = Field(default_factory=dict)
```

`LoggingManager.write_session_manifest(session_id)` 创建或更新 manifest。

`LoggingManager.close_session_archive(session_id)` 写 `closed_at` 并返回更新后的 manifest。

### 10.2 Archive Reading Contract

UI、测试工具和归档脚本应从 manifest 开始读取，而不是猜测文件名：

```text
1. locate <archive_root>/sessions/<session_id>/manifest.json
2. read files[category] to discover relative file paths
3. stream JSONL by ts, category, event, context.session_id/task_id/action_id
4. use config_hash to tell whether a run changed logging config mid-session
5. if closed_at is null, treat archive as live/incomplete
```

`files` 的 value 是相对 session 目录或 archive root 的展示路径。这样 UI 可以稳定展示 `llm.jsonl`、`tool.jsonl` 这类常规文件。

`templates` 用于描述 session manifest 无法枚举的动态路径，例如需要 `task_id` / `agent_id` 才能落定的文件。默认 profile 第一版不启用 task/agent 拆分，避免一个长会话产生过多小文件；但如果某个 session override 或未来 profile 启用了动态 sink，manifest 会把它列入 `templates`：

```json
{
  "llm": "tasks/{task_id}/llm.jsonl",
  "bus": "agents/{agent_id}/bus.jsonl"
}
```

`rotation` 第一版只记录摘要：

```json
{
  "enabled": true,
  "max_bytes": 10485760,
  "backup_count": 5
}
```

如果后续切到按 task/agent 拆分文件，manifest schema 不需要推翻。运行前只能列出模板；运行后如果需要稳定枚举已出现的 task/agent 文件，可以再扩展一个 archive index，而不是让 session manifest 反复追加海量文件项。例如未来 index 可以记录：

```json
{
  "task.task-123.llm": "tasks/task-123/llm.jsonl",
  "agent.planner.bus": "agents/planner/bus.jsonl"
}
```

权威数据仍是 JSONL；`taskweavn logging render` 只负责把一条 JSONL 渲染成人可读行，不作为稳定存储格式。

---

## 11. Redaction

第一版提供默认 key-based redaction：

```python
DEFAULT_REDACT_KEYS = {
    "api_key",
    "token",
    "authorization",
    "password",
    "secret",
    "cookie",
}
```

规则：

- dict key 包含这些词时，值替换为 `"<redacted>"`；
- list / tuple 递归处理；
- Pydantic model 先 `model_dump(mode="json")` 再处理；
- `payload_mode=summary` 默认不写 raw prompt / raw response；
- `payload_mode=full` 也经过 redaction，除非显式配置 `redact=false`。

---

## 12. Event Naming Taxonomy

日志事件名是长期查询接口的一部分，不应随着内部函数名随意变化。第一版采用短动词或对象状态名：

- `event` 使用 `snake_case`；
- 不重复 category 前缀，例如 `llm` category 里写 `request`，不写 `llm_request`；
- 同一生命周期尽量成对命名：`*_start` / `*_result` / `*_failed`；
- 失败事件统一以 `failed` 结尾，自动恢复或重试事件单独写 `retry`；
- 配置类事件使用过去式，表示配置已经生效，例如 `updated`、`profile_applied`、`level_set`；
- `data` 可以演进，但 `category + event + context` 的语义要保持稳定。

代码侧的公共命名表位于 `taskweavn.observability.events.LOG_EVENTS_BY_CATEGORY`。核心对象通过 `ObjectLogger` 写入的事件必须先进入该表；测试会静态扫描调用点，防止新增事件名绕过文档。

第一版核心事件表以当前已实现调用点为准：

| Category | Event | 语义 |
|---|---|---|
| `action` | `emit` | Action 写入 EventStream。 |
| `observation` | `emit` | Observation 写入 EventStream。 |
| `tool` | `invoke` | Runtime 即将执行某个 Tool / Action。 |
| `tool` | `result` | Tool 执行完成并返回 Observation。 |
| `llm` | `request` | Provider 发送模型请求前后的摘要入口。 |
| `llm` | `response` | Provider 返回模型响应摘要。 |
| `llm` | `retry` | Provider/retry 层决定重试。 |
| `audit` | `request` | AuditAgent 开始评估 Action。 |
| `audit` | `result` | AuditAgent 产生审计结果。 |
| `audit` | `llm_failed` | 审计 LLM 调用失败并降级。 |
| `audit` | `parse_failed` | 审计结果解析失败并降级。 |
| `bus` | `publish` | MessageBus 发布消息。 |
| `bus` | `response_received` | 等待中的 response 已到达。 |
| `bus` | `wait_closed` | Bus 关闭导致等待提前结束。 |
| `bus` | `response_timeout` | 等待 response 超时。 |
| `bus` | `subscribe` | 新订阅创建。 |
| `bus` | `close` | Bus 关闭。 |
| `gate` | `decision` | AutonomyGate 对 Action 做出 proceed/emit 决策。 |
| `wait` | `pending` | async wait 不阻塞，Action 进入待响应状态。 |
| `wait` | `got_response` | sync wait 收到用户响应。 |
| `wait` | `got_response_after_wait` | timeout action 为 `wait` 时，二次无限等待后收到响应。 |
| `wait` | `bus_closed` | 无限等待过程中 Bus 关闭，等待被折算为 skip。 |
| `wait` | `timeout_proceed` | 超时后自动继续。 |
| `wait` | `timeout_skip` | 超时后跳过。 |
| `sandbox` | `container_started` | Docker sandbox container 启动完成。 |
| `sandbox` | `container_remove_failed` | Docker sandbox container 清理失败。 |
| `sandbox` | `execute_start` | Sandbox 即将执行命令。 |
| `sandbox` | `execute_result` | Sandbox 命令执行完成。 |
| `sandbox` | `execute_failed` | Sandbox 执行异常。 |
| `sandbox` | `image_pull_start` | 开始拉取 sandbox image。 |
| `sandbox` | `image_pull_failed` | sandbox image 拉取失败。 |
| `sandbox` | `container_stopped` | Docker sandbox container 停止。 |
| `config` | `updated` | 全局 logging snapshot 已替换。 |
| `config` | `profile_applied` | Session profile 已生效。 |
| `config` | `level_set` | category level override 已生效。 |
| `config` | `session_archive_closed` | Session archive manifest 已关闭。 |

后续新增对象日志时，先扩展本表，再改代码。这样测试人员和 UI 可以把 `event` 当成稳定筛选条件。

---

## 13. Integration Plan

### 13.1 Current Emitters

当前日志点：

| 当前模块 | 当前 category | 迁移方式 |
|---|---|---|
| `core/event_stream.py` | `action` / `observation` | 用 `ObjectLogger` 写 `emit` event，context 带 event/action/observation id。 |
| `core/sqlite_event_stream.py` | `action` / `observation` | 同上，并补 task_id if available。 |
| `runtime/local.py` | `tool` | 用 `tool` + `runtime` category，区分 `invoke` / `result`。 |
| `llm/providers/*` | `llm` | 用 `llm` category，记录 provider/model/retry/usage/request_id。 |
| `llm/retry.py` | `llm` | retry 事件写 `retry`。 |
| `audit/agent.py` | stdlib module logger | 通过 bridge 或迁移到 `audit` category。 |
| `runtime/sandbox.py` | stdlib module logger | 通过 bridge 或迁移到 `sandbox` category。 |

### 13.2 LLM Event Payload

INFO summary：

```json
{
  "message_count": 8,
  "tool_count": 5,
  "provider": "deepseek",
  "model": "deepseek-chat",
  "thinking_enabled": false
}
```

DEBUG/full：

```json
{
  "messages": [...],
  "tools": [...],
  "raw_response": {...}
}
```

Retry：

```json
{
  "attempt": 2,
  "classification": "rate_limit",
  "delay_seconds": 1.5,
  "error": "429 ..."
}
```

### 13.3 Tool / Runtime Payload

INFO summary：

```json
{
  "tool_name": "write_file",
  "action_kind": "WriteFileAction",
  "result_kind": "FileWriteObservation",
  "success": true,
  "duration_ms": 12.4
}
```

DEBUG/full 可包含 action payload 和 observation payload。

---

## 14. CLI And User Entry Points

当前 CLI 入口：

```text
--log-dir PATH                 # 保留
--logging-profile normal|quiet|debug-llm|debug-tools|debug-bus|full-debug
--logging-config PATH          # JSON LoggingConfig
--log-level LEVEL              # default category level
```

示例：

```bash
uv run taskweavn run \
  --task "inspect docs" \
  --workspace . \
  --session-id debug-llm-run \
  --logging-profile debug-llm \
  --log-level INFO
```

配置文件第一版使用 JSON，直接反序列化完整 `LoggingConfig`。YAML 暂不解析，因为当前项目不依赖 PyYAML；用户传入 `.yaml` / `.yml` 时会得到明确错误。跨进程热更新不是当前 CLI 的能力；运行中修改日志配置应走同进程 `LoggingControlService`。

归档检查命令：

```bash
uv run taskweavn logging profiles
uv run taskweavn logging manifest --log-dir ./logs --session-id debug-llm-run
uv run taskweavn logging render ./logs/sessions/debug-llm-run/llm.jsonl --limit 50
```

---

## 15. Backward Compatibility

必须保持：

- `from taskweavn.observability import CHANNELS, configure_logging, get_channel_logger`
- `configure_logging(tmp_path / "logs")`
- 旧文件名：`tool.log` / `action.log` / `observation.log` / `llm.log`
- 旧调用点：`logger.info("event", extra={"data": payload})`

可以演进：

- JSONL 行可以增加字段；
- tests 可以从只读 `msg` 迁移到读 `event`，但短期可保留 `msg` alias；
- 新 object logger 不必返回 stdlib `logging.Logger`。

兼容策略降低风险：先让旧测试继续通过，再逐步迁移调用点。

---

## 16. Implementation Slices

### Slice 1 — Models And Defaults

产出：

- `levels.py`
- `models.py`
- 默认 config builder：
  - `build_legacy_logging_config(log_dir, level)`
  - `build_session_logging_config(log_dir, level)`

测试：

- level parsing；
- invalid category / sink / template；
- config freeze；
- default config path；
- patch merge；
- session override resolution。

### Slice 2 — Manager, Sinks, ObjectLogger

产出：

- `LoggingManager`
- `ObjectLogger`
- `FileSink`
- `ConsoleSink`
- `NullSink`
- lazy payload behavior；
- redaction。

测试：

- `OFF` 不构造 payload；
- DEBUG 未启用不构造 lazy data；
- apply config 不重复 writer；
- hot swap 后新日志去新 sink；
- redaction。

### Slice 3 — Compatibility Layer

产出：

- `configure_logging()` 内部转新 manager；
- `get_channel_logger()` 安装 bridge handler；
- legacy file path 兼容；
- JSONL 保留 `msg` alias。

测试：

- 当前 `tests/test_observability.py` 继续通过；
- stdlib logger `extra={"data": ...}` 进入新 JSONL；
- unknown channel 仍抛 `ValueError`。

### Slice 4 — Archive And Session Manifest

产出：

- `LogArchiveManifest`
- `write_session_manifest()` / `close_session_archive()`
- session path template。
- dynamic path `templates` for future task/agent sinks.

测试：

- manifest 创建；
- close 后写 `closed_at`；
- session file map 可被读取；
- dynamic task/agent path templates do not pollute concrete `files`.
- missing context fallback。

### Slice 5 — First Object Migration

产出：

- EventStream action/observation；
- Runtime/tool；
- LLM provider/retry；
- Audit/Sandbox bridge 接入。

测试：

- 每个核心 category 至少一个端到端日志；
- LLM retry records 进入 `llm` 日志；
- tool DEBUG/full 行为；
- action/observation context 包含 event/action/observation id。

### Slice 6 — CLI Profiles And Config File

产出：

- `--logging-profile`
- `--log-level`
- `--logging-config`
- JSON `LoggingConfig` loader。
- `taskweavn logging profiles`
- `taskweavn logging manifest`
- `taskweavn logging render`

测试：

- CLI profile debug-llm；
- CLI level default override；
- invalid profile/config/level error；
- JSON config load；
- archive inspection command behavior。

---

## 16. Test Matrix

| Area | Tests |
|---|---|
| Models | `test_logging_models.py` |
| Manager | `test_logging_manager.py` |
| Compatibility | `test_observability.py` |
| Archive | `test_logging_archive.py` |
| Control | `test_logging_control.py` |
| Event taxonomy | `test_logging_event_taxonomy.py` |
| CLI | `test_cli.py` |
| LLM integration | `test_llm_providers.py`, `test_llm_retry_policy.py`, `test_llm_contracts.py` |

Full gate:

```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest
```

---

## 17. Open Questions

| Question | Recommendation |
|---|---|
| YAML dependency now or later? | Later. V1 supports JSON `LoggingConfig`; YAML belongs in a broader configuration subsystem. |
| Keep old `msg` forever? | Keep during Phase 3B; deprecate only after docs/tests migrate to `event`. |
| Should logs live under `.taskweavn` or `logs/`? | CLI default remains `./logs`; workspace-integrated UI can later choose `.taskweavn/logs`. |
| Do we need background expiry thread? | No for v1; opportunistic cleanup is simpler and testable. |
| Should EventStream mirror all logs? | No. Logs can reference event ids, but EventStream remains the fact source. |
| Should default archive split by task/agent? | No for v1. Use session/category files and manifest `templates` for future dynamic sinks. |

---

## 18. Acceptance Criteria

This technical design is implemented when:

- existing logging API keeps working;
- new `ObjectLogger` supports lazy payload and structured context;
- logging config supports global/session/category effective rules;
- `OFF` prevents payload construction;
- hot update swaps config without duplicate handlers;
- session archive manifest exists and supports dynamic `templates`;
- LLM retry/provider metadata can be logged at summary/full levels;
- core object logs use documented event names;
- docs explain user-facing logging profile and config options;
- tests cover config models, manager, compatibility, archive, control, CLI, event taxonomy, and first object integrations.
