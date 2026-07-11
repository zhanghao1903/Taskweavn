# Architecture Review Fact Calibration Log

> Source document: `docs/architecture/review.md`
> Preserved original: `docs/architecture/review.original.md`
> Calibration date: 2026-07-10
> Scope: replace the 2026-05-09 concept-era self-review with an evidence-based
> review of the current local-first Product 1.1 architecture.

## 1. Workflow Gate Report

- User request summary: fact-calibrate architecture documents one by one,
  preserve each original, replace the active document, and add a per-document
  evidence log.
- Detected workflow phase: P5 architecture assessment, using P7/P8
  implementation and P9 release/test evidence.
- Task type: documentation-only architecture review correction.
- Required upstream artifacts:
  - original review and every document it assessed;
  - current calibrated architecture set;
  - current backend/frontend implementation;
  - ADRs, plans, release evidence, CI configuration, and tests.
- Found artifacts:
  - calibrated current architecture and fix logs;
  - 20 ADR files;
  - Product 1.1 beta/formal release notes and runtime evidence;
  - backend, frontend, E2E, Electron, and sidecar smoke assets;
  - current GitHub Actions workflow and package scripts.
- Missing or weak artifacts:
  - no generated architecture metrics/report;
  - at calibration time CI did not run the requested backend/frontend/E2E
    matrix; a 2026-07-11 follow-up adds it, while branch-protection enforcement
    remains unavailable on the current private-repository plan;
  - several cross-store guarantees remain documented as limitations rather than
    unified invariants.
- Implementation allowed now: yes, for documentation-only review calibration.
- Prework required: separate verified facts from evaluative scoring and avoid
  penalizing explicitly out-of-scope future features as current bugs.
- Execution scope: preserve/rewrite `review.md`, add this log, collect test/CI
  evidence, and run current validation. No code changes.
- Acceptance criteria:
  - historical review remains available;
  - old concept claims are reconciled against current source;
  - findings are evidence-backed and severity-ordered;
  - scores publish criteria and weights;
  - current scope limitations are separated from conditional future work;
  - backend/frontend document validation passes.
- Risks and assumptions:
  - architecture scoring is inherently evaluative;
  - test quantity does not prove coverage quality;
  - release notes prove recorded validation, not continuous CI enforcement;
  - current user goal is document truth, not implementation of the findings.

## 2. Original Preservation

- Original Git blob: `2958e6603fa35609ca9deaace8da26ee910c7d72`.
- Preserved path: `docs/architecture/review.original.md`.
- Pre-calibration working-tree hash matched `HEAD`.
- Original length: 151 lines.
- Original review date: 2026-05-09.
- It reviewed early `overview/task/session/agent/bus/bus-v2` concepts and already
  labeled itself historical, but the body retained outdated present-tense
  strengths, gaps, scores, and roadmap links.

## 3. Evidence Inspected

### 3.1 Current Architecture

- Every active non-README architecture document processed before this file,
  including its fix log and preserved original.
- Especially:
  - `overview.md`
  - `reference.md`
  - `agent.md`
  - `task.md`
  - `bus.md`
  - `interaction-layer.md`
  - `llm-provider-reliability.md`
  - `context-manager.md`
  - `configurable-logging-system.md`
  - `authoring-domain.md`
  - `authoring-command-protocol.md`
  - `task-domain-ui-model-separation.md`
  - `taskbus-service-multi-execution-env.md`
  - `tool-capability-layer.md`
  - `workspace-communication-protocol.md`
  - `multi-agent-collaboration.md` and English counterpart.

### 3.2 Implementation Evidence

- Task/authoring/context/interaction/LLM/logging/usage/Execution Plane/server
  code under `src/taskweavn/`.
- Frontend API, Main Page, Audit, Settings, diagnostics, usage, and E2E code
  under `frontend/src/`.
- Product error taxonomy and frontend recovery mappings.
- ExecutionEnv policy models and actual generic/handler-specific enforcement.
- Frontend high-token warning implementation.

### 3.3 Decisions And Release Evidence

- `docs/decisions/ADR-0001` through `ADR-0020`.
- `docs/releases/product-1-1-formal-release-notes.md`.
- `docs/releases/product-1-1-beta-external-release-notes.md`.
- Product 1.1 runtime router release evidence and component release records.
- Feature plans for product errors, token usage, logging, context, execution,
  interaction, packaging, and remote/dynamic foundations.

### 3.4 Test And CI Inventory

- 141 top-level backend `test_*.py` files.
- `uv run pytest --collect-only -q`: `1520 tests collected in 1.29s`.
- 69 `.test.ts` / `.test.tsx` files under `frontend/src`.
- Five frontend sidecar-backed E2E files.
- Electron dev, packaged, installer, launcher, workspace, and restart smoke
  scripts in `frontend/scripts/`.
- The calibration-time GitHub Actions workflow was
  `.github/workflows/product-1-0-frontend-integration.yml` and invoked only
  `npm run test:e2e:sidecar`.
- The 2026-07-11 follow-up replaces it with
  `.github/workflows/required-ci.yml`, covering complete backend tests,
  frontend test/lint/build, sidecar E2E, and an aggregate gate.

## 4. Historical Claims Reconciled

1. `CreateTaskTool` is not a current core innovation because it does not exist;
   task creation/revision is command-backed.
2. Constraint-driven Agent graph generation remains unimplemented.
3. `IOScope` and bus-v2 conflict scheduling remain target design.
4. LLM Task scheduling and assignment rationale are not current runtime facts.
5. Error handling evolved from a gap into product taxonomy, provider retry,
   Task retry, recovery labels, and diagnostic refs, with remaining holes.
6. Security evolved from “not discussed” to several local controls, but not a
   unified enforced permission system.
7. Observability evolved into structured logging, Event/Audit/diagnostics,
   inspection evidence, and usage analytics, with privacy/process limitations.
8. HITL evolved into authoring ASK, execution ASK, confirmation, Router input,
   and frontend states, with convergence asymmetry.
9. Cost evolved into token visibility and a static warning, not budget/quota
   enforcement.
10. Storage is concrete SQLite, making cross-store consistency the current
    concern.
11. Runtime/settings/LLM/logging configuration exists, but consumer/enforcement
    coverage is partial.
12. Test strategy is no longer empty; continuous CI coverage remains narrower
    than local assets.
13. End-to-end evidence exists in overview, release records, E2E, and smoke
    scripts.

## 5. Verified Current Findings

1. Local Product 1.1 has a real router-first, command-backed, fixed-route
   execution loop.
2. Dynamic Agent assignment, Agent Manager, remote workers, and multi-writer
   merge are not current features.
3. TaskBus remains the Published Task lifecycle authority.
4. Main Page fixed-route execution normally serializes work through one worker.
5. TaskBus itself does not enforce a global one-running-task guard.
6. Interaction facts span AskStore/MessageStream and TaskBus without a shared
   transaction.
7. ASK has recovery; confirmation does not have an equivalent service.
8. Direct confirmation response does not request execution dispatch.
9. Message response uniqueness/options are not fully enforced.
10. Main Page has broad local writer/shell tools with path protection but no
    unified runtime permission profile.
11. Generic Execution Plane policy enforcement covers only part of its DTO.
12. Raw LLM and trace logs can contain sensitive content beyond current key
    redaction.
13. Provider timeout/fallback/circuit/failed-usage evidence remains incomplete.
14. Product facts are distributed across deliberate authorities and several
    compatibility projections.
15. Plan/TaskNode and DraftTaskTree paths coexist.
16. Core and Main Page Session status use different algorithms/vocabularies.
17. Usage analytics records successful ChatResponse and has no budget enforcer.
18. Frontend “Budget” is a static high-token warning at one million tokens.
19. The repository has broad backend/frontend/E2E/smoke test assets.
20. Current GitHub CI runs the requested backend, frontend, and sidecar E2E
    matrix for every PR; GitHub plan limits prevent enforcing its aggregate
    result through `main` branch protection.
21. Formal Product 1.1 distribution is local macOS Apple Silicon, unsigned and
    not notarized.

## 6. Review Corrections Applied

- Replaced novelty/completeness/intuitiveness scoring with implementation-risk
  dimensions.
- Marked scores as evaluative and published weights/criteria.
- Replaced unimplemented “strengths” with current authority, closure, recovery,
  trust, and current/future separation evidence.
- Converted the old gap table into current severity-ordered findings.
- Reconciled every major 2026-05 gap against current implementation.
- Added cross-store consistency, tool policy, sensitive logs, LLM failure
  evidence, compatibility complexity, concurrency assumptions, CI, cost, and
  public distribution findings.
- Distinguished current-scope limitations from conditional future features.
- Reordered the roadmap so current local invariants are hardened before dynamic
  routing or remote execution.

## 7. Validation Plan

- Run the complete backend test suite and record pass/skip counts.
- Run the complete frontend Vitest suite and record file/test counts.
- Run `git diff --check` for the three review artifacts.
- Verify all active-document and evidence links.
- Confirm the original hash still matches `HEAD`.

## 8. Validation Record

Validation completed on 2026-07-10:

- Original preservation:
  - `git hash-object docs/architecture/review.original.md` returned
    `2958e6603fa35609ca9deaace8da26ee910c7d72`.
  - `git rev-parse HEAD:docs/architecture/review.md` returned the same blob id.
- Backend inventory:
  - `uv run pytest --collect-only -q` collected `1520 tests in 1.29s`.
- Complete backend run:
  - `uv run pytest -q` returned
    `3 failed, 1507 passed, 10 skipped in 59.32s`.
  - Reproducible failures:
    - two read-only inquiry sidecar acceptance tests received outcome
      `dispatched` instead of expected `answered`;
    - the minimal Main Page snapshot fixture no longer round-trips to identical
      canonical contract JSON.
  - Running only those three tests reproduced `3 failed in 2.26s`.
- Complete frontend run:
  - `npm test -- --reporter=dot` returned
    `1 failed, 557 passed, 6 skipped` across `78` files in `20.07s`.
  - The failure was the App resync transient-state assertion for “Resyncing”.
  - Targeted rerun of that test passed (`1 passed`, 34 non-selected tests
    skipped), so the observed failure is timing/order-sensitive rather than
    deterministically reproducible in isolation.
- Current CI command:
  - `npm run test:e2e:sidecar` could not start its child `uv` fixtures inside
    the filesystem sandbox because the child process could not access the
    user-level uv cache.
  - An unsandboxed retry was not available after approval review rejection, so
    this turn does not claim a fresh sidecar-E2E result.
  - The failure happened before product E2E tests executed and is not counted as
    a product test failure.
- Document checks:
  - preserved original hash matches `HEAD`;
  - relative architecture/fix-log links exist;
  - no source or frontend files were changed;
  - `git diff --check` passed for the review document artifacts.

## 9. Follow-Up Boundary

- This document records architecture findings; it does not implement them.
- `session.md` remains the final non-README architecture calibration target.
- README should be updated only after every document set and completion audit is
  finished.

## 10. Baseline Follow-Up Record

After the architecture calibration was committed independently as `2173573`,
the recorded baseline issues were handled in document order on 2026-07-10:

1. The two read-only inquiry acceptance tests now opt out of unrelated pending
   ASK and confirmation state added later to the shared sidecar fixture. The
   production Router and its active-ASK precedence were not changed.
2. `main_page_snapshot.min.json` now includes the three current model defaults
   missing from the golden fixture: `activePlan.archivedAt`, `archivedPlans`,
   and message `conversationRender`.
3. The App resync test now holds the refetch with a test-controlled promise
   instead of relying on an 80 ms wall-clock observation window.
4. The sidecar E2E command was retried outside the filesystem sandbox so its
   child `uv` processes could read the existing user cache.

Follow-up validation:

- targeted inquiry and related sidecar checks: `14 passed`;
- backend contract/model/plan checks: `23 passed`;
- frontend shared contract fixture: `7 passed`;
- resync test: 8 concurrent targeted runs passed;
- complete App test file: `35 passed`;
- complete backend suite: `1510 passed, 10 skipped in 47.87s`;
- complete frontend suite: `558 passed, 6 skipped` across 78 files in `8.15s`;
- sidecar-backed E2E: 5 files and 6 tests passed;
- frontend lint: 0 errors and 2 pre-existing Fast Refresh warnings;
- frontend TypeScript/Vite build: passed with the existing chunk-size warning;
- Ruff on the changed Python test files: passed.

This closes the four recorded local baseline issues. The next follow-up closes
the requested workflow coverage gap while recording the separate remote
enforcement limitation.

## 11. Required CI Follow-Up Record

On 2026-07-11, the path-filtered sidecar-only workflow was replaced with
`.github/workflows/required-ci.yml`.

Current workflow facts:

- trigger every pull request, every push to `main`, and manual dispatch;
- `Backend Tests` installs the locked development environment and runs
  `uv run pytest -q`;
- `Frontend Test, Lint, and Build` runs the complete Vitest suite, ESLint, and
  the TypeScript/Vite production build;
- `Sidecar E2E Acceptance` installs both Python and Node dependencies and runs
  `npm run test:e2e:sidecar`;
- `Required CI Gate` uses `always()` and fails unless all three validation jobs
  report `success`;
- PR path filters were removed, so the stable gate is created for every PR.

Remote enforcement fact:

- the authenticated repository account has admin permission;
- `main` branch-protection inspection returned HTTP 403 with GitHub's explicit
  response: upgrade to GitHub Pro or make the private repository public;
- the workflow therefore provides check results and one aggregate gate, but
  GitHub cannot currently require that gate before merge;
- once the plan or repository visibility changes, `Required CI Gate` is the
  single context to add to `main` branch protection.

Pre-push validation on 2026-07-11:

- workflow YAML parsed successfully and structural assertions confirmed all
  three triggers, four jobs, aggregate dependencies, and `always()` behavior;
- complete backend suite: `1510 passed, 10 skipped in 47.63s`;
- complete frontend suite: `558 passed, 6 skipped` across 78 files in `7.61s`;
- frontend lint: 0 errors and 2 pre-existing Fast Refresh warnings;
- frontend TypeScript/Vite build: passed with the existing chunk-size warning;
- sidecar-backed E2E: 5 files and 6 tests passed.
