# Agent 架构设计

> 多 Agent 协作架构的核心抽象 · v1.4 · 2026-06-24
>
> 2026-05-31 scope note: Product 1.0 通过固定 Default Agent route 执行 PublishedTask。Default Agent 有稳定 runtime boundary 和 system identity，但 Product 1.0 不引入 public Agent Manager、dynamic Agent assignment、custom Agent protocol 或 long-lived AgentLoop instance。
>
> 2026-06-19 fact note: 当前实现中 Agent 的 Product 1.0 事实是 `FixedRouteTaskExecutor -> Resident Default Agent boundary -> task-scoped AgentLoop run`。Agent 是能力/模板层概念，真正执行的是 task-scoped run；Session 与 context ownership 由 TaskBus、Context Manager、AskStore、Event/Audit stores 约束，不由 Agent 私有状态决定。
>
> 2026-06-24 Product 1.1 alignment: Product 1.1 已经落地 Runtime Input Router、Router LLM、read-only inquiry LLM、Collaborator/Execution Agent LLM profile 解析，以及全局 Settings-backed Agent LLM resolver。完整 Agent Manager、dynamic execution assignment、public Agent protocol 和用户自定义 Agent 仍是后续扩展，不是当前 Product 1.1 本地闭环事实。

---

## 1. 定义

**Agent 是能力载体和运行时边界。Execution Agent 是 Task 执行能力；Routing Agent 是 Task assignment 的策略能力。**

Execution Agent 在架构上分成三层：

1. Agent capability / template：声明 role、capability、工具、LLM 配置和控制能力；
2. Agent runtime boundary：Product 1.0 中是常驻 Default Agent identity 和固定执行入口；
3. Agent run / AgentLoop：针对一个 Task 的 task-scoped 执行过程，调用 LLM + 工具完成任务并输出 result、ASK、failure 或 interruption outcome。

当前 Product 1.0 不把 Agent Manager、public Agent protocol 或自定义 Agent
注册暴露给用户。它只有固定 Default Agent 路由，但保留 Agent template / run
分层，便于 Product 1.1+ 接入 Router、Agent Manager、skills 和 MCP。

```
Agent capability ≈ role + capability + tools + llm_config + control capabilities
Agent run ≈ scoped execution(Task, workspace root, context manager) → outcome
```

不存在跨任务私有记忆作为事实权威的 Agent。长期身份可以存在于 runtime
boundary 或 template 上，但 Task state、ASK、messages、context traces 和 audit
facts 仍由各自 domain/store 持久化。

Routing Agent 是一个特殊 Agent role：它观察 pending Tasks 和可用 Agent 描述，提交 assignment command。它可以是硬规则、LLM 策略或高级用户自定义策略，但不能直接修改 Task 状态。该能力是 later dynamic routing foundation，不是当前 Product 1.1 固定路线执行闭环的依赖。

---

## 2. 核心抽象

### 2.1 Agent Run 是函数式执行，不是独立 Actor

```
传统 Actor 模型：
  Agent 是长生命对象，维护邮箱、内部状态、跨任务记忆
  Agent 间通过消息通信
  → 资源管理复杂、状态一致性困难、调试痛苦

本架构：
  Agent run 以函数式方式处理一个 Task
  Agent 私有状态不作为系统事实来源
  Agent 间不直接通信，所有协作通过 TaskBus / Message / ASK / Event 流转
  → 资源管理简单、无状态一致性问题、可 replay
```

这是从 Erlang 风格 Agent actor 转向 TaskBus-centered execution 的关键决策。

### 2.2 Agent 的"身份" vs Agent 的"实例"

需要区分两个层次：

```
Agent Template (能力/身份)   Agent Runtime / Run
─────────────────────────    ───────────────────────────
注册或内置在系统              Product 1.0 是 Default Agent boundary
描述能力 + 工具 + LLM 配置    每个 Task 一个 scoped AgentLoop run
不变的，未来可跨 Session 复用  run 结束后释放执行栈
没有事实权威状态              持有当前 Task 的 transient execution context
```

```python
# Template
@dataclass(frozen=True)
class AgentTemplate:
    capability: str
    tools: list[Tool]
    llm_config: LLMConfig
    system_prompt: str

# Run
class AgentRun:
    template: AgentTemplate
    current_task: Task
    workspace_root: Path
    context_manager: SessionContextManager
    llm_client: LLMClient

    def execute(self) -> TaskResult: ...
```

**用户未来配置和系统注册的是 Template。运行时推进任务的是 Agent run。**
Product 1.0 的 Default Agent 是内置 template/runtime boundary，不需要 Agent
Manager 创建自定义实例。

### 2.3 Capability 是单值字符串

每个 Agent Template 有唯一的 `capability`，是 Bus 调度的匹配键：

```
"plan"        ─ 规划类 Agent
"execute"     ─ 执行类 Agent
"audit"       ─ 审计类 Agent
"summarize"   ─ 总结类 Agent
```

Capability 不是 set 也不是层级，**故意保持扁平**。需要"既能 plan 又能 execute"的 Agent？注册一个新的 capability `"plan_and_execute"`。这种粗粒度避免了能力匹配的歧义。

### 2.4 工具集决定能做什么

Agent 的实际能力由其 `tools` 字段决定，capability 只是调度匹配的标签：

```
plan agent:
  tools = [read_file, list_dir, create_task, query_thought_store]

execute agent:
  tools = [read_file, write_file, run_command, query_thought_store]

audit agent:
  tools = [read_file, diff, query_event_stream]
```

**协作能力（创建子任务）通过 `CreateTaskTool` 工具暴露**，与其他能力同等管理。挂载了它的 Agent 是协作节点，没挂载的是叶子节点。

### 2.5 Routing Agent 是可插拔策略对象

Task 路由策略不写死在 TaskBus。Product 1.1+ Routing Agent 负责决定 pending Task 应该交给哪个 Execution Agent：

```text
pending Tasks + Agent descriptors
  -> Routing Agent
  -> AssignmentCommand(task_id, assigned_agent_id, rationale)
  -> TaskBus validates and records assignment
```

Routing Agent 可以很严格，也可以很灵活：

- hard router：按 `required_agent_id` / `required_capability` 做确定性分配；
- LLM router：根据任务意图、上下文、成本、历史成功率和 fallback 策略做判断；
- custom router：高级用户接入自己的策略。

Routing Agent 的边界：

- 可以提交 assignment command；
- 可以说明 rationale；
- 可以在无可用 Agent 时发 routing notice；
- 不能直接把 Task 改成 running/done/failed；
- 不能绕过 TaskBus assignment / claim / completion validation。

这让路由成为可插拔能力，同时保持 TaskBus 的状态权威。

Product 1.0 note: fixed-route execution 使用 `FixedRouteTaskExecutor` 和 Resident Default Agent protocol。它不使用 Router / Routing Agent policy 或 Agent Manager 来选择 executor。

### 2.6 Agent Control Capabilities

中断不是 TaskBus 的能力，而是 Agent/runtime 的能力。不同 Agent 应声明自己支持哪些控制语义：

```text
supports_interrupt: bool
supports_pause: bool
supports_hard_cancel: bool
safe_point_description: str
```

1.0 默认采用 cooperative interruption：

- 外界只记录停止意图；
- Agent 在安全点检查 interruption；
- Runtime/tool 可以提供 best-effort hard cancel；
- UI 在 Agent 确认前显示 "stopping"，不承诺立即停止。

常见安全点包括 tool call 前后、文件写入前后、shell command 结束后、搜索批次结束后、等待用户确认时。

### 2.7 Later TODO: Agent Protocol

当前文档先定义 Agent 的系统边界，不在当前 Product 1.1 本地闭环内完成公开协议。后续 Agent Manager / dynamic assignment 需要补一层 Agent 接入协议，先回答“什么样的 Agent 允许接入系统”：

- 是否有稳定 `agent_id` / `template_id`、版本和 role；
- 是否声明 capability、工具需求、输入/输出 schema 和可观测事件；
- 是否声明 lifecycle hooks、启动前动作、健康检查、失败语义和控制能力；
- 是否通过 command 请求系统状态变化，而不是直接改 Task、Session、Audit 等状态；
- 是否能被 TaskBus、CapabilityCatalog、Interaction Layer 和 Audit Page 验证、观测和追溯。

特殊 Agent 的协议作为后续 TODO 补完，包括 Routing Agent、Execution Agent、Collaborator Agent、Audit Agent、Result Packaging Agent 等。高级用户自定义 Agent、router-style policy Agent、模板化创建 Agent 和 workflow 生成 Agent 都归入后续扩展性规划，不作为当前 Product 1.1 本地闭环事实。

---

## 3. 核心属性

### 3.1 AgentTemplate（注册时定义）

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `id` | `AgentTemplateId` | 模板唯一标识 |
| `capability` | `str` | 单值匹配键 |
| `display_name` | `str` | UI 显示名 |
| `description` | `str` | 能力描述，给用户看 |
| `tools` | `list[Tool]` | 可用工具集 |
| `llm_config` | `LLMConfig` | 模型、温度、max_tokens 等 |
| `system_prompt` | `str` | 该 capability 的角色定位 |
| `default_autonomy` | `AutonomyBehavior` | 默认自主度（可被 Session 覆盖） |

### 3.2 AgentRun（任务执行时持有）

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `run_id` | `AgentRunId` | 单次任务执行唯一标识 |
| `template` | `AgentTemplate` | 引用的模板 |
| `current_task` | `Task` | 正在执行的任务 |
| `workspace_root` | `Path` | selected workspace root 的引用 |
| `context_manager` | `SessionContextManager` | 构建每次 LLM input 的上下文治理入口 |
| `llm_client` | `LLMClient` | LLM 调用客户端 |
| `event_logger` | `EventLogger` | 写入 EventStream 的句柄 |
| `started_at` | `datetime` | run 启动时间 |

`AgentRun` 没有 `previous_tasks` 之类的字段。任务结束后 run 关闭，不积累跨任务事实权威状态。

---

## 4. 设计理念

### 4.1 无状态优于有状态

```
有状态 Agent 的代价：
  ├── 需要管理生命周期（什么时候创建？什么时候销毁？）
  ├── 需要解决并发访问（多任务能复用同一 Agent 吗？）
  ├── 需要处理状态泄漏（任务 A 的中间数据影响任务 B）
  └── 需要复杂的测试（同样输入不同输出）

无状态 Agent 的代价：
  └── LLM context 重建带来的 token 成本

权衡：
  正确性、可调试性、简洁性 远超 cache 命中率收益
  且 cache 命中通过 prompt 分层可以弥补
```

### 4.2 单任务优于多任务

```
为什么不让同一个 Agent run 处理多个任务？

如果允许 multi-task：
  - Agent 内部需要任务队列
  - 任务间状态隔离需要额外机制
  - "正在处理任务 X 时收到任务 Y" 的语义复杂
  - 调度器需要决定"派给空闲 Agent" 还是 "派给已有 Agent"

单任务约束让 Agent 退化为函数：
  Agent.execute(task) → result

  N 个任务 = N 个实例，资源分配 = 实例化成本
  这与函数调用模型完全一致
```

### 4.3 Agent 是 Capability 的运行时投影

Capability 是用户能感知的概念："我需要一个会审计代码的 Agent。" 用户在编排时选择的是 capability，不是某个具体 Agent run。

```
用户视角：       "审计 Agent" + "执行 Agent"
Template 视角：  AgentTemplate(capability="audit") + ...
Runtime 视角：   Resident Default Agent 或未来 Agent Manager 创建的 runtime
Run 视角：       task-scoped AgentLoop，结束后释放执行栈
```

这种分层让用户的心智模型简单（capability），系统的调度灵活（固定路由或未来按需实例化），运行时不依赖 Agent 私有状态作为事实来源。

### 4.4 Tool 是能力的细粒度表达

Capability 是粗粒度标签，Tool 才是细粒度能力描述。**真正决定 Agent 能做什么的是它挂载的工具，不是它的 capability 字符串。**

```
两个 audit Agent 可以有不同的工具集：
  AuditTemplateA.tools = [read_file, diff]              # 仅审计
  AuditTemplateB.tools = [read_file, diff, create_task] # 审计 + 派生修复任务

它们的 capability 都是 "audit"，调度上等价
但实际能力差异巨大
```

这种设计让"能力组合"有两个层次：
- 选 capability（粗粒度）
- 选 tools（细粒度）

ConstraintProfile（约束 profile）控制用户能在哪个层次做选择。

---

## 5. 生命周期

```
        ┌──────────────┐
        │  Template    │  内置或未来注册到 AgentPool
        │  (能力定义)  │
        └──────┬───────┘
               │
               │ Bus / executor 派发任务时启动 run
               ↓
        ┌──────────────┐
        │  Run Started │  分配 run_id, 通过 Context Manager 构建 LLM context
        └──────┬───────┘
               ↓
        ┌──────────────┐
        │  Executing   │  调用 LLM, 工具, 读写 workspace root
        └──────┬───────┘
        ┌──────┴───────┐
        ↓              ↓
   ┌─────────┐    ┌─────────┐
   │ Returned│    │ Crashed │
   └────┬────┘    └────┬────┘
        ↓              ↓
        └──────┬───────┘
               ↓
        ┌──────────────┐
        │  Run Closed  │  释放 transient execution stack
        └──────────────┘
```

### 5.1 注册（Template 阶段）

Product 1.0 使用内置 Default Agent boundary，不要求 AgentPool。Product 1.1+
的动态 Agent Template 可以在 Session 启动时（或更早）注册到 AgentPool：

```python
session.agent_pool.register(AgentTemplate(
    capability="audit",
    tools=[ReadFileTool(), DiffTool()],
    llm_config=LLMConfig(model="claude-sonnet-4.6"),
    system_prompt="你是代码审计专家...",
))
```

Template 是不变的，描述"系统中存在哪些能力"。

### 5.2 启动 Agent Run

Product 1.0 中，当 `FixedRouteTaskExecutor` 从 TaskBus claim 到某个 Task，
它启动一个 task-scoped Default Agent run。Product 1.1+ 中，Agent Manager 可从
对应 capability 的 Template 创建 runtime / run：

```python
def dispatch(self, task: Task) -> AgentRun:
    template = self.pool.find(capability=task.required_capability)
    run = AgentRun(
        template=template,
        current_task=task,
        workspace_root=self.session.workspace_root,
        context_manager=self.session.context_manager,
        llm_client=LLMClient.from_config(template.llm_config),
    )
    return run
```

启动 run 是**轻量操作**——只做对象创建、资源连接和 ContextBuildRequest
准备，不直接承诺 LLM 调用已经完成。

### 5.3 执行

```python
def execute(self) -> TaskResult:
    # 1. 构造 prompt（system + task + workspace context + memory）
    prompt = self._build_prompt()

    # 2. ReAct 循环
    while not self._is_done():
        response = self.llm_client.chat(prompt)
        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                observation = self._execute_tool(tool_call)
                prompt.append(observation)
        else:
            return self._extract_result(response)

    # 3. 返回结果
```

执行期间产生的所有事件（thought、tool_call、observation）写入 EventStream。

### 5.4 关闭 Run

任务终态或 cooperative interruption outcome 后关闭 run：

```python
def destroy(self):
    # 1. flush 所有 pending event
    self.event_logger.flush()
    # 2. 释放 LLM client 连接
    self.llm_client.close()
    # 3. 解除 workspace root 引用
    self.workspace = None
    # 4. 实例不再可访问
```

**关闭后 run_id 不会被复用**，便于事件溯源和审计。Agent template / Default
Agent identity 可以继续存在。

---

## 6. 与其他组件的关系

下图描述 Product 1.1+ routed Agent model。Product 1.0 fixed-route path 由
`FixedRouteTaskExecutor -> ResidentDefaultAgent` 执行，不通过 AgentPool 选择
executor。

```
        AgentPool (Session 内)
            │
            │ register
            ↓
        AgentTemplate (能力定义)
            │
            │ start_run(task)
            ↓
        AgentRun (task-scoped)
          │  │  │
          │  │  └── reads/writes → workspace root
          │  │
          │  └── calls → LLM
          │
          └── may create → Task (via CreateTaskTool)
                            │
                            ↓
                          TaskBus
```

- **与 Session：** Agent run 严格在 Session 内，不跨 Session 复用
- **与 Task：** Product 1.0 中一个 Agent run 处理一个 Task；Template / Default Agent identity 可被多个 run 复用
- **与 Bus：** Bus 是 Agent run 启动的状态权威，Agent 不主动绕过 Bus 拉任务
- **与 Workspace：** Agent 通过工具读写 selected workspace root，无独立工作区
- **与 Tool：** Tool 是 Agent 能力的载体；同一个 Tool 可被多个 Template 共用
- **与 ThoughtStore：** Agent 通过工具调用读写，不直接持有引用
- **与 EventStream：** Agent 的所有动作写入 EventStream，便于审计

---

## 7. 未来发展点

### 7.1 Product 1.1+：Agent Pool 预热

**减少冷启动成本**

```python
class AgentPool:
    def warmup(self, capability: str, count: int = 1):
        """预初始化 N 个 LLM client 连接。
        Template 不变，AgentRun 仍然 task-scoped。
        """
```

仅预热**资源**（LLM client、HTTP 连接），不预热**状态**——Template 保持无状态约束。

### 7.2 Product 1.1+：Capability 命名空间

```
"audit"           ─ 通用审计
"audit:security"  ─ 安全审计
"audit:perf"      ─ 性能审计
```

调度匹配支持前缀，`audit:security` 任务匹配不到时降级到 `audit`。增强表达力，不破坏单值约束。

### 7.3 v2.x：Agent 经验继承

**长期记忆显式注入**

ThoughtStore 中按 capability 累积的"经验"在启动 Agent run 时自动注入 system_prompt：

```python
def start_run(self, task: Task) -> AgentRun:
    template = self.pool.find(task.required_capability)
    relevant_memories = self.thought_store.query(
        capability=template.capability,
        related_to=task.intent,
        top_k=5,
    )
    enhanced_prompt = template.system_prompt + format_memories(relevant_memories)
    return AgentRun(template=template, system_prompt=enhanced_prompt, ...)
```

这是**经验复用**而非**状态复用**——Agent run 仍然 task-scoped，只是启动时拿到了相关历史经验。

### 7.4 v3.x：能力组合

**用户定义的复合 capability**

```python
session.agent_pool.compose(
    name="audit_and_fix",
    base_capabilities=["audit", "execute"],
    tools_union=True,
    system_prompt_merge=...,
)
```

让用户在 ConstraintProfile 控制下组合现有 Agent 创造新能力。这是 Phase 4 后期才考虑的扩展。

### 7.5 v3.x：跨 Session Agent 模板

**Template 全局化**

让 AgentTemplate 跨 Session 共享，用户在不同会话中复用同一套 Agent 定义。注意：仅 Template 共享，AgentRun 仍按 Session 隔离。

---

## 8. 设计决策小结

| 决策 | 选择 | 替代方案 | 选择理由 |
|------|------|---------|---------|
| 状态 | 无状态 | 持久状态 | 简洁性、可测试、可 replay |
| 任务并发 | task-scoped AgentRun | 多任务复用同一执行栈 | 函数式语义，避免状态隔离问题 |
| Capability 类型 | 单值字符串 | 多值 set / 层级 | 调度无歧义，匹配简单 |
| Template vs Run | 严格分离 | 单一概念 | 区分"能做什么"和"正在执行什么" |
| 协作能力 | 工具化 | Agent 类型分类 | 与其他能力同构 |
| Tool 归属 | Template 持有 | Session 全局 | 能力边界清晰，故障域小 |
| 关闭时机 | 任务终态或中断 outcome 后关闭 run | 复用执行栈 | 强制无事实状态泄漏 |
| 经验复用 | 通过 ThoughtStore + 显式注入 | AgentRun 间共享私有状态 | 数据是数据，行为是行为 |
