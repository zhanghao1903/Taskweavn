# Plato Dev Handoff Mapping

> Status: governed P4/P5 handoff mapping created
> Last Updated: 2026-05-25
> Canonical Figma file:
> <https://www.figma.com/design/CTK1yALdNEFo2zL8ZcEJIA>

This document mirrors the governed `11 - Dev Handoff` page in the canonical
Figma file. It is an input to P5 frontend architecture. It is not frontend
implementation completion.

P4.11/P4.12 note: `04 - Layout Components` and `05 - Domain Components` have
been upgraded from skeletons to visual baseline aligned drafts with run markers
`plato-layout-visual-upgrade-2026-05-25` and
`plato-domain-visual-upgrade-2026-05-25`. Main screen states have since been
recomposed against the upgraded components; Audit screen states still need the
same visual recomposition before visual implementation.
Final frontend implementation remains incomplete.

P4 acceptance note: on 2026-05-26 CST, `04 - Layout Components` was accepted as
the P4 product-aligned layout reference, and `05 - Domain Components` was
accepted for P4 domain component skeleton and semantic coverage. This acceptance
does not cover final high-fidelity visual polish, production copy, responsive
mobile design, frontend implementation, visual regression baseline, or full dev
handoff readiness.

P4.9 UX flow fidelity note: `06 - Main UX Flow` was upgraded on 2026-05-26 CST
with run marker `plato-main-ux-flow-fidelity-2026-05-26`. The existing state
inventory node `69:2` was preserved, and readable overview node `292:2` was
created for Main happy path, recovery/negative branches, and Main-to-Audit
entry/return context. This is a Figma flow overview, not executable prototype
interaction wiring.

## 1. Source Documents

- `docs/product/canonical-status-model.md`
- `docs/engineering/audit-page-contract.md`
- `docs/ux/screen-state-spec.md`
- `docs/ux/prototype-state-map.md`
- `docs/design/design-system.md`
- `docs/design/component-spec.md`
- `docs/design/component-state-matrix.md`
- `docs/design/figma-component-mapping.md`
- `docs/design/figma-layout-contract.md`
- `docs/frontend/ui-viewmodel-contract.md`
- `docs/frontend/api-ui-mapping.md`
- `docs/frontend/event-reducer-contract.md`

## 1.1 Metadata Ownership

Figma Dev Handoff and Screen State frames are summary and inspection surfaces.
They should show concise mapping summaries, visible state intent, and links to
repo docs. Full route, ViewModel, backend/API, event, permission, stale/resync,
error, and recovery metadata lives in this document and the source contracts
listed above.

Future Figma handoff work must follow
`docs/design/figma-layout-contract.md`: keep frame metadata short, move long
details into docs, and avoid placing component usage proof inside screen
preview zones.

## 2. Figma Handoff Sections

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

Run marker: `plato-dev-handoff-2026-05-24-batched`.

Handoff hygiene note:

- Figma handoff hygiene pass completed on 2026-05-25 CST with run marker
  `plato-handoff-hygiene-2026-05-25`.
- Base, Layout, and Domain component galleries were reflowed for readability;
  component node IDs and semantics were preserved.
- Domain component visual upgrade completed on 2026-05-25 CST with run marker
  `plato-domain-visual-upgrade-2026-05-25`; overlap/bounds follow-up completed
  with `plato-domain-overlap-and-bounds-fix-2026-05-25`.
- Page-level stale note/title overlap on `05 - Domain Components` was fixed
  with `plato-domain-page-overlap-fix-2026-05-25`; all visible top-level page
  siblings must be included in future Figma overlap checks.
- Variant root offset on `05 - Domain Components` was fixed with
  `plato-domain-variant-root-zero-origin-fix-2026-05-25`; visible root
  presentation frames should start at `x=0, y=0`, with padding inside the root
  frame rather than as root offset.
- `Domain/TaskTree` was refined on 2026-05-25 CST with
  `plato-domain-tasktree-visual-refinement-2026-05-25` and follow-up
  `plato-domain-tasktree-height-fix-2026-05-25`; it now uses the S7-style
  product tree pattern with compact card rows, hierarchy rhythm, selected-node
  treatment, and contained loading/empty/error variants.
- Domain component verification passed for effective-visible text overlap,
  clipping, component-set descendant bounds, page-level set/note overlap, and
  representative exports. Use the upgraded Domain component drafts as visual
  inputs for future screen-state recomposition, not as completed frontend code.
- Placeholder labels such as `Primary`, `Neutral`, `Card title`, and repeated
  skeleton text are non-production labels used only to describe component
  variants. Engineers should use props, ViewModels, and backend mappings from
  this document instead of copying placeholder text into runtime UI.

Screen-state handoff hygiene note:

- Screen-state readability pass completed on 2026-05-25 CST with run marker
  `plato-screen-state-handoff-hygiene-2026-05-25`.
- S1-S13 and A1-A14 state frame node IDs were preserved.
- Main state frames were normalized for screenshot readability; S10 now
  separates screen composition, state metadata, component usage, and
  implementation notes.
- Audit states A1-A14 now use visible handoff metadata panels. Hidden legacy
  metadata overlay nodes remain only for traceability and are not the handoff
  source.
- Permission/error states must be read from the visible handoff panels and this
  document: permission denied, stale snapshot, query error, evidence error,
  hidden evidence, and partial evidence remain separate UI states.
- Screenshot verification passed for S10, A11, S1, and A4. A3 screenshot
  transport failed twice, but A3 structural verification passed.
- Screen-state layout normalization completed on 2026-05-25 CST with run
  marker `plato-screen-state-layout-normalization-2026-05-25`.
- S1-S13 were normalized to the governed `ScreenStateTemplate` zone model:
  header, screen composition preview, metadata summary, implementation notes,
  and component usage summary.
- A1-A14 were normalized to the governed `AuditStateTemplate` zone model with
  the same five handoff zones and Audit-specific metadata summaries.
- All S1-S13 and A1-A14 state frame node IDs were preserved. Generated P4.7
  child layout zones are the current visible Figma handoff source.
- Full state, ViewModel, API, and recovery mappings remain in this document;
  Figma state frames intentionally contain short summaries only.
- Normalization verification passed structurally for all S1-S13 and A1-A14,
  including S10, S11, S12, S13, A5, A6, A11, A12, A13, and A14. Screenshot
  verification passed for S10, S8, A11, and A3; S1 had one screenshot transport
  failure via `backend-api/wham/apps`.
- Screen-state semantic fidelity pass applied on 2026-05-25 CST with run marker
  `plato-screen-state-semantic-fidelity-2026-05-25`.
- The pass restored low/mid-fidelity state-specific preview content while
  preserving the normalized zone layout and state frame IDs.
- Main previews now distinguish empty input, planning/loading, draft task tree,
  selected task, editing, running, confirmation, completed result, file/audit
  entry, permission denied, stale/resync, backend busy, and recoverable error
  states.
- Audit previews now distinguish empty, loading, records ready, selected
  record, partial evidence, hidden evidence, warning, failed, inconclusive, not
  available, permission denied, stale records, query error, and evidence load
  error states.
- S7 had one detected title/risk-badge overlap after semantic content was
  restored; it was fixed in place while preserving frame `75:432`.
- Post-write automated read verification and screenshots became blocked by
  Figma MCP 120s timeouts. Treat the semantic pass as applied but not fully
  visually verified until a verification-only follow-up succeeds.

Layout template note:

- Layout templates were created on 2026-05-25 CST with run marker
  `plato-layout-templates-2026-05-25`.
- Template nodes: `ScreenStateTemplate` (`188:5`), `AuditStateTemplate`
  (`188:56`), `DevHandoffSectionTemplate` (`188:107`),
  `MetadataSummaryCard` (`188:132`), `ImplementationNotesCard` (`188:141`),
  and `ComponentUsageSummaryCard` (`188:145`).
- These templates are reusable layout references, not production components and
  not new product states.
- Future Figma screen-state or handoff work should keep full metadata in this
  document and use the templates for readable Figma summaries.
- Text hygiene pass `plato-layout-template-text-hygiene-2026-05-25` fixed
  collapsed text heights in these templates while preserving template node IDs.
- Visible P4.10 screen composition size normalization
  `plato-visible-p410-preview-1440x1024-2026-05-26` updated the visible
  `07 - Main Screen States` S1-S13 `P4.10 / Screen composition preview` zones
  to a fixed `1440x1024`. S1-S13 state frame IDs were preserved; the outer Main
  state frames were widened to keep metadata outside the screen composition
  zone. The reusable template is `Template / P4.10 Screen composition preview`
  (`341:2`) inside `11 - Dev Handoff / Layout Templates`.

## 3. Token-To-Code Mapping

| Figma token | Code token candidate | Usage |
|---|---|---|
| `color/primitive/reason-blue` | `--plato-color-reason-blue` | primary reasoning/action blue |
| `color/primitive/cave-blue` | `--plato-color-cave-blue` | deep text/accent base |
| `color/primitive/clear-blue` | `--plato-color-clear-blue` | light selected/interactive surface |
| `color/primitive/wisdom-gold` | `--plato-color-wisdom-gold` | caution/risk/accent |
| `color/primitive/classic-cream` | `--plato-color-classic-cream` | warm muted surface |
| `color/primitive/marble` | `--plato-color-marble` | page neutral |
| `color/primitive/ink` | `--plato-color-ink` | primary text |
| `color/primitive/muted` | `--plato-color-muted` | secondary text |
| `color/primitive/line` | `--plato-color-line` | borders/dividers |
| `color/primitive/panel` | `--plato-color-panel` | panel surface |
| `color/semantic/page-bg` | `--plato-bg-page` | app background |
| `color/semantic/surface` | `--plato-surface` | panel/card surface |
| `color/semantic/surface-muted` | `--plato-surface-muted` | subtle info/loading surfaces |
| `color/semantic/text-primary` | `--plato-text-primary` | body and headings |
| `color/semantic/text-secondary` | `--plato-text-secondary` | metadata and helper text |
| `color/semantic/border` | `--plato-border` | component outlines |
| `color/semantic/focus-ring` | `--plato-focus-ring` | focus-visible ring |
| `color/semantic/action-primary` | `--plato-action-primary` | primary action controls |
| `color/status/success` | `--plato-status-success` | completion/pass |
| `color/status/warning` | `--plato-status-warning` | warning/partial |
| `color/status/danger` | `--plato-status-danger` | failed/error |
| `color/status/info` | `--plato-status-info` | neutral information |
| `color/audit/passed` | `--plato-audit-passed` | audit verdict `passed` |
| `color/audit/warning` | `--plato-audit-warning` | audit verdict `warning` |
| `color/audit/failed` | `--plato-audit-failed` | audit verdict `failed` |
| `color/audit/inconclusive` | `--plato-audit-inconclusive` | audit verdict `inconclusive` |
| `color/audit/not-available` | `--plato-audit-not-available` | audit verdict `not_available` |
| `typography/family/sans` | `--plato-font-sans` | UI text |
| `typography/family/serif` | `--plato-font-serif` | brand/editorial only if approved |
| `type/eyebrow` | `.plato-type-eyebrow` | section label |
| `type/heading` | `.plato-type-heading` | page/panel headings |
| `type/subheading` | `.plato-type-subheading` | card headings |
| `type/body` | `.plato-type-body` | normal content |
| `type/muted` | `.plato-type-muted` | secondary metadata |
| `type/label` | `.plato-type-label` | control labels and badges |
| `space/1..10` | `--plato-space-1..10` | spacing scale |
| `radius/sm`, `radius/md`, `radius/lg` | `--plato-radius-sm/md/lg` | component radius |
| `shadow/panel` | `--plato-shadow-panel` | raised panels |
| `shadow/focus` | `--plato-shadow-focus` | focus treatment |
| `motion/duration/fast/base/slow` | `--plato-motion-fast/base/slow` | transitions |
| `motion/easing/standard` | `--plato-ease-standard` | default easing |
| `breakpoint/mobile/tablet/desktop/wide` | `--plato-bp-mobile/tablet/desktop/wide` | responsive thresholds |

Do not introduce page-local colors, spacing, radius, shadows, motion, or status
colors when a mapped token exists.

## 4. Component-To-Code Mapping

Component paths are P5 architecture targets. If current frontend paths differ,
P5 should reconcile paths without changing Figma semantics.

| Figma component | Node ID | Expected React path | Main props/axes | Status |
|---|---|---|---|---|
| `Base/Button` | `28:46` | `src/components/ui/Button.tsx` | `variant`, `disabled`, `loading`, `children` | skeleton |
| `Base/Badge` | `28:84` | `src/components/ui/Badge.tsx` | `tone`, `size`, `children` | skeleton |
| `Base/Input` | `30:14` | `src/components/ui/Input.tsx` | `value`, `placeholder`, `disabled`, `error` | skeleton |
| `Base/TextArea` | `30:35` | `src/components/ui/TextArea.tsx` | `value`, `placeholder`, `disabled`, `error`, `minRows` | skeleton |
| `Base/Card` | `30:79` | `src/components/ui/Card.tsx` | `variant`, `selected`, `interactive`, `children` | skeleton |
| `Base/Panel` | `30:157` | `src/components/ui/Panel.tsx` | `variant`, `padding`, `state`, `children` | skeleton |
| `Base/Dialog` | `32:20` | `src/components/ui/Dialog.tsx` | `open`, `title`, `description`, `actions` | skeleton |
| `Base/Drawer` | `32:37` | `src/components/ui/Drawer.tsx` | deferred | explicitly deferred |
| `Base/Toast` | `32:81` | `src/components/ui/Toast.tsx` | `tone`, `title`, `message`, `action` | skeleton |
| `Base/Tooltip` | `32:93` | `src/components/ui/Tooltip.tsx` | `content`, `children`, `placement` | skeleton |
| `Base/EmptyState` | `34:11` | `src/components/ui/EmptyState.tsx` | `title`, `message`, `action` | skeleton |
| `Base/ErrorState` | `34:25` | `src/components/ui/ErrorState.tsx` | `kind`, `severity`, `retryAction`, `details` | formalized skeleton |
| `Base/Skeleton` | `34:50` | `src/components/ui/Skeleton.tsx` | `shape`, `size` | skeleton |
| `Layout/AppShell` | `45:24` | `src/components/layout/AppShell.tsx` | `route`, `pageState`, slots, `stale`, `error` | visual baseline aligned draft |
| `Layout/TopBar` | `45:52` | `src/components/layout/TopBar.tsx` | `project`, `workflow`, `session`, `actions`, `readonly`, `stale` | visual baseline aligned draft |
| `Layout/SideNav` | `46:43` | `src/components/layout/SideNav.tsx` | `items`, `selectedId`, `collapsed`, `loading`, `onSelect` | visual baseline aligned draft |
| `Layout/MainWorkArea` | `46:76` | `src/components/layout/MainWorkArea.tsx` | `mode`, `pageState`, slots, `emptyState`, `error`, `stale` | visual baseline aligned draft |
| `Layout/DetailPanel` | `48:72` | `src/components/layout/DetailPanel.tsx` | `selectedEntity`, `detailKind`, `pageState`, `permission`, `stale` | visual baseline aligned draft |
| `Layout/ContextInputBar` | `48:134` | `src/components/layout/ContextInputBar.tsx` | `inputMode`, `value`, `actions`, `disabled`, `submitting`, `onSubmit` | visual baseline aligned draft |
| `Domain/TaskTree` | `58:55` | `src/features/task-tree/components/TaskTree.tsx` | `TaskTreeView`, selection, permissions | visual baseline aligned draft |
| `Domain/TaskNode` | `58:203` | `src/features/task-tree/components/TaskNode.tsx` | readiness, execution, confirmation, permission | visual baseline aligned draft |
| `Domain/MessageStream` | `59:113` | `src/features/session/components/MessageStream.tsx` | messages, stream state, partial/hidden evidence | visual baseline aligned draft |
| `Domain/MessageCard` | `59:201` | `src/features/session/components/MessageCard.tsx` | `type`, `display`, content slots | visual baseline aligned draft |
| `Domain/ConfirmationPanel` | `60:333` | `src/features/confirmation/components/ConfirmationPanel.tsx` | `risk`, lifecycle, permissions | visual baseline aligned draft |
| `Domain/FileChangeTable` | `61:316` | `src/features/audit/components/FileChangeTable.tsx` | file changes, evidence visibility, permissions | visual baseline aligned draft |
| `Domain/AuditEntryCard` | `61:409` | `src/features/audit/components/AuditEntryCard.tsx` | verdict, display, evidence/permission/stale flags | visual baseline aligned draft |

## 5. Main State Handoff

Route model:

- `main.session`
- `main.sessionFallback`
- Audit entry from Main is represented in `S8`, `S9`, and `Flow 3`.

| State | Frame node | Route | Required ViewModel fields | State dimensions | Primary action / dependency | Recovery |
|---|---|---|---|---|---|---|
| `S1` Empty New Session | `71:2` | `main.sessionFallback` or `main.session` | project, workflows, permissions, input, pageState | planning `not_started`, readiness `not_created`, execution `idle`, confirmation `none`, permission available | submit goal command | command failure -> `S13` |
| `S2` Understanding / Planning | `71:110` | `main.session` | session, planning, messages, input | planning `understanding/planning`, readiness unavailable, execution planning | accepted goal, planning progress event | delayed -> `S12`; error -> `S13` |
| `S3` Draft Task Tree Ready | `71:217` | `main.session` | taskTree.nodes, planning, permissions | planning `draft_ready`, readiness `draft_ready`, execution idle | publish/continue/edit task | stale -> `S11`; failure -> `S13` |
| `S4` Task Node Selected | `73:216` | `main.session` | selectedTask, taskTree, detail data, auditLinks | readiness ready/suggested, execution idle/running, confirmation none/pending | edit/run/view audit | denied -> `S10` |
| `S5` Task Node Editing | `73:334` | `main.session` | selectedTask, input mode, permissions | readiness ready/suggested, execution idle, permission available | save/cancel edit | validation/failure -> `S13` |
| `S6` Published / Running | `73:450` | `main.session` | planning, taskTree, execution rollup, messages | planning published, execution queued/running, permissions limited for unsafe actions | event stream / job progress | delayed -> `S12`; failure -> `S13` |
| `S7` Waiting For Confirmation | `75:432` | `main.session` | pendingConfirmations, selectedTask, permissions | execution blocked, confirmation pending, permission available | confirm/reject/skip command | stale/conflict -> `S11` or panel conflict |
| `S8` Completed With Result | `75:563` | `main.session` | result, messages, auditSummary, auditLinks | execution completed, confirmation resolved, audit verdict summary | open audit / new task | audit route preserves return target |
| `S9` File Change Summary / Audit Entry | `75:686` | `main.session` | fileChangeSummary, auditSummary, auditLinks | execution completed, audit verdict summary, permission available/limited | open file/result-scoped audit | return target from file/result |
| `S10` Permission Denied | `77:659` | `main.session` | permissions, disabledReason, selected context | permission denied/hidden | return/back or safer alternative if supported | no retry unless permissions change |
| `S11` Stale Snapshot / Resync Required | `77:775` | `main.session` | cursor, generatedAt, staleReason | snapshot freshness stale | refetch snapshot | success returns previous valid state; failure -> `S13` |
| `S12` Backend Busy / Command Accepted But Delayed | `77:883` | `main.session` | pendingCommand, cursor, optimistic metadata | command accepted, async pending | wait for event or poll | timeout -> `S13` |
| `S13` Command Failed / Recoverable Error | `77:986` | `main.session` | command error, previous snapshot, recovery action | command error, permission unchanged | retry/cancel | return to previous valid state |

## 6. Audit State Handoff

Route model:

- `audit.session`
- `audit.task`

Entry context must preserve return target from session, task, confirmation,
result, or file change. Audit verdict, evidence visibility, permission,
snapshot freshness, and query state are separate dimensions.

| State | Frame node | Route | Required fields | Audit dimensions | Primary action / dependency | Recovery |
|---|---|---|---|---|---|---|
| `A1` Audit Empty | `91:2` | `audit.session` or `audit.task` | overview, filters, records=[] | verdict `not_available`, evidence none, query success-empty | refresh/return | no detail request |
| `A2` Audit Loading | `91:93` | `audit.session` or `audit.task` | request, scope, returnTarget pending | query loading, freshness unknown | get snapshot/list records | success -> `A3`/`A1`; error -> `A13` |
| `A3` Audit Records Ready | `91:165` | `audit.session` or `audit.task` | records, overview, filters, permissions | verdict mix, evidence visible/partial by record | select record | get detail -> `A4` |
| `A4` Audit Record Selected | `93:149` | `audit.session` or `audit.task` | selectedRecord, evidenceRefs, detail summary | selected verdict, permission available, fresh snapshot | load evidence/open logs/return | evidence error -> `A14` |
| `A5` Partial Evidence | `93:248` | `audit.session` or `audit.task` | evidenceRefs with partial flags, partial count | evidence partial; verdict may be passed/warning/inconclusive | load remaining evidence or acknowledge | do not render as pure success |
| `A6` Hidden Evidence / Permission Limited | `93:344` | `audit.session` or `audit.task` | hidden evidenceRefs, permissions, hiddenReason | permission limited, evidence hidden | return/request permission if supported | do not treat as missing data |
| `A7` Warning Verdict | `95:313` | `audit.session` or `audit.task` | selectedRecord.verdict=warning | verdict warning | inspect evidence/logs | combine with `A6` if hidden |
| `A8` Failed Verdict | `95:410` | `audit.session` or `audit.task` | verdict failed, reason, evidenceRefs | verdict failed | inspect evidence/return | recovery depends on origin |
| `A9` Inconclusive Verdict | `95:507` | `audit.session` or `audit.task` | verdict inconclusive, uncertainty reason | evidence partial/unknown | refresh or inspect missing evidence | records changed -> `A12` |
| `A10` Not Available Verdict | `95:601` | `audit.session` or `audit.task` | verdict not_available, availability reason | evidence none | return/open related logs if allowed | not an error unless query failed |
| `A11` Permission Denied | `98:527` | `audit.session` or `audit.task` | AuditPermissions denied, denialReason, returnTarget | permission denied | return to origin | no evidence/detail fetch |
| `A12` Stale Snapshot / Records Changed | `98:613` | `audit.session` or `audit.task` | cursor, generatedAt, staleReason, audit events | freshness stale, records changed | refresh snapshot | success -> `A3`/`A4`; failure -> `A13` |
| `A13` Audit Query Error | `98:977` | `audit.session` or `audit.task` | query error, previous snapshot if available | query error | retry snapshot/list records | preserve returnTarget |
| `A14` Evidence Load Error | `98:1040` | `audit.session` or `audit.task` | EvidenceDetail error, selectedRecord intact | evidence detail error, snapshot fresh | retry evidence | do not collapse page into `A13` |

## 7. Prototype Flow Handoff

The canonical `06 - Main UX Flow` page now includes a readable overview
(`292:2`) in addition to the preserved state inventory (`69:2`). It summarizes
the Main happy path, recovery branches, and Audit entry/return context with
short transition labels. The detailed route/API/ViewModel semantics remain in
the tables below.

The canonical `07 - Main Screen States` page was recomposed on 2026-05-26 with
run marker `plato-main-screen-state-recomposition-2026-05-26`. S1-S13 preserve
their frame node IDs and definitions, but their preview zones now use the
accepted `04 - Layout Components`, accepted `05 - Domain Components`, and the
upgraded `06 - Main UX Flow` overview. This is a P4 product-aligned handoff
reference only; it is not a final visual regression baseline and does not mean
frontend implementation is complete.

| Flow | Node ID | Entry | Exit | Trigger / dependency | Recovery |
|---|---|---|---|---|---|
| `Flow 1` Main happy path | `124:6` | `S1` | `S9` | goal, planning, edit, publish, run, confirmation, completion | branch to `Flow 2` on stale/load/permission/command issue |
| `Flow 2` Main recovery / negative path | `124:71` | `S10`/`S11`/`S12`/`S13` | previous valid Main state | permission block, stale cursor, busy backend, command error | fallback/return, resync, wait/poll, retry/cancel |
| `Flow 3` Main to Audit entry | `128:2` | `S8`/`S9`/`S4`/`S7` | `A2`/`A3`/`A4` | audit route with entryContext and returnTarget | denied -> `A11`; query failure -> `A13` |
| `Flow 4` Audit happy path | `128:69` | `A1`/`A2` | `A4` | load records and select record | empty -> `A1`; query error -> `A13` |
| `Flow 5` Audit evidence / verdict path | `130:2` | `A4` | `A5`/`A6`/`A7`/`A8`/`A9`/`A10` | get evidence/detail, permission check | evidence error -> `A14`; stale -> `A12` |
| `Flow 6` Audit recovery / negative path | `130:62` | `A11`/`A12`/`A13`/`A14` | previous valid audit state or return target | permission, stale, query error, evidence error | return, resync, retry snapshot, retry evidence |
| `Flow 7` Return paths | `130:124` | Audit states | originating Main context | returnTarget route context | stale refresh first; denied falls back to last valid session route |

## 8. API And ViewModel Gaps

- HTTP audit routes are still candidates, not implemented runtime endpoints:
  list audit records, get audit snapshot, get record detail, get evidence.
- Audit query gateway and real data aggregation are not implemented.
- Audit event candidates exist in contract, but runtime emission/wiring still
  needs implementation: `audit.records_changed`, `audit.record_updated`,
  `audit.evidence_hidden`, `audit.snapshot_stale`.
- AuditPageSnapshot TypeScript types, route constants, API client methods, and
  mock fixtures need P5/P6 work.
- Current frontend/backend transport may still have flattened session/task
  statuses. P5 must introduce separated selectors for planning, task
  readiness, execution, confirmation, permission/action availability, and audit
  verdict.
- Permission/action availability needs typed actions, disabled reasons, and
  hidden reasons instead of visual inference.
- Stale snapshot/resync behavior needs cursor-aware reducer handling.
- Unsupported event handling should be explicit: ignore unknown events, record
  diagnostics, and resync when cursor mismatch or stale marker appears.
- Responsive behavior exists as component notes and state metadata, but full
  mobile/tablet screen states are not exhaustive.

Do not solve these gaps inside UI components. Resolve them through frontend
architecture, API contracts, mock fixtures, and reducer contracts.

## 9. Frontend Architecture Input Summary

Routes needed:

- `main.session`
- `main.sessionFallback`
- `audit.session`
- `audit.task`
- return targets from Audit to session, task, confirmation, result, or file
  change context.

Feature modules needed:

- `src/components/ui`
- `src/components/layout`
- `src/features/task-tree`
- `src/features/session`
- `src/features/confirmation`
- `src/features/audit`
- `src/api` or `src/features/api`
- event reducer and stale/resync handling module

ViewModel boundaries:

- `MainPageSnapshot` and `AuditPageSnapshot` should be route-level boundaries.
- UI components should receive typed props, not raw API payloads.
- Selectors map canonical backend/domain statuses to UI labels and tokens.
- Action availability is data-driven and includes disabled/hidden reasons.

Mock scenarios needed:

- Main `S1`-`S13`.
- Audit `A1`-`A14`.
- Flow fixtures for Main happy path, recovery, Audit entry, Audit
  evidence/verdict, Audit recovery, and return paths.
- Event reducer fixtures for unsupported events, stale cursor, audit records
  changed, hidden evidence, and evidence load failure.

Tests needed:

- type/contract tests for ViewModels and API mapping;
- reducer tests for known events, unsupported event handling, stale snapshot,
  and resync;
- component tests for base/layout/domain variants;
- route tests for Main to Audit return context;
- visual regression candidates for `S1`-`S13`, `A1`-`A14`, and `Flow 1`-`7`.

## 10. Implementation Readiness Checklist

Ready for P5 architecture input:

- canonical Figma file exists;
- tokens are created and documented;
- Base components are created as governed skeletons; Layout and Domain
  components are visual baseline aligned drafts;
- `04 - Layout Components` and `05 - Domain Components` are accepted for their
  P4 reference/skeleton scopes;
- Main states `S1`-`S13` and Audit states `A1`-`A14` are created;
- Prototype Flows `1`-`7` are created as references;
- Dev Handoff mapping sections are created on `11 - Dev Handoff`.

Not ready for direct implementation without P5 architecture:

- frontend route/module architecture is not finalized;
- frontend ViewModel TypeScript surfaces are not reconciled with existing code;
- mock fixtures for all states are not implemented;
- Audit API endpoints are not implemented;
- event reducer behavior is documented but not fully wired in runtime;
- responsive visual QA and screenshot regression baselines are not complete.

Minimum P5 acceptance criteria:

- route model defined in code;
- MainPageSnapshot and AuditPageSnapshot TypeScript types added or aligned;
- API/mock boundary defined before UI implementation;
- reducer behavior defined for known/unknown events and stale/resync;
- component layer paths reconciled with existing repo conventions;
- no page-specific hardcoded visual values when tokens exist;
- no flattened generic status replacing canonical status dimensions.

## 11. Not Ready And Blocked

- Figma is not frontend implemented.
- Frontend architecture is not finalized.
- Frontend source code was not changed by this task.
- Prototype flows are not executable UI interactions.
- Dev Handoff mapping is a bridge into P5, not proof of runtime behavior.
- Component-gallery placeholder labels are not approved production copy.
- Hidden legacy metadata overlay nodes in Audit state frames are not the
  engineering handoff source; use the visible handoff metadata panels.

Known blockers:

- Audit HTTP routes and real audit aggregation are pending.
- Audit frontend API client/types/mocks are pending.
- Flattened status migration still needs code planning.
- Responsive state coverage is not exhaustive.
- Visual screenshot verification should be run as a separate QA step if design
  fidelity matters.

Guardrails for next work:

- Do not implement Audit Page UI until P5 frontend architecture and P6 API/mock
  boundary are accepted.
- Do not invent missing backend fields inside UI code.
- Do not migrate old Figma files.
- Do not use `Base/Drawer` unless a new drawer interaction spec is approved.
- Keep audit hidden evidence, permission denied, partial evidence, stale
  snapshot, query error, and evidence error as separate UI states.
