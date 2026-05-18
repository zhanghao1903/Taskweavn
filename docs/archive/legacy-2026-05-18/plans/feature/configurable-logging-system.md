# Feature Plan: 可配置分层日志系统

> Status: done / accepted
> Type: 新特性支持
> Last Updated: 2026-05-13
> Owner/Session: planning session
> Target Implementation Session: independent feature session
> Related Code: `src/taskweavn/observability/setup.py`, `tests/test_observability.py`
> Technical Design: [Configurable Logging System](../../architecture/configurable-logging-system.md)

---

## 1. 背景

当前 TaskWeavn 的日志能力还停留在早期阶段：

- 固定 channel：`tool` / `action` / `observation` / `llm`
- 固定输出：`<log_dir>/<channel>.log`
- 单一日志级别：`configure_logging(log_dir, level=INFO)`
- 只覆盖部分对象：Runtime Tool 调用、EventStream 中的 Action/Observation、LLM 请求响应
- 不支持 Task / Bus / Agent / Session / Config / Scheduler 等核心对象
- 不支持全局配置与 Session 配置的继承和覆盖
- 不支持运行中热更新日志级别或输出位置
- 没有专门的日志归档策略，长会话下日志文件会越来越难管理

这在用户测试、复杂任务调试和多 Agent 演进时会变成瓶颈。测试人员往往需要临时打开某个对象的 debug 日志，例如只看某个 Session 的 LLM 请求、只看某个 Task 的 Bus 消息、或临时把某个 Tool 的日志打到独立文件。

本计划目标是把现有“简单 channel logger”升级为“可配置、可继承、可热更新、可归档”的日志系统。

---

## 2. 目标

1. 建立完整日志配置模型，支持：
   - 全局默认配置
   - Session 级继承与重写
   - 对象级配置覆盖
   - 运行时热更新
2. 每个重要对象都有可配置日志能力：
   - Action
   - Observation
   - LLM
   - Task
   - Tool
   - Bus
   - Agent
   - Session
   - Runtime / Sandbox
   - Audit / Risk / Gate / Wait
3. 支持日志级别：
   - `TRACE`（可选扩展）
   - `DEBUG`
   - `INFO`
   - `WARNING`
   - `ERROR`
   - `CRITICAL`
   - `OFF`
4. 支持输出位置配置：
   - channel 文件
   - 对象文件
   - Session 目录
   - Task 目录或 Task 聚合文件
   - 控制台
   - 后续可扩展 remote sink
5. 支持日志归档：
   - 按 Session 归档
   - 按日期/大小轮转
   - 生成 session log manifest
6. 保持现有日志用法可平滑迁移，现有 `configure_logging()` 与 `get_channel_logger()` 不应突然失效。

---

## 3. 非目标

- 不在本计划中实现完整 OpenTelemetry / metrics 系统；那属于 `docs/plans/observability.md` 的范围。
- 不做日志可视化 UI，只定义后续 UI 可读取的归档结构和查询接口。
- 不做集中式日志服务，例如 ELK / Loki / Datadog 集成。
- 不做字段级隐私脱敏的完整策略，但预留 redaction hook。
- 不替代 EventStream。日志是调试与归档证据，EventStream 仍是系统状态事实源。

---

## 4. 当前代码事实

当前实现集中在 `src/taskweavn/observability/setup.py`：

```python
LOGGER_PREFIX = "taskweavn"
CHANNELS = ("tool", "action", "observation", "llm")

def get_channel_logger(channel: str) -> logging.Logger:
    ...

def configure_logging(log_dir: Path | str, *, level: str | int = logging.INFO) -> dict[str, Path]:
    ...
```

当前输出格式：

```json
{"ts": "...", "msg": "emit", "data": {...}}
```

当前使用点：

| 模块 | 现状 |
|---|---|
| `core/event_stream.py` | Action / Observation append 时写日志 |
| `core/sqlite_event_stream.py` | Action / Observation append 时写日志 |
| `runtime/local.py` | Tool invoke / result 写日志 |
| `llm/client.py` | LLM request / response / failure 写日志 |
| `audit/agent.py` | 使用普通 module logger，未接入 channel |
| `runtime/sandbox.py` | 使用普通 module logger，未接入 channel |
| Bus / Task / Agent | 暂无统一日志 channel |

---

## 5. 主要问题

| 问题 | 影响 |
|---|---|
| channel 固定 | 后续 Task / Bus / Agent 等对象接入会不断改全局常量 |
| 级别单一 | 不能单独把 LLM 调到 DEBUG，同时保持 Tool 为 INFO |
| 输出固定 | 无法把某个 Session 或对象的日志写到专门目录 |
| 没有继承模型 | Session 无法继承全局配置后局部覆盖 |
| 无热更新 | 测试中无法临时打开调试日志，只能重启进程 |
| 没有归档 manifest | 任务完成后无法稳定定位一个 Session 的所有日志文件 |
| 日志上下文不足 | 缺少 session_id、task_id、agent_id、trace_id 等统一字段 |
| 普通 logger 与 channel logger 混用 | Sandbox / Audit 等日志可能和主日志体系脱节 |

---

## 6. 设计原则

- **Object-aware**：日志配置围绕系统对象，不只是 Python logger 名称。
- **Config first**：日志输出由配置决定，调用点只声明事件和上下文。
- **Session inherits global**：Session 配置默认继承全局配置，只覆盖差异。
- **Hot reload must be atomic**：热更新日志配置时，handler 替换不能丢失或重复写日志。
- **Archive is a first-class output**：日志系统要能告诉用户“这个 Session 的日志归档在哪里”。
- **Structured storage, pretty display**：落盘默认 JSONL，方便机器查询和 UI 回放；给人看的 CLI / UI 默认渲染成短文本。
- **Lightweight INFO, deep DEBUG**：默认 `INFO` 只写摘要、hash、长度、耗时和状态；完整 prompt / response / payload 只在 `DEBUG` 或更细级别输出。
- **Profiles before YAML**：普通用户和测试人员优先通过 logging profile 和 UI/CLI 开关配置 Session，不要求手写完整 YAML。
- **Low overhead when off**：对象级 `OFF` 不应做昂贵 payload 序列化。

---

## 7. 核心概念

### 7.1 LogCategory

第一版建议内置：

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

这些 category 不等同于最终文件名。文件名由 sink 配置决定。

### 7.2 LogScope

日志配置需要支持不同作用域：

| Scope | 示例 | 含义 |
|---|---|---|
| `global` | 所有 Session | 默认配置 |
| `session` | `session_id=s1` | 某个会话内覆盖 |
| `task` | `task_id=t1` | 某个任务的更细覆盖 |
| `agent` | `agent_id=audit-1` | 某个 Agent 覆盖 |
| `tool` | `tool_name=write_file` | 某个 Tool 覆盖 |
| `llm` | `model=deepseek-v4-pro` | 某个模型或 provider 覆盖 |

第一版可以先实现 `global` + `session` + `category`，但接口必须预留 object-level override。

### 7.3 LogSink

```python
class LogSinkConfig(BaseModel):
    name: str
    type: Literal["file", "console", "null"]
    path_template: str | None = None
    format: Literal["jsonl", "pretty"] = "jsonl"
    rotation: RotationConfig | None = None
```

路径模板示例：

```text
{workspace}/.taskweavn/logs/global/{category}.log
{workspace}/.taskweavn/logs/sessions/{session_id}/{category}.log
{workspace}/.taskweavn/logs/sessions/{session_id}/tasks/{task_id}.log
```

### 7.4 LogRule

```python
class LogRule(BaseModel):
    category: str
    level: LogLevel = "INFO"
    sinks: list[str] = ["session_file"]
    payload_mode: Literal["summary", "full", "off"] = "summary"
    redaction: RedactionConfig | None = None
```

### 7.5 LoggingConfig

```python
class LoggingConfig(BaseModel):
    version: Literal["1"] = "1"
    enabled: bool = True
    default_level: LogLevel = "INFO"
    archive_root: str = "{workspace}/.taskweavn/logs"
    sinks: dict[str, LogSinkConfig]
    rules: dict[str, LogRule]
    profiles: dict[str, LoggingProfile] = {}
    overrides: list[LogOverride] = []
    hot_reload: HotReloadConfig = HotReloadConfig()
```

### 7.6 LogContext

所有日志事件应统一携带 context：

```python
class LogContext(BaseModel):
    session_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    trace_id: str | None = None
    action_id: str | None = None
    observation_id: str | None = None
    tool_name: str | None = None
    model: str | None = None
```

### 7.7 LoggingProfile

Profile 是用户友好的配置入口。它不是新的一套规则，而是对 `LoggingConfig` patch 的命名封装：

```python
class LoggingProfile(BaseModel):
    name: str
    description: str
    patch: LoggingConfigPatch
```

建议内置：

| Profile | 用途 |
|---|---|
| `normal` | 默认开发/用户模式，记录关键事件摘要 |
| `quiet` | 只记录 warning/error，适合长任务少打扰 |
| `debug-llm` | 当前 Session 打开 LLM DEBUG，保留更完整请求响应 |
| `debug-tools` | 当前 Session 打开 Tool/Runtime DEBUG |
| `debug-bus` | 当前 Session 打开 Bus/Task/Agent DEBUG |
| `full-debug` | 测试专用，尽可能完整记录，但需要明确提醒日志体积和敏感数据风险 |

---

## 8. 配置继承模型

### 8.1 全局配置

全局配置决定默认日志行为：

```yaml
logging:
  version: "1"
  enabled: true
  default_level: INFO
  archive_root: "{workspace}/.taskweavn/logs"
  sinks:
    session_file:
      type: file
      path_template: "{archive_root}/sessions/{session_id}/{category}.jsonl"
      format: jsonl
    console:
      type: console
      format: pretty
  profiles:
    normal:
      description: "记录关键事件摘要"
    debug-llm:
      description: "打开当前 Session 的 LLM DEBUG 日志"
      patch:
        rules:
          llm:
            level: DEBUG
            payload_mode: full
  rules:
    llm:
      level: INFO
      sinks: [session_file]
      payload_mode: summary
    action:
      level: INFO
      sinks: [session_file]
    observation:
      level: INFO
      sinks: [session_file]
    tool:
      level: INFO
      sinks: [session_file]
    bus:
      level: WARNING
      sinks: [session_file]
```

### 8.2 Session 覆盖

Session 配置继承全局配置，只声明差异。实现层可以支持 YAML patch，但用户层第一入口应该是 profile：

```text
Session logging profile: normal
```

用户在 UI 或 CLI 中切换：

```text
/log profile debug-llm --session current
/log level bus DEBUG --session current --duration 10m
/log quiet --session current
```

系统内部把这些操作转换为 Session logging override：

```yaml
session:
  logging:
    profile: debug-llm
    rules:
      llm:
        level: DEBUG
        payload_mode: full
      bus:
        level: DEBUG
      tool:
        sinks: [session_file, console]
```

合并规则：

- 标量字段：Session 覆盖全局。
- dict 字段：深度合并。
- list 字段：默认替换，后续可扩展 append/remove。
- 未声明 category：继承全局。
- profile 先展开成 patch，再和 Session 显式 override 合并。
- 带 duration 的临时 override 需要记录 expires_at，到期自动回到继承配置。

### 8.3 对象级覆盖

对象覆盖用于测试人员临时调试：

```yaml
overrides:
  - scope:
      session_id: "s1"
      task_id: "t42"
    category: llm
    level: DEBUG
    sinks: [session_file, console]

  - scope:
      tool_name: "run_command"
    category: tool
    level: TRACE
```

匹配优先级：

```text
object override > session rule > global rule > default_level
```

### 8.4 用户配置入口

第一版建议提供三种入口，避免让普通用户直接面对完整配置结构：

| 入口 | 面向对象 | 示例 |
|---|---|---|
| 配置文件 | 开发者 / 高阶用户 | 在项目配置中设置默认 profile、sink、归档目录 |
| Session profile | 普通用户 / 测试人员 | 创建 Session 时选择 `normal` / `debug-llm` / `quiet` |
| 临时调试开关 | 测试人员 / 开发者 | 运行中把当前 Session 的 `llm` 调成 `DEBUG` 10 分钟 |

配置文件是完整能力，profile 和临时开关是用户体验层。系统内部统一落到同一个 effective config。

---

## 9. 日志归档结构

建议归档目录：

```text
.taskweavn/
  logs/
    global/
      taskweavn.jsonl
      config.jsonl
    sessions/
      <session_id>/
        manifest.json
        session.jsonl
        task.jsonl
        bus.jsonl
        agent.jsonl
        llm.jsonl
        tool.jsonl
        action.jsonl
        observation.jsonl
        audit.jsonl
        tasks/
          <task_id>.jsonl
        agents/
          <agent_id>.jsonl
```

### 9.1 Manifest

每个 Session 目录生成 `manifest.json`：

```json
{
  "session_id": "s1",
  "created_at": "...",
  "closed_at": null,
  "config_hash": "...",
  "active_config_path": "...",
  "files": {
    "llm": "llm.jsonl",
    "tool": "tool.jsonl",
    "action": "action.jsonl"
  },
  "rotation": {
    "enabled": true,
    "max_bytes": 10485760,
    "backup_count": 5
  }
}
```

Manifest 的目标是让 UI、测试人员和归档脚本都能稳定找到某个 Session 的日志文件。

### 9.2 Rotation

第一版支持：

- size-based rotation
- session close archive

后续再扩展：

- date-based rotation
- gzip 压缩
- retention policy

---

## 10. 热更新机制

### 10.1 API

```python
class LoggingManager:
    def apply_config(self, config: LoggingConfig) -> None: ...
    def get_effective_config(self, session_id: str | None = None) -> LoggingConfig: ...
    def update_session_config(self, session_id: str, patch: LoggingConfigPatch) -> None: ...
    def apply_profile(self, session_id: str, profile_name: str) -> None: ...
    def set_level(self, scope: LogScope, category: str, level: LogLevel) -> None: ...
    def set_level_temporarily(
        self,
        scope: LogScope,
        category: str,
        level: LogLevel,
        duration_seconds: float,
    ) -> None: ...
    def reload_from_file(self) -> None: ...
```

### 10.2 热更新要求

- 更新必须原子化：旧 handler 移除与新 handler 安装不能造成重复写。
- 正在写日志时不能崩溃。
- 更新后要写一条 `config` category 日志：

```json
{"msg": "logging_config_updated", "data": {"old_hash": "...", "new_hash": "..."}}
```

### 10.3 热更新触发方式

第一版支持手动 API：

- CLI 命令或调试接口调用 `set_level`
- UI / CLI 调用 `apply_profile`
- UI / CLI 调用 `set_level_temporarily`
- 测试中直接调用 `LoggingManager.update_session_config`

后续支持：

- 监听 config 文件变更
- UI 面板切换日志级别

### 10.4 动态打印决策

系统不应该在每个日志点都无条件构造大 payload。调用点先询问当前 context 下该 category / level 是否启用：

```python
if logger.enabled("llm", "DEBUG", context):
    logger.debug("raw_response", context=context, data=lambda: build_raw_response_payload())
```

要求：

- `enabled(...) == False` 时，不调用 lazy payload。
- `payload_mode=summary` 时，只构造摘要 payload。
- `payload_mode=full` 时才构造完整 payload。
- `level=OFF` 时直接跳过。
- effective rule 根据 `session_id`、`task_id`、`agent_id`、`tool_name` 等 context 计算。

---

## 11. 日志事件格式

### 11.1 落盘格式：JSONL

统一落盘格式使用 JSONL envelope：

```json
{
  "ts": "2026-05-10T12:00:00+08:00",
  "level": "INFO",
  "category": "llm",
  "event": "request",
  "message": "llm request",
  "context": {
    "session_id": "s1",
    "task_id": "t1",
    "agent_id": "a1",
    "trace_id": "tr1",
    "model": "deepseek-v4-pro"
  },
  "data": {}
}
```

相比现有格式，新增：

- `level`
- `category`
- `event`
- `context`
- `message`

JSONL 会比纯文本更长，但换来稳定的机器查询、UI 过滤、按 Session/Task 聚合和长期归档。第一版通过以下方式控制体积：

- `INFO` 默认 `payload_mode=summary`
- 大字段默认写 hash、长度、摘要，不写全文
- `DEBUG` / `full` 才写完整 payload
- 支持 rotation
- 支持 category `OFF`

### 11.2 人类展示格式：Pretty View

CLI / UI 不应要求用户直接阅读 JSONL。需要提供 pretty renderer，把同一条 JSONL 渲染成短文本：

```text
12:03:11 INFO  llm.request   task=T3 model=deepseek-v4-pro tokens≈1200
12:03:14 INFO  tool.result   task=T3 tool=write_file success=true duration=31ms
12:03:15 WARN  gate.decision task=T3 risk=0.72 requires_user=true
```

Pretty view 是展示层，不是权威存储。调试人员可以在 UI/CLI 里切换：

- compact timeline
- expanded JSON
- raw JSONL file path

现有 `msg` 可以兼容映射到 `event` 或 `message`。

---

## 12. 对象日志需求

| 对象 | Category | 最低事件 |
|---|---|---|
| Action | `action` | `created` / `emitted` / `gated` / `rejected` |
| Observation | `observation` | `emitted` / `error` |
| LLM | `llm` | `request` / `response` / `retry` / `failure` / `usage` |
| Task | `task` | `created` / `updated` / `status_changed` / `completed` / `failed` |
| Tool | `tool` | `invoke` / `result` / `failure` / `timeout` |
| Bus | `bus` | `publish` / `claim` / `ack` / `wait` / `timeout` |
| Agent | `agent` | `started` / `step` / `delegated` / `finished` / `failed` |
| Session | `session` | `created` / `resumed` / `config_applied` / `closed` |
| Runtime | `runtime` | `execute` / `executor_missing` / `result` |
| Sandbox | `sandbox` | `container_start` / `container_stop` / `pull_image` / `exec` / `cleanup_failure` |
| Audit | `audit` | `request` / `verdict` / `failure` |
| Risk | `risk` | `assess` / `fallback` |
| Gate | `gate` | `decision` |
| Wait | `wait` | `actionable` / `response` / `timeout` |
| Config | `config` | `loaded` / `merged` / `updated` / `reloaded` |

---

## 13. 与 EventStream / MessageStream 的关系

日志不是事实源，不负责重建系统状态。

| 系统 | 作用 |
|---|---|
| EventStream | Action / Observation / lifecycle 的审计事实源 |
| MessageStream | 用户可见消息与确认动作事实源 |
| LoggingSystem | 调试、测试、归档、定位问题 |

设计约束：

- EventStream 事件可以镜像到日志，但日志丢失不应影响系统状态。
- MessageStream 消息可以生成日志，但日志不能成为用户消息事实源。
- 日志可以包含更丰富的调试上下文，例如 retry、duration、raw provider metadata。

---

## 14. 执行切片

### Slice 1: Logging Config Models

产出：

- `LoggingConfig`
- `LogSinkConfig`
- `LogRule`
- `LogScope`
- `LogContext`
- `RotationConfig`
- `HotReloadConfig`
- `LogLevel`，包含 `OFF`

验收：

- Pydantic 校验覆盖非法 level、非法 sink、非法 path template。
- Session config 可以和 global config 深度合并。
- object override 匹配优先级有单元测试。

### Slice 2: LoggingManager

产出：

- `LoggingManager`
- `apply_config`
- `apply_profile`
- `get_effective_rule`
- `set_level`
- `set_level_temporarily`
- `update_session_config`
- handler 原子替换

验收：

- 重新 apply config 不产生重复 FileHandler。
- 热更新后旧级别立即失效，新级别立即生效。
- 多个 Session 可以有不同日志级别和输出目录。
- 用户可以通过 profile 修改 Session 日志配置，不必手写完整 YAML。
- 临时 level override 到期后自动恢复继承配置。

### Slice 3: Structured Logger API

产出：

```python
logger = get_object_logger("llm")
logger.info("request", context=ctx, data=payload)
logger.debug("raw_response", context=ctx, data=lambda: build_raw_payload())
```

兼容：

- `get_channel_logger(channel)` 保留，内部适配新系统。
- `configure_logging(log_dir, level=...)` 保留，内部生成默认 `LoggingConfig`。

验收：

- 现有 `tests/test_observability.py` 仍可通过或有清晰迁移。
- 新 JSONL envelope 包含 level/category/event/context/data。
- `OFF` category 不写日志。
- 未启用 DEBUG 时，lazy payload 不被构造。
- `payload_mode=summary/full/off` 行为有测试覆盖。

### Slice 4: Session Archive Layout

产出：

- Session 日志目录创建
- `manifest.json`
- path template 渲染
- rotation 基础实现

验收：

- 创建 Session 后有稳定日志目录。
- manifest 能列出已启用 category 文件。
- size-based rotation 可测试。

### Slice 5: Core Object Integration

产出：

- Action / Observation 使用新 logger
- LLM 使用新 logger，并记录 retry / provider metadata 的预留字段
- Tool / Runtime 使用新 logger
- Bus / Task / Agent 接入 category，即使第一版事件较少
- Sandbox / Audit 从普通 module logger 迁移或桥接

验收：

- 每类核心对象至少有一条端到端日志测试。
- 可配置某个 category 到 DEBUG，其他 category 仍是 INFO。
- 可配置某个 Session 的 LLM 日志输出到单独文件。

### Slice 6: Hot Reload Entry Points

产出：

- CLI 或调试 API：
  - 查看当前有效日志配置
  - 应用 Session logging profile
  - 设置 session/category level
  - 设置带 duration 的临时 level
  - reload 配置文件
- 测试 helper：
  - 在测试中临时打开某个 category

验收：

- 运行中修改 `llm` level，下一次 LLM 调用生效。
- 修改某个 Session 的 `bus` level，不影响其他 Session。
- 应用 `debug-llm` profile 后，当前 Session 的 LLM payload 从 summary 切到 full。
- 临时 DEBUG 到期后回到原 profile。
- 配置更新事件写入 `config` 日志。

### Slice 7: Docs and Migration

产出：

- 更新用户文档：
  - 日志目录结构
  - 配置示例
  - 测试调试操作
- 更新开发文档：
  - 如何为新对象添加日志
  - 日志事件命名规范
  - payload redaction 约定

验收：

- 新 contributor 能根据文档给新对象接入日志。
- 测试人员能根据文档临时打开 Session 级 DEBUG。

---

## 15. 测试计划

### 15.1 单元测试

- `test_logging_config.py`
- `test_logging_manager.py`
- `test_logging_hot_reload.py`
- `test_logging_archive.py`
- 扩展 `test_observability.py`

### 15.2 关键场景

| 场景 | 期望 |
|---|---|
| 默认配置 | 生成 action/tool/llm/observation 日志，兼容旧行为 |
| Session 覆盖 LLM level | 该 Session 的 LLM DEBUG 生效，其他 Session 不变 |
| Session 使用 profile | `debug-llm` profile 展开成 Session override |
| 临时 DEBUG | 到期后自动恢复原始有效配置 |
| 对象级覆盖 Tool | 指定 tool 进入 TRACE，其他 tool 不变 |
| 热更新 level | 无需重启，下一条日志按新 level 输出 |
| 热更新 sink | 新日志写到新文件，旧 handler 关闭 |
| category OFF | 不序列化 payload，不写文件 |
| lazy payload | 未启用 DEBUG 时，不构造大 payload |
| pretty renderer | 同一条 JSONL 可以渲染成短文本 |
| manifest 生成 | Session 归档目录可被 UI/测试读取 |
| rotation | 文件超过大小后轮转 |
| Audit/Sandbox bridge | 普通 logger 可进入统一归档 |

---

## 16. 配置示例

### 16.1 默认开发配置

```yaml
logging:
  default_level: INFO
  profiles:
    normal:
      description: "记录关键事件摘要"
    debug-llm:
      description: "调试当前 Session 的 LLM 请求响应"
      patch:
        rules:
          llm:
            level: DEBUG
            payload_mode: full
    quiet:
      description: "只记录 warning/error"
      patch:
        default_level: WARNING
  sinks:
    session_file:
      type: file
      path_template: "{archive_root}/sessions/{session_id}/{category}.jsonl"
      format: jsonl
    console:
      type: console
      format: pretty
  rules:
    action: { level: INFO, payload_mode: summary, sinks: [session_file] }
    observation: { level: INFO, payload_mode: summary, sinks: [session_file] }
    tool: { level: INFO, payload_mode: summary, sinks: [session_file] }
    llm: { level: INFO, payload_mode: summary, sinks: [session_file] }
    bus: { level: WARNING, payload_mode: summary, sinks: [session_file] }
    task: { level: INFO, payload_mode: summary, sinks: [session_file] }
```

### 16.2 测试人员调试配置

普通入口：

```text
/log profile debug-llm --session current
/log level bus DEBUG --session current --duration 10m
/log level tool TRACE --task task-123 --duration 5m
```

等价底层配置：

```yaml
session:
  logging:
    profile: debug-llm
    rules:
      llm:
        level: DEBUG
        payload_mode: full
        sinks: [session_file, console]
      bus:
        level: DEBUG
        sinks: [session_file]
    overrides:
      - scope:
          task_id: "task-123"
        category: tool
        level: TRACE
```

---

## 17. 风险与决策点

| 风险 | 处理 |
|---|---|
| 日志系统过度复杂 | 第一版先实现 global/session/category，object override 预留接口 |
| 用户不理解完整 YAML 配置 | 第一版提供 profile、UI/CLI 开关和临时 override，YAML 作为高级入口 |
| JSONL 太长、不适合人读 | 落盘 JSONL，展示层提供 pretty renderer；INFO 默认只写 summary payload |
| 日志 payload 泄漏敏感数据 | 第一版保留 redaction hook，LLM raw prompt 默认 INFO 不完整输出，DEBUG 才输出完整 |
| DEBUG 产生过大日志 | 支持 duration 临时 override、rotation、payload_mode 和 category OFF |
| 热更新造成 handler 泄漏 | 强制测试 handler 数量和文件关闭 |
| 日志与 EventStream 职责重叠 | 文档明确日志不是事实源 |
| 高并发写文件 | 第一版单进程可用；多进程写入后续单独设计 |
| `TRACE` 非 Python 标准 level | 可作为自定义 level，也可第一版映射到 DEBUG 下的细分 event |

---

## 18. 完成标准

该 feature 完成时，应满足：

- 日志配置有 Pydantic schema，并支持全局与 Session 继承覆盖。
- 每个主要对象至少有 category 与基础事件定义。
- 日志输出位置和级别可配置。
- 普通用户可以通过 profile 或 UI/CLI 开关调整 Session 日志，不必手写完整配置。
- Session 日志有稳定归档目录和 manifest。
- 热更新可以修改某个 Session / category 的日志级别。
- 支持 lazy payload，未启用的 DEBUG/FULL 日志不会构造大 payload。
- JSONL 作为权威落盘格式，同时提供 pretty renderer 供人查看。
- 现有四类日志兼容迁移，不破坏已有测试。
- 新增测试覆盖配置合并、热更新、归档、对象级输出和兼容旧 API。

---

## 19. 状态

- Status: done / accepted
- Created: 2026-05-10
- Started: 2026-05-12
- Completed Branch: `codex/configurable-logging-design`
- Accepted: 2026-05-13
- Completed in first implementation pass:
  - Slice 1 partial/full: level helpers, config models, sink/rule/context/event models.
  - Slice 2 partial/full: `LoggingManager`, `ObjectLogger`, file/console/null sinks, lazy payload, redaction.
  - Slice 3 partial/full: legacy `configure_logging()` / `get_channel_logger()` bridge remains compatible with existing channel loggers.
  - Tests added for logging models and manager; existing observability tests still pass.
- Completed in second implementation pass:
  - Slice 4 partial/full: default session archive layout, `manifest.json`, config hash, category file map, close marker, and size-rotation metadata.
  - Slice 6 partial: CLI/runtime entry point for session logging via `configure_session_logging()`, `--logging-profile`, `--logging-config`, and `--log-level`.
  - Built-in profiles expanded: `normal`, `quiet`, `debug-llm`, `debug-tools`, `debug-bus`, `full-debug`.
  - Tests added for session archive manifests, profile scoping, config loading, and CLI validation.
- Completed in third implementation pass:
  - Added ambient log context via `use_log_context()` so `AgentLoop.run()` injects `session_id`, `task_id`, and `workspace_root` once, while lower-level objects add only local ids.
  - Migrated core execution logs to native `ObjectLogger` call sites:
    - `EventStream` / `SqliteEventStream`: `action.emit`, `observation.emit`.
    - `LocalRuntime`: `tool.invoke`, `tool.result`.
    - LLM providers and retry layer: `llm.request`, `llm.response`, `llm.retry`.
    - `AuditAgent`: `audit.request`, `audit.result`, `audit.llm_failed`, `audit.parse_failed`.
    - `MessageBus`, `AutonomyGate`, `WaitCoordinator`: bus publish/wait/subscribe, gate decisions, wait outcomes.
  - User-facing docs now describe session archive layout and logging CLI switches.
- Completed in fourth implementation pass:
  - `SandboxExecutor` now emits native `sandbox.container_started`, `sandbox.execute_start`, `sandbox.execute_result`, `sandbox.execute_failed`, `sandbox.image_pull_*`, and `sandbox.container_stopped` events.
  - Added CLI archive inspection commands:
    - `taskweavn logging profiles`
    - `taskweavn logging manifest --session-id <id>`
    - `taskweavn logging render <jsonl>`
  - Documented that these CLI commands inspect archive files; same-process hot update remains available through `LoggingManager` API until a daemon/control plane exists.
- Completed in fifth implementation pass:
  - Added `LoggingControlService` as the same-process UI/server control surface for runtime logging updates.
  - Added typed control results for profile application, scoped level changes, and session archive close operations.
  - `LoggingManager` now exposes the active immutable config snapshot and rejects negative temporary override durations.
  - User-facing configuration docs now distinguish archive inspection CLI from same-process hot-update control APIs.
  - Technical design now includes the first stable core event naming taxonomy for Action, Observation, Tool, Runtime, LLM, Audit, Bus, Gate, Wait, Sandbox, and Config logs.
  - Added code-level `LOG_EVENTS_BY_CATEGORY` taxonomy plus static tests that verify current `ObjectLogger` call sites use documented event names.
  - Expanded archive/manifest reading contract so UI and test tooling start from `manifest.json` instead of guessing category file paths.
  - Kept default archive layout at session/category granularity, while adding manifest `templates` for future task/agent dynamic sink paths.
  - Manifest generation now uses session-effective rules, so profile/session overrides are reflected in `files` and `templates`.
  - Aligned technical design with the implemented v1 API: JSON config, `--logging-profile`, `--logging-config`, archive inspection commands, and current module layout.
  - README now points users to manifest `files` / `templates` and logging archive inspection commands.
- Verified:
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest` — 441 passed, 1 warning
- Acceptance Notes:
  - Runtime logging configuration, archive layout, same-process control API, event taxonomy, and first core-object integrations are implemented.
  - Cross-process hot update remains explicitly out of v1 scope until a daemon/server control plane exists.
  - Risk-assessor long-call timeout/observability is tracked separately and should not block this logging-system acceptance.
- Follow-ups:
  - daemon / server control plane can later expose cross-process hot update.
  - Task / Agent archive index can be added when TaskBus and Agent templates stabilize.
  - Centralized runtime configuration should eventually absorb logging config resolution into the shared control plane.
