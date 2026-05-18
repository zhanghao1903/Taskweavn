# Architecture

> Status: canonical architecture entry
> Last Updated: 2026-05-18

Architecture docs describe stable system boundaries, object lifecycles, protocols, storage/replay assumptions, and trust/runtime architecture.

---

## 1. Current Architecture

| Architecture | Product Version | Status | Entry |
|---|---|---:|---|
| A1 | Plato 1.0 | active | [A1 Overview](versions/a1-product-1.0/overview.md) |

Use [current.md](current.md) for the active architecture pointer and migration notes.

---

## 2. Canonical A1 Documents

| File | Purpose |
|---|---|
| [versions/a1-product-1.0/overview.md](versions/a1-product-1.0/overview.md) | A1 system overview, core boundaries, trust model, and reserved future spaces. |

Detailed A1 docs should be added under `versions/a1-product-1.0/` as implementation needs mature.

---

## 3. Legacy Architecture Docs

Earlier architecture documents were archived to:

```text
docs/archive/legacy-2026-05-18/architecture/
```

They remain useful source material, but they are no longer canonical entry points for new work.

When a legacy idea becomes active again, pull the relevant content into:

- an A1 architecture file;
- a capability packet;
- a contract;
- or a feature plan package.
