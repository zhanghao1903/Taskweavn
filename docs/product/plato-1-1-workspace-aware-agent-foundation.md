# Plato Product 1.1 Focus Memo: Workspace-Aware Agent Foundation

> Status: focus memo / not an implementation plan
>
> Last Updated: 2026-06-07
>
> Related Baseline: [Plato Product 1.1 Plan](plato-1-1-product-plan.md)
>
> Scope: Product direction after the Product 1.0 closed loop. This memo
> narrows Product 1.1 around workspace-aware coding collaboration instead of
> broad platform expansion.

## 1. Decision

Product 1.1 should focus on making Plato reliable inside a real code
workspace.

The recommended Product 1.1 theme is:

```text
Workspace-aware coding agent foundation
```

Product 1.0 proves the Task-first closed loop:

```text
goal -> draft TaskTree -> publish -> execute -> ASK/confirmation -> result/file/audit
```

Product 1.1 should deepen that loop by giving the user and Agent a shared,
inspectable workspace surface:

- see what changed;
- inspect relevant files;
- apply safer line-scoped edits;
- answer or redirect work while it is running;
- ask read-only questions without mutating the workspace;
- prepare for skills without making the skill engine the center of 1.1.

This focus depends on four semantic baselines:

- [Plato Task Semantics](plato-task-semantics.md);
- [Plato Session Content Model](plato-session-content-model.md);
- [Plato Runtime Input Model](plato-runtime-input-model.md);
- [Plato Plan Cycle Semantics](plato-plan-cycle-semantics.md);
- [Plato Outcome Review Model](plato-outcome-review-model.md).

Implementation plans should use those documents as product meaning sources
before defining API, frontend, or backend behavior.

## 2. Primary Product 1.1 Bets

### 2.1 Git And Diff Support

Git and diff support should be the first 1.1 capability.

Why:

- Users need to trust what the Agent changed.
- Task result, file summary, and Audit evidence need a concrete diff source.
- Diff review is the natural bridge between execution and acceptance.

Minimum product surface:

- current repository status;
- changed file list;
- per-file diff view;
- staged versus unstaged distinction if available;
- task-to-file-change linkage;
- audit evidence references for changed files.

Not required in the first slice:

- full git history browser;
- branch management UI;
- merge conflict tooling;
- commit authoring automation.

### 2.2 Text File Viewing

Text file viewing should be the second 1.1 capability.

Why:

- The user and Agent need a shared object of attention.
- ASK, confirmation, result, and Audit flows are weaker if users cannot inspect
  referenced files.
- File viewing is a prerequisite for line-scoped editing, diff review, and
  read-only inquiry.

Minimum product surface:

- open a text file by path;
- show line numbers;
- support line-range loading;
- handle large files with truncation or paging;
- show unsupported/binary file fallback;
- link file views from result, file summary, and Audit records.

### 2.3 Tool Capability Upgrade

Product 1.1 should make file tools more precise and auditable.

Minimum tool direction:

- read file by line range;
- search within workspace;
- write or replace by line range;
- append to file;
- report changed line ranges;
- preserve before/after evidence for Audit.

Product requirement:

All file-writing tools must produce deterministic evidence that can be
projected into Main Page, Audit Page, and future diff views. Agent prose is not
the authority for what changed.

### 2.4 Runtime User Input Modes

Product 1.1 should support user input while work is running, but the product
must distinguish input intent.

Required distinction:

| Mode | Meaning | Product effect |
|---|---|---|
| Guidance | User gives additional preference, constraint, or clarification. | Enters context for the current Task or Session. Does not directly rewrite the Task plan. |
| Command | User changes execution state or task structure. | Goes through command handling: stop, retry, edit task, change priority, or modify plan. |
| ASK answer | User responds to an Agent question. | Resolves a durable ASK and may resume execution. |
| Confirmation response | User authorizes or rejects a known action. | Resolves a confirmation lifecycle. |
| Read-only inquiry | User asks a question about the workspace or current state. | Does not mutate TaskTree, TaskBus, or workspace. |

Product 1.1 should not treat every user message as chat. The same text input
surface may route to different modes, but the backend and UI must preserve the
distinction.

### 2.5 Read-Only Inquiry

Product 1.1 should support a mode where the user asks a question without
creating or modifying work.

Examples:

- "What does this file do?"
- "Is this diff risky?"
- "Why did this task fail?"
- "Which file should I inspect first?"

Minimum product behavior:

- no workspace writes;
- no TaskTree mutation;
- no TaskBus claim;
- may read files, diff, logs, and audit evidence;
- answer can optionally be converted into a Task later.

This capability prevents ordinary questions from polluting execution history
or forcing the user into a task workflow when they only need understanding.

### 2.6 Skills Integration

Skills are important, but Product 1.1 should treat them as a second-order
capability behind workspace and input-mode foundations.

Open product questions:

- What is the user-facing difference between Workflow, Skill, Agent, and Tool?
- Are skills selected by the user, inferred by the Collaborator, or both?
- How does a skill declare required tools, context needs, risks, and outputs?
- Can a skill be used only for read-only inquiry?
- How should skill usage appear in Audit?

Recommended Product 1.1 stance:

- define a skills contract and metadata model;
- support one or two internal skills if they directly improve workspace tasks;
- defer public skill marketplace, custom skill authoring UI, and broad skill
  routing until after the workspace foundation is stable.

## 3. Context Governance Assessment

Current Context Manager status:

- Session-scoped manager exists.
- Build requests are task-scoped through `session_id` and `task_id`.
- Task facts, execution state, ASK facts, event facts, workspace/file snippets,
  control facts, and guidance facts can be assembled for a specific Task.
- Cache-aware start/delta/checkpoint rendering exists for Product 1.0.

Current limitation:

- Task-level context is partially supported.
- Plan-level context is not a first-class governed model.
- Session-level long-lived memory governance remains minimal.
- Read-only inquiry context does not yet exist as a separate mode.

Product 1.1 should not jump directly to semantic memory or vector retrieval.
The next context step should be a clearer internal model:

```text
Session Context
  -> Task Context
  -> Plan Context
  -> Inquiry Context
```

### 3.1 Task Context

Task Context should remain the primary execution context.

It should include:

- task identity and objective;
- current execution status;
- relevant ASK/confirmation facts;
- recent tool results;
- selected file snippets;
- changed artifacts;
- interruption/retry facts;
- active guidance.

### 3.2 Plan Context

Plan Context should become a first-class Product 1.1 concept if runtime plan
editing becomes a priority.

It should include:

- current plan version;
- current step;
- completed steps;
- blocked steps;
- user guidance that influenced the plan;
- command history that modified the plan;
- relationship between plan steps and TaskNodes.

Do not implement Plan Context until the product decides whether runtime plan
editing is a Product 1.1 must-have or a later capability.

### 3.3 Inquiry Context

Inquiry Context should support read-only questions.

It should include:

- selected file or diff references;
- relevant Task/session metadata;
- selected Audit or result facts;
- explicit read-only controls;
- no write permissions by default.

Inquiry Context should not be rendered as a normal execution context. It has a
different product contract: answer the question, do not advance the Task.

## 4. Recommended 1.1 Sequencing

### Stage 1: Workspace Inspection

Goal: make changes and files visible.

Deliver:

- git status / diff contract;
- text file viewer contract;
- file/diff evidence model;
- Main/Audit entry points.

### Stage 2: Precision Tools

Goal: make file operations safer.

Deliver:

- line-range read;
- line-range replace;
- append;
- workspace search;
- changed-line evidence.

### Stage 3: Runtime Input Modes

Goal: let users intervene correctly while work is running.

Deliver:

- guidance versus command model;
- read-only inquiry mode;
- UI routing rules;
- context source updates.

### Stage 4: Skills Contract

Goal: prepare reusable capabilities without turning 1.1 into a platform
marketplace.

Deliver:

- skill metadata;
- capability/tool requirements;
- context requirements;
- risk/audit requirements;
- one narrow internal skill proof if needed.

## 5. Explicit Non-Goals For Early 1.1

- Public skill marketplace.
- Full custom Agent protocol productization.
- Multi-Agent routing as the main user-facing story.
- MCP-first product strategy.
- Full git client replacement.
- Merge conflict resolution UI.
- Rich binary/document/multimodal viewer.
- Semantic retrieval or vector memory as a prerequisite.
- Cross-session memory governance as a prerequisite.
- Result packaging cards as the first 1.1 milestone.

## 6. Planning Gates Before Implementation

Before turning this memo into implementation work, create focused plans for:

1. Git and diff product/API contract.
2. Text file viewer product/API contract.
3. Line-scoped tool contract and evidence model.
4. Runtime input modes: guidance, command, ASK, confirmation, inquiry.
5. Context governance extension: Task, Plan, and Inquiry Context boundaries.
6. Skills integration product contract.

Each plan must state:

- user-facing behavior;
- backend owner;
- frontend surface;
- audit evidence;
- permission/risk handling;
- tests and smoke path;
- what remains out of scope.

## 7. Product Principle

Product 1.1 should improve user trust before it expands automation breadth.

The user should be able to answer three questions at any time:

1. What is Plato doing?
2. What changed in my workspace?
3. How can I safely guide, stop, question, or redirect it?
