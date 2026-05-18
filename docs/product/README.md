# Product

> Status: canonical product entry
> Last Updated: 2026-05-18

Product docs describe what users experience, what a product version promises, and what is deliberately outside scope.

---

## 1. Current Product Version

| Version | Status | Architecture | Entry |
|---|---|---|---|
| Plato 1.0 | active | A1 | [Overview](versions/1.0/overview.md) |

---

## 2. Plato 1.0 Version Package

| File | Purpose |
|---|---|
| [versions/1.0/overview.md](versions/1.0/overview.md) | Product promise, target user, core flow, architecture binding, non-goals. |
| [versions/1.0/p0-scope.md](versions/1.0/p0-scope.md) | P0 capability scope and boundaries. |
| [versions/1.0/gap-analysis.md](versions/1.0/gap-analysis.md) | Current system vs Plato 1.0 P0 gap table and required plan packages. |
| [versions/1.0/acceptance.md](versions/1.0/acceptance.md) | Product and technical acceptance checklist. |

---

## 3. Active Product Specs

These documents are active product inputs for Plato 1.0. They should be reconciled into the version package, capability packets, and contracts when their scope changes.

| File | Purpose |
|---|---|
| [plato-audit-page-prd.md](plato-audit-page-prd.md) | Product requirements for Plato Audit Page as the Trust Plane for Session and Task traceability. |
| [plato-audit-page-ux-flow.md](plato-audit-page-ux-flow.md) | Audit Page UX flow: entry, scope, overview, filters, records, details, and edge states. |
| [plato-settings-logs-audit-boundary.md](plato-settings-logs-audit-boundary.md) | Product boundary for Settings, configuration change history, Diagnostics / Logs, and Audit Page reserved links. |
| [plato-ui-api-contract.md](plato-ui-api-contract.md) | Plato Main Page 1.0 UI API contract: snapshot, ViewModel, command, event, frontend adapter, and backend integration boundaries. |

---

## 4. Legacy Product Docs

Earlier product/UX documents were archived to:

```text
docs/archive/legacy-2026-05-18/product/
```

They are source material only. New product decisions should update the active version package, a capability packet, a contract, or a Product Decision Record.
