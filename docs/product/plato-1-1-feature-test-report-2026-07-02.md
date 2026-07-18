# Plato Product 1.1 Feature Test Report - 2026-07-02

> Status: completed with core release path passing; Workspace Picker follow-up fixed on `main`; optional LLM smoke follow-up open
>
> Tester role: professional QA tester using Electron/computer-use automation
>
> Test date: 2026-07-02 Asia/Shanghai
>
> Scope: Product 1.1 formal local release feature validation
>
> Release artifact under test: `frontend/dist-electron-installer/Plato-1.1-macos-arm64.dmg`

## Post-Report Source-Of-Truth Update - 2026-07-06

This report records the 2026-07-02 QA pass against the formal `1.1` DMG. Later
mainline evidence changes the current Product 1.1 release-evidence state:

- `F-2026-07-02-001` is fixed on `main` by
  `841cfd6 fix(electron): restore workspace picker smoke acceptance`.
  Workspace Picker, `npm run electron:smoke:workspace-entry`, and
  `npm run electron:smoke:workspace-git` should be treated as restored for the
  current Product 1.1 source-of-truth.
- `F-2026-07-02-002` remains open beta-depth evidence. The deterministic LLM
  answer rendered, but the full `npm run electron:smoke:read-only-inquiry-llm`
  script still needs a split or retry-recovery fix before it can be claimed
  green.
- The formal `1.1` release evidence source-of-truth is this report plus
  [`Product 1.1 Formal Release Notes`](../releases/product-1-1-formal-release-notes.md).
  The 2026-06-20 P0 release evidence remains the beta baseline.

## Workflow Gate Report

| Item | Result |
|---|---|
| User request | Use computer-use style tooling to test Product 1.1 features and generate a report. |
| Detected workflow phase | P9 QA, visual/runtime regression, release readiness. |
| Task type | Feature testing, smoke testing, release evidence review. |
| Required upstream artifacts | Product 1.1 release scope, acceptance matrix, app run scripts, API/UI contracts, existing evidence docs. |
| Found artifacts | `README.md`, Product 1.1 formal release notes, beta release notes, P0 release evidence, P1 coverage audit, Product 1.1 open-work index, Electron smoke scripts. |
| Missing or weak artifacts | No blocking artifact gap. Live Tavily web retrieval and real provider inquiry remain credential/config dependent. |
| Implementation allowed now | Yes. This task is QA/reporting only; no production code changes required. |
| Prework required | Derive feature matrix from release docs and separate environment blockers from product failures. |
| Execution scope | Backend targeted tests, frontend targeted tests, Electron dev/package/installer smoke, workspace entry/git smoke, sidecar replay smoke, live web retrieval skip check. |
| Acceptance criteria | Every major Product 1.1 feature has pass/fail/partial/skipped evidence, with reproducible commands for failures. |
| Risks and assumptions | Electron smoke requires macOS GUI/system access. Dummy local readiness keys were used only to pass settings readiness for workspace picker smoke and were not real provider credentials. |

## Source Scope

- `docs/releases/product-1-1-formal-release-notes.md`
- `docs/releases/product-1-1-beta-external-release-notes.md`
- `docs/product/plato-1-1-p0-release-evidence-2026-06-20.md`
- `docs/product/plato-1-1-p1-coverage-audit-2026-06-24.md`
- `docs/product/plato-1-1-open-work.md`
- `README.md`

## Environment

| Area | Observed value |
|---|---|
| OS/runtime | macOS Darwin, local Electron app automation |
| Python test runtime | Python 3.12.7, pytest 9.0.3 |
| Frontend test runtime | Vitest 4.1.6, Vite 8.0.13 |
| Repo state | Existing uncommitted `AGENTS.md` change was present before report generation and was not modified by QA commands. |
| External provider state | No live Tavily run was enabled. Workspace picker smoke used dummy local readiness keys only. |

## Executive Summary

The core Product 1.1 release path passed:

- backend Product 1.1 contract tests: 118 passed;
- frontend Main Page/runtime tests: 112 passed;
- configured Electron route matrix: passed;
- first-run Electron path: passed;
- sidecar restart replay: passed;
- packaged app smoke: passed;
- formal `1.1` DMG verification: passed;
- mounted installer smoke against `Plato-1.1-macos-arm64.dmg`: passed.

Two repeatable follow-up failures were found:

1. Workspace entry and workspace git-initialization Electron smoke do not show the expected Workspace Picker when `PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION=1`; the app goes directly to Main Page and reports `workspaceEntryRequired=false`.
2. Deterministic read-only inquiry LLM Electron smoke renders the expected LLM answer, but fails later in command-failure recovery while waiting for the retry task text.

Live Tavily web retrieval was intentionally skipped because the required live-smoke environment variables were not set.

## Feature Matrix

| Product 1.1 feature | Evidence run in this pass | Result | Notes |
|---|---|---:|---|
| Runtime Input Router default path | `uv run pytest ... test_runtime_input_router.py`; `npm run electron:smoke`; packaged and installer smoke | Pass | Covered read-only question, guidance, ASK, confirmation, execution handoff, unsupported route, no-effect behavior. |
| Durable Conversation and Activity | Backend tests plus Electron route matrix and sidecar restart replay | Pass | Activity replay passed after renderer reload and sidecar restart. |
| Read-only inquiry, deterministic non-LLM | Backend tests and configured Electron smoke | Pass | Answer produced with `no_effect` and diagnostic evidence refs. |
| Read-only inquiry, deterministic LLM path | `npm run electron:smoke:read-only-inquiry-llm` twice | Partial / Fail | LLM answer rendered correctly; smoke failed later at stale retry recovery. |
| ASK and confirmation routing | Backend tests, frontend tests, Electron route matrix | Pass | Routed active ASK answer and confirmation clarification/resolution covered by configured smoke. |
| Contract revision commands | Runtime router tests, collaborator/command coverage in targeted suites, Electron route matrix | Pass | Guidance and command-backed mutation paths remained auditable. |
| Execution handoff and no direct workspace mutation | Electron route matrix | Pass | Workspace-changing input created execution work instead of direct Router writes. |
| Audit and diagnostics linkage | `test_diagnostic_bundle_export.py`, `test_ui_query_gateway.py`, `test_audit_entry_closure.py`, Electron smoke | Pass | Diagnostic export included `runtime_input`; Audit navigation passed in dev/package/installer smoke. |
| Workspace inspection and file evidence | `test_workspace_inspection_api.py`, Electron smoke, packaged/installer smoke | Pass | Status, file viewer/diff entry points, diagnostics-safe labels covered by route matrix. |
| Workspace entry / picker | `npm run electron:smoke:workspace-entry` with dummy readiness keys | Fail | Expected Workspace Picker did not appear; app opened Main Page directly. |
| Workspace git initialization preference | `npm run electron:smoke:workspace-git` with dummy readiness keys | Fail | Same Workspace Picker issue prevented git-init preference validation. |
| Token usage analytics | `test_token_usage_analytics.py` and frontend usage route test | Pass | Unit/UI route coverage passed. |
| Precision file tools | `test_precision_file_tools_sidecar_acceptance.py` | Pass | Sidecar acceptance coverage passed. |
| Web search/fetch foundations | `test_web_search.py`, `test_web_fetch.py` | Pass | Mock/provider-independent coverage passed. |
| Live web retrieval | `uv run pytest tests/test_web_retrieval_live_smoke.py` | Skipped | Expected skip without `PLATO_RUN_LIVE_WEB_RETRIEVAL_SMOKE=1` and `TAVILY_API_KEY`. |
| First-run settings/readiness | `npm run electron:smoke:first-run`; packaged/installer first-run smoke | Pass | Missing config flow and return to Main Page passed. |
| Sidecar restart replay | `npm run electron:smoke:sidecar-restart` | Pass | Durable Conversation, Activity, Audit record, Audit evidence, fixture file state replayed without duplicate IDs. |
| Packaged app release path | `npm run electron:smoke:packaged -- --skip-package` | Pass | Configured, first-run, and startup diagnostics packaged smoke passed. |
| Formal DMG integrity | `hdiutil verify frontend/dist-electron-installer/Plato-1.1-macos-arm64.dmg` | Pass | DMG checksum was valid. |
| Mounted installer release path | `npm run electron:smoke:installer -- --skip-package --installer ./dist-electron-installer/Plato-1.1-macos-arm64.dmg` | Pass | Mounted configured, first-run, and startup diagnostics installer smoke passed. |

## Command Evidence

| Check | Command | Result |
|---|---|---|
| Backend Product 1.1 targeted suite | `uv run pytest tests/test_runtime_input_router.py tests/test_read_only_inquiry_answer_provider.py tests/test_runtime_input_llm_router.py tests/test_agent_llm_config.py tests/test_agent_llm_resolver.py tests/test_diagnostic_bundle_export.py tests/test_ui_query_gateway.py tests/test_audit_entry_closure.py tests/test_token_usage_analytics.py tests/test_precision_file_tools_sidecar_acceptance.py tests/test_workspace_inspection_api.py tests/test_web_search.py tests/test_web_fetch.py` | Pass: 118 passed in 6.20s |
| Frontend targeted suite | `npm run test -- src/pages/main-page/useMainPageController.test.tsx src/pages/main-page/SessionMessageCard.test.tsx src/pages/main-page/mainPageViewModel.test.ts src/pages/main-page/runtime/mainPageFocusScrollRuntime.test.ts src/pages/main-page/useMainPageFocusScrollRuntime.test.tsx src/pages/main-page/MainPageWorkbench.test.tsx src/pages/usage/WorkspaceUsageRoute.test.tsx src/pages/workspace-inspection/WorkspaceInspectionRoute.test.tsx src/pages/diagnostics/DiagnosticsLogsRoute.test.tsx src/app/AppRouting.test.tsx` | Pass: 10 files, 112 tests |
| Configured Electron route matrix | `npm run electron:smoke` | Pass after rerun outside sandbox; first sandbox attempt failed on local `uv` cache permission. |
| First-run Electron | `npm run electron:smoke:first-run` | Pass |
| Workspace git smoke, missing-config precondition | `npm run electron:smoke:workspace-git` | Blocked by missing `DEEPSEEK_API_KEY` / `LLM_API_KEY`, expected readiness gate. |
| Workspace git smoke, configured readiness | `env DEEPSEEK_API_KEY=smoke-test-key LLM_API_KEY=smoke-test-key LLM_PROVIDER=deepseek LLM_MODEL=deepseek-chat npm run electron:smoke:workspace-git` | Fail: Workspace Picker heading timed out; `workspaceEntryRequired=false`. |
| Workspace entry smoke, configured readiness | `env DEEPSEEK_API_KEY=smoke-test-key LLM_API_KEY=smoke-test-key LLM_PROVIDER=deepseek LLM_MODEL=deepseek-chat npm run electron:smoke:workspace-entry` | Fail: Workspace Picker heading timed out; `workspaceEntryRequired=false`. |
| Workspace/settings unit support | `npm run test -- ../frontend/electron/workspaceEntry.test.mjs ../frontend/electron/workspaceGit.test.mjs ../frontend/electron/workspacePaths.test.mjs ../frontend/electron/main.test.mjs` | Pass: 3 files, 15 tests |
| Settings/readiness backend support | `uv run pytest tests/test_main_page_sidecar_config.py tests/test_settings_readiness.py tests/test_settings_config.py tests/test_main_page_sidecar_app.py -k "settings or workspace or health or diagnostic"` | Pass: 19 selected |
| Sidecar restart replay | `npm run electron:smoke:sidecar-restart` | Pass |
| Live web retrieval | `uv run pytest tests/test_web_retrieval_live_smoke.py` | Skipped: live env vars not set |
| Read-only inquiry LLM smoke | `npm run electron:smoke:read-only-inquiry-llm` | Fail twice at stale retry recovery after the LLM answer rendered. |
| Packaged smoke | `npm run electron:smoke:packaged -- --skip-package` | Pass: configured, first-run, startup diagnostics |
| DMG verify | `hdiutil verify frontend/dist-electron-installer/Plato-1.1-macos-arm64.dmg` | Pass: checksum valid |
| Mounted installer smoke | `npm run electron:smoke:installer -- --skip-package --installer ./dist-electron-installer/Plato-1.1-macos-arm64.dmg` | Pass: configured installer, first-run installer, startup diagnostics installer |

## Findings

### F-2026-07-02-001: Workspace Picker smoke is bypassed

- Severity: P1
- Affected commands:
  - `npm run electron:smoke:workspace-entry`
  - `npm run electron:smoke:workspace-git`
- Expected: Electron opens the Workspace Picker with `Open a workspace`, then the smoke selects the seeded recent workspace.
- Actual: Electron opens the workspace directly on Main Page. Startup timing reports `workspaceEntryRequired=false`. The smoke times out waiting for `Workspace Picker heading`.
- Impact: Product 1.1 workspace selection and workspace git-initialization preference cannot be accepted through the real Electron smoke path in this run. Unit tests still pass, so the risk appears to be startup/integration behavior rather than the lower-level workspace entry/git helper logic.
- Reproduction note: Without local readiness keys, `workspace-git` first stops at the expected first-run configuration gate. With dummy readiness keys, the picker bypass reproduces.
- Suggested next step: inspect `PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION` handling in Electron startup and why the rendered startup config reports `workspaceEntryRequired=false` despite the smoke script setting the environment flag.

### F-2026-07-02-002: Read-only inquiry LLM smoke fails after rendering the LLM answer

- Severity: P2
- Affected command: `npm run electron:smoke:read-only-inquiry-llm`
- Expected: deterministic LLM read-only inquiry path completes the same configured smoke tail as non-LLM mode, including command-failure recovery.
- Actual: the page renders `LLM rendered a read-only answer from cited safe evidence only.`, then the smoke fails later waiting for `Run diagnostic-export-task` before the stale retry command.
- Repeatability: reproduced twice in this QA run.
- Impact: The optional LLM-rendered inquiry smoke cannot be used as full beta-depth acceptance evidence until the retry-recovery tail is fixed or the smoke is split so the LLM route and retry recovery are independently asserted.
- Suggested next step: split `smokeReadOnlyInquiryActivity` from `smokeCommandFailureRecovery` for the LLM-only script, or fix the Main Page route/state so selected task text remains visible after the longer LLM route activity sequence.

## Non-Defect Environment Notes

- The first `npm run electron:smoke` attempt failed inside the sandbox because `uv` could not access `/Users/zhanghao/.cache/uv`; rerunning outside the sandbox passed.
- Live web retrieval was skipped by design because `PLATO_RUN_LIVE_WEB_RETRIEVAL_SMOKE=1` and `TAVILY_API_KEY` were not set.
- The Product 1.1 DMG remains unsigned and not notarized, matching the formal release notes.

## Release Readiness Assessment

Product 1.1's formal core local release path is acceptable for the tested release artifact:

- formal DMG integrity passed;
- mounted installer smoke passed;
- packaged app smoke passed;
- configured Electron route matrix passed;
- first-run and startup diagnostics passed;
- backend and frontend targeted suites passed.

The 2026-07-02 run found two beta-depth/workspace-entry follow-ups:

1. workspace picker and workspace git initialization smoke are failing in the real Electron startup path;
2. optional read-only inquiry LLM smoke is only partially accepted because the LLM answer appears but the full script fails later.

Current source-of-truth update: workspace-entry and workspace git-init smoke
were restored on `main` by `841cfd6`. Do not use this report to claim that the
optional LLM inquiry smoke is green. The rest of the Product 1.1 route matrix
and formal DMG release path were validated in this run.

## Recommended Next Step

`F-2026-07-02-001` is fixed on `main`; keep its source pointer in release
evidence. Next, either fix or split the optional LLM inquiry smoke so Product
1.1 beta-depth evidence can distinguish LLM answer rendering from stale retry
recovery.
