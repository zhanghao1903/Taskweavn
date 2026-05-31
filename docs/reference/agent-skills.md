# Agent Skills：从上下文包到可执行工作流

## 以 OpenAI Codex 与 Anthropic Claude 为例

### 摘要

Agent Skill 是一种把“专业知识、操作步骤、项目约束、脚本和参考资料”打包给 AI Agent 按需使用的工程机制。它不是模型微调，也不是一个传统意义上的 API 工具，而是一种**可发现、可加载、可复用、可版本化的上下文与工作流封装格式**。在 Codex 和 Claude 中，skill 的核心设计都是 **progressive disclosure**：启动时只暴露 name 和 description，当任务匹配时再加载完整 SKILL.md，必要时继续读取引用文件或执行脚本。OpenAI 的 Codex 文档明确说，skill 用于把 instructions、resources 和 optional scripts 打包给 Codex，使其更可靠地遵循某个 workflow；Anthropic 也把 Agent Skills 定义为可被 Claude 自动使用的模块化能力，包含 instructions、metadata 和可选资源。

但 skill 不是硬状态机。它能显著提高 Agent 按流程执行的概率，却不能单独保证模型永远不跳步、不误用工具、不遗忘约束。真正可靠的 agent workflow，通常需要 skill 与 sandbox、approval、rules、hooks、测试、CI 和人工 review 共同构成约束系统。

## 1. 什么是 Skill

Agent Skill 可以理解为“给 Agent 用的、按需加载的 SOP 包”。

一个普通 prompt 是一次性指令：

请按我们的发布流程生成 release notes。

一个 skill 则是把这套发布流程沉淀成目录：

release-notes/

SKILL.md

references/

changelog-format.md

scripts/

collect_commits.py

assets/

release-template.md

从用户体验看，skill 让你不用每次都重复说明“我们团队怎么做这件事”。从系统设计看，skill 是一种上下文治理机制：先把所有可用 skill 的轻量元数据放进 Agent 的可见范围，真正需要时再加载完整说明和资源。Agent Skills 开放标准把 skill 定义为一个包含 SKILL.md 的文件夹，SKILL.md 至少包含 name、description 和正文 instructions，也可以附带 scripts、references、assets 等资源。

因此，skill 的本质不是“让模型多了一个原生能力”，而是让通用 Agent 在特定任务中拥有更好的：

- 任务触发条件

- 操作流程

- 项目上下文

- 工具使用方法

- 验收标准

- 可执行脚本

- 输出格式

- 常见错误规避

它更像“给新人看的 onboarding guide + runbook + checklist + validator scripts”，而不是一个 function call。

## 2. Skill 的组成部分：Codex 与 Claude 对比

Codex 和 Claude 的 skill 结构非常接近，因为二者都采用了 Agent Skills 这种文件系统式封装方式。

### 2.1 通用结构

典型 skill 目录如下：

my-skill/

SKILL.md # 必需：metadata + instructions

scripts/ # 可选：可执行代码

references/ # 可选：参考文档

assets/ # 可选：模板、图片、数据文件等资源

SKILL.md 通常包含 YAML frontmatter 和 Markdown 正文：

---

name: data-quality-review

description: Use this skill when reviewing data pipeline changes, validating schema migrations, checking data quality gates, or preparing a data release report.

---

# Data Quality Review

## Workflow

1. Inspect changed schema files.

2. Read the data quality contract.

3. Run validation scripts.

4. Summarize failures and required fixes.

5. Do not approve release if required gates fail.

Agent Skills 规范要求 name 和 description 为必填字段：name 有长度和命名限制，description 应描述 skill 做什么以及什么时候使用；正文没有固定格式，但推荐包含步骤、输入输出示例和边界情况。

### 2.2 Codex 的 Skill 组成

Codex 官方文档给出的 skill 目录包括：

my-skill/

SKILL.md # Required: instructions + metadata

scripts/ # Optional: executable code

references/ # Optional: documentation

assets/ # Optional: templates, resources

agents/

openai.yaml # Optional: appearance, policy, dependencies

Codex 的 agents/openai.yaml 是一个 Codex 侧的扩展配置，可以设置 UI metadata、invocation policy 和工具依赖。例如 allow_implicit_invocation: false 可以关闭隐式触发，只允许用户显式 $skill 调用。Codex 还允许在这个文件里声明 MCP tool dependencies，让 skill 和外部工具集成得更顺滑。

Codex 对 skill 的保存位置也有多层 scope：

REPO .agents/skills

USER ~/.agents/skills

ADMIN /etc/codex/skills

SYSTEM Codex 内置 skills

对于仓库内 skill，Codex 会从当前工作目录一路向上扫描 .agents/skills，直到 repository root；如果两个 skill 使用同一个 name，Codex 不会合并它们，而是都可能出现在选择器里。

### 2.3 Claude 的 Skill 组成

Claude 官方文档把 Agent Skill 描述为可自动使用的模块化能力，每个 skill 包含 instructions、metadata 和可选资源，例如 scripts 和 templates。Claude 的核心目录结构同样是 SKILL.md 加附加文件。Claude 文档还明确把 skill 内容分成三层加载：metadata 总是加载，SKILL.md 正文在触发后加载，资源和代码按需加载。

Claude 的一个重要特点是它的 VM / filesystem 环境。Anthropic 文档说明，Claude 可以在虚拟机里访问文件系统，因此 skill 可以像“给新同事的 onboarding guide”一样组织为目录、说明、代码和参考材料。

### 2.4 Codex 与 Claude 的差异概览

| **维度**      | **Codex**                                                | **Claude**                                           |
|---------------|----------------------------------------------------------|------------------------------------------------------|
| 核心文件      | SKILL.md                                                 | SKILL.md                                             |
| 必填 metadata | name, description                                        | name, description                                    |
| 可选资源      | scripts/, references/, assets/                           | scripts, templates, references 等                    |
| 触发方式      | 显式 $skill / /skills，或根据 description 隐式触发      | Claude 根据请求相关性自动使用                        |
| 额外配置      | agents/openai.yaml 可设置 UI、policy、dependencies       | Claude API / Claude Code / claude.ai 各有配置方式    |
| 分发方式      | 本地目录；可打包为 Codex plugin                          | Claude Code 本地 skill；API 上传；claude.ai zip 上传 |
| 运行环境      | Codex CLI / IDE / Codex app，结合 sandbox、approval、MCP | Claude VM / Claude Code / Claude API / claude.ai     |

共同点是：skill 不是单次 prompt，而是可复用、可按需加载的上下文与资源包。

## 3. Skill 是如何被发现和加载的

Skill 的发现和加载遵循 progressive disclosure，也就是“逐步披露”。

### 3.1 第一阶段：Discovery，只加载元数据

Agent 启动或会话初始化时，不会把所有 skill 的完整内容都塞进上下文。它先扫描 skill 目录，只读取每个 skill 的轻量元信息：

name

description

file path

Codex 文档明确说，Codex 一开始只使用每个 skill 的 name、description 和文件路径；只有当它决定使用某个 skill 时，才读取完整 SKILL.md。Codex 还会把可用 skill 初始列表放入 context 中，让模型可以选择合适的 skill；为了避免挤占 prompt，这个列表会被限制在大约模型上下文窗口的 2%，或者在未知上下文大小时限制在 8,000 字符左右。skills 过多时，Codex 会先缩短 description，极端情况下部分 skill 可能被省略并显示 warning。

Claude 的官方文档也描述了类似机制：Claude 启动时加载 skill YAML frontmatter 中的 name 和 description，并把这些 metadata 放入 system prompt；这让 Claude 知道 skill 存在以及何时使用，而不用把完整 skill 占进上下文窗口。

### 3.2 第二阶段：Activation，任务匹配后加载

### SKILL.md

当用户任务和某个 skill 的 description 匹配时，Agent 才读取完整 SKILL.md。

在 Codex 中，skill 可以通过两种方式激活：

1. 显式调用：用户在 prompt 里直接提到 skill，CLI/IDE 中可以用 /skills 或 $ mention。

2. 隐式调用：Codex 判断用户任务匹配某个 skill 的 description。

Codex 文档特别强调，隐式匹配依赖 description，所以 description 要简洁、边界清晰，并把关键触发词放在前面，以便 description 被截断时仍然能匹配。

Agent Skills 的 description 优化指南也指出，description 是 Agent 判断是否加载 skill 的主要机制；如果 description 过窄，应该触发时不会触发，如果过宽，则会误触发。

### 3.3 第三阶段：Execution，按需加载引用文件和脚本

完整 SKILL.md 被加载后，Agent 会根据正文 instructions 执行任务。如果正文里引用了额外文件，例如：

For API error handling, read references/api-errors.md.

For migration validation, run scripts/validate_migration.py.

Agent 会按需读取这些 reference 文件或执行 scripts。Anthropic 的工程博客举了 PDF skill 的例子：Claude 先读取 pdf/SKILL.md，再根据任务需要读取同目录下的 forms.md。

Agent Skills 规范也明确把加载分为三层：

1. Metadata：启动时加载 name 和 description

2. Instructions：skill 激活时加载完整 SKILL.md

3. Resources：scripts / references / assets 按需加载

规范还建议将 SKILL.md 保持在 500 行以内，把详细参考资料拆到独立文件中，并用相对路径从 SKILL.md 引用。

## 4. Skill 是如何生效的：Codex 如何让模型尽量按步骤走

Skill 的生效不是靠“代码强制执行每一步”，而是靠多层机制叠加。

### 4.1 第一层：模型遵循上下文中的 instructions

当 Codex 选择某个 skill 后，完整 SKILL.md 会进入当前任务上下文。此后模型在生成计划、选择工具、编辑文件、运行命令和输出报告时，会把 skill 里的步骤当作当前任务的操作规程。

这就是 skill 最基础的生效方式：

用户任务

↓

Codex 判断 skill relevant

↓

读取 SKILL.md

↓

模型把 SKILL.md 当作本轮任务的流程约束

↓

生成工具调用 / 文件修改 / 验收报告

这种方式类似给模型加了一份“当前任务操作手册”。它能强烈影响模型行为，但不是传统程序里的硬控制流。

### 4.2 第二层：Codex agent loop 持续把状态反馈给模型

Codex 不是一次性问答系统，而是 agent loop。OpenAI 的 Codex agent loop 文章说明：模型要么输出最终回复，要么请求工具调用；如果请求工具调用，Codex harness 执行工具，并把工具输出追加到原 prompt，再次查询模型；这个过程重复，直到模型不再请求工具调用而输出 assistant message。

这意味着 skill 的 instructions 会参与多轮循环：

Skill instructions

+ 用户任务

+ 环境信息

+ 工具定义

+ 文件读取结果

+ shell 输出

+ diff / test output

↓

模型决定下一步

↓

工具调用

↓

工具结果追加回上下文

↓

模型继续执行

如果 skill 写了：

1. Do not edit before inspection.

2. Run scripts/validate.py after edits.

3. If validation fails, fix and rerun.

4. Final answer must include changed files and unresolved risks.

Codex 在每次重新查询模型时，都有机会继续利用这份流程说明和上一步工具结果来决定下一步。OpenAI 的 agent loop 文章还说明，上一轮模型输出、function call 和 function call output 会作为下一次 Responses API 请求的 input 项继续存在；因此工具调用结果会成为后续推理的一部分。

### 4.3 第三层：脚本把软流程变成可验证步骤

Skill 里最强的部分不是“请遵守流程”这类自然语言，而是可以运行的脚本和检查器。

例如：

````markdown
## Validation

After changing migration files, run:

```bash

python scripts/validate_migration.py --changed-only
```

If validation fails, do not mark the task complete.
````

这比单纯写“请检查 migration 是否正确”更可靠，因为它把抽象要求变成了具体命令和可观察输出。Agent Skills 的 scripts 指南也建议：复杂命令应移入经过测试的 `scripts/`，脚本应自包含、错误信息清晰、输出结构化，方便 Agent 理解和自我修复。 [oai_citation:15‡Agent Skills](https://agentskills.io/skill-creation/using-scripts)

### 4.4 第四层：Sandbox、approval、rules、hooks 提供硬边界

Codex 还有 skill 之外的控制机制。Sandbox 定义 Codex 能在什么边界内自主运行，例如能否写文件、是否能联网、能否访问工作区外路径；approval policy 决定什么时候必须停下来请求确认。OpenAI 的 sandbox 文档说明，sandbox 是让 Codex 在没有完全访问机器权限的情况下自主工作的边界，approval 则决定越界时是否需要停下请求许可。 [oai_citation:16‡OpenAI Developers](https://developers.openai.com/codex/concepts/sandboxing)

Rules 可以控制 Codex 在 sandbox 外能运行哪些命令，支持 `allow`、`prompt` 和 `forbidden` 三种决策；当多条规则匹配时，Codex 采用更严格的结果，即 `forbidden > prompt > allow`。 [oai_citation:17‡OpenAI Developers](https://developers.openai.com/codex/rules)

Hooks 则允许在 Codex 生命周期中运行确定性脚本，例如 `PreToolUse`、`PostToolUse`、`PreCompact`、`Stop` 等。官方 Hooks 文档把它定义为“Run deterministic scripts during the Codex lifecycle”。这类机制可以在工具调用前后做检查、阻断、记录或追加验证。 [oai_citation:18‡OpenAI Developers](https://developers.openai.com/codex/hooks)

因此，Codex 让 skill 生效的正确理解是：

```text

Skill 负责告诉模型“应该怎么做”

Agent loop 负责让模型在执行过程中不断获得反馈

Scripts 负责把部分步骤变成可执行检查

Sandbox / approvals / rules / hooks 负责提供工程硬边界

Tests / CI / review 负责最终验收

Skill 本身不是硬约束，但可以把 Agent 引导到一套硬约束流程里。

```
## 5. Skill 内容在 Codex Agent Loop 中如何流转，以及何时消亡

这是理解 skill 的关键：skill 内容不是永久写入模型，也不会改变模型权重。它只是进入某一次会话、某一次 turn 或某段上下文窗口的输入材料。

### 5.1 启动时：只有 metadata 在初始 context 里

Codex 启动时会扫描 skill，并把初始 skill 列表放入 context。这个列表包含 name、description 和路径，但不包含所有 SKILL.md 正文。Codex 对这个初始列表设置上下文预算；当 skill 太多时，会缩短 description，甚至省略部分 skill。

此时上下文中有的是：

```text
Available skills:

- name: release-notes

description: Use this skill when...

path: ...

- name: figma-governance

description: Use this skill when...

path: ...
```

没有的是：

完整 release-notes/SKILL.md 正文

完整 figma-governance/SKILL.md 正文

references/ 下的所有文件

scripts/ 的源码全文

### 5.2 触发时：完整

### SKILL.md

### 进入当前任务上下文

当 Codex 隐式或显式选择某个 skill 后，会读取完整 SKILL.md。从 agent loop 角度看，这部分内容会成为模型后续推理和工具调用的输入之一。OpenAI 的 Codex agent loop 文章说明，Codex 构建 prompt 时会把 instructions、tools、input 等内容组织成带 role 的项目；模型调用工具后，tool call 和 tool output 会被追加进后续请求。

可以把一次 skill 触发后的上下文简化成：

```text
system / developer instructions

sandbox / approval instructions

AGENTS.md / project guidance

available skill metadata

activated skill: SKILL.md body

user task

environment context

tool definitions

tool results so far
```

其中 SKILL.md body 不是模型参数的一部分，而是当前上下文窗口的一部分。

### 5.3 执行中：reference 和 script output 按需进入上下文

Skill 中引用的文件不会自动全部进入上下文。它们只有在 Agent 读取时才进入。

例如：

If validation fails, read references/error-codes.md.

只有当 Codex 判断需要处理 validation failure 时，才会读取这个文件。Anthropic 对 Claude 的描述同样是：skill 启动后可选读取 forms.md 等 bundled files，动态加载保证只有相关 skill 内容占用上下文窗口。

脚本则更特殊：Agent 不一定需要把脚本源码全文读进上下文。很多时候它只需要运行脚本，并把脚本输出读回来。这样可以把大量确定性逻辑留在文件系统和运行环境中，只把结果放入上下文：

```text
scripts/validate.py 源码

不一定进入上下文

python scripts/validate.py 的 stdout/stderr

会作为 tool output 进入后续上下文
```

这也是 skill 搭配 scripts 的价值：复杂逻辑不必全部消耗 context tokens。

### 5.4 多轮中：skill 内容会随 conversation history 保留一段时间

在同一个 Codex conversation/thread 内，历史消息、工具调用和工具结果会成为后续 prompt 的一部分。OpenAI 的 agent loop 文章说明，每次用户在已有 conversation 中发送新消息时，conversation history 会包含之前 turn 的 messages 和 tool calls；prompt 会随着 conversation 增长而增长。

因此，如果一个 skill 的 SKILL.md 在某个 turn 中被读取，它通常会在后续同一 thread 的上下文历史中保留一段时间，除非被压缩、裁剪或新 session 不再继承它。

可以理解为：

同一 thread 内：

已加载 skill 内容可能继续影响后续 turn

新 thread / 新 run：

只会重新从 metadata 开始

完整 SKILL.md 需要再次触发才会加载

### 5.5 上下文过长时：内容会被 compact，细节可能消亡

Codex 不可能无限保留所有上下文。OpenAI 的 agent loop 文章说明，随着工具调用和历史消息增长，prompt 会变长，最终可能耗尽 context window；Codex 的策略是在 token 数超过阈值时进行 compaction，用一个更小的 input 列表替换原来的 input，以保留对先前对话的代表性理解并释放上下文窗口。文章还提到现在 Codex 会自动使用 /responses/compact endpoint，在超过 auto_compact_limit 时压缩 conversation。

这对 skill 的生命周期很重要：

原始 SKILL.md 正文

↓

进入上下文

↓

参与若干轮 agent loop

↓

上下文过长

↓

compaction

↓

可能被总结为“当前任务正在按 X skill 的 workflow 执行”

↓

原始细节可能不再逐字存在

换句话说，skill 内容的“消亡”通常发生在以下场景：

1. 当前 turn 结束，且后续没有继续使用同一 thread

2. 新开 Codex run / 新 thread，需要重新触发 skill

3. 上下文窗口过长，被自动 compact

4. 工具结果、历史消息、文件内容等后来内容挤占了注意力

5. 初始 skill metadata 因 skill 太多而被缩短或省略

公开文档没有把“skill content GC”作为一个单独概念描述；但结合 Codex 的 progressive disclosure 和 agent loop context management，可以得出一个工程上更准确的结论：**skill 内容不是永久驻留的系统规则，而是在会话上下文中动态出现、参与推理、随历史增长而被压缩或随 session 结束而消失的上下文资产。**

## 6. Codex 让 Skill 生效的挑战：为什么 Skill 不能完全保证执行

Skill 的限制来自 LLM 和 agent loop 的共同特性。

### 6.1

### description

### 可能不触发或误触发

Skill 是否隐式触发高度依赖 description。如果 description 太泛，例如：

description: Helps with documents.

它可能误触发。如果太窄，例如：

description: Use only when user says "generate Q4 release note".

它可能漏掉“帮我整理这个版本变更说明”这类真实请求。Agent Skills description 指南明确指出，description 是触发的主要机制，过窄会导致不触发，过宽会导致错误触发。

此外，模型行为本身存在非确定性；同一个 query 多次运行，skill 触发结果可能不同。Agent Skills description 指南建议对触发 query 多次运行，计算 trigger rate。

### 6.2 上下文不是硬状态机

把流程写进 SKILL.md，不等于 Codex 内部变成：

for step in skill.steps:

execute(step)

真实情况更接近：

模型读到 skill

↓

模型理解 skill

↓

模型生成下一步 action

↓

harness 执行 action

↓

结果回到上下文

↓

模型继续判断

每一步都有概率性。长上下文、复杂工具输出、相互冲突的项目说明、用户临时要求，都可能影响模型对 skill 的遵循程度。

### 6.3 Skill 的权威等级有限

Codex 的 prompt 里有不同来源的内容，例如 system / developer / user / assistant。OpenAI 关于 Codex agent loop 的文章说明，初始 prompt 中每个 item 有 role，优先级从高到低是 system、developer、user、assistant。

Skill 通常是 Agent runtime 加载的任务指导，能影响模型，但它不是最高级别的不可违背平台规则。它还会和 AGENTS.md、用户请求、工具返回、当前环境等内容共同竞争上下文注意力。OpenAI 的 AGENTS.md 文档也说明，Codex 会按全局、项目、当前目录等层级拼接项目说明，较靠近当前目录的文件因为出现在后面而覆盖更早的 guidance。

### 6.4 Skill 太长会稀释注意力

Skill 一旦触发，完整 SKILL.md 会进入上下文；每个 token 都会和 conversation history、system context、工具结果和其他 active skill 竞争模型注意力。Agent Skills best practices 明确提醒：skill 激活后，完整 SKILL.md 会与历史和其他上下文一起进入 context window；应只加入 Agent 不知道且容易出错的内容。

过长、过泛、边界不清的 skill 可能反而降低可靠性。

### 6.5 脚本、工具和环境可能不可用

Skill 里写了：

python scripts/validate.py

并不意味着一定能成功运行。运行依赖于：

- 当前 agent 是否有 shell 权限

- sandbox 是否允许读取/写入相关路径

- Python / Node / uv / npx 是否安装

- 网络是否可用

- 脚本依赖是否可解析

- 当前目录是否正确

Agent Skills scripts 指南也建议 pin versions、声明 prerequisites，并在命令复杂时写成自包含脚本。

### 6.6 Compaction 可能让细节丢失

长任务中，Codex 可能会 compact conversation。Compaction 的目标是保留代表性理解并释放上下文窗口，但这不保证原始 SKILL.md 的每条细节都逐字保留。OpenAI 的 Codex agent loop 文章说明，compaction 会用更小的 input 列表替代旧 input，让 Agent 带着对先前内容的理解继续执行。

因此，重要约束不能只藏在长 skill 的中间段落里。真正关键的 gate 应该变成脚本、hooks、rules、CI 或明确的 checklist。

### 6.7 没有外部验证，模型可能“自认为完成”

如果 skill 只写：

Make sure the output is correct.

模型可能在没有真正验证的情况下给出完成报告。更可靠的写法是：

Run `pnpm test`.

Run `pnpm lint`.

Run `python scripts/validate_report.py output.md`.

Only report completion if all commands pass.

Codex best practices 也强调，不要只让 Codex 生成代码，还应该让它创建或更新测试、运行检查、确认结果并 review 工作。

## 7. 好的 Skill 应该是什么样的

好的 skill 不是“把所有知识都塞进 SKILL.md”，而是用最少上下文让 Agent 在关键节点做对。

### 7.1 好的 Skill 应完成的目标

一个高质量 skill 应该完成四件事：

1. 准确触发：相关任务会触发，不相关任务不触发。

2. 降低不确定性：告诉 Agent 在该领域最容易错在哪里。

3. 固化流程：把重复工作变成可执行步骤、检查点和输出模板。

4. 可验证：尽量把关键步骤变成脚本、测试、validator 或 checklist。

Codex best practices 建议每个 skill 聚焦一个工作，使用明确的输入输出和祈使步骤，并通过测试 prompts 验证 description 是否触发正确。

### 7.2 好的 Skill 包含什么

#### 1. 清晰的

#### description

好的 description 要写“什么时候使用”，而不只是写“这个 skill 是什么”。

差的写法：

description: Helps with Figma.

好的写法：

description: Use this skill when modifying or reviewing Plato Figma design files, including design system pages, tokens, components, screen states, layout acceptance, UX audit states, and component migration. Do not use for general frontend coding unless the task depends on Figma design governance.

Agent Skills description 指南建议使用 “Use this skill when…” 这种祈使表达，聚焦用户意图而不是内部实现，保持简洁，同时包含真实用户会说的触发场景。

#### 2. 明确的输入、输出和停止条件

例如：

## Inputs

- Target repository or file path

- Requested change

- Relevant issue / PR / design link if provided

## Outputs

- Files changed

- Commands run

- Validation result

- Risks and follow-up items

## Stop conditions

Stop and ask for clarification if:

- Target file cannot be identified

- Required credentials or environment variables are missing

- Validation script fails for reasons unrelated to your change

停止条件很重要，因为它能防止 Agent 在信息不足时“猜着做”。

#### 3. 分阶段 workflow

例如：

## Mandatory workflow

### Phase 1: Inspect

- Read relevant files.

- Identify current conventions.

- Do not edit yet.

### Phase 2: Plan

- Summarize intended changes.

- Identify risks.

- Choose validation commands.

### Phase 3: Execute

- Make the smallest necessary change.

- Avoid unrelated refactors.

### Phase 4: Validate

- Run tests and validators.

- Fix failures caused by your change.

### Phase 5: Report

- Summarize files changed, commands run, and unresolved risks.

Agent Skills best practices 推荐用 checklist、validation loop、plan-validate-execute 等模式来帮助 Agent 跟踪步骤并避免跳步。

#### 4. Gotchas

Gotchas 是 skill 里性价比最高的部分，因为它记录的是 Agent “合理推测但会猜错”的地方。

例如：

## Gotchas

- This repo uses pnpm, not npm.

- Do not edit generated files under src/generated/.

- The health endpoint only checks web server liveness; use /ready for DB readiness.

- Customer IDs are named user_id in DB, uid in auth service, and accountId in billing API.

Agent Skills best practices 也强调 gotchas 应该是具体纠错，而不是“handle errors appropriately”这类泛泛建议。

#### 5. 可执行 scripts

当步骤需要确定性时，写脚本比写自然语言更好：

scripts/

validate_schema.py

check_component_duplicates.py

generate_release_report.py

SKILL.md 中引用：

````markdown
## Validation

Run:

```bash

python scripts/validate_schema.py --changed-only
```

If it fails, fix the issue and rerun. Do not report success until it passes.
````

Agent Skills scripts 指南建议脚本要自包含、避免交互式 prompt、提供 `--help`、输出清晰错误信息，并尽量使用结构化输出。 [oai_citation:36‡Agent Skills](https://agentskills.io/skill-creation/using-scripts)

#### 6. 输出模板

例如：

````markdown

## Final report template

## Summary

[What changed]

## Files changed

- ...

## Validation

- Command: ...

- Result: pass / fail

## Risks

- ...

## Follow-up

- ...
````

模板比抽象描述更可靠，因为模型对具体格式的模仿能力通常强于对散文式要求的遵守。

#### 7. Evaluation cases

成熟 skill 应该有 evals：

```text

evals/

evals.json

files/

```
Agent Skills eval 指南建议用真实用户 prompt、预期输出和输入文件组成测试用例，并将 skill 运行结果与无 skill 或旧版本 skill 对比。

### 7.3 好的 Skill 不应该包含什么

好的 skill 不应该包含：

1. 模型本来就知道的常识

2. 大段背景介绍

3. 和触发任务无关的公司文档

4. 模糊口号：follow best practices、handle errors properly

5. 没有输入输出的抽象原则

6. 互相冲突的流程

7. 多个不相干任务混在一个 skill 里

8. 需要强制执行但没有脚本/规则/测试支撑的要求

9. 过多工具选项而没有默认路径

10. 把秘密、token、凭证、敏感内部数据硬编码进 skill

Agent Skills best practices 的核心建议是：加入 Agent 不知道且没有 skill 容易做错的内容；删除 Agent 已经能做对的普通常识。它还提醒，过度全面的 skill 可能让 Agent 难以提取相关内容并走上无效路径。

## 8. 一个推荐的 Skill 模板

下面是一份适合 Codex / Claude 类 Agent 使用的通用模板：

````markdown
---

name: example-workflow

description: Use this skill when [specific user intent], including [trigger cases]. Do not use when [near-miss cases].

---

# Example Workflow

## Goal

Help the agent perform [task class] consistently, safely, and verifiably.

## Inputs

- [Input 1]

- [Input 2]

- [Optional context]

## Outputs

- [Output artifact]

- [Validation result]

- [Final report]

## Mandatory workflow

### Phase 1: Inspect

- Read [specific files or references].

- Identify [required context].

- Do not modify files in this phase.

### Phase 2: Plan

- Propose the smallest safe change.

- Identify validation commands.

- Stop if [condition].

### Phase 3: Execute

- Make changes only in [allowed scope].

- Do not [forbidden action].

### Phase 4: Validate

Run:

```bash

python scripts/validate.py
```

If validation fails:

1.  Inspect the error.

2.  Fix the issue if it is caused by your change.

3.  Rerun validation.

4.  Do not report success until validation passes.

### Phase 5: Report

Use this structure:

## Summary

...

## Changed files

...

## Validation

...

## Risks

...

## Follow-up

...

## Gotchas

- [Concrete non-obvious fact]

- [Common model mistake]

- [Project-specific naming issue]

## Available references

- references/contract.md: Read when validating output shape.

- references/error-codes.md: Read only if validation returns an error code.

## Available scripts

- scripts/validate.py: Validates output.

- scripts/generate_report.py: Generates final report draft.
````

这个模板的重点不是“写得长”，而是让 Agent 知道：

```text

什么时候用

先做什么

不能做什么

什么时候停

如何验证

如何报告

遇到边界情况去哪读

哪些部分交给脚本确定性执行

```
## 结论

Skill 是 Agent 工程中的一个重要抽象：它把专业知识、团队流程和可执行资源封装为可被 Agent 按需发现和加载的目录。Codex 和 Claude 都采用 progressive disclosure：启动时加载 name 和 description，触发后加载完整 SKILL.md，执行中再按需读取 references、assets 或运行 scripts。

但 skill 不是魔法，也不是流程引擎。它进入的是上下文窗口，而不是模型权重；它影响模型行为，但不能单独保证模型永远严格按步骤执行。Codex 的 agent loop 会把 skill、用户任务、工具定义、工具结果和历史消息一起送入模型，随着任务推进不断追加上下文；当上下文过长时，Codex 会 compact conversation，原始细节可能被压缩。

因此，最可靠的 agent workflow 不是“写一个很长的 SKILL.md”，而是：

Skill 写清楚流程和边界

Scripts 执行确定性检查

Rules / hooks / sandbox 提供硬约束

Tests / CI / review 做最终验收

Evals 持续改进触发与输出质量

一句话概括：

Skill 是让 Agent 按组织经验工作的上下文接口；真正的可靠性来自 skill 与工程控制面的组合。
