# Plato Figma Migration Plan

> Status: planned
> Last Updated: 2026-05-24
> Scope: Rules and phases for migrating useful ideas from old Figma files into
> the canonical Plato Figma file.
> Non-goals: no old content is migrated by this document.

## 1. Principle

Old Figma files are reference/archive only. They are not canonical design
system files, not final prototype files, and not dev handoff sources.

Migration means selectively recreating useful assets, components, screen
states, and prototype ideas in:

```text
Plato Product Design System and Prototype
```

Do not bulk-copy old pages or frames into canonical pages and call them final.

## 2. Migration Sources

| Source | Classification | Migration rule |
|---|---|---|
| `Plato MVP Main Page UX Draft` | Main Page draft/reference | Inspect for state coverage and layout patterns; recreate approved states in canonical pages. |
| Existing Audit Page draft frames | Audit Page draft/reference | Inspect for evidence timeline, filters, detail panel, and empty/error states; recreate after contract mapping is ready. |
| `Visual Exploration - Forward Workbench v0.1` | Visual exploration/reference | Extract principles only after design review; do not migrate wholesale. |
| `Plato Brand Logo and Product Mark` | Brand source/reference | Recreate approved product mark assets in `02 - Brand Assets` at source quality. |
| Historical screenshots under docs/plans/ui/images | Archive/reference | Use only as historical context, not canonical UI. |

## 3. Migration Intake Checklist

Before migrating any item, record:

| Field | Required |
|---|---|
| Source file name and URL | yes |
| Source page/frame/component | yes |
| Item type | asset, token, base component, layout component, domain component, screen state, prototype flow, dev handoff |
| Product reason | yes |
| Current source docs | yes |
| Recreate/defer/reject decision | yes |
| Canonical destination page | yes if recreated |
| Dev handoff impact | yes for components/screens |

## 4. Migration Phases

### Phase 0 - Inventory Only

Goal: understand old content without modifying Figma.

Allowed:

- read old file structure;
- list frames/components/assets;
- capture notes and screenshots for `99 - Archive References`;
- identify reusable ideas.

Not allowed:

- modifying old files;
- copying content into canonical pages;
- declaring old frames canonical.

Exit criteria:

- migration inventory exists;
- each item has recreate/defer/reject/reference-only classification.

### Phase 1 - Brand Assets

Goal: migrate approved product mark/logo assets at source quality.

Allowed:

- recreate approved product mark variants;
- add usage notes;
- create source-quality 2.5:1 or other approved ratios.

Required docs:

- `docs/product/plato-brand-and-ux-direction.md`
- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/design/figma-governance.md`

Exit criteria:

- product mark assets live in `02 - Brand Assets`;
- no visible border/frame unless part of the asset itself;
- dev usage notes say when to use each variant.

### Phase 2 - Tokens

Goal: translate visual direction into governed variables/styles.

Allowed:

- create primitive, semantic, and component token groups;
- document mapping to frontend CSS variables.

Required docs:

- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/plato-figma-ui-baseline.md`
- `docs/product/plato-frontend-technical-design.md`

Exit criteria:

- token groups exist in `01 - Tokens`;
- old draft colors are normalized into tokens or rejected;
- no screen state depends on detached old colors.

### Phase 3 - Component Library

Goal: recreate useful old UI patterns as governed components.

Required before production-grade work:

- `docs/design/component-spec.md`
- `docs/design/component-state-matrix.md`
- `docs/frontend/ui-viewmodel-contract.md`
- `docs/product/plato-frontend-technical-design.md`

Exit criteria:

- each component is base, layout, or domain;
- variants are complete enough for its interaction role;
- dev handoff row exists.

### Phase 4 - Screen States

Goal: recreate Main Page and Audit Page states from current product specs, not
from old frames alone.

Required docs:

- `docs/ux/screen-state-spec.md`
- `docs/product/canonical-status-model.md`
- `docs/product/plato-main-page-ux-flow.md` for Main Page
- `docs/product/plato-audit-page-ux-flow.md` for Audit Page
- `docs/engineering/audit-page-contract.md` for Audit Page

Exit criteria:

- screen states map to canonical state dimensions;
- loading/empty/error/partial/permission/stale states are represented where
  applicable;
- old frames are cited only as references.

### Phase 5 - Prototype Flows

Goal: wire approved screen states into product flows.

Required before high-confidence prototype work:

- `docs/ux/prototype-state-map.md`
- `docs/frontend/event-reducer-contract.md`
- `docs/frontend/api-ui-mapping.md`

Exit criteria:

- transitions preserve route context and return targets;
- Audit Page stays read-only;
- flow coverage is documented in `10 - Prototype Flows`.

### Phase 6 - Dev Handoff

Goal: make the canonical Figma file implementation-ready.

Required:

- component and state pages approved;
- frontend architecture references current;
- backend/API contract status known.

Exit criteria:

- `11 - Dev Handoff` has mapping rows:
  Figma element -> code component -> props -> backend/ViewModel source;
- missing code/API items are explicitly marked pending;
- no screenshot-only element is marked implementation-ready.

## 5. Migration Decision Values

Use these values in migration notes:

| Decision | Meaning |
|---|---|
| `recreate` | Rebuild in canonical file using current governance rules. |
| `defer` | Useful but blocked by missing docs, tokens, components, or product decision. |
| `reject` | Do not migrate because it conflicts with current product/design rules. |
| `reference_only` | Keep as archive context; no canonical design output. |

## 6. Migration Risks

| Risk | Mitigation |
|---|---|
| Old static frames become false source of truth | Mark old files reference/archive only and recreate selectively. |
| Visual exploration overrides product state model | Require canonical status and screen-state mapping before screen migration. |
| Components are copied without variants | Require component-state matrix before production component work. |
| Dev handoff implies backend exists | Require backend/ViewModel source status in every handoff row. |
| Brand asset quality regresses | Recreate brand assets at source quality; reject low-resolution screenshots. |

## 7. Migration Report Format

```text
Figma Migration Report:
- Source file:
- Source frames/components inspected:
- Items selected:
- Items recreated:
- Items deferred:
- Items rejected:
- Canonical destinations:
- Source docs checked:
- Missing blockers:
- Dev handoff impact:
- Next migration task:
```

## 8. Acceptance Criteria

- Old files are not edited.
- Canonical file remains the only production Figma destination.
- Every migrated item has source attribution and decision status.
- Recreated items follow token/component/state/prototype/handoff rules.
- Migration never bypasses current product docs or backend/frontend contracts.
