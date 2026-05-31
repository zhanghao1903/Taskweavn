问：我想到一个idea 了。execution agent 的prompt 应该是结构化的，我们就叫这个结构为 Task Context。 Task Context这个结构里面应该有original target，plan， concurrent step， last step. tool call history,(include tool  call and result), enevt history(it is overlap with tool call, so it need    to consider).
anyway, execution agent 是一个任务执行的agent，context 如何治理，需要回到需求方上，execution agent需要什么样的上下文。原始目标？计划？work flow，check point，permission，events history等等。如果我们将这个抽象出来了，上下文治理就有了一个锚点，能够持续迭代的锚点，而不是一次性解决问题的方案

gpt答：
这个 idea 很重要，而且我觉得你已经抓到 agent 上下文治理真正的锚点 了：

不要先问“怎么压缩上下文”，而是先问：execution agent 为了完成当前任务，到底需要什么上下文结构？

也就是说，Task Context 不是简单的 prompt 模板，而应该是 execution agent 的 任务执行上下文契约。

⸻

1. 这个抽象的价值：把“上下文治理”从玄学变成工程问题

很多 agent 项目的上下文治理容易变成：

历史太长了，怎么 summary？
文件太多了，怎么 RAG？
tool call 太多了，怎么裁剪？
prompt 太乱了，怎么压缩？

这些都是局部问题。

而你提出的 Task Context 更像是一个中心锚点：

Execution Agent 在每一步执行前，需要看到一个结构化 Task Context。
上下文治理的目标，就是持续维护和生成这个 Task Context。

这样以后所有优化都有了对象：

* 哪些字段是必须的？
* 哪些字段可以裁剪？
* 哪些字段需要 summary？
* 哪些字段必须保留原文？
* 哪些字段是当前 step 专用的？
* 哪些字段是全局任务约束？
* 哪些字段可以从 event log 重建？
* 哪些字段应该进入 LLM prompt，哪些只放在系统状态里？

这就从“一次性 prompt 工程”变成了“可持续迭代的 context architecture”。

⸻

2. Task Context 不应该只是 prompt，而是中间表示层

我建议你不要把它定义成：

Task Context = prompt 内容

而应该定义成：

Task Context = agent 执行状态的结构化中间表示
Prompt = Task Context 的一次渲染结果

也就是说：

事件日志 / workflow / plan / workspace / permissions
        ↓
Context Builder
        ↓
Task Context
        ↓
Prompt Renderer
        ↓
Execution Agent LLM Input

这点很关键。

因为同一个 Task Context，未来可以渲染成不同 prompt：

* 给 coding agent 的 prompt
* 给 planning agent 的 prompt
* 给 reviewer agent 的 prompt
* 给 recovery agent 的 prompt
* 给 evaluator agent 的 prompt

所以 Task Context 是系统内部的稳定结构，prompt 只是它的表达形式。

⸻

3. 一个初版 Task Context 可以这样设计

我觉得可以分成几大块。

A. Task Identity / Original Target

这是任务的源头，不能丢。

interface TaskIdentity {
  taskId: string
  originalTarget: string
  userIntent: string
  successCriteria?: string[]
  nonGoals?: string[]
}

这里要区分：

originalTarget = 用户最初说了什么
userIntent = 系统理解后的目标
successCriteria = 怎么算完成
nonGoals = 明确不做什么

例如用户说：

帮我修复上传文件 413 的问题

系统理解后可能是：

originalTarget:
修复上传文件 413 问题
userIntent:
定位是前端限制、后端限制、Nginx 限制还是网关限制，并修改配置使 10MB 文件可以上传
successCriteria:
- 10MB 文件上传成功
- 错误提示合理
- 不破坏已有上传流程
nonGoals:
- 不重构整个上传模块
- 不引入新的对象存储服务

这个部分应该长期保留，不能被 summary 弄丢。

⸻

B. Plan / Workflow

这里保存当前执行计划。

interface TaskPlan {
  planVersion: number
  status: "draft" | "approved" | "executing" | "revising" | "completed"
  steps: PlanStep[]
  currentStepId?: string
}

每个 step 可以是：

interface PlanStep {
  id: string
  title: string
  description?: string
  status: "pending" | "running" | "blocked" | "done" | "skipped" | "failed"
  dependsOn?: string[]
  expectedOutput?: string
}

这里我建议你用 currentStep，而不是 concurrent step。如果你说的是“当前步骤”，就叫 currentStep。如果你说的是“并发步骤”，那应该叫 concurrentSteps。

⸻

C. Current Step Context

这是 execution agent 最重要的部分。

interface CurrentStepContext {
  stepId: string
  objective: string
  inputContext: string[]
  requiredActions?: string[]
  expectedOutput?: string
  allowedTools?: string[]
  constraints?: string[]
  riskLevel?: "low" | "medium" | "high"
}

这里的核心是告诉 agent：

你现在不是重新理解整个任务，你现在是在执行这个 step。

这能明显减少 agent 发散。

比如：

Current Step:
检查 nginx 配置中是否存在 client_max_body_size 限制。
Allowed Tools:
- read_file
- grep
- list_dir
Constraints:
- 不要修改代码
- 只做定位

这样 execution agent 的行为会稳定很多。

⸻

D. Last Step / Recent Progress

这个字段很重要，因为 LLM 不擅长从长历史里自己判断“刚刚发生了什么”。

interface RecentProgress {
  lastStep?: {
    stepId: string
    result: "success" | "failed" | "partial" | "blocked"
    summary: string
    artifactsChanged?: string[]
    importantFindings?: string[]
    unresolvedIssues?: string[]
  }
}

你提到的 last step 是非常必要的。

它解决的是：

agent 当前这一轮应该从哪里接着做？

而不是让模型自己从几十条 tool call 里推断。

⸻

E. Tool Call History

这个字段要注意，不应该无限塞原始历史。

interface ToolCallHistory {
  recent: ToolCallRecord[]
  important: ToolCallRecord[]
  omittedSummary?: string
}

每个 tool call：

interface ToolCallRecord {
  id: string
  stepId?: string
  toolName: string
  arguments: unknown
  resultSummary: string
  status: "success" | "error"
  timestamp: string
  rawResultRef?: string
}

关键点是：prompt 里不一定放完整 raw result。

更好的方式是：

resultSummary + rawResultRef

需要的时候 agent 再按 ref 读取原始结果。

否则 tool call history 很快会把 context 撑爆。

⸻

F. Event History

你提到 tool call history 和 event history 有重叠，这个判断是对的。

我的建议是：

Event History 是 canonical source of truth。
Tool Call History 是从 Event History 中投影出来的一个 view。

也就是说，底层统一存：

interface Event {
  id: string
  type: string
  timestamp: string
  actor: "user" | "agent" | "system" | "tool"
  payload: unknown
  causationId?: string
  correlationId?: string
}

事件类型可以包括：

task.created
plan.created
plan.updated
step.started
step.completed
tool.called
tool.result.received
permission.requested
permission.granted
permission.denied
checkpoint.created
file.modified
error.occurred
user.interrupted
agent.message.created

然后根据不同用途生成不同视图：

Event Log
  ↓
Tool Call History View
  ↓
Recent Progress View
  ↓
Audit Timeline View
  ↓
Runtime State View
  ↓
Prompt Context View

这样你就不会纠结：

tool call history 和 event history 到底谁包含谁？

答案是：

Event History 是原始账本。
Tool Call History 是其中一种派生视图。

⸻

4. Permission / Checkpoint 必须进入 Task Context

execution agent 不是普通聊天模型，它会执行动作，所以权限和 checkpoint 很重要。

interface ExecutionControl {
  permissions: PermissionState[]
  checkpoints: Checkpoint[]
  pendingApprovals?: ApprovalRequest[]
  rollbackAvailable?: boolean
}

例如：

interface PermissionState {
  scope: string
  status: "allowed" | "denied" | "requires_approval"
  reason?: string
}

这部分会直接影响 agent 行为：

可以读文件，但不能写文件。
可以修改 frontend/src，但不能改 backend。
执行删除操作前必须请求确认。
当前 checkpoint 是 cp_20260527_001。

如果没有这个结构，agent 很容易在 prompt 里“忘记权限边界”。

⸻

5. Task Context 最核心的设计原则

我觉得可以定几条原则。

第一，原始目标不可丢

originalTarget 应该永远保留。

summary 可以压缩执行历史，但不能替换原始目标。否则任务会逐渐漂移。

⸻

第二，当前 step 要显式化

不能只给 agent 一个大目标，然后让它自由发挥。

要明确告诉它：

你当前正在执行哪个 step。
这个 step 的输入是什么。
这个 step 的输出是什么。
这个 step 允许做什么，不允许做什么。

⸻

第三，event log 做事实源，context 是派生物

不要把所有状态都手动维护成一堆重复字段。

更合理的是：

事件日志是事实源。
Task Context 是根据当前任务需要构建出来的工作视图。

这样后面你要做审计、回放、debug、可观测性，都会更稳。

⸻

第四，Tool Call 不等于 Context

tool call history 是证据，不是全部上下文。

有些 tool result 很长，比如：

* 文件内容
* grep 结果
* 编译日志
* 测试日志
* diff
* API 返回

这些不能全部塞 prompt，而应该摘要化、索引化、ref 化。

⸻

第五，Task Context 应该支持分层

不是所有字段都每次进入 LLM。

可以分成：

Core Context：每次必须进入 prompt
Step Context：当前 step 进入 prompt
Recent Context：最近 N 轮进入 prompt
Referenced Context：按需读取
Audit Context：不进 prompt，只用于审计
Recovery Context：失败恢复时才进入

这比简单地说“保留最近 20 条消息”要强很多。

⸻

6. 我建议的 Task Context 初版结构

可以先定义成这样：

interface TaskContext {
  task: {
    id: string
    originalTarget: string
    interpretedGoal: string
    successCriteria: string[]
    nonGoals?: string[]
  }
  plan: {
    version: number
    status: "draft" | "approved" | "executing" | "revising" | "completed"
    steps: PlanStep[]
    currentStepId?: string
  }
  currentStep?: {
    id: string
    objective: string
    expectedOutput?: string
    constraints?: string[]
    allowedTools?: string[]
    riskLevel?: "low" | "medium" | "high"
  }
  progress: {
    completedSteps: string[]
    lastStep?: {
      id: string
      result: "success" | "failed" | "partial" | "blocked"
      summary: string
      findings?: string[]
      changedArtifacts?: string[]
      unresolvedIssues?: string[]
    }
  }
  executionState: {
    status: "idle" | "running" | "waiting_user" | "blocked" | "failed" | "completed"
    pendingQuestion?: string
    pendingApproval?: string
    currentCheckpointId?: string
  }
  permissions: {
    allowedTools: string[]
    deniedTools?: string[]
    requiresApproval?: string[]
    fileScopes?: string[]
  }
  evidence: {
    recentToolCalls: ToolCallRecord[]
    importantFindings: string[]
    referencedArtifacts?: ArtifactRef[]
    omittedHistorySummary?: string
  }
  events: {
    recentEvents: EventSummary[]
    eventLogRef?: string
  }
  memory?: {
    durableFacts?: string[]
    userPreferences?: string[]
    projectConventions?: string[]
  }
}

这个结构不是最终版，但作为 0.1 非常够用了。

⸻

7. 更进一步：Task Context 可以成为 runtimeReducer 的输出

结合你前面问的 runtimeReducer，我觉得可以形成一个非常清晰的架构：

User / Agent / Tool / System Events
        ↓
runtimeReducer
        ↓
Runtime State
        ↓
contextBuilder
        ↓
Task Context
        ↓
promptRenderer
        ↓
Execution Agent

也就是说：

runtimeReducer 负责把事件折叠成当前运行时状态。
contextBuilder 负责从运行时状态中挑选、压缩、组织出 Task Context。
promptRenderer 负责把 Task Context 渲染成 LLM prompt。

这三个东西不要混在一起。

分别是：

runtimeReducer：事实状态治理
contextBuilder：上下文治理
promptRenderer：表达治理

这个分层很漂亮，也很适合作为你产品架构里的核心设计。

⸻

8. 这会带来一个很强的产品能力：可解释的上下文治理

很多 agent 失败的时候，用户不知道为什么失败。

但如果你有 Task Context，就可以展示：

本轮 Agent 看到的目标：
...
本轮 Agent 当前步骤：
...
本轮 Agent 参考了哪些历史：
...
本轮 Agent 忽略了哪些历史：
...
本轮 Agent 拥有哪些权限：
...
本轮 Agent 基于哪些 evidence 做判断：
...

这就是你之前一直强调的 运行时信任、审计、可观测性。

所以 Task Context 不只是内部实现，它甚至可以成为产品差异点。

Codex/Claude Code 这类工具很强，但用户很难看到：

它为什么这一步这么做？
它到底记住了什么？
它遗忘了什么？
它当前认为任务进展到哪里？
它是否还在执行原始目标？

你的 Task Context 抽象正好可以解决这个问题。

⸻

9. 最后给这个 idea 一个更准确的定位

我会这样定义它：

Task Context 是 execution agent 在某一执行时刻进行决策和行动所需的结构化任务状态。它由事件日志、计划、权限、工具结果、工作区状态、用户目标和执行进度共同构建，是上下文治理、prompt 渲染、审计回放和失败恢复的共同锚点。

更短一点：

Task Context 是 execution agent 的工作记忆结构，不是聊天历史，也不是简单 prompt。

这个方向非常值得继续做，而且我认为它比“单纯做 RAG”更接近 agent 应用真正的核心。