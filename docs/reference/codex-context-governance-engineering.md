# Codex 的上下文治理工程：从 Agent Loop 到可观测性

本文基于 OpenAI 公开文档与工程抽象整理，不假设 Codex 未公开的内部实现。更准确地说，本文讨论的是：**像 Codex 这样的代码 Agent，在工程上如何管理“模型每一轮应该看到什么”。**

## 摘要

Codex 这类 Agent 应用的核心难点，不只是“让模型会写代码”，而是让模型在长任务中持续看到正确的上下文：当前目标、项目规范、相关文件、工具结果、测试反馈、权限边界、历史计划、被压缩后的任务状态等。

LLM 有自己的 context window，但 Agent 应用的 context 是另一层东西。LLM context window 是模型一次推理能接收的 token 上限；Agent context 则是应用层维护的工作状态、文件证据、工具轨迹、任务计划、权限信息和历史记忆。Codex 每一轮并不是把所有内容都交给模型，而是经过筛选、排序、压缩、注入，最终组装成一次 Responses API 请求。

因此，Codex 的核心抽象不是简单的 ReAct 文本模板，而是：

structured tool calls

+ agent loop

+ context assembly

+ sandbox / approval

+ skills progressive disclosure

+ compaction

+ hooks / observability

上下文治理正是 Agent 从“能调用工具”走向“能稳定完成任务”的关键工程层。

## 1. Codex 的核心抽象：结构化 Tool Call Agent Loop

很多人会把 Agent 理解成 ReAct：

Thought → Action → Observation → Thought → Action → Observation

这个理解在行为模式上没有错。Codex 确实会经历“思考、调用工具、观察结果、继续下一步”的循环。但从工程抽象上看，Codex 更接近 **structured tool calls + agent loop**，而不是经典的纯文本 ReAct prompt。

OpenAI 关于 Codex agent loop 的文章说明，Codex CLI 会向 Responses API 发送请求来驱动模型推理；请求的核心部分包括 instructions、tools 和 input。其中 tools 是符合 Responses API schema 的工具定义，可以包含 Codex CLI 提供的工具、Responses API 工具，以及用户通过 MCP server 提供的工具。Codex 还会把模型返回的 output items、工具调用结果等继续放入后续请求中，形成循环。

可以把 Codex 的 agent loop 抽象成下面几步：

1. Assemble context

组装本轮模型输入：系统/开发者指令、用户任务、工具定义、项目文档、skills metadata、环境信息、历史状态等。

2. Call model

调用 LLM。模型可能返回自然语言，也可能返回结构化 tool call。

3. Execute tool

Codex harness 执行工具调用，例如读文件、改文件、运行 shell、调用 MCP 工具、执行测试等。

4. Observe result

工具结果回到 agent runtime，成为下一轮 context 的候选内容。

5. Update state

更新计划、diff、approval 状态、错误日志、测试结果、任务摘要等。

6. Continue or stop

如果任务未完成，继续下一轮；如果完成，输出总结、diff、风险和验证结果。

7. Compact when needed

当上下文变长，触发压缩，把长历史转换成更小但仍保留关键状态的上下文。

所以 Codex 不是一次性 prompt，而是一个持续运行的控制循环。

## 2. 为什么需要上下文治理？

因为 Agent 的失败经常不是模型“不知道怎么做”，而是模型在某一轮没有看到正确的信息。

对一个 coding agent 来说，任务状态会不断膨胀：

用户最初目标

+ 当前 repo 状态

+ AGENTS.md / 项目规则

+ 已读文件

+ 当前 diff

+ 测试结果

+ 报错日志

+ 工具调用历史

+ 历史计划

+ 审批记录

+ skill 指令

+ 压缩摘要

+ 用户后续补充要求

如果全部塞进模型，会出现几个问题：

1.  **成本和延迟上升**：上下文越长，请求越慢、越贵。

2.  **注意力被稀释**：模型看到更多 token，不等于更理解任务。

3.  **旧信息污染当前判断**：已经废弃的计划、旧错误、旧文件状态可能干扰模型。

4.  **关键上下文被挤出窗口**：长历史可能挤掉真正重要的当前报错或接口定义。

5.  **流程约束容易失效**：skill、AGENTS.md、审批规则如果没有被正确注入或持续保留，模型后续可能偏离 workflow。

6.  **任务重演困难**：如果没有记录“为什么这些上下文进入本轮模型”，后续即使 workspace 一致，也无法解释 Agent 为什么做出当时的选择。

所以，上下文治理不是“把 prompt 写好一点”，而是 Agent runtime 的核心职责：

每一轮都决定：什么应该被模型看到，什么应该被压缩，什么应该被丢弃，什么应该被隐藏但仍影响模型。

## 3. Agent 应用上下文与 LLM 上下文的区别

这里要区分两个概念。

### LLM context window

LLM context window 是模型一次推理能接收的最大 token 容量。它是模型能力边界。

例如一个模型可能支持 128k、400k、1M token。但这只是“物理上限”，不代表 Agent 每次都会把这么多内容喂给模型。

### Agent context

Agent context 是应用层维护的任务工作状态。它包括：

conversation transcript

plan history

tool call trace

workspace snapshot

file snippets

diff

test output

skills

project instructions

approval state

sandbox state

compacted state

persistent memory

这些内容不一定每一轮都进入 LLM。Agent 会根据任务阶段、token budget、工具结果、当前错误、skill 触发情况来选择其中一部分。

因此更准确的关系是：

Agent context 是候选工作状态。

LLM context 是本轮实际送入模型的输入窗口。

Context assembly 是从 Agent context 到 LLM context 的选择与压缩过程。

Codex 的 resume 功能也体现了这一点：恢复运行时会保留原始 transcript、plan history 和 approvals，使 Codex 能在新指令下使用先前上下文。  这些信息属于 Agent 应用层状态，但每一轮具体怎么进入模型，还要经过 context assembly。

## 4. 哪些内容会进入 Codex 的上下文？

根据公开文档和工程推断，Codex 的上下文来源大概可以分成十类。

| **上下文类型**             | **进入时机**                       | **用户是否明确感知**                       | **作用**                              |
|----------------------------|------------------------------------|--------------------------------------------|---------------------------------------|
| 用户当前请求               | 每轮用户输入时                     | 明确可见                                   | 定义当前任务目标                      |
| 系统/开发者指令            | 会话初始化、权限变化、配置变化时   | 通常不完整可见                             | 约束模型行为、角色、边界              |
| 工具定义                   | 每轮模型调用时作为 API 工具 schema | 通常隐藏                                   | 告诉模型能调用哪些工具                |
| 环境信息                   | 会话开始、cwd/shell 等环境变化时   | 部分可见                                   | 告诉模型当前运行目录、shell、环境限制 |
| AGENTS.md / 项目规则       | 会话初始化或进入项目目录时         | 文件本身可见，注入过程未必可见             | 提供项目长期约束                      |
| Skill metadata             | 会话初始化或 skill 列表刷新时      | 通常不作为普通消息展示                     | 帮助模型判断是否触发 skill            |
| 完整 SKILL.md              | skill 被显式或隐式选择后           | 用户可打开文件，但注入过程未必可见         | 给模型任务专用 workflow               |
| 文件片段 / repo 内容       | 模型决定读取文件或 runtime 检索后  | 工具调用通常可见                           | 提供代码事实依据                      |
| 工具结果 / shell 输出      | 每次工具调用后                     | 通常可见                                   | 形成 Observation，驱动下一步          |
| 压缩摘要 / compaction item | 上下文过长时                       | 摘要可能可见，opaque compaction 通常不可读 | 保留历史状态，降低 token 压力         |

Codex agent loop 的公开说明提到，初始 prompt 会包含 AGENTS.md / AGENTS.override.md 等项目指导内容，也会包含 skills 相关的短说明和 skill metadata；请求结构中还包含 instructions、tools 和 input。

## 5. Skill 是如何进入上下文的？

Skill 是理解 Codex 上下文治理的一个好例子。

Codex 的 skill 不是一开始把所有内容都塞进模型，而是采用 **progressive disclosure**。公开文档说明：Codex 初始只把每个 skill 的 name、description 和文件路径放进上下文；只有当 Codex 决定使用某个 skill 时，才加载完整 SKILL.md。此外，初始 skill 列表有预算限制：大约占模型上下文窗口的 2%，或者在未知窗口时限制在 8,000 字符左右；如果 skill 太多，会优先缩短描述，甚至省略部分 skill。

这说明 skill 的进入机制分为两阶段：

阶段 1：轻量索引进入上下文

- name

- description

- path

阶段 2：任务匹配后加载完整 workflow

- SKILL.md instructions

- references

- scripts

- assets

这正是上下文治理的典型模式：

先让模型知道“有哪些能力可能可用”，但不立即加载全部细节；等任务真的需要时，再展开完整上下文。

## 6. 哪些上下文用户能感知，哪些会被隐藏？

Agent 应用的上下文不是全部暴露给用户的。

可以分成三类。

### 6.1 用户明确感知的上下文

这类内容通常会出现在 UI、终端 transcript 或 diff 中：

用户输入

assistant 输出

工具调用

shell 命令

shell 输出

文件 diff

审批请求

测试结果

计划更新

这些内容是用户理解 Agent 工作过程的主要入口。

### 6.2 用户可追溯但不一定直接感知的上下文

这类内容用户可以通过文件或配置找到，但不一定知道它是否、何时、以何种形式进入了模型：

AGENTS.md

SKILL.md

项目配置

hooks 配置

被读取的文件内容

MCP server 提供的工具列表

例如用户知道项目里有 AGENTS.md，但未必知道 Codex 本轮实际注入了哪些段落、是否被截断、是否被压缩。

### 6.3 对用户隐藏或不可读的上下文

这类内容对模型或 runtime 有用，但普通用户通常看不到完整形式：

base instructions

developer instructions

tool schema

internal item ordering

compaction item

opaque encrypted content

缓存状态

模型内部 latent state

OpenAI 的 compaction 文档说明，server-side compaction 会在上下文超过阈值时运行，返回的 compaction item 会携带后续需要的关键状态和 reasoning，但它是 opaque 的，并不打算让人类解释。

这说明 Agent 可观测性如果只展示聊天记录，是远远不够的。真正重要的是：**哪些隐藏上下文影响了模型行为**。

## 7. 上下文如何被筛选？

Codex 这类 Agent 的上下文筛选大概率不是纯硬编码，也不是完全交给模型自由发挥，而是混合机制。

可以分成四层。

### 第一层：确定性规则

这部分由 runtime / harness 控制：

token budget

role priority

tool schema

sandbox mode

approval policy

当前工作目录

AGENTS.md 搜索路径

skill metadata 预算

context compaction threshold

例如 Codex 的公开文章说明，初始 prompt 中的 item 带有 role，优先级从 system、developer、user、assistant 递减；请求里包括 instructions、tools、input。

这类规则负责“边界”和“格式”。

### 第二层：检索与启发式

这部分可以包括：

最近修改文件

当前 git diff

报错日志中的路径

grep / ripgrep 结果

依赖关系

文件名匹配

目录结构

测试失败位置

这些机制不一定需要 LLM。它们负责生成候选上下文。

### 第三层：LLM 语义判断

LLM 参与判断：

这个 skill 是否相关？

当前该读哪个文件？

工具结果说明了什么？

这个错误是否与刚才的 diff 有关？

现在应该继续修改，还是先跑测试？

用户是在要求评估，还是要求执行？

这类判断很难靠硬编码完成。

### 第四层：验证与 gate

上下文选择之后，还需要验证：

mandatory context 是否被包含？

是否漏掉 AGENTS.md？

是否跳过 skill 要求的检查？

是否在没有权限时尝试写文件？

是否应当请求用户确认？

Codex 的 sandbox 和 approval 是这类治理的边界机制。官方文档说，sandbox 定义 Codex 能在受限环境中自主做什么，例如能修改哪些文件、是否能访问网络；approval policy 则决定什么时候必须停下来请求确认。

## 8. 上下文如何被压缩？

上下文压缩的目的不是“缩短聊天记录”，而是：

在保留后续任务所需状态的同时，释放 context window。

普通摘要追求“概括全文”；Agent 压缩追求“保留继续执行所需的任务状态”。

一个好的 Agent 压缩结果应该保留：

当前目标

已完成步骤

未完成步骤

关键决策

已废弃方案

当前 diff

失败测试

重要文件

用户约束

审批状态

风险点

下一步计划

OpenAI 的 compaction 文档说明，compaction 用于支持 long-running interactions，通过减少上下文大小同时保留后续 turn 需要的状态，来平衡质量、成本和延迟；server-side compaction 可以在 token count 超过阈值时自动运行。

Codex agent loop 的文章也提到，早期实现需要用户手动 /compact，之后 Responses API 支持 /responses/compact endpoint，返回可以替代之前 input 的 items；Codex 现在会在超过 auto_compact_limit 时自动使用该机制。

这说明 Codex 的上下文压缩不是简单的“把历史总结成一段话”。它已经成为 Agent loop 的基础设施。

## 9. LLM API 最终接收的上下文是什么样的？

从开发者视角看，最终送给 LLM 的不是一个纯文本 prompt，而是一个结构化请求。

抽象成伪代码，大概类似：

{

"model": "gpt-5.5",

"instructions": "... system/developer instructions ...",

"tools": [

{

"type": "function",

"name": "shell",

"description": "Run a shell command..."

},

{

"type": "function",

"name": "read_file",

"description": "Read file content..."

},

{

"type": "mcp_tool",

"name": "figma.get_node"

}

],

"input": [

{

"role": "user",

"content": "Fix the failing test in the auth module."

},

{

"role": "user",

"content": "\<environment_context>cwd=..., shell=...\</environment_context>"

},

{

"role": "developer",

"content": "\<project_instructions>...\</project_instructions>"

},

{

"role": "developer",

"content": "\<skills>name, description, path...\</skills>"

},

{

"role": "assistant",

"content": "Plan: inspect failing test..."

},

{

"type": "function_call_output",

"call_id": "...",

"output": "pytest failed at tests/test_auth.py::test_refresh_token"

},

{

"type": "compaction",

"encrypted_content": "..."

}

]

}

这不是 Codex 的真实内部 JSON，只是工程抽象。核心点是：LLM API 接收的是 **instructions + tools + input items**，而不是用户在终端里看到的一段纯文本。OpenAI 的 Codex agent loop 文章也强调，终端用户并不是逐字指定最终 prompt；Responses API 会把请求中的不同输入类型结构化成模型消费的 prompt item 列表。

## 10. 为什么上下文治理也需要 LLM 参与？

因为上下文选择本质上是语义问题，而不是纯规则问题。

例如用户说：

04 layout 和原始静态图差很多，帮我判断是不是出了问题。

硬编码可以识别一些关键词：

04

layout

static image

Figma

但真正要判断的是：

这是评估任务还是修改任务？

是否需要触发 Figma skill？

原始静态图是 canonical reference 还是旧稿？

应该先看 frame，还是先看 design system？

是否允许修改，还是只输出审计报告？

这些判断需要模型理解任务意图、上下文关系和当前阶段。

但是，完全交给 LLM 也不可靠。LLM 可能漏看关键文件、过度读取无关文件、被旧摘要污染、忘记 workflow、跳过测试。

所以合理架构是：

硬规则生成边界

↓

检索系统生成候选集

↓

LLM 做语义选择

↓

runtime 做 token budget 和排序

↓

hooks / tests / approval 做验证

也就是说：

LLM 负责“语义注意力分配”，工程系统负责“边界、预算和验证”。

## 11. 可观测性与上下文治理的关系

Agent 可观测性不是简单记录聊天记录，而是要记录 context governance trace。

普通日志记录的是：

用户说了什么

模型说了什么

工具执行了什么

文件改了什么

上下文治理需要进一步记录：

本轮有哪些候选上下文？

哪些进入了模型？

哪些被排除了？

为什么排除？

哪个 skill 被触发？

AGENTS.md 哪些规则被注入？

summary 是从哪些历史 step 压缩来的？

compaction 发生在什么时候？

tool result 如何改变任务状态？

Codex hooks 正是这一层的重要扩展点。公开文档说明，hooks 可以把自定义脚本注入 Codex lifecycle，用来把 conversation 发送到 logging / analytics engine、扫描 prompt 防止误贴 API key、自动总结对话生成持久记忆、在会话 turn 停止时运行 validation check、根据目录定制 prompting 等。

这些能力都和上下文治理直接相关：

logging / analytics

→ 记录上下文进入过程

prompt scan

→ 防止敏感信息进入上下文

persistent memory

→ 把历史变成长期上下文

validation check

→ 检查 Agent 是否跳过 workflow gate

directory-specific prompting

→ 根据项目区域切换上下文策略

所以可观测性不是附属功能，而是上下文治理的前提。

没有可观测性，就无法回答：

Agent 为什么看了这些文件？

为什么没有看另一个文件？

为什么触发了这个 skill？

为什么在这个时刻 compact？

为什么它认为任务完成了？

## 12. 为什么上下文治理让通用 Agent 很难成立？

通用 Agent 的难点不是“会不会调用工具”，而是“不同任务需要完全不同的上下文秩序”。

### 编码任务

编码任务关心：

相关文件

接口定义

测试结果

错误日志

git diff

依赖关系

项目规范

上下文优先级通常是：

当前 failing test

> 当前修改文件

> 相关接口

> 项目规范

> 历史讨论

### 研究任务

研究任务关心：

来源可信度

证据链

时间新旧

争议观点

引用关系

反例

上下文优先级是：

高可信来源

> 最新证据

> 直接引用

> 反方观点

> 历史背景

### 设计任务

设计任务关心：

用户路径

视觉层级

组件系统

交互状态

设计 token

品牌规范

验收标准

上下文优先级又变成：

产品目标

> 当前页面状态

> 组件系统

> 视觉一致性

> 历史设计决策

### 运维任务

运维任务关心：

当前告警

最近变更

日志时间线

指标异常

依赖服务

回滚方案

影响范围

上下文优先级是：

当前影响

> 最近变更

> 错误日志

> 关键指标

> 历史事故

这说明：

Runtime 可以通用，但 context policy 很难完全通用。

一个真正可靠的 Agent 系统，可能不是“一个无所不能的通用 Agent”，而是：

通用 agent runtime

+ 领域化 skill

+ 任务型 context policy

+ 专用 verifier

+ 可观测 trace

+ 人类确认节点

所以，通用 Agent 的瓶颈不是工具数量，而是上下文治理策略无法一刀切。

## 13. 从任务重演看上下文治理的重要性

如果要 replay 一个 Agent 任务，仅保存 workspace 和 LLM 输入输出并不够。

因为 LLM 输入本身已经是上下文治理的结果。

真正可重演的 Agent 任务，至少需要记录：

workspace snapshot

model version

tool schema

skill version

AGENTS.md version

context policy version

candidate context list

selected context list

rejected context list

compression event

final prompt hash

model output

tool call

tool result

state transition

否则会出现：

workspace 一致

但 context selection 不一致

context selection 一致

但 compaction 不一致

compaction 一致

但 tool result 不一致

tool result 一致

但模型输出不一致

所以任务重演的核心不是 workspace replay，而是 **context replay**。

这也是 Agent 应用可观测性未来会越来越重要的原因：它不仅是 debug 工具，也是模型训练、任务型 Agent 优化、context selector 训练、verifier 训练的重要数据来源。

## 14. Codex 使用的是专有模型，还是通用 LLM？

从公开文档看，Codex 推荐使用的是 OpenAI 为 coding、tool use、agentic workflow 优化过的模型，例如 gpt-5.5、gpt-5.4、gpt-5.4-mini、gpt-5.3-codex 等；其中 gpt-5.4 被描述为结合 GPT-5.3-Codex 的编码能力与更强 reasoning、tool use 和 agentic workflows。

但 Codex 也可以指向任何支持 Chat Completions 或 Responses API 的模型和供应商。

这说明：

Codex 的 agent harness 不完全等于某一个专有模型。

但最佳体验依赖经过 coding / tool-use / agentic workflow 优化的模型。

上下文治理本身也不是纯模型能力，而是：

harness 规则

+ LLM 语义判断

+ tool schema

+ sandbox / approval

+ skills

+ compaction

+ hooks

+ observability

共同完成。

## 15. 工程结论：上下文治理是 Agent 的真正中间层

可以把 Codex 类 Agent 分成六层：

1. Model Layer

LLM，本身有 context window 和 reasoning/tool-use 能力。

2. API Layer

Responses API，承载 instructions、tools、input、output items、compaction items。

3. Agent Runtime Layer

agent loop、tool execution、state update、context assembly。

4. Governance Layer

skills、AGENTS.md、sandbox、approval、hooks、policy。

5. Observability Layer

transcript、tool trace、context trace、compaction trace、approval trace。

6. User Workspace Layer

repo、文件、测试、CI、Figma、MCP、外部系统。

其中最容易被低估的是第 3 到第 5 层。

LLM 决定 Agent 能力上限，但上下文治理决定 Agent 稳定性上限。

## 结语

Codex 的价值不只是“模型会写代码”，而是它把模型放进了一个工程化 agent loop：

结构化输入

→ 工具调用

→ 沙箱执行

→ 结果观察

→ 状态更新

→ 上下文压缩

→ workflow 约束

→ 可观测扩展

在这个循环里，上下文治理是核心问题：

什么进入模型？

什么时候进入？

以什么优先级进入？

如何压缩？

如何隐藏？

如何审计？

如何重演？

如何防止错误上下文污染模型？

所以，Agent 应用的竞争不只是模型能力竞争，也不是工具数量竞争，而是上下文治理能力的竞争。

一句话总结：

**LLM context 是模型一次能看到多少；Agent context governance 是决定模型每一轮应该看到什么。前者决定容量，后者决定可靠性。**
