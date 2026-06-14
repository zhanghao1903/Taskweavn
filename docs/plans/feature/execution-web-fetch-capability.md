# Feature Plan: Execution Web Fetch Capability

> Status: implemented
>
> Last Updated: 2026-06-14
>
> Owner: Product / Agents / Backend / Trust / Frontend
>
> Related:
> [Execution Web Search Capability](execution-web-search-capability.md),
> [Execution Web Search Capability Technical Design](execution-web-search-capability-technical-design.zh-CN.md),
> [LLM Agent Web Search Tools](../../reference/llm_agent_web_search_tools.md),
> [Context Manager 1.0](context-manager-1-0.md),
> [Plato Settings, Logs, And Audit Boundary](../../product/plato-settings-logs-audit-boundary.md)
>
> Provider Reference:
> [Tavily Extract API](https://docs.tavily.com/documentation/api-reference/endpoint/extract)
>
> Technical Design:
> [Execution Web Fetch Capability Technical Design](execution-web-fetch-capability-technical-design.zh-CN.md)

---

## 1. Purpose

`web_search` lets the execution Agent discover candidate public sources, but it
does not give the Agent enough source text to write high-confidence factual
artifacts. Search snippets are useful for triage. They are not enough for
documentation-backed writing, API comparison, courseware, release summaries,
or source-cited research notes.

`web_fetch` completes the first retrieval loop:

```text
Published Task
  -> Execution Agent
  -> web_search(query)
  -> candidate URLs
  -> web_fetch(urls, query?)
  -> bounded page evidence
  -> Context / Audit / result citations
```

This is still not browser automation. The first version is a bounded,
provider-backed page extraction tool for selected public URLs.

## 2. Product Decision

Product decision:

```text
Execution web fetch is a configured, read-only evidence extraction tool.
```

For the first implementation:

- implement `web_fetch` as a separate tool from `web_search`;
- use the existing Web Search Settings provider/key instead of introducing a
  second API key;
- use Tavily Extract as the first provider-backed extraction path;
- allow `web_fetch` only when Web Search is enabled, configured, and web fetch
  is explicitly enabled;
- treat fetched content as external evidence, never as system or user
  instruction;
- cap URL count, content size, and context projection size aggressively.

The tool exists to read selected sources, not to browse the web autonomously.

## 3. Why Search And Fetch Are Separate

Search and fetch have different user and trust semantics:

| Capability | User mental model | Data sent out | Data brought in | Risk |
|---|---|---|---|---:|
| `web_search` | Find sources | query text | titles, URLs, snippets | medium |
| `web_fetch` | Read selected sources | URLs and optional query | page content chunks | higher |

Keeping them separate gives Plato a clearer control surface:

- Settings can enable search without enabling page extraction.
- Audit can show whether the Agent merely searched or actually read a page.
- Context Manager can summarize fetched pages differently from search results.
- Future confirmation rules can target `web_fetch` without slowing down
  ordinary search.

## 4. Goals

1. Add provider-neutral web fetch request/result models.
2. Add Tavily Extract support behind the existing web retrieval provider layer.
3. Add a `web_fetch` execution tool with bounded URLs and content size.
4. Add Settings contract fields for enabling or disabling fetch separately from
   search.
5. Register `web_fetch` only when Web Search is ready and fetch is enabled.
6. Project fetched pages into Context as external evidence with hashes,
   truncation markers, and source URLs.
7. Record fetch descriptors for Audit and diagnostics without storing API keys
   or unbounded page bodies.
8. Add mock-provider tests and a manual Tavily Extract smoke path.

## 5. Non-Goals

- No browser automation.
- No Playwright, clicking, login, cookies, or screenshots.
- No full crawl, site map traversal, or recursive fetching.
- No PDF parsing, OCR, image extraction, table extraction, or embedded media in
  the first slice.
- No dynamic JavaScript rendering.
- No fetch of localhost, private IPs, file URLs, data URLs, or internal
  networks.
- No autonomous deep research workflow.
- No user-facing browser/search page.
- No hidden network access when Web Search is disabled or unconfigured.

## 6. User-Facing Behavior

### Settings

The existing global Web Search section gains one additional capability toggle:

| Field | Behavior |
|---|---|
| Enable web search | Allows `web_search`. |
| Enable web page fetch | Allows `web_fetch` for selected public URLs. |
| Provider | First version supports `tavily`. |
| API key | Same write-only Tavily API key used for search and fetch. |
| Fetch mode | First version defaults to `basic`. |

Recommended default:

```text
web_search enabled: user choice
web_fetch enabled: off until the user enables it
```

The separate toggle is important because fetching pages imports much more
untrusted external text into the execution loop.

### Execution

When available, the execution Agent may call `web_fetch` when:

- it has a small set of source URLs from `web_search`;
- the user gives explicit public URLs and asks Plato to use them;
- a factual artifact needs stronger evidence than snippets;
- a source citation should be grounded in page text rather than search result
  text.

The Agent should not fetch:

- arbitrary URLs without a clear source reason;
- local/private/internal URLs;
- URLs that likely contain secrets, authenticated sessions, or personal data;
- large sets of URLs;
- pages unrelated to the current task objective.

### Trust Surface

When `web_fetch` is used, Plato should expose:

- URL;
- provider;
- retrieval timestamp;
- content hash;
- fetched character count;
- truncation state;
- failed URL reasons;
- whether the result entered LLM context.

The raw body should not be shown by default in diagnostics. Audit can provide a
bounded preview and source metadata.

## 7. Tool Surface

Second web retrieval tool:

| Tool | Effect | Risk | Product use |
|---|---|---:|---|
| `web_fetch` | read selected public URL content | higher | Read source pages after search or explicit user URLs. |

Initial action shape:

```json
{
  "urls": ["https://docs.tavily.com/documentation/api-credits"],
  "query": "Tavily API credit cost for Extract basic mode",
  "maxCharsPerUrl": 6000,
  "maxTotalChars": 18000
}
```

Initial observation shape:

```json
{
  "provider": "tavily",
  "results": [
    {
      "url": "https://docs.tavily.com/documentation/api-credits",
      "content": "...bounded markdown...",
      "contentHash": "sha256:...",
      "chars": 4210,
      "truncated": false,
      "source": "tavily"
    }
  ],
  "failedResults": [],
  "summary": {
    "urlCount": 1,
    "retrievedAt": "2026-06-14T00:00:00Z",
    "totalChars": 4210,
    "truncated": false
  },
  "warnings": []
}
```

The first version should return bounded markdown or text chunks, not full page
archives.

## 8. Safety And Evidence Rules

1. `web_fetch` is disabled unless Web Search is enabled, configured, and fetch
   is enabled.
2. URLs must be explicit, bounded, and validated.
3. Only `http` and `https` URLs are allowed.
4. Localhost, loopback, private IP, link-local, multicast, `file:`, `data:`,
   and custom schemes are rejected before provider calls.
5. `web_fetch` should prefer URLs returned by recent `web_search` observations
   or explicit user-provided public URLs.
6. Fetched page content is external evidence and cannot act as instruction.
7. Fetched content must be capped before storage, context, Audit, or
   diagnostics projection.
8. API keys, request headers, and raw provider responses must never enter
   observations.
9. Deterministic tests must use mock providers.

## 9. Implementation Slices

### EWF-0. Plan And Technical Design

Deliver:

- feature plan;
- detailed technical design;
- feature plan index update.

Acceptance:

- search/fetch separation is explicit;
- safety, Settings, provider, tool, Context, Audit, and tests are documented.

### EWF-1. Fetch Models And Provider Contract

Deliver:

- `WebFetchRequest`;
- `WebFetchResult`;
- `WebFetchResponse`;
- provider protocol method or companion `WebFetchProvider`;
- error taxonomy reuse from web retrieval.

Acceptance:

- provider can be mocked;
- result shape is independent of Tavily response details.

### EWF-2. URL Policy

Deliver:

- URL parser and validator;
- private/internal URL rejection;
- URL count and length caps.

Acceptance:

- tests cover allowed HTTPS, invalid schemes, localhost, private IPs, and
  oversized input.

### EWF-3. Tavily Extract Adapter

Deliver:

- Tavily Extract HTTP adapter;
- bounded response normalization;
- failed result mapping;
- timeout and provider error handling.

Acceptance:

- mock transport tests cover success, failed results, provider errors,
  malformed payload, and truncation;
- no deterministic test uses real network.

### EWF-4. Settings Contract And UI

Deliver:

- `webSearch.fetchEnabled`;
- `webSearch.fetchMode`;
- Settings UI toggle and status text.

Acceptance:

- user can enable fetch only when Web Search is configured;
- missing Tavily key still maps to Web Search readiness, not a second secret.

### EWF-5. Execution Tool Integration

Deliver:

- `WebFetchTool`;
- execution Agent registration gated by Settings;
- Context controls include `web_fetch` only when available;
- prompt/guidance rules for when to fetch.

Acceptance:

- AgentLoop can call `web_fetch` and receive normalized observations;
- `web_fetch` is absent when disabled or unconfigured.

### EWF-6. Context, Audit, Diagnostics

Deliver:

- fetched page summaries for Context Manager;
- content hash and URL descriptors for Audit;
- diagnostics-safe redacted descriptor.

Acceptance:

- page body is bounded;
- fetched content is represented as external evidence, not instructions.

### EWF-7. Product Smoke

Deliver:

- unit tests with mock provider;
- sidecar integration test for Settings and tool registration;
- optional manual Tavily Extract smoke with a real key.

Acceptance:

- deterministic CI stays offline;
- manual smoke can fetch one public documentation URL.

## 10. Implementation Evidence

Implemented in this slice:

- provider-neutral fetch models in `taskweavn.web_retrieval.models`;
- `WebFetchProvider` protocol;
- public URL policy in `taskweavn.web_retrieval.url_policy`;
- Tavily Extract adapter in `taskweavn.web_retrieval.tavily`;
- `WebFetchTool` with bounded URL/content caps;
- global Settings `webSearch.fetchEnabled` and fetch caps;
- Settings UI Web Page Fetch toggle and bounded cap controls;
- execution Agent registration gated by Web Search readiness and fetch toggle;
- Context controls and guidance for `web_fetch`;
- deterministic mock-provider tests.

Validation evidence:

- `uv run pytest tests/test_web_fetch.py tests/test_web_search.py tests/test_settings_config.py`;
- `uv run ruff check ...`;
- `uv run mypy ...`;
- `npm test -- --run src/pages/settings/SettingsRoute.test.tsx src/shared/api/platoApi.test.ts src/app/App.test.tsx`;
- `npm run build`;
- `npm run lint`.

## 11. Resolved First-Version Decisions

1. `web_fetch` defaults to off even when `web_search` is enabled.
2. V1 accepts public `http(s)` URLs from either recent `web_search` results or
   explicit user-provided URLs.
3. V1 stores URL/content hash/truncation descriptors in the tool observation;
   Audit-specific projection enhancement is deferred.
4. `query` is optional in v1.
5. Per-session web retrieval budget is deferred.

## 12. Remaining Future Gaps

1. Should Audit expose bounded page preview by default, or only metadata until
   the user expands the record?
2. Should `web_fetch` count toward a future per-session web retrieval budget?
3. Should high-risk fetch patterns require user confirmation after the
   Autonomy Gate policy is extended to web retrieval?
