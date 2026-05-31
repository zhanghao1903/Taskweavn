# Session 架构设计

> 多 Agent 协作架构的核心抽象 · v1.1 · 2026-05-31
>
> 2026-05-17 review note: 本文中的 `Workspace` 指 **Session Workspace / 执行工作区**，不是产品 UI 中用户长期管理的 `Project`。当前产品层级是 `Project -> Workflow -> Session -> Session Workspace`；Session Workspace 仍然是文件读写和权限隔离边界。
>
> 2026-05-31 scope note: Product 1.0 line-first execution 使用一个 active Session workspace 和 fixed-route Default Agent bridge。基于完整 AgentPool / Agent Manager 的 dynamic assignment 仍是 Product 1.1+ 方向。

---

## 1. 定义

**Session 是用户的一次完整交互上下文，是系统资源的最大组织单位。**

一个 Session 对应一个用户从开启到关闭会话的整个时间段，包含：
- 唯一的工作区（Workspace）
- 任务总线（TaskBus）的实例
- 默认执行 Agent 运行边界；Product 1.1+ 可扩展为 AgentPool / Agent Manager
- 长期记忆（ThoughtStore）的访问入口
- 整棵任务树的根节点

```
Session ≡ 一个隔离的工作环境 + 该环境内所有任务的容器
```

---

## 2. 核心抽象

### 2.1 Session 是资源边界

Session 是所有资源的**唯一入口和出口**。任何 Task、Agent、文件读写都发生在某个 Session 内，跨 Session 通信被严格约束。

```
┌─ Session A ────────────────┐    ┌─ Session B ────────────────┐
│  Workspace A               │    │  Workspace B               │
│  TaskBus A                 │    │  TaskBus B                 │
│  Tasks: [...]              │    │  Tasks: [...]              │
│  Agent instances: [...]    │    │  Agent instances: [...]    │
└────────────────────────────┘    └────────────────────────────┘
        ↑                                  ↑
        └── User 1                         └── User 2 (or User 1 again)
```

不同 Session **完全隔离**，Session A 的 Agent 看不到 Session B 的 Workspace 或 Task。

### 2.2 Session 拥有唯一 Workspace

这是本架构最强的约束之一：**一个 Session 只有一个工作区，所有 Task 共享。**

```
旧模型：Session > Task > Agent 三层 Workspace（fork/merge）
本架构：Session 单一 Workspace
        Task 串行访问，无 fork
```

并发写冲突被"任务串行执行"约束消解。这是简洁性的核心来源。

### 2.3 Session 是任务树的容器

每个 Session 至少有一个**根任务**（Root Task），由用户的初始请求产生。所有其他任务都是这棵树的后代。

```
Session
  │
  ├── Root Task (用户请求 1)
  │     ├── Subtask
  │     └── Subtask
  │
  └── Root Task (用户请求 2，同一 Session 内的后续请求)
        └── Subtask
```

同一 Session 内可以有**多棵任务树**（用户多次发起请求），但它们共享 Workspace，因此天然按时间串行。

---

## 3. 核心属性

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `id` | `SessionId` | 全局唯一 |
| `workspace` | `Workspace` | 唯一的工作区 |
| `bus` | `TaskBus` | 任务总线实例 |
| `agent_pool` | `AgentPool` | Agent 实例化的工厂 + 注册表 |
| `thought_store` | `ThoughtStore` | 长期记忆访问入口 |
| `event_stream` | `EventStream` | 事件日志，append-only |
| `root_tasks` | `list[TaskId]` | 该 Session 下所有根任务 |
| `created_at` | `datetime` | 会话开始时间 |
| `closed_at` | `datetime \| None` | 会话结束时间 |
| `status` | `SessionStatus` | `active` / `closed` / `abandoned` |
| `user_id` | `UserId` | 所属用户 |
| `config` | `SessionConfig` | 自主度、约束 profile 等用户配置 |

---

## 4. 设计理念

### 4.1 Session 是"进程"，不是"对话"

Session 不只是聊天记录的容器，更是**资源容器**。它对应操作系统的进程：

```
进程 (Process)              Session
─────────────────────────────────────
独立内存空间                独立工作区
进程内多线程                 Session 内多 Agent 实例
进程间通信需要显式机制       Session 间通信被约束（未来 sub-session）
进程结束清理资源             Session 结束清理 Agent 实例和缓存
```

这种映射意味着 Session 是**重量级**的，不应频繁创建。一个用户在一段时间内只应有少数活跃 Session。

### 4.2 单工作区是简洁性的支点

这条约束的取舍：

```
代价：失去 Task 间的并行写能力
收获：
  - 没有 fork / merge / conflict 解决
  - 没有跨 Workspace 同步开销
  - 没有"哪个 Workspace 是真相"的歧义
  - Task 之间的依赖在数据层面变得清晰（同一份文件）
```

并行的需求在 LLM 任务里通常是伪需求——LLM 调用本身是百毫秒~秒级，远超工作区 IO 时间。

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
2. 创建 Workspace（默认是临时目录或用户指定的项目根）
3. 实例化 TaskBus（空队列）
4. 初始化默认执行 Agent 运行边界；Product 1.1+ 可初始化 AgentPool（注册可用的 Agent 模板）
5. 连接 ThoughtStore（按 user_id 加载长期记忆）
6. 创建 EventStream（按 session_id 创建独立流）
7. 加载 SessionConfig（默认或用户指定）
```

完成后状态 `active`。

### 5.2 活跃（active）

Session 在 `active` 状态接受用户请求和 Agent 派生的任务：

```
用户请求 → 创建 Root Task → 进入 TaskBus → Agent 执行 → 综合 → 返回用户

期间：
  - Workspace 被持续读写
  - EventStream 持续 append
  - ThoughtStore 在任务完成时按需写入
  - AgentPool 按需创建 Agent 实例
```

`active` 期间**任意时刻只有一个任务在 running**（约束 2 的体现）。

### 5.3 关闭（closed）

正常关闭由用户显式触发或所有任务完成且无新请求超过阈值：

```
1. 等待当前 running 任务终态
2. 拒绝新任务进入 TaskBus
3. 销毁所有 Agent 实例
4. flush EventStream 到持久化存储
5. flush ThoughtStore 写缓存
6. 持久化 Workspace（如果用户选择保留）
7. 释放内存资源
```

关闭后 Session 不可恢复。要继续工作必须创建新 Session。

### 5.4 异常终止（abandoned）

```
触发条件：
  - 进程崩溃
  - 用户长时间无活动且超过 timeout
  - 系统资源压力导致主动终止

处理：
  - EventStream 保留到崩溃前的最后一个 event
  - Workspace 保留磁盘状态
  - 内存中的 running 任务标记为 failed（恢复时可见）
  - 用户下次访问时可以查看历史，但不能恢复执行
```

### 5.5 持久化模型

```
内存层（Session active 时）：
  - TaskBus 队列
  - Agent 实例
  - Workspace 文件描述符
  - ThoughtStore 写缓存

磁盘层（持续 flush）：
  - EventStream（append-only，每个事件实时写入）
  - Workspace（文件系统状态）
  - ThoughtStore（按 batch flush）

归档层（Session closed 后）：
  - EventStream 完整归档
  - Workspace 可选归档（用户选择）
  - ThoughtStore 永久保留（用户的长期资产）
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
                       │       Workspace
                       │       TaskBus
                       │       Default Agent boundary
                       │       AgentPool / Agent Manager (Product 1.1+)
                       │       ThoughtStore
                       │       EventStream
                       │
                       │ root
                       ↓
                    Root Task ──→ Subtasks ──→ ...
```

- **与 User：** 一个用户可同时拥有多个 Session（多个会话窗口），但每个 Session 只属于一个用户
- **与 Task：** Session 是 Task 的命名空间和资源容器
- **与 Agent：** Product 1.0 使用 Session 内 Default Agent execution boundary；Product 1.1+ dynamic assignment 中，Agent 实例的创建和销毁都在 Session 内
- **与 Bus：** 每个 Session 有独立的 TaskBus 实例，不跨 Session 共享
- **与 ThoughtStore：** ThoughtStore 按 user_id 持久化，Session 是访问入口；跨 Session 的长期记忆通过 user_id 共享

---

## 7. 未来发展点

### 7.1 v1.x：会话恢复

**断点续传**

Session 异常终止后，下次访问时不仅可以查看历史，还可以从中断点恢复执行：

```python
session = Session.resume(session_id)
# 加载所有持久化状态
# Running 任务被标记为 failed，但 ThoughtStore 中的推理保留
# 用户可以选择"重试"创建新 Task 继承上下文
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
| 工作区数量 | 单一 | 三层（Session/Task/Agent） | 简洁性 + 串行执行使并行写不必要 |
| 配置归属 | Session 级 | Agent 级 | 用户感知一致，一次设置贯穿会话 |
| EventStream 边界 | 按 Session 分片 | 全局共享 | 查询和审计的范围天然清晰 |
| Agent 实例归属 | Session 内 | 全局池 | 资源边界清晰，故障域小 |
| 持久化粒度 | EventStream 实时 + Workspace 持续 | 关闭时统一持久化 | 崩溃时丢失最少 |
| 跨 Session 通信 | 严格隔离 | 默认共享 | 与"进程"心智模型一致 |
| 关闭策略 | 显式或超时 | 自动按空闲清理 | 用户对会话边界有控制感 |
