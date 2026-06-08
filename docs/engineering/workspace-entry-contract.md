# Workspace Entry Contract

> Status: accepted for W1 and W2
> Last Updated: 2026-06-08
> Related Plan: [Workspace Entry And Root Semantics](../plans/feature/workspace-entry-root-semantics.md)
> Scope: Electron desktop workspace selection, safe renderer bridge, runtime handoff, and W2 workspace-root execution semantics.

---

## 1. Purpose

Product 1.0 needs a first desktop entry state before Settings and Main Page:
the user chooses which local workspace Plato should open.

This contract defines the W1 desktop Workspace Picker and the W2 workspace-root
execution semantics. Agent tools now treat the selected workspace root as the
project cwd; session-private metadata lives under `.plato`.

---

## 2. Ownership

| Concern | Owner | Rule |
|---|---|---|
| Native folder picker | Electron main | Renderer must request selection through preload IPC only. |
| Workspace path persistence | Electron main | Store recent/current workspace paths in app userData, not in renderer storage. |
| Python sidecar lifecycle | Electron main | Start or restart the sidecar only after a workspace is selected. |
| Renderer runtime config | Electron preload | Expose safe workspace summaries and sidecar runtime facts. |
| HTTP sidecar API | Python sidecar | No workspace selection HTTP API in W1. |

---

## 3. Renderer Bridge

Preload exposes `window.platoElectronWorkspace`.

```ts
type WorkspaceEntrySummary = {
  id: string;
  name: string;
  label: string;
  pathLabel: string;
  isCurrent: boolean;
};

type WorkspaceEntryState = {
  status: "needs_selection" | "ready" | "starting" | "failed";
  currentWorkspace: WorkspaceEntrySummary | null;
  recentWorkspaces: WorkspaceEntrySummary[];
  error: string | null;
};

type WorkspaceSelectionResult =
  | { status: "cancelled"; state: WorkspaceEntryState }
  | { status: "ready"; state: WorkspaceEntryState };
```

Required methods:

```ts
window.platoElectronWorkspace.getState(): Promise<WorkspaceEntryState>
window.platoElectronWorkspace.chooseWorkspace(): Promise<WorkspaceSelectionResult>
window.platoElectronWorkspace.useWorkspace(id: string): Promise<WorkspaceSelectionResult>
```

Optional future method:

```ts
window.platoElectronWorkspace.createWorkspace(): Promise<WorkspaceSelectionResult>
```

W1 can reuse `chooseWorkspace()` for both "Open Workspace" and "Create/Open
Folder" because the native directory picker lets users choose an existing or
newly created folder.

---

## 4. Runtime Config

`window.platoRuntimeConfig` remains the source for HTTP runtime configuration.
W1 adds safe workspace entry metadata:

```ts
type PlatoRuntimeConfig = {
  apiBaseUrl?: string;
  apiMode?: "mock" | "http";
  appVersion?: string;
  disableEvents?: boolean;
  sessionId?: string | null;
  startupId?: string;
  workspaceEntryRequired?: boolean;
  workspace?: WorkspaceEntrySummary | null;
};
```

Rules:

- If `workspaceEntryRequired=true`, the renderer shows Workspace Picker and
  must not render Main Page, Settings, Audit, or Diagnostics routes.
- When the sidecar becomes ready for a selected workspace, Electron main
  reloads the renderer with `apiMode=http`, `apiBaseUrl`, and
  `workspaceEntryRequired=false`.
- Absolute workspace paths are not displayed by default. `pathLabel` should be
  a safe local label, such as the basename or `workspace://current`.
- Startup diagnostics may still include `workspace://current`; raw absolute
  paths remain redacted in user-facing surfaces.

---

## 5. Electron Main Behavior

Startup algorithm for W1:

```text
Electron starts
  -> load persisted workspace state
  -> if explicit PLATO_ELECTRON_WORKSPACE exists:
       select it and start sidecar
     else if current persisted workspace exists:
       select it and start sidecar
     else if PLATO_ELECTRON_ALLOW_DEFAULT_WORKSPACE=1:
       use the package/dev default workspace and start sidecar
     else:
       load renderer in workspace picker mode
  -> after selected workspace is known:
       start Python sidecar with --workspace <selected path>
       inject HTTP runtime config
```

Product default is workspace selection when no persisted workspace exists.
`PLATO_ELECTRON_ALLOW_DEFAULT_WORKSPACE=1` is a test/developer compatibility
escape hatch for explicit default-workspace smoke paths.
`PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION=1` remains a deterministic smoke
flag and wins over the default-workspace escape hatch.

---

## 6. Error Rules

- Native picker cancellation returns `status="cancelled"` with the unchanged
  state.
- Invalid or inaccessible workspace selection returns `status="failed"` and a
  safe message.
- Sidecar startup failure after a selected workspace still uses the existing
  startup diagnostics surface.
- Renderer must not expose raw exception, prompt, provider payload, log payload,
  SQLite payload, or secret values.

---

## 7. W2 Boundary

W2 workspace root semantics:

- user project files live directly under `<workspace>/`;
- session metadata moves under `<workspace>/.plato/sessions/<session_id>/`;
- Agent tool cwd becomes `<workspace>/`;
- `.plato` is protected from normal tool reads/writes.

Normal tool protection includes filesystem tool path rejection, hidden root
directory listing for `.plato`, and direct `.plato` shell command/cwd
rejection. This is not a full OS sandbox; shell hardening remains future
defense-in-depth work.
