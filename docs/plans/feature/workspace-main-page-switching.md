# Feature Plan: Workspace-First Main Page Switching

> Status: accepted for W3 small implementation slice
> Last Updated: 2026-06-08
> Gap: Main Page cannot switch or add workspaces after startup
> Engineering Contract: [Workspace Main Page Switching Contract](../../engineering/workspace-main-page-switching-contract.md)
> Related Plans: [Workspace Entry And Root Semantics](workspace-entry-root-semantics.md)
> Related Contract: [Workspace Entry Contract](../../engineering/workspace-entry-contract.md)

---

## 1. Problem

Product 1.0 now starts from a selected local workspace and stores sessions under
that workspace. After entering Main Page, the user cannot switch to another
workspace or add/open a new workspace without restarting the app.

The visible Main Page IA also still says "Workflow" in places where the product
now behaves as a workspace-first desktop app. That creates a mismatch:

```text
Actual runtime: Workspace -> Sessions
Visible UI:     Project -> Workflow -> Session
```

## 2. Product Decision

For Product 1.0, Main Page should use this user-facing hierarchy:

```text
Workspace
  -> Sessions
      -> Plan / Tasks / Result / Audit
```

`Workflow` remains an internal/default mode in the backend snapshot for
compatibility. This slice must not remove or rename the backend `workflow`
field. It only removes user-visible Workflow navigation labels from Main Page.

## 3. Slice Scope

In scope:

- Main Page sidebar presents workspaces as parallel parent rows.
- The current workspace is expanded and shows sessions as child items under it.
- Recent workspaces are shown as sibling rows, not hidden in a dropdown.
- User can open or add a workspace from Main Page using the existing native folder
  picker bridge.
- User can switch to a recent workspace from Main Page.
- Switching delegates to Electron main, which owns sidecar restart and renderer
  reload.
- Visible "Workflow" labels in Main Page are replaced with "Workspace".
- Browser/mock mode degrades safely when the Electron workspace bridge is not
  available.

Out of scope:

- Deleting the backend `workflow` snapshot field.
- Cloud auth, remote workspace sync, or multi-workspace sidecar concurrency.
- Cross-workspace session migration.
- Running-task switch confirmation policy beyond a future documented gap.
- Full route migration away from `/projects/:projectId/workflows/:workflowId`.

## 4. UX States

| State | Behavior |
|---|---|
| bridge unavailable | Main Page may show the current workspace label if available, but switching is disabled/hidden. |
| ready | Current workspace is expanded; recent workspaces and open/add action are visible in the sidebar. |
| choosing | Native picker is open or IPC is pending; switch actions are disabled. |
| starting | Electron accepted a workspace and is starting the sidecar; Main Page shows a switching notice until reload. |
| failed | Safe error text is shown; raw absolute paths and sidecar errors are not exposed. |

## 5. Acceptance Criteria

- Main Page has an inline workspace list in the sidebar.
- Sessions are visually nested under the current workspace.
- Recent workspaces are visible as sibling workspace rows and can be selected
  directly.
- Current workspace name is visible when Electron runtime provides it.
- "Open or add workspace" from Main Page invokes `platoElectronWorkspace.chooseWorkspace`.
- Recent workspace selection invokes `platoElectronWorkspace.useWorkspace(id)`.
- Switching state does not expose raw absolute workspace paths.
- Main Page visible copy no longer presents "Workflow" as the primary user
  navigation object.
- Session create/rename/delete/switch behavior remains unchanged within the
  active workspace.

## 6. Future Gaps

- Add explicit confirmation when switching workspaces while tasks are running.
- Route migration from workflow-based contextual routes to workspace-scoped
  routes once backend and Audit return-link contracts are ready.
- Workspace-level context management and promoted session summaries remain
  governed by ADR-0017.
