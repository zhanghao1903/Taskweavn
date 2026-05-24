# Audit Page Backend-To-Frontend Contract

> Status: proposed contract
> Last Updated: 2026-05-24
> Scope: Audit Page API, backend ViewModel, frontend ViewModel, events, mock scenarios.
> Non-goals: no Audit Page UI implementation, no high-fidelity CSS, no MainPage rewrite, no runtime migration in this task.

## 0. Implementation Checkpoint

As of 2026-05-24, the additive backend contract model layer is in place:

- `src/taskweavn/server/ui_contract/view_models.py` defines Audit Page
  ViewModels for scope, entry context, return target, overview, filters,
  records, record detail, evidence, config summary, related logs, permissions,
  and page states.
- `src/taskweavn/server/ui_contract/snapshots.py` defines `AuditPageSnapshot`.
- `src/taskweavn/server/ui_contract/events.py` defines additive event literals
  and builders for `audit.records_changed`, `audit.record_updated`,
  `audit.evidence_hidden`, and `audit.snapshot_stale`.
- `tests/test_audit_page_contract_models.py` covers focused validation for the
  new contract shape, public verdict values, record detail consistency, config
  scope anchoring, sanitized payload disclosure, and audit event payloads.

Still not implemented:

- HTTP audit routes.
- Audit query gateway.
- Real aggregation from timeline, audit agent, config, logs, or task
  projection.
- Frontend API types, routes, mock fixtures, or Audit Page UI.

## 1. Purpose

Audit Page is Plato's Trust Plane. It must let users inspect what happened,
why it matters, what evidence exists, what is incomplete, and how to return to
the Main Page context that started the audit.

The backend now has additive Audit Page transport models and audit event
builders, but the route/gateway/data-aggregation layer is still absent. The
frontend still needs matching TypeScript types, mock fixtures, route constants,
API client methods, and UI implementation.

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
| Backend snapshot | `src/taskweavn/server/ui_contract/snapshots.py` defines `MainPageSnapshot` and additive `AuditPageSnapshot`. | Snapshot model exists; no query gateway or HTTP handler populates it yet. |
| Backend ViewModels | Audit Page scope, overview, record, detail, evidence, config/log link, permission, and page-state models exist. | No real data aggregation/mapping into those models yet. |
| HTTP routes | `src/taskweavn/server/ui_http.py` exposes session snapshot, commands, events, and client logs. | No audit query endpoints. |
| Events | `src/taskweavn/server/ui_contract/events.py` includes `audit.summary_updated` plus record/evidence/stale audit event builders. | No runtime source emits those events yet. |
| Frontend API types | `frontend/src/shared/api/types.ts` has `AuditLinkView`. | No Audit Page types. |
| Frontend audit entity | `frontend/src/entities/audit/model.ts` has `AuditEntryLink`. | Link-only; no records or verdict. |
| Backend audit agent | `AuditAgent` emits `pass`, `fail`, `inconclusive`. | Product verdict needs `passed`, `warning`, `failed`, `inconclusive`, `not_available`. |

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
  source: "event_stream" | "message_stream" | "task_projection" | "audit_agent" | "config_store" | "log_archive" | "mock";
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

## 13. Audit Event Candidates

Additive event candidates for `src/taskweavn/server/ui_contract/events.py`:

```ts
type AuditUiEventType =
  | "audit.records_changed"
  | "audit.record_updated"
  | "audit.evidence_hidden"
  | "audit.snapshot_stale";
```

| Event | Meaning | Required payload | Frontend behavior |
|---|---|---|---|
| `audit.records_changed` | Records were added/removed for a scope. | `scope`, `recordIds`, `reason`. | Refetch current AuditPageSnapshot or records for current filter. |
| `audit.record_updated` | A record detail, verdict, disclosure, or severity changed. | `recordId`, `scope`, optional `kind`, `verdict`. | If selected, refetch detail; otherwise patch/refetch list. |
| `audit.evidence_hidden` | Evidence was hidden/redacted after policy evaluation. | `recordId`, `evidenceIds`, `reasonCode`. | Refetch detail; show hidden evidence indicator. |
| `audit.snapshot_stale` | Current audit snapshot cannot be trusted without refetch. | `scope`, `reason`, optional `lastGoodCursor`. | Enter stale/resync and reload snapshot. |

Event payloads should include enough scope to know whether the current Audit
Page is affected. If payload is incomplete, frontend must refetch rather than
reconstruct evidence from raw events.

## 14. Mock Scenarios A1-A10

Mocks should be created before UI implementation. They should produce complete
`AuditPageSnapshot` fixtures with stable ids and expected route/query.

| Scenario | Route/scope | Required data | Expected state |
|---|---|---|---|
| A1 Task Audit Default | `/sessions/s1/tasks/t1/audit` | Task scope, overview, mixed confirmation/action/file/result records, no selected record. | `pageState.ready`, verdict `warning` or `passed`, completeness `complete`. |
| A2 Record Selected | same plus `recordId=r-file-1` | Selected file/action/risk detail with evidence refs and return target. | Detail visible; timeline context preserved. |
| A3 Session Audit Overview | `/sessions/s1/audit` | Session scope, important records across multiple tasks, counts by filter. | Default selected important issue if any. |
| A4 Filtered Records | `/sessions/s1/audit?filter=confirmations` | Confirmation-only list, counts for all filters remain visible. | Filtered list; selected record cleared unless still valid. |
| A5 Empty Audit | `/sessions/s1/tasks/t-draft/audit` | No records, draft/not-executed explanation. | `verdict = not_available`, `pageState.empty`. |
| A6 Running Partial | `/sessions/s1/tasks/t-running/audit` | Running audit, partial records, hidden count maybe zero. | `completeness = running` or `partial`; no final pass. |
| A7 Failed To Load | any audit route | Query error fixture or snapshot mock error state. | Retry available; return target preserved. |
| A8 Inconclusive Verdict | task route | Audit verdict record with missing/insufficient evidence reason. | `verdict = inconclusive`; detail explains what is missing. |
| A9 Hidden Evidence / Permission Denied | task or record detail route | Hidden/redacted evidence refs and permission reason. | Hidden indicator; raw payload absent; no secret leakage. |
| A10 Config And Related Logs | session or task route | Config record, effective config summary, related logs link. | Config/logs are read-only links, not embedded diagnostics. |

## 15. Backend Implementation Status

Additive contract models are complete. Gateway, route, and aggregation work
remains.

| File | Status | Later change |
|---|---|
| `src/taskweavn/server/ui_contract/view_models.py` | Done | Keep additive models stable; only extend with compatibility care. |
| `src/taskweavn/server/ui_contract/snapshots.py` | Done | `AuditPageSnapshot` exists; next work should populate it through a gateway. |
| `src/taskweavn/server/ui_contract/events.py` | Done | Builders exist; next work should decide runtime emission points. |
| `src/taskweavn/server/ui_contract/gateways.py` | Pending | Add `UiAuditQueryGateway` or audit methods on query gateway. |
| `src/taskweavn/server/ui_http.py` | Pending | Add audit route matching and handlers. |
| `src/taskweavn/server/ui_contract/mapping.py` | Pending | Add mappers from timeline/projection/audit agent/config/log facts to audit records. |
| `src/taskweavn/task/timeline.py` | Pending | Use or extend timeline entries as source facts for audit records. |
| `src/taskweavn/audit/agent.py` | Pending | Map `pass/fail/inconclusive` to product verdict and expose concerns safely. |
| `src/taskweavn/observability/*` | Pending | Later source for related logs and sanitized log evidence. |
| `src/taskweavn/configuration` or future config store | Pending | Later source for effective config and config change records. |

## 16. Later Frontend Files To Update

Do not update these in this task. Proposed frontend implementation touchpoints:

| File | Later change |
|---|---|
| `frontend/src/shared/api/types.ts` | Add Audit Page contract types. |
| `frontend/src/shared/api/platoApi.ts` | Add audit snapshot, records, detail, and evidence query functions. |
| `frontend/src/app/routes.ts` | Add audit route constants. |
| `frontend/src/entities/audit/model.ts` | Replace link-only model with audit scope/record helpers. |
| `frontend/src/pages/audit-page/*` | Future Audit Page implementation. |
| `frontend/src/pages/main-page/MainPage.tsx` | Later route Audit CTA to real audit route when contract/API exists. |
| `frontend/src/pages/main-page/httpMainPageAdapter.ts` | Later include audit summary/link behavior after backend fields exist. |
| `frontend/src/pages/main-page/fixtures.ts` | Add A1-A10 audit mock snapshots or a dedicated audit fixture file. |
| `frontend/src/pages/main-page/runtime/eventRouter.ts` | Add audit event routing/refetch behavior if Audit Page shares runtime reducer. |
| `frontend/src/shared/api/platoApi.test.ts` | Add audit API parsing tests. |

## 17. Open Product Questions

1. Should first implementation support only Task and Session audit, or include
   workflow scope as read-only preview?
2. Should `warning` be derived from any concern, only non-blocking risks, or a
   stricter product rule?
3. Who can view hidden evidence reasons: all users, technical users, or only
   debug/diagnostics users?
4. Should sanitized raw payload ever be visible in Audit Page, or only in
   Diagnostics/Logs?
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
- Endpoint candidates cover snapshot, list records, record detail, and evidence.
- Loading, empty, partial, hidden evidence, permission denied, error, and stale
  states are defined.
- Audit event candidates are defined without requiring frontend reconstruction
  of raw evidence.
- A1-A10 mock scenarios are defined before UI implementation.

## 19. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Add a mock-backed Audit Page query gateway and HTTP route shell.

Context:
docs/engineering/audit-page-contract.md defines the Audit Page contract.
Additive backend models and audit event builders already exist. We now need a
mock-backed gateway/route shell so frontend mocks and API client work can begin
without real audit aggregation.

Do not implement Audit Page UI.
Do not add high-fidelity CSS.
Do not rewrite MainPage.
Do not expose raw payloads.
Do not implement real audit data aggregation yet.

Required work:
1. Read docs/engineering/audit-page-contract.md and
   docs/product/canonical-status-model.md.
2. Add a minimal `UiAuditQueryGateway` protocol or equivalent query methods.
3. Add mock-backed AuditPageSnapshot responses for task and session scopes.
4. Add HTTP route matching/handlers for:
   - `GET /api/v1/sessions/{sessionId}/audit`
   - `GET /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/audit`
5. Preserve standard `QueryResponse<AuditPageSnapshot>` envelopes.
6. Add focused route/gateway tests.
7. Do not aggregate real timeline/log/audit-agent facts yet.

Output:
- files changed
- routes/gateway methods added
- mock snapshot behavior
- tests run
- remaining route/gateway/frontend tasks
```
