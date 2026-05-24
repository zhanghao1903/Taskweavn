# Plato Figma New File Plan

> Status: planned
> Last Updated: 2026-05-24
> Scope: Plan for creating the new canonical Plato Figma file skeleton.
> Non-goals: no Figma operation has been performed by this document.

## 1. Goal

Create a new governed Figma file for Plato product design work:

```text
Plato Product Design System and Prototype
```

The first pass should create structure and governance scaffolding only. It
should not migrate old frames, create high-fidelity screens, or build the full
component library.

## 2. Inputs

Required before creating the file skeleton:

- `docs/design/figma-governance.md`
- `docs/product/canonical-status-model.md`
- `docs/ux/screen-state-spec.md`
- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/plato-brand-and-ux-direction.md`
- `docs/product/plato-frontend-technical-design.md`

Audit Page-specific inputs:

- `docs/product/plato-audit-page-prd.md`
- `docs/product/plato-audit-page-ux-flow.md`
- `docs/engineering/audit-page-contract.md`
- `docs/frontend/ui-viewmodel-contract.md`
- `docs/frontend/api-ui-mapping.md`

## 3. File Creation Rules

- Use `figma:figma-create-new-file` before creating a new Figma file.
- Use `figma:figma-use` before any Figma API operation.
- Create only the canonical file. Do not create page-specific permanent Figma
  files unless governance is updated.
- Name the file exactly `Plato Product Design System and Prototype`.
- Add a top-level governance note that old files are reference/archive only.

## 4. Initial Page Skeleton

Create these pages in order:

1. `00 - Governance`
2. `01 - Tokens`
3. `02 - Brand Assets`
4. `03 - Base Components`
5. `04 - Layout Components`
6. `05 - Domain Components`
7. `06 - Main UX Flow`
8. `07 - Main Screen States`
9. `08 - Audit UX Flow`
10. `09 - Audit Screen States`
11. `10 - Prototype Flows`
12. `11 - Dev Handoff`
13. `99 - Archive References`

Each page should initially contain one labeled section/frame explaining its
purpose and source documents. Avoid high-fidelity visual work in the skeleton
task.

## 5. Suggested Skeleton Content

| Page | Initial content |
|---|---|
| `00 - Governance` | File name, source docs, operation/change report templates, old-file warning, current status. |
| `01 - Tokens` | Empty sections for primitive, semantic, component tokens; link to style guide. |
| `02 - Brand Assets` | Empty sections for product mark, logo variants, icons, imagery; link to brand docs. |
| `03 - Base Components` | Empty component inventory table and variant checklist. |
| `04 - Layout Components` | Empty layout inventory: shell, top bar, side nav, workbench, panels, drawers. |
| `05 - Domain Components` | Empty domain inventory: Project, Workflow, Session, TaskTree, TaskNode, Message, Confirmation, Result, FileChange, Audit. |
| `06 - Main UX Flow` | Placeholder flow map with source links. |
| `07 - Main Screen States` | Placeholder state grid aligned to `docs/ux/screen-state-spec.md`. |
| `08 - Audit UX Flow` | Placeholder entry/return flow for session/task/confirmation/result/file change. |
| `09 - Audit Screen States` | Placeholder state grid A1-A10 aligned to screen-state spec and audit contract. |
| `10 - Prototype Flows` | Empty prototype map; no transitions until states exist. |
| `11 - Dev Handoff` | Empty mapping table: Figma element -> code component -> props -> backend source. |
| `99 - Archive References` | Links to old files with `reference only` labels. |

## 6. Old File References

Known reference files from current docs and conversation context:

| Reference | Use |
|---|---|
| `Plato MVP Main Page UX Draft` | Main Page layout/state reference only. |
| `Visual Exploration - Forward Workbench v0.1` | Visual exploration reference only. |
| `Plato Brand Logo and Product Mark` | Brand asset reference; recreate final approved asset in canonical file. |
| Existing Audit Page draft frames | Audit Page state/layout reference only. |

Do not copy old pages into the canonical file as production design. Record links
and migrate selectively later.

## 7. Initial Token Stubs

The skeleton may create token section labels, but should not finalize token
values unless the task explicitly includes token creation.

Token groups to reserve:

- `color/primitive`
- `color/semantic`
- `color/status`
- `typography`
- `spacing`
- `radius`
- `shadow`
- `motion`
- `z-index`
- `component/button`
- `component/input`
- `component/badge`
- `component/panel`
- `component/task-node`
- `component/audit-record`

## 8. Initial Component Inventory

The skeleton may create an inventory table with status values:

```text
not_started | draft | in_review | approved | implemented | deprecated
```

The inventory should not imply a component exists until its Figma component and
dev handoff mapping exist.

## 9. File Skeleton Acceptance Criteria

- File has the exact canonical name.
- All canonical pages exist in order.
- `00 - Governance` states that old files are reference/archive only.
- Each page has a purpose note and source-doc links.
- No old frames are bulk-copied.
- No high-fidelity screen state is created unless separately approved.
- No component is marked approved without variants and handoff mapping.
- A Figma Change Report lists pages created and open next steps.

## 10. Recommended Next Task Prompt

```text
Use the product-workflow-gate skill first.
Use the plato-figma-governance skill next.
Use Figma skills only after both gates allow it.

Task:
Create the new canonical Figma file skeleton named
`Plato Product Design System and Prototype`.

Do not migrate old Figma content.
Do not create high-fidelity screens.
Do not implement frontend code.

Create the canonical pages from docs/design/figma-new-file-plan.md and add
governance/source notes to each page.

Output:
- Workflow Gate Report
- Figma Operation Gate Report
- Figma Change Report
- canonical file URL
- pages created
- next recommended token/component task
```
