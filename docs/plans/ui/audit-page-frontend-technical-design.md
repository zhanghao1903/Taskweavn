# Audit Page Frontend Technical Design

> Status: implementation baseline through AP-005H
> Last Updated: 2026-05-31
> Scope: Audit Page 前端技术方案。本文把 Audit Page PRD、UX Flow、Figma
> v0.1 静态稿、frontend API/mock baseline 和 backend-to-frontend contract
> 收敛成可执行的 UI 实施设计。
> Static reference: [Plato MVP Main Page UX Draft / Audit Page v0.1](https://www.figma.com/design/wHFPOBaxeImyhJer7BnMaq/Plato-MVP-Main-Page-UX-Draft?node-id=67-2)
> Related:
> [Audit Page Project Implementation Plan](audit-page-project-implementation-plan.md),
> [Audit Page Contract](../../engineering/audit-page-contract.md),
> [Audit Page UX Flow](../../product/plato-audit-page-ux-flow.md),
> [Frontend Technical Design](../../product/plato-frontend-technical-design.md),
> [UI ViewModel Contract](../../frontend/ui-viewmodel-contract.md),
> [API UI Mapping](../../frontend/api-ui-mapping.md)

---

## 1. Purpose

当前 Audit Page plan 只说明了阶段和大方向，不足以指导实现。本文补齐第一版
Audit Page 的前端技术方案，回答：

1. Figma v0.1 静态稿如何映射到 React 页面结构。
2. 页面如何使用已有 `PlatoApi` / mock audit API。
3. 页面组件如何拆分，哪些组件应该共享，哪些暂时属于 Audit Page。
4. 路由、查询、筛选、选中记录、详情、证据、错误和权限状态如何流动。
5. 第一版如何分片实现，避免一次性写出不可验证的大页面。

本文不是后端聚合方案，也不是高保真视觉规范。第一版实现目标是：

```text
mock-backed Audit Page shell
  -> Figma v0.1 layout parity
  -> A1-A14 mock scenario walkthrough
  -> Main Page audit entry can later route into this page
  -> backend audit gateway can later replace mock API
```

---

## 2. Workflow Gate Result

| Item | Result |
|---|---|
| Detected phase | P5 Frontend Architecture + P6 API/Mock Data + P7 Vertical Slice planning |
| Task type | Technical design document |
| Implementation allowed now | Documentation yes; production code no in this task |
| Required upstream artifacts | PRD, UX Flow, Figma static draft, API contract, mock data, frontend architecture |
| Found artifacts | All required artifacts exist as draft/baseline |
| Weak artifacts | Figma v0.1 is an old draft/reference file, not the canonical governed Figma file |
| Execution scope | Write detailed frontend technical design and link it from the plan |
| Main assumption | Figma v0.1 is accepted as the static visual reference for the first implementation slice |

Figma governance classification:

| Item | Result |
|---|---|
| Operation class | `read_reference` |
| Figma write allowed | No write in this task |
| Static source | Old draft file `Plato MVP Main Page UX Draft`, node `67:2` |
| Governance note | Old Figma files remain reference/archive only. Canonical work still belongs in `Plato Product Design System and Prototype`. |
| Connector note | Metadata and screenshot were readable. `get_design_context` failed with a selection-related connector error, so this document relies on metadata, screenshot, repo docs, and existing frontend contracts. |

---

## 3. Current Code Facts

### 3.1 Already Available

| Area | Current file | Status |
|---|---|---|
| Audit route constants | `frontend/src/app/routes.ts` | `auditSession`, `auditTask`, route builders exist |
| Audit API methods | `frontend/src/shared/api/platoApi.ts` | `getAuditSnapshot`, `listAuditRecords`, `getAuditRecordDetail`, `getEvidenceDetail` exist |
| Runtime API selection | `frontend/src/app/platoRuntime.ts` | `createAuditApiFromRuntimeEnv()` can return mock or HTTP audit API |
| Audit API types | `frontend/src/shared/api/types.ts` | `AuditPageSnapshot`, `AuditRecord`, `AuditRecordDetail`, `EvidenceDetail`, state types exist |
| Audit entity model | `frontend/src/entities/audit/model.ts` | Re-export/helper layer exists |
| Mock scenarios | `frontend/src/pages/audit-page/mockAuditScenarios.ts` | A1-A14 scenarios exist |
| Mock API | `frontend/src/pages/audit-page/mockAuditApi.ts` | Mock implementation exists |
| UI boundary mapping | `frontend/src/shared/api/apiUiMapping.ts` | Audit Page state mapping exists |
| Backend contract models | `src/taskweavn/server/ui_contract/*` | Additive models/events exist |

### 3.2 Remaining Gaps

| Area | Missing |
|---|---|
| Real backend routes | No audit HTTP route/gateway/aggregation yet |
| Runtime audit events | Audit event refetch behavior is not wired to a real audit source yet |
| Backend parity | Mock scenarios A1-A14 are the acceptance fixture set, but real backend data is not mapped into them |
| Mobile polish | Desktop and tablet are reviewable; Product-grade sub-960 mobile layout remains deferred |

---

## 4. Figma v0.1 Static Structure

The Figma node `67:2` is named `Audit Page v0.1`. It is a canvas containing
multiple 1440x1024 states, not a single responsive component.

### 4.1 Observed Frames

| Frame | Node | Purpose |
|---|---|---|
| `A1 - Task Audit Default` | `67:3` | Task audit default state: overview + filter rail + full-width evidence timeline |
| `A2 - Task Audit With Selected Record Detail` | `67:130` | Selected record state: overview + filter rail + narrower timeline + right detail/return context |
| `A12 - Detail Reserved Config And Logs` | `67:1329` | Detail state reserving effective configuration and related logs |
| `Audit Page v0.1 Notes` | `67:1484` | Notes/review gate |

### 4.2 Desktop Layout Measurements

The first implementation should use these as target proportions, not exact
absolute CSS pixels.

| Region | Figma position / size | Implementation intent |
|---|---|---|
| Top Bar | `x=0 y=0 w=1440 h=72` | Reuse Plato top bar style; audit page is read-only trust plane |
| Page title row | `x=32 y=94` plus scope/status text | Header context below top bar |
| Overview | `x=32 y=158 w=1376 h=116` | Full-width overview card below header |
| Filter Rail | `x=32 y=300 w=216 h=650` | Left rail on desktop |
| Default Timeline | `x=272 y=300 w=1136 h=650` | Full main evidence list when no detail is open |
| Selected Timeline | `x=272 y=300 w=632 h=650` | Narrow list when detail panel is open |
| Detail Drawer | `x=928 y=300 w=480 h=650` | Right-side record detail panel |
| Return Context Preview | `x=928 y=300 w=480 h=650` | Alternative right panel for return context state |

### 4.3 Visual Objects

The static draft implies these user-facing objects:

| Object | Figma layer names | UI component |
|---|---|---|
| Audit page chrome | `Top Bar`, `Breadcrumb`, `Pill / Read-only`, `Pill / Trust Plane`, `Button / Return to Task` | `AuditPageChrome` / route shell |
| Scope heading | `Page Title`, `Pill / Scope: Task`, `Subject`, `Status`, `Read Only Note` | `AuditHeader` |
| Overview | `Audit Overview`, `Metric / Confirmations`, `Metric / Risks`, `Metric / Files`, `Metric / Results` | `AuditOverviewPanel` |
| Filters | `Filter Rail`, `Filter / All`, `Filter / Confirmations`, etc. | `AuditFilterRail` |
| Timeline | `Evidence Timeline`, `Record / r* / *` | `AuditRecordList` |
| Record card | `Time`, `Pill / kind`, `Summary`, `Refs`, status pill, `Actor Flags` | `AuditRecordCard` |
| Detail | `Record Detail Drawer`, `What Happened`, `Evidence`, `Disclosure`, reserved config/logs | `AuditRecordDetailPanel` |
| Return context | `Return Context Preview`, `Mini Main Page` | Optional `AuditReturnContextPanel` |

---

## 5. Product And UX Invariants

1. Audit Page is a trust plane, not a control plane.
2. The page is read-only. It must not publish, retry, resolve confirmation, edit
   Task, or mutate Session state.
3. Audit scope is explicit: first implementation supports `session` and `task`.
4. Record list remains time-ordered. Overview may highlight important issues,
   but list ordering should not silently reorder evidence.
5. Missing/hidden/partial evidence is visible as uncertainty. The UI must not
   imply passed when evidence is absent.
6. Raw payloads, raw logs, stack traces, provider payloads, and prompts are not
   shown by default.
7. Audit Page may link to diagnostics/logs later, but it does not become a log
   console.
8. Main Page owns action recovery; Audit Page returns users to the right Main
   Page context.

---

## 6. Route And Runtime Design

### 6.1 Route Model

Use the existing route constants and builders:

```ts
routes.auditSession = "/sessions/:sessionId/audit";
routes.auditTask = "/sessions/:sessionId/tasks/:taskNodeId/audit";
```

Supported query fields:

```ts
type AuditRouteQuery = {
  entry?: AuditEntryKind;
  filter?: AuditFilterKind;
  recordId?: AuditRecordId;
  returnFocus?: "session" | "task" | "confirmation" | "result" | "file_change";
  returnSessionId?: SessionId;
  returnTaskNodeId?: TaskNodeId;
};
```

### 6.2 App Routing

Current `App.tsx` renders only `MainPageRoute`. The first implementation should
introduce a small router boundary without adopting a large routing framework:

```text
App
  -> AppErrorBoundary
    -> resolve current location
      -> AuditPageRoute when path matches audit routes
      -> MainPageRoute otherwise
```

This keeps the current Main Page stable and avoids introducing React Router just
for two routes. If routing grows beyond this, introduce a proper router in a
separate architecture slice.

### 6.3 Runtime API Selection

Use `createAuditApiFromRuntimeEnv()`:

```text
VITE_PLATO_API_MODE=mock
  -> createAuditMockApi(VITE_PLATO_AUDIT_MOCK_SCENARIO)

VITE_PLATO_API_MODE=http
  -> createHttpPlatoApi({ baseUrl })
```

The page must not import fixtures directly. It should depend on an `AuditApi`
shape:

```ts
type AuditApi = Pick<
  PlatoApi,
  | "getAuditSnapshot"
  | "listAuditRecords"
  | "getAuditRecordDetail"
  | "getEvidenceDetail"
>;
```

---

## 7. Data Flow

### 7.1 Snapshot Query

Primary query:

```ts
api.getAuditSnapshot({
  sessionId,
  taskNodeId,
  entry,
  filter,
  recordId,
  includeDetail: Boolean(recordId),
  limit,
  cursor,
});
```

Expected result:

```text
QueryResponse<AuditPageSnapshot>
```

The snapshot is the canonical source for header, overview, filters, record list,
selected record, permissions, page state, return target, related logs, and
effective config summary.

### 7.2 Detail Query

First implementation can rely on `snapshot.selectedRecord` when available. If a
record is selected but `selectedRecord` is missing, call:

```ts
api.getAuditRecordDetail({
  sessionId,
  recordId,
  includeEvidence: true,
  includeSanitizedPayload: false,
});
```

Do not request sanitized payload by default.

### 7.3 Evidence Query

Evidence detail should be lazy. First implementation may show evidence refs
inside the detail panel and defer full evidence expansion behind an explicit
action.

```ts
api.getEvidenceDetail({
  sessionId,
  evidenceId,
  includeSanitizedPayload: false,
});
```

### 7.4 Event Handling

First mock-backed shell does not need live event subscription. It should still
reserve the state transitions:

| Event | First behavior | Later behavior |
|---|---|---|
| `audit.records_changed` | expose manual refresh/retry | refetch snapshot/list |
| `audit.record_updated` | expose manual refresh/retry | refetch selected detail |
| `audit.evidence_hidden` | expose manual refresh/retry | refetch selected detail/evidence |
| `audit.snapshot_stale` | support stale pageState | enter stale/resync and refetch |

---

## 8. ViewModel Layer

Do not let React components consume `AuditPageSnapshot` directly everywhere.
Create a small page ViewModel adapter:

```text
AuditPageSnapshot
  -> buildAuditPageViewModel(snapshot, localState)
  -> AuditPageShell props
```

Suggested files:

```text
frontend/src/pages/audit-page/auditPageViewModel.ts
frontend/src/pages/audit-page/useAuditPageController.ts
```

### 8.1 Local State

Local UI state:

```ts
type AuditPageLocalState = {
  activeFilter: AuditFilterKind;
  selectedRecordId: AuditRecordId | null;
  detailMode: "closed" | "record" | "return_context";
  pendingEvidenceId: EvidenceId | null;
};
```

Rules:

- Route query initializes `activeFilter` and `selectedRecordId`.
- Selecting a filter clears `selectedRecordId` unless the selected record still
  belongs to the selected filter.
- Selecting a record sets `selectedRecordId` and opens detail mode.
- Closing detail keeps the active filter.
- Return to Main uses `snapshot.returnTarget`.

### 8.2 Page ViewModel

```ts
type AuditPageViewModel = {
  route: AuditRouteViewModel;
  chrome: AuditChromeViewModel;
  header: AuditHeaderViewModel;
  overview: AuditOverviewViewModel;
  filters: AuditFilterItemViewModel[];
  records: AuditRecordItemViewModel[];
  detail: AuditRecordDetailViewModel | AuditReturnContextViewModel | null;
  boundary: AuditBoundaryViewModel;
  actions: AuditPageActionViewModel;
};
```

### 8.3 Boundary State

Reuse `mapAuditSnapshotToUiBoundary()` where possible.

```ts
type AuditBoundaryViewModel =
  | { kind: "loading"; message?: string }
  | { kind: "empty"; reason: string }
  | { kind: "ready" }
  | { kind: "partial"; reason: string }
  | { kind: "permission_denied"; reason: string }
  | { kind: "stale"; reason: string }
  | { kind: "error"; message: string; retryable: boolean };
```

Page layout should stay visible for partial, stale, and recoverable error
states when existing snapshot context is available.

---

## 9. Component Architecture

Follow existing layering:

```text
shared/components      -> primitives
entities/audit         -> stable domain model exports
pages/audit-page       -> route/controller/page composition
```

First implementation should keep Audit Page components under
`frontend/src/pages/audit-page/` until they prove reusable. Do not prematurely
create a global audit component library.

### 9.1 Proposed Files

```text
frontend/src/pages/audit-page/
  AuditPageRoute.tsx
  AuditPage.tsx
  AuditPage.module.css
  useAuditPageController.ts
  auditPageViewModel.ts
  AuditPageChrome.tsx
  AuditHeader.tsx
  AuditOverviewPanel.tsx
  AuditFilterRail.tsx
  AuditRecordList.tsx
  AuditRecordCard.tsx
  AuditRecordDetailPanel.tsx
  AuditBoundaryState.tsx
  AuditReturnContextPanel.tsx
```

### 9.2 Component Responsibilities

| Component | Responsibility | Should not do |
|---|---|---|
| `AuditPageRoute` | parse route/location, create audit API, own query/controller | render detailed UI |
| `useAuditPageController` | load snapshot/detail/evidence, expose handlers | know CSS/layout |
| `auditPageViewModel` | map API snapshot/local state to render model | fetch data |
| `AuditPage` | compose shell layout | call API directly |
| `AuditPageChrome` | top bar, breadcrumb, read-only/trust badges, return button | mutate task/session |
| `AuditHeader` | page title, scope, subject, status/read-only note | compute data from raw API |
| `AuditOverviewPanel` | completeness/verdict/metrics/focus summary | show raw payload |
| `AuditFilterRail` | filter list/counts/selected state | reorder records |
| `AuditRecordList` | timeline/list container | fetch detail |
| `AuditRecordCard` | one record's summary, refs, actor, status | expose backend ids as primary copy |
| `AuditRecordDetailPanel` | what happened, why it matters, evidence, disclosure, config/log reservations | execute recovery actions |
| `AuditBoundaryState` | loading/empty/error/permission/stale UI | hide uncertainty |
| `AuditReturnContextPanel` | preview where return action goes | simulate Main Page state |

### 9.3 Shared Primitive Usage

If shared primitives already exist, use them. If not, keep primitive styling
inside Audit Page and extract only after duplication appears.

Expected primitive roles:

| Role | Existing/future primitive |
|---|---|
| Button | `Button` or page-local button style |
| Badge/Pill | `Badge` or page-local badge style |
| Panel/Card | `Panel`, `Card`, or page-local surface |
| Skeleton | `Skeleton` or simple page-local loading block |
| Error/Empty State | `ErrorState`, `EmptyState`, or page-local state block |

Do not add one-off global primitives just for one Audit Page use unless the
same primitive is needed by Main Page or Settings/Diagnostics.

---

## 10. Layout Design

### 10.1 Desktop First

Desktop layout mirrors Figma v0.1:

```text
TopBar
Header
Overview
Content Grid
  Filter Rail | Record Timeline | Optional Detail Panel
```

Suggested CSS grid:

```css
.content {
  display: grid;
  grid-template-columns: 216px minmax(0, 1fr);
  gap: var(--space-24);
}

.content[data-detail-open="true"] {
  grid-template-columns: 216px minmax(520px, 1fr) 480px;
}
```

Use design tokens from `frontend/src/shared/styles/tokens.css`. Do not introduce
new raw colors unless a placeholder token is first added.

### 10.2 Width And Height

Figma target is 1440x1024. Implementation should:

- support a minimum desktop width around 1280px;
- allow horizontal page scroll below the minimum width;
- keep top chrome stable;
- allow timeline/detail content to scroll inside their panels when records are
  longer than the viewport;
- avoid clipping record titles, refs, and disclosure text.

### 10.3 Tablet / Mobile

First implementation may be desktop-first, but must not become unusable on
narrow screens.

Suggested responsive behavior:

| Width | Behavior |
|---|---|
| `>= 1280px` | Figma-like rail + timeline + optional detail panel |
| `960px - 1279px` | Filter becomes horizontal bar above timeline; detail stacks below or opens as full-width panel |
| `< 960px` | Single-column layout; filter chips, record list, detail below selection |

If tablet/mobile polish is deferred, document it as a known gap and ensure
content remains reachable with scrolling.

---

## 11. Interaction Model

### 11.1 Initial Load

1. Parse current route.
2. Derive `sessionId`, optional `taskNodeId`, query `filter`, query `recordId`.
3. Load `AuditPageSnapshot`.
4. Build page ViewModel.
5. Render boundary state and content.

### 11.2 Filter Selection

User action:

```text
Click filter item
```

Behavior:

1. Update local `activeFilter`.
2. Update URL query `filter`.
3. Clear selected record unless it belongs to the new filter.
4. Call `getAuditSnapshot` or `listAuditRecords`.

First implementation can choose one of two strategies:

| Strategy | Recommendation |
|---|---|
| Snapshot reload per filter | Preferred first slice; simpler and matches contract |
| List-only query per filter | Later optimization when backend route exists |

### 11.3 Record Selection

User action:

```text
Click record card
```

Behavior:

1. Set `selectedRecordId`.
2. Update URL query `recordId`.
3. Open detail panel.
4. Use `snapshot.selectedRecord` if already present; otherwise call
   `getAuditRecordDetail`.

### 11.4 Detail Close

User action:

```text
Close detail / back to record list
```

Behavior:

1. Clear `selectedRecordId`.
2. Remove `recordId` from URL query.
3. Return timeline to wider layout.

### 11.5 Return To Main Page

User action:

```text
Click Return to Task / Return to Session
```

Behavior:

1. Use `snapshot.returnTarget` as source of truth.
2. Build Main Page route with `sessionId` and optional `taskNodeId`.
3. Navigate without mutating audit or task state.

### 11.6 Evidence Detail

First implementation:

- render evidence refs in record detail;
- show hidden/partial/inconclusive disclosure clearly;
- reserve explicit "open evidence" behavior only if needed for A14.

Do not inline raw payload by default.

---

## 12. State Coverage

The page must handle all mock scenarios:

| Scenario | Expected UI coverage |
|---|---|
| A1 Empty audit | Empty panel, no pass implied, return action visible |
| A2 Loading | Stable header/skeleton, no blank page |
| A3 Records ready | Overview + filter rail + record list |
| A4 Record selected | Detail panel open |
| A5 Partial evidence | Partial banner/disclosure |
| A6 Hidden evidence | Hidden evidence indicators, no raw payload |
| A7 Warning verdict | Warning verdict tone, non-blocking issue |
| A8 Failed verdict | Failed verdict tone and failure evidence |
| A9 Inconclusive verdict | Inconclusive copy, missing confidence explanation |
| A10 Not available | Not available state distinct from passed |
| A11 Permission denied | Permission boundary and return path |
| A12 Stale snapshot | Stale/resync message and retry action |
| A13 Query error | Error boundary and retry action |
| A14 Evidence load error | Evidence detail error isolated from page snapshot |

---

## 13. API Error And Recovery Rules

| Failure | UI behavior |
|---|---|
| Snapshot network error | Show page-level recoverable error; keep route context if known |
| Snapshot `permission_denied` | Show permission state, return action remains available |
| Snapshot `not_found` | Show missing context state, return to session fallback if possible |
| Record detail `not_found` | Clear selected record or show inline detail error |
| Evidence detail error | Show inline evidence error only; do not collapse whole page |
| Stale snapshot | Show stale banner/state; allow retry/refetch |

Retries should call the same query again. Retry must not mutate session/task.

---

## 14. Styling And Tokens

Use the existing token system:

```text
frontend/src/shared/styles/tokens.css
frontend/src/shared/styles/global.css
```

Audit Page should reuse current Plato visual language:

- page background: product app background token;
- panels: surface token;
- text: semantic text tokens;
- borders: semantic border tokens;
- verdict/status colors: semantic status/audit tokens where available;
- typography: existing product font stack and type roles.

If a needed audit semantic token is missing, add a placeholder token first and
name it by semantic intent, for example:

```css
--color-audit-verdict-warning-bg
--color-audit-verdict-warning-text
--color-audit-evidence-hidden-bg
```

Do not hardcode Figma color values inside Audit Page CSS.

---

## 15. Accessibility

Minimum requirements:

1. Filter rail uses buttons or accessible tabs/listbox semantics.
2. Selected record has `aria-current` or equivalent selected state.
3. Record cards are keyboard-focusable.
4. Detail panel has an accessible heading and focus management if opened as a
   drawer-like region.
5. Return action is a real button/link.
6. Color is not the only signal for warning/failed/inconclusive/hidden states.
7. Error and stale states announce enough text to be understood without visuals.

---

## 16. Testing Strategy

### 16.1 Unit Tests

| Test target | Coverage |
|---|---|
| `auditPageViewModel.ts` | snapshot -> view model mapping, verdict labels, filter selection, detail mode |
| route parser/helper | session audit route, task audit route, query parsing |
| filter behavior | counts, zero-count filters, selected record preservation/clearing |
| boundary mapping | loading, empty, partial, permission, stale, error |

### 16.2 Component Tests

Use Testing Library:

| Component/page | Coverage |
|---|---|
| `AuditPageRoute` | loads mock snapshot and renders header/overview/list |
| Filter interaction | clicking filter changes selected filter and list state |
| Record selection | clicking record opens detail |
| Detail close | clears detail and keeps filter |
| Return action | builds route from `returnTarget` |
| Permission/empty/error states | visible and action-safe |

### 16.3 Visual Checks

At minimum after implementation:

```text
npm run build
npm run lint
npm test
```

For frontend UI slices, also verify with Browser/Playwright-like screenshots at:

- desktop 1440x1024;
- narrower desktop/tablet around 1024x768;
- minimum supported width with scroll behavior.

Check specifically:

- no text overflow in pills/cards/panels;
- timeline and detail panels do not overlap;
- right detail panel remains readable;
- empty/error/permission/stale states do not create blank regions.

---

## 17. Implementation Slices

### AP-005A: Route And Controller Skeleton

Goal: mount an Audit Page route without changing Main Page behavior.

Work:

- Add `AuditPageRoute`.
- Add route matching in `App.tsx`.
- Use `createAuditApiFromRuntimeEnv()`.
- Load mock snapshot and render minimal page state.
- Initially keep Main Page `View audit` reserved until AP-005F enables routing.

Tests:

- route matching test;
- mock snapshot load test;
- Main Page still renders at `/`.

### AP-005B: Layout Shell

Goal: implement Figma v0.1 desktop shell.

Work:

- `AuditPage`, `AuditPageChrome`, `AuditHeader`.
- Top bar/header/overview/content grid.
- Desktop layout with filter rail and timeline.
- Detail-open grid mode.

Tests:

- shell renders scope/subject/return action;
- no data mutation actions exist.

### AP-005C: Overview, Filters, Record List

Goal: make A3 records-ready walkthrough usable.

Work:

- `AuditOverviewPanel`.
- `AuditFilterRail`.
- `AuditRecordList`.
- `AuditRecordCard`.
- filter query/local state.

Tests:

- filter counts render;
- zero-count filters stay selectable;
- records render in API order;
- selected filter state visible.

### AP-005D: Record Detail

Goal: make A4 selected-record and A12 reserved config/log detail usable.

Work:

- `AuditRecordDetailPanel`.
- detail query fallback when snapshot lacks selected detail.
- evidence refs, disclosure, effective config, related logs reservation.
- close/back to list behavior.

Tests:

- selecting a record opens detail;
- close detail clears record query state;
- hidden/partial disclosure shown.

### AP-005E: Boundary States

Goal: cover A1-A14.

Work:

- `AuditBoundaryState`.
- loading, empty, partial, hidden, warning, failed, inconclusive, not available,
  permission denied, stale, query error, evidence load error.

Tests:

- one smoke test per scenario group, not necessarily per component internals.

### AP-005F: Main Page Entry Wiring

Goal: enable Main Page `View audit` only after Audit Page route is stable.

Work:

- update Main Page ViewModel so `View audit` becomes enabled when an audit link
  can be built;
- use `buildAuditSessionRoute` / `buildAuditTaskRoute`;
- update tests that previously asserted reserved/disabled entry.

Tests:

- audit link enabled for valid snapshot/link;
- fallback remains disabled when no audit context exists.

### AP-005G: Visual And Accessibility Polish

Goal: make the first implementation reviewable.

Work:

- align typography, spacing, and surface treatment with current tokens;
- keyboard/focus pass;
- desktop/tablet screenshot pass;
- document deferred responsive/mobile gaps if any.

Tests:

- lint/build/test;
- screenshot/manual visual checklist.

Implementation note:

- Desktop and tablet reviewability are in scope for this slice.
- The first pass keeps the page horizontally reachable below the supported
  minimum width instead of treating mobile as a fully designed mode.
- Mobile-specific layout and interaction polish remain a follow-up after the
  Audit Page information model stabilizes.

### AP-005H: Release Readiness And Backend Handoff

Goal: close the mock-backed frontend slice as a reviewable baseline and make
the backend integration handoff explicit.

Work:

- update contract and implementation plan facts after AP-005A-G;
- record remaining gaps without reopening completed mock UI work;
- make `UiAuditQueryGateway` / HTTP route integration the next recommended
  slice;
- preserve the mock scenarios as backend parity fixtures.

Tests:

- documentation consistency pass;
- `git diff --check`;
- reuse AP-005G validation results as the current frontend readiness evidence.

---

## 18. Backend Integration Follow-up

After the mock-backed UI proves the interaction:

1. Implement backend `UiAuditQueryGateway`.
2. Add HTTP routes matching `platoApi.ts`.
3. Map timeline/projection/audit-agent/config/log facts into `AuditRecord`.
4. Emit or route audit events.
5. Switch `VITE_PLATO_API_MODE=http` and verify parity with mock scenarios.

Backend integration should preserve the same frontend API contract. If the
backend cannot supply a field, it should return explicit partial/not_available
state, not force the frontend to invent facts.

---

## 19. Acceptance Criteria

The first implementation is acceptable when:

1. `/sessions/:sessionId/audit` renders from mock API.
2. `/sessions/:sessionId/tasks/:taskNodeId/audit` renders from mock API.
3. A3 records-ready displays header, overview, filters, and record list.
4. A4 selected-record displays detail panel.
5. A1/A2/A5/A11/A12/A13 boundary states are visibly handled.
6. No Audit Page action mutates Task/Session state.
7. No raw payload is displayed by default.
8. Main Page audit entry routes to Audit Page when a valid audit route exists,
   while fallback remains disabled when no audit context exists.
9. Tests cover route load, filter, selection, detail, and key boundary states.
10. `npm run build`, `npm run lint`, and `npm test` pass for the frontend.

---

## 20. Open Questions

These do not block AP-005A through AP-005H:

1. Should first UI show session audit frame, or only task audit until backend
   aggregation exists?
2. Should the right panel default to record detail or return context preview
   when no record is selected?
3. Should evidence details open inline, in a nested panel, or defer to a later
   Diagnostics page?
4. Should `Config` filter be visible in first UI if real config records do not
   exist yet?
5. Should record list eventually support search, or is filter-only enough for
   Product 1.0?
6. Should canonical Figma file recreate Audit Page v0.1 before or after the
   mock UI implementation?

Current recommendation: preserve AP-005A-G as the mock-backed frontend
baseline, then implement backend audit query/gateway/route integration without
changing the frontend contract unless a documented gap appears.
