# Multi-Workspace API And Runtime Contract

> Status: accepted contract / implemented foundation
> Last Updated: 2026-06-09
> Related Plan: [Multi-Workspace API And Runtime Routing](../plans/feature/multi-workspace-api-runtime-routing.md)
> Related Contracts: [Workspace Entry Contract](workspace-entry-contract.md), [Workspace Main Page Switching Contract](workspace-main-page-switching-contract.md)
> Related ADR: [ADR-0017 Session And Workspace Context Management Foundation](../decisions/ADR-0017-session-and-workspace-context-management-foundation.md)

---

## 1. Purpose

This contract defines the backend and renderer-facing shape for a single local
Plato sidecar process that can address more than one local workspace.

The goal is not to run every workspace concurrently. The first target is:

```text
one Electron app
  -> one Python sidecar process
      -> many registered workspace roots
          -> workspace-scoped session catalogs and APIs
          -> one or more lazily opened workspace runtimes
```

This extends the existing Product 1.0 model where `WorkspaceLayout` stores
workspace-level SQLite files under `<workspace>/.plato/`, with sessions
isolated by `session_id`.

## 2. Core Decision

Multi-workspace support is primarily an API and runtime routing problem.

The sidecar does not need one OS process or thread per workspace for catalog
reads, session snapshots, command writes, or event replay. It needs an explicit
workspace identity in public API routes and an internal registry that maps that
identity to the correct `WorkspaceLayout` and stores.

The current single-workspace API remains valid as an active-workspace
compatibility surface until consumers migrate.

## 3. Definitions

| Term | Meaning |
|---|---|
| `workspaceId` | Opaque renderer-safe identifier for a registered workspace. It must not be a raw absolute path. |
| workspace root | Absolute local path used only inside Electron main and Python sidecar runtime. |
| workspace label | Renderer-safe display name, usually the folder basename or user-provided label. |
| workspace catalog | Safe list of registered workspaces and lightweight session summaries. |
| workspace runtime | Open set of workspace-scoped stores, gateways, event source, and optional dispatcher for one workspace. |
| active workspace | Workspace currently selected for command entry and compatibility APIs. |
| registered workspace | Workspace known to Electron and allowed to be routed by the sidecar. |

## 4. Ownership

| Concern | Owner | Rule |
|---|---|---|
| Native folder selection | Electron main | Renderer never reads raw paths. |
| Recent/current workspace persistence | Electron main | Electron persists roots and safe metadata. |
| Workspace root registry for sidecar | Electron main + sidecar launcher | Python receives an internal root map; renderer receives only safe summaries. |
| Workspace file/session stores | Python sidecar | `WorkspaceLayout` resolves all `.plato` paths. |
| Workspace runtime lifecycle | Python sidecar | Runtime registry opens/closes per-workspace stores lazily. |
| Visible workspace/session IA | Renderer | Displays Workspace -> Sessions. |
| Agent cwd | Python sidecar/runtime | A task runs with cwd equal to that workspace root. |

## 5. Workspace Registry Contract

Electron main owns the source of truth for selected/recent local workspace
roots. For multi-workspace sidecar routing, Electron must provide the Python
sidecar an internal registry containing:

```ts
type InternalWorkspaceRegistryEntry = {
  workspaceId: string;
  rootPath: string; // internal only; never renderer-facing
  label: string;
  isCurrent: boolean;
  lastOpenedAt: string | null;
};
```

The registry may be passed through a local manifest file or another
Electron-owned bootstrap channel. The implementation must ensure:

- renderer payloads never contain `rootPath`;
- diagnostics use safe labels or `workspace://<workspaceId>` style references;
- removed/missing workspace roots become `unavailable`, not fatal sidecar
  startup errors;
- workspace IDs remain stable across app restarts unless the workspace is
  removed from the registry.

## 6. Runtime Registry Contract

Python sidecar should introduce a `WorkspaceRuntimeRegistry` concept:

```text
WorkspaceRuntimeRegistry
  catalog: WorkspaceCatalogProvider
  get_runtime(workspaceId, purpose)
    -> WorkspaceRuntime
  close_idle()
  close_all()

WorkspaceRuntime
  workspaceId
  layout: WorkspaceLayout
  sessionManager: SessionManager
  messageStream / messageBus
  askStore
  taskBus
  rawTaskStore / draftStore / authoringStateStore
  resultSummaryStore
  uiEventSource
  queryGateway / commandGateway
  optional dispatcher / default agent
```

Rules:

- A runtime is keyed by `workspaceId`, not `sessionId`.
- Runtime construction must call `WorkspaceLayout(root)` for the routed root.
- Workspace-level SQLite files remain in that workspace's `.plato/` folder.
- `sessionId` is only unique inside a workspace. Public identity is
  `(workspaceId, sessionId)`.
- `.plato` protection applies independently to every workspace root.
- Closing one runtime must not close or corrupt another workspace runtime.
- Catalog reads may use a lightweight read-only path and do not need to start an
  agent dispatcher.

## 7. API Contract

### 7.1 Workspace Catalog

```http
GET /api/v1/workspaces
```

Response:

```json
{
  "currentWorkspaceId": "ws_current",
  "workspaces": [
    {
      "workspaceId": "ws_current",
      "label": "Taskweavn",
      "status": "available",
      "isCurrent": true,
      "sessionCount": 3,
      "recentSessions": [
        {
          "sessionId": "session-1",
          "name": "Product 1.0 RC",
          "status": "active",
          "updatedAt": "2026-06-08T12:00:00Z"
        }
      ],
      "updatedAt": "2026-06-08T12:00:00Z"
    }
  ]
}
```

`status` values:

```text
available | unavailable | starting | failed
```

Catalog responses must not include raw absolute paths.

### 7.2 Workspace Sessions

```http
GET /api/v1/workspaces/{workspaceId}/sessions
POST /api/v1/workspaces/{workspaceId}/sessions
PATCH /api/v1/workspaces/{workspaceId}/sessions/{sessionId}
DELETE /api/v1/workspaces/{workspaceId}/sessions/{sessionId}
```

Session lifecycle semantics match the current Main Page session lifecycle
contract, but all operations route through the selected workspace runtime.

### 7.3 Session Snapshot And Commands

```http
GET /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/snapshot
POST /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/commands
```

Rules:

- Command idempotency is workspace-scoped because the store lives under that
  workspace's `.plato/ui_commands.sqlite`.
- Renderer command state must key by `workspaceId + sessionId + commandId`.
- The command gateway must use the runtime for `workspaceId`; it must not fall
  back to the active workspace if the route contains a workspace ID.

### 7.4 Events

```http
GET /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/events?cursor=...
```

Rules:

- The route's `workspaceId` selects the `SqliteUiEventSource`.
- Cursors are workspace-local but renderer caches must key them by
  `workspaceId + sessionId`.
- Event payloads should include `workspaceId` once the UI contract is extended.
  Until then, the route context is authoritative.
- Unknown or stale cursors trigger the same `resync_required` behavior as the
  current single-workspace event source, scoped to the routed workspace.

### 7.5 Audit, Result, And Diagnostics

Workspace-scoped forms should be introduced for every session-addressed
surface:

```http
GET /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/audit
GET /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/diagnostics/export
GET /api/v1/workspaces/{workspaceId}/sessions/{sessionId}/results/{resultRef}
```

Existing active-workspace routes may remain as compatibility aliases, but new
renderer code should prefer workspace-scoped routes.

## 8. Error Contract

Use the existing `ApiError` top-level shape. Attach product metadata through
`ApiError.details`.

Required multi-workspace categories:

| Condition | Suggested category | Recovery action |
|---|---|---|
| Unknown workspace ID | `workspace_unavailable` | `open_workspace` |
| Workspace root no longer exists | `workspace_unavailable` | `open_workspace` |
| Workspace runtime failed to start | `workspace_runtime_failed` | `retry_check`, `export_diagnostics` |
| Session not found in workspace | `session_not_found` | `open_workspace` or `open_audit` when available |
| Command routed to unavailable workspace | `workspace_unavailable` | `open_workspace` |
| Event source unavailable | `event_stream_unavailable` | `retry_check` |

Error payloads must not expose:

- raw absolute paths;
- raw Python exceptions;
- prompts, provider payloads, secrets, logs, or SQLite payloads.

## 9. TaskBus And Dispatcher Semantics

No TaskBus schema change is required for the first multi-workspace API slice.
The DB file path provides workspace isolation:

```text
<workspace-a>/.plato/tasks.sqlite
<workspace-b>/.plato/tasks.sqlite
```

Inside each DB, tasks remain row-isolated by `session_id`.

The first implementation should not start execution dispatchers for every
registered workspace by default. Recommended policy:

| Mode | Behavior |
|---|---|
| catalog | Read workspace/session summaries only. No dispatcher. |
| active | Open stores and query/command gateways for selected workspace. |
| execution | Start dispatcher/default agent only for a session receiving execution commands. |
| multi-active execution | Deferred until explicit concurrency policy exists. |

## 10. Compatibility

Current active-workspace routes may remain:

```http
/api/v1/sessions/{sessionId}/...
```

Compatibility rules:

- They always resolve through `currentWorkspaceId`.
- They must be marked as active-workspace aliases in docs/tests.
- New frontend work should use workspace-scoped routes.
- Audit return links and diagnostic links should preserve `workspaceId` once
  route migration starts.

## 10.1 Implemented Slice Status

As of 2026-06-09, the accepted foundation implementation includes:

- internal `WorkspaceRegistryEntry` bootstrap input for local sidecar startup;
- one-process `WorkspaceRuntimeRegistry` with lazy per-workspace runtime
  construction;
- `GET /api/v1/workspaces` catalog responses with safe labels and recent
  session summaries;
- workspace-scoped session, snapshot, command, event, Audit, and diagnostic
  route aliases under `/api/v1/workspaces/{workspaceId}/sessions/...`;
- active-workspace compatibility routes under `/api/v1/sessions/...`;
- frontend HTTP client and Main Page state keyed by `workspaceId + sessionId`;
- Main Page workspace sidebar rows for all registered workspaces, including a
  desktop `Open or add workspace` entry that stays owned by Electron main.

Still deferred:

- concurrent execution policy across multiple active workspaces;
- inactive runtime eviction policy;
- full Audit page path migration away from session-only browser paths.

## 11. Test Contract

Focused contract tests should cover:

- catalog response omits raw paths;
- two workspaces can contain the same `sessionId` without cross-reading;
- workspace-scoped snapshot routes read from the correct `.plato` stores;
- workspace-scoped command routes write to the correct command/task stores;
- SSE subscription uses the routed workspace event source;
- unknown or missing workspace returns safe `ApiError.details`;
- active-workspace compatibility routes still resolve to the current workspace;
- diagnostics/export paths are redacted.

## 12. Open Questions

- Should `workspaceId` be generated by Electron only, or can Python derive it
  for CLI/dev workspaces?
- Should catalog responses include all sessions or only recent sessions plus a
  paged sessions endpoint?
- When should inactive workspace runtimes be closed?
- What UI policy should warn users before switching away from a workspace with
  running tasks?
- When Product 1.1 enables multi-workspace concurrent execution, what is the
  per-workspace and global dispatcher limit?
