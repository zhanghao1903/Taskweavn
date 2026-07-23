# LLM Provider Reliability Technical Design

> Status: implemented
> Last Updated: 2026-06-24
> Scope: server core execution line, Router/read-only inquiry, and Agent LLM resolver
> Related Plan: [LLM provider retry thinking](../plans/feature/llm-provider-retry-thinking.md)
> Related Release: [LLM Provider Reliability](../releases/llm-provider-reliability.md)
> Related Roadmap: [Phase 3B — Reliability And Observability](../roadmap.md#phase-3b--reliability-and-observability)
> Related Product 1.1: [Agent LLM Config And Router LLM](../plans/feature/agent-llm-config-and-router-llm.md), [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md), [Read-Only Inquiry Context](../plans/feature/read-only-inquiry-context.md)

Product 1.1 alignment: the LLM boundary is no longer only the execution
AgentLoop facade. Current runtime also uses Settings-backed Agent LLM profiles
for `execution`, `collaborator`, `router`, and `read_only_inquiry` roles. Router
and read-only inquiry calls must use the same provider reliability, redaction,
usage, and input/output logging discipline as execution calls.

---

## 1. Background

TaskWeavn originally treated the LLM layer as a thin adapter:

- `LLMClient.complete()` delegates to `openhands.sdk.LLM`.
- `LLMClient.chat()` calls `litellm.completion(...)` directly.
- failures are logged and re-raised;
- provider-specific behavior is not modeled;
- DeepSeek thinking mode is not supported;
- OpenRouter provider routing is not pinned, so the same model can be routed to different upstream providers.

This was acceptable for early experiments, but not for long-running Task
execution, user confirmations, Collaborator Agent planning, Runtime Input
Router calls, read-only inquiry, and multi-step server workflows. In that world,
LLM transport must be reliable, observable, configurable, and provider-aware.

This document is now the current architecture baseline for the implemented
roadmap item: **LLM Provider abstraction, automatic retry, DeepSeek thinking,
and OpenRouter provider routing**. Historical slice details and validation live
in the [feature plan](../plans/feature/llm-provider-retry-thinking.md) and
[release record](../releases/llm-provider-reliability.md).

---

## 2. Current Code Facts

Current implementation:

```text
src/taskweavn/llm/client.py
  LLMClient facade and backward-compatible action/tool helpers
src/taskweavn/llm/contracts.py
  LLMProvider, ProviderCapabilities, ChatRequest, ChatResponse, LLMUsage,
  RetryPolicy, RetryRecord, ThinkingConfig, ProviderRoutingConfig
src/taskweavn/llm/errors.py
  typed provider errors and retry classifications
src/taskweavn/llm/retry.py
  BaseLLMProvider retry loop and retry record collection
src/taskweavn/llm/providers/
  LiteLLMProvider, DeepSeekProvider, OpenRouterProvider, OpenAI-compatible helpers
src/taskweavn/llm/config.py
  env-driven provider and client construction
src/taskweavn/llm/agent_config.py
  role-aware Agent LLM configuration models
src/taskweavn/llm/agent_resolver.py
  Settings-backed role resolver for execution, collaborator, router,
  read_only_inquiry, audit, and summary roles
src/taskweavn/llm/logging.py
  LLM request/response/retry metadata logging helpers
```

Current `LLMClient.chat(...)` remains the application-facing compatibility
entry point:

```text
LLMClient.chat(...)
  -> selected LLMProvider
  -> provider retry/capability checks
  -> ChatResponse with content, tool calls, provider metadata, retry records,
     usage, and raw assistant message preservation
```

Current v1 baseline:

| Area | Current fact |
|---|---|
| Provider boundary | `LLMClient` delegates chat calls to an `LLMProvider`; LiteLLM remains the compatibility default. |
| Retry | Provider-level retry uses typed failure classification and records retry attempts. |
| DeepSeek | DeepSeek provider supports OpenAI-compatible thinking config and preserves `reasoning_content` when required. |
| OpenRouter | OpenRouter provider can serialize provider routing config such as fallback and parameter requirements. |
| Observability | Provider, model, retry, routing, thinking, usage, and request metadata are available for logging and diagnostics-safe summaries. |
| Role config | Product 1.1 runtime uses Settings-backed Agent LLM profiles for execution, collaborator, router, read-only inquiry, audit, and summary roles. |

---

## 3. V1 Capability Boundary

1. Keep a provider boundary under `LLMClient`.
2. Keep `LLMClient` as the facade used by AgentLoop, AuditAgent, RiskAssessor,
   Runtime Input Router, read-only inquiry, and future Agents.
3. Run provider-level automatic retry with explicit error classification.
4. Support DeepSeek provider behavior through the OpenAI-compatible SDK path.
5. Support DeepSeek thinking mode and preserve `reasoning_content` where required.
6. Support OpenRouter provider routing configuration.
7. Preserve the legacy LiteLLM path as the default compatibility provider.
8. Make provider metadata observable through configurable logging and
   diagnostics-safe summaries.

---

## 4. Non-goals

- Do not implement every provider in the first slice.
- Do not implement streaming UI.
- Do not implement cross-provider fallback in the first version.
- Do not implement model selection, cost optimization, or quota policy here.
- Do not make the LLM layer own configurable logging policy; provider metadata
  is emitted through the accepted configurable logging baseline.
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

The compatibility baseline supports env vars. Product 1.1 role-specific runtime
calls are resolved through Settings-backed Agent LLM profiles before falling
back to environment defaults where applicable.

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

### 12.2 Deferred config surface

The broader hierarchical config shape remains a deferred configuration-system
boundary, not the current provider runtime contract:

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

LLM provider reliability now integrates with the configurable logging system.
LLM logs should use the `llm` category and remain summary-safe by default.

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

Prompt and full response should remain hidden by default. Full payload belongs
behind explicit logging profile/configuration and redaction policy.

---

## 14. Compatibility Notes

### 14.1 Existing callers

Existing callers should continue to use:

```python
response = llm.chat(messages, tools)
```

They should not construct providers directly unless they are tests or advanced configuration code.

### 14.2 AgentLoop

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

### 14.3 AuditAgent and LLMRiskAssessor

AuditAgent and LLMRiskAssessor should not change in the first migration except for benefiting from retry and provider metadata.

Later, they may use cheaper/different provider configs:

- `AUDIT_LLM_PROVIDER`;
- `RISK_LLM_PROVIDER`;
- smaller models for frequent risk assessment.

---

## 15. Implementation History And Release Record

This architecture document no longer owns the execution slice plan. The
provider boundary, retry layer, DeepSeek support, and OpenRouter routing
foundation were accepted as the Phase 3B LLM provider reliability release.

Authoritative history:

- Implementation plan and slice detail:
  [LLM provider retry thinking](../plans/feature/llm-provider-retry-thinking.md).
- Accepted release summary, shipped surface, validation, and follow-ups:
  [Release: LLM Provider Reliability](../releases/llm-provider-reliability.md).

The accepted v1 baseline includes:

- `LLMProvider` protocol and shared request/response/config contracts;
- typed LLM provider errors with retry classification;
- `BaseLLMProvider` retry loop for retryable and rate-limit failures;
- LiteLLM compatibility provider as the default path;
- DeepSeek provider through the OpenAI-compatible SDK path;
- DeepSeek thinking config and `reasoning_content` preservation;
- DeepSeek model capability guards for tool-call and thinking combinations;
- OpenRouter provider routing request-body support;
- env-driven provider construction through `LLMClient.from_env(...)`;
- direct `openai` dependency for the DeepSeek provider path.

## 16. Validation Boundary

The accepted release record captured the implementation validation:

```bash
uv run ruff check src tests
uv run mypy src tests
uv run pytest
```

Current focused regression areas include:

| Area | Tests |
|---|---|
| Facade compatibility | `test_llm.py` |
| Provider contracts | `test_llm_contracts.py` |
| Retry policy | `test_llm_retry_policy.py` |
| Provider behavior | `test_llm_providers.py` |
| Role resolver | `test_agent_llm_resolver.py`, `test_agent_llm_config.py` |
| Runtime input / inquiry callers | `test_runtime_input_llm_router.py`, `test_read_only_inquiry_answer_provider.py` |
| Risk and audit callers | `test_interaction_risk_llm.py`, `test_audit_runtime_config_provider.py` |

Future changes to provider behavior should run the focused tests for the touched
boundary, plus the full gate when behavior crosses provider contracts, runtime
input, read-only inquiry, Agent LLM resolver, audit, or diagnostics.

## 17. Follow-Up Boundaries

These are not v1 blockers. They are future boundaries to keep explicit:

| Boundary | Current decision |
|---|---|
| External provider docs | DeepSeek/OpenRouter constraints were checked on 2026-05-11; re-check official docs before changing provider behavior. |
| Reasoning visibility | Preserve reasoning metadata where providers require it, but do not expose raw reasoning in UI by default. |
| Thinking default | Thinking remains explicit opt-in; provider defaults must not silently change TaskWeavn behavior. |
| OpenRouter fallback | Preserve OpenRouter default behavior unless routing config explicitly pins or disables fallbacks. |
| Cross-provider fallback | Not part of v1; retry remains single-provider unless a later policy design accepts fallback semantics. |
| Streaming | Not part of v1; keep synchronous chat as the baseline until a streaming transport/UI contract exists. |
| Credentialed smoke | Live DeepSeek/OpenRouter integration tests require test secrets and network policy; keep unit tests fake-client/offline-first. |
