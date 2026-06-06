# Plato Product 1.0 Frontend QA Runbook

> Status: draft QA runbook
> Last Updated: 2026-06-06
> Scope: Product 1.0 Main Page + Settings first-run + Audit Page frontend user-path validation.
> Related:
> [MVP PRD](plato-mvp-prd.md),
> [Main Page UX Flow](plato-main-page-ux-flow.md),
> [Audit Page PRD](plato-audit-page-prd.md),
> [Audit Page UX Flow](plato-audit-page-ux-flow.md),
> [Frontend Technical Design](plato-frontend-technical-design.md),
> [UI API Contract](plato-ui-api-contract.md),
> [Audit Page Contract](../engineering/audit-page-contract.md),
> [Gap Registry](../gaps/README.md)

---

## 1. Purpose

This runbook turns the current Product 1.0 status into a concrete frontend QA
path.

The current judgement is:

```text
The Product 1.0 vertical user loop is basically wired.
Remaining work is validation, polish, recovery hardening, and release readiness.
```

This document does not declare Product 1.0 released. It defines how to verify
whether the current frontend is ready for a first real user test.

---

## 2. Product 1.0 User Loop Under Test

Product 1.0 is validated only if this user-visible loop works:

```text
User opens Plato
  -> completes Settings first-run setup when local config is missing
  -> creates or selects a Session
  -> enters a natural-language goal
  -> sees a TaskTree
  -> selects a TaskNode
  -> adds Task-scoped guidance
  -> publishes / executes the task tree
  -> responds to a confirmation when needed
  -> sees task progress, result, and file change summary
  -> opens Audit Page from Main Page
  -> understands what happened and why it is trustworthy
```

The user should not need to understand:

- Agent internals;
- TaskBus internals;
- EventStream / MessageStream internals;
- SQLite storage;
- LLM provider details;
- raw logs or raw payloads.

---

## 3. QA Environments

| Environment | Purpose | Expected command / setup | Exit criteria |
|---|---|---|---|
| Mock frontend | Fast UI regression and scenario parity. | `cd frontend && npm run test`; optional Vite mock mode without `VITE_PLATO_API_MODE=http`. | Main Page and Audit Page mock scenarios still render and tests pass. |
| Formal sidecar E2E | Product 1.0 frontend integration acceptance and CI gate. | `cd frontend && npm run test:e2e:sidecar`. CI runs the same command in `.github/workflows/product-1-0-frontend-integration.yml`. | Real sidecar fixtures validate Diagnostic Bundle export plus Settings first-run configured and unconfigured save/recheck paths. |
| First-run manual smoke | Product setup acceptance without manually copying sidecar env vars. | `cd frontend && npm run dev:sidecar:first-run`. Optional Vite args can be passed after `--`, such as `npm run dev:sidecar:first-run -- --port 5174`. | Browser opens `/` in HTTP mode, shows first-run setup required, opens Settings as a large Main Page modal, saves Settings, rechecks readiness, and reaches Main Page. |
| Local sidecar HTTP | Main Product 1.0 runtime validation. | `uv run taskweavn plato-dev --workspace ./plato-workspace`. | Browser can complete the user loop through local HTTP/SSE. |
| Direct sidecar + frontend | Debug mode when ports/env need inspection. | `uv run taskweavn plato-sidecar --workspace ./plato-workspace`; then run Vite with printed env vars. | Frontend can load `GET /api/v1/sessions/{sessionId}/snapshot` and receive events. |
| Packaged browser/Electron | Release-readiness smoke. | TBD packaging command. | Same user loop works outside developer-only setup. |

Product 1.0 QA should not pass solely on mock mode.

---

## 4. Preflight Checklist

Before manual QA:

- `git status --short --branch` is clean or the changed files are intentional.
- `cd frontend && npm run test` passes.
- `cd frontend && npm run build` passes.
- `cd frontend && npm run test:e2e:sidecar` passes for the formal sidecar
  frontend integration acceptance path.
- Backend focused tests for the touched runtime area pass when a backend change
  is part of the release candidate.
- `uv run taskweavn plato-dev --workspace ./plato-workspace` starts both the
  sidecar and frontend.
- For Settings first-run acceptance, `cd frontend && npm run dev:sidecar:first-run`
  starts an unconfigured sidecar and Vite without manual env copying.
- Settings visual acceptance verifies that `/settings` is an in-app modal over
  the Main Page/first-run background, the outside background remains visible,
  and the panel itself carries the frosted blur treatment.
- The browser can reach the frontend dev URL.
- The sidecar health endpoint is reachable.
- The frontend console has no startup crash.
- Any known unrelated failure is recorded in the QA notes before testing.

CI acceptance:

- The GitHub Actions workflow `Product 1.0 Frontend Integration` runs
  `npm run test:e2e:sidecar` on relevant pull requests, pushes to `main`, and
  manual dispatch.
- This CI path uses deterministic sidecar fixtures and does not require real
  LLM provider secrets.

---

## 5. Test Data Policy

Use small, concrete tasks. Avoid vague prompts that make failures hard to
classify.

Recommended primary scenario:

```text
I want to build a simple personal website with a homepage, about section,
project showcase, and contact information.
```

Optional secondary scenarios:

1. Ask for a small documentation refresh.
2. Ask for a simple HTML/CSS page generation.
3. Ask for a task that should need user confirmation before file writes.

Do not use broad multi-agent or Product 1.1 scenarios for Product 1.0 QA.

---

## 6. Main Page QA Cases

### QA-MP-001 Open Main Page

| Item | Expectation |
|---|---|
| Action | Open Plato in local sidecar HTTP mode. |
| Expected UI | TopBar, SideNav, Session workspace, Detail Panel, and input bar are visible. |
| Expected API | Main Page snapshot request succeeds. |
| Pass criteria | User can identify current project/workflow/session, and the page is not stuck in loading/error. |

### QA-MP-002 Create Or Select Session

| Item | Expectation |
|---|---|
| Action | Select an existing session or create a new session if the UI exposes creation. |
| Expected UI | Session list selection changes; local selection state resets safely. |
| Expected API | Session snapshot query is keyed by `sessionId`. |
| Pass criteria | Old session details do not leak into the new session view. |

### QA-MP-003 Author Goal

| Item | Expectation |
|---|---|
| Action | Enter the primary natural-language scenario in the input bar. |
| Expected UI | Input enters pending/submitting state and then returns to usable state. |
| Expected API | Command request is sent through the UI gateway / sidecar API. |
| Pass criteria | A draft TaskTree or clear recoverable error is shown. |

### QA-MP-004 Review TaskTree

| Item | Expectation |
|---|---|
| Action | Inspect generated TaskNodes. |
| Expected UI | TaskNodes have readable titles, summaries, status badges, and hierarchy. |
| Expected API | Snapshot/result state is not locally fabricated after command completion. |
| Pass criteria | User can explain what tasks the system plans to do. |

### QA-MP-005 Select TaskNode

| Item | Expectation |
|---|---|
| Action | Click a TaskNode. |
| Expected UI | Selected node is visibly highlighted; Detail Panel changes to TaskNode context; input scope changes to selected task. |
| Expected API | No unnecessary write command is sent for simple selection. |
| Pass criteria | User understands that future input is Task-scoped. |

### QA-MP-006 Add Task-Scoped Guidance

| Item | Expectation |
|---|---|
| Action | With a TaskNode selected, enter guidance such as "Use React and keep the page simple." |
| Expected UI | Task-scoped message/projection updates or the task card reflects the new guidance. |
| Expected API | Command is scoped to the selected task/session. |
| Pass criteria | Session-level and task-level input semantics are not confused. |

### QA-MP-007 Publish Or Execute

| Item | Expectation |
|---|---|
| Action | Publish / execute the task tree when the UI enables it. |
| Expected UI | TaskNodes move through pending/running/done or failure states. |
| Expected API | TaskBus execution lifecycle is driven by backend state, not direct UI mutation. |
| Pass criteria | User can tell whether work is queued, running, done, or failed. |

### QA-MP-008 Confirmation Handling

| Item | Expectation |
|---|---|
| Action | When a confirmation appears, choose an available option. |
| Expected UI | Confirmation card shows context, options, pending state after click, then resolved state. |
| Expected API | Confirmation command is sent once; duplicate clicks are blocked or idempotent. |
| Pass criteria | User understands what is being authorized and sees the result of the decision. |

### QA-MP-009 Result And File Change Summary

| Item | Expectation |
|---|---|
| Action | After execution, inspect the result and file change summary. |
| Expected UI | Result summary and file changes are visible from the selected/completed TaskNode; parent nodes roll up child file changes. |
| Expected API | File summary comes from deterministic observed facts. |
| Pass criteria | User can answer "what changed?" without opening raw logs. |

### QA-MP-010 Recoverable Error

| Item | Expectation |
|---|---|
| Action | Trigger or inspect a failed command/task path. |
| Expected UI | Error is user-readable and offers a recovery path when supported. |
| Expected API | Error response uses the contract shape and does not crash the page. |
| Pass criteria | User knows whether to retry, edit input, inspect audit, or stop. |

---

## 7. Audit Page QA Cases

### QA-AP-001 Enter From Main Page

| Item | Expectation |
|---|---|
| Action | Click `View audit` / audit entry from Session or Task context. |
| Expected UI | Audit Page opens with correct scope and return context. |
| Expected API | Audit snapshot route is called for session/task scope. |
| Pass criteria | User understands that Audit Page is read-only trust evidence, not a control plane. |

### QA-AP-002 Overview And Filters

| Item | Expectation |
|---|---|
| Action | Use audit filters such as confirmations, files, actions, config, logs. |
| Expected UI | Counts, selected filter, and record list remain readable. |
| Expected API | List records query respects scope/filter where applicable. |
| Pass criteria | User can narrow evidence without losing context. |

### QA-AP-003 Record Ordering

| Item | Expectation |
|---|---|
| Action | Compare record order after task execution or confirmation resolution. |
| Expected UI | Timeline order is stable and explainable. |
| Expected API | Ordering is backend/projected, not reconstructed from raw frontend guesses. |
| Pass criteria | The user can follow "what happened first, then next". |

### QA-AP-004 Record Detail

| Item | Expectation |
|---|---|
| Action | Select an audit record. |
| Expected UI | Detail panel shows summary, actor/source, severity, verdict, completeness, and related refs. |
| Expected API | Detail query succeeds or falls back to snapshot detail when appropriate. |
| Pass criteria | User can understand the selected evidence without raw internal objects. |

### QA-AP-005 Sanitized Payload Disclosure

| Item | Expectation |
|---|---|
| Action | Open records/evidence with hidden, partial, redacted, or requested payload disclosure. |
| Expected UI | Hidden/partial/redacted states are explicitly labeled; sensitive payloads are not shown by default. |
| Expected API | Sanitized disclosure is generated at request time and not stored as a separate durable payload. |
| Pass criteria | User sees enough context to trust the result without exposing raw sensitive evidence. |

### QA-AP-006 Live Refresh

| Item | Expectation |
|---|---|
| Action | Keep Audit Page open while execution, confirmation, config/log, or event source changes occur. |
| Expected UI | Live refresh/stale/disconnected status is visible and non-disruptive. |
| Expected API | Runtime events trigger refetch or resync through the audit event router. |
| Pass criteria | User can tell whether audit information is current. |

### QA-AP-007 Boundary States

| Item | Expectation |
|---|---|
| Action | Validate A1-A14 mock parity scenarios and at least one real HTTP scenario. |
| Expected UI | Loading, empty, partial, stale, permission denied, query error, and evidence load error states render without overlap or crashes. |
| Expected API | Error states preserve return path and do not mutate task state. |
| Pass criteria | The Trust Plane remains usable even when evidence is incomplete. |

---

## 8. Cross-Page QA Cases

| ID | User path | Pass criteria |
|---|---|---|
| QA-X-001 | Main Page selected TaskNode -> Audit Page task scope -> back/return | Scope and selection context remain coherent. |
| QA-X-002 | Main Page execution event -> Audit Page live refetch | Audit Page updates or marks itself stale without manual reload. |
| QA-X-003 | Task failure -> Main Page error/result -> Audit detail | User can move from failure summary to supporting evidence. |
| QA-X-004 | Confirmation resolved -> Audit confirmations filter | Confirmation record appears or refetch state explains delay. |
| QA-X-005 | Browser refresh on Main Page or Audit Page | Session route can reload from backend state; no required hidden in-memory state is lost. |

### 8.1 Targeted Confirmation And Retry Fixtures

Use this slice when the primary Product 1.0 scenario does not naturally produce
a pending confirmation or failed Task.

The preferred verification path is:

1. start local sidecar HTTP mode with a clean workspace;
2. create a session through `POST /api/v1/sessions`;
3. inject workspace-backed fixture facts into the same stores used by the
   running sidecar:
   - an actionable `AgentMessage` tied to an existing Task;
   - a failed published Task with `canRetry: true`;
4. verify the snapshot before commands;
5. resolve confirmation through
   `POST /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond`;
6. retry the failed Task through
   `POST /api/v1/sessions/{sessionId}/tasks/{taskNodeId}/retry`;
7. verify the snapshot after commands;
8. open the frontend route and confirm the visible Main Page state reflects
   the final backend facts.

Pass criteria:

- pending confirmation appears in `pendingConfirmations`;
- resolving confirmation returns `ok: true`, clears the pending confirmation,
  and adds a response message;
- failed Task exposes retry permission before retry;
- retry returns `ok: true`, clears `errorRef`, changes execution back to
  pending/queued, and records the retry instruction;
- frontend HTTP mode renders the final queued/retry state and confirmation
  response history.

Coverage boundary:

- This validates sidecar HTTP, persistence-backed projection, command handling,
  and frontend rendering for confirmation/retry.
- This does not prove that the normal LLM/user workflow naturally creates a
  confirmation or recoverable failure. Record that separately as exploratory
  QA.

---

## 9. Responsive And Visual Checks

Minimum Product 1.0 manual viewports:

| Viewport | Purpose | Pass criteria |
|---|---|---|
| Desktop `1440x1024` | Primary workbench layout. | TopBar, SideNav, workspace, detail panel, and input bar align; no text overflow in normal sample data. |
| Laptop `1280x800` | Common developer laptop size. | Core task path remains usable without horizontal page loss. |
| Tablet `1024x768` | Narrower but still product-relevant view. | Layout remains reachable; Audit detail can be inspected. |
| Below minimum width/height | Overflow fallback. | Scrollbars appear rather than broken overlap. |

Mobile-specific Audit Page polish below `960px` is not a Product 1.0 release
blocker unless mobile users are included in the first test group.

---

## 10. Accessibility Smoke

Minimum checks:

- Keyboard can reach major navigation, TaskNode cards, action buttons, filters,
  record cards, and close/back controls.
- Focus-visible states are visible.
- Loading/error/live status text is not purely color-coded.
- Confirmation actions are button-like and reachable by keyboard.
- Audit Page live/stale/disconnected feedback uses readable text.
- Text does not overflow its container in the normal Product 1.0 sample data.

---

## 11. Console, Network, And Log Checks

During HTTP-mode QA, record:

- browser console errors;
- failed network requests;
- duplicate command submissions;
- SSE disconnect/reconnect behavior;
- sidecar startup logs;
- session log/archive presence when logging is enabled;
- any frontend logs posted back to the sidecar.

Console warnings are not automatically blockers, but the tester must classify
them before the run is accepted.

---

## 12. Pass / Fail Criteria

### 12.1 Release-candidate pass

The frontend is ready for first external user testing when:

1. preflight tests and build pass;
2. the primary scenario completes in local sidecar HTTP mode;
3. Main Page can show TaskTree, selected TaskNode, guidance, execution status,
   result, and file summary;
4. Audit Page can open from Main Page and show scope, overview, records,
   details, disclosure states, and live/stale state;
5. recoverable error paths do not crash the page;
6. at least desktop and laptop viewports pass;
7. all P0/P1 issues from the run are either fixed or explicitly accepted as
   non-blocking for the next test group.

### 12.2 Blocking failures

Block release/user testing if any occur:

- user cannot open Main Page;
- user cannot enter a goal;
- generated or loaded TaskTree is unreadable;
- publish/execute action silently fails;
- confirmation action can be double-submitted with conflicting result;
- Audit Page cannot load from a valid Main Page link;
- hidden/raw evidence is exposed when it should be sanitized;
- browser refresh loses required persisted session state;
- a normal user path requires direct SQLite/log/manual backend inspection.

---

## 13. Issue Severity

| Severity | Meaning | Examples |
|---|---|---|
| P0 | Blocks first user test. | Main Page crash, invalid session route, unsafe evidence exposure, command cannot complete. |
| P1 | Blocks confident Product 1.0 release candidate. | confusing confirmation, broken Audit return path, stale state invisible, result missing after success. |
| P2 | Usability or polish issue. | typography mismatch, minor spacing issue, low-priority text overflow in rare content. |
| P3 | Later improvement. | mobile layout polish, richer result cards, advanced filters. |

---

## 14. QA Notes Template

```text
Date:
Tester:
Branch / commit:
Environment:
Browser:
Workspace path:
Sidecar base URL:
Session ID:

Scenario:

Preflight:
- frontend test:
- frontend build:
- sidecar start:
- console startup:

Main Page result:
- QA-MP-001:
- QA-MP-002:
- QA-MP-003:
- QA-MP-004:
- QA-MP-005:
- QA-MP-006:
- QA-MP-007:
- QA-MP-008:
- QA-MP-009:
- QA-MP-010:

Audit Page result:
- QA-AP-001:
- QA-AP-002:
- QA-AP-003:
- QA-AP-004:
- QA-AP-005:
- QA-AP-006:
- QA-AP-007:

Cross-page result:
- QA-X-001:
- QA-X-002:
- QA-X-003:
- QA-X-004:
- QA-X-005:

Issues:
- [severity] title:

Decision:
- pass / conditional pass / fail

Follow-up:
```

---

## 15. Known Product 1.0 Gaps To Watch

These are known gaps. QA should observe them, but not silently expand Product
1.0 scope.

| Gap | QA stance |
|---|---|
| Richer timeline orchestration | Watch for confusing order or missing evidence; do not require full timeline service unless a Product 1.0 path is blocked. |
| Broader evidence coverage | Verify current EventStream/log/config/confirmation coverage; record missing evidence as partial/not_available if safe. |
| Message and confirmation UI hardening | Treat confusing or unsafe confirmation behavior as P0/P1. |
| Recoverable error UX | Treat missing user recovery on common failures as P1. |
| Settings release smoke | Settings first-run frontend completion is accepted. Use `npm run dev:sidecar:first-run` for manual regression; Browser/Electron smoke remains under release readiness. |
| Diagnostic bundle | Needed for early testers, but can be a separate release-readiness task. |
| Packaging / Electron | Required before non-developer users; not required for local developer smoke. |
| Mobile-specific Audit polish | Defer unless mobile is included in the first user test group. |

Product 1.1 items such as result packaging cards, routing/assignment
productization, skills, MCP, file/multimodal support, and advanced `task_after`
pipelines are outside this runbook.

---

## 16. Recommended Next Execution Slice

Recommended next task:

```text
Use the product-workflow-gate skill first.

Task:
Run Product 1.0 frontend QA against docs/product/plato-1-0-frontend-qa-runbook.md.

Scope:
- local sidecar HTTP mode;
- one primary personal-website scenario;
- Main Page QA-MP-001 through QA-MP-010;
- Audit Page QA-AP-001 through QA-AP-007;
- cross-page QA-X-001 through QA-X-005;
- desktop 1440x1024 and laptop 1280x800 smoke.

Output:
- QA notes using the template in the runbook;
- P0/P1 issue list;
- whether first external user testing is allowed;
- gaps that should become the next implementation slice.
```
