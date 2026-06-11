# Feature Plan: Workspace Archive, Delete, And Settings Data Management

> Status: completed Product 1.1 workspace archive/delete data management slice
> Last Updated: 2026-06-11
> Owner: Desktop / Frontend / Local Runtime
> Decision: [ADR-0018 Workspace Archive And Delete Semantics](../../decisions/ADR-0018-workspace-archive-and-delete-semantics.md)
> Technical Design: [Workspace Archive, Delete, And Settings Data Management Technical Design](workspace-archive-delete-data-management-technical-design.md)
> Related Contracts: [Workspace Entry Contract](../../engineering/workspace-entry-contract.md), [Multi-workspace API Runtime Contract](../../engineering/multi-workspace-api-runtime-contract.md), [Token Usage Analytics Contract](../../engineering/token-usage-analytics-contract.md)

---

## 1. Problem

Product 1.1 Main Page can show multiple workspaces and sessions, but users have
no way to manage workspace lifecycle after adding folders.

The current sidebar can accumulate stale or low-priority workspaces. At the same
time, Plato creates product-owned local metadata under `.plato`, plus legacy
roots such as `.taskweavn` and `.code-agent` in older workspaces. If the product
creates these files, the product also needs a clear cleanup path.

The product must avoid a three-word lifecycle model. The accepted decision is:

```text
Archive workspace
Delete Plato data
```

There is no separate "remove workspace" user action.

---

## 2. Product Goals

1. Let users hide a workspace from normal Main Page focus without losing data.
2. Let users restore archived workspaces from Settings.
3. Let users delete Plato-owned metadata from a workspace while preserving user
   project files.
4. Keep raw absolute paths out of renderer diagnostics and normal UI.
5. Provide a first-level Workspace Management entry that opens Settings -> Data
   Management.
6. Expose workspace row context-menu actions for archive and delete.
7. Move token usage browsing into Settings -> Usage Information.
8. Remove the Main Page first-level Token Usage / Workspace Usage button.

---

## 3. Product Semantics

### 3.1 Archive Workspace

User-facing text:

```text
Archive workspace
```

Meaning:

- hide the workspace from Main Page;
- keep user files and `.plato`;
- make the workspace recoverable from Settings;
- automatically restore when the same folder is opened again.

Archive is reversible.

### 3.2 Delete Plato Data

User-facing text:

```text
Delete Plato data
```

Meaning:

- delete Plato-owned metadata roots from that workspace;
- remove the workspace from normal and archived workspace lists;
- keep the workspace folder and all user project files;
- keep `.git` and repository content.

Delete is destructive for Plato state and requires explicit confirmation.

Delete targets:

```text
<workspace>/.plato/
<workspace>/.taskweavn/     # legacy, if present
<workspace>/.code-agent/    # legacy, if present
```

Delete must not touch:

```text
<workspace>/
<workspace>/.git/
user project files
```

---

## 4. Workspace Management Entry And Settings IA

Workspace management gets a first-level entry from Main Page or the workspace
sidebar:

```text
Workspace Management -> /settings?tab=data
```

The entry is not a separate page. It is a direct route into the Settings Data
Management tab so workspace cleanup and restore remain in one management
surface.

Workspace rows also expose a context menu with fast actions:

```text
Archive workspace
Delete Plato data
```

The context menu must have a keyboard-accessible equivalent through a row
actions button or the Data Management tab. Right-click must not be the only way
to archive or delete.

Settings remains a large modal route, but becomes a tabbed surface.

```text
Settings
  Configuration
  Data Management
  Usage Information
```

### Configuration Tab

Contains existing setup controls:

- provider;
- model;
- API key secret input;
- logging profile;
- interface language;
- workspace Git initialization preference.

### Data Management Tab

Contains:

- current workspace summary;
- recent workspace summaries;
- archived workspace summaries;
- Archive action for non-archived workspaces;
- Restore action for archived workspaces;
- Delete Plato data action for any known workspace summary.

When the Electron workspace bridge is unavailable, this tab shows a safe
unavailable state instead of pretending it can manage local folders.

### Usage Information Tab

Contains token usage analytics:

- Workspace totals;
- Session breakdown;
- Plan/Task breakdown when a session is selected;
- cache hit-rate visibility;
- unknown usage call count.

Main Page no longer exposes a first-level Usage button. It may keep contextual
Task/Plan usage facts inside detail panels only if they are not a route-level
navigation entry.

---

## 5. Slice Plan

### A1. Plan, Decision, And Technical Design

Status: completed.

- Accept two user-facing lifecycle actions.
- Define Settings tab IA.
- Define Electron-owned workspace registry changes.
- Define token usage entry relocation.

### A2. Settings Tab Shell

Goal: split Settings into three tabs without changing existing setup behavior.

Status: completed.

Acceptance:

- `/settings` opens the same modal surface.
- Configuration tab contains all existing controls.
- Data Management and Usage Information tabs render safe empty/loading states.
- Locale catalogs cover tab names and empty states.
- First-run setup behavior is unchanged.

### A2.5 Workspace Management Entry

Goal: make workspace management discoverable as a first-level action.

Status: completed.

Acceptance:

- Main Page/sidebar exposes a Workspace Management entry.
- The entry opens `/settings?tab=data`.
- The entry is available even when no workspace row context menu has been
  opened.
- Browser/mock mode either opens the mock Settings tab or shows a safe
  unavailable state.

### A3. Workspace Archive / Restore

Goal: add reversible workspace hiding.

Status: completed.

Acceptance:

- Workspace rows can be archived from the row context menu and from Settings
  Data Management.
- Archived workspaces disappear from Main Page sidebar/catalog after reload.
- Archived workspaces appear in Settings Data Management.
- Restore makes the workspace visible again.
- Opening the same folder through Open/Add auto-restores it.
- No raw absolute path is shown in renderer UI.

### A4. Delete Plato Data

Goal: clean product-owned local metadata.

Status: completed.

Acceptance:

- Delete action is available from the row context menu and from Settings Data
  Management.
- Confirmation text names `.plato`/Plato data and explicitly says project files
  are not deleted.
- Current workspace delete stops/restarts sidecar or returns to workspace
  selection safely.
- Deleted workspace disappears from normal and archived lists.
- `.plato` and legacy metadata roots are removed from the workspace when
  deletion succeeds.
- User project files and `.git` remain untouched.

### A5. Usage Information Tab

Goal: make Settings the primary token usage entry.

Status: completed.

Acceptance:

- Usage Information tab loads existing token usage summaries.
- Main Page no longer has a first-level token usage statistics button.
- Existing `/workspaces/{workspaceId}/usage` deep route may remain for links and
  tests, but is not a primary navigation surface.
- Browser/mock mode has fixtures for the Usage Information tab.

### A6. Acceptance / E2E

Goal: cover the desktop lifecycle paths.

Status: completed for the Product 1.1 local acceptance path.

Acceptance:

- Electron smoke covers archive, restore, and delete Plato data for seeded
  workspaces.
- Settings tabs are covered by frontend tests.
- Deleting current workspace data does not leave the renderer on a broken
  workspace route.

---

## 6. Out Of Scope

- Deleting the workspace root folder.
- Cloud workspace lifecycle.
- Multi-user permissions.
- Cross-device archive sync.
- Permanent deletion policy when OS Trash is unavailable.
- Full billing, budget, or quota enforcement for token usage.
- A separate top-level Usage page outside Settings.
- A separate standalone Workspace Management page outside Settings.

---

## 7. Closure Decisions And Follow-Ups

Closed for this slice:

1. Delete Plato Data removes product-owned metadata directly after explicit
   confirmation; it does not delete user project files or `.git`.
2. Archived workspace summaries use app-registry metadata and do not require
   reading archived `.plato` stores for normal rendering.
3. Settings tab navigation stays in-app and does not refresh the renderer.
4. Archiving the current workspace updates the visible workspace list without
   requiring an application restart.
5. Workspace Management remains a first-level sidebar entry, while workspace
   row context menus provide fast Archive and Delete Plato Data actions.

Future follow-up:

- Add richer Electron smoke coverage if release-readiness expands beyond the
  current local acceptance path.
