# Plato Product 1.1 Real Local QA Report - 2026-06-11

> Status: phase complete - Electron app evidence pass; defect fixes merged
> QA branch: `codex/product-1.1-qa-hardening`
> Closure branch: `codex/product-1.1-qa-report-closure`
> Baseline commit: `616bc1b`
> Merged main commit: `08cd72b`
> Scope: Product 1.0 core loop and Product 1.1 feature hardening
> Environment policy: use the real local runtime, Electron app shell, and configured LLM provider; do not use mock mode or browser-only UI as acceptance evidence.

## Objective

Validate and harden Plato Product 1.0 and Product 1.1 in a real local
environment.

Required outcomes:

- QA巡检 1.0 基本功能；
- QA巡检 1.1 新特性；
- confirmed product defects get GitHub issues and PR fixes;
- UX issues or improvement suggestions are recorded in an improvement list;
- final QA report records evidence, gaps, and release risk.

## Source Documents

- [Product 1.0 Frontend QA Runbook](plato-1-0-frontend-qa-runbook.md)
- [Product 1.1 Plan](plato-1-1-product-plan.md)
- [Workspace-Aware Agent Foundation](plato-1-1-workspace-aware-agent-foundation.md)
- [Product 1.1 Workspace Inspection Milestone](../plans/feature/product-1-1-workspace-inspection-milestone.md)
- [Git, Diff, And File Viewer API Contract](../engineering/git-diff-file-viewer-api-contract.md)
- [Token Usage Analytics](../plans/feature/token-usage-analytics.md)
- [Precision File Tools](../plans/feature/precision-file-tools.md)

## Real Electron Environment

Electron app path:

```bash
PLATO_ELECTRON_USER_DATA_DIR=/private/tmp/plato-electron-product-qa-userdata.Y1NiH8 \
PLATO_ELECTRON_UI_LOCALE=zh-CN \
npm run electron:dev -- --workspace /private/tmp/plato-electron-product-qa.Y1NiH8 --renderer-port 65321
```

Electron-owned sidecar:

- Base URL: `http://127.0.0.1:52257`
- Workspace ID: `05cc0db4f9ae1924`
- Real QA workspace: `/private/tmp/plato-electron-product-qa.Y1NiH8`
- Session ID: `a9460a80`
- LLM: real configured provider; token usage recorded by sidecar.

## QA Scope Matrix

| Area | Requirement | Evidence | Status |
|---|---|---|---|
| 1.0 startup | Open Plato from a real local app/runtime path. | Electron app launch with Electron-owned sidecar `52257`. | Pass |
| 1.0 first-run/settings | Missing config shows setup path; configured path reaches Main Page. | `npm run electron:smoke:first-run` rerun after fix; first-run setup returned to Main Page. | Pass |
| 1.0 session loop | Create/select session, enter goal, generate/review TaskTree. | `02`, `03`, `04` Electron screenshots; real LLM Draft ready. | Pass |
| 1.0 task control | Select TaskNode, publish/execute, stop running task. | `05`, `06`, `07` Electron screenshots. | Pass |
| 1.0 confirmation/ASK | Authoring ASK and Execution ASK are understandable and scoped. | `03` Authoring ASK and `06` Execution ASK screenshots. | Pass |
| 1.0 result/files | Result summary and file changes are visible after work. | Stop result visible in `07`; file-change completion not reached before token guard stop. | Partial |
| 1.0 Audit Page | Main Page -> Audit Page works and stays read-only. | `11` Electron Audit screenshot. | Pass |
| 1.0 recovery | Recoverable errors show safe labels and no raw internal payloads. | Stop/Retry recovery visible in Electron; command failure smoke remains automated coverage. | Partial |
| 1.1 workspace inspection | Git status, changed files, file viewer, and structured diff work on a real repo. | API smoke plus `08`, `09` Electron screenshots. | Pass |
| 1.1 path safety | Renderer/API do not expose raw absolute paths; `.plato` is protected. | Workspace labels use `workspace://05cc0db4f9ae1924`; protected metadata API returns safe bad request. | Pass |
| 1.1 token usage | Real LLM activity records and displays usage summaries. | Usage API recorded 24 calls / 472,771 total tokens; `10` screenshot. | Pass |
| 1.1 precision file tools | Line-range read/search/replace/append work with drift/idempotency guards. | `uv run pytest tests/test_precision_file_tools.py`; Electron task did not complete mutation stage. | Pass for tool layer, UI integration partial |
| 1.1 diagnostics | Diagnostics include redacted usage/inspection descriptors. | API export passed in sidecar run; Electron UI route visible through Audit handoff. | Partial |

## Electron App Screenshot Index

Screenshots are stored separately under:

```text
docs/product/qa-screenshots/2026-06-11-product-1-1-electron-app/
```

| File | Evidence |
|---|---|
| `01-electron-empty-session.png` | Electron app empty workspace/session state. |
| `02-electron-session-goal-input.png` | Created session and goal input state. |
| `03-electron-authoring-ask.png` | Agent asks planning clarification questions while generating the plan. |
| `04-electron-draft-ready-after-ask.png` | Draft plan generated after Authoring ASK answers. |
| `05-electron-published-running.png` | Published plan and running TaskNode state. |
| `06-electron-execution-ask.png` | Execution ASK when the Agent lacks required app location information. |
| `07-electron-stop-requested.png` | User stop request result/retry state. |
| `08-electron-workspace-inspection-status.png` | Workspace inspection changed-file status in Electron app. |
| `09-electron-workspace-inspection-diff.png` | Structured diff in Electron app. |
| `10-electron-token-usage.png` | Token usage dashboard in Electron app. |
| `11-electron-audit.png` | Read-only Audit Page in Electron app. |

## Findings

### F-001: Single-workspace sidecar catalog route fell through

- Severity: P1
- Issue: <https://github.com/zhanghao1903/Taskweavn/issues/66>
- Affected route: `GET /api/v1/workspaces`
- Real local before-fix behavior: single-workspace sidecar returned
  `internal_error` with `Plato UI route dispatch fell through`.
- Fix: single-workspace sidecar assembly now reuses
  `MultiWorkspacePlatoUiHttpTransport` with a one-entry
  `WorkspaceRuntimeRegistry`.
- Electron validation: Electron-owned sidecar returned `ok: true` catalog for
  workspace `05cc0db4f9ae1924` without raw absolute paths.

### F-002: Electron first-run setup used an unavailable workspace scope

- Severity: P1
- Issue: <https://github.com/zhanghao1903/Taskweavn/issues/69>
- Affected path: Electron first-run setup -> Continue to Main Page
- Real local before-fix behavior: `npm run electron:smoke:first-run` timed out
  after the settings save/recheck succeeded because the renderer requested
  `GET /api/v1/workspaces/<electron-display-workspace>/sessions` and the
  sidecar returned `workspace is unavailable`.
- Fix: Main Page runtime creation no longer treats Electron's display workspace
  summary id as the default API workspace scope. Explicit route `workspaceId`
  values still opt into scoped workspace APIs; otherwise Main Page lets the
  sidecar/session catalog resolve the active workspace.
- Electron validation: `npm run electron:smoke:first-run` passed after the fix
  and loaded `Diagnostics smoke` plus `Run diagnostic-export-task`.

## GitHub Issues And Fix PRs

| Type | Link | Status |
|---|---|---|
| Issue | <https://github.com/zhanghao1903/Taskweavn/issues/66> | Closed by PR #67 on 2026-06-11 |
| Fix PR | <https://github.com/zhanghao1903/Taskweavn/pull/67> | Merged on 2026-06-11 |
| CI | <https://github.com/zhanghao1903/Taskweavn/actions/runs/27352009609/job/80816123401> | `Sidecar E2E Acceptance` passed in 51s |
| Issue | <https://github.com/zhanghao1903/Taskweavn/issues/69> | Closed by PR #70 on 2026-06-11 |
| Fix PR | <https://github.com/zhanghao1903/Taskweavn/pull/70> | Merged on 2026-06-11 |
| CI | <https://github.com/zhanghao1903/Taskweavn/actions/runs/27353597629/job/80821850433> | `Sidecar E2E Acceptance` passed in 53s |

## UX Improvement List

1. User-initiated Stop currently surfaces as `failed` with `Retry`. Prefer a
   distinct `stopped` or `cancelled` user-facing state so intentional stops do
   not read as system failures.
2. Execution ASK mixed English and Chinese copy in the same panel. The question
   is clear, but localization should be consistent on zh-CN Electron builds.
3. The token usage dashboard is useful but can become extremely expensive in
   real QA. Add a visible warning or budget boundary for long-running tasks
   before continuing high-token execution.
4. When an Agent asks for an external app path, the product could offer known
   current workspace/repo choices instead of requiring free-text path input.

## Remaining Gaps

- Full task completion and resulting precision mutation evidence were stopped
  intentionally after Execution ASK recovery to control LLM cost.
- Diagnostics export reported `usage` as included, but workspace inspection
  evidence store was missing in the sidecar export descriptor. This should be
  tracked as a future diagnostics integration gap.

## Closure Assessment

Product 1.1 QA hardening is accepted as phase-complete for the currently
implemented 1.1 surface:

- confirmed P1 defects were filed, fixed, merged, and verified by CI;
- Electron screenshots cover the real app states used by the QA pass;
- Product 1.1 token usage, workspace inspection, and precision file tool layers
  have direct test or app evidence;
- remaining items are product/UX follow-ups or broader integration coverage
  gaps, not untriaged regressions in the checked release path.

## Evidence Log

| Time | Check | Evidence | Result |
|---|---|---|---|
| 2026-06-11 | Branch baseline | `codex/product-1.1-qa-hardening` from `616bc1b` | Started |
| 2026-06-11 | Regression test | `uv run pytest tests/test_multi_workspace_sidecar.py` | Pass |
| 2026-06-11 | Precision tools | `uv run pytest tests/test_precision_file_tools.py` | Pass |
| 2026-06-11 | Electron-owned catalog | `GET /api/v1/workspaces` on `127.0.0.1:52257` | Pass |
| 2026-06-11 | Electron workspace inspection | `GET /api/v1/inspection/status` and app screenshots `08`, `09` | Pass |
| 2026-06-11 | Real LLM usage | `GET /api/v1/usage/token-summary?dimension=workspace` | 24 calls / 472,771 total tokens |
| 2026-06-11 | Authoring ASK | Electron screenshot `03-electron-authoring-ask.png` | Pass |
| 2026-06-11 | Execution ASK | Electron screenshot `06-electron-execution-ask.png` | Pass |
| 2026-06-11 | Audit Page | Electron screenshot `11-electron-audit.png` | Pass |
| 2026-06-11 | PR fix closure | PR #67 merged into `main` at `7bdec9a`; issue #66 closed | Pass |
| 2026-06-11 | GitHub CI | `Sidecar E2E Acceptance` run `27352009609` / job `80816123401` | Pass |
| 2026-06-11 | Electron first-run regression | `npm run electron:smoke:first-run` exposed issue #69 before fix | Fail before fix |
| 2026-06-11 | Electron first-run validation | `npm run electron:smoke:first-run` after runtime workspace-scope fix | Pass |
| 2026-06-11 | PR #70 fix closure | PR #70 merged into `main` at `08cd72b`; issue #69 closed | Pass |
| 2026-06-11 | GitHub CI | `Sidecar E2E Acceptance` run `27353597629` / job `80821850433` | Pass |
