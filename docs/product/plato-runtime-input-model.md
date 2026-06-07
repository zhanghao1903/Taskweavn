# Plato Runtime Input Model

> Status: product semantic baseline
>
> Last Updated: 2026-06-07
>
> Scope: user-facing and internal meaning of runtime text input after a Session
> exists. This is not an API contract, UX layout spec, or implementation plan.
>
> Related:
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Task Semantics](plato-task-semantics.md),
> [Workflow, Session, And Task UX Model](workflow-session-task-ux-model.md)

## 1. Core Decision

Users should not have to learn Plato's internal input categories before typing.

The primary UI should keep one natural language input surface. Internally,
Plato must classify the input because the product effects are fundamentally
different.

```text
one user input
  -> intent routing
  -> question / guidance / command / ASK answer / confirmation response
```

The UI may provide a secondary override menu, but the default path should be
`Auto`.

## 2. Why Input Intent Matters

The same text box can produce very different product effects:

- a question should not mutate the workspace;
- guidance should affect future context but not directly rewrite the plan;
- a command may stop execution, retry work, or change a plan;
- an ASK answer resolves missing information;
- a confirmation response authorizes or rejects a known action.

If these meanings are collapsed into ordinary chat, the user loses control and
the system loses auditability.

## 3. User-Facing Principle

The user sees:

```text
Ask, guide, or change what Plato is doing...
```

The system handles classification.

When the system is confident and no side effect is risky, it can proceed. When
the system is uncertain or the input has state-changing side effects, it should
show an interpretation and ask for confirmation or correction.

## 4. Internal Intent Types

| Intent | User meaning | Product effect |
|---|---|---|
| Question | User wants understanding. | Read-only answer. No Task, Plan, or workspace mutation by default. |
| Guidance | User adds context, preference, or constraint. | Enters Session, Plan, or Task context. Does not directly mutate structure. |
| Command | User wants Plato to change state or structure. | Goes through command handling. May change Plan, Task, execution, or Session state. |
| ASK answer | User responds to a blocking or non-blocking ASK. | Resolves ASK and may resume work. |
| Confirmation response | User authorizes, rejects, or chooses among known options. | Resolves confirmation lifecycle. |

## 5. Collaboration Scope

Input intent should combine with collaboration scope.

Allowed primary scopes:

```text
Session
Plan
Task
```

File, diff, audit record, result, message, ASK, and confirmation are references,
not first-class collaboration scopes.

Examples:

| Input | Intent | Scope | Reference |
|---|---|---|---|
| "What is the current overall status?" | Question | Session | none |
| "Use Chinese explanations in this Session." | Guidance | Session | none |
| "Make the plan simpler." | Command | Plan | current Plan |
| "Why is this step blocked?" | Question | Task | selected Task |
| "Do not refactor CSS in this task." | Guidance | Task | selected Task |
| "Stop this task." | Command | Task | selected Task |
| "Use Vite." | ASK answer | Task | active ASK |
| "Approve the file write." | Confirmation response | Task | active confirmation |

## 6. Auto Router Rules

The first Product 1.1 model should be hybrid, not LLM-only.

Recommended routing order:

1. **Active interaction first.** If there is an active ASK or confirmation and
   the input matches expected answer shape, route there.
2. **Explicit commands by rule.** Stop, retry, skip, publish, cancel, continue,
   and regenerate should be detected by deterministic rules where possible.
3. **UI selection context.** Selected Task, Plan area, result, or Audit entry
   can provide default scope and references.
4. **LLM classification for ambiguous input.** Use LLM classification only
   when deterministic context is insufficient.
5. **Safe fallback.** If confidence is low, prefer question or ask the user to
   confirm the interpretation. Do not mutate Plan, Task, or workspace on low
   confidence.

## 7. Secondary Override Menu

The input surface can expose a compact mode control:

```text
Auto
Ask
Guide
Change
```

This is an override, not the primary workflow. Ordinary users should not need
to select a mode before every message.

Suggested meanings:

- `Auto`: Plato classifies the input.
- `Ask`: force read-only question.
- `Guide`: force guidance/context update.
- `Change`: force command interpretation, subject to confirmation if needed.

## 8. Interpretation Feedback

After routing, the UI should expose a concise interpretation.

Examples:

- `Interpreted as: Question about current Task.`
- `Interpreted as: Guidance for this Session.`
- `Interpreted as: Command to stop current Task.`
- `Interpreted as: Answer to ASK.`

If the interpretation has side effects, the user should be able to confirm,
cancel, or change interpretation.

## 9. Side Effect Policy

Input effects should be explicit:

| Effect class | Examples | Required behavior |
|---|---|---|
| No effect | Read-only question. | Answer without mutation. |
| Context effect | Guidance. | Persist as guidance/context fact and display in Activity. |
| State effect | Stop, retry, edit plan, skip, publish. | Use command route, record command result, show status change. |
| Authorization effect | Confirmation response. | Resolve confirmation lifecycle. |
| Resume effect | ASK answer. | Persist answer before resume. |
| Evidence effect | Result/file/audit references generated after work. | Project to user-visible surfaces. |

Command-like input should never silently mutate state if the router is unsure.

## 10. Relationship To Session Content

Every accepted input should become typed Session content.

| Intent | Content type |
|---|---|
| Question | Question |
| Answer | Answer |
| Guidance | User guidance |
| Command | Command / recovery note / planning note depending on result |
| ASK answer | ASK answer |
| Confirmation response | Confirmation response |

This keeps Activity Stream explainable without exposing raw router internals.

## 11. Relationship To Plan Cycle

After a Plan Cycle is accepted, a new user input may mean:

- read-only question about the result;
- follow-up guidance for a future Plan;
- command to create a follow-up Plan;
- recovery command for failed Tasks;
- new independent goal that should create a new Session.

Product 1.1 should classify these cases explicitly instead of treating every
post-acceptance message as ordinary chat.

## 12. Non-Goals

Early Product 1.1 does not need:

- three separate primary input boxes;
- user-visible technical intent labels as required knowledge;
- full natural language command language;
- automatic workspace mutation from ambiguous text;
- skill routing before input intent routing;
- prompt-only intent handling without structured command results.

## 13. Product Invariants

1. One primary input surface is enough.
2. Internal intent distinction is mandatory.
3. The user can override intent when needed.
4. Low-confidence routing must not mutate state.
5. Side effects must be command-shaped, auditable, and visible.
6. Questions must support read-only answers.
7. Guidance must affect context without silently rewriting Plan or Task.
8. ASK and confirmation remain separate lifecycles.
