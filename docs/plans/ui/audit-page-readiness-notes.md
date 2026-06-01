# Audit Page AP-005 Readiness Notes

> Status: ready for review
> Last Updated: 2026-06-01
> Scope: AP-005 mock-backed Audit Page frontend baseline, AP-010/AP-011
> projection-backed backend query path, AP-012 sanitized payload disclosure
> first pass, AP-013A-D runtime event/refetch baseline, and remaining
> backend handoff.
> Related:
> [Audit Page Implementation Plan](audit-page-project-implementation-plan.md),
> [Audit Page Frontend Technical Design](audit-page-frontend-technical-design.md),
> [Audit Page Sanitized Payload Disclosure Technical Design](audit-page-sanitized-payload-disclosure-technical-design.md),
> [Audit Page Runtime Event And Refetch Technical Design](audit-page-runtime-event-refetch-technical-design.md),
> [Audit Page Contract](../../engineering/audit-page-contract.md)

---

## 1. Current Baseline

AP-005 is ready for review as a mock-backed frontend baseline.

Completed slices:

| Slice | Status | Result |
|---|---|---|
| AP-005A | Done | Audit Page session/task route controller is mounted. |
| AP-005B | Done | Layout shell exists with overview, filter rail, timeline, and detail panel regions. |
| AP-005C | Done | Overview/filter/timeline walkthrough is usable with filter state and record ordering assertions. |
| AP-005D | Done | Selected record detail supports fallback query, close/back-to-list, and disclosure rendering. |
| AP-005E | Done | Boundary states cover A1-A14 mock scenarios. |
| AP-005F | Done | Main Page `View audit` routes to Audit Page when a valid audit link exists. |
| AP-005G | Done | Visual/accessibility polish pass added focus handling, live regions, focus-visible states, and desktop/tablet smoke. |
| AP-005H | Done | Contract/plan/gap facts synchronized and backend handoff made explicit. |

The first baseline was mock-backed. AP-010/AP-011 now adds a projection-backed
real HTTP query path plus first source hardening for EventStream, session log
archive, and logging manifest records. Timeline orchestration, runtime audit
events, and broader disclosure source coverage are still future work.
Sanitized payload disclosure now has a first request-time implementation path,
and AP-013A-D define and implement the event-to-refetch baseline with
mocked runtime subscriptions plus live refresh/stale/disconnected feedback.

---

## 2. Validation Evidence

Most recent AP-005G frontend validation:

```text
npm run test -- AuditPageRoute
npm run lint
npm run build
npm run test
```

Result:

```text
AuditPageRoute: 30 tests passed
Full frontend suite: 28 files, 192 tests passed
Production build: passed
Lint: passed
```

Browser smoke:

| Viewport | Route | Result |
|---|---|---|
| `1440x1024` | `/sessions/session-website-plan/tasks/task-implementation/audit?filter=confirmations&recordId=record-confirmation-1` | Desktop detail-open layout readable; detail panel receives focus without page scroll. |
| `1024x768` | `/sessions/session-website-plan/audit?entry=from_session&returnFocus=session&returnSessionId=session-website-plan` | Tablet stacked layout remains reachable; no browser console errors. |

---

## 3. Review Scope

The first review should focus on:

1. Whether users understand Audit Page as a read-only trust plane.
2. Whether Session and Task scope are visible enough.
3. Whether records, filters, verdicts, and disclosure notes answer "what
   happened" and "why it matters".
4. Whether Main Page entry and return behavior feel coherent.
5. Whether the page gives enough confidence without becoming a raw log console.

Do not use this review to judge real backend evidence completeness. That is the
next phase.

---

## 4. Remaining Gaps

| Gap | Status | Notes |
|---|---|---|
| Backend audit query gateway | First projection-backed path implemented | `DefaultUiQueryGateway` can now produce Audit Page snapshot, records, record detail, and evidence detail from Task projection facts. |
| HTTP audit routes | First path implemented | `ui_http.py` now exposes the frontend API methods for snapshot, records, record detail, and evidence detail. |
| Real data aggregation | Partial | Current source is Task projection plus message/confirmation/file/result facts, EventStream action/observation/AuditObservation records, and session log/config references when present. Timeline orchestration and runtime audit events remain pending. |
| Runtime audit events/refetch | Replay source implemented | Existing event builders are additive, [AP-013A runtime event/refetch design](audit-page-runtime-event-refetch-technical-design.md) defines event scope, cursor, stale/resync, and frontend invalidation rules, AP-013B wires the Audit Page frontend event router/hook with mock subscription tests, AP-013C adds non-blocking live refresh/stale/disconnected UI feedback, and AP-013D adds workspace-backed `SqliteUiEventSource` cursor replay. No runtime emission point appends audit-specific events yet. |
| Sanitized payload disclosure | First pass implemented | Contract keeps default hidden/sanitized behavior. AP-012C-E cover contract tests, request-time backend generation/injection, and frontend detail/evidence rendering; sanitized payload is not stored. |
| Mobile-specific layout below 960px | Deferred | Page remains reachable with scrolling; product-grade mobile UX is later polish. |
| User testing | Ready to prepare | At least one real backend path exists; user testing still needs a chosen scenario and runbook. |

---

## 5. Backend Handoff

Completed backend integration slice:

```text
AP-010/AP-011: backend audit query gateway + real HTTP mode integration
AP-012A: backend source hardening for EventStream/log/config references
AP-012B: sanitized payload disclosure technical design
AP-012C-E: sanitized payload contract tests, backend request-time generation,
and frontend detail/evidence rendering
AP-013A: runtime audit event/refetch technical design
AP-013B: frontend Audit Page event router/hook with mocked event-to-refetch tests
AP-013C: frontend live refresh/stale/disconnected status feedback
AP-013D: workspace-backed UI event source/replay store with cursor resync
```

Implemented first pass:

1. Added session/task audit snapshot query path.
2. Added list-records, record-detail, and evidence-detail routes.
3. Maps user-readable audit facts from `TaskProjectionService` plus projected
   messages, confirmations, file changes, and task results.
4. Maps durable `events.sqlite` actions, observations, and `AuditObservation`
   records into productized Audit Page records when available.
5. Maps session log archive files and logging manifests into `log_evidence`
   and `config_change` records when available.
6. Preserves `partial`, `empty/not_available`, and structured query error
   behavior explicitly.
7. Keeps mock scenarios A1-A14 as parity fixtures for frontend regression.

Remaining backend work:

1. Add `TaskInteractionTimelineService` as a richer ordering/evidence source.
2. Add runtime audit event emission from the first source change points.
3. Extend sanitized payload source coverage as EventStream/log/config evidence
   detail sources become richer.
4. Decide whether user testing or deeper backend aggregation should happen next.

The backend should return `AuditPageSnapshot` and related contract objects. It
must not ask the frontend to reconstruct audit records from raw EventStream,
MessageStream, SQLite rows, or log payloads.
