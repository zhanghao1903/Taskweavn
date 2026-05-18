# Docs Migration Inventory

> Status: active migration tracker
> Last Updated: 2026-05-18
> Related: [Docs Operating Model](docs-operating-model.md), [Capability Map](../capabilities/index.md), [Legacy Archive](../archive/legacy-2026-05-18/)

---

## 1. Purpose

This file records the docs reorganization state so future sessions know which paths are canonical and which paths are historical.

The current strategy is:

```text
new docs are authoritative
  -> old docs are archived for traceability
  -> active work starts from product/version/capability/contract/plan packages
```

---

## 2. Canonical Control Plane

| Area | Status | Entry |
|---|---:|---|
| Docs operating model | active | [docs-operating-model.md](docs-operating-model.md) |
| Global roadmap | active | [../roadmap.md](../roadmap.md) |
| Project plan | active | [roadmap.md](roadmap.md) |
| Capability map | active | [../capabilities/index.md](../capabilities/index.md) |
| Plato 1.0 version package | active | [../product/versions/1.0/overview.md](../product/versions/1.0/overview.md) |
| Architecture A1 package | active | [../architecture/versions/a1-product-1.0/overview.md](../architecture/versions/a1-product-1.0/overview.md) |
| UI/backend contracts entry | active | [../contracts/ui-backend/](../contracts/ui-backend/) |
| Decision family directories | active | [../decisions/](../decisions/) |
| Feature package convention | active | [../plans/features/](../plans/features/) |
| Release plans | active | [../plans/release/](../plans/release/) |

---

## 3. Legacy Archive

Historical docs were moved to:

```text
docs/archive/legacy-2026-05-18/
```

| Archive Area | Contents |
|---|---|
| `architecture/` | Old architecture notes and detailed technical designs. |
| `product/` | Old PRD, UX, brand, frontend, and product direction docs. |
| `plans/` | Old root plans, single-file feature plans, UI plans, and planning seeds. |
| `discussion/` | Exploratory discussions promoted before this docs model. |
| `issues/` | Historical issue docs. |
| `project/` | Historical project roadmap/task publisher docs. |
| `root/` | Old root-level docs such as planning workflow and configuration. |
| `user_cases/` | Historical manual user cases and terminal outputs. |

Archive docs should not be edited as active plans. If a historical idea becomes current again, promote it into a new canonical doc and link the archive as source material.

---

## 4. Migration Result

| Old Shape | Current Treatment |
|---|---|
| `docs/plans/feature/*.md` | Archived. New feature work uses `docs/plans/features/<feature>/`. |
| `docs/plans/ui/` | Archived. Current UI work routes through product version docs, capability packets, and contracts. |
| Root `docs/plans/*.md` | Archived unless reintroduced as feature/release plan packages. |
| Top-level `docs/decisions/ADR-*.md` | Moved into product / architecture / technology decision families. |
| `docs/architecture/*.md` detailed designs | Archived. Current pointer is `docs/architecture/current.md`; active version is A1. |
| `docs/product/plato-*.md` | Archived. Current product baseline is `docs/product/versions/1.0/`. |
| `docs/user_cases/UC-*.md` | Archived. New user tests should be written against current Plato 1.0 capabilities. |

---

## 5. Remaining Cleanup Candidates

| Candidate | Suggested Destination | Priority | Notes |
|---|---|---:|---|
| Concrete UI/backend API files | `docs/contracts/ui-backend/*.md` | P0 | Create during Main Page real backend / contract baseline plan. |
| Feature package details for P0 gaps | `docs/plans/features/<feature>/` | P0 | Create from capability packets. |
| New Plato 1.0 user tests | `docs/user_cases/` | P1 | Should follow current UI/product workflow, not old CLI-only cases. |
| Architecture A1 subdocuments | `docs/architecture/versions/a1-product-1.0/` | P1 | Add only when overview becomes too dense. |
| Decision indexes | decision family READMEs | P2 | Keep family indexes current as new records are added. |

---

## 6. Migration Rule

When a future session finds useful content in archive:

1. keep the archive file intact;
2. create or update the canonical doc in the active tree;
3. cite the archive file as source material if helpful;
4. avoid linking archive docs as normal workflow entry points.
