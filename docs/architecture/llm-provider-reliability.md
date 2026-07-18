# LLM Provider Reliability 架构事实

> Status: current implementation fact document
>
> Calibrated: 2026-07-10
>
> External protocol check: 2026-07-10
>
> Original historical document:
> [llm-provider-reliability.original.md](llm-provider-reliability.original.md)
>
> Calibration record:
> [fix-log/llm-provider-reliability.md](fix-log/llm-provider-reliability.md)

## 1. 文档目的

本文记录当前仓库中 LLM transport 的真实实现，包括：

- `LLMClient` 与 `LLMProvider` 的边界；
- retry、timeout、错误分类和 AgentLoop 失败落盘；
- LiteLLM、DeepSeek、OpenRouter 三个 provider 的实际参数透传；
- Main Page 的 Agent role 配置和装配；
- response normalization、token usage、logging 与 reasoning 数据边界；
- 调用方的失败/降级策略；
- 当前官方 DeepSeek/OpenRouter 协议与本地实现之间的差异。

本文不把 accepted ADR、历史 release 或 proposed plan 中的目标自动视为现状。外部 provider 能力以核验日期为边界，并与本地代码事实分开描述。

## 2. 当前架构结论

### 2.1 Chat 主路径

Main Page 使用 Settings resolver 时，典型调用链是：

```text
Agent caller
  -> UsageRecordingLLM
  -> AgentConfiguredLLM
  -> LazyLLMClient
  -> LLMClient.chat
  -> selected LLMProvider.chat
  -> BaseLLMProvider retry loop
  -> provider SDK / LiteLLM
  -> ChatResponse
```

如果 Main Page dependencies 显式注入 `llm` 或 `llm_factory`，四个当前角色共享该对象，只在外面包一层 `UsageRecordingLLM`。这种注入对象不一定使用本仓库的 `LLMProvider` 实现。

通用 CLI 有两条构造路径：

- 没有 `--model`：`LLMClient.from_env()`，读取 provider 配置；
- 有 `--model`：直接 `LLMClient(model=...)`，使用 LiteLLM provider，绕过 `LLM_PROVIDER` 选择。

### 2.2 不属于 provider chat 主路径的接口

`LLMClient.complete()` 和 `count_tokens()` 仍通过 lazy `openhands.sdk.LLM`：

- 不调用 `LLMProvider.complete/count_tokens`；
- 不经过 `BaseLLMProvider` retry；
- 不使用 thinking 或 OpenRouter routing；
- `UsageRecordingLLM` 只是转发这两个方法，不记录 usage event。

当前生产 LLM 调用点主要使用 `chat()`；complete/count token 是兼容接口，而不是已经迁移到 provider reliability 的路径。

### 2.3 当前能力边界

| 能力 | 当前事实 |
| --- | --- |
| Provider abstraction | chat 已委托给 `LLMProvider`；complete/count 尚未迁移 |
| Provider set | `LiteLLMProvider`、`DeepSeekProvider`、`OpenRouterProvider` |
| Retry | 单 provider、同步、分类后重试；不是所有 transport 错误都会重试 |
| Timeout | 默认 180 秒并透传给 transport；配置了 request timeout 的 timeout error 不重试 |
| Cross-provider fallback | TaskWeavn 没有；OpenRouter 平台自身 routing/fallback 是另一层行为 |
| Streaming | 未实现；所有当前 chat provider 路径是同步返回 |
| Circuit breaker / health | 未实现 |
| Usage | Main Page role client 对成功 `ChatResponse` 写一条 workspace usage event |
| Reasoning | response 可保留；不直接进入 UI，但会进入内存 transcript 和 `llm_io` 日志 |
| Agent role config | Main Page 实际装配 execution、collaborator、read-only inquiry、runtime-input router 四个角色 |

## 3. Provider Contracts

### 3.1 LLMProvider

`LLMProvider` Protocol 声明：

- `name`；
- `capabilities`；
- `chat(ChatRequest)`；
- `complete(CompletionRequest)`；
- `count_tokens(TokenCountRequest)`。

`BaseLLMProvider` 只实现 chat retry。默认 complete/count 会抛 `UnsupportedCapabilityError`，但 `LLMClient` facade 当前不会调用这两个 provider 方法。

`ProviderCapabilities` 当前是描述性模型。仓库没有生产调用点读取 `provider.capabilities` 做统一预检。DeepSeek 自己使用 model profile 做局部能力检查；LiteLLM/OpenRouter 不会根据 capability flags 拒绝不支持的 neutral config。

### 3.2 ChatRequest

`ChatRequest` 是 frozen、`extra="forbid"` 的 provider-neutral 请求，包含：

- model；
- OpenAI shape messages/tools；
- temperature、max_tokens；
- timeout_seconds；
- `ThinkingConfig`；
- `ProviderRoutingConfig`；
- application metadata。

metadata 默认不会发送给 provider。当前三个 provider 都只把它用于本地日志上下文；OpenRouter 也不会从 metadata 读取 `session_id` 形成平台 sticky session。

`timeout_seconds` 只校验为正数或 `None`。`LLMClient.chat(timeout_seconds=None)` 的 `None` 表示“使用 client 默认值”，不能用该参数在单次调用上关闭 client 的非空默认 timeout。关闭默认值必须在 client/env 构造阶段配置。

### 3.3 ThinkingConfig

字段：

- `enabled`，默认 false；
- `effort`，只允许 `high` 或 `max`；
- `expose_reasoning_to_ui`，默认 false。

只有 DeepSeek provider 读取 enabled/effort。`expose_reasoning_to_ui` 当前没有任何生产读取点，不是一个实际数据泄露控制开关。

### 3.4 ProviderRoutingConfig

当前本地模型支持：

- `order`；
- `only`；
- `ignore`；
- `allow_fallbacks`，对象默认 false；
- `require_parameters`，对象默认 true；
- `data_collection`：allow/deny；
- `zdr`。

只有 OpenRouter provider 读取该对象。序列化时总是包含 `allow_fallbacks` 和 `require_parameters`，其他空字段省略。

### 3.5 ChatResponse

`ChatResponse` 保留旧的前三个位置字段：

- `content`；
- `tool_calls`；
- `raw_assistant_message`。

并增加：

- `reasoning_content`；
- `provider_name`；
- `provider_request_id`；
- `LLMUsage`；
- `retry_count` 与 `retry_records`；
- `raw_response_metadata`。

AgentLoop 会把 `raw_assistant_message` 原样加入下一次 LLM transcript。这是 DeepSeek thinking tool-call 场景保留 `reasoning_content` 的实际链路。

## 4. 配置与运行时装配

### 4.1 默认值必须按构造路径区分

| 构造路径 | 默认 provider | 默认 model | 默认 timeout |
| --- | --- | --- | --- |
| `LLMClient(model=...)` 未传 provider | LiteLLM | 调用者传入 | 180 秒 |
| `LLMClient.from_env()` 未设置 `LLM_PROVIDER` | DeepSeek | 参数默认 `deepseek-v4-pro` | 180 秒 |
| `LazyLLMClient()` | 首次请求时走 `from_env` | `deepseek-v4-pro` | 首次 resolve 前 property 报 180 秒 |
| Main Page Settings resolver 无 role profile | global Settings/env fallback，非法 provider 会规范为 DeepSeek | global Settings/env 或 `deepseek-v4-pro` | profile 空时 inner client 仍默认 180 秒 |

因此“LiteLLM 是系统默认 provider”不准确。它只是直接构造 `LLMClient` 时的兼容默认；当前 Settings/readiness/from-env 默认是 DeepSeek。

provider 与 model 没有统一兼容性校验。若未设置 `LLM_PROVIDER` 却传入其他 provider 的 model id，`from_env` 仍会构造 DeepSeek provider 并把该 model 字符串交给 DeepSeek API。

### 4.2 环境变量

`load_client_config_from_env()` 当前读取：

| 变量 | 当前作用 |
| --- | --- |
| `LLM_PROVIDER` | `deepseek`、`openrouter`、`litellm`；默认 DeepSeek |
| `LLM_MODEL` | provider request model；否则使用调用者 default model |
| `LLM_API_KEY` | provider-specific key 的 fallback；LiteLLM 必需 |
| `DEEPSEEK_API_KEY` | DeepSeek 首选 key |
| `DEEPSEEK_BASE_URL` | DeepSeek OpenAI-compatible base URL |
| `OPENROUTER_API_KEY` | OpenRouter 首选 key |
| `LLM_REQUEST_TIMEOUT_SECONDS` | 正数；默认 180；`none/off/disabled` 关闭 |
| `LLM_THINKING_ENABLED` | 出现时创建 ThinkingConfig |
| `LLM_THINKING_EFFORT` | 只有 enabled 变量出现时才读取；high/max |
| `OPENROUTER_PROVIDER_ORDER` | CSV -> order |
| `OPENROUTER_PROVIDER_ONLY` | CSV -> only |
| `OPENROUTER_PROVIDER_IGNORE` | CSV -> ignore |
| `OPENROUTER_ALLOW_FALLBACKS` | boolean |
| `OPENROUTER_REQUIRE_PARAMETERS` | boolean |
| `OPENROUTER_DATA_COLLECTION` | allow/deny |
| `OPENROUTER_ZDR` | optional boolean |

当前没有环境变量或 Settings role profile 字段配置 `RetryPolicy`。env/from-env provider 使用代码默认 retry policy。

`OPENROUTER_ZDR` 单独出现时存在实现缺口：routing 创建条件没有检查该变量，所以没有其他 routing 变量时会返回 `None`，ZDR 不会发送。通过 Agent role `providerRouting` 对象传入 ZDR 不受这个条件影响。

### 4.3 Agent role profiles

`AgentLlmRole` 类型声明六个角色：

- runtime_input_router；
- execution_agent；
- collaborator；
- read_only_inquiry；
- audit_agent；
- summary_agent。

Main Page `WorkspaceAgentLlms` 当前只创建并注入前四个角色。audit_agent 与 summary_agent 只是配置模型中的保留值，没有 Main Page 装配调用点。

profile 支持：

- inheritance，最大深度 8；
- provider、model；
- timeout、temperature；
- thinking；
- provider routing；
- role binding 和 default profile。

实际失败行为：

- 无 `agentLlm`：使用 global Settings/env；
- profile binding 缺失：使用 default profile；
- `parse_agent_llm_config` 失败：resolver 静默忽略整个 agent block，回退 global；
- inheritance cycle：发生在 profile resolve 阶段，不在上述 parse catch 中，会向 runtime assembly 调用方抛出；
- provider key 缺失：仍创建 lazy role client，首次请求时才失败；
- profile 在 workspace runtime 构造时解析，已创建 client 不会因后续 Settings 修改自动重建。

当 dependencies 注入共享 LLM 时，role profile resolver 完全不参与，四个角色共享同一个 usage-wrapped LLM。

### 4.4 Runtime Config 边界

Runtime Config catalog 声明：

- `llm.default_provider`；
- `llm.default_model`；
- `llm.request_timeout_seconds`；
- mutability 为 `next_llm_call`。

但当前 `runtime_config_consumers.py` 没有 LLM consumer，ConfigBus 也没有替换既有 role client 的实现。实际 LLM provider/model/timeout 仍是 workspace runtime 装配时由 Settings/env/profile 确定。catalog 可见与 live consumer 生效必须分开描述。

## 5. Retry 与错误模型

### 5.1 RetryPolicy

默认值：

- `max_attempts=3`，表示总尝试次数，不是额外 retry 次数；
- initial delay 0.5 秒；
- pre-jitter max delay 8 秒；
- multiplier 2；
- jitter 开启；
- status allowlist：408、409、425、429、500、502、503、504。

delay 先按指数退避并截断到 max，再乘 `0.5 + random()`。因此 jitter 后的实际 delay 最多接近 pre-jitter max 的 1.5 倍；`max_delay_seconds` 不是最终绝对上限。

### 5.2 分类规则

| 输入 | 当前分类 | 是否重试 |
| --- | --- | --- |
| 已是 `LLMProviderError` | 保留其 classification | 仅 retryable/rate_limit |
| status 401/403 | fatal_auth | 否 |
| status 429 | rate_limit | 是，若仍有 attempt 且未被 timeout 边界禁止 |
| status 在 policy allowlist | retryable | 是，若仍有 attempt |
| status 400 | fatal_request | 否 |
| status 413 | context_limit | 否 |
| type/message 含 timeout | retryable | 见 timeout 特例 |
| message 同时含 rate 与 limit | rate_limit | 是 |
| context too long/length | context_limit | 否 |
| auth/permission/api key | fatal_auth | 否 |
| badrequest/invalid | fatal_request | 否 |
| 其他 | unknown | 否 |

代码没有显式识别通用 `ConnectionError` 或 `ConnectionResetError`。能否把连接失败分类为 retryable 取决于具体 SDK exception 的 status/name/message；不能概括为“所有连接错误都会重试”。

### 5.3 Timeout 特例

当 `ChatRequest.timeout_seconds` 非空且捕获到 timeout error 时，provider 立即 `_raise_final()`，不进入下一次 retry。

由于 `LLMClient` 默认 timeout 是 180 秒，标准路径中的 provider timeout 默认只尝试一次。这个行为是 cooperative interruption 的最长等待边界，用来避免 `timeout * retry count` 放大用户等待。

若 client 构造时把 timeout 关闭为 `None`，transport 不收到 TaskWeavn request timeout；此后其他来源产生的 timeout exception 才可能按 retryable 进入 retry。

timeout 只是传给 SDK/LiteLLM 的参数。TaskWeavn 没有外层 wall-clock watchdog，也不 hard-cancel 正在运行的同步 provider call。

### 5.4 Retry record

每次真正准备再次尝试的失败会生成 `RetryRecord`，记录：

- 当前 attempt 和 max attempts；
- classification；
- provider/model；
- delay；
- error type；
- 最多 500 字符的 error string。

最终失败的那次 attempt 不会生成 retry record，因为它没有后续 retry。因此 3 次全部失败时，error 中通常只有 2 条 retry record。

成功前发生 retry 时，`ChatResponse.retry_count` 是已执行 retry 的数量。最终失败通过 typed exception 携带之前的 records。

### 5.5 Retry 不提供的保证

- 不重试 Tool、Action、Runtime、TaskBus 或 UI command；
- 不做跨 provider fallback；
- 不做 circuit breaker、hedging、provider health routing 或并发限流；
- 不发送 TaskWeavn generation idempotency key；
- 不控制或统计底层 SDK/LiteLLM 自己可能执行的内部 retry；
- 不保证 timeout/transport error 发生前 upstream 一定没有接受或计费请求。

`BaseLLMProvider` 当前捕获 `BaseException`，而不只是 `Exception`。因此 process interrupt 类异常也可能被分类并包装，这是当前实现边界。

## 6. Provider 实现

### 6.1 参数透传矩阵

| 字段 / 行为 | LiteLLMProvider | DeepSeekProvider | OpenRouterProvider |
| --- | --- | --- | --- |
| Transport | `litellm.completion` | OpenAI SDK + DeepSeek base URL | `litellm.completion` |
| temperature | 透传 | 只在 non-thinking profile 且未走 thinking disable 分支时透传 | 当前忽略 |
| max_tokens | 透传 | 透传 | 当前忽略 |
| timeout | 透传 | 透传 | 透传 |
| thinking | 当前忽略 | 校验并映射 | 当前忽略 |
| provider_routing | 当前忽略 | 当前忽略 | 映射到 `extra_body.provider` |
| model capability guard | 无 | 有本地 model profile | 无 |
| response parser | OpenAI-compatible shared parser | 同左 | 同左 |

neutral contract 的存在不意味着三个 provider 等价支持全部字段。当前也没有统一预检来阻止“字段被 provider 静默忽略”。

### 6.2 LiteLLMProvider

LiteLLM provider 是直接构造 `LLMClient` 时的兼容实现：

- 透传 model、api_key、messages、tools；
- 可选透传 temperature、max_tokens、timeout；
- 不读取 ThinkingConfig；
- 不读取 ProviderRoutingConfig。

`pyproject.toml` 没有直接声明 `litellm` dependency；当前 lock 中由 `openhands-sdk` 间接带入。仓库生产代码直接 import LiteLLM，因此其可用性目前依赖传递依赖。

### 6.3 DeepSeekProvider

DeepSeek provider 使用 lazy OpenAI SDK client，默认 base URL 为 `https://api.deepseek.com`。

本地 model profile：

| model/profile | tools | thinking | reasoning_content input |
| --- | --- | --- | --- |
| `deepseek-chat` | 是 | 否 | 否 |
| `deepseek-reasoner` | 否 | 是 | 否，发送前删除 |
| `deepseek-v4-pro` | 是 | 是 | 是 |
| 名称含 `reasoner` | 按 reasoner |
| 名称含 `v4` 或 `thinking` | 按 v4-pro |
| 其他 | 按 deepseek-chat |

provider class-level capabilities 是最宽的全局描述；真正请求校验使用上述 profile。

行为：

- tools + profile 不支持 -> `LLMCapabilityError`，网络调用前失败；
- thinking enabled + profile 不支持 -> capability error；
- thinking enabled -> `reasoning_effort` + `extra_body.thinking=enabled`；
- thinking-capable profile 未显式启用 -> `extra_body.thinking=disabled`；
- reasoning input 不允许时，复制 message 后移除字段；
- SDK client 没有显式配置 `max_retries`，其内部行为不属于 TaskWeavn retry policy。

对于 thinking-capable profile，即使 thinking disabled，代码也进入显式 disable 分支而不透传 temperature。这比“只在 thinking enabled 时忽略 temperature”更严格。

### 6.4 OpenRouterProvider

OpenRouter 当前继续通过 LiteLLM transport：

- 透传 model、api_key、messages、tools、timeout；
- routing 存在时写 `extra_body={"provider": ...}`；
- 不透传 ChatRequest.temperature 或 max_tokens；
- 不读取 ThinkingConfig；
- 不发送 top-level OpenRouter `session_id`；
- parser 把 provider_name 固定为 `openrouter`，不提取实际 upstream provider endpoint。

当 routing 为 `None` 时，provider 不发送 `provider` object，OpenRouter 平台默认规则生效。`ProviderRoutingConfig` 的 false/true 默认值只有在对象实际创建并发送时才生效。

## 7. 外部协议核验

### 7.1 DeepSeek，核验于 2026-07-10

官方当前文档：

- [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)
- [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)
- [Change Log](https://api-docs.deepseek.com/updates/)

已核验的当前约束：

1. `deepseek-v4-flash` 和 `deepseek-v4-pro` 均支持 thinking/non-thinking，官方默认 thinking。
2. OpenAI format 使用 `extra_body.thinking` 和 `reasoning_effort=high|max`。
3. thinking mode 不支持 temperature/top_p/presence/frequency penalty；兼容请求会忽略。
4. thinking tool-call turn 的 `reasoning_content` 必须在后续请求完整回传，否则 400。
5. V4 Flash/Pro 当前均支持 Tool Calls。
6. `deepseek-chat` 与 `deepseek-reasoner` 是兼容别名，将于 2026-07-24 15:59 UTC 停用；当前分别映射 V4 Flash 非思考/思考模式。

本地实现的 `deepseek-v4-pro` 路径与关键 thinking tool-call 回传要求一致。精确的 `deepseek-reasoner` profile 仍按旧式“无 tools、移除 reasoning input”处理；这与当前主模型表的 V4 alias 能力不一致，而且该别名即将停止服务。默认 model 已是 v4-pro，不依赖旧别名。

### 7.2 OpenRouter，核验于 2026-07-10

官方当前文档：

- [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Prompt Caching And Sticky Routing](https://openrouter.ai/docs/guides/best-practices/prompt-caching)

已核验的当前约束：

1. 未指定 provider object 时，OpenRouter 会在可用 providers 中做默认负载均衡和 fallback。
2. 官方默认 `allow_fallbacks=true`、`require_parameters=false`。
3. order、only、ignore、data_collection 和 ZDR 仍是有效 routing 字段。
4. 当前官方 provider object 还支持 sort、quantizations、throughput/latency preferences、max price 等本地模型未覆盖的字段。
5. OpenRouter 现在有自动 provider sticky routing；也支持 top-level/header `session_id` 让 agent workflow 更早获得稳定路由。
6. 显式 `provider.order` 优先于自动 sticky routing。

本地实现支持官方 routing 的一个子集。它不发送 session_id，也不读取实际 upstream provider。旧文档把“固定 provider”写成唯一 cache-stability 手段已经过时；当前平台有 sticky routing，但显式 pin/order 仍会改变 availability 与 fallback 语义。

### 7.3 验证边界

本次只核验官方协议和本地 request construction。仓库没有带真实凭据的 DeepSeek/OpenRouter integration test，因此不能从离线测试证明：

- 当前 SDK/LiteLLM 与真实 endpoint 完整兼容；
- provider 内部 retry 次数；
- OpenRouter 实际 upstream provider、fallback 或 sticky routing；
- 真实 usage/cache 字段在所有模型上都可用。

## 8. Response Normalization

三个 provider 共用 `parse_openai_compatible_response()`：

1. 直接读取 `response.choices[0]`；
2. content 不是字符串时变成空字符串；
3. 可选读取 `reasoning_content`；
4. tool_calls 可迭代时逐项解析；
5. 没有 function name 的 tool call 被跳过；
6. 缺失 tool call id 会保留为空字符串；
7. 构造 raw assistant message；
8. 解析 provider request id、usage 和少量 metadata。

空 choices、异常 response shape 等没有单独的 provider response validation error 类型；异常回到 retry layer 后按通用 exception 规则分类，通常可能是 unknown 并立即失败。

### 8.1 Reasoning preservation

只要 response message 有字符串 `reasoning_content`：

- 写入 `ChatResponse.reasoning_content`；
- 写入 `raw_assistant_message.reasoning_content`；
- AgentLoop 后续 transcript 保留；
- DeepSeek 下一次请求按 model profile 保留或删除。

是否保留不受 `ThinkingConfig.expose_reasoning_to_ui` 控制。

### 8.2 Usage parsing

shared parser读取：

- prompt/input tokens；
- completion/output tokens；
- total tokens；
- completion reasoning tokens；
- prompt cached tokens；
- DeepSeek-style prompt cache hit/miss tokens；
- cache hit ratio。

provider 不返回任何已知字段时，usage 为 `None`。本地不会估算缺失 token。

### 8.3 Raw response metadata

当前只保存 response 的：

- model；
- system_fingerprint；
- created。

`raw_response_metadata` 没有其他生产读取点，也没有被 provider response logger 输出。不能把它描述成完整 provider metadata 或 routing diagnostics。

## 9. 调用方失败策略

| 调用方 | LLM 输入/输出日志 | provider 最终失败后的行为 |
| --- | --- | --- |
| Execution AgentLoop | application `llm_io` + summary log | 写 `AgentErrorObservation`；timeout -> `llm_timeout`，其他 -> `llm_error`；Task executor 后续标记失败 |
| Collaborator profile runner | application `llm_io` + summary log | public authoring service 捕获并返回 `invalid_llm_proposal` error，消息包含 exception text |
| Runtime Input LLM planner | application `llm_io` + summary log | catch-all -> planner `unavailable`，Router 回到确定性路径 |
| Read-only Inquiry | application `llm_io` + summary log | catch-all -> baseline answer + provider unavailable warning |
| LLMRiskAssessor | 无 application `llm_io` helper；仍有 provider summary log | catch-all -> baseline risk，不中断 AgentLoop |
| AuditAgent | 自有 audit summary log，无 application `llm_io` helper | catch-all -> inconclusive AuditObservation |

Main Page 当前不装配 AuditAgent 或 LLMRiskAssessor。CLI audit/risk 可以复用主 LLM，因此仍会受 provider retry/timeout 影响，但没有独立 AUDIT/RISK provider resolver。

Execution AgentLoop 在 provider error 前没有 Action。它写 loop-level `AgentErrorObservation` 到 EventStream，message 包含 exception type/text。只有 AgentLoop interaction bus 被装配时才额外写 informational AgentMessage；Main Page 默认 AgentLoop 没有该 bus 字段。

### 9.1 Cooperative interruption

AgentLoop 在以下时点检查 Task interrupt intent：

- LLM call 前；
- LLM response 后；
- timeout exception 返回后。

它不能中断正在进行的同步 SDK call。若 timeout 返回时已存在 interrupt intent，AgentLoop 优先返回 `interrupted`；否则记录 `llm_timeout`。

Runtime Input planner 显式使用 30 秒 timeout。Read-only Inquiry provider 默认不覆盖 timeout，因此通常使用 role client/client 的默认值。Role profile 可以为每个当前装配角色提供 timeout。

## 10. Logging 与 Token Usage

### 10.1 Provider logs

每次 `_chat_once` 都会记录 provider request summary，因此 retry 会产生多条 request summary。字段包括 provider/model、purpose、message/tool count、timeout、thinking 和 provider-specific extra。

成功 response 记录 content length、tool call id/name、reasoning presence、usage 和 retry count。最终失败没有 provider response event；retry failure 有 retry warning，最终错误由调用方处理。

retry warning 的 `error_summary` 是原 exception string 截断，不是结构化 sanitizer 结果。若 SDK exception 文本包含敏感内容，字段名本身不会触发 key-based secret redaction。

### 10.2 Application LLM I/O logs

Execution、Collaborator、Router、Read-only Inquiry 调用 `log_agent_llm_input/output()`：

- `llm` category 记录计数和 metadata summary；
- `llm_io` category 在 INFO 记录完整 messages、tool schemas、content、reasoning_content、raw assistant message 和 tool arguments。

当前 LoggingManager 的 `payload_mode=summary/full` 只是规则 metadata，不会自动裁剪 data。因此默认 session logging 中 `llm_io` 的 summary rule 仍会写完整 payload，除非 category 被显式关闭或重定向。旧文档“prompt/full response 默认隐藏”不符合当前实现。

### 10.3 UsageRecordingLLM

Main Page role client 外层使用 `UsageRecordingLLM`：

- 只在 inner call 成功返回 `ChatResponse` 后写 usage event；
- usage 缺失时仍写 `usage_source=unavailable` 的 event；
- retry 成功只写一个 logical chat event，不为每个 attempt 写 event；
- 最终失败不写 usage event；
- sink 写失败被 suppress，不改变 LLM 返回；
- provider request id 只保存短 hash；
- metadata 只保留 allowlist 且过滤 path-like 值；
- prompt、completion、tool args 和 raw provider payload 不进入 usage DB。

usage event 存在 `<workspace>/.plato/usage.sqlite`，可以按 Workspace/Session/Plan/Task 聚合。

wrapper 顺序带来一个限制：`UsageRecordingLLM` 位于 `AgentConfiguredLLM` 外层，usage normalizer 收到的是调用方原 metadata，而不是 inner decorator 后加的 `agent_llm_role/profile`。provider/model 仍来自 response 和 profile model，调用方提供的 agent_kind/id 也可保留，但 profile 名不会自动进入 usage event。

## 11. 数据与安全边界

1. API key 不进入 ChatRequest metadata 或普通 provider request summary。
2. `LLMProviderError` 保留 original exception，message 也包含 provider exception text；它不是自动安全化的用户消息。
3. AgentLoop EventStream、Collaborator command error、Audit rationale 等路径可能保留 exception text。
4. `llm_io` 当前可持久化完整 prompt、tool schema、tool arguments、response 和 reasoning。
5. `reasoning_content` 不直接成为 Main Page answer，但会在内存 transcript 和日志中存在。
6. `expose_reasoning_to_ui=false` 当前没有 enforcement call site。
7. Usage DB 是单独的安全摘要层，不存 raw prompt/response，并 hash provider request id。
8. OpenRouter data_collection/ZDR 只有在 routing object 实际发送时才改变平台路由；Settings/环境配置状态本身不证明请求已经携带策略。

## 12. 当前已知限制

1. complete/count token 仍绕过 provider reliability 与 usage recording。
2. ProviderCapabilities 没有统一消费方，neutral 字段可能被 provider 静默忽略。
3. 默认 request timeout 触发时不会 retry；“自动重试”不是所有 transient error 的保证。
4. 通用 connection reset 没有显式 retry classification。
5. jitter 在 max-delay cap 后应用，实际 delay 可超过配置 max。
6. retry 不发送 generation idempotency key，也不观察 SDK 内部 retry。
7. 无 cross-provider fallback、circuit breaker、streaming、health check、hedging 或 rate limiter。
8. LiteLLM 是传递依赖，而非 `pyproject.toml` 直接依赖。
9. LiteLLM/OpenRouter 忽略 ThinkingConfig；LiteLLM 忽略 routing。
10. OpenRouter 当前忽略 temperature 和 max_tokens。
11. DeepSeek thinking-capable profile 在显式 disabled 时也不透传 temperature。
12. OpenRouter 不发送 session_id，也不解析实际 upstream provider。
13. `OPENROUTER_ZDR` 单独配置会被 env routing 创建条件忽略。
14. OpenRouter 本地 routing 模型只覆盖当前官方字段子集。
15. 精确 `deepseek-reasoner` profile 与当前 V4 alias 能力表不一致，且别名即将停用。
16. response parser 假设 choices[0] 存在，缺少独立 malformed-response error。
17. raw_response_metadata 没有生产消费者。
18. `expose_reasoning_to_ui` 没有实际 enforcement。
19. Main Page 只装配四个 role；audit/summary role 未接入。
20. Agent config parse error 可静默回退，inheritance cycle 则会抛出，失败策略不一致。
21. provider key 缺失在 lazy client 首次调用时才失败。
22. role clients 是 assembly-time 快照；Runtime Config 没有 LLM live consumer。
23. usage 不记录失败调用或 retry attempts，sink failure 也不会反向告警调用方。
24. role/profile decorator metadata 不会自动进入外层 usage event。
25. `llm_io` 默认规则仍可能写完整敏感 payload。
26. 没有真实凭据的 DeepSeek/OpenRouter integration tests。

## 13. 代码事实索引

Provider core：

- `src/taskweavn/llm/contracts.py`
- `src/taskweavn/llm/errors.py`
- `src/taskweavn/llm/retry.py`
- `src/taskweavn/llm/client.py`
- `src/taskweavn/llm/config.py`
- `src/taskweavn/llm/logging.py`
- `src/taskweavn/llm/providers/_openai_compat.py`
- `src/taskweavn/llm/providers/litellm.py`
- `src/taskweavn/llm/providers/deepseek.py`
- `src/taskweavn/llm/providers/openrouter.py`

Role config、usage 与 runtime：

- `src/taskweavn/llm/agent_config.py`
- `src/taskweavn/llm/agent_resolver.py`
- `src/taskweavn/usage/recording.py`
- `src/taskweavn/usage/store.py`
- `src/taskweavn/server/main_page_llm_helpers.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/runtime_config/defaults.py`
- `src/taskweavn/server/runtime_config_consumers.py`

主要调用方：

- `src/taskweavn/core/loop.py`
- `src/taskweavn/task/execution.py`
- `src/taskweavn/task/collaborator_profile_runner.py`
- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/server/runtime_input_llm_router.py`
- `src/taskweavn/server/read_only_inquiry_answer_provider.py`
- `src/taskweavn/interaction/risk.py`
- `src/taskweavn/audit/agent.py`
- `src/taskweavn/cli/main.py`

决策与实施历史：

- `docs/decisions/ADR-0006-llm-provider-transport-boundary.md`
- `docs/plans/feature/llm-provider-retry-thinking.md`
- `docs/releases/llm-provider-reliability.md`
- `docs/plans/feature/agent-llm-config-and-router-llm.md`
- `docs/engineering/token-usage-analytics-contract.md`
- `docs/plans/feature/cooperative-task-interruption-technical-design.zh-CN.md`

## 14. 验证原则

修改本架构事实时，至少验证：

- contracts 和 facade compatibility；
- timeout special case、retry success/exhaustion 和 fatal classification；
- 三个 provider 的 request construction 与 response parsing；
- role profile inheritance/resolver；
- AgentLoop timeout/error/interruption；
- Collaborator、Router、Read-only Inquiry、Risk、Audit 的调用方策略；
- usage normalization、redaction、aggregation；
- Main Page runtime 装配；
- 外部 DeepSeek/OpenRouter 官方协议是否变化。

具体命令与结果记录在
[fix-log/llm-provider-reliability.md](fix-log/llm-provider-reliability.md)。
