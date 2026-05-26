# Plato Visual Baseline Alignment Audit

> Status: P4.9 visual baseline alignment audit
> Last Updated: 2026-05-26
> Scope: Read-only comparison between the canonical Figma file and the
> historical Plato MVP Main Page visual baseline.

Follow-up status:

- `04 - Layout Components` was upgraded in P4.11 and accepted on 2026-05-26
  for P4 product-aligned layout reference.
- `05 - Domain Components` was upgraded in P4.12 and accepted on 2026-05-26
  for P4 domain component skeleton and semantic coverage.
- `07 - Main Screen States` and `09 - Audit Screen States` still need
  recomposition against the upgraded Layout and Domain drafts.

## 1. Governance Position

The historical Figma file remains archive/reference input only:

- historical file: `Plato MVP Main Page UX Draft`
  <https://www.figma.com/design/wHFPOBaxeImyhJer7BnMaq>
- canonical file: `Plato Product Design System and Prototype`
  <https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA>

This audit extracts reusable visual and product patterns from the historical
baseline. It does not promote old frames to canonical source, does not copy old
frames, does not modify Figma, and does not change frontend code.

Canonical status, component, route, API, and ViewModel semantics remain the
source of truth:

- `docs/product/canonical-status-model.md`
- `docs/engineering/audit-page-contract.md`
- `docs/ux/screen-state-spec.md`
- `docs/ux/prototype-state-map.md`
- `docs/design/component-spec.md`
- `docs/design/component-state-matrix.md`
- `docs/design/dev-handoff.md`

## 2. Audit Inputs

Canonical pages inspected:

| Page | Evidence |
|---|---|
| `04 - Layout Components` | Read-only Figma inventory: `Layout/AppShell`, `Layout/TopBar`, `Layout/SideNav`, `Layout/MainWorkArea`, `Layout/DetailPanel`, `Layout/ContextInputBar` are present as verified skeletons. |
| `05 - Domain Components` | Read-only Figma inventory: `Domain/TaskTree`, `Domain/TaskNode`, `Domain/MessageStream`, `Domain/MessageCard`, `Domain/ConfirmationPanel`, `Domain/FileChangeTable`, and `Domain/AuditEntryCard` are present as verified skeletons. |
| `07 - Main Screen States` | S1-S13 frames exist, but text samples still show repeated generic skeleton labels such as `Default panel`, `Panel container skeleton`, `Neutral`, and `Primary`. |
| `09 - Audit Screen States` | A1-A14 frames exist, but many previews still use the same generic skeleton vocabulary instead of audit-specific product density. |
| `11 - Dev Handoff` | Mapping sections exist and are useful for P5 architecture input, but they describe structural mappings more strongly than visual baseline fidelity. |

Historical baseline inspected:

| Source | Evidence |
|---|---|
| `Plato MVP Main Page UX Draft` main page | S1-S9 desktop workbench frames, 1440x1024, with concrete project/workflow/session hierarchy, dense TaskTree content, contextual messages, detail inspector, status chips, and context-aware input. |
| `docs/product/plato-figma-ui-baseline.md` | Defines the historical Main Page visual baseline, workbench layout, sample TaskTree, state-specific content, and review criteria. |
| `docs/product/plato-design-philosophy-style-guide.md` | Defines `Modern Classical Workbench`, TaskTree as primary control object, restrained status colors, compact typography, and audit-as-trust-entry behavior. |

## 3. Executive Finding

The canonical Figma file is structurally valid but visually incomplete.

The current canonical design correctly establishes governed tokens, components,
screen states, prototype flows, and Dev Handoff mappings. However, the visual
and product fidelity is still below the historical Main Page baseline. The
canonical pages are dominated by skeleton placeholders, component proof labels,
and generic state previews. They do not yet communicate the historical
baseline's real product density: project/workflow/session context, central
TaskTree control, contextual DetailPanel, scoped input behavior, execution
messages, file summaries, and audit trust entry.

`04 - Layout Components` is the clearest example: it is structurally valid and
mapped, but visually incomplete. It proves layout slots exist; it does not yet
express the product workbench.

## 4. Baseline Patterns To Preserve

These are patterns to recreate in the canonical system, not frames to copy.

| Baseline pattern | Product value |
|---|---|
| Stable 1440x1024 workbench | Gives a real desktop operating surface instead of abstract component demos. |
| TopBar with project, workflow, session, status, audit/settings actions | Keeps route context visible and reduces "where am I?" uncertainty. |
| Workflow/session sidebar | Makes `Project -> Workflow -> Session` hierarchy visible. |
| TaskTree as central control object | Makes system planning, execution, confirmation, and progress understandable. |
| Dynamic DetailPanel / context inspector | Shows selected task, confirmation, result, file summary, or audit entry without modal drift. |
| Context-aware input | Makes the input target explicit: session-level goal or task-scoped instruction. |
| Process message stream | Supports the workflow without turning the product into chat. |
| Real sample content | Allows design review to catch density, wrapping, hierarchy, and semantic ambiguity. |
| Restrained blue/gold/cream/gray palette | Keeps the product calm while preserving state contrast. |
| Fine borders, subtle shadow, compact typography, <=8px radius | Maintains the Modern Classical Workbench direction. |

## 5. Component Gap Matrix

| Component area | Historical baseline pattern | Canonical current state | Gap types | Priority |
|---|---|---|---|---|
| `Layout/AppShell` | Full workbench with top, sidebar, main, detail, and bottom input regions. | Slot skeleton exists. Generic panel placeholders dominate. | visual style, layout density, dev handoff ambiguity | P0 |
| `Layout/TopBar` | Product mark, `Project`, `Personal Website`, workflow chip, `Session: ...`, status chips, audit/settings actions. | Default/loading/readonly skeletons exist with generic labels. Final product mark and overflow behavior deferred. | semantic content, visual style, component variant, copy placeholder | P0 |
| `Layout/SideNav` / `WorkflowSidebar` | Workflow list, new session action, selected workflow, sessions in workflow, hierarchy explanation. | Expanded/collapsed/empty skeletons exist; hierarchy and session density are weak. | semantic content, layout density, copy placeholder | P0 |
| `Layout/MainWorkArea` / `WorkbenchGrid` | TaskTree is visually central; message stream and result/file areas support the central object. | Main work area skeleton exists; state previews still show generic panels. | semantic content, layout density, visual style | P0 |
| `Layout/DetailPanel` | Context inspector changes by state: workflow setup, planning progress, selected task, confirmation, result, files, audit entry. | DetailPanel states exist but remain generic. Some notes still mention stale ErrorState alignment. | semantic content, component variant, dev handoff ambiguity | P0 |
| `Layout/ContextInputBar` | Shows scope, mode, placeholder, disabled/submitting state, and target context. | Mode states exist, but previews do not yet carry real scoped copy/density. | semantic content, copy placeholder, visual style | P0 |
| `Domain/TaskTree` | Concrete personal website tree with parent/child hierarchy and status distribution. | Skeleton variants exist; placeholder labels and generic rows dominate. | semantic content, layout density, copy placeholder | P0 |
| `Domain/TaskNode` | Node title, hierarchy, state, selection, running/waiting/done/failed, possible result/file/audit signals. | 12 structural variants exist, but visual richness and real status payload are weak. | visual style, semantic content, component variant | P0 |
| `Domain/MessageStream` | Shows process messages: understanding, planning, execution, user input, result updates. | Stream states exist, but lack baseline's real progress narrative. | semantic content, copy placeholder, layout density | P1 |
| `Domain/MessageCard` | Differentiates user request, assistant response, result, warning, error with lightweight markers. | Type variants exist; content remains generic. | copy placeholder, visual style, semantic content | P1 |
| `Domain/ConfirmationPanel` | Confirmation is attached to the relevant TaskNode and includes impact/files/options. | Lifecycle and risk variants exist; attachment semantics and concrete impact copy are not strong enough. | semantic content, component variant, layout density | P0 |
| `Domain/FileChangeTable` | Shows file path, change type, summary, and task/result aggregation. | State and change-kind variants exist; needs realistic file-change density and audit link behavior. | semantic content, layout density, copy placeholder | P1 |
| `Domain/AuditEntryCard` | Main Page shows audit as trust entry, not dominant workflow surface. | Verdict variants exist; Main/Audit relationship is structurally mapped but visually generic. | semantic content, visual style, dev handoff ambiguity | P1 |

## 6. Top Visual Fidelity Gaps

1. Canonical pages still read as component skeleton galleries, not a product
   workbench.
2. The TopBar does not yet carry the historical product context density:
   project, workflow, session, status, audit action, settings action.
3. The SideNav does not yet reproduce the workflow/session hierarchy and
   selected-session density.
4. TaskTree and TaskNode visuals do not yet show enough hierarchy, status, and
   result/file/audit signals to act as the primary control object.
5. DetailPanel is too generic and does not yet behave like a dynamic context
   inspector.
6. ContextInputBar does not yet make input scope as visible as the baseline.
7. MessageStream and MessageCard do not yet carry the baseline process narrative.
8. ConfirmationPanel is not yet visually attached strongly enough to the
   relevant TaskNode and impact surface.
9. FileChangeTable and AuditEntryCard need richer trust-entry presentation.
10. Audit states are structurally complete, but need a visual language aligned
    with Main Page density and trust-plane behavior.

## 7. Top Semantic Fidelity Gaps

1. Many canonical state previews still include generic labels (`Default panel`,
   `Panel container skeleton`, `Neutral`, `Primary`) where product-specific
   content is required.
2. The Main Page canonical S1-S13 set covers more states than the historical
   S1-S9 baseline, but the relationship between them is not visually obvious.
3. Historical S1-S9 showed concrete state progression; canonical states still
   rely heavily on metadata to explain the difference.
4. Planning, readiness, execution, confirmation, permission, and audit verdict
   are correctly separated in docs, but not yet visible enough in the preview
   content.
5. Audit Page contract states are represented, but there is no mature visual
   baseline for audit density, evidence detail, hidden evidence, partial
   evidence, stale snapshot, and permission-limited states.
6. Dev Handoff maps code/data/component ownership, but it does not yet
   explicitly protect engineers from treating skeleton previews as visual-ready
   implementation targets.

## 8. Canonical Pages Needing Upgrade

| Page | Current readiness | Required upgrade |
|---|---|---|
| `04 - Layout Components` | Structurally valid, visually incomplete. | Upgrade AppShell, TopBar, SideNav, MainWorkArea, DetailPanel, and ContextInputBar to express the real workbench baseline. |
| `05 - Domain Components` | Structurally valid, placeholder-heavy. | Add product-real sample content, stronger density, richer status payload, and clearer attachment semantics. |
| `07 - Main Screen States` | State coverage exists; visual semantics remain too generic. | Recompose S1-S13 after layout/domain components are upgraded; align visual progression to historical S1-S9 while preserving canonical extra states. |
| `09 - Audit Screen States` | Contract coverage exists; visual baseline is immature. | Create an Audit visual baseline aligned to Main Page, focused on evidence, permission, stale, partial, and verdict readability. |
| `11 - Dev Handoff` | Useful as P5 architecture input. | Add explicit visual readiness warnings and route engineers to upgraded visual baseline specs before frontend implementation. |

## 9. Readiness Classification

| Dimension | Status | Notes |
|---|---|---|
| Structural readiness | Mostly complete | Tokens, Base/Layout/Domain skeletons, Main/Audit state frames, prototype flows, and Dev Handoff mappings exist. |
| Semantic fidelity readiness | Partial | P4.8 restored state-specific intent, but post-write visual verification was incomplete and many previews remain generic. |
| Visual baseline alignment readiness | Not ready | Historical Main Page baseline density and visual/product specificity have not been rebuilt into canonical components/states. |
| Frontend implementation readiness | Not ready | P5 frontend architecture can use mappings, but UI implementation should not treat current Figma screens as final visual targets. |

## 10. Recommended Remediation Sequence

1. P4.10: Create a visual upgrade brief for Layout Components using this audit
   as input.
2. P4.11: Upgrade `04 - Layout Components` in Figma without changing state
   semantics: AppShell, TopBar, SideNav, MainWorkArea, DetailPanel, and
   ContextInputBar.
3. P4.12: Upgrade `05 - Domain Components` with product-real sample data,
   status payloads, density, and copy.
4. P4.13: Recompose `07 - Main Screen States` from the upgraded components;
   map historical S1-S9 progression to canonical S1-S13.
5. P4.14: Create an Audit visual baseline in `09 - Audit Screen States`,
   aligned with Main Page but optimized for evidence, verdict, permission,
   hidden/partial evidence, and stale recovery.
6. P4.15: Update `11 - Dev Handoff` to separate visual-ready targets from
   structural mapping targets.
7. P5: Start frontend architecture only after the canonical Figma has a
   visually aligned Main/Audit baseline or after product explicitly accepts
   a lower-fidelity implementation target.

## 11. Open Product/Design Questions

1. Should the canonical Main Page preserve the historical 1440x1024 workbench
   frame as the default desktop reference, or keep the newer 1440x1380
   handoff frame size and embed a 1440x1024 preview inside it?
2. Should Audit Page use the same SideNav/TopBar shell as Main Page, or a
   slightly more evidence-focused Trust Plane shell?
3. Which product mark asset should be locked as the top-bar production mark
   before visual upgrade work starts?
4. What is the minimum acceptable visual density for first frontend
   implementation: historical Main Page density, or a simplified but
   semantically complete workbench?

## 12. Acceptance Criteria For Remediation

Future visual alignment work is acceptable only when:

- old files remain archive/reference only;
- no old frames are copied into the canonical file;
- Layout and Domain components use canonical tokens and current component
  names;
- product-specific content replaces placeholder labels in screen previews;
- state dimensions remain separated;
- Main Page still keeps TaskTree as the primary control object;
- Audit Page keeps evidence/permission/stale/verdict states visible;
- Dev Handoff clearly states whether a frame is structural-only,
  semantically ready, visually baseline-aligned, or frontend-ready;
- screenshots or equivalent visual checks verify no overlap, no clipped
  semantic content, and sufficient product density.
