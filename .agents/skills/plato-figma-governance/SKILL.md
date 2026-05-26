---
name: plato-figma-governance
description: Use before every Plato/Taskweavn Figma-related task. Gates whether to create, edit, inspect, migrate, or hand off Figma assets, tokens, components, pages, screen states, prototype flows, and dev mappings. Treats old Figma files as reference/archive only.
---

# Plato Figma Governance Skill

Use this skill after `product-workflow-gate` and before any Figma-related
operation, including reads, writes, asset creation, token work, component work,
screen state work, prototype wiring, dev handoff mapping, or migration from old
files.

This skill is repo-scoped. It governs Plato/Taskweavn design work for this
repository and must be used in addition to plugin skills such as
`figma:figma-use`, `figma:figma-generate-design`, and
`figma:figma-generate-library` when actual Figma MCP calls are needed.

## Canonical Design Sources

Read the relevant sources before allowing a Figma write:

- `docs/design/figma-governance.md`
- `docs/design/figma-new-file-plan.md`
- `docs/design/figma-migration-plan.md`
- `docs/design/figma-readiness-checklist.md`
- `docs/design/figma-layout-contract.md` for Screen State, Prototype Flow
  handoff, and Dev Handoff layout/readability work
- `docs/design/design-system.md`
- `docs/design/component-spec.md`
- `docs/design/component-state-matrix.md`
- `docs/ux/prototype-state-map.md`
- `docs/product/canonical-status-model.md`
- `docs/ux/screen-state-spec.md`
- `docs/engineering/audit-page-contract.md` for Audit Page work
- `docs/frontend/ui-viewmodel-contract.md`
- `docs/frontend/api-ui-mapping.md`
- `docs/product/plato-frontend-technical-design.md`
- `docs/product/plato-design-philosophy-style-guide.md`
- `docs/product/plato-brand-and-ux-direction.md`

If component spec, component-state matrix, or prototype-state map artifacts do
not exist yet, block production-grade component/prototype Figma writes and
create or request those docs first. Do not silently invent them inside Figma.

## Canonical Figma File

The canonical Figma file name is:

```text
Plato Product Design System and Prototype
```

Old Figma files, including earlier Main Page drafts, Audit Page drafts, brand
exploration files, and visual exploration files, are reference/archive only.
They may be inspected for learning, but canonical work must be recreated or
rebuilt inside the canonical file following the governance docs.

## Canonical Page Structure

The canonical file must use these top-level pages:

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

Do not add page-level alternatives without updating
`docs/design/figma-governance.md`.

## Operation Gate

Before any Figma operation, produce this report:

```text
Figma Operation Gate Report:
- Requested operation:
- Operation class:
- Canonical file target:
- Existing file/frame/component target:
- Upstream docs checked:
- Required docs missing or weak:
- Allowed now: yes/no
- Figma write allowed: yes/no
- Assets/tokens/components affected:
- Screen states/prototype flows affected:
- Dev handoff impact:
- Migration/archive impact:
- Execution scope:
- Stop conditions:
```

If the operation is not allowed, stop after the report and recommend the
smallest upstream doc or design-system task that would unblock it.

## Operation Classes

Classify the request before acting:

- `read_reference`: inspect old or canonical files without writing.
- `create_canonical_file_skeleton`: create pages, basic notes, and empty
  sections only.
- `create_assets`: add or update product mark, icons, image assets, or media.
- `create_tokens`: add variables/styles for color, typography, spacing, radius,
  shadow, motion, and z-index.
- `create_base_components`: buttons, inputs, badges, tabs, tooltips, dialogs,
  panels, cards, lists, tables, chips, skeletons, toasts.
- `create_layout_components`: app shell, top bar, side nav, workbench grid,
  detail panel, timeline layout, split panes, drawers.
- `create_domain_components`: Project, Workflow, Session, TaskTree, TaskNode,
  Message, Confirmation, Result, FileChangeSummary, AuditRecord,
  AuditEvidence, EffectiveConfig, RelatedLogs.
- `create_screen_states`: Main Page or Audit Page frames derived from canonical
  status and screen state specs.
- `create_prototype_flows`: interactions and transitions between approved
  screen states.
- `create_dev_handoff`: mapping tables, annotations, component/code links, and
  implementation notes.
- `migrate_old_file_content`: recreate selected old content in the canonical
  file with explicit source attribution.

## Creation Rules

Assets:

- Create source-quality assets once in `02 - Brand Assets`.
- Prefer vector or high-resolution transparent bitmap assets.
- Do not paste low-resolution screenshots as product marks.
- Do not use old draft assets directly unless they pass current brand rules.

Tokens:

- Create primitive tokens before semantic tokens.
- Create semantic tokens before components.
- Token names must map to frontend CSS variable intent where possible.
- Do not hardcode one-off color, radius, spacing, shadow, or motion values in
  page frames when a token should exist.

Components:

- Build base components before layout components.
- Build layout components before domain components.
- Every interactive component must include default, hover, focus-visible,
  active, disabled, loading, and error variants when applicable.
- Domain components must map to ViewModel fields, not raw backend rows.
- Every Figma write that creates or edits visible components, component sets,
  screen states, prototype flow references, or Dev Handoff sections must run a
  post-write overlap and clipping verification before being reported complete.
- Overlap verification must inspect visible descendants inside each changed
  component/frame, not only top-level page nodes. Check visible text collisions
  with sibling/cousin nodes, text clipping against its parent bounds, note-frame
  overlap with component galleries, and page-level screenshot-width overflow.
- Page-level verification must include **all visible top-level siblings on the
  target page**, including old title frames, skeleton notes, hygiene notes,
  archive/reference notes, and generated warning frames. Do not limit the check
  to the nodes changed in the current script, because stale top-level notes can
  still overlap newly positioned component galleries.
- Visible descendant checks must use **effective visibility**: walk from the
  candidate node to the verification root and treat the node as hidden if any
  ancestor has `visible = false`. Do not count stale descendants inside hidden
  archived frames as visible overlap, but do keep those hidden descendants out
  of handoff/source-of-truth notes.
- For component sets, verification must compare note frames and neighboring
  galleries against the effective bounds of visible descendants, not only the
  component set node's own `width`/`height`. If a variant extends outside the
  component set bounds, resize/reflow the set before placing notes or following
  components.
- Component/page reflow must be driven by effective descendant bounds. Place
  note frames, following galleries, and section frames after the effective
  visible bottom/right edge, not after stale `node.width`/`node.height` values
  alone.
- Component variant internals must also be verified. If a variant uses one
  visible root presentation frame, that root frame must start at `x=0, y=0`
  and the variant bounds must match or fully contain the root. Do not create
  padding by offsetting the root frame to `14,14` or similar; put padding inside
  the root frame. Offset roots are blockers because they make the visible
  variant exceed the component boundary and overlap neighboring variants.
- Intentional text-on-background overlap is allowed only when the containing
  chip/button/panel encloses the text as its own label. Text colliding with
  another chip, button, panel, metadata block, or component preview is a
  blocker.
- If overlap or clipping is found, fix it in the same task or mark the Figma
  write incomplete. Do not mark structural verification as sufficient when a
  human-readable screenshot shows overlap.
- Each visible Figma write must report overlap results separately for: visible
  text collisions, text clipping, component-set descendant bounds, page-level
  set/note collisions, screenshot-width safety, and export/screenshot attempt.
  If Figma screenshot/export transport fails, keep structural verification
  separate and record screenshot/export as pending rather than silently passing.

Screen states:

- Derive states from `docs/ux/screen-state-spec.md` and
  `docs/product/canonical-status-model.md`.
- Before creating or editing Screen State frames, apply
  `docs/design/figma-layout-contract.md`.
- Use the standard ScreenState zones: header, screen preview, metadata summary,
  and implementation notes.
- Keep Figma metadata summary-length only. Full route, ViewModel, API, event,
  permission, stale/resync, and recovery metadata belongs in repo docs such as
  `docs/design/dev-handoff.md`.
- Do not place component usage proof galleries inside the screen preview zone.
- Do not collapse planning, readiness, execution, confirmation, permission, and
  audit verdict into one visual status.
- Include loading, empty, partial, error, permission denied, stale/resync, and
  success states when the page can reach them.
- Verify structural completeness, layout readability, screenshot-width safety,
  metadata overflow, and node ID preservation before marking state work
  complete.

Prototype flows:

- Prototype only approved states.
- Transitions must preserve route context, selected task/record, and return
  targets.
- Audit Page flows must remain read-only and return to Main Page for mutating
  actions.
- Flow handoff frames that include state references or metadata must follow the
  relevant layout contract summary and overflow rules.

Dev handoff:

- Every production-ready Figma element must map to a code component, props, and
  backend/ViewModel source.
- Handoff notes must say whether the component is base, layout, or domain.
- If no code component exists yet, mark it as `new component required`; do not
  imply implementation exists.
- Before creating or editing Dev Handoff sections, apply
  `docs/design/figma-layout-contract.md`.
- Use the standard DevHandoff section layout: section header, mapping table or
  list, gaps/blockers, and source references.
- Keep Figma Dev Handoff sections scannable. Full mapping detail lives in
  `docs/design/dev-handoff.md`; Figma sections should summarize and point to
  the repo docs.
- Verify no-overlap, screenshot-width readability, metadata overflow, and node
  ID preservation for future handoff hygiene passes.

Migration:

- Old files are reference/archive only.
- Migrate by recreating content in canonical pages, not by bulk-copying old
  frames.
- Record source file, frame, date inspected, decision, and whether recreated,
  deferred, or rejected.

## Change Report

After any allowed Figma write, return:

```text
Figma Change Report:
- Canonical file:
- Pages changed:
- Frames/components/assets/tokens changed:
- Source docs followed:
- Component and variant coverage:
- Screen states/prototype flows changed:
- Dev handoff mappings added/updated:
- Old file references used:
- Validation performed:
- Open issues:
- Next recommended task:
```

For doc-only governance tasks, report files changed instead of Figma nodes.
