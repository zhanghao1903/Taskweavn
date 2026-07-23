# Session 架构设计

> 多 Agent 协作架构的核心抽象 · v1.4 · 2026-07-02
>
> 2026-05-17 review note: 本文中的 `Workspace` 曾指 **Session Workspace / 执行工作区**，不是产品 UI 中用户长期管理的 `Project`。
>
> 2026-05-31 scope note: Product 1.0 line-first execution 使用 fixed-route Default Agent bridge。基于完整 AgentPool / Agent Manager 的 dynamic assignment 仍是 Product 1.1+ 方向。
>
> 2026-06-19 fact note: 当前实现采用 workspace-root-as-agent-cwd。一个 workspace root 可拥有多个 Session；Session 的元数据隔离在 `.plato/sessions/<session_id>/`，但 Agent 看到的项目文件根目录是 workspace root。Session 是会话、投影、执行状态和审计的隔离边界，不再等同于独占文件工作区。
>
> 2026-06-24 Product 1.1 alignment: Session 现在也是 durable Conversation / Activity、Router decision/outcome、read-only inquiry result、workspace inspection evidence links、token usage projection、Audit/diagnostics linkage、Plan archive / archived Plan projection 的归属边界。Workspace root 仍共享项目文件；Session 隔离的是运行事实、会话投影和审计证据。

---

## 1. 定义

**Session 是 workspace 内的一次连续交互上下文，是 UI、执行状态、投影和审计的主要隔离边界。**

一个 Session 对应一个用户从开启到关闭会话的整个时间段，包含：
- Session conversation / MessageStream rows
- active Plan / Direct Task / TaskNode 投影
- PublishedTask lifecycle facts（按 `session_id` 隔离）
- 默认执行 Agent 运行边界；Product 1.1+ 可扩展为 AgentPool / Agent Manager
- execution ASK、confirmation、runtime input、result、file summary、Audit projection
- session-private EventStream、ContextStore、ThoughtStore 和日志目录
- 对 workspace root 的受控文件读写

```
Session ≡ workspace 内的连续协作上下文 + session-scoped runtime facts
```

---

## 2. 核心抽象

### 2.1 Session 是资源边界

Session 是 TaskWeavn runtime facts 的主要边界。任何 Task、Agent run、
Message、ASK、Context snapshot、Audit event 都必须带有 `session_id`。

文件读写发生在 workspace root 内。当前实现不为每个 Session fork 一份用户
项目文件；它通过 session-scoped metadata、TaskBus 串行执行、protected
metadata 目录和未来显式 merge/export 策略控制复杂度。

```
┌─ Session A ────────────────┐    ┌─ Session B ────────────────┐
│  metadata .plato/A         │    │  metadata .plato/B         │
│  Task facts: session=A     │    │  Task facts: session=B     │
│  messages: session=A       │    │  messages: session=B       │
│  Agent run boundary A      │    │  Agent run boundary B      │
└────────────────────────────┘    └────────────────────────────┘
        │                                  │
        └──────── shared workspace root ───┘
```

不同 Session 的 Task、Message、ASK、Event、Context 和日志事实按
`session_id` 隔离。它们默认共享同一个 workspace root 的用户文件，因此
跨 Session 的文件层冲突不是通过文件系统 fork 解决，而应通过显式产品流程或
后续 workspace isolation 能力处理。

### 2.2 Session 拥有唯一 Project Root 视图

当前实现中，一个 Session 的 Agent project root 是所属 workspace root。
Session-private metadata 在 `.plato/sessions/<session_id>/` 下，workspace-level
stores 在 `.plato/*.sqlite`，并通过 `session_id` 做行级隔离。

```
workspace root/
  .plato/
    workspace.sqlite
    messages.sqlite
    tasks.sqlite
    authoring.sqlite
    asks.sqlite
    ui_events.sqlite
    results.sqlite
    sessions/<session_id>/
      events.sqlite
      context.sqlite
      thoughts.sqlite
      logs/
  ... user project files ...
```

这意味着 Session 是 runtime isolation boundary，不是文件系统 fork boundary。
Product 1.0 仍保持每个 Session 一个 active writer execution lane；跨 Session
并发写入和 merge 语义不是默认能力。

### 2.3 Session 是 Active Work 和历史工作的容器

一个 Session 可以连续承载多个工作段：

```
Session
  │
  ├── Plan / Direct Task (用户请求 1)
  │     ├── TaskNode / PublishedTask
  │     └── TaskNode / PublishedTask
  │
  └── Plan / Direct Task (用户请求 2，同一 Session 内的后续请求)
        └── TaskNode / PublishedTask
```

Product 1.1 Main Page 当前投影一个 active Plan / TaskTree，并通过 Session
snapshot / Activity projection 暴露 archived Plans。PlanStore 支持按 Session
列出多个 Plan 并区分 active non-archived Plan；Plan archive 已有 command /
HTTP route，归档后 Plan 从 active work 移入 Session history，Conversation
和 Activity 保留 `Plan archived` 边界。Execution side 仍通过 PublishedTask +
TaskBus 表达实际可执行工作。

---

## 3. 核心属性

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `id` | `SessionId` | 全局唯一 |
| `workspace_root` | `Path` | Agent project root；多个 Session 可共享 |
| `session_meta_dir` | `Path` | `.plato/sessions/<session_id>/` |
| `task_bus` | `TaskBus` | PublishedTask 生命周期权威，使用 workspace-level task store + `session_id` 隔离 |
| `message_stream` | `MessageStream` | workspace-level message store，按 `session_id` 过滤 |
| `plan_store` | `PlanStore` | workspace-level authoring/Plan store，按 `session_id` 过滤 |
| `ask_store` | `AskStore` | workspace-level execution ASK store，按 `session_id` 过滤 |
| `ui_event_store` | `UiEventStore` | workspace-level UI event replay store，按 `session_id` 过滤 |
| `event_stream` | `EventStream` | session-private execution/audit event store |
| `context_store` | `ContextStore` | session-private context snapshots/traces |
| `thought_store` | `ThoughtStore` | session-private thoughts store；长期记忆共享策略是后续扩展 |
| `default_agent_boundary` | `ResidentDefaultAgent` | Product 1.0 fixed-route execution boundary |
| `created_at` | `datetime` | 会话开始时间 |
| `closed_at` | `datetime \| None` | 会话结束时间 |
| `status` | `SessionStatus` | `active` / `closed` / `abandoned` |
| `user_id` | `UserId` | 所属用户 |
| `config` | `SessionConfig` | 自主度、约束 profile 等用户配置 |

---

## 4. 设计理念

### 4.1 Session 是 runtime context，不只是"对话"

Session 不只是聊天记录的容器，更是 runtime facts 的容器。它和操作系统
进程的类比只适用于生命周期和资源归属，不适用于文件系统隔离：

```
进程 (Process)              Session
─────────────────────────────────────
独立内存空间                独立 session metadata / context facts
进程内多线程                 Session 内 serialized Agent runs
进程间通信需要显式机制       Session 间事实引用需要显式产品/API 流程
进程结束清理资源             Session 结束清理 Agent runtime 和缓存
文件系统隔离                当前不成立：多个 Session 共享 workspace root
```

这种映射意味着 Session 是**有状态**的，不应被当作临时 chat turn。一个
workspace 可以有多个 Session，但 Product 1.0 默认仍以一个 active work lane
为主要体验。

### 4.2 Workspace Root 共享是简洁性的支点

这条约束的取舍：

```
代价：不同 Session 不天然拥有文件 fork 隔离
收获：
  - 没有 fork / merge / conflict 解决
  - 没有跨 Workspace 同步开销
  - 用户项目文件只有一个真实根目录
  - Task 之间的依赖在数据层面变得清晰（同一份文件）
```

写入并发的复杂性通过 TaskBus 串行执行和后续显式 workspace isolation
能力处理，而不是通过默认为每个 Session fork workspace 处理。

### 4.3 Session 配置是用户控制的边界

用户对 Agent 协作的控制（自主度、约束 profile、preset 选择）都附着在 Session 上，不是 Agent 上：

```python
@dataclass
class SessionConfig:
    autonomy_behavior: AutonomyBehavior      # 整个 Session 的默认自主度
    constraint_profile: ConstraintProfile    # 编排约束
    preset: OrchestrationPreset | None       # 选用的最佳实践
    interrupt_allowed: bool                  # 是否允许 Agent 打断用户
```

Agent 是无状态的，每次实例化时**继承 Session 的配置**。这让"调整自主度"在用户感知里是一致的——一次设置影响整个会话。

### 4.4 Session 是 EventStream 的根

EventStream 按 Session 分片：每个 Session 有独立的 event 流。这让事件查询、replay、审计的范围天然清晰。

```
EventStream queries:
  by session_id  → 一次会话的完整历史
  by task_id     → 一个任务的完整事件链
  by agent_run   → 一次 Agent 实例执行的事件
```

---

## 5. 生命周期

```
                ┌──────────┐
                │ creating │  Session 资源初始化
                └────┬─────┘
                     ↓
                ┌─────────┐
                │ active  │  正常工作状态
                └────┬────┘
              ┌──────┴──────┐
              ↓             ↓
         ┌────────┐    ┌────────────┐
         │ closed │    │ abandoned  │
         └────────┘    └────────────┘
          正常终止        异常终止/超时
```

### 5.1 创建（creating）

Session 创建时初始化所有资源：

```
1. 分配 SessionId
2. bootstrap workspace root 与 .plato metadata skeleton
3. 创建 .plato/sessions/<session_id>/ session-private metadata 目录
4. 打开 workspace-level stores：messages/tasks/authoring/asks/ui_events/results
5. 打开 session-private stores：events/context/thoughts/logs
6. 初始化默认执行 Agent 运行边界；Product 1.1+ 可初始化 AgentPool / Agent Manager
7. 加载 SessionConfig（默认或用户指定）
```

完成后状态 `active`。

### 5.2 活跃（active）

Session 在 `active` 状态接受用户请求和 Agent 派生的任务：

```
用户请求
  -> Runtime Input Router / Authoring Domain
  -> RawTask / DraftTaskTree / Plan
  -> PublishedTask
  -> TaskBus
  -> FixedRoute Default Agent
  -> Result / Activity / Audit projection

期间：
  - workspace root 可被 Agent 读写
  - workspace-level stores 按 session_id 写入消息、任务、ASK、结果和 UI events
  - session-private EventStream / ContextStore / logs 持续 append
  - Product 1.0 默认 Default Agent boundary 执行；Product 1.1+ 可引入 Agent Manager
```

`active` 期间每个 Session 默认只有一个 writer execution lane。TaskBus 可以有
`waiting_for_user` blocking point；用户 answer 成功后由 TaskBus resume 并由
dispatcher 继续推进。

### 5.3 关闭（closed）

正常关闭由用户显式触发或所有任务完成且无新请求超过阈值：

```
1. 等待当前 running 任务终态
2. 拒绝新任务进入 TaskBus
3. 停止 Default Agent / dispatcher runtime
4. flush session-private EventStream / ContextStore / logs
5. workspace-level stores 已持续写入，关闭时只需确保连接释放
6. workspace root 用户文件默认保留
7. 释放内存资源
```

关闭后不透明恢复原 Agent stack。已持久化的 Session facts 可以继续作为历史
查看、审计、read-only inquiry 或 follow-up work 的输入；新的执行工作应通过
新 command、retry 或新 Session 发起。

### 5.4 异常终止（abandoned）

```
触发条件：
  - 进程崩溃
  - 用户长时间无活动且超过 timeout
  - 系统资源压力导致主动终止

处理：
  - EventStream 保留到崩溃前的最后一个 event
  - workspace root 保留磁盘状态
  - 启动或 snapshot 查询前的 recovery hook 可将 stale interrupted running
    Task 收敛为 failed/cancelled projection
  - answered-but-not-continued ASK 可由 recovery service 补发 resume/dispatch
  - 用户下次访问时可以查看历史；继续执行通常通过 retry / follow-up work，
    不是透明恢复原 Agent stack
```

### 5.5 持久化模型

```
内存层（Session active 时）：
  - Default Agent / dispatcher runtime
  - open store connections
  - in-flight LLM/tool state

workspace-level 磁盘层（持续写入）：
  - .plato/workspace.sqlite
  - .plato/messages.sqlite
  - .plato/tasks.sqlite
  - .plato/authoring.sqlite
  - .plato/asks.sqlite
  - .plato/ui_events.sqlite
  - .plato/results.sqlite
  - workspace root 用户文件

session-private 磁盘层：
  - .plato/sessions/<session_id>/events.sqlite
  - .plato/sessions/<session_id>/context.sqlite
  - .plato/sessions/<session_id>/thoughts.sqlite
  - .plato/sessions/<session_id>/logs/
```

---

## 6. 与其他组件的关系

```
                      User
                       │
                       ↓ creates
                    Session  ─────┐
                      │          │ owns
                      │ contains ↓
                       │       session metadata
                       │       workspace-scoped stores filtered by session_id
                       │       Default Agent boundary
                       │       AgentPool / Agent Manager (Product 1.1+)
                       │       ContextStore / ThoughtStore
                       │       EventStream
                       │
                       │ active work
                       ↓
                    Plan / TaskNode ──→ PublishedTask ──→ TaskBus
```

- **与 User：** 一个用户可同时拥有多个 Session（多个会话窗口），但每个 Session 只属于一个用户
- **与 Workspace：** workspace root 是 Agent project root；Session metadata 和 store rows 按 `session_id` 隔离
- **与 Task：** Session 是 PublishedTask、Plan、TaskNode projection 的命名空间
- **与 Agent：** 当前 Product 1.1 使用 Session 内 Default Agent execution boundary；later dynamic assignment 中，Agent 实例的创建和销毁都在 Session 内
- **与 Bus：** TaskBus 操作按 `session_id` 隔离；当前 SQLite task store 是 workspace-level row-isolated store
- **与 Context Manager：** SessionContextManager 是 execution LLM input 的治理边界
- **与 ThoughtStore：** 当前 session-private thoughts store 是恢复/调试事实源；跨 Session 长期记忆仍是后续扩展

---

## 7. 未来发展点

### 7.1 v1.x：会话恢复

**断点续传**

Session 异常终止后，下次访问时可以查看历史，并通过 recovery hooks 收敛
stale stopping / answered ASK 等已知不一致状态。透明恢复原 Agent stack 不是
Product 1.0 事实；继续执行通过 retry 或 follow-up work：

```python
session = Session.resume(session_id)
# 加载所有持久化状态
# stale interrupted running 任务可被标记为 failed/cancelled projection
# answered ASK 可补发 resume/dispatch
# 用户可以选择 retry 或创建 follow-up work
```

### 7.2 v2.x：Sub-session

**真正的并行执行**

通过 sub-session 引入隔离的并行能力：

```python
parent_session.create_sub_session(
    workspace_fork="copy",  # fork 工作区
    config=...,
)
# Sub-session 拥有独立 Workspace
# 完成后可选 merge 回 parent 工作区
# 实质是把"约束 1（单工作区）"变成"按 session 边界单工作区"
```

这等价于把"单工作区"约束**作用域细化**到 sub-session 而非整个用户会话。

### 7.3 v2.x：Session 模板

**预设的工作环境**

用户可以保存当前 Session 的配置（自主度、约束、Agent 选择、初始 Workspace）为模板，下次创建 Session 时直接复用：

```
Session Template "代码审计模式":
  - 自主度: 风险确认
  - 约束 profile: audit-focus
  - 预装 Agent: AuditAgent, FixerAgent
  - 初始 Workspace: 当前 git 仓库
```

### 7.4 v3.x：跨用户协作

**多用户共享 Session**

```python
session.invite(user_id=other_user, role="reviewer")
# 多用户可以同时观察 Session
# 任务发布权可以按 role 控制
# Workspace 写权限严格管理
```

这是最远期的扩展，会引入新的权限和并发模型，可能需要重新评估"单工作区串行"约束。

### 7.5 v3.x：Session 间任务引用

**跨会话产物复用**

```python
new_session.import_artifact(from_session=old_id, task_id=...)
# 引用历史会话的任务结果
# 不复制 Workspace 或 ThoughtStore
# 仅作为 read-only artifact
```

让用户的多次会话之间形成轻量的数据连接，而不需要把所有内容堆在一个 Session 里。

---

## 8. 设计决策小结

| 决策 | 选择 | 替代方案 | 选择理由 |
|------|------|---------|---------|
| 用户文件工作区 | workspace root 共享 | 每 Session 自动 fork | 简洁性 + 用户文件只有一个真实根目录；隔离通过 session metadata 和后续显式 workspace isolation 处理 |
| 配置归属 | Session 级 | Agent 级 | 用户感知一致，一次设置贯穿会话 |
| EventStream 边界 | 按 Session 分片 | 全局共享 | 查询和审计的范围天然清晰 |
| Agent 实例归属 | Session 内 | 全局池 | 资源边界清晰，故障域小 |
| 持久化粒度 | workspace-level stores + session-private stores 持续写入 | 关闭时统一持久化 | 崩溃时丢失最少，snapshot 可恢复 |
| 跨 Session 通信 | runtime facts 默认隔离，workspace files 默认共享 | 完全隔离或完全共享 | 符合当前 workspace-root-as-agent-cwd 实现，同时保留后续显式引用/merge 能力 |
| 关闭策略 | 显式或超时 | 自动按空闲清理 | 用户对会话边界有控制感 |
