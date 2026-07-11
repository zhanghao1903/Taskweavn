# Session 架构事实说明

> 状态：当前实现事实基线
>
> 事实校准日期：2026-07-10
>
> 原始版本：[session.original.md](session.original.md)
>
> 修复记录：[fix-log/session.md](fix-log/session.md)
>
> 本文只描述仓库当前代码、契约和测试能够证明的行为。产品方向、已接受但未
> 实现的 ADR，以及旧文档中的示例 API，不作为当前实现事实。

---

## 1. 结论先行

当前 `Session` 同时有两个相关但不能混同的含义：

1. **产品语义**：一次连续协作的用户可见根，承载 Conversation、active work、
   historical Plans、Task 结果和 Audit 入口。
2. **后端实现**：`workspace.sqlite` 中的一条被动元数据记录，以及多数
   workspace-level facts 的 `session_id` 查询命名空间。

当前 `Session` **不是**一个拥有 TaskBus、MessageStream、AgentPool、
独立项目目录或独立 sidecar runtime 的聚合对象。那些资源由
`MainPageWorkspaceRuntime` 按 workspace 组合；请求中的 Session id
用于选择该 workspace runtime 中的事实。

`Session` 的当前文件边界也不是独立 workspace：

~~~text
public identity = (workspace_id, session_id)

workspace runtime
  -> one selected workspace root
  -> one set of workspace-level stores
  -> one fixed-route dispatcher/default-agent adapter
  -> many Session registry rows
       -> row-scoped messages/tasks/plans/asks/results
       -> per-session events/context/log metadata
       -> shared workspace project files
~~~

必须同时保留以下两个事实：

- 多数产品事实按 `session_id` 隔离；
- 多个 Session 在同一 workspace 内操作同一个 project root。

因此，Session 是当前**事实与交互边界**，但不是当前**文件系统 fork 边界**、
**进程边界**或**安全租户边界**。

---

## 2. 权威与所有权

### 2.1 Session 自身只拥有元数据

核心 `Session` 是 frozen dataclass：

~~~python
@dataclass(frozen=True)
class Session:
    id: str
    name: str
    workspace_root: Path
    created_at: datetime
    last_active_at: datetime
    status: SessionStatus = "active"
~~~

它还提供路径计算属性：

~~~text
layout
session_dir
meta_dir
project_dir
events_db_path
thoughts_db_path
messages_db_path
plan_path
logs_dir
~~~

这些属性不打开 store，也不让 Session 成为 store owner。变更元数据必须经过
`SessionManager`。

当前模型没有：

- `closed_at`；
- `user_id`；
- `SessionConfig`；
- autonomy profile；
- Agent 列表或 AgentPool；
- parent/sub-session 关系；
- per-Session workspace fork metadata。

### 2.2 当前事实权威表

| 事实 | 当前权威 | 物理作用域 |
|---|---|---|
| Session id/name/timestamps/stored status | `SessionManager` | `.plato/workspace.sqlite` |
| selected workspace -> runtime | `WorkspaceRuntimeRegistry` | sidecar process memory |
| Published Task lifecycle | `SqliteTaskBus` | workspace DB，按 `session_id` 查询 |
| RawTask/DraftTaskTree/active authoring | authoring stores | workspace DB，按 `session_id` 查询 |
| durable Plan/PlanTaskNode | `SqlitePlanStore` | `authoring.sqlite`，复合 Session key |
| Conversation messages | `SqliteMessageStream` | `messages.sqlite`，按 Session 过滤 |
| execution ASK | `SqliteAskStore` | `asks.sqlite`，按 Session 过滤 |
| task result/error summary | execution summary store | `results.sqlite`，按 Session/Task 查询 |
| renderer replay events | `SqliteUiEventSource` | `ui_events.sqlite`，按 Session 过滤 |
| Agent Action/Observation | `SqliteEventStream` | 每 Session 一个 `events.sqlite` |
| execution context snapshots/traces | `SqliteContextStore` | 每 Session 一个 `context.sqlite` |
| user-visible Activity | query-time projection | 不存在独立 Activity store |
| workspace files | selected workspace root | 同一 workspace 内所有 Session 共享 |
| default-agent adapter/dispatcher/stores | `MainPageWorkspaceRuntime` | 每个已打开 workspace runtime 一份 |

“Session owns X”在产品语义上可以表示“X 归属于该连续协作”，但实现文档必须进一步
说明 X 的真正代码 owner 和存储作用域。

### 2.3 Identity 不是全局单值

`new_session_id()` 返回 UUID hex 的前 8 位，即 32 bit 的短 id。
`workspace.sqlite.sessions.id` 是主键，所以数据库只保证一个 workspace
registry 内不重复。生成器没有显式碰撞重试。

多 workspace 测试明确允许两个 workspace 都存在 `shared-session`。
renderer 和 public route 的真实身份因此是：

~~~text
(workspaceId, sessionId)
~~~

不能把 `session_id` 单独写成跨 workspace 全局唯一 id，也不能把它当作
授权凭证。

---

## 3. WorkspaceLayout 与持久化

### 3.1 当前目录结构

~~~text
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
│  ├─ logs/                         # workspace/global logging when configured
│  └─ sessions/
│     └─ <session_id>/
│        ├─ events.sqlite           # created lazily by event consumers
│        ├─ context.sqlite          # created lazily by context consumers
│        ├─ thoughts.sqlite         # path helper exists; Main Page does not wire it
│        ├─ plan.md                 # path helper exists; no current production consumer
│        └─ logs/
├─ shared/
└─ user project files...
~~~

`WorkspaceLayout` 只负责 path math、目录 bootstrap 和少量 legacy
migration。它不会一次性创建所有 SQLite 文件；各 consumer 打开 store 时创建
schema。

### 3.2 Workspace-level stores

Main Page runtime 当前从同一个 `WorkspaceLayout` 打开：

- `messages.sqlite`；
- `tasks.sqlite`；
- `authoring.sqlite`；
- `asks.sqlite`；
- `ui_commands.sqlite`；
- `ui_events.sqlite`；
- `results.sqlite`；
- `inspection.sqlite`；
- `usage.sqlite`；
- `contract_revision.sqlite`；
- `runtime_config.sqlite`；
- `execution_plane.sqlite`。

不能把“workspace-level”误写成“跨 Session 无隔离”。例如：

- Task 的唯一性是 `(session_id, task_id)`；
- Plan 的主键是 `(session_id, plan_id)`；
- PlanTaskNode 的主键是 `(session_id, task_node_id)`；
- RawTask/DraftTask/authoring state 使用 Session key；
- Message 查询使用 `list_for_session(session_id)`；
- UI event cursor 的唯一性包含 `session_id`；
- result summary 可按 Session/Task 查询。

但也不能声称所有主键都以 Session 复合：

- Message `message_id` 在整个 workspace DB 内唯一；
- execution ASK 的 `ask_id` 是整个 `asks` 表主键；
- result `summary_id` 是全表唯一；
- inspection、runtime config 和部分 usage/contract facts 有 workspace 级作用域，
  不能一律归成 Session 私有。

### 3.3 Session-private stores

当前真正按目录物理分片的主要数据是：

| 路径 | 当前事实 |
|---|---|
| `events.sqlite` | Agent Action/Observation append log；Session 由文件路径隐含，row 没有 `session_id`；可选 `task_id` |
| `context.sqlite` | execution context snapshots/traces；文件已按 Session 分片，row 仍保存 `session_id` |
| `logs/` | session logging archive；创建 Session 时可初始化 manifest |
| `thoughts.sqlite` | layout/path helper存在；Main Page AgentLoop 默认仍使用 `NullThoughtStore` |
| `plan.md` | layout/path helper存在；当前 durable Plan 权威在 `authoring.sqlite` |

`events.sqlite` 的 `event_id` 列当前没有 UNIQUE constraint。
Agent event payload 本身也没有 `session_id` 字段；Session scope 来自所打开的
数据库路径。旧文档“任何 event 都必须携带 Session id”的绝对表述不成立。

### 3.4 Project root 是共享视图

当前实现：

~~~python
def session_project_dir(self, session_id: str) -> Path:
    del session_id
    return self.root
~~~

所以：

~~~text
Session A project_dir == workspace root
Session B project_dir == workspace root
~~~

没有自动 copy、git worktree、fork 或 merge。正常文件工具会阻止读取/写入
`.plato`、legacy `.taskweavn` 和 `.code-agent`
metadata tree，但这不构成 Session 间文件隔离。

“Session Workspace 是每个 Session 的独立执行目录”仍出现在部分 product direction
文档中；它是目标模型，不是当前代码事实。

### 3.5 Bootstrap 与 legacy migration

`WorkspaceLayout.bootstrap()` 当前会：

1. 创建 workspace root；
2. 当 `.plato` 不存在时，把 legacy `.taskweavn` 改名迁移；
3. 创建 `.plato`；
4. 把 legacy `.code-agent/logs` 迁入 `.plato/logs`；
5. 创建 root-level `shared/`；
6. 创建 `.plato/sessions/`。

`bootstrap_session(session_id)` 幂等创建 Session metadata directory 和
`logs/`。调用 `session_project_dir().mkdir()` 实际只是确保共享
workspace root 存在。

---

## 4. SessionManager 的真实生命周期

### 4.1 Registry schema

`SessionManager` 每 workspace 一份，连接 `workspace.sqlite`：

~~~sql
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    last_active_at  TEXT NOT NULL,
    status          TEXT NOT NULL
);
~~~

连接使用 autocommit、WAL 和 `synchronous=NORMAL`。

### 4.2 当前操作

| 方法 | 行为 |
|---|---|
| `create(name)` | 拒绝空名；生成短 id；插入 `active` row；bootstrap Session 目录 |
| `get(id)` | 缺失返回 `None` |
| `require(id)` | 缺失抛 `SessionManagerError` |
| `list()` | 按 `last_active_at DESC` 返回 |
| `touch(id)` | 只更新时间 |
| `rename(id, name)` | 拒绝空名并更新时间 |
| `mark_status(id, status)` | 写入允许的 core stored status 并更新时间 |
| `delete(id)` | 删除 registry row，把 Session metadata dir 移入 deleted archive，返回下一条最近 Session |
| `close()` | best-effort 关闭 registry connection |

`touch()` 和 `mark_status()` 当前生产代码没有调用；
`mark_status()` 的直接使用只出现在测试。普通消息、Task 或 LLM 运行不会自动
touch Session registry row。

### 4.3 Delete 不是“正常关闭”

Main Page 暴露的 Session delete 当前执行：

~~~text
DELETE workspace.sqlite.sessions row
move .plato/sessions/<id>/
  -> .plato/deleted-sessions/<id>-<timestamp>
return newest remaining Session id, or null
~~~

它**不会**：

- 等待或停止该 Session 的 running Task；
- 关闭一个 per-Session dispatcher 或 AgentPool，因为它们不存在；
- 拒绝新的 Task publish；
- cascade 删除 workspace-level messages/tasks/authoring/asks/UI events/results；
- 清除 usage、contract revision 或 execution-plane facts；
- 删除 workspace root 用户文件；
- 写入 `closed` / `abandoned` 状态。

因此 delete 是“registry 隐藏 + Session 私有目录归档”，不是完整数据清除、执行
quiesce 或生命周期终态。当前也没有跨 store transaction。

删除后，snapshot 先检查 Session registry，因而该 Session 不再可正常读取；留在
workspace-level DB 的同 id rows 没有被本路径清理。

### 4.4 当前不存在的 lifecycle

旧稿的：

~~~text
creating -> active -> closed | abandoned
~~~

不是当前 state machine。没有自动空闲超时关闭、`closed_at`、崩溃后
`abandoned` 标记，也没有 `Session.close()` 或
`Session.resume()`。

sidecar runtime 的 `close()` 是 workspace runtime 资源回收，与删除或关闭
某一 Session 不同。

---

## 5. 三套状态词必须分开

### 5.1 Stored core status

`Session.status` 的允许值是：

~~~text
active
awaiting_user
finished
archived
~~~

这是 registry 中的 stored hint，不是 Main Page 当前工作状态的统一权威。

### 5.2 Core derived helper

`core.session_status.derive_session_status()` 的规则是：

1. stored `archived` 优先；
2. MessageStream 有 pending actionable -> `awaiting_user`；
3. EventStream 最后一个事件是 `AgentFinishObservation` ->
   `finished`；
4. 其他情况 -> `active`。

当前 `src/` 中没有生产调用该 helper；直接调用点都在
`tests/test_session_status.py`。不能用它解释 Main Page snapshot。

### 5.3 Main Page UI status projection

Main Page 使用另一套状态词：

~~~text
new
understanding
draft_ready
running
waiting_user
completed
failed
~~~

当前 active Session 的优先级是：

1. active execution ASK -> `waiting_user`；
2. planning 中有 pending authoring ASK -> `waiting_user`；
3. pending confirmations -> `waiting_user`；
4. TaskTree 节点有 `waiting_for_user` -> `waiting_user`；
5. TaskTree status `draft` -> `draft_ready`；
6. TaskTree status `published/running` -> `running`；
7. TaskTree status `completed/failed` -> 同名 UI 终态；
8. stored `awaiting_user` -> `waiting_user`；
9. stored `finished` -> `completed`；
10. 有 messages -> `understanding`；
11. 否则 -> `new`。

snapshot 中同 workspace 的其他 Session 不是逐个投影；除当前 Session 外，候选项
统一被标为 `new`。

### 5.4 Catalog/lifecycle payload 又使用 stored status

`MainPageSessionLifecycleGateway.list_sessions()` 和 multi-workspace catalog
直接序列化 registry `session.status`。因此 catalog 可能返回
`active/awaiting_user/finished/archived`，而 snapshot 返回 UI status。

这造成当前 contract drift：

- frontend `SessionSummary.status` 类型只声明 UI status；
- lifecycle/catalog payload 实际可返回 core stored status；
- lifecycle/catalog payload 也不总是包含 backend
  `SessionSummary` 要求的 project/workflow 字段。

文档和消费者不能假定所有“Session status”来自同一个枚举或同一个派生函数。

---

## 6. Workspace runtime，而不是 Session runtime

### 6.1 MainPageWorkspaceRuntime

sidecar 为每个已打开 workspace 构造一个 `MainPageWorkspaceRuntime`。它
持有：

- `SessionManager`；
- MessageStream/MessageBus；
- AskStore；
- TaskBus；
- RawTask/Draft/authoring/Plan stores；
- result、usage、runtime config、contract revision、inspection stores/services；
- UI event source；
- query/command gateways；
- fixed-route Default Agent adapter；
- fixed-route dispatcher；
- HTTP transport。

这些对象被同一 workspace 内的所有 Session 请求复用。

`MainPageWorkspaceRuntime.session` 只是 sidecar 启动配置中可选的
`session_id` 解析结果。应用可以在 `session is None` 时启动，随后
通过 HTTP 创建并使用 Session。创建或前端选择 Session 不会把这个字段变成新的
“当前 Session”权威。

### 6.2 Default Agent 是 workspace runtime 资源

当前 fixed-route bridge 没有 Agent Manager、AgentPool 或动态分配：

~~~text
TaskBus pending Task
  -> FixedRouteExecutionDispatcher
  -> FixedRouteTaskExecutor
  -> one ResidentDefaultAgent adapter
  -> fresh AgentLoop runner for that Task
~~~

`AgentLoopResidentDefaultAgent` 每次 `run(task)` 通过
`loop_factory(task)` 创建 runner。runner 使用 Task 的
`session_id` 打开：

- 对应 Session 的 `events.sqlite`；
- 对应 Session 的 context builder/store；
- workspace root tools；
- TaskBus-backed interrupt checker。

它不会在 Task 结束后保留一个可透明恢复的 AgentLoop stack。

### 6.3 当前串行边界

一个 `FixedRouteExecutionDispatcher` 有一个 worker thread 和一个
Session queue：

~~~text
request_dispatch(session_id)
  -> coalesce duplicate pending/running request for that Session
  -> enqueue session_id
  -> one worker pops one Session
  -> drain up to max_ticks_per_trigger
  -> then process next queued Session
~~~

因此当前一个 workspace runtime 中，经该 dispatcher 的 Session drains 是依次
执行的；同一 Session 不会被该 dispatcher 重复并发 drain。

但边界不能夸大：

- `TaskBus.claim_next` 本身没有“该 Session 已有 running Task”全局锁；
- 其他直接调用 TaskBus/executor 的代码路径不自动继承 dispatcher 串行性；
- 每个 lazy workspace runtime 有自己的 dispatcher；
- 没有跨 workspace 的全局执行协调器或总并发上限；
- 当前 registry 没有 idle runtime eviction。

“每 Session 一个 writer lane”描述的是 Main Page fixed-route product path 的效果，
不是 Session 模型本身或 TaskBus schema 的不变量。

---

## 7. Active work、Plan 与历史

### 7.1 Session 是连续产品边界

产品语义上，Session 保留跨 work segment 的连续性：

~~~text
Session
  -> Conversation
  -> active RawTask / authoring state
  -> active Plan and TaskNodes
  -> Published Tasks and results
  -> archived Plans
  -> Audit/diagnostic links
~~~

Task lifecycle 仍由 TaskBus 权威决定；Session content 和 Activity 解释这些事实，
不能替代它们。

### 7.2 当前 Plan persistence

`SqlitePlanStore` 在 `authoring.sqlite` 中支持：

- 一个 Session 保存多个 Plans；
- `list_plans(session_id)`；
- `get_active_plan(session_id)` 选择最新的 non-archived Plan；
- PlanTaskNode 与 Plan 使用 Session 复合 key；
- Plan archive 设置 `status=archived`、`archived_at` 并增加
  version。

durable Plan 只有在这些状态之一才能由 lifecycle service 归档：

~~~text
awaiting_acceptance
accepted
follow_up_needed
failed
cancelled
~~~

legacy TaskTree projection 只有 `completed` 或 `failed` 可以归档。
归档会取消匹配的 active authoring state，并写入 Session Message：

~~~text
Plan archived: <title>
~~~

### 7.3 Snapshot 与 Activity 的历史投影

Main Page snapshot 当前包含：

- `planning`；
- `active_plan`；
- `archived_plans`；
- `task_tree`；
- Session messages；
- pending confirmations/ASKs；
- result/file summary；
- Audit links。

当 durable Plan 不可用时，snapshot model 仍可从 legacy TaskTree 投影
`active_plan`。所以“Plan”和“TaskTree”在当前兼容期不是两个完全独立的
active work 权威。

Plan archive 不删除 Session MessageStream。Activity 会为 archived Plans 生成
`Plan archived` history item，Conversation 连续性属于 Session，而不是
单个 Plan。

`.plato/sessions/<id>/plan.md` 不是上述 Plan lifecycle 的当前权威。

---

## 8. Conversation、Activity、Audit 与三种 event stream

### 8.1 Conversation

`SqliteMessageStream` 是 workspace-level durable message store。
`list_for_session(session_id)` 为 snapshot 和 Activity 提供当前 Session 的
messages。

Runtime Input publisher 把以下内容写成 `AgentMessage`：

- user input；
- Router interpretation/trace；
- clarification question card；
- guidance/ASK/confirmation/task change outcome；
- read-only inquiry answer。

这些消息带 Session id，并可带 Task id、related action/command refs 和安全的
render metadata。

### 8.2 Activity 是 projection，不是事实库

`DefaultSessionActivityProjectionService` 在读取时合并：

- Session messages；
- active Plan 与 PlanTaskNodes；
- archived Plans；
- legacy TaskTree fallback；
- pending/active ASK；
- confirmations；
- result；
- file change summary。

它按 item id 去重，按 `(occurred_at, id)` 逆序排序，使用整数 offset
cursor。limit 会被限制到 1..200。

Activity item 是用户可读解释，不是 Task/ASK/Plan 状态权威。当前没有独立
`activity.sqlite`；所谓“durable Activity”主要来自 durable source facts
和 MessageStream，再由 query-time projection 重建。

### 8.3 不要混同三个 stream

| 名称 | 用途 | 存储 |
|---|---|---|
| Agent `EventStream` | Action/Observation、tool/runtime execution evidence | per-Session `events.sqlite` |
| `MessageStream` | user-visible Conversation 与 actionable/response | workspace `messages.sqlite` |
| UI event source/store | SSE invalidation/replay cursor | workspace `ui_events.sqlite` |

Activity 读取上述事实和其他 domain stores 后投影。Audit 又在更广的 event、Task、
result、log、config、inspection evidence 上构建 trust projection。

所以“Session 是 EventStream 的根”只对 per-Session Agent event file 成立，不能
扩展成“所有 Session 事实都在一个 EventStream 中”。

---

## 9. API 与前端选择模型

### 9.1 当前 lifecycle routes

当前 sidecar 实际路由是：

| Method | Route | 行为 |
|---|---|---|
| `GET` | `/api/v1/sessions` | list |
| `POST` | `/api/v1/sessions` | create |
| `PATCH` | `/api/v1/sessions/{sessionId}` | rename |
| `POST` | `/api/v1/sessions/{sessionId}/delete` | delete/archive private metadata |
| `GET` | `/api/v1/sessions/{sessionId}/snapshot` | current Main Page projection |
| `GET` | `/api/v1/sessions/{sessionId}/activity` | Activity projection |
| `GET` | `/api/v1/sessions/{sessionId}/events` | UI/SSE event replay |

另有同一 Session scope 下的 runtime input、authoring、Plan、Task、ASK、Audit 和
diagnostics routes。

部分 engineering contract 仍写 `DELETE /sessions/{id}`；当前代码和前端
使用的是 `POST .../delete`。

### 9.2 Workspace-scoped routes

multi-workspace transport 支持：

~~~text
/api/v1/workspaces/{workspaceId}/sessions/...
~~~

它先用 renderer-safe workspace id 找到 lazy runtime，再把路径改写给该 runtime
的普通 transport。带 workspace id 的 Runtime Input body 若声明另一个
`workspaceId`，会被拒绝。

不带 workspace prefix 的 compatibility route 总是落到
`current_workspace_id`。

### 9.3 Frontend active identity

Main Page renderer 分别保存：

~~~text
activeWorkspaceId
activeSessionId
~~~

snapshot query key 和 snapshot identity 都包含两个维度。选择 catalog 中另一个
Session 时，renderer 同时采用该 Session 的 `workspaceId`。

HTTP adapter 的选择规则：

1. 有 preferred Session id 就使用；
2. 否则 list 当前 workspace Sessions；
3. 使用 `last_active_at DESC` 的第一条；
4. 若为空，抛“create a session to start”错误。

创建成功后 frontend 选择新 Session；rename 后刷新 catalog 和 snapshot；delete
成功后采用 backend 返回的 `nextSessionId`，没有剩余 Session 时设为
`null`。

### 9.4 Workspace catalog

`GET /api/v1/workspaces` 返回：

- renderer-safe workspace id/label；
- `available/unavailable`；
- current marker；
- Session count；
- 最近最多 20 个 registry Session summaries；
- last update time。

缺失 root 被标为 `unavailable`，不泄露 absolute path。catalog read 对每个
可用 workspace 临时打开 `SessionManager`；它本身不需要构造完整
workspace runtime。

---

## 10. Multi-workspace runtime 边界

### 10.1 Lazy registry

`WorkspaceRuntimeRegistry`：

- 用 `workspace_id` 查 internal `root_path`；
- root 不存在或 id 未注册时返回 safe unavailable error；
- 首次 workspace-scoped 请求时 lazy 构造完整 runtime；
- 缓存 runtime；
- sidecar 关闭时 `close_all()`。

当前没有 `close_idle()` 或 LRU eviction。

### 10.2 隔离边界

两个 workspace 有各自：

- `WorkspaceLayout`；
- Session registry；
- messages/tasks/authoring/ASK/UI events/results DB；
- LLM/runtime assembly；
- dispatcher/default-agent adapter。

同名 Session id 不会跨读，因为 route 先选择 workspace runtime。测试覆盖：

- duplicate Session id 的 snapshot 分别读取；
- command 只写 routed workspace；
- routed workspace 使用对应 LLM factory result；
- unknown workspace 返回 safe `workspace_unavailable`；
- compatibility route 使用 current workspace。

### 10.3 当前并发没有全局政策

registry 可以缓存多个完整 workspace runtimes；每个 runtime 都能拥有自己的 worker。
当前代码没有跨 runtime scheduler，也没有在离开 workspace 时自动暂停 running
Task。multi-active execution 的全局限制仍是未解决边界，不能从“lazy runtime”推导出
“只可能有一个 workspace 执行”。

---

## 11. 恢复语义

### 11.1 Startup Task recovery

workspace runtime 构造时会遍历 registry 中全部 Session，并把
`status=running` 且已有 `interrupt_requested` 的 Task 收敛为
`failed`，error ref 标记 `safe_point=sidecar_recovery`。

它不会恢复任意未标 interrupt 的 running Task，也不会重建原 AgentLoop 内存。

### 11.2 Snapshot best-effort recovery

每次 snapshot 读取前，transport best-effort 运行：

1. **ASK recovery**
   - 对已回答且 active 的 authoring RawTask，可重新调用幂等 task-tree generation；
   - 对已回答 blocking execution ASK，可把仍 waiting 的 Task resume 到
     `pending`，或为已经 pending 的 Task补发 dispatch。
2. **stale stop recovery**
   - 对 `running + interrupt_requested` 且超过 45 秒 grace 的 Task，收敛为
     failed/cancelled error projection。

recovery 异常会记录日志，但 snapshot read 继续。

### 11.3 不是透明 Session resume

当前恢复单位是 durable domain facts：

- Task lifecycle；
- ASK/authoring continuation；
- Event/Context/Message/Result/Audit evidence。

不存在：

- `Session.resume(session_id)`；
- provider transcript 续接；
- Python stack/AgentLoop 原地恢复；
- tool process 透明恢复；
- 自动重放全部 Agent actions。

新的 execution run 会从 durable facts 重建 context，并创建新的 AgentLoop。

---

## 12. 安全与隔离边界

### 12.1 当前具备

- workspace id 对 renderer 是 opaque safe id；
- catalog 不返回 raw absolute root；
- workspace-prefixed route 先选择注册 runtime；
- Runtime Input 验证 path/body workspace identity；
- command path/body Session identity 由 transport parser 验证；
- normal file/shell tools保护 `.plato`、`.taskweavn`、
  `.code-agent`；
- per-Session query 通常先要求 registry 中存在 Session；
- sidecar 可选 bearer token 保护 HTTP surface。

### 12.2 当前不具备

- Session model 没有 user/tenant identity；
- 没有 Session-level RBAC、invite 或共享角色；
- Session id 不是 secret；
- 没有 per-Session filesystem sandbox；
- 没有跨 Session file merge/conflict policy；
- delete 不是 secure erase；
- 没有 SessionConfig 驱动的 autonomy/permission profile；
- 没有统一的 Session-level runtime config override；Main Page 当前 effective runtime
  config 以 workspace scope 读取。

“Session 隔离”应限定为具体 store/file/query 边界，不能被用作完整安全隔离声明。

---

## 13. 当前实现与非现状

| 陈述 | 当前判定 | 事实 |
|---|---|---|
| Session 有全局唯一 id | 否 | id 只在 workspace registry 内为主键；public identity 是二元组 |
| 每个 Session 有独立 project root | 否 | `session_project_dir()` 返回 workspace root |
| Session owns TaskBus/MessageStream | 否 | workspace runtime owns，rows 按 Session 查询 |
| Session owns one Agent/AgentPool | 否 | workspace runtime owns one fixed-route adapter；每 Task 新 AgentLoop |
| 当前有 Agent Manager/dynamic assignment | 否 | fixed-route Default Agent |
| Session 有 `SessionConfig` | 否 | core model无该字段或类型 |
| Agent 从 Session 继承 autonomy | 否 | 当前无该装配路径 |
| lifecycle 是 creating/active/closed/abandoned | 否 | core stored 与 UI projection 使用另外两套状态 |
| Session 会空闲超时自动关闭 | 否 | 无实现 |
| delete 会等 running Task 并 cascade 清理 | 否 | registry delete + private dir archive |
| 所有 Session facts 都在 EventStream | 否 | 多个 domain stores、MessageStream、UI event store并存 |
| 所有 event rows 都携带 `session_id` | 否 | per-Session events file 隐含 scope |
| `plan.md` 是当前 Plan 权威 | 否 | `SqlitePlanStore` 位于 `authoring.sqlite` |
| Main Page 持久化 thoughts.sqlite | 否 | path exists；Main Page AgentLoop 使用默认 null thought store |
| 当前有 transparent Session resume | 否 | 只有 bounded durable-fact recovery |
| 当前有 sub-session API | 否 | 无 `create_sub_session` |
| 当前有 Session template | 否 | 无模型/registry/API |
| 当前有 multi-user invite/RBAC | 否 | 无 `invite` 或 user field |
| 当前有跨 Session artifact import API | 否 | 无 `import_artifact` |
| 当前有全局 multi-workspace concurrency policy | 否 | 每 runtime 自有 worker，无全局协调 |

---

## 14. 当前可依赖的不变量

### 14.1 Identity 与路由

1. workspace-scoped请求先解析 registered `workspaceId`；
2. Session registry 主键只在该 workspace DB 内有效；
3. frontend cache/query identity 应包含 workspace + Session；
4. compatibility route 使用 current workspace。

### 14.2 Persistence

1. Session registry 在 `workspace.sqlite`；
2. workspace-level domain stores 通过明确的 Session query/filter 隔离；
3. Agent EventStream 通过 per-Session DB path 隔离；
4. Context store通过 path 和 row field 双重携带 Session scope；
5. workspace files 不按 Session fork；
6. metadata DB 由 consumer lazy创建。

### 14.3 Execution

1. Main Page product path 使用 fixed-route Default Agent；
2. dispatcher 对同 Session dispatch coalesce；
3. 一个 workspace dispatcher worker 依次 drain queued Sessions；
4. 每个 Task execution 创建新的 AgentLoop；
5. AgentLoop 使用 Task 的 Session event/context paths 和共享 workspace root；
6. TaskBus 本身不是跨所有调用者的 single-writer scheduler。

### 14.4 Product projection

1. Session content 不替代 Task/ASK/Plan事实；
2. Main Page snapshot 有独立 UI status projection；
3. Activity 是 query-time read model；
4. Plan archive 保留 Conversation并进入 Session history；
5. Audit/diagnostics 是独立 trust surface。

---

## 15. 已知缺口与文档约束

### 15.1 当前代码缺口

| 缺口 | 当前影响 |
|---|---|
| 8 hex Session id 且无 collision retry | workspace registry 依赖 DB constraint，不能声称强全局唯一 |
| stored/core/UI 三套 status 边界 | catalog、lifecycle 和 snapshot 可能使用不同词汇 |
| lifecycle/catalog payload 与 frontend type drift | core statuses/project-workflow字段不完全匹配声明 |
| 非当前 Session snapshot summary 强制 `new` | Session list 不是每条实时状态视图 |
| delete 无跨 store cascade/quiesce | 可能留下 workspace-level historical/orphan facts；不是完整清除 |
| Session registry activity 不自动 touch | recency 不等同于最新 domain activity |
| workspace root 共享 | Session 间没有文件 fork/merge 隔离 |
| 每 workspace runtime独立 worker | 无全局 multi-workspace并发政策 |
| `thoughts.sqlite` / `plan.md` helpers未接当前 Main Page权威 | 路径存在不表示数据存在 |
| layered WorkspaceContext/SessionContext未实现 | 当前 Context Manager 仍主要服务 Task execution |
| lifecycle HTTP delete verb与部分 contract不同 | 当前代码使用 `POST .../delete` |
| no user/RBAC model | Session 不能作为 tenant security boundary |

### 15.2 相关 product/ADR 的使用方式

以下文档提供产品方向，但不能覆盖本文的代码事实：

- [Plato Session Content Model](../product/plato-session-content-model.md)：
  Session 是连续协作根、Session content 不是状态权威；
- [Plato Session Active Work Lifecycle](../product/plato-session-active-work-lifecycle.md)：
  active Plan/history/Conversation continuity 的产品语义；
- [Workflow, Session, And Task UX Model](../product/workflow-session-task-ux-model.md)：
  包含独立 Session Workspace 目标，与当前共享 root 实现不同；
- [ADR-0017](../decisions/ADR-0017-session-and-workspace-context-management-foundation.md)：
  明确是 accepted foundation / not implemented 的 layered context方向；
- [Multi-Workspace API And Runtime Contract](../engineering/multi-workspace-api-runtime-contract.md)：
  部分 foundation 已实现，部分 endpoint/concurrency/eviction仍是方向。

未来若实现 per-Session workspace、SessionConfig、Agent Manager、sub-session、
multi-user、artifact import 或完整 SessionContext，必须以独立 ADR/contract/代码/
测试落地后再更新事实文档，不能把示例代码提前写成现状。

---

## 16. 代码与测试索引

### 16.1 Core 与 storage

- [session.py](../../src/taskweavn/core/session.py)
- [session_manager.py](../../src/taskweavn/core/session_manager.py)
- [session_status.py](../../src/taskweavn/core/session_status.py)
- [workspace_layout.py](../../src/taskweavn/core/workspace_layout.py)
- [sqlite_event_stream.py](../../src/taskweavn/core/sqlite_event_stream.py)
- [sqlite_store.py](../../src/taskweavn/context/sqlite_store.py)
- [sqlite_thought_store.py](../../src/taskweavn/memory/sqlite_thought_store.py)
- [sqlite_message_stream.py](../../src/taskweavn/interaction/sqlite_message_stream.py)
- [sqlite_ask_store.py](../../src/taskweavn/interaction/sqlite_ask_store.py)
- [sqlite_bus.py](../../src/taskweavn/task/sqlite_bus.py)
- [sqlite_authoring.py](../../src/taskweavn/task/sqlite_authoring.py)
- [sqlite_plan_store.py](../../src/taskweavn/task/sqlite_plan_store.py)

### 16.2 Main Page runtime 与 projection

- [main_page.py](../../src/taskweavn/server/main_page.py)
- [main_page_agent.py](../../src/taskweavn/server/main_page_agent.py)
- [main_page_sessions.py](../../src/taskweavn/server/main_page_sessions.py)
- [multi_workspace.py](../../src/taskweavn/server/multi_workspace.py)
- [query_snapshot_helpers.py](../../src/taskweavn/server/ui_contract/query_snapshot_helpers.py)
- [session_activity_projection.py](../../src/taskweavn/server/ui_contract/session_activity_projection.py)
- [ask_recovery.py](../../src/taskweavn/server/ask_recovery.py)
- [task_stop_recovery.py](../../src/taskweavn/server/task_stop_recovery.py)
- [ui_http_routes.py](../../src/taskweavn/server/ui_http_routes.py)

### 16.3 Frontend

- [httpMainPageAdapter.ts](../../frontend/src/pages/main-page/httpMainPageAdapter.ts)
- [useMainPageSessionIdentityState.ts](../../frontend/src/pages/main-page/useMainPageSessionIdentityState.ts)
- [useMainPageSessionLifecycle.ts](../../frontend/src/pages/main-page/useMainPageSessionLifecycle.ts)
- [useMainPageSnapshotQuery.ts](../../frontend/src/pages/main-page/useMainPageSnapshotQuery.ts)
- [MainPageSessionSidebar.tsx](../../frontend/src/pages/main-page/MainPageSessionSidebar.tsx)
- [platoApi.ts](../../frontend/src/shared/api/platoApi.ts)

### 16.4 关键测试

- [test_workspace_layout.py](../../tests/test_workspace_layout.py)
- [test_session_manager.py](../../tests/test_session_manager.py)
- [test_session_status.py](../../tests/test_session_status.py)
- [test_session_activity_projection.py](../../tests/test_session_activity_projection.py)
- [test_main_page_sidecar_app.py](../../tests/test_main_page_sidecar_app.py)
- [test_multi_workspace_sidecar.py](../../tests/test_multi_workspace_sidecar.py)
- [test_ui_http_transport.py](../../tests/test_ui_http_transport.py)
- [test_ui_query_gateway.py](../../tests/test_ui_query_gateway.py)
- [useMainPageController.sessionLifecycle.test.tsx](../../frontend/src/pages/main-page/useMainPageController.sessionLifecycle.test.tsx)
- [httpMainPageAdapter.test.ts](../../frontend/src/pages/main-page/httpMainPageAdapter.test.ts)
- [platoApi.test.ts](../../frontend/src/shared/api/platoApi.test.ts)

---

## 17. 最终事实摘要

当前 Session 的最准确表达是：

~~~text
Session
  = workspace registry metadata
  + workspace-local fact namespace
  + product-visible continuous collaboration boundary
  + per-session execution event/context/log metadata

Session
  != independent workspace root
  != independent sidecar runtime
  != AgentPool owner
  != unified state machine
  != tenant/security boundary
  != transparent process checkpoint
~~~

当前系统通过 `(workspaceId, sessionId)` 路由、workspace-level row filtering
和 per-Session metadata files 实现事实隔离；通过共享 workspace root 执行文件工作；
通过 Main Page snapshot、Conversation、Activity 和 Audit 构建用户可见连续性。任何
更强的 isolation、ownership 或 recovery 声明都需要新的实现证据。
