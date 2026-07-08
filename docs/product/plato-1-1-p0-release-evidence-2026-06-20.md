# Plato Product 1.1 P0 Release Evidence - 2026-06-20

> Status: beta evidence baseline with formal `1.1` source-of-truth addendum
>
> Baseline branch: `main`
>
> Baseline commit: `135a853`
>
> Formal release addendum: `main` at `b8d7290`
>
> Scope: Product 1.1 P0 closure evidence for Runtime Input Router,
> Contract Revision Command Skills, durable Conversation / Activity, Router
> Audit / Diagnostics, and Electron acceptance.

## 1. Purpose

This document tracks the evidence required to call Product 1.1 P0
product-complete.

The Product 1.1 P0 functional code is now on `main`, including:

- Runtime Input Router as the Main Page input path;
- Contract Revision Command Skills for guidance, ASK / confirmation,
  Plan/TaskNode changes, and execution handoff;
- durable Router Conversation / Activity records;
- backend-only Agent LLM and Router LLM configuration.

The remaining P0 closure work is not first capability delivery. It is proving
that the loop works in the real Electron app, is inspectable through Audit /
Diagnostics, and has a release evidence record that users and maintainers can
trust.

## 2. Closure Decision

Product 1.1 P0 closure required all three gates below. They now pass for the
Product 1.1 beta evidence scope:

| Gate | Current status | Completion rule |
|---|---|---|
| Electron acceptance | Passed for configured P0 route matrix | Real Electron / sidecar evidence covers all P0 route classes and no-mutation guarantees. |
| Audit / Diagnostics closure | Passed for P0 route matrix | Router decisions, downstream command ids, Activity ids, Audit refs, and diagnostic descriptors are linked and redacted. |
| Release evidence | Passed for Product 1.1 beta P0 | This evidence package links each accepted feature to tests, smoke output, packaged app and mounted `1.1-beta` installer evidence, known limitations, and release notes. |

As of 2026-07-06, this document is the Product 1.1 beta P0 evidence baseline.
The current formal `1.1` local release evidence source-of-truth is layered on
top of it by:

- [Plato Product 1.1 Feature Test Report - 2026-07-02](plato-1-1-feature-test-report-2026-07-02.md);
- [Plato Product 1.1 Formal Release Notes](../releases/product-1-1-formal-release-notes.md).

The 2026-07-02 QA report validated the formal `1.1` DMG core local release path
and found `F-2026-07-02-001` / `F-2026-07-02-002`. `F-2026-07-02-001` is fixed
on `main` by `841cfd6 fix(electron): restore workspace picker smoke
acceptance`. `F-2026-07-02-002` remains beta-depth evidence: the deterministic
LLM answer rendered, but the full optional LLM smoke still needs a split or
retry-recovery fix before it can be claimed green.

## 3. P0 Acceptance Matrix

| Requirement | Implementation status | Current evidence | Missing evidence |
|---|---|---|---|
| Main Page input routes through Runtime Input Router by default. | Implemented on `main`. | `frontend/src/pages/main-page/useMainPageController.ts`; `frontend/src/pages/main-page/useMainPageController.test.tsx`; `npm run electron:smoke`; `npm run electron:smoke:packaged`; mounted `1.1-beta` installer smoke. | None for P0; broader task/plan visual screenshot evidence remains release polish. |
| Read-only questions return answers with evidence refs and `no_effect`. | Implemented on `main`. | `tests/test_runtime_input_router.py`; `tests/test_read_only_inquiry_answer_provider.py`; `npm run electron:smoke` passes and verifies read-only Runtime Input route, durable Activity replay after renderer reload, Audit navigation, and `runtime_input` diagnostic export section. | Optional LLM-rendered read-only inquiry smoke can still be run as beta depth, but is not a P0 blocker. |
| Guidance is persisted as typed context through command-backed facts. | Implemented on `main`. | `tests/test_runtime_input_router.py`; Contract Revision command tests covered by `tests/test_collaborator_authoring_service.py` and runtime router tests; `npm run electron:smoke` verifies `mode: guide` routes through `record_guidance` and appears in Activity. | Broader plan/task-scoped guidance smoke remains useful beta depth. |
| ASK answers work from explicit UI and routed input. | Implemented on `main`. | `tests/test_runtime_input_router.py`; `frontend/src/pages/main-page/SessionMessageCard.test.tsx`; existing 2026-06-11 ASK screenshots cover pre-Router Electron ASK states; `npm run electron:smoke` verifies routed active ASK answer through the Electron sidecar and durable Activity. | None for P0; richer visual screenshot evidence can be added for release notes. |
| Confirmation answers work from explicit UI and routed input. | Implemented on `main`. | `tests/test_runtime_input_router.py` includes confirmation route and durable question-card coverage; `npm run electron:smoke` verifies confirmation clarification/no-effect and routed confirmation resolution through the Electron sidecar. | None for P0; screenshot evidence can be added for release notes. |
| Contract-changing requests use versioned, idempotent command skills. | Implemented on `main`. | Contract Revision command tests and runtime router tests cover command-backed mutation and idempotency; runtime diagnostic descriptors link route command ids to downstream command ids and Activity/Audit refs. | None for P0. |
| Workspace-changing requests create executable contract work and do not run tools directly. | Implemented on `main`. | Runtime router tests cover `create_execution_task` handoff; Contract Revision docs define no direct workspace writes; `npm run electron:smoke` verifies `mode: change` routes to `execution_handoff`, creates `Execution work created` Activity, and leaves workspace status unchanged except the seeded fixture file. | None for P0. |
| Every accepted route creates durable user-visible Conversation / Activity evidence. | Implemented on `main`. | `src/taskweavn/server/runtime_input_activity.py`; `src/taskweavn/server/ui_contract/session_activity_projection.py`; `tests/test_runtime_input_router.py`; frontend Conversation card tests; `npm run electron:smoke` validates Activity replay for read-only, guidance, ASK, confirmation, execution handoff, and unsupported routes after renderer reload. | Sidecar restart replay remains beta-depth evidence, not first P0 closure. |
| Router decisions link to downstream command, Audit, and diagnostic refs. | Implemented for P0. | `router/runtime-input.summary.json` diagnostic bundle section links route command ids, Router decision ids, Conversation message ids, Activity message ids, downstream command ids, and message Audit refs. Audit UI projects Router input, Router decision, question card, and outcome messages as Runtime Input Router records/details. `npm run electron:smoke` verifies real route diagnostics include `runtime_input` after the route matrix. | None for P0; deeper per-route descriptor inspection is tracked in [Electron Route Log Descriptors](../plans/feature/electron-route-log-descriptors.md). |
| Low-confidence and unsupported input never mutates product state or workspace files. | Implemented and verified for P0. | Runtime router tests cover unsupported and clarification outcomes; `npm run electron:smoke` verifies unsupported route fails closed with `no_effect`, appears in Activity, and workspace inspection status still contains only the seeded fixture file. | None for P0. |
| Product 1.1 release notes distinguish stable/beta behavior and known limitations. | Closed for internal Product 1.1 P0 beta evidence. | [Product 1.1 Runtime Input Router Release Evidence](../releases/product-1-1-runtime-input-router-release-evidence.md) links shipped behavior, validation commands, `1.1-beta` DMG SHA256, signed/notarized status, and known limitations. | Public repository release-note sync remains P1 external-doc polish. |

## 4. Electron Acceptance Gate

Electron acceptance must use the Electron app shell and Electron-owned sidecar.
Browser-only verification is not sufficient for Product 1.1 P0.

### 4.1 Required Route Scenarios

| Scenario | Required evidence |
|---|---|
| Read-only question | Conversation shows user question, Router trace, answer; Activity contains answer with evidence refs; no workspace mutation. |
| Guidance | Main input records guidance as typed context; Conversation / Activity replay after reload. Covered for session-scoped guidance by `npm run electron:smoke`. |
| ASK answer | Active ASK can be answered through main input; explicit ASK controls still work. Covered by backend/frontend tests plus `npm run electron:smoke` routed active ASK answer. |
| Confirmation response | Confirmation can be answered through main input; ambiguous answer creates a question card or no-effect clarification. Covered by backend tests plus `npm run electron:smoke` routed clarification and confirmation resolution. |
| Execution handoff | Workspace-changing request creates executable contract work, not direct tool execution. Covered by `npm run electron:smoke` `mode: change` execution handoff and workspace no-mutation check. |
| Unsupported route | User sees safe explanation and recovery action; no product or workspace mutation. Covered for no-effect unsupported route by `npm run electron:smoke`. |
| Stop / retry | Explicit task controls still work after Router-first input migration. Covered by stale retry API rejection in `npm run electron:smoke`; richer visible button coverage remains beta-depth because the smoke fixture intentionally leaves a clarification card visible. |
| Reload / restart | Durable Conversation / Activity replay survives renderer reload and sidecar restart. Renderer reload is covered by `npm run electron:smoke`; sidecar restart remains a deferred beta-depth check. |

### 4.2 Candidate Commands

Use these existing scripts as the starting point:

```bash
cd frontend
npm run electron:smoke
npm run electron:smoke:packaged
npm run electron:package:installer -- --release-version 1.1-beta --include-smoke
npm run electron:smoke:installer -- --skip-package --installer ./dist-electron-installer/Plato-1.1-beta-macos-arm64.dmg
npm run electron:smoke:first-run
npm run electron:smoke:read-only-inquiry-llm
npm run electron:smoke:workspace-git
npm run electron:smoke:workspace-entry
```

The configured, packaged, and mounted `1.1-beta` installer smoke now cover the
P0 route matrix. Additional beta-depth smoke can still be added for sidecar
restart replay and LLM-rendered read-only inquiry output.

## 5. Audit / Diagnostics Closure Gate

Audit / Diagnostics closure must prove that a routed input can be inspected
without exposing hidden internals.

### 5.1 Required Links

Each accepted route should have enough safe references to answer:

| Question | Evidence source |
|---|---|
| What did the user ask Plato to do? | Durable Conversation user input. |
| How did Router classify the input? | Router trace / `router_interpretation` Activity. |
| Did the route have side effects? | Runtime decision side-effect class and command outcome. |
| Which command or downstream capability ran? | Command id, dispatch target, downstream refs. |
| What changed? | Plan/TaskNode refs, ASK/confirmation refs, result refs, file refs, or no-mutation proof. |
| Can support export this safely? | Diagnostic descriptor with redaction status and no raw hidden payloads. |

### 5.2 Required Redaction Guarantees

The diagnostic export must not expose:

- raw prompts;
- provider request / response payloads;
- API keys, tokens, secrets, Authorization headers;
- raw SQLite rows;
- raw logs by default;
- absolute workspace paths;
- hidden Audit evidence.

### 5.3 Current Status

The diagnostic bundle now includes a Router-specific
`router/runtime-input.summary.json` section for durable MessageStream evidence.
That section connects:

```text
runtime input command id
  -> Router decision id
  -> Conversation message ids
  -> Activity ids
  -> downstream command ids
  -> message Audit refs / diagnostic descriptors
```

The Audit UI projects Router-specific message records and details from the
same safe Conversation facts. `npm run electron:smoke` now proves the real
Electron sidecar can run the route matrix, export a diagnostics bundle that
includes `runtime_input`, open Audit evidence, and keep absolute workspace paths
out of the UI.

## 6. Release Evidence Gate

Release evidence is accepted when the release record contains:

1. Product 1.1 feature list and stable/beta distinction.
2. Validation commands and pass/fail output summary.
3. Electron screenshots or smoke logs for P0 route classes.
4. Audit / Diagnostics redaction evidence.
5. Known limitations and deferred P1/P2 work.
6. Links to user-facing docs and public release notes when applicable.

### 6.1 Product 1.1 Beta Artifact Evidence

The Product 1.1 beta release candidate smoke artifact is:

```text
frontend/dist-electron-installer/Plato-1.1-beta-macos-arm64.dmg
```

Evidence:

| Field | Value |
|---|---|
| Release version | `1.1-beta` |
| Package version | `1.1.0-beta` |
| Runtime kind | `bundled-python` |
| Release asset check | `ok=true`, `externalSymlinks=0` |
| Smoke assets | Included for deterministic beta smoke only |
| SHA256 | `fa67d9441d45537e6f59d674f03811fe10fcbf936da5986e12e6aef846e9406e` |
| Signed | `false` |
| Notarized | `false` |

The mounted installer smoke passed:

- configured packaged-default-workspace path;
- Runtime Input route matrix through launcher-owned sidecar;
- Audit, workspace inspection, diagnostics export, and `runtime_input`
  diagnostic section;
- first-run Settings path;
- startup diagnostics failure path.

## 7. Recommended Next Branches

1. `codex/product-1-1-sidecar-restart-replay`
   - Add beta-depth evidence that durable Conversation / Activity replay
     survives packaged sidecar restart, then fold it into installer smoke if the
     check is stable.

2. `codex/product-1-1-public-release-doc-sync`
   - Mirror the internal Product 1.1 beta release evidence into public
     repository release/user docs, with screenshots when useful.

## 8. Current Assessment

Product 1.1 P0 is accepted for beta release evidence across the configured
Electron app, packaged app, and mounted `1.1-beta` installer route matrix. The
formal `1.1` local release source-of-truth extends that baseline with formal
DMG verification, mounted installer smoke, sidecar restart replay, and the
Workspace Picker fix noted above.

The main remaining risk is beta-depth/publication polish, not P0 capability
closure: optional LLM-rendered inquiry smoke split/fix, public repository
release-note sync, signed/notarized distribution, and richer screenshots.

## 9. Evidence Log

| Date | Check | Evidence | Result |
|---|---|---|---|
| 2026-06-20 | Baseline | `main` at `135a853` includes Router-first Main Page, durable Conversation / Activity, Contract Revision Command Skills, and Agent LLM Router. | Pass |
| 2026-06-20 | Markdown / whitespace | `git diff --check` | Pass |
| 2026-06-20 | Backend Router and Agent LLM targeted tests | `uv run pytest tests/test_runtime_input_router.py tests/test_read_only_inquiry_answer_provider.py tests/test_runtime_input_llm_router.py tests/test_agent_llm_config.py tests/test_agent_llm_resolver.py` | Pass: 37 tests |
| 2026-06-20 | Frontend Main Page / Conversation targeted tests | `npm run test -- useMainPageController.test.tsx SessionMessageCard.test.tsx mainPageViewModel.test.ts` | Pass: 52 tests |
| 2026-06-20 | Runtime Input diagnostics bundle descriptors | `uv run pytest tests/test_runtime_input_router.py tests/test_read_only_inquiry_answer_provider.py tests/test_diagnostic_bundle_export.py` | Pass: 32 tests |
| 2026-06-20 | Runtime Input diagnostics lint | `uv run ruff check src/taskweavn/diagnostics/runtime_input.py src/taskweavn/diagnostics/bundle.py tests/test_diagnostic_bundle_export.py` | Pass |
| 2026-06-20 | Sidecar diagnostic export route | `uv run pytest tests/test_main_page_sidecar_app.py -k diagnostic` | Pass: 1 test |
| 2026-06-20 | Runtime Input Audit UI records/details | `uv run pytest tests/test_ui_query_gateway.py tests/test_audit_entry_closure.py` | Pass: 38 tests |
| 2026-06-20 | Runtime Input Audit lint | `uv run ruff check src/taskweavn/server/ui_contract/audit_projection.py src/taskweavn/server/ui_contract/audit_detail_projection.py tests/test_ui_query_gateway.py` | Pass |
| 2026-06-20 | Electron configured smoke with Runtime Input route matrix and diagnostics evidence | `npm run electron:smoke` | Pass: configured Electron smoke validates Audit, workspace inspection, diagnostics export, read-only Runtime Input Activity replay, guidance route Activity, routed ASK answer, confirmation clarification and resolution, execution handoff, unsupported no-effect route Activity, workspace no-mutation status, Audit navigation, stale retry rejection, and diagnostic export containing `runtime_input`. |
| 2026-06-20 | Electron packaged app smoke | `npm run electron:smoke:packaged` | Pass: packaged app validates configured route matrix, first-run path, and startup diagnostics. |
| 2026-06-20 | Installer cleanup robustness | `npm run electron:smoke:installer` | The mounted configured route matrix passed, then the wrapper failed during temporary directory cleanup with `ENOTEMPTY`; cleanup was fixed by adding `maxRetries` / `retryDelay` to `run-electron-smoke.mjs`. |
| 2026-06-20 | `1.1-beta` installer package | `npm run electron:package:installer -- --release-version 1.1-beta --include-smoke` | Pass: created `Plato-1.1-beta-macos-arm64.dmg`; release asset check `ok=true`, runtime `bundled-python`, `externalSymlinks=0`, signed `false`, notarized `false`. |
| 2026-06-20 | `1.1-beta` mounted installer smoke | `npm run electron:smoke:installer -- --skip-package --installer ./dist-electron-installer/Plato-1.1-beta-macos-arm64.dmg` | Pass: mounted DMG configured route matrix, first-run Settings path, and startup diagnostics all passed through launcher-owned sidecar. |
| 2026-06-20 | `1.1-beta` DMG SHA256 | `shasum -a 256 frontend/dist-electron-installer/Plato-1.1-beta-macos-arm64.dmg` | Pass: `fa67d9441d45537e6f59d674f03811fe10fcbf936da5986e12e6aef846e9406e`. |
| 2026-07-02 | Formal `1.1` feature test report | [Plato Product 1.1 Feature Test Report - 2026-07-02](plato-1-1-feature-test-report-2026-07-02.md) | Core local release path passed for backend/frontend targeted tests, configured Electron route matrix, first-run path, sidecar restart replay, packaged smoke, formal DMG verification, and mounted installer smoke. Workspace Picker and optional LLM smoke follow-ups were found. |
| 2026-07-03 | Workspace Picker acceptance fix | `841cfd6 fix(electron): restore workspace picker smoke acceptance` | `F-2026-07-02-001` is fixed on `main`; workspace-entry and workspace-git smoke should be treated as restored for current release evidence. |

These checks close the Product 1.1 P0 route-matrix acceptance gate for the
configured Electron sidecar, packaged app, mounted `1.1-beta` installer, formal
`1.1` local release artifact, and Router Audit / Diagnostics support path.
Remaining evidence work is P1/publication depth: optional LLM-rendered
read-only inquiry smoke split/fix, public release-note sync, signed/notarized
distribution, and richer visual evidence.
