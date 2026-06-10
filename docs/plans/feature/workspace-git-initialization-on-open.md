# Feature Plan: Workspace Git Initialization On Open

> Status: implemented
> Last Updated: 2026-06-10
> Product Baseline: [Plato Product 1.1 Plan](../../product/plato-1-1-product-plan.md)
> Related Contracts: [Workspace Entry Contract](../../engineering/workspace-entry-contract.md), [Git, Diff, And File Viewer API Contract](../../engineering/git-diff-file-viewer-api-contract.md)
> Related Milestone: [Product 1.1 Workspace Inspection Milestone](product-1-1-workspace-inspection-milestone.md)

## 1. Purpose

Workspace Inspection can show status, file content, and diffs when the selected
workspace is a Git repository. For plain folders, the inspection API correctly
returns `not_git`, but that blocks the user from using diff-based trust surfaces
unless they manually initialize a repository.

This slice adds an explicit desktop preference:

```text
Initialize Git for opened workspaces
```

When enabled, Plato prepares a selected workspace for Git inspection as part of
workspace open/switch. The preference is off by default.

## 2. Product Decision

Default behavior stays conservative.

- Plato must not silently write `.git/` into arbitrary folders by default.
- Users can opt in from Settings.
- When opted in, opening or switching a workspace prepares Git before the Python
  sidecar starts.
- `.plato/` is added to Git's local exclude file, not to project `.gitignore`.

The `.plato/` metadata directory is local Plato state. Excluding it through
`.git/info/exclude` avoids polluting the user's project files.

## 3. Scope

In scope:

- Settings checkbox for the desktop preference.
- Git availability status in Settings.
- Electron preload bridge options for workspace selection.
- Electron main-owned Git preparation before sidecar startup.
- Safe `git --version`, repository detection, `git init`, and
  `.git/info/exclude` writes.
- Focused Electron and frontend tests.

Out of scope:

- Commit creation, staging, unstaging, branching, or remote configuration.
- Python sidecar initializing Git from inspection APIs.
- Writing `.gitignore`.
- Cloud/user account preference sync.
- Multi-workspace concurrent Git operations.

## 4. Ownership

| Concern | Owner | Rule |
|---|---|---|
| Settings checkbox | Renderer Settings UI | Stores a local desktop preference and passes it to workspace bridge calls. |
| Git availability check | Electron main | Uses controlled `git --version`; returns safe status only. |
| Workspace path and Git init | Electron main | Owns raw local paths and performs initialization before sidecar start. |
| Python sidecar inspection | Python sidecar | Continues to report `not_git`; never auto-initializes from read APIs. |
| `.plato` protection | Shared policy | `.plato/` remains hidden/protected from normal tools and excluded from Git. |

## 5. Settings UX

Settings should show a small workspace/Git section:

```text
Git availability
  Git available: git version 2.x.x
  or
  Git not found

[ ] Initialize Git for opened workspaces
```

Rules:

- The checkbox is disabled when Git status is `missing` or `failed`.
- The status text must be safe and must not expose raw stderr, exception text,
  absolute paths, shell command payloads, or environment variables.
- The checkbox persists as a renderer-local desktop preference until a broader
  centralized settings system is accepted.
- The preference controls future workspace opens/switches. It does not
  retroactively initialize the current workspace until the user reopens or
  switches to it.

## 6. Renderer Preference

Initial storage can match the UI language preference pattern:

```text
localStorage key: plato.workspaceGit.initializeOnOpen
value: "1" | "0"
```

Only the boolean preference is stored. No workspace path, Git output, command
result, or repository metadata is stored in renderer local storage.

Future migration target: Electron `app.getPath("userData")` or centralized
runtime configuration, if Product 1.1 introduces broader preference ownership.

## 7. Bridge Contract

Extend the Electron workspace bridge without changing HTTP sidecar routes:

```ts
type PlatoWorkspaceGitStatus = {
  status: "available" | "missing" | "failed";
  version?: string;
};

type PlatoWorkspaceSelectionOptions = {
  initializeGitOnOpen?: boolean;
};

type PlatoElectronWorkspaceBridge = {
  getGitStatus(): Promise<PlatoWorkspaceGitStatus>;
  getState(): Promise<PlatoWorkspaceEntryState>;
  chooseWorkspace(
    options?: PlatoWorkspaceSelectionOptions,
  ): Promise<PlatoWorkspaceSelectionResult>;
  useWorkspace(
    id: string,
    options?: PlatoWorkspaceSelectionOptions,
  ): Promise<PlatoWorkspaceSelectionResult>;
};
```

Renderer call sites:

- Workspace Picker: pass the current preference to `chooseWorkspace` and
  `useWorkspace`.
- Main Page workspace sidebar: pass the current preference to `chooseWorkspace`
  and `useWorkspace`.
- If the bridge method does not support options in an older runtime, frontend
  should continue to work because JavaScript ignores unused arguments.

## 8. Electron Main Git Preparation

Electron main should use `spawn` or `execFile` with fixed executable and
argument arrays. It must not shell-concatenate user input.

Capability check:

```text
git --version
```

Repository detection:

```text
git -C <workspace> rev-parse --is-inside-work-tree
```

Initialization:

```text
git -C <workspace> init
```

Local exclude path:

```text
git -C <workspace> rev-parse --git-path info/exclude
```

Exclude rule:

```text
.plato/
```

Preparation flow:

```text
select workspace path
  -> if initializeGitOnOpen is false:
       remember workspace and start sidecar
  -> getGitStatus()
  -> if Git is not available:
       return failed selection state with safe message
  -> check repository
  -> if not a repository:
       run git init
  -> resolve .git/info/exclude
  -> append .plato/ if absent
  -> remember workspace and start sidecar
```

Idempotency:

- Existing Git repositories must not be reinitialized.
- `.plato/` must not be duplicated in `.git/info/exclude`.
- Worktrees and nested repositories should be treated according to Git's
  `rev-parse --is-inside-work-tree` result for the selected path.

## 9. Error Rules

Git preparation failures are workspace-selection failures, not sidecar startup
failures.

Safe failure states:

| Condition | User-facing status |
|---|---|
| `git` executable missing | Git not found. Install Git to enable automatic workspace initialization. |
| `git --version` fails | Git availability check failed. |
| `git init` fails | Could not initialize Git for that workspace. |
| `.git/info/exclude` write fails | Could not update Git exclude rules for that workspace. |

Do not expose:

- raw stderr/stdout;
- absolute paths;
- environment variables;
- command-line payloads;
- raw exceptions;
- `.plato` file contents.

If the preference is disabled, Git preparation failures cannot occur because no
Git command runs. Non-Git workspaces continue to open normally and Workspace
Inspection returns `not_git`.

## 10. Test Plan

Electron unit tests:

- Git status reports `available` when `git --version` succeeds.
- Git status reports `missing` or `failed` safely when the executable is not
  usable.
- Option off: workspace selection does not run Git preparation.
- Option on + non-Git folder: `git init` runs and `.git/info/exclude` contains
  `.plato/`.
- Option on + existing Git repo: no duplicate init; `.plato/` exclude is
  present.
- Existing exclude entry is not duplicated.
- Git preparation failure returns a safe failed selection state and does not
  start sidecar.

Frontend tests:

- Settings renders Git availability and checkbox states.
- Checkbox persists renderer-local preference.
- Workspace Picker passes `initializeGitOnOpen`.
- Main Page workspace sidebar passes `initializeGitOnOpen`.

Acceptance:

- Manual Electron smoke with a plain folder:
  1. open Settings;
  2. confirm Git availability;
  3. enable initialization;
  4. open a plain workspace;
  5. confirm `.git/` exists and `.git/info/exclude` contains `.plato/`;
  6. confirm Workspace Inspection no longer reports `not_git`.

Repeatable command:

```bash
cd frontend
npm run electron:smoke:workspace-git
```

The command launches the Electron dev shell with a plain recent workspace,
enables the renderer-local preference, selects that workspace, and verifies
that `.git/info/exclude` contains `.plato/` without writing project
`.gitignore`.

## 11. Implementation Slices

### WG-1. Contract And Settings Surface

Status: implemented.

Deliver:

- docs and bridge types;
- Settings Git availability display;
- persisted renderer-local checkbox;
- frontend tests for preference passing.

### WG-2. Electron Git Preparation

Status: implemented.

Deliver:

- controlled Git command helper;
- `getGitStatus`;
- `prepareWorkspaceGit`;
- workspace selection integration;
- Electron tests.

### WG-3. Acceptance Smoke

Status: implemented.

Deliver:

- repeatable Electron smoke for non-Git workspace opt-in initialization;
- documentation of manual RC acceptance.

Implementation evidence:

- `npm run test`
- `npm run build`
- `npm run electron:smoke:workspace-git`

## 12. Open Questions

1. Should the first implementation immediately prepare the current workspace
   when the user toggles the setting on, or only apply to future workspace
   opens? Current decision: future opens only.
2. Should the preference eventually live in Electron userData instead of
   renderer local storage? Current decision: renderer-local first; migrate only
   if broader preference ownership is accepted.
