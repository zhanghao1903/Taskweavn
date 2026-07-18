# session.md 事实校准记录

> 校准对象：`docs/architecture/session.md`
>
> 原文保留：`docs/architecture/session.original.md`
>
> 校准日期：2026-07-10
>
> 校准性质：文档事实修复；未修改生产代码

---

## 1. 原文保全

原文在任何改写前从 `HEAD` 工作树版本复制，保留信息如下：

| 项目 | 值 |
|---|---|
| 原文行数 | 442 |
| 原文 SHA-256 | `755b88258a338d16c7edb79198b3d9bdc75f5e9aaed56e628e5503e0ee3a45df` |
| HEAD commit | `1577d8c9900704085990106217077e42e77daeaf` |
| HEAD blob | `9a5808822cde35931603085d400f87dfe0f41002` |
| HEAD subject | `docs: align plan archive architecture docs` |
| HEAD date | `2026-07-02T00:30:47+08:00` |

保全要求：

1. `session.original.md` 必须与改写前 `session.md` byte-for-byte
   一致；
2. 必须与 `HEAD:docs/architecture/session.md` 的 SHA-256 一致；
3. 后续只改当前文档和本 fix log，不回写 original。

---

## 2. 校准方法

本次没有按旧文档的叙事推导实现，而是分别核验：

1. core Session 数据模型；
2. Session registry schema 与 CRUD；
3. WorkspaceLayout 的实际 path math；
4. workspace-level 与 per-Session store schema；
5. Main Page workspace runtime 组合；
6. fixed-route dispatcher 与 AgentLoop 构造；
7. Main Page snapshot、status、Activity projection；
8. Session lifecycle HTTP route；
9. frontend active workspace/Session identity；
10. multi-workspace routing；
11. startup/snapshot recovery；
12. 对应 unit、contract 和 frontend tests；
13. product/engineering/ADR 文档中的实现状态标记。

事实优先级：

~~~text
current source + executable tests
  > implemented contract sections
  > product semantic baseline
  > accepted but not implemented ADR
  > old architecture examples/future sketches
~~~

---

## 3. 主要代码证据

### 3.1 Core 与 layout

- `src/taskweavn/core/session.py`
- `src/taskweavn/core/session_manager.py`
- `src/taskweavn/core/session_status.py`
- `src/taskweavn/core/workspace_layout.py`
- `src/taskweavn/core/sqlite_event_stream.py`

确认：

- Session 只有六个 dataclass fields；
- id 是 8 hex；
- stored status 是 `active/awaiting_user/finished/archived`；
- SessionManager CRUD 的准确范围；
- delete 仅删 registry row 并移动 private dir；
- project dir 返回 workspace root；
- events/context/thoughts/plan/log path 的准确位置；
- legacy `.taskweavn` 和 `.code-agent/logs` migration。

### 3.2 Store 与 domain

- `src/taskweavn/interaction/sqlite_message_stream.py`
- `src/taskweavn/interaction/sqlite_ask_store.py`
- `src/taskweavn/task/sqlite_bus.py`
- `src/taskweavn/task/sqlite_authoring.py`
- `src/taskweavn/task/sqlite_plan_store.py`
- `src/taskweavn/task/sqlite_result_summary.py`
- `src/taskweavn/context/sqlite_store.py`
- `src/taskweavn/memory/sqlite_thought_store.py`

确认：

- messages/tasks/authoring/asks/results 是 workspace DB，不是 Session-owned DB；
- 每个 store 的 Session query/key 事实不同，不能一律写成复合主键；
- events DB 的 Session scope 由路径隐含；
- context DB 同时有 per-Session path 和 row `session_id`；
- current Plan 权威在 `authoring.sqlite`；
- Main Page 没有 wire `SqliteThoughtStore`。

### 3.3 Runtime、projection 与 recovery

- `src/taskweavn/server/main_page.py`
- `src/taskweavn/server/main_page_agent.py`
- `src/taskweavn/server/main_page_sessions.py`
- `src/taskweavn/server/multi_workspace.py`
- `src/taskweavn/server/ui_contract/query_snapshot_helpers.py`
- `src/taskweavn/server/ui_contract/session_activity_projection.py`
- `src/taskweavn/server/runtime_input_activity.py`
- `src/taskweavn/server/ask_recovery.py`
- `src/taskweavn/server/task_stop_recovery.py`
- `src/taskweavn/server/ui_http.py`
- `src/taskweavn/server/ui_http_routes.py`
- `src/taskweavn/task/execution.py`

确认：

- runtime owner 是 workspace；
- 应用可无 configured Session 启动；
- Default Agent adapter/dispatcher 被 workspace 中多个 Sessions 复用；
- 每 Task 创建新的 AgentLoop；
- dispatcher 的 single worker/coalescing 边界；
- snapshot 使用独立 UI status derivation；
- Activity 是 query-time projection；
- lifecycle delete route 实际使用 `POST .../delete`；
- startup recovery 与 snapshot recovery 的精确范围。

### 3.4 Frontend

- `frontend/src/pages/main-page/httpMainPageAdapter.ts`
- `frontend/src/pages/main-page/useMainPageController.ts`
- `frontend/src/pages/main-page/useMainPageSessionIdentityState.ts`
- `frontend/src/pages/main-page/useMainPageSessionLifecycle.ts`
- `frontend/src/pages/main-page/useMainPageSnapshotQuery.ts`
- `frontend/src/pages/main-page/MainPageSessionSidebar.tsx`
- `frontend/src/shared/api/platoApi.ts`
- `frontend/src/shared/api/types.ts`

确认：

- active workspace 和 active Session 是两个 state fields；
- query key/identity 使用两个维度；
- 无 preferred id 时从 Session list 选择最近一条；
- create/rename/delete 后的 selection/refetch；
- workspace-scoped 与 compatibility API path；
- frontend SessionStatus type 与 lifecycle/catalog 实际 payload 存在 drift。

---

## 4. 相关文档证据

### 4.1 已校准 architecture 文档

- `docs/architecture/overview.md`
- `docs/architecture/reference.md`
- `docs/architecture/task.md`
- `docs/architecture/bus.md`
- `docs/architecture/context-manager.md`
- `docs/architecture/interaction-layer.md`
- `docs/architecture/ui-backend-communication.md`
- `docs/architecture/workspace-communication-protocol.md`

这些文档用于交叉检查共享 workspace root、TaskBus row scope、status vocabulary、
Context Manager 和 HTTP routing；最终仍以源码/测试为准。

### 4.2 Product/engineering/ADR

- `docs/product/plato-session-content-model.md`
- `docs/product/plato-session-active-work-lifecycle.md`
- `docs/product/workflow-session-task-ux-model.md`
- `docs/engineering/multi-workspace-api-runtime-contract.md`
- `docs/decisions/ADR-0017-session-and-workspace-context-management-foundation.md`

判定：

- Session content、Conversation continuity 和 active Plan history 是当前产品语义；
- isolated Session Workspace 在 product direction 中存在，但与当前 path math 冲突；
- ADR-0017 明确标为 `not implemented`；
- multi-workspace contract 的 foundation 已部分实现，但 DELETE verb、runtime modes、
  eviction 和 concurrency policy 不能整体视为当前代码。

---

## 5. 逐项纠正

| 原陈述或隐含结论 | 证据 | 判定 | 新文档处理 |
|---|---|---|---|
| Session 是拥有全部 runtime resources 的聚合对象 | Session dataclass 只有六字段；runtime 持有 stores/dispatcher | 错误 | 分开产品归属、代码 owner 和物理 store |
| Session id 全局唯一 | 8 hex；workspace-local PK；multi-workspace 允许同名 id | 错误 | public identity 改为 `(workspaceId, sessionId)` |
| 任何 Task/Message/ASK/Event/Context/Audit 都必须携带 `session_id` | per-Session events row 无该列；部分 workspace facts 非 Session scope | 过度绝对 | 按 store 列出显式/隐式 scope |
| Session 拥有唯一 project root | `session_project_dir` 忽略 id 返回 workspace root | 容易误导 | 明确多个 Session 共享同一 root |
| 每 Session 自动 fork workspace | 无 copy/worktree/fork/merge code | 错误 | 标为未实现方向 |
| Session owns TaskBus | `MainPageWorkspaceRuntime.task_bus` workspace 级 | 错误 | Task rows 按 Session 过滤 |
| Session owns MessageStream | 一个 workspace messages DB | 错误 | Conversation 归属与 store ownership 分开 |
| Session owns PlanStore | PlanStore 由 workspace runtime 组合 | 错误 | Plan key 包含 Session，但 store workspace 级 |
| Session owns Default Agent | 一个 workspace runtime 一个 adapter | 错误 | 每 Task 用 Session id 创建 runner |
| 当前有 AgentPool/Agent Manager | fixed-route executor 代码明确否定 | 错误 | 移入非现状表 |
| Agent instance 生命周期等于 Session | 每 Task fresh AgentLoop；无 resident stack | 错误 | 说明 adapter resident、loop per Task |
| Agent 继承 SessionConfig | 无 SessionConfig 模型或装配 | 错误 | 删除示例 dataclass |
| autonomy/constraint/preset 属于 Session | 无字段、store、API | 未实现 | 不再陈述为现状 |
| lifecycle 是 creating/active/closed/abandoned | core 与 UI 各用另一套状态 | 错误 | 单独列出三套 status 边界 |
| auto timeout 关闭 | 无 scheduler/timeout transition | 错误 | 明确不存在 |
| closed 会等待 Task、拒绝新任务、flush resources | 无 per-Session close path | 错误 | 改写为实际 delete 与 runtime close |
| delete 是完整关闭/清理 | 只删 registry row 并移动 private dir | 错误 | 记录无 cascade/quiesce |
| user_id 是 Session 属性 | dataclass/schema 无该字段 | 错误 | 明确无 user/tenant/RBAC |
| EventStream 可按 Session/task/agent_run 统一查询 | Session 由文件隐含；只有 optional task_id；无 agent_run column | 错误 | 区分 EventStream 与 Context agent_run |
| thoughts.sqlite 是 Main Page 当前事实源 | Main Page AgentLoop 未传 thought store | 错误 | 标为 path helper/optional |
| plan.md 是 active Plan 持久化 | 只有 path helper 和测试；PlanStore 在 authoring DB | 错误 | 明确不是权威 |
| 每 Session 一个 writer execution runtime | dispatcher 是 workspace runtime 资源 | 不准确 | 描述 one worker + per-Session coalescing |
| TaskBus 本身保证单 Session 只有一个 running Task | claim 规则无该全局锁 | 错误 | 串行性限定为 dispatcher product path |
| 多 workspace 只会执行一个 active workspace | 每 lazy runtime 有独立 dispatcher | 无证据 | 明确无 global concurrency coordinator |
| Session Activity 是独立持久化流 | projection service 动态合并 facts | 错误 | Activity 定义为 query-time read model |
| 所有“Session status”同一枚举 | core stored/core helper/Main Page UI 不同 | 错误 | 三层分别记录 |
| lifecycle list 返回 UI-derived status | 直接序列化 stored status | 错误 | 记录 contract drift |
| Session.last_active_at 反映所有工作 | 生产不调用 touch；rename/create 更新 | 错误 | 明确 recency 边界 |
| transparent resume 原 Agent stack | 无 `Session.resume`；fresh AgentLoop | 错误 | 改为 bounded fact recovery |
| startup 恢复所有 running Task | 只恢复 running + interrupt_requested | 过度 | 写精确 predicate |
| snapshot recovery 恢复整个 Session | 只处理 ASK continuation 和 stale stop | 过度 | 写精确服务与 best-effort 语义 |
| sub-session 已规划为版本事实 | 无 model/API/tests | 未实现 | 不保留版本承诺 |
| Session template 已规划为版本事实 | 无 model/API/tests | 未实现 | 不保留版本承诺 |
| multi-user invite/RBAC 已规划为版本事实 | 无 user/role/invite implementation | 未实现 | 只列非现状 |
| 跨 Session artifact import 有既定 API | 无 `import_artifact` | 未实现 | 只列非现状 |
| multi-workspace contract 使用 DELETE | 实际 route 为 `POST .../delete` | 文档漂移 | 记录当前 verb 与差异 |

---

## 6. 保留并精化的事实

旧稿并非全部错误，以下事实被保留但收窄：

1. Session 是连续协作和用户可见 history 的产品边界；
2. Message、Task、ASK、Plan、result、UI event 等多数事实有 Session scope；
3. workspace root 是当前 Agent cwd；
4. Session event/context/log metadata 位于 `.plato/sessions/<id>/`；
5. TaskBus 可进入 `waiting_for_user`，answer/confirmation 后回到
   `pending` 并继续 dispatch；
6. fixed-route product path 给出串行 drain；
7. PlanStore 支持同 Session 多个 Plans 和 archive；
8. Conversation 在 Plan archive 后保留；
9. startup/snapshot 有 bounded recovery；
10. workspace-level store 持续落盘，Session 不是关闭时才统一持久化。

精化原则：

- 不把 product ownership 写成 object ownership；
- 不把 row isolation 写成 filesystem isolation；
- 不把 dispatcher behavior 写成 TaskBus invariant；
- 不把 accepted direction 写成 shipped implementation；
- 不把 recovery 写成 process checkpoint。

---

## 7. 新增的重要事实

本次不是只删除旧内容，还补充了旧文档缺失的现状：

1. public identity 是 workspace + Session；
2. catalog 允许 duplicate Session ids across workspaces；
3. workspace runtime 可在无 configured Session 时启动；
4. `MainPageWorkspaceRuntime.session` 不是 frontend active selection 权威；
5. stores/default agent/dispatcher 均按 workspace runtime 组合；
6. one dispatcher worker 在一个 workspace 内依次 drain Sessions；
7. multiple lazy workspace runtimes 没有 global execution coordinator；
8. AgentLoop per Task 重建；
9. EventStream row 不保存 Session id；
10. Main Page 不 wire persistent ThoughtStore；
11. `plan.md` 不是 PlanStore 权威；
12. Activity 不是独立 store；
13. core status helper 生产未使用；
14. non-active Session snapshot entries 被统一投影为 `new`；
15. lifecycle/catalog status 与 frontend UI type 不一致；
16. Session registry 不会因普通 work 自动 touch；
17. delete 不 cascade workspace-level facts；
18. recovery 只覆盖 explicit predicates；
19. current API delete 使用 POST action route；
20. layered SessionContext 仍未实现。

---

## 8. 交叉文档冲突

### 8.1 Isolated Session Workspace

`docs/product/workflow-session-task-ux-model.md` 把 Session Workspace 写成
独立 execution boundary，并明确反对多个 Session 共享 root。

当前代码事实相反：

~~~python
def session_project_dir(self, session_id: str) -> Path:
    del session_id
    return self.root
~~~

处理：当前 architecture 写共享 root；product 文档只作为方向引用，不改写其目标。

### 8.2 Layered SessionContext

ADR-0017 的状态是 `accepted foundation / not implemented`，并明确 current
`SessionContextManager` 主要仍是 Task execution context。

处理：不把 WorkspaceContext/SessionContext snapshot、promotion 和 cross-session
memory 写成现状。

### 8.3 Multi-workspace contract

contract 中：

- Session endpoint 示例使用 DELETE；
- 建议 catalog/active/execution runtime modes；
- 建议不为每个 registered workspace 启动 dispatcher；
- 定义 future idle close/concurrency 问题。

当前实现：

- lifecycle delete 是 POST action；
- catalog path 确实不构造完整 runtime；
- 首个 routed request lazy 构造完整 runtime，包含 dispatcher/default agent；
- 无 idle eviction；
- 无 global cross-workspace execution policy。

处理：逐项记录 implemented foundation，不把整个 contract 作为当前代码。

---

## 9. 验证计划

### 9.1 Backend targeted tests

计划运行：

~~~text
uv run pytest -q \
  tests/test_workspace_layout.py \
  tests/test_session_manager.py \
  tests/test_session_status.py \
  tests/test_sqlite_event_stream.py \
  tests/test_sqlite_message_stream.py \
  tests/test_session_activity_projection.py \
  tests/test_plan_store.py \
  tests/test_fixed_route_task_executor.py \
  tests/test_ask_recovery.py \
  tests/test_task_stop_recovery.py \
  tests/test_multi_workspace_sidecar.py \
  tests/test_ui_http_transport.py \
  tests/test_ui_query_gateway.py \
  tests/test_main_page_sidecar_app.py
~~~

结果：

~~~text
254 passed in 20.86s
~~~

状态：通过。

### 9.2 Frontend targeted tests

计划运行：

~~~text
npm test -- \
  src/pages/main-page/httpMainPageAdapter.test.ts \
  src/pages/main-page/useMainPageController.sessionLifecycle.test.tsx \
  src/pages/main-page/MainPageWorkspaceSwitcher.test.tsx \
  src/shared/api/platoApi.test.ts
~~~

结果：

~~~text
Test Files  4 passed (4)
Tests      33 passed (33)
Duration   1.56s
~~~

状态：通过。

### 9.3 文档检查

计划验证：

- original SHA 与 HEAD 一致；
- current 与 original 存在实质差异；
- Markdown local links 可解析；
- git diff 只包含预期 Session artifacts 及既有工作；
- 文档内没有把示例 future API 写成 implemented。

结果：

- `session.original.md` SHA-256 与
  `HEAD:docs/architecture/session.md` 一致；
- current SHA-256 为
  `bc2559b87daf1f9095b380762ea6c3d4ce0762ed87a2e7e53defd9a177c4e4b8`，
  与 original 不同；
- `git diff --check` 通过；
- local Markdown links 全部可解析；
- Session artifact 配对与 git scope 检查通过；

状态：通过。

---

## 10. 变更文件

| 文件 | 处理 |
|---|---|
| `docs/architecture/session.original.md` | 原文 byte-for-byte 保留 |
| `docs/architecture/session.md` | 按当前源码/测试完全改写 |
| `docs/architecture/fix-log/session.md` | 新增本事实、纠正和验证记录 |

未修改：

- core/runtime/frontend source；
- schemas/migrations；
- tests/fixtures；
- product/engineering/ADR docs。

---

## 11. 校准结论

旧稿的主要问题不是一个字段过期，而是把四个层次混成“Session owns everything”：

~~~text
product continuity
runtime composition
storage scoping
filesystem isolation
~~~

当前事实应拆为：

~~~text
product continuity -> Session
runtime composition -> WorkspaceRuntime
workspace DB facts  -> session_id-filtered rows
execution events    -> per-Session DB path
project files       -> shared workspace root
public identity     -> workspaceId + sessionId
~~~

同时，旧稿中的 `SessionConfig`、`closed/abandoned`、
AgentPool、sub-session、template、invite、artifact import 和 transparent resume 都没有
当前实现证据，已从现状叙事中移除。
