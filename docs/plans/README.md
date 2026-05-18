# Plans

> Status: canonical plans entry
> Last Updated: 2026-05-18

Plans are executable work packages for implementation sessions.

New product capability work should use plan packages:

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

## 1. Active Plan Areas

| Directory | Purpose |
|---|---|
| [features/](features/) | Product capability feature plan packages. |
| [release/](release/) | Packaging, signing, distribution, and release operations plans. |

---

## 2. Legacy Plans

Older single-file feature plans, broad root plans, and early UI sub-designs were archived to:

```text
docs/archive/legacy-2026-05-18/plans/
```

They are not canonical implementation plans for new work. If a legacy plan is revived, create a new package under [features/](features/) and cite the archive as source material.
