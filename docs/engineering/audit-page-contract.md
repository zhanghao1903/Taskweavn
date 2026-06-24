# Audit Page Backend-To-Frontend Contract

> Status: implementation contract with mock-backed frontend baseline and
> projection-backed real HTTP query path plus first EventStream/log/config
> source references, sanitized payload disclosure, and runtime event/refetch
> design baseline
> Last Updated: 2026-06-01
> Scope: Audit Page API, backend ViewModel, frontend ViewModel, events, mock scenarios.
> Non-goals: no raw payload exposure, no MainPage rewrite, no full audit storage rewrite.
> Disclosure Design:
> [Audit Page Sanitized Payload Disclosure Technical Design](../plans/ui/audit-page-sanitized-payload-disclosure-technical-design.md)
> Runtime Event Design:
> [Audit Page Runtime Event And Refetch Technical Design](../plans/ui/audit-page-runtime-event-refetch-technical-design.md)

## 0. Implementation Checkpoint

As of 2026-06-01, this contract is no longer only a proposed backend model.
The backend additive contract models, frontend transport/mock baseline,
mock-backed Audit Page route, page shell, A1-A14 scenario coverage, and Main
Page audit entry navigation are in place. The real backend audit query path is
now implemented as a projection-backed first pass and has been hardened with
source-provider seams for EventStream, log archive, and config manifest facts.

Backend contract baseline:

- `src/taskweavn/server/ui_contract/view_models.py` defines Audit Page
  ViewModels for scope, entry context, return target, overview, filters,
  records, record detail, evidence, config summary, related logs, permissions,
  and page states.
- `src/taskweavn/server/ui_contract/snapshots.py` defines `AuditPageSnapshot`.
- `src/taskweavn/server/ui_contract/events.py` defines additive event literals
  and builders for `audit.summary_updated`, `audit.records_changed`,
  `audit.record_updated`, `audit.evidence_hidden`, and `audit.snapshot_stale`.
- `tests/test_audit_page_contract_models.py` covers focused validation for the
  new contract shape, public verdict values, record detail consistency, config
  scope anchoring, sanitized payload disclosure, and audit event payloads.
- `DefaultUiQueryGateway` exposes Audit Page snapshot, records, record detail,
  and evidence detail using the same frontend contract in HTTP mode.
- `WorkspaceAuditEventProvider` can project durable `events.sqlite` Action /
  Observation / AuditObservation facts into productized audit records.
- `WorkspaceAuditLogProvider` can expose session log archive files as
  `log_evidence` records and related-log links.
- `WorkspaceAuditConfigProvider` can expose a session logging manifest as a
  `config_change` record and effective config summary.

Frontend transport/mock baseline:

- `frontend/src/shared/api/types.ts` defines Audit Page transport types for
  snapshot, request, overview, filters, records, record detail, evidence,
  permissions, and page states.
- `frontend/src/shared/api/platoApi.ts` defines audit query methods for
  snapshot, records, record detail, and evidence detail.
- `frontend/src/app/routes.ts` defines session and task audit routes plus route
  builders.
- `frontend/src/entities/audit/model.ts` re-exports Audit Page model helpers on
  top of the API contract.
- `frontend/src/pages/audit-page/mockAuditScenarios.ts` and
  `frontend/src/pages/audit-page/mockAuditApi.ts` provide mock scenarios and a
  mock API for Audit Page development.
- `frontend/src/shared/api/apiUiMapping.ts` maps Audit Page API states to UI
  boundary states.
- `frontend/src/app/platoRuntime.ts` can create the audit API in mock or HTTP
  mode.
- Focused frontend tests cover audit types, API methods, routes, mock
  scenarios/API, runtime construction, and API-to-UI boundary mapping.

Still not implemented:

- Full `TaskInteractionTimelineService` aggregation.
- Dedicated audit storage/query projection beyond productized records.
- Runtime audit event emission points. AP-013A defines the event, scope,
  cursor, and frontend invalidation strategy; AP-013B wires the frontend event
  router/hook with mock subscription tests; AP-013C adds visible live
  refresh/stale/disconnected feedback; and AP-013D adds the workspace-backed
  `SqliteUiEventSource` replay store. AP-013E emits the first task-scoped
  `audit.records_changed` event after AgentLoop writes EventStream facts, and
  AP-013F adds config manifest, log archive, and confirmation resolution
  `audit.records_changed` emissions.
- Broader runtime emission points beyond AgentLoop/config/log/confirmation.
- Product-grade mobile layout below the current supported minimum width.

## 1. Purpose

Audit Page is Plato's Trust Plane. It must let users inspect what happened,
why it matters, what evidence exists, what is incomplete, and how to return to
the Main Page context that started the audit.

The backend has additive Audit Page transport models, audit event builders, and
a first real route/gateway/data-aggregation path. The frontend has
matching TypeScript types, route builders, API client methods, mock scenarios,
mock API, runtime wiring, page route/shell/components, Main Page entry
navigation, and contract tests. AP-010/AP-011 adds the first real backend
query path: `DefaultUiQueryGateway` can now produce projection-backed
session/task audit snapshots, record lists, record details, and evidence
details, `ui_http.py` exposes the corresponding frontend endpoints, and the
gateway can now fold in EventStream, log archive, logging manifest source
records, and request-time sanitized payload disclosure when those sources
exist. Runtime refetch coverage now includes AgentLoop/EventStream updates,
session logging manifest writes, frontend error log archive writes, and
confirmation resolution. The remaining implementation gap is richer timeline
aggregation plus broader runtime audit event emission/source coverage.

This document defines the backend-to-frontend contract to unblock mock data,
API implementation, Figma/dev handoff, and later frontend implementation.

## 2. Contract Principles

1. Audit Page is read-only. It never edits tasks, resolves confirmations,
   publishes, retries, cancels, or reruns execution.
2. Audit verdict is a trust-plane result, not task execution status.
3. Missing or hidden evidence must be explicit. The UI must not imply a pass
   when evidence is absent, partial, redacted, or unavailable.
4. Backend/domain facts remain canonical. UI labels, icon tones, and layout
   states are presentation mappings.
5. Raw logs, raw tool payloads, provider payloads, stack traces, secrets, and
   full LLM prompts are not returned by default.
6. Audit records should be productized facts, not database/event/log rows.
7. Audit records are safe to list. Evidence detail may require permissions or
   redaction.
8. Main Page may show an audit summary/link, but Audit Page owns the evidence
   timeline and record detail.

## 3. Current Gap Inventory

| Area | Current state | Gap |
|---|---|---|
| Backend snapshot | `src/taskweavn/server/ui_contract/snapshots.py` defines `MainPageSnapshot` and additive `AuditPageSnapshot`; `DefaultUiQueryGateway` can populate it from Task projection, EventStream, log archive, and config manifest facts where available. | Full timeline/source orchestration remains pending. |
| Backend ViewModels | Audit Page scope, overview, record, record list result, detail, evidence, config/log link, permission, and page-state models exist. | Mapping remains productized; deeper timeline aggregation remains follow-up. |
| HTTP routes | `src/taskweavn/server/ui_http.py` exposes session/task audit snapshot, records, record detail, evidence detail, and session event stream routes. | More domain-specific source events can still be added as runtime surfaces grow. |
| Events | `src/taskweavn/server/ui_contract/events.py` includes `audit.summary_updated` plus record/evidence/stale audit event builders. AP-013A defines runtime refetch semantics, AP-013D adds workspace-backed `SqliteUiEventSource` cursor replay, AP-013E appends task-scoped `audit.records_changed` after AgentLoop EventStream updates, and AP-013F appends config/log/confirmation source updates. | AuditAgent verdict-specific emissions and richer timeline ordering remain follow-up. |
| Frontend API types | `frontend/src/shared/api/types.ts` defines the Audit Page snapshot, request, overview, record, detail, evidence, permissions, and page-state types. | Keep aligned with backend contract as it evolves. |
| Frontend API client/routes | `frontend/src/shared/api/platoApi.ts` defines audit query methods; `frontend/src/app/routes.ts` defines session/task audit routes; `App.tsx` now mounts session/task Audit Page routes. | Keep HTTP mode aligned as backend source coverage grows. |
| Frontend audit entity | `frontend/src/entities/audit/model.ts` re-exports Audit Page API models and link helpers. | Add page-specific selectors/helpers when the real UI consumes the contract. |
| Frontend audit mocks | `frontend/src/pages/audit-page/mockAuditScenarios.ts` and `mockAuditApi.ts` provide A1-A14 mock coverage. | Keep as acceptance fixtures for backend parity and future UI regression. |
| Frontend UI boundary mapping | `frontend/src/shared/api/apiUiMapping.ts` includes Audit Page state-to-boundary mapping. | Exercised by the page shell; extend only when backend introduces new states. |
| Frontend Audit Page UI | Audit Page route/shell/components exist, Main Page `View audit` routes to Audit Page, HTTP mode is wired, detail/evidence can request sanitized disclosure, AP-013B wires mock-backed runtime event-to-refetch behavior, and AP-013C shows live refresh/stale/disconnected feedback. | Validate the broader source coverage through an end-to-end user path before release closure. |
| Backend audit agent | `AuditAgent` emits `pass`, `fail`, `inconclusive`; EventStream-backed `AuditObservation` records are mapped to public verdicts when present. | Audit-specific event emission and broader audit-agent source coverage are still pending. |

## 4. Audit Verdict Model

Public frontend contract:

```ts
type AuditVerdict =
  | "passed"
  | "warning"
  | "failed"
  | "inconclusive"
  | "not_available";
```

| Verdict | Semantics | Backend mapping | UI rule |
|---|---|---|---|
| `passed` | Evidence supports the result/action and no blocking concern remains. | `AuditAgent.verdict = pass` and no warning/partial finding. | Show as trusted but still inspectable. |
| `warning` | Evidence exists, but there are non-blocking risks, validation gaps, policy warnings, or incomplete checks. | Derived from risk findings, partial evidence, unresolved low/medium concerns, or rule-based warning. | Show as needs review, not failed. |
| `failed` | Evidence shows failure, policy violation, scope violation, or untrusted result. | `AuditAgent.verdict = fail`, failed record, blocking risk. | Show failed and link evidence. |
| `inconclusive` | Audit could not establish confidence. | `AuditAgent.verdict = inconclusive`, missing observation, parser failure, insufficient evidence. | Do not treat as warning or pass. |
| `not_available` | No audit summary exists for this scope yet. | No audit record/summary for scope, or audit disabled. | Must not imply pass. |

Unsupported or unknown backend verdict values should not be emitted to the
frontend as public verdicts. The backend should map them to `inconclusive` when
some evidence exists but cannot be interpreted, or `not_available` when no
usable evidence exists. Include the cause in `AuditOverview.completeness` or
record disclosure.

## 5. Audit Scope Model

Audit scopes define what the user is inspecting. They are independent from
record kind and filter kind.

```ts
type AuditScopeKind =
  | "session"
  | "workflow"
  | "task"
  | "action"
  | "confirmation"
  | "file"
  | "result"
  | "config"
  | "log_evidence";

type AuditScope =
  | { kind: "session"; sessionId: SessionId }
  | { kind: "workflow"; workflowId: WorkflowId; projectId?: ProjectId | null }
  | { kind: "task"; sessionId: SessionId; taskNodeId: TaskNodeId; taskRef?: TaskRef | null }
  | { kind: "action"; sessionId: SessionId; actionId: string; taskNodeId?: TaskNodeId | null }
  | { kind: "confirmation"; sessionId: SessionId; confirmationId: ConfirmationId; taskNodeId?: TaskNodeId | null }
  | { kind: "file"; sessionId: SessionId; path: string; taskNodeId?: TaskNodeId | null }
  | { kind: "result"; sessionId: SessionId; resultId: ResultId; taskNodeId?: TaskNodeId | null }
  | { kind: "config"; sessionId?: SessionId | null; workflowId?: WorkflowId | null; configKey?: string | null }
  | { kind: "log_evidence"; sessionId: SessionId; evidenceId: EvidenceId; taskNodeId?: TaskNodeId | null };
```

First implementation may support only `session` and `task` snapshot routes,
while allowing records and entry contexts to reference the wider scope kinds.
Do not expose workflow-wide audit until permission, pagination, and retention
rules are defined.

## 6. Route Entry Contexts

Entry context tells Audit Page how the user arrived and where to return. It is
not the same as audit scope.

```ts
type AuditEntryKind =
  | "from_session"
  | "from_task"
  | "from_confirmation"
  | "from_result"
  | "from_file_change";

type AuditEntryContext = {
  kind: AuditEntryKind;
  sessionId: SessionId;
  taskNodeId?: TaskNodeId | null;
  taskRef?: TaskRef | null;
  confirmationId?: ConfirmationId | null;
  resultId?: ResultId | null;
  filePath?: string | null;
  sourceRoute: string;
  preferredFilter?: AuditFilterKind | null;
  preferredRecordId?: AuditRecordId | null;
};

type MainPageReturnTarget = {
  routeName: "main.session" | "main.sessionFallback";
  sessionId: SessionId;
  projectId?: ProjectId | null;
  workflowId?: WorkflowId | null;
  taskNodeId?: TaskNodeId | null;
  focus:
    | "session"
    | "task"
    | "confirmation"
    | "result"
    | "file_change";
  recordId?: AuditRecordId | null;
};
```

Entry defaults:

| Entry | Default scope | Default filter | Default selected record | Return focus |
|---|---|---|---|---|
| `from_session` | `session` | `all` | most important issue if any, else none | `session` |
| `from_task` | `task` | `all` | none or most important task record | `task` |
| `from_confirmation` | `confirmation` or task fallback | `confirmations` | confirmation record | `confirmation` |
| `from_result` | `result` or task fallback | `results` | result record | `result` |
| `from_file_change` | `file` or task fallback | `files` | file change record | `file_change` |

## 7. AuditPageSnapshot

`AuditPageSnapshot` is the primary query result for Audit Page. It should be
mockable before real backend data sources are complete.

```ts
type AuditPageSnapshot = {
  schemaVersion: "plato.audit.v1";
  request: AuditPageRequestView;
  scope: AuditScope;
  entryContext: AuditEntryContext;
  returnTarget: MainPageReturnTarget;

  project: ProjectSummary | null;
  workflow: WorkflowSummary | null;
  session: SessionSummary;
  selectedTask: TaskNodeCardView | null;

  overview: AuditOverview;
  filters: AuditFilterView[];
  records: AuditRecord[];
  selectedRecord: AuditRecordDetail | null;

  effectiveConfig: EffectiveConfigSummary | null;
  relatedLogs: RelatedLogsLink[];
  permissions: AuditPermissions;
  pageState: AuditPageState;

  cursor: EventCursor | null;
  generatedAt: string;
};

type AuditPageRequestView = {
  filter: AuditFilterKind;
  recordId?: AuditRecordId | null;
  includeDetail: boolean;
  limit: number;
  cursor?: string | null;
};
```

### 7.1 Audit Overview

```ts
type AuditCompleteness =
  | "not_started"
  | "running"
  | "partial"
  | "complete"
  | "failed"
  | "hidden";

type AuditOverview = {
  verdict: AuditVerdict;
  completeness: AuditCompleteness;
  summary: string;
  keyIssue: string | null;
  recordCounts: Record<AuditFilterKind, number>;
  importantRecordIds: AuditRecordId[];
  hiddenEvidenceCount: number;
  partialReason?: string | null;
  generatedBy: "audit_agent" | "projection" | "rules" | "mock";
  updatedAt: string;
};
```

### 7.2 Filters

```ts
type AuditFilterKind =
  | "all"
  | "confirmations"
  | "actions"
  | "risks"
  | "files"
  | "results"
  | "system"
  | "config"
  | "logs";

type AuditFilterView = {
  kind: AuditFilterKind;
  label: string;
  count: number;
  enabled: boolean;
  disabledReason?: string | null;
};
```

Counts stay visible even when zero. Selecting a zero-count filter returns a
filtered empty state, not a page error.

### 7.3 Page State And Permissions

```ts
type AuditPageState =
  | { kind: "loading"; message: string }
  | { kind: "ready" }
  | { kind: "empty"; reason: string }
  | { kind: "partial"; reason: string }
  | { kind: "hidden_evidence"; reason: string; hiddenCount: number }
  | { kind: "permission_denied"; reason: string }
  | { kind: "error"; code: string; message: string; retryable: boolean }
  | { kind: "stale"; reason: string };

type AuditPermissions = {
  canViewAudit: boolean;
  canViewEvidence: boolean;
  canViewHiddenEvidenceReason: boolean;
  canOpenRelatedLogs: boolean;
  readonlyReason?: string | null;
};
```

`loading` is usually frontend-local while the query is pending. It is included
here so mock scenarios can declare it. Backend query errors should still use
the standard `QueryResponse<AuditPageSnapshot>` error envelope.

## 8. AuditRecord

`AuditRecord` is the list item shape. It must be concise, safe by default, and
stable enough for filtering, selection, and deep links.

```ts
type AuditRecordId = string;
type EvidenceId = string;

type AuditRecordKind =
  | "confirmation"
  | "action"
  | "observation"
  | "risk"
  | "file_change"
  | "result"
  | "message"
  | "config_change"
  | "audit_verdict"
  | "system"
  | "log_evidence";

type AuditActorKind =
  | "user"
  | "agent"
  | "tool"
  | "system"
  | "audit_agent";

type AuditSeverity =
  | "info"
  | "success"
  | "warning"
  | "danger";

type AuditConfidence =
  | "high"
  | "medium"
  | "low"
  | "unknown";

type AuditRecord = {
  id: AuditRecordId;
  scope: AuditScope;
  kind: AuditRecordKind;
  filterKind: AuditFilterKind;

  title: string;
  summary: string;
  actor: AuditActorKind;
  sourceLabel: string;
  occurredAt: string;

  severity: AuditSeverity;
  confidence: AuditConfidence;
  verdict?: AuditVerdict | null;
  completeness: AuditCompleteness;

  taskNodeId?: TaskNodeId | null;
  taskRef?: TaskRef | null;
  actionId?: string | null;
  confirmationId?: ConfirmationId | null;
  resultId?: ResultId | null;
  filePath?: string | null;
  configKey?: string | null;

  evidenceRefs: EvidenceRef[];
  relatedRecordIds: AuditRecordId[];
  flags: AuditRecordFlags;
};

type AuditRecordFlags = {
  partial: boolean;
  hidden: boolean;
  redacted: boolean;
  stale: boolean;
  userVisible: boolean;
};
```

### 8.1 AuditRecordDetail

`AuditRecordDetail` is returned by snapshot when selected, or by the detail
endpoint. It answers "what happened, why it matters, where evidence came from,
what is missing or hidden."

```ts
type AuditRecordDetail = AuditRecord & {
  body: string;
  whyItMatters: string;
  outcome: string | null;
  references: AuditReference[];
  evidence: EvidenceSummary[];
  disclosure: AuditDisclosure;
  relatedLogs: RelatedLogsLink[];
  rawPayload: SanitizedRawPayload | null;
};

type AuditReference = {
  kind:
    | "task"
    | "message"
    | "confirmation"
    | "action"
    | "observation"
    | "file"
    | "result"
    | "config"
    | "log"
    | "external";
  label: string;
  href?: string | null;
  ref?: ObjectRef | null;
};

type AuditDisclosure = {
  rawPayloadAvailable: boolean;
  rawPayloadShown: boolean;
  redactionReason?: string | null;
  hiddenReason?: string | null;
  partialReason?: string | null;
  permissionReason?: string | null;
};
```

`rawPayload` is `null` by default. If later supported, it must be sanitized and
permission-gated.

## 9. Evidence Contract

Evidence can be linked from records without embedding raw data in the record
list. The frontend may request evidence detail only when the user opens a
record or explicit evidence link.

```ts
type EvidenceKind =
  | "message"
  | "event"
  | "action"
  | "observation"
  | "file_change"
  | "result"
  | "audit_observation"
  | "config_snapshot"
  | "log_excerpt";

type EvidenceRef = {
  id: EvidenceId;
  kind: EvidenceKind;
  label: string;
  summary: string;
  available: boolean;
  hidden: boolean;
  redacted: boolean;
};

type EvidenceSummary = EvidenceRef & {
  source: "event_stream" | "message_stream" | "task_projection" | "workspace_inspection" | "audit_agent" | "config_store" | "log_archive" | "mock";
  occurredAt?: string | null;
};

type EvidenceDetail = EvidenceSummary & {
  body: string;
  sanitizedPayload: SanitizedRawPayload | null;
  disclosure: AuditDisclosure;
};

type SanitizedRawPayload = {
  format: "json" | "text";
  content: string;
  redactions: string[];
};
```

## 10. Config And Related Logs

```ts
type EffectiveConfigSummary = {
  summary: string;
  profileLabel: string;
  effectiveAt: string;
  relevantRecordIds: AuditRecordId[];
  settingsHref?: string | null;
};

type RelatedLogsLink = {
  label: string;
  href: string;
  filters: {
    sessionId?: SessionId | null;
    workflowId?: WorkflowId | null;
    taskNodeId?: TaskNodeId | null;
    recordId?: AuditRecordId | null;
    category?: string | null;
  };
  enabled: boolean;
  disabledReason?: string | null;
};
```

Audit Page may link to Diagnostics/Logs. It must not become the full log viewer.

## 11. Endpoint Candidates

These endpoints are candidates for the later backend implementation. They are
named to preserve existing `/api/v1/sessions/{sessionId}` style while allowing
record/evidence resources to be addressed directly.

### 11.1 Get audit snapshot

Session scope:

```http
GET /api/v1/sessions/{sessionId}/audit
```

Task scope:

```http
GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/audit
```

Optional query:

| Param | Meaning |
|---|---|
| `filter` | `AuditFilterKind`, default `all`. |
| `recordId` | Selected record to include as `selectedRecord`. |
| `entry` | Entry context hint such as `from_task` or `from_file_change`. |
| `includeDetail` | Whether to include selected record detail. Default `true` when `recordId` is present. |
| `limit` | Record list page size. |
| `cursor` | Pagination cursor, not event cursor. |

Response:

```ts
type GetAuditSnapshotResponse = QueryResponse<AuditPageSnapshot>;
```

### 11.2 List audit records

```http
GET /api/v1/sessions/{sessionId}/audit/records
GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/audit/records
```

Optional query:

| Param | Meaning |
|---|---|
| `filter` | Filter records by kind group. |
| `kind` | Filter by exact `AuditRecordKind`. |
| `from` / `to` | Optional time range. |
| `limit` / `cursor` | Pagination. |
| `includeHiddenReasons` | Include hidden evidence reason if permitted. |

Response:

```ts
type ListAuditRecordsResponse = QueryResponse<{
  records: AuditRecord[];
  nextCursor: string | null;
  totalCount: number | null;
}>;
```

### 11.3 Get audit record detail

```http
GET /api/v1/sessions/{sessionId}/audit/records/{recordId}
```

Optional query:

| Param | Meaning |
|---|---|
| `includeEvidence` | Include evidence summaries. |
| `includeSanitizedPayload` | Include sanitized payload only when permitted. Default `false`. |

Response:

```ts
type GetAuditRecordDetailResponse = QueryResponse<AuditRecordDetail>;
```

### 11.4 Get evidence

```http
GET /api/v1/sessions/{sessionId}/audit/evidence/{evidenceId}
```

Optional query:

| Param | Meaning |
|---|---|
| `includeSanitizedPayload` | Include sanitized payload if user has permission. |

Response:

```ts
type GetEvidenceResponse = QueryResponse<EvidenceDetail>;
```

### 11.5 Future workflow scope

Workflow-wide audit should be a later endpoint because it expands retention and
permission requirements:

```http
GET /api/v1/workflows/{workflowId}/audit
```

Do not implement workflow audit in the first task unless product explicitly
prioritizes it.

## 12. Query States And Error Mapping

| State | Trigger | Contract behavior | UI behavior |
|---|---|---|---|
| Loading | Query pending. | Frontend local state or mock `pageState.kind = loading`. | Show header context if known, skeleton overview/list. |
| Empty | Snapshot loaded, no records for scope. | `records = []`, `overview.verdict = not_available`, `pageState.kind = empty`. | Explain no audit records; do not imply passed. |
| Partial | Some facts missing or still generating. | `overview.completeness = partial`, record flags mark partial. | Show available records plus missing reason. |
| Running | Execution/audit still producing records. | `overview.completeness = running`. | Keep current filter/selection while refreshing. |
| Hidden evidence | Evidence exists but is hidden/redacted. | `hiddenEvidenceCount > 0`, record/evidence `hidden = true`, disclosure reason if permitted. | Show hidden indicator, avoid raw payload. |
| Permission denied | User cannot view audit/evidence. | Query error `permission_denied` or snapshot `pageState.kind = permission_denied`. | Keep return path; show reason. |
| Error | Query/projection failure. | `QueryResponse.error` or snapshot `pageState.kind = error` for mock. | Retry and return to Main Page; never mutate task state. |
| Stale | Event cursor/snapshot stale. | `audit.snapshot_stale` event or `pageState.kind = stale`. | Refetch snapshot and disable evidence actions while stale. |

## 13. Runtime Audit Event And Refetch Contract

Detailed design lives in
[Audit Page Runtime Event And Refetch Technical Design](../plans/ui/audit-page-runtime-event-refetch-technical-design.md).
This section is the implementation contract summary.

Audit Page consumes the session SSE stream:

```text
GET /api/v1/sessions/{sessionId}/events?cursor={cursor}
```

Events are invalidation hints. They must not carry full Audit ViewModels, raw
payloads, or sanitized payload content. Frontend must refetch the canonical
Audit Page query APIs.

Canonical audit event types:

```ts
type AuditUiEventType =
  | "audit.summary_updated"
  | "audit.records_changed"
  | "audit.record_updated"
  | "audit.evidence_hidden"
  | "audit.snapshot_stale";
```

| Event | Meaning | Required payload | Frontend behavior |
|---|---|---|---|
| `audit.summary_updated` | Overview, verdict, count, or severity summary changed. | optional `severity`, optional `scope`, optional `reason`. | Refetch current AuditPageSnapshot. |
| `audit.records_changed` | Records were added/removed for a scope. | `scope`, `record_ids`, `reason`. | Refetch current AuditPageSnapshot or records for current filter. |
| `audit.record_updated` | A record detail, verdict, disclosure, or severity changed. | `record_id`, `scope`, optional `kind`, `verdict`. | If selected, refetch detail; otherwise patch/refetch list. |
| `audit.evidence_hidden` | Evidence was hidden/redacted after policy evaluation. | `record_id`, `evidence_ids`, `reason_code`. | Refetch detail; show hidden evidence indicator. |
| `audit.snapshot_stale` | Current audit snapshot cannot be trusted without refetch. | `scope`, `reason`, optional `last_good_cursor`. | Enter stale/resync and reload snapshot. |

Current Python builders use snake_case inside the free-form `payload` dictionary
(`record_ids`, `evidence_ids`, `last_good_cursor`). Frontend should support
these keys directly or normalize them at the Audit Page event-router boundary.

Event payloads should include enough scope to know whether the current Audit
Page is affected. If payload is incomplete but the session matches, frontend
must refetch rather than reconstruct evidence from raw events.

First implementation should add:

1. Audit Page route/controller event subscription.
2. Scope-aware event routing.
3. Snapshot/detail/evidence refetch behavior.
4. Non-blocking stale/disconnected UI feedback.
5. Backend workspace event source/emission points as a separate slice.

## 14. Mock Scenarios A1-A14

Mocks were created before UI implementation. They produce complete
`AuditPageSnapshot` fixtures with stable ids and expected route/query through
`frontend/src/pages/audit-page/mockAuditScenarios.ts` and
`frontend/src/pages/audit-page/mockAuditApi.ts`.

| Scenario | Current fixture id | Route/scope | Expected state |
|---|---|---|---|
| A1 Empty audit | `a1-audit-empty` | Task audit route | `pageState.empty`, verdict `not_available`, no records. |
| A2 Loading | `a2-audit-loading` | Task audit route | `pageState.loading`, running completeness, disabled evidence actions. |
| A3 Records ready | `a3-records-ready` | Task audit route | `pageState.ready`, records visible, verdict `passed`. |
| A4 Record selected | `a4-record-selected` | Task audit route plus selected record | Detail visible with evidence summary. |
| A5 Partial evidence | `a5-partial-evidence` | Task audit route | `pageState.partial`, verdict `inconclusive`, missing evidence called out. |
| A6 Hidden evidence | `a6-hidden-evidence` | Task audit route | Hidden evidence indicator and sanitized disclosure only. |
| A7 Warning verdict | `a7-warning-verdict` | Task audit route | Verdict `warning`, non-blocking concern visible. |
| A8 Failed verdict | `a8-failed-verdict` | Task audit route | Verdict `failed`, failure evidence visible. |
| A9 Inconclusive verdict | `a9-inconclusive-verdict` | Task audit route | Verdict `inconclusive`, unavailable confidence explained. |
| A10 Not available | `a10-not-available` | Task audit route | `pageState.empty`/not available; no pass implied. |
| A11 Permission denied | `a11-permission-denied` | Task audit route | Permission-denied state, return path preserved. |
| A12 Stale snapshot | `a12-stale-snapshot` | Task audit route | Stale state and refresh recovery behavior. |
| A13 Query error | `a13-query-error` | Task audit route | Query error and retry/recovery behavior. |
| A14 Evidence load error | `a14-evidence-load-error` | Task audit route plus evidence detail | Evidence detail query failure is handled separately from snapshot load. |

## 15. Backend Implementation Status

Additive contract models are complete. Gateway, route, and aggregation work
remains.

| File | Status | Later change |
|---|---|---|
| `src/taskweavn/server/ui_contract/view_models.py` | Done | Keep additive models stable; `AuditRecordsResult` now backs list-records responses. |
| `src/taskweavn/server/ui_contract/snapshots.py` | Done | `AuditPageSnapshot` exists and is populated by the first projection-backed gateway. |
| `src/taskweavn/server/ui_contract/events.py` | Done | Builders exist; AgentLoop, config manifest, log archive, and confirmation source emissions now use `audit.records_changed`. |
| `src/taskweavn/server/ui_contract/gateways.py` | Done first pass | `UiQueryGateway` and `DefaultUiQueryGateway` expose snapshot, records, detail, and evidence queries from Task projection facts. |
| `src/taskweavn/server/ui_http.py` | Done first pass | Session/task audit snapshot, records, record detail, and evidence detail routes are mounted. |
| `src/taskweavn/server/ui_contract/mapping.py` | Pending | Add shared mappers from timeline/audit agent/config/log facts to audit records if the gateway logic grows. |
| `src/taskweavn/task/timeline.py` | Pending | Use or extend timeline entries as source facts for audit records. |
| `src/taskweavn/audit/agent.py` | Pending | Map `pass/fail/inconclusive` to product verdict and expose concerns safely. |
| `src/taskweavn/observability/*` | Pending | Later source for related logs and sanitized log evidence. |
| `src/taskweavn/configuration` or future config store | Pending | Later source for effective config and config change records. |

## 16. Frontend Implementation Status And Remaining Touchpoints

The frontend mock-backed Audit Page baseline exists. The remaining frontend
work is end-to-end runtime validation, mobile-specific polish, and later
diagnostics/log handoff.

| File | Current status | Later change |
|---|---|---|
| `frontend/src/shared/api/types.ts` | Done | Keep Audit Page contract types aligned with backend model changes. |
| `frontend/src/shared/api/platoApi.ts` | Done | Keep HTTP audit routes aligned once backend routes exist. |
| `frontend/src/shared/api/platoApi.test.ts` | Done | Extend once new query params or error cases are added. |
| `frontend/src/app/routes.ts` | Done | Route builders are used by Main Page and Audit Page routing. |
| `frontend/src/app/platoRuntime.ts` | Done | Already creates mock or HTTP audit APIs; reuse for page wiring. |
| `frontend/src/entities/audit/model.ts` | Done | Add page-level selectors only when the UI needs them. |
| `frontend/src/shared/api/apiUiMapping.ts` | Done | Boundary mapping is exercised by the Audit Page shell. |
| `frontend/src/pages/audit-page/mockAuditScenarios.ts` | Done | Keep A1-A14 scenarios as the UI acceptance fixture set. |
| `frontend/src/pages/audit-page/mockAuditApi.ts` | Done | Use as the first Audit Page implementation adapter. |
| `frontend/src/pages/audit-page/*` UI components | Done | Mock-backed AP-005A-G route/shell/overview/filter/timeline/detail/boundary/polish is reviewable. Keep mock parity while adding backend integration. |
| `frontend/src/app/App.tsx` | Done | Keep Audit Page route matching aligned with route helpers. |
| `frontend/src/app/App.test.tsx` | Done | Reserved-entry assertion replaced after navigation was enabled. |
| `frontend/src/pages/main-page/*` | Done | Main Page `View audit` routes to session/task audit when the route is available; explicit fallback can still disable it. |
| `frontend/src/pages/audit-page/*` runtime hook/router | Done first pass | AP-013B implements Audit Page event-to-refetch behavior with mocked `subscribeSessionEvents`; AP-013C adds non-blocking live refresh/stale/disconnected status UI. |
| `frontend/src/pages/main-page/runtime/eventRouter.ts` | Reference only | Main Page event routing exists; Audit Page should use a scoped audit-specific router rather than making Main Page own trust-plane refresh. |

## 17. Open Product Questions

1. Should first implementation support only Task and Session audit, or include
   workflow scope as read-only preview?
2. Should `warning` be derived from any concern, only non-blocking risks, or a
   stricter product rule?
3. Who can view hidden evidence reasons: all users, technical users, or only
   debug/diagnostics users?
4. Should runtime Audit Page refetch continue to listen to coarse non-audit
   events (`message.appended`, `file_changes.updated`,
   `confirmation.resolved`) after AP-013F added audit-specific emissions for
   the covered source set?
5. How long are audit records retained for local sidecar sessions?
6. Should file paths be shown as workspace-relative by default, and when should
   absolute paths be redacted?
7. Should Audit Page preserve the last selected filter/record per session?
8. How should old sessions without complete timeline data be labeled:
   `partial`, `not_available`, or compatibility mode?
9. Should config records show only effective config or also user-visible config
   diffs in first release?
10. What permission model governs workflow-wide audit across sessions?

## 18. Acceptance Criteria

- `AuditPageSnapshot` is defined with scope, entry context, return target,
  overview, filters, records, selected detail, config/log links, permissions,
  page state, cursor, and timestamp.
- `AuditRecord` is defined with kind, filter, actor, summary, severity,
  confidence, verdict, completeness, references, evidence refs, and disclosure
  flags.
- Public audit verdicts are exactly `passed`, `warning`, `failed`,
  `inconclusive`, and `not_available`.
- Audit scopes cover session, workflow, task, action, confirmation, file,
  result, config, and log/evidence.
- Route entry contexts cover session, task, confirmation, result, and file
  change entries.
- Endpoint candidates cover snapshot, list records, record detail, and evidence;
  the first projection-backed backend routes are implemented.
- Loading, empty, partial, hidden evidence, permission denied, error, and stale
  states are defined.
- Audit event candidates are defined without requiring frontend reconstruction
  of raw evidence.
- A1-A14 mock scenarios are defined and remain parity fixtures for backend
  integration and future UI regression.

## 19. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Plan the next Audit Page hardening slice after AP-010/AP-011.

Context:
docs/engineering/audit-page-contract.md defines the Audit Page contract. The
mock-backed frontend route, Main Page audit entry, A1-A14 scenarios, read-only
UI shell, projection-backed backend audit routes, query gateway, workspace UI
event replay, and first AgentLoop/config/log/confirmation runtime emissions
are now in place. The next gap is richer timeline/source orchestration and
release-readiness validation.

Do not rewrite the Audit Page frontend contract unless the gap is documented
first.
Do not rewrite MainPage.
Do not expose raw payloads.
Do not bypass `AuditPageSnapshot` by returning raw EventStream, MessageStream,
SQLite, or log rows directly to the frontend.

Required work:
1. Read docs/engineering/audit-page-contract.md and
   docs/product/plato-audit-page-ux-flow.md.
2. Choose the next hardening target: timeline ordering, AuditAgent verdicts,
   end-to-end runtime validation, or richer config/log detail.
3. Extend the existing projection-backed gateway without changing the frontend
   contract unless a gap is documented first.
4. Preserve explicit partial/not_available/hidden/error/stale states when a
   source fact is missing or permission-limited.
5. Keep A1-A14 mock scenarios as frontend parity fixtures.
6. Add backend and frontend HTTP-mode regression tests for the chosen source.

Output:
- files changed
- gateway/routes/mappers added
- real data sources used
- tests run
- remaining audit event/refetch/mobile/diagnostics gaps
```
