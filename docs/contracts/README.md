# Contracts

> Status: active index
> Last Updated: 2026-05-18
> Related: [Docs Operating Model](../project/docs-operating-model.md), [Current Architecture](../architecture/current.md), [UI Backend Contracts](ui-backend/)

---

## 1. Purpose

Contracts are long-lived boundary agreements. They are stricter than plans and more implementation-facing than architecture docs.

Use contracts for:

- frontend/backend APIs;
- command and event semantics;
- viewmodel shape;
- error models;
- local sidecar startup/shutdown boundaries;
- compatibility expectations between independently implemented surfaces.

Feature plan `contract.md` files are proposed deltas. Completed and stable contract details should be merged back here.

Legacy UI/backend communication notes are archived under
`docs/archive/legacy-2026-05-18/architecture/`. They can be mined for detail,
but this directory owns active contract shape.

---

## 2. Contract Areas

| Area | Purpose | Status |
|---|---|---|
| [UI Backend](ui-backend/) | Main Page, Settings, Audit, events, commands, errors. | initial index |

---

## 3. Contract Rules

1. Cross-boundary implementation starts from contract.
2. Frontend mocks must follow the contract.
3. Backend transport must satisfy the contract.
4. UI-visible response shape changes require contract updates.
5. Product error states must be represented in the contract, not buried in implementation notes.

---

## 4. Minimum Contract Template

```md
# <Contract Name>

> Status: draft | active | deprecated
> Product Version:
> Architecture Version:
> Related Capability:

## Purpose

## Query APIs

## Command APIs

## Events

## ViewModels

## Error Model

## Idempotency And Versioning

## Examples

## Compatibility Notes
```
