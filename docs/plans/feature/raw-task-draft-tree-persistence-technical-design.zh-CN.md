# RawTask / DraftTaskTree 持久化基础：中文详细技术方案

> Status: implemented
> Type: backend persistence / authoring-domain reliability technical design
> Last Updated: 2026-05-28
> Parent Plan: [RawTask And DraftTaskTree Persistence Foundation](raw-task-draft-tree-persistence.md)
> Decision: [ADR-0009: Single Active Session Work Tree](../../decisions/ADR-0009-single-active-session-worktree.md)
> Release Record: [RawTask And DraftTaskTree Persistence](../../releases/raw-task-draft-tree-persistence.md)

---

## 0. 实施状态

本技术方案已按 P8.1-P8.6 落地，并通过 Product 1.0 authoring recovery
验收。

已实现范围：

- SQLite RawTask / DraftTaskTree / active authoring state stores；
- backend restart 后恢复当前 active RawTask / DraftTaskTree；
- projection 和 gateway 不再把 synthetic `TaskTreeView.id` 当作真实
  `draft_tree_id`；
- local sidecar 接入 `authoring.sqlite`；
- authoring command result 幂等；
- API command response 幂等和 request hash conflict。

仍不包含：

- post-publish editing 策略；
- fixed-route task execution bridge；
- Audit Page 完整实现；
- durable SSE replay。

## 1. 设计结论

本阶段应为 Authoring Domain 新增本地 SQLite 持久化层：

```text
<workspace>/.plato/
  tasks.sqlite        # Execution Domain: published TaskBus facts
  publish.sqlite      # Publish control plane: idempotency, scheduler, publish audit
  authoring.sqlite    # Authoring Domain: RawTask, DraftTaskTree, active state
```

核心设计：

1. `RawTask` 使用 compact snapshot 持久化。
2. `DraftTaskTree` 和 `DraftTaskNode` 使用关系表持久化。
3. `draft_to_published_mappings` 持久化 draft node 到 published task 的 lineage。
4. `authoring_active_sessions` 记录每个 Session 唯一 active RawTask / DraftTaskTree。
5. `TaskTreeView` 继续是 UI projection，不是 domain truth。
6. publish 必须使用真实 `draft_tree_id`，或由 gateway 解析 active draft tree。

原始第一批实现建议只做 P8.1 + P8.2：

- `SqliteRawTaskStore`
- `SqliteDraftTaskStore`
- `SqliteAuthoringStateStore`
- reopen / version conflict / mapping persistence tests

Projection、gateway、sidecar assembly 和幂等能力随后已按 P8.3-P8.6 接入。

---

## 2. 实施前代码基线

| Area | Current fact | Persistence gap |
|---|---|---|
| RawTask model | `taskweavn.task.authoring.RawTask` includes feasibility, asks, answers, constraints, assumptions, version, timestamps. | No SQLite store. |
| RawTask store | `RawTaskStore` protocol supports create/get/list/save. | Only in-memory implementation. |
| Draft tree model | `DraftTaskTree`, `DraftTaskNode`, `DraftToPublishedMapping` exist. | No SQLite store. |
| Draft store | `DraftTaskStore` supports create tree, list nodes, update node, accept, publish mappings. | Only in-memory implementation. |
| Command service | `DefaultAuthoringCommandService` applies structured commands and uses store snapshots for rollback. | Idempotency cache is in-memory. |
| Projection | `DefaultTaskProjectionService` currently projects all draft trees returned by `list_trees(session_id)`. | Needs active-tree selection. |
| Publish | `PublishDraftTaskTreeCommand` requires real `draft_tree_id`. | UI publish route may supply synthetic `TaskTreeView.id`. |
| Existing SQLite patterns | `SqliteTaskBus` and publish SQLite stores exist. | Authoring store needs equivalent local-first rules. |

---

## 3. Schema

### 3.1 `authoring_schema_meta`

```sql
CREATE TABLE IF NOT EXISTS authoring_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Initial row:

| key | value |
|---|---|
| `schema_version` | `1` |

### 3.2 `authoring_active_sessions`

记录一个 Session 的唯一 active authoring/work-tree state。

```sql
CREATE TABLE IF NOT EXISTS authoring_active_sessions (
    session_id TEXT PRIMARY KEY,
    active_raw_task_id TEXT,
    active_draft_tree_id TEXT,
    active_state TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

`active_state` values:

- `none`
- `raw_task`
- `draft_tree`
- `published`
- `cancelled`

规则：

- `active_raw_task_id` 指向当前 RawTask。
- `active_draft_tree_id` 指向当前 DraftTaskTree。
- publish 后 `active_draft_tree_id` 仍保留，用于 lineage 和 audit。
- regeneration 会替换 active draft tree。旧 tree 可作为 inactive trace 保留，但 Main Page 不展示为 forest。

### 3.3 `raw_tasks`

RawTask 是 exploratory object，第一版使用 compact snapshot，避免过早拆 ask/answer 表。

```sql
CREATE TABLE IF NOT EXISTS raw_tasks (
    session_id TEXT NOT NULL,
    raw_task_id TEXT NOT NULL,
    source_message_id TEXT NOT NULL,
    user_input TEXT NOT NULL,
    status TEXT NOT NULL,
    intent_summary TEXT,
    feasibility_json TEXT,
    asks_json TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    assumptions_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    replaced_by_raw_task_id TEXT,
    PRIMARY KEY (session_id, raw_task_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_tasks_session_updated
    ON raw_tasks(session_id, updated_at, raw_task_id);
```

字段说明：

- `feasibility_json` 存 `FeasibilityReport`。
- `asks_json` 存 `tuple[RawTaskAsk, ...]`。
- `answers_json` 存 `tuple[RawTaskAnswer, ...]`。
- `constraints_json` / `assumptions_json` 存 string tuple。
- `archived_at` 和 `replaced_by_raw_task_id` 用于后续轻量 trace。

### 3.4 `draft_task_trees`

```sql
CREATE TABLE IF NOT EXISTS draft_task_trees (
    session_id TEXT NOT NULL,
    draft_tree_id TEXT NOT NULL,
    source_raw_task_id TEXT,
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    replaced_by_draft_tree_id TEXT,
    PRIMARY KEY (session_id, draft_tree_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_task_trees_session_updated
    ON draft_task_trees(session_id, updated_at, draft_tree_id);
```

`source_raw_task_id` 是存储元数据，用于将 DraftTaskTree 关联回生成它的 RawTask。
当前 `DraftTaskTree` 模型不需要立刻增加该字段。

### 3.5 `draft_task_nodes`

```sql
CREATE TABLE IF NOT EXISTS draft_task_nodes (
    session_id TEXT NOT NULL,
    draft_tree_id TEXT NOT NULL,
    draft_task_id TEXT NOT NULL,
    parent_draft_task_id TEXT,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    intent TEXT NOT NULL,
    required_capability TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, draft_task_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_task_nodes_tree_order
    ON draft_task_nodes(session_id, draft_tree_id, parent_draft_task_id, order_index, draft_task_id);
```

读取 `DraftTaskTree` 时：

- tree row 提供 `draft_tree_id`、`session_id`、`created_by`、`version`、timestamps；
- root nodes 由 `parent_draft_task_id IS NULL` 的 node rows 重建；
- child nodes 通过 `list_children` / `list_nodes` 查询。

### 3.6 `draft_to_published_mappings`

```sql
CREATE TABLE IF NOT EXISTS draft_to_published_mappings (
    session_id TEXT NOT NULL,
    draft_tree_id TEXT NOT NULL,
    draft_task_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    published_at TEXT NOT NULL,
    publish_command_id TEXT NOT NULL,
    PRIMARY KEY (session_id, draft_task_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_mapping_task
    ON draft_to_published_mappings(session_id, task_id);
```

用途：

- publish 后恢复 draft-to-published lineage；
- audit / timeline 可以从 published task 追溯 draft task；
- retry/follow-up 策略后续可以复用 lineage。

### 3.7 `authoring_command_idempotency_records`

P8.5 实现，用于保存 authoring command 层的最终 `AuthoringCommandResult`。
同一个 `(session_id, idempotency_key)` 以第一次写入的结果为准，后续重试
直接 replay，不再重复写 RawTask、DraftTaskTree 或 publish side effects。

```sql
CREATE TABLE IF NOT EXISTS authoring_command_idempotency_records (
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_authoring_command_idempotency_session_created
    ON authoring_command_idempotency_records(session_id, created_at, idempotency_key);
```

设计决策：

- `idempotency_key` 是语义权威；第一次结果胜出。
- `request_hash` 作为诊断/后续强化字段保留，但 P8.5 不把 hash mismatch
  转成 conflict。原因是 `generate_task_tree` 的结构化 command payload 可能受
  LLM retry 输出影响，如果同 key 不 replay 而改成 conflict，会避免重复写入但
  不能给 UI 稳定结果。
- HTTP/UI gateway 负责把 generate/publish 的 idempotency key 传入 authoring
  command batch；prompt-to-generate 会拆成 `:raw` 和 `:tree` 两个子 key。
- publish 在 active state 已经是 `published` 时，如果请求携带同一个
  idempotency key，允许解析到上次 active draft tree 并 replay cached result。

### 3.8 `ui_command_response_idempotency_records`

P8.6 实现，用于在 HTTP/UI command 边界保存最终 `CommandResponse`。该层在
gateway、Collaborator、LLM、authoring command service 之前执行，因此可以避免
同一 logical user action 的 API retry 再次触发下游执行。

```sql
CREATE TABLE IF NOT EXISTS ui_command_response_idempotency_records (
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    headers_json TEXT NOT NULL,
    body_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ui_command_response_idempotency_session_created
    ON ui_command_response_idempotency_records(session_id, created_at, idempotency_key);
```

设计决策：

- 前端生成 `idempotencyKey`，并在同一个 logical user action 的 retry 中复用。
- `commandId` 是 trace/request id，不参与 request hash。
- request hash 包含：
  - route name；
  - path target，如 `task_node_id` / `confirmation_id`；
  - `session_id`；
  - `expected_version`；
  - payload。
- 同一个 `(session_id, idempotency_key)` 且 request hash 相同：直接 replay
  第一次保存的 HTTP response，不再进入 gateway。
- 同一个 `(session_id, idempotency_key)` 但 request hash 不同：返回
  `idempotency_conflict`，避免前端错误复用 key 后悄悄执行错误动作。
- P8.6 只保存 completed response；不实现 `in_progress` reservation。并发
  duplicate request 与 side-effect 成功但 response record 尚未写入之间的崩溃，
  仍由 P8.5 authoring command idempotency 作为下游兜底。

---

## 4. Store API

### 4.1 新增模块

```text
src/taskweavn/task/sqlite_authoring.py
```

推荐导出：

```python
SqliteRawTaskStore
SqliteDraftTaskStore
SqliteAuthoringStateStore
SqliteAuthoringStoreBundle
AuthoringStoreError
```

### 4.2 `SqliteRawTaskStore`

实现现有 `RawTaskStore`：

```python
class RawTaskStore(Protocol):
    def create(self, raw_task: RawTask) -> RawTask: ...
    def get(self, session_id: str, raw_task_id: str) -> RawTask | None: ...
    def list_for_session(self, session_id: str) -> list[RawTask]: ...
    def save(self, raw_task: RawTask, *, expected_version: int) -> RawTask: ...
```

行为要求：

- `create` 不允许同 `(session_id, raw_task_id)` 重复。
- `save` 必须检查 `expected_version`。
- `save` 写入时 version + 1，保留原 `created_at`，刷新 `updated_at`。
- `list_for_session` 按 `(created_at, updated_at, raw_task_id)` 稳定排序。
- 读取时必须通过 Pydantic model validation 还原 `RawTask`。

### 4.3 `SqliteDraftTaskStore`

实现现有 `DraftTaskStore`：

```python
class DraftTaskStore(Protocol):
    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree: ...
    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree: ...
    def list_trees(self, session_id: str) -> list[DraftTaskTree]: ...
    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]: ...
    def list_children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]: ...
    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None: ...
    def add_node(...): ...
    def update_node(...): ...
    def mark_accepted(...): ...
    def mark_published(...): ...
```

行为要求：

- `create_tree` 生成真实 `draft_tree_id`，并 normalize root nodes 的
  `session_id`、`draft_tree_id`、`parent_draft_task_id`。
- `add_node` 必须检查 tree version 和 parent 是否存在。
- `update_node` 只允许 status 为 `draft` 的 node。
- `mark_accepted` 把 draft nodes 改为 `accepted`，并使其后续只读。
- `mark_published` 持久化 node status 和 draft-to-published mappings。
- `list_for_draft` / `list_for_task` 可以作为 concrete helper 保留。

### 4.4 `AuthoringStateStore`

新增独立 active-state protocol，不塞进 `DraftTaskStore`：

```python
class ActiveAuthoringState(BaseModel):
    session_id: str
    active_raw_task_id: str | None = None
    active_draft_tree_id: str | None = None
    active_state: Literal["none", "raw_task", "draft_tree", "published", "cancelled"]
    updated_at: datetime


class AuthoringStateStore(Protocol):
    def get_active(self, session_id: str) -> ActiveAuthoringState: ...
    def set_active_raw_task(self, session_id: str, raw_task_id: str) -> None: ...
    def set_active_draft_tree(
        self,
        session_id: str,
        raw_task_id: str | None,
        draft_tree_id: str,
    ) -> None: ...
    def mark_published(self, session_id: str, draft_tree_id: str) -> None: ...
```

原因：

- 保持现有 `RawTaskStore` / `DraftTaskStore` protocol 兼容。
- projection/gateway 可以显式依赖 active-state 能力。
- 后续如果需要 in-memory active state，也可以独立实现。

---

## 5. Transaction And Rollback

当前 `DefaultAuthoringCommandService` 使用 in-memory store 的 `_snapshot` /
`_restore` 实现 all-or-nothing rollback。

SQLite 不能依赖对象快照做 rollback。推荐分阶段处理：

### 第一阶段

- store method 自己保证单方法原子性；
- `SqliteRawTaskStore` / `SqliteDraftTaskStore` 方法内部使用短事务；
- 不在事务内调用 LLM、工具、网络、用户等待或 TaskBus；
- 不强行一次解决 `AuthoringCommandBatch` 全批次跨 store 事务。

### 第二阶段

如果实际命令批处理需要严格 all-or-nothing，再新增：

```python
class AuthoringUnitOfWork:
    raw_task_store: RawTaskStore
    draft_store: DraftTaskStore
    state_store: AuthoringStateStore

    def __enter__(self) -> AuthoringUnitOfWork: ...
    def __exit__(...) -> None: ...
```

或让 `DefaultAuthoringCommandService` 接受 transaction-capable bundle。

---

## 6. Command / Projection / Publish Rules

### 6.1 RawTask create/update

- 创建新 RawTask 后，应设置为 `active_raw_task_id`。
- 替换 active RawTask 时，旧 RawTask 可标记 `archived_at`。
- 第一版不需要 UI 展示 archived RawTask。
- `save` 必须保持 version conflict 语义。

### 6.2 DraftTaskTree create/update

- 创建 DraftTaskTree 后，应设置为 `active_draft_tree_id`。
- 创建新的 active DraftTaskTree 时，旧未发布 tree 可标记 `archived_at` 或
  `replaced_by_draft_tree_id`。
- `list_trees(session_id)` 可继续返回全部 tree，便于测试/debug。
- 产品投影必须默认只用 active tree。

### 6.3 Main Page projection

`DefaultTaskProjectionService` 后续需要 active-tree-aware path：

```text
if active_draft_tree_id exists and include_drafts:
    project only that draft tree
else:
    project published tasks
```

Main Page 不显示 inactive draft trees，不显示 forest。

### 6.4 Publish identity

Publish 必须使用真实 `draft_tree_id`。

推荐 endpoint 行为：

```text
POST /api/v1/sessions/{sessionId}/task-tree/publish
payload: { draftTreeId?: string, startImmediately: boolean }
```

规则：

- 如果 `draftTreeId` 存在，必须校验它是当前 Session 的 active draft tree，
  或明确允许发布的 tree。
- 如果 `draftTreeId` 缺省，gateway 发布 active draft tree。
- 如果 frontend 传入 synthetic `TaskTreeView.id`，gateway 应解析为 active
  draft tree 或返回 `invalid_task_tree_identity`。
- UI contract 不应继续暗示 synthetic `TaskTreeView.id` 是 domain id。

---

## 7. SQLite Rules

所有 SQLite authoring store 初始化时：

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

实现规则：

- constructor 接收 `db_path: str | Path`；
- 自动创建父目录；
- schema 初始化幂等；
- store methods 使用短事务；
- 支持 `close()` 和 context manager；
- SQLite correctness 错误包装成 `AuthoringStoreError` 或复用
  `TaskStoreError` / `VersionConflictError`；
- 所有 timestamps 使用 ISO 8601；
- 读取时通过 Pydantic model validation；
- JSON 字段稳定序列化，避免测试不稳定。

---

## 8. Test Matrix

### P8.1 store tests

- SQLite RawTask create/get/list/save/reopen。
- SQLite RawTask version conflict。
- SQLite DraftTaskTree create/list nodes/reopen。
- SQLite DraftTaskNode add child/reopen。
- SQLite DraftTaskNode update/reopen。
- SQLite mark accepted/read-only behavior。
- SQLite mark published/mapping lookup/reopen。
- SQLite rejects duplicate RawTask and duplicate DraftTaskNode。
- SQLite close/context manager behavior。

### P8.2 active state tests

- create RawTask -> active raw task -> reopen。
- create DraftTaskTree -> active draft tree -> reopen。
- regenerate draft tree -> old tree inactive, new tree active。
- mark published -> active state becomes `published`。

### P8.3 projection/gateway tests

- projection only shows active draft tree。
- inactive draft tree does not appear as forest。
- publish without `draftTreeId` resolves active draft tree。
- publish with invalid/synthetic id returns structured error。

---

## 9. Implementation Order

1. Add `sqlite_authoring.py` with schema bootstrap and connection helper.
2. Implement `SqliteRawTaskStore`.
3. Port existing in-memory RawTaskStore tests to SQLite reopen tests.
4. Implement `SqliteDraftTaskStore`.
5. Port existing in-memory DraftTaskStore tests to SQLite reopen tests.
6. Implement `SqliteAuthoringStateStore`.
7. Add active-state tests.
8. Only after store foundation is stable, update projection/gateway.
9. Implement `SqliteAuthoringCommandIdempotencyStore`.
10. Propagate UI generate/publish idempotency keys through the collaborator
    adapter into authoring command batches.
11. Add restart duplicate generate/publish smoke coverage.
12. Implement `UiCommandResponseIdempotencyStore` and SQLite persistence.
13. Wrap UI HTTP command route dispatch with API response replay/conflict
    handling.
14. Add restart duplicate generate/publish API response replay tests.

---

## 10. Open Questions

1. Should `source_raw_task_id` become a first-class `DraftTaskTree` field later?
   Current recommendation: not required for P8.1.
2. Should archived RawTasks/DraftTaskTrees be queryable through API?
   Current recommendation: no, trace/debug only.
3. Should authoring command idempotency use conflict behavior for hash mismatch?
   Current recommendation: no for P8.5. Same-key replay is safer for generate
   retries because LLM proposal variance can change the command payload before
   the deterministic command service sees it.
4. Should `authoring.sqlite` share a transaction with `tasks.sqlite` during publish?
   Current recommendation: no for MVP; use explicit lineage and recovery tests.
5. Should API command idempotency implement `in_progress` reservation?
   Current recommendation: not in P8.6. Completed-response replay gives the
   main user-test benefit. Reservation/recovery can be added if concurrent
   duplicate submits become observable.
