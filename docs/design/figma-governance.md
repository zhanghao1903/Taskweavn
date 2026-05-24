# Plato Figma Governance

> Status: active governance draft
> Last Updated: 2026-05-24
> Scope: Rules for controlled Plato/Taskweavn Figma creation, migration,
> prototype work, and dev handoff.
> Non-goals: this document does not modify Figma, implement frontend code, or
> migrate old Figma content.

## 1. Purpose

Plato's Figma project must become a governed product design system, not a pile
of disconnected drafts. Every Figma operation must state whether it is creating
assets, tokens, base components, layout components, domain components, screen
states, prototype flows, or dev handoff mappings.

Old Figma files remain valuable for learning, but they are reference/archive
only. Canonical work happens in the new governed file.

## 2. Required Skills

For every Figma-related task:

1. Use `.agents/skills/product-workflow-gate/SKILL.md`.
2. Use `.agents/skills/plato-figma-governance/SKILL.md`.
3. If a Figma MCP write is allowed, also use the relevant Figma plugin skill,
   usually `figma:figma-use`, `figma:figma-generate-design`, or
   `figma:figma-generate-library`.

No Figma write may happen before a Figma Operation Gate Report says it is
allowed.

## 3. Canonical Figma File

Canonical file name:

```text
Plato Product Design System and Prototype
```

Naming rules:

- Use the product name `Plato` in the Figma file because it is the user-facing
  brand.
- Use `Taskweavn` only in dev handoff notes when referring to the repository or
  code modules.
- Do not continue canonical product design in old draft files.

## 4. Canonical Page Structure

The canonical file must use these pages in this order:

| Page | Purpose |
|---|---|
| `00 - Governance` | File rules, current source docs, change log, review notes, and do-not-edit warnings. |
| `01 - Tokens` | Placeholder page for future Figma variables/styles for color, typography, spacing, radius, shadow, motion, and z-index. |
| `02 - Brand Assets` | Product mark, logo assets, icons, image assets, and asset usage notes. |
| `03 - Base Components` | Base UI components with variants and token bindings. |
| `04 - Layout Components` | Shell, top bar, side nav, workbench grid, panels, drawers, and responsive layout components. |
| `05 - Domain Components` | Product object components such as TaskNode, Confirmation, Result, AuditRecord, and AuditEvidence. |
| `06 - Main UX Flow` | Main Page flow map and transition notes. |
| `07 - Main Screen States` | Approved Main Page screen states derived from the screen state spec. |
| `08 - Audit UX Flow` | Audit Page flow map and entry/return context. |
| `09 - Audit Screen States` | Approved Audit Page states derived from the screen state spec and audit contract. |
| `10 - Prototype Flows` | Clickable prototype entry points and transition wiring. |
| `11 - Dev Handoff` | Mapping tables from Figma elements to code components, props, and backend/ViewModel data. |
| `99 - Archive References` | Links and notes for old files. No canonical components live here. |

Any additional page must be approved by updating this document first.

## 5. Source Documents

| Source | Role |
|---|---|
| `docs/product/canonical-status-model.md` | Canonical planning, readiness, execution, confirmation, permission/action, and audit verdict dimensions. |
| `docs/ux/screen-state-spec.md` | Main Page and Audit Page screen states, route model, input modes, stale/resync, and permission states. |
| `docs/engineering/audit-page-contract.md` | Audit Page snapshot, records, evidence, scope, events, and endpoint candidates. |
| `docs/frontend/ui-viewmodel-contract.md` | Frontend ViewModel field names and shape for component props. |
| `docs/frontend/api-ui-mapping.md` | Backend-to-UI mapping and status translation rules. |
| `docs/frontend/event-reducer-contract.md` | Event patch/resync behavior for dynamic prototypes and future runtime behavior. |
| `docs/product/plato-frontend-technical-design.md` | Frontend architecture, component layering, and design-to-code principles. |
| `docs/product/plato-design-philosophy-style-guide.md` | Visual style principles and constraints. |
| `docs/product/plato-brand-and-ux-direction.md` | Brand, naming, and product direction. |
| `docs/plans/ui/page-project-implementation-template.md` | PRD -> UX -> Figma -> review -> UI code workflow. |
| `docs/design/design-system.md` | Token and component-layer contract. |
| `docs/design/component-spec.md` | Production-grade component creation beyond initial skeleton. |
| `docs/design/component-state-matrix.md` | Variant-complete component library work. |
| `docs/ux/prototype-state-map.md` | High-confidence prototype wiring beyond simple skeleton flows. |

Production-grade component/prototype work must verify these docs in the Figma
Operation Gate Report before any Figma write.

## 6. Operation Classes

Every Figma task must be classified as one or more of:

| Class | Allowed output |
|---|---|
| `read_reference` | Inspect old or canonical files; no write. |
| `create_canonical_file_skeleton` | Create canonical pages, governance notes, and empty sections. |
| `create_assets` | Create or update product mark, icons, bitmaps, and media assets. |
| `create_tokens` | Create Figma variables/styles and token documentation. |
| `create_base_components` | Build primitives such as Button, Input, Badge, Tabs, Tooltip, Dialog, Panel, Card, List, Skeleton, Toast. |
| `create_layout_components` | Build shell, top bar, side navigation, workbench grid, context inspector, timeline layout, split panes, drawers. |
| `create_domain_components` | Build product object components backed by ViewModels. |
| `create_screen_states` | Create Main Page or Audit Page frames for approved states. |
| `create_prototype_flows` | Wire approved state transitions and route/return behavior. |
| `create_dev_handoff` | Add mappings from design elements to code components, props, and backend/ViewModel fields. |
| `migrate_old_file_content` | Recreate selected old content in the canonical file with source attribution. |

## 7. Asset Creation Rules

- Assets must live in `02 - Brand Assets` before use in screen states.
- Product mark assets must be source quality: vector when possible, otherwise
  high-resolution transparent bitmap.
- Do not use low-resolution screenshots as canonical product marks.
- Do not use framed or bordered logo images when the intended usage is
  immersive/integrated.
- Asset names must include role and size or format, for example
  `brand/product-mark-horizontal-2.5x1`.
- Experimental assets may exist only in clearly marked exploration sections and
  must not be used by production screen states until approved.

## 8. Token Creation Rules

Create tokens in this order:

1. Primitive tokens: raw color ramps, font families, base sizes, base spacing,
   base radius, base shadow, motion durations.
2. Semantic tokens: text, background, surface, border, focus, status, brand,
   audit verdict, confirmation, risk, and disabled tokens.
3. Component tokens: button, input, badge, panel, timeline, top bar, task node,
   audit record.

Rules:

- Use Figma variables/styles for reusable values.
- Map token names to frontend CSS variable intent where possible.
- Do not hardcode one-off colors, spacing, radius, shadows, or motion values in
  production screen states.
- Tokens must support light mode first. Dark mode is deferred unless explicitly
  planned.
- Status tokens must reflect separated canonical dimensions; do not create one
  universal `status/running` token that mixes planning and execution meaning.

## 9. Component Creation Rules

Build components in layers:

1. Base components.
2. Layout components.
3. Domain components.
4. Screen compositions.

Base components:

- Must include relevant variants: default, hover, focus-visible, active,
  disabled, loading, error, selected, and read-only where applicable.
- Must use tokens, not detached colors or spacing.
- Must be generic and domain-free.

Layout components:

- Must define responsive constraints and resize behavior.
- Must not contain business logic or hardcoded sample data.
- Must include desktop-first behavior and notes for tablet/mobile if deferred.

Domain components:

- Must map to ViewModel fields in `docs/frontend/ui-viewmodel-contract.md`.
- Must not expose backend storage ids, raw logs, provider payloads, stack
  traces, secrets, or raw prompts.
- Must not infer permissions from visual status. Permission and disabled state
  must come from the ViewModel or mapping docs.

## 10. Screen State Creation Rules

Screen states must be derived from `docs/ux/screen-state-spec.md`.

Main Page states must account for:

- planning states;
- task readiness;
- execution status;
- confirmation status plus local resolving/failed overlays;
- permission denied/read-only controls;
- stale/resync;
- loading, empty, error, success, and partial states.

Audit Page states must account for:

- session and task scopes;
- selected and unselected record detail;
- filters with zero counts;
- loading, empty, partial, hidden evidence, permission denied, error, stale;
- audit verdicts: `passed`, `warning`, `failed`, `inconclusive`,
  `not_available`;
- effective config summary and related logs link reservations.

Do not create a screen state that communicates a trust or execution result that
does not exist in the canonical status model or backend-to-UI mapping.

## 11. Prototype Flow Rules

Prototype flows must preserve product context:

- Main Page route context: project, workflow, session, selected task.
- Audit Page entry context: from session, task, confirmation, result, or file
  change.
- Audit return target: return to Main Page with the relevant focus.
- Input mode: session-level, task-scoped, clarification, or read-only.

Audit Page prototype interactions are read-only. Mutating actions such as
editing, publishing, retrying, cancelling, or resolving confirmations must
return to Main Page.

Prototype wiring must be documented in `10 - Prototype Flows` and mapped to
screen state names. High-confidence prototype work must use
`docs/ux/prototype-state-map.md`.

## 12. Dev Handoff Rules

Every production-ready design element must have a handoff row:

| Figma element | Code component | Props/ViewModel fields | Backend/source data | Status |
|---|---|---|---|---|

Rules:

- Code component names should follow the frontend architecture:
  `shared` primitives, `entities` product objects, `features` actions, and
  `pages` composition.
- If a component does not exist, mark `new component required`.
- If a backend source does not exist, mark `mock only` or `contract pending`.
- Do not imply real backend integration when only fixtures exist.
- Handoff rows for Audit Page must reference
  `docs/engineering/audit-page-contract.md`.

## 13. Old File Migration Rules

Old Figma files are reference/archive only.

Allowed:

- inspect old files for layout, visual direction, brand exploration, and
  interaction ideas;
- copy screenshots into `99 - Archive References` as non-canonical references if
  needed;
- recreate selected assets/components/screens inside the canonical file after
  they pass governance rules.

Not allowed:

- continue production work inside old files;
- bulk-copy old pages into canonical pages and call them final;
- use old low-resolution assets as canonical assets;
- treat old static frames as interactive prototype states without rewriting
  their state and handoff mappings.

Migration must record:

- old file name and URL;
- source page/frame/component;
- decision: recreated, deferred, rejected, or reference only;
- reason;
- new canonical destination, if recreated.

## 14. Figma Operation Gate Report

Before any Figma operation, output:

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

## 15. Figma Change Report

After any Figma write, output:

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

For doc-only work, report repo files changed and note that Figma was not
modified.

## 16. Acceptance Criteria

- Every Figma task uses the governance skill after the product workflow gate.
- The canonical file name and page structure are stable.
- Old files are treated as archive/reference only.
- Tokens precede components, and components precede screen states.
- Screen states map to canonical product statuses and ViewModels.
- Prototype transitions preserve route, selection, and return context.
- Dev handoff maps Figma to code component, props, and backend/ViewModel
  source.
