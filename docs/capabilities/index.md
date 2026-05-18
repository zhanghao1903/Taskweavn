# Capability Map

> Status: active index
> Last Updated: 2026-05-18
> Product Version: Plato 1.0
> Architecture Version: A1
> Related: [Docs Operating Model](../project/docs-operating-model.md), [Plato 1.0 Overview](../product/versions/1.0/overview.md), [Plato 1.0 Gap Analysis](../product/versions/1.0/gap-analysis.md)

---

## 1. Purpose

This file is the system capability map. It answers:

- what the current system can do;
- what Plato 1.0 needs;
- which gaps have routed plans;
- which gaps are still unplanned.

Each important capability has a packet under `docs/capabilities/<capability>/`.

---

## 2. Plato 1.0 Capability Summary

| Capability | Current Status | 1.0 Priority | Gap Summary | Routed Plan |
|---|---|---:|---|---|
| [Main Page real backend](main-page-real-backend/) | active | P0 | Frontend baseline and backend projection exist, but no sidecar snapshot/command/event integration. | unplanned |
| [Settings and first run](settings-and-first-run/) | planned | P0 | Provider config exists through env; no user-facing setup or secure secret store. | unplanned |
| [Task authoring](task-authoring/) | current / active | P0 | Server-core authoring exists; UI transport and persistence need productization. | partial |
| [Task execution](task-execution/) | planned | P0 | Task publishing exists; TaskBus claim/execute/update loop is incomplete. | unplanned |
| [Message and confirmation](message-and-confirmation/) | current / active | P0 | Message substrate exists; UI event/command integration is still missing. | unplanned |
| [Audit trust](audit-trust/) | planned | P0 | Audit/logging facts and product PRD/UX exist; user-facing implementation and evidence projection are missing. | unplanned |
| [File change summary](file-change-summary/) | planned | P0 | ViewModel interface exists; real collection, storage, and parent-child aggregation are missing. | unplanned |
| [Diagnostic bundle](diagnostic-bundle/) | planned | P0 | Observability archive exists; one-click bundle/export/redaction is missing. | unplanned |
| [Product error handling](product-error-handling/) | planned | P0 | Provider/core errors exist; user-facing recovery model is missing. | unplanned |
| [Packaging and distribution](packaging-and-distribution/) | planned | P0 | Strategy exists; Electron/Python sidecar package and notarized DMG are missing. | [release plan](../plans/release/packaging-and-distribution-strategy.md) |
| [Configuration control plane](configuration-control-plane/) | planned | P1/P0 dependency | Logging control exists; general runtime config store/bus/effective snapshots are missing. | unplanned feature package; legacy source archived |

---

## 3. Status Legend

| Status | Meaning |
|---|---|
| `current` | Implemented and usable as current system capability. |
| `active` | Being shaped for Plato 1.0. |
| `planned` | Needed, but not yet implemented. |
| `partial` | Some plans or implementation exist, but the 1.0 path is incomplete. |
| `unplanned` | Known gap without an executable plan package yet. |
| `not_now` | Known capability intentionally outside Plato 1.0. |
| `wont_do` | Explicitly rejected unless assumptions change. |

---

## 4. Unplanned P0 Gaps

These should become feature plan packages before implementation starts:

1. `main-page-real-backend`
2. `settings-and-first-run`
3. `task-execution`
4. `message-and-confirmation`
5. `audit-trust`
6. `file-change-summary`
7. `diagnostic-bundle`
8. `product-error-handling`

Recommended feature plan package shape:

```text
docs/plans/features/<feature>/
  overview.md
  contract.md
  frontend.md
  backend.md
  integration.md
  acceptance.md
```

---

## 5. Not In Plato 1.0

| Capability | Status | Reason |
|---|---|---|
| Multi-user collaboration | not_now | Personal assistant product scope; multi-user would heavily complicate interaction and permissions. |
| Full multi-agent canvas | not_now | Task-first UI should stay simple; agent routing remains an advanced/system capability. |
| Marketplace / third-party tool registry | not_now | Architecture reserves capability/tool protocol space, but 1.0 should not carry platform complexity. |
| Complex workflow engine | not_now | Pipeline and publishing are enough for first product loop; conditional/looping workflow can wait. |
| Mobile companion control | not_now | Desktop local-first delivery comes first. |
| Enterprise permission/compliance system | not_now | 1.0 targets local single-user use. |
