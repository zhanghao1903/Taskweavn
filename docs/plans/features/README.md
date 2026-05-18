# Feature Plan Packages

> Status: active convention
> Last Updated: 2026-05-18
> Related: [Docs Operating Model](../../project/docs-operating-model.md), [Plans README](../README.md)

---

## 1. Purpose

This directory is for product capability feature packages.

Use this shape when frontend/backend/contract/integration work should remain part of one user-facing capability plan:

```text
docs/plans/features/<feature>/
  overview.md
  contract.md
  frontend.md
  backend.md
  integration.md
  acceptance.md
```

The older single-file feature plans are archived under
`docs/archive/legacy-2026-05-18/plans/feature/`. They remain source material,
but new executable work should use package directories here.

---

## 2. First Packages To Create

See [Plato 1.0 Gap Analysis](../../product/versions/1.0/gap-analysis.md#5-required-new-plan-packages).

Initial candidates:

- `ui-backend-contract-baseline`
- `local-sidecar-api-shell`
- `main-page-real-backend`
- `settings-and-first-run`
- `task-execution-lifecycle`
- `message-confirmation-integration`
- `file-change-summary`
- `audit-trust-page`
- `product-error-handling`
- `diagnostic-bundle`
