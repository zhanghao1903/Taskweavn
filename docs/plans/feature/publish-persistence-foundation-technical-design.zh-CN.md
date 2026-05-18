# 发布持久化基础：中文详细技术方案

> Status: done
> Type: 后端功能 / server-core persistence technical design
> Last Updated: 2026-05-17
> Owner/Session: backend implementation session
> Parent Plan: [Publish Persistence Foundation](publish-persistence-foundation.md)
> Related Docs: [Task Publisher 使用说明](../../project/task-publishers.md), [Task Publisher 发布记录](../../releases/task-publishers-schedule-api.md), [本地优先 SQLite 讨论](../../discussion/2026-05-16-local-first-storage-sqlite-evaluation.md)

---

## 1. 设计结论

这一阶段的后端工作应先建设 **发布控制面的 SQLite 持久化基础**，而不是先暴露 HTTP/RPC transport。

原因：

1. `TaskPublishService`、`DefaultTaskPublisher`、`DefaultApiTaskPublisher`、`SchedulerPublisher` 已经形成 server-core 语义边界。
2. `SqliteTaskBus` 已经能持久化发布后的 `TaskDomain`，但发布控制面仍是内存态。
3. 如果先做 server transport，会把“不跨进程可靠”的幂等、调度和审计语义暴露给上层。
4. SQLite stores 可以在纯后端测试中闭环，不依赖 UI，也不依赖 HTTP 框架。

本阶段交付目标：

- 发布幂等记录可跨重启保留。
- 发布审计事件可持久追加并按 session/request 查询。
- 定时发布配置和运行状态可跨重启恢复。
- API/scheduler/custom tree/collaborator publish 继续走同一条 `TaskPublishService -> TaskBus` 路径。
- 明确记录并后续关闭当前的“TaskBus 写入成功但幂等记录未写入时崩溃”的窗口。

---

## 2. 当前代码基线

当前已存在的关键后端边界：

| 模块 | 已有类型 | 当前职责 | 本阶段缺口 |
|---|---|---|---|
| `taskweavn.task.publisher_service` | `TaskPublishService` | 统一 preview/publish、幂等检查、审计 hook、pipeline 扩展 | 依赖内存幂等 store 和内存 audit sink |
| `taskweavn.task.publisher_service` | `PublishIdempotencyStore` | 幂等记录协议 | 缺少 SQLite 实现 |
| `taskweavn.task.publisher_service` | `TaskPublishAuditSink` | 发布审计 append 协议 | 缺少 SQLite 实现和查询 helper |
| `taskweavn.task.publisher` | `DefaultTaskPublisher` | 将 `NormalizedTaskTree` 发布到 `TaskBus` | 当前生成随机 task id，幂等崩溃恢复不能靠 task id 自然去重 |
| `taskweavn.task.scheduler` | `ScheduledPublishStore` | 定时发布配置和状态协议 | 缺少 SQLite 实现 |
| `taskweavn.task.scheduler` | `SchedulerPublisher` | tick 到期 schedule，并调用 `TaskPublishService.publish` | 重启后配置和 `next_run_at` 丢失 |
| `taskweavn.task.api_publisher` | `DefaultApiTaskPublisher` | transport-neutral API 适配层 | 缺少持久幂等 store 支撑 |
| `taskweavn.task.sqlite_bus` | `SqliteTaskBus` | 发布后 Task 的 SQLite read/publish surface | 不负责发布幂等、调度或审计 |

现有发布链路：

```text
PublishRequest
  -> optional pipeline expansion
  -> idempotency get
  -> publisher.preview
  -> DefaultTaskPublisher.publish
  -> TaskBus.publish(TaskDomain)
  -> idempotency put
  -> audit record
```

这条路径可以继续保留，但 store 实现需要从内存替换为 SQLite。

---

## 3. 范围边界

### 3.1 本阶段包含

1. 新增 SQLite-backed store：
   - `SqlitePublishIdempotencyStore`
   - `SqliteTaskPublishAuditSink`
   - `SqliteScheduledPublishStore`
2. 新增或复用轻量 SQLite 连接/schema helper。
3. 新增 `publish.sqlite` schema。
4. 补充 `TaskPublishService`、`SchedulerPublisher`、`DefaultApiTaskPublisher` 与 SQLite stores 的集成测试。
5. 更新 task publisher 使用文档和计划索引。

### 3.2 本阶段不包含

- 不做 HTTP/RPC transport。
- 不做 SSE/WebSocket/UI event transport。
- 不做 TaskBus `claim/complete/fail` 执行生命周期。
- 不做 completion-time `task_after` 编排。
- 不做 RawTask/DraftTaskTree authoring 持久化。
- 不做多进程 scheduler leasing。
- 不引入 PostgreSQL、Redis 或外部队列。
- 不建设完整 Storage Governance，只做 `publish.sqlite` 的最小 schema 管理。

---

## 4. 目标架构

```text
API / scheduler / collaborator / custom tree / pipeline
  -> PublishRequest
  -> TaskPublishService
       -> SqlitePublishIdempotencyStore
       -> SqliteTaskPublishAuditSink
       -> optional PipelineTaskLoader
  -> DefaultTaskPublisher
  -> SqliteTaskBus
```

持久化分层：

```text
<workspace>/.taskweavn/
  tasks.sqlite       # Execution Domain: 已发布 TaskBus facts
  publish.sqlite     # Publish Control Plane: 幂等、调度、发布审计
```

设计原则：

- `tasks.sqlite` 是执行域 Task truth。
- `publish.sqlite` 是发布控制面 truth。
- 两者暂时不共享事务边界。
- 当前版本假设单本地后端进程；多进程和分布式锁属于后续治理。
- 发布控制面的 store 不直接依赖 UI、HTTP、EventStream 或 MessageStream。

---

## 5. 推荐文件和导出结构

推荐新增一个聚合实现模块：

```text
src/taskweavn/task/sqlite_publish.py
```

该模块负责：

- 打开并初始化 `publish.sqlite`。
- 实现三个 SQLite store。
- 暴露轻量查询 helper。
- 将 SQLite 错误包装成 publish store 错误。

推荐导出：

```python
from taskweavn.task.sqlite_publish import (
    PublishStoreError,
    SqlitePublishIdempotencyStore,
    SqliteScheduledPublishStore,
    SqliteTaskPublishAuditSink,
)
```

同时在 `src/taskweavn/task/__init__.py` 中导出这些类型，方便测试和后续 service assembly 使用。

不建议在本阶段创建大型 storage framework。若确实需要消除重复，只允许新增小型私有 helper，例如：

```python
def _connect(db_path: str | Path) -> sqlite3.Connection: ...
def _init_schema(conn: sqlite3.Connection) -> None: ...
def _utcnow_iso() -> str: ...
```

---

## 6. 数据库连接规则

每个 SQLite store 初始化时必须：

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

连接行为：

- 构造函数接收 `db_path: str | Path`。
- 自动创建父目录。
- 使用 `sqlite3.Row`。
- 支持 `close()`、`__enter__()`、`__exit__()`。
- 关闭后继续调用方法时，错误风格应与现有 `SqliteTaskBus` 保持一致，测试只需要确认不会静默成功。

事务规则：

- 每个写操作使用短事务。
- 不在事务中调用 LLM、工具、网络、用户等待或 `TaskBus.publish`。
- schema 初始化必须幂等。
- store 层不要吞掉 correctness-sensitive 错误。

---

## 7. Schema 设计

### 7.1 `publish_schema_meta`

用途：记录 `publish.sqlite` 的最小 schema version。

```sql
CREATE TABLE IF NOT EXISTS publish_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

初始化：

```text
key = schema_version
value = 1
```

第一版不需要全局 migration manager。后续 Storage Governance 再统一迁移、备份和健康检查。

### 7.2 `publish_idempotency_records`

用途：保存一个稳定 idempotency key 对应的最终 `PublishResult`。

```sql
CREATE TABLE IF NOT EXISTS publish_idempotency_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    publisher_kind TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    publish_result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, publisher_kind, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_publish_idempotency_session_created
    ON publish_idempotency_records(session_id, created_at, id);
```

唯一键：

```text
(session_id, publisher_kind, idempotency_key)
```

协议映射：

- `get(session_id, publisher_kind, idempotency_key)`：
  - 查不到返回 `None`。
  - 查到后用 `PublishResult.model_validate_json(...)` 还原。
  - 返回 `PublishIdempotencyRecord`。
- `put(record)`：
  - 没有旧记录时插入并返回 `record`。
  - 已有旧记录且 `request_hash` 相同，返回旧记录。
  - 已有旧记录但 `request_hash` 不同，抛出 `PublishIdempotencyConflictError`。

建议实现方式：

1. 先尝试 `INSERT`。
2. 捕获 unique conflict 后读取旧记录。
3. 比较 `request_hash`。
4. 决定返回旧记录或抛 conflict。

不要用 `INSERT OR REPLACE`，因为它会覆盖原始审计意义上的首个结果。

### 7.3 `publish_audit_events`

用途：保存发布控制面的 append-only 审计事实。

```sql
CREATE TABLE IF NOT EXISTS publish_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    request_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    publisher_kind TEXT NOT NULL,
    actor_id TEXT,
    idempotency_key TEXT,
    root_task_ids_json TEXT NOT NULL,
    published_task_ids_json TEXT NOT NULL,
    reason TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_publish_audit_session_created
    ON publish_audit_events(session_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_publish_audit_request
    ON publish_audit_events(request_id, id);

CREATE INDEX IF NOT EXISTS idx_publish_audit_idempotency
    ON publish_audit_events(session_id, publisher_kind, idempotency_key, id);
```

协议映射：

- `record(event)` 是 Protocol 必需方法。
- concrete store 可额外提供：
  - `list_for_session(session_id, *, limit=None)`
  - `list_for_request(request_id)`
  - `list_for_idempotency(session_id, publisher_kind, idempotency_key)`

查询 helper 主要服务测试、debug endpoint 和未来 UI 审计页，不要求加入 Protocol。

### 7.4 `scheduled_publish_configs`

用途：保存 `ScheduledPublishConfig`。

```sql
CREATE TABLE IF NOT EXISTS scheduled_publish_configs (
    schedule_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scheduled_configs_enabled
    ON scheduled_publish_configs(enabled, updated_at, schedule_id);
```

为什么保存完整 JSON：

- `ScheduledPublishConfig` 已经是强类型 Pydantic model。
- 第一版 scheduler 在进程内判断 due，不需要复杂 DB-side query。
- 后续可以按需要增加冗余索引列，不影响协议。

### 7.5 `scheduled_publish_states`

用途：保存可变调度状态。

```sql
CREATE TABLE IF NOT EXISTS scheduled_publish_states (
    schedule_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL,
    last_run_at TEXT,
    next_run_at TEXT,
    last_result_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(schedule_id) REFERENCES scheduled_publish_configs(schedule_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scheduled_states_due
    ON scheduled_publish_states(enabled, next_run_at, updated_at, schedule_id);
```

协议映射：

- `upsert_config(config)`：
  - 写入或更新 config。
  - 如果 state 不存在，创建默认 `ScheduledPublishState(schedule_id=...)`。
  - config 和默认 state 应在同一短事务内完成。
- `get_config(schedule_id)`：
  - 查不到返回 `None`。
  - 查到后 `ScheduledPublishConfig.model_validate_json(...)`。
- `list_configs()`：
  - 按 `schedule_id` 升序返回，保持测试确定性。
- `set_enabled(schedule_id, enabled)`：
  - config 不存在时抛 `LookupError`，与内存实现一致。
  - 同时更新 config JSON 中的 `enabled` 和 state 表的 `enabled`。
- `get_state(schedule_id)`：
  - 查不到返回 `None`。
  - 还原 `last_result_json` 为 `PublishResult`。
- `save_state(state)`：
  - config 不存在时抛 `LookupError`。
  - 更新时间戳。

---

## 8. 序列化规则

必须使用 Pydantic model JSON 作为 durable payload：

| 对象 | 写入方式 | 读取方式 |
|---|---|---|
| `PublishResult` | `model_dump_json()` | `PublishResult.model_validate_json(raw)` |
| `PublishIdempotencyRecord` | 结构化列 + `publish_result_json` | 构造 `PublishIdempotencyRecord(...)` |
| `PublishAuditEvent.metadata` | `json.dumps(..., sort_keys=True)` | `json.loads(...)` 后交给 model validation |
| task id tuples | JSON array | tuple of str |
| `ScheduledPublishConfig` | `model_dump_json(by_alias=True)` | `ScheduledPublishConfig.model_validate_json(raw)` |
| `ScheduledPublishState.last_result` | `PublishResult.model_dump_json()` 或 NULL | `PublishResult.model_validate_json(raw)` |

时间规则：

- 所有新增时间戳使用 UTC aware datetime。
- DB 中保存 ISO 8601 字符串。
- 读取后交给 Pydantic 校验恢复 datetime。
- 不在 store 外部传递未校验 dict。

---

## 9. 幂等语义设计

### 9.1 当前语义

`TaskPublishService.publish()` 当前语义：

```text
expand pipeline
  -> compute request_hash
  -> idempotency_store.get
  -> publisher.preview
  -> publisher.publish
  -> idempotency_store.put
  -> audit_sink.record
```

`request_hash` 排除 `request_id`，因此同一语义请求可以用不同 request id 重试。

重放规则：

- 如果 key 不存在，继续发布。
- 如果 key 存在且 hash 相同，返回旧 `PublishResult`。
- 如果 key 存在但 hash 不同，返回 skipped result，reason 为 `idempotency conflict`。

### 9.2 SQLite store 必须保证的能力

SQLite idempotency store 只保证：

- 同一 `(session_id, publisher_kind, idempotency_key)` 最多保存一个最终结果。
- 同 key 同 hash 返回同一个结果。
- 同 key 不同 hash 识别为冲突。
- 进程重启后仍可 replay。

它不能单独解决下列问题：

- 两个并发请求同时在 `get` 时查不到，然后都进入 `TaskBus.publish`。
- `TaskBus.publish` 成功后，进程在 `idempotency_store.put` 前崩溃。

### 9.3 当前必须记录的崩溃窗口

当前发布顺序存在窗口：

```text
TaskBus.publish 成功
进程崩溃
idempotency record 尚未写入
重试后可能再次发布一组新 task
```

这是 server transport 前的阻塞风险，不应在 release note 中隐藏。

### 9.4 后续硬化选项

在对外暴露生产级 HTTP/RPC publish 前，应选择至少一种方案：

1. **幂等 reservation 状态机**

   ```text
   reserved -> completed / rejected
   ```

   首次请求先写 reservation；重试遇到未完成 reservation 时返回 `in_progress` 或 `unknown_result`，不重复发布。

2. **确定性 task id**

   根据以下输入派生 task id：

   ```text
   session_id + publisher_kind + idempotency_key + source_node_id
   ```

   同一个 idempotency key 重试时可以检测已存在 task。

3. **统一 SQLite 事务边界**

   将 `tasks.sqlite` 和 `publish.sqlite` 合并或引入同连接事务，使 task 写入和 idempotency finalization 原子化。该方案改动最大，暂不建议作为第一步。

推荐路径：

- 第一实现 slice 先做 SQLite stores。
- 第二实现 slice 做 reservation 或 deterministic task id。
- 若 server transport 要提前启动，只能作为实验接口，不能标记生产可用。

---

## 10. 审计语义设计

`TaskPublishService` 当前会产生这些事件：

- `task_publish.previewed`
- `task_publish.validated`
- `task_publish.rejected`
- `task_publish.published`
- `task_publish.idempotent_replayed`
- `task_publish.idempotency_conflict`

SQLite audit sink 应保持 append-only：

- 不更新旧事件。
- 不删除旧事件。
- `event_id` 唯一。
- 查询默认按 `created_at ASC, id ASC` 排序。

错误策略：

- 当前 `TaskPublishService._emit` 会 suppress 所有 audit sink 异常。
- 第一版 SQLite audit sink 可以抛 `PublishStoreError`，由 service 吞掉，保持“审计失败不阻断发布”的既有行为。
- 集成测试应覆盖：audit sink 正常时确实写入；如果 sink 失败，发布语义不受影响。

未来关系：

- 审计事件还不是 EventStream event。
- 后续可以增加 adapter，把 `PublishAuditEvent` 投影到 EventStream、MessageStream 或 debug API。
- 本阶段不要让 publisher 直接依赖这些上层流。

---

## 11. 调度持久化设计

`SchedulerPublisher.tick()` 的现有过程：

```text
list_configs
  -> get_state
  -> 判断 enabled/session/due
  -> build PublishRequest
  -> publish_service.publish
  -> save_state(last_run_at, next_run_at, last_result)
```

SQLite scheduled store 需要保证：

- `ScheduledPublishConfig` 跨重启保留。
- `ScheduledPublishState.next_run_at` 跨重启保留。
- 关闭后重启，在 `next_run_at` 前不会重复发布。
- `enabled` 状态在 config 和 state 中一致。

注意事项：

- `cron` 类型目前仍是 reserved unsupported，`_first_run_at` 会返回 `None`。
- `daily` 使用 config timezone 计算。
- `current` session selector 需要 tick 调用方传入 `current_session_id`，store 不负责解析。
- `save_state` 发生在 publish 之后，因此如果 publish 成功但保存 state 失败，下一次 tick 可能再次尝试。此时是否重复发布取决于 idempotency key 是否已成功写入。

测试重点：

- interval schedule 首次 due 后写入 `next_run_at`。
- 重启后，在 `next_run_at` 前 tick 返回 `not due`。
- daily schedule 保存 timezone 相关配置。
- disabled schedule 重启后仍 disabled。

---

## 12. 错误处理设计

推荐新增错误：

```python
class PublishStoreError(TaskStoreError):
    """Raised for durable publish control-plane store failures."""
```

错误行为：

| 场景 | 行为 |
|---|---|
| SQLite locked / IO failure | 抛 `PublishStoreError`，幂等检查失败时不能静默继续发布 |
| 幂等 key 同 hash | 返回已有记录 |
| 幂等 key 不同 hash | 抛 `PublishIdempotencyConflictError` |
| audit 写入失败 | store 抛错，service 按现状吞掉，不阻断 publish |
| config/state JSON 损坏 | 抛 `PublishStoreError`，错误信息包含表名和主键 |
| `save_state` 找不到 config | 抛 `LookupError`，与内存实现一致 |
| store 已关闭后调用 | 不静默成功，测试只要求失败可见 |

正确性优先级：

- 幂等 store 是 correctness-sensitive，失败应 fail closed。
- audit sink 是 observability-sensitive，可以 fail open。
- scheduler state 介于两者之间；第一版可让 `tick` 暴露异常，避免静默丢状态。

---

## 13. 与现有服务的集成方式

### 13.1 直接手动装配

第一版可先不新增 factory：

```python
task_bus = SqliteTaskBus(workspace / ".taskweavn" / "tasks.sqlite")
idempotency_store = SqlitePublishIdempotencyStore(
    workspace / ".taskweavn" / "publish.sqlite"
)
audit_sink = SqliteTaskPublishAuditSink(
    workspace / ".taskweavn" / "publish.sqlite"
)

publish_service = TaskPublishService(
    publisher=DefaultTaskPublisher(task_bus=task_bus),
    idempotency_store=idempotency_store,
    audit_sink=audit_sink,
)
```

### 13.2 可选 helper

如果测试或后续 server assembly 重复较多，可以新增小 helper：

```python
def build_sqlite_publish_service(
    *,
    task_bus: TaskBus,
    publish_db_path: str | Path,
    pipeline_loader: PipelineTaskLoader | None = None,
) -> TaskPublishService:
    ...
```

helper 只能负责装配，不应隐藏 store 类型，也不应创建 HTTP/API server。

### 13.3 API publisher 装配

```python
api_publisher = DefaultApiTaskPublisher(
    publish_service=publish_service,
    policy=ApiPublishPolicy(require_idempotency_key=True),
)
```

API adapter 不需要知道 SQLite 细节，它只依赖 `TaskPublishService`。

### 13.4 Scheduler 装配

```python
scheduled_store = SqliteScheduledPublishStore(
    workspace / ".taskweavn" / "publish.sqlite"
)

scheduler = SchedulerPublisher(
    store=scheduled_store,
    publish_service=publish_service,
)
```

多个 store 实例可以指向同一个 `publish.sqlite`。第一版推荐每个 store 持有独立连接，事务短且 WAL 开启。

---

## 14. 测试方案

新增测试文件：

```text
tests/test_sqlite_publish_stores.py
```

### 14.1 幂等 store 测试

- `isinstance(store, PublishIdempotencyStore)`。
- `put` 后 `get` 返回等价 `PublishIdempotencyRecord`。
- 关闭重开后仍可 `get`。
- 同 key 同 hash `put` 返回原记录。
- 同 key 不同 hash 抛 `PublishIdempotencyConflictError`。
- 损坏 `publish_result_json` 后读取抛 `PublishStoreError`。

### 14.2 审计 sink 测试

- `isinstance(sink, TaskPublishAuditSink)`。
- `record` 后可以按 session 查询。
- 可以按 request 查询。
- `root_task_ids` 和 `published_task_ids` round trip。
- `metadata` round trip。
- 关闭重开后事件仍存在。
- 重复 `event_id` 不应产生两条事件，具体行为可选择抛 `PublishStoreError`。

### 14.3 定时 store 测试

- `isinstance(store, ScheduledPublishStore)`。
- `upsert_config` 创建默认 state。
- config 关闭重开后仍存在。
- state 关闭重开后仍存在。
- `set_enabled(False)` 后 config 和 state 都 disabled。
- `save_state` 找不到 config 时抛 `LookupError`。
- `list_configs()` 按 `schedule_id` 排序。

### 14.4 集成测试

可放在新文件，也可扩展现有：

- `TaskPublishService` 使用 SQLite idempotency store：
  - 第一次 publish 写入 TaskBus 和 idempotency。
  - 重建 service 后同 key 同请求返回原 result，不新增 task。
- `DefaultApiTaskPublisher` 使用 SQLite stores：
  - 带 idempotency key 的 API publish 成功。
  - 重启后 replay 返回原 result。
- `SchedulerPublisher` 使用 SQLite scheduled store：
  - tick due 发布一次。
  - 关闭重开后，在 next_run_at 前 tick 不重复发布。
- pipeline publish：
  - `task_before` / `task_begin` 展开后 metadata 仍进入 TaskBus。
  - 幂等 replay 不重复插入展开任务。

验证命令：

```bash
uv run pytest \
  tests/test_task_publish_service.py \
  tests/test_task_scheduler_publisher.py \
  tests/test_task_api_publisher.py \
  tests/test_task_pipeline.py \
  tests/test_sqlite_task_bus.py \
  tests/test_sqlite_publish_stores.py

uv run ruff check src/taskweavn/task tests/test_sqlite_publish_stores.py
uv run mypy src/taskweavn/task tests/test_sqlite_publish_stores.py
```

---

## 15. 实施切片

### Slice 1：SQLite schema 和 publish idempotency/audit

改动：

- 新增 `src/taskweavn/task/sqlite_publish.py`。
- 新增 `PublishStoreError`。
- 实现 schema 初始化。
- 实现 `SqlitePublishIdempotencyStore`。
- 实现 `SqliteTaskPublishAuditSink`。
- 更新 `src/taskweavn/task/__init__.py` 导出。
- 新增幂等和审计测试。

验收：

- 幂等记录和审计事件跨重启。
- 内存 store 测试不受影响。

### Slice 2：SQLite scheduled publish store

改动：

- 在同一模块实现 `SqliteScheduledPublishStore`。
- 增加 config/state schema 测试。
- 增加 scheduler 重启恢复测试。

验收：

- schedule config/state 跨重启。
- scheduler 不会在 `next_run_at` 前重复发布。

### Slice 3：服务装配和 API/scheduler 集成测试

改动：

- 如有必要新增装配 helper。
- 增加 `TaskPublishService` + `SqliteTaskBus` + SQLite stores 的集成测试。
- 增加 `DefaultApiTaskPublisher` 和 `SchedulerPublisher` 集成测试。

验收：

- API/scheduler/custom tree 均可使用 SQLite stores。
- 不引入 transport 依赖。

### Slice 4：文档和状态更新

改动：

- 更新 `docs/project/task-publishers.md`。
- 更新 `docs/plans/feature/README.md`。
- 实现完成时新增 release note 或更新计划状态。
- 明确记录 crash window 是否已关闭。

验收：

- 文档能指导下一阶段 server transport。

### Slice 5：幂等硬化

改动：

- 选择 reservation 或 deterministic task id。
- 调整 `TaskPublishService` 或 `DefaultTaskPublisher`，使 partial publish retry 不会静默重复创建任务。

验收：

- 对外 server transport 前，幂等崩溃窗口被关闭或接口被明确标为实验。

---

## 16. 验收标准

本技术方案对应的实现完成时，应满足：

1. `PublishIdempotencyRecord` 可跨进程重启读取。
2. 同一 idempotency key 的同请求 replay 不重复写入 TaskBus。
3. 同一 idempotency key 的不同请求产生 conflict。
4. `PublishAuditEvent` 被持久追加。
5. 审计事件可按 session/request 查询。
6. `ScheduledPublishConfig` 和 `ScheduledPublishState` 可跨重启恢复。
7. scheduler 重启后尊重已保存的 `next_run_at`。
8. `DefaultApiTaskPublisher` 能使用 SQLite-backed `TaskPublishService`。
9. `SqliteTaskBus` 仍是 Published Task 的唯一持久化边界。
10. 当前幂等崩溃窗口被修复，或被明确列为 server transport 前必须完成的 blocker。

---

## 17. 风险和处理

| 风险 | 影响 | 处理 |
|---|---|---|
| `tasks.sqlite` 和 `publish.sqlite` 跨 DB 非原子 | 崩溃后可能重复发布 | 已通过 deterministic task id 硬化；完整 task set 可恢复，部分 task set 会拒绝继续发布 |
| SQLite store 过度抽象 | 拖慢当前后端推进 | 只做 `taskweavn.task` 私有小 helper |
| scheduler publish 成功但 state 保存失败 | 下次 tick 可能再次尝试 | 依赖 idempotency 降低重复发布风险，并在测试中显式覆盖 |
| JSON payload 演进 | 旧数据读取失败 | schema version + Pydantic validation，后续 Storage Governance 统一迁移 |
| audit 表增长 | 本地 DB 膨胀 | 第一版 append-only，清理/归档留给后续治理 |
| 多进程并发 publish | 可能绕过 get-then-put 幂等 | 第一版假设单本地后端进程，多进程前做 reservation |

---

## 18. 前置依赖判断

本阶段没有 UI 前置依赖，也没有 server transport 前置依赖。

需要已经存在的后端基础：

- `TaskPublishService`
- `DefaultTaskPublisher`
- `SqliteTaskBus`
- `DefaultApiTaskPublisher`
- `SchedulerPublisher`
- `DefaultPipelineTaskLoader`

这些基础已经具备。因此本阶段可以直接开始实现。

相反，以下工作应依赖本阶段结果：

- HTTP/RPC publish endpoint。
- scheduler 产品化运行。
- publish audit debug/API 查询。
- completion-time `task_after` 的可靠编排。
- 对外声称 API publish 幂等可靠。

---

## 19. 下一步建议

当前后端实现已完成，可以进入后续 server transport 设计：

1. HTTP/RPC publish endpoint 可以包装 `DefaultApiTaskPublisher`。
2. scheduler 产品化运行可以复用 `SqliteScheduledPublishStore`。
3. publish audit debug/API 查询可以读取 `SqliteTaskPublishAuditSink`。
4. completion-time `task_after` 可以依赖 durable publish metadata。

`SqlitePublishIdempotencyStore`、`SqliteTaskPublishAuditSink` 和
`SqliteScheduledPublishStore` 已经可用，`build_sqlite_publish_service(...)`
也已提供最小装配边界。幂等崩溃窗口已通过 deterministic task id
路线硬化：同一 idempotency key 会生成稳定 task id；重启后若 TaskBus
里已有完整 task set，则重建 `PublishResult` 并补写 idempotency record；
若只存在部分 task，则拒绝继续发布，避免静默重复创建 Task。

---

## 20. 当前实现状态

- 2026-05-17：Slice 1、Slice 2、Slice 3 和 Slice 5 已实现。
- 已新增 `SqlitePublishIdempotencyStore`。
- 已新增 `SqliteTaskPublishAuditSink`。
- 已新增 `SqliteScheduledPublishStore`。
- 已新增 `PublishStoreError`。
- 已新增 `build_sqlite_publish_service(...)`。
- 已新增 idempotent deterministic task id hardening。
- 已补充 `tests/test_sqlite_publish_stores.py`。
- 已补充 `DefaultApiTaskPublisher` 使用 SQLite stores 的集成测试。
- 后续：server transport、publish audit 查询接口、completion-time `task_after`。
