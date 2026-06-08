# Feature Plan: Workspace Entry And Root Semantics

> Status: W1 and W2 implemented
> Last Updated: 2026-06-08
> Gap: Product 1.0 desktop workspace entry and workspace-root semantics
> Engineering Contract: [Workspace Entry Contract](../../engineering/workspace-entry-contract.md)
> Related Plans: [Packaging and Electron Release Readiness](packaging-electron-release-plan.md), [Settings first-run frontend completion](settings-first-run-frontend-completion.md)
> Related Architecture: [WorkspaceLayout](../../architecture/), [UI and backend communication](../../architecture/ui-backend-communication.md)

---

## 1. Problem

Product 1.0 local unsigned RC can launch a desktop app, start the Python
sidecar, and reach Main Page. The missing product entry is workspace choice:
users should first choose the local workspace Plato will operate on.

Pre-W2 behavior was developer-oriented:

- CLI dev uses `--workspace ./plato-workspace`;
- packaged Electron defaults to `<userData>/workspace`;
- renderer enters Settings/Main Page without an explicit workspace choice;
- Agent tools wrote to a session-scoped project directory under the workspace.

Users expect a desktop app to ask "which workspace/project do you want to work
on?" before creating sessions or writing files.

---

## 2. Product Goal

For Product 1.0, the desktop entry is complete when a local user can:

1. open Plato;
2. see a Workspace Picker before Settings/Main Page when no workspace is
   selected;
3. choose a local folder as the current workspace;
4. let Electron main start the Python sidecar for that workspace;
5. continue into the existing Settings first-run or Main Page flow;
6. reopen a recent workspace without reselecting it from the file picker.

---

## 3. Scope

### W1: Workspace Picker

In scope:

- Electron main-owned current/recent workspace state.
- Native directory picker through preload IPC.
- Renderer Workspace Picker gate when workspace selection is required.
- Runtime config handoff after sidecar startup.
- Unit tests for Electron workspace store/selection and renderer picker.
- Keep mock/browser/HTTP dev flows working without native workspace IPC.

Out of scope:

- Changing Agent tool cwd.
- Moving session metadata.
- Workspace migration.
- Cloud login, authentication, or remote workspace sync.
- Multi-workspace sidecar process concurrency.

### W2: Workspace Root As Session Work Path

In scope and implemented:

- Change user project root to `<workspace>/`.
- Move session metadata under `<workspace>/.taskweavn/sessions/<session_id>/`.
- Make Agent tools use `<workspace>/` as cwd.
- Protect `.taskweavn` from normal tool access.
- Update Audit, Diagnostic Bundle, file evidence, and smoke fixtures.

Out of scope for W2:

- Multiple simultaneous sessions editing the same workspace.
- Cross-session conflict resolution.
- Full centralized runtime configuration.

---

## 4. W1 UX

Workspace Picker states:

| State | UI |
|---|---|
| loading | small desktop startup panel while preload state loads. |
| needs_selection | title, safe explanation, Open Workspace primary action, recent workspace list if any. |
| choosing | native picker is open or request is pending; actions disabled. |
| starting | selected workspace is accepted and sidecar is starting. |
| failed | safe error text and retry/open actions. |

The screen is app-like, not a marketing page. It should use the same restrained
Product 1.0 visual language as Settings/Main Page.

---

## 5. W1 Contract

Use [Workspace Entry Contract](../../engineering/workspace-entry-contract.md).

Important rules:

- Renderer must not call Electron APIs directly.
- Renderer must not start the sidecar.
- Electron main owns folder selection, persistence, sidecar start/restart, and
  startup diagnostics.
- The first W1 smoke gate can be opt-in through
  `PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION=1`.

---

## 6. W2 Path Decision

Current layout:

```text
<workspace>/
  .taskweavn/
  shared/
  sessions/<session_id>/.session/
  sessions/<session_id>/<session_id>/   # current Agent cwd
```

Target W2 layout:

```text
<workspace>/
  .taskweavn/
    workspace.sqlite
    sessions/<session_id>/
      events.sqlite
      thoughts.sqlite
      plan.md
      logs/
  user files written by Agent tools
```

The target keeps Product 1.0's "one local workspace" mental model while hiding
session internals under `.taskweavn`.

W2 must add explicit protection for `.taskweavn`. Without that protection,
moving Agent cwd to workspace root would expose private metadata and SQLite
stores to tools and prompts.

Implemented protection covers normal workspace tool path access:

- `read_file`, `write_file`, and `list_dir` reject direct `.taskweavn` access;
- root `list_dir` hides `.taskweavn`;
- `run_command` rejects `.taskweavn` as cwd and direct command text references.

This is a Product 1.0 tool policy guard, not a full OS sandbox. Stronger shell
isolation remains future sandbox hardening.

---

## 7. Acceptance Criteria

W1 acceptance:

- Electron can start without a persisted workspace and show Workspace Picker
  without launching a sidecar before selection.
- User can choose a workspace folder and proceed into existing Settings/Main
  Page flow.
- Recent/current workspace summaries are available through preload IPC.
- Mock/browser flows are unchanged.
- Startup diagnostics still work when sidecar startup fails after selection.

W2 acceptance:

- New sessions write user files directly under workspace root.
- Session metadata is hidden under `.taskweavn/sessions/<session_id>`.
- Agent tools cannot read/write `.taskweavn` through normal workspace tools.
- Audit, Diagnostics, result file summaries, Electron smoke, and sidecar E2E
  remain workspace-relative and redacted.

---

## 8. Recommended Next Slice

```text
Use the product-workflow-gate skill first.

Task:
Validate Workspace Picker + W2 root semantics in the next Product 1.0 acceptance
pass against a real selected workspace.

Scope:
1. Start Electron through the Workspace Picker.
2. Select a clean local workspace.
3. Run a task that writes a visible file at workspace root.
4. Verify .taskweavn is not visible through normal UI/tool surfaces.
5. Verify Audit/Diagnostics expose workspace labels, not absolute paths.

Do not add cloud auth or multi-workspace concurrency.
Do not expose raw absolute workspace paths in renderer diagnostics.

Output:
- acceptance result
- files/artifacts inspected
- remaining workspace gaps
```
