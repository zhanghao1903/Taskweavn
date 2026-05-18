# Decisions

> Status: canonical decisions entry
> Last Updated: 2026-05-18

Decision records preserve expensive product, architecture, and technology choices.

---

## 1. Decision Families

| Family | Directory | Use For |
|---|---|---|
| PDR | [product/](product/) | Product principles, scope trade-offs, UX commitments, explicit non-goals. |
| ADR | [architecture/](architecture/) | Core object boundaries, protocols, lifecycles, storage/replay models, trust model. |
| TDR | [technology/](technology/) | Frameworks, providers, packaging choices, SDK/runtime decisions with switching cost. |

---

## 2. Naming

```text
PDR-<num>-<slug>.md
ADR-<num>-<slug>.md
TDR-<num>-<slug>.md
```

Recommended metadata:

```md
> Status: proposed | accepted | superseded | rejected
> Date: YYYY-MM-DD
> Product Version: 1.0
> Architecture Version: A1
> Capability: <capability>
> Affects: frontend, backend, release
```

---

## 3. Existing Accepted Records

Existing `ADR-*` records have been classified into decision family directories:

- [Architecture decisions](architecture/)
- [Product decisions](product/)
- [Technology decisions](technology/)
