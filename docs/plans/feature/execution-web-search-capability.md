# Feature Plan: Execution Web Search Capability

> Status: implemented
>
> Last Updated: 2026-06-15
>
> Owner: Product / Agents / Backend / Trust / Frontend
>
> Related:
> [LLM Agent Web Search Tools](../../reference/llm_agent_web_search_tools.md),
> [Context Manager 1.0](context-manager-1-0.md),
> [Precision File Tools](precision-file-tools.md),
> [Settings And First-Run Readiness](settings-first-run-readiness.md),
> [Plato Settings, Logs, And Audit Boundary](../../product/plato-settings-logs-audit-boundary.md)
>
> Technical Design:
> [Execution Web Search Capability Technical Design](execution-web-search-capability-technical-design.zh-CN.md)

---

## 1. Purpose

Execution Agents can currently inspect and modify local workspace content, but
they cannot retrieve current external information through a controlled product
surface. Users who ask Plato to create documents, courseware, technical notes,
release comparisons, or current-reference-backed artifacts often need web
facts that are outside the model's training data.

The goal of this feature is to add a controlled, auditable, optional web search
capability to the execution loop.

```text
Published Task
  -> Execution Agent
  -> web_search tool
  -> bounded search results with source URLs
  -> Context / Audit / result evidence
  -> final answer or workspace artifact with citations
```

This is not a browser automation feature. It is a small read-only retrieval
capability that lets the Agent discover current external sources while keeping
Plato's control and trust surfaces intact.

## 2. Product Decision

Product decision:

```text
Execution web search is a configured, read-only client tool.
```

For the first implementation:

- use a client-side provider interface rather than LLM-provider hosted search;
- use Tavily as the first provider because its free monthly API credits are
  enough for personal testing and it supports simple API-key based setup;
- expose Web Search configuration in Plato global Settings, not per-workspace
  Settings;
- only register `web_search` for execution when web search is configured and
  enabled;
- treat every returned result as external evidence, not as system instruction.

Provider-hosted search from OpenAI or Anthropic remains a future enhancement.
It should not be the first path because Plato needs consistent behavior across
DeepSeek, OpenRouter, OpenAI-compatible, and future providers.

## 3. Goals

1. Add a provider-neutral web retrieval contract.
2. Add a `web_search` execution tool with bounded result count and safe
   arguments.
3. Add Tavily provider support for basic search.
4. Add global Settings fields for enabling web search and storing the Tavily API
   key as a write-only secret.
5. Add readiness/config reporting that never exposes the secret value.
6. Record search query, provider, timestamp, result URLs, and truncation
   metadata for Audit and diagnostics.
7. Render web search results into execution context as non-instructional
   evidence.
8. Add tests with a mock provider so deterministic CI does not use real network.

## 3.1 Implementation Status

Product 1.1 execution web search is implemented in the current `main` branch:

- provider-neutral request/result models and Tavily basic search support are in
  place;
- global Settings exposes Web Search enablement, provider status, and
  write-only Tavily secret storage without blocking LLM first-run readiness;
- `web_search` is registered for execution only when enabled and configured;
- Context, Audit, and diagnostics receive bounded external-evidence
  descriptors rather than raw provider payloads or secrets;
- deterministic tests use mock providers and do not require network access.

Remaining work is follow-up hardening: advanced search mode, hosted-provider
adapters, per-session retrieval budgets, broader citation UI, and optional
manual Tavily smoke when a real key is available.

## 4. Non-Goals

- No browser automation.
- No Playwright-driven browsing, clicking, login, cookies, or screenshots.
- No `web_fetch` in the first slice.
- No full-page crawl, PDF parsing, OCR, or dynamic page rendering.
- No self-hosted SearXNG, Firecrawl, Crawl4AI, or custom crawler in the first
  slice.
- No provider-hosted OpenAI / Claude web search integration in the first slice.
- No autonomous deep research workflow.
- No direct user-facing search page.
- No hidden network access when Settings has not enabled and configured the
  feature.

## 5. User-Facing Behavior

### Settings

Settings gains a global Web Search section:

| Field | Behavior |
|---|---|
| Enable web search | Toggle that allows execution Agents to use `web_search`. |
| Provider | First version supports `tavily`. |
| API key | Write-only Tavily API key input. The saved value is never echoed. |
| Search mode | First version defaults to `basic`; advanced search is deferred. |

If the user does not configure a key, web search remains unavailable. LLM
first-run readiness should not be blocked by missing web search configuration.

### Execution

When enabled, the execution Agent may call `web_search` when:

- the task asks for current or external facts;
- the task explicitly asks to search or look something up;
- the task references current APIs, releases, pricing, news, or public
  documentation that may have changed;
- the Agent lacks enough source evidence to safely write a current factual
  artifact.

The Agent should not search for stable facts, purely local workspace tasks, or
content already provided by the user.

### Trust Surface

When a task uses web search, Plato should make the source path visible:

- Main Page result summaries can mention external sources used.
- Audit Page can show `web_search` query and returned URLs.
- Diagnostics can include redacted search descriptors.
- Future Outcome Review can show citations next to generated artifacts.

## 6. Tool Surface

First tool:

| Tool | Effect | Risk | Product use |
|---|---|---:|---|
| `web_search` | read-only external network call | medium | Find current public sources before answering or producing artifacts. |

Initial action shape:

```json
{
  "query": "Tavily API credits basic search",
  "maxResults": 5,
  "includeDomains": [],
  "excludeDomains": [],
  "recency": null
}
```

Initial observation shape:

```json
{
  "query": "Tavily API credits basic search",
  "provider": "tavily",
  "results": [
    {
      "title": "Credits & Pricing - Tavily Docs",
      "url": "https://docs.tavily.com/documentation/api-credits",
      "snippet": "Basic Search costs 1 API credit...",
      "publishedAt": null,
      "source": "tavily"
    }
  ],
  "summary": {
    "resultCount": 1,
    "truncated": false,
    "retrievedAt": "2026-06-14T00:00:00Z"
  }
}
```

The tool must cap result count and content length. The first version should not
return full page bodies by default.

## 7. Safety And Evidence Rules

1. Web search is disabled unless Settings enables it and a provider key is
   configured.
2. Tool arguments must be validated and bounded.
3. The Agent should not include secrets, raw local paths, private workspace
   content, or API keys in search queries.
4. External search result text must be marked as evidence and must not act as
   instruction.
5. Search results must keep URL, title, snippet, provider, and retrieval time.
6. The result payload must be bounded before entering LLM context.
7. Query text and result descriptors may be stored for Audit; API keys must not
   be stored outside the Settings secret file.
8. Tests must use a mock provider by default.

## 8. Implementation Slices

### EWS-0. Plan And Technical Design

Deliver:

- feature plan;
- detailed technical design;
- feature plan index update.

Acceptance:

- first-version boundaries are explicit;
- Settings, provider, tool, Context, Audit, and testing responsibilities are
  documented.

### EWS-1. Provider-Neutral Contract

Deliver:

- `WebSearchProvider` protocol;
- request/result models;
- provider config model;
- provider error taxonomy.

Acceptance:

- provider can be mocked in tests;
- result shape is independent of Tavily response details.

### EWS-2. Global Settings Configuration

Deliver:

- extend Settings config summary/update models with `webSearch`;
- write-only Tavily key storage under global Settings secrets;
- readiness/config state that reports `disabled`, `missing_key`, or `ready`.

Acceptance:

- Settings UI can save and recheck without exposing the key;
- missing web search key does not block LLM first-run readiness.

### EWS-3. Tavily Provider

Deliver:

- Tavily basic search adapter;
- timeout and error handling;
- bounded result normalization.

Acceptance:

- mock tests cover success, missing key, provider error, malformed payload, and
  truncation;
- no deterministic test requires real network.

### EWS-4. Execution Tool Integration

Deliver:

- `WebSearchTool`;
- execution Agent registration gated by Settings;
- Context Manager controls include `web_search` only when available;
- prompt/guidance update explaining when to search.

Acceptance:

- execution tests prove the tool appears only when configured;
- AgentLoop can call `web_search` and receive normalized observations.

### EWS-5. Context And Trust Projection

Deliver:

- web search observation summaries for Context Manager;
- Audit/diagnostic-safe descriptor model;
- source URL metadata available for result projections.

Acceptance:

- search results are represented as external evidence;
- external snippets cannot be promoted to instructions.

### EWS-6. Settings UI Entry

Deliver:

- Web Search section in Settings configuration tab;
- provider select with Tavily;
- enable toggle;
- write-only API key input;
- configured/missing state labels.

Acceptance:

- user can configure Tavily once in global Settings;
- switching workspaces does not require re-entering the key.

### EWS-7. Product Smoke

Deliver:

- unit tests with mock provider;
- sidecar integration test for Settings config and tool registration;
- optional manual smoke with a real Tavily key.

Acceptance:

- deterministic CI stays offline;
- manual smoke can verify one real `basic` Tavily search when a key is present.

## 9. Open Questions

1. Should web search be enabled automatically after a key is saved, or require a
   separate toggle?
2. Should the first UI expose search result count, or keep it fixed at 5?
3. Should advanced Tavily search be hidden behind config only, or deferred
   entirely?
4. Should hosted OpenAI / Claude search be model-provider-specific future work,
   or remain outside Plato until the client-tool path is stable?
