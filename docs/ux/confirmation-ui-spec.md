# Confirmation UI Spec: Detail Panel Authorization

> Status: draft UI spec
> Last Updated: 2026-06-04
> Scope: Product 1.0 confirmation placement, component structure, state table,
> and Main Page projection rules.
> Related: `docs/plans/feature/message-ask-confirmation-backend.md`,
> `docs/plans/feature/ask-confirmation-frontend-integration.md`,
> `docs/ux/screen-state-spec.md`, `docs/frontend/ui-viewmodel-contract.md`,
> `docs/frontend/api-ui-mapping.md`, `docs/interaction-model/main-page.md`,
> `docs/ux/ask-ui-spec.md`

## 1. Purpose

Confirmation is the authorization mechanism for a known action. The Agent
already knows what it intends to do, but the system needs user approval,
rejection, or an alternative decision before continuing.

Confirmation is distinct from ASK:

| Mechanism | User meaning | Product 1.0 primary UI |
|---|---|---|
| ASK | The Agent lacks required information and needs user input. | Authoring ASK in Main Work Area; Execution ASK in Detail Panel. |
| Confirmation | The Agent knows the intended action and needs authorization. | Detail Panel authorization surface. |

Confirmation may share choice primitives with ASK, but it must keep separate
domain copy, commands, lifecycle, and audit meaning.

## 2. Product 1.0 Decisions

1. The selected TaskNode Detail Panel is the primary confirmation operation
   surface.
2. TaskTree shows a confirmation-needed badge and lets the user select the
   owning TaskNode.
3. MessageStream records passive/actionable history and can deep-link to the
   owning TaskNode, but it is not the primary confirmation form.
4. Top Bar may show a session-level waiting signal, but it does not host
   confirmation actions.
5. Product 1.0 does not introduce a global confirmation center.
6. Product 1.0 does not batch multiple confirmations.
7. Confirmation options are text-only.
8. Command accepted is not final UI truth. Final state follows snapshot, event,
   or query projection.

## 3. Placement Model

```text
MainPage
  PageShell
    TopBar
      SessionStatusSignal
    Sidebar
    MainWorkArea
      TaskTreePanel
        TaskNodeCard
          ConfirmationNeededBadge
      SessionMessageStream
        ConfirmationHistoryEntry
    DetailPanel
      ConfirmationDetailPanel
        TaskScopeHeader
        ConfirmationPromptCard
          ConfirmationRiskSummary
          ConfirmationOptionGroup
          ConfirmationActionFooter
        ConfirmationAuditHint
    ContextInputBar
      task guidance mode or disabled while resolve command submits
```

The Detail Panel owns the actionable controls because confirmation is scoped to
a concrete task/action. The Main Work Area stays available for task context.

## 4. Component Structure

| Component | Responsibility | Required state |
|---|---|---|
| `ConfirmationDetailPanel` | Detail mode shown when the selected TaskNode has a pending confirmation or a confirmation is focused from MessageStream. | pending, resolving, resolved refreshing, failed, expired, readonly, stale. |
| `TaskScopeHeader` | Shows owning TaskNode title, status, and confirmation reason. | task id, title, status badge, scope label. |
| `ConfirmationPromptCard` | Shows prompt, action summary, and available decisions. | prompt title/body, option state, local command state. |
| `ConfirmationRiskSummary` | Explains why authorization is needed. | risk label, reason, affected files/actions when available. |
| `ConfirmationOptionGroup` | Renders approval/rejection/alternative options. | selected option, default option, disabled state. |
| `ConfirmationActionFooter` | Submit button and secondary navigation/actions. | resolve enabled, resolving, command error. |
| `ConfirmationAuditHint` | Passive hint that confirmation and response are auditable. | audit link when available. |
| `ConfirmationNeededBadge` | TaskTree signal only. | count or pending marker. |
| `ConfirmationHistoryEntry` | MessageStream history entry and jump link. | pending/resolved/expired display state. |

## 5. Shared UI Primitives

Confirmation can reuse these ASK primitives:

| Shared primitive | Confirmation use |
|---|---|
| `AskChoiceGroup` or shared `ChoiceGroup` | Render text-only decision options. |
| `AskChoiceChip` or shared `ChoiceChip` | Compact approve/reject/skip choices. |
| `AskOptionRow` or shared `OptionRow` | Longer options with explanations. |
| `AskValidationLine` or shared `ValidationLine` | Inline validation and command failure. |

The shared primitive must not own domain commands. Parent containers choose
whether selection resolves a confirmation, answers an ASK, or stays local.

## 6. Local Draft Model

Frontend-only state:

```ts
type ConfirmationDraftState = {
  confirmationId: string;
  selectedOptionValue: string | null;
  touched: boolean;
  resolving: boolean;
  lastCommandId?: string | null;
  commandError?: string | null;
};
```

The draft is scoped by `confirmationId`. It is cleared only when backend
projection confirms the confirmation is resolved, expired, removed, or no
longer pending.

## 7. State Table

| State | Required conditions | UI behavior | Primary action | Exit condition |
|---|---|---|---|---|
| `not_applicable` | Selected TaskNode has no focused or pending confirmation. | Show normal TaskNode detail. | None. | Snapshot contains pending confirmation for selected/focused task. |
| `pending` | `ConfirmationActionView.status = pending`, no local resolve in flight. | Show prompt, risk summary, options, and default option if provided. | Resolve selected option. | User selects option or command starts. |
| `option_selected` | Pending confirmation has a valid local selected option. | Highlight selected option and enable resolve. | Resolve selected option. | Submit starts, user changes option, or projection changes. |
| `resolving` | Resolve command is in flight. | Disable options and submit; keep selected option visible. | None. | Command accepted or rejected. |
| `resolved_refreshing` | Resolve command accepted, but refreshed projection has not confirmed resolved state. | Show non-blocking saving state; prevent duplicate submit. | None or manual refresh after timeout. | Snapshot/event shows resolved, pending, or expired. |
| `resolve_failed` | Command failed before backend acceptance. | Keep selection, show inline error, re-enable controls if backend remains pending. | Retry. | Successful resolve, user changes option, or projection changes. |
| `resolved` | Backend projection says resolved. | Show read-only result and response history; hide submit. | View audit/history. | User changes selection to another object. |
| `expired` | Backend projection says expired. | Show terminal expired state and no action controls. | None. | User changes selection or new confirmation appears. |
| `readonly` | User cannot resolve, session is read-only, or stale snapshot disables commands. | Show prompt/options read-only with disabled reason. | Refresh if stale. | Permission/stale state changes. |
| `stale` | Confirmation id no longer matches selected task or projection version. | Disable controls and show resync state. | Refresh snapshot. | Projection reloads with valid confirmation or none. |
| `error` | Confirmation projection cannot be loaded. | Show recoverable detail panel error. | Retry snapshot. | Snapshot succeeds. |

## 8. Command Mapping

Resolve confirmation:

```http
POST /api/v1/sessions/{sessionId}/confirmations/{confirmationId}/respond
```

Payload:

```json
{
  "value": "approve"
}
```

Rules:

1. The UI must target the concrete confirmation id.
2. The selected option value must come from `ConfirmationActionView.options`.
3. Empty values are invalid.
4. A command response with accepted status creates local pending state only.
5. The UI must wait for `confirmation.resolved`, refreshed snapshot, or
   targeted query before rendering the confirmation as resolved.
6. Duplicate non-idempotent resolve attempts must remain disabled while a
   resolve command is in flight.

## 9. Projection Requirements

Existing `ConfirmationActionView` remains the Product 1.0 UI-facing shape:

```ts
type ConfirmationActionView = {
  id: string;
  sessionId: string;
  taskNodeId: string;
  taskRef?: TaskRef | null;
  title: string;
  body: string;
  options: ConfirmationOptionView[];
  defaultOptionValue?: string | null;
  status: "pending" | "resolved" | "expired";
  localStatus?: "idle" | "resolving" | "resolve_failed";
  riskLabel?: string | null;
  createdAt: string;
  resolvedAt?: string | null;
};
```

Required projection behavior:

| Projection field | UI use |
|---|---|
| `taskNodeId` | Select and render the owning TaskNode in Detail Panel. |
| `title` / `body` | Prompt text. |
| `riskLabel` | Risk summary label or reason. |
| `options` | Text-only decision choices. |
| `defaultOptionValue` | Initial highlighted recommendation; not auto-submitted. |
| `status` | Canonical pending/resolved/expired state. |
| `localStatus` | Optional frontend-only overlay; never persisted as domain truth. |

## 10. Cross-Surface Rules

| Surface | Required behavior |
|---|---|
| TaskTree | Show pending confirmation badge on the owning TaskNode. Badge click selects the TaskNode. |
| MessageStream | Show confirmation prompt/response as history. It may focus the Detail Panel but must not become the primary form. |
| Detail Panel | Owns active confirmation decision controls. |
| Top Bar | May show session-level `Waiting for user` or equivalent signal. |
| Audit Page | Shows confirmation records read-only; it must not resolve confirmations. |
| Context Input | Remains for guidance, or is disabled while resolve command is submitting if needed to avoid conflicting input. |

## 11. Visual And Interaction Requirements

1. Use explicit action labels: approve, reject, skip, revise, or equivalent
   product copy supplied by the option label.
2. Use a risk/reason summary when the confirmation author supplied one.
3. Do not auto-submit the default option.
4. Keep resolved confirmations visible as history, but remove active controls.
5. Show command failure inline and preserve the selected option.
6. Do not use browser-native `confirm` or `prompt` dialogs for Product 1.0
   confirmation UI.
7. Keyboard users must be able to select options and submit.
8. `Esc` must not silently dismiss a pending confirmation.
9. On mobile, confirmation content stays within the Detail Panel flow or route
   equivalent; it should not become an untracked overlay.

## 12. Acceptance Criteria

- Product 1.0 primary confirmation placement is the Detail Panel.
- TaskTree, MessageStream, and Top Bar roles are signal/navigation only.
- Component structure defines prompt, risk, option, action footer, audit hint,
  badge, and history entry responsibilities.
- State table covers pending, option selected, resolving, resolved refreshing,
  resolve failed, resolved, expired, readonly, stale, and error.
- Command mapping uses the concrete confirmation id and waits for backend truth
  before showing resolved state.
- Confirmation remains separate from ASK while sharing low-level choice
  primitives where useful.

## 13. Non-Goals

- No frontend implementation in this spec.
- No Figma component creation in this spec.
- No global confirmation center in Product 1.0.
- No batch confirmation resolution.
- No modal as the default confirmation surface.
- No merging confirmation into ASK.
