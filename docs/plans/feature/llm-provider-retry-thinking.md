# Feature Plan: LLM Provider 抽象、自动重试与 DeepSeek Thinking

> Status: planned  
> Type: 新特性支持  
> Last Updated: 2026-05-10  
> Owner/Session: planning session  
> Target Implementation Session: independent feature session  
> Related Code: `src/taskweavn/llm/client.py`, `tests/test_llm.py`

---

## 1. 背景

当前 TaskWeavn 的 LLM 层仍然偏“薄包装”：

- `LLMClient.complete()` 直接委托 `openhands.sdk.LLM`
- `LLMClient.chat()` 直接调用 `litellm.completion`
- 请求失败时只记录日志并重新抛出异常
- 没有统一 provider 抽象
- 没有 provider 级自动重试
- 没有 DeepSeek thinking mode 的请求参数和 `reasoning_content` 保留机制
- 使用 OpenRouter 时没有稳定指定唯一上游 provider，可能导致同一模型请求被路由到不同 provider，降低缓存命中率和行为一致性

这个计划的目标是把 LLM 调用从“一个 client 直接调第三方库”升级为“provider 驱动的可扩展调用层”。

---

## 2. 目标

1. 建立 provider 层抽象，后续可以实现多个 provider：
   - OpenAI
   - Anthropic
   - DeepSeek
   - OpenRouter
   - LiteLLM fallback / legacy provider
2. provider 层提供统一自动重试机制，子类可以重写错误分类、重试策略和请求构造。
3. 第一批落地 DeepSeek provider：
   - 使用官方文档推荐的 SDK 调用方式
   - 支持 thinking mode
   - 正确读取和保留 `reasoning_content`
   - 支持 ReAct 工具调用场景
4. 在接口层预留 OpenRouter provider routing 配置，支持固定唯一 provider 或固定 provider order。
5. 保持现有 `LLMClient` 对上层调用方尽量兼容，减少 AgentLoop、AuditAgent、RiskAssessor 的迁移成本。

---

## 3. 非目标

- 不在本计划中实现所有 provider。
- 不在第一版中实现 streaming UI。
- 不改 AgentLoop 的 ReAct 协议，除非 DeepSeek thinking tool-call 必须要求保留 assistant message 字段。
- 不实现模型自动选择、成本优化或 quota 系统。
- 不实现跨 provider fallback 策略；第一版只做单 provider 内 retry。

---

## 4. 当前代码事实

当前 `src/taskweavn/llm/client.py` 中：

- `LLMClient.__init__(model, api_key)` 只接收 model 和 api key。
- `from_env()` 只读取 `LLM_MODEL` 与 `LLM_API_KEY`。
- `chat()` 调用：

```python
litellm.completion(
    model=self._model,
    api_key=self._api_key,
    messages=messages,
    tools=tools,
)
```

- `chat()` 返回 `ChatResponse(content, tool_calls, raw_assistant_message)`。
- `raw_assistant_message` 当前只保留：
  - `role`
  - `content`
  - `tool_calls`
- 如果 provider 返回 `reasoning_content`，当前结构不会保留。
- 异常路径是 log + raise，没有 retry / classifier / fallback。

---

## 5. 主要问题

| 问题 | 影响 |
|---|---|
| 没有 provider 抽象 | 每个模型供应商的特殊能力会挤进 `LLMClient`，后续会越来越难维护 |
| 没有自动重试 | 临时网络抖动、429、5xx 会直接中断 AgentLoop |
| 错误不可分类 | 鉴权错误、参数错误、限流错误、服务临时错误无法采用不同策略 |
| DeepSeek thinking 未支持 | 无法使用 thinking mode，也无法保留 reasoning 信息 |
| Tool-call thinking 上下文不完整 | DeepSeek thinking + tool call 要求后续请求回传 `reasoning_content`，否则可能 400 |
| OpenRouter provider 不固定 | 默认路由可能跨 provider，缓存和行为一致性变差 |
| 配置入口过窄 | 只有 `LLM_MODEL` / `LLM_API_KEY`，无法表达 provider-specific 参数 |

---

## 6. 设计原则

- **Provider owns transport**：具体 SDK、base_url、extra_body、provider routing 都属于 provider。
- **LLMClient remains facade**：上层仍优先依赖 `LLMClient.chat()` / `complete()`。
- **Retry near transport**：重试发生在 provider 内部，而不是 AgentLoop 层。
- **Classify before retry**：只有 retryable error 才重试；参数错误和鉴权错误要快速失败。
- **Preserve provider-specific metadata**：provider 返回的 reasoning、provider id、request id、usage 都要能进入响应元数据。
- **No silent behavior drift**：OpenRouter 默认不得在用户期望缓存稳定时随意切换 provider。
- **Backwards compatible first**：现有测试和上层行为应先保持，再逐步启用新 provider。

---

## 7. 核心抽象

### 7.1 LLMProvider Protocol

接口草案：

```python
class LLMProvider(Protocol):
    name: str

    def chat(self, request: ChatRequest) -> ChatResponse:
        ...

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        ...

    def count_tokens(self, messages: list[MessageLike]) -> int:
        ...
```

第一版可以只强制 `chat()`，`complete()` / `count_tokens()` 允许 provider 抛出明确的 `UnsupportedCapabilityError`，但 `LLMClient` facade 要处理兼容。

### 7.2 ChatRequest

最低字段：

```python
class ChatRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    thinking: ThinkingConfig | None = None
    provider_routing: ProviderRoutingConfig | None = None
    metadata: dict[str, Any] = {}
```

注意：

- `thinking` 是跨 provider 的能力声明，不直接等同于某个 SDK 参数。
- `provider_routing` 主要服务 OpenRouter，但接口层先抽象出来。
- DeepSeek thinking mode 下需要过滤或忽略不支持的采样参数。

### 7.3 ChatResponse

现有 `ChatResponse` 需要扩展，但保持兼容：

```python
class ChatResponse:
    content: str
    tool_calls: list[ToolCall]
    raw_assistant_message: dict[str, Any]
    reasoning_content: str | None = None
    provider_name: str | None = None
    provider_request_id: str | None = None
    usage: LLMUsage | None = None
    retry_count: int = 0
```

关键点：

- `reasoning_content` 需要进入 `raw_assistant_message`，尤其是 DeepSeek thinking + tool call。
- 上层继续读取 `content` 和 `tool_calls` 不应破坏。
- provider 元数据可以先简略，后续接 observability。

### 7.4 RetryPolicy

```python
class RetryPolicy(BaseModel):
    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_status: tuple[int, ...] = (408, 409, 425, 429, 500, 502, 503, 504)
```

### 7.5 ProviderRoutingConfig

```python
class ProviderRoutingConfig(BaseModel):
    order: list[str] = []
    only: list[str] = []
    ignore: list[str] = []
    allow_fallbacks: bool = False
    require_parameters: bool = True
```

默认建议：

- 对 OpenRouter，缓存优先场景默认 `allow_fallbacks=False`。
- 如果设置 `only`，应只允许这些 provider。
- 如果设置 `order` 且 `allow_fallbacks=False`，应只按该顺序尝试，不回落到未声明 provider。

OpenRouter 官方文档说明其默认会在可用 provider 中路由；可通过 request body 的 `provider` 对象设置 `order`、`only`、`allow_fallbacks`、`require_parameters` 等字段。

---

## 8. Provider 基类需求

建议提供一个可复用基类：

```python
class BaseLLMProvider:
    retry_policy: RetryPolicy

    def chat(self, request: ChatRequest) -> ChatResponse:
        return self._with_retry(lambda: self._chat_once(request))

    def _chat_once(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    def classify_error(self, exc: Exception) -> ErrorClassification:
        ...
```

### 8.1 错误分类

| 分类 | 示例 | 默认行为 |
|---|---|---|
| `retryable` | timeout、connection reset、429、5xx | 指数退避重试 |
| `fatal_auth` | invalid api key、permission denied | 立即失败 |
| `fatal_request` | invalid model、bad schema、context too long | 立即失败 |
| `fatal_capability` | model 不支持 tools / thinking | 立即失败，错误信息要清楚 |
| `unknown` | 无法识别异常 | 默认不重试，或最多 1 次保守重试 |

### 8.2 重试记录

每次重试需要记录到 LLM 日志：

- provider
- model
- attempt
- max_attempts
- classification
- delay
- error type
- error message 摘要

成功响应需要记录：

- provider
- model
- retry_count
- request id（如果 provider 提供）
- usage（如果 provider 提供）

---

## 9. DeepSeek Provider 第一版

### 9.1 SDK 与官方文档

DeepSeek 官方 API 文档当前展示的是 OpenAI SDK 调用方式，并通过 DeepSeek `base_url` 发起请求。Thinking mode 文档要求使用 OpenAI 格式时：

- `reasoning_effort`
- `extra_body={"thinking": {"type": "enabled"}}`
- 响应中读取与 `content` 同级的 `reasoning_content`

官方文档还说明 thinking mode 不支持 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty` 等参数；这些参数即使传入也不会生效。

实现会话在编码前必须重新核对官方文档，避免 SDK 形态或模型名变化。

参考：

- DeepSeek Thinking Mode: `https://api-docs.deepseek.com/guides/thinking_mode`
- DeepSeek Reasoning Model: `https://api-docs.deepseek.com/guides/reasoning_model`

### 9.2 模型选择约束

需要区分两类能力：

| 模型 / 模式 | 能力 | UI / Agent 影响 |
|---|---|---|
| thinking mode，例如官方 thinking 文档里的 `deepseek-v4-pro` | 支持 thinking，并支持 tool calls | 可用于 ReAct 主循环 |
| `deepseek-reasoner` | 支持 reasoning output，但官方 reasoning model 文档说明不支持 Function Calling | 不适合作为当前 ReAct 工具调用主模型 |

因此第一版 DeepSeek provider 的目标不是“任意 DeepSeek reasoning 模型都能跑 ReAct”，而是：

- 对支持 tool calls 的 thinking mode 模型启用 ReAct。
- 对不支持 Function Calling 的 reasoning 模型，在配置或启动时给出明确错误。

### 9.3 ThinkingConfig

```python
class ThinkingConfig(BaseModel):
    enabled: bool = False
    effort: Literal["high", "max"] = "high"
    expose_reasoning_to_ui: bool = False
```

说明：

- `enabled=True` 时，DeepSeek provider 负责生成 provider-specific 参数。
- `expose_reasoning_to_ui` 第一版默认 `False`，避免 UI 误把推理内容当最终答案。
- 即使不展示给用户，也必须在需要时保留到 `raw_assistant_message`。

### 9.4 Tool-call 上下文要求

DeepSeek thinking mode 文档要求：如果 assistant turn 产生了 tool call，则后续请求必须回传该 turn 的 `reasoning_content`，否则 API 可能返回 400。

这意味着现有 `raw_assistant_message` 结构必须扩展：

```python
{
    "role": "assistant",
    "content": content,
    "reasoning_content": reasoning_content,
    "tool_calls": [...]
}
```

验收重点：

- 有 tool call 时，`reasoning_content` 必须保留。
- 无 tool call 时，可以保留但不强制参与后续上下文。
- AgentLoop 追加 assistant message 时不能丢失 provider-specific 字段。

---

## 10. OpenRouter Provider Routing 需求

OpenRouter 官方文档说明默认会在模型可用 provider 中做路由；为了提高缓存命中率和行为稳定性，TaskWeavn 需要支持固定 provider。

第一版接口要求：

```yaml
llm:
  provider: openrouter
  model: deepseek/deepseek-r1
  provider_routing:
    only: ["deepinfra/turbo"]
    order: ["deepinfra/turbo"]
    allow_fallbacks: false
    require_parameters: true
```

Provider 行为要求：

- 如果配置 `only`，请求必须携带 `provider.only`。
- 如果配置 `order`，请求必须携带 `provider.order`。
- 缓存优先时默认 `allow_fallbacks=false`。
- 如果需要高可用而非缓存优先，可显式改为 `allow_fallbacks=true`。
- 响应日志应尽量记录实际 provider / route 信息，如果 API 返回。

参考：

- OpenRouter Provider Routing: `https://openrouter.ai/docs/provider-routing`

---

## 11. 配置入口

建议新增或扩展环境变量：

| 环境变量 | 说明 |
|---|---|
| `LLM_PROVIDER` | `litellm` / `deepseek` / `openrouter` / `openai` / `anthropic` |
| `LLM_MODEL` | provider 内模型名 |
| `LLM_API_KEY` | 通用 api key，保持兼容 |
| `DEEPSEEK_API_KEY` | DeepSeek provider 优先读取 |
| `DEEPSEEK_BASE_URL` | 可选，默认 DeepSeek 官方 API base url |
| `LLM_THINKING_ENABLED` | `true` / `false` |
| `LLM_THINKING_EFFORT` | `high` / `max` |
| `OPENROUTER_API_KEY` | OpenRouter provider 优先读取 |
| `OPENROUTER_PROVIDER_ONLY` | 逗号分隔 provider slug |
| `OPENROUTER_PROVIDER_ORDER` | 逗号分隔 provider slug |
| `OPENROUTER_ALLOW_FALLBACKS` | `true` / `false` |

后续配置系统落地后，应迁移到统一配置文件；环境变量只作为 v1 入口。

---

## 12. 执行切片

### Slice 1: Provider Contracts

产出：

- `LLMProvider` Protocol
- `ChatRequest`
- `CompletionRequest`
- `RetryPolicy`
- `ProviderRoutingConfig`
- `ThinkingConfig`
- `ProviderError` / `ErrorClassification`
- `ChatResponse` 兼容扩展

验收：

- 现有 `LLMClient.chat()` 调用方不需要修改或只需要极小修改。
- 离线单元测试覆盖 contract 和基础 serialization。

### Slice 2: Retry Base Provider

产出：

- `BaseLLMProvider`
- `_with_retry`
- 默认错误分类
- retry logging
- 可重写 hooks：
  - `classify_error`
  - `prepare_request`
  - `parse_response`

验收：

- 模拟 429 后成功：自动重试并返回。
- 模拟 500 后成功：自动重试并记录 retry_count。
- 模拟 auth error：不重试。
- 模拟 bad request：不重试。
- 达到最大次数后抛出结构化错误。

### Slice 3: LLMClient Facade Migration

产出：

- `LLMClient` 接收 provider 或从 env 构造 provider。
- 默认 provider 可以先保持 `litellm`，保证现有行为不破。
- `from_env()` 支持 `LLM_PROVIDER`。
- 现有 `complete()` / `count_tokens()` 兼容旧路径。

验收：

- 现有 `tests/test_llm.py` 通过。
- 新增 provider selection 测试。
- 无 provider 配置时行为与当前版本一致。

### Slice 4: DeepSeek Provider

产出：

- `DeepSeekProvider`
- 官方 SDK 初始化
- thinking mode 参数注入
- `reasoning_content` 解析
- tool call 解析
- `raw_assistant_message` 保留 `reasoning_content`
- 不支持 Function Calling 的模型给出明确错误

验收：

- thinking disabled：普通 chat 正常。
- thinking enabled：请求包含 thinking 参数。
- response 有 `reasoning_content`：`ChatResponse.reasoning_content` 可读。
- thinking + tool_calls：`raw_assistant_message` 包含 `reasoning_content` 和 `tool_calls`。
- 传入不支持 thinking/tool 的模型时，错误清晰。
- 单元测试不访问真实网络。

### Slice 5: OpenRouter Routing Interface

产出：

- `ProviderRoutingConfig` 到 OpenRouter request body 的映射。
- 支持 `only` / `order` / `allow_fallbacks` / `require_parameters`。
- 即使 OpenRouter provider 实现放到后续，当前接口也应可被配置和测试。

验收：

- `allow_fallbacks=false` 时，构造出的请求不允许回落到未声明 provider。
- `only=["deepinfra/turbo"]` 时，请求只允许该 provider。
- provider routing 配置进入日志，便于排查缓存问题。

### Slice 6: Observability and Docs

产出：

- LLM 日志新增 provider、retry、reasoning、routing 字段。
- 更新用户文档：
  - 如何配置 DeepSeek thinking
  - 如何固定 OpenRouter provider
  - 重试策略默认值

验收：

- 失败日志能看出是否重试、重试几次、为什么失败。
- OpenRouter 请求日志能看出 provider routing 配置。

---

## 13. 测试计划

### 13.1 单元测试

- `test_provider_contracts.py`
- `test_llm_retry_policy.py`
- `test_deepseek_provider.py`
- `test_openrouter_routing_config.py`
- 扩展 `test_llm.py`

### 13.2 关键测试场景

| 场景 | 期望 |
|---|---|
| provider 第一次 429，第二次成功 | 自动重试，返回成功响应 |
| provider 连续 500 超过最大次数 | 抛出结构化 retry exhausted error |
| auth error | 不重试 |
| bad request / schema error | 不重试 |
| DeepSeek thinking response | 解析 `reasoning_content` |
| DeepSeek thinking + tool call | `raw_assistant_message` 保留 `reasoning_content` |
| DeepSeek unsupported model + tools | 明确失败 |
| OpenRouter fixed provider | 请求中包含固定 provider routing |
| legacy litellm path | 现有行为保持 |

### 13.3 手动验收

实现会话完成后，准备至少两个手动用例：

1. DeepSeek thinking + 简单工具调用：
   - 用户请求需要读文件或列目录。
   - LLM 返回 tool call。
   - 后续请求不因缺少 `reasoning_content` 报 400。
2. OpenRouter 固定 provider：
   - 配置 `only` / `order` / `allow_fallbacks=false`。
   - 检查请求日志中 provider routing 稳定。

---

## 14. 风险与决策点

| 风险 | 处理 |
|---|---|
| DeepSeek SDK / API 参数变化 | 实现前重新查官方文档； provider 代码集中封装 |
| `ChatResponse` 扩展影响上层 | 新字段必须有默认值，保持旧调用兼容 |
| thinking 内容是否展示给用户 | 第一版默认不展示，只保留给上下文和审计 |
| OpenRouter 固定 provider 降低可用性 | 默认缓存优先；高可用场景显式打开 fallback |
| Retry 导致重复副作用 | LLM 请求本身应无外部副作用；工具执行不在 provider retry 内 |
| LiteLLM 仍然有价值 | 保留 `LiteLLMProvider` 作为 legacy / fallback |

---

## 15. 完成标准

该 feature 完成时，应满足：

- 有 provider 抽象，`LLMClient` 不再直接绑定某一个第三方调用路径。
- provider 基类支持自动重试，且错误分类可重写。
- DeepSeek provider 可用，支持 thinking mode 和 `reasoning_content`。
- DeepSeek thinking + tool call 的上下文拼接不会丢失 reasoning 信息。
- OpenRouter provider routing 的接口和请求构造支持固定唯一 provider。
- 现有 LLM 单元测试仍通过，并新增 provider / retry / thinking 覆盖。
- 文档说明如何配置 DeepSeek thinking 和 OpenRouter fixed provider。

---

## 16. 状态

- Status: planned
- Created: 2026-05-10
- Next Step: 在独立实现会话中创建 feature 分支，先做 Slice 1 + Slice 2，再落地 DeepSeek provider。
