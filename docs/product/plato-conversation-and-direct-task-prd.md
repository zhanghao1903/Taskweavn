# Plato Conversation And Direct Task PRD

> Status: draft PRD
>
> Last Updated: 2026-06-19
>
> Scope: product requirements for making Plato feel responsive through a
> Session-level natural-language conversation layer, and for supporting small
> user requests through a Direct Task path without forcing every request through
> a full visible Plan.
>
> Related:
> [Core Product Principles](core-product-principles.md),
> [Plato Contract Loop Product Model](plato-contract-loop-model.md),
> [Plato Runtime Input Model](plato-runtime-input-model.md),
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Session Active Work Lifecycle](plato-session-active-work-lifecycle.md),
> [Plato Task Semantics](plato-task-semantics.md),
> [Session Conversation / Activity Timeline](../plans/feature/session-conversation-activity-timeline.md),
> [Runtime Input Router Contract](../plans/feature/runtime-input-router-contract.md)

---

## 1. One-Sentence Product Definition

Plato uses Tasks as executable work contracts, but the product core is the
Session. The user should experience Plato through a Session-level conversation
timeline that explains how Plato understood,
responded to, and acted on their instructions.

For small requests, Plato should be able to create and run a Direct Task
without requiring a full user-visible Plan.

---

## 2. Background And Problem

Plato's main product difference is that work is organized around Tasks instead
of an unstructured chat transcript.

That direction remains correct for control, recovery, evidence, and audit. But
the current user experience can feel too much like a background state machine:

- the user gives an instruction;
- the backend creates or updates Plan / Task / TaskBus facts;
- statuses change;
- Action / Observation / Audit facts exist;
- but the user may not feel that Plato is talking back or explaining what is
  happening.

Raw Action and Observation records are not suitable as the primary output for
ordinary users. They are too technical and belong to Audit or Diagnostics.

The missing layer is a natural-language response layer:

```text
User instruction
  -> Plato interprets it
  -> Plato says what it will do
  -> Plato creates Plan or Direct Task
  -> Plato reports user-readable progress and decisions
  -> Plato summarizes result, failure, or recovery path
```

There is a second product problem: not every request deserves a full Plan.

Current Task-first flow is optimized for larger goals:

```text
user goal -> Plan -> Task tree -> execute Tasks
```

For small requests, this can feel heavy. Examples:

- "Update the README install command."
- "Explain why this task failed."
- "Run the tests again."
- "Rename this task."
- "Fix this one copy issue."

Plato needs a lighter route without abandoning Task-first semantics.

---

## 3. Product Thesis

Task-first should define the system of record, not necessarily every visible
interaction shape.

Product rule:

```text
Session is the user-visible product root and conversation timeline.
Task is the minimum executable work contract.
Plan is a structured work segment for work that needs planning.
Direct Task is a lightweight work segment for small executable requests.
```

Therefore:

- Users see a Session-level conversation / activity timeline.
- Every message or activity item has a scope: Session, Plan, or Task.
- Large or ambiguous goals still go through Plan authoring.
- Small executable requests can become Direct Tasks.
- Workspace mutation still requires Task authority.
- Messages explain facts; they do not own canonical state.

---

## 4. Goals

### 4.1 User Experience Goals

1. The user should see that Plato heard the instruction and understood its
   intended consequence.
2. The user should understand whether Plato is answering a question, recording
   guidance, creating a Plan, creating a Direct Task, or asking for missing
   information.
3. The user should see a natural-language work log instead of only status
   changes.
4. The user should be able to trace a conversation item to its related Plan,
   Task, ASK, confirmation, result, file summary, or Audit entry.
5. Small requests should feel lightweight and fast.
6. The user should understand what the Agent is doing now, why it is doing it,
   and what visible consequence should happen next.

### 4.2 Product Architecture Goals

1. Preserve Task as the authority for executable work.
2. Preserve Plan as the authority for multi-step organized work.
3. Keep Session Conversation / Activity as a projection and history layer, not
   as a second state machine.
4. Avoid exposing raw Action / Observation / tool payloads as the main user
   experience.
5. Make the Direct Task route compatible with future Audit, retry, recovery,
   Context Manager, skills, and MCP governance.

---

## 5. Non-Goals

This PRD does not require:

- replacing Task-first with chat-first;
- showing raw Action / Observation as ordinary messages;
- making MessageStream the source of truth for Task or Plan state;
- creating a second durable Conversation store that competes with the Session
  Message Stream / Event facts;
- creating a full visual workflow engine;
- adding multi-Agent routing policy;
- adding user-configurable Router rules;
- supporting complex parallel Plans;
- implementing Product 1.1 skills, MCP, or multimodal inputs;
- defining API endpoints, frontend components, database schema, or Figma frames.

---

## 6. Core Concepts

### 6.1 Session Collaboration Facts And Projections

The Session owns durable collaboration facts that can be projected into
Conversation, Activity, Detail, and Audit surfaces.

The user-facing projections answer:

```text
What did I tell Plato?
How did Plato respond?
What did Plato do or decide as a consequence?
Where can I inspect the related work?
```

It is not a raw chat dump. It is a typed, scoped projection over product facts.

### 6.2 Message Scope

Every user-visible message or activity item should carry a collaboration scope:

```ts
type MessageScope =
  | { kind: "session" }
  | { kind: "plan"; planId: string }
  | { kind: "task"; taskId: string };
```

Scope meanings:

| Scope | User meaning | Examples |
|---|---|---|
| Session | This whole collaboration run. | Original request, session-wide guidance, overall status answer. |
| Plan | This organized round of work. | Plan generated, plan revised, plan completed, plan archived, plan outcome summary. |
| Task | One executable work contract. | Task started, ASK required, confirmation required, task completed, task failed. |

Files, diffs, ASK, confirmation, result, audit records, and messages are refs,
not primary collaboration scopes.

### 6.2.1 Session, Plan, And Active Work

Conversation belongs to Session, not to Plan.

Plan is a scope and work segment inside the Session. It can be active,
completed, or archived, but it should not reset the Session conversation.

```text
Session timeline
  -> Plan started
  -> Task updates
  -> Plan completed
  -> Plan archived
  -> next user input
```

A completed Plan remains active until the user clicks `Archive plan`. Archive
moves the Plan into Session history and returns the Session to a no-active-work
state, ready for a read-only question, Direct Task, or new Plan-required goal.

### 6.3 Direct Task

A Direct Task is a Task created from user input without requiring a full
user-visible Plan authoring step.

It is still a Task:

- it has a stable Task identity;
- it enters TaskBus before workspace mutation;
- it can produce status, result, file summary, audit, retry, and recovery;
- it can ask for missing information;
- it can request confirmation before risky actions.

It is direct only in the product flow:

```text
small user request
  -> interpreted as Direct Task
  -> task created
  -> task executed or queued
  -> result / recovery projected
```

Implementation may attach the Direct Task to an implicit single-task Plan or
Plan Cycle for internal consistency. The product requirement is that the user
does not have to review a full Plan when the request does not need one.

Direct Task can be the current active work item. When it reaches a terminal
state and no recovery is pending, it becomes Session history without a Plan
archive ceremony.

### 6.4 Plan-Required Work

Plan remains required when the request is broad, ambiguous, multi-step,
high-risk, or needs user review before execution.

```text
larger user goal
  -> interpreted as Plan-required
  -> Plan / Task tree drafted
  -> user reviews or answers ASK
  -> tasks publish and execute
```

### 6.5 Message Stream, Conversation, Activity, And Audit

Plato should use one durable collaboration fact layer and multiple user-facing
projections.

Product boundary:

```text
Session Message Stream / Events / domain facts
  -> Conversation projection
  -> Activity projection
  -> Audit projection
```

Meanings:

| Layer | Product role | User-facing behavior |
|---|---|---|
| Session Message Stream / Events | Durable fact and history input for projections. | Not shown raw as the primary UI. |
| Conversation | Natural-language collaboration layer. | Shows user inputs, Plato responses, lightweight status lines, and scoped references. |
| Activity | Work progress layer. | Shows what the Agent is doing, why, current phase, result, failure, recovery, and links. |
| Audit | Trust and evidence layer. | Shows traceability, raw-enough records, evidence, and diagnostic depth. |

Conversation must not become a separate store. It is a projection over facts.
The same Message Stream item or event can appear differently in Conversation,
Activity, and Audit.

Examples:

| Fact | Conversation projection | Activity projection | Audit projection |
|---|---|---|---|
| User asks a small question | User message + answer. | Optional no-op route note. | Route decision record. |
| Direct Task created | "I will handle this as a small task." | Task created with scope/reason. | Command/event record. |
| Task starts execution | Lightweight status line if useful. | Current phase, reason, next check. | Lifecycle event. |
| Tool result arrives | Usually hidden. | Summarized only if meaningful. | Detailed evidence. |
| Task completes with long result | Short summary + link. | Full result preview with expand/open actions. | Result and evidence records. |

### 6.6 Agent Work Narrative

The user needs more than status labels. Plato should make the Agent's work
legible at the product level.

For meaningful work transitions, the Activity projection should answer:

```text
What is the Agent doing?
Why is this step needed?
What is it waiting for or checking?
What changed as a result?
Where can I inspect details?
```

Minimum Agent work phases:

| Phase | Meaning | Example user-facing copy |
|---|---|---|
| Interpreting | Plato is deciding how to handle input. | "Deciding whether this is an answer, small task, or plan." |
| Planning | Plato is turning a larger goal into reviewable work. | "Breaking the goal into tasks before execution." |
| Preparing | Plato is setting up context or prerequisites. | "Reading the selected task and related files before editing." |
| Executing | Plato is performing the Task. | "Updating the README startup command." |
| Verifying | Plato is checking whether the result satisfies the task. | "Running the requested check before marking the task complete." |
| Waiting | Plato needs user input or confirmation. | "Waiting for your deployment target choice." |
| Recovering | Plato hit a failure and is choosing the safe next step. | "The file was missing, so the task needs revised instructions or retry." |

These phases are product projections, not required backend enum names in this
PRD. Implementation can map from existing events first.

---

## 7. Intent Routing Requirements

The input router should classify user input into product outcomes.

Minimum routing outcomes:

| Outcome | Meaning | Product effect |
|---|---|---|
| Read-only answer | User asks a question. | Answer in Conversation. No Plan, Task, or workspace mutation. |
| Guidance recorded | User adds context or preference. | Persist scoped guidance/context fact. |
| Direct Task | User asks for a small executable change. | Create one executable Task without visible Plan authoring. |
| Plan required | User asks for larger organized work. | Enter Plan authoring and Task tree flow. |
| ASK answer | User responds to a blocking ASK. | Persist answer before resume. |
| Confirmation response | User approves/rejects a known action. | Resolve confirmation lifecycle. |
| Command | User asks to stop, retry, publish, cancel, or revise state. | Use command route and show consequence. |
| Clarification needed | Router cannot safely decide. | Ask a focused question or present choices. |

Routing should be deterministic-first and LLM-assisted where needed.

Low-confidence routing must not mutate Plan, Task, or workspace state.

---

## 8. Direct Task Eligibility

Direct Task should be allowed when most of these are true:

- the request has one clear outcome;
- the expected work is short;
- the request is low ambiguity;
- the request does not need user review of a multi-step plan;
- the request does not require multiple dependent tasks;
- the request can be completed or rejected with a small amount of evidence;
- the risk can be managed through existing confirmation/ASK mechanisms.

Examples:

| User input | Expected route | Reason |
|---|---|---|
| "Update the README install command." | Direct Task | Clear small workspace change. |
| "Run tests again." | Direct Task | Clear execution request. |
| "Explain why this task failed." | Read-only answer | Inquiry, no mutation. |
| "Make the site production-ready." | Plan required | Broad, multi-step, needs decomposition. |
| "Build a personal portfolio site." | Plan required | Ambiguous and multi-step. |
| "Use Netlify." | ASK answer or guidance | Depends on active ASK / selected context. |

If Direct Task execution discovers that the work is larger than expected, it
should stop and return to Plan authoring or ask for clarification instead of
silently expanding scope.

---

## 9. Conversation Requirements

Conversation is not the raw Message Stream UI. It is the user-facing
collaboration projection over Session, Plan, Task, and execution facts.

### 9.1 Initial Response

After a user input, Plato should produce a concise natural-language response
that explains the interpretation.

Examples:

| Route | Example response |
|---|---|
| Direct Task | "I will handle this as a small task and update the README install command." |
| Plan required | "This needs a short plan first. I will break it into reviewable tasks." |
| Read-only answer | "I will answer this from the current session facts without changing the workspace." |
| Clarification needed | "I need one detail before proceeding: which deployment target should I use?" |

### 9.2 Progress Updates

Plato should produce natural-language progress updates for meaningful
transitions, not for every low-level event.

Good updates:

- "Created a direct task for the README change."
- "Started task: Update installation instructions."
- "The task needs your choice before continuing."
- "Task completed. README was updated and no tests were required."
- "Task failed because the referenced file does not exist."

Avoid:

- raw tool call names;
- raw JSON payloads;
- raw shell output unless the user asked for it;
- generic noise for every internal event.

Conversation should keep progress compact. Full work progress belongs in the
Activity projection.

Conversation can show:

- user inputs;
- Plato natural-language interpretation;
- lightweight status lines for meaningful transitions;
- short result summaries;
- links to related Plan, Task, Activity, result, file summary, and Audit.

Conversation should not show:

- card-heavy activity items as the default visual form;
- every lifecycle event;
- full long Task results by default;
- raw tool observations;
- long markdown dumps unless the user explicitly opens or expands them.

### 9.3 Activity Projection

Activity is the primary user-facing surface for "what the Agent is doing" and
"why this is happening."

Activity items should be more structured than Conversation messages, but still
non-technical by default. Each meaningful Activity item should include as many
of these fields as the product facts can support:

| Field | Meaning |
|---|---|
| Scope | Session, Plan, or Task. |
| Phase | Interpreting, planning, preparing, executing, verifying, waiting, recovering, completed, failed. |
| What | The concrete action or state transition. |
| Why | The product reason this step is needed. |
| Next | What the user should expect next, when known. |
| Evidence ref | Link to result, file summary, Audit, diagnostics, or related task. |

Activity should not expose raw Action / Observation as ordinary copy. If the
Agent read a file, ran a command, or called a tool, Activity should summarize
the user-facing consequence:

```text
Good: "Checked the courseware HTML for broken internal links."
Avoid: "tool_call read_file returned 49KB."
```

### 9.4 Long Text And Result Handling

Long Task results should not dominate Conversation.

Default behavior:

- Conversation shows a short summary and link/open action.
- Activity can show a longer preview with collapse/expand.
- Detail Panel can show the focused full result.
- Audit can show evidence-level records.
- User-facing message bodies should support safe Markdown rendering so Agent
  answers, summaries, lists, tables, links, and code excerpts remain readable.

If the long text is itself the answer the user asked for, Conversation may show
more of it, but it should still preserve scanability through headings,
progressive disclosure, or "show more" behavior.

### 9.5 Markdown Rendering Boundary

Frontend message rendering should support Markdown for user-facing message
bodies across Conversation, Activity previews, and focused Detail result views.

Minimum Markdown support:

- paragraphs and line breaks;
- emphasis and strong emphasis;
- ordered and unordered lists;
- inline code and fenced code blocks;
- blockquotes;
- links;
- headings;
- tables, because Agent results often summarize checks in tabular form.

Safety boundary:

- raw HTML must not execute;
- scripts, event handlers, iframes, and unsafe URLs must be stripped or
  rendered as inert text;
- links should be treated as user-visible navigation actions and should not
  mutate state by themselves;
- Markdown rendering must not make Message Stream the authority for Plan,
  Task, result, file evidence, or Audit state.

Rendering boundary:

- Conversation uses Markdown for readable text, but still summarizes long
  results by default.
- Activity can render longer Markdown previews behind collapse/expand.
- Detail can render the focused full Markdown result when that object is
  selected.
- Audit may render evidence with stricter disclosure and redaction rules.

### 9.6 Result And Recovery Messages

Terminal messages should explain:

- what was completed;
- what changed;
- what was verified;
- what failed or remains unresolved;
- what the user can do next.

They should link to Task result, file summary, Audit, retry, or follow-up
action where available.

---

## 10. User Flows

### 10.1 Small Request To Direct Task

```text
User: "Update the README startup command."
Plato: "I will handle this as a small task."
System creates Direct Task
Plato: "Started task: update README startup command."
Plato executes
Plato: "Done. Updated README and verified the command text."
```

Acceptance:

- The user does not have to review a full Plan.
- The work still has a Task identity and result.
- The user can inspect file changes and Audit if needed.

### 10.2 Larger Request To Plan

```text
User: "Build a polished personal website."
Plato: "This needs a plan. I will break it into reviewable tasks."
System drafts Plan / Task tree
Plato: "I created a plan with 5 tasks."
```

Acceptance:

- The user understands why Plan authoring happened.
- The plan is not hidden as background execution.

### 10.3 Ambiguous Request To Clarification

```text
User: "Deploy it."
Plato: "I need the deployment target before creating a task."
Options: Vercel / Netlify / GitHub Pages / Other
```

Acceptance:

- Plato does not guess a risky target.
- The question is scoped to the current Session, Plan, or Task.

### 10.4 Task-Scoped Follow-Up

```text
User selects a Task
User: "Do not touch CSS in this task."
Plato: "Recorded as guidance for this task."
```

Acceptance:

- The message appears in the Session timeline.
- The item is scoped to the selected Task.
- Future execution context can include the guidance.

---

## 11. Functional Requirements

### FR1. Session-Level Input And Timeline

Plato must support one primary natural-language input surface for the Session.
The visible timeline should show user inputs and Plato responses in order.

### FR2. Scoped Messages

Every message or activity item must carry Session, Plan, or Task scope when it
is created or projected.

### FR3. Natural-Language Interpretation Feedback

After input routing, Plato should show what it interpreted the input as and
what consequence it will have.

### FR4. Direct Task Route

Plato must support routing small executable requests into a Task without
requiring full visible Plan authoring.

### FR5. Plan Route

Plato must still route broad, ambiguous, multi-step, or high-risk work into
Plan authoring.

### FR6. Clarification Route

When routing or execution lacks required user-owned information, Plato should
ask a focused question instead of guessing.

### FR7. Activity Projection

User-visible conversation and activity items should be projected from product
facts where possible: input, route interpretation, Plan facts, Task facts, ASK,
confirmation, result, file summary, and recovery facts.

Activity projection must also expose meaningful Agent work phases, including
what the Agent is doing, why it is doing it, and what the user can expect next.

### FR8. State Authority Boundary

Messages must not be the authority for Plan state, Task state, ASK state,
confirmation state, result, file evidence, or Audit facts.

### FR9. Audit Linkage

Conversation items that summarize execution or evidence should link to Audit
or detailed evidence when available.

### FR10. Conversation Projection Boundary

Conversation must be a projection over existing Message Stream / Event /
domain facts. It must not introduce a second durable state authority for Plan,
Task, ASK, confirmation, result, file evidence, or Audit facts.

### FR11. Long Result Disclosure

Conversation must support short summaries and references for long Task results.
Full result text should be available through Activity, Detail, or Audit without
forcing the main Conversation layer to become a long result dump.

### FR12. Safe Markdown Rendering

Frontend message rendering must support safe Markdown for user-facing
Conversation, Activity preview, and Detail result text. Markdown support must
improve readability without allowing raw HTML/script execution or changing the
authority boundary of Message Stream / Event facts.

---

## 12. UX Requirements

1. The user can read the Session as a continuous story.
2. The UI can still expose Task Tree / Plan structure as the work control
   model.
3. Scope should be visible enough to understand context, but not so prominent
   that users must learn internal state names.
4. Direct Task should feel lightweight.
5. Plan-required work should clearly explain why a Plan is being created.
6. Activity messages should be concise and non-technical by default.
7. The user should be able to jump from a message to the related Task, Plan,
   result, file summary, or Audit entry.
8. The user should be able to tell what the Agent is doing now and why the
   current step exists.
9. Long results should remain accessible without overwhelming the Conversation
   layer.
10. Markdown-formatted messages should render readably and safely.

---

## 13. Success Criteria

This product slice is successful when:

1. A user can type a small request and see Plato respond naturally before or as
   a Direct Task is created.
2. A user can distinguish "Plato is answering me" from "Plato is creating work"
   from "Plato needs a Plan."
3. A Direct Task can complete without forcing the user through Plan review.
4. A larger request still enters Plan authoring.
5. Every visible response can be traced to Session, Plan, or Task scope.
6. The Main Page feels active and responsive without exposing raw Action /
   Observation logs.
7. Task-first control, result, file summary, and Audit remain intact.
8. Conversation reads like collaboration, not a stack of activity cards.
9. Activity makes Agent work legible enough that the user does not feel work is
   happening invisibly in the background.

---

## 14. Open Questions

1. Should Direct Task create an implicit Plan record for all cases, or only
   when later Plan Cycle features require it?
2. How many progress messages should execution produce before the timeline
   becomes noisy?
3. Should Direct Task execution start immediately by default, or should some
   low-risk tasks still ask for a quick confirmation?
4. How should the UI visually distinguish a Session message from a Plan or
   Task-scoped message without adding cognitive load?
5. Should the first version support user-visible routing correction, such as
   "Actually make this a plan" or "Just answer the question"?
6. Which Agent work phases should become explicit API fields versus frontend
   projection labels derived from existing events?

---

## 15. PRD-To-Implementation Handoff

Likely follow-up artifacts:

1. UX flow: Session conversation and Direct Task entry states.
2. API / contract update: scoped message / activity fields and Direct Task
   command response.
3. Runtime Input Router technical design update: add `direct_task` route.
4. Main Page frontend plan: conversation entry, latest response, and scoped
   timeline behavior.
5. Backend plan: Direct Task creation path and projection into Activity
   Timeline.
