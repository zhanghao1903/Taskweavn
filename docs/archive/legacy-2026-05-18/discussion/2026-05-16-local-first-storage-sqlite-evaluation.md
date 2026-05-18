# Discussion: Local-first Storage 与 SQLite 评估

> 日期：2026-05-16
> 类型：讨论稿（暂不升级为实施计划）
> 状态：exploratory

---

## 1. 背景

TaskWeavn 当前大量状态已经使用 SQLite：

- workspace registry：`workspace.sqlite`
- session events：`events.sqlite`
- thoughts：`thoughts.sqlite`
- messages：`messages.sqlite`
- published tasks：`tasks.sqlite`

项目最终希望交付一个能本地运行的产品。作为个人开发者，短期内不提供云服务，也不希望用户必须依赖外部数据库。

因此需要评估：

> SQLite 是否足以作为 TaskWeavn 的主要产品级存储？

---

## 2. 初步结论

**SQLite 可以继续作为 TaskWeavn 的默认主存储，而且它不是临时方案。**

对于 TaskWeavn 当前阶段和可预期的本地产品形态，SQLite 的优势非常明显：

- 零服务依赖；
- 单文件，易分发、备份、迁移；
- ACID 事务足够可靠；
- 查询能力远强于 JSON 文件；
- WAL 模式下读写体验足够好；
- 非常适合 local-first 桌面 / 本地 server 产品；
- 能支撑 message / task / event / config / audit 这类结构化状态。

但它需要明确边界：

1. SQLite 适合作为 **本地单用户 / 少量并发 agent / 一个本地后端进程** 的主存储。
2. SQLite 不适合作为 **云端多租户 / 大规模多写入 worker / 跨设备实时协作** 的最终存储。
3. TaskWeavn 可以长期以 SQLite 作为产品默认存储，但代码层必须继续保持 Protocol / Store 抽象，以免未来迁移困难。

一句话：

```text
SQLite 是 TaskWeavn 本地产品的正确默认值；
不是因为它简单，而是因为它正好匹配 local-first 产品的分发模型。
```

---

## 3. 当前产品假设

本评估基于以下产品形态：

| 假设 | 说明 |
| --- | --- |
| 单机本地运行 | 用户在自己的电脑启动 TaskWeavn |
| 一个本地后端进程 | UI / CLI / Agent 通过本地 server 或进程内服务访问核心系统 |
| 单用户为主 | 一个 workspace 通常归一个用户 |
| 多 session | 同一个 workspace 下可有多个 session |
| 多 agent 但数量有限 | 多 agent 是协作模型，不是云端 worker farm |
| 本地文件是用户世界 | workspace 文件、artifact、日志归档都在本地 |
| 无云端服务依赖 | 不要求 PostgreSQL、Redis、对象存储、消息队列 |

在这些假设下，SQLite 是合适的。

---

## 4. SQLite 适合承载什么

### 4.1 强适合

| 对象 | 是否适合 SQLite | 说明 |
| --- | --- | --- |
| Session registry | 是 | 小表、强一致、查询简单 |
| MessageStream | 是 | 按 session / task / agent / 时间查询，非常适合索引 |
| EventStream | 是 | append-only 审计流，SQLite 能稳定承载 |
| Published TaskBus | 是 | Task 状态、拓扑、发布顺序都适合关系模型 |
| RawTask / DraftTaskTree | 是 | authoring 状态需要版本、patch、追溯 |
| Publish idempotency | 是 | 唯一键 + request hash 是 SQLite 强项 |
| Scheduler state | 是 | due_at / status / lease 查询适合索引 |
| Config snapshots | 是 | 分级配置、变更历史适合表结构 |
| Audit summary | 是 | 可查询、可关联、可导出 |

### 4.2 可以承载，但要谨慎

| 对象 | 风险 | 建议 |
| --- | --- | --- |
| 高频日志 | 行数增长快 | 原始日志走 JSONL，SQLite 只存索引或摘要 |
| 大模型原始响应 | 可能很长 | 存文件 artifact，SQLite 存引用和摘要 |
| 文件 diff / patch | 可能很大 | 小 patch 可入库，大 patch 存 artifact |
| embedding / RAG | 需要向量检索 | 初期可 FTS5；向量可用 sqlite-vec 或 sidecar |
| 大量 replay trace | 数据膨胀 | 按 session 归档、压缩、清理策略 |

### 4.3 不建议直接放 SQLite

| 对象 | 原因 | 替代 |
| --- | --- | --- |
| 大文件内容 | DB 膨胀，备份慢 | 文件系统 + SQLite metadata |
| 长期完整日志流 | 写入量大，文本查看不方便 | JSONL archive + SQLite index |
| 大型二进制 artifact | 不利于 diff / 复制 / 清理 | artifact directory |
| 高并发任务队列 | SQLite 单写限制 | 本地阶段可用，云端阶段再换队列 |

---

## 5. 最大风险：写并发

SQLite 的核心限制是：

```text
多读很好，单写严格。
```

这不等于不能做本地产品。它意味着 TaskWeavn 要明确写入模型。

### 5.1 当前风险点

TaskWeavn 未来会有多个写入来源：

- AgentLoop 写 EventStream；
- MessageBus 写 MessageStream；
- TaskPublisher 写 TaskBus；
- Scheduler 写 publish state；
- Authoring Service 写 RawTask / DraftTaskTree；
- Logging system 写日志或索引；
- UI 写用户确认、补充信息、配置变更。

如果每个对象各自拿连接乱写，后面容易遇到：

- `database is locked`；
- 写入顺序不可解释；
- 跨表一致性难以保证；
- UI 卡顿；
- 测试偶发失败。

### 5.2 建议约束

本地产品阶段建议采用：

```text
一个本地后端进程
  -> 每个 SQLite DB 有受控 Store/Service
  -> 写入通过服务方法进入
  -> 必要时每个 DB 一个写入队列或短事务
```

最低工程约束：

- 所有 SQLite 连接启用 WAL；
- 设置 `busy_timeout`；
- 写事务保持短小；
- 不在事务内调用 LLM、工具、网络或用户交互；
- Store 层捕获并包装 SQLite 错误；
- 所有跨对象状态变化通过 Service 编排，不让 Agent 直接写 DB；
- 对高频 append 场景做批量写入或写队列预留。

---

## 6. 文件布局建议

当前项目已经是“多 SQLite 文件”布局。这个方向是合理的，因为不同数据域生命周期不同。

建议长期保持：

```text
<workspace>/
  .taskweavn/
    workspace.sqlite      # workspace registry / sessions
    messages.sqlite       # workspace-level messages, row-isolated by session_id
    tasks.sqlite          # published task bus / task topology
    authoring.sqlite      # RawTask / DraftTaskTree / command history
    publish.sqlite        # idempotency / scheduler / publisher audit
    config.sqlite         # config snapshots / overrides / change log
    search.sqlite         # FTS indexes, optional
    storage_meta.sqlite   # migrations / schema versions, optional

  sessions/
    <session_id>/
      .session/
        events.sqlite     # session-level Action / Observation event stream
        thoughts.sqlite   # optional thought store
        logs/             # JSONL / pretty logs / archives
      <session_id>/       # session project root

  shared/
    ...
```

### 为什么不是一个大库？

一个大库的好处是事务边界简单，但坏处也明显：

- messages / logs / events 增长会拖累核心配置和任务；
- 备份和归档不够灵活；
- session 级数据不好搬迁；
- schema 变更影响面更大。

TaskWeavn 的数据天然分域：

- 用户体验域：messages；
- 执行域：tasks；
- authoring 域：raw/draft；
- 审计域：events；
- 配置域：config；
- 归档域：logs/artifacts。

所以“多个小库 + 明确边界”比“一个超级库”更符合当前架构。

---

## 7. 需要补齐的存储能力

SQLite 能满足需要，但当前还缺一层“产品级存储治理”。

### 7.1 Migration

需要统一 schema migration：

- 每个 DB 有 `schema_version`；
- migration 可幂等执行；
- migration 失败有清晰错误；
- 启动时检查版本；
- 文档记录每个 DB 的 schema ownership。

当前各 Store 自己 `CREATE TABLE IF NOT EXISTS` 可以支撑早期开发，但产品阶段会不够。

### 7.2 Backup / Export / Import

本地产品必须考虑用户数据安全：

- workspace 一键备份；
- session 单独导出；
- Task Tree 导出；
- messages/events 导出；
- 配置导出；
- 支持压缩归档。

SQLite 文件可以直接复制，但 WAL 模式下不能天真只复制 `.sqlite` 主文件。需要使用 SQLite backup API 或停写后打包。

### 7.3 Retention / Archive

Message、Event、Log、Thought 都会增长。

需要策略：

- session 归档；
- thought 默认可关闭或按 phase 过滤；
- 大日志只保留摘要索引；
- 老 session 可压缩；
- 用户可清理缓存和中间 artifact。

### 7.4 Observability

需要能回答：

- 哪个 DB 在写？
- 哪个 Store 写入失败？
- 是否出现 locked / timeout？
- 当前 workspace 数据量多大？
- 哪些表增长最快？

这应该接入已有 logging / observability 计划。

---

## 8. TaskBus 的特别评估

TaskBus 是最接近“队列”的对象，因此最容易让 SQLite 边界变紧。

当前 SQLite TaskBus 只做：

- publish；
- get；
- list_for_session；
- list_children；
- 持久化 pending Task。

这没有问题。

未来如果增加：

- claim；
- lease；
- heartbeat；
- complete；
- fail；
- retry；
- agent assignment；
- task dependency unlock；

SQLite 仍然可以做，但要用明确的状态机和原子更新。

示意：

```sql
UPDATE tasks
SET status = 'running',
    claimed_by = ?,
    lease_until = ?
WHERE task_id = ?
  AND session_id = ?
  AND status = 'pending'
RETURNING payload;
```

本地单进程 / 少量 worker 下可以接受。

但如果未来变成：

- 多进程 agent worker；
- 高频任务调度；
- 多用户共享同一个 server；
- 远程执行池；

那 TaskBus 应该抽象到可替换后端，SQLite 作为 local backend，PostgreSQL / Redis / NATS 作为 server backend。

当前代码继续保留 `TaskBus` Protocol 是正确方向。

---

## 9. MessageStream 的特别评估

MessageStream 是 UI 体验核心。

SQLite 非常适合当前需求：

- 按 session 聚合；
- 按 task 聚合；
- 按 agent 聚合；
- 按时间排序；
- 查询 pending actionable；
- replay 历史消息；
- UI 打开后恢复上下文。

但要注意两点：

1. 不要让 message 表变成所有事件的大杂烩。
2. 大内容要拆 artifact 引用，不要让单行 payload 无限膨胀。

建议 MessageStream 长期保持：

```text
message row = 用户可见或产品交互相关的消息事实
event row   = 工程审计和运行事实
log row     = 调试和观测事实
artifact    = 大内容和文件级产物
```

这套分流是对的。

---

## 10. 搜索与 RAG

SQLite 对关键词搜索可以直接用 FTS5。

适合：

- message 全文搜索；
- task title / intent 搜索；
- session summary 搜索；
- docs / notes 搜索。

向量检索需要单独评估：

- 初期可以先不做向量；
- 中期可以尝试 `sqlite-vec` / `sqlite-vss`；
- 也可以用本地 sidecar，如 LanceDB / Chroma / FAISS；
- 但不要过早把 RAG 绑定到复杂外部服务。

本地产品的优先级应该是：

```text
SQLite structured data
  -> SQLite FTS
  -> optional local vector sidecar
  -> cloud search only作为未来扩展
```

---

## 11. 推荐决策

### 11.1 保持 SQLite 为默认产品存储

这是 TaskWeavn 当前最现实、也最产品友好的选择。

它降低：

- 用户安装成本；
- 开发运维成本；
- 数据所有权争议；
- 本地调试难度；
- 个人开发者负担。

### 11.2 不引入 PostgreSQL / Redis 作为必需依赖

短期不建议。

原因：

- 会破坏本地产品体验；
- 增加安装和支持成本；
- 对个人开发者维护压力大；
- 当前没有足够规模需求证明值得。

### 11.3 继续保留 Store / Bus / Stream Protocol

这很重要。

SQLite 是默认实现，但系统不应该把 SQLite 当成业务抽象。

业务层依赖：

- `TaskBus`
- `TaskStore`
- `MessageStream`
- `EventStream`
- `RawTaskStore`
- `DraftTaskStore`
- `PublishIdempotencyStore`
- `SchedulerStore`
- `ConfigStore`

SQLite 只是这些协议的 local backend。

### 11.4 增加 Storage Governance 计划

需要单独建一个计划，而不是零散补。

计划应覆盖：

- SQLite schema ownership；
- migration manager；
- backup/export；
- retention/archive；
- storage health check；
- busy timeout / connection policy；
- local storage security；
- artifact 引用规范；
- 测试夹具和数据恢复测试。

---

## 12. 当前未解决问题

1. 是否保持多个 SQLite 文件，还是收敛部分 DB？
   - 当前倾向：保持分域多库。

2. `authoring.sqlite` 是否应该独立？
   - 当前倾向：独立。RawTask / DraftTaskTree 生命周期不同于 Published Task。

3. Publish idempotency / scheduler / audit 是否放同一个 `publish.sqlite`？
   - 当前倾向：可以放一起，它们都属于发布控制面。

4. 日志是 JSONL 还是 SQLite？
   - 当前倾向：原始日志 JSONL，SQLite 存索引和摘要。

5. 是否需要 encryption-at-rest？
   - 个人本地产品初期可不做默认加密，但要预留敏感信息清理和导出能力。

6. 是否需要统一 StorageService？
   - 可以有，但不要变成大一统对象。更合理的是 `StorageRegistry` 管理 DB 路径、migration、health。

---

## 13. 后续建议

建议新增一个 feature plan：

```text
Local-first Storage Governance
```

优先级建议为 P0/P1，原因是后续 UI、TaskBus、Scheduler、Authoring 都会持续增加本地状态。

第一版不要做重，只做框架：

1. 明确所有 SQLite DB 的 ownership 和 schema 文档。
2. 增加统一 migration 表和 helper。
3. 给 SQLite 连接加标准参数：WAL、busy_timeout、foreign_keys。
4. 增加 workspace storage health check。
5. 增加 workspace backup/export 设计。
6. 明确 artifact 与 DB 的边界。

---

## 14. 当前共识草案

TaskWeavn 应该继续坚持 local-first。

SQLite 对这个方向不是妥协，而是优势：

- 它让产品可以被一个人开发、分发、调试；
- 它让用户数据天然留在本地；
- 它让复杂系统仍然保持低运维成本；
- 它让 TaskWeavn 不必过早变成云服务项目。

但从现在开始，SQLite 需要从“各模块自己建表”升级为“受治理的本地存储层”。

这个治理不改变产品方向，只是让本地产品变得可交付。
