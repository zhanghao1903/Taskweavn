# Token Usage Analytics Contract

> Status: completed Product 1.1 token usage analytics contract
>
> Last Updated: 2026-06-11
>
> Related plan:
> [Token Usage Analytics](../plans/feature/token-usage-analytics.md)

## 1. Purpose

This contract defines how Plato records and exposes token usage analytics by
Task, Plan, Session, and Workspace, including provider-reported cache
effectiveness.

The contract is product-facing observability, not raw LLM logging.

## 1.1 Implementation Status

Product 1.1 implementation is complete for the local sidecar/runtime path:

- normalized usage events are recorded at the session-bound LLM boundary;
- events are persisted in workspace-local `.plato/usage.sqlite`;
- `/api/v1/usage/token-summary` and
  `/api/v1/workspaces/{workspaceId}/usage/token-summary` return contract-shaped
  summaries;
- Settings exposes Usage Information as the primary usage browsing entry;
- Main Page exposes a compact contextual Task/Plan usage row;
- diagnostic bundles include a redacted `usage/token-summary.json` summary.

Deferred follow-ups:

- billing or dollar-cost calculation;
- quota/budget enforcement;
- first-class Plan attribution before a plan is published;
- deeper correlation between provider cache hits and Context Manager
  stable-prefix metadata.

## 2. Core Types

```ts
type UsageAggregationDimension = "task" | "plan" | "session" | "workspace";

type UsageSource =
  | "provider_reported"
  | "provider_partial"
  | "estimated"
  | "unavailable";

type CacheRateSource =
  | "hit_miss_tokens"
  | "input_tokens"
  | "unavailable";
```

Product 1.1 first implementation should use `provider_reported`,
`provider_partial`, and `unavailable`. `estimated` is reserved for future local
token estimation and must be visibly labeled if ever exposed.

## 3. Usage Event Shape

Backend normalized event:

```ts
type TokenUsageEvent = {
  usageEventId: string;
  occurredAt: string;
  workspaceId: string;
  sessionId: string | null;
  planId: string | null;
  taskNodeId: string | null;
  agentRunId: string | null;
  requestPurpose: string;
  provider: string | null;
  model: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
  reasoningTokens: number | null;
  cachedTokens: number | null;
  cacheHitTokens: number | null;
  cacheMissTokens: number | null;
  cacheHitRatio: number | null;
  usageSource: UsageSource;
  cacheRateSource: CacheRateSource;
};
```

Rules:

- `workspaceId` is a safe workspace identifier, not a filesystem path;
- `sessionId` is required for session-bound authoring/execution calls;
- `taskNodeId` is nullable because authoring and setup calls may not map to a
  Task;
- `planId` is nullable until the Plan model is first-class;
- `provider` and `model` are display-safe strings only;
- `provider_request_id` may be stored only as a hash or redacted correlation id.

## 4. Aggregation Shape

```ts
type TokenUsageSummary = {
  dimension: UsageAggregationDimension;
  id: string;
  label: string;
  workspaceId: string;
  sessionId?: string | null;
  planId?: string | null;
  taskNodeId?: string | null;
  callCount: number;
  unknownUsageCallCount: number;
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
  reasoningTokens: number | null;
  cachedTokens: number | null;
  cacheHitTokens: number | null;
  cacheMissTokens: number | null;
  cacheHitRatio: number | null;
  cacheRateSource: CacheRateSource;
  firstOccurredAt: string | null;
  lastOccurredAt: string | null;
};

type TokenUsageSummaryResponse = {
  dimension: UsageAggregationDimension;
  totals: TokenUsageSummary;
  rows: TokenUsageSummary[];
};
```

Aggregation rules:

- sum known counters;
- keep aggregate counters `null` only when no included event reports that
  counter;
- `unknownUsageCallCount` counts calls with no provider token usage;
- `cacheHitRatio` is computed from aggregate token sums, not by averaging per
  call ratios;
- a Task aggregate includes only calls attributed to that Task;
- a Plan aggregate includes calls attributed to that Plan plus child Task calls
  when the Plan/Task relationship is known;
- a Session aggregate includes all calls attributed to the Session;
- a Workspace aggregate includes all calls attributed to the Workspace.

## 5. Cache Hit Rate Contract

Preferred formula:

```text
sum(cacheHitTokens) / (sum(cacheHitTokens) + sum(cacheMissTokens))
```

Fallback formula:

```text
sum(cacheHitTokens) / sum(inputTokens)
```

Use fallback only when:

- hit tokens are present;
- miss tokens are unavailable;
- input tokens are present and greater than zero.

If neither formula is available, return:

```json
{
  "cacheHitRatio": null,
  "cacheRateSource": "unavailable"
}
```

Provider-reported cache hit rate and Context Manager stable-prefix metadata are
separate facts. The API may later expose both, but must not combine them into a
single misleading metric.

## 6. API Endpoints

Workspace-scoped Product 1.1 endpoints:

```http
GET /api/v1/usage/token-summary?dimension=workspace
GET /api/v1/workspaces/{workspaceId}/usage/token-summary?dimension=workspace
GET /api/v1/workspaces/{workspaceId}/usage/token-summary?dimension=session
GET /api/v1/workspaces/{workspaceId}/usage/token-summary?dimension=plan&sessionId={sessionId}
GET /api/v1/workspaces/{workspaceId}/usage/token-summary?dimension=task&sessionId={sessionId}
```

Optional filters:

| Query | Meaning |
|---|---|
| `sessionId` | Narrow to one Session. |
| `planId` | Narrow to one Plan. |
| `taskNodeId` | Narrow to one Task. |
| `from` / `to` | ISO datetime window. |
| `provider` | Filter display-safe provider id. |
| `model` | Filter display-safe model id. |

Response:

```json
{
  "ok": true,
  "data": {
    "dimension": "task",
    "totals": {
      "dimension": "task",
      "id": "total",
      "label": "Total",
      "workspaceId": "workspace-a",
      "callCount": 3,
      "unknownUsageCallCount": 1,
      "inputTokens": 12000,
      "outputTokens": 900,
      "totalTokens": 12900,
      "reasoningTokens": 240,
      "cachedTokens": 8000,
      "cacheHitTokens": 8000,
      "cacheMissTokens": 4000,
      "cacheHitRatio": 0.6667,
      "cacheRateSource": "hit_miss_tokens",
      "firstOccurredAt": "2026-06-10T00:00:00Z",
      "lastOccurredAt": "2026-06-10T00:02:00Z"
    },
    "rows": []
  },
  "error": null,
  "requestId": "request-id",
  "generatedAt": "2026-06-10T00:03:00Z"
}
```

## 7. UI Contract

Main Page Task detail may show:

- total tokens;
- input/output split;
- reasoning tokens when reported;
- cache hit rate when available;
- unknown usage count when relevant.

Plan/Session/Workspace usage views may show:

- totals;
- row breakdowns;
- cache hit rate;
- last activity time.

Implemented surfaces:

- compact Task and Plan usage cards in the Main Page detail panel;
- Workspace Usage page showing Workspace, Session, Plan, and Task summary
  sections.

Product 1.1 IA update:

- Settings -> Usage Information is the primary user entry for browsing token
  usage.
- Main Page must not expose a first-level Usage action/button.
- The deep route `/workspaces/{workspaceId}/usage` may remain for direct links,
  tests, and future diagnostics handoff.

Copy rules:

- use `Not reported` for missing provider usage;
- use `Cache unavailable` for unavailable cache rate;
- never show raw provider payloads;
- never show absolute workspace paths;
- never imply billing cost unless a separate price contract exists.

## 8. Persistence Contract

The first durable store should be workspace-local:

```text
.plato/usage.sqlite
```

The store may be queried by the sidecar runtime only. Renderer APIs must remain
workspace-id scoped.

Required indexes:

- `(workspace_id, occurred_at)`;
- `(workspace_id, session_id, occurred_at)`;
- `(workspace_id, session_id, task_node_id, occurred_at)`;
- `(workspace_id, session_id, plan_id, occurred_at)`;
- `(workspace_id, provider, model, occurred_at)`.

## 9. Safety Contract

Usage analytics must not persist or expose:

- raw prompts;
- raw completions;
- tool arguments;
- provider payloads;
- API keys or tokens;
- provider auth headers;
- raw exceptions;
- absolute local filesystem paths.

Diagnostic bundles may include aggregate usage summaries and selected usage
events after applying the same redaction rules.

## 10. Test Contract

Required focused tests:

- normalize full provider usage;
- normalize partial provider usage;
- store event without raw prompt/completion/provider payload;
- aggregate by Task;
- aggregate by Plan when task-to-plan relation exists;
- aggregate by Session;
- aggregate by Workspace;
- compute cache hit rate from hit/miss tokens;
- compute fallback cache hit rate from hit/input tokens;
- return unavailable cache rate when denominator is missing;
- reject or ignore unknown workspace ids without leaking paths.

## 11. Completed Implementation Boundary

The completed Product 1.1 slice includes:

- normalized event model;
- SQLite usage store;
- usage recorder at the LLM call boundary with product attribution;
- workspace-scoped summary API;
- Settings Usage Information as the primary usage browsing entry;
- Main Page compact contextual usage row;
- backend and frontend contract tests.

It should not add:

- budget enforcement;
- billing/price calculation;
- a broad dashboard;
- cloud sync;
- provider-specific cost tables;
- prompt/content inspection.
