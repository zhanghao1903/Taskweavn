# ASK UI Spec: Conversation-Native In-Place Cards

> Status: accepted UI spec
>
> Last Updated: 2026-07-24
>
> Scope: Authoring and Execution ASK cards inside Main Page Conversation.
>
> Related:
> [ASK Lifecycle Contract](../engineering/ask-lifecycle-contract.md),
> [ASK User Interaction](../interaction-model/ask-user-interaction.md),
> [Session Inline ASK Requirements](../plans/feature/session-inline-ask-rendering.zh-CN.md),
> [Technical Design](../plans/feature/session-inline-ask-rendering-technical-design.zh-CN.md).

## 1. Product Decision

Conversation is the only primary structured ASK answer surface.

| Domain | Conversation card | Durable authority |
|---|---|---|
| Authoring | One group card per RawTask clarification batch | RawTaskAsk / RawTaskAnswer |
| Execution | One card per AskRequest | AskRequest / AskAnswer |

The old Authoring Main Work Area form and Execution Detail Panel form are
retired as primary answer surfaces. Other regions may show status/context and a
link that focuses the related Conversation card.

## 2. Page Placement

```text
MainPage
  TopBar
  Sidebar
  Conversation
    SessionMessageCard[]
    ConversationAskCard[]
  Optional Plan / Progress layer
  Optional Detail inspector
  Context Input
```

Conversation stays visible while Authoring ASK is pending. ASK does not replace
the page or create a modal.

## 3. Shared Component Tree

```text
ConversationAskCard
  ConversationAskHeader
    DomainLabel
    StatusBadge
    CreatedOrResolvedTime
  AskReason
  ConversationAskQuestionList
    ConversationAskQuestionBlock[]
      QuestionLegend
      AskChoiceGroup
        AskChoiceControl[]
      AskFreeText
      AskAnswerSummary
      AskValidationLine
  AskCommandError
  ConversationAskActions
```

| Component | Required responsibility |
|---|---|
| `ConversationAskCard` | Stable message/card identity and domain/status presentation. |
| `ConversationAskQuestionBlock` | Original question, reason, options, draft, and final answer. |
| `AskChoiceGroup` | Single/multi/boolean selection with native semantics. |
| `AskFreeText` | Allowed custom text and final text answer. |
| `ConversationAskActions` | Domain-specific submit/defer/cancel. |
| `AskCommandError` | Recoverable error without losing draft. |

## 4. Authoring ASK Group Card

### 4.1 Content

- title: `Planning questions` or localized equivalent;
- RawTask goal/summary when available;
- every original RawTaskAsk in stable order;
- each question's option list;
- required/optional marker;
- one `Submit all answers` action;
- progress such as `2 of 3 answered` when useful.

### 4.2 Local Draft

```ts
type AuthoringConversationAskDraft = {
  rawTaskId: string;
  answersByAskId: Record<string, {
    selectedValue: string | null;
    text: string;
    touched: boolean;
  }>;
};
```

Rules:

1. Draft is keyed by rawTaskId and askId.
2. Choice option submits its backend value, not its localized label.
3. An optionless Authoring question may use text.
4. Required pending questions must be valid before submit.
5. Already answered historical questions are read-only.
6. Command failure preserves all pending drafts.
7. Backend-refetched RawTaskAnswer facts clear matching drafts.

### 4.3 Final State

After answer:

- keep every question and option visible;
- mark selected option with checked state and text/icon;
- render custom value under `Your answer`;
- remove submit controls;
- show resolved time when available;
- do not append a User Answer card.

## 5. Execution ASK Card

### 5.1 Content

- task/session scope;
- original question and reason;
- optional batch question list from AskRequest.questions;
- suggested options;
- allowed free text;
- answer/defer/cancel actions according to capability;
- resume hint as secondary context.

### 5.2 Local Draft

```ts
type ExecutionConversationAskDraft = {
  askId: string;
  selectedOptionIds: string[];
  text: string;
  questionTexts: Record<string, string>;
  submittingAction: "answer" | "defer" | "cancel" | null;
};
```

Validation continues to follow AskRequest:

- free_text requires text;
- single_choice allows at most one selected option;
- multi_choice allows multiple;
- boolean uses one explicit yes/no option;
- free text without option requires `allowNoOptionWithText`;
- option plus text requires `allowFreeText`.

### 5.3 Final State

- mark options selected by AskAnswer.selectedOptionIds;
- show AskAnswer.text under the original question/group;
- show status answered/deferred/cancelled/expired;
- remove primary controls;
- preserve task context and resolved time.

## 6. State Tables

### 6.1 Shared

| State | Visual behavior | Controls |
|---|---|---|
| loading | Card skeleton at chronological position. | None |
| pending | Full questions/options/text. | Enabled according to validity/capability |
| dirty | Draft remains visible; optional unsaved label. | Enabled |
| submitting | Selection remains visible; progress label. | Disabled |
| failed | Inline error; no state falsification. | Retry after safe re-enable |
| permission denied | Readable content and disabled reason. | Disabled |
| stale/resync | Refreshing indicator. | Disabled |
| answered | Selected answers emphasized; all content read-only. | None |
| deferred | Status and original content remain visible. | Policy-dependent, default none |
| cancelled | Terminal status/reason. | None |
| expired | Terminal status. | None |
| superseded | Historical Authoring state and plan-transition explanation. | None |

### 6.2 Command Accepted But Not Refetched

Command acceptance is not final truth.

```text
submit
  -> local submitting
  -> command accepted
  -> submitted_refreshing
  -> snapshot/event confirms terminal state
```

During `submitted_refreshing`, the card remains in place, preserves selection,
and prevents duplicate submit.

## 7. Conversation Visibility

ASK answer evidence may still exist as AgentMessage / Activity.

```ts
conversationVisibility: "visible" | "activity_only";
```

- synthetic ASK card: `visible`;
- ASK-specific User answer message: `activity_only`;
- Router `ask_answered` activity: `activity_only`;
- ordinary User input: `visible`;
- ordinary Read-only Inquiry Answer: `visible`.

Conversation counts and auto-scroll use only visible items.

## 8. Other Main Page Regions

### Top Bar

- show Waiting for User when a blocking ASK is active;
- optional action focuses the ASK card.

### TaskTree

- blocked task shows `Needs answer`;
- selecting/focusing the status may scroll to the Execution ASK card.

### Main Work Area / Plan

- Authoring ASK does not replace Conversation;
- Plan layer remains absent/present according to real Plan state.

### Detail Panel

- may show task title, status, reason, and `View question in Conversation`;
- must not render option/text/answer buttons.

### Context Input

- can be disabled with a pointer to the ASK card;
- Runtime Input Router may accept ASK answer text;
- structured card remains the canonical primary interaction.

## 9. Visual Requirements

- ASK cards are visually stronger than ordinary informational messages.
- Pending uses a waiting/accent treatment; terminal states use quieter surfaces.
- Selected option uses control state, icon/text, and styling—not color alone.
- Question hierarchy remains clear inside a multi-question Authoring card.
- Long reason text may collapse, but the original question cannot be hidden.
- Error text stays adjacent to the affected card/actions.
- Design tokens must supply color, radius, spacing, shadow, typography, and
  motion values.

## 10. Accessibility

- Use `article` for card and fieldset/legend for each question.
- Use native radio/checkbox where possible.
- Connect descriptions and errors with `aria-describedby`.
- Pending/submitting/errors use polite live regions.
- Focus the active ASK card without stealing focus from active typing.
- Submit is reachable by keyboard.
- Esc does not dismiss blocking ASK.
- Resolved state exposes selected option through accessible name/state.

## 11. Responsive Behavior

### Mobile

- one-column questions and full-width options;
- actions remain after the last question;
- no fixed overlay and no horizontal overflow.

### Tablet

- one-column questions; short choices may wrap into two columns;
- selected and error states remain adjacent to the question.

### Desktop

- Conversation column width controls line length;
- short options may use compact rows;
- long options remain full-width.

## 12. Error And Recovery

| Error | Required behavior |
|---|---|
| network/command failure | Keep draft, show retryable error. |
| already answered | Refetch and render answered card. |
| expired | Refetch and render expired card. |
| stale authoring context | Render superseded; offer plan guidance only through explicit future action. |
| permission denied | Read-only card and reason. |
| resume failure after answer | Card stays answered; task shows recoverable execution failure. |
| malformed render protocol | Fall back to safe message body, no guessed controls. |

## 13. Acceptance Criteria

1. Authoring ASK is one Conversation group card.
2. Execution ASK is one Conversation card per request.
3. Pending interaction and terminal history share stable identity.
4. Selected options and text render in the original question.
5. ASK answer evidence is Activity-only in Conversation.
6. Read-only answers remain visible.
7. Conversation remains visible while planning clarification is pending.
8. Detail/Main Work Area contain no duplicate primary ASK form.
9. Every shared state and error path is covered.
10. Mobile/tablet/desktop and keyboard/screen reader behavior are verified.

## 14. Non-Goals

- Confirmation UI migration.
- Attachments or image options.
- Editing historical answers.
- New page/route/modal.
- Making Conversation the persistence authority.
- Replacing Runtime Input Router clarification cards.
