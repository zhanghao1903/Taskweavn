# Hermes Agent 架构与上下文治理调研

> 调研主题：Hermes Agent 架构，尤其是 Agent 模块中的上下文管理、上下文压缩、长期记忆、会话持久化与可扩展治理机制。
> 目标：为后续围绕 Agent 上下文治理、Context Engine、Memory Provider、Session Search、Prompt Assembly 等模块的工程改造提供基础材料。
> 说明：本文基于官方架构文档、开发者文档与 GitHub 源码页面的静态调研整理；未包含本地运行 Hermes、压测或端到端测试结果。

---

## 目录

1. [总体判断](#1-总体判断)
2. [Agent 模块的上下文治理分层](#2-agent-模块的上下文治理分层)
3. [Prompt 构建：稳定上下文 vs 临时上下文](#3-prompt-构建稳定上下文-vs-临时上下文)
4. [Context Files 的治理](#4-context-files-的治理)
5. [Agent Turn Lifecycle：上下文何时被压缩](#5-agent-turn-lifecycle上下文何时被压缩)
6. [ContextEngine：最重要的扩展点](#6-contextengine最重要的扩展点)
7. [ContextCompressor：当前内置压缩策略](#7-contextcompressor当前内置压缩策略)
8. [压缩摘要的语义治理](#8-压缩摘要的语义治理)
9. [压缩失败和上下文丢失风险](#9-压缩失败和上下文丢失风险)
10. [Tool Call Pair 是硬约束](#10-tool-call-pair-是硬约束)
11. [MemoryProvider：长期记忆的扩展点](#11-memoryprovider长期记忆的扩展点)
12. [Session DB 与历史检索](#12-session-db-与历史检索)
13. [Prompt Caching 与上下文治理的张力](#13-prompt-caching-与上下文治理的张力)
14. [Agent-level Tools 与上下文相关工具](#14-agent-level-tools-与上下文相关工具)
15. [当前设计的优点](#15-当前设计的优点)
16. [当前设计的主要风险和缺口](#16-当前设计的主要风险和缺口)
17. [后续改造建议：Context Governance Layer](#17-后续改造建议context-governance-layer)
18. [推荐代码阅读顺序](#18-推荐代码阅读顺序)
19. [建议优先做的工程动作](#19-建议优先做的工程动作)
20. [测试建议](#20-测试建议)
21. [一句话架构建议](#21-一句话架构建议)
22. [参考资料](#22-参考资料)

---

## 1. 总体判断

Hermes 的上下文治理不是一个单独的 `memory` 模块，而是分散在以下多个模块之间：

- Prompt 构建
- 会话历史维护
- 上下文压缩
- 持久化记忆
- 外部 memory provider
- session search
- 工具调用协议
- prompt caching

官方架构文档中，Agent 内部与上下文治理高度相关的文件包括：

```text
run_agent.py
agent/prompt_builder.py
agent/context_engine.py
agent/context_compressor.py
agent/prompt_caching.py
agent/memory_manager.py
agent/memory_provider.py
agent/model_metadata.py
agent/agent_init.py
```

这些文件基本构成后续做上下文管理改造时的核心阅读路径。

从治理角度看，Hermes 已经有一套比较完整的上下文生命周期：

```text
用户输入
  ↓
AIAgent.run_conversation / agent loop
  ↓
prompt_builder 组装稳定 system prompt + 临时上下文层
  ↓
memory / user profile / project context / tool guidance 注入
  ↓
context_engine 判断是否需要压缩
  ↓
context_compressor 压缩中间历史，保护首尾和工具调用对
  ↓
模型响应
  ↓
工具调用、memory 写入、session DB 持久化
  ↓
下一轮继续
```

官方文档明确说明，`AIAgent` 负责 provider 选择、prompt 构造、工具执行、重试/回退、callbacks、压缩和持久化。它支持 Chat Completions、Codex Responses、Anthropic Messages 三种 API 模式，但内部最终会收敛到 OpenAI 风格的 message 结构。

核心结论：

> Hermes 已具备上下文治理的工程基础，但当前更偏“启发式压缩 + prompt 分层 + 单 memory provider + 单 context engine”的架构。如果后续要做更强的 Agent 上下文管理，最值得切入的是 `ContextEngine` 插件和 `MemoryProvider` 插件，而不是直接重写 agent loop。

---

## 2. Agent 模块的上下文治理分层

Hermes 的上下文治理可以拆成五层。

| 层级 | 主要文件 / 模块 | 作用 | 对后续改造的重要性 |
|---|---|---|---|
| Prompt 输入层 | `prompt_builder.py` | 决定哪些上下文进入模型，包括 SOUL、MEMORY、USER、skills、context files、tool guidance、platform info | 很高 |
| 会话历史层 | `run_agent.py` / session state | 维护当前 conversation messages，保证模型消息格式和工具调用顺序 | 很高 |
| 压缩治理层 | `context_engine.py` / `context_compressor.py` | 判断何时压缩、压缩什么、保留什么、摘要如何生成 | 最高 |
| 持久记忆层 | `memory_manager.py` / `memory_provider.py` | 管理 MEMORY、USER profile、外部记忆 provider、memory tools | 很高 |
| 持久会话与检索层 | SQLite session DB / FTS5 / `session_search` | 保存完整历史、支持 lineage、搜索历史消息 | 高 |

官方文档强调，system prompt 是由 SOUL、MEMORY、USER、skills index、context files、tool guidance、model/platform instructions 等层拼出来的；`context_compressor` 则在上下文超过阈值时摘要中间轮次。

---

## 3. Prompt 构建：稳定上下文 vs 临时上下文

Hermes 的 prompt 设计中有一个关键治理原则：

> 稳定 system prompt 和 API-call-time 临时层分离。

稳定 system prompt 通常包括：

1. SOUL identity
2. tool guidance
3. Honcho static instructions
4. 可选 system prompt
5. frozen MEMORY
6. frozen USER
7. skills index
8. context files
9. timestamp / session / platform 信息

官方文档将这些作为可缓存的 system prompt 层，并和以下 API 调用时临时注入层区分开：

- ephemeral prompt
- prefill
- gateway overlays
- Honcho recall
- API-call-time dynamic context

这对上下文治理非常关键，因为它意味着：

- 长期身份、工具规则、项目说明、用户画像更偏稳定层。
- 当前请求相关召回、gateway 注入、临时提示更偏 ephemeral 层。
- memory snapshot 在 session 开始时被冻结。
- session 中途写入 memory 会更新磁盘，但不会自动改变已经缓存的 system prompt。

这种设计带来一个明显取舍：

- 优点：提升 prompt caching 的稳定性。
- 风险：memory 写入后，模型不一定立即在 system prompt 中看到。

如果后续要做精细上下文治理，需要区分：

```text
哪些记忆应该立即进入当前轮？
哪些记忆只应该在下一 session 或下一次 prompt 重建时进入？
哪些内容只属于当前任务 working memory？
哪些内容应当进入长期 memory？
```

---

## 4. Context Files 的治理

Hermes 会加载项目上下文文件，例如：

```text
.hermes.md / HERMES.md
AGENTS.md
CLAUDE.md
.cursorrules
```

这些文件会被安全扫描，检测内容包括：

- prompt injection 模式
- Unicode 异常
- credential exfiltration 模式
- 其他潜在恶意上下文注入

同时，这些文件会被截断到大约 20,000 字符，YAML frontmatter 会被剥离。

这说明 Hermes 已经把“项目上下文”当作一种潜在不可信输入处理，而不是完全信任。

不过，这里仍然主要是启发式安全扫描。后续如果要做更强的上下文治理，建议引入更明确的 provenance / source trust 机制，例如：

```yaml
context_item:
  source: AGENTS.md
  trust_level: project_policy | user_supplied | tool_observed | model_generated
  scope: repo | session | task | global
  expires_at: optional
  can_override_system: false
  can_trigger_tool: false
```

当前文档和代码中没有看到完整的上下文来源账本 / context ledger 机制。

---

## 5. Agent Turn Lifecycle：上下文何时被压缩

官方 agent loop 文档给出了每轮对话的大致生命周期：

1. append user message
2. build or reuse prompt
3. preflight compression：当上下文超过约 50% 时触发
4. build API messages
5. 注入 ephemeral prompt layers
6. 插入 prompt cache markers
7. 调用模型
8. 解析模型响应
9. 如果有工具调用则执行工具，否则返回 final response
10. 保存 messages、flush memory、resume session

文档还说明，agent loop 会维护历史、处理压缩、重试、fallback，并在上下文丢失前 flush persistent memory。

这说明 Hermes 的上下文治理不是“等到爆 token 再裁剪”，而是在 agent loop 里持续做预算控制。

尤其值得注意的是，文档中提到两级压缩：

| 压缩机制 | 触发阈值 | 作用 |
|---|---:|---|
| Gateway hygiene compression | 约 85% 上下文 | 偏前置清理，避免 gateway 侧超限 |
| Agent ContextCompressor | 默认约 50% 上下文 | 使用真实 token 统计，偏 agent 内部治理 |

从工程角度看，这是合理的：

- gateway 只做粗估和保护；
- agent 内部用更准确的模型上下文窗口和 token 统计做决策。

---

## 6. ContextEngine：最重要的扩展点

`ContextEngine` 是 Hermes 上下文治理的核心抽象层。

源码注释把它定义为一个 ABC，用来在接近 token limit 时控制上下文。内置 compressor 是默认实现，第三方 engine 可以通过插件替换。配置项是：

```yaml
context:
  engine: your_engine_name
```

一次只能激活一个 context engine。

ContextEngine 插件文档说明，自定义 engine 可以替代 built-in `ContextCompressor`，例如可以实现 LCM DAG 这类更复杂的上下文管理。

插件通常需要实现以下方法或状态：

```text
update_from_response(...)
should_compress(...)
compress(...)
last_prompt_tokens
threshold_tokens
context_length
compression_count
```

这意味着，如果后续要做 Agent 上下文治理，最干净的路径是：

```text
不要优先改 run_agent.py
  ↓
实现自己的 ContextEngine
  ↓
在 engine 内部做：
  - token budget 统计
  - 上下文分级
  - 历史压缩
  - 事实抽取
  - 可逆引用
  - 检索增强
  - 压缩审计
  ↓
通过 context.engine 配置启用
```

源码层面，`agent_init.py` 会读取 `context.engine` 配置，从插件目录或通用 plugin system 加载自定义 context engine。如果没有配置，则 fallback 到内置 compressor。初始化时也会把 context engine 的 tool schemas 注入 agent 工具集中。

---

## 7. ContextCompressor：当前内置压缩策略

内置 `ContextCompressor` 的默认参数在源码中比较清楚：

```text
threshold_percent = 0.50
protect_first_n = 3
protect_last_n = 20
summary_target_ratio = 0.20
abort_on_summary_failure = false
```

这些默认值说明 Hermes 的默认策略是：

```text
上下文达到约 50% 就开始压缩
保护开头 3 条消息
保护最近 20 条消息
把中间历史压成大约 20% 的摘要
```

文档描述的压缩算法大致是：

1. 第一阶段先压缩旧 tool results。
2. 第二阶段再压缩中间消息。
3. 保护最早几条消息和最近若干消息。
4. 对齐边界，避免切断 tool call / tool result group。
5. 保留 session lineage。

源码中还能看到更细的治理逻辑：

- 去重重复 tool results。
- 摘要旧 tool results。
- 剥离历史 multimodal screenshots。
- 截断 tool call 参数但保持 JSON 有效。
- 在发送给辅助 summary model 前做敏感信息 redaction。
- 压缩失败时可以选择 abort，或者插入 fallback marker 并继续丢弃中间内容。

这部分是后续改造时最需要认真看源码的地方。

它不仅仅是在“摘要对话”，还在维护：

```text
message protocol
工具调用对完整性
tool pair 合法性
多模态内容裁剪
敏感信息处理
压缩失败策略
```

---

## 8. 压缩摘要的语义治理

`ContextCompressor` 的摘要前缀非常重要。源码里的 `SUMMARY_PREFIX` 明确声明压缩摘要是：

```text
REFERENCE ONLY
```

也就是说，摘要只是参考信息，而不是新的指令。

它还强调：

- 当前任务应该在 Active Task 中。
- persistent memory 比摘要更权威。
- 回答时只响应最新用户消息。

这个设计非常重要，因为压缩摘要有一个常见风险：

> 模型把旧摘要当成新的系统指令。

Hermes 通过摘要前缀试图降低这个风险。

不过，这仍然不是强保证。后续如果要增强上下文治理，可以考虑把摘要拆成结构化字段，而不是普通自然语言，例如：

```yaml
compressed_context:
  reference_only: true
  active_task: ...
  constraints:
    - ...
  completed_steps:
    - ...
  decisions:
    - ...
  open_questions:
    - ...
  files:
    - path: ...
      relevance: ...
  forbidden_as_instruction: true
```

这样做的好处是：

- 更容易验证；
- 更容易过滤；
- 更容易重排；
- 更容易审计；
- 更容易和 retrieval anchor 结合。

---

## 9. 压缩失败和上下文丢失风险

这是当前 Hermes 上下文治理中最需要注意的风险点。

官方文档明确提到：summary model 的上下文窗口必须至少和主模型一样大。如果 summary model 的上下文更小，摘要生成可能失败。

文档还说明，在某些失败路径下，compressor 可能会丢弃中间轮次而没有有效摘要，从而造成上下文丢失。

源码里已经有以下配置项：

```text
abort_on_summary_failure
```

其行为大致是：

| 配置值 | 行为 |
|---|---|
| `true` | 摘要失败时中止压缩，避免无摘要丢弃历史 |
| `false` | 插入静态 fallback marker，并可能继续 drop middle |

当前默认值是：

```text
abort_on_summary_failure = false
```

如果后续要做可靠的上下文治理，建议把这个作为第一优先级处理：

```yaml
compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20
  abort_on_summary_failure: true
```

同时要确保用于压缩的 auxiliary model 的 context window 不小于主模型。否则在长任务、代码任务、工具密集任务中，压缩失败会变成“静默遗忘”的高风险点。

---

## 10. Tool Call Pair 是硬约束

Hermes 的 agent loop 文档强调内部消息格式遵守严格 alternation rules。

工具调用必须和工具结果匹配，不能出现：

- orphan tool result
- 缺失 tool result 的 assistant tool call
- 被压缩切断的 tool call group

源码里的 compressor 也专门有 `_sanitize_tool_pairs` 逻辑，用来处理两类失败模式：

1. orphan tool result
2. assistant tool call 缺少对应 tool result

必要时它会删除或插入 stub，以维持协议合法性。

这对上下文治理非常关键。后续如果实现自己的 `ContextEngine`，不能只按 token 或消息数量裁剪历史，必须保持以下不变量：

```text
assistant(tool_calls=[...])
  必须跟随对应 tool role messages

tool result
  必须能对应到前面的 assistant tool_call_id

压缩边界
  不能切在 tool call group 中间

OpenAI-style messages
  需要维持合法 role 顺序
```

否则模型 API 可能直接报错，或者 agent 状态被破坏。

---

## 11. MemoryProvider：长期记忆的扩展点

Hermes 的 memory provider 是另一条关键扩展路径。

官方文档把 memory provider 定义为“持久跨 session 知识”的插件系统，它和本地 `MEMORY.md` / `USER.md` 不完全一样。

插件需要实现 `MemoryProvider` ABC。

核心方法包括：

```text
name
is_available
initialize
get_tool_schemas
handle_tool_call
```

可选 hooks 包括：

```text
system_prompt_block
prefetch
queue_prefetch
sync_turn
on_session_end
on_pre_compress
on_memory_write
shutdown
```

其中 `on_pre_compress` 对上下文治理尤其重要，因为它可以在压缩发生前把即将丢失的内容提取进长期记忆。

源码初始化路径里，`agent_init.py` 会根据配置加载 memory provider，并传入以下上下文：

- session id
- platform
- Hermes home
- gateway user / chat / thread
- active profile
- agent identity

不过，文档也说明一次只能激活一个外部 memory provider。

这对复杂治理是一个限制。如果想同时接入本地向量库、企业知识库、用户画像库、任务状态库，就需要：

1. 在单个 provider 内部做 router；或
2. 修改 Hermes 的 provider composition 机制。

---

## 12. Session DB 与历史检索

Hermes 会把 session metadata、完整消息历史、model config 等持久化到 SQLite，默认路径类似：

```text
~/.hermes/state.db
```

文档提到它使用：

- SQLite
- WAL
- FTS5
- lineage
- source tagging

相关表包括：

```text
sessions
messages
messages_fts
messages_fts_trigram
```

`messages` 表会保存：

- role
- content
- reasoning
- tool calls
- tool call id
- model
- source
- token
- cost
- 其他元数据

FTS5 触发器负责同步全文索引。

这意味着 Hermes 实际上有两种“长期上下文”：

```text
MemoryProvider / MEMORY / USER
  更像 agent 可主动使用的语义记忆

Session DB / session_search
  更像完整历史日志 + 可检索记录
```

后续做上下文治理时，不应该把所有东西都塞进 memory。

更好的方式是：

| 内容类型 | 推荐存放位置 |
|---|---|
| 事实、偏好、长期约束 | memory |
| 可追溯的原始对话和工具结果 | session DB |
| 当前任务状态 | active task / working memory |
| 大型历史内容 | session search 或自定义 context engine 检索回来 |

文档还说明 compression split 会保留 `parent_session_id`，形成 session lineage。这对“压缩后仍能追溯原始历史”非常重要。

---

## 13. Prompt Caching 与上下文治理的张力

Hermes 使用 Anthropic prompt cache 时最多可以设置 4 个 cache breakpoints。

文档提到一种 `system_and_3` 策略，会优先稳定 system prompt、消息排序和缓存边界。

压缩会使被压缩的历史区域失效，但稳定 system prompt 可以继续受益于缓存。

这带来一个核心张力：

```text
上下文治理希望：
  动态注入更多相关信息

prompt caching 希望：
  system prompt 尽量稳定，不频繁变动
```

Hermes 当前的解决方式是：

- 稳定身份、记忆快照、工具规则放 system prompt。
- 临时 recall、gateway overlays、prefill 放 API-call-time 层。
- 压缩只改历史消息，不随意改稳定 system prompt。

如果后续引入更复杂的 retrieval 或 memory ranking，建议不要直接频繁改 system prompt，而是通过 ephemeral context 或 context engine 的消息层注入，这样更符合 Hermes 现有设计。

---

## 14. Agent-level Tools 与上下文相关工具

Hermes agent loop 文档提到一些 agent-level tools 会被 agent 拦截处理，例如：

```text
todo
memory
session_search
delegate_task
```

这些工具不一定走普通外部工具执行路径，而是在 agent 层做特殊处理。

这对上下文治理意味着：

> memory 和 session_search 本身就是 agent 内部上下文操作工具。

如果要扩展 Agent 的上下文管理，不一定只做被动压缩，也可以暴露主动工具，例如：

```text
context_search(query)
context_pin(item_id)
context_forget(item_id)
context_summarize(scope)
context_expand(summary_id)
context_mark_decision(...)
context_mark_constraint(...)
```

ContextEngine 插件文档也说明，自定义 context engine 可以直接暴露工具 schema，agent 初始化时会把这些工具加入可用工具集中。

---

## 15. 当前设计的优点

### 15.1 Prompt 层次清楚

稳定 system prompt、memory snapshot、project context、ephemeral overlays 被区分开。这比把所有内容混进一个 system prompt 更好。

### 15.2 压缩是 Agent 内部的一等机制

它不是简单裁剪历史，而是考虑：

- token 阈值
- 首尾保护
- tool pair
- 旧 tool result 压缩
- summary 预算
- 多模态裁剪
- 敏感信息 redaction
- 压缩失败策略

### 15.3 ContextEngine 插件化

这让开发者可以在不大改 agent loop 的情况下替换上下文治理策略。

### 15.4 MemoryProvider 插件化

长期记忆、外部用户画像、pre-compress hook、turn sync 都有可扩展点。

### 15.5 会话持久化和全文检索比较完整

SQLite + FTS5 + lineage 让压缩后的 session 仍有机会追溯历史。

---

## 16. 当前设计的主要风险和缺口

### 16.1 压缩仍然是有损的

即使有摘要，压缩也不可避免损失细节。

尤其是工具密集型代码任务，很多关键上下文可能藏在：

- 旧 tool result
- 错误日志
- 文件 diff
- 用户修正
- 中间分析
- 被截断的命令输出

Hermes 已经做了旧 tool result 摘要和敏感信息 redaction，但压缩仍然可能丢失可执行细节。

建议：

> 把压缩摘要从纯自然语言升级为“结构化摘要 + 可回溯引用”。

---

### 16.2 默认 `abort_on_summary_failure = false` 有风险

当前源码默认在摘要失败时不一定中止压缩，而是可能插入 fallback marker 并继续丢弃中间历史。

建议：

对于高可靠 Agent，默认启用：

```yaml
compression:
  abort_on_summary_failure: true
```

---

### 16.3 Memory Snapshot 冻结会造成“刚写入记忆不可见”

文档明确说明，mid-session memory writes 会更新磁盘，但不会自动 mutate cached system prompt。

这对长期记忆一致性有好处，但对当前任务可能不理想。

建议把“当前任务临时记忆”和“长期 memory”分开：

```text
long_term_memory:
  frozen at session start

working_memory:
  mutable during current task
  injected ephemerally
  cleared or committed at session end
```

---

### 16.4 只有一个 Active ContextEngine / MemoryProvider

官方文档说明 context engine 和 external memory provider 都是单选。

这简化了架构，但限制了组合能力。

复杂上下文治理往往需要多个子系统：

- 摘要 engine
- retrieval engine
- vector memory
- user profile memory
- code workspace state
- task planner state
- security policy layer

建议未来做一个 composite provider 或 router。

---

### 16.5 Provenance 不够显式

Hermes 已经区分了 prompt layers，也做了 context file security scan，但没有看到完整的上下文 provenance ledger。

对于高可靠 Agent，应该知道每条上下文：

- 来自哪里；
- 何时生成；
- 可信度如何；
- 能否作为指令；
- 是否过期；
- 是否可被持久化；
- 是否可被压缩；
- 是否被用户确认。

建议新增：

```text
ContextLedger
  id
  source_type
  source_uri
  created_at
  last_seen_at
  trust_level
  scope
  expiry
  token_cost
  compression_state
  can_act_as_instruction
  can_be_persisted
```

---

## 17. 后续改造建议：Context Governance Layer

如果后续要真正做 “Agent 上下文治理”，建议不要只做一个更强的 summarizer，而是加一层：

```text
Context Governance Layer
```

推荐架构：

```text
AIAgent
  ↓
PromptBuilder
  ↓
Context Governance Layer
  ├── ContextLedger        # 上下文来源账本
  ├── ContextBudgeter      # token 预算分配
  ├── ContextRanker        # 相关性排序
  ├── CompressionPlanner   # 决定压缩哪些内容
  ├── MemoryRouter         # 哪些写入长期记忆
  ├── RetrievalRouter      # 何时调用 session_search / memory / vector
  ├── SafetyFilter         # prompt injection / secret / policy
  └── CompressionAuditor   # 压缩质量和可回溯性
  ↓
ContextEngine.compress()
  ↓
Model messages
```

最小可落地版本可以先做三件事：

1. **ContextLedger**：给每条上下文打来源、scope、trust、expiry。
2. **CompressionAuditor**：每次压缩输出“丢弃了什么、保留了什么、摘要覆盖了什么”。
3. **Retrieval-aware Compressor**：摘要里保留可检索锚点，例如 session id、message id、tool result id、file path、commit hash。

---

## 18. 推荐代码阅读顺序

### 18.1 `run_agent.py`

重点看：

- agent loop 主入口
- 消息历史维护
- 工具调用流程
- API 模式分支
- fallback 逻辑
- 与 `agent_init.initialize_agent` 的关系

当前源码显示，`AIAgent.__init__` 的主体已经抽到了 `agent.agent_init.initialize_agent`，`run_agent.py` 中的构造器会调用这个初始化函数。

---

### 18.2 `agent/agent_init.py`

这是上下文治理初始化的关键文件。

重点看：

- memory 配置加载
- memory provider 加载
- context engine 加载
- 内置 compressor fallback
- context engine tools 注入
- session lifecycle hooks
- active profile / agent identity 注入

---

### 18.3 `agent/prompt_builder.py`

重点看：

- system prompt 层次顺序
- memory snapshot
- context files
- skills index
- platform info
- ephemeral layers
- prompt caching 相关结构

官方 prompt assembly 文档已经对这部分做了比较清楚的解释。

---

### 18.4 `agent/context_engine.py`

这是自定义上下文治理的抽象入口。

重点看：

- ABC 方法
- 默认阈值
- 工具 schema 接入
- session lifecycle
- 和内置 compressor 的关系

---

### 18.5 `agent/context_compressor.py`

这是当前内置治理策略的主体。

重点看：

- 阈值计算
- boundary alignment
- previous summary rehydration
- tool pair sanitize
- multimodal stripping
- sensitive redaction
- summary failure handling
- anti-thrashing
- fallback marker

源码说明它会跳过收益低于 10% 的连续压缩，以避免反复压缩带来的 thrashing。

---

### 18.6 `agent/memory_provider.py` / `agent/memory_manager.py`

重点看：

- memory provider interface
- local MEMORY / USER 文件加载
- memory hooks
- pre-compress 行为
- profile isolation
- tool schema 暴露

---

### 18.7 Session DB 相关代码

重点看：

- SQLite schema
- FTS5
- session lineage
- message persistence
- session_search
- token / cost metadata
- source tagging

官方文档已经说明 session DB 会保存完整消息历史，并通过 FTS5 支持搜索。

---

## 19. 建议优先做的工程动作

### P0：配置层防止上下文静默丢失

建议配置：

```yaml
compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_last_n: 20
  abort_on_summary_failure: true
```

同时要求 compression auxiliary model 的 context window 不小于主模型。

官方文档已经明确指出 summary model context 太小会导致摘要失败风险。

---

### P1：实现自定义 ContextEngine，而不是硬改 agent loop

先实现一个 wrapper engine：

```text
GovernedContextEngine(ContextEngine)
  - 内部调用默认 ContextCompressor
  - 压缩前记录 ContextLedger
  - 压缩后做 CompressionAuditor
  - 必要时调用 session_search / memory provider
  - 暴露 context_status / context_expand 工具
```

这样可以复用 Hermes 当前 compressor 的 tool pair 保护和协议合法性。

---

### P2：把压缩摘要结构化

当前 Hermes 已经使用结构化 summary 模板，包含：

- 目标
- 约束
- 已完成 / 进展
- 关键决策
- 相关文件
- critical 信息

可以进一步把它改成机器可解析结构：

```json
{
  "reference_only": true,
  "active_task": "...",
  "constraints": [],
  "decisions": [],
  "completed_steps": [],
  "open_threads": [],
  "files": [],
  "tool_results": [],
  "retrieval_anchors": []
}
```

---

### P3：给 memory 写入加 provenance 和 TTL

Memory 不应该只是“文本追加”。

建议每条 memory 包含：

```yaml
memory_item:
  content: ...
  source: user_explicit | assistant_inferred | tool_observed | compressed_summary
  confidence: high | medium | low
  scope: global | project | session | task
  ttl: optional
  created_from_message_ids: [...]
  user_confirmed: true/false
```

MemoryProvider 已经有 `on_memory_write` 和 `sync_turn` 等 hook，可以在这些 hook 上扩展。

---

### P4：建立上下文治理测试集

至少需要覆盖：

```text
1. 压缩后无 orphan tool result
2. 压缩后 assistant tool_call 都有对应 tool result
3. 最近 N 轮不被压缩
4. system prompt 不被旧 summary 覆盖
5. memory 写入后不会污染当前 cached system prompt
6. summary model 失败时不会静默丢上下文
7. 压缩摘要不包含 secret
8. session lineage 可以追溯原始消息
9. 中文 / CJK 内容在 FTS / session_search 中可检索
10. 多次压缩不会重复累积错误摘要
```

---

## 20. 测试建议

后续如果要做工程化改造，建议建立以下测试类型。

### 20.1 协议合法性测试

验证压缩前后：

- tool call / tool result pair 不被切断；
- assistant tool call 都有结果；
- 没有 orphan tool result；
- OpenAI-style messages 符合 role 顺序要求。

### 20.2 压缩质量测试

验证：

- 关键约束是否保留；
- 活跃任务是否保留；
- 用户最新意图是否没有被旧摘要覆盖；
- 文件路径、错误日志、关键决策是否保留；
- summary 是否可被机器解析。

### 20.3 Memory 一致性测试

验证：

- memory 写入能落盘；
- memory snapshot 冻结行为符合预期；
- working memory 不污染 long-term memory；
- 用户明确否定的偏好不会继续存在。

### 20.4 安全测试

验证：

- 压缩摘要不包含 secret；
- project context 中的 prompt injection 不会覆盖 system instruction；
- 历史工具结果中的恶意文本不会被提升为指令；
- context file security scan 对常见攻击模式有效。

### 20.5 检索与追溯测试

验证：

- session lineage 可追溯原始消息；
- session_search 能找回被压缩前的关键内容；
- 中文 / CJK 内容可检索；
- retrieval anchor 能定位到原始消息、工具结果、文件路径或 commit hash。

---

## 21. 一句话架构建议

后续如果要围绕 Hermes 做 Agent 上下文管理，目标不应只是：

```text
让 prompt 更长
```

也不应只是：

```text
让摘要更好
```

更合理的目标是做成：

```text
可审计、可回溯、可分级、可压缩、可检索、可撤销的 Context Governance System
```

最现实的落点是：

1. **短期**：打开 safer compression 配置，审查 `ContextCompressor` 失败路径。
2. **中期**：实现自定义 `ContextEngine`，增加 ContextLedger 和 CompressionAuditor。
3. **长期**：实现 composite MemoryProvider / RetrievalRouter，把 memory、session_search、project context、tool results 统一纳入治理。

---

## 22. 参考资料

以下是本次调研中涉及的主要公开资料入口。

### 官方文档

- Hermes Developer Guide: Architecture
  <https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/architecture>

- Hermes Developer Guide: Agent Loop
  <https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/agent-loop>

- Hermes Developer Guide: Prompt Assembly
  <https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/prompt-assembly>

- Hermes Developer Guide: Context Compression and Caching
  <https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/context-compression-and-caching>

- Hermes Developer Guide: Context Engine Plugin
  <https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/context-engine-plugin>

- Hermes Developer Guide: Memory Provider Plugin
  <https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/memory-provider-plugin>

- Hermes Developer Guide: Session Storage
  <https://hermes-agent.nousresearch.com/docs/zh-Hans/developer-guide/session-storage>

### GitHub 源码

- `run_agent.py`
  <https://raw.githubusercontent.com/NousResearch/hermes-agent/main/run_agent.py>

- `agent/agent_init.py`
  <https://raw.githubusercontent.com/NousResearch/hermes-agent/main/agent/agent_init.py>

- `agent/context_engine.py`
  <https://raw.githubusercontent.com/NousResearch/hermes-agent/main/agent/context_engine.py>

- `agent/context_compressor.py`
  <https://raw.githubusercontent.com/NousResearch/hermes-agent/main/agent/context_compressor.py>

- GitHub 页面：`agent/context_compressor.py`
  <https://github.com/NousResearch/hermes-agent/blob/main/agent/context_compressor.py>

---

## 附录 A：后续可直接落地的 ContextEngine 草案

下面是一个后续可进一步细化的 ContextEngine 方向。

```text
GovernedContextEngine
  responsibilities:
    - wrap default ContextCompressor
    - maintain ContextLedger
    - run pre-compress extraction
    - call memory provider hooks
    - create structured summaries
    - attach retrieval anchors
    - audit compression loss
    - expose context tools

  tools:
    - context_status
    - context_search
    - context_expand
    - context_pin
    - context_forget
    - context_mark_decision
    - context_mark_constraint
```

可能的数据结构：

```yaml
context_record:
  id: ctx_...
  source_type: user_message | assistant_message | tool_result | memory | project_file | summary
  source_ref: ...
  content_hash: ...
  trust_level: system | developer | user | project | tool | model_generated
  scope: global | profile | project | session | task | turn
  created_at: ...
  expires_at: ...
  token_cost: ...
  relevance_score: ...
  compression_state: raw | summarized | dropped | pinned
  can_act_as_instruction: false
  can_be_persisted: true
  retrieval_anchor: ...
```

---

## 附录 B：推荐配置模板

```yaml
context:
  engine: governed_context_engine

compression:
  enabled: true
  threshold: 0.50
  target_ratio: 0.20
  protect_first_n: 3
  protect_last_n: 20
  abort_on_summary_failure: true
  preserve_tool_pairs: true
  preserve_recent_user_intent: true
  redact_sensitive_content: true

memory:
  provider: composite_memory_router
  write_policy:
    require_source: true
    require_scope: true
    allow_inferred_memory: false
  hooks:
    on_pre_compress: true
    on_memory_write: true
    sync_turn: true

session:
  persistence: sqlite
  search: fts5
  preserve_lineage: true
  store_tool_results: true
  store_token_costs: true
```

---

## 附录 C：上下文治理检查清单

```text
[ ] 是否区分 stable system prompt 与 ephemeral prompt？
[ ] 是否区分 long-term memory 与 working memory？
[ ] 是否有 context provenance？
[ ] 是否有 context scope？
[ ] 是否有 context TTL / expiry？
[ ] 是否有压缩失败保护？
[ ] 是否保证 tool call pair 完整？
[ ] 是否保留最近用户意图？
[ ] 是否防止旧 summary 变成新指令？
[ ] 是否能追溯被压缩内容？
[ ] 是否能检索 session 历史？
[ ] 是否能处理中文 / CJK 检索？
[ ] 是否有 secret redaction？
[ ] 是否能审计每次压缩丢弃了什么？
[ ] 是否能撤销或修正错误 memory？
```
