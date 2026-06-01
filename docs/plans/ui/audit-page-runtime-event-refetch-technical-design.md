# Audit Page Runtime Event And Refetch Technical Design

> Status: draft technical design
> Last Updated: 2026-06-01
> Scope: Audit Page runtime audit event contract, event source responsibilities,
> frontend invalidation/refetch behavior, and implementation slices.
> Related:
> [Audit Page Contract](../../engineering/audit-page-contract.md),
> [Audit Page Implementation Plan](audit-page-project-implementation-plan.md),
> [Audit Page Readiness Notes](audit-page-readiness-notes.md),
> [Plato Frontend Technical Design](../../product/plato-frontend-technical-design.md)

---

## 1. Problem

Audit Page already has:

- projection-backed snapshot, records, record detail, and evidence detail APIs;
- frontend route/detail rendering in mock and HTTP mode;
- sanitized payload disclosure on explicit detail/evidence requests;
- `UiEvent` contract types for audit events;
- a generic session SSE endpoint.

The missing piece is runtime freshness.

Today a user can open Audit Page while execution, confirmations, logs, config,
or audit records are still changing. Without runtime event/refetch behavior the
page can become stale until a manual reload. That is especially risky for a
trust plane: stale audit facts can make the system look more certain, more
complete, or safer than it is.

This design defines a conservative first pass:

```text
runtime/source changes
  -> emit additive UiEvent
  -> frontend treats event as invalidation hint
  -> Audit Page refetches the smallest safe query
  -> page keeps filter/selection when still valid
```

Events do not carry complete Audit ViewModels. Backend APIs remain canonical.

---

## 2. Goals

1. Define which runtime events affect Audit Page.
2. Define event payload shape and scope matching rules.
3. Define frontend refetch behavior for snapshot, record detail, and evidence
   detail.
4. Define backend event-source responsibilities without forcing a large event
   store rewrite in this slice.
5. Preserve A1-A14 mock fixtures as parity tests.
6. Keep sanitized payload disclosure request-driven; do not persist or stream
   sanitized payloads.
7. Make stale/resync behavior explicit and user-safe.

---

## 3. Non-goals

This slice does not implement:

- WebSocket or bidirectional realtime transport.
- Complete audit timeline orchestration.
- Durable audit-specific storage.
- Raw payload streaming.
- Event payload patching of UI ViewModels.
- Multi-user permission or collaborative audit sync.
- Product-grade mobile layout changes.

---

## 4. Current Code Facts

| Area | Current fact | Design implication |
|---|---|---|
| Backend event model | `src/taskweavn/server/ui_contract/events.py` includes `audit.summary_updated`, `audit.records_changed`, `audit.record_updated`, `audit.evidence_hidden`, and `audit.snapshot_stale`. | Keep the event set additive; refine payload and routing rules before runtime emission. |
| Backend event source | `src/taskweavn/server/ui_events.py` has `UiEventSource`, `StaticUiEventSource`, and `ResyncOnlyEventSource`. | The transport seam exists, but a live workspace source is still missing. |
| HTTP/SSE route | `src/taskweavn/server/ui_http.py` exposes `/api/v1/sessions/{sessionId}/events`. | Audit Page should reuse the session event stream rather than introduce a separate audit endpoint. |
| Frontend API client | `frontend/src/shared/api/platoApi.ts` subscribes to all canonical named `UiEventType` values. | No new low-level API client is required for audit events. |
| Main Page runtime | Main Page already uses `subscribeSessionEvents` to refetch snapshot facts. | Audit Page can reuse the same invalidation pattern with Audit-specific scope routing. |
| Runtime reducer | `frontend/src/shared/runtime/runtimeReducer.ts` already recognizes audit events as `query_audit_snapshot` effects. | The shared reducer intent is ahead of Audit Page route wiring; use it as a reference, not as a mandatory dependency. |
| Audit Page route | `frontend/src/pages/audit-page/AuditPageRoute.tsx` fetches snapshot/detail/evidence but does not subscribe to events. | First implementation work belongs here or in an Audit-specific controller hook. |

---

## 5. Design Principles

1. **Events are invalidation hints, not state.** Frontend must refetch contract
   APIs instead of reconstructing records from event payloads.
2. **Scope before refetch.** Ignore events for other sessions/tasks when the
   payload has enough scope to decide safely.
3. **Refetch conservatively when uncertain.** If an audit event is malformed or
   underspecified but belongs to the current session, refetch the snapshot.
4. **Keep user context.** Current filter, selected record, and scroll/focus
   should survive a refetch if the selected record still exists.
5. **Sanitized payload remains pull-based.** Audit events may say evidence
   changed or hidden, but they must not carry sanitized payload content.
6. **Resync beats patch.** Cursor gaps, stale snapshots, and unsupported event
   versions should force a snapshot refetch/resync state.
7. **No UI mutation from Audit Page.** Runtime refresh cannot become a hidden
   command channel.

---

## 6. Event Contract

### 6.1 Event Types

Audit Page should consume these canonical session events:

| Event type | Meaning | Primary refetch target |
|---|---|---|
| `audit.summary_updated` | Overview/verdict/count summary changed. | Snapshot |
| `audit.records_changed` | Records were added, removed, or reordered for a scope. | Snapshot or records list |
| `audit.record_updated` | One record's detail, verdict, disclosure, or severity changed. | Selected detail if selected; otherwise snapshot/list |
| `audit.evidence_hidden` | Evidence visibility/redaction changed. | Selected detail/evidence if affected; otherwise snapshot/list |
| `audit.snapshot_stale` | Current snapshot cannot be trusted without a full refresh. | Snapshot with stale/resync state |
| `session.resync_required` | Generic session event replay is not reliable. | Snapshot with resync state |

Main Page events such as `message.appended`, `confirmation.resolved`,
`file_changes.updated`, and `result.updated` may indirectly affect Audit Page.
First implementation can either:

1. ignore them on Audit Page and rely on backend audit events; or
2. treat them as coarse snapshot invalidation when the current Audit Page scope
   matches the session/task.

Preferred first pass: use option 2 only if backend audit event emission is not
yet complete. Once backend emits audit-specific events reliably, Audit Page
should prefer audit events for better refetch control.

### 6.2 Payload Shape

`UiEvent` top-level fields are serialized with camelCase by `UiContractModel`.
The free-form `payload` dictionary currently preserves backend-provided keys.
Current backend audit event builders use snake_case payload keys such as
`record_ids`, `evidence_ids`, and `last_good_cursor`.

First implementation should support the current payload keys and avoid adding a
second naming convention in the UI. If a later API cleanup wants camelCase
inside `payload`, it should add a normalizer and keep backward compatibility.

Recommended payload fields:

| Event | Payload fields |
|---|---|
| `audit.summary_updated` | `severity?`, `scope?`, `reason?` |
| `audit.records_changed` | `scope`, `record_ids`, `reason?` |
| `audit.record_updated` | `record_id`, `scope?`, `kind?`, `verdict?` |
| `audit.evidence_hidden` | `record_id`, `evidence_ids`, `reason_code` |
| `audit.snapshot_stale` | `scope`, `reason`, `last_good_cursor?` |

`scope` should be a JSON-safe object projected from `AuditScope`:

```json
{
  "kind": "task",
  "sessionId": "session-website-plan",
  "taskNodeId": "task-implementation"
}
```

For compatibility with existing backend payloads, scope readers should accept
either `sessionId` / `taskNodeId` or `session_id` / `task_node_id`.

### 6.3 Cursor Rules

The event `cursor` is the SSE replay cursor, not a snapshot version by itself.

Frontend rules:

1. Subscribe with the current `AuditPageSnapshot.cursor`.
2. Remember the last seen event cursor to skip duplicate browser/EventSource
   deliveries.
3. After a successful snapshot refetch, treat the new snapshot cursor as
   canonical and resubscribe from that cursor.
4. If backend emits `session.resync_required` or `audit.snapshot_stale`, do not
   rely on incremental events; perform a full snapshot refetch.

---

## 7. Frontend Refetch Strategy

### 7.1 Route-Level State

Audit Page route currently owns:

- parsed route scope;
- active filter;
- selected record id;
- snapshot query;
- optional selected record detail query;
- optional selected evidence detail query.

Runtime refetch should be added either directly to `AuditPageRoute` or as a
small hook:

```ts
useAuditPageRuntimeEvents({
  api,
  snapshot,
  activeFilter,
  selectedRecordId,
  selectedEvidenceRef,
  refetchSnapshot,
  refetchDetail,
  refetchEvidence,
});
```

Do not put event parsing inside presentational components.

### 7.2 Event-To-Refetch Table

| Event | If current scope matches | Refetch behavior |
|---|---|---|
| `audit.summary_updated` | yes or unknown | Refetch snapshot. |
| `audit.records_changed` | yes or unknown | Refetch snapshot; preserve selected record if still present and still matches filter. |
| `audit.record_updated` | `record_id === selectedRecordId` | Refetch record detail with `includeEvidence=true` and `includeSanitizedPayload=true`; then refetch evidence detail if selected evidence still exists. |
| `audit.record_updated` | different record | Refetch snapshot/list only. |
| `audit.evidence_hidden` | selected record or selected evidence affected | Refetch record detail and evidence detail. |
| `audit.evidence_hidden` | different record | Refetch snapshot/list only. |
| `audit.snapshot_stale` | yes or unknown | Mark route as resyncing/stale; refetch snapshot; clear stale state on success. |
| `session.resync_required` | same session | Same as `audit.snapshot_stale`. |
| non-audit event | same task/session and backend audit events not reliable yet | Coarse snapshot refetch, preferably debounced. |

### 7.3 Debounce And Concurrency

Runtime can emit several events for one user-visible change. The UI should
coalesce them:

- debounce window: 100-250 ms;
- one in-flight snapshot refetch per Audit Page route;
- detail/evidence refetch should not start until the matching record id is
  known after snapshot projection;
- if both snapshot and detail are invalidated, snapshot wins first.

React Query can provide most de-duplication, but the route should still avoid
starting detail/evidence requests when selected ids are already stale.

### 7.4 UI Boundary Behavior

Audit Page should add lightweight live-state feedback:

| State | UI behavior |
|---|---|
| connected | No extra banner. |
| refreshing | Optional subtle "Updating audit evidence" text; do not block reading. |
| resyncing/stale | Show recoverable banner; disable detail expansion only if selected record disappeared. |
| disconnected | Show non-blocking "Live audit updates unavailable" note; manual refresh remains possible. |

Do not replace the current page with a loading boundary for ordinary event
refetch. Trust pages should remain readable while refreshing.

---

## 8. Backend Emission Strategy

### 8.1 First Implementation Source

The first runtime source should emit audit events when a productized Audit Page
source changes, not whenever a low-level row changes.

Candidate emission points:

| Source change | Event |
|---|---|
| Agent loop appends Action / Observation EventStream facts | `audit.records_changed` for affected session/task scope |
| `AuditObservation` appended or verdict changes | `audit.summary_updated` and `audit.record_updated` |
| File change summary updates | `audit.records_changed` or coarse `file_changes.updated` until audit-specific emission exists |
| Confirmation created/resolved | `audit.records_changed` or existing confirmation event as coarse invalidation |
| Session log archive file added | `audit.records_changed` with `reason=log_archive_updated` |
| Logging manifest/config changes | `audit.records_changed` with `reason=config_manifest_updated` |
| Sanitizer policy starts hiding evidence previously visible | `audit.evidence_hidden` |
| Event cursor gap / projection inconsistency | `audit.snapshot_stale` |

Do not emit `audit.evidence_hidden` on every detail query just because a
payload is hidden by default. It should represent a change in visibility,
policy, source classification, or projection trust.

### 8.2 Event Source Implementation Options

| Option | Description | Fit |
|---|---|---|
| Keep `ResyncOnlyEventSource` | Always asks frontend to refetch. | Current fallback only; too noisy for Audit Page. |
| `StaticUiEventSource` | Deterministic tests. | Keep for tests and smoke. |
| Workspace-backed append-only UI event store | Persist `UiEvent` rows per session with cursor. | Preferred first durable implementation. |
| Derived EventStream polling source | Convert EventStream rows to UI events on subscribe. | Useful bridge, but cursor semantics are harder. |

Preferred implementation path:

```text
UiEventStore / WorkspaceUiEventSource
  append(UiEvent)
  subscribe(sessionId, cursor)
  replay after cursor
```

This is smaller than a full audit storage rewrite and aligns with the existing
SSE transport seam.

---

## 9. API And Contract Impact

No new HTTP endpoint is required.

Existing endpoint:

```text
GET /api/v1/sessions/{sessionId}/events?cursor={cursor}
```

Existing Audit Page query endpoints remain canonical:

```text
GET /api/v1/sessions/{sessionId}/audit
GET /api/v1/sessions/{sessionId}/audit/records
GET /api/v1/sessions/{sessionId}/audit/records/{recordId}
GET /api/v1/sessions/{sessionId}/audit/evidence/{evidenceId}
```

Frontend should keep using `includeSanitizedPayload=true` only for explicit
record/evidence detail refetch. Snapshot/list refetch must remain summary-only.

---

## 10. Testing Plan

### 10.1 Backend Contract Tests

Add or keep tests for:

- audit event builders serialize stable event types;
- payload includes scope/record/evidence fields;
- event source replays after cursor;
- unknown cursor returns `session.resync_required`;
- source emission does not include raw/sanitized payload content.

### 10.2 Frontend Unit Tests

Add Audit Page route/controller tests:

1. `audit.records_changed` refetches the snapshot.
2. `audit.record_updated` for selected record refetches detail.
3. `audit.record_updated` for a different record keeps detail stable and
   refetches snapshot/list.
4. `audit.evidence_hidden` for selected evidence refetches evidence detail.
5. Scope mismatch is ignored.
6. Missing scope falls back to snapshot refetch.
7. `audit.snapshot_stale` shows stale/resync feedback and refetches snapshot.
8. Event subscription failure shows non-blocking live-update unavailable state.
9. Duplicate event cursor does not trigger duplicate refetch.

### 10.3 Integration / Browser Smoke

Smoke route:

```text
/sessions/session-website-plan/tasks/task-implementation/audit?filter=confirmations&recordId=record-confirmation-1
```

Checks:

- page remains readable while event refresh is pending;
- selected record survives refetch when still present;
- selected detail closes or shows a clear stale state when record disappears;
- sanitized payload detail is still requested only on detail/evidence queries.

---

## 11. Implementation Slices

| Slice | Scope | Acceptance |
|---|---|---|
| AP-013A | This design document and contract/plan status sync. | Docs describe event/refetch contract and implementation path. |
| AP-013B | Add frontend Audit Page event router/hook with mocked `subscribeSessionEvents`. | Unit tests prove event-to-refetch behavior without backend emission. |
| AP-013C | Add UI live refresh/stale/disconnected feedback. | Audit Page remains readable; stale state is explicit. |
| AP-013D | Add workspace-backed UI event store/source or equivalent first live source. | SSE can replay audit events after cursor; unknown cursor emits resync. |
| AP-013E | Emit audit events from the first runtime/source change points. | EventStream/log/config/confirmation changes trigger appropriate invalidations. |
| AP-013F | End-to-end smoke and docs/readiness closure. | A1-A14 fixtures still pass; one HTTP mode audit page updates after a runtime event. |

---

## 12. Open Questions

1. Should coarse non-audit events invalidate Audit Page in Product 1.0, or
   should Audit Page wait for audit-specific events only?
2. Should event cursor be shared with `MainPageSnapshot.cursor`, or should Audit
   Page snapshot expose a separate `auditCursor` later?
3. Should `audit.records_changed` include filter hints such as `filterKinds`, or
   should the frontend always refetch the current snapshot/list?
4. Should stale/resync state be represented in `AuditPageSnapshot.pageState`,
   local route state, or both?

Recommended first-pass answers:

1. Use coarse non-audit events as fallback invalidation until audit-specific
   backend emission is complete.
2. Keep one session cursor for now; introduce `auditCursor` only if event volume
   or replay semantics diverge.
3. Do not add filter hints yet; snapshot/list refetch is safer.
4. Use local route state for live transport issues and backend `pageState` for
   query/projection issues.

