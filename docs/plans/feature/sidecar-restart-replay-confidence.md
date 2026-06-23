# Sidecar Restart Replay Confidence Technical Plan

> Status: implemented for repo-mode and launcher-packaged sidecar replay smoke;
> installer fold-in remains follow-up
>
> Last Updated: 2026-06-24
>
> Scope: Product 1.1 P1 beta-depth release confidence. This plan proves durable
> Conversation / Activity replay after Product 1.1 route state is produced, the
> Electron-owned Python sidecar is relaunched against the same workspace, and
> the same durable state is re-queried. It does not add new product behavior.
>
> Related:
> [Product 1.1 Open Work](../../product/plato-1-1-open-work.md),
> [Product 1.1 P0 Release Evidence](../../product/plato-1-1-p0-release-evidence-2026-06-20.md),
> [Product 1.1 Runtime Input Router Release Evidence](../../releases/product-1-1-runtime-input-router-release-evidence.md),
> [Runtime Input Router Contract](runtime-input-router-contract.md),
> [Session Conversation / Activity Timeline](session-conversation-activity-timeline.md)

## 1. Goal

Prove that Product 1.1 durable collaboration state survives a backend process
restart:

```text
seed session activity
  -> kill Electron-owned sidecar
  -> relaunch sidecar against the same workspace
  -> reload/requery Main Page
  -> Conversation / Activity / Audit refs replay without duplication or loss
```

The existing Product 1.1 evidence covers renderer reload and normal configured,
packaged, and installer smoke. This slice closes the narrower sidecar restart
confidence gap.

## 2. Minimal Scenario

The smoke creates or reuses a deterministic session containing:

- one read-only inquiry answer with evidence refs;
- one no-effect router activity;
- one durable Activity item linked to Audit or diagnostics;
- one selected task scope.

Then the harness starts the Electron-owned Python sidecar process against the
same workspace, captures replayed state, stops that sidecar, relaunches it,
waits for readiness, and re-queries the same session.

## 3. Acceptance Criteria

- The same session opens after sidecar restart.
- Conversation message count is stable: no missing records and no duplicate
  records caused by replay.
- Activity records replay with the same titles, scopes, timestamps, and safe
  evidence refs.
- Audit and diagnostic refs still resolve after restart.
- The UI leaves transient loading/understanding states and renders the replayed
  session.
- The test does not mutate workspace files beyond the deterministic smoke
  fixture.

## 4. Implementation Slices

1. Add `electron:smoke:sidecar-restart` or an equivalent smoke flag.
2. Reuse the configured Product 1.1 route matrix fixture where possible.
3. Add a harness-level sidecar kill/relaunch step that targets the owned Python
   process, not only the renderer.
4. Add snapshot/activity/audit replay assertions after readiness returns.
5. Run first against repo-mode Electron sidecar lifecycle, then against packaged
   launcher smoke, then installer smoke if stable.
6. Update Product 1.1 release evidence and open-work status after the smoke is
   accepted.

## 5. Non-Goals

- No new Session, Plan, Task, ASK, or Activity product semantics.
- No hard recovery for actively running execution tasks.
- No signed/notarized installer work.
- No broad rewrite of Electron sidecar ownership.

## 6. Risks

- Renderer reload can mask the real sidecar restart path; the harness must
  explicitly kill the sidecar process.
- SSE cursors may be stale after restart; snapshot re-query must be treated as
  the durable recovery path.
- SQLite locks or stale runtime state may surface only in packaged/installer
  mode.
- Re-running commands after restart would create false duplicates; assertions
  must query existing durable state instead.

## 7. Implementation Status

Implemented smoke commands:

```bash
npm run electron:smoke:sidecar-restart
npm run electron:smoke:sidecar-restart:launcher
```

Current coverage:

- seeds deterministic Product 1.1 sidecar state in a temporary workspace;
- creates one read-only inquiry answer with safe evidence refs;
- starts the Electron sidecar lifecycle process against the same workspace,
  captures replayed state, stops it, and starts it again;
- re-queries `snapshot`, `activity`, audit record, and audit evidence after the
  restart;
- asserts stable message IDs, Activity IDs, read-only inquiry Activity payload,
  Audit refs, evidence refs, and fixture file content.
- `:launcher` builds `dist-electron-launcher` and repeats the same replay
  assertions through the package-local sidecar launcher and bundled Python
  runtime.

Remaining follow-up:

- fold the same replay confidence into mounted installer smoke if release
  cadence needs installer-level replay evidence.
