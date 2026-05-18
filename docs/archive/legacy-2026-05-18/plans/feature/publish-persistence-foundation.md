# Feature Plan: Publish Persistence Foundation

> Status: done
> Type: 后端功能 / server-core persistence
> Last Updated: 2026-05-17
> Owner/Session: backend implementation session
> Target Implementation Session: current backend session
> Work Stream: P3D — Task Publishing And Pipeline
> Related Docs: [中文详细技术方案](publish-persistence-foundation-technical-design.zh-CN.md), [Task Publisher Plan](task-publishers-schedule-api.md), [Task Publisher Usage](../../project/task-publishers.md), [Task Publisher Release](../../releases/task-publishers-schedule-api.md), [Local-first Storage Discussion](../../discussion/2026-05-16-local-first-storage-sqlite-evaluation.md), [Roadmap](../../roadmap.md)

---

## 1. Background

TaskPublisher 已经完成 server-core 语义层：

- `TaskPublishService` 统一 preview/publish、idempotency 和 audit hook；
- `DefaultTaskPublisher` 将 `NormalizedTaskTree` 发布为普通 `TaskDomain`；
- `DefaultApiTaskPublisher` 提供 transport-neutral API publisher；
- `SchedulerPublisher` 支持 interval/daily schedule tick；
- `DefaultPipelineTaskLoader` 支持 publish-time `task_before` / `task_begin` 扩展；
- `SqliteTaskBus` 已经持久化 published Task 的 publish/read surface。

当前缺口是 publish 控制面仍主要依赖 in-memory store：

- `InMemoryPublishIdempotencyStore`
- `InMemoryTaskPublishAuditSink`
- `InMemoryScheduledPublishStore`

这会阻断后续后端能力：

- API publish 不能跨进程重启安全 replay；
- scheduler config/state 不能产品化；
- publish audit 不能被后续 UI/API/debug 工具查询；
- pipeline/publisher 行为无法稳定恢复；
- server transport 即使暴露出来，也缺少可靠后端状态。

本计划目标是在不引入 HTTP/SSE transport 的前提下，先把 publish 控制面落到 SQLite。

---

## 2. Goal

实现一组 SQLite-backed publish stores，使现有 publisher 语义可以跨进程、跨重启保持一致。

第一阶段应交付：

1. `SqlitePublishIdempotencyStore`
2. `SqliteTaskPublishAuditSink`
3. `SqliteScheduledPublishStore`
4. `publish.sqlite` schema ownership 和连接策略
5. 与 `TaskPublishService` / `SchedulerPublisher` / `DefaultApiTaskPublisher` 的集成测试
6. 文档更新：usage、roadmap follow-up、release 或 plan 状态记录

成功后，当前发布链路应支持：

```text
API / scheduler / custom tree / collaborator publish
  -> TaskPublishService
  -> SQLite idempotency + audit
  -> DefaultTaskPublisher
  -> SqliteTaskBus.publish(TaskDomain)
```

---

## 3. Non-goals

- 不实现 HTTP/RPC server transport。
- 不实现 SSE / UI event transport。
- 不实现 TaskBus `claim/complete/fail` 生命周期。
- 不实现 completion-time `task_after` orchestration。
- 不实现 persistent RawTask / DraftTaskTree authoring stores。
- 不实现分布式 scheduler 或多进程 worker leasing。
- 不引入 PostgreSQL / Redis 等外部服务依赖。
- 不一次性建设完整 Storage Governance 系统；只在本包内建立 publish DB 的最小治理。

---

## 4. Current Code Facts

| Area | Current implementation | Gap |
|---|---|---|
| TaskBus publish/read | `SqliteTaskBus` persists pending `TaskDomain` rows. | No claim/complete/fail yet, but enough for publish persistence. |
| Idempotency | `PublishIdempotencyStore` Protocol + in-memory implementation. | No SQLite implementation. |
| Publish audit | `TaskPublishAuditSink` Protocol + in-memory implementation. | No durable append sink. |
| Scheduler | `ScheduledPublishStore` Protocol + in-memory implementation. | Config/state lost after restart. |
| API publisher | Transport-neutral adapter exists. | No HTTP/RPC wrapper; persistence should come first. |
| Pipeline | Publish-time before/begin expansion exists. | `task_after` belongs to later completion-time orchestration. |

This means this work can proceed without UI or transport work.

---

## 5. Scope Decision

The phase should start with persistence, not transport.

Recommended ordering:

```text
publish persistence
  -> service assembly / factory
  -> API/server transport
  -> completion-time pipeline
  -> TaskBus execution lifecycle
```

Reason:

- Transport without persistence exposes unstable semantics.
- Persistence can be tested entirely inside server-core.
- Existing `DefaultApiTaskPublisher` is already transport-neutral, so HTTP can remain a thin wrapper later.
- Scheduler needs durable state before it is useful in a long-running backend process.

---

## 6. Data Ownership

Use a dedicated publish control-plane database:

```text
<workspace>/
  .taskweavn/
    tasks.sqlite      # Published TaskBus facts and task topology
    publish.sqlite    # Publish idempotency, scheduler config/state, publish audit
```

Rationale:

- `tasks.sqlite` is execution-domain task truth.
- `publish.sqlite` is publish control-plane truth.
- Scheduler and idempotency grow with publisher behavior, not with task execution state.
- Separate DBs preserve local-first backup and archive flexibility.

`publish.sqlite` is owned by `taskweavn.task` publish modules.

---

## 7. SQLite Connection Rules

Every SQLite-backed publish store must follow the same local-first rules:

1. Enable WAL:

   ```sql
   PRAGMA journal_mode=WAL;
   ```

2. Enable foreign keys:

   ```sql
   PRAGMA foreign_keys=ON;
   ```

3. Set a bounded busy timeout:

   ```sql
   PRAGMA busy_timeout=5000;
   ```

4. Keep transactions short.
5. Never call LLM, tools, network, or user wait code inside a transaction.
6. Store code should raise typed store errors instead of leaking raw `sqlite3` errors where possible.
7. Store implementations should support `close()` and context manager usage.

Implementation may use a small private helper, e.g. `taskweavn.task.sqlite_utils`, if it avoids duplicating connection setup across `SqliteTaskBus` and publish stores. Do not create a large storage framework in this package.

---

## 8. Schema Design

### 8.1 `publish_schema_meta`

Minimal local schema version table:

```sql
CREATE TABLE IF NOT EXISTS publish_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Initial values:

| key | value |
|---|---|
| `schema_version` | `1` |

First implementation can keep migrations simple and idempotent. A global migration manager belongs to later Storage Governance work.

### 8.2 `publish_idempotency_records`

Stores final publish results behind stable idempotency keys.

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

Protocol mapping:

- `get(session_id, publisher_kind, idempotency_key)` reads one row and validates `PublishIdempotencyRecord`.
- `put(record)` inserts if absent.
- If a row exists with the same `request_hash`, return existing record.
- If a row exists with a different `request_hash`, raise `PublishIdempotencyConflictError`.

### 8.3 `publish_audit_events`

Append-only publish control-plane events.

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

First public API:

```python
class SqliteTaskPublishAuditSink(TaskPublishAuditSink):
    def record(self, event: PublishAuditEvent) -> None: ...
    def list_for_session(self, session_id: str, *, limit: int | None = None) -> tuple[PublishAuditEvent, ...]: ...
    def list_for_request(self, request_id: str) -> tuple[PublishAuditEvent, ...]: ...
```

Only `record()` is required by the current Protocol. Query helpers are allowed as concrete extensions for tests and future debug/API adapters.

### 8.4 `scheduled_publish_configs`

Stores scheduler configs as validated model JSON.

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

Reason for storing full JSON:

- `ScheduledPublishConfig` is already a strongly typed Pydantic model.
- The scheduler first version lists configs in-process rather than running DB-side due queries.
- Future query indexes can be added without changing the protocol.

### 8.5 `scheduled_publish_states`

Stores mutable scheduler state.

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

Protocol mapping:

- `upsert_config(config)` writes config and creates a default state if missing.
- `get_config(schedule_id)` validates JSON into `ScheduledPublishConfig`.
- `list_configs()` returns deterministic ordering by `schedule_id`.
- `set_enabled(schedule_id, enabled)` updates config and state.
- `get_state(schedule_id)` validates JSON fields into `ScheduledPublishState`.
- `save_state(state)` requires existing config and updates `updated_at`.

---

## 9. Serialization Rules

Use Pydantic model JSON for durable payloads:

| Object | Serialization |
|---|---|
| `PublishResult` | `model_dump_json()` |
| `PublishIdempotencyRecord` | row columns + `publish_result_json` |
| `PublishAuditEvent.metadata` | JSON object |
| task id tuples | JSON arrays |
| `ScheduledPublishConfig` | `model_dump_json(by_alias=True)` |
| `ScheduledPublishState.last_result` | `PublishResult.model_dump_json()` or NULL |

Datetime values:

- Store ISO 8601 strings.
- Preserve timezone-aware datetimes.
- New timestamps should use UTC.

Deserialization must use model validation:

```python
PublishResult.model_validate_json(raw)
ScheduledPublishConfig.model_validate_json(raw)
```

Do not parse JSON into untyped dicts and pass them around.

---

## 10. Error Handling

Introduce a narrow store error type if needed:

```python
class PublishStoreError(TaskStoreError): ...
```

Recommended behavior:

| Case | Behavior |
|---|---|
| SQLite locked / IO failure | Raise store error; do not silently publish if idempotency cannot be checked. |
| Existing idempotency key, same hash | Return existing record. |
| Existing idempotency key, different hash | Raise `PublishIdempotencyConflictError`. |
| Audit sink failure | Preserve existing `TaskPublishService` behavior: audit failure must not block publish. |
| Scheduler save failure after publish | Return publish result but surface store error in logs/tests? First version should let exception propagate from `tick` after publish only if save failed before returning. |
| Corrupt JSON row | Raise store error with row identity. |

Important distinction:

- Idempotency store failure is correctness-sensitive and should fail closed.
- Audit sink failure is observability-sensitive and may fail open, matching current service behavior.

---

## 11. Idempotency Crash Window

Current `TaskPublishService.publish()` sequence is:

```text
check idempotency
  -> preview
  -> TaskBus publish
  -> store idempotency record
```

This preserves existing behavior but has a known crash window:

```text
TaskBus publish succeeds
process crashes before idempotency record is stored
retry may publish duplicate tasks
```

First implementation may preserve this behavior if scoped strictly to persistence adapters, but the gap must be recorded.

Before exposing a production HTTP/API publish endpoint, one of these hardening options should be implemented:

1. **Idempotency reservation state machine**

   ```text
   reserved -> completed / rejected
   ```

   Repeated calls with an unfinished reservation return `in_progress` / `unknown_result` instead of republishing.

2. **Deterministic task ids for idempotent publishes**

   Derive task ids from:

   ```text
   session_id + publisher_kind + idempotency_key + source_node_id
   ```

   Retrying the same publish can detect existing tasks instead of creating duplicates.

3. **Single-DB transaction boundary**

   Keep task inserts and idempotency finalization in the same SQLite transaction. This is larger because `SqliteTaskBus` and publish stores are currently separate boundaries.

Recommended path:

- Slice 1 preserves current Protocol and adds SQLite stores.
- Slice 2 adds either reservation or deterministic ids before public transport.

Do not hide this gap in release notes.

---

## 12. Implementation Slices

### Slice 1 — SQLite Publish Store Models And Schema

Deliver:

- `SqlitePublishIdempotencyStore`
- `SqliteTaskPublishAuditSink`
- `publish_schema_meta`
- schema creation on store construction
- WAL / foreign_keys / busy_timeout setup
- context manager and `close()`

Tests:

- protocol conformance
- insert/get idempotency record
- same key/same hash returns existing
- same key/different hash raises conflict
- audit append and list by session/request
- persists across reopen
- corrupt JSON produces store error

### Slice 2 — SQLite Scheduled Publish Store

Deliver:

- `SqliteScheduledPublishStore`
- config/state schema
- `upsert_config`, `set_enabled`, `save_state`
- deterministic `list_configs()`

Tests:

- protocol conformance
- config persists across reopen
- state persists across reopen
- disabled schedule remains disabled after reopen
- `save_state` without config raises
- scheduler tick can resume from persisted `next_run_at`

### Slice 3 — Service Assembly And Integration Tests

Deliver:

- small factory/helper for local publish services, if useful:

  ```python
  build_sqlite_publish_service(
      task_bus: TaskBus,
      publish_db_path: Path,
      ...
  ) -> TaskPublishService
  ```

- integration tests using:
  - `SqliteTaskBus`
  - `SqlitePublishIdempotencyStore`
  - `SqliteTaskPublishAuditSink`
  - `SqliteScheduledPublishStore`

Tests:

- publish with idempotency survives service restart
- replay after restart returns original result
- scheduler tick publishes once, closes, reopens, does not duplicate before next run
- API publisher with SQLite stores writes TaskBus and idempotency record

### Slice 4 — Docs And Usage

Deliver:

- update `docs/project/task-publishers.md`
- update `docs/plans/feature/README.md`
- add release notes when implementation completes
- update roadmap/project roadmap status if this package changes immediate queue

Docs should include:

- `publish.sqlite` ownership
- example wiring
- what is persistent now
- known idempotency crash window
- remaining transport and `task_after` follow-ups

### Slice 5 — Idempotency Hardening Before Transport

Deliver one of:

- reservation state machine, or
- deterministic task IDs for idempotent publishes.

This slice can be done immediately after the first SQLite store pass or folded in if implementation complexity remains low.

Acceptance:

- a retry after a partial/incomplete publish path cannot silently duplicate tasks.
- behavior is documented before any HTTP/RPC publish endpoint is considered production-ready.

---

## 13. Test Matrix

| Test | Expected |
|---|---|
| SQLite idempotency protocol | `isinstance(store, PublishIdempotencyStore)` is true. |
| idempotency round trip | Stored `PublishIdempotencyRecord` loads equal to original. |
| idempotency replay | Same key/hash returns original result after reopen. |
| idempotency conflict | Same key/different hash raises or returns existing conflict through service. |
| audit append | Publish audit events are appended in created order. |
| audit query | Can list by session and request id. |
| scheduler config round trip | `ScheduledPublishConfig` survives close/reopen. |
| scheduler state round trip | `ScheduledPublishState.last_result` survives close/reopen. |
| scheduler duplicate prevention | Reopened scheduler honors persisted `next_run_at`. |
| integration publish | `TaskPublishService` with SQLite stores writes to `SqliteTaskBus`. |
| API adapter integration | `DefaultApiTaskPublisher.publish` works with SQLite stores. |
| pipeline metadata | Publish-time pipeline tasks retain publisher + pipeline metadata with SQLite stores. |
| context manager | Store methods fail after close in the same style as existing SQLite stores. |

Validation commands:

```bash
uv run pytest \
  tests/test_task_publish_service.py \
  tests/test_task_scheduler_publisher.py \
  tests/test_task_api_publisher.py \
  tests/test_sqlite_task_bus.py \
  tests/test_sqlite_publish_stores.py

uv run ruff check src/taskweavn/task tests/test_sqlite_publish_stores.py
uv run mypy src/taskweavn/task tests/test_sqlite_publish_stores.py
```

---

## 14. Acceptance Criteria

This phase is complete when:

1. Publish idempotency can survive process restart.
2. Publish audit events are durably recorded in `publish.sqlite`.
3. Scheduled publish config/state can survive process restart.
4. Scheduler tick does not duplicate work after restart before `next_run_at`.
5. API publisher integration can use SQLite stores without HTTP transport.
6. Existing in-memory tests still pass.
7. `SqliteTaskBus` remains the published Task persistence boundary.
8. Known idempotency crash window is either fixed or explicitly documented as a blocker before production transport.
9. Docs and feature README point to this plan.

---

## 15. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Cross-DB atomicity gap between `publish.sqlite` and `tasks.sqlite` | Hardened with deterministic task ids for idempotent publishes; partial existing task sets are rejected instead of duplicated. |
| Store code grows into generic storage framework | Keep helper small and private; global Storage Governance remains separate. |
| Scheduler state update fails after publish | Add tests and decide fail behavior explicitly; idempotency prevents duplicate task publish on retry when final record exists. |
| JSON payload schema drift | Store schema version and validate all rows through Pydantic models. |
| SQLite locked errors in local backend | Use WAL, busy_timeout, short transactions, and one local backend process assumption. |
| Audit table grows too large | First version is append-only; retention/archive belongs to Storage Governance follow-up. |

---

## 16. Follow-ups

After this phase:

1. API/server transport can wrap `DefaultApiTaskPublisher`.
2. Completion-time `task_after` orchestration can rely on durable publish metadata.
3. Persistent authoring stores can be added for RawTask/DraftTaskTree.
4. TaskBus claim/complete/fail lifecycle can extend `tasks.sqlite`.
5. Storage Governance plan should cover migration manager, backup/export, retention, and health checks across all SQLite DBs.

---

## 17. Status

- Status: done
- Last Updated: 2026-05-17
- Current decision: implement SQLite publish stores before HTTP/RPC transport.
- Slice 1: implemented `SqlitePublishIdempotencyStore` and
  `SqliteTaskPublishAuditSink`.
- Slice 2: implemented `SqliteScheduledPublishStore`.
- Slice 3: implemented `build_sqlite_publish_service(...)` and API publisher
  integration coverage with SQLite stores.
- Slice 5: implemented deterministic task ids for idempotent publishes.
- Crash-window hardening: if TaskBus already contains all deterministic tasks,
  publish can reconstruct a result and store the idempotency record; if only
  part of the task set exists, publish is rejected without creating duplicates.
