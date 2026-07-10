# Fix Log: llm-provider-reliability.md

> Architecture document:
> [../llm-provider-reliability.md](../llm-provider-reliability.md)
>
> Original:
> [../llm-provider-reliability.original.md](../llm-provider-reliability.original.md)
>
> Calibration date: 2026-07-10
>
> External protocol check: 2026-07-10

## Workflow Gate Report

1. User request summary: calibrate architecture documents one at a time against
   current code and related documents, preserve each original, and record facts
   in a per-document fix log.
2. Detected workflow phase: P5/P8/P10 runtime architecture, backend integration,
   and iterative architecture documentation, with P9 tests as evidence.
3. Task type: documentation-only architecture fact calibration.
4. Required upstream artifacts: LLM contracts/client/retry/providers/config,
   role resolver, caller failure policies, usage/logging/runtime config,
   accepted ADR/release, current official provider protocols, and tests.
5. Found artifacts: local implementation and offline tests were present;
   DeepSeek and OpenRouter official documentation was available for current
   protocol verification.
6. Missing or weak artifacts: no credentialed live DeepSeek/OpenRouter tests;
   role resolver tests are narrow; the old document mixed implemented code,
   proposed Product 1.1 behavior, and external assumptions last checked earlier.
7. Whether implementation is allowed now: yes. Evidence is sufficient for a
   docs-only rewrite with explicit unverified-live boundaries.
8. Prework required before implementation: preserve the original, inspect all
   provider and caller paths, compare config/runtime wiring, and re-check
   official provider documents.
9. Proposed execution scope: replace only
   `docs/architecture/llm-provider-reliability.md`, preserve its original, and
   add this fix log. No production code changes.
10. Acceptance criteria: original matches HEAD; retry/timeout semantics,
    provider parameter support, role wiring, usage/logging, caller failure
    handling, and external drift are stated accurately; targeted checks pass.
11. Risks and assumptions: provider APIs are time-sensitive; offline request
    construction tests cannot prove live compatibility or upstream routing.

## Original Preservation

- `llm-provider-reliability.original.md` was copied before rewriting the
  current document.
- Original file SHA-1: `d05852eee907a79488bfd47e9ec8c0e58fe29903`.
- Original Git blob id: `68e0fd16a7e0ee4702b7892aadff97e46ba251c7`.
- The copied original has the same Git blob id as
  `HEAD:docs/architecture/llm-provider-reliability.md`.

## Sources Inspected

Architecture, ADR, plans, releases, and related contracts:

- `docs/architecture/llm-provider-reliability.md`
- `docs/architecture/configurable-logging-system.md`
- `docs/architecture/context-manager.md`
- `docs/architecture/ui-backend-communication.md`
- `docs/decisions/ADR-0006-llm-provider-transport-boundary.md`
- `docs/plans/feature/llm-provider-retry-thinking.md`
- `docs/releases/llm-provider-reliability.md`
- `docs/plans/feature/agent-llm-config-and-router-llm.md`
- `docs/plans/feature/token-usage-analytics.md`
- `docs/engineering/token-usage-analytics-contract.md`
- `docs/plans/feature/cooperative-task-interruption-technical-design.zh-CN.md`
- `docs/plans/feature/centralized-runtime-configuration.md`
- `docs/configuration.md`
- `docs/issues/ISSUE-001-llm-request-failure-no-event-record.md`

Official external sources checked on 2026-07-10:

- DeepSeek Thinking Mode:
  `https://api-docs.deepseek.com/guides/thinking_mode/`
- DeepSeek Models and Pricing:
  `https://api-docs.deepseek.com/quick_start/pricing/`
- DeepSeek Change Log:
  `https://api-docs.deepseek.com/updates/`
- OpenRouter Provider Routing:
  `https://openrouter.ai/docs/guides/routing/provider-selection`
- OpenRouter Prompt Caching and Sticky Routing:
  `https://openrouter.ai/docs/guides/best-practices/prompt-caching`

LLM core and provider code:

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
- `pyproject.toml`
- `uv.lock`

Role config, runtime, usage, and logging:

- `src/taskweavn/llm/agent_config.py`
- `src/taskweavn/llm/agent_resolver.py`
- `src/taskweavn/server/main_page_llm_helpers.py`
- `src/taskweavn/server/main_page.py`
- `src/taskweavn/runtime_config/defaults.py`
- `src/taskweavn/runtime_config/resolver.py`
- `src/taskweavn/server/runtime_config_consumers.py`
- `src/taskweavn/usage/recording.py`
- `src/taskweavn/usage/models.py`
- `src/taskweavn/usage/store.py`
- `src/taskweavn/observability/manager.py`
- `src/taskweavn/observability/redaction.py`

Callers and failure policies:

- `src/taskweavn/core/loop.py`
- `src/taskweavn/task/execution.py`
- `src/taskweavn/task/collaborator_profile_runner.py`
- `src/taskweavn/task/collaborator.py`
- `src/taskweavn/server/runtime_input_llm_router.py`
- `src/taskweavn/server/read_only_inquiry_answer_provider.py`
- `src/taskweavn/interaction/risk.py`
- `src/taskweavn/audit/agent.py`
- `src/taskweavn/cli/main.py`

Tests selected for verification:

- `tests/test_llm.py`
- `tests/test_llm_contracts.py`
- `tests/test_llm_retry_policy.py`
- `tests/test_llm_providers.py`
- `tests/test_agent_llm_config.py`
- `tests/test_agent_llm_resolver.py`
- `tests/test_token_usage_analytics.py`
- `tests/test_loop.py`
- `tests/test_fixed_route_task_executor.py`
- `tests/test_collaborator_authoring_loop_contract.py`
- `tests/test_collaborator_authoring_service.py`
- `tests/test_runtime_input_llm_router.py`
- `tests/test_read_only_inquiry_answer_provider.py`
- `tests/test_interaction_risk_llm.py`
- `tests/test_audit.py`
- `tests/test_main_page_sidecar_config.py`

## Verified Facts

### Facade and contracts

1. `LLMClient.chat` delegates a ChatRequest to an LLMProvider.
2. `LLMClient.complete` and count_tokens still delegate to lazy OpenHands SDK,
   not provider methods.
3. Provider retry, thinking, routing, and usage recording therefore apply to
   chat, not to facade complete/count calls.
4. Current production LLM call sites use chat; complete/count remain
   compatibility surfaces.
5. ChatRequest contains model, messages, tools, sampling limits, timeout,
   thinking, routing, and metadata.
6. Metadata is local and none of the current providers sends it to the external
   API.
7. Per-call timeout `None` means use the client's default, not disable it.
8. ProviderCapabilities is not read by production orchestration.
9. Base provider complete/count methods raise UnsupportedCapabilityError, but
   the facade bypasses them.
10. ChatResponse preserves content, tool calls, raw assistant message,
    reasoning, provider identity/request id, usage, retry data, and limited raw
    metadata.
11. AgentLoop appends raw_assistant_message to its transcript.
12. ThinkingConfig expose_reasoning_to_ui has no production read call site.

### Construction and defaults

13. Direct LLMClient construction without a provider creates LiteLLMProvider.
14. `LLMClient.from_env` defaults `LLM_PROVIDER` to DeepSeek.
15. LazyLLMClient defaults its model to deepseek-v4-pro.
16. The default request timeout is 180 seconds.
17. Provider and model compatibility are not validated together.
18. `LLMClient.from_env` can therefore combine the default DeepSeek provider
    with an arbitrary caller-supplied model string.
19. CLI without `--model` uses from_env and provider selection.
20. CLI with `--model` directly constructs LLMClient and selects LiteLLM,
    bypassing `LLM_PROVIDER`.
21. From-env supports only deepseek, openrouter, and litellm provider names.
22. Provider-specific key takes precedence over LLM_API_KEY fallback.
23. Environment and role profile configuration expose no RetryPolicy fields.
24. LLM_REQUEST_TIMEOUT_SECONDS accepts a positive number or
    none/off/disabled.
25. LLM_THINKING_EFFORT is only consumed when LLM_THINKING_ENABLED is present.
26. OpenRouter env parsing supports order, only, ignore, fallback,
    require-parameters, data collection, and ZDR.
27. ZDR alone does not trigger routing-object creation due to the current
    creation predicate.

### Role profiles and runtime config

28. AgentLlmRole declares six role strings.
29. Main Page actually builds four role clients: execution, collaborator,
    read-only inquiry, and runtime-input router.
30. Audit and summary roles are not wired into WorkspaceAgentLlms.
31. Profiles support inheritance, provider/model, timeout, temperature,
    thinking, routing, and bindings.
32. Missing agentLlm uses global Settings/env fallback.
33. Missing role binding uses the default profile.
34. Resolver catches parse failures and treats the agent block as absent without
    logging in that code path.
35. Inheritance cycles occur during resolve, outside that parse catch, and
    propagate.
36. Missing provider secrets do not disable client creation; failure is lazy at
    first request.
37. Role profile and env values are captured during workspace runtime assembly.
38. Existing clients are not rebuilt after later Settings changes.
39. Explicit injected `llm`/`llm_factory` bypasses role-specific resolver and is
    shared across four current roles.
40. Runtime Config catalogs llm provider/model/timeout as next-LLM-call values.
41. No LLM adapter exists in runtime_config_consumers and no ConfigBus consumer
    replaces current clients.

### Retry and timeout

42. RetryPolicy max_attempts is total attempts and defaults to three.
43. Retryable and rate-limit are the only classifications that enter retry.
44. Auth, request, capability, context-limit, and unknown failures do not retry.
45. Status 401/403 maps to auth, 429 to rate limit, configured status codes to
    retryable, 400 to request, and 413 to context limit.
46. Timeout/rate/auth/context/request heuristics also inspect exception type and
    message.
47. Generic ConnectionError/ConnectionResetError has no explicit classification
    branch.
48. A timeout error with non-null request timeout immediately raises without
    retry.
49. Standard 180-second calls therefore do not retry provider timeout failures.
50. This behavior has a direct unit test.
51. Timeout is forwarded to SDK/LiteLLM; there is no outer timer or hard cancel.
52. If timeout is disabled, another timeout exception can be retried according
    to classification.
53. Delay is capped before jitter; jitter can raise actual delay above the
    configured max.
54. A RetryRecord is made only when another attempt will run.
55. Three exhausted attempts therefore carry two retry records.
56. Success after retry uses dataclass replace to attach retry_count/records.
57. Final typed error carries prior retry records.
58. RetryRecord error_summary is raw exception text truncated to 500 chars.
59. Retry wraps the whole provider `_chat_once`, including request
    construction, response parsing, and provider logging.
60. Tool/runtime/TaskBus operations are outside provider retry.
61. There is no TaskWeavn cross-provider fallback, circuit breaker, hedging,
    health policy, rate limiter, or generation idempotency key.
62. Provider SDK internal retry is neither disabled nor counted by this layer.
63. BaseLLMProvider catches BaseException rather than Exception.

### Provider behavior

64. LiteLLM provider forwards model/key/messages/tools, optional temperature,
    max tokens, and timeout.
65. LiteLLM provider ignores thinking and provider routing.
66. Project code imports LiteLLM directly but pyproject declares it only
    transitively through OpenHands SDK.
67. DeepSeek provider uses a lazy OpenAI SDK client and configurable base URL.
68. It checks local model profiles before network calls.
69. Exact deepseek-chat is tool-capable/non-thinking and strips reasoning input.
70. Exact deepseek-reasoner is thinking/non-tool and strips reasoning input.
71. Exact deepseek-v4-pro is tool/thinking/reasoning-input capable.
72. Name heuristics map reasoner, v4/thinking, and other models to those
    profiles.
73. Thinking enable sends reasoning_effort and extra_body.thinking enabled.
74. Thinking-capable profile without enabled config sends explicit disabled.
75. DeepSeek max tokens and timeout are forwarded.
76. DeepSeek temperature is only forwarded in its non-thinking profile branch;
    it is omitted even when a thinking-capable profile is explicitly disabled.
77. DeepSeek OpenAI client does not explicitly set SDK max_retries.
78. OpenRouter provider currently uses LiteLLM transport.
79. It forwards model/key/messages/tools/timeout and an optional provider object.
80. It ignores ChatRequest temperature, max_tokens, and thinking.
81. With no routing object, no provider body is sent and OpenRouter defaults
    apply.
82. With a routing object, local defaults send allow_fallbacks false and
    require_parameters true.
83. OpenRouter does not send top-level session_id.
84. Parser labels responses openrouter and does not extract actual upstream
    endpoint/provider.

### External protocol drift

85. Current DeepSeek V4 official docs say V4 Flash/Pro support both thinking
    modes and tool calls.
86. Official thinking docs confirm reasoning_content must be returned after
    thinking tool-call turns.
87. Official docs say legacy deepseek-chat/deepseek-reasoner aliases map to V4
    Flash modes and retire on 2026-07-24 15:59 UTC.
88. The local exact deepseek-reasoner no-tool profile no longer matches the
    current primary V4 model table.
89. Current OpenRouter docs default to provider load balancing/fallback, with
    allow_fallbacks true and require_parameters false.
90. Current OpenRouter docs also describe automatic sticky routing and explicit
    session_id.
91. Local ProviderRoutingConfig covers only a subset of current official
    provider routing fields.
92. Local code does not implement OpenRouter session stickiness explicitly.
93. No live credentialed test verifies either provider.

### Response parsing

94. Shared parser assumes choices[0] exists.
95. Non-string content becomes an empty string.
96. String reasoning_content is preserved in ChatResponse and raw assistant
    message.
97. Tool calls without a function name are skipped; a missing id can become an
    empty string.
98. Malformed response shape has no dedicated typed classification.
99. Usage parser supports prompt/completion/total, reasoning, cached, and
    DeepSeek-style hit/miss fields.
100. No known usage fields produces usage None; there is no local estimation.
101. Raw response metadata only captures model, system_fingerprint, and created.
102. Raw response metadata has no production consumer and is not included by the
     provider response logger.

### Caller policy, logging, and usage

103. AgentLoop converts final LLM errors into AgentErrorObservation and
     llm_error/llm_timeout stop reasons.
104. AgentLoop recognizes timeout through nested LLMProviderError original
     errors.
105. If an interrupt exists when timeout returns, interruption wins.
106. Synchronous inflight LLM calls cannot be cooperatively stopped before the
     SDK returns or times out.
107. Collaborator public service maps provider failures into an
     invalid_llm_proposal result containing exception text.
108. Runtime Input LLM planner fails closed to an unavailable planner result.
109. Read-only Inquiry falls back to its baseline answer and warning.
110. LLMRiskAssessor falls back to baseline risk.
111. AuditAgent returns an inconclusive observation.
112. Main Page does not wire AuditAgent or LLMRiskAssessor.
113. Execution, Collaborator, Router, and Inquiry use application input/output
     logging helpers; Risk and Audit do not.
114. Provider request summary is emitted for each attempt, while provider
     response summary exists only on success.
115. llm_io logs full messages/tools/content/reasoning/tool arguments at INFO.
116. Logging payload_mode does not shape these payloads, so summary mode does not
     hide them.
117. Key-based redaction does not sanitize arbitrary content or retry exception
     strings.
118. UsageRecording writes one event after a successful ChatResponse, even when
     usage is unavailable.
119. Retry attempts and failed logical calls do not get usage events.
120. Usage sink errors are suppressed.
121. Usage events hash provider request id and allowlist metadata without raw
     prompt/response/tool payload.
122. UsageRecording wraps AgentConfigured outside-in and normalizes original
     caller metadata, so decorator-added role/profile metadata is not included.

## Stale or Corrected Claims

1. The old document called LiteLLM the default provider without qualifying the
   construction path. Direct construction defaults LiteLLM; from-env,
   readiness, and Main Page fallback default DeepSeek.
2. The old role table said Product 1.1 runtime uses execution, collaborator,
   router, inquiry, audit, and summary profiles. Main Page wires only four.
3. The old statement that all roles share the same usage/redaction/input-output
   logging discipline is false: Risk/Audit do not use application I/O helpers,
   and usage depends on wrapper assembly.
4. The old generic automatic-retry wording hid the configured-timeout special
   case. Standard provider timeouts do not retry.
5. The old examples listed connection reset as retryable. Generic connection
   errors are not explicitly classified.
6. The old max-delay contract implied an absolute cap. Jitter runs after the
   cap.
7. The old retry-record model could be read as recording every failed attempt.
   The final failed attempt has no record because no retry follows.
8. The old document described prompt/full response as hidden by default.
   llm_io currently writes full payload in default session logging.
9. The old document listed a raw provider metadata summary as a response log
   field. raw_response_metadata is not logged or consumed.
10. The old observability summary did not state that retry error strings and
    caller exception messages are not sanitized content.
11. The old provider compatibility section did not state that complete/count
    bypass provider reliability and usage.
12. The old contract wording implied ProviderCapabilities drives validation.
    It is currently descriptive only.
13. The old neutral request design did not disclose parameter support gaps:
    OpenRouter ignores temperature/max_tokens/thinking and LiteLLM ignores
    thinking/routing.
14. The old DeepSeek text treated deepseek-reasoner no-tools as a stable current
    provider fact. Current V4 docs and alias retirement changed that boundary.
15. The old external check date was 2026-05-11. It missed July 2026 V4 alias
    retirement and current model/routing docs.
16. The old OpenRouter cache discussion treated manual provider pinning as the
    only stability mechanism. OpenRouter now documents automatic sticky routing
    and explicit session_id.
17. The old OpenRouter design did not state that no routing object preserves
    platform defaults, while local false/true defaults only apply when an object
    is sent.
18. The old config section omitted DATA_COLLECTION and ZDR and did not capture
    the ZDR-only env bug.
19. The old hierarchical config section called role-level config deferred even
    though agentLlm profiles now exist in code; retry config remains deferred.
20. The old Runtime Config language did not distinguish catalog mutability from
    actual lack of an LLM consumer.
21. The old role failure policy came from a proposed plan. Parse errors, cycles,
    and missing credentials have different actual behaviors.
22. The old reasoning-visibility claim did not state that the exposure flag is
    unused and reasoning is logged in llm_io.
23. The old usage wording did not state that failures/retry attempts are absent
    or that profile metadata is lost at the outer wrapper.
24. The old document did not cover AgentLoop timeout/interruption precedence or
    caller-specific fallback policies.
25. Historical slice and target-design sections were replaced by current
    contracts, assembly, failure behavior, and explicit limits.

## New Document Decisions

1. Separate direct constructor, from-env, CLI, Main Page resolver, and injected
   LLM defaults.
2. Treat chat and complete/count as different reliability paths.
3. Describe retry from exact control flow, especially timeout and retry-record
   semantics.
4. Publish a provider parameter-support matrix rather than implying neutral
   contract parity.
5. Separate local implementation from external official protocol facts.
6. Date external checks and call out live-test absence.
7. Record caller-specific degradation and error persistence behavior.
8. Treat raw LLM I/O logs and usage analytics as different safety boundaries.
9. Distinguish Runtime Config catalog declarations from assembly-time consumers.
10. List reliability mechanisms that do not exist instead of implying a broad
    high-availability layer.

## Validation Log

Validation commands selected for this rewrite:

```bash
git diff --check
uv run pytest tests/test_llm.py tests/test_llm_contracts.py tests/test_llm_retry_policy.py tests/test_llm_providers.py tests/test_agent_llm_config.py tests/test_agent_llm_resolver.py tests/test_token_usage_analytics.py tests/test_loop.py tests/test_fixed_route_task_executor.py tests/test_collaborator_authoring_loop_contract.py tests/test_collaborator_authoring_service.py tests/test_runtime_input_llm_router.py tests/test_read_only_inquiry_answer_provider.py tests/test_interaction_risk_llm.py tests/test_audit.py tests/test_main_page_sidecar_config.py
```

Results:

- `git diff --check`: passed.
- Backend pytest: 190 passed.
- Credentialed DeepSeek/OpenRouter network tests: not run; the repository does
  not provide test credentials or a live-provider acceptance fixture for this
  boundary.
