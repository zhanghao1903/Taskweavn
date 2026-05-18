# TaskWeavn / Plato Docs

> Status: canonical docs entry
> Last Updated: 2026-05-18
> Rule: new work starts from this page, the capability map, and the active product version package.

---

## 1. Start Here

| Need | Start With |
|---|---|
| What are we building now? | [Plato 1.0 Overview](product/versions/1.0/overview.md) |
| What is in / out of 1.0? | [Plato 1.0 P0 Scope](product/versions/1.0/p0-scope.md) |
| What gaps remain? | [Plato 1.0 Gap Analysis](product/versions/1.0/gap-analysis.md) |
| What can the system do? | [Capability Map](capabilities/index.md) |
| What architecture version is active? | [Current Architecture](architecture/current.md) |
| How do frontend/backend agree? | [Contracts](contracts/) |
| How do we plan new work? | [Docs Operating Model](project/docs-operating-model.md) |
| What moved to archive? | [Docs Migration Inventory](project/docs-migration-inventory.md) |

---

## 2. Canonical Directory Map

| Directory | Purpose |
|---|---|
| [product/](product/) | Product version packages, scope, gap analysis, and acceptance. |
| [architecture/](architecture/) | Active architecture version and long-lived system boundaries. |
| [capabilities/](capabilities/) | Capability packets: current/planned/not-now status and gap routing. |
| [contracts/](contracts/) | Stable boundary contracts, especially UI/backend. |
| [plans/](plans/) | Executable feature/release plan packages. |
| [decisions/](decisions/) | Product, architecture, and technology decision records. |
| [project/](project/) | Roadmap, docs operating model, migration inventory. |
| [releases/](releases/) | Completed milestone and feature-slice records. |
| [issues/](issues/) | Active bug/defect records. |
| [discussion/](discussion/) | Active unresolved discussions before decision or plan. |
| [user_model/](user_model/) | User needs, scenarios, metrics, and traceability. |
| [user_cases/](user_cases/) | Active user test cases for current product versions. |
| [assets/](assets/) | Shared media assets. |
| [archive/](archive/) | Historical docs and generated exports. |

---

## 3. Current Product / Architecture

| Layer | Current |
|---|---|
| Product version | [Plato 1.0](product/versions/1.0/overview.md) |
| Architecture version | [A1 for Plato 1.0](architecture/versions/a1-product-1.0/overview.md) |
| Primary roadmap | [Global Roadmap](roadmap.md) |
| Operational roadmap | [Project Roadmap](project/roadmap.md) |
| Capability map | [Capability Map](capabilities/index.md) |

---

## 4. Workflow Rule

New product work should follow:

```text
Product version / Capability packet
  -> Contract, if boundary is affected
  -> Feature plan package
  -> Implementation session
  -> Release record
  -> Capability and gap update
```

Old docs are not the source of truth for new work. They are archived under:

```text
docs/archive/legacy-2026-05-18/
```
