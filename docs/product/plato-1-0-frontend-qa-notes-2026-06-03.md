# Plato Product 1.0 Frontend QA Notes - 2026-06-03

> Status: P1 rerun pass for local sidecar HTTP first external user testing
> Runbook: [Plato Product 1.0 Frontend QA Runbook](plato-1-0-frontend-qa-runbook.md)
> Branch: `codex/product-1-0-frontend-qa`
> Environment: local sidecar HTTP mode

---

## 1. Summary

The Product 1.0 vertical loop is substantially working in local sidecar HTTP
mode:

```text
create session
  -> submit natural-language goal
  -> generate draft TaskTree
  -> select TaskNode
  -> append Task-scoped guidance
  -> publish TaskTree
  -> execute fixed-route tasks
  -> produce task results and file-change summaries
  -> open Audit Page
  -> inspect filters, records, detail, and disclosure
```

The first run found two P1 issues that needed to be fixed or explicitly
accepted before first external user testing:

1. Main Page does not reliably live-refresh after backend execution progresses,
   while still showing `Events live`.
2. Audit Page `Return` performs an SPA navigation to a valid Main Page URL but
   leaves the user on an `Audit unavailable` route state until manual reload.

Both P1s were fixed and rerun in a real browser execution environment against
local sidecar HTTP mode on 2026-06-03. No P0 issue was found in either run.

---

## 2. Environment

| Field | Value |
|---|---|
| Date | 2026-06-03 Asia/Shanghai |
| Tester | Codex |
| Branch | `codex/product-1-0-frontend-qa` |
| Runtime mode | local sidecar HTTP |
| Workspace path | `./plato-workspace` |
| Frontend URL | `http://127.0.0.1:5174/` |
| Sidecar URL | `http://127.0.0.1:52789` |
| Session ID | `e3e3bb55` |
| Session name | `QA Personal Website 2026-06-03` |

Vite automatically used `5174` because `5173` was already occupied.

---

## 3. Preflight

| Check | Result | Notes |
|---|---|---|
| Branch created | Pass | Created `codex/product-1-0-frontend-qa`. |
| Frontend tests | Pass | First run: `npm run test --prefix frontend`, 30 files, 212 tests passed. P1 rerun: 30 files, 214 tests passed. |
| Frontend build | Pass | `npm run build --prefix frontend`: TypeScript + Vite build passed. |
| Sidecar start | Pass | `uv run taskweavn plato-dev --workspace ./plato-workspace --sidecar-port 52789 --frontend-port 5173`. |
| Sidecar health | Pass | `GET /api/v1/health` returned `{"name":"Plato Sidecar","version":"0.1.0"}`. |
| Browser startup | Pass | Main Page loaded from local sidecar HTTP mode. |

Note: local shell HTTP requests to `127.0.0.1:52789` required sandbox
escalation. Browser-side runtime and sidecar process were healthy.

---

## 4. Scenario

Primary prompt:

```text
I want to build a simple personal website with a homepage, about section,
project showcase, and contact information.
```

Task-scoped guidance added to the first TaskNode:

```text
Use React with simple CSS and keep the homepage concise.
```

---

## 5. Main Page Results

| ID | Result | Evidence |
|---|---|---|
| QA-MP-001 | Pass | Main Page loaded real sidecar snapshot; TopBar, SideNav, workspace, detail panel, and input bar visible. |
| QA-MP-002 | Pass | `New` opened a create-session dialog; creating `QA Personal Website 2026-06-03` switched to a new empty session. |
| QA-MP-003 | Pass | Session-scoped input submitted the personal-website prompt; input entered disabled/submitting state and recovered. |
| QA-MP-004 | Pass | Draft TaskTree generated with five draft TaskNodes. |
| QA-MP-005 | Pass | First TaskNode became selected; Detail Panel and input scope changed to selected-task context. |
| QA-MP-006 | Pass | Task-scoped guidance updated the selected TaskNode summary and appeared in task-scoped messages. |
| QA-MP-007 | Pass | Publish started execution; tasks moved from draft to running/queued/done in backend state. P1 rerun verified Main Page event-driven refetch while the browser page stayed open. |
| QA-MP-008 | Not covered | No pending confirmation appeared in this scenario. |
| QA-MP-009 | Pass | Backend snapshot produced task result and file-change summary; reload showed file changes in the detail panel. |
| QA-MP-010 | Not covered | No recoverable error path was triggered in this scenario. |

Main Page generated session artifacts under:

```text
plato-workspace/sessions/e3e3bb55/
```

Generated project files observed:

```text
plato-workspace/sessions/e3e3bb55/e3e3bb55/index.html
plato-workspace/sessions/e3e3bb55/e3e3bb55/app.js
plato-workspace/sessions/e3e3bb55/e3e3bb55/styles.css
```

---

## 6. Audit Page Results

| ID | Result | Evidence |
|---|---|---|
| QA-AP-001 | Pass | Main Page `View audit` opened a task-scoped Audit Page with correct return context. P1 rerun verified `Return` performs SPA navigation back to Main Page. |
| QA-AP-002 | Pass | Filter rail showed counts for All, Confirmations, Actions, Risks, Files, Results, System, Config, and Logs. |
| QA-AP-003 | Pass | Evidence Timeline showed ordered records with timestamps and source categories. |
| QA-AP-004 | Pass | Selecting a file-change record opened detail with What happened, Why it matters, Evidence, Disclosure, sanitized evidence, and reserved links. |
| QA-AP-005 | Pass | Raw payload was hidden by default; partial reason was explicit; no raw payload was exposed. |
| QA-AP-006 | Pass | Audit counts updated while the page was open as execution progressed, showing runtime refetch behavior. |
| QA-AP-007 | Partial | Partial evidence / Warning / retryable state rendered correctly. A1-A14 mock parity was not rerun beyond the automated test suite. |

Audit Page correctly communicates that it is read-only:

```text
Audit is a read-only trust plane. It explains what happened without changing
the Task or session.
```

---

## 7. Cross-Page Results

| ID | Result | Evidence |
|---|---|---|
| QA-X-001 | Pass | P1 rerun loaded Audit Page, set an in-page browser marker, clicked `Return`, and verified the marker survived while URL changed back to `/sessions/{sessionId}?taskNodeId=...`. |
| QA-X-002 | Pass | P1 rerun opened Main Page before command execution, generated a TaskTree through real sidecar HTTP, and observed the already-open browser tab change from `No TaskTree yet` to `Draft ready` without manual reload. |
| QA-X-003 | Not covered | No task failure occurred in this scenario. |
| QA-X-004 | Not covered | No confirmation appeared in this scenario. |
| QA-X-005 | Pass | Browser reload on Main Page restored the latest backend snapshot and selected/running context. |

---

## 8. Visual And Accessibility Smoke

| Check | Result | Notes |
|---|---|---|
| Desktop workbench layout | Partial | In-app browser visible area was narrower than a full desktop viewport. Core regions remained reachable. |
| Laptop viewport | Partial | Browser plugin viewport control did not provide a reliable full 1280px visual frame; DOM remained readable and reachable. |
| Text overflow | Partial | TaskNode titles are heavily truncated after publish; readable enough for this run, but scannability is reduced. |
| Keyboard/accessibility | Not fully covered | DOM roles for buttons, links, regions, status, and detail panels are present. Full keyboard pass not executed. |
| Audit read-only framing | Pass | Read-only / Trust plane / No mutations labels visible. |

---

## 9. P0/P1 Issue List

### P0

None found in this run.

### P1-001 Main Page live refresh lags while showing Events live

Severity: P1

Current status: fixed and browser-verified in the 2026-06-03 rerun.

Observed behavior:

- After publishing, backend snapshot progressed to done/running states and
  produced result/file-change summaries.
- Main Page continued to show stale task statuses for a period while TopBar
  still showed `Events live`.
- Manual reload corrected the UI and loaded the latest backend snapshot.

Why it matters:

- Users may believe execution is stuck even though backend work is progressing.
- `Events live` becomes misleading if the UI is not applying/refetching the
  latest facts.

Acceptance target:

- Main Page should update from runtime events or mark itself stale /
  disconnected when event-driven refresh is not current.
- The UI should not continue to show `Events live` as a confidence signal when
  the displayed task state is stale.

Rerun evidence:

- Browser environment: headless Chrome CDP against `http://127.0.0.1:5174/`
  with local sidecar HTTP at `http://127.0.0.1:52789`.
- Session: `6265bbd2`, `QA Browser Live P1 1780421636`.
- Initial visible state in the already-open browser tab:

```text
Session: QA Browser Live P1 1780421636
New session
Events live
No TaskTree yet
```

- Command: `POST /api/v1/sessions/6265bbd2/task-tree/generate`.
- Command result: accepted, `draft task tree generated`.
- Browser result without manual reload:

```text
Session: QA Browser Live P1 1780421636
Draft ready
Events live
TaskTree
Draft Website Content
Design Page Layouts and Visual Style
Develop the Static Website
Review Website Content and Functionality
```

- Observed freshness latency: about 28 seconds from command start to visible
  browser update. This is acceptable for the current local QA environment, but
  still worth watching in future performance-oriented runs.

### P1-002 Audit Page Return requires manual reload

Severity: P1

Current status: fixed and browser-verified in the 2026-06-03 rerun.

Observed behavior:

- From Audit Page, clicking `Return` changed the URL to:

```text
/sessions/e3e3bb55?taskNodeId=6fcb706906f84a48b01ede18f92302ae
```

- The app still rendered:

```text
Audit unavailable
Invalid Audit Page route.
```

- Manual browser reload on that same URL rendered Main Page correctly.

Why it matters:

- The trust-plane round trip is broken in SPA navigation.
- Users can recover only by manual reload, which is not acceptable for a
  first external user test unless explicitly accepted.

Acceptance target:

- `Return` should transition to Main Page in-app without showing Audit
  unavailable.
- Main Page should preserve the returned session/task focus when possible.

Rerun evidence:

- Browser environment: headless Chrome CDP against the task-scoped Audit Page
  route.
- Audit URL:

```text
/sessions/6265bbd2/tasks/1e251c16f8764159bf6aa7511823fb44/audit?entry=from_task&returnFocus=task&returnSessionId=6265bbd2&returnTaskNodeId=1e251c16f8764159bf6aa7511823fb44
```

- Verification method: after Audit Page loaded, set
  `window.__platoQaReturnMarker = "set-on-audit-page"`, clicked `Return`,
  then checked the browser state.
- Result URL:

```text
/sessions/6265bbd2?taskNodeId=1e251c16f8764159bf6aa7511823fb44
```

- Result DOM: Main Page rendered immediately with `TaskTree`, the returned
  session, and selected task context.
- SPA evidence: `window.__platoQaReturnMarker` remained present after Return,
  proving the Return action did not force a full page reload.

---

## 10. Lower-Severity Observations

| Severity | Observation | Notes |
|---|---|---|
| P2 | Published TaskNode titles can degrade into long summaries and truncation. | The first node changed from `Create the homepage` to a truncated sentence. This reduces scan quality but did not block the flow. |
| P2 | Confirmation path untested. | The selected scenario did not produce a confirmation request. A dedicated confirmation scenario is still needed. |
| P2 | Recoverable error path untested. | No failure occurred in this run. Existing failed session/Retry UI was visible in another session but not exercised as part of the new QA session. |
| P2 | Full viewport QA incomplete. | In-app browser viewport was narrower than desktop/laptop targets, so visual QA should be rerun in a normal browser or packaged app. |

---

## 11. P1 Rerun

Date: 2026-06-03 Asia/Shanghai.

Execution mode:

```text
uv run taskweavn plato-dev --workspace ./plato-workspace --sidecar-port 52789 --frontend-port 5174
```

Checks rerun:

| Check | Result | Notes |
|---|---|---|
| Frontend tests | Pass | `npm run test --prefix frontend`: 30 files, 214 tests passed. |
| Frontend build | Pass | `npm run build --prefix frontend`: TypeScript + Vite build passed. |
| SSE transport tests | Pass | `uv run pytest tests/test_ui_sse_transport.py`: 9 tests passed. |
| Sidecar health | Pass | `GET /api/v1/health` returned `Plato Sidecar` `0.1.0`. |
| Main Page freshness | Pass | Already-open browser tab updated from empty TaskTree to draft TaskTree after real `task-tree/generate` command. |
| Audit Return SPA navigation | Pass | Audit Page `Return` preserved an in-page marker and rendered Main Page on `/sessions/{sessionId}?taskNodeId=...`. |

Browser tooling note:

- The in-app browser tab was able to render the app earlier in the run but
  became unstable while binding a tab handle for automated interaction.
- Final browser verification used local headless Chrome controlled via CDP.
  This still exercised the real Vite frontend and sidecar HTTP/SSE runtime,
  not jsdom or mocked frontend state.

## 12. Decision

Decision: P1 rerun pass for local sidecar HTTP first external user testing.

Rationale:

- Core vertical loop is real and mostly working.
- No P0 blocker was found.
- The two previously found P1 issues were fixed and verified in a browser
  against local sidecar HTTP mode.

Recommendation:

1. Treat this branch as ready for a first local Product 1.0 user test.
2. Add a second targeted scenario that forces a confirmation.
3. Add a third targeted scenario that verifies recoverable error / retry UX.
4. Continue monitoring Main Page event freshness latency in longer execution
   runs.

After those pass, Product 1.0 can move from internal QA to first external user
testing.

---

## 12. Follow-Up Candidate Slices

| Slice | Priority | Goal |
|---|---:|---|
| Fix Main Page runtime freshness indicator/refetch | P1 | Ensure Main Page task/result/file state stays current or explicitly stale. |
| Fix Audit Page Return SPA navigation | P1 | Return from Audit Page to Main Page without manual reload. |
| Confirmation-specific QA scenario | P1 | Force HITL confirmation and validate option submit/idempotency. |
| Recoverable error QA scenario | P1 | Trigger failure and validate retry/recovery affordance. |
| Full browser/Electron visual smoke | P2 | Validate desktop/laptop viewport outside the constrained in-app browser. |
