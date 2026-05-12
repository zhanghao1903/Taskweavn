# LLM Provider Reliability Technical Design

> Status: implemented
> Last Updated: 2026-05-11
> Scope: server core execution line
> Related Plan: [LLM provider retry thinking](../plans/feature/llm-provider-retry-thinking.md)
> Related Roadmap: [Phase 3B — Reliability And Observability](../roadmap.md#phase-3b--reliability-and-observability)

---

## 1. Background

TaskWeavn currently treats the LLM layer as a thin adapter:

- `LLMClient.complete()` delegates to `openhands.sdk.LLM`.
- `LLMClient.chat()` calls `litellm.completion(...)` directly.
- failures are logged and re-raised;
- provider-specific behavior is not modeled;
- DeepSeek thinking mode is not supported;
- OpenRouter provider routing is not pinned, so the same model can be routed to different upstream providers.

This is acceptable for early experiments, but not for TaskWeavn's next phase. The system is moving toward long-running Task execution, user confirmations, Collaborator Agent planning, and multi-step server workflows. In that world, LLM transport must become reliable, observable, configurable, and provider-aware.

This document defines the server-side technical design for the implemented roadmap item: **LLM Provider abstraction, automatic retry, DeepSeek thinking, and OpenRouter provider routing**.

---

## 2. Current Code Facts

Current implementation:

```text
src/taskweavn/llm/client.py
  ToolCall
  ChatResponse
  LLMClient
  tool_schema_from_action
  parse_tool_arguments
```

Current `LLMClient.chat(...)` shape:

```python
response = litellm.completion(
    model=self._model,
    api_key=self._api_key,
    messages=messages,
    tools=tools,
)
```

Current response object:

```python
@dataclass(frozen=True)
class ChatResponse:
    content: str
    tool_calls: list[ToolCall]
    raw_assistant_message: dict[str, Any]
```

Current limitations:

| Limitation | Impact |
|---|---|
| no provider abstraction | DeepSeek/OpenRouter/OpenAI/Anthropic behavior will keep leaking into `LLMClient` |
| no retry policy | transient 429/5xx/network errors can end a long-running task |
| no error classification | auth/config/schema/capability errors are indistinguishable from transient failures |
| no provider metadata | cannot audit actual provider, request id, usage, retry count |
| no `reasoning_content` support | DeepSeek thinking + tool calls can fail or lose context |
| no routing config | OpenRouter can load-balance to varying providers, reducing cache stability |

---

## 3. Goals

1. Introduce a provider boundary under `LLMClient`.
2. Keep `LLMClient` as the facade used by AgentLoop, AuditAgent, RiskAssessor, and future Agents.
3. Add provider-level automatic retry with explicit error classification.
4. Add DeepSeek provider using the OpenAI-compatible SDK path.
5. Support DeepSeek thinking mode and preserve `reasoning_content` where required.
6. Support OpenRouter provider routing configuration.
7. Preserve the legacy LiteLLM path as the default until users opt into a specific provider.
8. Make provider metadata observable without waiting for the full logging-system redesign.

---

## 4. Non-goals

- Do not implement every provider in the first slice.
- Do not implement streaming UI.
- Do not implement cross-provider fallback in the first version.
- Do not implement model selection, cost optimization, or quota policy here.
- Do not replace the later configurable logging system.
- Do not expose raw reasoning to users by default.

---

## 5. Key External Constraints

This design was checked against current official docs on 2026-05-11.

### 5.1 DeepSeek thinking mode

DeepSeek thinking mode uses OpenAI-compatible request fields:

- `extra_body={"thinking": {"type": "enabled"}}`
- `reasoning_effort="high" | "max"`
- response message includes `reasoning_content` at the same level as `content`.

DeepSeek docs state that thinking mode does not support `temperature`, `top_p`, `presence_penalty`, or `frequency_penalty`; compatibility may make these parameters no-op rather than hard failures.

DeepSeek thinking mode supports tool calls, but there is a critical context rule:

- if an assistant turn performs tool calls, its `reasoning_content` must be passed back in subsequent requests;
- failing to pass it back can produce a 400 error.

Reference: <https://api-docs.deepseek.com/guides/thinking_mode>

### 5.2 DeepSeek `deepseek-reasoner`

`deepseek-reasoner` is different from thinking mode:

- it exposes `reasoning_content`;
- it does not support Function Calling;
- passing `reasoning_content` back in input messages can produce a 400 error.

So `deepseek-reasoner` is not a valid ReAct tool-calling model for the current AgentLoop. It can be useful for non-tool reasoning calls later, but the first DeepSeek provider must fail fast if tools are passed to a model capability that cannot call tools.

Reference: <https://api-docs.deepseek.com/zh-cn/guides/reasoning_model>

### 5.3 OpenRouter provider routing

OpenRouter load-balances requests by default. The request body can include a `provider` object with routing fields such as:

- `order`
- `allow_fallbacks`
- `require_parameters`
- `data_collection`
- `zdr`

For TaskWeavn, the most important fields are:

- `order`: provider slug priority list;
- `allow_fallbacks`: whether backup providers are allowed;
- `require_parameters`: only route to providers that support all request parameters.

Reference: <https://openrouter.ai/docs/guides/routing/provider-selection>

---

## 6. Architecture Decision Summary

| Decision | Choice | Reason |
|---|---|---|
| LLM entry point | keep `LLMClient` facade | preserve current callers |
| provider boundary | add `LLMProvider` Protocol | isolate SDK/API/provider behavior |
| first default | `LiteLLMProvider` | no behavior drift for current users |
| retry location | provider base class | retry belongs near transport, not AgentLoop |
| error model | typed provider errors + classification | avoid retrying auth/schema/capability failures |
| response model | extend `ChatResponse` compatibly | keep existing `content/tool_calls/raw_assistant_message` access |
| DeepSeek SDK path | OpenAI SDK with DeepSeek `base_url` | matches official docs and current dependency graph |
| thinking default | disabled in TaskWeavn unless configured | preserve current non-thinking behavior; pass explicit disable where provider defaults differ |
| reasoning exposure | store but do not show by default | needed for correctness/audit, not UX yet |
| OpenRouter default | cache-stable routing when configured | avoid silent provider drift |

---

## 7. Module Layout

Proposed server-side layout:

```text
src/taskweavn/llm/
  __init__.py
  client.py                 # facade, compatibility API
  contracts.py              # request/response/config models and Protocol
  errors.py                 # provider error hierarchy
  retry.py                  # RetryPolicy and BaseLLMProvider retry loop
  providers/
    __init__.py
    litellm.py              # current behavior wrapped as provider
    deepseek.py             # official SDK / OpenAI-compatible provider
    openrouter.py           # routing-aware provider, can initially share LiteLLM transport
  config.py                 # env/config parsing and provider factory
```

The first implementation can merge small files if useful, but the conceptual boundaries should remain clear:

- `contracts.py`: stable API.
- `errors.py`: failure vocabulary.
- `retry.py`: generic retry behavior.
- `providers/*`: transport-specific code.
- `client.py`: facade only.

---

## 8. Public Contracts

### 8.1 LLMProvider Protocol

```python
@runtime_checkable
class LLMProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    def chat(self, request: ChatRequest) -> ChatResponse:
        ...

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        ...

    def count_tokens(self, request: TokenCountRequest) -> int:
        ...
```

Implementation note:

- First version can require only `chat`.
- Unsupported methods should raise `UnsupportedCapabilityError`, not `NotImplementedError`.
- `LLMClient.complete()` can keep using `openhands.sdk.LLM` until a provider supports it.

### 8.2 ProviderCapabilities

```python
class ProviderCapabilities(BaseModel):
    chat: bool = True
    completion: bool = False
    token_count: bool = False
    tool_calls: bool = True
    thinking: bool = False
    reasoning_content_output: bool = False
    reasoning_content_input: bool = False
    provider_routing: bool = False
```

Rules:

- DeepSeek thinking mode provider: `thinking=True`, `tool_calls=True`, `reasoning_content_output=True`, `reasoning_content_input=True`.
- `deepseek-reasoner` profile: `thinking=True`, `tool_calls=False`, `reasoning_content_output=True`, `reasoning_content_input=False`.
- OpenRouter provider: `provider_routing=True`.

### 8.3 ChatRequest

```python
class ChatRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    thinking: ThinkingConfig | None = None
    provider_routing: ProviderRoutingConfig | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

`metadata` is not sent to provider by default. It is for logs and tracing:

- session_id;
- task_id;
- agent_id;
- request_purpose, such as `react_loop`, `audit`, `risk_assessment`, `collaborator`.

### 8.4 ThinkingConfig

```python
class ThinkingConfig(BaseModel):
    enabled: bool = False
    effort: Literal["high", "max"] = "high"
    expose_reasoning_to_ui: bool = False
```

Provider behavior:

- if disabled and provider default is enabled, provider should explicitly disable thinking when possible;
- if enabled, provider maps this to its native parameters;
- `expose_reasoning_to_ui` affects future UI projection only, not transport correctness.

### 8.5 ProviderRoutingConfig

```python
class ProviderRoutingConfig(BaseModel):
    order: tuple[str, ...] = ()
    only: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    allow_fallbacks: bool = False
    require_parameters: bool = True
    data_collection: Literal["allow", "deny"] | None = None
    zdr: bool | None = None
```

OpenRouter mapping:

```python
{
    "provider": {
        "order": [...],
        "only": [...],
        "ignore": [...],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
    }
}
```

Fields with `None` or empty tuples should be omitted.

### 8.6 RetryPolicy

```python
class RetryPolicy(BaseModel):
    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_status: tuple[int, ...] = (408, 409, 425, 429, 500, 502, 503, 504)
```

Validation:

- `max_attempts >= 1`;
- delays must be non-negative;
- `max_delay_seconds >= initial_delay_seconds`.

### 8.7 ChatResponse

Extend current dataclass compatibly:

```python
@dataclass(frozen=True)
class ChatResponse:
    content: str
    tool_calls: list[ToolCall]
    raw_assistant_message: dict[str, Any]
    reasoning_content: str | None = None
    provider_name: str | None = None
    provider_request_id: str | None = None
    usage: LLMUsage | None = None
    retry_count: int = 0
    retry_records: tuple[RetryRecord, ...] = ()
    raw_response_metadata: dict[str, Any] = field(default_factory=dict)
```

Compatibility rule:

- existing code that reads `content`, `tool_calls`, or `raw_assistant_message` must keep working.
- field order must keep the three existing required fields first.

### 8.8 LLMUsage and RetryRecord

```python
class LLMUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
```

```python
class RetryRecord(BaseModel):
    attempt: int
    max_attempts: int
    classification: ErrorClassification
    provider_name: str
    model: str
    delay_seconds: float
    error_type: str
    error_summary: str
```

---

## 9. Error Model

### 9.1 ErrorClassification

```python
class ErrorClassification(StrEnum):
    RETRYABLE = "retryable"
    FATAL_AUTH = "fatal_auth"
    FATAL_REQUEST = "fatal_request"
    FATAL_CAPABILITY = "fatal_capability"
    RATE_LIMIT = "rate_limit"
    CONTEXT_LIMIT = "context_limit"
    UNKNOWN = "unknown"
```

Retry rule:

| Classification | Retry? | Examples |
|---|---:|---|
| `RETRYABLE` | yes | timeout, connection reset, 5xx |
| `RATE_LIMIT` | yes | 429, provider quota throttle |
| `FATAL_AUTH` | no | invalid key, permission denied |
| `FATAL_REQUEST` | no | schema error, unsupported parameter |
| `FATAL_CAPABILITY` | no | tools passed to model without function calling |
| `CONTEXT_LIMIT` | no | context too long; fix requires prompt compaction |
| `UNKNOWN` | no by default | unless provider overrides |

### 9.2 Error classes

```python
class LLMError(Exception): ...
class LLMProviderError(LLMError): ...
class LLMRetryExhaustedError(LLMProviderError): ...
class LLMAuthError(LLMProviderError): ...
class LLMRequestError(LLMProviderError): ...
class LLMCapabilityError(LLMProviderError): ...
class LLMContextLimitError(LLMProviderError): ...
```

All provider errors should carry:

- provider name;
- model;
- classification;
- original error type;
- safe summary;
- retry records.

---

## 10. Request Lifecycle

### 10.1 Facade lifecycle

```text
caller
  -> LLMClient.chat(messages, tools)
  -> ChatRequest(model, messages, tools, config, metadata)
  -> provider.chat(request)
  -> ChatResponse
  -> caller appends raw_assistant_message to loop history
```

`LLMClient` should not know DeepSeek/OpenRouter details. It chooses a provider and forwards request objects.

### 10.2 Provider lifecycle

```text
provider.chat(request)
  -> validate capabilities
  -> normalize request
  -> run BaseLLMProvider._with_retry(...)
      -> prepare provider-specific request
      -> send transport call
      -> parse provider response
      -> return ChatResponse
  -> provider-level logs/metadata
```

### 10.3 Retry lifecycle

```text
attempt 1
  -> exception
  -> classify
  -> if retryable and attempt < max_attempts:
       log retry
       sleep with backoff + jitter
       attempt 2
  -> else:
       raise typed provider error
```

Retry never wraps tool execution. Only pure LLM request transport can be retried.

---

## 11. Provider Designs

### 11.1 LiteLLMProvider

Purpose:

- wrap current `litellm.completion(...)` behavior;
- remain default provider;
- preserve existing tests and behavior.

Behavior:

- supports `chat`;
- may support provider routing only through LiteLLM-compatible extra kwargs if explicitly added;
- no thinking support in first slice unless already available through underlying model/provider.

Required tests:

- legacy `LLMClient.chat(...)` behavior remains compatible;
- tool call parsing unchanged;
- raw assistant message shape unchanged except extra optional metadata.

### 11.2 DeepSeekProvider

Purpose:

- official OpenAI-compatible SDK path;
- support thinking mode;
- preserve `reasoning_content`;
- fail fast on unsupported model/tool combinations.

Construction:

```python
client = OpenAI(
    api_key=api_key,
    base_url=base_url or "https://api.deepseek.com",
)
```

Request mapping:

```python
client.chat.completions.create(
    model=request.model,
    messages=normalized_messages,
    tools=request.tools,
    reasoning_effort=request.thinking.effort,
    extra_body={"thinking": {"type": "enabled"}},
)
```

When `thinking.enabled=False`, provider should explicitly disable thinking if the API supports it:

```python
extra_body={"thinking": {"type": "disabled"}}
```

This preserves TaskWeavn's current non-thinking default.

Tool-call reasoning rule:

- if a response contains `tool_calls` and `reasoning_content`, include both in `raw_assistant_message`;
- AgentLoop already appends `raw_assistant_message`, so preserving the field is enough for subsequent requests.

Capability guard:

```text
if request.tools and selected model profile does not support tool calls:
    raise LLMCapabilityError(...)
```

DeepSeek model profile table, first version:

| Profile | Tool calls | Thinking/reasoning | Input `reasoning_content` |
|---|---:|---:|---:|
| `deepseek-v4-pro` thinking mode | yes | yes | yes when tool calls occurred |
| `deepseek-reasoner` | no | yes | no |
| `deepseek-chat` | yes | no | no |

The table should be configuration-driven, not hard-coded forever. First implementation can start with known defaults plus override hooks.

### 11.3 OpenRouterProvider

Purpose:

- make provider routing explicit;
- avoid silent provider drift;
- support cache-stable routing.

Transport options:

1. use OpenRouter SDK if adopted later;
2. use OpenAI-compatible client with OpenRouter base URL;
3. use LiteLLM with provider-specific kwargs if easier.

First version can focus on request construction and tests even if the full transport still goes through LiteLLM.

Request mapping:

```python
extra_body = {
    "provider": provider_routing.to_openrouter_dict()
}
```

Default policy:

- if `provider_routing` is configured, default `allow_fallbacks=False`;
- if no routing is configured, preserve OpenRouter default behavior;
- if `require_parameters=True`, do not route to providers that ignore requested parameters.

---

## 12. Configuration

### 12.1 Environment variables

First version supports env vars:

| Env var | Meaning |
|---|---|
| `LLM_PROVIDER` | `litellm`, `deepseek`, `openrouter` |
| `LLM_MODEL` | provider-local model id |
| `LLM_API_KEY` | generic fallback API key |
| `DEEPSEEK_API_KEY` | DeepSeek-specific key |
| `DEEPSEEK_BASE_URL` | optional override |
| `LLM_THINKING_ENABLED` | `true` / `false` |
| `LLM_THINKING_EFFORT` | `high` / `max` |
| `OPENROUTER_API_KEY` | OpenRouter-specific key |
| `OPENROUTER_PROVIDER_ORDER` | comma-separated provider slugs |
| `OPENROUTER_PROVIDER_ONLY` | comma-separated provider slugs |
| `OPENROUTER_PROVIDER_IGNORE` | comma-separated provider slugs |
| `OPENROUTER_ALLOW_FALLBACKS` | `true` / `false` |
| `OPENROUTER_REQUIRE_PARAMETERS` | `true` / `false` |

### 12.2 Future config file shape

```yaml
llm:
  provider: deepseek
  model: deepseek-v4-pro
  api_key_env: DEEPSEEK_API_KEY
  retry:
    max_attempts: 3
    initial_delay_seconds: 0.5
    max_delay_seconds: 8.0
  thinking:
    enabled: true
    effort: high
    expose_reasoning_to_ui: false
```

OpenRouter:

```yaml
llm:
  provider: openrouter
  model: deepseek/deepseek-r1
  provider_routing:
    order: ["deepinfra/turbo"]
    only: ["deepinfra/turbo"]
    allow_fallbacks: false
    require_parameters: true
    data_collection: deny
```

---

## 13. Observability

This feature should not wait for the full configurable logging system, but it must emit useful structured fields through the current `llm` channel.

### 13.1 Request log fields

- provider;
- model;
- request_purpose;
- session_id;
- task_id;
- agent_id;
- tool_count;
- thinking_enabled;
- thinking_effort;
- provider_routing summary;
- prompt/message count;
- redacted prompt hash if possible.

### 13.2 Retry log fields

- provider;
- model;
- attempt;
- max_attempts;
- classification;
- delay_seconds;
- error_type;
- error_summary.

### 13.3 Response log fields

- provider;
- model;
- provider_request_id;
- retry_count;
- usage;
- content length;
- tool call names;
- has_reasoning_content;
- raw provider metadata summary.

Prompt and full response should remain summary-level by default. Full payload belongs to the configurable logging plan.

---

## 14. Migration Plan

### Slice 1: contracts and errors

Files:

- `src/taskweavn/llm/contracts.py`
- `src/taskweavn/llm/errors.py`

Add:

- `LLMProvider`;
- request/config models;
- extended response fields;
- typed error hierarchy.

Acceptance:

- no behavior change;
- contract tests pass;
- existing imports from `taskweavn.llm.client` still work.

### Slice 2: retry base provider

Files:

- `src/taskweavn/llm/retry.py`
- `tests/test_llm_retry_policy.py`

Add:

- `BaseLLMProvider`;
- retry loop;
- classification hooks;
- retry record collection.

Acceptance:

- retryable errors retry;
- auth/request/capability errors do not retry;
- exhausted retries raise `LLMRetryExhaustedError`.

### Slice 3: LiteLLMProvider and facade migration

Files:

- `src/taskweavn/llm/providers/litellm.py`
- `src/taskweavn/llm/client.py`
- `src/taskweavn/llm/config.py`

Acceptance:

- default behavior remains compatible;
- `LLMClient.from_env()` supports `LLM_PROVIDER`;
- current `tests/test_llm.py` still passes.

### Slice 4: DeepSeekProvider

Files:

- `src/taskweavn/llm/providers/deepseek.py`
- `tests/test_deepseek_provider.py`

Acceptance:

- thinking request maps to DeepSeek fields;
- response parses `reasoning_content`;
- tool-call assistant message preserves `reasoning_content`;
- unsupported model/tool combination fails fast;
- tests use fake SDK/client objects, no real network.

### Slice 5: OpenRouter routing

Files:

- `src/taskweavn/llm/providers/openrouter.py`
- `tests/test_openrouter_routing_config.py`

Acceptance:

- `ProviderRoutingConfig` serializes correctly;
- `allow_fallbacks=false` is represented in provider body;
- `require_parameters=true` is represented;
- route metadata is logged.

### Slice 6: docs and integration

Files:

- `docs/plans/feature/llm-provider-retry-thinking.md`
- `docs/architecture/reference.md`
- user-facing config docs, if present.

Acceptance:

- docs explain DeepSeek thinking config;
- docs explain OpenRouter provider pinning;
- roadmap/release docs can be updated after implementation.

---

## 15. Test Plan

### 15.1 Unit tests

| Test file | Coverage |
|---|---|
| `tests/test_llm_contracts.py` | request/config validation, serialization, compatibility |
| `tests/test_llm_retry_policy.py` | retry loop and classification |
| `tests/test_litellm_provider.py` | legacy behavior wrapper |
| `tests/test_deepseek_provider.py` | thinking fields, reasoning parsing, tool-call preservation |
| `tests/test_openrouter_routing_config.py` | routing body construction |
| `tests/test_llm.py` | current facade behavior remains stable |

### 15.2 Critical cases

| Case | Expected |
|---|---|
| first call 429, second succeeds | returns response with `retry_count=1` |
| repeated 500 until max attempts | raises `LLMRetryExhaustedError` |
| invalid API key | no retry |
| invalid request schema | no retry |
| context too long | no retry, classification `CONTEXT_LIMIT` |
| thinking enabled response | `reasoning_content` is available |
| thinking + tool calls | `raw_assistant_message` includes `reasoning_content` and `tool_calls` |
| `deepseek-reasoner` with tools | raises `LLMCapabilityError` |
| OpenRouter fixed provider | body includes provider routing fields |
| no provider env set | legacy default remains compatible |

### 15.3 Manual smoke tests

DeepSeek thinking:

```text
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-pro
LLM_THINKING_ENABLED=true
```

Run a simple tool-calling prompt. Verify:

- tool call works;
- follow-up LLM call does not 400;
- log shows `has_reasoning_content=true`.

OpenRouter fixed provider:

```text
LLM_PROVIDER=openrouter
LLM_MODEL=deepseek/deepseek-r1
OPENROUTER_PROVIDER_ONLY=deepinfra/turbo
OPENROUTER_ALLOW_FALLBACKS=false
OPENROUTER_REQUIRE_PARAMETERS=true
```

Verify:

- provider routing object is present;
- logs show routing summary;
- repeated calls use the same configured route unless the request fails.

---

## 16. Compatibility Notes

### 16.1 Existing callers

Existing callers should continue to use:

```python
response = llm.chat(messages, tools)
```

They should not construct providers directly unless they are tests or advanced configuration code.

### 16.2 AgentLoop

AgentLoop already appends `response.raw_assistant_message` to the message history. That is good. The key implementation requirement is that provider-specific fields required for future requests must be preserved in `raw_assistant_message`.

For DeepSeek thinking + tool calls, that means:

```python
{
    "role": "assistant",
    "content": content,
    "reasoning_content": reasoning_content,
    "tool_calls": [...]
}
```

### 16.3 AuditAgent and LLMRiskAssessor

AuditAgent and LLMRiskAssessor should not change in the first migration except for benefiting from retry and provider metadata.

Later, they may use cheaper/different provider configs:

- `AUDIT_LLM_PROVIDER`;
- `RISK_LLM_PROVIDER`;
- smaller models for frequent risk assessment.

---

## 17. Open Questions

| Question | Default for first implementation |
|---|---|
| Should `openai` become a direct dependency? | Yes, if DeepSeek provider imports it directly. Do not rely on transitive LiteLLM dependency. |
| Should thinking default to DeepSeek provider default? | No. TaskWeavn should preserve current behavior and require explicit enablement. |
| Should reasoning be visible in UI? | No. Store/preserve it, but do not expose by default. |
| Should OpenRouter fallback default be disabled globally? | Only when routing config is explicitly provided. Without config, preserve OpenRouter default. |
| Should provider retry include cross-provider fallback? | No. Keep first version single-provider retry. |
| Should streaming be supported now? | No. Leave a future streaming contract, but keep synchronous chat first. |

---

## 18. Completion Criteria

This technical design is implemented when:

- `LLMClient` delegates chat calls to an `LLMProvider`;
- legacy LiteLLM behavior remains available;
- provider-level retry works with typed failure classification;
- DeepSeek thinking mode can run tool calls while preserving `reasoning_content`;
- unsupported model/capability combinations fail before network calls where possible;
- OpenRouter routing config can pin provider behavior;
- LLM logs include provider, retry, thinking, routing, and usage metadata;
- tests cover retry, provider selection, DeepSeek thinking, and OpenRouter routing.
