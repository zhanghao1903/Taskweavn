# Plato Session Content Model

> Status: product semantic baseline
>
> Last Updated: 2026-06-09
>
> Scope: user-facing meaning of Session content and its relationship to
> Session, Plan, Task, Activity, MessageStream, and Audit. This is not a UI
> layout spec, API contract, or implementation plan.
>
> Related:
> [Plato Task Semantics](plato-task-semantics.md),
> [Workflow, Session, And Task UX Model](workflow-session-task-ux-model.md),
> [Core Product Principles](core-product-principles.md),
> [Plan / TaskNode Model Technical Design](../plans/feature/plan-tasknode-model-technical-design.zh-CN.md)

## 1. Core Definition

Session content is a typed, scoped collaboration record.

It is not the Task itself and not raw chat. It explains Task intent, planning,
execution, user decisions, results, and recovery.

Task remains the work contract and state authority. Session content is the
user-readable narrative and interaction history around that contract.

Plan is the scoped work program inside a Session. Session content should attach
to Plan when the content is about this round of authoring, execution,
finalization, or outcome review.

## 2. Product Meaning

For a Task-first product, Session content answers:

1. Why does this work exist?
2. How did the user's intent become a Plan?
3. What did the user guide, ask, confirm, or reject?
4. What did Plato do while executing?
5. Why did the work pause, fail, retry, or recover?
6. What result and evidence were produced?
7. What can the user do next?

Session content is therefore the collaboration layer around Session, Plan, and
Task. It should not become the primary product object.

```text
Plan = scoped work program and context-management boundary
Task = work contract and state authority inside a Plan
Session content = collaboration narrative around Plan and Task contracts
Audit = evidence trace behind the contracts
```

## 3. What Session Content Is Not

Session content is not:

- raw LLM output;
- a raw chat transcript;
- a replacement for Task status;
- a replacement for Audit records;
- a dump of tool calls or logs;
- the source of truth for execution state.

Raw LLM output can influence product facts, but it should not be displayed as
the primary user-facing Session content without projection, classification, or
summarization.

## 4. Collaboration Scope Model

The main collaboration scopes should stay small:

```text
Session
Plan
Task
```

The user should not need to think in file, diff, event, or audit scopes when
collaborating with Plato. Those objects can be referenced, but they are not the
primary collaboration objects.

| Scope | User meaning | Examples |
|---|---|---|
| Session | This collaboration run. | Original goal, session-wide preference, overall progress question. |
| Plan | This round of organized work. | Revise plan, split steps, simplify sequence, review outcome, start follow-up plan. |
| Task | A concrete work contract inside the plan. | Add guidance, answer ASK, resolve confirmation, retry, inspect result. |

Plan scope is especially important because a long Session may contain multiple
Plans. A user can ask about the Session, but most actionable collaboration
should attach to the active Plan or a selected TaskNode.

## 5. References Are Not Scopes

File, diff, audit record, result, ASK, confirmation, and message objects should
be treated as references.

```text
intent + collaboration_scope + optional_reference
```

Examples:

| User input | Intent | Scope | Reference |
|---|---|---|---|
| "What changed in this diff?" | question | Task | diff |
| "Why did this file change?" | question | Task | file change summary |
| "Do not touch CSS in this task." | guidance | Task | selected Task |
| "Make the plan frontend-first." | command | Plan | current Plan |
| "Summarize what this plan achieved." | question | Plan | Plan outcome |
| "Start the next plan from these results." | command | Plan / Session | accepted Plan |
| "Explain the overall status." | question | Session | none |

This keeps the product model centered on collaboration rather than low-level
workspace objects.

## 6. Typed Content Taxonomy

Session content should be typed. Type is what prevents Activity Stream from
degrading into raw chat.

| Type | Meaning | Typical scope | State effect |
|---|---|---|---|
| User intent | Original user goal or follow-up goal. | Session / Plan | May create RawTask or Plan authoring. |
| Planning note | User-readable note about interpretation or plan generation. | Plan | Explains plan state. |
| Plan summary | User-readable summary of the current Plan. | Plan | Explains scope, progress, and outcome. |
| Plan finalization note | Summary, validation, integration, or context-compression output after TaskNode execution. | Plan | May prepare outcome review or follow-up authoring. |
| User guidance | Constraint, preference, or additional context. | Session / Task | Affects future context, not direct structure. |
| Question | User asks for understanding. | Session / Plan / Task | No state mutation by default. |
| Answer | Plato answers a read-only question. | Session / Plan / Task | No state mutation by default. |
| ASK | Plato needs missing user-owned information. | Task | Blocks or guides execution. |
| ASK answer | User supplies missing information. | Task | Resolves ASK and may resume execution. |
| Confirmation | Plato knows the action but needs authorization. | Task | Blocks side-effecting action. |
| Confirmation response | User authorizes, rejects, or chooses an option. | Task | Resolves authorization lifecycle. |
| Execution update | User-readable progress or process summary. | Task | Describes execution facts. |
| Result summary | User-readable outcome. | Task / Session | Summarizes terminal facts. |
| File summary | User-readable workspace change summary. | Task / Session | Summarizes evidence. |
| Recovery note | Failure, stop, retry, or recovery explanation. | Task / Session | Explains recovery path. |
| Activity interpretation | User-readable explanation of how an input was routed and what consequence it had. | Session / Plan / Task | Explains the Router outcome; state authority belongs to underlying facts. |

Plan-level content may be produced by Collaborator, reviewer, summarizer, audit,
or context-management agents. It should still be projected into typed content
rather than displayed as raw model output.

## 7. State Authority Rule

Session content may explain state, but it does not own state.

State authority belongs to:

- Session lifecycle facts;
- Plan lifecycle facts;
- Plan finalization facts;
- Task lifecycle facts;
- ASK facts;
- confirmation facts;
- result summaries;
- file summaries;
- audit records.

Activity Stream and message projections should be derived from those facts where
possible. If a visible content item conflicts with a canonical fact, the
canonical fact wins.

## 8. Display Boundaries

### 8.0 Work View, Conversation, And Audit

Session has three related but distinct user surfaces:

| Surface | User question | Primary content |
|---|---|---|
| Work view | What is Plato doing, what is the plan, and what can I control now? | Plan, Task, result, file summary, current actions. |
| Conversation / Activity | What did I tell Plato, how did it interpret that, and what consequence did it have? | User inputs, answers, guidance, Plan/Task changes, ASK, confirmation, result/recovery notes. |
| Audit | Why is this trustworthy, and what evidence exists? | Event, tool, evidence, log, config, diagnostic refs. |

The Main Page should stay work-first. A Latest Activity summary can expose the
most recent activity, while a Conversation / Activity drawer or secondary view
can expose the full typed history.

### 8.1 Main Page Activity

Main Page Activity is the user-readable session narrative.

It should show:

- user intent;
- interpreted input effect;
- affected scope;
- plan ready / plan revised;
- task started / paused / completed / failed;
- ASK required;
- confirmation required;
- result summary;
- file summary;
- recoverable error;
- suggested next action.

It should not show:

- raw LLM output;
- full tool payloads;
- internal bus events;
- complete audit trace;
- verbose logs.

### 8.2 Task Detail Activity

Task Detail should show the content relevant to the selected Task.

It should show:

- Task intent and plan fragment;
- Task-specific guidance;
- active ASK or confirmation;
- execution updates;
- result summary;
- file summary;
- recovery options;
- links to evidence or audit.

### 8.3 Plan Activity

Plan Activity should show how the current plan was created or changed.

It should show:

- original goal;
- planning notes;
- Plan-level constraints and context policy when user-visible;
- plan revision requests;
- plan acceptance;
- transition from plan to execution;
- Plan finalization progress;
- Plan outcome summary;
- follow-up plan creation when Product 1.1 supports it.

### 8.4 Audit

Audit remains the trust plane.

Audit can display precise evidence and references, but its records should not
become the primary collaboration surface. Main Page and Task Detail should link
to Audit when the user needs proof, not force proof into every activity item.

## 9. Relationship To MessageStream

The backend may keep one Session message stream. The product should not expose
that stream as raw chat by default.

MessageStream can be a storage or transport substrate for:

- user-visible communication;
- actionable prompts;
- responses;
- process summaries;
- result summaries.

The UI should project typed views from MessageStream and other facts:

```text
MessageStream + Plan facts + Task facts + ASK facts + confirmation facts + result facts
  -> Activity Stream
  -> Conversation / Activity timeline
  -> Task Detail Activity
  -> Plan Activity
```

Conversation / Activity is therefore a projection, not a table dump. It should
preserve user-readable chat history while making each item explicit about
scope, effect, and related product facts.

## 10. Relationship To Plan Cycles

When a Session supports multiple rounds of planning and execution, content
should attach to a Plan when applicable.

```text
Session
  -> Plan
      -> Plan content
      -> Task content
      -> Outcome content
```

This lets the user continue a Session after accepting an outcome without
mixing the old plan and the new follow-up plan into one ambiguous thread.

Plan content should include enough information for the next Plan to be authored
without relying on raw chat:

- original Plan goal;
- accepted TaskNode list;
- TaskNode outcomes;
- file-change rollups;
- unresolved questions and warnings;
- user acceptance or follow-up decision;
- context-compression summary for Collaborator.

## 11. Product Invariants

1. Session content is typed and scoped.
2. Session content is not raw chat, but it can project a typed conversation
   history.
3. Task remains the work contract and state authority.
4. Plan is the scoped work program and context-management boundary.
5. Activity explains what happened in user-readable form.
6. File, diff, result, audit, ASK, and confirmation are references unless they
   also represent a Task or Plan interaction.
7. Raw LLM output should not be the default visible artifact.
8. Every visible content item should make clear whether it changes nothing,
   changes context, changes state, or reports evidence.
9. Plan-level summary, validation, integration, and context-compression content
   belongs to Plan scope, not raw Session chat.
10. Every routed runtime input should have a user-readable activity
    interpretation unless it is fully internal and invisible by policy.
