# Feature Plan: Settings And First-Run Readiness

> Status: in_progress
> Last Updated: 2026-06-05
> Gap: [Settings and first run](../../gaps/README.md)
> Architecture: [Configurable Logging System](../../architecture/configurable-logging-system.md), [LLM Provider Reliability](../../architecture/llm-provider-reliability.md), [UI And Backend Communication](../../architecture/ui-backend-communication.md)
> Product: [Plato Settings, Logs, And Audit Boundary](../../product/plato-settings-logs-audit-boundary.md)
> Related Plans: [Settings first-run frontend completion](settings-first-run-frontend-completion.md), [Centralized Runtime Configuration](centralized-runtime-configuration.md), [Diagnostic Bundle Export](diagnostic-bundle-export.md), [Product Error Handling](product-error-handling.md)
> Release Record: TBD

---

## 1. Problem / Gap

Product 1.0 needs a non-developer first-run path before broader testing. The
full centralized runtime configuration plane and Settings UI are intentionally
larger than the current backend closure work, but the frontend still needs a
stable way to know whether the local sidecar can create and run a session.

This plan owns the read-only readiness contract. Product-complete frontend
setup work is now tracked separately in
[Settings first-run frontend completion](settings-first-run-frontend-completion.md).

The immediate backend gap is read-only readiness:

- LLM provider/auth configuration must be discoverable without exposing secret
  values.
- Built-in logging profiles must be discoverable for the future Settings /
  Diagnostics surfaces.
- Diagnostic bundle export availability should be visible so frontend
  integration can wire the eventual handoff.
- Missing or invalid first-run configuration should map to Product 1.0 recovery
  actions rather than raw exceptions.

---

## 2. Scope

Implement the smallest Product 1.0 backend slice:

1. Add a read-only settings/first-run readiness provider.
2. Add a local sidecar route:

   ```text
   GET /api/v1/settings/readiness
   ```

3. Report sanitized LLM provider readiness from environment-derived config.
4. Report logging profile availability from the existing logging config.
5. Report diagnostic bundle export availability.
6. Add focused backend contract tests.

---

## 3. Non-goals

- Do not implement the full Settings UI.
- Do not add config writes or secret storage.
- Do not implement the centralized runtime configuration store.
- Do not run provider network checks or validate API keys remotely.
- Do not expose raw environment values for secrets.
- Do not add a diagnostic bundle HTTP export route in this slice.

---

## 4. Readiness Contract

Initial Product 1.0 response is returned inside the existing sidecar JSON
envelope:

```json
{
  "ok": true,
  "data": {
    "schemaVersion": "plato.settings_readiness.v1",
    "status": "needs_configuration",
    "firstRun": {
      "ready": false,
      "blockingIssueCodes": ["llm.missing_api_key"],
      "recommendedActions": ["open_settings"]
    },
    "llm": {
      "provider": "litellm",
      "providerSource": "default",
      "model": "anthropic/claude-sonnet-4-5-20250929",
      "modelSource": "default",
      "configured": false,
      "apiKeyConfigured": false,
      "missingEnvVars": ["LLM_API_KEY"],
      "requestTimeoutSeconds": 180,
      "requestTimeoutConfigured": false,
      "requestTimeoutValid": true,
      "thinking": {
        "configured": false,
        "enabled": null,
        "effort": null
      }
    },
    "logging": {
      "enabled": true,
      "level": "INFO",
      "selectedProfile": null,
      "selectedProfileKnown": true,
      "defaultProfile": "normal",
      "profiles": [
        {
          "id": "normal",
          "description": "Record normal summaries."
        }
      ]
    },
    "diagnostics": {
      "bundleExportAvailable": true,
      "httpExportRouteAvailable": false,
      "cliCommandTemplate": "uv run taskweavn diagnostics export --workspace <workspace> --session-id <sessionId> --output <dir>"
    },
    "blockingIssues": [],
    "warnings": []
  },
  "error": null
}
```

Contract rules:

- The top-level `ApiError` / JSON envelope remains unchanged.
- Secret values are never returned. Env var names may be returned as recovery
  hints.
- Readiness is deterministic and local; it does not call LLM providers.
- A missing API key is `needs_configuration`, not a transport failure.
- Invalid first-run settings are represented as blocking issue objects with
  Product recovery actions.

---

## 5. Implementation Slices

### S1 Readiness Provider

Deliver:

- settings readiness models;
- env-backed LLM provider inspection;
- logging profile summary;
- diagnostics export availability summary.

Acceptance:

- no provider construction or network call;
- no secret value in serialized output;
- missing LLM keys and invalid provider/timeout/bool settings are explicit.

### S2 Sidecar Route

Deliver:

- `GET /api/v1/settings/readiness`;
- app assembly injection for the real sidecar;
- transport test with a stubbed provider.

Acceptance:

- route uses existing JSON envelope;
- auth and method handling remain consistent with other sidecar routes;
- missing gateway returns a structured transport error.

### S3 Frontend Integration Follow-up

Status: planned / current frontend slice.

Product 1.0 frontend assumption:

- The readiness path gates the Main Page route only in HTTP runtime mode.
- Mock runtime keeps using fixture data without calling the sidecar.
- Audit and Diagnostics deep links remain open so support/debug handoff routes
  are not blocked by missing LLM credentials.
- The UI is read-only: it shows setup blockers, safe env var names, recovery
  actions, logging/diagnostics availability, and a retry check action.
- It does not write config, store secrets, or validate provider credentials
  remotely.

Deliver:

- Settings / first-run UI consumption;
- missing or invalid LLM config recovery state;
- disabled/reserved full Settings affordance copy;
- controlled sidecar smoke fixture flag for first-run-unconfigured frontend
  checks;
- controlled sidecar smoke fixture flag for deterministic first-run configured
  checks;
- final browser/Electron acceptance after frontend integration.

Acceptance:

- HTTP runtime with `firstRun.ready=false` shows a first-run blocker before the
  Main Page starts session work;
- HTTP runtime with `firstRun.ready=true` continues to Main Page;
- loading and readiness-route failure states are explicit and retryable;
- no secret values are displayed;
- mock runtime remains unchanged.
- `tests.fixtures.sidecar_smoke --first-run-unconfigured` can produce a real
  sidecar `needs_configuration` readiness payload for frontend E2E.
- `npm run test:e2e:sidecar` covers both first-run-unconfigured and
  deterministic configured sidecar readiness paths.
- `.github/workflows/product-1-0-frontend-integration.yml` runs the same
  sidecar E2E command as the Product 1.0 frontend integration CI gate.

---

## 6. Tests And Validation

Required backend tests:

- LLM missing-key readiness returns `needs_configuration` with env var names only.
- Configured LLM readiness does not expose API key values.
- Invalid provider and invalid timeout map to blocking issues.
- Logging profiles are listed from existing logging config.
- HTTP route returns the readiness payload through the sidecar envelope.
- Main Page sidecar assembly wires the real readiness provider.

Full user-path acceptance is intentionally deferred until frontend integration.
The current read-only gate is not sufficient for final product acceptance of
the Settings first-run feature; final acceptance requires the completion plan's
save/recheck setup flow.

---

## 7. Risks And Assumptions

| Risk | Mitigation |
|---|---|
| Readiness becomes a full Settings backend | Keep this slice read-only and env-backed. |
| Secret leakage | Return booleans and env var names only; test serialized output. |
| First-run UX decisions harden too early | Expose backend facts and Product recovery actions, not UI copy. |
| Centralized config plan diverges | Reference the centralized runtime configuration plan and avoid config writes here. |

Assumption: Product 1.0 first-run can start with local environment-based LLM
configuration and built-in logging profile discovery. A future Settings UI can
replace env-backed writes without changing the readiness route shape.

---

## 8. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Integrate Settings/first-run readiness into the frontend runtime.

Context:
docs/plans/feature/settings-first-run-readiness.md defines the read-only
backend route GET /api/v1/settings/readiness. Full Settings UI and config writes
are out of scope for Product 1.0 backend closure.

Scope:
1. Add frontend API client support for settings readiness.
2. Surface missing LLM config and recovery actions in the first-run path.
3. Keep Diagnostic/Logs actions reserved unless wired by a follow-up route.
4. Add focused frontend tests.

Do not implement config writes.
Do not expose secrets.
Do not run final acceptance until the frontend integration path is ready.

Output:
- files changed
- tests run
- readiness states handled
- remaining Settings/Diagnostics gaps
```
