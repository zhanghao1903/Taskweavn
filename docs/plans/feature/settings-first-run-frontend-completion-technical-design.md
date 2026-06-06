# Technical Design: Settings First-Run Frontend Completion

> Status: accepted
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
  -> Main Page route
      -> FirstRunReadinessGate
          -> setup summary / configure action
          -> Main Page when ready
  -> Settings route
      -> FirstRunReadinessGate + Main Page/first-run background
      -> SettingsRoute(presentation="modal")
          -> Settings setup form
          -> readiness recheck
          -> continue / close to safe return target
```

The route guard still protects Main Page work in HTTP runtime mode. `/settings`
is available as an in-app modal route even when readiness is blocked; Audit and
Diagnostics routes remain accessible.

---

## 2. Accepted Closure

Accepted Product 1.0 implementation:

- `PlatoApi.getSettingsReadiness()`;
- `PlatoApi.getSettingsConfig()`;
- `PlatoApi.updateSettingsConfig()`;
- `PlatoApi.recheckSettingsReadiness()`;
- `FirstRunReadinessGate`;
- loading state;
- route-unavailable retry state;
- blocking setup panel;
- configured path to Main Page;
- `/settings` route as a large in-app modal over the Main Page/first-run
  background;
- provider/model/API-key/logging profile setup form;
- write-only secret input that is never prefilled or echoed after save;
- save/recheck/continue flow;
- degraded warning in Main Page with a Settings link;
- Main Page Settings entry after setup is ready;
- Settings modal close behavior through the safe `returnTo` target;
- panel-level frosted blur while keeping the outside Main Page background
  recognizable;
- diagnostics export action from Settings setup;
- sidecar E2E for configured readiness, unconfigured save/recheck, and
  diagnostic export;
- CI gate for the sidecar E2E runner;
- manual first-run smoke command: `npm run dev:sidecar:first-run`.

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
Settings route: gated Main Page/first-run background + Settings modal
Main Page route wrapped in FirstRunReadinessGate
```

Behavior:

- `/settings` is available even when first-run readiness is blocked.
- `/settings` does not open a new window and does not replace the whole visual
  page; it overlays a modal on the current Main Page/first-run background.
- Main Page remains blocked while `firstRun.ready=false`.
- Returning from Settings after successful save should navigate to `/` or the
  original `returnTo` path if one is present and safe.
- Closing the modal without saving also returns to the safe `returnTo` path.

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
- continue button after ready;
- close button for modal Settings entry.

Interaction details:

- Provider selector changes required key hint:
  - `litellm`: `LLM_API_KEY`;
  - `deepseek`: `DEEPSEEK_API_KEY` or `LLM_API_KEY`;
  - `openrouter`: `OPENROUTER_API_KEY` or `LLM_API_KEY`.
- API key input is never prefilled.
- Saving shows pending state and disables duplicate submit.
- Failed save preserves user-entered non-secret fields but clears the secret
  field unless a clear reason exists to keep it in memory.
- Modal Settings uses a light page overlay and applies `backdrop-filter` to the
  Settings panel itself, so the Main Page/first-run background remains visible
  outside the panel and is visually blurred through the panel.

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
- modal Settings uses `role="dialog"` and exposes a close affordance;
- desktop, tablet, and mobile widths do not clip long env var names;
- buttons do not resize layout when pending text changes;
- mobile Settings modal stays inside the viewport width and uses internal
  scrolling when the setup form is taller than the viewport.

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
- no fake secret appears in DOM or exported bundle text;
- manual browser visual smoke confirms the Settings modal is a large in-app
  overlay over Main Page/first-run background, with panel-level blur and no
  mobile horizontal overflow.

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
9. Settings modal visual acceptance on desktop and mobile browser viewports.
10. Browser/Electron release smoke, tracked separately under release readiness.

Do not start at step 5 before step 1 is accepted. A frontend-only form without
a backend write contract would create a false product acceptance signal.

---

## 13. Closed Decisions

1. Where is Product 1.0 local secret storage implemented?
   - accepted Product 1.0 answer: local sidecar storage under
     `.taskweavn/settings/`, with safe read summaries and write-only secret
     replacement;
   - OS keychain and encrypted workspace secret store remain future
     hardening options.

2. Does Product 1.0 allow provider network test?
   - accepted answer: no. Save and local readiness only unless a separate
     test-connection API is accepted.

3. Can setup diagnostics be exported before a session exists?
   - accepted answer: no. The Settings page exports diagnostics for an
     available sidecar session and shows limited setup diagnostics guidance
     when no session exists.

4. Is logging profile save in Product 1.0 required or read-only?
   - accepted answer: logging profile selection is part of the Product 1.0
     settings config write slice.

5. Is Settings a separate page/window or an in-app modal?
   - accepted answer: `/settings` remains a route for deep-linking and return
     targets, but Product 1.0 presents it as a large modal over the
     Main Page/first-run background. The outside background stays recognizable;
     the Settings panel carries the frosted blur treatment.

---

## 14. Completion Boundary

This feature is accepted because Settings first-run is usable as a Product 1.0
setup flow and the Settings surface visual treatment has been accepted as an
in-app Main Page modal. It does not complete the broader centralized runtime
configuration system.

The broader system remains governed by
[Centralized runtime configuration](centralized-runtime-configuration.md).
Browser/Electron smoke remains a release-readiness activity outside this
technical design's acceptance boundary.
