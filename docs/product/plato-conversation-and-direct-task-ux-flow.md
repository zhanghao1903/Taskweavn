# Plato Conversation And Direct Task UX Flow

> Status: accepted UX flow
>
> Last Updated: 2026-06-17
>
> Scope: UX flow for the Session-level conversation entry and the three first
> routing outcomes: read-only answer, Direct Task, and Plan required. This
> document converts the PRD into user-facing screen states and interaction
> rules. It is not a Figma file, component API, backend contract, or database
> design.
>
> Related:
> [Plato Conversation And Direct Task PRD](plato-conversation-and-direct-task-prd.md),
> [Plato Runtime Input Model](plato-runtime-input-model.md),
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Main Page UX Flow](plato-main-page-ux-flow.md),
> [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md)

---

## 1. Goal

The goal is to make Plato feel visibly responsive without giving up the
Task-first product model.

The user should be able to type one natural-language input and immediately see
which of three high-level outcomes Plato selected:

```text
Read-only answer
Direct Task
Plan required
```

The UX must answer:

1. Did Plato hear me?
2. How did Plato interpret my input?
3. Is Plato answering, creating a small task, or creating a plan?
4. Where can I see the related Plan or Task?
5. What is happening now?

---

## 2. UX Principles

1. **Conversation is the user perception layer.** The user should see natural
   language responses, not only status changes.
2. **Task remains the execution authority.** Direct Task is still a Task; it
   only skips full visible Plan authoring.
3. **Plan remains the structure for larger work.** Do not hide multi-step work
   inside one Direct Task.
4. **Activity is scoped.** Every visible response belongs to Session, Plan, or
   Task scope.
5. **Action / Observation are not primary copy.** Tool calls and observations
   can inform Audit and Diagnostics, but Main Page should project them into
   concise natural-language updates.
6. **The layout should spend space on work, not chrome.** Remove the persistent
   topbar from the Main Page direction and use a three-column workbench shell.
7. **Conversation is not activity cards.** Conversation should read like a
   collaboration thread, while Activity can use denser structured records.
8. **Activity explains Agent work.** Activity should make visible what the
   Agent is doing, why that step exists, and what the user should expect next.

---

## 3. Target Page Shape

### 3.1 Three-Column Workbench

Target structure:

```text
┌───────────────┬──────────────────────────────────┬──────────────────┐
│ Workspace Rail│ Session Work Area                │ Detail Panel     │
│               │                                  │                  │
│ Workspace     │ Conversation / Plan switch        │ Focused object   │
│ Sessions      │ Session conversation              │ Task / Plan /    │
│ Tools         │ Plan & Progress                   │ Result / Audit   │
│               │ Context input                     │                  │
└───────────────┴──────────────────────────────────┴──────────────────┘
```

Topbar removal means its current responsibilities must move:

| Current topbar responsibility | New location |
|---|---|
| Product identity | Top of Workspace Rail, compact. |
| Workspace/session navigation | Workspace Rail. |
| Current session title/status | Session Work Area header. |
| Events live / published status | Session Work Area status row. |
| Settings | Workspace Rail footer or compact icon in Detail Panel header. |
| Audit entry | Related object controls in Session Work Area / Detail Panel. |

The design should be closer to a focused workbench than a page with a large
global header.

### 3.2 Conversation And Plan Layers

The center column has two primary layers:

```text
Conversation
Plan & Progress
```

The user should be able to switch between them without changing Session or
selected Task.

Recommended default:

- Empty/new Session: Conversation is primary.
- After Plan exists: Plan & Progress is primary, with latest conversation
  response visible.
- During Direct Task: Conversation and current Direct Task progress are both
  visible; Plan layer may show a compact single-task plan or "No full plan
  needed".
- After completion: Conversation shows the narrative, Plan/Task shows result
  structure.

### 3.3 Conversation, Activity, And Audit Projections

The Main Page should not create a separate Conversation state authority.

Projection model:

```text
Session Message Stream / Events / domain facts
  -> Conversation layer
  -> Activity layer
  -> Detail Panel
  -> Audit Page
```

User-facing roles:

| Surface | Role | Default density |
|---|---|---|
| Conversation | Collaboration narrative. | Lightweight, thread-like, non-card. |
| Activity | Work progress and Agent explanation. | Structured, filterable, can be card/list-like. |
| Detail Panel | Focused object details. | Full object summary and controls. |
| Audit | Evidence and traceability. | Technical depth allowed. |

Conversation should not render each item as a heavy card by default. It should
look more like a readable thread:

```text
User
  Add visual aids for twelve-year-old students.

Plato
  I recorded this as task guidance. It will shape the courseware visual style.

Task 3 completed
  Created the HTML courseware. Open result / View activity.
```

Activity should remain available for richer status, filters, result previews,
and execution explanations.

### 3.4 Input Placement

The input stays at the bottom of the Session Work Area.

It should always show scope:

```text
Write to Session
Write to Plan
Write to Task 3
```

The placeholder should describe behavior:

```text
Ask, guide, or request a change...
```

The user should not choose "read-only answer / Direct Task / Plan required"
before typing. Plato routes by default and explains the interpretation after
submission.

---

## 4. Shared Flow Skeleton

All three entry states begin the same way:

```text
User types input
  -> input appears in Session conversation timeline
  -> Plato shows interpreting state
  -> router selects outcome
  -> Plato posts natural-language interpretation
  -> product state updates or answer appears
```

The interpreting state should be short and concrete:

```text
Understanding your request...
```

It should not say only:

```text
Thinking...
```

because the user needs to know the system is routing the input, not only
generating text.

### 4.1 Agent Work Visibility

The user must be able to understand what Plato is doing beyond a status badge.

For meaningful transitions, the UI should project:

```text
phase -> what -> why -> next / evidence
```

Example:

```text
Phase: Verifying
What: Checking the generated courseware HTML.
Why: The task requires content accuracy, valid links, and browser display checks.
Next: If checks pass, Plato will mark the task complete and attach the result.
```

Where this appears:

- Conversation: short status line only when it matters.
- Activity: full phase / what / why / next item.
- Detail Panel: focused task or result detail.
- Audit: evidence-level trace.

Minimum visible Agent phases:

| Phase | Conversation pattern | Activity pattern |
|---|---|---|
| Interpreting | "I am deciding how to handle this." | Route decision with reason. |
| Planning | "This needs a plan first." | Planning reason and current output. |
| Preparing | Usually hidden or one short line. | Context/files/prerequisites summarized. |
| Executing | "Started Task 3." | Current work, reason, related task. |
| Verifying | "Checking the result." | What is being checked and why. |
| Waiting | "I need your answer before continuing." | ASK/confirmation reason and blocked task. |
| Recovering | "This failed; here is the safe next step." | Failure reason, retry/skip/ask options. |
| Completed | Short result summary. | Full result preview and evidence refs. |

Do not show raw tool calls, JSON payloads, or internal class names as the
visible explanation.

---

## 5. Entry State A: Read-Only Answer

### 5.1 When To Use

Use read-only answer when the user asks for understanding and no Plan, Task, or
workspace mutation is required.

Examples:

- "What is the current status?"
- "Why did this task fail?"
- "What changed in this file?"
- "Is this result trustworthy?"

### 5.2 Screen State

Conversation layer:

```text
User: Why did this task fail?
Plato: I will answer from the current Task facts without changing the workspace.
Plato: This task failed because ...
```

Rendering:

- show as a lightweight thread item, not a card;
- keep the answer readable inline when it is short;
- if the answer is long, show a summary first and allow expansion;
- show related refs as compact actions, not as full evidence blocks.

Plan & Progress layer:

- unchanged;
- selected Plan/Task remains selected;
- no new Task appears;
- no Plan draft appears.

Detail Panel:

- keeps current focus;
- may show answer refs if the answer is about a selected Task/result/file;
- should not switch focus unless the user clicks a related ref.

### 5.3 User Controls

Available controls:

- ask follow-up;
- open related Task / result / file / Audit ref;
- convert answer into guidance or follow-up task if offered.

Not available by default:

- publish;
- run;
- retry;
- file mutation.

### 5.4 Success Criteria

- The user can tell this was an answer, not execution.
- No Task or Plan is created.
- The answer is visible in the Session conversation timeline.
- The answer carries scope and safe evidence refs when available.

---

## 6. Entry State B: Direct Task

### 6.1 When To Use

Use Direct Task when the user asks for one clear, small executable outcome.

Examples:

- "Update the README startup command."
- "Run tests again."
- "Fix this typo."
- "Rename this task."

### 6.2 Screen State

Conversation layer:

```text
User: Update the README startup command.
Plato: I will handle this as a small task.
Plato: Created task: Update README startup command.
Plato: Started task.
Plato: Done. Updated README and verified the command text.
```

Rendering:

- user request and Plato response appear as conversation messages;
- task lifecycle appears as sparse status lines, not full cards;
- complete result text is summarized unless the user expands it;
- "Open activity" or equivalent action exposes full progress and result
  preview.

Plan & Progress layer:

- shows a Direct Task row or compact single-task plan;
- does not force a multi-step Draft Plan review;
- task status transitions are visible:

```text
queued -> running -> done / failed / waiting for user
```

Detail Panel:

- focuses the Direct Task after creation;
- shows task intent, instructions if any, result, file summary, and audit
  entry;
- shows ASK or confirmation if execution needs user input.

### 6.3 User Controls

Available controls:

- stop while running;
- answer ASK;
- resolve confirmation;
- retry if failed;
- inspect result/file/audit;
- ask follow-up.

Optional controls:

- expand into Plan if Plato or the user decides the task is larger than
  expected;
- create follow-up Plan from result.

### 6.4 Escalation To Plan

If the Direct Task becomes too broad, Plato should stop and explain:

```text
This is larger than a small task. I should turn it into a short plan before
continuing.
```

The user can then approve plan creation or narrow the request.

### 6.5 Success Criteria

- The user does not review a full Plan before execution.
- The work still has a visible Task identity.
- The user sees natural-language progress.
- Result, file summary, and audit linkage remain available.
- The system does not silently expand a small task into broad multi-step work.

---

## 7. Entry State C: Plan Required

### 7.1 When To Use

Use Plan required when the request is broad, ambiguous, multi-step, risky, or
requires review before execution.

Examples:

- "Build a personal portfolio website."
- "Make this project production-ready."
- "Create a complete courseware package."
- "Migrate this app to a new framework."

### 7.2 Screen State

Conversation layer:

```text
User: Build a personal portfolio website.
Plato: This needs a short plan first. I will break it into reviewable tasks.
Plato: I created a plan with 5 tasks.
```

Rendering:

- Conversation explains why a Plan is required;
- the generated Plan itself belongs in Plan & Progress;
- long Plan descriptions should be summarized in Conversation with a link to
  the Plan layer.

Plan & Progress layer:

- switches or highlights Plan & Progress after the plan is ready;
- shows Plan overview;
- shows task list or task tree;
- shows draft/review/publish state as applicable.

Detail Panel:

- initially shows Plan summary and review guidance;
- switches to Task detail when the user selects a Task;
- shows publish/run affordance when the Plan is ready.

### 7.3 User Controls

Available controls:

- review plan;
- select Task;
- add guidance;
- answer planning ASK;
- publish / run;
- ask why the plan was generated.

Not available before publish:

- execution result;
- file summary from tasks that have not run;
- task retry.

### 7.4 Success Criteria

- The user understands why a Plan was created.
- The plan is visible before execution.
- The user can review or guide the Plan.
- Plan creation is not mistaken for background execution.

---

## 8. Transition Rules

### 8.1 From Read-Only Answer

```text
answer only
  -> user asks follow-up
  -> may stay read-only
  -> may become guidance / Direct Task / Plan required if user requests action
```

### 8.2 From Direct Task

```text
direct task done
  -> result review
  -> user accepts / asks follow-up / creates follow-up task or plan
```

```text
direct task too broad
  -> propose Plan required
  -> create Plan only after user accepts or after low-risk auto route policy
```

### 8.3 From Plan Required

```text
plan ready
  -> user reviews
  -> publish / revise / ask question / cancel
```

```text
plan complete
  -> outcome review
  -> accept / follow-up Plan / Direct Task fix / read-only question
```

---

## 9. Copy Guidelines

### 9.1 Interpretation Copy

Use direct product language:

| Route | Copy pattern |
|---|---|
| Read-only answer | "I will answer without changing the workspace." |
| Direct Task | "I will handle this as a small task." |
| Plan required | "This needs a plan first." |
| Clarification | "I need one detail before proceeding." |

Avoid:

- "Running agent..."
- "Executing action..."
- "Tool call started..."
- "TaskBus status changed..."

### 9.2 Progress Copy

Progress messages should be meaningful and sparse:

- created task;
- started task;
- waiting for user;
- completed task;
- failed task;
- created plan;
- plan ready for review.

Do not create user-visible messages for every internal event.

### 9.3 Agent Explanation Copy

Activity copy should answer the user's implicit question:

```text
What is Plato doing, and why is that reasonable?
```

Good:

- "Checking the generated HTML because this task requires link and browser
  validation."
- "Reading the existing README before editing so the command can be updated in
  the right section."
- "Waiting for your deployment target choice before writing config files."
- "Retrying this task because the previous run stopped before verification."

Avoid:

- "AgentLoop step 12"
- "read_file returned content"
- "TaskBus lifecycle event received"
- "Context manager selected snippets"
- "LLM response received"

### 9.4 Long Text Copy

Conversation should prefer summaries over long dumps, while still rendering
message text as safe Markdown:

```text
Task completed. Plato checked the HTML courseware for structure, links,
scientific terms, slide count, responsive rules, encoding, and offline
compatibility. Open full result.
```

Activity may show a longer preview:

```text
Full result
  [collapsed markdown preview]
  Show more / Open detail / View audit
```

Detail Panel can show the focused full content when the selected object is a
result or file summary.

### 9.5 Markdown Rendering

Frontend message rendering should support Markdown wherever user-facing message
body text is shown.

Surfaces:

| Surface | Markdown behavior |
|---|---|
| Conversation | Render short Markdown inline; summarize and collapse long Markdown. |
| Activity | Render structured Markdown preview with collapse/expand. |
| Detail Panel | Render focused full Markdown result or message. |
| Audit | Render only through evidence disclosure and redaction rules. |

Required Markdown readability:

- paragraphs and line breaks;
- bold, italic, inline code;
- ordered and unordered lists;
- fenced code blocks;
- blockquotes;
- links;
- headings;
- tables.

Safety rules:

- raw HTML must not execute;
- scripts, event handlers, iframes, and unsafe URLs must not be active;
- links should be explicit navigation affordances, not hidden commands;
- rendering Markdown must not turn message text into canonical Plan or Task
  state.

Markdown examples:

```markdown
Task completed. Plato checked:

1. HTML structure
2. Internal links
3. Responsive rules

Open full result for the detailed table.
```

```markdown
| Check | Result |
|---|---|
| Links | Passed |
| Encoding | UTF-8 |
```

---

## 10. Empty, Loading, Error, And Recovery States

### 10.1 Empty State

Conversation layer should invite natural input:

```text
Ask, guide, or request a change.
```

Plan & Progress layer can show:

```text
No plan yet.
Small requests can run as Direct Tasks; larger goals will become a Plan.
```

### 10.2 Routing Loading State

Show:

```text
Understanding your request...
```

Optional supporting copy:

```text
Plato is deciding whether to answer, create a small task, or make a plan.
```

If the request has already become execution, use a phase-specific state:

```text
Preparing task context...
Updating files...
Checking result...
Waiting for your answer...
Recovering from the failed run...
```

These states should be scoped to the current Session, Plan, or Task.

### 10.3 Routing Error

Show:

```text
I could not decide how to handle this request.
```

Actions:

- retry;
- ask as read-only question;
- create small task;
- create plan;
- cancel.

### 10.4 Command Rejected

If Direct Task or Plan creation is rejected, show the user-readable reason and
preserve the original input in Conversation.

The user should be able to revise the input or choose another route.

---

## 11. Accessibility And Responsiveness

### 11.1 Keyboard

- The Conversation / Plan switch must be keyboard reachable.
- The input should stay reachable without moving focus through the full task
  list.
- Route correction actions should be buttons, not hidden text links.

### 11.2 Mobile / Narrow Width

If three columns cannot fit:

```text
Workspace Rail -> collapses
Center Work Area -> primary
Detail Panel -> drawer
Conversation / Plan switch -> remains visible
```

Direct Task and Plan required states must remain distinguishable on narrow
screens.

### 11.3 Visual Density

The no-topbar layout should improve density, not create a cramped dashboard.

Each column needs a stable purpose:

- left: navigation;
- center: conversation and plan;
- right: focused detail.

---

## 12. Non-Goals For First UX Slice

- No full chat-first redesign.
- No raw transcript mode as default.
- No raw Action / Observation timeline in Main Page.
- No separate durable Conversation store.
- No multi-agent visual routing.
- No Figma handoff in this document.
- No API contract changes in this document.
- No exact component naming.

---

## 13. UX Acceptance Criteria

This UX flow is ready for implementation planning when:

1. The Main Page has a clear no-topbar, three-column direction.
2. Conversation and Plan are defined as switchable center-column layers.
3. Read-only answer, Direct Task, and Plan required have distinct screen
   states.
4. The user can see natural-language interpretation after input.
5. Direct Task does not require full visible Plan review.
6. Plan-required work still surfaces a reviewable Plan before execution.
7. Messages and activity items remain scoped to Session, Plan, or Task.
8. No state authority is assigned to chat messages.
9. Conversation uses lightweight thread rendering instead of heavy activity
   cards.
10. Activity shows enough Agent work explanation for the user to understand
    what is happening and why.
11. Long Task results are summarized in Conversation and available in Activity
    or Detail without overwhelming the center layer.
12. User-facing message bodies render safe Markdown for readable lists,
    headings, links, tables, and code excerpts.

---

## 14. Handoff Notes

Next artifacts:

1. Main Page layout technical design: no-topbar three-column shell.
2. Frontend state model update: Conversation / Plan layer switch and
   lightweight Conversation projection.
3. Runtime Input Router plan update: route outcomes for read-only answer,
   Direct Task, and Plan required.
4. Activity projection update: Agent phase, what, why, next, and evidence refs
   derived from existing facts where possible.
5. UI contract update: Direct Task command / projection, scoped conversation
   items, and optional explicit Agent work phase fields if frontend derivation
   is not sufficient.
6. Frontend rendering update: shared safe Markdown renderer for Conversation,
   Activity previews, and Detail result text.
7. Figma / visual design only after this UX flow is accepted.
