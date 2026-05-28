# Plato Figma Readiness Checklist

> Status: active checklist draft
> Last Updated: 2026-05-25
> Scope: Gate checklist for Figma assets, tokens, components, screen states,
> prototype flows, migration, and dev handoff.

Use this checklist with `.agents/skills/plato-figma-governance/SKILL.md`
before and after Figma work.

## 1. Universal Gate

| Check | Required | Status |
|---|---:|---|
| Product workflow gate report produced | yes | pending per task |
| Figma Operation Gate Report produced | yes | pending per task |
| Canonical file target is `Plato Product Design System and Prototype` | yes | created: <https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA> |
| Old files treated as reference/archive only | yes | active rule |
| Source docs listed in the operation report | yes | pending per task |
| Figma write explicitly allowed | yes for writes | available, subject to operation gate |
| Stop conditions named | yes | pending per task |

## 2. Source Document Readiness

| Source | Required for | Status |
|---|---|---|
| `docs/product/canonical-status-model.md` | status-sensitive assets, screen states, prototypes, handoff | available |
| `docs/ux/screen-state-spec.md` | Main Page and Audit Page states | available |
| `docs/engineering/audit-page-contract.md` | Audit Page components, states, handoff | available |
| `docs/frontend/ui-viewmodel-contract.md` | component props and handoff mapping | available |
| `docs/frontend/api-ui-mapping.md` | backend-to-UI source mapping | available |
| `docs/frontend/event-reducer-contract.md` | dynamic prototype/event behavior | available |
| `docs/product/plato-frontend-technical-design.md` | frontend architecture and component layering | available |
| `docs/product/plato-design-philosophy-style-guide.md` | visual style and token direction | available |
| `docs/product/plato-brand-and-ux-direction.md` | brand/naming/product mark direction | available |
| `docs/design/design-system.md` | token and layer contract | available |
| `docs/design/component-spec.md` | production component creation | available |
| `docs/design/component-state-matrix.md` | complete component variants | available |
| `docs/ux/prototype-state-map.md` | high-confidence prototype wiring | available |
| `docs/design/figma-layout-contract.md` | Screen State and Dev Handoff layout/readability verification | available |
| `docs/design/visual-baseline-alignment.md` | visual baseline alignment before frontend UI implementation | available |

The minimum component/prototype docs now exist. Production-grade Figma writes
still require a per-task Figma Operation Gate Report and must stay within the
specific operation class that is approved.

Screen State, Prototype Flow handoff, and Dev Handoff writes must also follow
`docs/design/figma-layout-contract.md`. Figma frames should contain readable
summaries and doc references; complete metadata belongs in repo docs.

## 3. Asset Readiness

Asset work is ready only when:

- source asset or generation brief is identified;
- target page is `02 - Brand Assets`;
- required output format and ratio are specified;
- source quality is high enough for Figma and frontend use;
- usage rules are documented;
- old assets are recreated or explicitly marked reference only.

Product mark checks:

- no accidental border/frame;
- transparent or background-integrated where intended;
- ratio documented, such as 2.5:1;
- high-resolution or vector source available;
- visual alignment tested in top bar usage before approval.

## 4. Token Readiness

Token work is ready only when:

- primitive token groups are named;
- semantic token groups are named;
- component token groups are named;
- token naming can map to frontend CSS variable intent;
- status tokens do not collapse distinct canonical dimensions;
- color and surface choices reference the visual style guide;
- no page-specific one-off value is introduced without a reason.

Minimum token groups:

- color primitive;
- color semantic;
- color status and audit verdict;
- typography;
- spacing;
- radius;
- shadow;
- motion;
- z-index.

Current status:

| Item | Status |
|---|---|
| Token variables/styles | created in canonical Figma file |
| Token page | `01 - Tokens` |
| Documentation frame | `Token Documentation / Governed Tokens v0.1`, ID `10:131` |
| Color variables | `Plato Color`, 88 variables |
| Typography variables/styles | `Plato Typography`, 2 family variables, 6 text styles |
| Spacing variables | `Plato Spacing`, 8 variables |
| Radius variables | `Plato Radius`, 3 variables |
| Shadow styles | `shadow/panel`, `shadow/focus` |
| Motion variables | `Plato Motion`, 4 variables |
| Breakpoint variables | `Plato Breakpoint`, 4 variables |
| Z-index variables | `Plato Z Index`, 5 variables |
| Components | base skeletons created; layout and domain component drafts visually upgraded |
| Screen states | Main and Audit screen states created |
| Prototype flows | created as governed flow references |
| Dev handoff | mapping created for P5 architecture input |

Token partial notes:

- Success/warning/danger color primitives use the current frontend CSS
  baseline where the design-system contract names the tone but does not fully
  enumerate raw values.
- `color/semantic/surface-muted` is currently bound to `classic-cream` and
  should be visually reviewed before component sign-off.
- `color/semantic/focus-ring` uses the existing frontend CSS focus alpha of
  16%.
- Typography style sizes use the existing frontend `Text` component CSS
  baseline because the design-system contract defines roles, not full type
  metrics.
- Breakpoint variables represent min-width thresholds.

## 5. Base Component Readiness

Base component work is ready only when:

- component is listed in the component inventory;
- token dependencies exist or are deliberately stubbed;
- required variants are listed;
- accessibility behavior is known;
- the component is domain-free;
- dev handoff row exists or is explicitly deferred.

Required variants when applicable:

- default;
- hover;
- focus-visible;
- active;
- disabled;
- loading;
- error;
- selected;
- read-only.

Current status:

| Item | Status |
|---|---|
| Base component skeleton creation | attempted on 2026-05-24 13:41:33 CST |
| Verification | blocked: Figma MCP timed out during write and subsequent reads |
| Recovery retry | blocked again on 2026-05-24 14:35:03 CST: Figma `whoami` pre-check timed out after 120s |
| Latest creation request | blocked on 2026-05-24 14:51:55 CST: Figma `whoami` pre-check timed out after 120s |
| Repeated creation request | blocked on 2026-05-24 15:13:40 CST: Figma `whoami` pre-check timed out after 120s |
| Successful skeleton creation | completed and verified on 2026-05-24 15:50:19 CST |
| Stabilization pass | completed on 2026-05-24 15:50:19 CST: existing nodes preserved and notes organized next to component sets |
| Completion status | governed base component skeletons stabilized; not frontend implementation |
| Spec-status sync | completed on 2026-05-24 17:00:08 CST for `Base/ErrorState` and `Base/Drawer` |
| Handoff hygiene pass | completed on 2026-05-25 CST with run marker `plato-handoff-hygiene-2026-05-25`; component galleries reflowed, notes kept adjacent, placeholder-copy warning added |
| Run marker to inspect | `plato-base-components-2026-05-24` |
| Retry run marker reserved | `plato-base-components-retry-2026-05-24` |
| Active run marker | `plato-base-components-2026-05-24-batched` |
| Target page | `03 - Base Components` |
| Mapping document | `docs/design/figma-component-mapping.md` |

Verified component skeletons:

| Component | Node ID | Variants verified | Status |
|---|---|---:|---|
| `Base/Button` | `28:46` | 20 | skeleton |
| `Base/Badge` | `28:84` | 15 | skeleton |
| `Base/Input` | `30:14` | 5 | skeleton |
| `Base/TextArea` | `30:35` | 4 | skeleton |
| `Base/Card` | `30:79` | 12 | skeleton |
| `Base/Panel` | `30:157` | 25 | skeleton |
| `Base/Dialog` | `32:20` | 6 | skeleton |
| `Base/Drawer` | `32:37` | 3 | deferred placeholder |
| `Base/Toast` | `32:81` | 12 | skeleton |
| `Base/Tooltip` | `32:93` | 2 | skeleton |
| `Base/EmptyState` | `34:11` | 3 | skeleton |
| `Base/ErrorState` | `34:25` | 2 | formalized skeleton |
| `Base/Skeleton` | `34:50` | 4 | skeleton; covers requested `LoadingSkeleton` |

Post-creation requirement:

- Domain component drafts, Main/Audit screen states, prototype flow references,
  and Dev Handoff mappings are now created and verified.
- Keep `Base/TextArea` as the canonical spelling; treat `Base/Textarea` as a
  search alias only.
- Treat requested `LoadingSkeleton` as an alias of canonical `Base/Skeleton`.
- Treat `Base/Drawer` as explicitly deferred. Do not use it for Domain
  Components or Main/Audit Screen States unless a future drawer interaction
  task formalizes behavior.
- Treat `Base/ErrorState` as a formal standalone base primitive for page,
  panel, and inline query/command/permission/stale errors. Its Figma
  note/metadata has been synced with the latest spec alignment decision.
- Keep `03 - Base Components` as skeleton-ready only; it is not implementation
  handoff ready.

## 6. Layout Component Readiness

Layout component work is ready only when:

- layout role is clear: shell, top bar, side nav, workbench, panel, drawer,
  timeline, split pane, or inspector;
- desktop constraints are defined;
- tablet/mobile behavior is defined or explicitly deferred;
- component does not include hardcoded business data;
- component supports content overflow and long text;
- dev handoff maps to frontend layout layer.

Current status:

| Item | Status |
|---|---|
| Layout component skeleton creation | completed and verified on 2026-05-24 16:31:16 CST |
| Handoff hygiene pass | completed on 2026-05-25 CST with run marker `plato-handoff-hygiene-2026-05-25`; long variant rows wrapped and notes kept adjacent |
| Layout visual upgrade | completed on 2026-05-25 CST with run marker `plato-layout-visual-upgrade-2026-05-25` |
| Layout overlap fix | completed on 2026-05-25 CST with run marker `plato-layout-overlap-fix-2026-05-25`; internal overlap, clipping, descendant-bound, note/gallery overlap, and width verification passed across all layout component sets |
| P4 acceptance | accepted on 2026-05-26 CST for product-aligned layout reference |
| Passed acceptance scope | TopBar product context, workflow/session SideNav hierarchy, AppShell slot structure, MainWorkArea/DetailPanel/ContextInputBar layout roles, running/readonly/stale/error layout states, no major overlap/clipping, valid component mapping |
| Out of scope for acceptance | final high-fidelity visual polish, final production copy, frontend implementation, responsive/mobile final design, complete interaction behavior |
| Completion status | governed layout components are accepted as P4 product-aligned layout reference; frontend implementation remains incomplete |
| Active run markers | `plato-layout-components-2026-05-24-batched`; `plato-layout-visual-upgrade-2026-05-25`; `plato-layout-overlap-fix-2026-05-25` |
| Target page | `04 - Layout Components` |
| Mapping document | `docs/design/figma-component-mapping.md` |
| Domain components | complete as visually baseline aligned drafts |
| Screen states | Main and Audit screen states created as governed skeletons |
| Prototype flows | created as governed flow references |
| Dev handoff | mapping created for P5 architecture input |

Verified layout component drafts:

| Component | Node ID | Visible variants verified | Hidden archived variants | Status |
|---|---|---:|---:|---|
| `Layout/AppShell` | `45:24` | 4 | 0 | visual baseline aligned draft |
| `Layout/TopBar` | `45:52` | 4 | 0 | visual baseline aligned draft |
| `Layout/SideNav` | `46:43` | 6 | 5 | visual baseline aligned draft |
| `Layout/MainWorkArea` | `46:76` | 6 | 5 | visual baseline aligned draft |
| `Layout/DetailPanel` | `48:72` | 10 | 6 | visual baseline aligned draft |
| `Layout/ContextInputBar` | `48:134` | 7 | 7 | visual baseline aligned draft |

Layout overlap verification:

| Check | Result |
|---|---|
| Components rechecked | `Layout/AppShell`, `Layout/TopBar`, `Layout/SideNav`, `Layout/MainWorkArea`, `Layout/DetailPanel`, `Layout/ContextInputBar` |
| Visible text/component overlap | passed: 0 overlap issues after fix |
| Text clipping against parent bounds | passed: 0 clipping issues after fix |
| Component set descendant bounds | passed: all visible descendants are inside their component set bounds |
| Page-level set/note overlap | passed: 0 overlap pairs using effective descendant bounds |
| Screenshot-width safety | passed: effective maxRight 1592 |
| Node ID preservation | passed: all six layout component set node IDs preserved |
| Export verification | passed for all six layout component sets |
| Governance rule | `.agents/skills/plato-figma-governance/SKILL.md` now requires overlap/clipping verification for every visible Figma write |

Naming and alias decisions:

- `Layout/SideNav` maps to the spec concept `Layout/WorkflowSidebar`.
- `Layout/MainWorkArea` maps to the spec concept `Layout/WorkbenchGrid`.
- `Layout/ContextInputBar` maps to the spec concept `Layout/BottomInputDock`.

Post-creation requirement:

- Domain component drafts and Main/Audit screen states are now created and
  verified. Main screen states are recomposed against upgraded Layout and
  Domain components; Audit screen states still need equivalent recomposition
  before frontend UI implementation.
- `04 - Layout Components` is upgraded enough to guide P5 layout architecture,
  but final responsive behavior, real copy, and production styling remain
  implementation/handoff work.
- Hidden archived skeleton variants were preserved for instance-safety and
  should not be used as implementation targets.

## 7. Domain Component Readiness

Domain component work is ready only when:

- ViewModel fields are identified from
  `docs/frontend/ui-viewmodel-contract.md`;
- backend/source mapping is identified from `docs/frontend/api-ui-mapping.md`;
- permissions and disabled reasons come from data, not visual inference;
- loading/empty/error/partial states are defined if data-driven;
- raw backend/log/provider payloads are not exposed by default;
- dev handoff states whether code exists or is `new component required`.

Domain components include:

- Project;
- Workflow;
- Session;
- TaskTree;
- TaskNode;
- Message;
- Confirmation;
- Result;
- FileChangeSummary;
- AuditRecord;
- AuditEvidence;
- EffectiveConfig;
- RelatedLogs.

Current status:

| Item | Status |
|---|---|
| Domain component skeleton creation | completed and verified on 2026-05-24 17:10:01 CST |
| Handoff hygiene pass | completed on 2026-05-25 CST with run marker `plato-handoff-hygiene-2026-05-25`; long variant rows wrapped and notes kept adjacent |
| Domain visual upgrade brief | created: `docs/design/domain-components-visual-upgrade-brief.md` |
| Domain visual upgrade | completed on 2026-05-25 CST with run marker `plato-domain-visual-upgrade-2026-05-25` |
| Domain overlap/bounds fix | completed on 2026-05-25 CST with run marker `plato-domain-overlap-and-bounds-fix-2026-05-25`; effective-visible overlap, clipping, descendant bounds, set/note overlap, screenshot-width, and representative export verification passed |
| Domain page-level overlap fix | completed on 2026-05-25 CST with run marker `plato-domain-page-overlap-fix-2026-05-25`; stale page title and hygiene note overlap with `Domain/TaskTree` was fixed and all visible top-level nodes were rechecked |
| Domain variant root normalization | completed on 2026-05-25 CST with run marker `plato-domain-variant-root-zero-origin-fix-2026-05-25`; `P4.12 visual draft` roots now start at `x=0, y=0` and variant bounds match/contain root frames |
| Domain TaskTree visual refinement | completed on 2026-05-25 CST with run marker `plato-domain-tasktree-visual-refinement-2026-05-25`; `Domain/TaskTree` now follows the S7 static visual baseline more closely with card rows, hierarchy rhythm, status pills, and selected-node treatment |
| Domain TaskTree height fix | completed on 2026-05-25 CST with run marker `plato-domain-tasktree-height-fix-2026-05-25`; loading, empty, and error variants no longer overflow their component bounds |
| P4 acceptance | accepted on 2026-05-26 CST for domain component skeleton and semantic coverage |
| Passed acceptance scope | structural verification, component existence verification, domain state coverage, no major overlap, base component reuse, representative domain content, confirmation lifecycle coverage, file change/evidence/permission/risk coverage |
| Not passed / out of scope | final visual polish, production copy, frontend implementation readiness, visual regression baseline, full dev handoff readiness |
| Completion status | governed domain components are accepted as P4 domain component skeleton and semantic coverage; frontend implementation remains incomplete |
| Active run markers | `plato-domain-components-2026-05-24-batched`; `plato-domain-visual-upgrade-2026-05-25`; `plato-domain-overlap-and-bounds-fix-2026-05-25`; `plato-domain-page-overlap-fix-2026-05-25`; `plato-domain-variant-root-zero-origin-fix-2026-05-25`; `plato-domain-tasktree-visual-refinement-2026-05-25`; `plato-domain-tasktree-height-fix-2026-05-25` |
| Target page | `05 - Domain Components` |
| Mapping document | `docs/design/figma-component-mapping.md` |
| Main screen states | created and verified on 2026-05-24 17:41:55 CST |
| Audit screen states | created and verified on 2026-05-24 19:17:53 CST |
| Prototype flows | created as governed flow references |
| Dev handoff | mapping created for P5 architecture input |

Verified domain component drafts:

| Component | Node ID | Variants verified | Status |
|---|---|---:|---|
| `Domain/TaskTree` | `58:55` | 7 | visual baseline aligned draft |
| `Domain/TaskNode` | `58:203` | 12 | visual baseline aligned draft |
| `Domain/MessageStream` | `59:113` | 6 | visual baseline aligned draft |
| `Domain/MessageCard` | `59:201` | 12 | visual baseline aligned draft |
| `Domain/ConfirmationPanel` | `60:333` | 11 | visual baseline aligned draft |
| `Domain/FileChangeTable` | `61:316` | 9 | visual baseline aligned draft |
| `Domain/AuditEntryCard` | `61:409` | 9 | visual baseline aligned draft |

Domain overlap and bounds verification:

| Check | Result |
|---|---|
| Effective-visible text overlap | passed: zero overlap issues across 7 component sets and 7 note frames |
| Text clipping | passed: zero clipping issues |
| Component set descendant bounds | passed: all visible descendants contained by component/note bounds |
| Variant root zero-origin | passed: zero variant root offset/overflow issues after fixed-layout normalization |
| TaskTree static-baseline refinement | passed: row-card hierarchy, selected child row, status pills, and state-specific previews applied to `Domain/TaskTree` |
| TaskTree variant height containment | passed: zero internal overflow issues after height fix |
| Page-level all-visible-top-level overlap | passed: zero overlap pairs across 16 visible top-level nodes, including title and hygiene notes |
| Screenshot-width safety | passed: effective maxRight 1432 |
| Export verification | passed for representative sets: `TaskTree`, `ConfirmationPanel`, `FileChangeTable`, `AuditEntryCard`; post-fix exports also passed for `TaskTree` and `ConfirmationPanel` |
| Node ID preservation | passed: all seven component set node IDs preserved |

Naming and alias decisions:

- `Domain/TaskNode` maps to `Domain/TaskNodeCard`.
- `Domain/MessageStream` maps to message stream composition around
  `Domain/SessionMessageRow`.
- `Domain/MessageCard` maps to `Domain/SessionMessageRow`.
- `Domain/ConfirmationPanel` maps to `Domain/ConfirmationCard`.
- `Domain/FileChangeTable` maps to `Domain/FileChangeSummary` plus audit
  file-change evidence rows.
- `Domain/AuditEntryCard` maps to `Domain/AuditRecordCard` or
  `Domain/AuditSummaryLink`, depending usage context.

Post-creation requirement:

- Main and Audit screen states are now created and verified, but they must be
  recomposed after Layout and Domain visual upgrades before frontend visual
  implementation.
- Do not use `Base/Drawer` unless drawer behavior is formalized in a future
  task.

## 8. Screen State Readiness

Main Page screen states are ready only when they map to:

- planning state;
- task readiness;
- execution status;
- confirmation status and local overlay;
- permission/action availability;
- input mode;
- stale/resync behavior.

Audit Page screen states are ready only when they map to:

- audit scope;
- route entry context;
- return target;
- audit verdict;
- record filters;
- selected record detail;
- evidence availability/hidden/redacted state;
- effective config summary;
- related logs link;
- page state: loading, ready, empty, partial, hidden evidence, permission
  denied, error, stale.

Current status:

| Item | Status |
|---|---|
| Main UX flow map | created and verified on 2026-05-24 17:41:55 CST |
| Main UX flow fidelity upgrade | completed on 2026-05-26 CST with run marker `plato-main-ux-flow-fidelity-2026-05-26`; readable overview node `292:2` added and State Inventory node `69:2` preserved |
| Main screen state frames | created and verified on 2026-05-24 17:41:55 CST |
| Main screen state recomposition | completed on 2026-05-26 CST with run marker `plato-main-screen-state-recomposition-2026-05-26`; S1-S13 recomposed from accepted `04 - Layout Components`, accepted `05 - Domain Components`, and upgraded `06 - Main UX Flow` overview |
| Audit UX flow map | created and verified on 2026-05-24 19:17:53 CST |
| Audit screen state frames | created and verified on 2026-05-24 19:17:53 CST |
| Screen-state handoff hygiene pass | completed on 2026-05-25 CST with run marker `plato-screen-state-handoff-hygiene-2026-05-25`; S10 and A1-A14 readability zones updated, Main frames normalized for screenshot readability |
| Active Main run marker | `plato-main-screen-states-2026-05-24-batched` |
| Active Main recomposition marker | `plato-main-screen-state-recomposition-2026-05-26` |
| Active Main UX Flow run marker | `plato-main-ux-flow-fidelity-2026-05-26` |
| Active Audit run marker | `plato-audit-screen-states-2026-05-24-batched` |
| Active Prototype run marker | `plato-prototype-flows-2026-05-24-batched` |
| Target pages | `06 - Main UX Flow`, `07 - Main Screen States`, `08 - Audit UX Flow`, `09 - Audit Screen States`, `10 - Prototype Flows` |
| Mapping document | `docs/design/figma-component-mapping.md` |
| Layout contract | active: `docs/design/figma-layout-contract.md` is required before future Screen State edits |
| Prototype flows | created and verified on 2026-05-24 23:00:30 CST |
| Dev handoff | mapping created for P5 architecture input |

Verified Main UX Flow overview:

| Element | Node ID | Status |
|---|---|---|
| `Main UX Flow Overview / P4.9` | `292:2` | readable UX flow overview created |
| `State Inventory / Governed S1-S13 (preserved)` | `69:2` | existing state inventory preserved |

Main UX Flow transition coverage:

| Flow section | Transitions represented |
|---|---|
| Happy path | `S1 -> S2`, `S2 -> S3`, `S3 -> S4`, `S4 -> S5`, `S5 -> S6`, `S6 -> S7`, `S7 -> S8`, `S8 -> S9` |
| Recovery / negative path | `Any -> S10`, `Any -> S11`, `Any -> S12`, `Any -> S13` |
| Main-to-Audit entry / return | `S8 -> Audit`, `S9 -> Audit`, `Task -> Audit`, `Confirm -> Audit`, `Audit -> Main` |

Main UX Flow verification:

| Check | Result |
|---|---|
| State inventory distinguished from UX flow | passed |
| Action/API/condition/destination labels | passed: 17 transition cards |
| Existing state IDs | preserved; no S1-S13 definition changes |
| Overview text overlap | passed: 0 |
| Overview text clipping | passed: 0 |
| State inventory descendant overflow | passed: 0 |
| Page-level overlap | passed: 0 |
| Screenshot-width safety | passed: maxRight 1600 |
| Screenshot verification | passed for node `292:2` at 1440x1590 |

Verified Main screen state frames:

| State | Frame | Node ID | Readiness |
|---|---|---|---|
| `S1` | `S1 - Empty New Session` | `71:2` | recomposed product-aligned reference, not prototype-wired |
| `S2` | `S2 - Understanding / Planning` | `71:110` | recomposed product-aligned reference, not prototype-wired |
| `S3` | `S3 - Draft Task Tree Ready` | `71:217` | recomposed product-aligned reference, not prototype-wired |
| `S4` | `S4 - Task Node Selected` | `73:216` | recomposed product-aligned reference, not prototype-wired |
| `S5` | `S5 - Task Node Editing` | `73:334` | recomposed product-aligned reference, not prototype-wired |
| `S6` | `S6 - Published / Running` | `73:450` | recomposed product-aligned reference, not prototype-wired |
| `S7` | `S7 - Waiting For Confirmation` | `75:432` | recomposed product-aligned reference, not prototype-wired |
| `S8` | `S8 - Completed With Result` | `75:563` | recomposed product-aligned reference, not prototype-wired |
| `S9` | `S9 - File Change Summary / Audit Entry` | `75:686` | recomposed product-aligned reference, not prototype-wired |
| `S10` | `S10 - Permission Denied` | `77:659` | recomposed product-aligned reference, not prototype-wired |
| `S11` | `S11 - Stale Snapshot / Resync Required` | `77:775` | recomposed product-aligned reference, not prototype-wired |
| `S12` | `S12 - Backend Busy / Command Accepted But Delayed` | `77:883` | recomposed product-aligned reference, not prototype-wired |
| `S13` | `S13 - Command Failed / Recoverable Error` | `77:986` | recomposed product-aligned reference, not prototype-wired |

Main screen state recomposition verification:

| Check | Result |
|---|---|
| State frame preservation | passed: S1-S13 node IDs preserved |
| State definition preservation | passed: no new states and no S1-S13 definition changes |
| Accepted component basis | passed: previews recomposed from accepted `04`, accepted `05`, and upgraded `06` |
| Preview zones | passed: all S1-S13 have `P4.10 / Screen composition preview` |
| Run marker | passed: all S1-S13 carry `plato-main-screen-state-recomposition-2026-05-26` |
| Top-level overlap | passed: `0` |
| Text overlap | passed: `0` |
| Descendant overflow | passed: `0` |
| Screenshot verification | passed for S7, S9, S10, and S13 at `1440x1380` |

Post-creation notes:

- Main screen states reuse existing Base/Layout/Domain component instances.
- User-requested state labels that differ from `prototype-state-map.md`
  canonical numbering are mapped in visible Figma metadata and the mapping doc.
- Permission denied, stale/resync, pending command, and recoverable command
  failure remain separate state dimensions instead of execution statuses.
- Audit Page screen states reuse existing Base/Layout/Domain component
  instances and keep audit verdict, permission/action availability, evidence
  visibility, snapshot freshness, and query/loading/error state separate.

Verified Audit screen state frames:

| State | Frame | Node ID | Readiness |
|---|---|---|---|
| `A1` | `A1 - Audit Empty` | `91:2` | governed skeleton, not prototype-wired |
| `A2` | `A2 - Audit Loading` | `91:93` | governed skeleton, not prototype-wired |
| `A3` | `A3 - Audit Records Ready` | `91:165` | governed skeleton, not prototype-wired |
| `A4` | `A4 - Audit Record Selected` | `93:149` | governed skeleton, not prototype-wired |
| `A5` | `A5 - Partial Evidence` | `93:248` | governed skeleton, not prototype-wired |
| `A6` | `A6 - Hidden Evidence / Permission Limited` | `93:344` | governed skeleton, not prototype-wired |
| `A7` | `A7 - Warning Verdict` | `95:313` | governed skeleton, not prototype-wired |
| `A8` | `A8 - Failed Verdict` | `95:410` | governed skeleton, not prototype-wired |
| `A9` | `A9 - Inconclusive Verdict` | `95:507` | governed skeleton, not prototype-wired |
| `A10` | `A10 - Not Available Verdict` | `95:601` | governed skeleton, not prototype-wired |
| `A11` | `A11 - Permission Denied` | `98:527` | governed skeleton, not prototype-wired |
| `A12` | `A12 - Stale Snapshot / Records Changed` | `98:613` | governed skeleton, not prototype-wired |
| `A13` | `A13 - Audit Query Error` | `98:977` | governed skeleton, not prototype-wired |
| `A14` | `A14 - Evidence Load Error` | `98:1040` | governed skeleton, not prototype-wired |

Audit post-creation notes:

- Audit UX flow map `Audit UX Flow Map / Governed States` is created on
  `08 - Audit UX Flow` with node ID `89:2`.
- All Audit state frames contain visible metadata for entry context, audit
  scope, verdict, permission/action availability, evidence visibility, snapshot
  freshness, query/loading/error state, required data, actions, disabled
  states, exit conditions, behavior, source docs, and readiness.
- `Base/Drawer` was not used.
- Structural verification passed with no missing frames, metadata, run marker,
  or overlap.
- Screenshot verification passed for `A3 - Audit Records Ready` at 1600x892.

Screen-state handoff hygiene notes:

- P4.6 readability pass completed on 2026-05-25 with run marker
  `plato-screen-state-handoff-hygiene-2026-05-25`.
- S1-S13 and A1-A14 node IDs were preserved.
- Main state frames were normalized to 1440x1340 so component proof content is
  not clipped in common screenshots.
- S10 now separates screen composition, state metadata, and component usage /
  implementation notes.
- Audit states A1-A14 now use visible handoff metadata panels; overlapping
  legacy metadata overlay nodes are hidden for traceability instead of used as
  the handoff source.
- A11 Permission Denied now has a readable metadata panel and explicit
  permission/error hierarchy with return/fallback behavior visible.
- Effective-visibility structural verification passed with zero missing states,
  zero visible metadata overlays, and zero visible handoff/text clipping.
- Screenshot verification passed for S10 (`77:659`, 1440x1340), A11
  (`98:527`, 1440x1580), S1 (`71:2`, 1440x1340), and A4 (`93:149`, rendered
  1409x1600 from original 1440x1635). A3 screenshot transport failed twice, so
  A4 was used as the normal Audit-state fallback.

Required verification for future Screen State edits:

| Verification | Required check | Status |
|---|---|---|
| Structural verification | State IDs, run marker, required zones, visible metadata, and component instances still exist | required per task |
| Layout readability verification | No text overlap, metadata clipping, preview/metadata collision, or unreadable hierarchy at normal review zoom | required per task |
| Screenshot verification | Attempt screenshot-width verification at 1600px or nearest supported transport width; record failures separately | required per task |
| Metadata overflow verification | Figma metadata respects `figma-layout-contract.md` max text rules; full metadata is moved to docs | required per task |

## 9. Prototype Readiness

Prototype work is ready only when:

- source and destination screen states are approved;
- route parameters and query state are named;
- selected task/record persistence is defined;
- input mode changes are explicit;
- command/result/resync behavior is documented;
- Audit Page transitions remain read-only;
- return targets from Audit Page to Main Page are preserved.

High-confidence prototype work should use `docs/ux/prototype-state-map.md`.

Current status:

| Item | Status |
|---|---|
| Prototype flow references | created and verified on 2026-05-24 23:00:30 CST |
| Target page | `10 - Prototype Flows` |
| Active run marker | `plato-prototype-flows-2026-05-24-batched` |
| Dev handoff | mapping created for P5 architecture input |

Verified prototype flow references:

| Flow | Frame | Node ID | Coverage |
|---|---|---|---|
| `Flow 1` | `Flow 1 - Main happy path` | `124:6` | S1 -> S9 |
| `Flow 2` | `Flow 2 - Main recovery / negative path` | `124:71` | S10 -> S13 |
| `Flow 3` | `Flow 3 - Main to Audit entry` | `128:2` | S8/S9/S4/S7 -> Audit route entry |
| `Flow 4` | `Flow 4 - Audit happy path` | `128:69` | A1 -> A4 |
| `Flow 5` | `Flow 5 - Audit evidence / verdict path` | `130:2` | A4 -> A5/A6/A7/A8/A9/A10 |
| `Flow 6` | `Flow 6 - Audit recovery / negative path` | `130:62` | A11/A12/A13/A14 |
| `Flow 7` | `Flow 7 - Return paths` | `130:124` | Audit -> originating Main context and previous valid state |

Prototype post-creation notes:

- Flow references include visible metadata for flow ID, entry/exit state,
  trigger, user action, backend/API dependency, route context, recovery
  behavior, related source docs, and readiness.
- Route from Main to Audit preserves return context.
- Stale snapshot recovery is separate from generic query/evidence retry.
- Permission denied has explicit fallback/return behavior.
- Hidden evidence remains permission-limited, not missing data.
- `A3 - Audit Records Ready` covers passed/default audit entries.
- Screenshot verification passed for the prototype flow title frame at
  1600x219.

## 10. Dev Handoff Readiness

Dev handoff is ready only when every mapped element has:

| Field | Required |
|---|---:|
| Figma element/page/frame/component | yes |
| Code component or `new component required` | yes |
| Props/ViewModel fields | yes |
| Backend/source data or `mock only`/`contract pending` | yes |
| State/variant coverage | yes |
| Responsive note | yes for page/layout components |
| Accessibility note | yes for interactive components |
| Open implementation risk | yes if any |

Current status:

| Item | Status |
|---|---|
| Dev Handoff page | `11 - Dev Handoff` |
| Dev Handoff mapping creation | completed and verified on 2026-05-24 23:31:00 CST |
| Active Dev Handoff run marker | `plato-dev-handoff-2026-05-24-batched` |
| Repo mirror | `docs/design/dev-handoff.md` |
| Layout contract | active: `docs/design/figma-layout-contract.md` is required before future Dev Handoff edits |
| Layout template creation | completed on 2026-05-25 CST with run marker `plato-layout-templates-2026-05-25` |
| Layout template text hygiene | completed on 2026-05-25 CST with run marker `plato-layout-template-text-hygiene-2026-05-25`; collapsed 1px text heights fixed |
| Readiness | ready as P5 frontend architecture mapping input; visual baseline alignment and frontend implementation are not complete |

Verified Dev Handoff sections:

| Section | Node ID | Status |
|---|---|---|
| `Dev Handoff / Overview` | `136:2` | created |
| `Dev Handoff / Token-to-Code Mapping` | `136:7` | created |
| `Dev Handoff / Component-to-Code Mapping` | `136:12` | created |
| `Dev Handoff / Main State Handoff S1-S13` | `138:2` | created |
| `Dev Handoff / Audit State Handoff A1-A14` | `140:2` | created |
| `Dev Handoff / Prototype Flow Handoff Flow 1-7` | `142:2` | created |
| `Dev Handoff / API and ViewModel Gaps` | `142:7` | created |
| `Dev Handoff / Frontend Architecture Input Summary` | `142:12` | created |
| `Dev Handoff / Implementation Readiness Checklist` | `142:17` | created |
| `Dev Handoff / Not Ready and Blocked` | `142:22` | created |
| `Dev Handoff / Layout Templates` | `188:2` | created |

Dev Handoff is still not frontend implementation. P5 architecture, P6 API/mock
boundary, and frontend source changes remain separate gated tasks.

Required verification for future Dev Handoff edits:

| Verification | Required check | Status |
|---|---|---|
| Structural verification | Handoff section headers, mapping rows, node IDs, source references, gaps, and readiness notes still exist | required per task |
| Layout readability verification | Tables/lists are readable, not clipped, and not mixed with screen previews or component proof galleries | required per task |
| Screenshot verification | Attempt screenshot-width verification for changed handoff sections; record transport failure separately from structural verification | required per task |
| Metadata overflow verification | Figma contains summaries only; long mapping detail is kept in `docs/design/dev-handoff.md` | required per task |

Verified layout template nodes:

| Template | Node ID | Verification |
|---|---|---|
| `ScreenStateTemplate` | `188:5` | structural, zone, overflow, overlap, screenshot passed |
| `AuditStateTemplate` | `188:56` | structural, zone, overflow, overlap, screenshot passed |
| `DevHandoffSectionTemplate` | `188:107` | structural, zone, overflow, overlap, screenshot passed |
| `MetadataSummaryCard` | `188:132` | structural and overflow passed |
| `ImplementationNotesCard` | `188:141` | structural and overflow passed |
| `ComponentUsageSummaryCard` | `188:145` | structural and overflow passed |

Layout template notes:

- templates are reusable Figma frames, not production components;
- future Screen State and Dev Handoff work should copy or instantiate the
  layout pattern before adding state-specific content;
- existing S1-S13, A1-A14, and Dev Handoff sections were not rewritten;
- `whoami` failed due a ChatGPT app transport issue, but Figma metadata read,
  `use_figma` read, write, structural verification, and screenshots succeeded.
- text hygiene fixed template font overlap by normalizing 82 text node heights;
  post-fix verification found zero short text nodes, zero metadata overflow
  nodes, zero visible text overlaps, and required zones intact.
- screen composition size normalization on 2026-05-26 updated
  `ScreenStateTemplate` (`188:5`) to `1986x1540` and `AuditStateTemplate`
  (`188:56`) to `1986x1610`; both templates now use a fixed `1440x1024`
  screen preview zone.
- visible P4.10 preview normalization on 2026-05-26 updated all S1-S13
  `P4.10 / Screen composition preview` zones to `1440x1024` and created
  `Template / P4.10 Screen composition preview` (`341:2`) as the reusable
  fixed product-state preview template.

## 11. Screen State Layout Normalization Readiness

Figma screen-state layout normalization is a readability and handoff pass only.
It does not create new states, change state IDs, change backend mappings, create
new components, or implement frontend code.

Current status:

| Item | Status |
|---|---|
| Run marker | `plato-screen-state-layout-normalization-2026-05-25` |
| Main states | S1-S13 normalized against `ScreenStateTemplate` zones |
| Audit states | A1-A14 normalized against `AuditStateTemplate` zones |
| State frame node IDs | preserved for all S1-S13 and A1-A14 frames |
| Zone model | header, screen composition preview, metadata summary, implementation notes, component usage summary |
| Main screen composition size | S1-S13 visible `P4.10 / Screen composition preview` zones normalized to `1440x1024` on 2026-05-26 |
| Long metadata handling | full details remain in `docs/design/dev-handoff.md`; Figma frames contain short summaries |
| Component proof handling | proof galleries removed from visible preview zones; component usage is summarized textually |
| Main structural verification | passed for S1-S13: state frame IDs preserved, `1986x1540` outer frames, visible `P4.10` zones sized `1440x1024`, no direct top-level overlap |
| Audit structural verification | passed for A1-A14: 1440x1620, fixed layout, clipped, five visible P4.7 zones |
| Error/permission/stale/partial verification | passed for S10, S11, S12, S13, A5, A6, A11, A12, A13, A14 |
| Visible overlap verification | passed; zero visible text overlap issues detected |
| Screenshot verification | passed for S10, S8, A11, and A3; S1 screenshot attempt failed once due `backend-api/wham/apps` transport |

## 12. Screen State Semantic Fidelity Readiness

Figma screen-state semantic fidelity is a preview-content pass only. It restores
state-specific meaning inside normalized preview zones while preserving the
layout contract and avoiding component proof galleries.

Current status:

| Item | Status |
|---|---|
| Run marker | `plato-screen-state-semantic-fidelity-2026-05-25` |
| Main states | S1-S13 semantic previews updated in place |
| Audit states | A1-A14 semantic previews updated in place |
| State frame node IDs | preserved for all S1-S13 and A1-A14 frames |
| Layout contract | preserved: content remains inside `P4.7 / Screen composition preview`; metadata and notes remain separate |
| Main semantic coverage | S1 empty input, S2 planning/loading, S3 draft tree, S4 selection, S5 editing, S6 running, S7 confirmation, S8 result, S9 file/audit, S10 permission, S11 stale, S12 busy, S13 recoverable error |
| Audit semantic coverage | A1 empty, A2 loading, A3 records ready, A4 selected record, A5 partial, A6 hidden evidence, A7 warning, A8 failed, A9 inconclusive, A10 not available, A11 permission denied, A12 stale, A13 query error, A14 evidence load error |
| S7 overlap follow-up | one ConfirmationPanel title/risk-badge overlap was detected and fixed |
| Post-write read verification | blocked after S7 fix by two consecutive 120s Figma MCP `use_figma` timeouts |
| Screenshot verification | S7 screenshot attempt timed out after 120s; remaining required screenshots deferred until transport stabilizes |
| Readiness | semantically applied but not fully post-write visually verified |

Required follow-up:

- run a verification-only Figma task when MCP transport is stable;
- verify no visible overlap for S1-S13 and A1-A14;
- verify S7, S9, S10, A5, A6, A11, A13 screenshots or equivalent visual
  inspection;
- only then mark semantic fidelity as fully visually verified.

## 13. Visual Baseline Alignment Readiness

Visual baseline alignment verifies that canonical Figma pages express the
historical Main Page product density and visual direction without copying old
frames or treating old files as canonical.

Current status:

| Dimension | Status |
|---|---|
| Audit artifact | `docs/design/visual-baseline-alignment.md` created on 2026-05-25 |
| Layout visual upgrade brief | `docs/design/layout-components-visual-upgrade-brief.md` created on 2026-05-25 |
| Layout visual upgrade pass | completed on `04 - Layout Components` with run marker `plato-layout-visual-upgrade-2026-05-25` |
| Historical reference | `Plato MVP Main Page UX Draft`, file key `wHFPOBaxeImyhJer7BnMaq`; archive/reference only |
| Canonical target | `Plato Product Design System and Prototype`, file key `CTK1yALdNEFo2zL8ZcEJIA` |
| Structural readiness | mostly complete: tokens, Base/Layout/Domain skeletons, S1-S13, A1-A14, prototype flows, and Dev Handoff mappings exist |
| Semantic fidelity readiness | partial: P4.8 semantic previews were applied, but visual verification was blocked by Figma MCP timeouts and many previews still contain generic skeleton labels |
| Visual baseline alignment readiness | partial overall: `04 - Layout Components` and `05 - Domain Components` are accepted for P4 scope; `07 - Main Screen States` is recomposed; Audit screen states still need recomposition against the upgraded components |
| Frontend implementation readiness | not ready for visual implementation; current Figma is usable as architecture/mapping input only |

Page-level status:

| Page | Structural readiness | Semantic fidelity readiness | Visual baseline alignment readiness | Frontend implementation readiness |
|---|---|---|---|---|
| `04 - Layout Components` | valid | improved | accepted for P4 product-aligned layout reference; AppShell, TopBar, SideNav, MainWorkArea, DetailPanel, and ContextInputBar upgraded from skeletons | not ready |
| `05 - Domain Components` | valid | improved | accepted for P4 domain component skeleton and semantic coverage; TaskTree, TaskNode, messages, confirmation, file, and audit components upgraded from skeletons | not ready |
| `07 - Main Screen States` | valid | improved | recomposed from accepted `04`/`05` and upgraded `06`; P4 product-aligned reference, not final visual polish | not ready |
| `09 - Audit Screen States` | valid | partial | not ready; Audit needs a product visual baseline aligned to evidence/trust-plane behavior | not ready |
| `11 - Dev Handoff` | valid as mapping input | partial | partial; should warn engineers not to treat skeleton previews as visual-ready targets | not ready |

P4.11 layout visual upgrade verification:

| Check | Result |
|---|---|
| Component sets covered | `Layout/AppShell`, `Layout/TopBar`, `Layout/SideNav`, `Layout/MainWorkArea`, `Layout/DetailPanel`, `Layout/ContextInputBar` |
| Node IDs | preserved for all six layout component sets |
| Visible variants | AppShell 4, TopBar 4, SideNav 6, MainWorkArea 6, DetailPanel 10, ContextInputBar 7 |
| Hidden archived variants | SideNav 5, MainWorkArea 5, DetailPanel 6, ContextInputBar 7; kept for instance-safety instead of destructive deletion |
| Structural verification | passed; page visible maxRight 1592 |
| Export verification | passed for all six layout component sets |
| Frontend code | not modified |

Required follow-up:

- keep old Figma frames as pattern reference only;
- recompose Main/Audit screen states using the upgraded Layout and Domain
  component drafts;
- update Dev Handoff after visual baseline alignment so engineers can clearly
  distinguish structural mapping from visual implementation targets.

## 14. Handoff Hygiene Readiness

Figma handoff hygiene is a visual-organization pass only. It does not create
new components, variants, states, flows, state dimensions, API mappings, or
frontend implementation.

Current status:

| Item | Status |
|---|---|
| Hygiene pass | completed on 2026-05-25 CST |
| Run marker | `plato-handoff-hygiene-2026-05-25` |
| Pages inspected | `03 - Base Components`, `04 - Layout Components`, `05 - Domain Components`, `07 - Main Screen States`, `09 - Audit Screen States`, `10 - Prototype Flows`, `11 - Dev Handoff` |
| Pages changed | `03 - Base Components`, `04 - Layout Components`, `05 - Domain Components` |
| Structural verification | passed: page content stayed readable within a 1600px screenshot-width target after reflow (`03` maxRight 1416, `04` maxRight 1592, `05` maxRight 1552) |
| Screenshot verification | passed for `Layout/TopBar` (`45:52`, 1168x368), `Domain/TaskNode` (`58:203`, 1184x1040), and `Base/Button` (`28:46`, 828x296) |
| Placeholder copy warning | added to Base, Layout, and Domain pages; labels such as `Primary`, `Neutral`, `Card title`, and repeated skeleton text are component placeholders, not production copy |

Preserved:

- component set node IDs;
- variant semantics and counts;
- token bindings;
- canonical status model and state mappings;
- route, API, and ViewModel handoff mappings.

## 15. File Skeleton Readiness

The new canonical file skeleton is ready to create when:

- governance docs exist;
- canonical file name is known;
- canonical page structure is known;
- no old content migration is included;
- first Figma task is limited to pages and notes;
- Figma Operation Gate Report allows a write.

Current status:

| Item | Status |
|---|---|
| Governance docs | complete |
| Canonical file name | complete |
| Canonical page structure | complete |
| Skeleton creation attempt | complete |
| Canonical file URL | <https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA> |
| File key | `CTK1yALdNEFo2zL8ZcEJIA` |
| Registry | recorded in `docs/design/figma-file-registry.md` |
| Dev handoff readiness | mapping created for P5 architecture input |

Skeleton creation is complete. Dev Handoff mapping is also created, but the
frontend implementation is not complete.

## 16. Acceptance Criteria

- Checklist status is consulted before each Figma task.
- Missing docs are surfaced in the operation report.
- Skeleton work is not blocked by missing component/prototype docs.
- Production-grade components and prototypes are blocked until the relevant
  operation gate confirms the required docs and Figma prerequisites.
- Dev handoff is not marked ready unless Figma, code, props, and data sources
  are mapped.
- Future Screen State and Dev Handoff Figma writes pass structural,
  layout-readability, screenshot-width, and metadata-overflow verification from
  `docs/design/figma-layout-contract.md`.
