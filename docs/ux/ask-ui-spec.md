# ASK UI Spec: Authoring Work Area And Execution Detail Panel

> Status: draft UI spec
> Last Updated: 2026-06-04
> Scope: Product 1.0 Authoring ASK Work Area and Execution ASK Detail Panel.
> Related: `docs/plans/feature/ask-domain-unification-batch-answer.md`,
> `docs/engineering/ask-lifecycle-contract.md`,
> `docs/interaction-model/ask-user-interaction.md`,
> `docs/frontend/ui-viewmodel-contract.md`,
> `docs/ux/screen-state-spec.md`

## 1. Purpose

This document defines the Product 1.0 UI structure and state tables for ASK.

ASK has two domains:

| Domain | UI container | Backend authority | User mental model |
|---|---|---|---|
| Authoring ASK | Main Work Area | RawTask / authoring domain | The system needs planning clarification before it can produce or refine the Draft TaskTree. |
| Execution ASK | Detail Panel | ASK store / TaskBus execution domain | A selected or running PublishedTask is blocked and needs user input before execution can continue. |

The two domains may share visual primitives, but they must not share command
semantics or backend authority. Product 1.0 assumes authoring ASK and execution
ASK do not appear as simultaneous active surfaces.

## 2. Product 1.0 Decisions

1. Authoring ASK uses the Main Work Area, replacing the normal TaskTree work
   area while planning clarification is required.
2. Execution ASK uses the selected TaskNode Detail Panel, not a global modal.
3. Shared ASK primitives are allowed for options, validation, local draft state,
   and submit affordances.
4. Product 1.0 options are text-only. No image options, file choices, uploads,
   or rich option media.
5. ASK should prefer low-cost user choices over free text.
6. Free text is secondary. It is shown only when the ASK permits or requires
   custom text, and should be visually subordinate to choices.
7. Authoring ASK supports local multi-question drafts and one batch submit.
8. Execution ASK remains one active blocking ASK in Product 1.0.
9. Command accepted is not final UI truth. Final UI state follows snapshot,
   event, or query projection.

## 3. Shared Component Primitives

These primitives can be shared by both domains:

| Component | Responsibility | Notes |
|---|---|---|
| `AskQuestionBlock` | Displays one question, reason, required marker, options, optional text input, validation, and local draft state. | Domain-neutral. Receives command handlers from parent container. |
| `AskChoiceGroup` | Renders selectable text options. | Supports single choice, multi choice, boolean, and compact segmented modes. |
| `AskChoiceChip` | Compact option for short values. | Good for yes/no, category, priority, or simple constraints. |
| `AskOptionRow` | Full-width text option for longer labels and descriptions. | Use when options need 1 to 2 lines of explanation. |
| `AskOptionalText` | Secondary free-text input. | Collapsed or visually secondary by default. |
| `AskValidationLine` | Shows required-field, stale, rejected, or permission feedback. | Must preserve user draft on recoverable errors. |
| `AskBatchFooter` | Shows submit state, answered count, validation summary, and batch submit action. | Authoring only in Product 1.0. |
| `AskCommandError` | Inline command failure message. | Does not mark ASK answered locally. |

Choice controls should be keyboard accessible and expose selected state.

## 4. Authoring ASK Work Area

### 4.1 Placement

Authoring ASK owns the Main Work Area while RawTask planning is blocked on user
input. The normal TaskTree area is hidden or replaced because the user is still
clarifying the plan. The Detail Panel can show passive session context, but it
must not become the primary answer surface for authoring ASK.

```text
MainPage
  PageShell
    TopBar
    Sidebar
    MainWorkArea
      AuthoringAskWorkArea
        AuthoringAskHeader
        RawTaskContextSummary
        AuthoringAskBatchForm
          AskQuestionBlock[]
        AuthoringAskDraftSummary
        AskBatchFooter
    DetailPanel
      SessionContextDetail | PlanningContextDetail
    ContextInputBar
      disabled or secondary guidance mode
```

### 4.2 Component Structure

| Component | Responsibility | Required state |
|---|---|---|
| `AuthoringAskWorkArea` | Container that replaces the normal TaskTree work area for planning ASK. | loading, awaiting input, submitting, submitted refreshing, error. |
| `AuthoringAskHeader` | Shows planning scope and concise reason the system needs input. | title, subtitle, planning status badge. |
| `RawTaskContextSummary` | Shows the user goal or RawTask summary being clarified. | raw task title/summary, optional validation summary. |
| `AuthoringAskBatchForm` | Owns local answer drafts for all pending RawTask ASK objects. | local draft map keyed by ask id. |
| `AskQuestionBlock[]` | One block per pending question. | selected option values, optional text, per-question validity. |
| `AuthoringAskDraftSummary` | Optional compact count of answered required questions. | answered count, required count, unsaved flag. |
| `AskBatchFooter` | Primary submit all action and local validation summary. | submit enabled, submitting, rejected, stale. |

### 4.3 Local Draft Model

Frontend-only state:

```ts
type AuthoringAskDraftState = {
  rawTaskId: string;
  answersByAskId: Record<
    string,
    {
      selectedOptionValues: string[];
      text: string;
      touched: boolean;
      valid: boolean;
      error?: string | null;
    }
  >;
  dirty: boolean;
  submitting: boolean;
  lastCommandId?: string | null;
  commandError?: string | null;
};
```

The local draft must be cleared only when the backend projection confirms the
ASK objects are answered or no longer pending.

### 4.4 State Table

| State | Required conditions | UI behavior | Primary action | Exit condition |
|---|---|---|---|---|
| `not_applicable` | No pending authoring ASK. | Show normal Main Work Area. | None. | Snapshot contains pending authoring ASK. |
| `loading` | Session snapshot or planning ASK projection is loading. | Show skeleton in Main Work Area. | None or retry load. | Projection loaded or load error. |
| `awaiting_input` | Pending authoring ASK exists and no command is in flight. | Show all pending questions, preselect defaults when provided, preserve local drafts. | `Submit all answers` when required questions are valid. | User edits draft or submits. |
| `dirty_draft` | Local draft differs from loaded ASK projection. | Show unsaved signal and keep all questions editable. | `Submit all answers`. | Submit starts, user clears draft, or projection changes. |
| `submitting` | Batch answer command is in flight. | Disable option controls and submit; keep current selections visible. | None. | Command accepted or rejected. |
| `submitted_refreshing` | Batch command accepted, but refreshed projection has not confirmed answered state. | Show non-blocking saving state; prevent duplicate submit for same draft. | None or manual refresh if timeout. | Snapshot/event shows ASK answered or still pending. |
| `rejected` | Command rejected or failed before backend acceptance. | Keep draft, show inline error, re-enable valid controls. | Retry with same or new idempotency policy. | Successful submit or user changes answer. |
| `empty_options` | ASK has no suggested options but allows text. | Show compact text-first question block as exception. | Submit text answer. | Valid text submitted or ASK projection updates. |
| `readonly` | User lacks permission or session is stale/read-only. | Show questions read-only with disabled reason. | Refresh if stale. | Permission or stale state changes. |
| `error` | Projection cannot be loaded. | Show recoverable error in work area. | Retry snapshot. | Snapshot succeeds. |

### 4.5 Command Mapping

Authoring batch submit:

```http
POST /api/v1/sessions/{sessionId}/authoring/raw-tasks/{rawTaskId}/asks/answers
```

Payload:

```json
{
  "answers": [
    {
      "askId": "ask_1",
      "value": "Use React and Vite"
    }
  ]
}
```

The UI must send all valid local answer drafts in one command. If the backend
rejects duplicate ASK ids or already answered ASK objects, the UI keeps the
local draft and refreshes projection before retry.

## 5. Execution ASK Detail Panel

### 5.1 Placement

Execution ASK appears in the selected TaskNode Detail Panel because it is
task-scoped and blocks TaskBus execution. The TaskTree remains visible so the
user can keep task context while answering. The Main Work Area must not be
replaced by execution ASK in Product 1.0.

```text
MainPage
  PageShell
    TopBar
    Sidebar
    MainWorkArea
      TaskTreePanel
      SessionMessageStream
    DetailPanel
      ExecutionAskDetailPanel
        TaskScopeHeader
        ExecutionAskCard
          AskQuestionBlock
          ExecutionAskActions
        ExecutionAskContext
    ContextInputBar
      task guidance mode or disabled while answer command submits
```

### 5.2 Component Structure

| Component | Responsibility | Required state |
|---|---|---|
| `ExecutionAskDetailPanel` | Detail mode for the selected task when it has an active execution ASK. | waiting input, submitting answer, resume waiting, stale, error. |
| `TaskScopeHeader` | Shows selected TaskNode title, status, and why it is blocked. | task id, title, status badge, waiting reason. |
| `ExecutionAskCard` | Shows the active blocking ASK question and answer controls. | selected answer, validation, command state. |
| `AskQuestionBlock` | Shared question block for one active ASK. | options, optional text, validity. |
| `ExecutionAskActions` | Domain-specific answer/defer/cancel actions. | can answer, can defer, can cancel, pending action. |
| `ExecutionAskContext` | Passive context such as last relevant message or tool result summary. | short context only; no raw logs by default. |

### 5.3 Local Draft Model

Frontend-only state:

```ts
type ExecutionAskDraftState = {
  askId: string;
  selectedOptionValues: string[];
  text: string;
  touched: boolean;
  valid: boolean;
  submittingAction: "answer" | "defer" | "cancel" | null;
  commandError?: string | null;
};
```

The draft is scoped to `askId`. Switching selected tasks should preserve the
draft for the active ASK if the same ASK id is still pending.

### 5.4 State Table

| State | Required conditions | UI behavior | Primary action | Exit condition |
|---|---|---|---|---|
| `not_applicable` | Selected task has no pending execution ASK. | Show normal TaskNode detail. | None. | Snapshot contains pending ASK for selected task. |
| `waiting_input` | Selected task has one pending blocking ASK. | Show question, choices, optional text, and answer action. | Answer when draft is valid. | User selects/edits or task changes. |
| `choice_selected` | Draft is valid. | Highlight selected options and enable answer. | Answer. | Submit starts or draft becomes invalid. |
| `submitting_answer` | Answer command is in flight. | Disable controls, keep current selection visible, show saving state. | None. | Command accepted or rejected. |
| `resume_waiting` | Answer command accepted, but task has not resumed or refreshed yet. | Keep panel visible with non-blocking resume state; prevent duplicate submit. | None or refresh if timeout. | Snapshot/event shows ASK answered, task running/done/failed, or new ASK. |
| `defer_pending` | Defer command is in flight. | Disable answer controls and show defer progress. | None. | Command accepted/rejected and projection refreshes. |
| `cancel_pending` | Cancel ASK command is in flight. | Disable controls and show cancel progress. | None. | Command accepted/rejected and projection refreshes. |
| `rejected` | Answer/defer/cancel command failed before backend acceptance. | Keep draft, show inline error, re-enable controls when still pending. | Retry. | Command accepted, projection changes, or ASK becomes terminal. |
| `stale` | Selected task or ASK id no longer matches projection. | Disable controls, show resync state. | Refresh snapshot. | Projection reloads with a valid selected task/ASK. |
| `readonly` | User lacks permission to answer. | Show question and disabled reason; no answer submit. | None or request permission flow if future feature exists. | Permission changes. |
| `error` | ASK projection cannot be loaded. | Show recoverable detail panel error. | Retry snapshot. | Snapshot succeeds. |

### 5.5 Command Mapping

Execution answer uses the execution ASK command surface defined in the ASK
lifecycle contract. The UI must target the concrete ASK id, not only the
TaskNode id.

```http
POST /api/v1/sessions/{sessionId}/asks/{askId}/answer
```

Defer and cancel, when available, target the same ASK id through their
domain-specific endpoints or command gateway actions. Product 1.0 does not
batch execution ASK answers.

## 6. Cross-Domain UI Rules

| Rule | Authoring ASK | Execution ASK |
|---|---|---|
| Primary placement | Main Work Area | Detail Panel |
| Batch submit | Required in Product 1.0 | Not in Product 1.0 |
| Simultaneous display | Not simultaneous with execution ASK in Product 1.0 | Not simultaneous with authoring ASK in Product 1.0 |
| Source label | Planning clarification | Task needs input |
| Main status signal | Planning needs input | Task waiting for user |
| TaskTree visibility | May be absent or hidden while planning | Remains visible |
| Text input priority | Secondary, unless no options exist | Secondary, unless ASK requires custom text |
| Options with images | Not supported | Not supported |
| File attachments | Not supported | Not supported |
| MessageStream role | Passive history only | Passive history only |

## 7. Visual And Interaction Requirements

1. Choice-first layout: show recommended text options before text input.
2. Short options use compact chips or segmented controls.
3. Long options use full-width rows with concise descriptions.
4. Required questions must be visually marked without relying only on color.
5. Submit buttons must use loading/disabled states and prevent duplicate
   non-idempotent submissions.
6. Recoverable command errors must preserve local drafts.
7. `Esc` must not silently dismiss an unanswered blocking ASK.
8. Keyboard users must be able to move through options, select/deselect, type
   text, and submit.
9. On mobile, authoring questions stack vertically and the batch footer remains
   reachable after the last question. Execution ASK stays inside the Detail
   Panel flow rather than becoming an untracked overlay.

## 8. Projection Requirements

Authoring ASK projection follow-up must provide enough data for
`AuthoringAskWorkArea`:

```ts
type AuthoringAskView = {
  domain: "authoring";
  rawTaskId: string;
  askId: string;
  question: string;
  reason?: string | null;
  required: boolean;
  options: AskOptionView[];
  allowFreeText: boolean;
  status: "pending" | "answered" | "expired";
};
```

Execution ASK projection should provide:

```ts
type ExecutionAskView = {
  domain: "execution";
  askId: string;
  sessionId: string;
  taskNodeId: string;
  question: string;
  reason?: string | null;
  required: boolean;
  options: AskOptionView[];
  allowFreeText: boolean;
  canAnswer: boolean;
  canDefer: boolean;
  canCancel: boolean;
  status: "pending" | "answered" | "deferred" | "cancelled" | "expired";
};
```

Shared option shape:

```ts
type AskOptionView = {
  value: string;
  label: string;
  description?: string | null;
  recommended?: boolean;
};
```

Product 1.0 does not include image, icon, file, or attachment fields on ASK
options.

## 9. Acceptance Criteria

- Authoring ASK component hierarchy is defined for Main Work Area placement.
- Execution ASK component hierarchy is defined for Detail Panel placement.
- Shared components are named without merging domain command semantics.
- Authoring state table covers loading, local drafts, batch submit, command
  rejection, stale/readonly, and projection errors.
- Execution state table covers waiting input, submit, resume waiting,
  defer/cancel pending, stale/readonly, and projection errors.
- Command mappings explicitly distinguish RawTask authoring batch answer from
  execution ASK answer/defer/cancel.
- Product 1.0 constraints are explicit: text-only options, no attachments, no
  execution batch, no simultaneous active authoring/execution ASK surfaces.

## 10. Non-Goals

- No frontend implementation in this spec.
- No Figma component creation in this spec.
- No execution multi-ASK group runtime behavior.
- No full custom form builder.
- No answer editing after successful submission.
- No multimodal answer input.
