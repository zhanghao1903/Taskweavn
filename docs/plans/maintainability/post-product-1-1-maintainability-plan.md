# Post Product 1.1 Maintainability Plan

> Status: proposed
> Last Updated: 2026-06-25
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

Current line-count signals checked on 2026-06-25:

| Area | File | Lines | Risk |
|---|---|---:|---|
| Main Page controller | `frontend/src/pages/main-page/useMainPageController.ts` | 1801 | high |
| UI contract gateway | `src/taskweavn/server/ui_contract/gateways.py` | 1360 | high |
| Main Page sidecar assembly | `src/taskweavn/server/main_page.py` | 1240 | high |
| Command gateway | `src/taskweavn/server/ui_contract/command_gateway.py` | 1068 | medium/high |
| Frontend API contract | `frontend/src/shared/api/types.ts` | 1344 | high |
| Transport tests | `tests/test_ui_http_transport.py` | 2529 | blocked-size test hotspot |
| Sidecar tests | `tests/test_main_page_sidecar_app.py` | 2302 | blocked-size test hotspot |

The problem is concentrated in a few boundary files. A broad rewrite is not
appropriate; small zero-behavior slices are.

## 3. Rules

1. No product behavior changes in maintainability PRs.
2. Preserve public imports and JSON/API contracts.
3. Keep compatibility facades during the first split.
4. Move tests/fixtures with the boundary they protect.
5. Do not combine frontend, backend, and API contract refactors in one PR.
6. Delete wrappers only in a later cleanup PR after imports have moved.

## 4. Priority Slices

| Order | Slice | Goal | Suggested validation |
|---:|---|---|---|
| 1 | Main Page controller split | Move event subscription, command dispatch, input state, plan overlay, and conversation helpers out of `useMainPageController.ts`; keep the hook as composition. | `npm run test -- useMainPageController MainPageWorkbench MainPageRoute` |
| 2 | UI contract gateway continuation | Continue splitting `gateways.py` into protocol/provider/projection/disclosure modules while keeping re-exports. | `uv run pytest tests/test_ui_query_gateway.py tests/test_ui_command_gateway.py` |
| 3 | Test fixture extraction | Move large repeated fixtures/builders out of `test_ui_http_transport.py` and `test_main_page_sidecar_app.py`. | affected pytest files only |
| 4 | Main Page sidecar assembly slimming | Move logging, resident AgentLoop setup, session lifecycle helpers, and audit event wrappers out of `main_page.py`. | `uv run pytest tests/test_main_page_sidecar_app.py` |
| 5 | Frontend API type split | Split `frontend/src/shared/api/types.ts` by domain only after API contract churn slows. | `npm run test -- platoApi` plus typecheck/lint |

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

## 7. Recommended First PR

Start with the Main Page controller split. It is the largest production hotspot
and is likely to receive more product work. The first PR should extract only
pure helpers and narrow hooks; it should not change rendering, routing, command
semantics, or snapshot behavior.
