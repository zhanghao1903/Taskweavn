# Technical Slice: Audit Entry Closure

> Status: implemented_backend
> Last Updated: 2026-06-05
> Parent Plan: [Result And Evidence Exposure Surface](result-exposure-surface.md)
> Related: [Audit Page Contract](../../engineering/audit-page-contract.md), [Product Error Handling](product-error-handling.md), [Diagnostic Bundle Export](diagnostic-bundle-export.md)

---

## 1. Goal

Close the Product 1.0 backend gap where Main Page can point to Audit Page, but
Audit records are not yet orchestrated from the task interaction timeline.

This slice makes backend Audit projection route-ready for completed and failed
Product 1.0 Tasks without changing the existing `AuditPageSnapshot`,
`AuditRecord`, `AuditRecordDetail`, or `EvidenceDetail` shapes.

---

## 2. Current Facts

- Audit routes already exist for snapshot, records, record detail, and evidence
  detail.
- Existing projection can emit task state, message, result, file, EventStream,
  config, and log records.
- `TaskInteractionTimelineService` already stitches task messages,
  confirmations, EventStream refs, file facts, result summaries, and draft
  publication lineage, but the Audit gateway does not use it as an orchestration
  source.
- Runtime `audit.records_changed` UI events already exist for AgentLoop,
  config/log manifest, and confirmation source changes.

---

## 3. Scope

Implement a narrow backend source-orchestration slice:

1. Add a workspace-backed timeline provider for Audit projection.
2. Add timeline-to-`AuditRecord` mapping for task messages, confirmations,
   file facts, result/error summaries, and draft publication/source entries.
3. Keep EventStream action/observation records mapped by the existing
   EventStream provider because it has typed payload access.
4. Inject the timeline provider into the Main Page sidecar query gateway.
5. Add focused backend tests for timeline-sourced Audit records and task-scope
   ordering.

---

## 4. Non-goals

- Do not change frontend UI.
- Do not add new Audit contract fields unless a contract gap is documented
  first.
- Do not expose raw EventStream, MessageStream, SQLite, or log payloads.
- Do not persist sanitized payload copies.
- Do not implement a full Audit timeline UI.
- Do not implement diagnostic bundle HTTP export.

---

## 5. Backend Design

### 5.1 Timeline Provider

Add a small workspace adapter that opens the session-scoped
`events.sqlite` only for the duration of a timeline read and delegates to
`DefaultTaskInteractionTimelineService`.

This avoids storing a single session-specific `SqliteEventStream` inside the
sidecar app, which can serve multiple sessions.

### 5.2 Audit Projection Mapping

When a timeline service is configured:

- task state records still come from the current task card projection;
- timeline entries produce message, confirmation, file, result, and system
  records;
- EventStream action/observation/AuditObservation records continue to come from
  `WorkspaceAuditEventProvider`;
- config/log records continue to come from their current providers;
- dedupe keeps stable record ids such as `record-message-*`,
  `record-file-*`, and `record-result-published-*`.

When no timeline service is configured, the existing projection-only path
remains the fallback.

### 5.3 Source Failure Behavior

Timeline provider failures become a partial `system` Audit record rather than
failing the whole Audit snapshot. This matches current EventStream/config/log
provider behavior.

---

## 6. Acceptance Criteria

- Task-scoped Audit snapshot can include timeline-sourced message,
  confirmation, file, result/error, and draft/publication records.
- Existing typed EventStream action/observation records still appear when
  source facts exist.
- Config and log records still appear when source facts exist.
- Missing timeline source produces explicit partial source-unavailable evidence.
- Record/detail/evidence endpoints continue using existing contract shapes.
- No raw prompts, provider payloads, SQLite rows, or log payloads are exposed by
  default.

---

## 7. Implementation Notes

- `WorkspaceTaskInteractionTimelineService` opens the requested session's
  `events.sqlite` only for the duration of a timeline read, then delegates to
  `DefaultTaskInteractionTimelineService`.
- `timeline_audit_records` maps timeline entries into existing `AuditRecord`
  shapes and keeps stable ids for `record-message-*`, `record-file-*`,
  `record-confirmation-*`, and `record-result-*`.
- `DefaultUiQueryGateway` accepts an optional timeline service; existing
  projection-only records remain the fallback and timeline records override the
  same facts by stable record id when available.
- Sidecar assembly wires the workspace timeline provider without changing HTTP
  route shape or frontend contract fields.

---

## 8. Tests

Backend tests for this slice:

- gateway test with an injected fake timeline proving task-scope record order
  and stable record ids: implemented in `tests/test_audit_entry_closure.py`;
- source-unavailable timeline test: implemented in
  `tests/test_audit_entry_closure.py`;
- workspace provider smoke proving the real provider can open the session event
  stream: implemented in `tests/test_audit_entry_closure.py`;
- existing Audit EventStream/config/log tests remain covered by
  `tests/test_ui_query_gateway.py`.

---

## 9. Remaining Follow-ups

- Frontend first-run and Audit Page integration validation.
- Broader product error refs once frontend consumes recovery actions.
- Diagnostic bundle Audit-specific refs after Audit evidence closure is
  validated in a real sidecar session.
