# Plato Contract Loop Product Model

> Status: product semantic baseline
>
> Last Updated: 2026-06-13
>
> Related Architecture:
> [Contract Revision And Execution Loops](../architecture/contract-revision-and-execution-loops.md)
>
> Related:
> [Core Product Principles](core-product-principles.md),
> [Plato Runtime Input Model](plato-runtime-input-model.md),
> [Plato Session Content Model](plato-session-content-model.md),
> [Plato Plan Cycle Semantics](plato-plan-cycle-semantics.md),
> [Plato Task Semantics](plato-task-semantics.md)

This document defines Plato's product answer to natural-language input and the
user's world: users are not chatting with a generic assistant; they are shaping
and executing an explicit work contract with Plato.

---

## 1. Core Product Belief

Plato understands user work through two loops:

```text
Contract Revision Loop
  "What should Plato understand, plan, change in the task contract, or ask?"

Contract Execution Loop
  "Now execute the accepted contract and show evidence of what changed."
```

This distinction is foundational. Future Product 1.1+ features should return
to it before adding new Agents, skills, MCP integrations, input modes, memory,
or workspace tools.

---

## 2. What Is The Contract?

The contract is the user-visible agreement about work.

It can include:

- the Session goal;
- the current Plan;
- TaskNodes and their instructions;
- constraints and preferences;
- guidance added by the user;
- ASK answers;
- confirmation responses;
- selected references such as files, diffs, audit records, or results;
- execution policy and recovery choices.

The contract is not:

- raw chat;
- raw prompt text;
- provider output;
- hidden Agent memory;
- workspace files themselves;
- terminal output;
- audit logs or SQLite rows.

Workspace files are the user's world. The contract says what Plato is allowed
to do in that world.

---

## 3. User Input Meanings

The same text box can express different meanings.

| User meaning | Product interpretation | Loop |
|---|---|---|
| "Explain this." | Read-only question | Contract Revision Loop, no mutation |
| "Use this requirement." | Guidance | Contract Revision Loop |
| "Change this task." | Contract edit | Contract Revision Loop |
| "Add/remove a step." | Plan/TaskNode edit | Contract Revision Loop |
| "Answer this question." | ASK answer | Contract Revision Loop |
| "Approve/reject this action." | Confirmation response | Contract Revision Loop |
| "Modify the project files." | Execution request | Revision Loop creates/updates executable work, then Execution Loop |

The user may type naturally. The product must classify the intent, show enough
interpretation to keep the user in control, and preserve the right boundary.

---

## 4. Who Is The User Talking To?

The user is talking to the Plato Session, not directly to Collaborator,
Execution Agent, or a file tool.

Internally:

```text
User input
  -> Interaction Router
  -> Inquiry / Guidance / Plan edit / ASK / Confirmation / TaskBus request
```

Collaborator is one capability inside the Contract Revision Loop. It can help
author or revise Plans, but it is not the universal owner of chat.

Execution Agents are capabilities inside the Contract Execution Loop. They can
read and write the workspace only while executing accepted work.

---

## 5. Workspace Change Rule

User input may request a workspace change, but it must not directly mutate the
workspace from the chat box.

Required product path:

```text
User asks for workspace change
  -> interpreted as execution request
  -> creates or updates Plan/TaskNode contract
  -> enters TaskBus execution
  -> Agent changes workspace under task authority
  -> result, file evidence, audit, and diagnostics are projected
```

This rule protects:

- user control;
- task identity;
- retry and recovery;
- file evidence;
- audit explainability;
- outcome review;
- future skill and MCP governance.

---

## 6. Guidance Rule

Guidance changes Plato's understanding. It does not directly change the
workspace.

Examples:

- "Use a concise tone."
- "Do not refactor CSS in this task."
- "Prefer Vite examples."
- "This session is for a Chinese teaching courseware project."

Guidance should become typed Session, Plan, or Task context. It may influence
future Collaborator or Execution Agent behavior, but it is not a file edit and
not a hidden prompt-only note.

If guidance would change Plan or TaskNode structure, it should become a
contract edit. If it would change workspace files, it should become an
execution request.

---

## 7. Inquiry Rule

Questions are allowed without creating work.

Examples:

- "What changed in this diff?"
- "Why did this task fail?"
- "Which file should I inspect first?"
- "Is this risky?"

Read-only inquiry may inspect selected files, diffs, audit records, results, or
diagnostics under policy. It must not mutate Plan, TaskBus, or workspace state.

An answer can include an explicit next action, such as:

```text
Use this as guidance
Create follow-up task
Revise the plan
```

Those next actions are separate contract revisions.

---

## 8. Contract Edit Rule

Changing Plan or TaskNode structure is a product-state change.

Examples:

- rename a TaskNode;
- tighten acceptance criteria;
- split a task;
- add a validation step;
- delete a no-longer-needed step;
- reorder tasks.

These changes should feel conversational, but they must be command-backed:

```text
user input -> interpreted contract edit -> command -> updated Plan/TaskNode
```

The product should show the resulting contract change in the control plane.

---

## 9. Execution Rule

Execution changes the user's workspace or produces artifacts.

Examples:

- edit files;
- run tests;
- generate a document;
- call an external tool;
- package a release.

Execution belongs to TaskBus and Execution Agents. It must produce user-visible
status, result, file evidence, and audit records.

If execution needs more information, it asks. If execution needs permission, it
requests confirmation. If execution discovers the contract is wrong, it returns
to the Contract Revision Loop with a proposal or recovery request.

---

## 10. Product Design Implications

The Main Page input should not be modeled as "chat with Collaborator." It is a
Session input surface.

Product principle:

```text
Natural input, explicit consequence.
```

The product should communicate effects rather than internal machinery:

| If the input was... | Product should show... |
|---|---|
| read-only question | answer with evidence refs |
| guidance | guidance recorded and target scope |
| Plan/Task edit | changed contract fields |
| workspace change request | task created/updated and ready/running state |
| ASK answer | ASK resolved and work may resume |
| confirmation response | action approved/rejected and resulting state |

The user should not need to know whether the Router used rules, an LLM, or
internal skills. The user should understand what effect their input had.

---

## 11. Conversation / Activity Timeline

Plato should keep a conversation history, but the history is not the product's
primary object.

Session owns a typed Conversation / Activity timeline:

```text
User input
  -> interpreted effect
  -> affected scope
  -> linked Plan / Task / result / audit refs
```

The Main Page should remain work-first. It may show a Latest Activity summary
and offer a Conversation / Activity drawer or secondary view for full history.

Conversation / Activity should answer:

```text
What did I tell Plato, how did Plato interpret it, and what consequence did it have?
```

It should not answer the Audit question:

```text
What exact evidence proves this happened?
```

That remains the Audit plane.

Default activity records should include:

- user-visible input;
- answers;
- guidance recorded;
- Plan or Task changes;
- ASK and ASK answer;
- confirmation and response;
- execution update;
- result, file summary, or recovery note.

Default activity records should not expose raw prompts, hidden reasoning,
provider payloads, raw tool arguments, raw observations, EventStream rows, or
diagnostic logs.

---

## 12. Future Feature Test

Before adding a future feature, answer:

1. Does it revise the contract?
2. Does it execute the contract?
3. Does it only answer a question?
4. Which state can it mutate?
5. Which evidence or audit record proves what happened?
6. Can the user see and recover from the result?
7. What Conversation / Activity record explains the user-visible consequence?

If the answer is unclear, the feature needs a product/architecture decision
before implementation.
