# ASK Lifecycle Contract

> Status: draft contract
> Last Updated: 2026-06-03
> Scope: `ask_user` tool semantics, durable ASK objects, answer contract,
> task pause/resume behavior, events, API candidates, and recovery rules.
> Related: [UI ViewModel Contract](../frontend/ui-viewmodel-contract.md),
> [Event Reducer Contract](../frontend/event-reducer-contract.md),
> [Main Page Interaction Model](../interaction-model/main-page.md),
> [ASK User Interaction](../interaction-model/ask-user-interaction.md),
> [ADR-0014 Interaction Control Taxonomy](../decisions/ADR-0014-interaction-control-taxonomy-for-product-1-0.md),
> [Canonical Status Model](../product/canonical-status-model.md).

## 1. Purpose

ASK is the user-input recovery mechanism for agent execution.

When an Agent cannot safely continue because required information is missing,
ambiguous, or user-owned, it must be able to ask the user a structured question,
pause execution, persist that question, and resume after the user answers.

ASK is not a normal chat message, not a confirmation, and not an
interruption/control intent.

| Mechanism | Meaning | Example |
|---|---|---|
| Message | Informational process history. | "Agent inspected project files." |
| ASK | Agent lacks required information and needs user input. | "Which deployment target should I prepare for?" |
| Confirmation | Agent knows the intended action but needs authorization. | "Approve editing these files?" |

Without ASK, the Agent is forced to guess and continue. That breaks Product 1.0
closed-loop trust, DFX, restart recovery, and task-level accountability.

## 2. Contract Principles

1. ASK is a durable object, not only prose in MessageStream.
2. ASK is created by an Agent/runtime tool call and owned by the backend.
3. A blocking ASK pauses the current task until answered, cancelled, expired, or
   otherwise resolved.
4. The frontend displays ASK as a high-signal interaction surface and records it
   separately from ordinary messages.
5. The MessageStream may contain an ASK history entry, but the answer UI is not
   embedded as a normal message card.
6. Users may select suggested options, provide free text, or do both.
7. For Product 1.0, files are not supported as ASK answers.
8. ASK and Confirmation may share UI primitives, but their domain semantics must
   remain separate.
9. Unknown or malformed ASK events must trigger resync instead of optimistic UI
   mutation.
10. ASK answers must be persisted before task execution resumes.

## 3. LLM Tool Contract

Agents learn that they can ask the user through a registered tool.

```ts
type AskUserToolInput = {
  session_id: string;
  task_id?: string | null;
  question: string;
  reason: string;
  questions?: AskQuestionInput[];
  suggested_options?: AskOptionInput[];
  answer_type:
    | "free_text"
    | "single_choice"
    | "multi_choice"
    | "boolean";
  allow_free_text: boolean;
  allow_no_option_with_text: boolean;
  blocking: boolean;
  resume_hint?: string | null;
  attachments_supported: false;
};

type AskOptionInput = {
  id: string;
  label: string;
  description?: string | null;
};

type AskQuestionInput = {
  id?: string;
  question: string;
  input_hint?: string | null;
  required: boolean;
};
```

Example:

```json
{
  "session_id": "7d68bd14",
  "task_id": "task:deploy",
  "question": "Which deployment target should Plato prepare for?",
  "reason": "The deployment task needs a target platform before generating configuration.",
  "suggested_options": [
    { "id": "github_pages", "label": "GitHub Pages" },
    { "id": "netlify", "label": "Netlify" },
    { "id": "vercel", "label": "Vercel" },
    { "id": "not_sure", "label": "Not sure yet" }
  ],
  "answer_type": "single_choice",
  "allow_free_text": true,
  "allow_no_option_with_text": true,
  "blocking": true,
  "resume_hint": "Continue deployment planning after the user chooses or describes a target.",
  "attachments_supported": false
}
```

Batch example:

```json
{
  "question": "Portfolio planning details",
  "reason": "The portfolio task needs user-owned details before planning.",
  "questions": [
    { "id": "role", "question": "What is your professional role?", "required": true },
    { "id": "work_type", "question": "What work types should the site showcase?", "required": true }
  ],
  "answer_type": "free_text",
  "allow_free_text": true,
  "allow_no_option_with_text": true,
  "blocking": true,
  "attachments_supported": false
}
```

System prompt / Agent policy must state:

- do not guess when required user-owned information is missing;
- call `ask_user` instead of writing a passive chat question;
- use suggested options as suggestions, not as the full answer space;
- set `allow_free_text=true` whenever user intent may exceed the option list;
- when several related facts are needed, put them in `questions` instead of
  writing a long numbered list into `question`;
- keep `questions` short and ask only for the smallest set needed for the next
  safe step;
- treat `ask_user` as a yield point when `blocking=true`;
- do not continue executing a task after a blocking ASK is created.

## 4. Domain Objects

```ts
type AskRequest = {
  id: string;
  sessionId: string;
  taskId?: string | null;
  question: string;
  reason: string;
  questions: AskQuestion[];
  suggestedOptions: AskOption[];
  answerType:
    | "free_text"
    | "single_choice"
    | "multi_choice"
    | "boolean";
  allowFreeText: boolean;
  allowNoOptionWithText: boolean;
  blocking: boolean;
  attachmentsSupported: false;
  status: AskStatus;
  answerRef?: string | null;
  resumeHint?: string | null;
  createdBy: "agent" | "system";
  createdAt: string;
  answeredAt?: string | null;
  expiresAt?: string | null;
};

type AskOption = {
  id: string;
  label: string;
  description?: string | null;
};

type AskQuestion = {
  id: string;
  question: string;
  inputHint?: string | null;
  required: boolean;
};

type AskStatus =
  | "pending"
  | "answering"
  | "answered"
  | "deferred"
  | "cancelled"
  | "expired";
```

`answering` is a frontend/local or command-in-flight state unless the backend
needs to expose command progress. Backend canonical status should normally be
`pending`, then `answered`, `deferred`, `cancelled`, or `expired`.

```ts
type AskAnswer = {
  id: string;
  askId: string;
  sessionId: string;
  taskId?: string | null;
  selectedOptionIds: string[];
  text?: string | null;
  attachments: [];
  answeredBy: "user";
  createdAt: string;
};
```

Validation:

- `selectedOptionIds` may be empty.
- `text` may be null or empty.
- A submitted answer is valid only when at least one selected option exists or
  `text.trim()` is non-empty.
- If `answerType="single_choice"`, at most one option may be selected.
- If `attachments` is non-empty in Product 1.0, reject with a structured
  unsupported-input error.
- If `allowNoOptionWithText=false`, free text alone is not sufficient.
- If `allowFreeText=false`, `text` must be empty.

## 5. Task Execution Integration

ASK introduces a task-level pause state.

Recommended canonical status extension:

```ts
type ExecutionStatus =
  | "not_started"
  | "pending"
  | "running"
  | "waiting_for_user"
  | "done"
  | "failed"
  | "cancelled"
  | "unknown";
```

Runtime behavior:

```text
Agent running task
  -> calls ask_user
  -> backend persists AskRequest
  -> task execution status becomes waiting_for_user
  -> MessageStream records an ask-created entry
  -> UI shows ASK Dock
  -> user submits AskAnswer
  -> backend persists AskAnswer
  -> runtime resumes task with answer in task context
```

`waiting_for_user` is distinct from:

- `pending`: task is queued or waiting for executor capacity;
- `running`: executor is actively making progress;
- `failed`: task cannot proceed without retry or user intervention;
- `confirmation.pending`: user authorization is required for a known action.

For Product 1.0, a task should have at most one active blocking ASK. Multiple
pending ASK objects can exist at session level after restarts or concurrent
future flows, but the default running task should yield only one blocking ASK
at a time.

## 6. Persistence And Recovery

ASK must survive process restart.

Required durable records:

- `AskRequest`
- `AskAnswer`
- task status transition into `waiting_for_user`
- MessageStream ask-created / ask-answered entries
- answer-to-task resume trace

Restart behavior:

| State before restart | Required recovery |
|---|---|
| ASK pending, task waiting for user | Snapshot shows pending ASK and task remains `waiting_for_user`. |
| User answered, resume not yet started | Answer remains durable; dispatcher may resume the task idempotently. |
| Task resumed, execution running | Snapshot shows resumed task state; ASK remains answered history. |
| ASK expired/cancelled | Snapshot shows resolved ASK history and task follows policy-defined next state. |

The runtime must not silently discard pending ASK objects during restart.

## 7. API Candidates

Initial endpoints can stay narrow:

```text
GET  /sessions/{sessionId}/asks
GET  /sessions/{sessionId}/asks/{askId}
POST /sessions/{sessionId}/asks/{askId}/answer
POST /sessions/{sessionId}/asks/{askId}/defer
POST /sessions/{sessionId}/asks/{askId}/cancel
```

Answer command request:

```ts
type AnswerAskRequest = {
  idempotencyKey: string;
  selectedOptionIds: string[];
  text?: string | null;
  attachments?: [];
};
```

Answer command response should follow existing command response conventions:

- accepted is not final truth;
- rejected returns structured `ApiError`;
- response includes refresh hints for session snapshot, task tree, messages, and
  asks.

## 8. Event Candidates

```ts
type AskUiEventType =
  | "ask.created"
  | "ask.answered"
  | "ask.deferred"
  | "ask.cancelled"
  | "ask.expired";
```

Event handling rules:

| Event | Reducer behavior |
|---|---|
| `ask.created` | Add or refresh pending ASK; if it blocks current task, activate ASK Dock and refresh snapshot. |
| `ask.answered` | Mark ASK answered, clear local answer pending, refresh task/message snapshot. |
| `ask.deferred` | Mark ASK deferred and keep task/session policy-visible. |
| `ask.cancelled` | Mark ASK cancelled and refresh task state. |
| `ask.expired` | Mark ASK expired and refresh task state. |

If payload does not include a complete frontend ASK ViewModel, reducers should
request snapshot or ASK list refetch.

## 9. Main Page Snapshot Additions

The frontend should not infer active ASK from ordinary message text. Snapshot
should expose ASK facts directly.

Candidate additive fields:

```ts
type MainPageSnapshot = {
  // existing fields...
  pendingAsks: AskRequestView[];
  activeAsk: AskRequestView | null;
};

type AskRequestView = {
  id: string;
  sessionId: string;
  taskNodeId?: string | null;
  question: string;
  reason: string;
  suggestedOptions: AskOptionView[];
  answerType: "free_text" | "single_choice" | "multi_choice" | "boolean";
  allowFreeText: boolean;
  allowNoOptionWithText: boolean;
  blocking: boolean;
  attachmentsSupported: false;
  status: "pending" | "answered" | "deferred" | "cancelled" | "expired";
  createdAt: string;
};
```

## 10. Multiple ASK Rules

Product 1.0 policy:

1. Prefer one active blocking ASK per running task.
2. If the Agent needs multiple pieces of information, combine them into one ASK
   when practical.
3. If multiple pending ASK objects exist, rank by:
   - selected/current task;
   - blocking before non-blocking;
   - oldest created time;
   - session-level ASK after task-scoped ASK.
4. UI shows one active ASK and a compact queue for the rest.
5. A later task should not execute past a dependency that is waiting for user
   input.

## 11. Error And Permission Rules

| Case | Behavior |
|---|---|
| User cannot answer ASK | UI shows permission-limited state and disables submit. |
| ASK already answered | Reject duplicate answer idempotently or return existing result. |
| ASK expired | Reject answer with `ask_expired`; refresh snapshot. |
| Unsupported attachment | Reject with `unsupported_input_mode`. |
| Stale snapshot | Reject or accept according to version policy, then return refresh hint. |
| Runtime cannot resume after answer | Persist answer, show task recoverable error or retry action. |

## 12. Non-Goals

- File attachments for ASK answers.
- Rich form builders beyond options plus free text.
- Multi-agent negotiation over one ASK.
- Voice or multimodal ASK input.
- Replacing Confirmation with ASK.
- Treating ordinary chat questions as durable ASK objects.

## 13. Implementation Readiness Gaps

Before implementation, update or create:

- canonical status model: add `waiting_for_user` or equivalent execution pause;
- UI ViewModel contract: add `AskRequestView` / `AskAnswer`;
- event reducer contract: add ASK events and resync behavior;
- API/UI mapping: add ASK API errors and UI boundary states;
- Main Page interaction model: add ASK Dock interactions;
- storage design: add durable ASK request/answer store;
- Agent runtime: register `ask_user` tool and enforce pause/resume behavior.

## 14. Acceptance Criteria

Product 1.0 ASK lifecycle is acceptable when:

1. An Agent can call `ask_user` instead of guessing.
2. A blocking ASK pauses the task and survives restart.
3. Main Page snapshot exposes pending/active ASK directly.
4. User can answer using options, free text, or both.
5. Files are explicitly unsupported.
6. MessageStream records ASK history without being the primary answer UI.
7. Answer submission is idempotent and recoverable.
8. Task resumes with the answer in context.
9. Unknown/malformed ASK events trigger resync.
10. Confirmation remains a separate lifecycle.
