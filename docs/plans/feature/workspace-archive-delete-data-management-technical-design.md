# Workspace Archive, Delete, And Settings Data Management Technical Design

> Status: draft technical design / implementation blocked until accepted
> Last Updated: 2026-06-11
> Plan: [Workspace Archive, Delete, And Settings Data Management](workspace-archive-delete-data-management.md)
> Decision: [ADR-0018](../../decisions/ADR-0018-workspace-archive-and-delete-semantics.md)

---

## 1. Design Summary

This design adds workspace lifecycle management without moving raw path
authority into the renderer or Python sidecar.

High-level ownership:

```text
Electron main
  owns raw workspace paths, app registry, archive/restore/delete, sidecar restart

Renderer
  owns Settings tab UI and safe summaries

Python sidecar
  owns currently opened workspace stores and workspace-scoped HTTP APIs
```

The two accepted user actions are:

```text
Archive workspace
Delete Plato data
```

Settings becomes:

```text
Settings
  Configuration
  Data Management
  Usage Information
```

---

## 2. App-Level Workspace Registry

Current Electron storage is:

```ts
type WorkspaceEntryStoreV1 = {
  currentPath: string | null;
  recentPaths: string[];
};
```

V2 should preserve backward compatibility and move toward records:

```ts
type WorkspaceEntryStoreV2 = {
  schemaVersion: 2;
  currentPath: string | null;
  workspaces: WorkspaceEntryRecord[];
};

type WorkspaceEntryRecord = {
  path: string;
  archived: boolean;
  addedAt: string | null;
  lastOpenedAt: string | null;
  archivedAt: string | null;
};
```

Rules:

- raw paths remain only in Electron main storage;
- renderer receives sanitized summaries;
- V1 files migrate in memory and write back as V2 on next mutation;
- duplicate paths collapse by normalized absolute path;
- archived records are retained past the normal recent-workspace cap;
- visible recent records keep the existing cap behavior.

Renderer-facing summary:

```ts
type WorkspaceEntrySummary = {
  id: string;
  name: string;
  label: string;
  pathLabel: string;
  isCurrent: boolean;
  lifecycleStatus: "active" | "archived";
  sessionCount?: number | null;
  updatedAt?: string | null;
};
```

`pathLabel` remains a safe label, not an absolute path.

---

## 3. Electron Preload Contract

Extend `window.platoElectronWorkspace`:

```ts
type WorkspaceLifecycleResult =
  | {
      status: "ok";
      state: WorkspaceEntryState;
    }
  | {
      status: "cancelled" | "failed";
      state: WorkspaceEntryState;
      error?: string;
    };

type WorkspaceEntryState = {
  status: "needs_selection" | "ready" | "starting" | "failed";
  currentWorkspace: WorkspaceEntrySummary | null;
  recentWorkspaces: WorkspaceEntrySummary[];
  archivedWorkspaces: WorkspaceEntrySummary[];
  error: string | null;
};

type DeleteWorkspaceDataOptions = {
  useTrash?: boolean;
};

type PlatoElectronWorkspaceBridge = {
  getState(): Promise<WorkspaceEntryState>;
  chooseWorkspace(options?: WorkspaceSelectionOptions): Promise<WorkspaceSelectionResult>;
  useWorkspace(id: string, options?: WorkspaceSelectionOptions): Promise<WorkspaceSelectionResult>;
  archiveWorkspace(id: string): Promise<WorkspaceLifecycleResult>;
  restoreWorkspace(id: string): Promise<WorkspaceLifecycleResult>;
  deleteWorkspaceData(
    id: string,
    options?: DeleteWorkspaceDataOptions,
  ): Promise<WorkspaceLifecycleResult>;
};
```

Rules:

- invalid ids return safe failed states;
- archived workspace ids cannot be selected by `useWorkspace` unless restored
  first;
- `chooseWorkspace` auto-restores if the chosen path matches an archived record;
- raw filesystem errors are mapped to safe text and product error metadata when
  surfaced through renderer state;
- Browser/mock mode must handle bridge absence.

---

## 4. Archive Flow

```text
Settings -> Data Management
  -> user chooses Archive workspace
  -> renderer calls archiveWorkspace(workspaceId)
  -> Electron main marks record archived
  -> if archived workspace is current:
       stop sidecar
       choose next visible workspace when available
       otherwise show Workspace Picker
     else:
       restart sidecar registry if needed
  -> renderer reloads or updates state
```

Catalog rules:

- archived workspaces are excluded from the sidecar registry passed to Python;
- archived workspaces are excluded from `GET /api/v1/workspaces`;
- archived workspaces remain visible in Settings Data Management through the
  Electron bridge.

Default for archiving the current workspace:

1. if another visible workspace exists, switch to the most recently opened one;
2. otherwise show Workspace Picker / entry state.

This keeps the app from showing a workspace the user just hid.

---

## 5. Restore Flow

```text
Settings -> Data Management -> Archived workspaces
  -> user chooses Restore
  -> renderer calls restoreWorkspace(workspaceId)
  -> Electron main marks record active
  -> if no current workspace exists:
       select restored workspace and start sidecar
     else:
       keep current workspace and refresh registry
```

Opening the same folder through the native picker must perform the same restore
before sidecar startup.

---

## 6. Delete Plato Data Flow

Delete targets:

```ts
const PLATO_DATA_DIRS = [".plato", ".taskweavn", ".code-agent"];
```

Flow:

```text
Settings -> Data Management
  -> user chooses Delete Plato data
  -> renderer shows confirmation copy
  -> Electron main validates id and path
  -> if target workspace has active sidecar/runtime:
       stop sidecar and close runtime first
  -> move Plato-owned metadata dirs to OS Trash when available
  -> if Trash is unavailable:
       fail safely in first implementation
       future slice may add permanent-delete second confirmation
  -> remove workspace record from registry
  -> if deleted workspace was current:
       switch to next active workspace or show Workspace Picker
```

First implementation should prefer OS Trash:

- macOS/Electron: `shell.trashItem(path)` for each existing metadata root;
- if Trash fails, return a safe failed result and do not partially update the
  registry unless all existing targets were removed;
- permanent recursive delete is deferred unless explicitly accepted.

The delete operation must never target:

```text
workspace root
.git
any path outside workspace root
any symlink-resolved target outside workspace root
```

Path policy:

- construct deletion paths from the stored workspace root plus fixed directory
  names only;
- reject path traversal and symlink escape;
- do not accept arbitrary renderer-provided paths.

Git local exclude:

- existing `.git/info/exclude` may contain `.plato/` from the Git
  initialization feature;
- first implementation should not edit `.git/info/exclude` because existing
  lines are not marker-owned;
- future work can add marker comments before safely removing Plato-owned lines.

---

## 7. Settings Tab Architecture

Current Settings route remains:

```text
/settings
```

Add tab query parameter:

```text
/settings?tab=configuration
/settings?tab=data
/settings?tab=usage
```

Fallback:

- missing or unknown `tab` selects `configuration`;
- first-run blocked setup also selects `configuration`;
- close behavior continues to respect `returnTo`.

Component boundary:

```text
SettingsRoute
  SettingsTabs
    ConfigurationTab
      existing Settings setup form
    DataManagementTab
      workspace lifecycle bridge state
    UsageInformationTab
      token usage summaries
```

Do not place cards inside cards. The tab body should use section bands or
unframed panels inside the existing Settings modal.

### Configuration Tab

Move existing Settings controls into this tab:

- provider;
- model;
- API key;
- logging profile;
- interface language;
- workspace Git initialization preference;
- save/recheck/continue buttons;
- diagnostics export action if still relevant to setup state.

### Data Management Tab

States:

| State | Behavior |
|---|---|
| bridge unavailable | show safe unavailable message and no destructive actions |
| loading | tab shell with loading rows |
| ready | show active/recent and archived workspaces |
| action pending | disable lifecycle buttons for the affected row |
| failed | show safe error text, no raw paths |
| empty archived | show empty state under Archived Workspaces |

Actions:

- `Archive` for active workspace rows;
- `Restore` for archived workspace rows;
- `Delete Plato data` for active and archived rows.

Destructive confirmation copy must say:

```text
This deletes Plato data for this workspace, including sessions, audit evidence,
usage records, settings, and diagnostics stored under .plato. It does not delete
your project files or the workspace folder.
```

### Usage Information Tab

Use the existing token usage API:

```text
GET /api/v1/workspaces/{workspaceId}/usage/token-summary
```

The tab may embed or refactor the existing Workspace Usage route component. The
important product change is navigation:

- Settings tab is the primary entry;
- Main Page no longer shows a first-level Usage button;
- deep route `/workspaces/{workspaceId}/usage` may remain for direct links,
  browser tests, and future diagnostics handoff.

---

## 8. Sidecar Runtime Updates

`buildSidecarWorkspaceRegistry(currentPath)` should read only active records.

When archive/delete changes the visible workspace set:

- if current workspace remains active, restart sidecar or refresh registry using
  the existing startup path;
- if current workspace is no longer active, stop sidecar and select fallback;
- if no active workspace remains, show workspace entry state.

The Python sidecar should not receive archived workspace roots.

---

## 9. Localization And Copy

Add UI text keys under existing catalogs:

```text
settings.tabs.configuration
settings.tabs.dataManagement
settings.tabs.usageInformation
workspace.actions.archiveWorkspace
workspace.actions.restoreWorkspace
workspace.actions.deletePlatoData
workspace.states.archived
workspace.states.noArchivedWorkspaces
workspace.messages.deletePlatoDataExplanation
workspace.messages.lifecycleUnavailable
usage.labels.usageInformation
```

Both `en-US` and `zh-CN` catalogs are required in the implementation slice.

---

## 10. Tests

### Electron Unit Tests

- V1 registry migrates to V2.
- Archive hides a workspace from active summaries.
- Restore returns an archived workspace to active summaries.
- Choosing an archived path auto-restores it.
- Delete targets only fixed Plato metadata dirs.
- Delete rejects symlink escape.
- Deleting current workspace selects fallback or entry state.

### Frontend Tests

- Settings renders three tabs.
- Configuration tab preserves existing setup behavior.
- Data Management tab shows active and archived workspace sections.
- Archive/restore/delete call bridge methods.
- Bridge unavailable state is safe.
- Usage Information tab loads token usage summaries.
- Main Page no longer renders a first-level Usage button.

### Integration / Smoke

- Electron smoke with seeded workspaces:
  1. archive secondary workspace;
  2. verify Main Page no longer shows it;
  3. restore from Settings;
  4. delete Plato data for a disposable workspace;
  5. verify project file remains and `.plato` is gone.

---

## 11. Implementation Slices

Recommended order:

1. Settings tab shell and route-state tests.
2. Workspace registry V2 and archive/restore IPC.
3. Data Management tab UI.
4. Delete Plato data IPC and safety tests.
5. Usage Information tab relocation and Main Page entry removal.
6. Electron smoke for archive/restore/delete.

Each slice should preserve first-run Settings behavior and existing workspace
switching behavior.

---

## 12. Risks

- Deleting `.plato` while SQLite handles are open can fail or corrupt cleanup.
  Stop/close sidecar before deleting current workspace data.
- Archived current workspace can leave renderer route state pointing to a now
  hidden session. Reload through fallback selection.
- Users may read "delete" as project deletion. Product copy must always say
  "Delete Plato data" and explicitly state project files are kept.
- OS Trash may fail in packaged contexts. First implementation should fail safe
  rather than permanently delete without a separately accepted policy.
