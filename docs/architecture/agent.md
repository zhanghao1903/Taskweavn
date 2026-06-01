# Agent 架构设计

> 多 Agent 协作架构的核心抽象 · v1.2 · 2026-05-31
>
> 2026-05-31 scope note: Product 1.0 通过固定 Default Agent route 执行 PublishedTask。Default Agent 有稳定 runtime boundary 和 system identity，但 Product 1.0 不引入 public Agent Manager、dynamic Agent assignment、custom Agent protocol 或 long-lived AgentLoop instance。Routing Agent 和 public Agent protocol 仍是 Product 1.1+ 方向。

---

## 1. 定义

**Agent 是无状态的能力载体。Execution Agent 是 Task 的执行单元；Routing Agent 是 Task assignment 的策略单元。**

Execution Agent 本质上是一个**一次性函数对象**：接收一个 Task 作为输入，访问所属 Session 的 Session Workspace 作为环境，调用 LLM + 工具集完成执行，输出 result。**任务结束即销毁。**

```
Agent ≡ 一次性函数(Task, Session Workspace) → Result
        capability + tools + llm_config 是它的"签名"
```

不存在"长生命周期 Agent"的概念。同种能力的 N 个并发任务对应 N 个独立的 Agent 实例。

Routing Agent 是一个特殊 Agent role：它观察 pending Tasks 和可用 Agent 描述，提交 assignment command。它可以是硬规则、LLM 策略或高级用户自定义策略，但不能直接修改 Task 状态。该能力是 Product 1.1+ routing foundation，不是 Product 1.0 固定路线执行闭环的依赖。

---

## 2. 核心抽象

### 2.1 Agent 是函数，不是 Actor

```
传统 Actor 模型：
  Agent 是长生命对象，维护邮箱、内部状态、跨任务记忆
  Agent 间通过消息通信
  → 资源管理复杂、状态一致性困难、调试痛苦

本架构：
  Agent 是函数对象，每次实例化处理一个 Task 后销毁
  Agent 间不直接通信，所有协作通过 Task 流转
  → 资源管理简单、无状态一致性问题、可 replay
```

这是从 Erlang 风格转向纯函数式的关键决策。

### 2.2 Agent 的"身份" vs Agent 的"实例"

需要区分两个层次：

```
Agent Template (身份)        Agent Instance (实例)
─────────────────────────    ───────────────────────────
注册在 AgentPool             从 Template 实例化
描述能力 + 工具 + LLM 配置    每个 Task 一个独立实例
不变的，跨 Session 复用       一次性，任务结束销毁
没有运行时状态                持有当前 Task 的执行上下文
```

```python
# Template
@dataclass(frozen=True)
class AgentTemplate:
    capability: str
    tools: list[Tool]
    llm_config: LLMConfig
    system_prompt: str

# Instance
class AgentInstance:
    template: AgentTemplate
    current_task: Task
    workspace: Workspace
    llm_client: LLMClient

    def execute(self) -> TaskResult: ...
```

**用户配置和系统注册的是 Template。运行时存在的是 Instance。**

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

### 2.7 Product 1.1 TODO：Agent Protocol

当前文档先定义 Agent 的系统边界，不在 1.0 内完成公开协议。Product 1.1 需要补一层 Agent 接入协议，先回答“什么样的 Agent 允许接入系统”：

- 是否有稳定 `agent_id` / `template_id`、版本和 role；
- 是否声明 capability、工具需求、输入/输出 schema 和可观测事件；
- 是否声明 lifecycle hooks、启动前动作、健康检查、失败语义和控制能力；
- 是否通过 command 请求系统状态变化，而不是直接改 Task、Session、Audit 等状态；
- 是否能被 TaskBus、CapabilityCatalog、Interaction Layer 和 Audit Page 验证、观测和追溯。

特殊 Agent 的协议作为后续 TODO 补完，包括 Routing Agent、Execution Agent、Collaborator Agent、Audit Agent、Result Packaging Agent 等。高级用户自定义 Agent、router-style policy Agent、模板化创建 Agent 和 workflow 生成 Agent 都归入 Product 1.1+ 的扩展性规划，不作为 1.0 闭环阻塞项。

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

### 3.2 AgentInstance（运行时持有）

| 属性 | 类型 | 说明 |
|-----|------|-----|
| `instance_id` | `AgentInstanceId` | 运行时唯一标识 |
| `template` | `AgentTemplate` | 引用的模板 |
| `current_task` | `Task` | 正在执行的任务 |
| `workspace` | `Workspace` | Session 工作区的引用 |
| `llm_client` | `LLMClient` | LLM 调用客户端 |
| `event_logger` | `EventLogger` | 写入 EventStream 的句柄 |
| `started_at` | `datetime` | 实例创建时间 |

`AgentInstance` 没有 `previous_tasks` 之类的字段——**任务结束即销毁，不积累状态。**

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
为什么不让 Agent 实例处理多个任务？

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

Capability 是用户能感知的概念："我需要一个会审计代码的 Agent。" 用户在编排时选择的是 capability，不是某个具体 Agent 实例。

```
用户视角：       "审计 Agent" + "执行 Agent"
Template 视角：  AgentTemplate(capability="audit") + ...
Instance 视角：  运行时按需实例化，结束即销毁
```

这种分层让用户的心智模型简单（capability），系统的调度灵活（按需实例化），运行时无状态泄漏（实例销毁）。

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
        │  Template    │  注册到 AgentPool
        │  (永久存在)  │
        └──────┬───────┘
               │
               │ Bus 派发任务时实例化
               ↓
        ┌──────────────┐
        │  Instantiated│  分配 instance_id, 加载 LLM context
        └──────┬───────┘
               ↓
        ┌──────────────┐
        │  Executing   │  调用 LLM, 工具, 读写 Workspace
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
        │  Destroyed   │  释放资源, 实例不可访问
        └──────────────┘
```

### 5.1 注册（Template 阶段）

AgentTemplate 在 Session 启动时（或更早）注册到 AgentPool：

```python
session.agent_pool.register(AgentTemplate(
    capability="audit",
    tools=[ReadFileTool(), DiffTool()],
    llm_config=LLMConfig(model="claude-sonnet-4.6"),
    system_prompt="你是代码审计专家...",
))
```

Template 是不变的，描述"系统中存在哪些能力"。

### 5.2 实例化

当 TaskBus 决定执行某个 Task 时，从对应 capability 的 Template 实例化一个 Agent：

```python
def dispatch(self, task: Task) -> AgentInstance:
    template = self.pool.find(capability=task.required_capability)
    instance = AgentInstance(
        template=template,
        current_task=task,
        workspace=self.session.workspace,
        llm_client=LLMClient.from_config(template.llm_config),
    )
    return instance
```

实例化是**轻量操作**——只做对象创建和资源连接，不触发 LLM 调用。

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

### 5.4 销毁

任务终态后立即销毁：

```python
def destroy(self):
    # 1. flush 所有 pending event
    self.event_logger.flush()
    # 2. 释放 LLM client 连接
    self.llm_client.close()
    # 3. 解除 Workspace 引用
    self.workspace = None
    # 4. 实例不再可访问
```

**销毁后 instance_id 不会被复用**，便于事件溯源和审计。

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
        AgentTemplate (永久)
            │
            │ instantiate(task)
            ↓
        AgentInstance (一次性)
          │  │  │
          │  │  └── reads/writes → Workspace
          │  │
          │  └── calls → LLM
          │
          └── may create → Task (via CreateTaskTool)
                            │
                            ↓
                          TaskBus
```

- **与 Session：** Agent 实例严格在 Session 内，不跨 Session 复用
- **与 Task：** 1:1 映射——一个 Agent 实例处理一个 Task
- **与 Bus：** Bus 是 Agent 实例化的触发器，Agent 不主动从 Bus 拉任务
- **与 Workspace：** Agent 通过工具读写 Workspace，无独立工作区
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
        """预初始化 N 个 LLM client 连接，
        Template 不变，仍然单任务用完即销毁。
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

ThoughtStore 中按 capability 累积的"经验"在实例化时自动注入 Agent 的 system_prompt：

```python
def instantiate(self, task: Task) -> AgentInstance:
    template = self.pool.find(task.required_capability)
    relevant_memories = self.thought_store.query(
        capability=template.capability,
        related_to=task.intent,
        top_k=5,
    )
    enhanced_prompt = template.system_prompt + format_memories(relevant_memories)
    return AgentInstance(template=template, system_prompt=enhanced_prompt, ...)
```

这是**经验复用**而非**状态复用**——Agent 实例仍然无状态，只是初始化时拿到了相关历史经验。

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

让 AgentTemplate 跨 Session 共享，用户在不同会话中复用同一套 Agent 定义。注意：仅 Template 共享，Instance 仍按 Session 隔离。

---

## 8. 设计决策小结

| 决策 | 选择 | 替代方案 | 选择理由 |
|------|------|---------|---------|
| 状态 | 无状态 | 持久状态 | 简洁性、可测试、可 replay |
| 任务并发 | 单任务实例 | 多任务复用 | 函数式语义，避免状态隔离问题 |
| Capability 类型 | 单值字符串 | 多值 set / 层级 | 调度无歧义，匹配简单 |
| Template vs Instance | 严格分离 | 单一概念 | 区分"能做什么"和"正在做什么" |
| 协作能力 | 工具化 | Agent 类型分类 | 与其他能力同构 |
| Tool 归属 | Template 持有 | Session 全局 | 能力边界清晰，故障域小 |
| 销毁时机 | 任务终态立即销毁 | 池化复用 | 强制无状态，避免泄漏 |
| 经验复用 | 通过 ThoughtStore + 显式注入 | Instance 间共享 | 数据是数据，行为是行为 |
