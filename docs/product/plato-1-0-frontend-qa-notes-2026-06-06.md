# Plato Product 1.0 Frontend QA Notes - 2026-06-06

> Status: automated Product 1.0 frontend acceptance plus Browser smoke pass
> Runbook: [Plato Product 1.0 Frontend QA Runbook](plato-1-0-frontend-qa-runbook.md)
> Branch: `codex/result-audit-evidence-validation`
> Environment: mock frontend tests, focused backend contract tests, formal real-sidecar E2E fixtures, and normal browser dev smoke

---

## 1. Summary

This pass validates the current Product 1.0 frontend integration path after
Main Page recovery labels, Audit evidence validation, Diagnostic Bundle export,
and Settings first-run completion were added to the formal sidecar runner. It
also covers a normal browser smoke through the configured sidecar dev command.

Result: pass for automated acceptance coverage. No P0/P1 blocker was found in
the automated path or the covered browser smoke path.

Decision: no recovery label needs to become a concrete button or deep link in
this pass. The real command failure path surfaces `Refresh session` as guidance
and does not require an immediate action handler. Future slices may promote
`open_audit`, `open_settings`, or `export_diagnostics` only when the current
surface has a concrete safe target and the required session/task/record refs.

Browser smoke found one P2 viewport issue: Main Page had a 15px horizontal
scrollbar at 1280x800 because the root layout forced `min-width: 1280px` while
the vertical scrollbar reduced client width. The issue was fixed in
`frontend/src/pages/main-page/MainPage.module.css` by bounding the root
`min-width` to the available width.

Electron smoke result for this pass: blocked. The repository now has a
Packaging/Electron release plan. On 2026-06-07, E1/E2 added the Electron dev
shell, main-owned sidecar lifecycle, startup diagnostics foundation, preload
runtime injection, and `npm run electron:dev`. On 2026-06-07, E5 added
configured `npm run electron:smoke` for Main Page, Audit evidence, Diagnostic
Bundle export, and command-failure recovery labels. The same date also added
`npm run electron:smoke:first-run` for Settings first-run setup, save/recheck,
secret redaction, and transition into Main Page. E6 added
`npm run electron:package:dir` and `npm run electron:smoke:packaged`, covering
the configured and first-run paths against the packaged renderer without Vite.
The packaged startup diagnostics hardening follow-up extends
`npm run electron:smoke:packaged` with a main-owned sidecar startup-failure
path that runs without a seeded external sidecar. The signed runtime plan
follow-up records the accepted launcher boundary: Electron main keeps lifecycle
ownership, while a release-local launcher encapsulates Python runtime details.
E9 adds `npm run electron:package:launcher-dir` and
`npm run electron:smoke:launcher`, covering configured, first-run, and startup
diagnostics paths through the package-local launcher. E10 replaces the E9
repo-local launcher runtime manifest with package-local `python-env` and
`python-src` runtime candidate assets, so launcher smoke no longer depends on
repo `uv`, repo `src/tests`, or the developer `.venv`. E11 accepts bundled
Python behind the release-local launcher as the Product 1.0 final runtime
strategy and defines the release asset checker plus installer smoke command
contracts. E12 implements `npm run electron:check:release-assets`, which now
blocks the current runtime candidate on external Python executable symlinks and
external `pyvenv.cfg` runtime ownership.

---

## 2. Environment

| Field | Value |
|---|---|
| Date | 2026-06-06 Asia/Shanghai |
| Tester | Codex |
| Branch | `codex/result-audit-evidence-validation` |
| Runtime mode | formal sidecar E2E fixtures, frontend mock regression, and normal browser dev smoke |
| Sidecar fixture | `tests/fixtures/sidecar_smoke.py --keep-alive` via `npm run test:e2e:sidecar` |
| Browser smoke URL | `http://127.0.0.1:5175/` |
| Browser smoke sidecar URL | `http://127.0.0.1:55403` |
| Browser smoke session ID | `01ce1fc7` |

---

## 3. Checks Run

| Check | Result | Notes |
|---|---|---|
| Frontend regression tests | Pass | `cd frontend && npm run test`: 46 files passed, 4 skipped; 332 tests passed, 5 skipped. |
| Frontend build | Pass | `cd frontend && npm run build`: TypeScript and Vite build passed. |
| Frontend lint | Pass | `cd frontend && npm run lint`: ESLint passed. |
| Backend focused tests | Pass | `uv run pytest tests/test_ui_contract_models.py tests/test_diagnostic_bundle_export.py tests/test_task_result_summary_store.py`: 22 passed, 1 dependency warning. |
| Formal sidecar E2E | Pass | `cd frontend && npm run test:e2e:sidecar`: 4 files passed, 5 tests passed. |
| Diff whitespace check | Pass | `git diff --check`. |
| Browser dev smoke | Pass | `cd frontend && npm run dev:sidecar:configured -- --port 5174`; Vite used `5175` because `5174` was occupied. |
| Electron smoke | Pass for configured, first-run, packaged renderer, packaged startup-diagnostics, and launcher-backed paths after 2026-06-07 follow-ups | Packaging/Electron release plan exists. E1/E2 dev shell exists as of 2026-06-07; E5 configured `electron:smoke` passed; first-run `electron:smoke:first-run` passed; E6 `electron:smoke:packaged` passed and now includes startup diagnostics failure without a seeded external sidecar. Signed runtime planning accepts the launcher boundary. E9 `electron:smoke:launcher` passes configured, first-run, and startup diagnostics paths, and E10 updates that command to use package-local runtime candidate assets instead of repo Python paths. |

---

## 4. Covered Product Paths

| Area | Result | Evidence |
|---|---|---|
| Main Page -> Audit -> record/detail/evidence | Pass | Real sidecar E2E opens Audit from Main Page and validates result, projected file, typed `FileWriteObservation`, config, and log records. |
| Main Page recoverable command failure | Pass | Real sidecar E2E primes a failed task through retry, then clicks Main Page `Retry` against stale UI state and receives the backend rejection `only failed tasks can be retried`. |
| Product recovery labels | Pass | The command failure path renders `Refresh session` and does not expose raw `command_rejected`, `recoveryActions`, `productCategory`, or backend exception types. |
| Diagnostic Bundle export | Pass | Real sidecar E2E exports a redacted bundle from the seeded Audit log handoff route. |
| Settings first-run configured path | Pass | Real sidecar E2E opens Main Page when readiness is already configured. |
| Settings first-run unconfigured path | Pass | Real sidecar E2E opens setup, saves write-only local config, rechecks readiness, and reaches Main Page without exposing the secret. |
| Electron Settings first-run path | Pass | `npm run electron:smoke:first-run` starts an unconfigured seeded sidecar, opens Settings in the Electron dev shell, saves local setup, rechecks readiness, verifies secret redaction, and reaches Main Page. |
| Normal browser Settings modal | Pass | Browser smoke opens `/settings` as an in-app modal over the Main Page background; stored secrets are not rendered. |
| Normal browser Audit path | Pass | Browser smoke opens Audit from Main Page, switches to All records, and sees result, file, `FileWriteObservation`, config, and log evidence without raw workspace path exposure. |
| Normal browser Diagnostics export | Pass | Browser smoke opens the diagnostics log handoff route and exports a bundle showing only `workspace://current/...` paths. |
| Normal browser stale retry recovery | Pass | Browser smoke primes the failed task through the sidecar API, clicks stale Main Page `Retry`, and sees `only failed tasks can be retried` plus `Refresh session`; the label is not a button and raw metadata is not rendered. |
| Browser viewports | Pass after fix | 1440x1024 and 1280x800 show Main Page with no horizontal scroll and visible Settings/Audit entry points. |

---

## 5. Action Label Decision

The acceptance path did not produce evidence that the current labels block a
Product 1.0 user path.

| Recovery action | Decision | Reason |
|---|---|---|
| `refresh_snapshot` | Keep as label | The current UI has event/refetch behavior; a dedicated manual refresh handler needs a separate accepted interaction design. |
| `retry_task` | Keep existing task button, keep metadata label elsewhere | Failed task retry is already exposed by backend projection when safe. Metadata labels should not duplicate state-dependent controls. |
| `retry_command` | Keep as label | Safe command replay depends on command idempotency and current surface state. |
| `open_audit` | Future button/deep link candidate | Promote only when session/task/record refs are present and the entry target is unambiguous. |
| `open_settings` | Future button/deep link candidate | Promote only where Settings is the accepted recovery surface for config/auth issues. |
| `export_diagnostics` | Future button/deep link candidate | Promote only when session/log/diagnostic refs are present and export is safe from the current state. |

---

## 6. Remaining Gaps

- Browser/Electron smoke remains release readiness and is not closed by this
  automated pass. Browser dev smoke is now covered; configured Electron smoke,
  Electron first-run smoke, packaged renderer smoke, and packaged startup
  diagnostics failure smoke are covered as of 2026-06-07. The signed runtime
  direction is accepted as a release-local launcher boundary. Launcher-backed
  package/smoke is covered by `npm run electron:smoke:launcher`, now using a
  package-local self-contained runtime candidate. Final Product 1.0 runtime
  strategy is bundled Python behind launcher. The release asset checker is
  implemented and currently blocks the external-linked runtime candidate.
  Replacing it with a signable bundled Python runtime, then signing,
  notarization, and installer UX/smoke remain open.
  The executable plan is tracked in
  [Packaging/Electron Release Plan](../plans/feature/packaging-electron-release-plan.md).
- Audit Page still lacks dedicated product-error recovery UI beyond existing
  result/evidence refs.
- Broader product error refs beyond task result failures remain follow-up
  coverage.
- A full manual local sidecar user scenario with real provider behavior remains
  separate from deterministic sidecar fixture acceptance.

---

## 7. Release Readiness Decision

Automated Product 1.0 frontend acceptance, normal browser dev smoke, Electron
dev-shell configured/first-run smoke, packaged renderer smoke, and packaged
startup diagnostics failure smoke are pass for the covered paths. The Product
1.0 unsigned package-directory runtime ownership decision is recorded:
Electron main owns Python sidecar startup and uses the repo-managed
`uv run taskweavn plato-sidecar` path. The signed runtime direction is also
recorded: Electron main keeps lifecycle ownership, while a release-local
launcher encapsulates Python runtime details. E9 launcher-backed smoke is now
covered for configured, first-run, and startup diagnostics paths. E10 replaces
the repo-local launcher runtime manifest with package-local runtime candidate
assets. E11 accepts bundled Python behind launcher as the final Product 1.0
runtime strategy. E12 implements the release asset checker and records that the
current runtime candidate is not sign-ready because Python symlinks and
`pyvenv.cfg` still point outside `Plato.app`. The next release-readiness work
is replacing that runtime with a signable bundled Python runtime, then signing,
notarization, and installer UX/smoke. Manual provider issues found in a local
sidecar user scenario remain separate follow-up evidence.
