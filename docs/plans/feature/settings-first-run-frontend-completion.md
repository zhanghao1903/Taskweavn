# Feature Plan: Settings First-Run Frontend Completion

> Status: in_progress
> Last Updated: 2026-06-06
> Gap: [Settings and first run](../../gaps/README.md)
> Upstream: [Settings readiness](settings-first-run-readiness.md), [Centralized runtime configuration](centralized-runtime-configuration.md), [Diagnostic bundle export](diagnostic-bundle-export.md), [Product error handling](product-error-handling.md)
> Product: [Settings, Logs, and Audit Boundary](../../product/plato-settings-logs-audit-boundary.md), [Frontend QA Runbook](../../product/plato-1-0-frontend-qa-runbook.md)
> Technical Design: [Settings first-run frontend completion technical design](settings-first-run-frontend-completion-technical-design.md)
> API Contract: [Settings first-run API contract](../../engineering/settings-first-run-api-contract.md)

---

## 1. Problem

The current Settings first-run frontend path is a read-only gate:

- it calls `GET /api/v1/settings/readiness`;
- it blocks Main Page when `firstRun.ready=false`;
- it shows safe setup facts and recovery copy;
- it is covered by the sidecar E2E runner.

That is useful but not a complete product experience. A user who sees the
blocker still cannot fix configuration in the app. Product acceptance should
wait until the user can move from "setup required" to "ready" without leaving
Plato or manually editing environment variables.

---

## 2. Product Goal

For Product 1.0, Settings first-run is complete when a local user can:

1. open Plato with an unconfigured sidecar;
2. understand what is missing without seeing raw secrets or backend internals;
3. choose a local LLM provider and model;
4. enter the required API key through a protected field;
5. save the configuration through a local sidecar settings API;
6. re-run readiness from the UI;
7. continue to Main Page after readiness becomes ready;
8. export diagnostics if setup still fails;
9. revisit a Settings surface later to inspect current safe config summaries.

This plan intentionally stays smaller than the full centralized runtime
configuration system. It only completes the first-run/product setup path needed
for Product 1.0.

---

## 3. Scope

### In Scope

- First-run setup screen as a real setup flow, not only a blocker.
- Settings route/surface for Product 1.0 setup.
- LLM provider selection for `litellm`, `deepseek`, and `openrouter`.
- Model text input.
- API key secret input with masked display and no value echo after save.
- Logging profile selection from readiness metadata.
- Diagnostics export action from the first-run/setup surface.
- Degraded/warning state surfaced after first-run readiness is true.
- Retry/recheck readiness action after saving settings.
- Real sidecar E2E covering unconfigured -> save -> ready.
- CI inclusion through `npm run test:e2e:sidecar`.

### Out Of Scope For This Feature

- Full centralized config hierarchy across global/workspace/session/task.
- Remote provider network validation unless a separate test-connection API is
  accepted first.
- Showing stored secret values.
- Raw environment editing.
- Complete Diagnostics/Logs browser.
- Audit Page configuration editing.
- Electron packaging work, except for later release smoke.

---

## 4. Required Upstream Dependencies

Frontend implementation must not invent write API shapes in UI code. Product
completion requires a small backend/API slice before or alongside the frontend:

1. a settings config read endpoint for safe current values;
2. a settings config save endpoint for provider/model/logging profile and
   secret update;
3. a storage policy for local secrets;
4. readiness recomputation after save;
5. product error metadata for save failures;
6. audit/log event emission for accepted configuration changes without secret
   values.

If these are not available, the frontend can only deliver a read-only setup
guide, not a complete product experience.

---

## 5. UX Surfaces

### 5.1 First-Run Setup Screen

Entry:

- Main Page route in HTTP runtime mode.
- Rendered before session list or snapshot work starts.

States:

- `checking`: readiness request in flight.
- `blocked`: readiness returned `firstRun.ready=false`.
- `route_unavailable`: readiness route failed or returned invalid envelope.
- `saving`: settings save command in flight.
- `save_failed`: save command failed with product error metadata.
- `ready`: continue to Main Page.
- `degraded`: continue to Main Page with warning summary.

Expected content:

- setup status;
- provider/model fields;
- masked API key field;
- missing env/config hints;
- logging profile selector;
- diagnostics availability;
- primary action: `Save and check`;
- secondary actions: `Retry check`, `Export diagnostics`;
- safe explanation that secret values are never displayed.

### 5.2 Settings Route

Entry:

- first-run blocker `Configure settings`;
- Main Page utility/settings entry once Main Page is accessible;
- Diagnostics route support affordance when setup or export fails.

Product 1.0 route target:

```text
/settings
```

Required states:

- loading;
- ready/editable;
- degraded/warnings;
- save pending;
- save failed;
- disabled/unavailable sidecar;
- no-secret display after save.

### 5.3 Main Page Warning Integration

If readiness is `ready`, Main Page opens.

If readiness is `degraded`, Main Page still opens but should show a restrained
warning affordance. Examples:

- logging disabled;
- unknown logging profile fell back to default;
- diagnostics export unavailable.

This warning must not block session work.

---

## 6. API Contract

The Product 1.0 backend/API slice finalizes the frontend write contract in
[Settings first-run API contract](../../engineering/settings-first-run-api-contract.md).

Existing:

```text
GET /api/v1/settings/readiness
```

Accepted:

```text
GET /api/v1/settings/config
PATCH /api/v1/settings/config
POST /api/v1/settings/readiness/recheck
```

`GET /api/v1/settings/config` returns safe values only:

- provider;
- model;
- logging profile;
- diagnostic export availability;
- whether an API key is configured;
- never the API key value.

`PATCH /api/v1/settings/config` accepts:

- provider;
- model;
- optional API key replacement;
- logging profile.

Response:

- existing sidecar JSON envelope;
- updated safe config summary;
- refreshed readiness summary;
- product error metadata on failure.

Security rules:

- never echo secret values;
- do not log raw secret input;
- redact request bodies in diagnostic output;
- reject unsupported providers or invalid values with structured product
  errors;
- record config change evidence with hashes/summaries only when an audit slice
  accepts that event surface.

---

## 7. Implementation Slices

### F1 Plan And Contract Closure

Deliver:

- this frontend completion plan;
- technical design;
- backend API contract decision.

Acceptance:

- product scope is clear;
- no UI implementation starts with missing write API assumptions.

### F2 Settings API Client And Types

Deliver:

- frontend types for safe config read/save;
- API client methods;
- focused contract tests.

Acceptance:

- secret values are modeled as write-only input;
- read responses only expose booleans/safe summaries.

### F3 Settings Page Shell

Deliver:

- `/settings` route;
- setup/edit page layout;
- loading/error/disabled states;
- provider/model/logging controls;
- masked API key field;
- no persistence until API wiring is ready.

Acceptance:

- no one-off controls if shared primitives exist;
- no hardcoded API shapes in page code;
- mobile/tablet/desktop text does not overlap.

### F4 First-Run Blocker To Setup Flow

Deliver:

- first-run blocker primary action opens Settings setup surface;
- save/recheck loop;
- continue to Main Page when ready;
- route unavailable fallback.

Acceptance:

- blocked path does not start Main Page session work;
- successful save causes readiness recheck;
- no raw secrets appear in DOM, logs, or diagnostics.

### F5 Diagnostics And Recovery Actions

Deliver:

- export diagnostics action from setup failure state;
- product error recovery labels;
- support-safe bundle path display;
- retry behavior after failure.

Acceptance:

- diagnostic export uses existing export flow;
- setup failures show actionable, non-technical recovery guidance.

### F6 Degraded Readiness On Main Page

Deliver:

- non-blocking warning summary when readiness is degraded;
- Settings link from warning;
- tests for ready/degraded/blocking split.

Acceptance:

- degraded status does not block Main Page;
- warnings do not expose secrets or raw backend details.

### F7 E2E And Release Readiness

Deliver:

- sidecar E2E: unconfigured -> save -> ready -> Main Page;
- configured sidecar path remains covered;
- diagnostic export path remains covered;
- CI workflow continues to run the formal command.

Acceptance:

- `npm run test:e2e:sidecar` passes locally and in CI;
- browser/Electron release smoke remains listed separately.

---

## 8. Acceptance Criteria

The Settings first-run frontend feature is product-complete when:

1. unconfigured local sidecar opens a setup flow instead of a dead-end blocker;
2. the user can enter minimal provider/model/API-key settings in Plato;
3. saving settings updates local sidecar configuration without exposing the
   secret value;
4. readiness can be rechecked from the UI after save;
5. ready state continues to Main Page;
6. degraded state opens Main Page and shows a non-blocking warning;
7. setup failures show product recovery actions;
8. diagnostic export is reachable from setup failure states;
9. Audit/Diagnostics deep links remain usable when Main Page is blocked;
10. the formal sidecar E2E runner covers unconfigured, configured, and
    diagnostic export paths;
11. docs and gap registry mark exactly this frontend completion scope as
    accepted, without claiming the full centralized Settings system.

---

## 9. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Frontend ships a form before write APIs are stable | Gate F2/F4 on backend API contract closure. |
| Secret values leak through DOM, logs, or diagnostics | Treat secret input as write-only; add DOM/log/bundle assertions. |
| Settings scope expands into full runtime config | Keep Product 1.0 to LLM setup, logging profile, diagnostics handoff. |
| Users expect provider validation | Copy must say save checks local config only unless test-connection API exists. |
| Degraded warnings block work unnecessarily | Degraded is warning-only; only `firstRun.ready=false` blocks. |

---

## 10. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.

Task:
Finalize the Settings first-run frontend completion API contract and backend
write slice.

Context:
docs/plans/feature/settings-first-run-frontend-completion.md defines the
product-complete frontend experience. The current frontend blocker is read-only
and cannot be accepted as the full feature until settings save/recheck exists.

Scope:
1. Define safe settings config read/save contract.
2. Implement backend storage/write gateway for Product 1.0 LLM setup and
   logging profile only.
3. Ensure secret input is write-only and redacted from logs/diagnostics.
4. Refresh readiness after save.
5. Add contract tests.

Do not implement full centralized runtime configuration.
Do not expose stored secret values.
Do not run provider network validation unless a separate API is accepted.

Output:
- files changed
- tests run
- API contract implemented
- remaining frontend slices
```
