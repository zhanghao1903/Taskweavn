# Post Product 1.1 Maintainability Plan

> Status: executed; follow-up only
> Last Updated: 2026-06-27
> Scope: zero-behavior maintainability work after Product 1.1 P1 closure
> Product behavior: no user-facing behavior change

---

## 1. Purpose

Product 1.1 P1 is closed for the current beta-readiness pass. The next
engineering risk is not missing capability; it is cumulative code size and
boundary drift in the Main Page, UI contract, sidecar gateway, and test layers.

This plan defines a short maintenance window for behavior-preserving cleanup
before the next major product slice.

## 2. Current Signals

Current line-count signals checked on 2026-06-27 after the post-Product 1.1
maintenance PR series and PR #172:

| Area | File | 2026-06-25 | 2026-06-27 | Current risk |
|---|---|---:|---:|---|
| Main Page controller | `frontend/src/pages/main-page/useMainPageController.ts` | 1801 | 291 | low |
| UI contract gateway | `src/taskweavn/server/ui_contract/gateways.py` | 1360 | 640 | low/medium |
| Main Page sidecar assembly | `src/taskweavn/server/main_page.py` | 1240 | 1038 | medium |
| Command gateway | `src/taskweavn/server/ui_contract/command_gateway.py` | 1068 | 983 | medium |
| Frontend API contract | `frontend/src/shared/api/types.ts` | 1344 | 1262 | high |
| Transport tests | `tests/test_ui_http_transport.py` | 2529 | 1182 | medium/high |
| Sidecar tests | `tests/test_main_page_sidecar_app.py` | 2302 | 1657 | high |
| Main Page controller tests | `frontend/src/pages/main-page/useMainPageController.test.tsx` | n/a | 770 | low/medium |
| Plato API tests | `frontend/src/shared/api/platoApi.test.ts` | n/a | 1165 | medium/high |

The highest-risk frontend controller boundary has been reduced substantially.
No broad rewrite is warranted before the next product slice. Remaining
high-signal follow-ups should be triggered by actual product work touching the
remaining hotspots, not by line count alone.

## 3. Rules

1. No product behavior changes in maintainability PRs.
2. Preserve public imports and JSON/API contracts.
3. Keep compatibility facades during the first split.
4. Move tests/fixtures with the boundary they protect.
5. Do not combine frontend, backend, and API contract refactors in one PR.
6. Delete wrappers only in a later cleanup PR after imports have moved.

## 4. Priority Slices

| Order | Slice | Goal | Status |
|---:|---|---|---|
| 1 | Main Page controller split | Move event subscription, command dispatch, input state, plan overlay, and conversation helpers out of `useMainPageController.ts`; keep the hook as composition. | Done for the current maintenance window. |
| 2 | UI contract gateway continuation | Continue splitting `gateways.py` into protocol/provider/projection/disclosure modules while keeping re-exports. | Done enough for current window; continue only when product work touches this boundary. |
| 3 | Test fixture extraction | Move large repeated fixtures/builders out of `test_ui_http_transport.py` and `test_main_page_sidecar_app.py`. | Partially done; PR #172 reduced transport tests and is merged. |
| 4 | Main Page sidecar assembly slimming | Move logging, resident AgentLoop setup, session lifecycle helpers, and audit event wrappers out of `main_page.py`. | Partially done; remaining work should be demand-driven. |
| 5 | Frontend API type split | Split `frontend/src/shared/api/types.ts` by domain only after API contract churn slows. | Started; avoid further churn until API contract stabilizes. |

## 5. Non-goals

- no new Product 1.1 feature behavior;
- no API shape changes;
- no UI redesign;
- no state management rewrite;
- no broad removal of compatibility exports in the first pass;
- no signed/notarized release work.

## 6. Acceptance Criteria

A maintainability slice is accepted only when:

1. behavior and public contracts are unchanged;
2. old imports still work or are deliberately migrated in the same PR;
3. targeted tests cover the moved behavior;
4. `git diff --check` passes;
5. the PR description names the boundary moved and the boundary intentionally
   left in place.

## 7. Closure Guidance

Treat this maintenance window as closed for Product 1.1 unless a future product
slice directly touches one of the remaining hotspots. Future maintainability
work should stay demand-driven and narrow:

1. split before adding behavior to files over 1200 lines;
2. prefer test fixture extraction when tests block iteration speed;
3. keep compatibility facades until imports have moved;
4. do not start another broad cleanup window without a concrete product
   delivery risk.
