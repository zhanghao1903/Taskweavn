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

## 2. Initial Contract Files To Create

| Contract | Capability | Status |
|---|---|---|
| `main-page-snapshot.md` | Main Page real backend | to_create |
| `task-authoring.md` | Task authoring | to_create |
| `commands.md` | Session/task/publish/confirmation commands | to_create |
| `events-sse.md` | Session event stream | to_create |
| `settings.md` | Settings and first run | to_create |
| `audit-trust.md` | Audit / Trust page | to_create |
| `file-change-summary.md` | File Change Summary | to_create |
| `error-model.md` | Product-level error handling | to_create |

---

## 3. Current Existing Inputs

Existing documents and code to reconcile:

- [Legacy UI Backend Communication](../../archive/legacy-2026-05-18/architecture/ui-backend-communication.md)
- [Legacy Plato Frontend Technical Design](../../archive/legacy-2026-05-18/product/plato-frontend-technical-design.md)
- Future canonical frontend API source paths, to be created by the frontend scaffold / Main Page real backend plan.
- `src/taskweavn/task/views.py`
- `src/taskweavn/task/projection.py`
- `src/taskweavn/task/collaborator_api.py`

---

## 4. Contract First Rule

Before implementing a real backend adapter for the frontend:

1. create or update the relevant contract file here;
2. update frontend mocks to match the contract;
3. implement backend transport against the same contract;
4. add integration acceptance examples.
