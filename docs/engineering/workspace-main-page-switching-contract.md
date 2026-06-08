# Workspace Main Page Switching Contract

> Status: accepted for W3 small implementation slice
> Last Updated: 2026-06-08
> Related Plan: [Workspace-First Main Page Switching](../plans/feature/workspace-main-page-switching.md)
> Related Contract: [Workspace Entry Contract](workspace-entry-contract.md)

---

## 1. Purpose

This contract defines the small Product 1.0 bridge between Main Page and the
existing Electron-owned workspace entry lifecycle.

The goal is not to add a second workspace system. Main Page uses the same
preload bridge that the startup Workspace Picker already uses.

## 2. Ownership

| Concern | Owner | Rule |
|---|---|---|
| Workspace folder selection | Electron main | Renderer only calls preload IPC. |
| Recent/current workspace persistence | Electron main | Renderer receives summaries only. |
| Sidecar restart after workspace switch | Electron main | Renderer does not stop/start sidecars directly. |
| Session list after switch | Python sidecar for selected workspace | Renderer reloads with the new HTTP runtime. |
| User-facing Main Page IA | Renderer | Show Workspace -> Sessions; do not expose Workflow as navigation. |

## 3. Renderer Inputs

Main Page may receive:

```ts
type PlatoWorkspaceEntryRuntime = {
  bridge: PlatoElectronWorkspaceBridge | null;
  currentWorkspace: PlatoWorkspaceEntrySummary | null;
  isRequired: boolean;
};
```

The bridge shape remains:

```ts
type PlatoElectronWorkspaceBridge = {
  getState(): Promise<PlatoWorkspaceEntryState>;
  chooseWorkspace(): Promise<PlatoWorkspaceSelectionResult>;
  useWorkspace(id: string): Promise<PlatoWorkspaceSelectionResult>;
};
```

No new backend HTTP API is required for this slice.

## 4. Workspace Switch Flow

```text
User sees Main Page workspace list
  -> renderer calls bridge.getState()
  -> renderer displays current workspace and recent workspace summaries inline
  -> current workspace renders its sessions as children
  -> user selects a recent workspace row or Open/add workspace
  -> renderer calls useWorkspace(id) or chooseWorkspace()
  -> Electron main persists selected workspace
  -> Electron main starts/restarts the Python sidecar for that workspace
  -> Electron main reloads renderer with new apiBaseUrl/workspace runtime config
```

If selection is cancelled, the active Main Page remains unchanged.

If startup fails after selection, Electron main shows the existing startup
diagnostics surface.

## 5. Safety Rules

- Renderer-facing workspace labels must use safe summaries from Electron.
- Do not expose raw absolute workspace paths in Main Page, diagnostics links, or
  error text.
- Do not expose raw sidecar exceptions, logs, SQLite payloads, provider payloads,
  prompts, or secrets.
- Browser/mock mode must not assume Electron IPC exists.
- Backend `workflow` remains available in snapshot data for compatibility, but
  Main Page should not present it as the primary navigation label.

## 6. Product Copy Rules

For this slice:

- "Workflow sessions" becomes "Workspace sessions".
- Sidebar presents workspaces as parallel rows.
- The current workspace is expanded, with sessions indented underneath it.
- Recent workspaces are visible sibling rows, not hidden behind a dropdown.
- Sidebar section label "Workflow" becomes "Workspace".
- Top bar "Project / Workflow / Session" becomes "Workspace / Session".
- Existing detailed plan/task/session language stays unchanged.

Settings copy that says "Product 1.0 workflows" is outside this slice unless a
later Settings copy pass accepts it.

## 7. Test Contract

Focused tests should cover:

- Main Page renders the current workspace and can open the switcher.
- Open or add workspace calls `chooseWorkspace`.
- Recent workspace selection calls `useWorkspace(id)`.
- Switching state is visible and does not leak absolute paths.
- Existing session lifecycle actions continue to render.
