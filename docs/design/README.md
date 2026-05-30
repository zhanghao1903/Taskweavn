# Design Governance

This directory governs Plato Figma work and design-system handoff.

| File | Purpose |
|---|---|
| [figma-governance.md](figma-governance.md) | Canonical Figma file, page structure, creation rules, migration rules, and report formats. |
| [figma-file-registry.md](figma-file-registry.md) | Canonical Figma file URL/key/page registry and creation status. |
| [figma-new-file-plan.md](figma-new-file-plan.md) | Plan for creating the new canonical Figma file skeleton. |
| [figma-migration-plan.md](figma-migration-plan.md) | Rules for selectively recreating old Figma content in the canonical file. |
| [figma-readiness-checklist.md](figma-readiness-checklist.md) | Gate checklist for assets, tokens, components, states, prototypes, and dev handoff. |
| [figma-layout-contract.md](figma-layout-contract.md) | Layout/readability contract for Screen State and Dev Handoff Figma frames. |
| [visual-baseline-alignment.md](visual-baseline-alignment.md) | Read-only audit comparing canonical Figma pages with the historical Main Page visual baseline. |
| [layout-components-visual-upgrade-brief.md](layout-components-visual-upgrade-brief.md) | Governed upgrade targets for `04 - Layout Components` before Figma visual alignment work. |
| [domain-components-visual-upgrade-brief.md](domain-components-visual-upgrade-brief.md) | Governed upgrade targets for `05 - Domain Components` before Main/Audit screen-state recomposition. |
| [design-system.md](design-system.md) | Minimal production-grade token and component-layer contract. |
| [typography-system.md](typography-system.md) | Font family, type scale, text color semantics, and typography usage rules. |
| [component-spec.md](component-spec.md) | Component inventory, Figma-to-code mapping, and readiness contract. |
| [component-state-matrix.md](component-state-matrix.md) | Required variants and states for base, layout, and domain components. |
| [dev-handoff.md](dev-handoff.md) | Governed Figma-to-frontend mapping for tokens, components, states, flows, ViewModels, API gaps, and P5 architecture input. |
| [../ux/prototype-state-map.md](../ux/prototype-state-map.md) | Main Page and Audit Page prototype state and transition map. |

Canonical Figma file name:

```text
Plato Product Design System and Prototype
```

Canonical Figma file URL:
[Plato Product Design System and Prototype](https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA).

File key and page IDs are recorded in
[figma-file-registry.md](figma-file-registry.md).

Old Figma files are reference/archive only.

Current P4 acceptance:

- `04 - Layout Components` is accepted as the product-aligned layout reference.
- `05 - Domain Components` is accepted for domain component skeleton and
  semantic coverage.
- Acceptance does not include final visual polish, production copy, frontend
  implementation, responsive/mobile final design, visual regression baseline,
  or full dev handoff readiness.
