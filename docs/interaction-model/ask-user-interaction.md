# ASK User Interaction Model

> Status: accepted interaction model
>
> Last Updated: 2026-07-24
>
> Scope: Conversation-native Authoring and Execution ASK placement, in-place
> answer behavior, task/session signals, and recovery states.
>
> Related: [ASK Lifecycle Contract](../engineering/ask-lifecycle-contract.md),
> [Main Page Interaction Model](main-page.md),
> [ASK UI Spec](../ux/ask-ui-spec.md),
> [Session Inline ASK Requirements](../plans/feature/session-inline-ask-rendering.zh-CN.md).

## 1. Purpose

ASK appears when Plato needs user-owned information before work can continue.
It is a durable interaction object, not an ordinary text message.

The user must be able to understand one complete interaction in one place:

- what Plato asked;
- why it asked;
- which options were available;
- what the user selected or typed;
- whether the answer is pending, submitting, accepted, deferred, cancelled,
  expired, or superseded.

## 2. Source Of Truth

| Domain | Durable authority | Command authority |
|---|---|---|
| Authoring ASK | RawTask / RawTaskAsk / RawTaskAnswer | Authoring batch answer command |
| Execution ASK | AskStore / AskRequest / AskAnswer | Execution answer/defer/cancel commands |

Conversation is the product presentation and interaction surface. It does not
replace these stores or infer ASK state from message prose.

## 3. UX Decision

Conversation is the single primary ASK answer surface for Product 1.1.

```text
Main Page
  Conversation
    ordinary typed conversation items
    ConversationAskCard[]
      AuthoringAskGroupCard
      ExecutionAskCard
  Plan / Task progress
  Context / Detail inspector
  Context Input
```

The previous Authoring ASK Main Work Area and Execution ASK Detail Panel forms
are no longer primary answer surfaces. They may show:

- waiting-for-user state;
- related RawTask / TaskNode context;
- a control that scrolls/focuses the Conversation ASK card.

They must not duplicate the full question/options/submit controls.

ASK is not a modal. Modal use remains limited to destructive draft discard or
navigation-loss warnings.

## 4. Component Model

| Component | Responsibility |
|---|---|
| `ConversationAskCard` | Stable Conversation item for one Authoring batch or one Execution ASK. |
| `ConversationAskHeader` | Domain, status, created/resolved time, and concise reason. |
| `ConversationAskQuestionBlock` | One original question, its options, free text, validation, and final answer. |
| `ConversationAskOptionGroup` | Single/multi/boolean options with selected state. |
| `ConversationAskFreeText` | Allowed custom answer or historical answer text. |
| `ConversationAskActions` | Authoring submit-all or Execution answer/defer/cancel. |
| `ConversationAskError` | Recoverable command/stale/permission feedback on the same card. |
| `TaskNeedsAnswerBadge` | Passive TaskTree signal linked to the active card. |
| `TopBarWaitingForUserStatus` | Passive session status linked to the active card. |

## 5. Authoring ASK Group

All questions belonging to one RawTask clarification batch render inside one
card, in original order.

```text
Planning questions
  Question 1
    option A
    option B
  Question 2
    option A
    option B
  Question 3
    option A
    option B
  Submit all answers
```

Rules:

1. Draft state is keyed by `rawTaskId + askId`.
2. Already answered questions are read-only if a partial historical batch
   exists.
3. Batch submit is all-or-nothing for currently pending required questions.
4. After backend confirmation, the same card becomes answered.
5. Selected options remain visible inside each original question.
6. A free-text value that does not match an option appears as `Your answer`.
7. The answer message remains Activity/Audit evidence but is not a separate
   Conversation card.

## 6. Execution ASK

Each durable AskRequest renders as one Conversation card.

Rules:

1. The active pending card owns answer/defer/cancel controls.
2. Options submit their stable option ids.
3. Free text is available only when the ASK contract allows it.
4. Answer accepted is not final truth; controls remain pending until snapshot
   or event facts confirm the result.
5. `answered`, `deferred`, `cancelled`, and `expired` are read-only on the same
   card.
6. The selected TaskNode Detail Panel may show context and a focus link, but no
   duplicate answer form.

## 7. In-Place Resolution

ASK cards have stable identities and chronological positions.

```text
pending
  -> local draft
  -> submitting
  -> answered
```

or:

```text
pending
  -> defer/cancel
  -> deferred/cancelled
```

In all cases:

- card id does not change;
- created time and Conversation ordering do not change;
- resolved time may be added;
- no independent `User answer` / `Answer` Conversation item is appended;
- Activity may append an `ASK answered` state-change summary.

## 8. Answer Rules

| Input | Validity |
|---|---|
| Option only | Valid when the answer type and required rules allow it. |
| Free text only | Valid only when free text without an option is allowed. |
| Option plus free text | Valid when free text is allowed. |
| Empty | Invalid for required questions. |
| Attachment | Unsupported in Product 1.1 ASK. |

Single-choice selects at most one option. Multi-choice can select multiple.
Boolean uses explicit yes/no semantics. The final selected state must not rely
on color alone.

## 9. Multiple ASK Behavior

Conversation may contain multiple ASK cards at their historical positions.

Active focus priority:

1. pending ASK for the selected TaskNode;
2. blocking ASK for the running TaskNode;
3. pending Authoring ASK before a TaskTree exists;
4. oldest blocking session ASK;
5. deferred/read-only historical ASK.

Only the active pending card receives automatic focus. Other cards remain
readable. Drafts are preserved by card/question identity when focus changes.

## 10. Main Page Signals

| Surface | Requirement |
|---|---|
| Conversation | Full ASK question/options/actions and final selected state. |
| Top Bar | Waiting-for-user status; optional focus action. |
| TaskTree | `needs answer` badge on blocked task; optional focus action. |
| Main Work Area | Normal Conversation/Plan layout; no Authoring ASK replacement page. |
| Detail Panel | Passive task/ASK status and context; no duplicate answer controls. |
| Context Input | May be disabled or route to active ASK, but does not replace the structured card. |
| Activity | ASK asked/answered/deferred/cancelled summary and refs. |
| Audit | Durable command, answer, resume, and failure evidence. |

## 11. Interaction Table

| ID | Trigger | Required behavior |
|---|---|---|
| `ASK-UI-001` | ASK appears in snapshot | Insert/update one stable Conversation ASK card and focus it if active. |
| `ASK-UI-002` | User selects an option | Update local card draft; do not append a message. |
| `ASK-UI-003` | User types allowed free text | Update local card draft; do not append a message. |
| `ASK-UI-004` | User submits | Keep selections visible, disable duplicate submit, wait for backend facts. |
| `ASK-UI-005` | Command rejected | Preserve draft and show recoverable error on the same card. |
| `ASK-UI-006` | User defers | Show pending action, then update the same card to deferred. |
| `ASK-UI-007` | User cancels | Show pending action, then update the same card to cancelled. |
| `ASK-UI-008` | Another client answers | Refetch and update the same card to answered. |
| `ASK-UI-009` | ASK expires/supersedes | Remove controls and show terminal reason on the same card. |
| `ASK-UI-010` | User clicks a passive task/status signal | Scroll and focus the related Conversation card. |

## 12. UI States

| State | Required UI |
|---|---|
| loading | Stable card position with loading affordance. |
| pending | Question, options, allowed text, and actions. |
| dirty draft | Unsaved state; preserve by card/question id. |
| submitting | Controls disabled; current selection remains visible. |
| failed | Inline error; draft preserved and retry available. |
| permission denied | Readable card, disabled controls, reason visible. |
| stale/resync | Controls disabled; refresh state visible. |
| answered | Read-only original questions and selected answers. |
| deferred | Read-only or policy-allowed follow-up state. |
| cancelled/expired/superseded | Read-only terminal state and reason. |

## 13. Accessibility And Responsive Rules

- Use fieldset/legend or equivalent question semantics.
- Native radio/checkbox semantics are preferred.
- Expose selected/checked state programmatically.
- Announce validation and command errors near the card actions.
- Keep visible focus for card, option, text, and submit controls.
- Esc must not dismiss a blocking ASK.
- Mobile uses one column without horizontal overflow.
- Tablet and desktop may use denser option layouts.
- Long bilingual question/option text wraps without truncating required meaning.

## 14. Non-Goals

- Replacing Confirmation with ASK.
- Making MessageStream storage the ASK authority.
- Editing a historical answer that already resumed work.
- File/image/attachment answers.
- A new page, route, modal, or independent answer detail.
- Removing ordinary Read-only Inquiry answers.

## 15. Acceptance Criteria

1. Authoring and Execution ASK both render inside Conversation.
2. One Authoring batch uses one card with multiple question blocks.
3. The same card owns pending interaction and terminal history.
4. Answered options and text appear with their original questions.
5. No ASK-specific independent Answer card appears after submission.
6. Ordinary Read-only Inquiry Answer remains visible.
7. Activity/Audit retain answer evidence.
8. Pending, submitting, failed, permission, stale, answered, deferred,
   cancelled, expired, and superseded states are represented.
9. Reload/restart restores the same cards from durable facts.
10. Mobile, tablet, desktop, keyboard, and screen-reader behavior are covered.
