# Release: LLM Provider Reliability

> Status: done
> Date: 2026-05-11
> Work Stream: Phase 3B — Reliability And Observability
> Related Plan: [LLM provider retry thinking](../plans/feature/llm-provider-retry-thinking.md)
> Related Design: [LLM provider reliability](../architecture/llm-provider-reliability.md)
> Related ADR: [ADR-0006](../decisions/ADR-0006-llm-provider-transport-boundary.md)

---

## Summary

This release upgrades the LLM layer from a thin `LLMClient` wrapper into a provider-backed transport layer with typed contracts, automatic retry, provider-specific capability checks, DeepSeek thinking support, and OpenRouter provider routing.

The application-facing `LLMClient.chat(...)` entry point stays compatible for AgentLoop, AuditAgent, and risk assessment callers.

---

## Shipped

- Added `LLMProvider` Protocol and shared request/response/config contracts.
- Added typed LLM provider errors with retry classification.
- Added `BaseLLMProvider` retry loop for retryable and rate-limit failures.
- Added `LiteLLMProvider` as the default compatibility provider.
- Added `DeepSeekProvider` using the OpenAI-compatible official SDK path.
- Added DeepSeek thinking config and `reasoning_content` preservation.
- Added model capability checks for DeepSeek tool-call and thinking combinations.
- Added `OpenRouterProvider` with provider routing request body support.
- Added env-driven provider construction through `LLMClient.from_env(...)`.
- Added direct `openai` dependency for the DeepSeek provider path.

---

## Validation

- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run pytest` -> 405 passed

Focused coverage:

- provider contract validation;
- retry success and retry exhaustion;
- non-retryable auth/request failure classification;
- DeepSeek thinking request construction;
- DeepSeek reasoning metadata preservation;
- DeepSeek model capability guards;
- OpenRouter provider routing body construction;
- existing `LLMClient` chat compatibility.

---

## Follow-Ups

- Feed retry records, provider names, request IDs, and usage into the configurable logging plan.
- Move env-based provider settings into hierarchical global/session config.
- Add credential-backed integration tests for DeepSeek and OpenRouter once test secrets and network policy are settled.
