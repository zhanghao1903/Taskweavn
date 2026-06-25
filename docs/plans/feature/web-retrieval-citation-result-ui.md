# Feature Plan: Web Retrieval Citation And Result UI

> Status: planned Product 1.1 P1 hardening
>
> Last Updated: 2026-06-24
>
> Owner: Product / Frontend / UI Contract / Audit / Trust
>
> Related:
> [Execution Web Search Capability](execution-web-search-capability.md),
> [Execution Web Fetch Capability](execution-web-fetch-capability.md),
> [Plato 1.1 Product Plan](../../product/plato-1-1-product-plan.md),
> [Plato Audit Page UX Flow](../../product/plato-audit-page-ux-flow.md),
> [Plato UI API Contract](../../product/plato-ui-api-contract.md)

---

## 1. Purpose

Product 1.1 web retrieval can already collect bounded external evidence through
`web_search` and `web_fetch`, and Context/Audit/diagnostics receive safe
descriptors. The remaining P1 trust gap is user comprehension:

```text
Agent used web evidence
  -> user sees an answer or artifact
  -> user needs to know which public sources informed it
  -> user can inspect source descriptors in Audit without reading raw logs
```

This plan defines the minimal citation/result UI and Audit projection needed to
make web retrieval understandable during beta without building a full research
workspace.

## 2. Product Boundary

The feature is evidence presentation, not retrieval expansion.

In scope:

- show which search/fetch sources contributed to an answer, result, or task;
- distinguish `search_result` evidence from `fetched_page` evidence;
- show safe metadata: title, URL, provider, retrieval time, snippet/summary,
  truncation, content hash, and error state when available;
- provide Audit detail projection for search/fetch operations;
- preserve no-secret and no-raw-oversized-payload constraints.

Out of scope:

- browser automation;
- authenticated pages;
- recursive crawling;
- source ranking or deep research workspace;
- user-managed retrieval budgets;
- full raw page body display by default;
- provider-hosted search adapters.

## 3. User-Facing Behavior

### Main Page Result Surface

When a task result or read-only answer used web retrieval evidence, the result
surface should show a compact `Sources used` section.

Minimal source card fields:

| Field | Behavior |
|---|---|
| Source title | Prefer provider title; fall back to URL host/path. |
| URL | Opens as external URL only after standard safe-link handling. |
| Evidence type | `Search result`, `Fetched page`, or `Retrieval error`. |
| Provider | Example: `Tavily`. |
| Retrieved at | Local time. |
| Snippet / summary | Bounded text, never a raw full page by default. |
| Truncation | Visible when content or descriptors were truncated. |

Inline citation chips may be added later, but the P1 minimum is a grouped
source section near the answer/result. This avoids needing exact sentence-level
grounding before the Agent output contract supports it.

### Audit Detail Projection

Audit should expose web retrieval evidence as structured records:

- `web_search` query, provider, result count, truncation, and result URLs;
- `web_fetch` URL list, provider, success/error per URL, content hash, and
  truncation;
- relation to task/result/read-only inquiry when available;
- disclosure state when raw content is hidden or only partially available.

Audit must not expose provider API keys, raw request headers, private local
paths, or unbounded page bodies.

### Diagnostics

Diagnostics can keep descriptor-level summaries. The UI should link to
diagnostics only when a support path exists; ordinary users should not need to
open a diagnostic bundle to understand which public sources were used.

## 4. UI Contract Direction

Add a small projection model instead of leaking provider payloads into UI:

```python
class WebRetrievalSourceProjection:
    id: str
    evidence_type: Literal["search_result", "fetched_page", "retrieval_error"]
    provider: str
    title: str | None
    url: str | None
    retrieved_at: datetime | None
    snippet: str | None
    summary: str | None
    content_hash: str | None
    truncated: bool
    status: Literal["ok", "partial", "failed"]
    audit_ref: AuditRef | None
```

Attach source projections to existing UI scopes where evidence is already
represented:

- task result;
- read-only inquiry result;
- Audit record detail;
- Activity item refs when the source list is small.

Do not make frontend components parse raw tool observations directly.

## 5. Implementation Slices

### C1. Projection Contract Inventory

- Inventory existing web retrieval descriptors in Context/Audit/diagnostics.
- Define the smallest UI projection model.
- Add fixture examples for search-only, fetch-success, fetch-partial, and
  provider-failed cases.

Acceptance:

- UI fixtures can render source cards without provider payloads.
- No API shape is invented inside UI components.

### C2. Shared Source Components

- Add shared source list/source card primitives.
- Reuse existing Markdown and link safety rules.
- Handle empty, partial, failed, truncated, and hidden-evidence states.

Acceptance:

- Components support hover/focus/disabled/error states.
- Long URLs and snippets do not overflow the main/detail layout.

### C3. Main Result Surface

- Show `Sources used` for task results and read-only answers when source
  projections exist.
- Keep the result readable when no sources exist.
- Avoid showing raw provider debug text in the conversation stream.

Acceptance:

- User can identify which public sources informed the result.
- No source section appears for results that did not use web retrieval.

### C4. Audit Detail Projection

- Add Audit detail rendering for web search/fetch evidence.
- Show disclosure status for hidden or truncated evidence.
- Link back to related task/result/read-only inquiry when available.

Acceptance:

- Support can inspect query/URL/provider/status without reading logs.
- Audit does not expose secrets or oversized raw content.

### C5. Validation

- Unit tests for projection builders and source UI components.
- Fixture tests for conversation/result rendering.
- Audit detail tests for search/fetch/partial/error cases.
- Manual smoke with mock data before any live Tavily validation.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Users assume citations are sentence-level proof. | Use `Sources used` wording until exact citation spans exist. |
| UI exposes too much provider payload. | Use bounded projection models only. |
| Audit becomes noisy. | Collapse source details by default; show descriptors first. |
| Long URLs break layout. | Apply wrapping/truncation and accessible title text. |
| Fetch content appears authoritative when partial. | Display `partial` and `truncated` states explicitly. |

## 7. Acceptance Criteria

This plan is ready for implementation when:

- the UI projection model is accepted;
- Main result and Audit detail surfaces are the first two target surfaces;
- `Sources used` is accepted as the P1 wording;
- raw provider payloads remain out of normal UI;
- implementation slices C1-C5 can be executed independently.
