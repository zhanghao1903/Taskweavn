# Product 1.1 Web Retrieval Live Smoke

> Status: P1 beta-hardening runbook
>
> Last Updated: 2026-06-24
>
> Related:
> [Execution Web Search Capability](../plans/feature/execution-web-search-capability.md),
> [Execution Web Fetch Capability](../plans/feature/execution-web-fetch-capability.md),
> [Product 1.1 Open Work](../product/plato-1-1-open-work.md)

## Purpose

Product 1.1 includes Tavily-backed `web_search` and `web_fetch` client tools.
Mock-provider coverage proves the normalized contracts, but beta release
readiness also needs a repeatable way to verify the real Tavily Search and
Extract endpoints when a release operator has a valid API key.

This smoke is intentionally opt-in. It performs live network calls and can
consume provider credits.

## Command

```bash
PLATO_RUN_LIVE_WEB_RETRIEVAL_SMOKE=1 \
TAVILY_API_KEY=tvly-... \
uv run pytest tests/test_web_retrieval_live_smoke.py
```

Optional query override:

```bash
PLATO_RUN_LIVE_WEB_RETRIEVAL_SMOKE=1 \
TAVILY_API_KEY=tvly-... \
PLATO_LIVE_WEB_RETRIEVAL_QUERY="site:docs.tavily.com Tavily Extract API" \
uv run pytest tests/test_web_retrieval_live_smoke.py
```

Without both `PLATO_RUN_LIVE_WEB_RETRIEVAL_SMOKE=1` and `TAVILY_API_KEY`, the
test skips and does not make network calls.

## What It Verifies

- `TavilyWebSearchProvider` can call the real Search endpoint.
- The normalized search response contains at least one HTTPS result.
- `TavilyWebFetchProvider` can call the real Extract endpoint for a selected
  search result.
- The normalized fetch response returns bounded non-empty page content.

## What It Does Not Verify

- User-visible citation layout in the Main Page Conversation.
- Audit detail depth for web retrieval evidence.
- Per-session or per-provider retrieval budget enforcement.
- Provider behavior under rate limits or exhausted Tavily credits.

Those remain separate Product 1.1 beta-hardening items.
