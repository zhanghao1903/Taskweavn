# Technical Design: Settings First-Run Frontend Completion

> Status: draft
> Last Updated: 2026-06-06
> Plan: [Settings first-run frontend completion](settings-first-run-frontend-completion.md)
> Existing Baseline: [Settings readiness](settings-first-run-readiness.md)
> API Contract: [Settings first-run API contract](../../engineering/settings-first-run-api-contract.md)

---

## 1. Design Summary

The existing `FirstRunReadinessGate` should become an entry point into a
minimal Settings setup flow instead of remaining a read-only blocker.

The frontend architecture should stay narrow:

```text
App route guard
  -> FirstRunReadinessGate
      -> setup summary / configure action
      -> SettingsSetupRoute
          -> SettingsSetupForm
          -> readiness recheck
          -> continue to Main Page
```

The route guard still protects only Main Page in HTTP runtime mode. Audit and
Diagnostics routes remain accessible.

---

## 2. Current Baseline

Implemented today:

- `PlatoApi.getSettingsReadiness()`;
- `FirstRunReadinessGate`;
- loading state;
- route-unavailable retry state;
- blocking setup panel;
- configured path to Main Page;
- sidecar E2E for configured/unconfigured readiness;
- CI gate for the sidecar E2E runner.

Known limitations:

- no `/settings` route;
- no Settings page;
- no config read/write API client;
- no secret input;
- no save/recheck loop;
- no degraded warning in Main Page;
- diagnostics export is not available from the setup blocker;
- recovery actions are text only.

---

## 3. Frontend Module Shape

Recommended files:

```text
frontend/src/pages/settings/
  FirstRunReadinessGate.tsx
  FirstRunReadinessGate.module.css
  SettingsRoute.tsx
  SettingsRoute.module.css
  SettingsSetupForm.tsx
  SettingsSetupForm.module.css
  settingsRouteModel.ts
  settingsViewModel.ts
  settingsApiModel.ts
  settingsCopy.ts
```

Shared components should remain under `frontend/src/shared/components` only if
the Settings work reveals genuinely reusable primitives. Do not create
page-specific clones of Button, Input, Select, Banner, or Field patterns if
shared primitives already exist.

---

## 4. Routing

Add a route predicate:

```text
isSettingsPath(pathname) -> pathname === "/settings"
```

`App` routing order:

```text
Audit route
Diagnostics route
Settings route
Main Page route wrapped in FirstRunReadinessGate
```

Behavior:

- `/settings` is available even when first-run readiness is blocked.
- Main Page remains blocked while `firstRun.ready=false`.
- Returning from Settings after successful save should navigate to `/` or the
  original `returnTo` path if one is present and safe.

Allowed query:

```text
/settings?source=first-run&returnTo=/
```

`returnTo` must only allow local app paths.

---

## 5. State Model

### 5.1 Readiness Gate State

```text
idle
checking
blocked
ready
degraded
unavailable
```

Rules:

- `ready`: render children.
- `degraded`: render children and optionally pass warning metadata to Main Page
  or a route-level banner.
- `blocked`: render setup summary with a primary configure action.
- `unavailable`: render retry + diagnostics guidance.

### 5.2 Settings Setup State

```text
loading_config
loading_failed
editing
saving
save_failed
rechecking
ready_to_continue
```

Rules:

- The API key field starts empty even when `apiKeyConfigured=true`.
- The UI may show "API key configured" as a safe boolean.
- Saving an empty API key should keep the existing secret when one exists, and
  should be invalid when no key exists.
- Recheck readiness after a successful save.
- If readiness is still blocked, keep the user in the setup flow and show the
  updated blocking issues.

---

## 6. API Client Design

Extend `PlatoApi` against the accepted backend contract.

Draft types:

```ts
type SettingsProvider = "litellm" | "deepseek" | "openrouter";

type SettingsConfigSummary = {
  schemaVersion: "plato.settings_config.v1";
  llm: {
    provider: SettingsProvider;
    providerSource: "default" | "env" | "stored";
    model: string;
    modelSource: "default" | "env" | "stored";
    apiKeyConfigured: boolean;
    apiKeySource: "none" | "env" | "stored";
    apiKeyEnvVar: string;
  };
  logging: {
    selectedProfile: string | null;
    selectedProfileSource: "default" | "env" | "stored";
    selectedProfileKnown: boolean;
    defaultProfile: string | null;
    profiles: Array<{ id: string; description: string }>;
  };
  diagnostics: {
    bundleExportAvailable: boolean;
  };
};

type UpdateSettingsConfigPayload = {
  llm: {
    provider: SettingsProvider;
    model: string;
    apiKey?: string;
  };
  logging?: {
    selectedProfile?: string | null;
  };
};
```

Draft client methods:

```ts
getSettingsConfig(): Promise<QueryResponse<SettingsConfigSummary>>;
updateSettingsConfig(
  payload: UpdateSettingsConfigPayload,
): Promise<
  QueryResponse<{
    schemaVersion: "plato.settings_config_update.v1";
    config: SettingsConfigSummary;
    readiness: SettingsReadinessReport;
  }>
>;
recheckSettingsReadiness(): Promise<QueryResponse<SettingsReadinessReport>>;
```

If the backend keeps readiness recheck as a plain `GET`, the frontend can use
`getSettingsReadiness()` instead of a separate recheck method.

---

## 7. View Model Rules

`settingsViewModel.ts` should convert API facts into stable UI facts:

- provider options;
- selected provider;
- model field value;
- API key field policy;
- missing config issues;
- warning issues;
- primary action label;
- disabled/save state;
- diagnostics action availability;
- safe return target.

No component should inspect raw issue arrays for layout decisions beyond simple
rendering. Product labels should live in `settingsCopy.ts`.

---

## 8. UI Controls

Required controls:

- provider selector;
- model text input;
- API key password input;
- logging profile selector;
- save/check button;
- retry readiness button;
- export diagnostics button when available;
- continue button after ready.

Interaction details:

- Provider selector changes required key hint:
  - `litellm`: `LLM_API_KEY`;
  - `deepseek`: `DEEPSEEK_API_KEY` or `LLM_API_KEY`;
  - `openrouter`: `OPENROUTER_API_KEY` or `LLM_API_KEY`.
- API key input is never prefilled.
- Saving shows pending state and disables duplicate submit.
- Failed save preserves user-entered non-secret fields but clears the secret
  field unless a clear reason exists to keep it in memory.

---

## 9. Diagnostics Integration

The Settings setup flow should reuse the existing diagnostic export API and UI
patterns.

Minimum Product 1.0 behavior:

- show `Export diagnostics` when sidecar export route is available;
- export the current session if a session exists;
- if no session exists, show a support note that setup diagnostics are limited;
- never include raw secret input in bundle assertions.

If export requires a session and none exists, the setup page should not create a
session just for diagnostics unless a backend contract explicitly allows it.

---

## 10. Accessibility And Responsive Requirements

Required:

- form fields have labels;
- errors are associated with fields or sections;
- pending state is announced through visible text;
- keyboard can reach every control;
- desktop, tablet, and mobile widths do not clip long env var names;
- buttons do not resize layout when pending text changes.

Settings surfaces should be utilitarian and dense enough for repeated use. This
is an operational setup screen, not a marketing page.

---

## 11. Testing Strategy

Unit/component tests:

- Settings route loads safe config.
- API key value is never shown after read or save.
- Provider change updates required-key hint.
- Save success triggers readiness recheck.
- Save failure shows product recovery copy.
- Degraded readiness shows non-blocking warning.
- Mock runtime does not call settings APIs for Main Page.

API client tests:

- `GET /api/v1/settings/config`;
- `PATCH /api/v1/settings/config`;
- readiness recheck path;
- structured error metadata.

E2E:

- unconfigured sidecar opens Settings setup from first-run gate;
- save minimal config;
- readiness becomes ready;
- Main Page opens;
- configured sidecar opens Main Page directly;
- diagnostic export remains available;
- no fake secret appears in DOM or exported bundle text.

CI:

- `npm run test:e2e:sidecar` remains the formal Product 1.0 frontend
  integration acceptance command.

---

## 12. Implementation Order

1. Backend API contract/write slice.
2. Frontend API types/client.
3. Settings route shell and safe config read.
4. First-run blocker configure action and routing.
5. Settings form save/recheck loop.
6. Degraded warning on Main Page.
7. Diagnostics action integration.
8. Sidecar E2E unconfigured -> save -> ready.
9. Browser/Electron release smoke.

Do not start at step 5 before step 1 is accepted. A frontend-only form without
a backend write contract would create a false product acceptance signal.

---

## 13. Open Decisions

1. Where is Product 1.0 local secret storage implemented?
   - environment file;
   - OS keychain;
   - encrypted workspace secret store;
   - process-local development store.

2. Does Product 1.0 allow provider network test?
   - default recommendation: no, save and local readiness only.

3. Can setup diagnostics be exported before a session exists?
   - default recommendation: no, unless a backend setup diagnostics endpoint is
     added.

4. Is logging profile save in Product 1.0 required or read-only?
   - default recommendation: allow selection only if the backend config write
     slice includes it; otherwise display as read-only.

---

## 14. Completion Boundary

This feature is complete when Settings first-run is usable as a product setup
flow. It does not complete the broader centralized runtime configuration system.

The broader system remains governed by
[Centralized runtime configuration](centralized-runtime-configuration.md).
