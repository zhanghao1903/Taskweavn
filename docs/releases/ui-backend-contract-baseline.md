# Release: UI/backend Contract Baseline

> Status: done
> Date: 2026-05-20
> Work Stream: Phase 3E — Task-first UI System
> Related Plan: [UI/backend Contract Baseline](../plans/feature/ui-backend-contract-baseline.md)
> Technical Design: [UI/backend Contract Baseline Technical Design](../plans/feature/ui-backend-contract-baseline-technical-design.zh-CN.md)
> Architecture: [UI And Backend Communication](../architecture/ui-backend-communication.md), [Task Domain/UI Model Separation](../architecture/task-domain-ui-model-separation.md)

---

## 1. Summary

This release establishes the framework-neutral backend contract baseline for Plato's Main Page.

The backend now has explicit transport-facing models and gateways for UI snapshots, commands, events, and errors. These models sit between server-core Task projections / command services and the future local sidecar HTTP/SSE transport.

The main outcome is that the next sidecar work can expose a stable contract instead of leaking internal Task, authoring, message, or SQLite shapes directly to the frontend.

---

## 2. Shipped

### 2.1 Contract Package

Added `taskweavn.server.ui_contract` with:

- shared camelCase/frozen/forbid-extra base model behavior;
- `ApiError`;
- `QueryResponse`, `CommandRequest`, `CommandResponse`, `CommandResult`, and `RefreshHint`;
- `ObjectRef`, `AffectedObjectRef`, and `AffectedScope`;
- transport-facing ViewModels for project, workflow, session, Task tree/node, messages, confirmations, results, file changes, and audit links;
- `MainPageSnapshot`;
- `UiEvent` and canonical event constructors.

### 2.2 Mapping Boundary

Added deterministic mapping functions from `taskweavn.task.views` server-core read models into transport-facing UI contract models.

`taskweavn.task.views` remains a server-core projection/read-model package, not the frontend transport contract.

### 2.3 Query Gateway

Added `DefaultUiQueryGateway.get_session_snapshot()`.

The query gateway composes:

- `SessionReader`;
- `TaskProjectionService`;
- lightweight project/workflow providers;
- mapping adapters.

It does not introduce HTTP/SSE and does not reimplement Task projection logic.

### 2.4 Command Gateway

Added `DefaultUiCommandGateway` wrappers for:

- session input;
- Task tree generation;
- Task node update;
- task-scoped input;
- Task tree publish;
- confirmation resolution.

The gateway wraps existing Collaborator and Task command services into UI `CommandResponse` envelopes with stable error and refresh semantics.

### 2.5 Event Projection

Added pure `UiEvent` constructors for:

- session status changes and resync;
- Task tree/node changes;
- message append;
- confirmation create/resolve;
- result/file/audit updates;
- command completion/failure.

Events remain thin patch hints. Durable replay, SSE framing, and cursor retention are intentionally deferred to the sidecar/SSE plan.

### 2.6 Frontend Contract Parity

Aligned frontend TypeScript contract types and tests with backend additions:

- `ObjectRef`;
- `AffectedObjectRef`;
- `AffectedScope`;
- richer `CommandResult`;
- `permission_denied`;
- canonical `UiEventType` values.

Added shared JSON fixtures under `tests/fixtures/ui_contract/` and frontend tests that consume those backend contract fixtures through TypeScript types.

---

## 3. Validation

Final validation:

- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run pytest` — 730 passed
- `uv run pytest tests/test_ui_contract_fixtures.py` — 3 passed
- `npm test -- backendContractFixtures.test.ts` from `frontend/` — 3 passed
- `npm test` from `frontend/` — 49 passed
- `npm run build` from `frontend/`
- `npm run lint` from `frontend/`
- `git diff --check`

The shared fixture checks are intentionally small but strict:

- Python validates fixture JSON through Pydantic contract models and compares canonical `model_dump(mode="json")` output.
- Frontend imports the same JSON fixtures and consumes them through `QueryResponse<MainPageSnapshot>`, `CommandResponse`, and `UiEvent` types.

---

## 4. Follow-ups

- Implement the local sidecar API shell for the Plato UI.
- Add a durable SSE cursor/replay plan before relying on event replay across process boundaries.
- Connect Main Page to real backend gateways instead of fixture/mock adapters.
- Add richer query endpoints after snapshot integration proves the main contract.
- Keep shared fixtures updated whenever backend contract fields change.
