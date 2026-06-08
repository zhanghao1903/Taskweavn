# Feature Plan: Multi-Workspace API And Runtime Routing

> Status: draft plan / implementation not started
> Last Updated: 2026-06-08
> Gap: Main Page can show and switch workspaces, but backend APIs and runtime assembly remain single-workspace scoped
> Engineering Contract: [Multi-Workspace API And Runtime Contract](../../engineering/multi-workspace-api-runtime-contract.md)
> Related Plans: [Workspace Entry And Root Semantics](workspace-entry-root-semantics.md), [Workspace-First Main Page Switching](workspace-main-page-switching.md)
> Related ADR: [ADR-0017 Session And Workspace Context Management Foundation](../../decisions/ADR-0017-session-and-workspace-context-management-foundation.md)

---

## 1. Problem

Product 1.0 moved Plato toward this visible hierarchy:

```text
Workspace
  -> Sessions
      -> Task plan / execution / result / audit
```

The current runtime still behaves like this:

```text
Electron selected one workspace
  -> Python sidecar starts with one workspace root
      -> all /api/v1/sessions/... routes resolve inside that workspace
```

That is enough for Product 1.0 local RC, but it prevents a Codex-like sidebar
where multiple workspaces can be visible at the same time and each workspace
can show its sessions without restarting the app.

The storage model is already close to the target: `WorkspaceLayout` stores
workspace-level DB files under `<workspace>/.plato/`, and `TaskBus` /
messages / UI events are session-filtered inside that workspace. The missing
piece is explicit `workspaceId` routing and a sidecar runtime registry.

## 2. Product Decision

Use one local Python sidecar process to route requests across registered local
workspaces.

Do not start one process per workspace for the first version. Do not start
dispatchers or agent loops for every workspace just to render the sidebar.

The first product target is:

```text
show all registered workspaces
  -> show each workspace's session summaries
  -> route session reads/writes by workspaceId
  -> keep execution lazy and scoped to the active/commanded workspace
```

## 3. Scope

In scope:

- Define `workspaceId + sessionId` as the public identity for multi-workspace
  session APIs.
- Add workspace catalog semantics for renderer-safe workspace and session
  summaries.
- Plan a Python `WorkspaceRuntimeRegistry` that routes to the correct
  `WorkspaceLayout`, stores, gateways, event source, and dispatcher.
- Keep workspace roots internal to Electron/Python.
- Preserve current active-workspace routes as compatibility aliases during
  migration.
- Define event, command idempotency, diagnostics, audit, and result routing
  expectations.

Out of scope:

- Cloud auth or remote workspace sync.
- Multi-workspace concurrent agent execution as a default behavior.
- Cross-workspace session migration.
- Removing the backend `workflow` field.
- Full route migration in this planning slice.
- Exposing raw absolute paths in renderer diagnostics.

## 4. Slice Plan

### MW0: Contract Closure

Status: this plan.

Deliverables:

- Multi-workspace API/runtime contract.
- Feature plan with staged implementation order.
- Explicit non-goals for concurrent execution and cloud sync.

Acceptance:

- Contract identifies workspace-scoped routes and compatibility aliases.
- Plan separates catalog/read routing from execution concurrency.

### MW1: Workspace Catalog API

Goal: let Main Page render all registered workspaces and lightweight session
summaries without restarting sidecar.

Backend scope:

- Add internal workspace registry input from Electron launcher to Python
  sidecar.
- Add `GET /api/v1/workspaces`.
- Read each workspace's `workspace.sqlite` through `SessionManager` or a
  lightweight catalog reader.
- Return safe labels, availability status, session counts, and recent sessions.
- Do not start dispatchers or default agents for catalog reads.

Frontend scope:

- Replace Electron-only recent workspace display with catalog-backed workspace
  rows when HTTP runtime supports it.
- Keep existing Electron bridge fallback for browser/mock or compatibility
  mode.

Tests:

- Catalog omits raw paths.
- Missing workspace root appears as unavailable.
- Multiple workspaces with sessions render as parallel sidebar rows.

### MW2: Workspace-Scoped Session Query And Lifecycle API

Goal: route session reads and session lifecycle operations by workspace ID.

Backend scope:

- Add:

```http
GET /api/v1/workspaces/{workspaceId}/sessions
POST /api/v1/workspaces/{workspaceId}/sessions
PATCH /api/v1/workspaces/{workspaceId}/sessions/{sessionId}
DELETE /api/v1/workspaces/{workspaceId}/sessions/{sessionId}
GET /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/snapshot
```

- Implement `WorkspaceRuntimeRegistry.get_runtime(workspaceId, purpose="query")`.
- Ensure duplicate `sessionId` values in different workspaces do not collide.
- Preserve `/api/v1/sessions/...` as current-workspace aliases.

Frontend scope:

- Store selected session identity as `{ workspaceId, sessionId }`.
- Load snapshots through workspace-scoped routes when available.
- Keep current active-workspace path as fallback until route migration is
  complete.

Tests:

- Two workspaces with same session ID return different snapshots.
- Session create/rename/delete writes under the routed workspace.
- Compatibility route still uses current workspace.

### MW3: Workspace-Scoped Commands, Events, Audit, Results, Diagnostics

Goal: make the full Main Page/Audit flow workspace-routed.

Backend scope:

- Add workspace-scoped command endpoint.
- Add workspace-scoped SSE event endpoint.
- Add workspace-scoped audit/result/diagnostic routes or route aliases.
- Key command idempotency and renderer event cursors by `workspaceId +
  sessionId`.
- Keep `ApiError.details` redacted and product-action metadata intact.

Frontend scope:

- Use workspace-scoped command routes.
- Key Main Page state, event subscriptions, audit links, diagnostic links, and
  result refs by workspace/session identity.
- Preserve recovery labels and diagnostics export action behavior.

Tests:

- Command writes go to the correct workspace stores.
- Event subscription reads the correct workspace event source.
- Audit/evidence/diagnostic links carry workspace identity without raw paths.

### MW4: Execution Runtime Policy

Goal: decide whether multi-workspace execution should be active concurrently.

Default recommendation:

- Keep one active execution workspace/session at a time for the first
  implementation.
- Let catalog and query APIs cover inactive workspaces.
- Start dispatcher/default agent only when a command targets a workspace/session
  that needs execution.

Future policy questions:

- Global max running workspaces.
- Per-workspace dispatcher limits.
- User warning when switching away from a running workspace.
- How running-task status appears in the global workspace sidebar.

## 5. API Migration Strategy

Keep old active-workspace routes during migration:

```http
/api/v1/sessions/{sessionId}/...
```

Introduce canonical routes:

```http
/api/v1/workspaces/{workspaceId}/sessions/{sessionId}/...
```

Migration rule:

- new frontend code should prefer canonical workspace-scoped routes;
- existing tests may keep active-workspace routes until the fixture runner is
  updated;
- route aliases must be documented in contract tests;
- all renderer state should move toward `{ workspaceId, sessionId }` identity.

## 6. Acceptance Criteria

The multi-workspace foundation is accepted when:

- Main Page can show multiple registered workspaces and their sessions from one
  sidecar process.
- Selecting a session in workspace A reads workspace A stores.
- Selecting a session with the same ID in workspace B reads workspace B stores.
- Commands, event cursors, audit links, diagnostic links, and result refs are
  keyed by workspace/session identity.
- Renderer-facing payloads do not expose raw absolute paths.
- Inactive workspace catalog reads do not start agent loops.
- Existing Product 1.0 active-workspace flow remains compatible.

## 7. Risks And Assumptions

- The first implementation assumes Electron can provide Python a trusted local
  workspace registry with internal root paths.
- Workspace catalog reads may need paging once session counts grow.
- SQLite connections must be closed per workspace runtime to avoid stale file
  handles.
- Concurrent execution is intentionally deferred because it needs a separate
  user-facing policy and resource limit.
- UI route migration may touch Audit return links and diagnostic export URLs.

## 8. Recommended Implementation Prompt

```text
Use the product-workflow-gate skill first.

Task:
Implement MW1 workspace catalog API from
docs/plans/feature/multi-workspace-api-runtime-routing.md and
docs/engineering/multi-workspace-api-runtime-contract.md.

Scope:
1. Add internal workspace registry input for sidecar tests.
2. Add GET /api/v1/workspaces returning safe workspace/session summaries.
3. Read session summaries without starting dispatchers/default agents.
4. Add focused contract tests for path redaction, missing workspace, and
   duplicate session IDs across workspaces.
5. Do not change existing active-workspace /api/v1/sessions routes.

Do not implement concurrent multi-workspace execution.
Do not expose raw absolute workspace paths in renderer payloads.

Output:
- files changed
- tests run
- API contract implemented
- remaining MW2/MW3 gaps
```
