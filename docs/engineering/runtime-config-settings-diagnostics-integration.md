# Runtime Config Settings, Diagnostics, And Audit Integration

> Status: C7 design accepted; C7.1 diagnostics read model implemented.
> Related Plan:
> [Centralized Runtime Configuration](../plans/feature/centralized-runtime-configuration.md)
> Related Contracts:
> [Runtime Config Change Store](runtime-config-change-store.md),
> [Runtime Config Write API](runtime-config-write-api-contract.md),
> [Runtime Config ConfigBus](runtime-config-configbus-contract.md),
> [Settings First-Run API](settings-first-run-api-contract.md)
> Product Boundary:
> [Plato Settings, Logs, And Audit Boundary](../product/plato-settings-logs-audit-boundary.md)
> Last Updated: 2026-06-24

## 1. Purpose

C1-C6 made runtime configuration queryable, mutable through an internal service,
durably recorded, publishable through an internal ConfigBus, and partially
applicable for live-safe logging changes. C7 defines how those facts should
enter Settings, Diagnostics, and Audit without collapsing their product
responsibilities.

C7 must answer:

- which runtime config facts belong in Settings;
- which facts are Diagnostics-only;
- how Audit references config evidence;
- whether Settings can write runtime config before HTTP write routes exist;
- how Product 1.0 / 1.1 avoids exposing a giant raw config editor.

## 2. Source-Of-Truth Hierarchy

Runtime config surfaces must use this hierarchy:

1. `RuntimeConfigRegistry` owns supported keys, mutability, scopes, defaults,
   and restart metadata.
2. `RuntimeConfigResolver` owns effective value/source/status resolution.
3. `RuntimeConfigChangeStore` owns durable patch/change/snapshot facts.
4. `RuntimeConfigMutationService` owns validation and persistence.
5. `RuntimeConfigConfigBus` owns internal propagation facts.
6. Settings, Diagnostics, and Audit are read/write surfaces over those facts.

No route, UI component, Audit provider, or Settings form may invent runtime
config key names, source priority, mutability copy, or status labels.

## 3. Existing Settings Boundary

Product 1.0 already has a narrower Settings/first-run contract:

- LLM provider;
- LLM model;
- write-only API key;
- logging profile;
- readiness/recheck;
- diagnostics export availability.

That contract is intentionally not the full centralized runtime config editor.
It should remain stable while C7 introduces a broader runtime config surface.

The existing Settings config may keep owning first-run setup until runtime
config write routes, authorization, and UI copy are implemented. C7 must not
retrofit existing first-run writes through internal services without a route
contract.

## 4. Surface Responsibilities

| Surface | Runtime Config Role | Write Access |
|---|---|---|
| Settings | User-facing safe controls and pending-state copy. | Only through local HTTP write route after C7.3. |
| Diagnostics | Raw effective config, change history, snapshots, ConfigBus publication summaries. | Read-only in first C7 implementation. |
| Audit | Relevant effective config and config changes for a session/task/action. | Read-only evidence only. |
| Main Page | Shows selected effective behavior summary only when it affects current workflow. | No raw editor. |

## 5. Settings Control Policy

Settings must not expose every registry key. First implementation should split
keys into three groups.

### 5.1 Safe User Controls

Candidate keys for Product 1.1 Settings controls:

| Key | Scope | UI Treatment | Notes |
|---|---|---|---|
| `logging.level` | workspace/session | Select control. | `active` can apply live through C6.2. |
| `web.search_enabled` | workspace/session | Toggle. | Applies at next action; needs tool permission copy. |
| `safety.high_risk_confirmation` | workspace/session/task | Segmented control. | Requires careful copy; high-risk default should remain conservative. |
| `llm.request_timeout_seconds` | workspace/session | Numeric input. | Applies next LLM call; avoid provider validation. |

### 5.2 Existing First-Run Controls

These remain in existing Settings config until runtime config write routes and
secret boundaries are ready:

| Existing Control | Runtime Config Key Relationship |
|---|---|
| provider | Related to `llm.default_provider`. |
| model | Related to `llm.default_model`. |
| API key | Secret boundary; not ordinary runtime config patch. |
| logging profile | Related to `logging.profile`, but profile scope semantics remain deferred. |

### 5.3 Diagnostics-Only Keys

These should be visible but not editable in first Settings implementation:

- `agent_loop.default_max_steps`;
- `context_manager.*`;
- `execution_dispatcher.*`;
- `task_api.*`;
- `computer_use.*`;
- `debug.main_page_trace_*`;
- any `startup_only`, `migration_only`, process-only, secret, or
  agent-run-level key.

Reason: changing these values can alter runtime safety, restart behavior, or
execution reproducibility. They need operator/admin UX before ordinary Settings
editing.

## 6. Diagnostics Requirements

Diagnostics should expose:

1. Effective config snapshot by scope:
   - existing `GET /api/v1/runtime/config/effective`;
   - value, source, mutability, effective status, redaction.
2. Key explanation:
   - existing `GET /api/v1/runtime/config/explain?key=...`;
   - source layers and selected value.
3. Change history:
   - future `GET /api/v1/runtime/config/changes`;
   - accepted/rejected/no-op, actor, reason, hashes, rejected keys.
4. Snapshot lookup:
   - future `GET /api/v1/runtime/config/snapshots/{configHash}` only when
     Audit or diagnostics needs direct lookup.
5. ConfigBus diagnostics:
   - internal `RuntimeConfigBusDiagnosticsSnapshot`;
   - publication event/change IDs;
   - active/pending keys;
   - consumer results and failures.

Diagnostics may show raw key names and safe structured values. It must not show
secret payloads or provider credentials.

## 7. Audit Requirements

Audit should reference runtime config as evidence, not as an editor.

Audit records may include:

- `effective_config_snapshot`;
- `config_change`;
- `config_validation_rejected`;
- `config_bus_publication`, only when relevant to a live behavior claim.

Audit detail should show:

- config hash;
- scope;
- key names;
- source kind;
- effective status;
- actor/reason when a change exists;
- redacted value marker when applicable;
- link to Diagnostics for raw details.

Audit must not:

- show raw secrets;
- become the primary config history browser;
- offer edit controls;
- imply pending config changed an already-running agent.

## 8. HTTP Write Route Requirement

Settings runtime config writes must wait for the C5.5 HTTP write contract to be
implemented.

Reason:

- route boundary owns authorization;
- route boundary owns actor construction;
- route boundary owns idempotency conflict semantics;
- Settings UI needs response warnings and pending-state copy;
- direct frontend or Settings service calls to `RuntimeConfigMutationService`
  would bypass the accepted API contract.

Therefore:

- Diagnostics read-only work may proceed before write routes.
- Settings read-only effective config display may proceed before write routes.
- Settings runtime config mutation must wait for:
  - `PATCH /api/v1/runtime/config`;
  - `GET /api/v1/runtime/config/changes`;
  - route tests for accepted/rejected/no-op/idempotency conflict;
  - local-only authorization placeholder.

## 9. Implementation Sequence

### C7.1 Diagnostics Read Model

Status: implemented.

- Added `DefaultRuntimeConfigDiagnosticsGateway` in
  `src/taskweavn/server/runtime_config_diagnostics.py`.
- Added focused validation in
  `tests/test_runtime_config_diagnostics_gateway.py`.
- The internal diagnostics gateway combines:
  - effective config;
  - key explanation;
  - change list;
  - snapshot lookup;
  - ConfigBus diagnostics snapshot.
- No Settings UI.
- No HTTP write route.
- No Audit UI change.

### C7.2 HTTP Read Extension

Status: deferred.

- Expose scoped change list route.
- Add snapshot lookup route only if diagnostics or Audit needs it.
- Preserve existing read-only route behavior.

### C7.3 Runtime Config HTTP Write Route

Status: deferred.

- Implement `PATCH /api/v1/runtime/config`.
- Implement idempotency replay/conflict.
- Enforce local-only authorization placeholder.
- Keep `allowPartialAcceptance=false` by default.

### C7.4 Settings Runtime Config Controls

Status: deferred.

- Add a Settings runtime behavior section.
- Start with safe controls only.
- Show effective status copy after save:
  - applied now;
  - next action;
  - next LLM call;
  - next task;
  - next session;
  - restart required.
- Keep Diagnostics-only keys visible behind an advanced raw view, not editable.

### C7.5 Audit Evidence Projection

Status: deferred.

- Project config evidence refs into relevant Audit records.
- Link to Diagnostics for full details.
- Do not make Audit a config editor.

## 10. Acceptance Criteria

- Settings control scope is explicitly limited.
- Diagnostics can explain current effective config without exposing secrets.
- Audit can reference config evidence without owning config history.
- Runtime config writes are not implemented before the HTTP write boundary.
- App-specific automation behavior remains outside top-level runtime config.
- Pending statuses are preserved in UI/diagnostics copy.

## 11. Open Questions

1. Should `logging.profile` become session-only first, or should it stay in the
   existing Settings config until logging profile semantics are redesigned?
2. Should `safety.high_risk_confirmation` be exposed in Product 1.1 Settings,
   or remain a diagnostics-only policy until ASK/confirmation UI is complete?
3. Should Diagnostics expose ConfigBus publications through HTTP, diagnostic
   bundle export, or only in-process support tooling first?
4. Should Audit query runtime config snapshots directly by hash, or should
   task/action evidence refs resolve them through a narrower provider?
5. Should ordinary users ever edit `agent_loop` and `context_manager` budgets,
   or should they remain developer/operator controls?
