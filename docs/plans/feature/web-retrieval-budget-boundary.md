# Web Retrieval Budget Boundary

> Status: planned Product 1.1 P1 beta hardening
>
> Last Updated: 2026-06-24
>
> Owner: Execution / Settings / Observability
>
> Related plans:
> [Execution Web Search Capability](execution-web-search-capability.md),
> [Execution Web Fetch Capability](execution-web-fetch-capability.md),
> [Token Usage Analytics](token-usage-analytics.md)

## 1. Problem

Product 1.1 can call external web retrieval providers through `web_search` and
`web_fetch`. This makes read-only inquiry and execution more useful for current
public information, but it also introduces a second cost surface beyond LLM
tokens:

- provider credits can be consumed by repeated searches and extracts;
- failed or low-quality searches can still consume provider calls;
- users cannot currently see or bound retrieval usage before a task runs;
- diagnostics can show evidence after the fact, but not an explicit budget
  state.

The Product 1.1 beta needs a small, understandable retrieval budget boundary so
web retrieval remains trustworthy without building a billing system.

## 2. Goals

1. Define a product-level budget boundary specifically for web retrieval calls.
2. Count search calls, fetch calls, fetched URLs, failed calls, and extracted
   bytes when available.
3. Let Settings expose whether web retrieval is enabled and whether a local
   budget boundary is active.
4. Project near-limit and exhausted states in Main Page, Activity/Audit, and
   diagnostics without leaking API keys, raw provider payloads, or absolute
   paths.
5. Keep the first implementation independent from token usage analytics while
   preserving a future combined Usage Information surface.

## 3. Non-Goals

- No dollar-cost calculation.
- No provider-specific billing estimator.
- No cloud quota or team policy engine.
- No automatic purchase, credit refresh, or remote account lookup.
- No broad token budget enforcement. Token usage remains covered by the
  separate token usage analytics track.
- No hard enterprise policy model in Product 1.1.

## 4. Product Boundary

First Product 1.1 behavior should be local and conservative:

- Budget policy is workspace-local or session-local; there is no user account
  billing concept.
- A disabled budget boundary means retrieval remains governed only by the
  existing enablement toggles, URL safety policy, and provider errors.
- An enabled budget boundary blocks new retrieval calls after the limit is
  exhausted.
- A near-limit state warns the user and is visible in Activity/Audit.
- Exhaustion is not a task failure by itself. The tool call returns a structured
  retriable or non-retriable retrieval-budget error, and the Agent decides
  whether it can continue with existing evidence.
- Settings must never echo the provider secret or raw provider usage payload.

## 5. Minimal Schema

```ts
type WebRetrievalBudgetScope = "session" | "task" | "workspace";

type WebRetrievalBudgetPolicy = {
  enabled: boolean;
  scope: WebRetrievalBudgetScope;
  maxSearchCalls: number | null;
  maxFetchCalls: number | null;
  maxFetchedUrls: number | null;
  maxFetchedBytes: number | null;
  warningThresholdRatio: number;
  resetAt: string | null;
};

type WebRetrievalUsageSummary = {
  scope: WebRetrievalBudgetScope;
  scopeId: string;
  provider: string | null;
  searchCalls: number;
  fetchCalls: number;
  fetchedUrls: number;
  failedCalls: number;
  fetchedBytes: number | null;
  warning: boolean;
  exhausted: boolean;
  lastUsedAt: string | null;
};
```

Initial implementation should prefer `session` scope. `task` and `workspace`
scope can be stored in the contract but do not need full UI controls until a
specific beta need appears.

## 6. Pipeline

```text
Settings policy
  -> Retrieval tool registration
  -> web_search / web_fetch budget preflight
  -> provider call
  -> retrieval usage event
  -> usage summary projection
  -> Main Page / Audit / diagnostics
```

Rules:

1. Preflight checks the active policy before calling Tavily or any future
   provider.
2. Successful and failed provider calls both write retrieval usage events.
3. Fetch accounting counts each selected URL and the best available extracted
   byte length.
4. Provider errors and safety-policy rejections remain separate error types;
   they should not be misreported as budget exhaustion.
5. Context Manager may receive a compact budget fact such as
   `web_retrieval_budget: near_limit` or `exhausted`, but it must not receive
   raw provider usage payloads.

## 7. UI And Projection

Minimum user-visible surfaces:

- Settings: show web retrieval enablement plus optional local budget controls.
- Main Page: show a compact warning when the active Session is near or over the
  retrieval budget.
- Activity/Audit: record budget exhaustion or near-limit notices as system
  state updates with safe evidence references.
- Diagnostics: include a redacted retrieval usage summary for support.

The first beta UI should avoid complex charts. The goal is to make usage
understandable and bounded, not to build analytics.

## 8. Implementation Slices

### WRB-1. Contract And Settings Projection

- Add typed policy and usage summary models.
- Extend Settings query/command contracts with optional budget fields.
- Preserve existing enablement and write-only key semantics.
- Add contract tests for defaults and secret redaction.

### WRB-2. Runtime Accounting Seam

- Add a narrow preflight and accounting boundary around `web_search` and
  `web_fetch`.
- Record one retrieval usage event per attempted provider call.
- Return structured budget errors before provider calls when exhausted.
- Keep URL safety errors separate from budget errors.

### WRB-3. Activity, Audit, And Diagnostics Projection

- Project near-limit and exhausted states into Activity/Audit.
- Add diagnostic bundle descriptor and redacted summary.
- Add tests that no API key, raw provider payload, or absolute path appears.

### WRB-4. Main Page Warning Surface

- Show near-limit/exhausted notices in the Session work surface.
- Keep warning copy short and actionable.
- Do not block unrelated non-retrieval user input.

### WRB-5. Acceptance Smoke

- Run offline mock-provider tests for normal, near-limit, exhausted, and failed
  provider-call paths.
- Optionally run one live Tavily smoke with a tiny configured budget and a real
  key when available.

## 9. Acceptance Criteria

- A user can configure a local retrieval budget boundary without exposing the
  Tavily key.
- Calls are blocked before provider access when the configured budget is
  exhausted.
- Search and fetch usage are counted separately.
- Main Page, Activity/Audit, and diagnostics can explain near-limit and
  exhausted states.
- Existing web search/fetch behavior remains unchanged when the budget boundary
  is disabled.
- Tests cover defaults, exhausted preflight, provider failure accounting, and
  redaction.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Users confuse retrieval budget with token budget. | Keep naming explicit: Web Retrieval Budget. Link token usage as a separate usage surface. |
| Provider credit costs change. | Count local calls and URLs, not dollars. Avoid price estimates. |
| Agents over-fetch before UI warnings appear. | Runtime preflight must be authoritative; UI is projection only. |
| Budget state becomes stale after sidecar restart. | Persist usage events in the workspace-local store and rebuild summaries from durable events. |
| Too many controls for beta users. | Default budget boundary can be off; expose simple limits first. |

## 11. Open Questions

1. Should the default beta boundary be off, or should Settings offer a low
   default warning-only boundary after a key is configured?
2. Should Product 1.1 implement only session scope first, even if the contract
   names task/workspace scopes?
3. Should live Tavily smoke require an explicit temporary low budget to protect
   provider credits during QA?
