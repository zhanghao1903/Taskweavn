# Plato Figma File Registry

> Status: skeleton created
> Last Updated: 2026-05-25
> Scope: Canonical Figma file registration for Plato design governance.

## 1. Canonical File

| Field | Value |
|---|---|
| Canonical file name | `Plato Product Design System and Prototype` |
| File URL | <https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA> |
| File key | `CTK1yALdNEFo2zL8ZcEJIA` |
| Editor type | Figma design |
| Creation timestamp | 2026-05-24 12:26:31 CST |
| Last verified | 2026-05-25 CST |
| Last token update | 2026-05-24 13:15:54 CST |
| Last base component attempt | 2026-05-24 13:41:33 CST, blocked by Figma MCP timeout before verification |
| Last base component retry | 2026-05-24 14:35:03 CST, blocked during Figma pre-check because `whoami` timed out after 120s; no page inspection or writes were attempted |
| Last base component creation request | 2026-05-24 14:51:55 CST, blocked during required Figma access pre-check because `whoami` timed out after 120s; no page inspection or writes were attempted |
| Latest base component creation request | 2026-05-24 15:13:40 CST, blocked during required Figma access pre-check because `whoami` timed out after 120s; no page inspection or writes were attempted |
| Last base component skeleton creation | 2026-05-24 15:50:19 CST, created and verified with run marker `plato-base-components-2026-05-24-batched` |
| Last base component stabilization | 2026-05-24 15:50:19 CST, existing node IDs preserved; notes organized next to component sets; mapping doc created |
| Last base spec-status sync | 2026-05-24 17:00:08 CST, synced `Base/ErrorState` and `Base/Drawer` notes/metadata with run marker `plato-base-spec-status-sync-2026-05-24` |
| Last layout component skeleton creation | 2026-05-24 16:31:16 CST, created and verified with run marker `plato-layout-components-2026-05-24-batched` |
| Last domain component skeleton creation | 2026-05-24 17:10:01 CST, created and verified with run marker `plato-domain-components-2026-05-24-batched` |
| Last Main screen state creation | 2026-05-24 17:41:55 CST, created and verified Main UX flow map and S1-S13 Main screen state frames with run marker `plato-main-screen-states-2026-05-24-batched` |
| Last Audit screen state creation | 2026-05-24 19:17:53 CST, created and verified Audit UX flow map and A1-A14 Audit screen state frames with run marker `plato-audit-screen-states-2026-05-24-batched` |
| Last prototype flow creation | 2026-05-24 23:00:30 CST, created and verified governed prototype flow references Flow 1-7 with run marker `plato-prototype-flows-2026-05-24-batched` |
| Last Dev Handoff mapping creation | 2026-05-24 23:31:00 CST, created and verified governed Dev Handoff mapping sections with run marker `plato-dev-handoff-2026-05-24-batched` |
| Last handoff hygiene pass | 2026-05-25 CST, reflowed Base/Layout/Domain component galleries and adjacent notes with run marker `plato-handoff-hygiene-2026-05-25`; inspected Main/Audit state, Prototype Flow, and Dev Handoff pages |
| Status | skeleton created; governed token layer created; base component skeletons stabilized; layout and domain component skeletons created; Main and Audit screen states created; prototype flow references created; Dev Handoff mapping created for P5 architecture input; handoff hygiene pass completed |
| Dev handoff readiness | mapping created for P5 architecture input; frontend implementation not complete |

## 2. Access Check

The required Figma access/token pre-check succeeded before file creation.

```text
whoami succeeded
plan: fraser stone's team
plan key: team::1636738050709715017
```

Previous blocked attempts are retained for traceability:

- 2026-05-24 11:54:15 CST: `whoami` failed with `401 token_expired`.
  No Figma write was attempted.
- 2026-05-24 12:02:54 CST: `whoami` failed with `401 token_expired`.
  No Figma write was attempted.
- 2026-05-24 12:10:05 CST: `whoami` failed with `401 token_expired`.
  No Figma write was attempted.
- 2026-05-24 12:12:55 CST: `whoami` failed while requesting
  `https://chatgpt.com/backend-api/wham/apps`. No Figma write was attempted.
- 2026-05-24 14:35:03 CST: base component recovery retry `whoami`
  pre-check timed out after 120s. No Figma write was attempted.
- 2026-05-24 14:51:55 CST: base component creation request `whoami`
  pre-check timed out after 120s. No Figma write was attempted.
- 2026-05-24 15:13:40 CST: repeated base component creation request
  `whoami` pre-check timed out after 120s. No Figma write was attempted.

## 3. Page Registry

The canonical file skeleton contains these top-level pages.

| Order | Page name | Status | Page ID | Skeleton frame ID |
|---:|---|---|---|---|
| 1 | `00 - Governance` | skeleton | `0:1` | `4:2` |
| 2 | `01 - Tokens` | governed variables/styles created | `4:20` | `4:21` |
| 3 | `02 - Brand Assets` | skeleton | `4:27` | `4:28` |
| 4 | `03 - Base Components` | governed base component skeletons stabilized | `4:34` | `4:35` |
| 5 | `04 - Layout Components` | governed layout component skeletons created | `4:41` | `4:42` |
| 6 | `05 - Domain Components` | governed domain component skeletons created | `4:48` | `4:49` |
| 7 | `06 - Main UX Flow` | governed Main UX flow map created | `4:55` | `4:56` |
| 8 | `07 - Main Screen States` | governed Main screen state frames created | `4:62` | `4:63` |
| 9 | `08 - Audit UX Flow` | governed Audit UX flow map created | `4:69` | `4:70` |
| 10 | `09 - Audit Screen States` | governed Audit screen state frames created | `4:76` | `4:77` |
| 11 | `10 - Prototype Flows` | governed prototype flow references created | `4:83` | `4:84` |
| 12 | `11 - Dev Handoff` | governed Dev Handoff mapping created | `4:90` | `4:91` |
| 13 | `99 - Archive References` | archive/reference only | `4:113` | `4:114` |

## 4. Skeleton Scope Created

Created:

- canonical Figma design file;
- canonical page structure;
- page title frames;
- source/governance notes;
- placeholder section frames;
- Dev Handoff placeholder sections;
- Archive References warning that old files are historical/reference input only.
- governed token variables/styles in `01 - Tokens`.
- governed base component skeletons in `03 - Base Components`.
- governed layout component skeletons in `04 - Layout Components`.
- governed domain component skeletons in `05 - Domain Components`.
- governed Main UX flow map in `06 - Main UX Flow`.
- governed Main screen state frames in `07 - Main Screen States`.
- governed Audit UX flow map in `08 - Audit UX Flow`.
- governed Audit screen state frames in `09 - Audit Screen States`.
- governed prototype flow references in `10 - Prototype Flows`.
- governed Dev Handoff mapping sections in `11 - Dev Handoff`.
- governed handoff hygiene organization on `03 - Base Components`,
  `04 - Layout Components`, and `05 - Domain Components`.

Not created:

- old Figma content migration;
- high-fidelity UI;
- high-fidelity production components;
- implementation-ready component variants;
- high-fidelity motion polish;
- frontend implementation source code.

## 5. Token Layer Created

Created on 2026-05-24 13:15:54 CST:

| Token group | Figma structure | Count/status |
|---|---|---|
| color | Variable collection `Plato Color`, mode `Light` | 88 variables |
| typography | Variable collection `Plato Typography`, text styles | 2 family variables, 6 text styles |
| spacing | Variable collection `Plato Spacing` | 8 variables |
| radius | Variable collection `Plato Radius` | 3 variables |
| shadow | Effect styles | 2 styles: `shadow/panel`, `shadow/focus` |
| motion | Variable collection `Plato Motion` | 4 variables |
| breakpoint | Variable collection `Plato Breakpoint` | 4 variables |
| z-index | Variable collection `Plato Z Index` | 5 variables |

Token documentation frame:

| Field | Value |
|---|---|
| Page | `01 - Tokens` |
| Frame | `Token Documentation / Governed Tokens v0.1` |
| Frame ID | `10:131` |

Partial notes:

- Auxiliary success/warning/danger primitive colors use the existing frontend
  CSS baseline because `docs/design/design-system.md` names those tones but
  does not fully enumerate their raw values.
- `color/semantic/surface-muted` resolves to `classic-cream`; the
  design-system contract allows classic-cream or light blue, so this needs
  visual QA during component creation.
- `color/semantic/focus-ring` uses the existing frontend CSS focus alpha of
  16%.
- Breakpoint variables store min-width thresholds; range semantics remain in
  `docs/design/design-system.md`.
- Typography text styles use the existing frontend `Text` component CSS
  baseline for sizes and weights because the design-system contract defines
  roles but not numeric type metrics.

## 6. Base Component Skeletons Created

Created on 2026-05-24 15:50:19 CST with run marker
`plato-base-components-2026-05-24-batched`.

| Component | Node ID | Verified variants | Status |
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

Each component has a visible `Note / Base/...` documentation frame next to the
component set covering source spec, states covered, states deferred, expected
code path, and readiness status. This is a governed skeleton layer only and is
not frontend implementation.

Spec-status sync:

- `Base/ErrorState` note/metadata was synced on 2026-05-24 with readiness
  status `formalized skeleton`.
- `Base/Drawer` note/metadata was synced on 2026-05-24 with readiness status
  `explicitly deferred`.
- Component node IDs and variant counts were preserved.

Mapping document:

- `docs/design/figma-component-mapping.md`

Naming decisions:

- `Base/TextArea` is the canonical Figma spelling. `Base/Textarea` is treated
  as a search alias only.
- `Base/Skeleton` is the canonical Figma component for the requested
  `LoadingSkeleton` concept.

## 7. Layout Component Skeletons Created

Created on 2026-05-24 16:31:16 CST with run marker
`plato-layout-components-2026-05-24-batched`.

| Component | Node ID | Verified variants | Status |
|---|---|---:|---|
| `Layout/AppShell` | `45:24` | 2 | skeleton |
| `Layout/TopBar` | `45:52` | 3 | skeleton |
| `Layout/SideNav` | `46:43` | 5 | skeleton |
| `Layout/MainWorkArea` | `46:76` | 5 | skeleton |
| `Layout/DetailPanel` | `48:72` | 6 | skeleton |
| `Layout/ContextInputBar` | `48:134` | 7 | skeleton |

Each component has a visible `Note / Layout/...` documentation frame next to
the component set covering source docs, states covered, states deferred,
expected code path, base components reused, and readiness status. This is a
governed skeleton layer only and is not frontend implementation.

Base components reused:

- `Base/Button`
- `Base/Badge`
- `Base/Input`
- `Base/TextArea`
- `Base/Panel`
- `Base/Skeleton`
- `Base/EmptyState`

Alias decisions:

- `Layout/SideNav` is the user-facing Figma name for the spec concept
  `Layout/WorkflowSidebar`.
- `Layout/MainWorkArea` is the user-facing Figma name for the spec concept
  `Layout/WorkbenchGrid`.
- `Layout/ContextInputBar` is the user-facing Figma name for the spec concept
  `Layout/BottomInputDock`.

Status note:

- `Base/ErrorState` is formalized in docs and its Figma note/metadata has been
  synced. Existing layout skeletons were not changed by this base component
  status sync.

## 8. Domain Component Skeletons Created

Created on 2026-05-24 17:10:01 CST with run marker
`plato-domain-components-2026-05-24-batched`.

| Component | Node ID | Verified variants | Status |
|---|---|---:|---|
| `Domain/TaskTree` | `58:55` | 7 | skeleton |
| `Domain/TaskNode` | `58:203` | 12 | skeleton |
| `Domain/MessageStream` | `59:113` | 6 | skeleton |
| `Domain/MessageCard` | `59:201` | 12 | skeleton |
| `Domain/ConfirmationPanel` | `60:333` | 11 | skeleton |
| `Domain/FileChangeTable` | `61:316` | 9 | skeleton |
| `Domain/AuditEntryCard` | `61:409` | 9 | skeleton |

Each component has a visible `Note / Domain/...` documentation frame next to
the component set covering source docs, states covered, states deferred,
canonical backend/frontend state mapping, expected code path, reused base
components, and readiness status. This is a governed skeleton layer only and
is not frontend implementation.

Base components reused:

- `Base/Button`
- `Base/Badge`
- `Base/Card`
- `Base/Panel`
- `Base/EmptyState`
- `Base/ErrorState`
- `Base/Skeleton`

Not used:

- `Base/Drawer`, because it is explicitly deferred.

Alias decisions:

- `Domain/TaskNode` maps to the spec concept `Domain/TaskNodeCard`.
- `Domain/MessageStream` maps to the message stream composition around
  `Domain/SessionMessageRow`.
- `Domain/MessageCard` maps to the spec concept `Domain/SessionMessageRow`.
- `Domain/ConfirmationPanel` maps to the spec concept
  `Domain/ConfirmationCard`.
- `Domain/FileChangeTable` maps to `Domain/FileChangeSummary` plus audit
  file-change evidence rows.
- `Domain/AuditEntryCard` maps to `Domain/AuditRecordCard` or
  `Domain/AuditSummaryLink` depending usage context.

## 9. Main UX Flow And Screen States Created

Created on 2026-05-24 17:41:55 CST with run marker
`plato-main-screen-states-2026-05-24-batched`.

Main UX flow map:

| Page | Frame | Node ID | Status |
|---|---|---|---|
| `06 - Main UX Flow` | `Main UX Flow Map / Governed States` | `69:2` | created and verified; transition map only, no prototype interactions |

Main screen state frames:

| State | Frame | Node ID | Canonical mapping note |
|---|---|---|---|
| `S1` | `S1 - Empty New Session` | `71:2` | `prototype-state-map S1 Empty` |
| `S2` | `S2 - Understanding / Planning` | `71:110` | `prototype-state-map S2 Understanding` |
| `S3` | `S3 - Draft Task Tree Ready` | `71:217` | user-requested label mapped to `prototype-state-map S4 Draft Ready` |
| `S4` | `S4 - Task Node Selected` | `73:216` | user-requested label mapped to `prototype-state-map S5 Task Selected` |
| `S5` | `S5 - Task Node Editing` | `73:334` | user-requested label mapped to `prototype-state-map S6 Task Editing` |
| `S6` | `S6 - Published / Running` | `73:450` | user-requested combined state mapped to `prototype-state-map S7 Published/Pending` plus `S8 Running` |
| `S7` | `S7 - Waiting For Confirmation` | `75:432` | user-requested label mapped to `prototype-state-map S9 Waiting Confirmation` |
| `S8` | `S8 - Completed With Result` | `75:563` | user-requested label mapped to `prototype-state-map S10 Completed` |
| `S9` | `S9 - File Change Summary / Audit Entry` | `75:686` | focused Main Page entry state for `completed-with-result-file-audit` |
| `S10` | `S10 - Permission Denied` | `77:659` | explicit permission/action availability state |
| `S11` | `S11 - Stale Snapshot / Resync Required` | `77:775` | user-requested label mapped to `prototype-state-map S12 Stale/Resync` |
| `S12` | `S12 - Backend Busy / Command Accepted But Delayed` | `77:883` | command accepted / `pending_command` overlay state |
| `S13` | `S13 - Command Failed / Recoverable Error` | `77:986` | recoverable command failure; related to but narrower than load-error handling |

Verification notes:

- all 13 state frames include visible metadata for trigger, state dimensions,
  required data, visible components, actions, disabled states, exit condition,
  behavior, source docs, and readiness status;
- frames use existing Base/Layout/Domain component instances;
- frame dimensions were stabilized to 1440x1080 with non-overlapping vertical
  placement;
- no Audit Page states, prototype interactions, frontend code, or old-file
  migration were created.

## 10. Audit UX Flow And Screen States Created

Created on 2026-05-24 19:17:53 CST with run marker
`plato-audit-screen-states-2026-05-24-batched`.

Audit UX flow map:

| Page | Frame | Node ID | Status |
|---|---|---|---|
| `08 - Audit UX Flow` | `Audit UX Flow Map / Governed States` | `89:2` | created and verified; transition map only, no prototype interactions |

Audit screen state frames:

| State | Frame | Node ID | Canonical mapping note |
|---|---|---|---|
| `A1` | `A1 - Audit Empty` | `91:2` | `audit-page-contract pageState.empty` plus `prototype-state-map A5 Empty Audit` |
| `A2` | `A2 - Audit Loading` | `91:93` | `audit-page-contract pageState.loading` |
| `A3` | `A3 - Audit Records Ready` | `91:165` | `audit-page-contract pageState.ready` with records list |
| `A4` | `A4 - Audit Record Selected` | `93:149` | selected `AuditRecordDetail` state, related to `prototype-state-map A2 Record Selected` |
| `A5` | `A5 - Partial Evidence` | `93:248` | `audit-page-contract pageState.partial` and `AuditRecord.flags.partial` |
| `A6` | `A6 - Hidden Evidence / Permission Limited` | `93:344` | `audit-page-contract pageState.hidden_evidence` and hidden/redacted `EvidenceRef` |
| `A7` | `A7 - Warning Verdict` | `95:313` | `AuditVerdict.warning` |
| `A8` | `A8 - Failed Verdict` | `95:410` | `AuditVerdict.failed` |
| `A9` | `A9 - Inconclusive Verdict` | `95:507` | `AuditVerdict.inconclusive`, related to `prototype-state-map A8 Inconclusive` |
| `A10` | `A10 - Not Available Verdict` | `95:601` | `AuditVerdict.not_available` |
| `A11` | `A11 - Permission Denied` | `98:527` | `audit-page-contract pageState.permission_denied` and `canViewAudit=false` |
| `A12` | `A12 - Stale Snapshot / Records Changed` | `98:613` | `audit.snapshot_stale`, `audit.records_changed`, and `pageState.stale` |
| `A13` | `A13 - Audit Query Error` | `98:977` | `AuditPageSnapshot` query failure and `pageState.error` |
| `A14` | `A14 - Evidence Load Error` | `98:1040` | `EvidenceDetail` query failure while the snapshot remains ready |

Verification notes:

- all 14 state frames include visible metadata for trigger, entry context,
  audit scope, audit verdict, permission/action availability, evidence
  visibility, snapshot freshness, query/loading/error state, required data,
  visible components, actions, disabled states, exit condition, behavior,
  source docs, and readiness status;
- frames use existing Base/Layout/Domain component instances;
- `Base/Drawer` was not used;
- frame dimensions are 1440x1120 with non-overlapping vertical placement;
- structural verification passed with no missing frames, no missing run marker,
  no missing metadata, and no overlap;
- screenshot verification passed for `A3 - Audit Records Ready` at rendered
  size 1600x892;
- no prototype interactions, frontend code, old-file migration, or dev handoff
  annotations were created.

## 11. Known Blockers

| Blocker | Impact | Required action |
|---|---|---|
| `Base/Drawer` is deferred | Drawer behavior is not needed for Domain Components or Main/Audit Screen States. | Formalize only if drawer-based mobile detail, side-sheet navigation, or transient inspector behavior is approved. |
| Frontend architecture not finalized | Dev Handoff is a P5 architecture input, not implementation completion. | Create the frontend architecture plan before UI code. |
| Audit API/runtime routes not implemented | Audit Page UI cannot safely bind to real backend data yet. | Implement audit routes/gateway or a governed mock/API boundary in P6/P8. |

## 12. Prototype Flows Created

Created on 2026-05-24 23:00:30 CST with run marker
`plato-prototype-flows-2026-05-24-batched`.

Prototype flow page:

| Page | Frame | Node ID | Status |
|---|---|---|---|
| `10 - Prototype Flows` | `Prototype Flows / Governed Interaction References` | `124:2` | created and verified; title and governance notes |

Flow references:

| Flow | Frame | Node ID | Coverage |
|---|---|---|---|
| `Flow 1` | `Flow 1 - Main happy path` | `124:6` | S1 -> S9 main happy path |
| `Flow 2` | `Flow 2 - Main recovery / negative path` | `124:71` | S10 -> S13 main recovery states |
| `Flow 3` | `Flow 3 - Main to Audit entry` | `128:2` | S8/S9/S4/S7 to Audit route entry with return context |
| `Flow 4` | `Flow 4 - Audit happy path` | `128:69` | A1 -> A4 audit loading, records ready, selected record |
| `Flow 5` | `Flow 5 - Audit evidence / verdict path` | `130:2` | A4 -> A5/A6/A7/A8/A9/A10 evidence and verdict paths |
| `Flow 6` | `Flow 6 - Audit recovery / negative path` | `130:62` | A11/A12/A13/A14 audit recovery states |
| `Flow 7` | `Flow 7 - Return paths` | `130:124` | Audit return targets to originating Main states and previous valid state |

Verification notes:

- all seven flow references include visible metadata for flow ID, flow name,
  entry state, exit state, trigger, user action, backend/API dependency, route
  context, recovery behavior, related source docs, and readiness status;
- route from Main to Audit explicitly preserves return context;
- stale snapshot recovery is separate from generic query/evidence retry;
- permission denied has explicit fallback/return behavior;
- hidden evidence remains visibly permission-limited, not missing data;
- `A3 - Audit Records Ready` covers passed/default audit entries;
- structural verification passed with no missing flows, no missing metadata,
  no missing run marker, and no overlap;
- screenshot verification passed for the prototype flow title frame at rendered
  size 1600x219;
- no frontend code, old-file migration, high-fidelity animation polish, or dev
  handoff annotations were created.

## 13. Dev Handoff Mapping Created

Created on 2026-05-24 23:31:00 CST with run marker
`plato-dev-handoff-2026-05-24-batched`.

Dev Handoff page:

| Page | Status |
|---|---|
| `11 - Dev Handoff` | governed handoff mapping created; frontend implementation not complete |

Handoff sections:

| Section | Node ID | Coverage |
|---|---|---|
| `Dev Handoff / Overview` | `136:2` | source docs, canonical file, scope, not-ready scope, usage rules |
| `Dev Handoff / Token-to-Code Mapping` | `136:7` | Figma token name to CSS/theme token candidate mapping |
| `Dev Handoff / Component-to-Code Mapping` | `136:12` | Base, Layout, and Domain component mapping to expected React paths and props |
| `Dev Handoff / Main State Handoff S1-S13` | `138:2` | Main states to routes, ViewModel fields, state dimensions, actions, APIs, recovery |
| `Dev Handoff / Audit State Handoff A1-A14` | `140:2` | Audit states to routes, entry context, audit scope, snapshot/record/evidence fields, verdict, permission, stale behavior |
| `Dev Handoff / Prototype Flow Handoff Flow 1-7` | `142:2` | Flow references to triggers, route changes, API/event dependencies, return contexts, recovery |
| `Dev Handoff / API and ViewModel Gaps` | `142:7` | missing/weak backend routes, audit gateway, frontend types, mocks, reducers, stale/resync handling |
| `Dev Handoff / Frontend Architecture Input Summary` | `142:12` | routes, feature modules, component layers, ViewModel boundaries, mocks, tests |
| `Dev Handoff / Implementation Readiness Checklist` | `142:17` | P5 readiness criteria and non-ready implementation items |
| `Dev Handoff / Not Ready and Blocked` | `142:22` | explicit blockers and downstream guardrails |

Verification notes:

- structural verification passed with no missing Dev Handoff sections;
- all sections have run marker `plato-dev-handoff-2026-05-24-batched`;
- Figma screenshot verification was not run for this handoff task;
- frontend source code was not modified;
- the handoff is ready as P5 frontend architecture input, not as completed
  frontend implementation.

Repo mirror:

- `docs/design/dev-handoff.md`

## 14. Handoff Hygiene Pass Completed

Completed on 2026-05-25 CST with run marker
`plato-handoff-hygiene-2026-05-25`.

Scope:

- inspected `03 - Base Components`, `04 - Layout Components`,
  `05 - Domain Components`, `07 - Main Screen States`,
  `09 - Audit Screen States`, `10 - Prototype Flows`, and
  `11 - Dev Handoff`;
- updated organization/readability on `03 - Base Components`,
  `04 - Layout Components`, and `05 - Domain Components`;
- preserved component node IDs, variant semantics, token bindings, state
  definitions, route/API mappings, and ViewModel handoff mappings;
- added visible hygiene notes clarifying that placeholder labels are not
  production copy.

Added hygiene note nodes:

| Page | Note node ID | Purpose |
|---|---|---|
| `03 - Base Components` | `151:2` | placeholder-copy warning and hygiene run marker |
| `04 - Layout Components` | `149:76` | placeholder-copy warning and hygiene run marker |
| `05 - Domain Components` | `150:279` | placeholder-copy warning and hygiene run marker |

Structural verification:

| Page | Result |
|---|---|
| `03 - Base Components` | passed; maxRight 1416 after reflow |
| `04 - Layout Components` | passed; maxRight 1592 after reflow |
| `05 - Domain Components` | passed; maxRight 1552 after reflow |

Screenshot verification:

| Node | Rendered size | Result |
|---|---:|---|
| `Layout/TopBar` (`45:52`) | 1168x368 | passed |
| `Domain/TaskNode` (`58:203`) | 1184x1040 | passed |
| `Base/Button` (`28:46`) | 828x296 | passed |

No frontend source code was modified. This pass does not mark frontend
implementation complete.

## 15. Next Allowed Figma Task

The next task should move to P5 frontend architecture, not direct UI
implementation. Recommended next step:

- create a frontend architecture plan from `docs/design/dev-handoff.md`;
- optionally add clickable Figma prototype reactions later as a separate
  interaction-wiring task if product review requires click-through behavior.

Do not migrate old Figma content, create production components or variants,
or mark frontend implementation complete until the relevant governance gates are
complete.
