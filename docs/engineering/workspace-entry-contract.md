# Workspace Entry Contract

> Status: accepted for W1 and W2; implemented W3 Git initialization extension
> Last Updated: 2026-06-10
> Related Plan: [Workspace Entry And Root Semantics](../plans/feature/workspace-entry-root-semantics.md)
> Scope: Electron desktop workspace selection, safe renderer bridge, runtime handoff, W2 workspace-root execution semantics, and draft W3 Git initialization preference.

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
| Optional Git initialization | Electron main | W3: initialize Git only when the Settings desktop preference is enabled. |

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

type WorkspaceGitStatus = {
  status: "available" | "missing" | "failed";
  version?: string;
};

type WorkspaceSelectionOptions = {
  initializeGitOnOpen?: boolean;
};
```

Required methods:

```ts
window.platoElectronWorkspace.getState(): Promise<WorkspaceEntryState>
window.platoElectronWorkspace.chooseWorkspace(
  options?: WorkspaceSelectionOptions,
): Promise<WorkspaceSelectionResult>
window.platoElectronWorkspace.useWorkspace(
  id: string,
  options?: WorkspaceSelectionOptions,
): Promise<WorkspaceSelectionResult>
```

Draft W3 method:

```ts
window.platoElectronWorkspace.getGitStatus(): Promise<WorkspaceGitStatus>
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
       if initializeGitOnOpen option is true:
         verify Git availability
         initialize Git if the folder is not a repository
         ensure .plato/ is present in .git/info/exclude
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

---

## 8. W3 Git Initialization Boundary

Related plan: [Workspace Git Initialization On Open](../plans/feature/workspace-git-initialization-on-open.md).

W3 adds an explicit Settings-controlled desktop preference:

```text
Initialize Git for opened workspaces
```

Rules:

- The preference is off by default.
- Renderer stores only the boolean preference and passes it to
  `chooseWorkspace` / `useWorkspace`.
- Electron main owns raw workspace paths and Git preparation.
- Python sidecar inspection APIs remain read-only and never auto-initialize
  Git in response to status/diff/file viewer requests.
- Git commands must use fixed executable calls and argument arrays, not shell
  string concatenation.
- If Git is unavailable, Settings disables the preference and shows a safe
  status.
- If Git preparation fails while the preference is enabled, workspace selection
  returns a safe failed state and the sidecar is not started for that selection.

Preparation flow:

```text
select workspace path
  -> if initializeGitOnOpen=false:
       remember workspace and start sidecar
  -> run git --version
  -> run git -C <workspace> rev-parse --is-inside-work-tree
  -> if not a repository:
       run git -C <workspace> init
  -> run git -C <workspace> rev-parse --git-path info/exclude
  -> append .plato/ when absent
  -> remember workspace and start sidecar
```

The `.plato/` exclusion must be written to `.git/info/exclude`, not to
`.gitignore`, so Plato local metadata does not modify project-tracked files.
