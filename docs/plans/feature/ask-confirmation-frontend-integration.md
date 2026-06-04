# Feature Plan: ASK And Confirmation Frontend Integration

> Status: in progress
> Type: Product 1.0 frontend implementation plan
> Last Updated: 2026-06-04
> UX Specs: [ASK UI Spec](../../ux/ask-ui-spec.md), [Confirmation UI Spec](../../ux/confirmation-ui-spec.md)
> Backend Plans: [Message, ASK, And Confirmation Backend](message-ask-confirmation-backend.md), [ASK Domain Unification And Batch Answer](ask-domain-unification-batch-answer.md)
> Frontend Architecture: [Frontend Architecture Plan](../../frontend/frontend-architecture-plan.md), [Main Page Refactor / Rewrite Plan](../../frontend/main-page-refactor-rewrite-plan.md)
> Contracts: [UI ViewModel Contract](../../frontend/ui-viewmodel-contract.md), [Backend To UI Mapping](../../frontend/api-ui-mapping.md), [Event Reducer Contract](../../frontend/event-reducer-contract.md)

---

## 0. Workflow Gate Report

| Item | Decision |
|---|---|
| User request | Enter frontend implementation planning for ASK and confirmation UI. |
| Detected phase | P5/P7 planning for frontend vertical slices. |
| Task type | Docs-only frontend implementation plan. |
| Required upstream artifacts | ASK UI spec, confirmation UI spec, backend ASK/confirmation commands, Main Page frontend architecture, current Main Page code inventory. |
| Found artifacts | `docs/ux/ask-ui-spec.md`, `docs/ux/confirmation-ui-spec.md`, `docs/plans/feature/message-ask-confirmation-backend.md`, `docs/plans/feature/ask-domain-unification-batch-answer.md`, `docs/frontend/main-page-refactor-rewrite-plan.md`, `frontend/src/pages/main-page/*`. |
| Missing or weak artifacts | Frontend API types do not yet include execution ASK views or commands; Main Page ViewModel does not yet model Authoring ASK Work Area or Execution ASK Detail Panel; current `ConfirmationPanel` is inline and button-immediate. |
| Implementation allowed now | Planning is allowed now. Production frontend implementation should proceed only by the slices below. |
| Prework required | Record contract/type work before component work; avoid widening `MainPage.tsx` or `MainPageDetailPanel.tsx`. |
| Execution scope | Define frontend implementation slices, target files, tests, acceptance criteria, and non-goals. |
| Acceptance criteria | Plan maps each UI spec surface to concrete frontend modules, commands, tests, and rollout order. |
| Risks and assumptions | Product 1.0 keeps no global confirmation center, no execution ASK batch, no multimodal ASK options, and no new Figma dependency. |

---

## 1. Progress

| Date | Slice | Status | Notes |
|---|---|---|---|
| 2026-06-04 | C1 Frontend Contract And Adapter Wiring | done | Added frontend ASK types, `MainPageSnapshot.pendingAsks/activeAsk`, `PlatoApi` ASK query/command methods, MainPage adapter command seams, HTTP adapter delegates, mock adapter commands, and targeted tests. |
| 2026-06-04 | C2 Shared Choice Primitives | done | Added a domain-neutral `ChoiceGroup` primitive with single/multi/segmented layouts, disabled/loading/error handling, keyboard-accessible button choices, tokenized CSS, exports, README entry, and component tests. |
| 2026-06-04 | C3 Authoring ASK Work Area | done | Added `AuthoringAskWorkArea`, typed `MainPageWorkAreaView`, authoring batch submit controller seam, S2 authoring ASK mock projection, and targeted component/ViewModel/controller/scenario tests. |
| 2026-06-04 | C4 Execution ASK Detail Panel | done | Added `ExecutionAskDetailPanel`, execution ASK detail ViewModel selection, answer/defer/cancel controller seams, S14 execution ASK mock projection, and targeted component/ViewModel/controller/scenario tests. |
| 2026-06-04 | C5 Confirmation Detail Panel Hardening | done | Extracted `ConfirmationDetailPanel`, replaced immediate option submit with local selection plus explicit resolve, preserved failed selections, rendered terminal confirmations read-only, and added targeted component tests. |

---

## 2. Problem

Product 1.0 now has backend support and UI specs for:

- Authoring ASK batch answers;
- execution ASK waiting/resume commands;
- confirmation hardening;
- Main Page snapshot projection for planning, pending confirmations, and
  backend ASK facts.

At plan start, the frontend still had these gaps:

- `frontend/src/shared/api/types.ts` has `PlanningAskView` and
  `ConfirmationActionView`, but it does not yet expose backend execution
  `AskRequestView`, `AskListResult`, `pendingAsks`, or `activeAsk`.
- `frontend/src/shared/api/platoApi.ts` has `resolveConfirmation`, but no ASK
  answer/defer/cancel commands and no authoring ASK batch answer command.
- `frontend/src/pages/main-page/MainPageWorkbench.tsx` always renders the
  TaskTree/message work grid; it cannot yet replace the Main Work Area with
  Authoring ASK.
- `frontend/src/pages/main-page/MainPageDetailPanel.tsx` has an inline
  confirmation panel and no execution ASK detail mode.
- shared choice primitives do not exist yet; confirmation currently renders
  direct action buttons.

This plan defines a small-slice implementation path that avoids adding more
responsibility to the existing large Main Page files.

---

## 3. Current Code Facts

| Area | Current fact | Implication |
|---|---|---|
| Runtime boundary | `MainPageWorkbench` receives `MainPageViewModel` plus controller actions. | Good place to switch main work area and detail panel by typed view models. |
| View model | `MainPageDetailView` already has `confirmation`, `confirmationResolved`, `task`, `result`, `fileChanges`, and `note`. | Add new discriminants rather than passing more booleans. |
| Controller | `useMainPageController` owns mutations and local pending/error state. | Add ASK/confirmation draft state there, not inside leaf components. |
| HTTP adapter | `PlatoApi` and `MainPageAdapter` already wrap command transport. | Add ASK commands at adapter boundary before UI wiring. |
| Shared UI | `Button`, `Badge`, `Panel`, and `Text` exist. | Add choice primitives before domain panels. |
| Confirmation UI | Existing inline `ConfirmationPanel` calls resolve immediately from each option button. | Refactor into selection plus submit state according to `confirmation-ui-spec`. |
| Backend contract | Backend exposes `AskRequestView`, `AskListResult`, `pending_asks`, `active_ask`, ASK commands, and authoring batch answer route. | Frontend should map to those contract facts instead of inventing fixture-only shapes. |

---

## 4. Target Frontend Shape

Target render tree:

```text
MainPageRoute
  -> useMainPageController
      -> buildMainPageViewModel
          -> MainPageWorkbench
              -> MainPageTopBar
              -> MainPageSessionSidebar
              -> MainWorkArea
                  -> AuthoringAskWorkArea
                  -> TaskWorkspaceGrid
                      -> TaskTreePanel
                      -> SessionMessagePanel
              -> MainPageDetailPanel
                  -> ExecutionAskDetailPanel
                  -> ConfirmationDetailPanel
                  -> TaskDetailPanel
                  -> ResultSummaryPanel
                  -> FileChangeSummaryPanel
                  -> StateNotePanel
              -> ContextInputPanel
```

Target module additions:

```text
frontend/src/shared/components/choice/
  ChoiceGroup.tsx
  ChoiceGroup.module.css

frontend/src/pages/main-page/interaction/
  AskQuestionBlock.tsx
  AuthoringAskWorkArea.tsx
  ExecutionAskDetailPanel.tsx
  ConfirmationDetailPanel.tsx
  interactionDrafts.ts
```

Do not move existing Main Page files in this feature. Extract by wrapping and
replacing current inline content in place.

---

## 5. Implementation Slices

### C1. Frontend Contract And Adapter Wiring - done

Deliver:

- Add frontend types matching backend UI contract:
  - `AskAnswerType`;
  - `AskRequestStatus`;
  - `AskOptionView`;
  - `AskRequestView`;
  - `AskListResult`;
  - `MainPageSnapshot.pendingAsks`;
  - `MainPageSnapshot.activeAsk`.
- Add payload types:
  - `AnswerAskPayload`;
  - `AnswerAuthoringAskBatchPayload`;
  - `DeferAskPayload`;
  - `CancelAskPayload`.
- Add `PlatoApi` methods:
  - `answerAsk(sessionId, askId, request)`;
  - `answerAuthoringAskBatch(sessionId, rawTaskId, request)`;
  - `deferAsk(sessionId, askId, request)`;
  - `cancelAsk(sessionId, askId, request)`;
  - optional `listAsks(sessionId, params)` if a targeted query becomes needed.
- Add `MainPageAdapter` methods for the same commands.
- Add HTTP adapter implementations using existing backend routes.
- Update mock adapter with deterministic no-op or fixture-compatible command
  responses.

Acceptance:

- TypeScript contract tests cover camelCase fields for `activeAsk` and
  `pendingAsks`.
- HTTP API tests verify request paths and payloads.
- Existing Main Page tests still pass.

### C2. Shared Choice Primitives - done

Deliver:

- Add a domain-neutral choice primitive under `frontend/src/shared/components`.
- Support:
  - single choice;
  - multi choice;
  - boolean/simple segmented choices;
  - disabled/loading;
  - keyboard selection;
  - inline validation;
  - long option rows.
- Keep the primitive command-free.

Acceptance:

- Component tests cover single, multi, disabled, keyboard, and validation
  states.
- CSS uses existing tokens and does not add page-specific color literals.
- No ASK or confirmation command logic lives in the shared primitive.

### C3. Authoring ASK Work Area - done

Deliver:

- Add `AuthoringAskWorkArea` under `frontend/src/pages/main-page/interaction`.
- Add local draft state keyed by `rawTaskId` and `askId`.
- Extend `MainPageViewModel` with a typed main work area view:

  ```ts
  type MainWorkAreaView =
    | { kind: "authoringAsk"; rawTaskId: string; asks: AuthoringAskView[]; ... }
    | { kind: "taskWorkspace"; ... };
  ```

- Render `AuthoringAskWorkArea` when `snapshot.planning?.asks` contains
  pending authoring asks and `sourceRawTaskId` is available.
- Submit all valid local drafts through
  `answerAuthoringAskBatch(sessionId, rawTaskId, request)`.
- Preserve drafts on command failure.
- Clear drafts only after refreshed projection shows asks answered or removed.

Acceptance:

- Main Work Area is replaced by authoring questions only while planning ASK is
  pending.
- Batch submit sends all valid answers in one command.
- Duplicate submit is disabled while command is in flight.
- Command accepted triggers snapshot refetch and does not locally mark durable
  state as answered.
- Tests cover loading, draft, submitting, rejected, and projection-confirmed
  states.

### C4. Execution ASK Detail Panel - done

Deliver:

- Add `ExecutionAskDetailPanel`.
- Extend `MainPageDetailView` with:

  ```ts
  | {
      kind: "executionAsk";
      ask: AskRequestView;
      commandError: string | null;
      draft: ExecutionAskDraftView;
      header: MainPageDetailHeader;
      selectedTask?: TaskNodeCardView;
    }
  ```

- Select execution ASK detail when:
  - selected task matches `snapshot.activeAsk.taskNodeId`; or
  - selected task execution is `waiting_for_user`; or
  - no selected task exists and `snapshot.activeAsk` exists.
- Add local draft state keyed by `ask.id`.
- Wire answer/defer/cancel commands through adapter.
- Preserve drafts on failed commands.
- Clear drafts after snapshot/event shows ASK no longer pending.

Acceptance:

- Execution ASK appears in Detail Panel, not Main Work Area.
- TaskTree and MessageStream remain visible.
- Answer command targets the concrete ASK id.
- Defer/cancel show pending state and wait for backend facts.
- Tests cover valid answer, text-only answer when allowed, command rejection,
  stale ASK id, and task refocus.

### C5. Confirmation Detail Panel Hardening - done

Deliver:

- Extract current inline confirmation panel into `ConfirmationDetailPanel`.
- Replace direct per-option submit with local option selection and an explicit
  resolve action, matching `docs/ux/confirmation-ui-spec.md`.
- Add `ConfirmationDraftState` keyed by confirmation id.
- Use default option as a recommendation, not auto-submit.
- Preserve selection on command failure.
- Keep resolved/expired confirmations read-only.

Acceptance:

- Pending confirmation renders in Detail Panel only.
- TaskTree and MessageStream remain signals/navigation.
- Resolve command targets the concrete confirmation id.
- UI waits for backend facts before showing resolved state.
- Tests cover pending, selected, resolving, resolve failed, resolved, expired,
  readonly, and stale states.

### C6. Event, Refetch, And Mock Scenario Alignment

Deliver:

- Do not invent frontend-only ASK event types.
- Use current conservative invalidation behavior for task/message/command
  events.
- Add ask-specific event types only if backend exposes them in the UI event
  contract.
- Add or update mock scenarios:
  - authoring ASK pending;
  - authoring ASK rejected command;
  - execution ASK waiting for answer;
  - execution ASK answer accepted and refreshing;
  - confirmation pending/resolving/resolved;
  - stale snapshot with pending interaction controls disabled.

Acceptance:

- Fixture and HTTP modes render the same ViewModel states.
- `command.completed` / `command.failed` clear only matching local pending
  state.
- Snapshot refetch remains the source of durable state convergence.

### C7. QA And Browser Verification

Deliver:

- Unit/component tests for new primitives and panels.
- Main Page view model tests for interaction selection priority.
- Controller tests for command submission and local draft clearing.
- Browser verification in fixture mode and HTTP mode.

Required commands:

```text
cd frontend
npm run test
npm run lint
npm run build
```

Browser checks:

- Desktop width around 1440px;
- tablet width;
- mobile width;
- authoring ASK;
- execution ASK;
- pending confirmation;
- command failure state;
- stale/resync disabled state.

Acceptance:

- No text overlap in option controls or detail panels.
- Detail Panel remains readable on desktop and mobile.
- Authoring ASK batch footer is reachable on mobile.
- Existing Main Page runtime tests still pass.

---

## 6. Implementation Order

Recommended order:

1. C1 contract/API/adapter wiring.
2. C2 shared choice primitives.
3. C5 confirmation hardening.
4. C3 Authoring ASK Work Area.
5. C4 Execution ASK Detail Panel.
6. C6 mock/event alignment.
7. C7 QA/browser closure.

Reasoning:

- Confirmation already has a partial frontend implementation and is the lowest
  risk place to validate shared choice primitives.
- Authoring ASK needs Main Work Area switching and batch draft state.
- Execution ASK needs frontend execution ASK types and command transport first.

---

## 7. Non-Goals

- No Figma write.
- No global confirmation center.
- No execution ASK batch.
- No multimodal ASK options or attachments.
- No frontend direct workspace file reads.
- No backend lifecycle changes.
- No large Main Page rewrite in one slice.
- No new event payload semantics unless backend contract exposes them.

---

## 8. Open Questions

1. Whether confirmation should remain explicit select-then-resolve for all
   options, or allow one-click low-risk options later. Product 1.0 uses
   select-then-resolve until a UX review changes it.
2. Whether `ExecutionStatus` frontend type should immediately add
   `waiting_for_user` to match backend execution status, or keep
   `TaskNodeStatus = "waiting_user"` as compatibility during C1. C1 should
   reconcile this explicitly.
3. Whether execution ASK answer/defer/cancel should use targeted ASK queries
   after command accepted, or rely only on full session snapshot refetch.
   Product 1.0 can start with full snapshot refetch.

---

## 9. Completion Criteria

This feature is complete when:

- Authoring ASK can be answered in one batch from the Main Work Area.
- Execution ASK can be answered/deferred/cancelled from the Detail Panel.
- Confirmation can be resolved from the Detail Panel with explicit local
  command states.
- All three surfaces share choice primitives without sharing domain commands.
- UI waits for backend facts before marking ASK or confirmation resolved.
- Fixture and HTTP paths both cover the new interaction states.
- Frontend tests, lint, build, and browser checks pass.
