# Plato 1.1 Web Retrieval Beta Limitations

> Status: Product 1.1 P1 beta hardening reference
> Last Updated: 2026-06-24
> Scope: user-visible limits for `web_search` and `web_fetch`

Product 1.1 web retrieval gives execution Agents controlled access to public
external evidence. It is not a general browser, crawler, or research agent.

This document defines the beta limitations that should be visible in release
notes, Settings copy, support docs, and public-facing Product 1.1 material.

## 1. What Works In 1.1 Beta

- `web_search` can call the configured Tavily Search provider when web search
  is enabled and a valid key is stored.
- `web_fetch` can call the configured Tavily Extract provider for selected
  public `http(s)` URLs when fetch is enabled.
- Provider keys are write-only from the UI perspective. Configuration reads and
  rechecks must not expose the secret value.
- Search and fetch output is treated as external evidence, not as instructions
  for the Agent or system.
- Context Manager, Audit, and diagnostics receive bounded evidence descriptors
  such as provider, query or URL, timestamp, result URLs, truncation, and safe
  summary metadata.
- Deterministic CI uses mock providers. Live provider smoke is optional and
  requires explicit local configuration.

## 2. User-Visible Limitations

### 2.1 Availability

- Web retrieval is disabled by default until the user enables it in Settings.
- Live retrieval depends on provider availability, network reachability,
  account permissions, rate limits, and remaining provider credits.
- If the provider is unavailable, Plato should fail closed with a user-visible
  explanation rather than inventing unsupported evidence.

### 2.2 Freshness And Accuracy

- Search snippets may be stale, incomplete, duplicated, or inconsistent across
  sources.
- Time-sensitive questions depend on the injected current date and timezone,
  plus the freshness of returned sources.
- Plato should present retrieved material as evidence-backed assistance, not as
  an authoritative source of truth.
- Users should verify high-stakes, legal, medical, financial, operational, or
  time-critical answers against primary sources.

### 2.3 Fetch Coverage

- `web_fetch` is limited to selected public `http(s)` URLs.
- Fetch does not support authenticated pages, logged-in sessions, cookies,
  browser extension state, interactive forms, screenshots, or JavaScript-only
  rendering.
- Fetch does not perform recursive crawling.
- Fetch does not extract PDF, OCR, image, video, audio, or arbitrary media
  content in the Product 1.1 beta path.
- Fetch may return truncated content when the provider or Plato safety bounds
  limit the response.

### 2.4 Evidence And UI

- Product 1.1 evidence projection is intentionally bounded. Audit and
  diagnostics show safe descriptors, not full provider payloads.
- Broader citation/result cards, source comparison, and expandable Audit
  source previews remain follow-up hardening.
- A generated answer can cite search/fetch evidence, but the UI does not yet
  provide a full research workspace for ranking, comparing, or saving sources.

### 2.5 Cost And Budget Boundaries

- Live calls may consume third-party provider credits.
- Product 1.1 does not yet provide per-session web retrieval budgets,
  per-question cost previews, or retrieval-specific spend controls.
- Users should treat live web retrieval as an opt-in beta capability and keep it
  disabled when external calls are not needed.

## 3. Non-Goals For 1.1 Beta

- Browser automation or Computer Use browsing.
- Authenticated web access.
- Recursive crawling.
- Dynamic rendering.
- PDF/OCR/media extraction.
- Hosted-provider search adapters beyond the current Tavily path.
- Deep research workflows with multi-source synthesis workspaces.
- User-managed per-session retrieval budgets.
- Full citation/result card UI.

## 4. Recommended User-Facing Copy

Settings helper copy:

```text
Enable web retrieval to let execution tasks search or fetch public web evidence
through the configured provider. Results may be incomplete or stale, live calls
can consume provider credits, and Plato does not browse authenticated or
dynamic pages in this beta.
```

Release-note copy:

```text
Product 1.1 includes beta web retrieval for controlled public search and
selected URL fetch. It is evidence-oriented, opt-in, and bounded: no
authenticated browsing, no browser automation, no crawling, no PDF/OCR/media
extraction, and no per-session retrieval budgets yet.
```

Failure copy:

```text
Web retrieval could not produce reliable external evidence. Check provider
configuration, network availability, rate limits, and whether the requested
source is public and supported.
```

## 5. Beta Acceptance Checklist

- Settings clearly distinguishes search enablement, fetch enablement, and
  write-only provider key storage.
- Retrieval unavailable states produce user-visible Activity or error evidence.
- Context/Audit/diagnostics preserve safe evidence descriptors without leaking
  secrets or raw oversized provider payloads.
- Release docs link to this limitations page.
- Support/debug docs state that live provider behavior is optional and
  environment-dependent.
- Follow-up work remains tracked for citation/result UI, Audit projection
  depth, and retrieval budgets.

