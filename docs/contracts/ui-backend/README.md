# UI Backend Contracts

> Status: initial index
> Last Updated: 2026-05-18
> Product Version: Plato 1.0
> Architecture Version: A1
> Related: [Current Architecture](../../architecture/current.md), [Main Page Real Backend Capability](../../capabilities/main-page-real-backend/), [Plato 1.0 Overview](../../product/versions/1.0/overview.md)

---

## 1. Purpose

This directory is the stable contract authority between Plato frontend and the local Python backend sidecar.

The first implementation direction remains:

```text
Electron renderer / Vite frontend
  -> local authenticated HTTP commands and queries
  -> SSE event stream for session updates
  -> Python sidecar backed by server-core services
```

---

## 2. Initial Contract Files To Create Or Split

| Contract | Capability | Status |
|---|---|---|
| `main-page-snapshot.md` | Main Page real backend | draft source exists in product contract and frontend API types |
| `task-authoring.md` | Task authoring | to_create |
| `commands.md` | Session/task/publish/confirmation commands | draft source exists in product contract and frontend API types |
| `events-sse.md` | Session event stream | draft source exists in product contract and frontend API types |
| `settings.md` | Settings and first run | to_create |
| `audit-trust.md` | Audit / Trust page | product PRD/UX exists |
| `file-change-summary.md` | File Change Summary | to_create |
| `error-model.md` | Product-level error handling | draft source exists in frontend API types |

---

## 3. Current Existing Inputs

Existing documents and code to reconcile:

- [Plato UI API Contract](../../product/plato-ui-api-contract.md)
- [Plato Audit Page PRD](../../product/plato-audit-page-prd.md)
- [Plato Audit Page UX Flow](../../product/plato-audit-page-ux-flow.md)
- [Legacy UI Backend Communication](../../archive/legacy-2026-05-18/architecture/ui-backend-communication.md)
- [Legacy Plato Frontend Technical Design](../../archive/legacy-2026-05-18/product/plato-frontend-technical-design.md)
- `frontend/src/shared/api/types.ts`
- `frontend/src/shared/api/platoApi.ts`
- `frontend/src/pages/main-page/httpMainPageAdapter.ts`
- `src/taskweavn/task/views.py`
- `src/taskweavn/task/projection.py`
- `src/taskweavn/task/collaborator_api.py`
- `src/taskweavn/server/api_publish.py`

---

## 4. Contract First Rule

Before implementing a real backend adapter for the frontend:

1. create or update the relevant contract file here;
2. update frontend mocks to match the contract;
3. implement backend transport against the same contract;
4. add integration acceptance examples.
