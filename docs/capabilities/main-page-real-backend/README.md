# Main Page Real Backend Capability

> Status: active
> Product Version: Plato 1.0
> Architecture Version: A1
> Owner Area: full-stack

## User Problem

Users need the Main Page to control a real Plato session, not a fixture demo.

## Current System Capability

- Backend Task projection models and services exist.
- Frontend source is not part of the current canonical repository baseline; any local `frontend/` build artifacts are not treated as source of truth.
- Backend has Task projection models and services.
- UI/backend communication architecture is drafted.

## Target Capability

Main Page loads real session snapshots, sends commands, receives events, and reflects Task/message/confirmation/result/file states from the backend sidecar.

## Known Gaps

| Gap | Plan | Status | Notes |
|---|---|---|---|
| No canonical Main Page source | unplanned | open | Need tracked frontend scaffold/source before product integration. |
| No local sidecar transport for UI | unplanned | open | Need HTTP + SSE or equivalent local channel. |
| No backend snapshot adapter | unplanned | open | Need adapter from server-core views to UI contract. |
| No command transport | unplanned | open | Need command routing for session input, task input, publish, confirmation. |
| No event transport | unplanned | open | Need session event stream and cursor semantics. |

## Related Product Docs

- [Plato 1.0 Overview](../../product/versions/1.0/overview.md)
- [Plato 1.0 P0 Scope](../../product/versions/1.0/p0-scope.md)
- [Plato 1.0 Gap Analysis](../../product/versions/1.0/gap-analysis.md)

## Related Architecture Docs

- [Current Architecture](../../architecture/current.md)
- [Architecture A1](../../architecture/versions/a1-product-1.0/overview.md)

## Related Contracts

- [UI Backend Contracts](../../contracts/ui-backend/)

## Legacy Sources

- [Plato MVP PRD](../../archive/legacy-2026-05-18/product/plato-mvp-prd.md)
- [Main Page UX Flow](../../archive/legacy-2026-05-18/product/plato-main-page-ux-flow.md)
- [Frontend Technical Design](../../archive/legacy-2026-05-18/product/plato-frontend-technical-design.md)
- [UI Backend Communication](../../archive/legacy-2026-05-18/architecture/ui-backend-communication.md)
- [Task Domain UI Model Separation](../../archive/legacy-2026-05-18/architecture/task-domain-ui-model-separation.md)

## Related Code

- Future canonical frontend paths should be defined by the Main Page real backend plan.
- `src/taskweavn/task/projection.py`
- `src/taskweavn/task/views.py`

## Open Questions

- First transport implementation: FastAPI/Starlette, aiohttp, or thin stdlib server?
- Should first event stream be SSE only, with WebSocket deferred?
