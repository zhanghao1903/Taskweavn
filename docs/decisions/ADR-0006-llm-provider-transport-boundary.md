# ADR-0006: LLM Provider Transport Boundary

> Status: accepted
> Date: 2026-05-11
> Related Plan: [LLM provider retry thinking](../plans/feature/llm-provider-retry-thinking.md)
> Related Design: [LLM provider reliability](../architecture/llm-provider-reliability.md)
> Related Release: [LLM provider reliability](../releases/llm-provider-reliability.md)

---

## Context

TaskWeavn originally used `LLMClient` as a thin wrapper around two transport paths:

- `litellm.completion(...)` for ReAct-style chat/tool calls;
- `openhands.sdk.LLM` for completion and token counting compatibility.

That was enough for early experiments, but it did not give the system a stable place to model:

- provider-specific capabilities;
- automatic retry and error classification;
- DeepSeek thinking mode and `reasoning_content`;
- OpenRouter provider routing and cache-friendly provider pinning;
- structured request metadata for future logs and debugging.

Long-running Task execution needs LLM transport failures to be classified and retried before they collapse a session.

---

## Decision

TaskWeavn treats provider transport as a dedicated boundary below `LLMClient`.

The boundary is:

```text
Agent / Audit / Risk / Tooling
  -> LLMClient
  -> LLMProvider Protocol
  -> provider implementation
  -> external SDK/API
```

`LLMClient` remains the stable application-facing facade. Provider implementations own request construction, retry behavior, capability checks, and response normalization.

The first provider set is:

- `LiteLLMProvider`: compatibility/default provider for existing behavior;
- `DeepSeekProvider`: OpenAI-compatible official SDK path with thinking support;
- `OpenRouterProvider`: LiteLLM-backed transport with provider routing controls.

Retry belongs inside the provider transport boundary and only wraps LLM requests. Tool execution, Action execution, and TaskBus operations are not retried by the LLM provider layer.

---

## Consequences

Positive:

- LLM failures now have a typed classification and retry record.
- DeepSeek thinking metadata can be preserved without leaking provider-specific details into AgentLoop.
- OpenRouter routing can be pinned through a first-class config object.
- Future providers can be added without changing AgentLoop or AuditAgent call sites.

Tradeoffs:

- `LLMClient` now has more internal moving parts and must preserve compatibility deliberately.
- Some provider-specific features still require explicit capability checks.
- `complete()` and `count_tokens()` remain on the legacy OpenHands path until a later migration.

---

## Follow-Ups

- Connect provider retry records and request metadata to the configurable logging system.
- Move env-based provider configuration into the future hierarchical config model.
- Add provider-specific integration tests when real credentials and sandbox policy are available.
