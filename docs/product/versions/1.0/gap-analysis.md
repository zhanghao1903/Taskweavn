# Plato 1.0 Gap Analysis

> Status: active
> Last Updated: 2026-05-18
> Product Version: 1.0
> Architecture Version: A1
> Related: [P0 Scope](p0-scope.md), [Capability Map](../../../capabilities/index.md)

---

## 1. Summary

Current TaskWeavn has strong backend foundations, but Plato 1.0 still needs productization work.

The biggest gap is not a missing idea. The biggest gap is connecting existing server-core capabilities to a reliable user-facing local desktop product.

---

## 2. P0 Gap Table

| Requirement | Current Capability | Gap | Plan | Status |
|---|---|---|---|---|
| First-run provider/workspace setup | Env-based LLM config; provider/retry support; workspace layout | No Settings UI, config store, Keychain path, or connectivity test | unplanned | open |
| Main Page real backend | Frontend baseline, shared API types, HTTP adapter, backend task projection, publish persistence, and API publish transport exist | No local sidecar API binding for Main Page snapshot/commands/events; no real projection adapter wired to UI | unplanned | open |
| Task authoring | RawTask, feasibility, DraftTaskTree, Collaborator server-core | UI transport and persistence not productized | partial | open |
| Task execution | AgentLoop, TaskPublisher, SQLite TaskBus publish/read | No complete TaskBus claim/execute/update lifecycle | unplanned | open |
| Message/confirmation | MessageStream, MessageBus, WaitCoordinator, UI mock confirmations | No real UI command/event integration | unplanned | open |
| File Change Summary | ViewModel and projection protocol | No concrete collection/store/recursive aggregation | unplanned | open |
| Audit Trust page | AuditAgent, EventStream, MessageStream, observability archive, Audit Page PRD/UX | No user-facing evidence projection or implemented Audit Page | unplanned | open |
| Product error handling | Provider errors/retry, API error types | No unified product error model and recovery UX | unplanned | open |
| Diagnostic bundle | Structured logs and manifests | No one-click export/bundle/redaction policy | unplanned | open |
| Signed local app | Packaging strategy | No Electron shell, sidecar executable, signing/notarization pipeline | [packaging plan](../../../plans/release/packaging-and-distribution-strategy.md) | planned |

---

## 3. Critical Path

Recommended path:

```text
1. Contract baseline
2. Local sidecar API shell
3. Main Page real backend
4. Settings / first run
5. Task execution lifecycle
6. Message / confirmation integration
7. File Change Summary
8. Audit Trust page
9. Product error handling
10. Diagnostic bundle
11. Packaging and signed DMG
```

This order is not purely sequential. The important dependency is:

```text
contract + sidecar API
  -> frontend/backend can split implementation safely
```

---

## 4. Highest-Risk Gaps

### 4.1 UI/Backend Boundary

Risk:

- frontend and backend can drift if contracts are vague;
- UI artifacts or prototypes can look complete without validating backend semantics.

Mitigation:

- create `docs/contracts/ui-backend/` baseline before implementation;
- feature plans must include `contract.md`.

### 4.2 Task Execution Lifecycle

Risk:

- Task authoring and publishing exist, but product value requires execution state updates.

Mitigation:

- create a dedicated Task execution plan;
- keep 1.0 execution single-local-agent first;
- defer multi-agent scheduling complexity.

### 4.3 Trust Surface

Risk:

- users may not trust a system that changes files without readable evidence;
- raw logs are too technical.

Mitigation:

- build a Task-first Audit / Trust projection;
- connect File Change Summary and diagnostic bundle.

### 4.4 Packaging And Startup

Risk:

- CLI/dev setup blocks non-technical testing;
- unsigned builds are only suitable for highly trusted users.

Mitigation:

- execute packaging plan after sidecar API stabilizes;
- prioritize signed/notarized DMG before broader beta.

---

## 5. Required New Plan Packages

Create these under `docs/plans/features/`:

| Plan Package | Priority | Notes |
|---|---:|---|
| `ui-backend-contract-baseline` | P0 | May also update `docs/contracts/`. |
| `local-sidecar-api-shell` | P0 | Health, auth token, snapshot, commands, events. |
| `main-page-real-backend` | P0 | Connect the tracked frontend baseline to the real contract and local backend sidecar. |
| `settings-and-first-run` | P0 | Provider/workspace setup. |
| `task-execution-lifecycle` | P0 | TaskBus claim/execute/complete/fail. |
| `message-confirmation-integration` | P0 | Real confirmation and task-scoped inputs. |
| `file-change-summary` | P0 | Store, capture, recursive projection. |
| `audit-trust-page` | P0 | Evidence projection and page. |
| `diagnostic-bundle` | P0 | Redacted export. |
| `product-error-handling` | P0 | Error taxonomy, recovery actions, and UI states. |

---

## 6. Product Doc Drift

The legacy [Plato MVP PRD](../../../archive/legacy-2026-05-18/product/plato-mvp-prd.md) marked full Audit Page and full configuration center as out of MVP scope.

Current 1.0 planning raises both into P0, but with a constrained interpretation:

- Settings and first run are required; advanced config center can wait.
- Audit / Trust page is required; compliance-grade raw log query can wait.

This version package supersedes those old MVP scope lines for Plato 1.0.
