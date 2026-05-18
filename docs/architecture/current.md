# Current Architecture

> Status: active pointer
> Last Updated: 2026-05-18
> Current Architecture Version: A1 for Plato 1.0
> Related: [A1 Overview](versions/a1-product-1.0/overview.md), [Plato 1.0 Overview](../product/versions/1.0/overview.md), [Capability Map](../capabilities/index.md), [Legacy Archive](../archive/legacy-2026-05-18/architecture/)

---

## 1. Canonical Architecture

The current architecture baseline is:

```text
Architecture A1 for Plato 1.0
```

Start from:

- [A1 Overview](versions/a1-product-1.0/overview.md)
- [Architecture README](README.md)
- [Docs Operating Model](../project/docs-operating-model.md)
- [Capability Map](../capabilities/index.md)
- [Contracts](../contracts/)

---

## 2. Authority Model

Old architecture documents have been archived under:

```text
docs/archive/legacy-2026-05-18/architecture/
```

They remain useful reasoning artifacts, but they are no longer active entry points.

| Legacy Area | Current Interpretation |
|---|---|
| Interaction Layer | Implemented foundation through Phase 3.8; now summarized by A1 and release records. |
| Authoring / Collaborator / Task UI model | Server-core foundation is done; current product gaps live in capability packets. |
| Bus / TaskBus | Design input for the upcoming Task execution lifecycle plan. |
| UI/backend communication | Moved to contract-first work under `docs/contracts/`. |
| Tool capability / workspace protocol | Architecture reserve for future capability platform and MCP-like adapters. Not a Plato 1.0 implementation target. |
| Multi-agent collaboration | Later-phase direction, not current 1.0 UI scope. |

---

## 3. Product Version Binding

| Product Version | Architecture Version | Status |
|---|---|---|
| Plato 1.0 | A1 | active |

Future architecture versions should be introduced when product versions change core interaction object, protocol boundaries, storage/replay assumptions, trust model, execution lifecycle, or release/runtime shape.
