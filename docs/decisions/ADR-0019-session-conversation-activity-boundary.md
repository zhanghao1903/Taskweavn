# ADR-0019: Session Conversation And Activity Boundary

> Status: accepted
> Date: 2026-06-13
> Related: [Plato Contract Loop Product Model](../product/plato-contract-loop-model.md), [Plato Session Content Model](../product/plato-session-content-model.md), [Plato Runtime Input Model](../product/plato-runtime-input-model.md), [Contract Revision And Execution Loops](../architecture/contract-revision-and-execution-loops.md), [ADR-0015](ADR-0015-main-page-activity-overlay-message-history.md)

---

## Context

Plato keeps a natural-language input surface because users should not need to
learn internal command categories before asking for work. But a pure chat
product would compete directly with general coding assistants and would weaken
Plato's differentiator: explicit plans, controlled execution, evidence, and
auditability.

The product therefore needs an answer to three related questions:

1. where does the user see prior conversation;
2. how is conversation different from work control and audit;
3. how does every routed input remain understandable after the fact.

The accepted contract-loop model already says that user input enters the Plato
Session, not Collaborator directly. The missing decision is how the resulting
conversation and activity are exposed to users.

---

## Decision

Plato will model conversation as a Session-owned Conversation / Activity
timeline.

The Main Page remains work-first. Conversation is available as a secondary
Session view or drawer, with a lightweight Latest Activity entry on the main
work surface.

The timeline is typed, not a raw chat transcript.

```text
Session
  -> Work view
      Plan / Task / Result / Files / Audit links

  -> Conversation / Activity timeline
      User input
      Plato answer
      Guidance recorded
      Plan updated
      Task changed
      ASK / ASK answer
      Confirmation / response
      Execution update
      Result / recovery note
```

Every Runtime Input Router outcome should produce a user-readable activity
record that explains:

- what the user said;
- how Plato interpreted the input;
- what scope was affected;
- what changed, if anything;
- where the user can inspect the related Plan, Task, result, file, or audit
  evidence.

This does not mean every low-level event becomes visible conversation. The
timeline is a product projection over typed Session content and relevant facts.

---

## View Boundaries

### Work View

Work View answers:

```text
What is Plato doing, what is the plan, what task is active, and what can I do?
```

It owns Plan, Task, result, file summary, and current control actions.

### Conversation / Activity

Conversation / Activity answers:

```text
What did I tell Plato, how did Plato interpret it, and what consequence did it have?
```

It owns user-readable history of input, answers, guidance, plan/task changes,
ASK, confirmation, result notes, and recovery notes.

### Audit

Audit answers:

```text
Why is this trustworthy, and what evidence exists?
```

It owns precise evidence, tool/event/log/config refs, diagnostic links, and
traceability.

The three views may link to each other, but they must not collapse into one
surface.

---

## Exposure Rules

Default Conversation / Activity should show:

- user input;
- Plato answer;
- interpreted effect such as `Answer only`, `Guidance recorded`, `Plan
  updated`, `Task created`, or `Files will change through task execution`;
- affected scope: Session, Plan, or Task;
- linked Plan / Task / result / audit refs where relevant.

Default Conversation / Activity should not show:

- raw prompts;
- hidden reasoning;
- provider payloads;
- raw tool arguments;
- raw observations;
- full stdout/stderr by default;
- SQLite rows;
- raw EventStream records;
- full diagnostic logs.

Those belong in Audit or Diagnostics when policy allows.

---

## Consequences

Positive:

- Users can recover conversation history without making chat the primary
  product object.
- Runtime input becomes explainable: every input has a visible consequence.
- Work view stays focused on Plan/Task control.
- Audit remains the trust plane instead of becoming a general conversation
  transcript.
- Future Router and internal skill work has a clear projection obligation.

Tradeoffs:

- The product must maintain typed activity projection, not just render message
  rows.
- UI needs a careful secondary surface so conversation history is discoverable
  without competing with Plan/Task control.
- Activity records must avoid overwhelming users with low-level execution
  noise.

---

## Implementation Direction

Future implementation should add:

1. a typed Session Activity model or projection;
2. a Conversation / Activity query surface;
3. Latest Activity as the main work view entry point;
4. Router output records that include interpreted effect and affected scope;
5. links from activity items to Plan, Task, result, file, audit, or diagnostic
   refs.

It should not add:

- a pure chat-first Main Page;
- raw MessageStream rendering as the default conversation UI;
- direct workspace mutation from conversation;
- Audit as the primary chat history.
