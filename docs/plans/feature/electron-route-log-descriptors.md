# Electron Route Log Descriptors

> Status: planned Product 1.1 P1 beta hardening
>
> Last Updated: 2026-06-24
>
> Owner: Electron / Diagnostics / QA
>
> Related:
> [Diagnostic Bundle Export](diagnostic-bundle-export.md),
> [Product 1.1 P0 Release Evidence](../../product/plato-1-1-p0-release-evidence-2026-06-20.md),
> [Packaging Electron Release Plan](packaging-electron-release-plan.md)

## 1. Problem

Product 1.1 P0 proves the Runtime Input Router route matrix through configured,
packaged, and mounted installer Electron smoke. The diagnostic bundle can
already link Router decisions, Activity, Audit refs, and runtime-input
descriptors.

The remaining P1 diagnostics gap is supportability after an Electron smoke or
manual beta run fails:

- the smoke log shows pass/fail text, but not a normalized per-route descriptor;
- support cannot quickly tell which route class failed without reading raw
  console output;
- release notes can say the route matrix passed, but do not have a compact
  machine-readable route-log summary;
- raw Electron logs can include noisy implementation details and should not
  become the user-facing diagnostic contract.

## 2. Goals

1. Define a small per-route Electron log descriptor contract.
2. Capture route class, expected outcome, observed outcome, diagnostic refs,
   Audit refs, workspace mutation expectation, and pass/fail status.
3. Make descriptors safe for diagnostic bundles and release evidence.
4. Keep raw Electron console logs as support material, not the product-facing
   diagnostic source.
5. Preserve existing smoke commands and add descriptor output as a compatible
   enhancement.

## 3. Non-Goals

- No full Electron log browser.
- No raw console log ingestion into normal UI.
- No screenshot or video capture pipeline.
- No remote telemetry upload.
- No cloud support workflow.
- No change to Runtime Input Router semantics.
- No replacement for Audit or Activity as product facts.

## 4. Descriptor Shape

Recommended first schema:

```ts
type ElectronRouteLogDescriptor = {
  schemaVersion: "plato.electron_route_log_descriptor.v1";
  runId: string;
  routeId: string;
  routeClass:
    | "read_only_question"
    | "guidance"
    | "ask_answer"
    | "confirmation_answer"
    | "execution_handoff"
    | "unsupported"
    | "stop_retry"
    | "diagnostics_export";
  command: string;
  appMode: "electron_dev" | "packaged_app" | "mounted_installer";
  startedAt: string;
  completedAt: string | null;
  status: "passed" | "failed" | "skipped";
  expectedOutcome: string;
  observedOutcome: string | null;
  noMutationExpected: boolean;
  workspaceMutationObserved: boolean | null;
  sessionId: string | null;
  activityMessageIds: string[];
  auditRecordIds: string[];
  diagnosticSectionIds: string[];
  failureReason: string | null;
  redactionApplied: boolean;
};
```

The descriptor should use safe ids and summaries only. It must not include
provider payloads, prompts, secrets, absolute paths, full console output, or
SQLite rows.

## 5. Pipeline

```text
Electron smoke route step
  -> route assertion result
  -> ElectronRouteLogDescriptor
  -> descriptor JSONL or JSON summary
  -> diagnostic bundle / release evidence
```

First implementation can write a single JSON summary beside existing smoke
artifacts. Diagnostic bundle inclusion can follow after the shape is stable.

## 6. Implementation Slices

### ERL-1. Contract And Smoke Runner Shape

- Add typed route descriptor shape to the Electron smoke runner boundary.
- Emit one descriptor per route class exercised by the smoke matrix.
- Keep existing pass/fail console output unchanged.

Acceptance:

- configured Electron smoke can produce a descriptor summary;
- descriptors include route class, status, and safe refs;
- existing smoke output remains readable for developers.

### ERL-2. Packaged And Installer Coverage

- Reuse the same descriptor shape for packaged app and mounted installer smoke.
- Include `appMode` so release evidence can distinguish runtime surfaces.
- Mark skipped routes explicitly instead of omitting them.

Acceptance:

- packaged app and mounted installer smoke can produce comparable descriptor
  summaries;
- skipped routes are visible and explain why they were skipped.

### ERL-3. Diagnostic Bundle Projection

- Include a redacted route descriptor summary in diagnostic exports when
  available.
- Add manifest entries that describe descriptor source and redaction.
- Preserve raw log omission by default.

Acceptance:

- diagnostic bundle includes route descriptor summary without absolute paths;
- missing descriptor files are reported as missing or skipped, not as export
  failure.

### ERL-4. Release Evidence Sync

- Link descriptor summaries from Product 1.1 release evidence.
- Use descriptor counts to summarize route coverage.
- Keep screenshots and raw logs optional.

Acceptance:

- release evidence can state route coverage from descriptor data;
- support can identify failed route classes without parsing raw logs.

## 7. Acceptance Criteria

- Each Electron smoke route class can emit a safe descriptor.
- Descriptor output is deterministic enough for test assertions.
- Descriptor summaries can be attached to diagnostics and release evidence.
- No descriptor includes secrets, raw provider payloads, absolute paths, raw
  prompts, full console logs, or SQLite rows.
- Existing smoke commands keep their current behavior when descriptor output is
  not requested.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Descriptor duplicates Audit or Activity facts. | Store only refs and smoke assertion outcomes; Audit/Activity remain product facts. |
| Logs become a product state source. | Keep descriptors as QA/support evidence, not runtime authority. |
| Packaged and installer modes diverge. | Use one schema with explicit `appMode`. |
| Raw logs leak sensitive data. | Include summaries and refs only; keep raw logs out of default diagnostic bundles. |

## 9. Open Questions

1. Should descriptor generation be always-on for smoke commands or gated behind
   an explicit output flag?
2. Should release artifacts include descriptor JSON by default, or only when a
   smoke run fails?
3. Should descriptor summaries be surfaced in Settings diagnostics, or remain
   only inside exported bundles and release evidence?
