# Feature Plan: Diagnostic Bundle Export

> Status: accepted for Product 1.0 local unsigned RC
> Last Updated: 2026-06-07
> Gap: [Diagnostic bundle](../../gaps/README.md)
> Architecture: [Configurable Logging System](../../architecture/configurable-logging-system.md), [UI And Backend Communication](../../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../../architecture/task-domain-ui-model-separation.md)
> Product: [Plato Settings, Logs, And Audit Boundary](../../product/plato-settings-logs-audit-boundary.md), [Plato Product 1.0 Frontend QA Runbook](../../product/plato-1-0-frontend-qa-runbook.md)
> Related Plans: [Product Error Handling](product-error-handling.md), [Result And Evidence Exposure Surface](result-exposure-surface.md), [Configurable Logging System](configurable-logging-system.md)
> Release Record: Product 1.0 local unsigned RC accepted on 2026-06-07; broader support diagnostics remain follow-up work.

---

## 1. Problem / Gap

Product 1.0 needs enough diagnostics for early technical users and testers.
The accepted local RC diagnostic boundary includes redacted export packaging,
HTTP/frontend export, formal sidecar E2E, and mounted unsigned DMG smoke.
The logging system has session archive manifests, category JSONL files,
redaction hooks, and CLI manifest inspection. Audit Page can expose selected
evidence records, config/log references, and sanitized payload details.

The product boundary is:

- testers should not have to inspect SQLite files, guess log paths, or manually
  collect session artifacts;
- support/debug workflows need one redacted bundle with stable manifest
  metadata;
- Audit Page should remain a trust surface, not a full log browser;
- raw payloads, secrets, absolute paths, prompts, and provider payloads must not
  be included by default.

---

## 2. Architecture References Reviewed

Current facts this plan must preserve:

- `LoggingManager` and logging archives can write session `manifest.json`
  files with category file paths, templates, close markers, config hashes, and
  rotation metadata.
- Logging redaction masks common secret keys.
- Logs are debug/support material, not system state authority.
- EventStream, MessageStream, TaskBus, result/error summaries, config/log
  manifests, and Audit Page projection are the durable sources for Product 1.0
  explanation.
- Audit Page sanitized payloads are request-time only and should not be
  persisted as a separate fact source.

---

## 3. Scope

Build the smallest useful diagnostic export for Product 1.0:

1. Define a diagnostic bundle manifest schema.
2. Collect session/task/product facts from existing durable stores.
3. Include logging archive refs and selected redacted log snippets.
4. Include Audit summary/record refs without exposing raw hidden payloads.
5. Normalize or redact paths and secrets.
6. Provide a local export entry, preferably CLI first, with sidecar/API support
   only if needed for user testing.

---

## 4. Non-goals

- Do not build a full Diagnostics / Logs UI.
- Do not implement remote upload or cloud support collection.
- Do not include raw provider payloads, raw prompts, raw tool arguments, or raw
  hidden evidence by default.
- Do not create cross-session analytics.
- Do not implement long-term retention, compression policy, or user permission
  management beyond local Product 1.0 defaults.
- Do not make Audit Page responsible for assembling the bundle.

---

## 5. Bundle Contract

### 5.1 Output Shape

Recommended Product 1.0 output:

```text
diagnostic-bundle-<session_id>-<timestamp>.zip
  manifest.json
  session/summary.json
  session/tasks.json
  session/messages.summary.json
  session/results.json
  audit/summary.json
  audit/records.summary.json
  events/events.summary.jsonl
  logs/manifest.json
  logs/<category>.summary.jsonl
  config/effective-summary.json
  frontend/client-errors.summary.jsonl
```

The bundle can be produced as a directory during tests and zipped for user
delivery. The manifest must describe every included file.

### 5.2 Manifest Fields

```json
{
  "schemaVersion": "diagnostic_bundle.v1",
  "bundleId": "diag-session-123-20260605T120000Z",
  "createdAt": "2026-06-05T12:00:00Z",
  "workspaceRootLabel": "workspace://current",
  "sessionId": "session-123",
  "taskIds": ["task-1"],
  "redactionProfile": "product_1_0_default",
  "includedSections": ["session", "tasks", "audit", "events", "logs", "config"],
  "warnings": [],
  "files": [
    {
      "path": "session/summary.json",
      "kind": "session_summary",
      "redacted": true,
      "source": "SessionManager"
    }
  ]
}
```

### 5.3 Included Sources

| Source | Product 1.0 inclusion |
|---|---|
| Session summary | Session id, name, status, created/updated timestamps, workspace label. |
| Task tree | Task ids, titles, statuses, parent ids, result/error refs, retry eligibility. |
| Result/error summaries | User-readable summaries plus refs; no raw stack traces. |
| MessageStream | Message ids, kind, task refs, short redacted body previews. |
| EventStream | Event ids, timestamps, action/observation kinds, task refs, sanitized summaries. |
| Audit Page | Snapshot summary, record ids/kinds/verdicts/completeness, evidence refs. |
| Logs | Session log manifest and redacted category summaries. |
| Config | Effective config summary or config manifest refs when present. |
| Frontend client logs | Posted frontend errors if available. |
| Environment | TaskWeavn/Plato version, Python version, platform summary; no env secrets. |

### 5.4 Redaction Rules

Default Product 1.0 redaction:

- mask secret-like keys: `api_key`, `token`, `authorization`, `password`,
  `secret`, `credential`;
- convert absolute workspace paths to `workspace://...`;
- omit raw prompts and provider request/response payloads by default;
- include hashes or short previews only when helpful;
- mark hidden/permission-limited Audit evidence as hidden rather than forcing
  disclosure;
- cap each log/category summary to a bounded number of recent or relevant
  entries;
- include a manifest warning when a section is missing, partial, or skipped.

---

## 6. Implementation Slices

### D1 Bundle Models And Manifest

Deliver:

- diagnostic bundle manifest model;
- file entry model;
- section status model: `included`, `partial`, `missing`, `skipped`;
- redaction profile id.

Acceptance:

- manifest serializes deterministically;
- missing sections are explicit;
- every file in the bundle has a manifest entry.

### D2 Source Collectors

Deliver collectors for:

- session summary;
- TaskBus / Task projection facts;
- result/error summary store;
- MessageStream summaries;
- EventStream summaries;
- Audit Page snapshot/records through the same gateway contract where possible;
- logging archive manifest and redacted log snippets;
- config/log references;
- frontend client error logs when present.

Acceptance:

- collectors do not read frontend-only state;
- collectors can run after sidecar restart using durable stores;
- failure in one collector does not prevent other sections from being exported.

### D3 Redaction And Path Normalization

Deliver:

- shared diagnostic redaction helper using existing logging redaction rules as
  the baseline;
- workspace path normalizer;
- payload truncation and preview policy;
- tests for secrets, absolute paths, prompt-like payloads, and hidden evidence.

Acceptance:

- default bundle does not expose secrets or absolute local paths;
- raw hidden evidence remains hidden;
- redaction decisions are visible in the manifest.

### D4 Export Entry

Preferred Product 1.0 order:

1. CLI export command for developer/tester workflow.
2. Backend service that the CLI calls.
3. Optional sidecar HTTP route only if first user testing needs an in-app
   `Export diagnostics` action.

Candidate CLI:

```text
uv run taskweavn diagnostics export --workspace ./plato-workspace --session-id <id> --output ./diagnostics
```

Acceptance:

- export path is printed clearly;
- command can run against a stopped sidecar as long as workspace stores exist;
- output can be generated as a directory for tests and zip for delivery.

### D5 QA And Handoff

Deliver:

- fixture-based export test;
- real local sidecar HTTP session export smoke;
- QA note template fields for bundle path, redaction profile, warnings, and
  missing sections;
- Audit/Diagnostics handoff copy for disabled or reserved links.

Acceptance:

- Product 1.0 QA can attach one diagnostic bundle without manual SQLite/log
  collection;
- support can inspect manifest first and know what was included or skipped.

---

## 7. Contract / API Changes

Initial Product 1.0 preference:

- implement backend service and CLI first;
- do not add a frontend API unless the UI needs a visible export action;
- if adding HTTP, use a command-style endpoint and return a local file/ref
  descriptor, not raw bundle bytes in the normal JSON envelope.

Potential HTTP endpoint if needed:

```text
POST /api/v1/sessions/{sessionId}/diagnostics/export
GET  /api/v1/sessions/{sessionId}/diagnostics/exports/{bundleId}
```

This endpoint is optional for Product 1.0 local developer smoke. It becomes
important for non-developer testing or packaged app support.

Product 1.0 UI export slice assumptions:

- `POST /api/v1/sessions/{sessionId}/diagnostics/export` writes a local bundle
  under a sidecar-controlled diagnostics directory, defaulting to
  `workspace://current/.taskweavn/diagnostics`.
- The response returns a descriptor only:
  `bundleId`, `bundleDir`, `bundleDirLabel`, `zipPath`, `zipPathLabel`,
  `manifestPath`, `redactionProfile`, `includedSections`, `sections`,
  `warnings`, and `fileCount`.
- The response does not stream or embed bundle bytes, log lines, SQLite payloads,
  prompts, provider payloads, or hidden Audit evidence.
- Diagnostics UI may offer an `Export diagnostics` action when the HTTP sidecar
  is available. The UI shows success/error state and local bundle paths, but it
  does not become a logs browser.
- `GET /api/v1/sessions/{sessionId}/diagnostics/exports/{bundleId}` remains a
  future descriptor/download lookup and is not part of this slice.

---

## 8. Tests And Validation

Required backend tests:

- manifest serialization and deterministic file listing;
- section collector success/partial/missing behavior;
- redaction of secret keys and absolute paths;
- truncation of long payloads/log entries;
- export can run after sidecar restart;
- one failed Task bundle includes task status, error ref, result/error summary,
  Audit refs, and log manifest refs.

Required smoke:

- run Product 1.0 local sidecar HTTP scenario;
- export bundle for the created session;
- inspect `manifest.json`;
- verify no obvious secrets or absolute workspace paths appear;
- verify missing sources are marked partial/missing instead of silently omitted.

Frontend integration/E2E runner:

- `npm run test:e2e:sidecar` from `frontend/` starts
  `tests/fixtures/sidecar_smoke.py --keep-alive`, waits for the seeded
  sidecar descriptor, then runs the Diagnostics route E2E test against the real
  sidecar HTTP API.
- This runner is Product 1.0 acceptance infrastructure for real sidecar data.
  It does not replace later browser visual/Electron smoke coverage.

---

## 9. Acceptance Criteria

Diagnostic bundle export is acceptable for Product 1.0 when:

1. a tester can generate one bundle for a session with a single command;
2. the bundle includes session, task, result/error, Audit, event, log, and
   config summaries where available;
3. every included file is listed in `manifest.json`;
4. missing or unavailable sources are explicit;
5. secret-like fields and absolute workspace paths are redacted by default;
6. raw prompts, raw provider payloads, and hidden Audit payloads are excluded by
   default;
7. Product 1.0 QA notes can reference the bundle path and warnings.

---

## 10. Risks And Assumptions

| Risk | Mitigation |
|---|---|
| Bundle becomes a full log browser | Keep export service separate from UI; bundle is support artifact only. |
| Raw payload leakage | Default redaction, hidden evidence policy, tests for secret/path/prompt cases. |
| Export fails because one source is missing | Per-section partial/missing status and warnings. |
| Bundle is too large | Summary-only log snippets and bounded event/message previews. |
| Frontend wants export before backend service is stable | Add optional sidecar route only after CLI/backend service works. |

Assumption: Product 1.0 early users are local or technical enough to retrieve a
local bundle path. Non-developer packaged support can add a visible UI action
later without changing the bundle contract.

---

## 11. Implementation Notes

2026-06-05 backend slice started:

- Added CLI-first backend exporter target:
  `taskweavn diagnostics export --workspace <workspace> --session-id <id> --output <dir>`.
- Bundle manifest and section/file entries are implemented with
  `diagnostic_bundle.v1` and Product 1.0 default redaction profile.
- Initial collectors cover session summary, TaskBus facts, result/error
  summaries, MessageStream summaries, EventStream summaries, UI event replay,
  Audit Page gateway snapshot/records, log archive manifest/snippets, config
  summary, frontend client error summaries, and runtime environment summary.
- Collector failures are isolated into manifest section warnings instead of
  aborting the whole export.
- Default redaction masks secret-like keys, omits prompt/raw/provider/tool
  payload-like fields, truncates long strings, and normalizes workspace paths
  to `workspace://current`.
- Task-level product error summaries consume flat Product 1.0 metadata and add
  validated Audit result/evidence ids (`auditRef`, `auditRecordId`,
  `auditEvidenceId`) without exposing raw provider, prompt, log, or SQLite
  payloads.

Product 1.0 local RC closure:

- CLI/backend export, HTTP export route, frontend diagnostic export flow,
  redacted session/task/result/message/event/audit/log/config/frontend
  summaries, task-result product-error Audit refs, workspace path
  normalization, zip output, and formal sidecar E2E coverage are in place.
- Mounted unsigned DMG smoke covers Diagnostic Bundle export through the
  launcher-backed bundled runtime.

Follow-ups:

- Broaden Audit-specific diagnostic refs beyond task result failures when
  additional support paths need them.
- Add richer QA handoff copy beyond the in-app descriptor state if early tester
  support needs it.
- Signed/notarized distribution validation is deferred under the Packaging plan
  until Apple Developer credentials are available.

---

## 12. Follow-Up Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Implement a small Diagnostic Bundle support-handoff hardening slice.

Context:
Product 1.0 local unsigned RC already includes backend/HTTP/frontend export,
redacted zip output, sidecar E2E, and mounted unsigned DMG smoke. This follow-up
should improve support handoff only where early tester feedback needs it.

Scope:
1. Add or refine QA/support copy for bundle path, warnings, missing sections,
   and redaction profile.
2. Broaden Audit-specific diagnostic refs only for a concrete support path.
3. Add focused tests for any new descriptor/copy/ref behavior.

Do not implement remote upload.
Do not build a full logs browser.
Do not include raw prompts, provider payloads, hidden evidence, or secrets by
default.

Output:
- files changed
- tests run
- support handoff behavior
- redaction/ref evidence
- remaining Product 1.1 diagnostics gaps
```
